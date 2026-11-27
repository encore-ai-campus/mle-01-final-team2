"""Synthetic contract-design checks; no production normalization or evaluation."""
import argparse
import ast
import copy
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import io
import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def read(name):return json.loads((HERE/name).read_text(encoding='utf-8'))
ATTR=read('attribute_semantic_contract_v1.json')
VALUE=read('value_normalization_contract_v1.json')
BY_FIELD={row['canonical_field']:row for row in ATTR['attributes']}
ALIASES={alias:row['canonical_field'] for row in ATTR['attributes'] for alias in row['aliases']}

def alias_proposal(field,category,entity,ambiguous=False):
    """Design-only oracle for the documented safe subset; never imported by extractors."""
    canonical=field if field in BY_FIELD else ALIASES.get(field)
    if not canonical:return 'HOLD_UNSUPPORTED',None
    if category!=canonical:return 'HOLD_CATEGORY_MISMATCH',None
    if entity!=BY_FIELD[canonical]['entity_scope'] or ambiguous:return 'HOLD_SEMANTICS',None
    return 'NORMALIZATION_CANDIDATE',canonical

def number(value):
    if isinstance(value,bool):raise ValueError('BOOL_NOT_NUMBER')
    result=Decimal(str(value))
    if not result.is_finite():raise ValueError('FINITE_NUMBER_REQUIRED')
    return result

def unit_proposal(value,unit,profile):
    n=number(value)
    if profile=='money' and unit in VALUE['money_units']:
        rule=VALUE['money_units'][unit]
        return n*Decimal(rule['multiplier']),rule['target']
    canonical=VALUE['unit_aliases'].get(unit)
    if not canonical:raise ValueError('UNRESOLVED_UNIT')
    return n,canonical

def range_proposal(legacy):
    if set(legacy)!={'minimum','maximum','min_inclusive','max_inclusive'}:raise ValueError('BOUNDARIES_REQUIRED')
    lo,hi=number(legacy['minimum']),number(legacy['maximum'])
    if type(legacy['min_inclusive']) is not bool or type(legacy['max_inclusive']) is not bool:raise ValueError('BOUNDARIES_REQUIRED')
    if lo>hi or (lo==hi and not (legacy['min_inclusive'] and legacy['max_inclusive'])):raise ValueError('EMPTY_INTERVAL')
    return {'lower':{'value':legacy['minimum'],'inclusive':legacy['min_inclusive']},
            'upper':{'value':legacy['maximum'],'inclusive':legacy['max_inclusive']}}

def compatible(field,operator,value,value_type,unit=None):
    attribute=BY_FIELD[field]
    if operator not in attribute['allowed_operators'] or value_type not in attribute['allowed_value_types']:return False
    if unit is not None and unit not in attribute['allowed_units']:return False
    if operator in ['EXISTS','NOT_EXISTS',None]:return value is None and value_type=='UNKNOWN' and unit is None
    if operator in ['IN','NOT_IN']:
        return value_type=='ARRAY' and isinstance(value,list) and len(value)>0 and all(isinstance(v,str) for v in value)
    if operator=='BETWEEN':
        if value_type!='RANGE' or not isinstance(value,dict) or set(value)!={'lower','upper'}:return False
        try:
            lo,hi=value['lower'],value['upper']
            range_proposal({'minimum':lo['value'],'maximum':hi['value'],'min_inclusive':lo['inclusive'],'max_inclusive':hi['inclusive']})
        except (KeyError,ValueError,InvalidOperation):return False
        return unit is not None
    if value_type=='NUMBER':
        try:n=number(value)
        except (ValueError,InvalidOperation):return False
        if attribute['value_profile']=='persons' and (n<0 or n!=n.to_integral_value()):return False
        if attribute['value_profile'] in ['age','duration','percent'] and n<0:return False
        return type(value) in [int,float] and unit is not None
    if value_type=='BOOLEAN':return type(value) is bool and operator in ['EQ','NEQ']
    if value_type=='STRING':return isinstance(value,str) and len(value)>0 and operator in ['EQ','NEQ']
    return False

def check_logic(node,known):
    if node['kind']=='REF':return node['id'] in known
    children=node['children'];op=node['operator']
    return op in ['AND','OR','NOT','UNRESOLVED'] and (len(children)==1 if op=='NOT' else len(children)>=2) and all(check_logic(child,known) for child in children)

