#!/usr/bin/env python3
"""그래프가 SQL보다 나을 수 있는 곳 실험: E1 근거 경로 설명, E3 법령 개정 영향(CQ-15).

가설과 성공 기준은 결과를 보기 전에 정했다(docs/ontology/SCHEMA_Neo4j_그래프스키마정의서_v0.1.md §6.3).
  E1 판정 카드의 "왜 충족/불충족인가"(지역 경로 + 정의 + 조문)를 SQL·Cypher로 각각 만든다.
     성공 기준: 모든 입력에서 카드가 같고, 질의 + 후처리 코드가 30% 이상 적다.
  E3 조문(또는 별표)이 바뀌었다고 가정하고 영향받는 공고 집합을 두 방식으로 구한다.
     성공 기준: 결과가 같고, 깊이를 늘릴 때 Cypher는 숫자 1개, SQL은 CTE 수정이 든다.
     시나리오 S0 조문만·IS_A ≤2 / S1 별표까지 / S2 IS_A ≤3. 바꾼 줄 수를 센다.

공정성
- 같은 그래프 파일(data/graph, Aura에 적재한 것과 같은 빌드)에서 SQL 테이블을 만들고, Cypher는 Neo4j에 묻는다.
- SQL은 그래프 라벨을 그대로 옮긴 "종류별 테이블" 설계(조문·별표 테이블이 따로)와, 조문·별표를 한 테이블에 모은
  "통합 조항 테이블" 설계 두 가지로 짠다. 후자가 SQL에 유리한 강한 설계다.
- 두 언어 모두 같은 서식(절 하나에 한 줄), 후처리는 같은 출력 형식(카드)을 만드는 파이썬 함수로 센다.
- 실행 시간은 재지 않는다(지연은 compare_neo4j.py).

사용: python tools/graphrag/compare_path_impact.py   (Neo4j 읽기 전용. .env의 NEO4J_* 또는 환경 변수)
결과: data/eval/compare_path_impact.json
"""
from __future__ import annotations

import argparse
import difflib
import inspect
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from graphrag.compare_query_size import metrics  # noqa: E402

GRAPH = ROOT / "data" / "graph"
OUT = ROOT / "data" / "eval" / "compare_path_impact.json"
SEED = 20261127
N_E1 = 120  # E1 입력 수(공고 × 사용자 지역)

# ----------------------------------------------------------------------------- SQL 테이블(그래프 파일에서)
DDL = """
CREATE TABLE notice(notice_id TEXT PRIMARY KEY, is_open INTEGER);
CREATE TABLE requirement(req_id TEXT PRIMARY KEY, notice_id TEXT);
CREATE TABLE condition(cond_id TEXT PRIMARY KEY, req_id TEXT, attribute TEXT);
CREATE TABLE concept(concept_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE concept_edge(child TEXT, parent TEXT, rel TEXT);
CREATE TABLE condition_concept(cond_id TEXT, concept_id TEXT);
CREATE TABLE definition(def_id TEXT PRIMARY KEY, term TEXT);
CREATE TABLE concept_definition(concept_id TEXT, def_id TEXT);
CREATE TABLE external_law(law_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE law_article(article_id TEXT PRIMARY KEY, law_id TEXT, article_no TEXT);
CREATE TABLE law_appendix(appendix_id TEXT PRIMARY KEY, law_id TEXT, table_no TEXT, title TEXT);
CREATE TABLE definition_article(def_id TEXT, article_id TEXT);
CREATE TABLE definition_appendix(def_id TEXT, appendix_id TEXT);
CREATE TABLE provision(provision_id TEXT PRIMARY KEY, law_id TEXT, label TEXT);
CREATE TABLE definition_provision(def_id TEXT, provision_id TEXT);
CREATE INDEX req_n ON requirement(notice_id); CREATE INDEX cond_r ON condition(req_id);
CREATE INDEX ce_c ON concept_edge(child); CREATE INDEX ce_p ON concept_edge(parent);
CREATE INDEX cc_c ON condition_concept(cond_id); CREATE INDEX cc_k ON condition_concept(concept_id);
"""


