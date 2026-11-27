import copy
import unittest
from decimal import Decimal
from unittest.mock import patch
from tools import condition_safe_normalization_experiment as n
from tests.test_condition_llm_extractor import condition,response,source_row

class SafeNormalizationTests(unittest.TestCase):
    def apply(self,c,arm='N5',source=None):
        return n.normalize(c,arm,source if source is not None else c['evidence_quotes'][0])
    def quantitative(self,unit='년',value=4,**kw):
        return condition(field='BUSINESS_AGE',op='LT',value=value,value_type='NUMBER',unit=unit,quote='업력 4년 미만',**kw)
    def test_year_unit(self):
        c=self.quantitative();r,e,_=self.apply(c,'N1')
        self.assertEqual(r['unit'],'YEAR');self.assertEqual(len(e),1)
    def test_month_and_percent(self):
        for field,quote,unit,target in [('BUSINESS_AGE','업력 4개월 미만','개월','MONTH'),
            ('INDUSTRY_REVENUE_SHARE','산업 매출 비중 4% 이상','%','PERCENT')]:
            c=condition(field=field,op='GTE',value=4,value_type='NUMBER',unit=unit,quote=quote)
            self.assertEqual(self.apply(c,'N1')[0]['unit'],target)
    def test_person_count(self):
        c=condition(field='EMPLOYEE_COUNT',op='GTE',value=8,value_type='NUMBER',unit='명',quote='상시 근로자 8명 이상')
        self.assertEqual(self.apply(c,'N1')[0]['unit'],'PERSON')
    def test_missing_unit_not_created(self):
        c=self.quantitative(unit=None)
        self.assertIsNone(self.apply(c)[0]['unit'])
    def test_different_dimension_rejected(self):
        c=self.quantitative(unit='%');c['evidence_quotes']=['업력 4%']
        r,_,reject=self.apply(c,'N1')
        self.assertEqual(r['unit'],'%');self.assertEqual(reject[0]['reason'],'ATTRIBUTE_UNIT_DIMENSION_MISMATCH')
    def test_unit_must_be_in_source(self):
        c=self.quantitative();c['evidence_quotes']=['업력 요건이 있습니다']
        self.assertEqual(self.apply(c,'N1')[0]['unit'],'년')
    def test_exact_money_multiplier_and_idempotency(self):
        c=condition(field='REVENUE_FINANCIAL',op='GTE',value=1.25,value_type='NUMBER',unit='억원',quote='전년도 매출 1.25억원 이상')
        r,events,_=self.apply(c,'N2')
        self.assertEqual((r['value'],r['unit']),(125000000,'KRW'))
        self.assertEqual(self.apply(r,'N2')[0],r)
        self.assertEqual(len(events),1)
    def test_no_currency_guess(self):
        c=condition(field='REVENUE',op='GTE',value=4,value_type='NUMBER',unit='달러',quote='매출 4달러')
        self.assertEqual(self.apply(c,'N2')[0],c)
    def test_already_scaled_money_not_scaled_again(self):
        c=condition(field='REVENUE',op='GTE',value=400000000,value_type='NUMBER',unit='억원',quote='매출 4억원 이상')
        r,_,rej=self.apply(c,'N2');self.assertEqual(r,c);self.assertTrue(rej)
    def test_numeric_string_known_metric_only(self):
        c=self.quantitative(unit='YEAR',value='4');c['value_type']='STRING'
        r,_,_=self.apply(c,'N2');self.assertEqual((r['value'],r['value_type']),(4,'NUMBER'))
        c['field']=c['category_id']='BUSINESS_TYPE'
        self.assertEqual(self.apply(c,'N2')[0]['value'],'4')
    def test_boolean_not_numeric(self):
        with self.assertRaises(ValueError):n.decimal(True)
        self.assertEqual(n.json_number(Decimal('0.125')),0.125)
    def test_unknown_range_flags_held(self):
        c=condition(field='APPLICANT_AGE',op='BETWEEN',value={'minimum':21,'maximum':44},value_type='RANGE',unit='YEAR',quote='만 21세 이상 44세 이하')
        r,_,rej=self.apply(c,'N3');self.assertEqual(r,c);self.assertEqual(rej[0]['reason'],'BOUNDARY_FLAGS_NOT_EXPLICIT')
    def test_range_explicit_source_and_flags_preserved(self):
        c=condition(field='APPLICANT_AGE',op='BETWEEN',value={'minimum':21,'maximum':44,'min_inclusive':False,'max_inclusive':True},value_type='RANGE',unit='YEAR',quote='만 21세 초과 44세 이하')
        r,_,_=self.apply(c,'N3')
        self.assertEqual(r['value'],{'lower':{'value':21,'inclusive':False},'upper':{'value':44,'inclusive':True}})
        self.assertIsNone(n.llm._check_value_shape(r))
        self.assertEqual(self.apply(r,'N3')[0],r)
    def test_range_source_disagrees(self):
        c=condition(field='APPLICANT_AGE',op='BETWEEN',value={'min':21,'max':44,'min_inclusive':False,'max_inclusive':True},value_type='RANGE',unit='YEAR',quote='만 21세 이상 44세 이하')
        self.assertEqual(self.apply(c,'N3')[0],c)
    def test_forbidden_aliases_are_not_applied(self):
        for field in ['APPLICANT_TYPE','APPLICANT_ADDRESS','REPRESENTATIVE_AGE','EMPLOYMENT','REVENUE_FINANCIAL']:
            c=condition(field=field,op='EQ',value='일반 유형',value_type='STRING',quote='일반 유형')
            self.assertEqual(self.apply(c,'N4')[0],c)
    def test_existing_alias_is_delegated_to_v2(self):
        c=condition(field='BUSINESS_LOCATION',op='EQ',value='부산',value_type='STRING',quote='사업장 부산 소재')
        c['field']='business_location'
        r,events,_=self.apply(c,'N4')
        self.assertEqual(r,c);self.assertEqual(events,[])
        normalized,_,reason=n.llm.normalize_condition_attribute(r)
        self.assertIsNone(reason);self.assertEqual(normalized['field'],'BUSINESS_LOCATION')
    def test_original_and_temporal_preserved(self):
        c=self.quantitative(temporal_constraint={'anchor_event':'APPLICATION','offset_value':4,'offset_unit':'YEAR'})
        old=copy.deepcopy(c);r,_,_=self.apply(c)
        self.assertEqual(c,old);self.assertEqual(r['temporal_constraint'],old['temporal_constraint'])
        self.assertEqual(r['evidence_quotes'],old['evidence_quotes'])
    def test_ambiguous_attribute_remains_held(self):
        c=condition(field='APPLICANT_TYPE',op='EQ',value='소상공인',value_type='STRING',quote='소상공인 대상')
        self.assertEqual(self.apply(c)[0],c)
        self.assertEqual(n.llm.normalize_condition_attribute(c)[2],'ATTRIBUTE_SEMANTIC_AMBIGUITY')
    def test_pipeline_remaps_ids_and_keeps_evidence_logic_exception(self):
        c=self.quantitative();s=source_row(c['evidence_quotes'][0])
        obj=response([c],logic_sections=[{'section_type':'ELIGIBILITY','condition_indexes':[0],'operator':'UNRESOLVED','evidence_quote':c['evidence_quotes'][0]}],
            exceptions=[{'target_condition_indexes':[0],'effect':'WAIVE_REQUIREMENT','effect_target':'업력','precondition':'별도 승인','replacement':None,
                         'effect_confirmed':False,'application_mode':'EFFECT_ONLY','evidence_quote':c['evidence_quotes'][0]}])
        before=n.llm._response_to_artifacts(s,obj)
        normalized=copy.deepcopy(obj);normalized['conditions'][0]=self.apply(c)[0]
        after=n.llm._response_to_artifacts(s,normalized)
        self.assertNotEqual(before['conditions'][0]['condition_id'],after['conditions'][0]['condition_id'])
        self.assertEqual(before['conditions'][0]['source'],after['conditions'][0]['source'])
        self.assertEqual(after['logic_proposal']['exceptions'],obj['exceptions'])
        self.assertFalse(after['conditions'][0]['decision_eligible'])
        self.assertEqual(after['logic_proposal']['index_to_condition_id'][0],after['conditions'][0]['condition_id'])
    def test_unknown_operator_never_repaired(self):
        c=self.quantitative();c['operator']='UNKNOWN'
        r,_,_=self.apply(c);self.assertEqual(r['operator'],'UNKNOWN')
    def test_nested_logic_and_unresolved_references_preserved(self):
        original={'conditions':[{}, {}, {}],
            'logic_sections':[{'operator':'AND','condition_indexes':[0],
                'children':[{'operator':'OR','condition_indexes':[1,2]}]}],
            'exceptions':[{'target_condition_indexes':[2],'effect':'WAIVE_REQUIREMENT'}],
            'unresolved_relations':[{'condition_indexes':[1,2],'reason':'unknown scope'}]}
        saved=copy.deepcopy(original)
        proposal=n.llm.preserve_logic_references(original,{0:'normalized-id',1:'unchanged-id'})
        self.assertEqual(original,saved)
        self.assertEqual(proposal['unresolved_condition_indexes'],[2])
        self.assertEqual(proposal['logic_sections'][0]['operator'],'UNRESOLVED')
        self.assertEqual(proposal['logic_sections'][0]['children'][0]['operator'],'UNRESOLVED')
        self.assertEqual(proposal['unresolved_relations'],original['unresolved_relations'])
        self.assertEqual(proposal['exceptions'],original['exceptions'])
        self.assertFalse(proposal['exception_resolution'][0]['application_allowed'])
    def test_no_api_and_deterministic(self):
        with patch.object(n.llm,'OpenAIDirectProvider',side_effect=AssertionError('API_FORBIDDEN')):
            c=self.quantitative();self.assertEqual(self.apply(c),self.apply(c))

if __name__=='__main__':unittest.main()
