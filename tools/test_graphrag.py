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


class RegionTableTests(unittest.TestCase):
    """지역 코드표 318행, WITHIN(행정)과 MEMBER_OF(묶음) 분리(설계서 4.2 H13·H14)."""

    def test_missing_sigungu_are_now_found(self):
        for name in ("강북구", "광진구", "금천구", "연수구", "계양구", "부평구", "미추홀구", "제물포구", "영종구", "서해구", "증평군", "태안군"):
            self.assertEqual(len(RG.find_by_name(name)), 1, name)

    def test_general_gu_reaches_sido_in_three_hops(self):
        jangan = RG.find_by_name("장안구")[0]
        anc = RG.ancestors(jangan)
        self.assertEqual((anc["REGION:4111000000"], anc["REGION:4100000000"], anc["REGION:NATIONWIDE"]), (1, 2, 3))

    def test_every_region_has_exactly_one_admin_parent(self):  # 점검 V8
        for rid, n in RG.nodes.items():
            if n.get("level") in ("NATIONWIDE", "GROUP"):
                continue
            self.assertEqual(len(RG.admin_parents(rid)), 1, rid)

    def test_every_edge_endpoint_is_a_node(self):
        """전국 노드와 통합 후계(MERGED_INTO)가 실제 노드로 이어져야 한다(그래프 내보내기 점검에서 발견)."""
        self.assertIn(RG.nodes["REGION:NATIONWIDE"]["level"], ("NATIONWIDE",))
        known = set(RG.nodes) | set(RG.retired)
        for rid, parents in RG.parents.items():
            for p, _ in parents:
                self.assertIn(p, known, (rid, p))
        for rid, succ in RG.successors.items():
            for sid in succ:
                self.assertIn(sid, known, (rid, sid))

    def test_group_membership_uses_member_of_not_within(self):
        namgu = "REGION:1227000000"
        rels = {p: rel for p, rel in RG.parents[namgu]}
        self.assertEqual(rels["REGION:1200000000"], "WITHIN")
        self.assertEqual(rels["REGION_GROUP:GWANGJU_OLD"], "MEMBER_OF")
        self.assertEqual(RG.edge_basis[(namgu, "REGION_GROUP:GWANGJU_OLD", "MEMBER_OF")], "GROUP_MEMBER")

    def test_retired_regions_are_not_searchable_but_keep_successors(self):
        self.assertEqual(len(RG.retired), 33)
        self.assertNotIn("REGION:2811000000", RG.nodes)  # 옛 인천 중구
        self.assertEqual(RG.successors["REGION:2811000000"], ["REGION:2812500000", "REGION:2815500000"])
        self.assertEqual(len(RG.find_by_name("중구", "SIGUNGU")), len([r for r in RG.nodes.values() if r["name"] == "중구" and r["level"] == "SIGUNGU"]))


