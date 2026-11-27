"""Synthetic v1.1 evaluator contracts. No real development scores are calculated."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from tools.evaluate_condition_pipeline_v11 import (
    GOLD, compare_extended, compare_notice_logic, common_differences,
    evaluate_records, evidence_diagnostics, match_notice, preflight, safety_diagnostics,
)


def gold(cid="G:1", **kw):
    row = {"gold_condition_id": cid, "condition_type": "ELIGIBILITY", "category": "BUSINESS_TYPE",
           "field": "BUSINESS_TYPE", "operator": "EQ", "value": "SME", "unit": None,
           "raw_text": "SME", "source_field": "eligibility", "evidence_reference": {"start_char": 0, "end_char": 3},
           "reference_date_type": "UNKNOWN", "reference_date": None, "decision_possible": False,
           "source_completeness": "UNKNOWN", "value_type": "STRING", "applicability_scope": "applicant",
           "evaluation_phase": "APPLICATION", "fulfillment_phase": "APPLICATION",
           "requirement_kind": "CURRENT_STATE", "temporal_constraint": None,
           "evidence_references": [{"role": "PRIMARY", "source_field": "eligibility", "start_char": 0, "end_char": 3, "evidence_text": "SME"}],
           "external_reference": None}
    row.update(kw)
    return row


def pred(cid="P:1", **kw):
    row = {"condition_id": cid, "notice_id": "N:1", "schema_version": "1.0",
           "condition_type": "ELIGIBILITY", "category_id": "BUSINESS_TYPE", "field": "BUSINESS_TYPE",
           "operator": "EQ", "value": "SME", "unit": None, "decision_eligible": False,
           "source": {"source_field": "eligibility", "location": {"start_char": 0, "end_char": 3}, "evidence_text": "SME"}}
    row.update(kw)
    return row


def ref(cid):
    return {"node_type": "CONDITION_REF", "condition_id": cid}


def group(op, *children):
    return {"node_type": "LOGICAL_GROUP", "group_id": "any", "operator": op, "children": list(children)}


def logic(*roots, **kw):
    row = {"gold_logic_roots": list(roots), "gold_logic_sections": [], "gold_exceptions": [], "gold_benefits": [], "unresolved_relations": []}
    row.update(kw)
    return row


class SyntheticV11Cases(unittest.TestCase):
    def test_01_exact_and_partial_are_separate(self):
        self.assertEqual(match_notice([gold()], [pred()])["metrics"]["tp"], 1)
        m = match_notice([gold()], [pred(value="large")])
        self.assertEqual((m["metrics"]["tp"], m["partial_count"]), (0, 1))
        result = evaluate_records(
            [{"notice_id": "N:1", "source_system": "BIZINFO", "gold_conditions": [gold()],
              "missed_condition_candidates": [], "whole_notice_conditions_complete": False}],
            [{"notice_id": "N:1", **logic(ref("G:1"))}], [pred()],
            [{"notice_id": "N:1", "logical_roots": [ref("P:1")]}],
        )
        self.assertEqual(result["common"]["micro"]["tp"], 1)
        self.assertTrue(result["notices"][0]["logic"]["notice_structure_exact"])

    def test_02_duplicate_prediction_is_not_second_tp(self):
        m = match_notice([gold()], [pred(), pred("P:2")])
        self.assertEqual((m["metrics"]["tp"], m["metrics"]["fp"]), (1, 1))

    def test_03_input_order_cannot_change_pairs(self):
        gs = [gold("G:1"), gold("G:2")]
        ps = [pred("P:1"), pred("P:2")]
        a = match_notice(gs, ps)
        b = match_notice(list(reversed(gs)), list(reversed(ps)))
        self.assertEqual([(x["gold_id"], x["prediction_id"]) for x in a["pairs"]],
                         [(x["gold_id"], x["prediction_id"]) for x in b["pairs"]])

    def test_04_and_or_child_order_is_commutative(self):
        for op in ("AND", "OR"):
            a = logic(group(op, ref("G:1"), ref("G:2")))
            b = {"logical_roots": [group(op, ref("P:2"), ref("P:1"))]}
            self.assertTrue(compare_notice_logic(a, b, {"P:1": "G:1", "P:2": "G:2"})["notice_structure_exact"])

    def test_05_and_or_change_fails(self):
        a = logic(group("AND", ref("G:1"), ref("G:2")))
        b = {"logical_roots": [group("OR", ref("P:1"), ref("P:2"))]}
        self.assertFalse(compare_notice_logic(a, b, {"P:1": "G:1", "P:2": "G:2"})["notice_structure_exact"])

    def test_06_not_scope_change_fails(self):
        a = logic(group("NOT", group("AND", ref("G:1"), ref("G:2"))))
        b = {"logical_roots": [group("AND", group("NOT", ref("P:1")), ref("P:2"))]}
        self.assertFalse(compare_notice_logic(a, b, {"P:1": "G:1", "P:2": "G:2"})["notice_structure_exact"])

    def test_07_actual_application_and_deadline_differ(self):
        g = gold(reference_date_type="APPLICATION_END")
        p = pred(reference_date={"date_type": "APPLICATION_START", "value": None})
        m = match_notice([g], [p])
        self.assertEqual(compare_extended([g], m["pairs"])["reference_date_type"]["correct"], 0)

    def test_08_month_and_day_or_boundary_differ(self):
        g = gold(temporal_constraint={"offset_value": 3, "offset_unit": "MONTH", "inclusive": True})
        p = pred(temporal_constraint={"offset_value": 90, "offset_unit": "DAY", "inclusive": False})
        counts = compare_extended([g], match_notice([g], [p])["pairs"])
        self.assertEqual(counts["temporal_constraint.offset_unit"]["correct"], 0)
        self.assertEqual(counts["temporal_constraint.inclusive"]["correct"], 0)

    def test_09_exception_effect_is_not_existence(self):
        ex = {"applies_to_gold_ids": ["G:1"], "precondition": "LOCAL_ONLY", "effect": "EXCLUDE_FROM_SCOPE", "effect_target": "history", "replacement": None, "effect_confirmed": True, "application_mode": "EFFECT_ONLY"}
        a = logic(ref("G:1"), gold_exceptions=[ex])
        b = {"logical_roots": [ref("P:1")], "gold_exceptions": [{**ex, "applies_to_gold_ids": ["P:1"], "effect": "WAIVE_REQUIREMENT"}]}
        self.assertFalse(compare_notice_logic(a, b, {"P:1": "G:1"})["exception_effects"]["exact"])

    def test_10_individual_exception_not_teamwide(self):
        ex = {"applies_to_gold_ids": ["G:1"], "precondition": "INDIVIDUAL_SERVICE", "effect": "UNKNOWN", "effect_target": "person_age", "replacement": None, "effect_confirmed": True, "application_mode": "UNKNOWN"}
        a = logic(ref("G:1"), gold_exceptions=[ex])
        b = {"logical_roots": [ref("P:1")], "gold_exceptions": [{**ex, "applies_to_gold_ids": ["P:1"], "effect_target": "whole_team_age"}]}
        self.assertFalse(compare_notice_logic(a, b, {"P:1": "G:1"})["exception_effects"]["exact"])

    def test_11_ip_right_binding_is_not_automatically_resolved(self):
        g = logic(ref("G:1"), unresolved_relations=[{"gold_condition_ids": ["G:1"]}])
        self.assertIn("UNRESOLVED_AS_DEFINITE", safety_diagnostics({}, {}, {"pairs": []}, g, {"logic_relation_status": "RESOLVED"}))

    def test_12_applicant_and_recommended_target_differ(self):
        g = gold(field="APPLICANT_TYPE")
        p = pred(field="RECOMMENDED_COMPANY_TYPE")
        self.assertIn("field", common_differences(g, p))

    def test_13_unknown_condition_cannot_be_decision_eligible(self):
        g = gold(operator=None, value_type="UNKNOWN", value=None)
        p = pred(operator=None, value=None, decision_eligible=True)
        m = match_notice([g], [p])
        self.assertIn("UNKNOWN_AS_DEFINITE", safety_diagnostics({}, {}, m))

    def test_14_preference_as_eligibility_is_not_exact(self):
        g = gold(condition_type="PREFERENCE")
        p = pred(condition_type="ELIGIBILITY")
        m = match_notice([g], [p])
        self.assertEqual(m["metrics"]["tp"], 0)
        self.assertIn("PREFERENCE_AS_REQUIRED", safety_diagnostics({}, {}, m))

    def test_15_post_selection_obligation_is_not_application_eligibility(self):
        g = gold(requirement_kind="FULFILLMENT_OBLIGATION")
        p = pred(evaluation_phase="APPLICATION")
        self.assertIn("POST_SELECTION_AS_APPLICATION", safety_diagnostics({}, {}, match_notice([g], [p])))

    def test_16_confirmed_source_effect_can_be_execution_unsupported(self):
        g = logic(ref("G:1"), gold_exceptions=[{"effect": "UNKNOWN", "effect_confirmed": True}])
        self.assertEqual(compare_notice_logic(g, {"logical_roots": [ref("P:1")]}, {"P:1": "G:1"})["exception_effects"]["status"], "UNSUPPORTED_V1_0")
        self.assertIn("UNSUPPORTED_EXCEPTION_EXECUTED", safety_diagnostics({}, {}, {"pairs": []}, g, {"decision_eligible": True}))

    def test_17_same_text_wrong_branch_position_is_not_exact(self):
        g = gold()
        p = pred(source={"source_field": "eligibility", "location": {"start_char": 10, "end_char": 13}, "evidence_text": "SME"})
        m = match_notice([g], [p])
        self.assertEqual(m["metrics"]["tp"], 0)
        self.assertEqual(evidence_diagnostics(m["pairs"][0]), "WRONG_BRANCH_OR_LOCATION")

    def test_18_supporting_evidence_is_not_another_gold_condition(self):
        g = gold(evidence_references=[{"role": "PRIMARY", "evidence_text": "SME"}, {"role": "SUPPORTING", "evidence_text": "small company"}])
        self.assertEqual(len([g]), 1)
        self.assertEqual(match_notice([g], [pred()])["metrics"]["tp"], 1)
        self.assertEqual(compare_extended([g], match_notice([g], [pred()])["pairs"])["evidence_references"]["unsupported"], 1)

    def test_19_v10_missing_semantic_fields_are_unsupported(self):
        g = gold()
        counts = compare_extended([g], match_notice([g], [pred()])["pairs"])
        self.assertEqual(counts["evaluation_phase"]["unsupported"], 1)
        self.assertEqual(counts["applicability_scope"]["unsupported"], 1)

    def test_20_mixed_or_unfrozen_prediction_is_blocked_before_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            wrong = Path(tmp) / "predictions.jsonl"
            wrong.write_text('{"notice_id":"EVAL:1","schema_version":"1.0"}\n', encoding="utf-8")
            result = preflight(GOLD, conditions_path=wrong)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertFalse(result["scores_computed"])


if __name__ == "__main__":
    unittest.main()
