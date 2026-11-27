from __future__ import annotations

import copy
import json
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tools import extract_condition_candidates_llm as llm
from tools import run_condition_llm_openai_pilot_r2 as parent_runner
from tools import run_condition_llm_openai_pilot_r2_norm_v2 as runner


def condition(field: str, category: str, value, quote: str, **extra):
    return {"field": field, "category_id": category, "value": value,
            "evidence_quotes": [quote], **extra}


class AttributeNormalizationV2Tests(unittest.TestCase):
    def test_uppercase_applicant_type_business_size_is_held(self):
        source = condition("APPLICANT_TYPE", "APPLICANT_TYPE", "소상공인", "소상공인")
        normalized, record, reason = llm.normalize_condition_attribute(source)
        self.assertEqual(reason, "ATTRIBUTE_SEMANTIC_AMBIGUITY")
        self.assertEqual(record["mapping_status"], "AMBIGUOUS")
        self.assertIsNone(record["normalized_field"])
        self.assertEqual(normalized["field"], "APPLICANT_TYPE")
        self.assertEqual(record["original_value"], source["value"])
        self.assertEqual(record["original_evidence_quotes"], source["evidence_quotes"])

    def test_lowercase_and_uppercase_applicant_type_have_same_ambiguity(self):
        low = llm.normalize_condition_attribute(condition("applicant_type", "APPLICANT_TYPE", "소상공인", "소상공인"))
        upper = llm.normalize_condition_attribute(condition("APPLICANT_TYPE", "APPLICANT_TYPE", "소상공인", "소상공인"))
        self.assertEqual(low[2], upper[2])
        self.assertEqual(low[1]["mapping_status"], upper[1]["mapping_status"])
        self.assertEqual(low[1]["normalized_field"], upper[1]["normalized_field"])

    def test_clear_applicant_type_is_not_held(self):
        normalized, record, reason = llm.normalize_condition_attribute(
            condition("APPLICANT_TYPE", "APPLICANT_TYPE", "대학(원)생", "대학(원)생"))
        self.assertIsNone(reason)
        self.assertEqual(normalized["field"], "APPLICANT_TYPE")
        self.assertEqual(record["mapping_status"], "IDENTITY")

    def test_unknown_attribute_is_rejected(self):
        _, _, reason = llm.normalize_condition_attribute(condition("UNKNOWN_FIELD", "UNCLASSIFIED", "x", "x"))
        self.assertEqual(reason, "UNSUPPORTED_ATTRIBUTE")

    def test_field_category_mismatch_is_rejected(self):
        normalized, _, reason = llm.normalize_condition_attribute(
            condition("applicant_address", "BUSINESS_LOCATION", "서울", "서울"))
        self.assertEqual(normalized["field"], "APPLICANT_ADDRESS")
        self.assertEqual(reason, "ATTRIBUTE_CATEGORY_MISMATCH")

    def test_date_and_temporal_values_are_preserved(self):
        source = condition("business_location", "BUSINESS_LOCATION", "서울", "서울",
                           reference_date_type="FIXED", reference_date="2024-01-01",
                           temporal_constraint={"operator": "LT", "offset_value": 2, "offset_unit": "YEAR"})
        normalized, _, reason = llm.normalize_condition_attribute(source)
        self.assertIsNone(reason)
        for key in ("reference_date_type", "reference_date", "temporal_constraint"):
            self.assertEqual(normalized[key], source[key])


