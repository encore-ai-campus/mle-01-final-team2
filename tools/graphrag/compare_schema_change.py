"""E2 스키마 변경 비용 비교 (그래프 스키마 정의서 §10.3 E2, BASELINE_SQL_그래프_비교측정결과 8절).

사전 등록 기준: 시나리오 3개 중 2개 이상에서 그래프 쪽 수정량이 적다. 지표는 DDL·적재·질의 수정 줄 수와 손댄 파일 수다.
  S1 새 계층 관계: 업종(KSIC) 상하위 SUBCLASS_OF + 업종 조건으로 공고 찾기(새 질의 Q5)
  S2 하위 조건: 조건 아래 조건(HAS_CHILD, 3단까지). 조건을 지나는 질의 Q0~Q4가 모두 영향을 받는다
  S3 정정 공고: 새 공고가 예전 공고를 대신한다(SUPERSEDES). 공고 목록을 돌려주는 Q1·Q4가 예전 공고를 빼야 한다

비교 대상(기준선은 compare_query_size.py와 같다)
- SQL: 정규화 스키마(DDL)와 강한 설계(계층 간선을 concept_edge 하나로). 적재 = 원천 → 테이블 대응(EXPORT, 테이블당 한 줄).
- 그래프: 유일 제약(schema.cypher)과 적재 검증표(sync_graph_neo4j.py의 SIGNATURE·SCOPES, 관계당 한 줄). 적재 문장은 레이블·
  관계 종류에 상관없이 같은 코드라 바뀌지 않는다. 대신 새 관계는 검증표에 올려야 적재된다(올리지 않으면 validate가 막는다).
- 질의: compare_query_size의 Q0~Q4를 시나리오에 맞게 고친다. 새 질의는 줄 전체가 더한 줄이다.
- 수정 줄 = 더한 줄 + 뺀 줄(difflib). 한 줄을 고치면 2다. 원천 추출(공고 → 노드·간선 파일)은 두 쪽이 같아 뺀다.

정확성 확인
- 합성 자료(SQLite): 바꾼 SQL 질의가 새 구조에서 기대한 답을 내는지, 예전 질의는 무엇을 놓치는지.
- 실제 자료(Aura, 읽기 전용): 새 구조가 아직 없는 지금 자료에서 바꾼 질의가 예전 질의와 같은 답을 내는지(뒤로 호환).
  SQL은 Aura에서 내려받은 같은 자료로 만든 SQLite에서 같은 검사를 한다.
- 합성 자료(로컬 Neo4j, --local-uri): 같은 합성 자료를 그래프로 넣고 바꾼 Cypher가 SQL과 같은 기대 답을 내는지.
  DB를 비우고 쓰므로 localhost만 받는다. 공유 Aura에는 쓰지 않는다.

사용: python tools/graphrag/compare_schema_change.py            (Aura 읽기 전용, .env의 NEO4J_*)
      python tools/graphrag/compare_schema_change.py --offline  (비용과 합성 자료 검사만, DB 접속 없음)
      python tools/graphrag/compare_schema_change.py --local-uri bolt://localhost:7688   (위에 더해 로컬 Neo4j 검사)
        로컬 Neo4j 예: docker run -d --rm --name e2-neo4j -p 127.0.0.1:7688:7687 -e NEO4J_AUTH=neo4j/e2-local-test neo4j:5.26-community
결과: data/eval/compare_schema_change.json
"""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import sync_graph_neo4j as L  # noqa: E402
from graphrag.compare_path_impact import changed_lines  # noqa: E402
from graphrag.compare_query_size import DDL, EXPORT, QUERIES, norm_rows  # noqa: E402

OUT = ROOT / "data" / "eval" / "compare_schema_change.json"
BASE_SQL = {q: v["sql"] for q, v in QUERIES.items()}
BASE_CY = {q: v["cypher"] for q, v in QUERIES.items()}
CONSTRAINTS = "\n".join(ln for ln in (ROOT / "docs" / "submission" / "ontology" / "schema.cypher").read_text(encoding="utf-8").splitlines()
                        if ln.startswith("CREATE CONSTRAINT"))


