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


def grp(cid, logic, children, **kw):
    d = {"cond_id": cid, "logic": logic, "children": children}
    d.update(kw)
    return d


class TestGroups(unittest.TestCase):
    def test_nested_or_of_and(self):
        # 구미 건(T-07)의 구조: OR{ AND{지역 구미, 업력 7년 이내}, 본사 이전 계획 }
        g = grp("G1", "AND", [cond("C1", "region", "WITHIN", {"label": "구미"}), cond("C2", "business_age", "LTE", {"value": 7})])
        other = cond("C3", "other", "EQ", {"label": "본사 이전 계획"})
        a = {"requirements": [req("R1", [g, other], logic="OR")], "tracks": []}
        p_in = dict(P1, region="경북 구미시", business_age_years=5)
        v = judge(a, p_in)
        self.assertEqual((v.conditions["G1"], v.conditions["C3"], v.overall), ("SATISFIED", "UNKNOWN", ELIGIBLE))
        p_old = dict(P1, region="경북 구미시", business_age_years=9)
        v = judge(a, p_old)
        self.assertEqual((v.conditions["G1"], v.overall), ("UNSATISFIED", NEEDS_CHECK))  # 이전 계획은 알 수 없어 확정 못 함
        v = judge(a, P1)  # 서울: 지역 불충족 -> 그룹 불충족, 이전 계획 미확인
        self.assertEqual((v.conditions["G1"], v.overall), ("UNSATISFIED", NEEDS_CHECK))

    def test_group_depth_limit(self):
        three = grp("G1", "AND", [grp("G2", "AND", [grp("G3", "AND", [cond("C1", "business_age", "LTE", {"value": 7})])])])
        a = {"requirements": [req("R1", [three])], "tracks": []}
        self.assertEqual(judge(a, P1).conditions["G3"], "SATISFIED")  # 그룹 3단까지 허용
        four = grp("G1", "AND", [grp("G2", "AND", [grp("G3", "AND", [grp("G4", "AND", [cond("C1", "business_age", "LTE", {"value": 7})])])])])
        a = {"requirements": [req("R1", [four])], "tracks": []}
        self.assertEqual(judge(a, P1).conditions["G4"], "UNKNOWN")  # 4단째는 평가하지 않고 UNKNOWN
        arec = {"notice_id": "N", "reviewer": "A", "ambiguities": [], "requirements": [req("R1", [four])]}
        self.assertIn("3단을 넘음", " ".join(validate_a(arec, "")))

    def test_preference_not_used_for_overall(self):
        pref = req("R2", [cond("C2", "founder_age", "LTE", {"value": 30})], kind="PREFERENCE")
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})]), pref], "tracks": []}
        v = judge(a, P1)  # 대표자 35세: 우대 불충족이어도 신청 가능
        self.assertEqual((v.overall, v.preferences), (ELIGIBLE, {"R2": "UNSATISFIED"}))

    def test_exclusion_none_of_group(self):
        ex = req("R2", [cond("C2", "employees", "GTE", {"value": 10}), cond("C3", "revenue", "GTE", {"value": 1000})], logic="NONE_OF", kind="EXCLUSION")
        a = {"requirements": [req("R1", [cond("C1", "business_age", "LTE", {"value": 7})]), ex], "tracks": []}
        self.assertEqual(judge(a, dict(P1, revenue_krw=0)).overall, ELIGIBLE)
        self.assertEqual(judge(a, dict(P1, employees=20, revenue_krw=0)).overall, NOT_ELIGIBLE)
        self.assertEqual(judge(a, P1).overall, NEEDS_CHECK)  # 매출 미입력

    def test_validate_group(self):
        g = grp("G1", "XOR", [cond("C1", "business_age", "LTE", {"value": 7})])
        a = {"notice_id": "N", "reviewer": "A", "ambiguities": [], "requirements": [req("R1", [g])]}
        self.assertIn("그룹의 logic 값 오류", " ".join(validate_a(a, "")))
        g = grp("G1", "OR", [cond("C1", "business_age", "LTE", {"value": 7}), cond("C2", "founder_age", "LTE", {"value": 39})])
        a = {"notice_id": "N", "reviewer": "A", "ambiguities": [], "requirements": [req("R1", [g])]}
        self.assertEqual(validate_a(a, ""), [])


