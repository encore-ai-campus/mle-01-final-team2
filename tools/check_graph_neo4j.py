#!/usr/bin/env python3
"""Aura(Neo4j) 그래프를 읽기 전용으로 점검한다. 쓰기는 하지 않는다.

점검 항목
  - 레이블별 노드 수, 타입별 관계 수
  - V0~V17 점검 쿼리(설계서 §6.2, `docs/submission/ontology/schema.cypher`, 설계서 부록 A)
    `zero`는 0이어야 정상이고, `known`은 알려진 값이 있어 바뀌었는지만 본다(바뀌면 경고, 실패 아님).
  - 법령 링크 형식(`law_url`), 개념 → 정의 → 조문 → 법령 경로 수
  - `--check-definitions`: DB 정의의 조문 원문 해시를 로컬 조문 파일에서 다시 만든 값과 비교한다

사용
  python tools/check_graph_neo4j.py                          # 점검 결과 출력
  python tools/check_graph_neo4j.py --save before.json       # 결과를 스냅숏으로 저장(적재 전)
  python tools/check_graph_neo4j.py --compare before.json    # 저장한 스냅숏과 비교(적재 후)
  python tools/check_graph_neo4j.py --check-definitions      # 정의 원문 해시까지 확인

종료 코드: 0 정상, 1 `zero` 점검 실패 또는 정의 해시 불일치.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import load_graph_neo4j as L  # noqa: E402

# (번호, 설명, Cypher, 기대). 기대: "zero" 또는 알려진 값(int, 2026-11-26 기준)
CHECKS: list[tuple[str, str, str, object]] = [
    ("V1", "서로 다른 scheme 사이 WITHIN·IS_A",
     "MATCH (a:Concept)-[r:IS_A|WITHIN]->(b:Concept) WHERE a.scheme <> b.scheme AND NOT (a.scheme = 'ZONE' AND b.scheme = 'REGION') "
     "RETURN count(r) AS c", "zero"),
    ("V2", "계층 순환(IS_A·WITHIN·MEMBER_OF, 6 hop)", "MATCH p = (a:Concept)-[:IS_A|WITHIN|MEMBER_OF*1..6]->(a) RETURN count(p) AS c", "zero"),
    ("V3", "금지된 방향 관계(HAS_SUBREGION)", "MATCH ()-[r:HAS_SUBREGION]->() RETURN count(r) AS c", "zero"),
    ("V4", "고아 조건", "MATCH (c:Condition) WHERE NOT ( ()-[:HAS_CONDITION]->(c) OR ()-[:HAS_CHILD]->(c) ) RETURN count(c) AS c", "zero"),
    ("V5", "근거(evidence) 없는 요건·조건 관계",
     "MATCH ()-[r:HAS_REQUIREMENT|HAS_CONDITION|HAS_CHILD]->() WHERE r.evidence IS NULL RETURN count(r) AS c", "zero"),
    ("V6", "그룹 중첩 3단 초과",
     "MATCH p = (:Requirement)-[:HAS_CONDITION]->(:Condition)-[:HAS_CHILD*4..]->(:Condition) RETURN count(p) AS c", "zero"),
    ("V7", "SUPERSEDES 방향 오류",
     "MATCH (n:Notice)-[:SUPERSEDES]->(o:Notice) WHERE n = o OR n.version <= o.version RETURN count(*) AS c", "zero"),
    ("V8", "행정 WITHIN 상위가 둘 이상인 지역",
     "MATCH (a:Concept {scheme:'REGION'})-[r:WITHIN]->(:Concept) WITH a, count(r) AS p WHERE p > 1 RETURN count(a) AS c", "zero"),
    ("V9", "ABOUT 없는 개념형 조건",
     "MATCH (c:Condition) WHERE c.attribute IN ['region','applicant_type','company_size','industry','certification'] "
     "AND NOT (c)-[:ABOUT]->(:Concept) RETURN count(c) AS c", 546),
    ("V10", "대칭 관계 양방향", "MATCH (a:Notice)-[:SAME_AS]->(b:Notice), (b)-[:SAME_AS]->(a) RETURN count(*) AS c", "zero"),
    ("V11", "같은 쌍의 중복 HAS_CONDITION·ABOUT",
     "MATCH (a)-[r:HAS_CONDITION|ABOUT]->(b) WITH a, b, type(r) AS t, count(*) AS n WHERE n > 1 RETURN count(*) AS c", "zero"),
    ("V12", "조건 없는 요건", "MATCH (r:Requirement) WHERE NOT (r)-[:HAS_CONDITION]->() RETURN count(r) AS c", "zero"),
    ("V13", "지역 조건이 지역 아닌 개념을 가리킴",
     "MATCH (c:Condition {attribute: 'region'})-[:ABOUT]->(k) WHERE NOT k:Region RETURN count(c) AS c", "zero"),
    ("V14", "법령에 안 붙은 조문·별표",
     "MATCH (a) WHERE (a:LawArticle OR a:LawAppendix) AND NOT (a)-[:PART_OF]->(:ExternalLaw) RETURN count(a) AS c", "zero"),
    ("V15", "요건이 하나도 없는 공고", "MATCH (n:Notice) WHERE NOT (n)-[:HAS_REQUIREMENT]->() RETURN count(n) AS c", 330),
    ("V16", "상위(WITHIN)가 없는 현행 시군구·구",
     "MATCH (a:Region) WHERE a.level IN ['SIGUNGU', 'GU'] AND coalesce(a.status, '') <> '폐지' AND NOT (a)-[:WITHIN]->() RETURN count(a) AS c", "zero"),
    ("V16a", "상위(WITHIN)가 없는 비시도 지역(폐지 시군구 31·권역 3 포함)",
     "MATCH (a:Region) WHERE NOT a.level IN ['SIDO', 'NATIONWIDE'] AND NOT (a)-[:WITHIN]->() RETURN count(a) AS c", 34),
    ("V17", "개념에 안 붙은 정의", "MATCH (d:Definition) WHERE NOT ()-[:DEFINED_BY]->(d) RETURN count(d) AS c", 2),
    # 계층 관계 제약(강사 피드백 2026-11-27 ②): 끝점 종류, 자기 관계, 묶음 대상, 승계 방향
    ("V20", "계층 관계 끝점 위반(WITHIN: 지역·구역→지역, MEMBER_OF·SUCCEEDED_BY: 지역→지역, IS_A: 지역 아닌 개념끼리)",
     "MATCH (a)-[r:WITHIN|MEMBER_OF|SUCCEEDED_BY|IS_A]->(b) WHERE "
     "(type(r) = 'WITHIN' AND NOT (a.scheme IN ['REGION','ZONE'] AND b.scheme = 'REGION')) OR "
     "(type(r) IN ['MEMBER_OF','SUCCEEDED_BY'] AND NOT (a.scheme = 'REGION' AND b.scheme = 'REGION')) OR "
     "(type(r) = 'IS_A' AND (a:Region OR b:Region OR NOT a:Concept OR NOT b:Concept)) RETURN count(r) AS c", "zero"),
    ("V21", "자기 자신을 가리키는 계층 관계", "MATCH (a)-[r:WITHIN|MEMBER_OF|SUCCEEDED_BY|IS_A]->(a) RETURN count(r) AS c", "zero"),
    ("V22", "MEMBER_OF 양쪽 모두 묶음(GROUP)이 아님(지역→묶음, 묶음→상위 지역만 허용)",
     "MATCH (a)-[r:MEMBER_OF]->(g) WHERE coalesce(a.level, '') <> 'GROUP' AND coalesce(g.level, '') <> 'GROUP' RETURN count(r) AS c", "zero"),
    ("V23", "SUCCEEDED_BY 순환(승계가 되돌아옴, 6 hop)", "MATCH p = (a)-[:SUCCEEDED_BY*1..6]->(a) RETURN count(p) AS c", "zero"),
    ("V24", "SUCCEEDED_BY 출발이 폐지 지역이 아님", "MATCH (a)-[r:SUCCEEDED_BY]->() WHERE coalesce(a.status, '') <> '폐지' RETURN count(r) AS c", "zero"),
    ("V25", "위임 별표를 가리키는 정의 관계(Definition-CITES_LAW->LawAppendix, 검수 확인분)",
     "MATCH (:Definition)-[r:CITES_LAW]->(:LawAppendix) RETURN count(r) AS c", 4),
    ("D1", "조문·별표를 인용하지 않은 정의", "MATCH (d:Definition) WHERE NOT (d)-[:CITES_LAW]->() RETURN count(d) AS c", "zero"),
    ("D2", "옛 형식 법령 링크(lsInfoP.do?lsiSeq= 아님)",
     "MATCH (l:ExternalLaw) WHERE l.source_url IS NULL OR NOT l.source_url STARTS WITH 'https://www.law.go.kr/lsInfoP.do?lsiSeq=' RETURN count(l) AS c", "zero"),
]
PATHS = {"개념→정의→조문→법령 경로":
         "MATCH p = (:Concept)-[:DEFINED_BY]->(:Definition)-[:CITES_LAW]->()-[:PART_OF]->(:ExternalLaw) RETURN count(p) AS c"}


def key_check_cypher(label: str, key: str) -> str:
    assert L.IDENT.match(label) and L.IDENT.match(key)
    return f"MATCH (n:{label}) RETURN count(n) - count(n.{key}) AS missing, count(n.{key}) - count(DISTINCT n.{key}) AS dup"


def collect(session) -> dict:
    """DB를 읽어 스냅숏(dict)을 만든다. session은 읽기 전용이어야 한다."""
    one = lambda c: session.run(c).single()["c"]  # noqa: E731
    labels = {r["l"]: r["c"] for r in session.run("MATCH (n) UNWIND labels(n) AS l RETURN l, count(*) AS c").data()}
    rels = {r["t"]: r["c"] for r in session.run("MATCH ()-[r]->() RETURN type(r) AS t, count(*) AS c").data()}
    keys = {}
    for label, key in L.KEY.items():
        if labels.get(label):
            r = session.run(key_check_cypher(label, key)).single()
            keys[label] = {"missing": r["missing"], "dup": r["dup"]}
    return {"taken_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "nodes": sum(v for k, v in labels.items() if k in L.KEY), "relationships": sum(rels.values()),
            "labels": dict(sorted(labels.items())), "relationship_types": dict(sorted(rels.items())), "keys": keys,
            "checks": {cid: one(cy) for cid, _, cy, _ in CHECKS}, "paths": {name: one(cy) for name, cy in PATHS.items()}}


def judge(snap: dict) -> tuple[list[str], list[str]]:
    """(실패, 경고). 실패는 0이어야 하는 점검이 0이 아닌 것과 키 결측·중복, 경고는 알려진 값이 바뀐 것."""
    fails, warns = [], []
    for label, r in snap["keys"].items():
        if r["missing"] or r["dup"]:
            fails.append(f"V0 {label} 키 결측 {r['missing']}, 중복 {r['dup']}")
    for cid, desc, _, expect in CHECKS:
        got = snap["checks"].get(cid)
        if got is None:
            continue
        if expect == "zero" and got:
            fails.append(f"{cid} {desc}: {got}")
        elif isinstance(expect, int) and got != expect:
            warns.append(f"{cid} {desc}: 알려진 값 {expect} → {got}")
    return fails, warns


def diff(old: dict, new: dict) -> list[str]:
    """두 스냅숏의 차이(건수가 바뀐 항목만)."""
    out = []
    for name in ("nodes", "relationships"):
        if old.get(name) != new.get(name):
            out.append(f"{name}: {old.get(name)} → {new.get(name)} ({new.get(name, 0) - (old.get(name) or 0):+d})")
    for sect in ("labels", "relationship_types", "checks", "paths"):
        a, b = old.get(sect, {}), new.get(sect, {})
        for k in sorted(set(a) | set(b)):
            if a.get(k) != b.get(k):
                out.append(f"{sect}.{k}: {a.get(k)} → {b.get(k)} ({(b.get(k) or 0) - (a.get(k) or 0):+d})")
    return out


def definition_hashes(session) -> list[str]:
    """DB 정의의 원문 해시를 로컬 조문에서 다시 만든 정의와 비교한다. 불일치 목록."""
    from graphrag import concepts_laws as C
    _, _, by = C.concepts()
    _, _, idx, _ = C.laws()
    local = {n["def_id"]: n.get("article_text_hash") for n in C.definitions(by, idx)[0]}
    db = {r["i"]: r["h"] for r in session.run("MATCH (d:Definition) RETURN d.def_id AS i, d.article_text_hash AS h").data()}
    out = [f"{i}: DB에만 있음" for i in sorted(set(db) - set(local))]
    out += [f"{i}: 로컬에만 있음" for i in sorted(set(local) - set(db))]
    out += [f"{i}: 해시 다름" for i in sorted(set(db) & set(local)) if db[i] != local[i]]
    return out


def report(snap: dict) -> None:
    print(f"노드 {snap['nodes']:,}, 관계 {snap['relationships']:,}  ({snap['taken_at']})")
    print("노드:", ", ".join(f"{k} {v:,}" for k, v in snap["labels"].items()))
    print("관계:", ", ".join(f"{k} {v:,}" for k, v in snap["relationship_types"].items()))
    print("\n점검")
    bad_keys = sum(r["missing"] + r["dup"] for r in snap["keys"].values())
    print(f"  V0  키 결측·중복 ({len(snap['keys'])}개 레이블): {bad_keys}")
    for cid, desc, _, expect in CHECKS:
        tag = "0이어야 함" if expect == "zero" else (f"알려진 값 {expect}" if expect is not None else "참고")
        print(f"  {cid:<5}{desc}: {snap['checks'][cid]:,}  [{tag}]")
    for name, c in snap["paths"].items():
        print(f"  {name}: {c:,}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--save", type=Path, help="결과 스냅숏을 JSON으로 저장한다")
    ap.add_argument("--compare", type=Path, help="저장한 스냅숏과 비교한다")
    ap.add_argument("--check-definitions", action="store_true", help="정의 원문 해시를 로컬 조문과 비교한다")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows 콘솔(cp949)에서 한글이 깨지지 않게

    from neo4j import READ_ACCESS
    driver, db, host = L.connect()
    print(f"DB: {host} (읽기 전용)")
    try:
            # 없는 관계 타입(HAS_CHILD·SAME_AS 등)을 묻는 점검이 있어 서버 경고는 끈다
        with driver.session(database=db, default_access_mode=READ_ACCESS, notifications_min_severity="OFF") as s:
            snap = collect(s)
            hash_problems = definition_hashes(s) if a.check_definitions else []
    finally:
        driver.close()
    report(snap)
    fails, warns = judge(snap)
    if a.check_definitions:
        print(f"\n정의 원문 해시: 불일치 {len(hash_problems)}")
        fails += [f"정의 {p}" for p in hash_problems]
    if a.compare:
        changes = diff(json.loads(a.compare.read_text(encoding="utf-8")), snap)
        print(f"\n{a.compare}와 비교: 바뀐 항목 {len(changes)}")
        for c in changes:
            print("  ", c)
    if a.save:
        a.save.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\n스냅숏 저장: {a.save}")
    for w in warns:
        print("경고:", w)
    for f in fails:
        print("실패:", f)
    print("\n결과:", "실패" if fails else "정상")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
