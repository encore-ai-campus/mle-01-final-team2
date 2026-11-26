import unittest

from tools.extract_condition_candidates_legacy_augmented import (
    _source_facts_by_key,
    reconcile_proposals,
    validate_legacy_candidate,
)


def make_case(text="중소기업"):
    notice_id = "BIZINFO:TEST-1"
    fact = {"attribute": "company_size", "operator": "IS_A", "value": {"label": "중소기업"},
            "ambiguous": False, "evidence_text": text, "char_start": 0,
            "kind": "ELIGIBILITY", "review_status": "unreviewed"}
    candidate = {"notice_id": notice_id, "source_system": "BIZINFO",
                 "candidate_ref": notice_id + ":FACT:x:0", "legacy_candidate_ref": notice_id + ":company_size:0",
                 "source_file": "data/normalized/20261124/notices_normalized.jsonl", "source_field": None,
                 "source_position": 0, "attribute": "company_size", "kind": "ELIGIBILITY",
                 "normalized_value": {"label": "중소기업"}, "evidence_text": text, "review_status": "UNREVIEWED"}
    row = {"notice_id": notice_id, "source_system": "BIZINFO", "raw_text": text, "evidence": []}
    facts = _source_facts_by_key([{"notice_id": notice_id, "facts": [fact]}])
    return candidate, row, facts


def synthetic_condition(notice_id, field="BUSINESS_TYPE", op="EQ", value="중소기업", start=0, end=5):
    return {"notice_id": notice_id, "condition_type": "ELIGIBILITY", "field": field,
            "operator": op, "value": value, "unit": None,
            "source": {"location": {"start_char": start, "end_char": end}},
            "condition_id": f"CND:{field}:{op}:{value}:{start}:{end}"}


