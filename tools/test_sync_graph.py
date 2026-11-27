"""통합 적재 스크립트(sync_graph_neo4j) 단위 시험. DB에 접속하지 않는다.

실행
  python -m unittest tools.test_sync_graph -v          # 이 파일만
  python -m unittest tools.test_sync_graph.DiffTests   # 묶음 하나만
  CI(.github/workflows/tools-tests.yml)가 tools/test_*.py를 모두 돌린다.

묶음
  FileTests       파일 검증(중복·끝점 없음·시그니처 위반), 속성 변환, --with-rules
  DiffTests       파일과 DB 스냅숏 비교: 새로·바뀜·같음, DB에만 있는 속성, 지울 노드·관계, 검수 노드 보호, 레이블 충돌
  StatementTests  쓰기 문장의 순서(제약 → 노드 → 관계 → 삭제)와 Cypher 모양, --prune 없이는 DELETE가 없는지
  ReadDbTests     FakeSession(가짜 Neo4j 세션)으로 read_db가 diff_graph와 같은 모양을 만드는지, 키 없는 DB 노드에서 멈추는지
  CliTests        DB 없이 되는 명령행 경로의 종료 코드(--offline 0, 잘못된 파일 2, --apply와 --offline 동시 사용 오류)

실제 DB에 쓰는 동작은 여기서 보지 않는다. 로컬 일회용 Neo4j로 시험하는 법은 sync_graph_neo4j.py 설명 5-2에 있다.
"""
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import sync_graph_neo4j as G  # noqa: E402

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


def db_from(nodes, edges, extra_nodes=(), extra_edges=()):
    """파일 행으로 DB 스냅숏을 만든다(적재가 끝난 상태). extra는 DB에만 있는 것: (레이블, id, 속성), (타입, from, to, 시작 레이블, 끝 레이블)."""
    label_of = {G.node_id(n): n["label"] for n in nodes}
    snap = {"nodes": {}, "labels": {}, "edges": {}, "edge_labels": {}}
    for n in nodes:
        nid = G.node_id(n)
        snap["nodes"][(n["label"], nid)] = {G.KEY[n["label"]]: nid, **G.node_props(n)}
        snap["labels"][nid] = [n["label"]] + (["Region"] if n.get("scheme") == "REGION" else [])
    for label, nid, p in extra_nodes:
        snap["nodes"][(label, nid)] = {G.KEY[label]: nid, **p}
        snap["labels"][nid] = [label]
        label_of[nid] = label
    for e in edges:
        k = (e["type"], e["from"], e["to"])
        snap["edges"][k] = G.edge_props(e)
        snap["edge_labels"][k] = (label_of[e["from"]], label_of[e["to"]])
    for t, f, to, a, b in extra_edges:
        snap["edges"][(t, f, to)] = {}
        snap["edge_labels"][(t, f, to)] = (a, b)
    return snap


EMPTY = {"nodes": {}, "labels": {}, "edges": {}, "edge_labels": {}}


