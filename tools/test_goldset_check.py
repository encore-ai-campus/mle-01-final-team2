"""label_eval / goldset_check 단위 시험 (합성 라벨·프로필). 실행: python -m unittest tools.test_goldset_check -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from goldset_check import agree_notice, kappa, validate_a, validate_b  # noqa: E402
from graphrag.label_eval import ELIGIBLE, NEEDS_CHECK, NOT_ELIGIBLE, judge  # noqa: E402

P1 = {"profile_id": "P1", "region": "서울 성동구", "business_status": "사업자", "business_age_years": 2, "founder_age": 35, "company_size": "소기업", "industry": "제조업", "employees": 8, "revenue_krw": None, "certifications": []}
P4 = {"profile_id": "P4", "region": "광주 남구", "business_status": "사업자", "business_age_years": 5, "founder_age": 39, "company_size": "중기업", "industry": "서비스업", "employees": None, "revenue_krw": None, "certifications": []}
P6 = {"profile_id": "P6", "region": "경기 성남시", "business_status": "사업자", "business_age_years": 3.0, "founder_age": 40, "company_size": None, "industry": None, "employees": None, "revenue_krw": None, "certifications": None}


def cond(cid, attr, op, value, **kw):
    d = {"cond_id": cid, "attribute": attr, "operator": op, "value": value, "ref_date_kind": "NOTICE_DATE"}
    d.update(kw)
    return d


def req(rid, conds, logic="AND", kind="ELIGIBILITY", basis="explicit", **kw):
    d = {"req_id": rid, "kind": kind, "logic": logic, "logic_basis": basis, "open_ended": False, "status": "parsed", "conditions": conds, "source_sentence": "x"}
    d.update(kw)
    return d


class TestRules(unittest.TestCase):
    def test_guide_6_1_example(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7}), cond("C2", "applicant_type", "IS_A", {"label": "창업기업"}, needs_definition=True)], basis="assumed")], "tracks": []}
        v = judge(a, P1)
        self.assertEqual(v.conditions["C1"], "SATISFIED")
        self.assertEqual(v.conditions["C2"], "UNKNOWN")
        self.assertEqual(v.overall, NEEDS_CHECK)

    def test_and_unsat_is_not_eligible(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 1}), cond("C2", "founder_age", "LTE", {"value": 39})])], "tracks": []}
        self.assertEqual(judge(a, P1).overall, NOT_ELIGIBLE)

    def test_all_satisfied_explicit_is_eligible(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7}), cond("C2", "founder_age", "LTE", {"value": 39})])], "tracks": []}
        self.assertEqual(judge(a, P1).overall, ELIGIBLE)

    def test_boundary_p6_lt3_unsat(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LT", {"value": 3})])], "tracks": []}
        self.assertEqual(judge(a, P6).conditions["C1"], "UNSATISFIED")
        self.assertEqual(judge(a, P6).overall, NOT_ELIGIBLE)

    def test_boundary_p6_lte3_sat(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 3})])], "tracks": []}
        self.assertEqual(judge(a, P6).conditions["C1"], "SATISFIED")

    def test_none_of(self):
        ex = req("R2", [cond("C2", "employees", "GTE", {"value": 10})], logic="NONE_OF", kind="EXCLUSION")
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})]), ex], "tracks": []}
        self.assertEqual(judge(a, P1).overall, ELIGIBLE)  # 직원 8명: 제외 조건 해당 안 함
        p = dict(P1, employees=12)
        self.assertEqual(judge(a, p).overall, NOT_ELIGIBLE)
        self.assertEqual(judge(a, P6).overall, NEEDS_CHECK)  # 직원 미입력 -> 제외 여부 불명

    def test_at_least(self):
        r = req("R1", [cond("C1", "business_age", "LTE", {"value": 7}), cond("C2", "founder_age", "LTE", {"value": 30}), cond("C3", "employees", "GTE", {"value": 5})], logic="AT_LEAST", min_count=2)
        a = {"requirements": [r], "tracks": []}
        self.assertEqual(judge(a, P1).overall, NOT_ELIGIBLE if False else judge(a, P1).overall)  # 충족 2(C1, C3) -> ELIGIBLE
        self.assertEqual(judge(a, P1).overall, ELIGIBLE)
        p = dict(P1, employees=None)
        self.assertEqual(judge(a, p).overall, NEEDS_CHECK)  # 충족1 + 미확인1 -> 불확정

    def test_open_ended_blocks_eligible(self):
        a = {"requirements": [req("R1", [cond("C1", "certification", "EXISTS", {"label": "벤처기업"})], logic="OR", open_ended=True)], "tracks": []}
        p = dict(P1, certifications=["벤처기업"])
        self.assertEqual(judge(a, p).overall, NEEDS_CHECK)

    def test_open_ended_no_unsat(self):
        a = {"requirements": [req("R1", [cond("C1", "certification", "EXISTS", {"label": "벤처기업"})], logic="OR", open_ended=True)], "tracks": []}
        p = dict(P1, certifications=["이노비즈"])
        self.assertEqual(judge(a, p).overall, NEEDS_CHECK)

    def test_unparsed_blocks_eligible(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})]), req("R2", [], status="unparsed")], "tracks": []}
        self.assertEqual(judge(a, P1).overall, NEEDS_CHECK)

    def test_tracks_any_eligible(self):
        t1 = req("R1", [cond("C1", "business_age", "LTE", {"value": 1})], track_id="T1")
        t2 = req("R2", [cond("C2", "business_age", "LTE", {"value": 7})], track_id="T2")
        a = {"requirements": [t1, t2], "tracks": [{"track_id": "T1"}, {"track_id": "T2"}]}
        v = judge(a, P1)
        self.assertEqual(v.overall, ELIGIBLE)
        self.assertEqual(v.tracks, {"T1": NOT_ELIGIBLE, "T2": ELIGIBLE})

    def test_region_legacy_group(self):
        a = {"requirements": [req("R1", [cond("C1", "region", "WITHIN", {"label": "광주광역시"})])], "tracks": []}
        v = judge(a, P4)
        self.assertEqual(v.conditions["C1"], "SATISFIED")

    def test_region_other_branch_unsat(self):
        a = {"requirements": [req("R1", [cond("C1", "region", "WITHIN", {"label": "부산"})])], "tracks": []}
        self.assertEqual(judge(a, P1).conditions["C1"], "UNSATISFIED")

    def test_region_parent_only_unknown(self):
        a = {"requirements": [req("R1", [cond("C1", "region", "WITHIN", {"label": "구미시"})])], "tracks": []}
        p = dict(P1, region="경북")
        self.assertEqual(judge(a, p).conditions["C1"], "UNKNOWN")

    def test_preliminary_founder_business_age_unknown(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})])], "tracks": []}
        p = {"profile_id": "P3", "region": "경남 창원시", "business_status": "예비창업자", "business_age_years": None, "founder_age": 24}
        self.assertEqual(judge(a, p).conditions["C1"], "UNKNOWN")

    def test_company_size_hierarchy(self):
        a = {"requirements": [req("R1", [cond("C1", "company_size", "IS_A", {"label": "중소기업"})])], "tracks": []}
        self.assertEqual(judge(a, P1).conditions["C1"], "SATISFIED")  # 소기업 ⊂ 중소기업
        self.assertEqual(judge(a, dict(P1, company_size="중견")).conditions["C1"], "UNSATISFIED")
        self.assertEqual(judge(a, dict(P1, company_size="소상공인")).conditions["C1"], "UNKNOWN")


class TestCheck(unittest.TestCase):
    def test_validate_a_ok(self):
        a = {"notice_id": "N", "reviewer": "A", "ambiguities": [], "requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})])]}
        self.assertEqual(validate_a(a, ""), [])

    def test_validate_a_errors(self):
        r = req("R1", [cond("C1", "badattr", "LTE", {"value": 7}), cond("C1", "business_age", "LTE", {"value": 7}, ref_date_kind="NONE")], logic="AT_LEAST")
        a = {"notice_id": "N", "reviewer": "A", "ambiguities": [], "requirements": [r]}
        e = " ".join(validate_a(a, ""))
        self.assertIn("attribute 허용 목록 밖", e)
        self.assertIn("cond_id 중복", e)
        self.assertIn("min_count", e)
        self.assertIn("기준일", e)

    def test_validate_a_source_sentence_in_packet(self):
        a = {"notice_id": "N", "reviewer": "A", "ambiguities": [], "requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})], source_sentence="업력 7년 이내")]}
        self.assertEqual(validate_a(a, "자격: 업력 7년  이내 창업기업"), [])
        self.assertTrue(validate_a(a, "전혀 다른 문장"))

    def test_validate_b(self):
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})])]}
        b = {"notice_id": "N", "judgments": [{"profile_id": "P1", "overall": "ELIGIBLE", "conditions": [{"cond_ref": "C9", "result": "SATISFIED"}], "reason_codes": ["XX"]}]}
        e = " ".join(validate_b(b, a, {"P1": {}}))
        self.assertIn("cond_ref C9", e)
        self.assertIn("reason_code", e)

    def test_agree_identical(self):
        r = req("R1", [cond("C1", "business_age", "LTE", {"value": 7})], source_sentence="업력 7년 이내 창업기업")
        a = {"requirements": [r]}
        m = agree_notice(a, a)
        self.assertEqual((m["matched"], m["cond_strict"], m["logic_match"]), (1, 1, 1))

    def test_agree_value_differs(self):
        r1 = req("R1", [cond("C1", "business_age", "LTE", {"value": 7})], source_sentence="업력 7년 이내 창업기업")
        r2 = req("R1", [cond("C1", "business_age", "LTE", {"value": 5})], source_sentence="업력 7년 이내 창업기업")
        m = agree_notice({"requirements": [r1]}, {"requirements": [r2]})
        self.assertEqual((m["cond_strict"], m["cond_loose"]), (0, 1))

    def test_kappa(self):
        self.assertEqual(kappa([("A", "A"), ("B", "B"), ("A", "A"), ("B", "B")]), 1.0)
        self.assertAlmostEqual(kappa([("A", "B"), ("B", "A")]), -1.0)


if __name__ == "__main__":
    unittest.main()
