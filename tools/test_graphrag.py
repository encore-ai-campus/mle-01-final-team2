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
        self.assertEqual(len(self.dnodes), 23)  # v0.1 사전 6 + v0.2 법령 7 + v0.3 추가 법령 10
        self.assertEqual(sum(e["type"] == "CITES_LAW" for e in self.dedges), 23)
        self.assertEqual(sum(e["type"] == "DEFINED_BY" for e in self.dedges), 21)  # 청년창업기업·중장년창업기업은 같은 이름의 개념이 없다
        self.assertEqual(len(self.notes), 2)
        self.assertTrue(all("rule_json" not in n for n in self.dnodes))  # 원문 확인 전에는 판정 기준을 만들지 않는다

    def test_v03_definitions_are_verbatim_clauses(self):
        from graphrag import concepts_laws as C
        arts = {(r["doc_name"], str(r["article_no"])): r["text"] for r in C._jsonl(C.LAW_DIR / "조문.jsonl") if r.get("level") == "article"}
        defs = C.law_definitions()
        self.assertEqual(len(defs), len(C.LAW_DEFS))  # 원문에서 못 찾은 정의가 없어야 한다
        for name, legal, law, art_no, _, _ in C.LAW_DEFS:
            self.assertIn(defs[name]["text"], arts[(law, art_no)])  # 잘라 온 조항이 조문 원문 그대로다
            self.assertIn(legal, defs[name]["text"])
        self.assertNotIn("3의3.", defs["이노비즈"]["text"])  # 다음 호에서 멈춘다
        self.assertIn("나. 해당 기업에 고용된", defs["장애인기업"]["text"])  # 딸린 목은 포함
        self.assertNotIn("③", defs["자활기업"]["text"])
        self.assertIn("3년간은 소상공인으로 본다", defs["소상공인"]["text"])  # 유예 조항(제2항)까지
        self.assertIn("다. 그 밖에 지분 소유", defs["중견기업"]["text"])  # 번호 뒤 공백 없는 호도 찾는다
        self.assertNotIn("중견기업 후보기업", defs["중견기업"]["text"])
        self.assertNotIn("평가기준과 평가방법", defs["벤처기업"]["text"])  # 제2조의2 제2항은 빼고
        self.assertNotIn("사회적협동조합", defs["협동조합"]["text"])
        self.assertNotIn("청년 1인 창조기업", defs["1인 창조기업"]["text"])
        sme = defs["중소기업"]["text"]  # 용어 사전의 `[중략]` 문장 대신 조문 원문
        self.assertNotIn("[중략]", sme)
        self.assertIn("5. 「중소기업협동조합법」", sme)
        self.assertIn("5년간은 중소기업으로 본다", sme)
        self.assertNotIn("④", sme)

    def test_law_source_url_opens_collected_version(self):
        laws = [n for n in self.lnodes if n["label"] == "ExternalLaw"]
        self.assertTrue(all(n["source_url"] == f"https://www.law.go.kr/lsInfoP.do?lsiSeq={n['law_id'].split(':')[1]}" for n in laws))

    def test_every_applicant_type_with_a_law_definition_is_linked(self):
        defined = {e["from"] for e in self.dedges if e["type"] == "DEFINED_BY"}
        for name in ("소상공인", "중견기업", "벤처기업", "여성기업", "사회적기업", "협동조합", "1인 창조기업"):
            self.assertIn(self.by_label[name], defined)

    def test_v03_concepts_are_defined_by_law(self):
        from graphrag import concepts_laws as C
        defined = {e["from"] for e in self.dedges if e["type"] == "DEFINED_BY"}
        for scheme, name, _, _ in C.LAW_CONCEPTS_V03:
            self.assertEqual(self.by_label[name], f"{scheme}:{name}")
            self.assertIn(f"{scheme}:{name}", defined)  # 새 개념은 모두 법령 정의에 이어진다
        self.assertNotEqual(self.by_label["중소기업협동조합"], self.by_label["협동조합"])  # 협동조합 기본법의 협동조합과 다른 개념

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


