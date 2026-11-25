#!/usr/bin/env python3
"""기업마당 지원사업정보 API 수집기 (표준 라이브러리만 사용).

- 엔드포인트: https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do  (GET, JSON)
- 인증키: 환경변수 BIZINFO_API_KEY 또는 저장소 루트의 .env (값은 출력·저장하지 않는다)
- 공식 API는 마감되지 않은 공고만 제공한다. 전체 건수는 응답의 totCnt.
- 첨부 URL의 downloadToken 값은 저장 전에 [REDACTED]로 치환한다. 첨부 파일은 내려받지 않는다.

사용 예:
    python tools/collect_bizinfo.py                       # 전체 수집
    python tools/collect_bizinfo.py --max-pages 1         # 첫 페이지만(시험)
    python tools/collect_bizinfo.py --lclas 06 --hashtags 서울   # 분야·해시태그 필터

산출물: data/bizinfo/raw/<YYYYMMDD_HHMMSS>/page_001.json ..., manifest.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ENDPOINT = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
KST = timezone(timedelta(hours=9))
REPO = Path(__file__).resolve().parent.parent
TOKEN_RE = re.compile(r"(downloadToken=)[^&\"\s]+")


def load_key() -> str:
    key = os.environ.get("BIZINFO_API_KEY", "").strip()
    if key:
        return key
    env = REPO / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            m = re.match(r"\s*BIZINFO_API_KEY\s*=\s*(.*?)\s*$", line)
            if m:
                return m.group(1).strip().strip('"').strip("'")
    raise SystemExit("BIZINFO_API_KEY를 환경변수 또는 .env에서 찾지 못했습니다.")


def redact(obj):
    """응답 안의 다운로드 토큰을 지운다."""
    if isinstance(obj, str):
        return TOKEN_RE.sub(r"\1[REDACTED]", obj)
    if isinstance(obj, list):
        return [redact(x) for x in obj]
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    return obj


def fetch_page(key: str, page_index: int, page_unit: int, extra: dict, retries: int = 3) -> dict:
    params = {"crtfcKey": key, "dataType": "json", "pageUnit": str(page_unit), "pageIndex": str(page_index)}
    params.update(extra)
    url = ENDPOINT + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "mle-team2-collector/0.1"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8")
            if key in body:
                raise RuntimeError("응답 본문에 인증키가 포함되어 있어 중단합니다.")
            return json.loads(body)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            last = str(e).replace(key, "***")
            if attempt < retries:
                time.sleep(2 * attempt)
    raise SystemExit(f"페이지 {page_index} 수집 실패: {last}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(REPO / "data" / "bizinfo" / "raw"))
    ap.add_argument("--page-unit", type=int, default=100)
    ap.add_argument("--max-pages", type=int, default=50, help="안전 상한")
    ap.add_argument("--sleep", type=float, default=1.0, help="호출 간 대기(초)")
    ap.add_argument("--lclas", default="", help="분야 코드 searchLclasId (01 금융 02 기술 03 인력 04 수출 05 내수 06 창업 07 경영 09 기타)")
    ap.add_argument("--hashtags", default="", help="해시태그 필터(쉼표 구분)")
    args = ap.parse_args()

    key = load_key()
    extra = {}
    if args.lclas: extra["searchLclasId"] = args.lclas
    if args.hashtags: extra["hashtags"] = args.hashtags

    started = datetime.now(KST)
    run = started.strftime("%Y%m%d_%H%M%S")
    out = Path(args.out) / run
    out.mkdir(parents=True, exist_ok=True)

    pages, rows, ids, tot = [], 0, [], None
    for idx in range(1, args.max_pages + 1):
        data = redact(fetch_page(key, idx, args.page_unit, extra))
        items = data.get("jsonArray") or []
        if items and tot is None:
            try: tot = int(items[0].get("totCnt"))
            except (TypeError, ValueError): tot = None
        fname = f"page_{idx:03d}.json"
        text = json.dumps(data, ensure_ascii=False, indent=1)
        (out / fname).write_text(text, encoding="utf-8")
        pages.append({"file": fname, "items": len(items), "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()})
        rows += len(items)
        ids += [x.get("pblancId") for x in items]
        print(f"page {idx}: {len(items)}건 (누적 {rows}/{tot})")
        if not items or len(items) < args.page_unit or (tot is not None and rows >= tot):
            break
        time.sleep(args.sleep)

    uniq = len({i for i in ids if i})
    manifest = {
        "collected_at": started.isoformat(timespec="seconds"),
        "finished_at": datetime.now(KST).isoformat(timespec="seconds"),
        "endpoint": ENDPOINT,
        "query_conditions": {"dataType": "json", "pageUnit": args.page_unit, "pageIndex": f"1..{len(pages)}", **extra},
        "totCnt_reported": tot,
        "rows_retrieved": rows,
        "unique_pblancId": uniq,
        "duplicate_rows": rows - uniq,
        "complete": bool(tot is not None and rows >= tot),
        "pages": pages,
        "scope_note": "공식 API는 마감되지 않은 공고 범위만 제공. 인증키·다운로드 토큰은 저장하지 않음(downloadToken=[REDACTED]).",
    }
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (Path(args.out) / "LATEST").write_text(run, encoding="utf-8")
    print(f"완료: {out}  rows={rows} unique={uniq} totCnt={tot} complete={manifest['complete']}")
    if not manifest["complete"]:
        print("경고: 보고된 totCnt보다 적게 수집했습니다(--max-pages 확인).", file=sys.stderr)


if __name__ == "__main__":
    main()
