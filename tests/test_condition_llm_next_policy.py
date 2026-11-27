import copy
import json
import unittest
import httpx
from jsonschema import ValidationError
from tools import condition_llm_next_policy as n
from tests.test_condition_llm_extractor import condition,source_row

def cref(i):return {'node_type':'CONDITION_REF','condition_index':i}
def gref(i):return {'node_type':'GROUP_REF','group_id':i}
def uref(i):return {'node_type':'UNRESOLVED_REF','unresolved_index':i}
def fixture():
    quotes=['사업장이 울산광역시에 있어야 한다.',
            '연구기관 또는 창업 4년 미만 기업만 신청할 수 있다.',
            '사업장 증빙서류를 신청 시 제출해야 한다.',
            '환경산업 기업은 우대한다.',
            '다른 시설에 중복 입주한 기업은 신청할 수 없다.']
    cs=[condition(field='BUSINESS_LOCATION',op='EQ',value='울산광역시',value_type='STRING',quote=quotes[0]),
        condition(field='APPLICANT_TYPE',op='EQ',value='연구기관',value_type='STRING',quote=quotes[1]),
        condition(field='BUSINESS_AGE',op='LT',value=4,value_type='NUMBER',unit='YEAR',quote=quotes[1]),
        condition(field='DOCUMENT_SUBMISSION',op='EQ',value='사업장 증빙서류 제출',value_type='STRING',quote=quotes[2]),
        condition(field='INDUSTRY',op='EQ',value='환경산업',value_type='STRING',kind='PREFERENCE',quote=quotes[3]),
        condition(field='DUPLICATE_OCCUPANCY',op='EQ',value=True,value_type='BOOLEAN',kind='EXCLUSION',quote=quotes[4])]
    payload={'schema_version':n.VERSION,'status':'CONDITIONS_FOUND','source_state':'CONDITIONS_PRESENT',
        'conditions':cs,'unresolved_conditions':[],
        'logic_groups':[{'group_id':'g-choice','operator':'OR','children':[cref(1),cref(2)],'evidence_quote':quotes[1]},
            {'group_id':'g-required','operator':'AND','children':[cref(0),gref('g-choice'),cref(3)],'evidence_quote':None}],
        'logic_sections':[{'section_id':'elig','section_type':'ELIGIBILITY','root_ref':gref('g-required'),
                           'evaluation_phase':'APPLICATION','fulfillment_phase':'APPLICATION'},
                          {'section_id':'pref','section_type':'PREFERENCE','root_ref':cref(4),
                           'evaluation_phase':'SELECTION','fulfillment_phase':'SELECTION'},
                          {'section_id':'excl','section_type':'EXCLUSION','root_ref':cref(5),
                           'evaluation_phase':'APPLICATION','fulfillment_phase':'APPLICATION'}],
        'exceptions':[],'unresolved_relations':[],'logic_completeness':'PROPOSAL_ONLY','decision_eligible':False}
    source=source_row('\n'.join(quotes));source['notice_id']='SYNTHETIC:NEXT_POLICY'
    return source,payload

def unresolved(source,payload,code='UNSUPPORTED_ATTRIBUTE'):
    text='팀원은 만 26세 이상이어야 한다.' if code!='EXPLICIT_NO_RESTRICTION' else '대표자 거주 지역에는 제한이 없다.'
    source['raw_text']+='\n'+text
    payload['unresolved_conditions'].append({'raw_condition':text,'evidence_quotes':[text],
        'proposed_field':'team_member_age' if code!='EXPLICIT_NO_RESTRICTION' else 'residence',
        'entity_scope':'TEAM_MEMBER' if code!='EXPLICIT_NO_RESTRICTION' else 'REPRESENTATIVE_PERSON',
        'condition_type':'ELIGIBILITY','operator':None,'reason_code':code,'reason':'기존 표준 속성으로 의미를 확정하지 못함',
        'review_status':'NEEDS_REVIEW','decision_eligible':False})
    payload['logic_completeness']='INCOMPLETE'

