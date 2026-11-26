#!/usr/bin/env python3
"""검수 패킷 50건(2-4 정답셋)의 준비표를 만든다. 정답이나 판정은 채우지 않는다.

- 개발용(30건): 원문, 공고 링크, 기존 추출 후보(조건·논리 그룹), 원문에서 찾은 확인 포인트(제외·연결어·숫자 표현)
- 평가용(20건): 블라인드라 원문과 링크만 넣는다. 기존 후보와 확인 포인트는 넣지 않는다(검수 가이드의 분리 원칙)

사용: python tools/make_review_prep.py   -> docs/REVIEW_검수패킷_준비표_v0.1.md
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKETS = ROOT / "data" / "goldsets" / "conditions" / "v1" / "20261125"
NOTICES = ROOT / "data" / "cleaned" / "20261124" / "notices.jsonl"
OUT = ROOT / "docs" / "REVIEW_검수패킷_준비표_v0.1.md"

# 원문에서 사람이 놓치기 쉬운 표현. 정답이 아니라 "여기를 보라"는 표시다
WATCH = [
    ("제외", r"제외|불가|불가능|제한|해당하지|아닌 자|아닌 기업|참여할 수 없"),
    ("단서", r"단[,\s]|다만|※"),
    ("또는", r"또는|혹은|이나\b|거나"),
    ("및", r"및|그리고|모두"),
    ("수량", r"\d+\s*(년|세|억|만원|원|%|명|개월|인)"),
    ("경계", r"이상|이하|미만|이내|초과"),
    ("기준일", r"공고일|마감일|신청일|접수일|기준"),
    ("우대", r"우대|가점|우선"),
]


def jsonl(path: Path) -> list[dict]:
    # splitlines()는 원문 안의 U+2028 같은 문자에서도 잘라 JSON이 깨진다. 줄바꿈 문자로만 나눈다
    return [json.loads(x) for x in path.read_text(encoding="utf-8").split("\n") if x.strip()] if path.exists() else []


def cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", "<br>").strip()


def watch_points(text: str) -> list[str]:
    return [name for name, rx in WATCH if re.search(rx, text or "")]


def candidates(row: dict) -> str:
    out = []
    for c in row.get("existing_candidates", []):
        v = c.get("value")
        v = ", ".join(map(str, v)) if isinstance(v, list) else v
        out.append(f"{c.get('condition_type', '')[:4]} {c.get('field') or c.get('category_id')} {c.get('operator')} {v}")
    return "<br>".join(cell(x) for x in out) or "없음"


def logic_hint(row: dict | None) -> str:
    if not row:
        return "—"
    groups = row.get("existing_relation_candidates", [])
    if not groups:
        return "후보 없음"
    return "<br>".join(f"{g.get('operator_candidate')} ({g.get('hint_status')}, 조건 {len(g.get('condition_ids', []))}개)" for g in groups)


def build() -> str:
    notices = {n["notice_id"]: n for n in jsonl(NOTICES)}
    lines = ["# 검수 패킷 준비표 v0.1", "",
             "| 항목 | 내용 |", "|---|---|",
             "| 목적 | 검수 패킷 50건(`data/goldsets/conditions/v1/20261125/`)을 검수하기 전에 원문·링크·기존 후보를 한 장에 모았다. **정답이나 판정은 채우지 않았다** |",
             "| 만든 방법 | `python tools/make_review_prep.py`. 패킷 JSONL과 정리층 공고(`data/cleaned/20261124/notices.jsonl`)를 읽는다 |",
             "| 검수 순서 | 1) 팀 회의에서 D-1·D-2를 정한다(`docs/MEETING_판정규칙_결정시트_2026-11-27.md`) → 2) 이 표로 원문을 확인한다 → 3) `condition_review.jsonl`·`logic_review.jsonl`을 고친다(CSV는 읽기용) → 4) `python tools/ingest_condition_gold_reviews.py --split development`(평가용은 `evaluation`) |",
             "| 가이드 | `docs/CONDITION_GOLDSET_REVIEW_GUIDE_V1.md`. 검수 완료 행만 `review_status=VERIFIED`, 검수자·검수일 기록 |",
             "| 확인 포인트 | 원문에 있는 표현을 규칙으로 표시만 했다(제외·단서·또는·및·수량·경계·기준일·우대). 조건이 그 표현에 있다는 뜻은 아니다 |",
             "| 평가용 | **블라인드.** 기존 추출 후보와 확인 포인트를 넣지 않았다. 원문과 링크만 있다 |",
             ""]
    for split in ("development", "evaluation"):
        rows = jsonl(PACKETS / split / "condition_review.jsonl")
        logic = {r["notice_id"]: r for r in jsonl(PACKETS / split / "logic_review.jsonl")}
        dev = split == "development"
        src = Counter(r["source_system"] for r in rows)
        status = Counter(r["review_status"] for r in rows)
        lines += [f"## {'개발용' if dev else '평가용'} {len(rows)}건", "",
                  f"출처 {', '.join(f'{k} {v}' for k, v in sorted(src.items()))}. 검수 상태 {', '.join(f'{k} {v}' for k, v in status.items())}. "
                  f"원문 합계 {sum(len(r['source_text']) for r in rows):,}자.", ""]
        if dev:
            wp = Counter(w for r in rows for w in watch_points(r["source_text"]))
            n_c = sum(len(r.get("existing_candidates", [])) for r in rows)
            fields = Counter((c.get("field") or "미분류") for r in rows for c in r.get("existing_candidates", []))
            lines += [f"기존 조건 후보 {n_c}개({', '.join(f'{k} {v}' for k, v in fields.most_common())}). "
                      f"확인 포인트가 있는 패킷: {', '.join(f'{k} {v}' for k, v in wp.most_common())}.", "",
                      "| # | 공고 | 원문(발췌) | 기존 조건 후보 | 논리 후보 | 확인 포인트 | 메모 |", "|---:|---|---|---|---|---|---|"]
        else:
            lines += ["| # | 공고 | 원문(발췌) | 메모 |", "|---:|---|---|---|"]
        for i, r in enumerate(rows, 1):
            n = notices.get(r["notice_id"], {})
            title = cell(n.get("title", ""))[:60]
            link = f"[{r['notice_id']}]({n['detail_url']})" if n.get("detail_url") else r["notice_id"]
            head = f"{link}<br>{title}" + (f"<br>마감 {n['deadline']}" if n.get("deadline") else "")
            if dev:
                lines.append(f"| {i} | {head} | {cell(r['source_text'])} | {candidates(r)} | {logic_hint(logic.get(r['notice_id']))} | "
                             f"{', '.join(watch_points(r['source_text'])) or '—'} | |")
            else:
                lines.append(f"| {i} | {head} | {cell(r['source_text'])} | |")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    OUT.write_text(build(), encoding="utf-8")
    print(OUT)