class ChildLineageAndBudgetTests(unittest.TestCase):
    def test_parent_r2_artifacts_remain_unchanged_and_blocked(self):
        paths = [runner.PARENT_MANIFEST, runner.PARENT_LEDGER, runner.PARENT_GATE, runner.PARENT_RAW]
        before = {p: runner.digest(p) for p in paths}
        lineage = runner.verify_parent_lineage()
        self.assertEqual(lineage["status"], "LEAD_BLOCKED")
        self.assertTrue(lineage["parent_continuation_blocked"])
        self.assertEqual(before, {p: runner.digest(p) for p in paths})

    def test_parent_continue_fingerprint_rejects_v2_extractor_without_api(self):
        ids = parent_runner.prior.read_json(parent_runner.prior.PREPARATION / "pilot_notice_ids.json")
        parent = runner.read_json(runner.PARENT_MANIFEST)
        fp = parent_runner.fingerprint(ids, parent["fingerprint"]["model_id"])
        with self.assertRaisesRegex(RuntimeError, "R2_CODE_CHANGE_RECORD_MISMATCH"):
            parent_runner.assert_same_run(runner.PARENT_MANIFEST, fp)

    def test_parent_usage_is_inherited_without_new_budget(self):
        parent = runner.read_json(runner.PARENT_LEDGER)
        inherited = {"limit": 12, "used": parent["used"], "parent_used": 3,
                     "new_budget_granted": 0, "child_limit": 9}
        self.assertEqual(parent["used"], 3)
        self.assertEqual(inherited["used"] + inherited["child_limit"], inherited["limit"])
        self.assertEqual(inherited["new_budget_granted"], 0)

    def test_child_budget_uses_only_ordinals_four_through_twelve(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "ledger.json"
            parent = runner.read_json(runner.PARENT_LEDGER)
            ledger = {"limit": 12, "used": 3, "attempts": copy.deepcopy(parent["attempts"]),
                      "child_attempts": [], "lineage": {"child_limit": 9}}
            runner.write_json_atomic(path, ledger)
            with patch.object(runner, "LOCK_PATH", root / "budget.lock"):
                budget = runner.ChildLedgerBudget(path, "N")
                ordinals = []
                for _ in range(10):
                    if budget.consume():
                        ordinals.append(budget.used)
            saved = runner.read_json(path)
            self.assertEqual(ordinals, list(range(4, 13)))
            self.assertEqual(saved["used"], 12)
            self.assertEqual(len(saved["child_attempts"]), 9)

    def test_only_one_successor_can_claim_inherited_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claim.json"
            claim = {"run_id": runner.RUN_ID, "fingerprint": {"sha256": "a"}}
            self.assertTrue(runner.claim_single_successor(path, claim))
            self.assertFalse(runner.claim_single_successor(path, claim))
            with self.assertRaisesRegex(RuntimeError, "ALREADY_CLAIMED"):
                runner.claim_single_successor(path, {"run_id": "other-child"})

    def test_budget_lock_serializes_concurrent_threads(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(runner, "LOCK_PATH", Path(directory) / "lock"):
            active = 0
            maximum = 0
            state_lock = threading.Lock()

            def task():
                nonlocal active, maximum
                with runner.successor_lock():
                    with state_lock:
                        active += 1
                        maximum = max(maximum, active)
                    time.sleep(0.02)
                    with state_lock:
                        active -= 1

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lambda _: task(), range(8)))
            self.assertEqual(maximum, 1)

    def test_fingerprint_change_blocks_child(self):
        with self.assertRaisesRegex(RuntimeError, "CHILD_FINGERPRINT_CHANGED"):
            runner.validate_saved_fingerprint({"extractor_sha256": "old"}, {"extractor_sha256": "new"})

    def test_preflight_runs_fourteen_checks_without_api(self):
        with patch.object(llm, "call_and_parse", side_effect=AssertionError("API path called")), \
                patch.object(llm, "run_pilot", side_effect=AssertionError("live runner called")):
            result = runner.check_dependencies()
        self.assertEqual(result["fixed_input_check_count"], 14)
        self.assertTrue(all(result["fixed_input_checks"].values()))
        self.assertEqual(result["api_call_count"], 0)

    def test_live_mode_requires_explicit_api_authorization(self):
        with patch.object(sys, "argv", ["runner", "--run-remaining"]), \
                patch.object(runner, "run_remaining", side_effect=AssertionError("live mode entered")):
            with self.assertRaises(SystemExit) as raised:
                runner.main()
        self.assertEqual(raised.exception.code, 2)


