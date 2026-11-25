import hashlib, json, tempfile, unittest
from collections import Counter
from pathlib import Path
from tools.prepare_condition_inputs import OUT, SNAP, FACTS, KS, run, candidate_ref

def jl(path):
    with path.open(encoding='utf-8') as f:
        for line in f:
            if line.strip(): yield json.loads(line)

class ConditionInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=list(jl(OUT/'extraction_inputs.jsonl'))
        cls.dispositions=list(jl(OUT/'dispositions.jsonl'))
        cls.samples=list(jl(OUT/'representative_samples.jsonl'))
        cls.candidates=list(jl(OUT/'candidate_refs.jsonl'))
        wanted={r['notice_id'] for r in cls.inputs}; cls.notices={}
        for r in jl(SNAP/'notices.jsonl'):
            if r['notice_id'] in wanted: cls.notices[r['notice_id']]=r
        cids={c for row in cls.inputs for ev in row['evidence'] for c in ev['chunk_ids']}; cls.chunks={}
        for r in jl(SNAP/'chunks.jsonl'):
            if r['chunk_id'] in cids: cls.chunks[r['chunk_id']]=r
    def test_counts_and_disjoint_complete_id_sets(self):
        ids=[r['notice_id'] for r in self.dispositions]
        self.assertEqual(len(ids),197180); self.assertEqual(len(set(ids)),len(ids))
        target={r['notice_id'] for r in self.inputs}; deferred={r['notice_id'] for r in self.dispositions if r['disposition']=='DEFERRED'}
        self.assertEqual(len(target),5116); self.assertEqual(len(deferred),192064)
        self.assertFalse(target&deferred); self.assertEqual(target|deferred,set(ids))
    def test_evidence_and_candidate_references_resolve(self):
        cids={r['candidate_ref'] for r in self.candidates}
        self.assertEqual(len(cids),17211)
        self.assertTrue(all(r.get('legacy_candidate_ref') for r in self.candidates))
        for row in self.inputs:
            self.assertEqual(row['raw_text'],self.notices[row['notice_id']]['condition_texts']['eligibility']['text'])
            for ev in row['evidence']:
                self.assertEqual(ev['path'],'condition_texts.eligibility.text')
                self.assertTrue(ev['text'])
                for cid in ev['chunk_ids']:
                    self.assertIn(cid,self.chunks); self.assertEqual(self.chunks[cid]['notice_id'],row['notice_id'])
            self.assertTrue(set(row['candidate_refs'])<=cids)
            self.assertFalse(row['decision_eligible'])
    def test_candidate_reference_is_stable_and_distinguishes_evidence(self):
        a={'source_kind':'TEXT_RULE','section':'eligibility_api','source_field':'a','char_start':0,'attribute':'size','kind':'ELIGIBILITY','rule_id':'r','evidence_text':'기업','value':{'label':'SME'}}
        b={**a,'section':'att_eligibility','source_field':'b'}
        self.assertEqual(candidate_ref('N',a)[1],candidate_ref('N',a)[1])
        self.assertNotEqual(candidate_ref('N',a)[1],candidate_ref('N',b)[1])
        self.assertEqual(sorted([candidate_ref('N',a)[1],candidate_ref('N',b)[1]]),sorted([candidate_ref('N',b)[1],candidate_ref('N',a)[1]]))
    def test_samples_split_counts_no_overlap_and_pii_safe(self):
        self.assertEqual(len(self.samples),100)
        ids=[r['notice_id'] for r in self.samples]; self.assertEqual(len(set(ids)),100)
        counts=Counter((r['source_system'],r['split']) for r in self.samples)
        self.assertEqual(counts,{('BIZINFO','DEVELOPMENT'):40,('BIZINFO','EVALUATION'):10,('KSTARTUP','DEVELOPMENT'):40,('KSTARTUP','EVALUATION'):10})
        for r in self.samples: self.assertFalse(r['decision_eligible']); self.assertEqual(r['review_status'],'UNREVIEWED')
    def test_g2b_is_deferred_and_candidate_statuses_preserved(self):
        g=[r for r in self.dispositions if r['source_system']=='G2B']
        self.assertEqual(len(g),192064); self.assertTrue(all(r['disposition']=='DEFERRED' for r in g))
        report=json.loads((OUT/'analysis_report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['kstartup_review_status_counts'],{'needs_review':27945,'not_found':18231})
        self.assertEqual(report['kstartup_duplicate_ids'],0)
    def test_deterministic_recreation(self):
        with tempfile.TemporaryDirectory() as d:
            run(Path(d))
            for name in ('candidate_refs.jsonl','dispositions.jsonl','extraction_inputs.jsonl','g2b_deferred_samples.jsonl','kstartup_candidate_audit.jsonl','representative_samples.jsonl'):
                self.assertEqual(hashlib.sha256((OUT/name).read_bytes()).digest(),hashlib.sha256((Path(d)/name).read_bytes()).digest(),name)

if __name__=='__main__': unittest.main()
