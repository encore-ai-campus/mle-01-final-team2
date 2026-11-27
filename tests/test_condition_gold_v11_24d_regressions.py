"""Focused structural regressions for the 2-4D reviewed draft packets."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKET_DIR = ROOT / "data/goldsets/conditions/v1.1/20261126/remaining25/development"


def packets(filename: str) -> dict[str, dict]:
    return {
        row["notice_id"]: row
        for row in (
            json.loads(line)
            for line in (PACKET_DIR / filename).read_text(encoding="utf-8").splitlines()
            if line
        )
    }


def groups(node: dict) -> list[dict]:
    if node["node_type"] != "LOGICAL_GROUP":
        return []
    return [node, *(g for child in node["children"] for g in groups(child))]


def refs(node: dict) -> set[str]:
    if node["node_type"] == "CONDITION_REF":
        return {node["condition_id"]}
    return set().union(*(refs(child) for child in node["children"]))


class Remaining25SemanticRegressions(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.conditions = packets("condition_review.jsonl")
        cls.logics = packets("logic_review.jsonl")

    def test_119490_group_ids_are_unique_with_two_regional_hire_branches(self) -> None:
        row = self.logics["BIZINFO:PBLN_000000000119490"]
        all_groups = [g for section in row["gold_logic_sections"] for g in groups(section["root"])]
        ids = [g["group_id"] for g in all_groups]
        self.assertEqual(len(ids), len(set(ids)))
        root = row["gold_logic_sections"][0]["root"]
        self.assertEqual(root["operator"], "AND")
        regional = next(child for child in root["children"] if child["node_type"] == "LOGICAL_GROUP")
        self.assertEqual(regional["operator"], "OR")
        self.assertEqual(len(regional["children"]), 2)
        self.assertTrue(all(branch["operator"] == "AND" for branch in regional["children"]))


    def test_128028_group_ids_are_unique_and_base_and_optional_duties_are_separate(self) -> None:
        conditions = self.conditions["BIZINFO:PBLN_000000000128028"]
        logic = self.logics["BIZINFO:PBLN_000000000128028"]
        all_groups = [g for section in logic["gold_logic_sections"] for g in groups(section["root"])]
        ids = [g["group_id"] for g in all_groups]
        self.assertEqual(len(ids), len(set(ids)))
        fields = {c["field"]: c for c in conditions["gold_conditions"]}
        self.assertEqual(fields["COMPLIANCE_PLAN_CONTENT"]["value"], "기본의무 포함")
        self.assertEqual(fields["OPTIONAL_DUTY_COUNT"]["operator"], "GTE")
        self.assertEqual(fields["OPTIONAL_DUTY_COUNT"]["value"], 2)
        self.assertEqual(fields["DOCUMENT_SUBMISSION"]["value"], "이행계획서 제출")


    def test_119490_nonmetro_hire_evidence_uses_its_own_source_span(self) -> None:
        record = self.conditions["BIZINFO:PBLN_000000000119490"]
        condition = next(c for c in record["gold_conditions"]
                         if c["field"] == "HIRE_STATUS" and c["evidence_reference"]["start_char"] == 142)
        start, end = condition["evidence_reference"]["start_char"], condition["evidence_reference"]["end_char"]
        self.assertEqual((start, end), (142, 156))
        self.assertEqual(record["source_text"][start:end], condition["raw_text"])
        logic = self.logics["BIZINFO:PBLN_000000000119490"]
        self.assertIn(condition["gold_condition_id"], refs(logic["gold_logic_sections"][0]["root"]))


    def test_127992_qualifying_fields_are_alternatives_not_conjunctive(self) -> None:
        root = self.logics["BIZINFO:PBLN_000000000127992"]["gold_logic_sections"][0]["root"]
        self.assertEqual(root["node_type"], "LOGICAL_GROUP")
        self.assertEqual(root["operator"], "OR")
        self.assertEqual(len(root["children"]), 2)


    def test_177447_military_extension_is_individual_age_exception_not_teamwide(self) -> None:
        logic = self.logics["KSTARTUP:177447"]
        condition = self.conditions["KSTARTUP:177447"]["gold_conditions"][0]
        exception = logic["gold_exceptions"][0]
        by_duration = {x["duration"]: x["upper_age"] for x in exception["replacement"]["upper_age_by_service_duration"]}
        self.assertEqual(by_duration, {"<1 YEAR": 40, ">=1 AND <2 YEARS": 41, ">=2 YEARS": 42})
        self.assertEqual(exception["applies_to_gold_ids"], [condition["gold_condition_id"]])
        self.assertTrue(exception["effect_confirmed"])
        self.assertEqual(exception["application_mode"], "UNKNOWN")
        self.assertFalse(condition["decision_possible"])


    def test_126715_domestic_company_only_requirements_are_isolated_and_unknown(self) -> None:
        conditions = self.conditions["BIZINFO:PBLN_000000000126715"]
        logic = self.logics["BIZINFO:PBLN_000000000126715"]
        self.assertEqual(len(logic["gold_logic_sections"]), 2)
        base, conditional = logic["gold_logic_sections"]
        self.assertEqual(base["evaluation_phase"], "APPLICATION")
        self.assertEqual(conditional["evaluation_phase"], "UNKNOWN")
        conditional_refs = refs(conditional["root"])
        by_id = {c["gold_condition_id"]: c for c in conditions["gold_conditions"]}
        self.assertEqual(len(conditional_refs), 2)
        self.assertEqual({by_id[cid]["field"] for cid in conditional_refs}, {"BUSINESS_AGE", "CERTIFICATION"})


    def test_177506_private_company_credit_condition_is_not_in_common_root(self) -> None:
        conditions = self.conditions["KSTARTUP:177506"]
        logic = self.logics["KSTARTUP:177506"]
        credit = next(c for c in conditions["gold_conditions"] if c["field"] == "CREDIT_RATING")
        self.assertIsNone(credit["operator"])
        self.assertFalse(credit["decision_possible"])
        common = next(s for s in logic["gold_logic_sections"] if s["evaluation_phase"] == "APPLICATION")
        conditional = next(s for s in logic["gold_logic_sections"] if s["evaluation_phase"] == "UNKNOWN")
        self.assertNotIn(credit["gold_condition_id"], refs(common["root"]))
        self.assertEqual(refs(conditional["root"]), {credit["gold_condition_id"]})


if __name__ == "__main__":
    unittest.main()
