"""Synthetic contracts for explicit LLM attribute normalization and offline replay."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import extract_condition_candidates_llm as llm
from tools import replay_condition_llm_attribute_normalization as replay_tool


def proposal(field: str | None, category: str, quote: str, value: object,
             *, operator: str = "EQ", value_type: str = "STRING", **updates):
    item = {
        "condition_type": "ELIGIBILITY", "category_id": category, "field": field,
        "operator": operator, "value": value, "value_type": value_type, "unit": None,
        "evidence_quotes": [quote], "source_field": llm.SOURCE_FIELD,
        "applicability_scope": None, "evaluation_phase": "APPLICATION",
        "fulfillment_phase": "APPLICATION", "requirement_kind": "CURRENT_STATE",
        "reference_date_type": "UNKNOWN", "reference_date": None,
        "temporal_constraint": None,
        "uncertainty": {"is_uncertain": False, "reason": None}, "external_reference": None,
    }
    item.update(updates)
    return item


def five_proposal_response():
    first = "대구시에 주소와 사업장을 둔 소상공인"
    second = "2024. 1. 1. 이전부터 대구시에 사업자등록증명원 소재지 및 주소지 유지"
    text = first + "\n- " + second
    conditions = [
        proposal("applicant_type", "APPLICANT_TYPE", first, "소상공인"),
        proposal("applicant_address", "APPLICANT_ADDRESS", first, "대구시"),
        proposal("business_location", "BUSINESS_LOCATION", first, "대구시"),
        proposal("applicant_address", "APPLICANT_ADDRESS", second, "대구시",
                 reference_date_type="SPECIFIC_DATE", reference_date="2024-01-01",
                 temporal_constraint={"anchor_event": "FIXED_DATE", "fixed_reference_date": "2024-01-01",
                     "offset_value": None, "offset_unit": None, "operator": "LT", "inclusive": False,
                     "applies_to": "대구시 주소지 유지", "anchor_date_known": True}),
        proposal("business_location", "BUSINESS_LOCATION", second, "대구시",
                 reference_date_type="SPECIFIC_DATE", reference_date="2024-01-01",
                 temporal_constraint={"anchor_event": "FIXED_DATE", "fixed_reference_date": "2024-01-01",
                     "offset_value": None, "offset_unit": None, "operator": "LT", "inclusive": False,
                     "applies_to": "사업자등록증명원 소재지 유지", "anchor_date_known": True}),
    ]
    return text, {"status": "CONDITIONS_FOUND", "conditions": conditions,
                  "logic_sections": [{"section_type": "ELIGIBILITY", "condition_indexes": [0, 1, 2, 3, 4],
                                      "operator": "AND", "evidence_quote": text}],
                  "exceptions": [], "unresolved_relations": []}


class AttributeNormalizationTests(unittest.TestCase):
    def test_standard_uppercase_attribute_is_preserved(self):
        c = proposal("BUSINESS_LOCATION", "BUSINESS_LOCATION", "사업장", "대구시")
        normalized, record, reason = llm.normalize_condition_attribute(c, 0)
        self.assertEqual(normalized["field"], "BUSINESS_LOCATION")
        self.assertEqual(record["mapping_status"], "IDENTITY")
        self.assertIsNone(reason)

    def test_clear_lowercase_aliases_normalize(self):
        for field, canonical in (("applicant_address", "APPLICANT_ADDRESS"),
                                 ("business_location", "BUSINESS_LOCATION"),
                                 ("business_age", "BUSINESS_AGE")):
            c = proposal(field, canonical, "근거", 3)
            normalized, record, reason = llm.normalize_condition_attribute(c, 0)
            self.assertEqual(normalized["field"], canonical)
            self.assertEqual(record["mapping_status"], "NORMALIZED")
            self.assertIsNone(reason)

    def test_unknown_attribute_is_rejected(self):
        normalized, record, reason = llm.normalize_condition_attribute(
            proposal("mystery_field", "BUSINESS_LOCATION", "근거", "x"), 0)
        self.assertEqual(normalized["field"], "mystery_field")
        self.assertEqual(record["mapping_status"], "UNMAPPED")
        self.assertEqual(reason, "UNSUPPORTED_ATTRIBUTE")

    def test_sme_applicant_type_is_held_as_ambiguous(self):
        normalized, record, reason = llm.normalize_condition_attribute(
            proposal("applicant_type", "APPLICANT_TYPE", "소상공인일 것", "소상공인"), 0)
        self.assertEqual(normalized["field"], "APPLICANT_TYPE")
        self.assertIsNone(record["normalized_field"])
        self.assertEqual(record["mapping_status"], "AMBIGUOUS")
        self.assertEqual(reason, "ATTRIBUTE_SEMANTIC_AMBIGUITY")

    def test_field_and_category_mismatch_is_not_silently_repaired(self):
        normalized, record, reason = llm.normalize_condition_attribute(
            proposal("business_location", "APPLICANT_ADDRESS", "사업장", "대구시"), 0)
        self.assertEqual(normalized["field"], "BUSINESS_LOCATION")
        self.assertEqual(normalized["category_id"], "APPLICANT_ADDRESS")
        self.assertEqual(record["mapping_status"], "FIELD_CATEGORY_MISMATCH")
        self.assertEqual(reason, "ATTRIBUTE_CATEGORY_MISMATCH")

    def test_date_and_temporal_fields_survive_normalization_and_candidate_build(self):
        text, response = five_proposal_response()
        source = {"notice_id": "SYN:DATE", "source_system": "SYN", "raw_text": text,
                  "completeness_status": "PARTIAL"}
        before = response["conditions"][3:]
        artifacts = llm._response_to_artifacts(source, response)
        candidates = {candidate["field"]: candidate for candidate in artifacts["conditions"]}
        for field, original in zip(("APPLICANT_ADDRESS", "BUSINESS_LOCATION"), before):
            candidate = candidates[field]
            self.assertEqual(candidate["reference_date"]["value"], "2024-01-01")
            self.assertEqual(candidate["temporal_constraint"], original["temporal_constraint"])

    def test_bad_evidence_still_fails_after_normalization(self):
        source = {"notice_id": "SYN:EVIDENCE", "source_system": "SYN", "raw_text": "사업장 소재",
                  "completeness_status": "UNKNOWN"}
        c = proposal("business_location", "BUSINESS_LOCATION", "없는 문구", "대구시")
        artifacts = llm._response_to_artifacts(source, {"status": "CONDITIONS_FOUND", "conditions": [c],
            "logic_sections": [], "exceptions": [], "unresolved_relations": []})
        self.assertEqual(artifacts["held"][0]["status"], "EVIDENCE_NOT_IN_SOURCE")
        self.assertEqual(artifacts["conditions"], [])

    def test_bad_operator_still_fails_after_normalization(self):
        source = {"notice_id": "SYN:OP", "source_system": "SYN", "raw_text": "사업장 소재",
                  "completeness_status": "UNKNOWN"}
        c = proposal("business_location", "BUSINESS_LOCATION", "사업장 소재", "대구시",
                     operator="BETWEEN", value_type="STRING")
        artifacts = llm._response_to_artifacts(source, {"status": "CONDITIONS_FOUND", "conditions": [c],
            "logic_sections": [], "exceptions": [], "unresolved_relations": []})
        self.assertEqual(artifacts["held"][0]["status"], "OPERATOR_VALUE_TYPE_MISMATCH")

    def test_duplicate_candidates_are_deduplicated(self):
        source = {"notice_id": "SYN:DUP", "source_system": "SYN", "raw_text": "사업장 소재",
                  "completeness_status": "UNKNOWN"}
        c = proposal("business_location", "BUSINESS_LOCATION", "사업장 소재", "대구시")
        artifacts = llm._response_to_artifacts(source, {"status": "CONDITIONS_FOUND", "conditions": [c, c],
            "logic_sections": [], "exceptions": [], "unresolved_relations": []})
        self.assertEqual(len(artifacts["conditions"]), 1)

    def test_held_condition_makes_and_logic_unresolved(self):
        text, response = five_proposal_response()
        source = {"notice_id": "SYN:LOGIC", "source_system": "SYN", "raw_text": text,
                  "completeness_status": "PARTIAL"}
        artifacts = llm._response_to_artifacts(source, response)
        logic = artifacts["logic_proposal"]
        self.assertEqual(logic["logical_completeness"], "INCOMPLETE")
        self.assertEqual(logic["unresolved_condition_indexes"], [0])
        self.assertEqual(logic["logic_sections"][0]["operator"], "UNRESOLVED")
        self.assertIn("INCOMPLETE_LOGIC_DUE_TO_HELD_CONDITIONS",
                      artifacts["notice_set"]["decision_readiness"]["limiting_reasons"])

    def test_source_response_is_not_mutated(self):
        text, response = five_proposal_response()
        original = json.dumps(response, ensure_ascii=False, sort_keys=True)
        source = {"notice_id": "SYN:IMMUTABLE", "source_system": "SYN", "raw_text": text,
                  "completeness_status": "PARTIAL"}
        llm._response_to_artifacts(source, response)
        self.assertEqual(json.dumps(response, ensure_ascii=False, sort_keys=True), original)


class OfflineReplayTests(unittest.TestCase):
    def test_replay_is_offline_reproducible_and_preserves_prior_ledger(self):
        text, response = five_proposal_response()
        notice_id = "SYN:REPLAY"
        source = {"notice_id": notice_id, "source_system": "SYN", "raw_text": text,
                  "completeness_status": "PARTIAL"}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            r2root = root / "r2"
            (r2root / "lead_retry").mkdir(parents=True)
            raw_path = r2root / "lead_retry/raw_llm_responses.jsonl"
            llm._write_jsonl(raw_path, [{"notice_id": notice_id, "response_attempts":
                                         [json.dumps(response, ensure_ascii=False)], "accepted": True}])
            llm._write_jsonl(r2root / "lead_retry/intermediate_responses.jsonl",
                             [{"notice_id": notice_id, "intermediate_response": response}])
            for rel in replay_tool.PRIOR_ARTIFACTS:
                path = r2root / rel
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("{}\n", encoding="utf-8")
            (r2root / "manifest.json").write_text(json.dumps({"fingerprint": {"extractor_sha256": "old"}}), encoding="utf-8")
            (r2root / "request_ledger.json").write_text(json.dumps({"limit": 12, "used": 3}), encoding="utf-8")
            (r2root / "lead_retry/run_report.json").write_text(json.dumps({"prompt_sha256": "prompt-hash"}), encoding="utf-8")

            inputs, samples = root / "inputs.jsonl", root / "samples.jsonl"
            llm._write_jsonl(inputs, [source])
            llm._write_jsonl(samples, [{"notice_id": notice_id, "split": "DEVELOPMENT"}])
            destinations = [root / "replay-a", root / "replay-b"]
            manifest_hash = replay_tool.digest(r2root / "manifest.json")
            ledger_hash = replay_tool.digest(r2root / "request_ledger.json")
            with (patch.object(replay_tool, "R2", r2root), patch.object(llm, "INPUTS", inputs),
                  patch.object(llm, "SAMPLES", samples),
                  patch.object(llm, "call_and_parse", side_effect=AssertionError("API path called")),
                  patch.object(llm, "run_pilot", side_effect=AssertionError("live runner called"))):
                reports = [replay_tool.replay(raw_path, dest) for dest in destinations]
            self.assertEqual(reports[0], reports[1])
            for name in reports[0]["output_hashes"]:
                self.assertEqual((destinations[0] / name).read_bytes(), (destinations[1] / name).read_bytes())
            self.assertEqual(reports[0]["api_call_count"], 0)
            self.assertEqual(reports[0]["accepted_unreviewed_count"], 4)
            self.assertEqual(reports[0]["held_for_review_count"], 1)
            held_detail = next(row for row in replay_tool.llm._read_jsonl(destinations[0] / "validation_details.jsonl")
                               if row["proposal_index"] == 0)
            self.assertIsNone(held_detail["normalized_field"])
            self.assertEqual(replay_tool.digest(r2root / "manifest.json"), manifest_hash)
            self.assertEqual(replay_tool.digest(r2root / "request_ledger.json"), ledger_hash)
            self.assertEqual((destinations[0] / "review_queue.jsonl").is_file(), True)


if __name__ == "__main__":
    unittest.main()
