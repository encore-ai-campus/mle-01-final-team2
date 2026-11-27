#!/usr/bin/env python3
"""정답셋(요건 정규화·판정) 후보 공고를 선정한다 (표준 라이브러리만 사용).

- 기업마당: 수집·추출을 마친 1,294건 중 라벨링할 수 있는 공고를 뽑는다(parsed + extracted 결과 사용).
- K-Startup: 동료가 만든 neo4j_import.json의 K-Startup 30건 중에서 뽑는다(우리 쪽에는 K-Startup 수집기가 없다).
- 방식: 시드를 고정한 '특징별 최소 건수 + 다양성' 탐욕 선택. 모집단과 제외 건수, 입력 파일 해시를 보고서에 남긴다.
- 선정은 라벨링 대상 후보일 뿐이다. 특징은 정규식 힌트이며 정답이 아니다(라벨러가 원문을 읽고 확인한다).
- 결과 파일에는 공고 본문을 넣지 않는다(ID·메타·특징·로컬 파일 경로만).

사용 예:
    python tools/select_goldset_candidates.py
    python tools/select_goldset_candidates.py --seed 20261124 --bizinfo 15 --kstartup 15
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOT = REPO / "data" / "bizinfo"
CENTRAL_SUFFIX = ("부", "청", "처", "위원회", "원")  # 중앙행정기관 이름 끝(힌트)

PAT = {
    "age": r"만\s*\d+\s*세",
    "bizage": r"(업력|창업|설립)[^\n]{0,15}\d+\s*년|\d+\s*년\s*(이내|미만|이하)",
    "local": r"(소재|관내|거주|본사)",
    "track": r"(트랙|유형\s*[ⅠⅡⅢ1-3①②]|[ⅠⅡⅢ]\s*유형|분야별|대상별|기업\s*유형|지원\s*유형|\([1-3]\)\s*[가-힣]+기업)",
    "nofm": r"(\d+\s*(개|가지)\s*(중|이상))|중\s*\d+\s*(개|가지)\s*이상|하나\s*이상|1개\s*이상",
    "law": r"[「『][^」』]+[」』]",
    "indiv": r"(근로자|재직자|구직|취업자|실업자|퇴직)",
}
OPEN_RX = re.compile(r"등\s*(\)|$|\n|의|을|이)")
KST_FULL_BIZAGE = {"예비창업자", "1년미만", "2년미만", "3년미만", "5년미만", "7년미만", "10년미만"}
KST_AGE_RANGES = ["만 20세 미만", "만 20세 이상 ~ 만 39세 이하", "만 40세 이상"]


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


# ---------------------------------------------------------------- 선택 알고리즘
def greedy_select(cands: list[dict], k: int, targets: dict[str, int], div_keys: list[str], rng: random.Random,
                  caps: dict[str, int] | None = None) -> list[dict]:
    """특징별 최소 건수(targets)를 우선 채우고, 같은 값이 반복되지 않도록 다양성 보너스를 준다. caps는 특징별 최대 건수."""
    chosen: list[dict] = []
    seen: dict[str, collections.Counter] = {d: collections.Counter() for d in div_keys}
    have = collections.Counter()
    pool = list(cands)
    rng.shuffle(pool)  # 동점일 때 시드 고정 무작위
    caps = caps or {}
    while pool and len(chosen) < k:
        pool = [c for c in pool if all(not c["tags"].get(t) or have[t] < m for t, m in caps.items())]
        if not pool:
            break
        have_tags = set(targets) | set(caps)
        def score(c: dict) -> float:
            s = sum(max(targets[t] - have[t], 0) * 10 for t in targets if c["tags"].get(t))
            s += sum(1.0 / (1 + seen[d][c.get(d)]) for d in div_keys)
            return s
        best = max(pool, key=score)
        pool.remove(best)
        chosen.append(best)
        for t in have_tags:
            if best["tags"].get(t):
                have[t] += 1
        for d in div_keys:
            seen[d][best.get(d)] += 1
    return chosen


# ---------------------------------------------------------------- 기업마당
def load_bizinfo(run_parsed: str, run_files: str) -> tuple[list[dict], dict]:
    notices = {}
    for ln in (ROOT / "parsed" / run_parsed / "notices.jsonl").read_text(encoding="utf-8").splitlines():
        if ln.strip():
            r = json.loads(ln); notices[r["notice_id"]] = r
    ext = json.loads((ROOT / "extracted" / run_files / "extraction_report.json").read_text(encoding="utf-8"))
    excluded = collections.Counter()
    out = []
    for it in ext["items"]:
        n = notices.get(it.get("notice_id"))
        if not n:
            excluded["no_parsed_notice"] += 1; continue
        if it["status"] != "OK":  # 일반 추출만. OCR·배포용·오류 공고는 정답 작성이 어려워 제외한다
            excluded["not_plain_text_extract:" + it["status"]] += 1; continue
        if not (1200 <= it["chars"] <= 20000):
            excluded["text_length_out_of_range"] += 1; continue
        text = (ROOT / "extracted" / run_files / it["text_file"]).read_text(encoding="utf-8")
        first = n["eligibility_criteria_text"] or ""
        if re.search(PAT["indiv"], first + n["title"]):
            excluded["individual_target_hint(D-5)"] += 1; continue
        tags = {
            "age": bool(re.search(PAT["age"], text)), "bizage": bool(re.search(PAT["bizage"], text)),
            "local": bool(re.search(PAT["local"], first)) or bool(n["jurisdiction_sido_code"]),
            "track": bool(re.search(PAT["track"], text)), "nofm": bool(re.search(PAT["nofm"], text)),
            "open": bool(OPEN_RX.search(first)),
            "law5": len(re.findall(PAT["law"], text)) >= 5,
            "excl": any(s["label"] == "EXCLUSION" for s in it["sections"]),
            "date": n["apply_status_kind"] == "DATE_RANGE",
            "non_date": n["apply_status_kind"] != "DATE_RANGE",
            "fmt_pdf": it["format"] == "pdf", "fmt_hwp": it["format"] == "hwp", "fmt_hwpx": it["format"] == "hwpx",
            "central": (not n["jurisdiction_sido_code"]) and n["jurisdiction_org_name"].endswith(CENTRAL_SUFFIX),
            "basic_local_gov": n["executor_kind"] == "LOCAL_GOVERNMENT_UNSPECIFIED",
        }
        tags["nofm_or_open"] = tags["nofm"] or tags["open"]
        tags["age_or_bizage"] = tags["age"] or tags["bizage"]
        tags["local_date"] = tags["local"] and tags["date"]
        tags["excl_and_cond"] = tags["excl"] and tags["age_or_bizage"]
        out.append({
            "source": "BIZINFO", "notice_id": n["notice_id"], "title": n["title"], "org": n["jurisdiction_org_name"],
            "published_at": (n["published_at"] or "")[:10], "deadline": n["application_end_date"] or n["deadline_raw"],
            "period_kind": n["apply_status_kind"], "format": it["format"], "chars": it["chars"],
            "support": n["support_category_major"], "executor_kind": n["executor_kind"], "url": n["detail_url"],
            "local_text": str(Path("data/bizinfo/extracted") / run_files / it["text_file"]),
            "local_original": str(Path("data/bizinfo/files") / run_files / it["file"]), "tags": tags,
        })
    return out, dict(excluded)


# ---------------------------------------------------------------- K-Startup
def load_kstartup(path: Path) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    out, excluded = [], collections.Counter()
    for n in data["notices"]:
        if n["source_system"] != "KSTARTUP":
            continue
        elig = n.get("eligibility_criteria_text") or ""
        biz = set((n.get("business_age_criteria_text") or "").split(",")) - {""}
        age = n.get("age_criteria_text") or ""
        region = (n.get("region_text") or "").strip()
        tags = {
            "region_specific": region not in ("", "전국"), "nationwide": region == "전국",
            "bizage_restricted": bool(biz) and biz != KST_FULL_BIZAGE,
            "age_restricted": bool(age) and not all(r in age for r in KST_AGE_RANGES),
            "track": bool(re.search(r"(트랙|유형|[①②③]|\([1-3]\)|\n-)", elig)),
            "open": bool(OPEN_RX.search(elig)), "trivial": len(elig) < 25,
            "long_elig": len(elig) >= 100,
        }
        out.append({
            "source": "KSTARTUP", "notice_id": n["notice_id"], "title": n["title"], "org": n.get("department_name") or "",
            "published_at": "", "deadline": n.get("application_end_date") or n.get("deadline_raw"), "period_kind": "DATE_RANGE" if n.get("application_end_date") else "",
            "format": "api_text", "chars": len(elig), "support": n.get("support_category") or "", "executor_kind": n.get("supervising_org_type") or "",
            "url": n.get("detail_url"), "local_text": "", "local_original": "", "tags": tags,
        })
    return out, dict(excluded)


# ---------------------------------------------------------------- 실행
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=20261124)
    ap.add_argument("--bizinfo", type=int, default=15)
    ap.add_argument("--kstartup", type=int, default=15)
    ap.add_argument("--backup", type=int, default=10, help="출처별 예비 후보 수")
    ap.add_argument("--pilot", type=int, default=5, help="출처별 파일럿(1단계 일치율 측정) 건수")
    ap.add_argument("--kstartup-json", required=True,
                    help="Path to the shared neo4j_import.json input (use a path valid on the current OS)")
    ap.add_argument("--out", default=str(REPO / "data" / "goldset"))
    args = ap.parse_args()

    run_parsed = (ROOT / "raw" / "LATEST").read_text(encoding="utf-8").strip()
    run_files = sorted(p.name for p in (ROOT / "extracted").iterdir() if p.is_dir())[-1]
    rng = random.Random(args.seed)

    biz, biz_ex = load_bizinfo(run_parsed, run_files)
    kst, _ = load_kstartup(Path(args.kstartup_json))

    biz_targets = {"nofm_or_open": 2, "track": 2, "law5": 2, "excl_and_cond": 3, "age_or_bizage": 4, "local_date": 2, "central": 2,
                   "basic_local_gov": 2, "non_date": 4, "fmt_pdf": 3, "fmt_hwp": 3, "fmt_hwpx": 3}
    kst_targets = {"region_specific": 6, "nationwide": 1, "bizage_restricted": 4, "age_restricted": 3, "track": 2, "open": 1, "trivial": 1, "long_elig": 3}
    biz_sel = greedy_select(biz, args.bizinfo, biz_targets, ["org", "support", "executor_kind"], rng)
    biz_rest = [c for c in biz if c not in biz_sel]
    biz_bak = greedy_select(biz_rest, args.backup, {k: 1 for k in ("track", "excl_and_cond", "age_or_bizage", "nofm_or_open")}, ["org", "support"], rng)
    kst_sel = greedy_select(kst, args.kstartup, kst_targets, ["executor_kind", "org"], rng, caps={"trivial": 2})  # 조건이 거의 없는 공고는 최대 2건
    kst_rest = [c for c in kst if c not in kst_sel]
    kst_bak = greedy_select(kst_rest, min(args.backup, len(kst_rest)), {"region_specific": 2, "bizage_restricted": 2}, ["executor_kind"], rng)

    def pilot(sel: list[dict], n: int) -> set[str]:
        """파일럿(1단계 일치율 측정): 조건이 실제로 있고(trivial 제외) 특징이 다양하며 너무 길지 않은 공고.
        라벨링 규칙의 모호한 곳을 빨리 찾는 것이 목적이라 조건이 없는 공고는 쓰지 않는다."""
        def key(c):
            feats = sum(v for k, v in c["tags"].items() if not k.startswith("fmt_"))
            too_long = c["source"] == "BIZINFO" and c["chars"] > 9000  # 첨부 본문이 너무 길면 파일럿 라벨링이 오래 걸린다
            return (bool(c["tags"].get("trivial")), too_long, -feats, c["chars"])
        return {c["notice_id"] for c in sorted(sel, key=key)[:n]}
    pilots = pilot(biz_sel, args.pilot) | pilot(kst_sel, args.pilot)

    rows = []
    for role, group in (("PRIMARY", biz_sel + kst_sel), ("BACKUP", biz_bak + kst_bak)):
        for c in group:
            r = "PILOT" if (role == "PRIMARY" and c["notice_id"] in pilots) else role
            rows.append({**{k: c[k] for k in ("source", "notice_id", "title", "org", "published_at", "deadline", "period_kind", "format", "chars",
                                               "support", "executor_kind", "url", "local_text", "local_original")},
                         "role": r, "features": ";".join(sorted(k for k, v in c["tags"].items() if v))})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cols = ["role", "source", "notice_id", "title", "org", "support", "executor_kind", "published_at", "deadline", "period_kind", "format", "chars", "features", "url", "local_text", "local_original"]
    with open(out / "candidates_v0.1.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

    def cover(sel, keys): return {k: sum(1 for c in sel if c["tags"].get(k)) for k in keys}
    report = {
        "seed": args.seed, "inputs": {"bizinfo_parsed_run": run_parsed, "bizinfo_extracted_run": run_files,
                                      "notices_sha256": sha256(ROOT / "parsed" / run_parsed / "notices.jsonl"),
                                      "extraction_report_sha256": sha256(ROOT / "extracted" / run_files / "extraction_report.json"),
                                      "kstartup_json": Path(args.kstartup_json).name, "kstartup_json_sha256": sha256(Path(args.kstartup_json))},
        "pool": {"bizinfo_total_notices": 1294, "bizinfo_eligible_pool": len(biz), "bizinfo_excluded": biz_ex, "kstartup_pool": len(kst)},
        "selected": {"bizinfo_primary": len(biz_sel), "bizinfo_backup": len(biz_bak), "kstartup_primary": len(kst_sel), "kstartup_backup": len(kst_bak), "pilot": len(pilots)},
        "targets": {"bizinfo": biz_targets, "kstartup": kst_targets},
        "coverage_bizinfo_primary": cover(biz_sel, biz_targets), "coverage_kstartup_primary": cover(kst_sel, kst_targets),
        "pool_feature_counts_bizinfo": cover(biz, biz_targets),
        "diversity_bizinfo_primary": {"orgs": len({c['org'] for c in biz_sel}), "support": dict(collections.Counter(c["support"] for c in biz_sel)),
                                      "format": dict(collections.Counter(c["format"] for c in biz_sel)), "period_kind": dict(collections.Counter(c["period_kind"] for c in biz_sel))},
        "diversity_kstartup_primary": {"supervising": dict(collections.Counter(c["executor_kind"] for c in kst_sel))},
        "note": "특징은 정규식·필드 기반 힌트이며 정답이 아니다. 후보 교체는 가이드라인의 교체 규칙을 따른다.",
    }
    (out / "selection_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("pool", "selected", "coverage_bizinfo_primary", "coverage_kstartup_primary", "diversity_bizinfo_primary", "diversity_kstartup_primary")}, ensure_ascii=False, indent=2))
    print("출력:", out)


if __name__ == "__main__":
    main()
