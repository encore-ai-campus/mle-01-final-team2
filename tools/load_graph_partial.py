#!/usr/bin/env python3
"""그래프의 일부만 Neo4j(Aura)에 MERGE한다. 기본은 dry-run이고, DB와 비교한 변경 내역을 먼저 보여 준다.

`load_graph_neo4j.py`는 빈 DB에 단계 전체를 올리는 도구다. 이미 적재된 공용 DB에 정의 하나, 검수 요건 몇 개처럼
일부만 더하거나 고칠 때 이 도구를 쓴다. 지우기(DELETE·REMOVE)는 하지 않는다.

선택(--select, 여러 개 가능)
  laws        법령·조문·별표·정의와 PART_OF·DEFINED_BY·CITES_LAW
  gold        사람이 검수한 본문 요건(`status=reviewed_excerpt`)과 그 조건, HAS_REQUIREMENT·HAS_CONDITION·ABOUT
  sme-rule    중소기업 판정 기준(`data/graph/definition_rules.json`)을 기존 Definition 노드의 `rule_json` 속성으로 붙인다(노드는 만들지 않는다)
  ids         --ids에 준 ID(정규식)와 맞는 노드, 그 노드에서 나가거나 들어오는 관계
입력은 `python tools/graphrag/build.py export`가 만든 `data/graph/nodes.jsonl`·`edges.jsonl`이다. 적재 전에 다시 내보낸다.

사용
  python tools/load_graph_partial.py --select gold                       # dry-run: DB와 비교만(읽기 전용)
  python tools/load_graph_partial.py --select sme-rule --show-changes     # 바뀌는 속성까지 출력
  python tools/load_graph_partial.py --select gold --apply --confirm-host <호스트>

안전 장치
  - `--apply`에는 접속 대상 호스트를 `--confirm-host`로 다시 입력해야 한다.
  - 파일 검증(중복 ID, 시그니처), 같은 ID가 DB에서 다른 레이블로 쓰이는지, 관계 끝점이 선택이나 DB에 있는지 확인한다. 하나라도 걸리면 쓰지 않는다.
  - 적재 전후 `check_graph_neo4j` 점검을 돌려 바뀐 건수를 보여 주고, 0이어야 하는 점검이 실패하면 종료 코드 5로 끝난다.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_graph_neo4j as CHK  # noqa: E402
import load_graph_neo4j as L  # noqa: E402

RULES = L.GRAPH / "definition_rules.json"
LAW_LABELS = {"ExternalLaw", "LawArticle", "LawAppendix", "Definition"}
LAW_EDGES = {"PART_OF", "DEFINED_BY", "CITES_LAW"}


def select_laws(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    return [n for n in nodes if n["label"] in LAW_LABELS], [e for e in edges if e["type"] in LAW_EDGES]


def select_gold(nodes: list[dict], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    reqs = {n["req_id"] for n in nodes if n["label"] == "Requirement" and n.get("status") == "reviewed_excerpt"}
    sel_e = [e for e in edges if (e["type"] == "HAS_REQUIREMENT" and e["to"] in reqs) or (e["type"] == "HAS_CONDITION" and e["from"] in reqs)]
    conds = {e["to"] for e in sel_e if e["type"] == "HAS_CONDITION"}
    sel_e += [e for e in edges if e["type"] == "ABOUT" and e["from"] in conds]
    return [n for n in nodes if L.node_id(n) in reqs | conds], sel_e


def select_ids(nodes: list[dict], edges: list[dict], pattern: str) -> tuple[list[dict], list[dict]]:
    rx = re.compile(pattern)
    sel = [n for n in nodes if rx.search(L.node_id(n) or "")]
    ids = {L.node_id(n) for n in sel}
    return sel, [e for e in edges if e["from"] in ids or e["to"] in ids]


def sme_rule_nodes(path: Path = RULES) -> list[dict]:
    """정의 노드에 붙일 판정 기준. 속성만 더하는 갱신 행이라 `must_exist`로 표시한다."""
    out = []
    for def_id, rule in json.loads(path.read_text(encoding="utf-8")).items():
        out.append({"label": "Definition", "def_id": def_id, "rule_json": json.dumps(rule, ensure_ascii=False, sort_keys=True),
                    "rule_id": rule["rule_id"], "rule_status": rule["status"], "rule_needs_review": rule["needs_review"], "_must_exist": True})
    return out


def merge_selection(parts: list[tuple[list[dict], list[dict]]]) -> tuple[list[dict], list[dict]]:
    """여러 선택을 합친다. 같은 노드가 두 번 나오면 속성을 합친다(뒤의 값이 이긴다)."""
    by_key: dict[tuple[str, str], dict] = {}
    edges: dict[tuple[str, str, str], dict] = {}
    for ns, es in parts:
        for n in ns:
            k = (n["label"], L.node_id(n))
            by_key[k] = {**by_key.get(k, {}), **n}
        for e in es:
            edges[(e["type"], e["from"], e["to"])] = e
    return list(by_key.values()), list(edges.values())


def comparable(n: dict) -> dict:
    """DB 속성과 비교할 모양. 적재 때와 같은 변환(None 제거, 맵은 JSON 문자열)을 쓴다."""
    return L.props({k: v for k, v in n.items() if not k.startswith("_")}, {"label", L.KEY[n["label"]]})


def classify(nodes: list[dict], db_props: dict[tuple[str, str], dict | None]) -> dict[str, list]:
    """노드를 new / changed / same / missing(속성 갱신인데 DB에 없음)으로 나눈다. changed는 (노드, 바뀐 키 목록)."""
    out: dict[str, list] = {"new": [], "changed": [], "same": [], "missing": []}
    for n in nodes:
        cur = db_props.get((n["label"], L.node_id(n)))
        if cur is None:
            out["missing" if n.get("_must_exist") else "new"].append(n)
            continue
        want = comparable(n)
        keys = sorted(k for k, v in want.items() if cur.get(k) != v)
        (out["changed"].append((n, keys)) if keys else out["same"].append(n))
    return out


def endpoint_problems(nodes: list[dict], edges: list[dict], db_labels: dict[str, list[str]]) -> list[str]:
    """관계 끝점이 선택에도 DB에도 없거나, 시그니처에 맞지 않으면 문제."""
    local = {L.node_id(n): n["label"] for n in nodes}
    out = []
    for e in edges:
        ends = []
        for end in (e["from"], e["to"]):
            labs = [local[end]] if end in local else [x for x in db_labels.get(end, []) if x in L.KEY]
            ends.append(labs[0] if labs else None)
        if None in ends:
            out.append(f"끝점 없음 {e['type']}: {e['from']} -> {e['to']}")
        elif tuple(ends) not in L.SIGNATURE.get(e["type"], []):
            out.append(f"시그니처 위반 {e['type']}: {ends[0]} -> {ends[1]}")
    return out[:50]


def read_db(session, nodes: list[dict], edges: list[dict]) -> dict:
    """선택한 노드·관계를 DB에서 읽는다(읽기 전용). 레이블별 키(유일 제약 인덱스)로 찾는다."""
    ids = sorted({L.node_id(n) for n in nodes} | {x for e in edges for x in (e["from"], e["to"])})
    db_props: dict[tuple[str, str], dict] = {}
    db_labels: dict[str, list[str]] = {}
    for label, key in L.KEY.items():  # 같은 ID가 다른 레이블로 있는지까지 보려고 모든 레이블에서 찾는다
        for chunk in L.batches(ids):
            for r in session.run(f"UNWIND $ids AS i MATCH (n:{label} {{{key}: i}}) RETURN i, properties(n) AS p", ids=chunk):
                db_props[(label, r["i"])] = r["p"]
                db_labels.setdefault(r["i"], []).append(label)
    local = {L.node_id(n): n["label"] for n in nodes}
    label_of = lambda i: local.get(i) or (db_labels.get(i) or [None])[0]  # noqa: E731
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for e in edges:
        a, b = label_of(e["from"]), label_of(e["to"])
        if a and b:
            groups.setdefault((e["type"], a, b), []).append({"a": e["from"], "b": e["to"]})
    existing_edges = set()
    for (t, a, b), rows in groups.items():
        assert all(L.IDENT.match(x) for x in (t, a, b))
        q = (f"UNWIND $rows AS row MATCH (a:{a} {{{L.KEY[a]}: row.a}})-[:{t}]->(b:{b} {{{L.KEY[b]}: row.b}}) "
             "RETURN DISTINCT row.a AS a, row.b AS b")
        for chunk in L.batches(rows):
            existing_edges |= {(t, r["a"], r["b"]) for r in session.run(q, rows=chunk)}
    return {"props": db_props, "labels": db_labels, "edges": existing_edges}


def label_conflicts(nodes: list[dict], db_labels: dict[str, list[str]]) -> list[str]:
    out = []
    for n in nodes:
        other = [x for x in db_labels.get(L.node_id(n), []) if x in L.KEY and x != n["label"]]
        if other:
            out.append(f"{L.node_id(n)}: 선택은 {n['label']}, DB에는 {'·'.join(sorted(set(other)))}")
    return out[:50]


def statements(nodes: list[dict], edges: list[dict], db_labels: dict[str, list[str]]) -> list[tuple[str, str, list[dict]]]:
    clean = [{k: v for k, v in n.items() if not k.startswith("_")} for n in nodes]
    known = {L.node_id(n) for n in clean}
    ctx = clean + [{"label": next(x for x in labs if x in L.KEY), L.KEY[next(x for x in labs if x in L.KEY)]: i}
                   for i, labs in db_labels.items() if i not in known and any(x in L.KEY for x in labs)]
    out = L.node_statements(clean)
    # 속성 갱신 행(_must_exist)은 MERGE 대신 MATCH로 쓴다. 없는 노드를 새로 만들지 않게 한다
    must = {L.node_id(n) for n in nodes if n.get("_must_exist")}
    if must:
        out = [(d, c.replace("MERGE (n:", "MATCH (n:", 1) if all(r["id"] in must for r in rows) else c, rows) for d, c, rows in out]
    return out + L.edge_statements(ctx, edges)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--select", nargs="+", choices=["laws", "gold", "sme-rule", "ids"], required=True)
    ap.add_argument("--ids", help="--select ids에 쓸 정규식(노드 ID에 search)")
    ap.add_argument("--graph-dir", type=Path, default=L.GRAPH)
    ap.add_argument("--show-changes", action="store_true", help="바뀌는 속성의 전후 값을 출력한다")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm-host")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if "ids" in a.select and not a.ids:
        ap.error("--select ids에는 --ids가 필요하다")

    parts = []
    if set(a.select) - {"sme-rule"}:
        all_nodes, all_edges = L.read_jsonl(a.graph_dir / "nodes.jsonl"), L.read_jsonl(a.graph_dir / "edges.jsonl")
        errors = L.validate(all_nodes, all_edges)
        if errors:
            print("파일 검증 실패:", *errors[:20], sep="\n  - ")
            return 2
        for s in a.select:
            if s == "laws":
                parts.append(select_laws(all_nodes, all_edges))
            elif s == "gold":
                parts.append(select_gold(all_nodes, all_edges))
            elif s == "ids":
                parts.append(select_ids(all_nodes, all_edges, a.ids))
    if "sme-rule" in a.select:
        parts.append((sme_rule_nodes(), []))
    nodes, edges = merge_selection(parts)
    print(f"선택 {'+'.join(a.select)}: 노드 {len(nodes):,} {dict(Counter(n['label'] for n in nodes))}, "
          f"관계 {len(edges):,} {dict(Counter(e['type'] for e in edges))}")
    if not nodes and not edges:
        print("선택된 것이 없다. 아무것도 하지 않는다.")
        return 0

    from neo4j import READ_ACCESS
    driver, db, host = L.connect()
    try:
        with driver.session(database=db, default_access_mode=READ_ACCESS, notifications_min_severity="OFF") as s:
            cur = read_db(s, nodes, edges)
            before = CHK.collect(s)
        cls = classify(nodes, cur["props"])
        problems = label_conflicts(nodes, cur["labels"]) + endpoint_problems(nodes, edges, cur["labels"])
        problems += [f"속성 갱신 대상이 DB에 없음: {n['label']} {L.node_id(n)}" for n in cls["missing"]]
        new_edges = [e for e in edges if (e["type"], e["from"], e["to"]) not in cur["edges"]]
        print(f"\nDB 비교({host}, 읽기 전용)")
        print(f"  노드: 새로 {len(cls['new']):,}, 속성 바뀜 {len(cls['changed']):,}, 같음 {len(cls['same']):,}")
        print(f"  관계: 새로 {len(new_edges):,}, 이미 있음 {len(edges) - len(new_edges):,} (있는 관계도 속성은 다시 SET)")
        if cls["new"]:
            print("  새 노드 예:", ", ".join(L.node_id(n) for n in cls["new"][:5]))
        changed_keys = Counter(k for _, ks in cls["changed"] for k in ks)
        if changed_keys:
            print("  바뀌는 속성:", dict(changed_keys.most_common()))
        if a.show_changes:
            for n, ks in cls["changed"][:20]:
                old = cur["props"][(n["label"], L.node_id(n))]
                want = comparable(n)
                for k in ks:
                    print(f"    {L.node_id(n)}.{k}: {str(old.get(k))[:80]!r} -> {str(want.get(k))[:80]!r}")
        if problems:
            print("\n문제(쓰지 않는다):", *problems, sep="\n  - ")
            return 3
        if not a.apply:
            print("\ndry-run 끝. 아무것도 쓰지 않았다.")
            return 0
        if a.confirm_host != host:
            print(f"중단: --confirm-host가 접속 대상 호스트({host})와 같아야 한다.")
            return 4
        print("\n적재 시작")
        with driver.session(database=db) as s:
            for desc, cypher, rows in statements(nodes, edges, cur["labels"]):
                for chunk in L.batches(rows):
                    s.run(cypher, rows=chunk).consume()
                print(f"  {desc}")
        with driver.session(database=db, default_access_mode=READ_ACCESS, notifications_min_severity="OFF") as s:
            after = CHK.collect(s)
    finally:
        driver.close()
    print("\n적재 전후 차이:", *(CHK.diff(before, after) or ["없음"]), sep="\n  ")
    fails, warns = CHK.judge(after)
    for w in warns:
        print("경고:", w)
    for f in fails:
        print("실패:", f)
    return 5 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
