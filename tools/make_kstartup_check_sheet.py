#!/usr/bin/env python3
"""K-Startup 공고 10건의 'API 텍스트 vs 상세 페이지·첨부' 수동 비교 시트를 만든다 (표준 라이브러리만 사용).

목적: API 텍스트만으로 요건 정보가 충분한지, 상세 페이지·첨부(공고문)에 얼마나 더 있는지를 사람이 직접 확인한다.
- K-Startup은 robots.txt가 공고 HTML과 첨부 경로를 막으므로 이 확인은 **사람이 브라우저로 직접** 한다(자동 수집 금지).
- 표본: 최근(2026-01 이후 접수 시작) 공고에서 시드 고정으로 뽑는다.
  '본문에 첨부·붙임·공고문 참조 문구가 있는 공고 5건' + '없는 공고 5건', 모집 중 4건 + 종료 6건, 주관 유형을 고르게.
- 출력: data/goldset/kstartup_api_vs_page_check_v0.1.csv (Excel에서 열 수 있게 UTF-8 BOM)

사용 예:
    python tools/make_kstartup_check_sheet.py --jsonl data/kstartup/processed/kstartup_cleaned.jsonl
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MENTION = re.compile(r"(첨부|붙임|별첨|별지)|(공고문|모집공고|상세\s*내용|자세한\s*(내용|사항)|세부\s*(내용|사항))[^\n]{0,15}(참조|참고|확인)")


def clean(s: str | None, n: int) -> str:
    s = re.sub(r"\r\n?", "\n", s or "").strip()
    return s if len(s) <= n else s[:n] + " …(이하 생략)"


def pick(pool: list[dict], k: int, n_open: int, rng: random.Random) -> list[dict]:
    rng.shuffle(pool)
    chosen, seen = [], collections.Counter()
    for want_open, cnt in ((True, n_open), (False, k - n_open)):
        cands = [r for r in pool if (r["application_status_raw"] == "Y") == want_open and r not in chosen]
        for _ in range(cnt):
            if not cands:
                break
            best = max(cands, key=lambda r: 1 / (1 + seen[r["source_api_fields"]["sprv_inst"]]))
            cands.remove(best); chosen.append(best); seen[best["source_api_fields"]["sprv_inst"]] += 1
    return chosen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--jsonl", default=str(REPO / "data" / "kstartup" / "processed" / "kstartup_cleaned.jsonl"))
    ap.add_argument("--seed", type=int, default=20261124)
    ap.add_argument("--out", default=str(REPO / "data" / "goldset" / "kstartup_api_vs_page_check_v0.1.csv"))
    args = ap.parse_args()

    # str.splitlines()는 문자열 안의  ·\x0b 같은 문자에서도 줄을 나눠 JSONL이 깨지므로 \n으로만 나눈다
    rows = [json.loads(l) for l in Path(args.jsonl).read_text(encoding="utf-8").split("\n") if l.strip()]
    recent = [r for r in rows if r["application_start"] >= "2026-01-01" and len(r["eligibility_text"] or "") >= 20]
    text = lambda r: "\n".join([r["eligibility_text"] or "", r["announcement_body"] or "", r["support_details"] or "", r["evaluation_criteria"] or ""])
    mention = [r for r in recent if MENTION.search(text(r))]
    silent = [r for r in recent if not MENTION.search(text(r))]
    rng = random.Random(args.seed)
    sel = [("있음", r) for r in pick(mention, 5, 2, rng)] + [("없음", r) for r in pick(silent, 5, 2, rng)]

    cols = ["번호", "공고ID", "제목", "주관기관", "주관 유형", "모집 상태", "접수 시작", "접수 마감", "API 첨부·공고문 참조 문구", "상세 페이지 링크", "안내 URL(원본 필드)",
            "API 자격 문구", "API 업력 값", "API 연령 값", "API 지역 값", "API 공고 본문", "API 지원내용", "API 평가 방법",
            # --- 아래는 사람이 상세 페이지·첨부를 열어 채운다 ---
            "상세 페이지가 열림(Y/N)", "첨부파일 있음(Y/N)", "첨부 파일명(쉼표 구분)", "첨부 열람 가능(Y/N/로그인 필요)",
            "API에 없는 자격 요건이 페이지·첨부에 있음(Y/N)", "API에 없는 제외 요건 있음(Y/N)", "API에 없는 평가·선정 기준 있음(Y/N)",
            "API에 없는 제출 서류·한도·기간 있음(Y/N)", "API와 다르게 적힌 내용 있음(Y/N)", "추가로 확인된 요건 요약(원문 그대로 1~2문장)", "확인자", "확인일", "메모"]
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for i, (m, r) in enumerate(sel, 1):
            s = r["source_api_fields"]
            w.writerow([i, r["announcement_id"], r["title"], r["organization"], s.get("sprv_inst"),
                        "모집 중" if r["application_status_raw"] == "Y" else "종료", r["application_start"], r["application_end"], m,
                        s.get("detl_pg_url"), s.get("biz_gdnc_url") or "",
                        clean(r["eligibility_text"], 800), r["business_age_raw"], s.get("biz_trgt_age") or "", r["support_region_raw"],
                        clean(r["announcement_body"], 1000), clean(r["support_details"], 600), clean(r["evaluation_criteria"], 500)] + [""] * (len(cols) - 18))
    print(f"출력: {out}  ({len(sel)}건)")
    for i, (m, r) in enumerate(sel, 1):
        print(i, r["announcement_id"], "모집중" if r["application_status_raw"] == "Y" else "종료", r["source_api_fields"]["sprv_inst"], f"참조문구{m}", f"자격{len(r['eligibility_text'])}자 본문{len(r['announcement_body'] or '')}자", r["title"][:30])


if __name__ == "__main__":
    main()
