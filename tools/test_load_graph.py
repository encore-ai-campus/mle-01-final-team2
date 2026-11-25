"""적재 스크립트 단위 시험(DB 접속 없음). 실행: python -m unittest tools.test_load_graph -v"""
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import load_graph_neo4j as L  # noqa: E402

NODES = [
    {"label": "Notice", "notice_id": "N1", "title": "공고", "deadline": None, "is_open": True},
    {"label": "Organization", "org_id": "ORG:1", "name": "기관"},
    {"label": "SupportCategory", "category_id": "CAT:1", "name": "분야", "source_system": "BIZINFO"},
    {"label": "Concept", "concept_id": "REGION:1100000000", "scheme": "REGION", "name": "서울특별시", "level": "SIDO"},
    {"label": "Concept", "concept_id": "REGION:NATIONWIDE", "scheme": "REGION", "name": "전국", "level": "NATIONWIDE"},
    {"label": "Requirement", "req_id": "N1#R1", "kind": "ELIGIBILITY", "logic": "AND"},
    {"label": "Condition", "cond_id": "N1#C1", "attribute": "region", "operator": "WITHIN", "value": {"concept_id": "REGION:1100000000"}},
]
EDGES = [
    {"type": "ANNOUNCED_BY", "from": "N1", "to": "ORG:1", "source_field": "x"},
    {"type": "IN_SUPPORT_CATEGORY", "from": "N1", "to": "CAT:1"},
    {"type": "WITHIN", "from": "REGION:1100000000", "to": "REGION:NATIONWIDE", "basis": "MOIS"},
    {"type": "HAS_REQUIREMENT", "from": "N1", "to": "N1#R1", "evidence": "e", "source": "s"},
    {"type": "HAS_CONDITION", "from": "N1#R1", "to": "N1#C1", "evidence": "e", "source": "s"},
    {"type": "ABOUT", "from": "N1#C1", "to": "REGION:1100000000"},
]


class TestLoader(unittest.TestCase):
    def test_props_drop_none_and_stringify_maps(self):
        p = L.props(NODES[6], {"label", "cond_id"})
        self.assertEqual(p["value"], '{"concept_id": "REGION:1100000000"}')
        self.assertEqual(L.props(NODES[0], {"label", "notice_id"}), {"title": "공고", "is_open": True})  # deadline None은 속성을 만들지 않는다

    def test_valid_graph_has_no_errors(self):
        self.assertEqual(L.validate(NODES, EDGES), [])

    def test_validation_catches_problems(self):
        self.assertTrue(any("중복 노드" in e for e in L.validate(NODES + [NODES[0]], EDGES)))
        self.assertTrue(any("끝점이 없는" in e for e in L.validate(NODES, EDGES + [{"type": "WITHIN", "from": "X", "to": "REGION:1100000000"}])))
        self.assertTrue(any("시그니처 위반" in e for e in L.validate(NODES, EDGES + [{"type": "WITHIN", "from": "N1", "to": "ORG:1"}])))
        self.assertTrue(any("알 수 없는 레이블" in e for e in L.validate(NODES + [{"label": "Foo", "x": 1}], EDGES)))
        self.assertTrue(any("알 수 없는 관계" in e for e in L.validate(NODES, EDGES + [{"type": "LIKES", "from": "N1", "to": "ORG:1"}])))

    def test_stage_selection_keeps_requirements_out_of_meta(self):
        n, e = L.select(NODES, EDGES, "meta")
        self.assertEqual({x["label"] for x in n}, {"Notice", "Organization", "SupportCategory", "Concept"})
        self.assertEqual({x["type"] for x in e}, {"ANNOUNCED_BY", "IN_SUPPORT_CATEGORY", "WITHIN"})
        n, e = L.select(NODES, EDGES, "requirements")
        self.assertEqual({x["label"] for x in n}, {"Requirement", "Condition"})
        self.assertEqual({x["type"] for x in e}, {"HAS_REQUIREMENT", "HAS_CONDITION", "ABOUT"})

    def test_region_concepts_get_the_region_label_and_merge_by_key(self):
        stmts = dict((d.split()[1], c) for d, c, _ in L.node_statements(NODES))
        self.assertIn("MERGE (n:Concept:Region {concept_id: row.id})", stmts["Concept:Region"])
        self.assertIn("MERGE (n:Notice {notice_id: row.id})", stmts["Notice"])
        self.assertFalse(any("DELETE" in c.upper() for c in stmts.values()))

    def test_edge_statements_match_endpoints_by_key(self):
        pl = L.plan(NODES, EDGES, "requirements")  # ABOUT은 이미 적재된 Concept를 가리킨다
        about = [c for d, c, _ in pl["edge_statements"] if "ABOUT" in d][0]
        self.assertIn("MATCH (a:Condition {cond_id: row.from}) MATCH (b:Concept {concept_id: row.to})", about)
        self.assertIn("MERGE (a)-[r:ABOUT]->(b)", about)

    def test_constraints_only_for_stage_labels(self):
        meta = L.constraints_for({"Notice", "Concept"})
        self.assertEqual(len(meta), 2)
        self.assertTrue(all("CREATE CONSTRAINT" in c and "IF NOT EXISTS" in c for c in meta))

    def test_dry_run_writes_nothing_and_needs_no_database(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "nodes.jsonl").write_text("\n".join(json.dumps(n, ensure_ascii=False) for n in NODES) + "\n", encoding="utf-8")
            (d / "edges.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in EDGES) + "\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                code = L.main(["--graph-dir", t, "--stage", "all"])
            self.assertEqual(code, 0)
            self.assertIn("dry-run 끝. 아무것도 쓰지 않았다.", out.getvalue())
            self.assertIn("노드 7개", out.getvalue())

    def test_invalid_file_stops_before_any_database_access(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t)
            (d / "nodes.jsonl").write_text(json.dumps(NODES[0]) + "\n", encoding="utf-8")
            (d / "edges.jsonl").write_text(json.dumps({"type": "ANNOUNCED_BY", "from": "N1", "to": "NOPE"}) + "\n", encoding="utf-8")
            with redirect_stdout(io.StringIO()):
                self.assertEqual(L.main(["--graph-dir", t, "--apply", "--confirm-host", "x"]), 2)


if __name__ == "__main__":
    unittest.main()
