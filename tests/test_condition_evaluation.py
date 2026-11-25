from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evaluate_condition_pipeline import (
    compare_logic,
    evaluate,
    evaluate_conditions,
    match_conditions,
    preflight,
)
from tools.ingest_condition_gold_reviews import ingest, make_id


def gold_condition(cid="GOLD:A", *, start=0, end=3, text="SME", **changes):
    row = {
        "gold_condition_id": cid, "condition_type": "ELIGIBILITY", "category": "BUSINESS_TYPE",
        "field": "BUSINESS_TYPE", "applicability_scope": None, "operator": "EQ",
        "value": "SME", "value_type": "STRING", "unit": None, "reference_date": None,
        "reference_date_type": "UNKNOWN", "raw_text": text, "source_field": "condition_texts.eligibility.text",
        "evidence_reference": {"start_char": start, "end_char": end}, "source_completeness": "COMPLETE",
        "decision_possible": True, "review_status": "VERIFIED", "review_comment": None,
        "matched_candidate_ids": [],
    }
    row.update(changes)
    return row


def prediction(cid="CAND:A", *, start=0, end=3, text="SME", **changes):
    row = {
        "condition_id": cid, "notice_id": "NOTICE:1", "condition_type": "ELIGIBILITY",
        "category_id": "BUSINESS_TYPE", "field": "BUSINESS_TYPE", "operator": "EQ",
        "value": "SME", "value_type": "STRING", "unit": None,
        "reference_date": {"value": None, "date_type": "UNKNOWN"}, "raw_text": text,
        "source": {"source_field": "condition_texts.eligibility.text", "location": {"start_char": start, "end_char": end}, "evidence_text": text},
    }
    row.update(changes)
    return row


def ref(cid):
    return {"node_type": "CONDITION_REF", "condition_id": cid}


def group(op, *children, gid="G"):
    return {"node_type": "LOGICAL_GROUP", "group_id": gid, "operator": op,
            "review_status": "VERIFIED", "evidence": None, "children": list(children)}