class FileTests(unittest.TestCase):
    def test_props_drop_none_private_and_stringify_maps(self):
        self.assertEqual(G.node_props(NODES[6])["value"], '{"concept_id": "REGION:1100000000"}')
        self.assertEqual(G.node_props(NODES[0]), {"title": "공고", "is_open": True})  # deadline None은 속성을 만들지 않는다
        self.assertEqual(G.props({"a": 1, "_x": 2}, set()), {"a": 1})

    def test_valid_graph_has_no_errors(self):
        self.assertEqual(G.validate(NODES, EDGES), [])

    def test_validation_catches_problems(self):
        def has(word, nodes, edges):
            return any(word in e for e in G.validate(nodes, edges))
        self.assertTrue(has("중복 노드", NODES + [NODES[0]], EDGES))
        self.assertTrue(has("중복 관계", NODES, EDGES + [EDGES[0]]))
        self.assertTrue(has("끝점이 없는", NODES, EDGES + [{"type": "WITHIN", "from": "X", "to": "REGION:1100000000"}]))
        self.assertTrue(has("시그니처 위반", NODES, EDGES + [{"type": "WITHIN", "from": "N1", "to": "ORG:1"}]))
        self.assertTrue(has("알 수 없는 레이블", NODES + [{"label": "Foo", "x": 1}], EDGES))
        self.assertTrue(has("알 수 없는 관계", NODES, EDGES + [{"type": "LIKES", "from": "N1", "to": "ORG:1"}]))
        self.assertTrue(has("시그니처 위반", [{"label": "Definition", "def_id": "D"}, {"label": "ExternalLaw", "law_id": "L"}],
                            [{"type": "PART_OF", "from": "D", "to": "L"}]))

    def test_scope_keeps_labels_and_types_apart(self):
        n, e = G.in_scope(NODES, EDGES, ["meta"])
        self.assertEqual({x["label"] for x in n}, {"Notice", "Organization", "SupportCategory", "Concept"})
        self.assertEqual({x["type"] for x in e}, {"ANNOUNCED_BY", "IN_SUPPORT_CATEGORY", "WITHIN"})
        n, e = G.in_scope(NODES, EDGES, ["requirements"])
        self.assertEqual({x["type"] for x in e}, {"HAS_REQUIREMENT", "HAS_CONDITION", "ABOUT"})

    def test_rules_attach_to_existing_definitions_only(self):
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "r.json"
            p.write_text(json.dumps({"DEF:a": {"rule_id": "R1", "status": "draft", "needs_review": True}, "DEF:없음": {"rule_id": "R2", "status": "draft", "needs_review": True}}),
                         encoding="utf-8")
            nodes, missing = G.with_rules([{"label": "Definition", "def_id": "DEF:a"}], p)
        self.assertEqual(json.loads(nodes[0]["rule_json"])["rule_id"], "R1")
        self.assertEqual(missing, ["판정 기준의 정의가 파일에 없음: DEF:없음"])

    def test_constraints_come_from_schema_cypher(self):
        cs = G.constraints_for({"Notice", "Concept"})
        self.assertEqual(len(cs), 2)
        self.assertTrue(all(c.startswith("CREATE CONSTRAINT") and "IF NOT EXISTS" in c for c in cs))
        self.assertEqual(len(G.constraints_for(set(G.KEY))), 13)


