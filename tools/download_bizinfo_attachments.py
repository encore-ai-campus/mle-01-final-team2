#!/usr/bin/env python3
"""기업마당 첨부 파일 내려받기 (로컬 전용, 표준 라이브러리만 사용).

- 용도: 교육 프로젝트 내부 분석. 원본 파일은 data/bizinfo/files/ 에만 저장하고 git에 올리지 않는다(.gitignore).
- 다운로드 URL에는 API 응답마다 새로 발급되는 downloadToken이 필요하다. 그래서 파일을 받기 전에
  API를 다시 호출해 토큰을 메모리에서만 사용하고, 매니페스트에는 토큰을 저장하지 않는다.
  토큰 유효 시간을 모르므로 --refresh-every 건마다, 그리고 실패했을 때 목록을 다시 받아 토큰을 갱신한다.
- 대상: 최근 parsed run의 공고. 기본은 시드 고정 무작위 N건(--n, 기본 30), --all 이면 전체.
  기본 파일은 공고마다 하나인 본문 출력 파일(PRINT_BODY). --role ATTACHMENT / ALL 로 바꿀 수 있다.
- 중단·실패 후에는 --resume <폴더>로 이어받는다(이미 받은 파일은 건너뛴다).
- 호출 간 대기를 두고(기본 1.0초) 한 번에 하나씩만 받는다.

사용 예:
    python tools/download_bizinfo_attachments.py --n 30
    python tools/download_bizinfo_attachments.py --all
    python tools/download_bizinfo_attachments.py --all --resume data/bizinfo/files/20261124_101500
    python tools/download_bizinfo_attachments.py --n 5 --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(_HERE), str(_HERE / "old")]  # collect_bizinfo.py가 tools/old로 옮겨진 경우도 찾는다
from collect_bizinfo import fetch_page  # noqa: E402

REPO = _HERE.parent  # collect_bizinfo.py의 REPO는 파일 위치에 따라 달라지므로 직접 계산한다
KST = timezone(timedelta(hours=9))
MAGIC = [(b"%PDF", "pdf"), (b"\xd0\xcf\x11\xe0", "hwp"), (b"PK\x03\x04", "zip/hwpx/xlsx"), (b"\x89PNG", "png"), (b"\xff\xd8\xff", "jpg")]
_SN = re.compile(r"fileSn=(\d+)")
_ID = re.compile(r"atchFileId=([A-Za-z0-9_]+)")


def load_key() -> str:
    import os
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


def sniff(head: bytes) -> str:
    for sig, name in MAGIC:
        if head.startswith(sig):
            return name
    if head.lstrip()[:1] == b"<":
        return "html(오류 페이지 가능)"
    return "unknown"


def safe(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|\r\n\t]', "_", name).strip()[:120]


def latest_parsed() -> Path:
    run = (REPO / "data" / "bizinfo" / "raw" / "LATEST").read_text(encoding="utf-8").strip()
    return REPO / "data" / "bizinfo" / "parsed" / run


def build_url_map(key: str, page_unit: int = 100) -> dict[str, dict]:
    """API를 다시 호출해 pblancId -> 원본 item(토큰 포함)을 만든다. 메모리에만 둔다."""
    out: dict[str, dict] = {}
    for idx in range(1, 40):
        data = fetch_page(key, idx, page_unit, {})
        items = data.get("jsonArray") or []
        for it in items:
            out[it["pblancId"]] = it
        if len(items) < page_unit:
            break
        time.sleep(1.0)
    return out


def download_one(item: dict, a: dict, max_bytes: int) -> tuple[dict, bytes | None]:
    """한 파일을 받는다. 반환: (결과 레코드, 본문 또는 None). 토큰은 레코드에 넣지 않는다."""
    rec = {"notice_id": a["notice_id"], "role": a["role"], "file_name": a["file_name"], "file_sn": a["file_sn"], "atch_file_id": a["atch_file_id"]}
    src = (item.get("printFlpthNm") if a["role"] == "PRINT_BODY" else item.get("flpthNm")) or ""
    fid = _ID.search(src).group(1) if _ID.search(src) else None
    tok = dict(re.findall(r"fileSn=(\d+)&downloadToken=([^&]+)", src)).get(str(a["file_sn"]))
    if not fid or tok is None:
        rec["status"] = "NO_URL_OR_TOKEN"
        return rec, None
    url = "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?" + urllib.parse.urlencode({"atchFileId": fid, "fileSn": a["file_sn"], "downloadToken": tok})
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "mle-team2-collector/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            ctype, clen = r.headers.get("Content-Type"), r.headers.get("Content-Length")
            if clen and int(clen) > max_bytes:
                rec.update(status="TOO_LARGE", content_length=int(clen))
                return rec, None
            body = r.read(max_bytes + 1)
    except (urllib.error.URLError, TimeoutError) as e:
        rec.update(status="ERROR", error=str(e).replace(tok, "***")[:120])
        return rec, None
    kind = sniff(body[:8])
    ok = not kind.startswith(("html", "unknown")) and len(body) > 0
    rec.update(status="OK" if ok else "INVALID_CONTENT", bytes=len(body), content_type=ctype, sniffed=kind,
               sha256=hashlib.sha256(body).hexdigest(), expected_ext=a["file_extension"])
    return rec, body if ok else None


def write_manifest(out: Path, args, sample_n: int, planned: int, results: list[dict], started: str, finished: bool) -> None:
    manifest = {"started_at": started, "updated_at": datetime.now(KST).isoformat(timespec="seconds"), "finished": finished,
                "seed": args.seed, "role": args.role, "all": bool(args.all), "sample_notices": sample_n, "files_planned": planned,
                "ok": sum(1 for r in results if r["status"] == "OK"),
                "by_status": {s: sum(1 for r in results if r["status"] == s) for s in sorted({r["status"] for r in results})},
                "note": "토큰은 저장하지 않음. 원본 파일은 로컬 전용(git 제외).", "results": results}
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--all", action="store_true", help="표본이 아니라 전체 공고")
    ap.add_argument("--notice", action="append", default=[], metavar="ID", help="이 공고만(공고 ID 끝자리 또는 전체 notice_id, 여러 번 지정 가능)")
    ap.add_argument("--seed", type=int, default=20261124)
    ap.add_argument("--role", choices=["PRINT_BODY", "ATTACHMENT", "ALL"], default="PRINT_BODY")
    ap.add_argument("--sleep", type=float, default=1.0)
    ap.add_argument("--max-mb", type=float, default=30.0, help="파일당 상한")
    ap.add_argument("--refresh-every", type=int, default=250, help="이 건수마다 API를 다시 받아 토큰을 갱신")
    ap.add_argument("--resume", help="이어받을 data/bizinfo/files/<run> 폴더")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    parsed = latest_parsed()
    atts = [json.loads(l) for l in (parsed / "attachments.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    by_notice: dict[str, list[dict]] = {}
    for a in atts:
        if args.role == "ALL" or a["role"] == args.role:
            by_notice.setdefault(a["notice_id"], []).append(a)

    pool = sorted(by_notice)
    if args.notice:
        pool = [p for p in pool if any(p == x or p.endswith(x) for x in args.notice)]
        if not pool:
            raise SystemExit("--notice에 맞는 공고가 없습니다.")
    sample = pool if (args.all or args.notice) else random.Random(args.seed).sample(pool, min(args.n, len(pool)))
    plan = [(nid, a) for nid in sample for a in by_notice[nid]]
    print(f"대상 공고 {len(sample)}건, 파일 {len(plan)}개 (role={args.role}, {'전체' if args.all else 'seed=' + str(args.seed)})", flush=True)
    if args.dry_run:
        for nid, a in plan[:10]:
            print(" ", nid[-6:], a["role"], a["file_extension"], a["file_name"][:50])
        return

    key = load_key()
    started = datetime.now(KST).isoformat(timespec="seconds")
    if args.resume:
        out = Path(args.resume)
        old = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
        results = [r for r in old["results"] if r["status"] == "OK" and (out / r["saved_as"]).exists()]
        started = old.get("started_at", started)
    else:
        out = REPO / "data" / "bizinfo" / "files" / datetime.now(KST).strftime("%Y%m%d_%H%M%S")
        results = []
    out.mkdir(parents=True, exist_ok=True)
    done = {(r["notice_id"], r["role"], r["file_sn"]) for r in results}
    todo = [(nid, a) for nid, a in plan if (nid, a["role"], a["file_sn"]) not in done]
    print(f"이미 받음 {len(results)}개, 이번에 받을 파일 {len(todo)}개 → {out}", flush=True)

    urlmap = build_url_map(key)
    since_refresh, fails_in_a_row = 0, 0
    max_bytes = int(args.max_mb * 1024 * 1024)
    try:
        for i, (nid, a) in enumerate(todo, 1):
            pid = nid.split(":", 1)[1]
            if since_refresh >= args.refresh_every:
                urlmap = build_url_map(key); since_refresh = 0
            item = urlmap.get(pid)
            if not item:
                rec = {"notice_id": nid, "role": a["role"], "file_name": a["file_name"], "file_sn": a["file_sn"], "status": "NOT_IN_CURRENT_API"}
                results.append(rec); print(f"[{i}/{len(todo)}] 목록에 없음 {pid[-6:]}", flush=True); continue
            rec, body = download_one(item, a, max_bytes)
            if body is None and rec["status"] in ("ERROR", "INVALID_CONTENT"):  # 토큰 만료 가능성: 목록을 다시 받아 한 번 재시도
                time.sleep(2)
                urlmap = build_url_map(key); since_refresh = 0
                if urlmap.get(pid):
                    rec, body = download_one(urlmap[pid], a, max_bytes); rec["retried_with_fresh_token"] = True
            since_refresh += 1
            if body is not None:
                fname = f"{pid[-6:]}_{a['file_sn']}_{safe(a['file_name'])}"
                (out / fname).write_bytes(body)
                rec["saved_as"] = fname
                fails_in_a_row = 0
            else:
                fails_in_a_row += 1
            results.append(rec)
            if i % 25 == 0 or body is None:
                print(f"[{i}/{len(todo)}] ok={sum(1 for r in results if r['status'] == 'OK')} 마지막={rec['status']} {pid[-6:]} {rec.get('sniffed', '')}", flush=True)
            if i % 50 == 0:
                write_manifest(out, args, len(sample), len(plan), results, started, False)
            if fails_in_a_row >= 5:
                print("연속 5건 실패로 중단합니다(--resume으로 이어받기 가능).", flush=True); break
            time.sleep(args.sleep)
    finally:
        write_manifest(out, args, len(sample), len(plan), results, started, len(results) >= len(plan))
    ok = sum(1 for r in results if r["status"] == "OK")
    print(f"완료: {out}  ok={ok}/{len(plan)}", flush=True)


if __name__ == "__main__":
    main()