class LegacyCandidateValidationTests(unittest.TestCase):
    def test_01_valid_exact_legacy_candidate_admitted_as_unreviewed_proposal(self):
        c, row, facts = make_case()
        result = validate_legacy_candidate(c, row, facts)
        self.assertEqual(result["disposition"], "ADMITTED_PROPOSAL")
        self.assertEqual(result["proposal"]["review_status"], "UNREVIEWED")
        self.assertFalse(result["proposal"]["decision_eligible"])

    def test_02_cross_notice_candidate_is_blocked(self):
        c, row, facts = make_case()
        row["notice_id"] = "BIZINFO:OTHER"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_NOTICE_MISMATCH")

    def test_03_cross_notice_candidate_reference_is_blocked(self):
        c, row, facts = make_case()
        c["candidate_ref"] = "BIZINFO:OTHER:FACT:x:0"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_CANDIDATE_REFERENCE_MISMATCH")

    def test_04_evidence_absent_from_current_input_is_blocked(self):
        c, row, facts = make_case()
        row["raw_text"] = "중견기업"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_EVIDENCE_NOT_IN_INPUT")

    def test_05_repeated_evidence_is_blocked_as_ambiguous(self):
        c, row, facts = make_case()
        row["raw_text"] = "중소기업 및 중소기업"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_EVIDENCE_AMBIGUOUS")

    def test_06_source_position_mismatch_is_blocked(self):
        c, row, facts = make_case()
        c["source_position"] = 1
        facts = _source_facts_by_key([{"notice_id": c["notice_id"], "facts": [{
            "attribute": "company_size", "operator": "IS_A", "value": {"label": "중소기업"},
            "ambiguous": False, "evidence_text": c["evidence_text"], "char_start": 1,
            "kind": "ELIGIBILITY", "review_status": "unreviewed"}]}])
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_POSITION_MISMATCH")

    def test_07_version_two_source_is_blocked(self):
        c, row, facts = make_case()
        c["source_file"] = "data/normalized/v2/notices.jsonl"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_DATA_VERSION_MISMATCH")

    def test_08_mismatched_normalized_value_is_blocked(self):
        c, row, facts = make_case()
        c["normalized_value"] = {"label": "중견기업"}
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_NORMALIZED_VALUE_MISMATCH")

    def test_09_non_eligibility_polarity_is_not_reversed(self):
        c, row, facts = make_case()
        c["kind"] = "EXCLUSION"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_CONDITION_POLARITY")

    def test_10_region_without_applicant_scope_is_held(self):
        c, row, facts = make_case()
        c["attribute"] = "region"
        facts = _source_facts_by_key([{"notice_id": c["notice_id"], "facts": [{
            "attribute": "region", "operator": "WITHIN", "value": {"label": "중소기업"},
            "ambiguous": False, "evidence_text": c["evidence_text"], "char_start": 0,
            "kind": "ELIGIBILITY", "review_status": "unreviewed"}]}])
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_REGION_SCOPE")

    def test_11_recommendation_scope_is_held(self):
        c, row, facts = make_case("추천 대상 중소기업")
        c["evidence_text"] = "추천 대상 중소기업"
        c["normalized_value"] = {"label": "중소기업"}
        facts = _source_facts_by_key([{"notice_id": c["notice_id"], "facts": [{
            "attribute": "company_size", "operator": "IS_A", "value": {"label": "중소기업"},
            "ambiguous": False, "evidence_text": c["evidence_text"], "char_start": 0,
            "kind": "ELIGIBILITY", "review_status": "unreviewed"}]}])
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_APPLICANT_SCOPE")

    def test_12_unmapped_certification_attribute_is_held(self):
        c, row, facts = make_case()
        c["attribute"] = "certification"
        facts = _source_facts_by_key([{"notice_id": c["notice_id"], "facts": [{
            "attribute": "certification", "operator": "EXISTS", "value": {"label": "중소기업"},
            "ambiguous": False, "evidence_text": c["evidence_text"], "char_start": 0,
            "kind": "ELIGIBILITY", "review_status": "unreviewed"}]}])
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_ATTRIBUTE_UNSUPPORTED")

    def test_13_ambiguous_source_fact_is_held(self):
        c, row, facts = make_case()
        fact = facts[(c["notice_id"], c["attribute"], 0, c["evidence_text"])][0]
        fact["ambiguous"] = True
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_AMBIGUOUS_SOURCE_FACT")

    def test_14_unstructured_exclusion_candidate_is_held(self):
        c, row, facts = make_case()
        c["kind"] = "EXCLUSION"
        self.assertEqual(validate_legacy_candidate(c, row, facts)["disposition"], "HOLD_CONDITION_POLARITY")

    def test_15_identical_rule_candidate_is_deduplicated(self):
        c, row, facts = make_case()
        p = validate_legacy_candidate(c, row, facts)["proposal"]
        merged, states = reconcile_proposals([p], [p])
        self.assertEqual(len(merged), 1)
        self.assertEqual(states[p["condition_id"]], "DUPLICATE_RULE")

    def test_16_distinct_source_spans_are_not_collapsed(self):
        a = synthetic_condition("BIZINFO:TEST-1", start=0, end=5)
        b = synthetic_condition("BIZINFO:TEST-1", start=20, end=25)
        merged, states = reconcile_proposals([], [a, b])
        self.assertEqual(len(merged), 2)
        self.assertEqual(set(states.values()), {"ADMITTED_PROPOSAL"})

    def test_17_different_values_same_span_operator_are_held(self):
        a = synthetic_condition("BIZINFO:TEST-1", value="중소기업")
        b = synthetic_condition("BIZINFO:TEST-1", value="중견기업")
        merged, states = reconcile_proposals([], [a, b])
        self.assertEqual(merged, [])
        self.assertEqual(set(states.values()), {"HOLD_VALUE_CONFLICT"})

    def test_18_different_age_bounds_remain_distinct(self):
        a = synthetic_condition("BIZINFO:TEST-1", field="BUSINESS_AGE", op="GTE", value=1)
        b = synthetic_condition("BIZINFO:TEST-1", field="BUSINESS_AGE", op="LT", value=7)
        merged, states = reconcile_proposals([], [a, b])
        self.assertEqual(len(merged), 2)
        self.assertEqual(set(states.values()), {"ADMITTED_PROPOSAL"})


if __name__ == "__main__":
    unittest.main()