class TestExceptionDirections(unittest.TestCase):
    """설계서 §4.3 부정 표현 규칙과 §4.7 예외 방향 표의 3값 결과를 평가기로 확인한다."""

    base = req("R1", [cond("C1", "business_age", "LTE", {"value": 7})])

    def test_exclusion_and_vs_or_keep_their_meaning(self):
        a_and = {"requirements": [self.base, req("R2", [grp("G1", "AND", [cond("C2", "employees", "GTE", {"value": 10}), cond("C3", "revenue", "GTE", {"value": 1000})])],
                                                  logic="NONE_OF", kind="EXCLUSION")], "tracks": []}
        a_or = {"requirements": [self.base, req("R2", [cond("C2", "employees", "GTE", {"value": 10}), cond("C3", "revenue", "GTE", {"value": 1000})],
                                                 logic="NONE_OF", kind="EXCLUSION")], "tracks": []}
        only_one = dict(P1, employees=20, revenue_krw=500)  # A만 해당
        self.assertEqual(judge(a_and, only_one).overall, ELIGIBLE)      # A이면서 B인 기업 제외: 둘 다여야 제외
        self.assertEqual(judge(a_or, only_one).overall, NOT_ELIGIBLE)   # 하나라도 해당하면 제외
        both = dict(P1, employees=20, revenue_krw=2000)
        self.assertEqual(judge(a_and, both).overall, NOT_ELIGIBLE)

    def test_relaxes_eligibility(self):
        r = req("R1", [cond("C1", "employees", "GTE", {"value": 10}), cond("C2", "certification", "EXISTS", {"label": "벤처기업"})], logic="OR")
        a = {"requirements": [r], "tracks": []}
        small = dict(P1, employees=8)
        self.assertEqual(judge(a, dict(small, certifications=["벤처기업"])).overall, ELIGIBLE)   # 기본 불충족 + 예외 충족
        self.assertEqual(judge(a, dict(small, certifications=[])).overall, NOT_ELIGIBLE)        # 기본 불충족 + 예외 불충족
        self.assertEqual(judge(a, dict(small, certifications=None)).overall, NEEDS_CHECK)       # 예외 여부 미확인
        self.assertEqual(judge(a, dict(P1, employees=12, certifications=None)).overall, ELIGIBLE)  # 기본 충족이면 예외 무관

    def test_lifts_exclusion(self):
        # 제외 대상(직원 10명 이상)이어도 예외(인증 보유)에 해당하면 제외되지 않는다: NONE_OF{ AND(제외 상태, NOT 예외) }
        ex = req("R2", [grp("G1", "AND", [cond("C2", "employees", "GTE", {"value": 10}),
                                          cond("C3", "certification", "EXISTS", {"label": "벤처기업"}, negate=True)])],
                 logic="NONE_OF", kind="EXCLUSION")
        a = {"requirements": [self.base, ex], "tracks": []}
        self.assertEqual(judge(a, dict(P1, employees=8, certifications=[])).overall, ELIGIBLE)        # 제외 대상 아님
        self.assertEqual(judge(a, dict(P1, employees=12, certifications=["벤처기업"])).overall, ELIGIBLE)  # 예외 해당
        self.assertEqual(judge(a, dict(P1, employees=12, certifications=[])).overall, NOT_ELIGIBLE)    # 예외 해당 안 됨
        self.assertEqual(judge(a, dict(P1, employees=12, certifications=None)).overall, NEEDS_CHECK)   # 예외 여부 미확인

    def test_narrows_eligibility_is_a_separate_exclusion(self):
        ex = req("R2", [cond("C2", "employees", "GTE", {"value": 10})], logic="NONE_OF", kind="EXCLUSION")
        a = {"requirements": [self.base, ex], "tracks": []}
        self.assertEqual(judge(a, dict(P1, employees=12)).overall, NOT_ELIGIBLE)


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
