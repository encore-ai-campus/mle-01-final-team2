"""E2 스키마 변경 비용 비교 도구 단위 시험(DB 접속 없음). 실행: python -m unittest tools.test_compare_schema_change -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphrag import compare_schema_change as E  # noqa: E402


class Fixture(unittest.TestCase):
    def test_changed_sql_gives_expected_answers_on_new_structures(self):
        for name in E.SCENARIOS:
            for c in E.check_fixture(name):
                self.assertTrue(c["ok"], (name, c))

    def test_old_queries_miss_nested_and_superseded(self):
        s2 = {c["query"]: c for c in E.check_fixture("S2")}
        self.assertEqual(s2["Q1"]["before_change"], [("N1",), ("N4",)])  # 그룹 아래 서울 조건(N2)을 놓친다
        s3 = {c["query"]: c for c in E.check_fixture("S3")}
        self.assertEqual(s3["Q1"]["before_change"], [("N1",), ("N4",)])  # 대신된 N1이 남는다


class LocalNeo4j(unittest.TestCase):
    def test_only_local_uri_is_accepted(self):
        self.assertEqual(E.local_only("bolt://localhost:7688"), "bolt://localhost:7688")
        self.assertEqual(E.local_only("neo4j://127.0.0.1:7687"), "neo4j://127.0.0.1:7687")
        with self.assertRaises(SystemExit):
            E.local_only("neo4j+s://abcd1234.databases.neo4j.io")

    def test_cypher_fixture_has_same_ids_as_sql_fixture(self):
        import re
        ids = lambda s: set(re.findall(r"'((?:N\d|R:|T:|KSIC:|D1|L1|A2)[^']*)'", s))  # noqa: E731
        sql = ids(E.FIXTURE) | {i for x in E.EXTRA.values() for i in ids(x)}
        cy = ids(E.CY_FIXTURE) | {i for x in E.CY_EXTRA.values() for i in ids(x)}
        self.assertEqual(sql, cy)

    def test_cypher_check_uses_given_runners(self):
        calls = []
        out = E.check_fixture_cypher("S3", calls.append, lambda q, **p: [("N4",)])
        self.assertEqual(calls[0], "MATCH (n) DETACH DELETE n")
        self.assertIn("SUPERSEDES", calls[1])
        self.assertTrue(all(c["ok"] for c in out))


class Cost(unittest.TestCase):
    def test_counts_and_criterion(self):
        c = {n: E.cost(sc) for n, sc in E.SCENARIOS.items()}
        # 그래프 적재 검증표: 관계 한 줄 + 범위 한 줄 수정 = +2/-1, 스키마(제약)는 그대로
        for n in c:
            self.assertEqual(c[n]["cypher"]["load"], {"added": 2, "removed": 1})
            self.assertEqual(c[n]["cypher"]["schema"], {"added": 0, "removed": 0})
        self.assertEqual(c["S2"]["sql_best"], "sql_view")
        self.assertTrue(c["S1"]["graph_less"] and c["S2"]["graph_less"])
        self.assertTrue(c["S3"]["tie"])
        self.assertGreaterEqual(sum(v["graph_less"] for v in c.values()), 2)

    def test_load_render_is_one_line_per_relation(self):
        sig, scopes = E.with_rel("X_REL", ("Concept", "Concept"), "meta")
        lines = E.render_graph_load(sig, scopes).splitlines()
        self.assertEqual(len(lines), len(sig) + len(scopes))
        self.assertIn("X_REL", scopes["meta"]["edges"])


if __name__ == "__main__":
    unittest.main()