def jsonl(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()]


def article_label(no: str) -> str:
    return f"제{no}조"


def appendix_label(table_no: str, title: str) -> str:
    return f"[별표 {table_no}] {title}"


def build_sql(nodes: list[dict], edges: list[dict]) -> sqlite3.Connection:
    """그래프 노드·간선을 관계형 테이블로 옮긴다. 조문·별표는 종류별 테이블과 통합 조항 테이블 두 가지로 둔다."""
    db = sqlite3.connect(":memory:")
    db.executescript(DDL)
    ins = lambda t, row: db.execute(f"INSERT OR IGNORE INTO {t} VALUES ({','.join('?' * len(row))})", row)  # noqa: E731
    for n in nodes:
        lab = n["label"]
        if lab == "Notice":
            ins("notice", (n["notice_id"], int(bool(n.get("is_open")))))
        elif lab == "Condition":
            ins("condition", (n["cond_id"], None, n.get("attribute")))
        elif lab == "Concept":
            ins("concept", (n["concept_id"], n.get("name")))
        elif lab == "Definition":
            ins("definition", (n["def_id"], n.get("term")))
        elif lab == "ExternalLaw":
            ins("external_law", (n["law_id"], n.get("name")))
        elif lab == "LawArticle":
            ins("law_article", (n["article_id"], n["law_id"], n["article_no"]))
            ins("provision", (n["article_id"], n["law_id"], article_label(n["article_no"])))
        elif lab == "LawAppendix":
            ins("law_appendix", (n["appendix_id"], n["law_id"], n["table_no"], n["title"]))
            ins("provision", (n["appendix_id"], n["law_id"], appendix_label(n["table_no"], n["title"])))
    arts = {n["article_id"] for n in nodes if n["label"] == "LawArticle"}
    for e in edges:
        t, a, b = e["type"], e["from"], e["to"]
        if t == "HAS_REQUIREMENT":
            ins("requirement", (b, a))
        elif t == "HAS_CONDITION":
            db.execute("UPDATE condition SET req_id = ? WHERE cond_id = ?", (a, b))
        elif t in ("WITHIN", "MEMBER_OF", "IS_A"):
            ins("concept_edge", (a, b, t))
        elif t == "ABOUT":
            ins("condition_concept", (a, b))
        elif t == "DEFINED_BY":
            ins("concept_definition", (a, b))
        elif t == "CITES_LAW":
            ins("definition_article" if b in arts else "definition_appendix", (a, b))
            ins("definition_provision", (a, b))
    db.commit()
    return db


# ----------------------------------------------------------------------------- E1 판정 근거 카드
E1_SQL = """
WITH RECURSIVE up(id, hops, path) AS (
  SELECT k.concept_id, 0, k.name FROM concept k WHERE k.concept_id = :u
  UNION ALL
  SELECT e.parent, up.hops + 1, up.path || ' > ' || p.name
  FROM concept_edge e JOIN up ON e.child = up.id
  JOIN concept p ON p.concept_id = e.parent
  WHERE e.rel IN ('WITHIN', 'MEMBER_OF') AND up.hops < 3
),
sup(start, id, hops) AS (
  SELECT concept_id, concept_id, 0 FROM concept
  UNION
  SELECT sup.start, e.parent, sup.hops + 1
  FROM concept_edge e JOIN sup ON e.child = sup.id
  WHERE e.rel = 'IS_A' AND sup.hops < 2
),
basis(concept_id, term, law, provision) AS (
  SELECT sup.start, d.term, l.name, '제' || a.article_no || '조'
  FROM sup JOIN concept_definition kd ON kd.concept_id = sup.id
  JOIN definition d ON d.def_id = kd.def_id
  JOIN definition_article da ON da.def_id = d.def_id
  JOIN law_article a ON a.article_id = da.article_id
  JOIN external_law l ON l.law_id = a.law_id
  UNION
  SELECT sup.start, d.term, l.name, '[별표 ' || x.table_no || '] ' || x.title
  FROM sup JOIN concept_definition kd ON kd.concept_id = sup.id
  JOIN definition d ON d.def_id = kd.def_id
  JOIN definition_appendix dx ON dx.def_id = d.def_id
  JOIN law_appendix x ON x.appendix_id = dx.appendix_id
  JOIN external_law l ON l.law_id = x.law_id
)
SELECT c.cond_id, c.attribute, k.name, up.path, b.term, b.law, b.provision
FROM requirement r
JOIN condition c ON c.req_id = r.req_id
JOIN condition_concept cc ON cc.cond_id = c.cond_id
JOIN concept k ON k.concept_id = cc.concept_id
LEFT JOIN up ON up.id = k.concept_id AND c.attribute = 'region'
LEFT JOIN basis b ON b.concept_id = k.concept_id
WHERE r.notice_id = :nid
"""