class ConceptsAndLawsTests(unittest.TestCase):
    """신청자 유형·인증 개념, 법령 노드, 정의 노드(설계서 4.1·4.2·4.3)."""

    @classmethod
    def setUpClass(cls):
        from graphrag import concepts_laws as C
        cls.C = C
        cls.cnodes, cls.cedges, cls.by_label = C.concepts()
        cls.lnodes, cls.ledges, cls.index, cls.pending = C.laws()
        cls.dnodes, cls.dedges, cls.notes = C.definitions(cls.by_label, cls.index)

    def test_certified_statuses_are_certification_not_applicant_type(self):
        for name in ("벤처기업", "사회적기업", "여성기업", "장애인기업", "이노비즈", "메인비즈", "소상공인확인"):
            self.assertEqual(self.by_label[name], f"CERTIFICATION:{name}")
        self.assertEqual(self.by_label["소상공인"], "APPLICANT_TYPE:소상공인")  # 규모 개념은 신청자 유형에 남는다
        self.assertNotIn("APPLICANT_TYPE:벤처기업", {n["concept_id"] for n in self.cnodes})

    def test_only_law_grounded_is_a_edges(self):
        self.assertEqual({(e["from"], e["to"]) for e in self.cedges},
                         {("APPLICANT_TYPE:소기업", "APPLICANT_TYPE:중소기업"), ("APPLICANT_TYPE:중기업", "APPLICANT_TYPE:중소기업")})

    def test_law_counts_match_collected_data(self):
        from collections import Counter
        c = Counter(n["label"] for n in self.lnodes)
        self.assertEqual((c["ExternalLaw"], c["LawArticle"], c["LawAppendix"]), (44, 2325, 59))
        self.assertEqual(len(self.ledges), 2384)  # 조문·별표마다 PART_OF 하나
        ids = [n.get("article_id") or n.get("appendix_id") or n["law_id"] for n in self.lnodes]
        self.assertEqual(len(ids), len(set(ids)))  # 같은 번호의 별표가 있어도 ID는 유일

    def test_definitions_link_only_what_exists(self):
        self.assertEqual(len(self.dnodes), 16)  # v0.1 사전 6 + v0.3 추가 법령 10
        self.assertEqual(sum(e["type"] == "CITES_LAW" for e in self.dedges), 16)
        self.assertEqual(sum(e["type"] == "DEFINED_BY" for e in self.dedges), 8)  # 청년창업기업·중장년창업기업·마을기업·어업인·농업인·자활기업·연구소기업·중소기업협동조합은 같은 이름의 개념이 없다
        self.assertEqual(len(self.notes), 8)
        self.assertTrue(all("rule_json" not in n for n in self.dnodes))  # 원문 확인 전에는 판정 기준을 만들지 않는다

    def test_v03_definitions_are_verbatim_clauses(self):
        from graphrag import concepts_laws as C
        arts = {(r["doc_name"], str(r["article_no"])): r["text"] for r in C._jsonl(C.LAW_DIR / "조문.jsonl") if r.get("level") == "article"}
        defs = C.law_definitions_v03()
        self.assertEqual(len(defs), len(C.LAW_DEFS_V03))  # 원문에서 못 찾은 정의가 없어야 한다
        for name, legal, law, art_no, _, _ in C.LAW_DEFS_V03:
            self.assertIn(defs[name]["text"], arts[(law, art_no)])  # 잘라 온 조항이 조문 원문 그대로다
            self.assertIn(legal, defs[name]["text"])
        self.assertNotIn("3의3.", defs["이노비즈"]["text"])  # 다음 호에서 멈춘다
        self.assertIn("나. 해당 기업에 고용된", defs["장애인기업"]["text"])  # 딸린 목은 포함
        self.assertNotIn("③", defs["자활기업"]["text"])

    def test_citation_backlog_keeps_every_citing_notice(self):
        self.assertEqual(len(self.pending), 640)  # v0.1 543 + v0.2 추가 법령 인용 97


class ConditionSchemaTests(unittest.TestCase):
    """조건 값 스키마 통일(설계서 4.3). 옛 옵션 목록 값과 새 형식의 숫자가 같아야 한다."""

    def test_business_age_keeps_lt(self):
        from graphrag.condition_schema import unify
        legacy = parse_business_age_options("1년미만,2년미만,3년미만")
        self.assertEqual(unify("business_age", legacy), ("business_age", "LT", {"value": 3, "unit": "YEAR"}))

    def test_all_options_is_unknown_not_unlimited(self):
        from graphrag.condition_schema import unify
        legacy = parse_business_age_options("예비창업자,1년미만,2년미만,3년미만,5년미만,7년미만,10년미만")
        attr, op, val = unify("business_age", legacy)
        self.assertEqual((attr, op, val), ("business_age", None, {"all_options": True}))

    def test_only_pre_founder_becomes_applicant_type(self):
        from graphrag.condition_schema import unify
        self.assertEqual(unify("business_age", parse_business_age_options("예비창업자")), ("applicant_type", "IN", {"labels": ["예비창업자"]}))

    def test_pre_founder_is_split_into_or_requirement(self):
        from graphrag.condition_schema import split_pre_founder
        age = {"attribute": "business_age", "value": parse_business_age_options("예비창업자,1년미만,3년미만")}
        other = {"attribute": "region", "value": {"concept_id": "REGION:1100000000"}}
        rest, split = split_pre_founder([age, other])
        self.assertIs(split, age)
        self.assertEqual(rest, [other])
        rest, split = split_pre_founder([{"attribute": "business_age", "value": parse_business_age_options("1년미만,3년미만")}])
        self.assertIsNone(split)  # 예비창업자 허용이 없으면 분리하지 않는다

    def test_founder_age_ranges_keep_half_open_bounds(self):
        from graphrag.condition_schema import unify
        attr, op, val = unify("founder_age", {"ranges": [(20, 40), (40, 200)]})
        self.assertEqual(op, "BETWEEN")
        self.assertEqual(val["ranges"][0], {"min": 20, "max": 40, "min_inclusive": True, "max_inclusive": False})
        self.assertIsNone(val["ranges"][1]["max"])


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
