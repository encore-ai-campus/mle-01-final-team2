"""Build a non-deployed semantic contract from inspected source definitions only.

No extractor, evaluation, API or goldset records are executed or loaded.
"""
import ast
import csv
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def write(name,obj):
    path=HERE/name
    if path.exists():raise FileExistsError(path)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def table(name,rows):
    with (HERE/name).open('x',encoding='utf-8-sig',newline='') as stream:
        fields=list(dict.fromkeys(k for row in rows for k in row))
        w=csv.DictWriter(stream,fieldnames=fields);w.writeheader()
        w.writerows({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v for k,v in r.items()} for r in rows)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

# Definitions are draft interpretations with source evidence, not claims that
# current schemas already enforce per-field semantic restrictions.
DEFS=[
('BUSINESS_TYPE','사업체의 규모·법적/조직적 형태·사업 단계 유형','Business classification by size, organization or business stage','BUSINESS','categorical','중소기업','개인 신청자 여부','예비창업자 포함 여부는 사업 단계/신청 주체 문맥 검수 필요'),
('APPLICANT_TYPE','신청 주체의 자격상 유형 및 법적 주체','Legal or participation type of the applicant entity','APPLICANT','categorical','연구기관','소상공인 규모 분류','기업 규모·사업체 유형과 혼동 시 보류; 예비창업자 전역 BUSINESS_TYPE 치환 금지'),
('APPLICANT_ADDRESS','신청자 개인의 주소·거주 요건','Address or residence requirement of the applicant person','APPLICANT_PERSON','region','신청자 주소가 부산광역시','사업장 부산 소재','대표자 주소인지 신청자 주소인지 역할을 명시'),
('BUSINESS_LOCATION','명시된 사업장 소재지 요건','Location of an explicitly identified business site','BUSINESS_SITE','region','사업장이 부산광역시에 소재','신청자 거주 부산','본사/지점/사업장 entity role 보존; 도내/관내 문맥 미확인 시 보류'),
('BUSINESS_AGE','사업 개시 후 경과 업력','Elapsed duration since business commencement','BUSINESS','duration','사업 개시 후 4년 미만','대표자 나이 40세','기준시점·사업개시일 종류·예비창업자 분기 보존'),
('REPRESENTATIVE_AGE','대표자로 지정된 개인의 연령','Age of a person explicitly acting as representative','REPRESENTATIVE_PERSON','age','대표자 만 25세 이상','팀원 만 25세 이상','대표자와 신청자 동일인인지 추정하지 않음'),
('APPLICANT_AGE','신청자·참가자로 지정된 개인의 연령','Age of an explicitly identified applicant or participant','APPLICANT_PERSON','age','참가자 만 25세 이상','대표자와 팀원 모두의 나이','역할별 주어/수량사 보존; 팀원까지 자동 확장 금지'),
('INDUSTRY','요구되는 사업 분야·업종','Required industry or business sector','BUSINESS','categorical','제조업 또는 정보통신업','산업 매출액 비중','코드 체계·버전 미확인 시 원문 라벨 유지'),
('REVENUE','기간과 회계 기준이 명시된 매출액','Revenue amount with period and accounting basis','BUSINESS','money','전년도 매출 2억원 이상','투자유치 2억원','결산기간·개별/연결·부가세 기준 추정 금지'),
('REVENUE_FINANCIAL','구 규칙의 매출·재무 계열 식별자; 의미 범위 미확정','Legacy revenue/financial identifier with unresolved semantic breadth','BUSINESS','money','구 규칙 매출액 2억원','총자산 2억원을 매출로 간주','현재 카탈로그 유지; REVENUE 전역 alias 금지, 원문이 매출액임을 확인해야 함'),
('INDUSTRY_REVENUE_SHARE','특정 업종 매출이 전체 매출에서 차지하는 비중','Share of total revenue attributable to an industry','BUSINESS','percent','매출 중 제조업 비중 15% 이상','수익률 15%','분자 업종·분모 전체매출·기간 보존'),
('EMPLOYEE_COUNT','요건에 지정된 고용인원 수','Count of employees under an explicit counting basis','BUSINESS_EMPLOYMENT','persons','상시근로자 8명 이상','향후 채용 대상 청년','현재 인원/신규채용 인원/기간 평균 및 포함 범위 구분'),
('CERTIFICATION','확인된 인증 자격·인증 상태','Certification designation or certification status','BUSINESS_OR_APPLICANT','status','환경 인증 보유','지식재산권 보유','인증·면허·특허권은 별개; 인증명과 유효성/발급기관 범위 유지'),
('LICENSE_STATUS','면허·허가 보유 또는 상태','License or permit possession and status','BUSINESS_OR_APPLICANT','status','영업허가 보유','사업자등록 완료','면허 종류·허가·등록 구분; 무효/취소/기한 유지'),
('BUSINESS_REGISTRATION','사업자등록 사건 또는 요구 행위','Business registration event or required registration action','BUSINESS','status','선정 후 2개월 이내 사업자등록','현재 사업자등록 완료 여부','미래 가능/이행 의무/현재 사건은 phase/requirement_kind로 구분'),
('BUSINESS_REGISTRATION_STATUS','기준 시점의 사업자등록 상태','Business registration status at a reference time','BUSINESS','status','신청일 현재 사업자등록 완료','선정 후 등록 가능한 자','사업자등록과 상태는 맥락에 따라 구분; completed 라벨은 코드 승인 전 원문 보존'),
('PROGRAM_PARTICIPATION','지원·보육 등 사업 참여 사실 또는 이력','Participation in a program including past participation','APPLICANT_OR_BUSINESS','status','공공 보육사업 참여 이력','특정 기관과 기술이전 가능','사업 유형·지원 주체·과거/현재·횟수·제외 범위 보존'),
('DOCUMENT_SUBMISSION','특정 증빙 또는 신청 서류의 제출 의무','Obligation to submit an identified document','APPLICANT_DOCUMENT_OBLIGATION','status','거주 증명서 제출 필수','서울 거주 요건 자체','서류의 증명 대상 사실과 제출 행위를 별도 조건으로 취급'),
('FINANCIAL_CAPACITY','매출 외 명시된 자금조달·부담·재정 능력 요건','Explicit financial capacity or contribution requirement other than revenue','BUSINESS_FINANCE','money','자부담 500만원 확보','매출 500만원','자산/자부담/투자/담보/지원금은 측정 대상이 달라 subtype 문맥 필요'),
('DUPLICATE_OCCUPANCY','동시·중복 입주 사실 또는 금지','Concurrent or duplicate occupancy requirement','BUSINESS_SITE_PARTICIPATION','status','다른 시설 중복입주 불가','다른 지원금 중복수혜','시설 범위·본점/지점·시점·부정 극성 보존'),
('QUALITATIVE_QUALIFICATION','별도 속성으로 구조화하지 못한 질적 요건','Qualitative requirement not represented by a more specific attribute','APPLICANT_OR_BUSINESS','qualitative','친환경 기술역량 보유','명확한 매출 2억원 요건','알 수 없는 모든 개념을 자동 수용하는 fallback으로 사용 금지'),
('UNCLASSIFIED','대상 속성 및 의미가 미확정인 조건 원문','Unclassified source requirement awaiting review','UNRESOLVED','unclassified','해석이 미확정인 원문','아무 조건 없음','미확인을 조건 없음으로 해석하지 않으며 판정 불가')]

