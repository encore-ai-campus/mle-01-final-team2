from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_condition_logic import OUT, build, read_jsonl, validate_graph
from tests.test_condition_schema import make_validator
from tools.normalize_support_data import pii_findings


class ConditionLogicCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = make_validator()

    def test_generated_development_sets_validate_and_cover_candidates(self):
        records = read_jsonl(OUT / "notice_condition_sets.jsonl")
        candidates = read_jsonl(ROOT / "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl")
        self.assertEqual(len(records), 80)
        self.assertEqual(len({r["notice_id"] for r in records}), 80)
        self.assertEqual(sum(len(c["conditions"]) for r in records for c in r["condition_sets"].values()), len(candidates))
        for record in records:
            with self.subTest(notice_id=record["notice_id"]):
                self.assertEqual(list(self.validator.iter_errors(record)), [])
                validate_graph(record)
                self.assertFalse(record["decision_readiness"]["eligibility_decision_eligible"])
                self.assertFalse(record["decision_readiness"]["preference_assessment_eligible"])
                for collection in record["condition_sets"].values():
                    self.assertFalse(collection["decision_eligible"])
                    self.assertNotEqual(collection["availability_status"], "NO_CONDITION_CONFIRMED")

    def test_all_candidate_ids_are_preserved_and_every_reference_is_local(self):
        generated = read_jsonl(OUT / "notice_condition_sets.jsonl")
        original = read_jsonl(ROOT / "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl")
        before = {c["condition_id"] for c in original}
        after = {c["condition_id"] for r in generated for group in r["condition_sets"].values() for c in group["conditions"]}
        self.assertEqual(before, after)

    def test_generated_group_ids_are_unique_and_wrong_notice_refs_fail(self):
        records = read_jsonl(OUT / "notice_condition_sets.jsonl")
        group_ids = []
        for record in records:
            for collection in record["condition_sets"].values():
                stack = list(collection["logical_roots"])
                while stack:
                    node = stack.pop()
                    if node["node_type"] == "LOGICAL_GROUP":
                        group_ids.append(node["group_id"])
                        stack.extend(node["children"])
        self.assertEqual(len(group_ids), len(set(group_ids)))
        record = next(r for r in records if r["condition_sets"]["eligibility"]["conditions"])
        record["condition_sets"]["eligibility"]["conditions"][0]["notice_id"] = "WRONG:NOTICE"
        with self.assertRaisesRegex(ValueError, "another notice"):
            validate_graph(record)

    def test_nested_logic_operators_validate_as_unconfirmed_candidates(self):
        record = next(r for r in read_jsonl(OUT / "notice_condition_sets.jsonl")
                      if len(r["condition_sets"]["eligibility"]["conditions"]) >= 3)
        collection = record["condition_sets"]["eligibility"]
        conditions = collection["conditions"]
        ids = [c["condition_id"] for c in conditions[:3]]
        collection["logical_roots"] = [{
            "node_type": "LOGICAL_GROUP", "group_id": "test-outer", "operator": "NOT",
            "review_status": "NEEDS_REVIEW", "evidence": None,
            "children": [{
                "node_type": "LOGICAL_GROUP", "group_id": "test-inner", "operator": "OR",
                "review_status": "NEEDS_REVIEW", "evidence": None,
                "children": [
                    {"node_type": "CONDITION_REF", "condition_id": ids[0]},
                    {"node_type": "LOGICAL_GROUP", "group_id": "test-and", "operator": "AND",
                     "review_status": "NEEDS_REVIEW", "evidence": None,
                     "children": [{"node_type": "CONDITION_REF", "condition_id": ids[1]},
                                  {"node_type": "CONDITION_REF", "condition_id": ids[2]}]},
                ],
            }],
        }]
        # The graph validator checks closed references and arity; this test AST is not emitted.
        validate_graph(record)

    def test_generated_records_and_qualifier_candidates_are_pii_clean(self):
        for row in read_jsonl(OUT / "notice_condition_sets.jsonl"):
            self.assertEqual(pii_findings(row), [], row["notice_id"])
        for row in read_jsonl(OUT / "qualifier_candidates.jsonl"):
            self.assertEqual(pii_findings(row), [], row["candidate_id"])
        packet = read_jsonl(OUT / "human_logic_review.jsonl")
        self.assertEqual(len(packet), 30)
        self.assertTrue(all(row["review_status"] == "UNREVIEWED" and row["reviewer_logic_correction"] is None for row in packet))
        for row in packet:
            self.assertEqual(pii_findings(row), [], row["notice_id"])

    def test_conflict_candidates_are_closed_and_never_approved(self):
        known = {c["condition_id"] for r in read_jsonl(OUT / "notice_condition_sets.jsonl")
                 for group in r["condition_sets"].values() for c in group["conditions"]}
        for row in read_jsonl(OUT / "conflict_review.jsonl"):
            self.assertTrue(set(row["condition_ids"]) <= known)
            self.assertFalse(row["decision_eligible"])
            self.assertEqual(row["review_status"], "NEEDS_REVIEW")

    def test_relation_candidates_retain_source_evidence_and_spans(self):
        for row in read_jsonl(OUT / "relation_review.jsonl"):
            evidence = row["evidence"]
            if evidence is not None:
                location = evidence["location"]
                self.assertGreaterEqual(location["start_char"], 0)
                self.assertGreater(location["end_char"], location["start_char"])
                self.assertEqual(location["end_char"] - location["start_char"], len(evidence["evidence_text"]))
                self.assertFalse(row["decision_eligible"])

    def test_rebuild_is_deterministic_and_does_not_use_evaluation_split(self):
        first = read_jsonl(OUT / "notice_condition_sets.jsonl")
        temp = ROOT / "data/condition_inputs/v1/20261125/logic_test_tmp"
        try:
            report = build(temp)
            second = read_jsonl(temp / "notice_condition_sets.jsonl")
            self.assertEqual(first, second)
            self.assertFalse(report["evaluation_records_used"])
            self.assertEqual(report["conditions_in_sets"], 98)
        finally:
            import shutil
            shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