class RequirementLogicTests(unittest.TestCase):
    """평가기가 그래프와 같은 요건 단위(`requirement_groups`)로 AND/OR를 합친다."""

    def notice(self, *conds, text="reviewed"):
        return {"notice_id": "N", "conditions": list(conds), "text_requirements": text}

    def test_pre_founder_age_option_becomes_or_requirement(self):
        r = evaluate_notice(self.notice(region_cond("REGION:1100000000"), age_cond("예비창업자,3년미만")), Profile(pre_founder=True, region="REGION:1100000000"), RG)
        self.assertEqual([(q["req_id"], q["logic"]) for q in r["requirements"]], [("N#R1", "AND"), ("N#R2", "OR")])
        self.assertEqual(r["requirements"][1]["cond_ids"], ["c2", "N#C-pre_founder"])
        self.assertEqual(r["requirements"][1]["status"], SAT)
        self.assertEqual(r["verdict"], ELIGIBLE)  # 업력 조건이 불충족이어도 같은 OR 요건의 예비창업자가 충족하면 사유가 아니다

    def test_or_requirement_outcomes(self):
        n = self.notice(age_cond("예비창업자,3년미만"))
        cases = [(Profile(business_age_years=1), ELIGIBLE),             # 업력 충족
                 (Profile(business_age_years=9), NOT_ELIGIBLE),         # 업력 불충족, 업력이 있으니 예비창업자 아님
                 (Profile(pre_founder=False, business_age_years=9), NOT_ELIGIBLE),
                 (Profile(business_age_years=2.8), NEEDS_CHECK),        # 경계값 UNKNOWN OR 불충족 -> UNKNOWN
                 (Profile(), NEEDS_CHECK)]                              # 아무것도 모르면 UNKNOWN
        for prof, want in cases:
            self.assertEqual(evaluate_notice(n, prof, RG)["verdict"], want, prof)

    def test_age_without_pre_founder_option_stays_in_and_requirement(self):
        r = evaluate_notice(self.notice(age_cond("3년미만")), Profile(pre_founder=True), RG)
        self.assertEqual([q["logic"] for q in r["requirements"]], ["AND"])
        self.assertEqual(r["verdict"], NOT_ELIGIBLE)

    def test_combine_three_valued(self):
        from graphrag.evaluator import combine
        self.assertEqual(combine("AND", [SAT, UNK]), UNK)
        self.assertEqual(combine("AND", [UNK, UNSAT]), UNSAT)
        self.assertEqual(combine("OR", [UNSAT, UNK]), UNK)
        self.assertEqual(combine("OR", [UNK, SAT]), SAT)
        self.assertEqual(combine("OR", [UNSAT, UNSAT]), UNSAT)
        self.assertEqual(combine("NONE_OF", [SAT]), UNK)  # 규칙 없는 논리는 판정하지 않는다


def gold(gid, ctype, field, op, value, raw, unit=None, status="VERIFIED"):
    return {"gold_condition_id": gid, "condition_type": ctype, "category": field, "field": field, "applicability_scope": None,
            "operator": op, "value": value, "value_type": "NUMBER" if isinstance(value, (int, float)) else "STRING", "unit": unit,
            "reference_date": None, "reference_date_type": "UNKNOWN", "raw_text": raw, "source_field": "condition_texts.eligibility.text",
            "evidence_reference": {"start_char": 0, "end_char": len(raw)}, "source_completeness": "PARTIAL", "decision_possible": True,
            "review_status": status, "review_comment": None, "matched_candidate_ids": []}


def ref(gid):
    return {"node_type": "CONDITION_REF", "condition_id": gid}