PROFILES={
'categorical':(['EQ','NEQ','IN','NOT_IN'],['STRING','ARRAY'],[]),
'region':(['EQ','NEQ','IN','NOT_IN'],['STRING','ARRAY'],[]),
'duration':(['EQ','NEQ','GT','GTE','LT','LTE','BETWEEN'],['NUMBER','RANGE'],['DAY','MONTH','YEAR']),
'age':(['EQ','NEQ','GT','GTE','LT','LTE','BETWEEN'],['NUMBER','RANGE'],['YEAR']),
'money':(['EQ','NEQ','GT','GTE','LT','LTE','BETWEEN'],['NUMBER','RANGE'],['KRW','USD']),
'percent':(['EQ','NEQ','GT','GTE','LT','LTE','BETWEEN'],['NUMBER','RANGE'],['PERCENT']),
'persons':(['EQ','NEQ','GT','GTE','LT','LTE','BETWEEN'],['NUMBER','RANGE'],['PERSON']),
'status':(['EQ','NEQ','IN','NOT_IN','EXISTS','NOT_EXISTS'],['STRING','BOOLEAN','ARRAY','UNKNOWN'],[]),
'qualitative':(['EQ','NEQ','EXISTS','NOT_EXISTS',None],['STRING','UNKNOWN'],[]),
'unclassified':([None],['UNKNOWN'],[])}