class ConditionEvaluationTests(unittest.TestCase):
    def test_synthetic_case_manifest_is_separate_from_real_metrics(self):
        fixture = json.loads((ROOT / "sample_data/conditions/condition-evaluation-synthetic-cases-v1.json").read_text(encoding="utf-8"))
        self.assertEqual(fixture["kind"], "SYNTHETIC_TEST")
        self.assertFalse(fixture["used_for_real_notice_metrics"])
        ids = {case["id"] for case in fixture["scenarios"]}
        self.assertTrue({"CONDITION_PERFECT", "CONDITION_MISSING", "CONDITION_DUPLICATE", "LOGIC_NOT_SCOPE_MISMATCH", "EMPTY_GOLDSET"} <= ids)

    def test_full_one_to_one_match_and_numeric_surface_normalization(self):
        gold = gold_condition(value=1000, value_type="NUMBER", unit="원")
        pred = prediction(value="1,000", value_type="NUMBER", unit="원")
        result = match_conditions([gold], [pred])
        self.assertEqual(result["full_pairs"], [(0, 0)])
        metrics = evaluate_conditions([{"notice_id": "NOTICE:1", "source_system": "BIZINFO", "gold_conditions": [gold]}], {"NOTICE:1": [pred]})
        self.assertEqual(metrics["micro"]["tp"], 1)
        self.assertEqual(metrics["micro"]["precision"], 1.0)
        self.assertEqual(metrics["micro"]["recall"], 1.0)

    def test_missing_extra_duplicate_and_partial_mismatch_counts(self):
        a = gold_condition("GOLD:A")
        b = gold_condition("GOLD:B", start=4, end=7, text="ABC", value="ABC")
        pred_a = prediction("P:A")
        pred_duplicate = prediction("P:A2")
        result = evaluate_conditions([{"notice_id": "NOTICE:1", "source_system": "BIZINFO", "gold_conditions": [a, b]}],
                                    {"NOTICE:1": [pred_a, pred_duplicate]})
        self.assertEqual((result["micro"]["tp"], result["micro"]["fp"], result["micro"]["fn"]), (1, 1, 1))
        mismatch = prediction("P:X", operator="NEQ", value="OTHER")
        partial = match_conditions([a], [mismatch])
        self.assertEqual(len(partial["partial_pairs"]), 1)
        self.assertEqual(len(partial["full_pairs"]), 0)

    def test_partial_semantics_never_count_as_true_positive(self):
        gold = gold_condition()
        pred = prediction(operator="GTE", value="SME")
        result = evaluate_conditions([{"notice_id": "NOTICE:1", "source_system": "KSTARTUP", "gold_conditions": [gold]}],
                                    {"NOTICE:1": [pred]})
        self.assertEqual(result["micro"]["tp"], 0)
        self.assertEqual(result["micro"]["fp"], 1)
        self.assertEqual(result["micro"]["fn"], 1)
        self.assertEqual(result["partial_match_diagnostics"]["count"], 1)

    def test_zero_denominators_are_unavailable_not_zero_accuracy(self):
        result = evaluate_conditions([{"notice_id": "NOTICE:1", "source_system": "BIZINFO", "gold_conditions": []}], {})
        self.assertIsNone(result["micro"]["precision"])
        self.assertIsNone(result["micro"]["recall"])
        self.assertEqual(result["micro"]["precision_status"], "NO_PREDICTIONS")
        self.assertEqual(result["micro"]["recall_status"], "NO_GOLD_CONDITIONS")

    def test_extra_predictions_are_false_positives(self):
        gold = gold_condition()
        result = evaluate_conditions([{"notice_id": "NOTICE:1", "source_system": "BIZINFO", "gold_conditions": [gold]}],
                                    {"NOTICE:1": [prediction("P1"), prediction("P2")]})
        self.assertEqual((result["micro"]["tp"], result["micro"]["fp"], result["micro"]["fn"]), (1, 1, 0))

    def test_source_type_category_and_notice_omission_breakdowns(self):
        g1 = gold_condition("GOLD:1")
        g2 = gold_condition("GOLD:2", start=4, end=7, text="ABC", condition_type="PREFERENCE", category="INDUSTRY", field="INDUSTRY")
        rows = [
            {"notice_id": "N1", "source_system": "BIZINFO", "gold_conditions": [g1]},
            {"notice_id": "N2", "source_system": "KSTARTUP", "gold_conditions": [g2]},
        ]
        metrics = evaluate_conditions(rows, {"N1": [prediction()]})
        self.assertEqual(metrics["by_source"]["BIZINFO"]["tp"], 1)
        self.assertEqual(metrics["by_source"]["KSTARTUP"]["fn"], 1)
        self.assertIn("PREFERENCE", metrics["by_condition_type"])
        self.assertIn("INDUSTRY", metrics["by_category"])
        self.assertEqual(metrics["notice_condition_omission"]["notices_with_misses"], 1)

    def test_logic_child_order_and_associative_grouping_are_canonical(self):
        gold = [group("AND", ref("A"), group("OR", ref("B"), ref("C"), gid="nested"), gid="root")]
        pred = [group("AND", group("OR", ref("C"), ref("B"), gid="other-nested"), ref("A"), gid="other-root")]
        self.assertTrue(compare_logic(gold, pred)["notice_structure_exact"])
        flat_gold = [group("AND", ref("A"), group("AND", ref("B"), ref("C"), gid="inner"), gid="outer")]
        flat_pred = [group("AND", group("AND", ref("A"), ref("B"), gid="inner2"), ref("C"), gid="outer2")]
        self.assertTrue(compare_logic(flat_gold, flat_pred)["notice_structure_exact"])

    def test_operator_swap_and_not_scope_are_detected(self):
        and_root = [group("AND", ref("A"), ref("B"))]
        or_root = [group("OR", ref("A"), ref("B"))]
        self.assertFalse(compare_logic(and_root, or_root)["notice_structure_exact"])
        gold_not = [group("NOT", group("OR", ref("A"), ref("B"), gid="inside"))]
        wrong_scope = [group("AND", group("NOT", ref("A"), gid="na"), ref("B"))]
        self.assertFalse(compare_logic(gold_not, wrong_scope)["notice_structure_exact"])

    def test_exception_and_preference_benefit_targets_are_scored(self):
        gold_exc = [{"raw_text": "except B", "applies_to_gold_ids": ["GOLD:B"], "linkage_status": "LINKED"}]
        pred_record = {"conditions": [{"condition_id": "P:B", "qualifiers": [{"qualifier_type": "EXCEPTION",
                         "raw_text": "except B", "applies_to_condition_ids": ["P:B"], "linkage_status": "LINKED"}],
                         "benefit": {"raw_text": "bonus", "applies_when_condition_ids": ["P:B"]}}]}
        mapped = compare_logic([], [], {"P:B": "GOLD:B"}, gold_exceptions=gold_exc,
                               gold_benefits=[{"raw_text": "bonus", "applies_when_gold_ids": ["GOLD:B"]}],
                               prediction_record=pred_record)
        self.assertEqual(mapped["exceptions"]["tp"], 1)
        self.assertEqual(mapped["preference_benefit_links"]["tp"], 1)
        wrong = compare_logic([], [], {"P:B": "GOLD:A"}, gold_exceptions=gold_exc, prediction_record=pred_record)
        self.assertEqual(wrong["exceptions"]["tp"], 0)

    def test_unresolved_relation_appropriateness(self):
        gold_roots = [group("AND", ref("A"), ref("B"))]
        pred_roots = [group("UNRESOLVED", ref("A"), ref("B"))]
        correct_unknown = compare_logic([group("UNRESOLVED", ref("A"), ref("B"))], pred_roots,
                                       gold_unresolved_relations=[{"gold_condition_ids": ["A", "B"]}])
        self.assertEqual(correct_unknown["unresolved_handling"]["correct"], 1)
        overcautious = compare_logic(gold_roots, pred_roots)
        self.assertEqual(overcautious["unresolved_handling"]["overcautious_unresolved"], 1)

    def test_preflight_blocks_current_empty_and_unreviewed_gold_before_opening_predictions(self):
        ready = preflight("development")
        self.assertEqual(ready["score_status"], "BLOCKED")
        self.assertIn("NO_VERIFIED_COMPLETE_GOLDSET", {x["code"] for x in ready["blocking_reasons"]})
        with tempfile.TemporaryDirectory() as directory:
            result = evaluate("development", output_root=Path(directory),
                              condition_predictions_path=Path(directory) / "must-not-be-read.jsonl",
                              logic_predictions_path=Path(directory) / "must-not-be-read-logic.jsonl")
            self.assertEqual(result["score_status"], "NOT_COMPUTED")
            self.assertIsNone(result["condition_metrics"])
            self.assertFalse((Path(directory) / "development/must-not-be-read.jsonl").exists())

    def test_synthetic_verified_end_to_end_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "gold"
            out = Path(directory) / "out"
            for split in ("development", "evaluation"):
                d = root / split
                d.mkdir(parents=True)
                split_name = split.upper()
                nid = f"NOTICE:{split}"
                text = "SME qualifies"
                status = "VERIFIED" if split == "development" else "UNREVIEWED"
                adjudication = "REVIEWED_COMPLETE" if status == "VERIFIED" else "PENDING"
                condition = {
                    "schema_version": "1.0", "record_type": "condition_gold_review", "data_kind": "ACTUAL_SOURCE",
                    "dataset_split": split_name, "notice_id": nid, "source_system": "BIZINFO",
                    "source_field": "condition_texts.eligibility.text", "source_text": text,
                    "provided_text_scope": "SAMPLED_CONDITION_TEXT_EXCERPT", "source_text_completeness": "COMPLETE",
                    "whole_notice_conditions_complete": False, "source_condition_status": "AVAILABLE",
                    "evidence_reference": {"source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": len(text)},
                    "gold_conditions": [], "missed_condition_candidates": [], "candidate_alignments": [],
                    "review_status": status, "adjudication_status": adjudication, "reviewer": "test" if status == "VERIFIED" else None,
                    "reviewed_at": "2026-11-25T12:00:00Z" if status == "VERIFIED" else None,
                    "revision_history": [], "review_comment": None,
                }
                logic = {
                    "schema_version": "1.0", "record_type": "logic_gold_review", "data_kind": "ACTUAL_SOURCE",
                    "dataset_split": split_name, "notice_id": nid, "source_system": "BIZINFO", "source_text": text,
                    "condition_gold_ids": [], "gold_logic_roots": [], "gold_exceptions": [], "gold_benefits": [],
                    "unresolved_relations": [], "review_status": status, "adjudication_status": adjudication,
                    "reviewer": "test" if status == "VERIFIED" else None,
                    "reviewed_at": "2026-11-25T12:00:00Z" if status == "VERIFIED" else None,
                    "revision_history": [], "review_comment": None,
                }
                if split == "development":
                    condition["existing_candidates"] = []
                    logic.update({"existing_condition_candidates": [], "existing_logic_roots": {},
                                  "existing_relation_candidates": [], "existing_qualifier_candidates": []})
                (d / "condition_review.jsonl").write_text(json.dumps(condition) + "\n", encoding="utf-8")
                (d / "logic_review.jsonl").write_text(json.dumps(logic) + "\n", encoding="utf-8")
            manifest = {"files": {}}
            (root / "baseline_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            gid = make_id("NOTICE:development", "ELIGIBILITY", 0, 3, "SME")
            condition = json.loads((root / "development/condition_review.jsonl").read_text(encoding="utf-8"))
            condition["gold_conditions"] = [gold_condition(gid, applicability_scope="applicant")]
            (root / "development/condition_review.jsonl").write_text(json.dumps(condition) + "\n", encoding="utf-8")
            logic = json.loads((root / "development/logic_review.jsonl").read_text(encoding="utf-8"))
            logic["condition_gold_ids"] = [gid]
            logic["gold_logic_roots"] = [ref(gid)]
            (root / "development/logic_review.jsonl").write_text(json.dumps(logic) + "\n", encoding="utf-8")
            ingest(root, "development")
            ingest(root, "evaluation")
            cond_pred = Path(directory) / "conditions.jsonl"
            logic_pred = Path(directory) / "logic.jsonl"
            pred = prediction()
            pred["notice_id"] = "NOTICE:development"
            pred["applicability_scope"] = "applicant"
            cond_pred.write_text(json.dumps(pred) + "\n", encoding="utf-8")
            logic_pred.write_text(json.dumps({"notice_id": "NOTICE:development", "conditions": [pred], "logical_roots": [ref("CAND:A")]}) + "\n", encoding="utf-8")
            result = evaluate("development", gold_root=root, output_root=out,
                              condition_predictions_path=cond_pred, logic_predictions_path=logic_pred)
            self.assertEqual(result["score_status"], "COMPUTED")
            self.assertEqual(result["condition_metrics"]["micro"]["tp"], 1)
            self.assertTrue(result["logic_by_notice"][0]["notice_structure_exact"])
            foreign = dict(pred, notice_id="NOTICE:evaluation")
            cond_pred.write_text(cond_pred.read_text(encoding="utf-8") + json.dumps(foreign) + "\n", encoding="utf-8")
            logic_pred.write_text(logic_pred.read_text(encoding="utf-8") + json.dumps({"notice_id": "NOTICE:evaluation", "logical_roots": []}) + "\n", encoding="utf-8")
            leaked = evaluate("development", gold_root=root, output_root=out,
                              condition_predictions_path=cond_pred, logic_predictions_path=logic_pred)
            self.assertEqual(leaked["score_status"], "NOT_COMPUTED")
            self.assertEqual(leaked["blocking_reasons"][0]["code"], "PREDICTION_SPLIT_LEAKAGE")


if __name__ == "__main__":
    unittest.main()