# 강한 SQL 설계: 조문·별표를 통합 조항 테이블(provision, 표시 이름은 적재 때 만든다)에 모으면 근거 CTE가 짧아진다
_BASIS_TYPED = E1_SQL[E1_SQL.index("basis(concept_id"):E1_SQL.index("SELECT c.cond_id") - 1]
E1_SQL_GENERIC = E1_SQL.replace(_BASIS_TYPED, """basis(concept_id, term, law, provision) AS (
  SELECT sup.start, d.term, l.name, p.label
  FROM sup JOIN concept_definition kd ON kd.concept_id = sup.id
  JOIN definition d ON d.def_id = kd.def_id
  JOIN definition_provision dp ON dp.def_id = d.def_id
  JOIN provision p ON p.provision_id = dp.provision_id
  JOIN external_law l ON l.law_id = p.law_id
)""")
assert E1_SQL_GENERIC != E1_SQL

E1_CYPHER = """
MATCH (:Notice {notice_id: $nid})-[:HAS_REQUIREMENT]->(:Requirement)-[:HAS_CONDITION]->(c:Condition)-[:ABOUT]->(k:Concept)
OPTIONAL MATCH p = (:Concept {concept_id: $u})-[:WITHIN|MEMBER_OF*0..3]->(k) WHERE c.attribute = 'region'
OPTIONAL MATCH (k)-[:IS_A*0..2]->(:Concept)-[:DEFINED_BY]->(d:Definition)-[:CITES_LAW]->(x)-[:PART_OF]->(l:ExternalLaw)
RETURN c.cond_id, c.attribute, k.name, collect(DISTINCT [y IN nodes(p) | y.name]) AS paths,
       collect(DISTINCT CASE WHEN d IS NULL THEN null ELSE [d.term, l.name, coalesce('제' + x.article_no + '조', '[별표 ' + x.table_no + '] ' + x.title)] END) AS basis
"""


def card_from_sql(rows) -> list:
    """SQL 행(조건·개념마다 경로 × 근거로 펼쳐짐)을 조건·개념별 카드로 묶는다."""
    card = {}
    for cond, attr, concept, path, term, law, prov in rows:
        paths, basis = card.setdefault((cond, attr, concept), (set(), set()))
        if path:
            paths.add(path)
        if term:
            basis.add((term, law, prov))
    return sorted((*k, tuple(sorted(p)), tuple(sorted(b))) for k, (p, b) in card.items())


def card_from_cypher(rows) -> list:
    """Cypher 행(조건·개념마다 경로 목록과 근거 목록이 이미 모여 있음)을 같은 카드 형식으로 바꾼다."""
    return sorted((cond, attr, concept, tuple(sorted(" > ".join(p) for p in paths)), tuple(sorted(tuple(b) for b in basis)))
                  for cond, attr, concept, paths, basis in rows)


