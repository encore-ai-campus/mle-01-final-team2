"""SQL 대비 Cypher 질의 코드량 비교 (스키마 정의서 §9, BASELINE_SQL_그래프_비교측정결과 §4.2).

Neo4j Aura에 적재된 그래프를 **읽기 전용**으로 내려받아, 같은 내용을 정규화한 관계형 테이블(SQLite, 메모리)에 넣는다.
같은 질문을 SQL과 Cypher로 한 번씩 짜서
  1) 여러 입력에서 결과가 같은지 확인하고(다르면 코드량 비교는 의미가 없다),
  2) 줄 수·토큰 수·조인(관계 hop) 수·재귀 CTE 수를 센다.

공정성 원칙
- SQL 쪽은 계층 간선을 테이블 하나(concept_edge: child, parent, rel)로 둔 "강한" 설계를 쓴다. 관계마다 테이블을 따로 두면 SQL이 더 길어진다.
- 공고→조건을 미리 펼친 테이블이나 폐쇄 테이블(사전 계산)은 쓰지 않는다. 그래프와 같은 정보만 가진 정규화 스키마다.
- 두 언어 모두 같은 서식 규칙(절 하나에 한 줄)으로 쓴다. 서식에 덜 흔들리게 토큰 수도 함께 본다.
- 코드가 짧다는 것은 정확도·속도의 우위가 아니다. 결과 해석은 문서에 따로 적는다.

사용: python tools/graphrag/compare_query_size.py   (.env의 NEO4J_* 필요, 쓰기 없음)
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

OUT = REPO / "data" / "eval" / "query_size_compare.json"

DDL = """
CREATE TABLE notice(notice_id TEXT PRIMARY KEY);
CREATE TABLE requirement(req_id TEXT PRIMARY KEY, notice_id TEXT REFERENCES notice);
CREATE TABLE condition(cond_id TEXT PRIMARY KEY, req_id TEXT REFERENCES requirement, attribute TEXT);
CREATE TABLE concept(concept_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE concept_edge(child TEXT REFERENCES concept, parent TEXT REFERENCES concept, rel TEXT);
CREATE TABLE condition_concept(cond_id TEXT REFERENCES condition, concept_id TEXT REFERENCES concept);
CREATE TABLE definition(def_id TEXT PRIMARY KEY, term TEXT);
CREATE TABLE concept_definition(concept_id TEXT REFERENCES concept, def_id TEXT REFERENCES definition);
CREATE TABLE external_law(law_id TEXT PRIMARY KEY, name TEXT);
CREATE TABLE law_article(article_id TEXT PRIMARY KEY, law_id TEXT REFERENCES external_law, article_no TEXT);
CREATE TABLE definition_article(def_id TEXT REFERENCES definition, article_id TEXT REFERENCES law_article);
CREATE INDEX req_n ON requirement(notice_id); CREATE INDEX cond_r ON condition(req_id);
CREATE INDEX ce_c ON concept_edge(child); CREATE INDEX ce_p ON concept_edge(parent);
CREATE INDEX cc_c ON condition_concept(cond_id); CREATE INDEX cc_k ON condition_concept(concept_id);
"""

EXPORT = {
    "notice": "MATCH (n:Notice) RETURN n.notice_id",
    "requirement": "MATCH (n:Notice)-[:HAS_REQUIREMENT]->(r:Requirement) RETURN r.req_id, n.notice_id",
    "condition": "MATCH (r:Requirement)-[:HAS_CONDITION]->(c:Condition) RETURN c.cond_id, r.req_id, c.attribute",
    "concept": "MATCH (k:Concept) RETURN k.concept_id, k.name",
    "concept_edge": "MATCH (a:Concept)-[x:WITHIN|MEMBER_OF|IS_A]->(b:Concept) RETURN a.concept_id, b.concept_id, type(x)",
    "condition_concept": "MATCH (c:Condition)-[:ABOUT]->(k:Concept) RETURN c.cond_id, k.concept_id",
    "definition": "MATCH (d:Definition) RETURN d.def_id, d.term",
    "concept_definition": "MATCH (k:Concept)-[:DEFINED_BY]->(d:Definition) RETURN k.concept_id, d.def_id",
    "external_law": "MATCH (l:ExternalLaw) RETURN l.law_id, l.name",
    "law_article": "MATCH (a:LawArticle)-[:PART_OF]->(l:ExternalLaw) RETURN a.article_id, l.law_id, a.article_no",
    "definition_article": "MATCH (d:Definition)-[:CITES_LAW]->(a:LawArticle) RETURN d.def_id, a.article_id",
}

# 질문 id: (설명, 관련 CQ·에이전트 노드, SQL, Cypher, 결과 정규화 함수 이름)
QUERIES: dict[str, dict] = {
    "Q0": {
        "title": "공고의 요건·조건 목록 (재귀 없음, 기준선)",
        "where": "P-4 요건 트리, 판정 카드",
        "sql": """
SELECT r.req_id, c.cond_id, c.attribute
FROM requirement r
JOIN condition c ON c.req_id = r.req_id
WHERE r.notice_id = :nid
""",
        "cypher": """
MATCH (n:Notice {notice_id: $nid})-[:HAS_REQUIREMENT]->(r:Requirement)-[:HAS_CONDITION]->(c:Condition)
RETURN r.req_id, c.cond_id, c.attribute
""",
    },
    "Q1": {
        "title": "사용자 지역으로 충족되는 공고 (지역 계층 ≤3 hop)",
        "where": "CQ-01·04·17, search_candidates",
        "sql": """
WITH RECURSIVE up(id, hops) AS (
  SELECT :u, 0
  UNION
  SELECT e.parent, up.hops + 1
  FROM concept_edge e JOIN up ON e.child = up.id
  WHERE e.rel IN ('WITHIN', 'MEMBER_OF') AND up.hops < 3
)
SELECT DISTINCT r.notice_id
FROM up
JOIN condition_concept cc ON cc.concept_id = up.id
JOIN condition c ON c.cond_id = cc.cond_id AND c.attribute = 'region'
JOIN requirement r ON r.req_id = c.req_id
""",
        "cypher": """
MATCH (u:Concept {concept_id: $u})-[:WITHIN|MEMBER_OF*0..3]->(:Concept)
      <-[:ABOUT]-(:Condition {attribute: 'region'})<-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice)
