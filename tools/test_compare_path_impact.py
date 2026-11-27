"""E1 근거 경로·E3 법령 개정 영향 비교 도구 단위 시험(DB 접속 없음). 실행: python -m unittest tools.test_compare_path_impact -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphrag import compare_path_impact as P  # noqa: E402

# 작은 그래프: 공고 1건, 요건 1개, 조건 2개(지역, 신청자 유형).
# 지역: 강남구 → 서울(WITHIN). 신청자 유형: 1인 창조기업 IS_A 중소기업, 중소기업은 정의 → 조문 제2조·별표 1
NODES = [
    {"label": "Notice", "notice_id": "N1", "is_open": True},
    {"label": "Requirement", "req_id": "N1#R"},
    {"label": "Condition", "cond_id": "N1#C-region", "attribute": "region"},
    {"label": "Condition", "cond_id": "N1#C-type", "attribute": "applicant_type"},
    {"label": "Concept", "concept_id": "REGION:SEOUL", "name": "서울"},
    {"label": "Concept", "concept_id": "REGION:GANGNAM", "name": "강남구"},
    {"label": "Concept", "concept_id": "TYPE:SOLO", "name": "1인 창조기업"},
    {"label": "Concept", "concept_id": "TYPE:SME", "name": "중소기업"},
    {"label": "Definition", "def_id": "DEF:SME", "term": "중소기업"},
    {"label": "ExternalLaw", "law_id": "LAW:1", "name": "중소기업기본법"},
    {"label": "LawArticle", "article_id": "LAW:1:A2", "law_id": "LAW:1", "article_no": "2"},
    {"label": "LawAppendix", "appendix_id": "LAW:1:T1", "law_id": "LAW:1", "table_no": "1", "title": "규모 기준"},
]
EDGES = [
    {"from": "N1", "to": "N1#R", "type": "HAS_REQUIREMENT"},
    {"from": "N1#R", "to": "N1#C-region", "type": "HAS_CONDITION"},
    {"from": "N1#R", "to": "N1#C-type", "type": "HAS_CONDITION"},
    {"from": "N1#C-region", "to": "REGION:SEOUL", "type": "ABOUT"},
    {"from": "N1#C-type", "to": "TYPE:SOLO", "type": "ABOUT"},
    {"from": "REGION:GANGNAM", "to": "REGION:SEOUL", "type": "WITHIN"},
    {"from": "TYPE:SOLO", "to": "TYPE:SME", "type": "IS_A"},
    {"from": "TYPE:SME", "to": "DEF:SME", "type": "DEFINED_BY"},
    {"from": "DEF:SME", "to": "LAW:1:A2", "type": "CITES_LAW"},
    {"from": "DEF:SME", "to": "LAW:1:T1", "type": "CITES_LAW"},
]
BASIS = (("중소기업", "중소기업기본법", "[별표 1] 규모 기준"), ("중소기업", "중소기업기본법", "제2조"))
CARD = [("N1#C-region", "region", "서울", ("강남구 > 서울",), ()),
        ("N1#C-type", "applicant_type", "1인 창조기업", (), BASIS)]


class PathImpactTests(unittest.TestCase):
    def setUp(self):
        self.db = P.build_sql(NODES, EDGES)

    def test_e1_sql_card_has_region_path_and_law_basis(self):
        for q in (P.E1_SQL, P.E1_SQL_GENERIC):  # 종류별 테이블·통합 조항 테이블 모두 같은 카드
            rows = self.db.execute(q, {"nid": "N1", "u": "REGION:GANGNAM"}).fetchall()
            self.assertEqual(P.card_from_sql(rows), CARD)

    def test_e1_unreachable_region_has_no_path(self):
        rows = self.db.execute(P.E1_SQL, {"nid": "N1", "u": "TYPE:SME"}).fetchall()
        self.assertEqual(P.card_from_sql(rows)[0][3], ())

    def test_cypher_card_normalizes_to_same_shape(self):
        # Neo4j가 돌려주는 모양: 경로는 노드 이름 목록의 목록, 근거는 [용어, 법령, 조항] 목록
        rows = [("N1#C-type", "applicant_type", "1인 창조기업", [], [list(b) for b in reversed(BASIS)]),
                ("N1#C-region", "region", "서울", [["강남구", "서울"]], [])]
        self.assertEqual(P.card_from_cypher(rows), CARD)

    def test_e3_impact_by_scenario(self):
        q = P.E3
        # S0은 조문만 시작점이다. 별표에서 시작하면 종류별 SQL은 찾지 못하고, 통합 조항 SQL은 처음부터 찾는다
        self.assertEqual(self.db.execute(q["S0"]["sql_typed"], {"pid": "LAW:1:A2"}).fetchall(), [("N1",)])
        self.assertEqual(self.db.execute(q["S0"]["sql_typed"], {"pid": "LAW:1:T1"}).fetchall(), [])
        self.assertEqual(self.db.execute(q["S0"]["sql_generic"], {"pid": "LAW:1:T1"}).fetchall(), [("N1",)])
        for k in ("sql_typed", "sql_generic"):
            self.assertEqual(self.db.execute(q["S1"][k], {"pid": "LAW:1:T1"}).fetchall(), [("N1",)])

    def test_e3_scenarios_change_what_they_claim(self):
        self.assertIn("IS_A*0..3", P.E3["S2"]["cypher"])
        self.assertIn("sub.hops < 3", P.E3["S2"]["sql_typed"])
        self.assertIn("LawAppendix", P.E3["S1"]["cypher"])
        self.assertEqual(P.changed_lines(P.E3["S1"]["sql_typed"], P.E3["S2"]["sql_typed"]), {"added": 1, "removed": 1})
        self.assertEqual(P.changed_lines(P.E3["S0"]["sql_generic"], P.E3["S1"]["sql_generic"]), {"added": 0, "removed": 0})

    def test_code_size_counts_post_processing(self):
        s = P.code_size(P.E1_SQL, "sql", P.card_from_sql)
        self.assertGreater(s["post_lines"], 0)
        self.assertEqual(s["total_lines"], s["lines"] + s["post_lines"])

    def test_inputs_are_deterministic(self):
        self.assertEqual(P.e1_inputs(self.db), P.e1_inputs(self.db))
        self.assertEqual(P.e3_inputs(self.db), {"S0": ["LAW:1:A2"], "S1": ["LAW:1:A2", "LAW:1:T1"], "S2": ["LAW:1:A2", "LAW:1:T1"]})


if __name__ == "__main__":
    unittest.main()
