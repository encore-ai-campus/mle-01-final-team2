#!/usr/bin/env python3
"""서비스 경로의 그래프 지연 측정(KPI P-01). 서버(AWS)에서 Aura까지의 실제 왕복을 재려고 만든 도구다.

판정은 규칙 평가기가 같은 프로세스에서 하고, 그래프(Neo4j Aura)는 판정 근거를 붙이는 데만 쓴다. 그래서 요청 하나의
그래프 비용은 "근거를 받는 질의가 몇 번 왕복하느냐"로 거의 정해진다. 이 도구는 같은 입력으로 두 방식을 잰다.
  old  trace_path(condition_paths) + fetch_definition(definitions_for_notices) = 질의 2번
  new  근거 카드 evidence = 질의 1번 (api/repositories/graph.py, E1 실험의 카드)
또 후보 검색의 지역 질의(region_candidates)를 예전 3번(split)과 합친 1번(merged)으로 잰다. 이 질의는 지금 서비스가
부르지 않는다(후보 검색은 규칙 엔진). 후보 검색을 그래프로 옮길 때의 비용을 보려는 것이다.
두 방식의 결과가 같은지도 확인한다(경로·정의 행, 후보 집합). 다르면 종료 코드 1.

입력: 규칙 엔진으로 무작위 프로필(시드 고정)의 상위 5건을 뽑는다. 실제 요청과 같은 공고·조건 묶음이다.
시간: 워밍업 5회를 빼고 요청마다 잰 p50·p95. 빈 질의(RETURN 1) 왕복도 함께 적는다.

사용(쓰기 없음. .env 또는 환경 변수의 NEO4J_*):
  python tools/measure_service_latency.py --label local-pc        # 개발 PC → Aura
  python tools/measure_service_latency.py --label aws             # API 서버(AWS)에서 → Aura. 서비스 지연은 이 값을 쓴다
결과: data/eval/service_latency_<label>_<날짜>.json
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

SEED = 20261127
N_REQ = 60
WARMUP = 5
TOP = 5


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def summarize(ms: list[float]) -> dict:
    return {"n": len(ms), "p50_ms": round(statistics.median(ms), 1), "p95_ms": round(pct(ms, 0.95), 1), "mean_ms": round(statistics.mean(ms), 1)}


def timed(fn, *a):
    t = time.perf_counter()
    out = fn(*a)
    return out, (time.perf_counter() - t) * 1000


def old_rows(repo, region, notice_ids, region_cond_ids):
    """예전 방식: 경로 질의 + 정의 질의."""
    paths = repo.condition_paths(region, region_cond_ids)
    defs = repo.definitions_for_notices(notice_ids)
    return paths, defs


def comparable(paths, defs, cards, region):
    """두 방식의 결과를 같은 모양으로 맞춘다. 경로: 조건 → 노드 id 목록. 정의: (공고, 조건, 정의, 조항) 집합."""
    p_old = {p["cond_id"]: [n["id"] for n in p["nodes"]] if p["nodes"] else None for p in paths}
    want = set(p_old)
    p_new = {c["cond_id"]: [n["id"] for n in c["nodes"]] if c["nodes"] else None for c in cards if c["cond_id"] in want} if region else {}
    d_old = {(d["notice_id"], d["cond_id"], d["def_id"], d.get("article_id")) for d in defs}
    d_new = {(c["notice_id"], c["cond_id"], b["def_id"], b.get("article_id")) for c in cards for b in c.get("basis") or []}
    return (p_old, d_old), (p_new, d_new)


def main(argv: list[str] | None = None) -> int:
    from api.core.config import get_settings
    from api.repositories.graph import from_settings
    from graphrag.engine import Engine
    from graphrag.evaluator import Profile

    ap = argparse.ArgumentParser(description="서비스 경로 그래프 지연 측정(읽기 전용)")
    ap.add_argument("--label", required=True, help="어디서 쟀는지(local-pc, aws 등). 파일 이름에 들어간다")
    ap.add_argument("--n", type=int, default=N_REQ)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    repo = from_settings(get_settings())
    if repo is None:
        print("NEO4J_* 설정이 없습니다.")
        return 1
    eng = Engine()
    rng = random.Random(SEED)
    regions = sorted(r for r, n in eng.rg.nodes.items() if n.get("level") in ("SIDO", "SIGUNGU", "GU"))
    reqs = []
    while len(reqs) < args.n + WARMUP:
        region = rng.choice(regions)
        prof = Profile(region=region, business_age_years=rng.choice([None, 1, 3, 7]), applicant_type=rng.choice([None, "일반기업", "일반인"]))
        res = eng.query(prof, "", TOP)["results"]
        if res:
            ids = [r["notice_id"] for r in res]
            rc = [c.cond_id for r in res for c in r["conditions"] if c.attribute == "region"]
            reqs.append((region, ids, rc))

    t_ping, t_old, t_new, t_split, t_merged = [], [], [], [], []
    mism = {"evidence_paths": 0, "evidence_definitions": 0, "candidates": 0}
    examples = []
    for i, (region, ids, rc) in enumerate(reqs):
        _, a = timed(repo.ping)
        (paths, defs), b = timed(old_rows, repo, region, ids, rc)
        cards, c = timed(repo.evidence, ids, region)
        split, d = timed(repo.region_candidates_split, region)
        merged, e = timed(repo.region_candidates, region)
        (po, do), (pn, dn) = comparable(paths, defs, cards, region)
        bad = []
        if po != pn:
            mism["evidence_paths"] += 1
            bad.append("paths")
        if do != dn:
            mism["evidence_definitions"] += 1
            bad.append("definitions")
        if split != merged:
            mism["candidates"] += 1
            bad.append("candidates")
        if bad and len(examples) < 3:
            examples.append({"region": region, "notices": ids, "differs": bad,
                             "defs_only_old": sorted(map(str, do - dn))[:3], "defs_only_new": sorted(map(str, dn - do))[:3]})
        if i >= WARMUP:
            t_ping.append(a)
            t_old.append(b)
            t_new.append(c)
            t_split.append(d)
            t_merged.append(e)
    repo.close()

    report = {
        "label": args.label, "measured_on": time.strftime("%Y-%m-%d"), "requests": args.n, "warmup": WARMUP, "top": TOP, "seed": SEED,
        "neo4j_ping_ms": summarize(t_ping),
        "evidence_per_request": {"old_2_queries": summarize(t_old), "new_1_query": summarize(t_new)},
        "region_candidates": {"split_3_queries": summarize(t_split), "merged_1_query": summarize(t_merged)},
        "mismatched_requests": mism, "mismatch_examples": examples,
        "note": "규칙 판정(같은 프로세스)과 모델 설명 생성은 들어 있지 않다. 그래프 근거를 받는 비용만 잰다.",
    }
    out = args.out or ROOT / "data" / "eval" / f"service_latency_{args.label}_{time.strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ev, rc = report["evidence_per_request"], report["region_candidates"]
    print(f"[{args.label}] 빈 질의 왕복 p50 {report['neo4j_ping_ms']['p50_ms']}ms")
    print(f"  근거: 예전 2번 p50 {ev['old_2_queries']['p50_ms']}ms(p95 {ev['old_2_queries']['p95_ms']}) → 카드 1번 p50 {ev['new_1_query']['p50_ms']}ms(p95 {ev['new_1_query']['p95_ms']})")
    print(f"  후보 지역: 예전 3번 p50 {rc['split_3_queries']['p50_ms']}ms → 1번 p50 {rc['merged_1_query']['p50_ms']}ms")
    print(f"  결과 불일치 요청: {mism}")
    print("저장:", out)
    return 1 if any(mism.values()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