RETURN DISTINCT n.notice_id
""",
    },
    "Q2": {
        "title": "공고 조건의 개념 → 정의 → 조문 → 법령 (IS_A ≤2 hop)",
        "where": "CQ-05, fetch_definition",
        "sql": """
WITH RECURSIVE sup(start, id, hops) AS (
  SELECT concept_id, concept_id, 0 FROM concept
  UNION
  SELECT sup.start, e.parent, sup.hops + 1
  FROM concept_edge e JOIN sup ON e.child = sup.id
  WHERE e.rel = 'IS_A' AND sup.hops < 2
)
SELECT DISTINCT c.cond_id, d.term, l.name, a.article_no
FROM requirement r
JOIN condition c ON c.req_id = r.req_id
JOIN condition_concept cc ON cc.cond_id = c.cond_id
JOIN sup ON sup.start = cc.concept_id
JOIN concept_definition kd ON kd.concept_id = sup.id
JOIN definition d ON d.def_id = kd.def_id
JOIN definition_article da ON da.def_id = d.def_id
JOIN law_article a ON a.article_id = da.article_id
JOIN external_law l ON l.law_id = a.law_id
WHERE r.notice_id = :nid
""",
        "cypher": """
MATCH (:Notice {notice_id: $nid})-[:HAS_REQUIREMENT]->(:Requirement)-[:HAS_CONDITION]->(c:Condition)
      -[:ABOUT]->(:Concept)-[:IS_A*0..2]->(:Concept)-[:DEFINED_BY]->(d:Definition)
      -[:CITES_LAW]->(a:LawArticle)-[:PART_OF]->(l:ExternalLaw)