class TechnicalGateTests(unittest.TestCase):
    @staticmethod
    def write_jsonl(path: Path, rows):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def test_held_semantic_candidate_does_not_fail_technical_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            detail = {"evidence_quote_validation": "PASS", "date_temporal_preserved": True,
                      "decision_eligible": False}
            for name, rows in {
                "validation_details.jsonl": [detail, detail],
                "logic_proposals.jsonl": [{"logical_completeness": "INCOMPLETE", "unresolved_condition_indexes": [0]}],
            }.items():
                self.write_jsonl(root / name, rows)
            result = runner.tech_gate_for_replay_only({"api_call_count": 0, "v11_schema_error_count": 0,
                "accepted_unreviewed_count": 1, "held_for_review_count": 1, "rejected_count": 0,
                "proposal_count": 2, "decision_eligible_true_count": 0}, root)
            self.assertEqual(result["status"], "PASS")
            self.assertFalse(result["decision_eligible"])

    def test_no_valid_candidate_blocks_technical_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_jsonl(root / "validation_details.jsonl", [{"evidence_quote_validation": "PASS",
                "date_temporal_preserved": True, "decision_eligible": False}])
            self.write_jsonl(root / "logic_proposals.jsonl", [])
            result = runner.tech_gate_for_replay_only({"api_call_count": 0, "v11_schema_error_count": 0,
                "accepted_unreviewed_count": 0, "held_for_review_count": 0, "rejected_count": 1,
                "proposal_count": 1, "decision_eligible_true_count": 0}, root)
            self.assertEqual(result["status"], "BLOCKED")

    def test_zero_valid_candidates_can_pass_technical_gate_and_remain_quality_flagged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            replay_dir = root / "attribute_replay_v2"
            replay_dir.mkdir()
            self.write_jsonl(root / "per_notice_execution.jsonl", [{"status": "COMPLETED"}])
            self.write_jsonl(root / "raw_llm_responses.jsonl", [{"response_attempts": ["{}"]}])
            self.write_jsonl(root / "predictions_before_validation.jsonl", [
                {"proposal_index": i} for i in range(3)])
            self.write_jsonl(root / "validation_details.jsonl", [
                {"decision_eligible": False, "reason": "UNSUPPORTED_ATTRIBUTE"} for _ in range(3)])
            self.write_jsonl(replay_dir / "validation_details.jsonl", [
                {"evidence_quote_validation": "PASS", "date_temporal_preserved": True,
                 "final_status": "REJECTED", "decision_eligible": False} for _ in range(3)])
            self.write_jsonl(replay_dir / "logic_proposals.jsonl", [
                {"logical_completeness": "INCOMPLETE", "unresolved_condition_indexes": [0, 1, 2],
                 "logic_sections": [{"condition_indexes": [0, 1, 2], "operator": "UNRESOLVED"}]}])
            (root / "run_report.json").write_text(json.dumps({"failure_count": 0, "schema_error_count": 0}), encoding="utf-8")
            report = {"accepted_unreviewed_count": 0, "held_for_review_count": 0,
                      "rejected_count": 3, "proposal_count": 3, "v11_schema_error_count": 0,
                      "api_call_count": 0, "decision_eligible_true_count": 0}
            original = {"conditions": [{}, {}, {}], "logic_sections": [
                {"condition_indexes": [0,1,2], "operator": "AND"}],
                "exceptions": [], "unresolved_relations": []}
            self.write_jsonl(root / "raw_llm_responses.jsonl", [{"response_attempts": [json.dumps(original)]}])
            details = [{"proposal_index": i, "final_status": "REJECTED",
                        "evidence_quote_validation": "PASS", "date_temporal_preserved": True,
                        "decision_eligible": False} for i in range(3)]
            self.write_jsonl(replay_dir / "validation_details.jsonl", details)
            proposal = llm.preserve_logic_references(original, {})
            proposal["index_to_condition_id"] = {}
            proposal["proposal_validation_states"] = {str(i): "REJECTED_OR_DEDUPLICATED" for i in range(3)}
            self.write_jsonl(replay_dir / "logic_proposals.jsonl", [proposal])
            result = runner.tech_gate_for_notice(root, report)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["valid_candidate_count"], 0)
            self.assertEqual(result["extraction_quality_state"], "ZERO_VALID_CANDIDATES")
            self.assertEqual(result["extraction_quality_gate"], "REVIEW_REQUIRED")
            self.assertFalse(result["decision_eligible"])


if __name__ == "__main__":
    unittest.main()