def main():
    tree=ast.parse((ROOT/'tools/extract_condition_candidates_llm.py').read_text(encoding='utf-8'))
    catalog=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ATTRIBUTE_CATALOG' for t in n.targets))
    assert {r[0] for r in DEFS}==catalog
    rows=[];mapping=[]
    for field,ko,en,scope,profile,example,counter,ambiguity in DEFS:
        ops,types,units=PROFILES[profile]
        rows.append({'canonical_field':field,'category_id':field,'description_ko':ko,'description_en':en,
            'entity_scope':scope,'allowed_condition_types':['UNCLASSIFIED'] if field=='UNCLASSIFIED' else ['ELIGIBILITY','EXCLUSION','PREFERENCE'],
            'allowed_operators':ops,'allowed_value_types':types,'allowed_units':units,'value_profile':profile,
            'aliases':[field.lower()],
            'normalization_policy':{'automatic_candidate':'EXACT_CASE_ONLY','field_category_must_agree':True,
                'value_normalization_contract':'value_normalization_contract_v1.json',
                'scope_preservation':True,'null_field_allowed':field=='UNCLASSIFIED'},
            'ambiguity_policy':{'action':'HOLD_FOR_REVIEW','reason_ko':ambiguity,'never_infer_from_gold':True},
            'examples':[{'text':example,'kind':'SYNTHETIC_CONCEPT_EXAMPLE_NOT_OPERATIONAL_PREDICTION'}],
            'counterexamples':[counter],'definition_source':[
                'tools/extract_condition_candidates_llm.py:ATTRIBUTE_CATALOG',
                'docs/condition/CONDITION_SCHEMA_V1.md:initial categories',
                'schemas/conditions/condition-common-v1.1.schema.json#/$defs/condition'],
            'definition_status':'DRAFT_INTERPRETATION_REQUIRES_REVIEW',
            'compatibility_note':'Per-field restrictions are proposed semantic intersections, not existing schema enforcement.'})
        mapping.append({'source_field':field.lower(),'target_field':field,'relationship':'EXACT_ALIAS',
            'automatic_candidate':True,'required_context':'Same entity, category agrees; apply ambiguity checks after case normalization',
            'reason':'Unique case-only match to existing catalog','provenance':'attribute-normalization-v2',
            'status':'DRAFT_NOT_DEPLOYED'})
    def relation(src,target,kind,context,reason):
        mapping.append({'source_field':src,'target_field':target,'relationship':kind,'automatic_candidate':kind=='EXACT_ALIAS',
            'required_context':context,'reason':reason,'provenance':'SOURCE_CODE_AND_SEMANTIC_REVIEW','status':'DRAFT_NOT_DEPLOYED'})
    for src,target,context in [('EMPLOYMENT','EMPLOYEE_COUNT','Legacy rule numeric count of workers only; not generic hiring/employment state'),
        ('REVENUE_FINANCIAL','REVENUE','Explicit revenue metric with unchanged period/currency/basis'),
        ('residence','APPLICANT_ADDRESS','Applicant person residence, not workplace or headquarters'),
        ('residence_proof','DOCUMENT_SUBMISSION','Explicit document submission obligation; proof existence alone does not imply submission'),
        ('military_service_proof','DOCUMENT_SUBMISSION','Explicit document submission; never infer military eligibility fact'),
        ('hiring_target','PROGRAM_PARTICIPATION','No direct mapping: hiring is not participation'),
        ('prior_occupancy_experience','PROGRAM_PARTICIPATION','Explicit program identity, history period and exceptions preserved'),
        ('program_purpose_and_item','QUALITATIVE_QUALIFICATION','Explicit qualitative scope with external-reference uncertainty retained'),
        ('university_industry_academia_cooperation','PROGRAM_PARTICIPATION','Only explicit participation in a cooperation program; bilateral relation itself differs'),
        ('technology_transfer_capability','QUALITATIVE_QUALIFICATION','Feasibility requirement; not completed transfer or certification'),
        ('사업장 소재지','BUSINESS_LOCATION','Business site explicit; preserve HQ/branch role'),
        ('기업 유형','BUSINESS_TYPE','Value refers to business size/organization/stage, not generic applicant entity'),
        ('사업자 등록','BUSINESS_REGISTRATION','Registration event/action, not completed status'),
        ('지식재산권','CERTIFICATION','No direct mapping; patent/trademark/design rights are not certifications')]:
        kind='DISTINCT_CONCEPT' if src in ['hiring_target','지식재산권'] else 'CONTEXT_DEPENDENT'
        relation(src,target,kind,context,'No unconditional semantic equivalence')
    for a,b in [('APPLICANT_TYPE','BUSINESS_TYPE'),('APPLICANT_ADDRESS','BUSINESS_LOCATION'),
        ('REPRESENTATIVE_AGE','TEAM_MEMBER_AGE'),('RESIDENCE_REQUIREMENT','RESIDENCE_PROOF'),
        ('ELIGIBILITY_FACT','DOCUMENT_SUBMISSION'),('BUSINESS_REGISTRATION','BUSINESS_REGISTRATION_STATUS')]:
        relation(a,b,'DISTINCT_CONCEPT','Never global replacement; preserve entity/event and evidence','Required semantic boundary')
        relation(b,a,'DISTINCT_CONCEPT','Never global replacement; preserve entity/event and evidence','Required semantic boundary')
    for src,target in [('team_member_age','TEAM_MEMBER_AGE'),('hiring_target','HIRING_REQUIREMENT'),
        ('university_industry_academia_cooperation','COLLABORATION_RELATION'),
        ('technology_transfer_capability','TECHNOLOGY_TRANSFER_FEASIBILITY'),('지식재산권','IP_RIGHT_REQUIREMENT')]:
        relation(src,target,'NEW_ATTRIBUTE_REQUIRED','Catalog review and approval required; not an existing canonical field',
                 'Distinct actor/event/relationship generalizable beyond one source')
    relation('임의의 한국어 속성명','','UNSUPPORTED_OR_UNRESOLVED','Exact known definition unavailable','Do not translate field by guessing')
    contract={'contract_version':'attribute-semantic-contract-v1-draft','status':'DRAFT_NOT_DEPLOYED',
        'canonical_authority':'Existing 22-member LLM catalog retained; schema category is open vocabulary',
        'existing_catalog_count':22,'attributes':rows,'candidate_promotion_allowed':False,
        'new_attribute_candidates':[{'canonical_field':f,'status':'REQUIRES_APPROVAL','not_in_existing_catalog':True,
            'reason':reason} for f,reason in [('TEAM_MEMBER_AGE','Different person role from representative/applicant'),
            ('HIRING_REQUIREMENT','Required hiring action/target/status differs from employee stock count'),
            ('COLLABORATION_RELATION','Bilateral cooperation relation is not necessarily program participation'),
            ('TECHNOLOGY_TRANSFER_FEASIBILITY','Future capability differs from participation/actual transfer'),
            ('IP_RIGHT_REQUIREMENT','Right ownership, validity, territory and type differ from certification')]],
        'all_new_candidates_source_independent':True}
    write('attribute_semantic_contract_v1.json',contract);table('attribute_mapping_policy_v1.csv',mapping)
    review=[]
    for src,action,target,reason in [
        ('hiring_target','NEW_ATTRIBUTE_CANDIDATE','HIRING_REQUIREMENT','Employment count is not hiring action or target; timing and employment type matter'),
        ('team_member_age','NEW_ATTRIBUTE_CANDIDATE','TEAM_MEMBER_AGE','Preserve team-member role and ALL/ANY quantifier'),
        ('residence','CONTEXT_MAPPING','APPLICANT_ADDRESS','Require explicit person subject and address/residence meaning'),
        ('residence_proof','CONTEXT_MAPPING','DOCUMENT_SUBMISSION','Must require submission of proof, not proof of eligibility alone'),
        ('military_service_proof','CONTEXT_MAPPING','DOCUMENT_SUBMISSION','Separate document duty from military-service eligibility'),
        ('prior_occupancy_experience','CONTEXT_MAPPING','PROGRAM_PARTICIPATION','Program type, temporal history and exceptions must remain representable; count restrictions may require narrower attribute'),
        ('program_purpose_and_item','HUMAN_REVIEW','QUALITATIVE_QUALIFICATION','External technical scope must not be invented or confirmed'),
        ('university_industry_academia_cooperation','NEW_ATTRIBUTE_CANDIDATE','COLLABORATION_RELATION','Generic counterpart-based collaboration relationship'),
        ('technology_transfer_capability','NEW_ATTRIBUTE_CANDIDATE','TECHNOLOGY_TRANSFER_FEASIBILITY','Future capability rather than actual transfer'),
        ('한글 속성명','HUMAN_REVIEW','','No blanket translation; known labels require entity/context/category checks')]:
        review.append({'input_field':src,'recommended_action':action,'candidate_target':target,
            'automatic_mapping':False,'meaning_and_conditions':reason,'source_scope':'ANY_SOURCE',
            'catalog_approval_needed':action=='NEW_ATTRIBUTE_CANDIDATE',
            'unrepresentable_action':'HOLD_FOR_REVIEW_OR_REJECT_UNSUPPORTED; never coerce into another attribute'})
    table('unsupported_attribute_review.csv',review)
    ops=[]
    for op in ['EQ','NEQ','GT','GTE','LT','LTE','IN','NOT_IN','BETWEEN','EXISTS','NOT_EXISTS',None]:
        meaning={'EQ':'等値 / equals','NEQ':'not equal','GT':'strictly greater; exclusive','GTE':'greater or equal; inclusive',
            'LT':'strictly less; exclusive','LTE':'less or equal; inclusive','IN':'member of explicit alternatives',
            'NOT_IN':'not a member of explicit alternatives','BETWEEN':'both bounds with independent inclusive flags',
            'EXISTS':'existence of field-defined fact','NOT_EXISTS':'absence of field-defined fact',None:'Operator not established; not a match-all'}[op]
        types=(['ARRAY'] if op in ['IN','NOT_IN'] else ['RANGE'] if op=='BETWEEN' else ['UNKNOWN'] if op in ['EXISTS','NOT_EXISTS',None]
               else ['NUMBER','DATE'] if op in ['GT','GTE','LT','LTE'] else ['STRING','NUMBER','DATE','BOOLEAN'])
        ops.append({'operator':'null' if op is None else op,'meaning':meaning,'allowed_value_types':types,
            'value_shape':'nonempty array of homogeneous scalar alternatives' if op in ['IN','NOT_IN'] else
                'lower/upper:{value,inclusive}; lower<=upper and nonempty interval' if op=='BETWEEN' else
                'value=null; unit=null' if op in ['EXISTS','NOT_EXISTS',None] else 'scalar consistent with attribute profile',
            'boundary_rule':{'GT':'exclusive lower','GTE':'inclusive lower','LT':'exclusive upper','LTE':'inclusive upper'}.get(op,'explicit only'),
            'unknown_policy':'UNKNOWN token is invalid operator; do not auto-map to null',
            'status':'DRAFT_PROFILE_INTERSECTION; NO_CURRENT_SCHEMA_CHANGE'})
    table('operator_value_compatibility_v1.csv',ops)
    value={'version':'value-normalization-contract-v1-draft','status':'DRAFT_NOT_DEPLOYED',
      'provenance_required':['original_field','original_value','original_unit','original_operator','rule_id','rule_version','reason','mapping_status','source_evidence'],
      'unit_aliases':{'년':'YEAR','YEAR':'YEAR','개월':'MONTH','MONTH':'MONTH','일':'DAY','DAY':'DAY','%':'PERCENT','PERCENT':'PERCENT','명':'PERSON','PERSON':'PERSON'},
      'context_unit_aliases':{'세':{'target':'YEAR','require':'Explicit person age'},'월':{'target':'MONTH','require':'Explicit duration, not calendar month'},
          '개':{'target':'COUNT','require':'Explicit counted entity subtype'},'달러':{'target':'USD','require':'Explicit US dollars; no assumed currency'}},
      'money_units':{'원':{'target':'KRW','multiplier':'1'},'천원':{'target':'KRW','multiplier':'1000'},
          '만원':{'target':'KRW','multiplier':'10000'},'억원':{'target':'KRW','multiplier':'100000000'},
          'KRW':{'target':'KRW','multiplier':'1'},'USD':{'target':'USD','multiplier':'1'}},
      'numeric_policy':{'arithmetic':'exact decimal; no float rounding','bool_is_number':False,'commas':'only well-formed thousands grouping',
          'percent_scale':'15 percent stays 15 PERCENT; 0.15 is not multiplied without explicit ratio convention',
          'cross_dimension_conversion':False,'year_month_conversion':'No automatic conversion: calendar/age conventions differ',
          'currency_conversion':'No exchange-rate conversion; currency must be explicit'},
      'unit_state':{'NONE':'Dimensionless categorical/existence condition','UNKNOWN':'Dimension expected but not identified',
          'KNOWN':'Explicit supported unit','transport':'Current unit:null cannot encode NONE vs UNKNOWN alone; keep sidecar provenance. New persisted state field needs schema approval.'},
      'range':{'canonical_operator':'BETWEEN','canonical_value_type':'RANGE',
          'canonical_shape':{'lower':{'value':3,'inclusive':True},'upper':{'value':8,'inclusive':False}},
          'legacy_conversion':'minimum/maximum or min/max may convert ONLY when both boundary flags and metric/unit/basis are explicit and identical',
          'missing_flags':'HOLD_FOR_REVIEW; no default inclusive boundary','unbounded':'Use explicit GT/GTE/LT/LTE for one-sided ranges; no invented bound',
          'boundary_tokens':{'이상':'GTE','이하':'LTE','초과':'GT','미만':'LT','이내':'LTE_ONLY_WHEN_DURATION_CONTEXT_EXPLICIT'}},
      'categorical':{'single':'EQ/NEQ scalar string; preserve original label','multiple':'IN/NOT_IN nonempty alternatives, not arbitrary comma-splitting',
          'array_logic':'IN alternatives only when source establishes OR membership; separate requirements require explicit AST',
          'codes':'Namespace/version/source label required; no guessed code','status_boolean':'EQ true/false is distinct from EXISTS/NOT_EXISTS; never coerce EXISTS true to null automatically'},
      'region':{'canonical_level':'Explicit administrative level and authoritative namespace/version if available',
          'person_site_roles':['APPLICANT_ADDRESS','BUSINESS_LOCATION','HEADQUARTERS_ROLE','BRANCH_ROLE'],
          'exact_alias_candidate':'Only validated unambiguous geographic ID; short city label alone may be ambiguous',
          'context_required':['도내','관내','본사','지점'],
          'NO_RESTRICTION':'Explicit absence of geographic requirement; retain as source assertion sidecar, not a positive region condition or UNKNOWN',
          'UNKNOWN':'Geographic restriction cannot be established; distinct from NO_RESTRICTION',
          'NATIONWIDE':'Explicit scope is not necessarily absence of all geographic requirements',
          'transport':'No new runtime enum is introduced; novel source assertions need downstream versioned contract approval'},
      'temporal':{'date':'YYYY-MM-DD with real calendar validation, original precision retained',
          'reference':'Existing reference_date/date_type and temporal_constraint anchor must be preserved',
          'relative':'offset_value/offset_unit/operator/inclusive/applies_to/anchor_date_known preserved',
          'unknown_anchor':'Never substitute current date, publication date, or collection time',
          'application_date':'APPLICATION temporal anchor is distinct from APPLICATION_START reference date; require explicit basis',
          'phases':'evaluation_phase/fulfillment_phase/requirement_kind remain independent; do not flatten future obligations to current facts'},
      'operator_contract':'operator_value_compatibility_v1.csv','attribute_contract':'attribute_semantic_contract_v1.json',
      'schema_compatibility':'Existing range structure retained. New unit_status/region assertion states are sidecar draft only.'}
    write('value_normalization_contract_v1.json',value)
    # Inventory actual static names, not goldset vocabulary.
    inventory=[]
    source_specs=[('schemas/conditions/condition-common-v1.schema.json','OPEN_VOCABULARY'),
        ('schemas/conditions/condition-common-v1.1.schema.json','OPEN_VOCABULARY'),
        ('schemas/conditions/condition-vocabularies-v1.schema.json','OPEN_VOCABULARY'),
        ('docs/condition/CONDITION_SCHEMA_V1.md','DOCUMENTED_INITIAL_VOCABULARY'),
        ('tools/extract_condition_candidates.py','REGEX_PATTERN_FIELDS'),
        ('tools/extract_condition_candidates_rules_v2.py','EXPERIMENTAL_RULE_FIELDS'),
        ('tools/extract_condition_candidates_legacy_augmented.py','LEGACY_AUGMENTATION'),
        ('tools/extract_condition_candidates_llm.py','CLOSED_22_CATALOG_AND_NORMALIZATION_V2'),
        ('tools/graphrag/condition_schema.py','SEPARATE_LEGACY_GRAPH_CONTRACT'),
        ('schemas/conditions/source-field-mapping-v1.csv','SOURCE_PATHS_NOT_SEMANTIC_ATTRIBUTE_MAP'),
        ('tools/evaluate_condition_pipeline.py','VALUE_AND_EVIDENCE_NORMALIZATION'),
        ('tools/evaluate_condition_pipeline_v11.py','STRICT_COMMON_AND_EXTENDED_FIELDS'),
        ('tools/run_condition_llm_openai_pilot.py','RAW_PREVALIDATION_ADAPTER')]
    for name,kind in source_specs:
        path=ROOT/name;text=path.read_text(encoding='utf-8')
        literals=[]
        if path.suffix=='.py':
            literals=sorted({n.value for n in ast.walk(ast.parse(text)) if isinstance(n,ast.Constant) and isinstance(n.value,str)
                             and n.value in catalog|{'EMPLOYMENT','TAX_DEBT','BUSINESS_STATUS','DUPLICATE_BENEFIT','LEGAL_SANCTION'}})
        inventory.append({'definition_source':name,'kind':kind,'catalog_field_literals_present':literals,
            'semantic_enforcement':'No shared attribute-level contract import; inspect source before adoption',
            'sha256':sha(path)})
    table('attribute_definition_inventory.csv',inventory)
    write('contract_build_metadata.json',{'sources':{name:sha(ROOT/name) for name,_ in source_specs},
        'baseline_fixed':{'notices':10,'gold_conditions':62,'rule_v1_f1_percent':13.64,'rule_e_f1_percent':14.12,
            'llm_pre_f1_percent':1.67,'llm_post_f1_percent':2.13,'llm_post_tp':1,'llm_post_fp':31,'llm_post_fn':61,
            'requests_used':13,'request_limit':13,'remaining':0},'gold_records_loaded':False,'api_calls':0})

if __name__=='__main__':main()
