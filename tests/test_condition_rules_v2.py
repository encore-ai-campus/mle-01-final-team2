import json
import unittest

from tools.extract_condition_candidates_rules_v2 import (
    _context_safe,
    categorical_candidates,
    condition_type_review_candidates,
    extract_experiment,
    quantitative_candidates,
)


def row(text, notice="SYNTH:1", source="BIZINFO"):
    return {"notice_id": notice, "source_system": source, "raw_text": text, "chunk_ids": []}


class RuleImprovementTests(unittest.TestCase):
    def test_age_operator_boundary_keywords(self):
        got = quantitative_candidates(row("신청자는 만 39세 이하"))
        age = next(c for c in got if c["field"] == "APPLICANT_AGE")
        self.assertEqual((age["operator"], age["value"], age["unit"]), ("LTE", 39, "YEAR"))

    def test_age_requires_applicant_context(self):
        got = quantitative_candidates(row("참여 프로그램은 39세 이하 대상"))
        self.assertFalse(any(c["field"] == "APPLICANT_AGE" for c in got))

    def test_age_range_keeps_both_bounds(self):
        got = quantitative_candidates(row("대표자 및 팀원 연령 만 19~39세"))
        age = next(c for c in got if c["field"] == "APPLICANT_AGE")
        self.assertEqual(age["operator"], "BETWEEN")
        self.assertEqual(age["value"], {"lower": {"value": 19, "inclusive": True}, "upper": {"value": 39, "inclusive": True}})
        self.assertEqual(age["value_type"], "RANGE")

    def test_age_chained_comparators_preserve_inclusive_bounds(self):
        got = quantitative_candidates(row("신청자 나이는 19세 이상 39세 이하"))
        age = next(c for c in got if c["field"] == "APPLICANT_AGE")
        self.assertEqual(age["value"], {"lower": {"value": 19, "inclusive": True}, "upper": {"value": 39, "inclusive": True}})

    def test_business_age_chained_comparators_preserve_open_upper_bound(self):
        got = quantitative_candidates(row("업력 3년 이상 7년 미만 기업"))
        age = next(c for c in got if c["field"] == "BUSINESS_AGE")
        self.assertEqual(age["value"], {"lower": {"value": 3, "inclusive": True}, "upper": {"value": 7, "inclusive": False}})
        self.assertEqual(age["operator"], "BETWEEN")

    def test_startup_age_uses_year_unit(self):
        got = quantitative_candidates(row("업력 7년 미만인 기업"))
        self.assertEqual([(c["field"], c["value"], c["operator"], c["unit"]) for c in got],
                         [("BUSINESS_AGE", 7, "LT", "YEAR")])

    def test_months_are_not_converted_to_years(self):
        got = quantitative_candidates(row("창업 후 18개월 이내"))
        self.assertEqual(got[0]["unit"], "MONTH")
        self.assertEqual(got[0]["value"], 18)

    def test_employee_count_and_operator(self):
        got = quantitative_candidates(row("상시근로자 5명 이상"))
        employee = next(c for c in got if c["field"] == "EMPLOYEE_COUNT")
        self.assertEqual((employee["value"], employee["operator"], employee["unit"]), (5, "GTE", "PERSON"))

    def test_revenue_is_separate_from_revenue_share(self):
        got = quantitative_candidates(row("매출액 3억원 이상, 산업 매출 비중 20% 이상"))
        self.assertEqual({c["field"] for c in got}, {"REVENUE", "INDUSTRY_REVENUE_SHARE"})

    def test_currency_conversion_preserves_currency(self):
        got = quantitative_candidates(row("매출액 1,200만원 이상 및 지원금 5,000 USD 이상"))
        revenue, usd = got
        self.assertEqual((revenue["value"], revenue["unit"]), (12_000_000, "KRW"))
        self.assertEqual((usd["value"], usd["unit"]), (5_000, "USD"))

    def test_currency_in_parentheses_is_not_a_second_condition(self):
        got = quantitative_candidates(row("매출액 1억원 이상(원화 환산액 100,000,000원)"))
        self.assertEqual(len(got), 1)

    def test_multiple_business_types_are_preserved(self):
        got = categorical_candidates(row("신청 대상은 중소기업 및 소상공인"))
        self.assertEqual({c["value"] for c in got if c["field"] == "BUSINESS_TYPE"}, {"중소기업", "소상공인"})

    def test_head_office_and_business_site_markers_gate_location(self):
        good = categorical_candidates(row("경기도 사업장 소재 기업 신청 가능"))
        self.assertTrue(any(c["field"] == "BUSINESS_LOCATION" and c["value"] == "경기도" for c in good))
        bad = categorical_candidates(row("지원기관은 경기도에 소재"))
        self.assertFalse(any(c["field"] == "BUSINESS_LOCATION" for c in bad))

    def test_applicant_address_is_not_business_site(self):
        got = categorical_candidates(row("신청자 주소지는 대구이고 사업장 소재지는 경기도이다."))
        fields = {c["field"] for c in got}
        self.assertIn("APPLICANT_ADDRESS", fields)
        self.assertIn("BUSINESS_LOCATION", fields)

    def test_nationwide_is_not_a_positive_region(self):
        got = categorical_candidates(row("전국 소재 기업 지원"))
        self.assertFalse(any(c["field"] == "BUSINESS_LOCATION" for c in got))

    def test_recommended_target_does_not_become_applicant_type(self):
        got = categorical_candidates(row("추천 대상 창업기업은 중소기업"))
        self.assertFalse(got)

    def test_certification_holding_is_distinct_from_document_submission(self):
        holding = categorical_candidates(row("벤처기업 인증을 보유한 기업"))
        submission = categorical_candidates(row("벤처기업 인증서를 제출한 기업"))
        self.assertTrue(any(c["field"] == "CERTIFICATION" for c in holding))
        self.assertFalse(submission)

    def test_business_registration_status_is_not_a_document(self):
        got = categorical_candidates(row("신청기업은 사업자등록이 완료되어야 한다."))
        self.assertTrue(any(c["field"] == "BUSINESS_REGISTRATION_STATUS" for c in got))
        document = categorical_candidates(row("사업자등록증을 제출해야 한다."))
        self.assertFalse(any(c["field"] == "BUSINESS_REGISTRATION_STATUS" for c in document))

    def test_program_participation_requires_explicit_status(self):
        got = categorical_candidates(row("지원사업에 참여중인 기업"))
        self.assertTrue(any(c["field"] == "PROGRAM_PARTICIPATION" for c in got))
        future = categorical_candidates(row("지원사업 참여를 희망하는 기업"))
        self.assertFalse(any(c["field"] == "PROGRAM_PARTICIPATION" for c in future))

    def test_document_submission_is_kept_separate(self):
        got = categorical_candidates(row("사업계획서를 제출해야 신청할 수 있다."))
        self.assertTrue(any(c["field"] == "DOCUMENT_SUBMISSION" for c in got))

    def test_industry_requires_eligibility_context(self):
        good = categorical_candidates(row("정보통신 분야 기업이 신청할 수 있다."))
        self.assertTrue(any(c["field"] == "INDUSTRY" for c in good))
        bad = categorical_candidates(row("정보통신 분야 소개"))
        self.assertFalse(any(c["field"] == "INDUSTRY" for c in bad))

    def test_exclusion_and_preference_are_separate_types(self):
        r = row("지원 제외 대상은 중복수혜 기업이다. 우대 대상은 청년기업이다.")
        got = condition_type_review_candidates(r)
        self.assertIn("EXCLUSION", {c["condition_type"] for c in got})
        self.assertIn("PREFERENCE", {c["condition_type"] for c in got})
        self.assertTrue(all(c["decision_eligible"] is False and c["review_status"] == "NEEDS_REVIEW" for c in got))

    def test_source_offsets_round_trip(self):
        r = row("앞 문구. 업력 7년 미만인 기업 신청 가능.")
        c = quantitative_candidates(r)[0]
        loc = c["source"]["location"]
        self.assertEqual(r["raw_text"][loc["start_char"]:loc["end_char"]], c["source"]["evidence_text"])
        self.assertEqual(c["raw_text"], c["source"]["evidence_text"])

    def test_identical_candidates_deduplicate_and_keep_baseline(self):
        r = row("업력 7년 미만인 기업")
        first = quantitative_candidates(r)[0]
        out = extract_experiment(r, [first], "A")
        self.assertEqual(len(out), 1)
        self.assertEqual(first["review_status"], "UNREVIEWED")
        self.assertFalse(first["decision_eligible"])

    def test_experiment_modes_are_deterministic_and_separate(self):
        r = row("신청 대상은 중소기업이고 사업장 소재지는 대구이다. 업력 7년 미만")
        first = extract_experiment(r, [], "E")
        second = extract_experiment(r, [], "E")
        canon = lambda xs: json.dumps(xs, ensure_ascii=False, sort_keys=True)
        self.assertEqual(canon(first), canon(second))
        self.assertNotEqual(len(extract_experiment(r, [], "A")), len(first))


if __name__ == "__main__":
    unittest.main()