class DiffTests(unittest.TestCase):
    def test_empty_db_means_everything_is_new(self):
        d = G.diff_graph(NODES, EDGES, EMPTY)
        s = G.summary(d)
        self.assertEqual((s["nodes_new"], s["edges_new"], s["nodes_same"]), (7, 6, 0))
        self.assertEqual(G.delete_count(d), 0)

    def test_same_db_is_synced(self):
        d = G.diff_graph(NODES, EDGES, db_from(NODES, EDGES))
        self.assertTrue(G.is_synced(d, prune=True))
        self.assertEqual(G.summary(d)["nodes_same"], 7)

    def test_changed_properties_and_extra_db_properties(self):
        db = db_from(NODES, EDGES)
        db["nodes"][("Notice", "N1")]["title"] = "옛 제목"
        db["nodes"][("Notice", "N1")]["old_field"] = 1
        db["edges"][("WITHIN", "REGION:1100000000", "REGION:NATIONWIDE")]["basis"] = "옛"
        d = G.diff_graph(NODES, EDGES, db)
        s = G.summary(d)
        self.assertEqual([(G.node_id(n), ks) for n, ks in d["nodes"]["changed"]], [("N1", ["title"])])
        self.assertEqual(s["edges_changed"], 1)
        self.assertEqual(s["extra_props_in_db"], {"Notice.old_field": 1})  # 지우지 않고 보고만 한다

    def test_stale_requirements_are_deleted_with_their_edges(self):
        # C-6처럼 파일에서 빠진 요건·조건: 노드는 지우고, 그 노드에 붙은 관계는 DETACH DELETE로 함께 없어진다
        db = db_from(NODES, EDGES,
                     extra_nodes=[("Requirement", "N1#R2", {}), ("Condition", "N1#C2", {})],
                     extra_edges=[("HAS_REQUIREMENT", "N1", "N1#R2", "Notice", "Requirement"),
                                  ("HAS_CONDITION", "N1#R2", "N1#C2", "Requirement", "Condition"),
                                  ("ABOUT", "N1#C2", "REGION:1100000000", "Condition", "Concept"),
                                  ("ABOUT", "N1#C1", "REGION:NATIONWIDE", "Condition", "Concept")])
        d = G.diff_graph(NODES, EDGES, db)
        self.assertEqual(d["stale_nodes"], [("Condition", "N1#C2"), ("Requirement", "N1#R2")])
        self.assertEqual(d["detached_edges"], 3)
        self.assertEqual(d["stale_edges"], [("ABOUT", "N1#C1", "REGION:NATIONWIDE")])  # 남는 조건에서 나가는 옛 ABOUT은 따로 지운다
        self.assertEqual(G.delete_count(d), 6)
        self.assertFalse(G.is_synced(d, prune=True))
        self.assertTrue(G.is_synced(d, prune=False))

    def test_reviewed_and_other_labels_are_not_deleted(self):
        db = db_from(NODES, EDGES, extra_nodes=[("Requirement", "GOLD:R", {"status": "reviewed_excerpt"}), ("Condition", "GOLD:C", {"reviewed": True}),
                                                ("Concept", "APPLICANT_TYPE:옛", {"scheme": "APPLICANT_TYPE"})],
                     extra_edges=[("HAS_REQUIREMENT", "N1", "GOLD:R", "Notice", "Requirement")])
        d = G.diff_graph(NODES, EDGES, db)
        self.assertEqual(d["stale_nodes"], [])
        self.assertEqual((d["stale_edges"], d["kept_edges"]), ([], 1))  # 검수 요건에 붙은 관계도 지우지 않는다(고아 방지)
        self.assertEqual(sorted(d["protected"]), [("Condition", "GOLD:C"), ("Requirement", "GOLD:R")])
        self.assertEqual(d["kept_stale_nodes"], [("Concept", "APPLICANT_TYPE:옛")])
        d = G.diff_graph(NODES, EDGES, db, prune_labels=["Concept"])
        self.assertEqual(d["stale_nodes"], [("Concept", "APPLICANT_TYPE:옛")])

    def test_label_conflict_is_reported(self):
        db = db_from(NODES, EDGES)
        db["labels"]["N1#C1"] = ["Requirement"]
        self.assertTrue(G.diff_graph(NODES, EDGES, db)["conflicts"][0].startswith("N1#C1:"))


class StatementTests(unittest.TestCase):
    def test_write_order_and_cypher(self):
        db = db_from(NODES, EDGES, extra_nodes=[("Condition", "N1#C2", {})],
                     extra_edges=[("ABOUT", "N1#C1", "REGION:NATIONWIDE", "Condition", "Concept")])
        db["nodes"][("Notice", "N1")]["title"] = "옛"
        d = G.diff_graph(NODES, EDGES, db)
        plan = G.write_plan(d, NODES, db, prune=True, scope_labels=set(G.KEY))
        descs = [x[0] for x in plan]
        kinds = [("제약" if x == "제약" else "삭제" if "삭제" in x else "관계" if x.startswith("관계") else "노드") for x in descs]
        self.assertEqual(kinds, sorted(kinds, key=["제약", "노드", "관계", "삭제"].index))  # 제약 → 노드 → 관계 → 삭제
        cy = {d_: c for d_, c, _ in plan}
        self.assertIn("MERGE (n:Notice {notice_id: row.id}) SET n += row.props", cy["노드 Notice 1개"])
        self.assertIn("MATCH (a:Condition {cond_id: row.from})-[r:ABOUT]->(b:Concept {concept_id: row.to}) DELETE r", cy["관계 삭제 ABOUT (Condition->Concept) 1개"])
        self.assertIn("MATCH (n:Condition {cond_id: row.id}) DETACH DELETE n", cy["노드 삭제 Condition 1개"])
        self.assertFalse(any("삭제" in x for x in [p[0] for p in G.write_plan(d, NODES, db, prune=False, scope_labels=set())]))

    def test_new_graph_merges_region_label_and_matches_endpoints(self):
        d = G.diff_graph(NODES, EDGES, EMPTY)
        plan = G.write_plan(d, NODES, EMPTY, prune=False, scope_labels=set())
        cy = " ".join(c for _, c, _ in plan)
        self.assertIn("MERGE (n:Concept:Region {concept_id: row.id})", cy)
        self.assertIn("MATCH (a:Condition {cond_id: row.from}) MATCH (b:Concept {concept_id: row.to}) MERGE (a)-[r:ABOUT]->(b)", cy)
        self.assertNotIn("DELETE", cy.upper())