class ContractTests(unittest.TestCase):
    def test_structure_required_definitions(self):
        schema={'type':'object','required':['contract_version','status','attributes'],
            'properties':{'status':{'const':'DRAFT_NOT_DEPLOYED'},'attributes':{'type':'array','minItems':22,'maxItems':22,
              'items':{'type':'object','required':['canonical_field','category_id','description_ko','description_en','entity_scope',
              'allowed_condition_types','allowed_operators','allowed_value_types','allowed_units','aliases',
              'normalization_policy','ambiguity_policy','examples','counterexamples','definition_source']}}}}
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(ATTR)),[])
        for row in ATTR['attributes']:
            self.assertEqual(row['canonical_field'],row['category_id'])
            self.assertTrue(row['description_ko'] and row['description_en'] and row['definition_source'])
            self.assertTrue(row['examples'] and row['counterexamples'])
    def test_existing_catalog_coverage_and_no_expansion(self):
        tree=ast.parse((ROOT/'tools/extract_condition_candidates_llm.py').read_text(encoding='utf-8'))
        catalog=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ATTRIBUTE_CATALOG' for t in n.targets))
        self.assertEqual(set(BY_FIELD),catalog)
        self.assertFalse({x['canonical_field'] for x in ATTR['new_attribute_candidates']} & catalog)
    def test_no_duplicate_fields_or_aliases(self):
        self.assertEqual(len(ATTR['attributes']),len(BY_FIELD))
        all_aliases=[a for row in ATTR['attributes'] for a in row['aliases']]
        self.assertEqual(len(all_aliases),len(set(all_aliases)))
        self.assertEqual(len({f.casefold() for f in BY_FIELD}),len(BY_FIELD))
    def test_mapping_only_exact_is_automatic(self):
        rows=list(csv.DictReader((HERE/'attribute_mapping_policy_v1.csv').open(encoding='utf-8-sig')))
        self.assertTrue(all((r['automatic_candidate']=='True')==(r['relationship']=='EXACT_ALIAS') for r in rows))
        automatic={r['source_field']:r['target_field'] for r in rows if r['automatic_candidate']=='True'}
        self.assertEqual(automatic,ALIASES)
        self.assertTrue(all(target in BY_FIELD for target in automatic.values()))
    def test_case_alias_safe_candidate(self):
        self.assertEqual(alias_proposal('business_location','BUSINESS_LOCATION','BUSINESS_SITE'),('NORMALIZATION_CANDIDATE','BUSINESS_LOCATION'))
    def test_entity_mismatch_held(self):
        self.assertEqual(alias_proposal('business_location','BUSINESS_LOCATION','APPLICANT_PERSON')[0],'HOLD_SEMANTICS')
    def test_category_mismatch_held(self):
        self.assertEqual(alias_proposal('applicant_address','BUSINESS_LOCATION','APPLICANT_PERSON')[0],'HOLD_CATEGORY_MISMATCH')
    def test_upper_and_lower_semantic_ambiguity_held(self):
        for field in ['APPLICANT_TYPE','applicant_type']:
            self.assertEqual(alias_proposal(field,'APPLICANT_TYPE','APPLICANT',True)[0],'HOLD_SEMANTICS')
    def test_team_member_not_representative(self):
        self.assertEqual(alias_proposal('team_member_age','REPRESENTATIVE_AGE','REPRESENTATIVE_PERSON')[0],'HOLD_UNSUPPORTED')
    def test_address_not_document(self):
        self.assertNotEqual(BY_FIELD['APPLICANT_ADDRESS']['entity_scope'],BY_FIELD['DOCUMENT_SUBMISSION']['entity_scope'])
        self.assertEqual(alias_proposal('residence_proof','APPLICANT_ADDRESS','APPLICANT_PERSON')[0],'HOLD_UNSUPPORTED')
    def test_duration_units(self):
        self.assertEqual(unit_proposal(2,'년','duration'),(Decimal(2),'YEAR'))
        self.assertEqual(unit_proposal(5,'개월','duration'),(Decimal(5),'MONTH'))
        self.assertNotEqual(unit_proposal(1,'년','duration'),unit_proposal(12,'개월','duration'))
    def test_percent_not_fraction_inference(self):
        self.assertEqual(unit_proposal(15,'%','percent'),(Decimal(15),'PERCENT'))
        self.assertEqual(unit_proposal('0.15','PERCENT','percent'),(Decimal('0.15'),'PERCENT'))
    def test_money_exact_multiplier(self):
        self.assertEqual(unit_proposal('1.25','억원','money'),(Decimal('125000000'),'KRW'))
        self.assertEqual(unit_proposal('250','USD','money'),(Decimal(250),'USD'))
    def test_unknown_currency_not_assumed(self):
        with self.assertRaises(ValueError):unit_proposal(250,'달러','money')
    def test_boolean_is_not_number(self):
        with self.assertRaises(ValueError):number(True)
    def test_range_flags_preserved(self):
        source={'minimum':21,'maximum':46,'min_inclusive':False,'max_inclusive':True}
        r=range_proposal(source)
        self.assertFalse(r['lower']['inclusive']);self.assertTrue(r['upper']['inclusive'])
    def test_no_default_range_flags(self):
        with self.assertRaises(ValueError):range_proposal({'minimum':21,'maximum':46})
    def test_empty_range_rejected(self):
        for lo,hi,inc in [(5,3,True),(5,5,False)]:
            with self.assertRaises(ValueError):range_proposal({'minimum':lo,'maximum':hi,'min_inclusive':inc,'max_inclusive':inc})
    def test_operator_numeric_and_unit(self):
        self.assertTrue(compatible('EMPLOYEE_COUNT','GTE',8,'NUMBER','PERSON'))
        self.assertFalse(compatible('EMPLOYEE_COUNT','GTE',True,'NUMBER','PERSON'))
        self.assertFalse(compatible('EMPLOYEE_COUNT','GTE',8.5,'NUMBER','PERSON'))
        self.assertFalse(compatible('EMPLOYEE_COUNT','GTE',8,'NUMBER','YEAR'))
    def test_membership_requires_array(self):
        self.assertTrue(compatible('INDUSTRY','IN',['제조업','정보통신업'],'ARRAY'))
        self.assertFalse(compatible('INDUSTRY','IN','제조업, 정보통신업','STRING'))
        self.assertFalse(compatible('INDUSTRY','IN',[],'ARRAY'))
    def test_existence_payload_not_boolean(self):
        self.assertTrue(compatible('CERTIFICATION','EXISTS',None,'UNKNOWN'))
        self.assertFalse(compatible('CERTIFICATION','EXISTS',True,'BOOLEAN'))
        self.assertTrue(compatible('CERTIFICATION','EQ',True,'BOOLEAN'))
    def test_unknown_is_not_null_operator(self):
        self.assertFalse(compatible('QUALITATIVE_QUALIFICATION','UNKNOWN',None,'UNKNOWN'))
        self.assertTrue(compatible('QUALITATIVE_QUALIFICATION',None,None,'UNKNOWN'))
    def test_unit_none_and_unknown_different(self):
        self.assertNotEqual(VALUE['unit_state']['NONE'],VALUE['unit_state']['UNKNOWN'])
        self.assertFalse(compatible('BUSINESS_AGE','LT',4,'NUMBER',None))
    def test_region_no_restriction_not_unknown(self):
        self.assertNotEqual(VALUE['region']['NO_RESTRICTION'],VALUE['region']['UNKNOWN'])
        self.assertFalse(compatible('BUSINESS_LOCATION','EXISTS',None,'UNKNOWN'))
    def test_temporal_and_role_preserved(self):
        record={'field':'business_location','category_id':'BUSINESS_LOCATION','entity_scope':'BUSINESS_SITE',
                'evaluation_phase':'SELECTION','fulfillment_phase':'POST_MOVE_IN','requirement_kind':'FULFILLMENT_OBLIGATION',
                'temporal_constraint':{'anchor_event':'MOVE_IN_START','offset_value':2,'offset_unit':'MONTH','operator':'LTE','inclusive':True}}
        original=copy.deepcopy(record)
        alias_proposal(record['field'],record['category_id'],record['entity_scope'])
        self.assertEqual(record,original)
        date.fromisoformat('2032-02-29')
        with self.assertRaises(ValueError):date.fromisoformat('2031-02-29')
    def test_and_or_structure_and_exception_scope(self):
        ast_node={'kind':'GROUP','operator':'AND','children':[{'kind':'REF','id':'a'},
            {'kind':'GROUP','operator':'OR','children':[{'kind':'REF','id':'b'},{'kind':'REF','id':'c'}]}]}
        self.assertTrue(check_logic(ast_node,{'a','b','c'}))
        self.assertFalse(check_logic(ast_node,{'a','b'}))
        exception={'targets':['b'],'effect':'WAIVE_REQUIREMENT','precondition':'증빙 검수 완료','application_allowed':False}
        self.assertEqual(exception['targets'],['b'])
        self.assertFalse(exception['application_allowed'])
        # Atom split preserves scoped OR instead of AND(a,b,c).
        self.assertEqual(ast_node['children'][1]['operator'],'OR')
    def test_operator_rows_and_no_profile_conflicts(self):
        operators=list(csv.DictReader((HERE/'operator_value_compatibility_v1.csv').open(encoding='utf-8-sig')))
        known={r['operator'] for r in operators}
        self.assertEqual(len(known),12)
        for row in ATTR['attributes']:
            self.assertTrue({op if op is not None else 'null' for op in row['allowed_operators']}<=known)
            self.assertEqual(len(row['allowed_operators']),len(set(row['allowed_operators'])))

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',action='store_true');args=parser.parse_args()
    stream=io.StringIO();suite=unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests)
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    print(stream.getvalue())
    report={'status':'PASS' if result.wasSuccessful() else 'FAIL','tests_run':result.testsRun,
        'failures':len(result.failures),'errors':len(result.errors),'case_names':unittest.defaultTestLoader.getTestCaseNames(ContractTests),
        'gold_records_read':False,'api_calls':0,'production_code_executed':False,'performance_evaluation_performed':False,
        'scope':'Synthetic design oracle and structural checks; not a production normalizer or proof of extraction accuracy'}
    if args.report:
        with (HERE/'contract_validation_report.json').open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2);f.write('\n')
    return 0 if result.wasSuccessful() else 1

if __name__=='__main__':raise SystemExit(main())
