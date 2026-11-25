import json, unittest
from pathlib import Path
from tools.extract_condition_candidates import extract_one, LLMProvider
from tests.test_condition_schema import make_validator

def row(text):
    return {'notice_id':'TEST:1','source_system':'BIZINFO','raw_text':text,'evidence':[{'chunk_ids':[]}]}

class ExtractorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator=make_validator()
        cls.schemas=Path('schemas/conditions')
        from jsonschema import Draft202012Validator,FormatChecker
        from referencing import Registry,Resource
        resources=[]; root=None
        for p in cls.schemas.glob('*.schema.json'):
            s=json.loads(p.read_text(encoding='utf-8')); resources.append((s['$id'],Resource.from_contents(s)))
            if p.name=='condition-v1.schema.json': root=s
        cls.condition_validator=Draft202012Validator(root,registry=Registry().with_resources(resources),format_checker=FormatChecker())
    def test_numeric_boundaries_age_business_and_region(self):
        cs=extract_one(row('창업 후 7년 이하이며, 중소기업이고 서울특별시에 소재'))
        self.assertTrue(any(c['field']=='BUSINESS_AGE' and c['operator']=='LTE' and c['value']==7 for c in cs))
        self.assertTrue(any(c['field']=='BUSINESS_TYPE' for c in cs)); self.assertTrue(any(c['field']=='BUSINESS_LOCATION' for c in cs))
    def test_exclusion_preference_and_unclassified_remain_unverified(self):
        cs=extract_one(row('다만 체납기업은 제외한다. 여성기업은 가점 대상.'))
        self.assertTrue(all(c['decision_eligible'] is False for c in cs))
        self.assertTrue(all(c['review_status']!='VERIFIED' for c in cs))
        self.assertIn('EXCLUSION',[c['condition_type'] for c in cs]); self.assertIn('PREFERENCE',[c['condition_type'] for c in cs])
    def test_evidence_offsets_match_raw_source_and_schema(self):
        text='대상 요건:\n중소기업이며 창업 후 3년 미만'
        for c in extract_one(row(text)):
            self.assertEqual(text[c['source']['location']['start_char']:c['source']['location']['end_char']],c['source']['evidence_text'])
            self.assertFalse(list(self.condition_validator.iter_errors(c)))
    def test_no_synthetic_values_and_llm_failure_closed(self):
        cs=extract_one(row('매출 실적이 일정 기준 이상이어야 함'))
        self.assertTrue(all(c['decision_eligible'] is False for c in cs))
        self.assertEqual(LLMProvider().extract('원문',model='none',prompt_version='v1')['status'],'NOT_CONFIGURED')
    def test_deterministic_ids(self):
        self.assertEqual([c['condition_id'] for c in extract_one(row('중소기업, 창업 후 3년 이내'))],[c['condition_id'] for c in extract_one(row('중소기업, 창업 후 3년 이내'))])
    def test_multiple_types_regions_and_explanatory_text(self):
        cs=extract_one(row('중소기업과 소상공인 대상, 서울과 경기 소재기업 신청 가능'))
        types=[c['raw_text'] for c in cs if c['field']=='BUSINESS_TYPE']
        regions=[c['raw_text'] for c in cs if c['field']=='BUSINESS_LOCATION']
        self.assertIn('중소기업',types); self.assertIn('소상공인',types)
        self.assertIn('서울',regions); self.assertIn('경기',regions)
        self.assertTrue(all(c['decision_eligible'] is False for c in cs))

if __name__=='__main__': unittest.main()