class FakeSession:
    """read_db가 보내는 세 종류의 읽기 쿼리에 답하는 가짜 세션."""

    def __init__(self, snap):
        self.snap = snap

    def run(self, q, **_):
        m = re.match(r"MATCH \(n:(\w+)\) RETURN n\.(\w+) AS i", q)
        if m:
            return [{"i": i, "p": p, "ls": self.snap["labels"][i]} for (label, i), p in self.snap["nodes"].items() if label == m.group(1)]
        m = re.match(r"MATCH \(a:(\w+)\)-\[r:(\w+)\]->\(b:(\w+)\)", q)
        if m:
            a, t, b = m.groups()
            return [{"f": f, "t": to, "p": p} for (tt, f, to), p in self.snap["edges"].items() if tt == t and self.snap["edge_labels"][(tt, f, to)] == (a, b)]
        m = re.match(r"MATCH \(\)-\[r:(\w+)\]->\(\) RETURN count", q)
        n = sum(1 for (tt, _, _) in self.snap["edges"] if tt == m.group(1))
        return type("R", (), {"single": lambda self_: {"c": n}})()


class ReadDbTests(unittest.TestCase):
    def test_keyless_db_node_stops_instead_of_crashing(self):
        # 키 속성 이름이 틀린 노드(키 없음)는 비교 중 정렬 오류를 내지 않고 충돌로 보고해 쓰기를 막는다
        class S(FakeSession):
            def run(self, q, **kw):
                rows = super().run(q, **kw)
                if q.startswith("MATCH (n:Requirement)"):
                    rows = list(rows) + [{"i": None, "p": {"requirement_id": "X"}, "ls": ["Requirement"]}] * 2
                return rows
        got = G.read_db(S(db_from(NODES, EDGES)), list(G.SCOPES))
        self.assertEqual(got["bad_keys"], {"Requirement": 2})
        d = G.diff_graph(NODES, EDGES, got)
        self.assertIn("Requirement 노드 2개", d["conflicts"][0])

    def test_read_db_round_trip_matches_diff(self):
        snap = db_from(NODES, EDGES, extra_edges=[("ABOUT", "N1#C1", "REGION:NATIONWIDE", "Condition", "Concept")])
        got = G.read_db(FakeSession(snap), list(G.SCOPES))
        self.assertEqual(set(got["nodes"]), set(snap["nodes"]))
        self.assertEqual(got["labels"]["REGION:1100000000"], ["Concept", "Region"])
        self.assertEqual(got["edge_labels"][("ABOUT", "N1#C1", "REGION:NATIONWIDE")], ("Condition", "Concept"))
        self.assertEqual(got["off_signature"], {})
        d = G.diff_graph(NODES, EDGES, got)
        self.assertEqual(d["stale_edges"], [("ABOUT", "N1#C1", "REGION:NATIONWIDE")])


class CliTests(unittest.TestCase):
    def write(self, t, nodes, edges):
        (Path(t) / "nodes.jsonl").write_text("\n".join(json.dumps(n, ensure_ascii=False) for n in nodes) + "\n", encoding="utf-8")
        (Path(t) / "edges.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in edges) + "\n", encoding="utf-8")

    def test_offline_needs_no_database(self):
        with tempfile.TemporaryDirectory() as t:
            self.write(t, NODES, EDGES)
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(G.main(["--graph-dir", t, "--offline"]), 0)
            self.assertIn("오프라인 확인 끝", out.getvalue())
            self.assertIn("노드 7", out.getvalue())

    def test_invalid_file_stops_before_any_database_access(self):
        with tempfile.TemporaryDirectory() as t:
            self.write(t, NODES[:1], [{"type": "ANNOUNCED_BY", "from": "N1", "to": "NOPE"}])
            with redirect_stdout(io.StringIO()):
                self.assertEqual(G.main(["--graph-dir", t, "--apply", "--confirm-host", "x"]), 2)

    def test_apply_and_offline_conflict(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            G.main(["--offline", "--apply"])


if __name__ == "__main__":
    unittest.main()
