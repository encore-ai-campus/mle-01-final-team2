from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_condition_gold_v11_precheck import build
from tools.evaluate_condition_pipeline import preflight
from tools.ingest_condition_gold_reviews import schema_validators, validate_review_packets

V11 = ROOT / "data/goldsets/conditions/v1.1/20261126/precheck5"


class GoldV11Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conditions, cls.logics = build()
        cls.c = {r["notice_id"]: r for r in cls.conditions}
        cls.l = {r["notice_id"]: r for r in cls.logics}

    def test_v11_schema_and_references(self):
        _, _, report = validate_review_packets(V11, "development")
        self.assertEqual((report["schema_version"], report["unreviewed_records"]), ("1.1", 0))
        self.assertEqual(report["reviewed_condition_records"], 5)
        self.assertEqual(report["reviewed_logic_records"], 5)

    def test_v10_schema_remains_valid(self):
        validators = schema_validators()
        source = ROOT / "data/goldsets/conditions/v1/20261126_balanced/precheck5/development"
        for name, schema in (("condition_review.jsonl", "condition-gold-review-v1.schema.json"),
                             ("logic_review.jsonl", "logic-gold-review-v1.schema.json")):
            for line in (source / name).read_text(encoding="utf-8").splitlines():
                self.assertFalse(list(validators[schema].iter_errors(json.loads(line))))

    def test_common_v11_notice_contract(self):
        directory = ROOT / "schemas/conditions"
        schemas = [json.loads(p.read_text(encoding="utf-8")) for p in directory.glob("*.schema.json")]
        registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in schemas)
        wrapper = next(s for s in schemas if s["$id"] == "urn:mle-team2:support-conditions:v1.1:notice-set")
        validator = Draft202012Validator(wrapper, registry=registry, format_checker=FormatChecker())
        sample = json.loads((ROOT / "sample_data/conditions/actual-condition-samples.jsonl").read_text(encoding="utf-8").splitlines()[0])
        sample["schema_version"] = "1.1"
        for collection in sample["condition_sets"].values():
            for c in collection["conditions"]:
                c["schema_version"] = "1.1"
                c.update(structure_capable=True, facts_sufficient=False, evaluation_phase="APPLICATION",
                         fulfillment_phase="APPLICATION", requirement_kind="CURRENT_STATE",
                         temporal_constraint=None, external_reference=None,
                         evidence_references=[{"role": "PRIMARY", "source_field": "sample", "start_char": 0,
                                               "end_char": 1, "evidence_text": "x", "document_id": None, "evidence_id": None}])
        cid = sample["condition_sets"]["eligibility"]["conditions"][0]["condition_id"]
        sample["logic_sections"] = [{"section_id": "eligibility", "condition_type": "ELIGIBILITY",
            "evaluation_phase": "APPLICATION", "fulfillment_phase": "APPLICATION",
            "root": {"node_type": "CONDITION_REF", "condition_id": cid}, "review_status": "UNREVIEWED"}]
        self.assertFalse(list(validator.iter_errors(sample)))

    def test_founder_future_feasibility_inside_eligibility_branch(self):
        nid = "KSTARTUP:178507"
        cs = self.c[nid]["gold_conditions"]
        founder = next(c for c in cs if c["field"] == "BUSINESS_REGISTRATION")
        self.assertEqual((founder["evaluation_phase"], founder["fulfillment_phase"], founder["requirement_kind"]),
                         ("APPLICATION", "POST_MOVE_IN", "FUTURE_FEASIBILITY"))
        self.assertEqual((founder["temporal_constraint"]["offset_value"], founder["temporal_constraint"]["offset_unit"]), (3, "MONTH"))
        root = self.l[nid]["gold_logic_sections"][0]["root"]
        branch = root["children"][1]["children"][0]
        self.assertEqual(branch["operator"], "AND")
        self.assertIn(founder["gold_condition_id"], [n["condition_id"] for n in branch["children"]])
        self.assertFalse(any(s["condition_type"] == "POST_SELECTION_OBLIGATION" and
                             s["root"].get("condition_id") == founder["gold_condition_id"]
                             for s in self.l[nid]["gold_logic_sections"]))

    def test_post_selection_and_exclusion_sections_separate(self):
        nid = "KSTARTUP:178507"
        sections = self.l[nid]["gold_logic_sections"]
        self.assertEqual(sections[0]["condition_type"], "ELIGIBILITY")
        self.assertTrue(any(s["condition_type"] == "EXCLUSION" for s in sections))
        self.assertTrue(any(s["condition_type"] == "POST_SELECTION_OBLIGATION" for s in sections))
        self.assertEqual(next(s for s in sections if s["section_id"] == "address_transfer")["evaluation_phase"], "POST_SELECTION")
        duplicate = [c for c in self.c[nid]["gold_conditions"] if c["field"] == "DUPLICATE_OCCUPANCY"]
        general = next(c for c in duplicate if c["gold_condition_id"].endswith("64HML7YO6L4FES5PLPUTFK2O"))
        selected = next(c for c in duplicate if c["gold_condition_id"].endswith("XNGYEKKQZZIRCEYLRC7XBPHS"))
        self.assertEqual((general["evaluation_phase"], general["fulfillment_phase"]), ("UNKNOWN", "UNKNOWN"))
        self.assertEqual((selected["evaluation_phase"], selected["fulfillment_phase"]), ("POST_SELECTION", "POST_SELECTION"))
        exclusion_sections = {s["section_id"]: s for s in sections if s["condition_type"] == "EXCLUSION"}
        self.assertEqual(exclusion_sections["exclusion_2"]["evaluation_phase"], general["evaluation_phase"])
        self.assertEqual(exclusion_sections["exclusion_3"]["evaluation_phase"], selected["evaluation_phase"])

    def test_move_in_deadline_and_unconfirmed_age_date(self):
        conditions = self.c["KSTARTUP:178507"]["gold_conditions"]
        address = next(c for c in conditions if c["field"] == "BUSINESS_LOCATION")
        temporal = address["temporal_constraint"]
        self.assertEqual((temporal["anchor_event"], temporal["offset_value"], temporal["offset_unit"], temporal["inclusive"]),
                         ("MOVE_IN_START", 30, "DAY", True))
        self.assertEqual(address["evaluation_phase"], "POST_SELECTION")
        self.assertEqual(temporal["applies_to"], "HEAD_OR_BRANCH_ADDRESS_TRANSFER")
        age = next(c for c in conditions if c["field"] == "APPLICANT_AGE")
        self.assertIsNone(age["temporal_constraint"]["fixed_reference_date"])
        self.assertFalse(age["temporal_constraint"]["anchor_date_known"])
        self.assertTrue(any(e["evidence_text"] == "2026. 7. 7." for e in age["evidence_references"]))

    def test_exception_modes_prevent_double_application(self):
        nonprofit = self.l["BIZINFO:PBLN_000000000118182"]["gold_exceptions"][0]
        local = self.l["KSTARTUP:176813"]["gold_exceptions"][0]
        self.assertEqual((nonprofit["effect"], nonprofit["application_mode"]), ("WAIVE_REQUIREMENT", "AST_ONLY"))
        self.assertEqual((local["effect"], local["application_mode"]), ("EXCLUDE_FROM_SCOPE", "EFFECT_ONLY"))

    def test_evidence_tamper_and_unreviewed_decision_rejected(self):
        from jsonschema import ValidationError
        row = copy.deepcopy(self.c["BIZINFO:PBLN_000000000118927"])
        row["gold_conditions"][0]["evidence_references"][1]["start_char"] = -1
        validator = schema_validators()["condition-gold-review-v1.1.schema.json"]
        self.assertTrue(list(validator.iter_errors(row)))
        report = preflight("development", V11)
        self.assertEqual(report["score_status"], "BLOCKED")
        self.assertEqual(report["evaluation_version"], "1.1")


if __name__ == "__main__":
    unittest.main()
