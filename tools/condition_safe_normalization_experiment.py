"""Opt-in safe draft-v1 subset. No gold access, API, or production extractor hook."""
from __future__ import annotations
import copy
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from tools import extract_condition_candidates_llm as llm

ROOT=Path(__file__).resolve().parents[1]
CONTRACT=ROOT/'schemas/conditions/contracts/draft-v1'
VALUE=json.loads((CONTRACT/'value_normalization_contract_v1.json').read_text(encoding='utf-8'))
ATTR=json.loads((CONTRACT/'attribute_semantic_contract_v1.json').read_text(encoding='utf-8'))
ATTRS={a['canonical_field']:a for a in ATTR['attributes']}
VERSION='safe-condition-normalization-subset-v1'
EXPERIMENTS={'N0':[], 'N1':['UNIT'], 'N2':['NUMERIC','MONEY'], 'N3':['RANGE'],
             'N4':[], 'N5':['UNIT','NUMERIC','MONEY','RANGE']}
NUMBER=r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
def decimal(value):
    if isinstance(value,bool) or not isinstance(value,(str,int,float)):raise ValueError('NOT_NUMERIC')
    text=str(value)
    if not re.fullmatch(NUMBER,text):raise ValueError('INVALID_NUMERIC_LITERAL')
    result=Decimal(text.replace(',',''))
    if not result.is_finite():raise ValueError('NONFINITE_NUMBER')
    return result
def json_number(value):
    if value==value.to_integral_value():return int(value)
    result=float(value)
    if Decimal(str(result))!=value:raise ValueError('LOSSY_JSON_NUMBER')
    return result
def snapshot(condition):
    return {k:copy.deepcopy(condition.get(k)) for k in ['field','category_id','operator','value','value_type','unit']}