RETURN DISTINCT c.cond_id, d.term, l.name, a.article_no
""",
    },
    "Q3": {
        "title": "판정 근거 경로를 결과로 반환 (사용자 지역 → 조건 지역, 경로 노드 이름)",
        "where": "trace_path, 화면 경로 표시",
        "sql": """
WITH RECURSIVE up(id, hops, path) AS (
  SELECT k.concept_id, 0, k.name FROM concept k WHERE k.concept_id = :u
  UNION ALL
  SELECT e.parent, up.hops + 1, up.path || ' > ' || p.name
  FROM concept_edge e JOIN up ON e.child = up.id
  JOIN concept p ON p.concept_id = e.parent
  WHERE e.rel IN ('WITHIN', 'MEMBER_OF') AND up.hops < 3
)
SELECT c.cond_id, up.path
FROM requirement r
JOIN condition c ON c.req_id = r.req_id AND c.attribute = 'region'
JOIN condition_concept cc ON cc.cond_id = c.cond_id
JOIN up ON up.id = cc.concept_id
WHERE r.notice_id = :nid
""",
        "cypher": """
MATCH (:Notice {notice_id: $nid})-[:HAS_REQUIREMENT]->(:Requirement)-[:HAS_CONDITION]->(c:Condition {attribute: 'region'})-[:ABOUT]->(t:Concept)
MATCH p = (:Concept {concept_id: $u})-[:WITHIN|MEMBER_OF*0..3]->(t)
RETURN c.cond_id, [x IN nodes(p) | x.name] AS path
""",
    },
    "Q4": {
        "title": "조문이 바뀌면 영향받는 공고 (조문 → 정의 → 개념 ← IS_A ← 조건 ← 공고)",
        "where": "CQ-15, 법령 개정 영향 분석",
        "sql": """
WITH RECURSIVE sub(id, hops) AS (
  SELECT kd.concept_id, 0
  FROM definition_article da JOIN concept_definition kd ON kd.def_id = da.def_id
  WHERE da.article_id = :aid
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
MATCH (:LawArticle {article_id: $aid})<-[:CITES_LAW]-(:Definition)<-[:DEFINED_BY]-(:Concept)<-[:IS_A*0..2]-(:Concept)
      <-[:ABOUT]-(:Condition)<-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice)