class NextPolicyTests(unittest.TestCase):
    def test_valid_payload_projects_to_existing_validator(self):
        s,p=fixture();result=n.validate_and_convert(s,p)
        self.assertEqual(len(result['conditions']),6)
        n.old.INTERMEDIATE_VALIDATOR.validate(result['existing_intermediate_projection'])
        self.assertEqual(n.old.validate_artifacts(result['conditions'],[]),[])
    def test_enum_contract_matches_existing_allowlists(self):
        c=n.provider_schema()['$defs']['condition']['properties']
        self.assertEqual(set(c['field']['enum']),n.old.ATTRIBUTE_CATALOG)
        self.assertEqual(set(c['operator']['enum']),set(n.old.OPERATORS))
        self.assertNotIn('UNKNOWN',c['operator']['enum'])
        self.assertEqual(set(c['condition_type']['enum']),set(n.old.CONDITION_TYPES))
        parts=n.prompt_parts()
        for row in n.ATTRS:self.assertIn(row['canonical_field'],parts['attributes'])
    def test_provider_schema_subset_shape(self):
        forbidden={'allOf','if','then','else','not','oneOf','uniqueItems','patternProperties'}
        def walk(x):
            if isinstance(x,dict):
                self.assertFalse(set(x)&forbidden)
                if x.get('type')=='object':
                    self.assertFalse(x['additionalProperties'])
                    self.assertEqual(set(x['required']),set(x['properties']))
                for v in x.values():walk(v)
            elif isinstance(x,list):
                for v in x:walk(v)
        walk(n.provider_schema())
    def test_required_field_missing(self):
        s,p=fixture();del p['conditions'][0]['evidence_quotes']
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_unknown_operator_rejected(self):
        s,p=fixture();p['conditions'][0]['operator']='UNKNOWN'
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_arbitrary_field_rejected(self):
        s,p=fixture();p['conditions'][0]['field']='hiring_target'
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_category_field_mismatch_rejected(self):
        s,p=fixture();p['conditions'][0]['category_id']='APPLICANT_ADDRESS'
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_value_type_mismatch_rejected(self):
        s,p=fixture();p['conditions'][2]['value']='four'
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_exists_boolean_payload_rejected(self):
        s,p=fixture();p['conditions'][5]['operator']='EXISTS'
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_unsupported_attribute_preserved_as_review_not_candidate(self):
        s,p=fixture();unresolved(s,p)
        r=n.validate_and_convert(s,p)
        self.assertEqual(len(r['conditions']),6)
        self.assertEqual(r['unresolved_conditions'],p['unresolved_conditions'])
        self.assertFalse(r['unresolved_conditions'][0]['decision_eligible'])
    def test_no_restriction_not_location_condition(self):
        s,p=fixture();unresolved(s,p,'EXPLICIT_NO_RESTRICTION')
        r=n.validate_and_convert(s,p)
        self.assertEqual(len(r['conditions']),6)
        self.assertEqual(r['unresolved_conditions'][0]['reason_code'],'EXPLICIT_NO_RESTRICTION')
    def test_team_member_age_not_forced_to_representative(self):
        s,p=fixture();unresolved(s,p)
        r=n.validate_and_convert(s,p)
        self.assertFalse(any(c['field']=='REPRESENTATIVE_AGE' for c in r['conditions']))
    def test_units_n1_is_opt_in_experimental_only(self):
        s,p=fixture();p['conditions'][2]['unit']='년'
        r=n.validate_and_convert(s,p)
        self.assertEqual(next(c for c in r['conditions'] if c['field']=='BUSINESS_AGE')['unit'],'YEAR')
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p,apply_n1=False)
    def test_range_boundaries(self):
        s,p=fixture();text='참가자 만 23세 초과 48세 이하만 신청할 수 있다.';s['raw_text']+='\n'+text
        p['conditions'][2]=condition(field='APPLICANT_AGE',op='BETWEEN',value_type='RANGE',unit='YEAR',quote=text,
            value={'lower':{'value':23,'inclusive':False},'upper':{'value':48,'inclusive':True}})
        r=n.validate_and_convert(s,p)
        age=next(c for c in r['conditions'] if c['field']=='APPLICANT_AGE')
        self.assertFalse(age['value']['lower']['inclusive']);self.assertTrue(age['value']['upper']['inclusive'])
    def test_range_flag_missing_rejected(self):
        s,p=fixture();p['conditions'][2]['operator']='BETWEEN';p['conditions'][2]['value_type']='RANGE'
        p['conditions'][2]['value']={'lower':{'value':2},'upper':{'value':4,'inclusive':True}}
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_invalid_date_rejected(self):
        s,p=fixture();p['conditions'][2]['reference_date']='2031-02-29'
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_independent_condition_types(self):
        s,p=fixture();r=n.validate_and_convert(s,p)
        self.assertEqual({c['condition_type'] for c in r['conditions']},{'ELIGIBILITY','EXCLUSION','PREFERENCE'})
        self.assertEqual(next(c for c in r['conditions'] if c['field']=='DOCUMENT_SUBMISSION')['condition_type'],'ELIGIBILITY')
    def test_nested_group_exact_transport(self):
        s,p=fixture();r=n.validate_and_convert(s,p)
        root=r['evaluation_record']['logical_roots'][0]
        self.assertEqual(root['operator'],'AND')
        self.assertEqual(root['children'][1]['operator'],'OR')
        self.assertEqual(root['group_id'],'g-required')
    def test_bad_group_reference_rejected(self):
        s,p=fixture();p['logic_sections'][0]['root_ref']=gref('missing')
        with self.assertRaisesRegex(ValueError,'UNKNOWN_GROUP_REF'):n.validate_and_convert(s,p)
    def test_bad_condition_reference_rejected(self):
        s,p=fixture();p['logic_groups'][0]['children'][0]=cref(99)
        with self.assertRaisesRegex(ValueError,'UNKNOWN_CONDITION_INDEX'):n.validate_and_convert(s,p)
    def test_cycle_rejected(self):
        s,p=fixture();p['logic_groups'][0]['children'][0]=gref('g-required')
        with self.assertRaisesRegex(ValueError,'CYCLIC_GROUP_REF'):n.validate_and_convert(s,p)
    def test_held_ref_blocks_entire_group_without_removing_child(self):
        s,p=fixture();unresolved(s,p);p['logic_groups'][0]['children'].append(uref(0))
        r=n.validate_and_convert(s,p)
        self.assertNotIn('g-required',[x.get('group_id') for x in r['evaluation_record']['logical_roots']])
        self.assertEqual(r['raw_logic_groups'],p['logic_groups'])
        self.assertEqual(r['logic_completeness'],'INCOMPLETE')
    def test_exception_target_scope_and_application_block(self):
        s,p=fixture();unresolved(s,p);text=p['unresolved_conditions'][0]['evidence_quotes'][0]
        p['exceptions']=[{'target_refs':[uref(0)],'effect':'WAIVE_REQUIREMENT','effect_target':'팀원 연령',
            'precondition':'별도 검수','replacement':None,'effect_confirmed':False,'application_mode':'EFFECT_ONLY','evidence_quote':text}]
        r=n.validate_and_convert(s,p)
        self.assertEqual(r['exceptions'][0]['original_exception'],p['exceptions'][0])
        self.assertEqual(r['exceptions'][0]['application_status'],'BLOCKED_UNRESOLVED_TARGET')
        self.assertFalse(r['exceptions'][0]['application_allowed'])
    def test_evidence_not_in_source_rejected_by_existing_validator(self):
        s,p=fixture();p['conditions'][0]['evidence_quotes']=['없는 원문']
        r=n.validate_and_convert(s,p)
        self.assertEqual(len(r['conditions']),5)
        self.assertIn(0,r['unvalidated_condition_indexes'])
        self.assertEqual(r['logic_completeness'],'INCOMPLETE')
    def test_unresolved_evidence_not_in_source_is_error(self):
        s,p=fixture();unresolved(s,p);p['unresolved_conditions'][0]['evidence_quotes']=['없는 문장']
        with self.assertRaisesRegex(ValueError,'UNRESOLVED_EVIDENCE'):n.validate_and_convert(s,p)
    def test_decision_approval_rejected(self):
        s,p=fixture();p['decision_eligible']=True
        with self.assertRaises(ValidationError):n.validate_and_convert(s,p)
    def test_source_and_payload_immutable_and_deterministic(self):
        s,p=fixture();old_s,old_p=copy.deepcopy(s),copy.deepcopy(p)
        r=n.validate_and_convert(s,p)
        self.assertEqual(r,n.validate_and_convert(s,p));self.assertEqual(s,old_s);self.assertEqual(p,old_p)

class SDKMockTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_sdk_structured_request_and_legacy_validation(self):
        source,payload=fixture();requests=[]
        async def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,'model':'gpt-5.6-luna',
                'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(payload)}}]})
        client=n.NextPolicyClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        try:
            result=await client.extract(source)
            self.assertEqual(len(result['conditions']),6)
            self.assertEqual(requests[0]['response_format']['type'],'json_schema')
            self.assertTrue(requests[0]['response_format']['json_schema']['strict'])
            self.assertEqual(client.client.max_retries,0)
        finally:await client.aclose()
        self.assertTrue(client.client.is_closed())
    async def test_json_mode_uses_same_contract_locally(self):
        source,payload=fixture();requests=[]
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200,json={'id':'offline','object':'chat.completion','created':1,'model':'gpt-5.6-luna',
                'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':json.dumps(payload)}}]})
        client=n.NextPolicyClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        try:
            await client.extract(source,variant='P1')
            self.assertEqual(requests[0]['response_format']['type'],'json_object')
            self.assertIn('JSON output schema',requests[0]['messages'][0]['content'])
        finally:await client.aclose()
    async def test_real_network_transport_is_forbidden(self):
        client=httpx.AsyncClient()
        try:
            with self.assertRaisesRegex(ValueError,'MOCK_TRANSPORT_REQUIRED'):n.NextPolicyClient(client)
        finally:await client.aclose()

if __name__=='__main__':unittest.main()