# ----------------------------------------------------------------------------- E3 법령 개정 영향(CQ-15)
# 같은 질문을 시나리오마다 다시 짠다. 바뀐 줄 수가 "변경 비용"이다.
E3 = {
    "S0": {  # 조문만, IS_A ≤2 (질의 코드량 비교 Q4와 같은 질문)
        "sql_typed": """
WITH RECURSIVE sub(id, hops) AS (
  SELECT kd.concept_id, 0
  FROM definition_article da JOIN concept_definition kd ON kd.def_id = da.def_id
  WHERE da.article_id = :pid
  UNION
  SELECT e.child, sub.hops + 1
  FROM concept_edge e JOIN sub ON e.parent = sub.id
  WHERE e.rel = 'IS_A' AND sub.hops < 2
)
SELECT DISTINCT r.notice_id
FROM sub
JOIN condition_concept cc ON cc.concept_id = sub.id
JOIN condition c ON c.cond_id = cc.cond_id
JOIN requirement r ON r.req_id = c.req_id
""",
        "sql_generic": """
WITH RECURSIVE sub(id, hops) AS (
  SELECT kd.concept_id, 0
  FROM definition_provision dp JOIN concept_definition kd ON kd.def_id = dp.def_id
  WHERE dp.provision_id = :pid
  UNION
  SELECT e.child, sub.hops + 1
  FROM concept_edge e JOIN sub ON e.parent = sub.id
  WHERE e.rel = 'IS_A' AND sub.hops < 2
)
SELECT DISTINCT r.notice_id
FROM sub
JOIN condition_concept cc ON cc.concept_id = sub.id
JOIN condition c ON c.cond_id = cc.cond_id
JOIN requirement r ON r.req_id = c.req_id
""",
        "cypher": """
MATCH (:LawArticle {article_id: $pid})<-[:CITES_LAW]-(:Definition)<-[:DEFINED_BY]-(:Concept)<-[:IS_A*0..2]-(:Concept)
      <-[:ABOUT]-(:Condition)<-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice)
RETURN DISTINCT n.notice_id
""",
    },
}
# S1: 별표(LawAppendix)도 바뀔 수 있다. 종류별 테이블 설계는 시작점을 하나 더 합쳐야 한다
E3["S1"] = {
    "sql_typed": E3["S0"]["sql_typed"].replace(
        """  WHERE da.article_id = :pid
""", """  WHERE da.article_id = :pid
  UNION
  SELECT kd.concept_id, 0
  FROM definition_appendix dx JOIN concept_definition kd ON kd.def_id = dx.def_id
  WHERE dx.appendix_id = :pid
"""),
    "sql_generic": E3["S0"]["sql_generic"],  # 통합 조항 테이블은 질의를 바꿀 필요가 없다(설계 단계에서 비용을 냈다)
    "cypher": E3["S0"]["cypher"].replace("MATCH (:LawArticle {article_id: $pid})<-[:CITES_LAW]-",
                                         "MATCH (x:LawArticle|LawAppendix)<-[:CITES_LAW]-").replace(
        "RETURN DISTINCT n.notice_id", "WHERE x.article_id = $pid OR x.appendix_id = $pid\nRETURN DISTINCT n.notice_id"),
}
# S2: 상위 개념을 한 단계 더(IS_A ≤3)
E3["S2"] = {k: v.replace("sub.hops < 2", "sub.hops < 3").replace("IS_A*0..2", "IS_A*0..3") for k, v in E3["S1"].items()}

for _s in ("S1", "S2"):  # 시나리오 문자열 치환이 실제로 일어났는지(조용히 같은 질의가 되지 않게)
    _prev = "S0" if _s == "S1" else "S1"
    assert E3[_s]["cypher"] != E3[_prev]["cypher"] and E3[_s]["sql_typed"] != E3[_prev]["sql_typed"], _s


