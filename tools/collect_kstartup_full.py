#!/usr/bin/env python3
"""K-Startup 공고 API 전체를 페이지로 받아 저장하고, 접수 시작일 기준 최근 1년치를 따로 만든다 (표준 라이브러리만 사용).

왜 전체를 받나: 서버의 날짜 필터가 동작하지 않고, 공고 번호순(최신순)으로는 시작일이 최근인 오래된 번호의 공고를 놓친다
(예: 168638). 그래서 전체를 받아 시작일로 직접 거른다.

- 인증키는 .env의 `k_startup`에서 읽고 출력·저장하지 않는다.
- 첨부 정보는 API에 없고, 공고 상세 페이지·첨부 경로는 robots.txt가 금지하므로 접근하지 않는다.
- 출력(로컬 전용, Git 제외): data/kstartup/raw/<날짜>_full/announcements_all.jsonl, announcements_1y.jsonl, manifest.json

사용: python tools/collect_kstartup_full.py [--since 2025-11-24] [--per-page 500] [--sleep 0.4]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASE = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
KST = timezone(timedelta(hours=9))


def load_key() -> str:
    m = re.search(r'^\s*k_startup\s*=\s*"?([^"\n\r]+)', (REPO / ".env").read_text(encoding="utf-8"), re.M)
    if not m:
        sys.exit(".env에 k_startup 키가 없다")
    return m.group(1).strip()


def fetch(key: str, page: int, per: int, retries: int = 5) -> dict:
    q = urllib.parse.urlencode({"serviceKey": key, "page": page, "perPage": per, "returnType": "json"})
    err = None
    for t in range(retries):
        try:
            with urllib.request.urlopen(f"{BASE}?{q}", timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001  재시도 후 마지막 오류만 전달
            err = type(e).__name__
            time.sleep(2 * (t + 1))
    raise RuntimeError(f"page {page} 실패: {err}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", default="2025-11-24", help="접수 시작일 하한(YYYY-MM-DD)")
    ap.add_argument("--per-page", type=int, default=500)
    ap.add_argument("--sleep", type=float, default=0.4)
    args = ap.parse_args()
    key = load_key()
    started = datetime.now(KST)
    out = REPO / "data" / "kstartup" / "raw" / f"{started:%Y%m%d}_full"
    out.mkdir(parents=True, exist_ok=True)
    first = fetch(key, 1, args.per_page)
    total = first["totalCount"]
    pages = -(-total // args.per_page)
    rows = list(first["data"])
    print(f"totalCount={total}, pages={pages}", flush=True)
    for p in range(2, pages + 1):
        time.sleep(args.sleep)
        d = fetch(key, p, args.per_page)
        rows += d["data"]
        if p % 10 == 0 or p == pages:
            print(f"  page {p}/{pages} rows={len(rows)}", flush=True)
    # 완전성 검사
    sn = [str(r["pbanc_sn"]) for r in rows]
    uniq = len(set(sn))
    dup = len(sn) - uniq
    seen, all_rows = set(), []
    for r in rows:
        k = str(r["pbanc_sn"])
        if k not in seen:
            seen.add(k)
            all_rows.append(r)
    since = args.since.replace("-", "")
    one = [r for r in all_rows if (r.get("pbanc_rcpt_bgng_dt") or "") >= since]
    no_start = sum(1 for r in all_rows if not r.get("pbanc_rcpt_bgng_dt"))

    def dump(name: str, data: list[dict]) -> str:
        p = out / name
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            for r in data:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        return hashlib.sha256(p.read_bytes()).hexdigest()

    h_all, h_1y = dump("announcements_all.jsonl", all_rows), dump("announcements_1y.jsonl", one)
    snums = sorted(int(r["pbanc_sn"]) for r in one)
    manifest = {
        "collected_at": started.isoformat(timespec="seconds"), "finished_at": datetime.now(KST).isoformat(timespec="seconds"),
        "endpoint": BASE, "per_page": args.per_page, "pages": pages, "totalCount_reported": total, "rows_received": len(rows),
        "unique_pbanc_sn": uniq, "duplicate_rows": dup, "complete": len(rows) == total and dup == 0,
        "since_start_date": args.since, "rows_1y_by_start_date": len(one), "rows_without_start_date": no_start,
        "open_in_1y": sum(1 for r in one if r.get("rcrt_prgs_yn") == "Y"), "open_all": sum(1 for r in all_rows if r.get("rcrt_prgs_yn") == "Y"),
        "pbanc_sn_range_1y": [snums[0], snums[-1]] if snums else None,
        "start_year_distribution_1y": dict(sorted(Counter((r["pbanc_rcpt_bgng_dt"] or "")[:6] for r in one).items())),
        "sha256": {"announcements_all.jsonl": h_all, "announcements_1y.jsonl": h_1y},
        "note": "서버 날짜 필터 대신 전체를 받아 접수 시작일로 직접 계산. 인증키는 저장하지 않음. 첨부 정보 없음(API에 칸이 없고 robots.txt가 첨부 경로를 금지).",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in manifest.items() if k not in ("sha256", "start_year_distribution_1y")}, ensure_ascii=False, indent=1))
    print("저장:", out)


if __name__ == "__main__":
    main()