def sub(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def render_sql_load(export: dict) -> str:
    return "\n".join(f'"{t}": "{q}",' for t, q in export.items())


def render_graph_load(signature: dict, scopes: dict) -> str:
    sig = [f'"{t}": {sorted(v)},' for t, v in signature.items()]
    sc = [f'"{s}": {v["edges"]},' for s, v in scopes.items()]
    return "\n".join(sig + sc)


def with_rel(rel: str, ends: tuple[str, str], scope: str) -> tuple[dict, dict]:
    """검증표에 새 관계를 올린 SIGNATURE·SCOPES."""
    sig = {**L.SIGNATURE, rel: [ends]}
    scopes = {k: {**v, "edges": v["edges"] + ([rel] if k == scope else [])} for k, v in L.SCOPES.items()}
    return sig, scopes


# ----------------------------------------------------------------------------- S2 하위 조건: 요건 아래 조건 트리
TREE = """tree(req_id, cond_id, depth) AS (
  SELECT c.req_id, c.cond_id, 0 FROM condition c WHERE c.req_id IS NOT NULL
  UNION ALL
  SELECT tree.req_id, c.cond_id, tree.depth + 1
  FROM condition c JOIN tree ON c.parent_cond_id = tree.cond_id
  WHERE tree.depth < 3
)"""


def with_tree(sql: str) -> str:
    """조건 트리 CTE를 맨 앞에 붙인다. 이미 WITH RECURSIVE가 있으면 그 앞에 쉼표로 잇는다."""
    s = sql.strip()
    if s.startswith("WITH RECURSIVE "):
        return "WITH RECURSIVE " + TREE + ",\n" + s[len("WITH RECURSIVE "):]
    return "WITH RECURSIVE " + TREE + "\n" + s


DOWN = ("JOIN condition c ON c.req_id = r.req_id", "JOIN tree t ON t.req_id = r.req_id\nJOIN condition c ON c.cond_id = t.cond_id")
UP = ("JOIN requirement r ON r.req_id = c.req_id", "JOIN tree t ON t.cond_id = c.cond_id\nJOIN requirement r ON r.req_id = t.req_id")
S2_SQL = {
    "Q0": with_tree(sub(BASE_SQL["Q0"], *DOWN)),
    "Q1": with_tree(sub(BASE_SQL["Q1"], *UP)),
    "Q2": with_tree(sub(BASE_SQL["Q2"], *DOWN)),
    "Q3": with_tree(sub(BASE_SQL["Q3"], "JOIN condition c ON c.req_id = r.req_id AND c.attribute = 'region'",
                        "JOIN tree t ON t.req_id = r.req_id\nJOIN condition c ON c.cond_id = t.cond_id AND c.attribute = 'region'")),
    "Q4": with_tree(sub(BASE_SQL["Q4"], *UP)),
}
# 더 강한 SQL: 트리 CTE를 뷰 하나로 두고 질의는 조인 줄만 바꾼다
VIEW = "CREATE VIEW condition_tree AS\nWITH RECURSIVE " + TREE + "\nSELECT req_id, cond_id FROM tree;\n"
VDOWN = (DOWN[0], DOWN[1].replace("JOIN tree t", "JOIN condition_tree t"))
VUP = (UP[0], UP[1].replace("JOIN tree t", "JOIN condition_tree t"))
S2_SQL_VIEW = {
    "Q0": sub(BASE_SQL["Q0"], *VDOWN), "Q1": sub(BASE_SQL["Q1"], *VUP), "Q2": sub(BASE_SQL["Q2"], *VDOWN),
    "Q3": sub(BASE_SQL["Q3"], "JOIN condition c ON c.req_id = r.req_id AND c.attribute = 'region'",
              "JOIN condition_tree t ON t.req_id = r.req_id\nJOIN condition c ON c.cond_id = t.cond_id AND c.attribute = 'region'"),
    "Q4": sub(BASE_SQL["Q4"], *VUP),
}
CHILD = "-[:HAS_CHILD*0..3]->"
S2_CY = {
    "Q0": sub(BASE_CY["Q0"], "-[:HAS_CONDITION]->(c:Condition)", f"-[:HAS_CONDITION]->(:Condition){CHILD}(c:Condition)"),
    "Q1": sub(BASE_CY["Q1"], "(:Condition {attribute: 'region'})<-[:HAS_CONDITION]-",
              "(:Condition {attribute: 'region'})<-[:HAS_CHILD*0..3]-(:Condition)<-[:HAS_CONDITION]-"),
    "Q2": sub(BASE_CY["Q2"], "-[:HAS_CONDITION]->(c:Condition)", f"-[:HAS_CONDITION]->(:Condition){CHILD}(c:Condition)"),
    "Q3": sub(BASE_CY["Q3"], "-[:HAS_CONDITION]->(c:Condition {attribute: 'region'})",
              f"-[:HAS_CONDITION]->(:Condition){CHILD}(c:Condition {{attribute: 'region'}})"),
    "Q4": sub(BASE_CY["Q4"], "<-[:ABOUT]-(:Condition)<-[:HAS_CONDITION]-", "<-[:ABOUT]-(:Condition)<-[:HAS_CHILD*0..3]-(:Condition)<-[:HAS_CONDITION]-"),
}

# ----------------------------------------------------------------------------- S3 정정 공고: 대신된 공고 빼기
NOT_OLD_SQL = "\nWHERE r.notice_id NOT IN (SELECT old_id FROM notice_supersedes)"
NOT_OLD_CY = ("\nRETURN DISTINCT n.notice_id", "\nWHERE NOT EXISTS { (n)<-[:SUPERSEDES]-(:Notice) }\nRETURN DISTINCT n.notice_id")

# ----------------------------------------------------------------------------- S1 업종 계층: 새 질의
Q5_SQL = """
WITH RECURSIVE up(id, hops) AS (
  SELECT :k, 0
  UNION
  SELECT e.parent, up.hops + 1
  FROM concept_edge e JOIN up ON e.child = up.id
  WHERE e.rel = 'SUBCLASS_OF' AND up.hops < 4
)
SELECT DISTINCT r.notice_id
FROM up
JOIN condition_concept cc ON cc.concept_id = up.id
JOIN condition c ON c.cond_id = cc.cond_id AND c.attribute = 'industry'
JOIN requirement r ON r.req_id = c.req_id
"""
Q5_CY = """
MATCH (:Concept {concept_id: $k})-[:SUBCLASS_OF*0..4]->(:Concept)
      <-[:ABOUT]-(:Condition {attribute: 'industry'})<-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice)
RETURN DISTINCT n.notice_id
"""

_S1_SIG = with_rel("SUBCLASS_OF", ("Concept", "Concept"), "meta")
_S2_SIG = with_rel("HAS_CHILD", ("Condition", "Condition"), "requirements")
_S3_SIG = with_rel("SUPERSEDES", ("Notice", "Notice"), "meta")

SCENARIOS: dict[str, dict] = {
    "S1": {
        "title": "새 계층 관계: 업종 KSIC 상하위(SUBCLASS_OF)와 업종 조건 검색",
        "sql": {"ddl": DDL,  # concept_edge.rel이 문자열이라 테이블은 그대로다
                "load": {**EXPORT, "concept_edge": EXPORT["concept_edge"].replace("WITHIN|MEMBER_OF|IS_A", "WITHIN|MEMBER_OF|IS_A|SUBCLASS_OF")},
                "queries": {"Q5": Q5_SQL}},
        "cypher": {"schema": CONSTRAINTS, "signature": _S1_SIG[0], "scopes": _S1_SIG[1], "queries": {"Q5": Q5_CY}},
    },
    "S2": {
        "title": "하위 조건: 조건 아래 조건(HAS_CHILD, 3단까지)",
        "sql": {"ddl": sub(DDL, "CREATE TABLE condition(cond_id TEXT PRIMARY KEY, req_id TEXT REFERENCES requirement, attribute TEXT);",
                           "CREATE TABLE condition(cond_id TEXT PRIMARY KEY, req_id TEXT REFERENCES requirement, "
                           "parent_cond_id TEXT REFERENCES condition, attribute TEXT);").rstrip() + "\nCREATE INDEX cond_p ON condition(parent_cond_id);\n",
                "load": {**EXPORT, "condition": "MATCH (c:Condition) OPTIONAL MATCH (r:Requirement)-[:HAS_CONDITION]->(c) "
                                                "OPTIONAL MATCH (p:Condition)-[:HAS_CHILD]->(c) RETURN c.cond_id, r.req_id, p.cond_id, c.attribute"},
                "queries": S2_SQL},
        "sql_view": {"queries": S2_SQL_VIEW},  # ddl·load는 아래에서 sql 것에 뷰를 더해 채운다
        "cypher": {"schema": CONSTRAINTS, "signature": _S2_SIG[0], "scopes": _S2_SIG[1], "queries": S2_CY},
    },
    "S3": {
        "title": "정정 공고: 새 공고가 예전 공고를 대신함(SUPERSEDES)",
        "sql": {"ddl": DDL.rstrip() + "\nCREATE TABLE notice_supersedes(new_id TEXT REFERENCES notice, old_id TEXT REFERENCES notice);"
                                      "\nCREATE INDEX ns_o ON notice_supersedes(old_id);\n",
                "load": {**EXPORT, "notice_supersedes": "MATCH (a:Notice)-[:SUPERSEDES]->(b:Notice) RETURN a.notice_id, b.notice_id"},
                "queries": {q: BASE_SQL[q].rstrip() + NOT_OLD_SQL + "\n" for q in ("Q1", "Q4")}},
        "cypher": {"schema": CONSTRAINTS, "signature": _S3_SIG[0], "scopes": _S3_SIG[1],
                   "queries": {q: sub(BASE_CY[q], *NOT_OLD_CY) for q in ("Q1", "Q4")}},
    },
}

SCENARIOS["S2"]["sql_view"].update(ddl=SCENARIOS["S2"]["sql"]["ddl"] + VIEW, load=SCENARIOS["S2"]["sql"]["load"])


def add(a: dict, b: dict) -> dict:
    return {"added": a["added"] + b["added"], "removed": a["removed"] + b["removed"]}


def cost(sc: dict) -> dict:
    """시나리오 하나의 수정량. 산출물(파일)별 더한·뺀 줄, 손댄 파일 수, 합계.
    SQL 설계가 둘이면(sql_view) 줄 수가 적은 쪽과 비교한다."""
    zero = {"added": 0, "removed": 0}
    out = {}
    sides = [("sql", BASE_SQL), ("cypher", BASE_CY)] + ([("sql_view", BASE_SQL)] if "sql_view" in sc else [])
    for side, base_q in sides:
        s = sc[side]
        if side.startswith("sql"):
            parts = {"schema": changed_lines(DDL, s["ddl"]), "load": changed_lines(render_sql_load(EXPORT), render_sql_load(s["load"]))}
        else:
            parts = {"schema": changed_lines(CONSTRAINTS, s["schema"]),
                     "load": changed_lines(render_graph_load(L.SIGNATURE, L.SCOPES), render_graph_load(s["signature"], s["scopes"]))}
        q = zero
        per_query = {}
        for qid, text in s["queries"].items():
            per_query[qid] = changed_lines(base_q.get(qid, ""), text)
            q = add(q, per_query[qid])
        parts["queries"] = q
        total = sum(v["added"] + v["removed"] for v in parts.values())
        out[side] = {**parts, "per_query": per_query, "files_touched": sum(1 for v in parts.values() if v["added"] + v["removed"]),
                     "changed_lines": total, "schema_and_load_lines": total - q["added"] - q["removed"]}
    best = min((v["changed_lines"], k) for k, v in out.items() if k.startswith("sql"))
    out["sql_best"] = best[1]
    out["graph_less"] = out["cypher"]["changed_lines"] < best[0]
    out["tie"] = out["cypher"]["changed_lines"] == best[0]
    return out


# ----------------------------------------------------------------------------- 합성 자료(SQLite)
# 공고 N1(강남구, 1인 창조기업), N4(서울, 1인 창조기업), N5(업종 C10). S2: N2의 그룹 조건 아래 서울·1인 창조기업.
# S3: N4가 N1을 대신한다. S1: KSIC C1011 → C101 → C10 → C
FIXTURE = """
INSERT INTO notice VALUES ('N1'), ('N2'), ('N4'), ('N5');
INSERT INTO requirement VALUES ('N1#R', 'N1'), ('N2#R', 'N2'), ('N4#R', 'N4'), ('N5#R', 'N5');
INSERT INTO condition(cond_id, req_id, attribute) VALUES ('N1#C1', 'N1#R', 'region'), ('N1#C2', 'N1#R', 'applicant_type'),
  ('N4#C1', 'N4#R', 'region'), ('N4#C2', 'N4#R', 'applicant_type'), ('N5#C1', 'N5#R', 'industry');
INSERT INTO concept VALUES ('R:SEOUL', '서울'), ('R:GANGNAM', '강남구'), ('T:SOLO', '1인 창조기업'), ('T:SME', '중소기업'),
  ('KSIC:C', '제조업'), ('KSIC:C10', '식료품'), ('KSIC:C101', '도축·육류'), ('KSIC:C1011', '도축업');
INSERT INTO concept_edge VALUES ('R:GANGNAM', 'R:SEOUL', 'WITHIN'), ('T:SOLO', 'T:SME', 'IS_A');
INSERT INTO condition_concept VALUES ('N1#C1', 'R:GANGNAM'), ('N1#C2', 'T:SOLO'), ('N4#C1', 'R:SEOUL'), ('N4#C2', 'T:SOLO'),
  ('N5#C1', 'KSIC:C10');
INSERT INTO definition VALUES ('D1', '중소기업');
INSERT INTO concept_definition VALUES ('T:SME', 'D1');
INSERT INTO external_law VALUES ('L1', '중소기업기본법');
INSERT INTO law_article VALUES ('A2', 'L1', '제2조');
INSERT INTO definition_article VALUES ('D1', 'A2');
"""
EXTRA = {
    "S1": "INSERT INTO concept_edge VALUES ('KSIC:C1011', 'KSIC:C101', 'SUBCLASS_OF'), ('KSIC:C101', 'KSIC:C10', 'SUBCLASS_OF'), "
          "('KSIC:C10', 'KSIC:C', 'SUBCLASS_OF');",
    "S2": "INSERT INTO condition(cond_id, req_id, parent_cond_id, attribute) VALUES ('N2#G', 'N2#R', NULL, 'group'), "
          "('N2#C2a', NULL, 'N2#G', 'region'), ('N2#C2b', NULL, 'N2#G', 'applicant_type');\n"
          "INSERT INTO condition_concept VALUES ('N2#C2a', 'R:SEOUL'), ('N2#C2b', 'T:SOLO');",
    "S3": "INSERT INTO notice_supersedes VALUES ('N4', 'N1');",
}
# (질의, 입력, 바뀐 질의의 기대 답). 예전 질의의 답은 함께 기록해 무엇을 놓치는지 보인다
CHECKS = {
    "S1": [("Q5", {"k": "KSIC:C1011"}, {("N5",)}), ("Q5", {"k": "KSIC:C"}, set())],
    "S2": [("Q0", {"nid": "N2"}, {("N2#R", "N2#G", "group"), ("N2#R", "N2#C2a", "region"), ("N2#R", "N2#C2b", "applicant_type")}),
           ("Q1", {"u": "R:GANGNAM"}, {("N1",), ("N2",), ("N4",)}),
           ("Q2", {"nid": "N2"}, {("N2#C2b", "중소기업", "중소기업기본법", "제2조")}),
           ("Q3", {"nid": "N2", "u": "R:GANGNAM"}, {("N2#C2a", "강남구 > 서울")}),
           ("Q4", {"aid": "A2"}, {("N1",), ("N2",), ("N4",)})],
    "S3": [("Q1", {"u": "R:GANGNAM"}, {("N4",)}), ("Q4", {"aid": "A2"}, {("N4",)})],
}


def fixture_db(ddl: str, extra: str = "") -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.executescript(ddl + FIXTURE + extra)
    return db


def check_fixture(name: str) -> list[dict]:
    """바꾼 SQL이 새 구조에서 기대한 답을 내는지. 예전 질의(예전 스키마)의 답도 같이 적는다."""
    sc = SCENARIOS[name]
    new_db = fixture_db(sc["sql"]["ddl"], EXTRA[name])
    old_db = fixture_db(DDL, EXTRA[name] if name == "S1" else "")  # 예전 스키마에는 하위 조건·정정 관계를 넣을 곳이 없다
    out = []
    for qid, p, want in CHECKS[name]:
        got = norm_rows(new_db.execute(sc["sql"]["queries"][qid], p).fetchall())
        before = norm_rows(old_db.execute(BASE_SQL[qid], p).fetchall()) if qid in BASE_SQL else None
        row = {"query": qid, "input": p, "ok": got == want, "got": sorted(got), "before_change": None if before is None else sorted(before)}
        if "sql_view" in sc:
            view_db = fixture_db(sc["sql_view"]["ddl"], EXTRA[name])
            row["ok"] = row["ok"] and norm_rows(view_db.execute(sc["sql_view"]["queries"][qid], p).fetchall()) == want
        out.append(row)
    return out


# ----------------------------------------------------------------------------- 합성 자료(로컬 Neo4j)
# FIXTURE·EXTRA와 같은 자료를 그래프로. 바꾼 Cypher가 새 구조 위에서 맞는지 본다. 쓰기가 필요해 로컬 DB에서만 한다
CY_FIXTURE = """
CREATE (n1:Notice {notice_id: 'N1'}), (n2:Notice {notice_id: 'N2'}), (n4:Notice {notice_id: 'N4'}), (n5:Notice {notice_id: 'N5'}),
  (r1:Requirement {req_id: 'N1#R'}), (r2:Requirement {req_id: 'N2#R'}), (r4:Requirement {req_id: 'N4#R'}), (r5:Requirement {req_id: 'N5#R'}),
  (n1)-[:HAS_REQUIREMENT]->(r1), (n2)-[:HAS_REQUIREMENT]->(r2), (n4)-[:HAS_REQUIREMENT]->(r4), (n5)-[:HAS_REQUIREMENT]->(r5),
  (c11:Condition {cond_id: 'N1#C1', attribute: 'region'}), (c12:Condition {cond_id: 'N1#C2', attribute: 'applicant_type'}),
  (c41:Condition {cond_id: 'N4#C1', attribute: 'region'}), (c42:Condition {cond_id: 'N4#C2', attribute: 'applicant_type'}),
  (c51:Condition {cond_id: 'N5#C1', attribute: 'industry'}),
  (r1)-[:HAS_CONDITION]->(c11), (r1)-[:HAS_CONDITION]->(c12), (r4)-[:HAS_CONDITION]->(c41), (r4)-[:HAS_CONDITION]->(c42),
  (r5)-[:HAS_CONDITION]->(c51),
  (seoul:Concept {concept_id: 'R:SEOUL', name: '서울'}), (gangnam:Concept {concept_id: 'R:GANGNAM', name: '강남구'}),
  (solo:Concept {concept_id: 'T:SOLO', name: '1인 창조기업'}), (sme:Concept {concept_id: 'T:SME', name: '중소기업'}),
  (kc:Concept {concept_id: 'KSIC:C', name: '제조업'}), (k10:Concept {concept_id: 'KSIC:C10', name: '식료품'}),
  (k101:Concept {concept_id: 'KSIC:C101', name: '도축·육류'}), (k1011:Concept {concept_id: 'KSIC:C1011', name: '도축업'}),
  (gangnam)-[:WITHIN]->(seoul), (solo)-[:IS_A]->(sme),
  (c11)-[:ABOUT]->(gangnam), (c12)-[:ABOUT]->(solo), (c41)-[:ABOUT]->(seoul), (c42)-[:ABOUT]->(solo), (c51)-[:ABOUT]->(k10),
  (d1:Definition {def_id: 'D1', term: '중소기업'}), (l1:ExternalLaw {law_id: 'L1', name: '중소기업기본법'}),
  (a2:LawArticle {article_id: 'A2', article_no: '제2조'}),
  (sme)-[:DEFINED_BY]->(d1), (d1)-[:CITES_LAW]->(a2), (a2)-[:PART_OF]->(l1)
"""
CY_EXTRA = {
    "S1": "CREATE (k1011)-[:SUBCLASS_OF]->(k101), (k101)-[:SUBCLASS_OF]->(k10), (k10)-[:SUBCLASS_OF]->(kc)",
    "S2": "CREATE (g:Condition {cond_id: 'N2#G', attribute: 'group'}), (r2)-[:HAS_CONDITION]->(g),\n"
          "  (c2a:Condition {cond_id: 'N2#C2a', attribute: 'region'}), (c2b:Condition {cond_id: 'N2#C2b', attribute: 'applicant_type'}),\n"
          "  (g)-[:HAS_CHILD]->(c2a), (g)-[:HAS_CHILD]->(c2b), (c2a)-[:ABOUT]->(seoul), (c2b)-[:ABOUT]->(solo)",
    "S3": "CREATE (n4)-[:SUPERSEDES]->(n1)",
}


def local_only(uri: str) -> str:
    """합성 자료를 넣으려고 DB를 비우므로 이 컴퓨터의 DB만 받는다(공유 Aura를 지우지 않게)."""
    from urllib.parse import urlparse
    host = urlparse(uri).hostname
    if host not in ("localhost", "127.0.0.1", "::1"):
        raise SystemExit(f"--local-uri는 이 컴퓨터의 Neo4j만 받습니다: {host}")
    return uri


def check_fixture_cypher(name: str, write, read) -> list[dict]:
    """로컬 Neo4j를 비우고 합성 자료를 넣은 뒤 바꾼 Cypher가 기대한 답(SQL과 같은 CHECKS)을 내는지 본다.
    write(query)는 쓰기, read(query, **params) -> list[tuple]은 읽기."""
    sc = SCENARIOS[name]
    write("MATCH (n) DETACH DELETE n")
    write(CY_FIXTURE + CY_EXTRA[name])
    out = []
    for qid, p, want in CHECKS[name]:
        got = norm_rows(read(sc["cypher"]["queries"][qid], **p))
        before = norm_rows(read(BASE_CY[qid], **p)) if qid in BASE_CY else None
        out.append({"query": qid, "input": p, "ok": got == want, "got": sorted(got), "before_change": None if before is None else sorted(before)})
    return out


# ----------------------------------------------------------------------------- 실제 자료(뒤로 호환)
def export_db(read, ddl: str, export: dict) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.executescript(ddl)
    for table, cy in export.items():
        rows = read(cy)
        if rows:
            db.executemany(f"INSERT OR IGNORE INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)
    db.commit()
    return db


def real_inputs(read) -> dict:
    regions = [r[0] for r in read("MATCH (k:Region) WHERE k.level IN ['SIGUNGU','GU','SIDO'] RETURN k.concept_id ORDER BY k.concept_id")][::25]
    notices = [r[0] for r in read("MATCH (n:Notice)-[:HAS_REQUIREMENT]->()-[:HAS_CONDITION]->()-[:ABOUT]->()-[:IS_A*0..2]->()-[:DEFINED_BY]->() "
                                  "RETURN DISTINCT n.notice_id ORDER BY n.notice_id LIMIT 15")]
    pairs = read("MATCH (n:Notice)-[:HAS_REQUIREMENT]->()-[:HAS_CONDITION]->(c:Condition {attribute:'region'})-[:ABOUT]->(t:Concept) "
                 "MATCH (u:Region)-[:WITHIN*1..2]->(t) WHERE u.level IN ['SIGUNGU','GU'] "
                 "WITH n, head(collect(u.concept_id)) AS u RETURN n.notice_id, u ORDER BY n.notice_id LIMIT 15")
    arts = [r[0] for r in read("MATCH (:Definition)-[:CITES_LAW]->(a:LawArticle) RETURN DISTINCT a.article_id ORDER BY a.article_id")]
    return {"Q0": [{"nid": n} for n in notices[:8]], "Q1": [{"u": u} for u in regions], "Q2": [{"nid": n} for n in notices],
            "Q3": [{"nid": n, "u": u} for n, u in pairs], "Q4": [{"aid": a} for a in arts],
            "Q5": [{"k": "KSIC:C10"}, {"k": "KSIC:C1011"}]}


def regression(read) -> dict:
    """새 구조가 없는 지금 자료에서 바꾼 질의 = 예전 질의, 그리고 SQL = Cypher."""
    inputs = real_inputs(read)
    base_db = export_db(read, DDL, EXPORT)
    base_cy_cache: dict = {}
    out = {}
    for name, sc in SCENARIOS.items():
        new_db = export_db(read, sc["sql"]["ddl"], sc["sql"]["load"])
        view_db = export_db(read, sc["sql_view"]["ddl"], sc["sql_view"]["load"]) if "sql_view" in sc else None
        r = {"inputs": 0, "sql_changed_vs_before": 0, "cypher_changed_vs_before": 0, "sql_vs_cypher": 0, "result_rows": 0}
        for qid in sc["sql"]["queries"]:
            for p in inputs[qid]:
                s_new = norm_rows(new_db.execute(sc["sql"]["queries"][qid], p).fetchall())
                if "sql_view" in sc:
                    r["sql_changed_vs_before"] += s_new != norm_rows(view_db.execute(sc["sql_view"]["queries"][qid], p).fetchall())
                c_new = norm_rows(read(sc["cypher"]["queries"][qid], **p))
                if qid in BASE_SQL:
                    s_old = norm_rows(base_db.execute(BASE_SQL[qid], p).fetchall())
                    key = (qid, tuple(sorted(p.items())))
                    if key not in base_cy_cache:
                        base_cy_cache[key] = norm_rows(read(BASE_CY[qid], **p))
                    r["sql_changed_vs_before"] += s_new != s_old
                    r["cypher_changed_vs_before"] += c_new != base_cy_cache[key]
                r["sql_vs_cypher"] += s_new != c_new
                r["inputs"] += 1
                r["result_rows"] += len(s_new)
        out[name] = r
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="E2 스키마 변경 비용 비교")
    ap.add_argument("--offline", action="store_true", help="DB 없이 비용·합성 자료 검사만")
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--local-uri", help="바꾼 Cypher를 합성 자료로 시험할 로컬 Neo4j(예: bolt://localhost:7687). DB를 비운다")
    ap.add_argument("--local-auth", default="neo4j:e2-local-test", help="로컬 Neo4j 사용자:비밀번호(일회용 컨테이너)")
    args = ap.parse_args(argv)

    report: dict = {"criterion": "시나리오 3개 중 2개 이상에서 그래프 수정 줄 수가 적다", "scenarios": {}}
    for name, sc in SCENARIOS.items():
        report["scenarios"][name] = {"title": sc["title"], "cost": cost(sc), "fixture": check_fixture(name)}
    wins = sum(r["cost"]["graph_less"] for r in report["scenarios"].values())
    report["graph_less_in"] = wins
    report["criterion_met"] = wins >= 2
    report["fixture_all_ok"] = all(c["ok"] for r in report["scenarios"].values() for c in r["fixture"])

    if args.local_uri:
        from neo4j import GraphDatabase
        logging.getLogger("neo4j").setLevel(logging.ERROR)
        user, pw = args.local_auth.split(":", 1)
        with GraphDatabase.driver(local_only(args.local_uri), auth=(user, pw)) as drv, drv.session() as sess:
            def lw(query):
                sess.run(query).consume()

            def lr(query, **params):
                return [tuple(r.values()) for r in sess.run(query, **params)]
            version = lr("CALL dbms.components() YIELD versions RETURN versions[0]")[0][0]
            cy = {name: check_fixture_cypher(name, lw, lr) for name in SCENARIOS}
            lw("MATCH (n) DETACH DELETE n")
        report["fixture_cypher"] = {"neo4j": version, "all_ok": all(c["ok"] for v in cy.values() for c in v), "scenarios": cy}

    if not args.offline:
        from neo4j import READ_ACCESS
        logging.getLogger("neo4j").setLevel(logging.ERROR)  # 아직 없는 관계 타입 경고(HAS_CHILD 등)는 예상한 것
        driver, dbname, host = L.connect()
        with driver.session(database=dbname, default_access_mode=READ_ACCESS) as sess:
            def read(query, **params):
                return [tuple(r.values()) for r in sess.run(query, **params)]
            report["regression_on_aura"] = {"neo4j_host": host, **regression(read)}
        driver.close()

    report["code"] = {name: {**({"sql_view": {"view": VIEW.strip(), **{q: t.strip() for q, t in sc["sql_view"]["queries"].items()}}}
                                if "sql_view" in sc else {}),
                             "sql": {q: t.strip() for q, t in sc["sql"]["queries"].items()},
                             "cypher": {q: t.strip() for q, t in sc["cypher"]["queries"].items()}} for name, sc in SCENARIOS.items()}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("| 시나리오 | SQL 스키마 | SQL 적재 | SQL 질의 | SQL 합계(파일) | 그래프 스키마 | 그래프 적재 | 그래프 질의 | 그래프 합계(파일) |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    f = lambda d: f"+{d['added']}/-{d['removed']}"  # noqa: E731
    for name, r in report["scenarios"].items():
        s, c = r["cost"]["sql"], r["cost"]["cypher"]
        print(f"| {name} | {f(s['schema'])} | {f(s['load'])} | {f(s['queries'])} | {s['changed_lines']}({s['files_touched']}) | "
              f"{f(c['schema'])} | {f(c['load'])} | {f(c['queries'])} | {c['changed_lines']}({c['files_touched']}) |")
        if "sql_view" in r["cost"]:
            v = r["cost"]["sql_view"]
            print(f"| {name} SQL 뷰 | {f(v['schema'])} | {f(v['load'])} | {f(v['queries'])} | {v['changed_lines']}({v['files_touched']}) | | | | |")
    print(f"그래프가 적은 시나리오 {wins}/3 → 기준 {'충족' if report['criterion_met'] else '미충족'}. 합성 자료 검사 {'통과' if report['fixture_all_ok'] else '실패'}")
    if "regression_on_aura" in report:
        print("뒤로 호환(Aura):", {k: v for k, v in report["regression_on_aura"].items() if k != "neo4j_host"})
    print("저장:", args.out)
    if "fixture_cypher" in report:
        fc = report["fixture_cypher"]
        print(f"바꾼 Cypher 합성 자료 검사(로컬 Neo4j {fc['neo4j']}): {'통과' if fc['all_ok'] else '실패'}")
    ok = report["fixture_all_ok"] and report.get("fixture_cypher", {}).get("all_ok", True) and all(
        v["sql_changed_vs_before"] == v["cypher_changed_vs_before"] == v["sql_vs_cypher"] == 0
        for k, v in report.get("regression_on_aura", {}).items() if k != "neo4j_host")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