def changed_lines(a: str, b: str) -> dict:
    """두 질의 사이에 더한 줄·뺀 줄 수. 한 줄을 고치면 added 1, removed 1이다."""
    diff = [ln for ln in difflib.unified_diff(a.strip().splitlines(), b.strip().splitlines(), lineterm="", n=0)
            if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
    return {"added": sum(ln[0] == "+" for ln in diff), "removed": sum(ln[0] == "-" for ln in diff)}


def code_size(query: str, lang: str, post) -> dict:
    """질의 지표 + 후처리 함수 줄 수(빈 줄·문서 문자열 제외)."""
    src = inspect.getsource(post).splitlines()
    body = [ln for ln in src[1:] if ln.strip() and not ln.strip().startswith(('"""', "#"))]
    m = metrics(query, lang)
    return {**m, "post_lines": len(body), "total_lines": m["lines"] + len(body)}


# ----------------------------------------------------------------------------- 입력
def e1_inputs(db: sqlite3.Connection, seed: int = SEED, n: int = N_E1) -> list[dict]:
    """모집 중 공고 중 지역 조건이나 정의가 달린 개념 조건이 있는 공고를 고르고, 사용자 지역을 무작위로 붙인다."""
    rng = random.Random(seed)
    region_n = [r[0] for r in db.execute("""SELECT DISTINCT r.notice_id FROM requirement r JOIN notice n ON n.notice_id = r.notice_id
        JOIN condition c ON c.req_id = r.req_id WHERE n.is_open = 1 AND c.attribute = 'region' ORDER BY 1""")]
    def_n = [r[0] for r in db.execute("""SELECT DISTINCT r.notice_id FROM requirement r JOIN notice n ON n.notice_id = r.notice_id
        JOIN condition c ON c.req_id = r.req_id JOIN condition_concept cc ON cc.cond_id = c.cond_id
        JOIN concept_definition kd ON kd.concept_id = cc.concept_id WHERE n.is_open = 1 ORDER BY 1""")]
    regions = [r[0] for r in db.execute("SELECT concept_id FROM concept WHERE concept_id LIKE 'REGION:%' AND concept_id <> 'REGION:NATIONWIDE' ORDER BY 1")]
    half = n // 2
    picks = rng.sample(region_n, min(half, len(region_n))) + rng.sample(def_n, min(n - half, len(def_n)))
    return [{"nid": nid, "u": rng.choice(regions)} for nid in sorted(set(picks))]


def e3_inputs(db: sqlite3.Connection) -> dict:
    arts = [r[0] for r in db.execute("SELECT DISTINCT article_id FROM definition_article ORDER BY 1")]
    apps = [r[0] for r in db.execute("SELECT DISTINCT appendix_id FROM definition_appendix ORDER BY 1")]
    return {"S0": arts, "S1": arts + apps, "S2": arts + apps}


# ----------------------------------------------------------------------------- 실행
def run(db: sqlite3.Connection, cypher_read) -> dict:
    """cypher_read(query, **params) -> list[tuple]. 테스트에서는 가짜 함수를 넘긴다."""
    open_ids = {r[0] for r in db.execute("SELECT notice_id FROM notice WHERE is_open = 1")}
    # E1
    inputs = e1_inputs(db)
    mism, mism_generic, examples, n_cards, n_paths, n_basis = 0, 0, [], 0, 0, 0
    for p in inputs:
        s = card_from_sql(db.execute(E1_SQL, p).fetchall())
        g = card_from_cypher(cypher_read(E1_CYPHER, **p))
        mism_generic += card_from_sql(db.execute(E1_SQL_GENERIC, p).fetchall()) != g
        n_cards += len(s)
        n_paths += sum(1 for x in s if x[3])
        n_basis += sum(1 for x in s if x[4])
        if s != g:
            mism += 1
            if len(examples) < 3:
                examples.append({"input": p, "only_sql": [x for x in s if x not in g][:2], "only_cypher": [x for x in g if x not in s][:2]})
    sql_size, cy_size = code_size(E1_SQL, "sql", card_from_sql), code_size(E1_CYPHER, "cypher", card_from_cypher)
    gen_size = code_size(E1_SQL_GENERIC, "sql", card_from_sql)
    red = lambda a, b, k: round(1 - b[k] / a[k], 3)  # noqa: E731
    e1 = {"inputs": len(inputs), "card_rows": n_cards, "rows_with_region_path": n_paths, "rows_with_law_basis": n_basis,
          "mismatched_inputs": {"sql_typed": mism, "sql_generic": mism_generic}, "mismatch_examples": examples,
          "size": {"sql_typed": sql_size, "sql_generic": gen_size, "cypher": cy_size},
          "cypher_reduction_vs_sql_typed": {"total_lines": red(sql_size, cy_size, "total_lines"), "tokens": red(sql_size, cy_size, "tokens")},
          "cypher_reduction_vs_sql_generic": {"total_lines": red(gen_size, cy_size, "total_lines"), "tokens": red(gen_size, cy_size, "tokens")},
          "example_card": card_from_cypher(cypher_read(E1_CYPHER, **next(p for p in inputs if any(x[3] or x[4] for x in card_from_sql(db.execute(E1_SQL, p).fetchall())))))[:4]}
    # E3
    e3 = {}
    for sc, pids in e3_inputs(db).items():
        q = E3[sc]
        res = {"inputs": len(pids), "mismatched_inputs": {"sql_typed": 0, "sql_generic": 0}, "impacted_notices": {}, "impacted_open_notices": {}}
        for pid in pids:
            g = {r[0] for r in cypher_read(q["cypher"], pid=pid)}
            for k in ("sql_typed", "sql_generic"):
                if {r[0] for r in db.execute(q[k], {"pid": pid})} != g:
                    res["mismatched_inputs"][k] += 1
            res["impacted_notices"][pid] = len(g)
            res["impacted_open_notices"][pid] = len(g & open_ids)
        res["size"] = {k: metrics(v, "cypher" if k == "cypher" else "sql") for k, v in q.items()}
        e3[sc] = res
    for sc, prev in (("S1", "S0"), ("S2", "S1")):
        e3[sc]["changed_lines_from_" + prev] = {k: changed_lines(E3[prev][k], E3[sc][k]) for k in E3[sc]}
    return {"e1": e1, "e3": e3}


def main(argv: list[str] | None = None) -> int:
    import sync_graph_neo4j as L
    from neo4j import READ_ACCESS

    ap = argparse.ArgumentParser(description="E1 근거 경로·E3 법령 개정 영향 비교(읽기 전용)")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args(argv)
    nodes, edges = jsonl(GRAPH / "nodes.jsonl"), jsonl(GRAPH / "edges.jsonl")
    db = build_sql(nodes, edges)
    driver, dbname, host = L.connect()
    with driver.session(database=dbname, default_access_mode=READ_ACCESS) as sess:
        def cypher_read(query, **params):
            return [tuple(r.values()) for r in sess.run(query, **params)]
        report = {"snapshot": {"graph_nodes": len(nodes), "graph_edges": len(edges), "neo4j_host": host, "seed": SEED}, **run(db, cypher_read)}
    driver.close()
    report["queries"] = {"E1": {"sql_typed": E1_SQL.strip(), "sql_generic": E1_SQL_GENERIC.strip(), "cypher": E1_CYPHER.strip()},
                         "E3": {sc: {k: v.strip() for k, v in q.items()} for sc, q in E3.items()}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    e1, e3 = report["e1"], report["e3"]
    print(f"E1 입력 {e1['inputs']}개, 카드 행 {e1['card_rows']}개, 불일치 {e1['mismatched_inputs']}")
    for k, v in e1["size"].items():
        print(f"   {k}: {v['total_lines']}줄(질의 {v['lines']} + 후처리 {v['post_lines']}), 토큰 {v['tokens']}")
    print(f"   Cypher 감소: 종류별 SQL 대비 {e1['cypher_reduction_vs_sql_typed']}, 통합 SQL 대비 {e1['cypher_reduction_vs_sql_generic']}")
    for sc, r in e3.items():
        ch = {k: v for k, v in r.items() if k.startswith("changed_lines")}
        print(f"E3 {sc}: 입력 {r['inputs']}개, 불일치 {r['mismatched_inputs']}, {ch}")
    print("저장:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