def normalize(condition,experiment,source_text):
    """Returns a new proposal plus change and refusal records; never invents fields."""
    if experiment not in EXPERIMENTS:raise ValueError('UNKNOWN_EXPERIMENT')
    out=copy.deepcopy(condition);events=[];refusals=[]
    canonical,_,attribute_reason=llm.normalize_condition_attribute(condition)
    field=canonical.get('field');profile=ATTRS.get(field,{}).get('value_profile')
    def refuse(rule,reason):
        refusals.append({'rule_id':rule,'reason':reason,'status':'NO_TRANSFORM_POLICY_HOLD',
                         'original':snapshot(condition),'source_evidence':condition.get('evidence_quotes',[])})
    def record(rule,before,reason):
        if before!=snapshot(out):events.append({'rule_id':rule,'reason':reason,'before':before,'after':snapshot(out)})
    # N4 deliberately delegates to v2 at the shared validation stage in every arm.
    # Its case-only rules already cover every EXACT_ALIAS in draft-v1.
    if experiment in ['N0','N4']:return out,events,refusals
    quotes=condition.get('evidence_quotes',[])
    if not quotes or any(not isinstance(q,str) or source_text.count(q)!=1 for q in quotes):
        refuse('EVIDENCE_PREFLIGHT','SOURCE_QUOTE_NOT_UNIQUE_OR_MISSING');return out,events,refusals
    if attribute_reason:
        refuse('ATTRIBUTE_PREFLIGHT',attribute_reason);return out,events,refusals
    text='\n'.join(quotes);rules=EXPERIMENTS[experiment]
    unit=out.get('unit')
    if 'UNIT' in rules and unit is not None:
        target=VALUE['unit_aliases'].get(unit)
        if target and target!=unit:
            if target not in ATTRS[field]['allowed_units']:
                refuse('UNIT_EXACT_V1','ATTRIBUTE_UNIT_DIMENSION_MISMATCH')
            elif not re.search(NUMBER+r'\s*'+re.escape(unit)+r'(?![A-Za-z])',text):
                refuse('UNIT_EXACT_V1','EXPLICIT_UNIT_NOT_IN_EVIDENCE')
            else:
                before=snapshot(out);out['unit']=target;record('UNIT_EXACT_V1',before,'Explicit same-dimension unit alias in source')
        elif target is None:refuse('UNIT_EXACT_V1','UNIT_NOT_IN_SAFE_SUBSET')
    if 'NUMERIC' in rules and isinstance(out.get('value'),str) and profile in ['age','duration','percent','persons','money']:
        if out.get('operator') in ['EQ','NEQ','GT','GTE','LT','LTE']:
            try:
                n=decimal(out['value'])
                if not any(decimal(m.group())==n for m in re.finditer(NUMBER,text)):raise ValueError('NUMERIC_VALUE_NOT_IN_EVIDENCE')
                if n<0 or (profile=='persons' and n!=n.to_integral_value()):raise ValueError('INVALID_QUANTITY')
                before=snapshot(out);out['value']=json_number(n);out['value_type']='NUMBER'
                record('NUMERIC_SCALAR_V1',before,'Known quantitative field and identical numeric source literal')
            except (ValueError,InvalidOperation) as exc:refuse('NUMERIC_SCALAR_V1',str(exc))
    if 'MONEY' in rules and profile=='money' and out.get('unit') in VALUE['money_units']:
        rule=VALUE['money_units'][out['unit']]
        if out['unit']!=rule['target']:
            try:
                if out.get('value_type')!='NUMBER':raise ValueError('MONEY_REQUIRES_SCALAR_NUMBER')
                n=decimal(out['value'])
                matches=list(re.finditer('('+NUMBER+r')\s*'+re.escape(out['unit']),text))
                if not matches or not any(decimal(m.group(1))==n for m in matches):raise ValueError('MONEY_AMOUNT_AND_UNIT_NOT_IN_EVIDENCE')
                if n<0:raise ValueError('NEGATIVE_AMOUNT_REQUIRES_REVIEW')
                before=snapshot(out);out['value']=json_number(n*Decimal(rule['multiplier']));out['unit']=rule['target']
                record('MONEY_SCALE_V1',before,'Explicit currency and exact Decimal magnitude conversion; no FX')
            except (ValueError,InvalidOperation) as exc:refuse('MONEY_SCALE_V1',str(exc))
    if 'RANGE' in rules and out.get('operator')=='BETWEEN':
        value=out.get('value')
        if not isinstance(value,dict):refuse('RANGE_EXPLICIT_FLAGS_V1','RANGE_OBJECT_REQUIRED')
        elif set(value)=={'lower','upper'}:pass
        else:
            keys=('minimum','maximum') if 'minimum' in value else ('min','max')
            allowed={*keys,'min_inclusive','max_inclusive'}
            if set(value)!=allowed or type(value.get('min_inclusive')) is not bool or type(value.get('max_inclusive')) is not bool:
                refuse('RANGE_EXPLICIT_FLAGS_V1','BOUNDARY_FLAGS_NOT_EXPLICIT')
            else:
                try:
                    lo,hi=decimal(value[keys[0]]),decimal(value[keys[1]])
                    if lo>hi or (lo==hi and not(value['min_inclusive'] and value['max_inclusive'])):raise ValueError('EMPTY_RANGE')
                    # Require source inequalities too; flags alone are an LLM claim.
                    lo_token='이상' if value['min_inclusive'] else '초과'
                    hi_token='이하' if value['max_inclusive'] else '미만'
                    lower_ok=re.search(re.escape(str(value[keys[0]]))+r'\s*(?:세|년|개월|명|%)?\s*'+lo_token,text)
                    upper_ok=re.search(re.escape(str(value[keys[1]]))+r'\s*(?:세|년|개월|명|%)?\s*'+hi_token,text)
                    if not(lower_ok and upper_ok):raise ValueError('SOURCE_BOUNDARY_MEANING_NOT_CONFIRMED')
                    before=snapshot(out);out['value']={'lower':{'value':json_number(lo),'inclusive':value['min_inclusive']},
                        'upper':{'value':json_number(hi),'inclusive':value['max_inclusive']}};out['value_type']='RANGE'
                    record('RANGE_EXPLICIT_FLAGS_V1',before,'Both original flags and source inequalities agree')
                except (ValueError,InvalidOperation) as exc:refuse('RANGE_EXPLICIT_FLAGS_V1',str(exc))
    return out,events,refusals

def specification():
    return {'version':VERSION,'status':'EXPERIMENT_ONLY_NOT_DEPLOYED','experiments':EXPERIMENTS,
        'order':['UNIT','NUMERIC','MONEY','RANGE','SHARED_ATTRIBUTE_NORMALIZATION_V2'],
        'unit_aliases':VALUE['unit_aliases'],'money_units':VALUE['money_units'],
        'range':'Explicit flags and source inequalities only; no inferred boundaries',
        'N4':'NO_CHANGE: all EXACT_ALIAS already handled by existing attribute-normalization-v2',
        'excluded':['Semantic field mapping','Region/category rewrites','Boundary invention','UNKNOWN operator repair',
                    'Case-specific rules','Currency FX','Categorical code guessing'],
        'input_scope':'LLM intermediate schema, not legacy GraphRAG containers',
        'contract_hashes':{name:hashlib.sha256((CONTRACT/name).read_bytes()).hexdigest() for name in
            ['attribute_semantic_contract_v1.json','value_normalization_contract_v1.json','attribute_mapping_policy_v1.csv']}}