RETURN DISTINCT n.notice_id
""",
    },
}

TOKEN = re.compile(r"'[^']*'|\$\w+|:\w+|\w+|\.\.|\*|->|<-|[^\w\s]")


def metrics(code: str, lang: str) -> dict:
    lines = [ln for ln in code.strip().splitlines() if ln.strip()]
    toks = TOKEN.findall(code)
    if lang == "sql":
        joins = len(re.findall(r"\bJOIN\b", code))
        recursive = len(re.findall(r"\bRECURSIVE\b", code))
        hops = joins
    else:
        joins = 0
        recursive = 0
        hops = len(re.findall(r"-\[[^\]]*\]-", code))  # 관계 패턴 수
    return {"lines": len(lines), "chars": len(re.sub(r"\s+", " ", code.strip())), "tokens": len(toks),
            "joins_or_hops": hops, "recursive_cte": recursive}


def norm_rows(rows) -> set:
    out = set()
    for r in rows:
        vals = []
        for v in r:
            if isinstance(v, list):
                v = " > ".join(v)
            vals.append(v)
        out.add(tuple(vals))
    return out


def main() -> int:
    from api.core.config import get_settings
    from api.repositories.graph import from_settings

    repo = from_settings(get_settings())
    if repo is None:
        print("NEO4J_* 설정이 없습니다.")
        return 1

    db = sqlite3.connect(":memory:")
    db.executescript(DDL)
    sizes = {}
    for table, cy in EXPORT.items():
        rows = [tuple(r.values()) for r in repo._read(cy)]
        db.executemany(f"INSERT OR IGNORE INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)
        sizes[table] = len(rows)
    db.commit()

    # 입력: 실제로 결과가 나오는 값을 고른다
    regions = [r["id"] for r in repo._read("MATCH (k:Region) WHERE k.level IN ['SIGUNGU','GU','SIDO'] RETURN k.concept_id AS id ORDER BY id")][::10]
    def_notices = [r["id"] for r in repo._read(
        "MATCH (n:Notice)-[:HAS_REQUIREMENT]->()-[:HAS_CONDITION]->()-[:ABOUT]->()-[:IS_A*0..2]->()-[:DEFINED_BY]->() "
        "RETURN DISTINCT n.notice_id AS id ORDER BY id LIMIT 40")]
    reg_notices = [(r["nid"], r["u"]) for r in repo._read(
        "MATCH (n:Notice)-[:HAS_REQUIREMENT]->()-[:HAS_CONDITION]->(c:Condition {attribute:'region'})-[:ABOUT]->(t:Concept) "
        "MATCH (u:Region)-[:WITHIN*1..2]->(t) WHERE u.level IN ['SIGUNGU','GU'] "
        "WITH n, head(collect(u.concept_id)) AS u RETURN n.notice_id AS nid, u ORDER BY nid LIMIT 40")]
    articles = [r["id"] for r in repo._read("MATCH (:Definition)-[:CITES_LAW]->(a:LawArticle) RETURN DISTINCT a.article_id AS id")]
    inputs = {
        "Q0": [{"nid": n} for n in def_notices[:20]],
        "Q1": [{"u": u} for u in regions],
        "Q2": [{"nid": n} for n in def_notices],
        "Q3": [{"nid": n, "u": u} for n, u in reg_notices],
        "Q4": [{"aid": a} for a in articles],
    }

    report = {"tables": sizes, "queries": {}}
    for qid, q in QUERIES.items():
        mismatch, total_rows, t_sql, t_cy = 0, 0, [], []
        for p in inputs[qid]:
            t0 = time.perf_counter()
            s = norm_rows(db.execute(q["sql"], p).fetchall())
            t_sql.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter()
            g = norm_rows([tuple(r.values()) for r in repo._read(q["cypher"], **p)])
            t_cy.append((time.perf_counter() - t0) * 1000)
            total_rows += len(s)
            if s != g:
                mismatch += 1
        report["queries"][qid] = {
            "title": q["title"], "where": q["where"], "inputs": len(inputs[qid]), "result_rows": total_rows,
            "mismatched_inputs": mismatch,
            "sql": metrics(q["sql"], "sql"), "cypher": metrics(q["cypher"], "cypher"),
            "ms_p50": {"sqlite_local": round(statistics.median(t_sql), 2), "neo4j_roundtrip": round(statistics.median(t_cy), 1)},
            "sql_code": q["sql"].strip(), "cypher_code": q["cypher"].strip(),
        }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print("| 질문 | 입력 | 결과 불일치 | SQL 줄 | Cypher 줄 | SQL 토큰 | Cypher 토큰 | SQL 조인 | Cypher 관계 패턴 | 재귀 CTE |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for qid, r in report["queries"].items():
        s, c = r["sql"], r["cypher"]
        print(f"| {qid} {r['title']} | {r['inputs']} | {r['mismatched_inputs']} | {s['lines']} | {c['lines']} | {s['tokens']} | "
              f"{c['tokens']} | {s['joins_or_hops']} | {c['joins_or_hops']} | {s['recursive_cte']} |")
    print("tables", sizes)
    print("result rows", {k: v["result_rows"] for k, v in report["queries"].items()})
    print("ms", {k: v["ms_p50"] for k, v in report["queries"].items()})
    print("saved", OUT.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
