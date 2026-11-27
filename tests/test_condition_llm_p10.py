import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import extract_condition_candidates_llm as llm
from tools import run_condition_llm_p10 as p10
from tools import run_condition_llm_openai_pilot_r2_norm_v2_p8 as engine

class LogicReferenceTests(unittest.TestCase):
    def source(self):
        return {'conditions': [{} for _ in range(6)], 'logic_sections': [
            {'operator': 'AND', 'condition_indexes': [0], 'children': [
                {'operator': 'OR', 'condition_indexes': [1, 2]}]}],
            'exceptions': [{'target_condition_indexes': [3], 'effect': 'EXCLUDE_FROM_SCOPE'}],
            'unresolved_relations': [{'condition_indexes': [2, 4], 'reason': 'unknown'}]}

    def test_all_structures_and_unreferenced_candidates(self):
        source = self.source()
        original = copy.deepcopy(source)
        result = llm.preserve_logic_references(source, {0: 'C0'})
        self.assertEqual(source, original)
        self.assertEqual(result['unresolved_condition_indexes'], [1,2,3,4,5])
        self.assertEqual(result['unreferenced_unresolved_condition_indexes'], [5])
        self.assertEqual(result['logic_sections'][0]['operator'], 'UNRESOLVED')
        self.assertEqual(result['logic_sections'][0]['children'][0]['operator'], 'UNRESOLVED')
        self.assertEqual(result['exceptions'], source['exceptions'])
        self.assertFalse(result['exception_resolution'][0]['application_allowed'])
        self.assertEqual(result['exception_resolution'][0]['unresolved_target_indexes'], [3])
        self.assertEqual(result['unresolved_relations'], source['unresolved_relations'])
        self.assertEqual(result['logical_completeness'], 'INCOMPLETE')

    def test_invalid_index_is_detected(self):
        source = self.source()
        source['exceptions'][0]['target_condition_indexes'].append(9)
        self.assertEqual(llm.preserve_logic_references(source, {})['invalid_reference_indexes'], [9])

    def test_valid_targets_are_never_automatically_applied(self):
        r = llm.preserve_logic_references(self.source(), {i: str(i) for i in range(6)})
        self.assertEqual(r['unresolved_condition_indexes'], [])
        self.assertFalse(r['exception_resolution'][0]['application_allowed'])

    def test_duplicate_references_are_deterministic(self):
        s = self.source()
        s['exceptions'].append(copy.deepcopy(s['exceptions'][0]))
        self.assertEqual(llm.preserve_logic_references(s, {})['unresolved_condition_indexes'], list(range(6)))

    def test_held_and_rejected_exception_targets_remain_blocked(self):
        for field, value in [('applicant_type', '소상공인'), ('unknown_attribute', 'x')]:
            condition = {'field':field, 'category_id':'APPLICANT_TYPE', 'value':value,
                         'evidence_quotes':[value]}
            _, _, reason = llm.normalize_condition_attribute(condition)
            self.assertIsNotNone(reason)
            s = self.source()
            s['conditions'][3] = condition
            result = llm.preserve_logic_references(s, {0:'valid'})
            self.assertFalse(result['exception_resolution'][0]['application_allowed'])
            self.assertIn(3, result['unresolved_condition_indexes'])

    def test_gate_blocks_tampered_exception_and_invalid_reference(self):
        import shutil
        source = p10.OUT / 'notice_06'
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'notice'
            shutil.copytree(source, target)
            report = p10.base.read_json(target / 'attribute_replay_v2/replay_report.json')
            logic_file = target / 'attribute_replay_v2/logic_proposals.jsonl'
            original = llm._read_jsonl(logic_file)
            for mutate in ['exception', 'complete', 'missing']:
                rows = copy.deepcopy(original)
                if mutate == 'exception': rows[0]['exception_resolution'][0]['application_allowed'] = True
                if mutate == 'complete': rows[0]['logical_completeness'] = 'COMPLETE'
                if mutate == 'missing': rows[0]['unresolved_condition_indexes'].remove(3)
                llm._write_jsonl(logic_file, rows)
                self.assertEqual(p10.base.tech_gate_for_notice(target, report)['status'], 'BLOCKED')

    def test_replay_seven_and_candidate_identity(self):
        report = p10.base.read_json(p10.OUT / 'comparison_report.json')
        self.assertEqual(len(report['comparison']), 7)
        self.assertTrue(all(r['candidates_identical'] and r['gate']['status']=='PASS' for r in report['comparison']))
        target = llm._read_jsonl(p10.OUT / 'notice_06/attribute_replay_v2/logic_proposals.jsonl')[0]
        self.assertEqual(target['unresolved_condition_indexes'], [0,3,4,5])
        self.assertEqual(target['exception_resolution'][0]['application_status'], 'BLOCKED_UNRESOLVED_TARGET')

    def test_budget_only_ordinals_11_through_13_in_temporary_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            engine.write_json(out / 'request_ledger.json', {'limit':13,'used':10,'attempts':[], 'p8_attempts':[]})
            with patch.multiple(engine, RUN_DIR=out, ALREADY_USED=10, P8_MAX_REQUESTS=3):
                b = engine.P8Budget('synthetic')
                self.assertEqual([b.consume() for _ in range(4)], [True,True,True,False])
            saved = engine.read_json(out / 'request_ledger.json')
            self.assertEqual([x['request_ordinal'] for x in saved['p8_attempts']], [11,12,13])

if __name__ == '__main__':
    unittest.main()
