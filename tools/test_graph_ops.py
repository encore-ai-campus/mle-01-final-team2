"""Aura 점검·부분 적재 도구 단위 시험(DB 접속 없음). 실행: python -m unittest tools.test_graph_ops -v"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_graph_neo4j as CHK  # noqa: E402
import load_graph_partial as P  # noqa: E402

NODES = [
    {"label": "Notice", "notice_id": "N1", "title": "공고"},
    {"label": "Requirement", "req_id": "N1#R1", "status": "structured_only"},
    {"label": "Requirement", "req_id": "N1#G1", "status": "reviewed_excerpt", "logic_tree": {"operator": "AND"}},
    {"label": "Condition", "cond_id": "N1#C1", "attribute": "region"},
    {"label": "Condition", "cond_id": "GOLD:1", "attribute": "region", "reviewed": True},
    {"label": "Concept", "concept_id": "REGION:1", "scheme": "REGION"},
    {"label": "ExternalLaw", "law_id": "LAW:1", "source_url": "u"},
    {"label": "LawArticle", "article_id": "LAW:1:A1"},
    {"label": "Definition", "def_id": "DEF:X"},
]
EDGES = [
    {"type": "HAS_REQUIREMENT", "from": "N1", "to": "N1#R1", "evidence": "e"},
    {"type": "HAS_REQUIREMENT", "from": "N1", "to": "N1#G1", "evidence": "e"},
    {"type": "HAS_CONDITION", "from": "N1#R1", "to": "N1#C1", "evidence": "e"},
    {"type": "HAS_CONDITION", "from": "N1#G1", "to": "GOLD:1", "evidence": "e"},
    {"type": "ABOUT", "from": "N1#C1", "to": "REGION:1"},
    {"type": "ABOUT", "from": "GOLD:1", "to": "REGION:1"},
    {"type": "PART_OF", "from": "LAW:1:A1", "to": "LAW:1"},
    {"type": "CITES_LAW", "from": "DEF:X", "to": "LAW:1:A1"},
]


def snap(**checks):
    base = {cid: (exp if isinstance(exp, int) else 0) for cid, _, _, exp in CHK.CHECKS}
    return {"nodes": 10, "relationships": 5, "labels": {"Notice": 1}, "relationship_types": {"ABOUT": 2}, "keys": {"Notice": {"missing": 0, "dup": 0}},
            "checks": {**base, **checks}, "paths": {"p": 21}}


class CheckTests(unittest.TestCase):
    def test_judge_zero_checks_fail_and_known_values_warn(self):
        self.assertEqual(CHK.judge(snap()), ([], []))
        fails, warns = CHK.judge(snap(V4=3, V17=5))
        self.assertEqual(len(fails), 1)
        self.assertIn("V4", fails[0])
        self.assertIn("V17", warns[0])
        bad = snap()
        bad["keys"]["Notice"] = {"missing": 0, "dup": 2}
        self.assertIn("V0", CHK.judge(bad)[0][0])

    def test_diff_lists_only_changes(self):
        a, b = snap(), snap(V17=1)
        b["labels"] = {"Notice": 1, "Definition": 2}
        b["nodes"] = 12
        out = CHK.diff(a, b)
        self.assertEqual(len(out), 3)
        self.assertTrue(any(x.startswith("nodes: 10 → 12 (+2)") for x in out))
        self.assertTrue(any("labels.Definition: None → 2" in x for x in out))
        self.assertEqual(CHK.diff(a, snap()), [])

    def test_key_query_rejects_bad_identifiers(self):
        self.assertIn("count(n.notice_id)", CHK.key_check_cypher("Notice", "notice_id"))
        with self.assertRaises(AssertionError):
            CHK.key_check_cypher("Notice) DETACH DELETE n //", "x")


class PartialLoadTests(unittest.TestCase):
    def test_select_gold_takes_only_reviewed_requirements(self):
        n, e = P.select_gold(NODES, EDGES)
        self.assertEqual({x.get("req_id") or x.get("cond_id") for x in n}, {"N1#G1", "GOLD:1"})
        self.assertEqual({(x["type"], x["to"]) for x in e}, {("HAS_REQUIREMENT", "N1#G1"), ("HAS_CONDITION", "GOLD:1"), ("ABOUT", "REGION:1")})

    def test_select_laws_and_ids(self):
        n, e = P.select_laws(NODES, EDGES)
        self.assertEqual({x["label"] for x in n}, {"ExternalLaw", "LawArticle", "Definition"})
        self.assertEqual({x["type"] for x in e}, {"PART_OF", "CITES_LAW"})
        n, e = P.select_ids(NODES, EDGES, r"^N1#C1$")
        self.assertEqual(len(n), 1)
        self.assertEqual({x["type"] for x in e}, {"HAS_CONDITION", "ABOUT"})

    def test_classify_new_changed_same_missing(self):
        nodes = [{"label": "Notice", "notice_id": "A", "title": "t"}, {"label": "Notice", "notice_id": "B", "title": "새"},
                 {"label": "Notice", "notice_id": "C", "title": "t", "meta": {"x": 1}}, {"label": "Definition", "def_id": "D", "rule_json": "{}", "_must_exist": True}]
        db = {("Notice", "B"): {"notice_id": "B", "title": "옛"}, ("Notice", "C"): {"notice_id": "C", "title": "t", "meta": '{"x": 1}'}}
        c = P.classify(nodes, db)
        self.assertEqual([x["notice_id"] for x in c["new"]], ["A"])
        self.assertEqual([(x["notice_id"], k) for x, k in c["changed"]], [("B", ["title"])])
        self.assertEqual([x["notice_id"] for x in c["same"]], ["C"])  # 맵은 JSON 문자열로 비교한다
        self.assertEqual([x["def_id"] for x in c["missing"]], ["D"])  # 속성 갱신 대상이 없으면 만들지 않는다

    def test_endpoint_and_label_problems(self):
        nodes = [{"label": "Condition", "cond_id": "GOLD:1"}]
        edges = [{"type": "ABOUT", "from": "GOLD:1", "to": "REGION:1"}, {"type": "ABOUT", "from": "GOLD:1", "to": "NOPE"},
                 {"type": "ABOUT", "from": "GOLD:1", "to": "N1"}]
        db_labels = {"REGION:1": ["Concept", "Region"], "N1": ["Notice"]}
        probs = P.endpoint_problems(nodes, edges, db_labels)
        self.assertEqual(len(probs), 2)
        self.assertTrue(probs[0].startswith("끝점 없음"))
        self.assertTrue(probs[1].startswith("시그니처 위반"))
        self.assertEqual(P.label_conflicts([{"label": "Concept", "concept_id": "N1"}], db_labels)[0][:3], "N1:")

    def test_statements_match_instead_of_merge_for_property_updates(self):
        rows = P.sme_rule_nodes(Path(__file__).resolve().parents[1] / "data" / "graph" / "definition_rules.json")
        self.assertEqual(rows[0]["def_id"], "DEF:중소기업")
        self.assertEqual(json.loads(rows[0]["rule_json"])["status"], "draft")
        st = P.statements(rows, [], {})
        self.assertTrue(st[0][1].startswith("UNWIND $rows AS row MATCH (n:Definition"))
        self.assertNotIn("_must_exist", st[0][2][0]["props"])
        st = P.statements([{"label": "Condition", "cond_id": "GOLD:1"}], [{"type": "ABOUT", "from": "GOLD:1", "to": "REGION:1"}], {"REGION:1": ["Concept", "Region"]})
        self.assertIn("MERGE (n:Condition", st[0][1])
        self.assertIn("MATCH (b:Concept {concept_id: row.to})", st[1][1])

    def test_merge_selection_combines_properties(self):
        n, e = P.merge_selection([([{"label": "Definition", "def_id": "D", "term": "x"}], []),
                                  ([{"label": "Definition", "def_id": "D", "rule_json": "{}"}], [EDGES[0], EDGES[0]])])
        self.assertEqual(n, [{"label": "Definition", "def_id": "D", "term": "x", "rule_json": "{}"}])
        self.assertEqual(len(e), 1)

    def test_dry_run_without_selection_needs_no_db(self):
        with tempfile.TemporaryDirectory() as t:
            for f in ("nodes.jsonl", "edges.jsonl"):
                (Path(t) / f).write_text("", encoding="utf-8")
            self.assertEqual(P.main(["--select", "gold", "--graph-dir", t]), 0)


if __name__ == "__main__":
    unittest.main()