class GoldBridgeTests(unittest.TestCase):
    """합성 검수 정답(실제 검수 결과 아님)으로 정답 -> 요건·조건 -> 평가기 연결을 확인한다."""

    NID = "BIZINFO:TEST"

    def write(self, root, conds, roots=None):
        import json
        d = root / "development"
        d.mkdir(parents=True)
        row = {"notice_id": self.NID, "gold_conditions": conds, "missed_condition_candidates": [], "reviewer": "합성", "reviewed_at": "2026-11-26T00:00:00Z",
               "adjudication_status": "REVIEWED_COMPLETE", "source_field": "condition_texts.eligibility.text", "whole_notice_conditions_complete": False}
        (d / "reviewed_condition_gold.jsonl").write_text(json.dumps(row, ensure_ascii=False) + "\n", encoding="utf-8")
        logic = [{"notice_id": self.NID, "gold_logic_roots": roots}] if roots is not None else []
        (d / "reviewed_logic_gold.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in logic), encoding="utf-8")

    def notice(self, conds, roots=None):
        import tempfile
        from graphrag import gold_bridge
        with tempfile.TemporaryDirectory() as t:
            self.write(Path(t), conds, roots)
            g = gold_bridge.load(Path(t))
        n = {"notice_id": self.NID, "conditions": [], "text_requirements": "unparsed"}
        self.assertEqual(gold_bridge.attach([n], g), 1)
        return n

    def test_or_logic_and_partial_review_never_eligible(self):
        conds = [gold("GOLD:A", "ELIGIBILITY", "BUSINESS_AGE", "LT", 7, "업력 7년 미만", "YEAR"),
                 gold("GOLD:B", "ELIGIBILITY", "BUSINESS_LOCATION", "EQ", "대구", "대구")]
        n = self.notice(conds, [{"node_type": "LOGICAL_GROUP", "group_id": "g1", "operator": "OR", "children": [ref("GOLD:A"), ref("GOLD:B")],
                                 "review_status": "VERIFIED", "evidence": None}])
        self.assertEqual(n["text_requirements"], "partially_reviewed")
        r = evaluate_notice(n, Profile(business_age_years=10, region="REGION:2700000000"), RG)
        self.assertEqual(r["requirements"][0]["status"], SAT)  # 업력은 불충족이지만 대구라 OR 충족
        self.assertEqual(r["verdict"], NEEDS_CHECK)  # 발췌 검수라 ELIGIBLE을 풀지 않는다
        self.assertIn("REQ_UNPARSED", r["reasons"])

    def test_unsatisfied_gold_is_soft_and_exclusion_negates(self):
        n = self.notice([gold("GOLD:A", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3, "창업 3년 이내", "YEAR"),
                         gold("GOLD:X", "EXCLUSION", "BUSINESS_LOCATION", "EQ", "서울특별시", "서울특별시")])
        self.assertEqual(n["gold_requirements"][0]["logic_basis"], "assumed")  # 논리 검수 없음 -> AND 가정
        r = evaluate_notice(n, Profile(business_age_years=10, region=RG.find_by_name("성동구")[0]), RG)
        st = {c.cond_id: c.status for c in r["conditions"]}
        self.assertEqual(st, {"GOLD:A": UNSAT, "GOLD:X": UNSAT})  # 서울 소재 -> 제외 조건에 해당 -> 요건 불충족
        self.assertEqual(r["verdict"], NEEDS_CHECK)  # 검수 조건은 soft라 NOT_ELIGIBLE을 만들지 않는다
        self.assertIn("SOFT_CONDITION_UNSATISFIED", r["reasons"])

    def test_skips_unverified_preference_and_keeps_unsupported_unknown(self):
        n = self.notice([gold("GOLD:P", "PREFERENCE", "BUSINESS_TYPE", "EQ", "여성기업", "여성기업 우대"),
                         gold("GOLD:U", "ELIGIBILITY", "BUSINESS_AGE", "LT", 5, "5년 미만", "YEAR", status="NEEDS_REVIEW"),
                         gold("GOLD:R", "ELIGIBILITY", "REVENUE_FINANCIAL", "LT", 100, "매출 100억 미만", "억원"),
                         gold("GOLD:D", "ELIGIBILITY", "BUSINESS_LOCATION", "EQ", "동구", "동구")])
        ids = [c["cond_id"] for g in n["gold_requirements"] for c in g["conditions"]]
        self.assertEqual(ids, ["GOLD:R", "GOLD:D"])  # 우대·미검수는 옮기지 않는다
        r = evaluate_notice(n, Profile(region="REGION:2700000000"), RG)
        self.assertEqual({c.cond_id: c.status for c in r["conditions"]}, {"GOLD:R": UNK, "GOLD:D": UNK})  # 매출 규칙 없음, 동구는 모호

    def test_no_reviewed_gold_changes_nothing(self):
        from graphrag import gold_bridge
        self.assertEqual(gold_bridge.load(Path("does-not-exist")), {})


class ChunkTests(unittest.TestCase):
    def test_short_and_redaction_only_chunks_are_dropped(self):
        self.assertEqual(_chunk("N", "S", "x", "API", "창업교육"), [])
        self.assertEqual(_chunk("N", "S", "x", "API", "[REDACTED_CONTACT]" * 3), [])
        self.assertEqual(len(_chunk("N", "S", "x", "API", "창업 7년 이내 기업을 대상으로 사업화 자금을 지원합니다")), 1)


if __name__ == "__main__":
    unittest.main()
