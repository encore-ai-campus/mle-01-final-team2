#!/usr/bin/env python3
"""공고 그래프(data/graph/nodes.jsonl, edges.jsonl)를 Neo4j에 적재한다. 기본은 dry-run이다.

입력은 `python tools/graphrag/build.py export`가 만든 파일이다. 기존 `tools/load_neo4j.py`는 IBK 규정용이라 이 프로젝트와 무관하다.

단계(--stage)
  meta          메타·개념 층: Notice, Organization, SupportCategory, Concept와 ANNOUNCED_BY, EXECUTED_BY, IN_SUPPORT_CATEGORY, WITHIN, MEMBER_OF, SUCCEEDED_BY
  requirements  요건 층: Requirement, Condition과 HAS_REQUIREMENT, HAS_CONDITION, ABOUT (K-Startup 구조화 필드로 만든 `structured_only`만 있다)
  all           두 단계 모두

사용
  python tools/load_graph_neo4j.py                         # dry-run: 파일 검증과 적재 계획만 출력, DB 접속 없음
  python tools/load_graph_neo4j.py --check-db              # dry-run + DB를 읽기 전용으로 조회(비어 있는지 확인)
  python tools/load_graph_neo4j.py --apply --confirm-host <NEO4J_URI의 호스트>   # 실제 적재

안전 장치
  - 기본은 아무것도 쓰지 않는다. `--apply`에는 접속 대상 호스트를 `--confirm-host`로 다시 입력해야 한다.
  - 적재 전에 DB를 읽기 전용으로 조회해 노드가 하나라도 있으면 중단한다(`--allow-existing`으로만 해제).
  - MERGE로 적재해 여러 번 실행해도 같은 결과다. DELETE는 이 스크립트에 없다.
  - 요건 층(`--stage requirements`)은 검수 전 값이 섞이므로 기본 단계(`meta`)에 넣지 않았다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
GRAPH = ROOT / "data" / "graph"
SCHEMA = ROOT / "docs" / "submission" / "ontology" / "schema.cypher"
BATCH_SIZE = 1000
AURA_FREE_LIMITS = {"nodes": 200_000, "relationships": 400_000}  # Aura Free 한도. 인스턴스 등급이 다르면 달라진다

KEY = {"Notice": "notice_id", "Organization": "org_id", "SupportCategory": "category_id", "Concept": "concept_id",
       "Requirement": "req_id", "Condition": "cond_id", "Definition": "def_id", "ExternalLaw": "law_id",
       "LawArticle": "article_id", "LawAppendix": "appendix_id", "Track": "track_id", "Program": "program_id", "Attachment": "attachment_id"}
STAGES = {
    "meta": {"labels": ["Notice", "Organization", "SupportCategory", "Concept"],
             "edges": ["ANNOUNCED_BY", "EXECUTED_BY", "IN_SUPPORT_CATEGORY", "WITHIN", "MEMBER_OF", "SUCCEEDED_BY"]},
    "requirements": {"labels": ["Requirement", "Condition"], "edges": ["HAS_REQUIREMENT", "HAS_CONDITION", "ABOUT"]},
}
# 관계 시그니처(설계서 5.2): 관계 -> (시작 레이블, 끝 레이블)
SIGNATURE = {"ANNOUNCED_BY": ("Notice", "Organization"), "EXECUTED_BY": ("Notice", "Organization"),
             "IN_SUPPORT_CATEGORY": ("Notice", "SupportCategory"), "WITHIN": ("Concept", "Concept"), "MEMBER_OF": ("Concept", "Concept"),
             "SUCCEEDED_BY": ("Concept", "Concept"), "HAS_REQUIREMENT": ("Notice", "Requirement"),
             "HAS_CONDITION": ("Requirement", "Condition"), "ABOUT": ("Condition", "Concept")}
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def stage_names(stage: str) -> list[str]:
    return list(STAGES) if stage == "all" else [stage]


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line.strip()]


def props(record: dict, drop: Iterable[str]) -> dict[str, Any]:
    """Neo4j 속성으로 쓸 수 있는 값만 남긴다. None은 속성을 만들지 않고, 맵·중첩 목록은 JSON 문자열로 바꾼다."""
    out: dict[str, Any] = {}
    for k, v in record.items():
        if k in drop or v is None:
            continue
        if isinstance(v, dict) or (isinstance(v, list) and any(isinstance(x, (dict, list)) for x in v)):
            v = json.dumps(v, ensure_ascii=False)
        out[k] = v
    return out


def node_id(n: dict) -> str | None:
    return n.get(KEY.get(n.get("label", ""), ""))


def validate(nodes: list[dict], edges: list[dict]) -> list[str]:
    """파일 자체의 문제. 비어 있어야 적재할 수 있다."""
    errors: list[str] = []
    by_id: dict[str, str] = {}
    seen: Counter = Counter()
    for n in nodes:
        label = n.get("label")
        if label not in KEY:
            errors.append(f"알 수 없는 레이블: {label}")
            continue
        nid = node_id(n)
        if not nid:
            errors.append(f"{label} 노드에 {KEY[label]}가 없음")
            continue
        seen[(label, nid)] += 1
        by_id[nid] = label
    errors += [f"중복 노드 {label}:{nid}" for (label, nid), c in seen.items() if c > 1][:20]
    for e in edges:
        sig = SIGNATURE.get(e.get("type"))
        if not sig:
            errors.append(f"알 수 없는 관계 타입: {e.get('type')}")
            continue
        a, b = by_id.get(e["from"]), by_id.get(e["to"])
        if a is None or b is None:
            errors.append(f"끝점이 없는 간선 {e['type']}: {e['from']} -> {e['to']}")
        elif (a, b) != sig:
            errors.append(f"시그니처 위반 {e['type']}: {a} -> {b} (허용 {sig[0]} -> {sig[1]})")
    return errors[:50]


def select(nodes: list[dict], edges: list[dict], stage: str) -> tuple[list[dict], list[dict]]:
    labels = {l for s in stage_names(stage) for l in STAGES[s]["labels"]}
    types = {t for s in stage_names(stage) for t in STAGES[s]["edges"]}
    return [n for n in nodes if n["label"] in labels], [e for e in edges if e["type"] in types]


def batches(rows: list, size: int = BATCH_SIZE) -> Iterable[list]:
    for i in range(0, len(rows), size):
        yield rows[i:i + size]


def node_statements(nodes: list[dict]) -> list[tuple[str, str, list[dict]]]:
    """(설명, cypher, 행 목록). Concept 중 REGION은 보조 레이블 Region을 붙인다(설계서 D-2)."""
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for n in nodes:
        label, key = n["label"], KEY[n["label"]]
        suffix = ":Region" if label == "Concept" and n.get("scheme") == "REGION" else ""
        groups[(label + suffix, key)].append({"id": n[key], "props": props(n, {"label", key})})
    out = []
    for (labels, key), rows in sorted(groups.items()):
        assert all(IDENT.match(x) for x in labels.split(":") + [key])
        out.append((f"노드 {labels} {len(rows)}개", f"UNWIND $rows AS row MERGE (n:{labels} {{{key}: row.id}}) SET n += row.props", rows))
    return out


def edge_statements(nodes: list[dict], edges: list[dict]) -> list[tuple[str, str, list[dict]]]:
    label_of = {node_id(n): n["label"] for n in nodes}
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for e in edges:
        groups[(e["type"], label_of[e["from"]], label_of[e["to"]])].append(
            {"from": e["from"], "to": e["to"], "props": props(e, {"type", "from", "to"})})
    out = []
    for (t, a, b), rows in sorted(groups.items()):
        assert all(IDENT.match(x) for x in (t, a, b))
        ka, kb = KEY[a], KEY[b]
        out.append((f"관계 {t} ({a}->{b}) {len(rows)}개",
                    f"UNWIND $rows AS row MATCH (a:{a} {{{ka}: row.from}}) MATCH (b:{b} {{{kb}: row.to}}) MERGE (a)-[r:{t}]->(b) SET r += row.props", rows))
    return out


def constraints_for(labels: set[str]) -> list[str]:
    """schema.cypher의 CREATE CONSTRAINT 중 이번 단계 레이블에 해당하는 것."""
    out = []
    if SCHEMA.exists():
        for line in SCHEMA.read_text(encoding="utf-8").split("\n"):
            m = re.match(r"CREATE CONSTRAINT\s+\w+\s+IF NOT EXISTS FOR \(\w+:(\w+)\)", line.strip())
            if m and m.group(1) in labels:
                out.append(line.strip())
    return out


def plan(nodes: list[dict], edges: list[dict], stage: str) -> dict:
    sel_nodes, sel_edges = select(nodes, edges, stage)
    # 선택한 단계의 관계가 가리키는 노드가 선택 밖이면(예: requirements 단계의 ABOUT -> Concept) 이미 적재된 노드를 가리킨다고 본다.
    ctx_nodes = nodes if stage != "meta" else sel_nodes
    n_stmts = node_statements(sel_nodes)
    e_stmts = edge_statements(ctx_nodes, sel_edges)
    labels = {n["label"] for n in sel_nodes}
    return {"nodes": sel_nodes, "edges": sel_edges, "node_statements": n_stmts, "edge_statements": e_stmts,
            "constraints": constraints_for(labels),
            "counts": {"nodes": len(sel_nodes), "relationships": len(sel_edges),
                       "node_labels": dict(Counter(n["label"] for n in sel_nodes)), "edge_types": dict(Counter(e["type"] for e in sel_edges))}}


def connect():
    try:
        import truststore  # Windows 인증서 저장소를 쓴다. 없으면 Python 기본 번들로 검증한다(사내망에서 실패할 수 있음)
        truststore.inject_into_ssl()
    except ImportError:
        print("참고: truststore가 없어 기본 인증서 번들을 쓴다. 인증서 오류가 나면 `pip install truststore`", file=sys.stderr)
    from dotenv import load_dotenv
    from neo4j import GraphDatabase
    load_dotenv(ROOT / ".env")
    uri, user, pw, db = os.getenv("NEO4J_URI") or "", os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"), os.getenv("NEO4J_DATABASE") or None
    if "://" not in uri:
        raise SystemExit("NEO4J_URI에 '://'가 없다. 예: neo4j+s://<id>.databases.neo4j.io")
    if not (user and pw):
        raise SystemExit("NEO4J_USERNAME, NEO4J_PASSWORD가 .env에 없다")
    driver = GraphDatabase.driver(uri, auth=(user, pw))
    driver.verify_connectivity()
    return driver, db, uri.split("://", 1)[1].split("/")[0].split(":")[0]


def db_overview(driver, db) -> dict:
    """읽기 전용 조회."""
    from neo4j import READ_ACCESS
    with driver.session(database=db, default_access_mode=READ_ACCESS) as s:
        nodes = s.run("MATCH (n) RETURN count(n) AS c").single()["c"]
        rels = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
        labels = {r["l"]: r["c"] for r in s.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c").data()}
        constraints = [r["name"] for r in s.run("SHOW CONSTRAINTS YIELD name").data()]
    return {"nodes": nodes, "relationships": rels, "labels": labels, "constraints": constraints}


def verify(driver, db, expected: dict) -> list[str]:
    """적재 후 건수와 점검 쿼리(설계서 5.4). 문제 목록을 돌려준다."""
    from neo4j import READ_ACCESS
    problems = []
    with driver.session(database=db, default_access_mode=READ_ACCESS) as s:
        have = {r["l"]: r["c"] for r in s.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c").data()}
        for label, c in expected["node_labels"].items():
            if have.get(label) != c:
                problems.append(f"노드 {label}: 기대 {c}, 실제 {have.get(label)}")
        rels = {r["t"]: r["c"] for r in s.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c").data()}
        for t, c in expected["edge_types"].items():
            if rels.get(t) != c:
                problems.append(f"관계 {t}: 기대 {c}, 실제 {rels.get(t)}")
        if "Concept" in expected["node_labels"]:
            v8 = s.run("MATCH (a:Concept {scheme:'REGION'})-[r:WITHIN]->(b:Concept) WITH a, count(r) AS p WHERE p > 1 RETURN count(a) AS c").single()["c"]
            v2 = s.run("MATCH p = (a:Concept)-[:IS_A|WITHIN*1..6]->(a) RETURN count(p) AS c").single()["c"]
            if v8:
                problems.append(f"V8 행정 WITHIN 상위가 둘 이상인 지역 {v8}개")
            if v2:
                problems.append(f"V2 순환 {v2}개")
        if "Condition" in expected["node_labels"]:
            v4 = s.run("MATCH (c:Condition) WHERE NOT ( ()-[:HAS_CONDITION]->(c) OR ()-[:HAS_CHILD]->(c) ) RETURN count(c) AS c").single()["c"]
            if v4:
                problems.append(f"V4 고아 조건 {v4}개")
    return problems


def apply(driver, db, pl: dict) -> None:
    with driver.session(database=db) as s:
        for cypher in pl["constraints"]:
            s.run(cypher).consume()
        for group in (pl["node_statements"], pl["edge_statements"]):  # 노드를 모두 올린 뒤 관계를 올린다
            for desc, cypher, rows in group:
                done = 0
                for chunk in batches(rows):
                    s.run(cypher, rows=chunk).consume()
                    done += len(chunk)
                print(f"  적재 {desc}: {done}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage", choices=["meta", "requirements", "all"], default="meta")
    ap.add_argument("--graph-dir", type=Path, default=GRAPH)
    ap.add_argument("--check-db", action="store_true", help="DB를 읽기 전용으로 조회한다(dry-run에서도 사용 가능)")
    ap.add_argument("--apply", action="store_true", help="실제로 적재한다")
    ap.add_argument("--confirm-host", help="--apply 때 접속 대상 호스트를 다시 입력한다(오적재 방지)")
    ap.add_argument("--allow-existing", action="store_true", help="DB에 노드가 있어도 적재한다(기본은 중단)")
    ap.add_argument("--report", type=Path, help="계획 요약을 JSON으로 저장한다")
    a = ap.parse_args(argv)

    nodes, edges = read_jsonl(a.graph_dir / "nodes.jsonl"), read_jsonl(a.graph_dir / "edges.jsonl")
    errors = validate(nodes, edges)
    print(f"입력: 노드 {len(nodes):,}개, 관계 {len(edges):,}개 ({a.graph_dir})")
    if errors:
        print("파일 검증 실패:")
        for e in errors:
            print("  -", e)
        return 2
    print("파일 검증: 중복 노드 0, 끝점 없는 간선 0, 관계 시그니처 위반 0")

    pl = plan(nodes, edges, a.stage)
    c = pl["counts"]
    print(f"\n단계 `{a.stage}`: 노드 {c['nodes']:,}개, 관계 {c['relationships']:,}개")
    for k, v in sorted(c["node_labels"].items()):
        print(f"  노드 {k}: {v:,}")
    for k, v in sorted(c["edge_types"].items()):
        print(f"  관계 {k}: {v:,}")
    n_batches = sum(len(list(batches(rows))) for _, _, rows in pl["node_statements"] + pl["edge_statements"])
    print(f"제약 {len(pl['constraints'])}개를 먼저 건다. 배치 크기 {BATCH_SIZE}, 쓰기 트랜잭션 {n_batches}회")
    for limit, name in (("nodes", "노드"), ("relationships", "관계")):
        used = c[limit]
        print(f"Aura Free 한도 {name}: {used:,} / {AURA_FREE_LIMITS[limit]:,} ({used / AURA_FREE_LIMITS[limit]:.1%})")
    print("\n실행할 Cypher(첫 배치 1행씩):")
    for desc, cypher, rows in pl["node_statements"] + pl["edge_statements"]:
        print(f"  [{desc}]\n    {cypher}\n    예: {json.dumps(rows[0], ensure_ascii=False)[:150]}")

    report = {"stage": a.stage, "counts": c, "constraints": pl["constraints"], "write_transactions": n_batches}
    driver = db = host = None
    if a.check_db or a.apply:
        driver, db, host = connect()
        ov = db_overview(driver, db)
        report["db_before"] = ov
        print(f"\nDB 조회(읽기 전용): host={host}, database={db}, 노드 {ov['nodes']:,}, 관계 {ov['relationships']:,}, 제약 {len(ov['constraints'])}개")
        if ov["nodes"] and not a.allow_existing:
            print("중단: DB에 이미 노드가 있다. 확인하거나 --allow-existing을 쓴다.")
            driver.close()
            return 3
    if a.report:
        a.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"계획 요약 저장: {a.report}")
    if not a.apply:
        print("\ndry-run 끝. 아무것도 쓰지 않았다.")
        if driver:
            driver.close()
        return 0
    if a.confirm_host != host:
        print(f"중단: --confirm-host가 접속 대상 호스트({host})와 같아야 한다.")
        driver.close()
        return 4
    print("\n적재 시작")
    apply(driver, db, pl)
    problems = verify(driver, db, pl["counts"])
    driver.close()
    if problems:
        print("적재 후 점검에서 문제 발견:")
        for p in problems:
            print("  -", p)
        return 5
    print("적재 후 점검 통과(건수 일치, V2·V4·V8 0)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
