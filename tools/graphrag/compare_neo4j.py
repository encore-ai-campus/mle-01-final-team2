#!/usr/bin/env python3
"""SQL 대 그래프 비교 측정: 지역 계층 판정(질문 유형 `hierarchy`)과 정의→법령 경로(`definition`)를 같은 스냅샷에서 잰다.

측정 방법은 docs/BASELINE_SQL_벡터RAG_측정방법_KPI산정근거_v0.1.md를 따른다. 구성:
  A    SQL 필터        사용자 지역과 조건 지역이 같은 값일 때만 충족(계층 없음)
  A2   SQL + 폐쇄 테이블  사전에 계산한 (지역, 상위 지역, hop) 테이블을 조인
  A3   SQL 재귀 CTE     질의 시점에 계층 간선(`WITHIN`·`MEMBER_OF`)을 재귀로 따라감(폐쇄 테이블 없음)
  C    파이썬 평가기    `evaluator.evaluate_condition`(기준 구현)
  G    Neo4j(Cypher)  적재한 그래프에서 `[:WITHIN|MEMBER_OF*0..3]` 경로 질의

공정성: 모든 구성이 같은 공고 집합(모집 중, 지역 조건 있음), 같은 지역 코드표·묶음 사전, 같은 3값 규칙(충족·불충족·미확인)과 hop 한도 3을 쓴다.
시간은 같은 기기에서 워밍업을 빼고 프로필당 질의 묶음의 p50·p95를 3회 반복해 잰다.

지연 비교의 공정성(2026-11-27 보강)
  SQLite(A·A2·A3)는 같은 프로세스의 메모리 안에서 돌아 네트워크·직렬화 비용이 없다. Neo4j(G)는 드라이버가 Bolt로 서버에 묻는다.
  그래서 G는 세 가지를 따로 적는다.
    - 서버 처리 시간: 서버가 보고한 result_available_after + result_consumed_after(정수 ms). 네트워크가 빠진다.
    - 왕복 시간: 호출 쪽 perf_counter. 네트워크·드라이버·직렬화가 들어간다.
    - 빈 질의 왕복(`RETURN 1`): 질의 한 번에 드는 고정 비용. G는 프로필당 질의를 2번(SAT·UNK) 보낸다.
  같은 기기 비교는 로컬 Neo4j(Docker)에 같은 그래프를 적재해 잰다(Aura는 원격이라 같은 기기 조건이 아니다).
    docker run -d --name neo4j-bench -p 17687:7687 -e NEO4J_AUTH=neo4j/<시험용 비밀번호> neo4j:5.26-community
    $env:NEO4J_URI="bolt://localhost:17687"; $env:NEO4J_USERNAME="neo4j"; $env:NEO4J_PASSWORD="<시험용 비밀번호>"; $env:NEO4J_DATABASE="neo4j"
    python tools/sync_graph_neo4j.py --apply --confirm-host localhost
    python tools/graphrag/compare_neo4j.py            # 결과: data/eval/compare_sql_graph_<날짜>_local.json
    docker rm -f neo4j-bench
  Aura에서 그냥 돌리면 결과는 data/eval/compare_sql_graph_<날짜>_aura.json. --out으로 바꿀 수 있다.

해석 기준(결과를 보기 전에 정했다)
  1. 일치: 구성 X의 3값 판정이 기준 C와 한 쌍도 다르지 않으면 "같은 결과". 다르면 원인을 분해하기 전에는 우열을 주장하지 않는다.
  2. 같은 결과이면 그래프의 우위 근거가 아니다. 계층 질의는 SQL(A2·A3)로 풀리고 그래프 DB가 필요하다는 주장은 하지 않는다.
  3. 시간은 서버 처리 시간 p50이 A2의 2배 이내면 "비슷", 그보다 크면 "느림", 절반 미만이면 "빠름"으로만 적는다.
  4. A의 계층 Recall(계층을 올라가야 충족되는 쌍 중 충족으로 낸 비율)이 C보다 낮으면 "계층 사전이 필요하다"는 근거로 쓰되, 그래프 필요성의 근거로는 쓰지 않는다.
  5. 질문 유형 `relation`(정정·재공고)·`definition`의 영향 전파(CQ-15)는 데이터가 없으면 "측정 불가"로 적는다.
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))

from graphrag.cleaned import load_cleaned  # noqa: E402
from graphrag.evaluator import SAT, UNK, UNSAT, Profile, evaluate_condition  # noqa: E402
from graphrag.regions import MAX_HOPS, RegionGraph  # noqa: E402

GRAPH = ROOT / "data" / "graph"
OUT = ROOT / "data" / "eval"
SEED = 20261124
N_PROFILES = 300
REPEATS = 3
WARMUP = 5
PING_N = 100
LOCAL_HOSTS = ("localhost", "127.0.0.1", "::1")
NATIONWIDE = "REGION:NATIONWIDE"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def summarize(ms: list[float]) -> dict:
    return {"n": len(ms), "p50_ms": round(statistics.median(ms), 2), "p95_ms": round(pct(ms, 0.95), 2), "mean_ms": round(statistics.mean(ms), 2)}


# ----------------------------------------------------------------------------- 데이터
def load_inputs():
    """그래프 파일(적재한 것과 같은 스냅샷)에서 간선과 지역 조건을 읽는다."""
    nodes, edges = jsonl(GRAPH / "nodes.jsonl"), jsonl(GRAPH / "edges.jsonl")
    hier = [(e["from"], e["to"], e["type"]) for e in edges if e["type"] in ("WITHIN", "MEMBER_OF")]
    notice_open = {n["notice_id"]: bool(n["is_open"]) for n in nodes if n["label"] == "Notice"}
    cond_attr = {n["cond_id"]: n["attribute"] for n in nodes if n["label"] == "Condition"}
    req_notice = {e["to"]: e["from"] for e in edges if e["type"] == "HAS_REQUIREMENT"}
    cond_req = {e["to"]: e["from"] for e in edges if e["type"] == "HAS_CONDITION"}
    about = {e["from"]: e["to"] for e in edges if e["type"] == "ABOUT" and cond_attr.get(e["from"]) == "region"}
    notice_region = {}
    for cid, target in about.items():
        nid = req_notice[cond_req[cid]]
        if notice_open.get(nid):
            notice_region[nid] = target
    return hier, notice_region, nodes, edges


def make_profiles(rg: RegionGraph) -> list[str | None]:
    rng = random.Random(SEED)
    regions = sorted(r for r, n in rg.nodes.items() if n.get("level") in ("SIDO", "SIGUNGU", "GU"))
    return [rng.choice(regions + [None]) for _ in range(N_PROFILES)]


# ----------------------------------------------------------------------------- 구성 A·A2·A3 (SQLite)
def build_sql(hier, notice_region):
    db = sqlite3.connect(":memory:")
    db.executescript("""CREATE TABLE edge(child TEXT, parent TEXT, rel TEXT); CREATE INDEX edge_c ON edge(child); CREATE INDEX edge_p ON edge(parent);
                        CREATE TABLE notice_region(notice_id TEXT, target TEXT); CREATE INDEX nr_t ON notice_region(target);
                        CREATE TABLE closure(region TEXT, ancestor TEXT, hops INTEGER); CREATE INDEX cl_r ON closure(region); CREATE INDEX cl_a ON closure(ancestor);""")
    db.executemany("INSERT INTO edge VALUES (?,?,?)", hier)
    db.executemany("INSERT INTO notice_region VALUES (?,?)", notice_region.items())
    parents = defaultdict(list)
    for c, p, _ in hier:
        parents[c].append(p)
    rows = []
    for r in set(parents) | {p for ps in parents.values() for p in ps}:
        seen, frontier = {r: 0}, [r]
        for h in range(1, MAX_HOPS + 1):
            nxt = []
            for x in frontier:
                for p in parents.get(x, []):
                    if p not in seen:
                        seen[p] = h
                        nxt.append(p)
            frontier = nxt
        rows += [(r, a, h) for a, h in seen.items()]
    db.executemany("INSERT INTO closure VALUES (?,?,?)", rows)  # 폐쇄 테이블: 사전에 한 번 계산
    return db


SQL_A = """SELECT notice_id, 'SAT' FROM notice_region WHERE target = :u OR target = 'REGION:NATIONWIDE'"""
SQL_A2 = """SELECT notice_id, 'SAT' FROM notice_region n JOIN closure c ON n.target = c.ancestor WHERE c.region = :u
            UNION SELECT notice_id, 'UNK' FROM notice_region n JOIN closure c ON n.target = c.region WHERE c.ancestor = :u AND c.hops >= 1"""
SQL_A3 = """WITH RECURSIVE up(id, hops) AS (SELECT :u, 0 UNION SELECT e.parent, up.hops + 1 FROM edge e JOIN up ON e.child = up.id WHERE up.hops < 3),
                 down(id, hops) AS (SELECT :u, 0 UNION SELECT e.child, down.hops + 1 FROM edge e JOIN down ON e.parent = down.id WHERE down.hops < 3)
            SELECT notice_id, 'SAT' FROM notice_region WHERE target IN (SELECT id FROM up)
            UNION SELECT notice_id, 'UNK' FROM notice_region WHERE target IN (SELECT id FROM down WHERE hops >= 1)"""
SQL_NONE = """SELECT notice_id, 'SAT' FROM notice_region WHERE target = 'REGION:NATIONWIDE'"""


def run_sql(db, sql, region):
    rows = db.execute(SQL_NONE if region is None else sql, {} if region is None else {"u": region}).fetchall()
    return rows


# ----------------------------------------------------------------------------- 구성 G (Neo4j)
CYPHER_SAT = """MATCH (u:Concept {concept_id: $u})-[:WITHIN|MEMBER_OF*0..3]->(t:Concept)<-[:ABOUT]-(c:Condition {attribute: 'region'})
                <-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice {is_open: true}) RETURN DISTINCT n.notice_id AS id"""
CYPHER_UNK = """MATCH (t:Concept)-[:WITHIN|MEMBER_OF*1..3]->(u:Concept {concept_id: $u}) MATCH (t)<-[:ABOUT]-(c:Condition {attribute: 'region'})
                <-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice {is_open: true}) RETURN DISTINCT n.notice_id AS id"""
CYPHER_NONE = """MATCH (t:Concept {concept_id: 'REGION:NATIONWIDE'})<-[:ABOUT]-(c:Condition {attribute: 'region'})
                 <-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice {is_open: true}) RETURN DISTINCT n.notice_id AS id"""


def run_neo4j(session, region):
    """(SAT 집합, UNK 집합, 서버 처리 시간 ms). 왕복 시간은 호출 쪽 perf_counter에 들어 있다."""
    server = 0.0
    if region is None:
        r = session.run(CYPHER_NONE)
        sat = {x["id"] for x in r}
        s = r.consume()
        return sat, set(), (s.result_available_after or 0) + (s.result_consumed_after or 0)
    out = []
    for q in (CYPHER_SAT, CYPHER_UNK):
        r = session.run(q, u=region)
        out.append({x["id"] for x in r})
        s = r.consume()
        server += (s.result_available_after or 0) + (s.result_consumed_after or 0)
    return out[0], out[1] - out[0], server


# ----------------------------------------------------------------------------- 기준 C
def run_c(rg, cond_by_notice, region):
    prof = Profile(region=region)
    sat, unk = set(), set()
    for nid, cond in cond_by_notice.items():
        st = evaluate_condition(cond, prof, rg).status
        (sat if st == SAT else unk if st == UNK else set()).add(nid)
    return sat, unk


def to_status(universe, sat, unk):
    return {n: (SAT if n in sat else UNK if n in unk else UNSAT) for n in universe}


# ----------------------------------------------------------------------------- 정의→법령 경로(definition)
def definition_paths(nodes, edges, session):
    db = sqlite3.connect(":memory:")
    db.executescript("CREATE TABLE defined_by(concept TEXT, def TEXT); CREATE TABLE cites(def TEXT, article TEXT); CREATE TABLE part_of(article TEXT, law TEXT);"
                     "CREATE TABLE article(id TEXT, no TEXT); CREATE TABLE law(id TEXT, name TEXT); CREATE TABLE concept(id TEXT, name TEXT);")
    for e in edges:
        t = {"DEFINED_BY": "defined_by", "CITES_LAW": "cites", "PART_OF": "part_of"}.get(e["type"])
        if t:
            db.execute(f"INSERT INTO {t} VALUES (?,?)", (e["from"], e["to"]))
    for n in nodes:
        if n["label"] == "LawArticle":
            db.execute("INSERT INTO article VALUES (?,?)", (n["article_id"], n["article_no"]))
        elif n["label"] == "ExternalLaw":
            db.execute("INSERT INTO law VALUES (?,?)", (n["law_id"], n["name"]))
        elif n["label"] == "Concept":
            db.execute("INSERT INTO concept VALUES (?,?)", (n["concept_id"], n["name"]))
    sql = """SELECT c.name, a.no, l.name FROM defined_by d JOIN concept c ON c.id = d.concept JOIN cites x ON x.def = d.def
             JOIN article a ON a.id = x.article JOIN part_of p ON p.article = a.id JOIN law l ON l.id = p.law ORDER BY 1"""
    cypher = """MATCH (c:Concept)-[:DEFINED_BY]->(d:Definition)-[:CITES_LAW]->(a:LawArticle)-[:PART_OF]->(l:ExternalLaw)
                RETURN c.name AS concept, a.article_no AS art, l.name AS law ORDER BY concept"""
    t = time.perf_counter()
    sq = db.execute(sql).fetchall()
    t_sql = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    r = session.run(cypher)
    cy = [(x["concept"], x["art"], x["law"]) for x in r]
    t_cy = (time.perf_counter() - t) * 1000
    s = r.consume()
    return {"rows_sql": len(sq), "rows_cypher": len(cy), "same_result": sorted(sq) == sorted(cy), "sql_ms": round(t_sql, 2), "cypher_roundtrip_ms": round(t_cy, 2),
            "cypher_server_ms": (s.result_available_after or 0) + (s.result_consumed_after or 0), "sql_joins": 5, "cypher_hops": 3, "examples": sq[:3]}


# ----------------------------------------------------------------------------- 실행
def ping(session, n: int = PING_N) -> list[float]:
    """빈 질의(`RETURN 1`) 왕복 시간. 질의 한 번에 드는 네트워크·드라이버 고정 비용이다."""
    out = []
    for _ in range(n):
        t = time.perf_counter()
        session.run("RETURN 1").consume()
        out.append((time.perf_counter() - t) * 1000)
    return out


def main(argv: list[str] | None = None) -> int:
    import sync_graph_neo4j as L
    from neo4j import READ_ACCESS

    ap = argparse.ArgumentParser(description="SQL 대 그래프 비교 측정(읽기 전용)")
    ap.add_argument("--out", type=Path, help="결과 JSON 경로(기본: data/eval/compare_sql_graph_<날짜>_<aura|local>.json)")
    args = ap.parse_args(argv)

    hier, notice_region, nodes, edges = load_inputs()
    rg = RegionGraph()
    cleaned = load_cleaned(rg)
    cond_by_notice = {}
    for n in cleaned["notices"]:
        if n["notice_id"] in notice_region:
            cond_by_notice[n["notice_id"]] = next(c for c in n["conditions"] if c["attribute"] == "region")
    universe = sorted(notice_region)
    # 같은 스냅샷인지 확인: 그래프 파일의 지역 조건 대상과 정리층 평가 입력이 같아야 한다
    assert set(cond_by_notice) == set(notice_region), "그래프 파일과 정리층의 지역 조건 공고가 다르다"
    assert all(cond_by_notice[n]["value"]["concept_id"] == notice_region[n] for n in universe), "지역 조건 대상이 다르다"
    db = build_sql(hier, notice_region)
    profiles = make_profiles(rg)
    print(f"공고(모집 중, 지역 조건 있음) {len(universe):,}건, 프로필 {len(profiles)}개(지역 없음 {profiles.count(None)}), 간선 {len(hier)}개")

    driver, dbname, host = L.connect()
    sess = driver.session(database=dbname, default_access_mode=READ_ACCESS)
    arms = {"A": lambda r: run_sql(db, SQL_A, r), "A2": lambda r: run_sql(db, SQL_A2, r), "A3": lambda r: run_sql(db, SQL_A3, r)}
    times = {k: [] for k in ("A", "A2", "A3", "C", "G")}
    server_ms: list[float] = []
    mism = {k: 0 for k in ("A", "A2", "A3", "G")}
    mism_pairs = {k: Counter() for k in mism}
    examples = {k: [] for k in mism}
    hier_pairs = a_hier_sat = 0
    by_level = defaultdict(lambda: {k: 0 for k in ("profiles", "A", "A2", "A3", "G")})

    # 워밍업(측정에서 제외)
    for r in profiles[:WARMUP]:
        for f in arms.values():
            f(r)
        run_c(rg, cond_by_notice, r)
        run_neo4j(sess, r)
    ping(sess, 10)  # 워밍업
    ping_ms = ping(sess)
    location = "local" if host.split(":")[0] in LOCAL_HOSTS else "remote"
    print(f"Neo4j {host}({location}) 빈 질의 왕복 p50 {statistics.median(ping_ms):.2f}ms")

    for i, region in enumerate(profiles):
        level = rg.nodes[region]["level"] if region else "NONE"
        by_level[level]["profiles"] += 1
        res = {}
        for rep in range(REPEATS):
            for name, f in arms.items():
                t = time.perf_counter()
                rows = f(region)
                times[name].append((time.perf_counter() - t) * 1000)
                if rep == 0:
                    sat = {n for n, s in rows if s == "SAT"}
                    res[name] = (sat, {n for n, s in rows if s == "UNK"} - sat)
            t = time.perf_counter()
            c_sat, c_unk = run_c(rg, cond_by_notice, region)
            times["C"].append((time.perf_counter() - t) * 1000)
            t = time.perf_counter()
            g_sat, g_unk, srv = run_neo4j(sess, region)
            times["G"].append((time.perf_counter() - t) * 1000)
            server_ms.append(srv)
            if rep == 0:
                res["G"] = (g_sat, g_unk)
        ref = to_status(universe, c_sat, c_unk)
        for name in ("A", "A2", "A3", "G"):
            got = to_status(universe, *res[name])
            bad = [n for n in universe if got[n] != ref[n]]
            if bad:
                mism[name] += len(bad)
                by_level[level][name] += 1
                mism_pairs[name].update((ref[n], got[n]) for n in bad)
                if len(examples[name]) < 3:
                    examples[name].append({"profile_region": region, "notice": bad[0], "reference": ref[bad[0]], name: got[bad[0]]})
        if (i + 1) % 100 == 0:
            print(f"  프로필 {i + 1}/{len(profiles)} 완료")

    # A의 계층 Recall(N-04): 계층을 1 hop 이상 올라가야 충족되는 쌍 중 A가 충족으로 낸 비율. 시간 측정과 분리해 센다
    for region in profiles:
        if not region:
            continue
        anc = rg.ancestors(region)
        a_sat = {n for n, s in run_sql(db, SQL_A, region) if s == "SAT"}
        for n in universe:
            tgt = notice_region[n]
            if tgt != NATIONWIDE and anc.get(tgt, 99) >= 1 and anc.get(tgt, 99) <= MAX_HOPS:
                hier_pairs += 1
                a_hier_sat += n in a_sat

    definition = definition_paths(nodes, edges, sess)
    sess.close()
    driver.close()

    pairs = len(universe) * len(profiles)
    report = {
        "snapshot": {"graph_nodes": len(nodes), "graph_edges": len(edges), "notices_with_region_condition_open": len(universe), "profiles": len(profiles), "seed": SEED,
                     "repeats": REPEATS, "warmup_profiles": WARMUP, "neo4j_host": host,
                     "neo4j_location": location, "measured_on": time.strftime("%Y-%m-%d")},
        "hierarchy": {"pairs_checked_per_arm": pairs, "mismatch_vs_C": mism, "mismatch_status_pairs": {k: {f"{a}->{b}": v for (a, b), v in c.items()} for k, c in mism_pairs.items()},
                      "profiles_with_any_mismatch_by_region_level": {k: v for k, v in by_level.items()}, "mismatch_examples": examples,
                      "hierarchy_pairs_A_could_not_match": {"pairs_needing_hierarchy": hier_pairs, "A_found_sat": a_hier_sat,
                                                            "A_recall": round(a_hier_sat / hier_pairs, 4) if hier_pairs else None}},
        "latency_per_profile_query": {k: summarize(v) for k, v in times.items()},
        "neo4j_server_ms_per_profile": summarize(server_ms),
        "neo4j_ping_roundtrip_ms": summarize(ping_ms),
        "neo4j_queries_per_profile": {"with_region": 2, "without_region": 1},
        "definition_path": definition,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    path = args.out or OUT / f"compare_sql_graph_{time.strftime('%Y%m%d')}_{'local' if location == 'local' else 'aura'}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("저장:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
