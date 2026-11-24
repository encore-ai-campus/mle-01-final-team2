"""graphrag 평가기·지역 계층·청크 필터 단위 시험. 실행: python tools/test_graphrag.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphrag.data import _chunk  # noqa: E402
from graphrag.evaluator import (ELIGIBLE, NEEDS_CHECK, NOT_ELIGIBLE, SAT, UNK, UNSAT, Profile,  # noqa: E402
                                evaluate_condition, evaluate_notice, parse_age_options, parse_business_age_options)
from graphrag.regions import RegionGraph  # noqa: E402

RG = RegionGraph()


def region_cond(target, strength="soft"):
    return {"cond_id": "c1", "attribute": "region", "strength": strength, "value": {"concept_id": target}}


def age_cond(raw):
    return {"cond_id": "c2", "attribute": "business_age", "strength": "hard", "value": parse_business_age_options(raw)}


class RegionTests(unittest.TestCase):
    def test_sido_chain(self):
        sd = RG.find_by_name("성동구")[0]
        anc = RG.ancestors(sd)
        self.assertEqual(anc[sd], 0)
        self.assertEqual(anc["REGION:1100000000"], 1)
        self.assertEqual(anc["REGION:NATIONWIDE"], 2)

    def test_gwangju_group_between_gu_and_merged_city(self):
        namgu = "REGION:1227000000"
        anc = RG.ancestors(namgu)
        self.assertIn("REGION_GROUP:GWANGJU_OLD", anc)
        self.assertIn("REGION:1200000000", anc)
        self.assertNotIn("REGION_GROUP:JEONNAM_OLD", anc)
        self.assertEqual(len(RG.groups["REGION_GROUP:GWANGJU_OLD"]["members"]), 5)
        self.assertEqual(len(RG.groups["REGION_GROUP:JEONNAM_OLD"]["members"]), 22)

    def test_legacy_abbreviations(self):
        self.assertEqual(RG.resolve_abbr("광주"), "REGION_GROUP:GWANGJU_OLD")
        self.assertEqual(RG.resolve_abbr("전남광주"), "REGION:1200000000")
        self.assertIsNone(RG.resolve_abbr("없는지역"))

    def test_three_hop_limit(self):
        # 달서구 -> 대구 -> 경상권 -> 전국 은 3 hop, 4 hop 조상은 닿지 않는다
        dal = RG.find_by_name("달서구")[0]
        self.assertEqual(RG.ancestors(dal)["REGION_GROUP:GYEONGSANG"], 2)
        self.assertNotIn("REGION:NATIONWIDE", RG.ancestors(dal, max_hops=1))

    def test_no_cycles(self):
        for rid in RG.nodes:
            self.assertEqual(RG.ancestors(rid, 10)[rid], 0)
            # 자기 자신이 자신의 상위에 다시 나타나면 순환
            seen = {p for p, _ in RG.parents.get(rid, [])}
            self.assertNotIn(rid, seen)


class ConditionTests(unittest.TestCase):
    def test_region_satisfied_with_path(self):
        r = evaluate_condition(region_cond("REGION:1100000000"), Profile(region=RG.find_by_name("성동구")[0]), RG)
        self.assertEqual(r.status, SAT)
        self.assertEqual(r.path, ["성동구", "서울특별시"])

    def test_region_user_value_above_condition_is_unknown(self):  # H3
        r = evaluate_condition(region_cond(RG.find_by_name("성동구")[0]), Profile(region="REGION:1100000000"), RG)
        self.assertEqual(r.status, UNK)

    def test_region_different_branch_unsatisfied(self):
        r = evaluate_condition(region_cond("REGION:2600000000"), Profile(region="REGION:1100000000"), RG)
        self.assertEqual(r.status, UNSAT)

    def test_region_missing_input_unknown(self):
        self.assertEqual(evaluate_condition(region_cond("REGION:1100000000"), Profile(), RG).status, UNK)

    def test_region_nationwide(self):
        self.assertEqual(evaluate_condition(region_cond("REGION:NATIONWIDE"), Profile(), RG).status, SAT)

    def test_legacy_gwangju_matches_namgu_but_flags_unreviewed(self):
        r = evaluate_condition(region_cond("REGION_GROUP:GWANGJU_OLD"), Profile(region="REGION:1227000000"), RG)
        self.assertEqual(r.status, SAT)
        self.assertIn("unreviewed_group", r.flags)
        r2 = evaluate_condition(region_cond("REGION_GROUP:GWANGJU_OLD"), Profile(region="REGION:1211000000"), RG)  # 목포시
        self.assertEqual(r2.status, UNSAT)

    def test_business_age_boundaries(self):
        c = age_cond("3년미만")
        self.assertEqual(evaluate_condition(c, Profile(business_age_years=1), RG).status, SAT)
        self.assertEqual(evaluate_condition(c, Profile(business_age_years=2.8), RG).status, UNK)  # 기준일 불명 경계
        self.assertEqual(evaluate_condition(c, Profile(business_age_years=3), RG).status, UNK)
        self.assertEqual(evaluate_condition(c, Profile(business_age_years=5), RG).status, UNSAT)

    def test_pre_founder(self):
        self.assertEqual(evaluate_condition(age_cond("예비창업자,3년미만"), Profile(pre_founder=True), RG).status, SAT)
        self.assertEqual(evaluate_condition(age_cond("3년미만"), Profile(pre_founder=True), RG).status, UNSAT)
        self.assertEqual(evaluate_condition(age_cond("예비창업자"), Profile(business_age_years=1), RG).status, UNSAT)

    def test_all_options_does_not_become_unconditional_pass(self):
        c = age_cond("예비창업자,1년미만,2년미만,3년미만,5년미만,7년미만,10년미만")
        r = evaluate_condition(c, Profile(business_age_years=15), RG)
        self.assertEqual(r.status, UNK)  # '전체 나열 = 제한 없음' 규칙은 미검증이라 SATISFIED로 만들지 않는다
        self.assertEqual(evaluate_condition(c, Profile(business_age_years=4), RG).status, SAT)

    def test_unparseable_options_return_none(self):
        self.assertIsNone(parse_business_age_options("알수없음"))
        self.assertIsNone(parse_age_options("만 50세"))

    def test_missing_input_is_never_satisfied(self):
        for c in (age_cond("3년미만"), region_cond("REGION:1100000000")):
            self.assertEqual(evaluate_condition(c, Profile(), RG).status, UNK)


class NoticeTests(unittest.TestCase):
    def test_hard_fail_is_not_eligible(self):
        n = {"notice_id": "N", "conditions": [age_cond("3년미만")], "text_requirements": "unparsed"}
        self.assertEqual(evaluate_notice(n, Profile(business_age_years=9), RG)["verdict"], NOT_ELIGIBLE)

    def test_soft_fail_is_needs_check_not_not_eligible(self):
        n = {"notice_id": "N", "conditions": [region_cond("REGION:2600000000")], "text_requirements": "reviewed"}
        r = evaluate_notice(n, Profile(region="REGION:1100000000"), RG)
        self.assertEqual(r["verdict"], NEEDS_CHECK)
        self.assertIn("SOFT_CONDITION_UNSATISFIED", r["reasons"])

    def test_unparsed_text_requirements_never_eligible(self):
        n = {"notice_id": "N", "conditions": [age_cond("3년미만")], "text_requirements": "unparsed"}
        r = evaluate_notice(n, Profile(business_age_years=1), RG)
        self.assertEqual(r["structured"], "PASS")
        self.assertEqual(r["verdict"], NEEDS_CHECK)
        self.assertIn("REQ_UNPARSED", r["reasons"])

    def test_eligible_only_when_everything_passes_and_text_reviewed(self):
        n = {"notice_id": "N", "conditions": [age_cond("3년미만")], "text_requirements": "reviewed"}
        self.assertEqual(evaluate_notice(n, Profile(business_age_years=1), RG)["verdict"], ELIGIBLE)


class ChunkTests(unittest.TestCase):
    def test_short_and_redaction_only_chunks_are_dropped(self):
        self.assertEqual(_chunk("N", "S", "x", "API", "창업교육"), [])
        self.assertEqual(_chunk("N", "S", "x", "API", "[REDACTED_CONTACT]" * 3), [])
        self.assertEqual(len(_chunk("N", "S", "x", "API", "창업 7년 이내 기업을 대상으로 사업화 자금을 지원합니다")), 1)


if __name__ == "__main__":
    unittest.main()
