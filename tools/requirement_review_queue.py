"""REQ_UNPARSED 공고의 본문 요건 검수 큐(결정 B-3 ②: 모델·규칙 추출 후 사람 검수). 설계: docs/DESIGN_요건검수큐_v0.1.md

  build   서비스 공고 중 본문 요건이 검수되지 않은 공고(text_requirements≠reviewed)를 큐 행으로 만든다.
          원문은 자격·제외 구역(공고 요약 신청 자격, 첨부 신청 자격·제외 대상)을 이어 붙인 글이고,
          규칙 추출 후보(tools/graphrag/extract_req)와 선택적으로 모델 추출 후보(--proposals)를 '사전 채움'으로 싣는다.
          사전 채움은 검수 전 후보다. 판정에 쓰지 않는다(decision_possible=false).
  ingest  사람이 VERIFIED로 바꾼 행만 검사해 gold_bridge가 읽는 모양(reviewed_condition_gold.jsonl·reviewed_logic_gold.jsonl)으로 쓴다.
          검사에 걸린 행은 건너뛰고 사유를 보고서에 남긴다(fail-closed, 행 단위).
  status  큐 상태 집계.

- 큐와 검수 결과는 골든셋(data/goldsets)과 섞지 않는다. 서비스 검수 결과는 평가 정답으로 쓰지 않는다.
- 첨부에서 추출한 원문을 담으므로 data/reviews/는 git에 올리지 않는다(로컬 전용).
- 다시 build해도 사람이 손댄 행(UNREVIEWED가 아니거나 조건이 있는 행)은 덮어쓰지 않는다. 원문이 바뀌었으면 stale_source로 표시하고 ingest가 건너뛴다.

사용:
  python tools/requirement_review_queue.py build [--open-only] [--limit N] [--proposals 파일·폴더]
  python tools/requirement_review_queue.py ingest
  python tools/requirement_review_queue.py status
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.ingest_condition_gold_reviews import make_id  # noqa: E402  골든셋과 같은 결정적 id 규칙

QUEUE_DIR = ROOT / "data" / "reviews" / "requirements"
QUEUE = QUEUE_DIR / "queue.jsonl"
SERVICE_SPLIT = "service"  # gold_bridge.load(QUEUE_DIR, ("service",))가 읽는 폴더
SCHEMA_VERSION = "requirement-service-review-1.0"
SOURCE_FIELD = "service.eligibility_sections"

# 원문으로 쓰는 구역: (구역 종류, 조건 종류, 화면 이름). 앞 순서대로 이어 붙인다
SECTIONS = (("eligibility_api", "ELIGIBILITY", "신청 자격(공고 요약)"),
            ("att_eligibility", "ELIGIBILITY", "첨부 공고문 · 신청 자격"),
            ("att_exclusion", "EXCLUSION", "첨부 공고문 · 신청 제외 대상"))
SEPARATOR = "\n\n"
CONDITION_TYPES = {"ELIGIBILITY", "EXCLUSION"}  # 판정에 쓰는 종류. 우대·미분류는 gold_bridge가 옮기지 않는다
DONE_STATUSES = {"REVIEWED_COMPLETE", "CONFIRMED_NONE_IN_PROVIDED_TEXT"}
SOON_DAYS = 14


# ---------- 원문 구성 ----------
def compose_source(chunks: Iterable[dict]) -> tuple[str, list[dict]]:
    """한 공고의 청크에서 자격·제외 구역을 골라 원문 하나로 잇는다. 청크 글은 고치지 않는다(근거 위치가 원문과 맞아야 한다)."""
    chunks = list(chunks)
    parts: list[str] = []
    segments: list[dict] = []
    seen: set[str] = set()
    pos = 0
    for kind, ctype, label in SECTIONS:
        for c in chunks:
            if c["section"].split("@")[0] != kind:
                continue
            text = c["text"]
            key = " ".join(text.split())
            if len(key) < 15 or key in seen:
                continue
            seen.add(key)
            if parts:
                pos += len(SEPARATOR)
            parts.append(text)
            segments.append({"chunk_id": c["chunk_id"], "section": c["section"], "label": label, "condition_type": ctype,
                             "start": pos, "end": pos + len(text)})
            pos += len(text)
    return SEPARATOR.join(parts), segments


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _unique_span(text: str, quote: str, lo: int = 0, hi: int | None = None) -> tuple[int, int] | None:
    """quote가 [lo, hi) 안에 정확히 한 번 있으면 위치. 여러 번이면 None(첫 위치를 고르지 않는다)."""
    hi = len(text) if hi is None else hi
    if not quote:
        return None
    first = text.find(quote, lo, hi)
    if first < 0 or text.find(quote, first + 1, hi) >= 0:
        return None
    return first, first + len(quote)


# ---------- 사전 채움 ----------
def rule_prefill(notice_id: str, source: str, source_text: str, segments: list[dict], extract=None) -> list[dict]:
    """구역마다 규칙 추출기를 돌려 근거 위치를 원문 기준으로 붙인다. 위치를 확정하지 못한 후보는 버린다."""
    if extract is None:
        from tools.graphrag.extract_req import extract  # 지역 사전을 읽으므로 쓸 때만 불러온다
    out = []
    for seg in segments:
        seg_text = source_text[seg["start"]:seg["end"]]
        origin = "ATTACHMENT" if seg["section"].startswith("att_") else "API"
        for c in extract(seg_text, notice_id, source, origin, seg["section"], seg["condition_type"]):
            span = _unique_span(source_text, c["evidence_text"], seg["start"] + c.get("char_start", 0), seg["end"])
            if span is None:
                continue
            out.append({"candidate_id": f"RULE:{source_hash(json.dumps([notice_id, c['rule_id'], span], ensure_ascii=False))}",
                        "extraction_method": "rule", "rule_id": c["rule_id"], "condition_type": seg["condition_type"],
                        "attribute": c["attribute"], "operator": c["operator"], "value": c["value"], "concept": c.get("concept"),
                        "ambiguous": bool(c.get("ambiguous")), "raw_text": c["evidence_text"],
                        "evidence_reference": {"start_char": span[0], "end_char": span[1]},
                        "review_status": "UNREVIEWED", "decision_possible": False})
    return out


def load_proposals(path: Path | None) -> dict[str, list[dict]]:
    """모델 추출 결과(condition v1.1 행: field·operator·value·condition_type·raw_text)를 공고별로 모은다. 폴더면 하위의
    predictions_after_validation.jsonl을 모두 읽는다."""
    if path is None:
        return {}
    files = sorted(path.rglob("predictions_after_validation.jsonl")) if path.is_dir() else [path]
    out: dict[str, list[dict]] = {}
    for f in files:
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                out.setdefault(row["notice_id"], []).append(row)
    return out


def proposal_prefill(notice_id: str, source_text: str, proposals: list[dict]) -> tuple[list[dict], int]:
    """모델 후보를 이 원문에서 다시 찾는다(원문 층이 다를 수 있다). 정확히 한 번 나오면 위치를 붙이고, 아니면 위치 없이 둔다."""
    out, unanchored = [], 0
    for p in proposals:
        quote = (p.get("source") or {}).get("evidence_text") or p.get("raw_text") or ""
        span = _unique_span(source_text, quote)
        if span is None:
            unanchored += 1
        out.append({"candidate_id": f"LLM:{p.get('condition_id') or source_hash(quote)}", "extraction_method": "llm",
                    "condition_type": p.get("condition_type"), "attribute": p.get("field") or p.get("category_id"),
                    "operator": p.get("operator"), "value": p.get("value"), "unit": p.get("unit"), "raw_text": quote,
                    "evidence_reference": {"start_char": span[0], "end_char": span[1]} if span else None,
                    "anchored": span is not None, "review_status": "UNREVIEWED", "decision_possible": False})
    return out, unanchored


# ---------- 우선순위 ----------
def priority(notice: dict, is_open: bool, today: str) -> tuple[tuple, list[str]]:
    """정렬 키와 사유. 모집 중 → 마감 임박(14일) → 마감일 → 기간 없음 순. 임시 기본값(2026-11-28, 팀 검토 전, 설계 문서 Q-2)."""
    reasons = []
    deadline = notice.get("deadline")
    soon = False
    if is_open:
        reasons.append("모집 중")
        if deadline:
            try:
                left = (date.fromisoformat(deadline[:10]) - date.fromisoformat(today)).days
                soon = 0 <= left <= SOON_DAYS
            except ValueError:
                pass
        if soon:
            reasons.append(f"마감 {SOON_DAYS}일 이내")
    else:
        reasons.append("마감·상태 미상")
    return (not is_open, not soon, deadline or "9999-99-99", notice["notice_id"]), reasons


# ---------- 큐 만들기 ----------
def queue_row(notice: dict, chunks: list[dict], is_open: bool, today: str, proposals: list[dict] | None = None,
              extract=None) -> dict | None:
    source_text, segments = compose_source(chunks)
    if not source_text:
        return None
    nid = notice["notice_id"]
    cands = rule_prefill(nid, notice.get("source", ""), source_text, segments, extract)
    llm, unanchored = proposal_prefill(nid, source_text, proposals or [])
    key, reasons = priority(notice, is_open, today)
    return {"schema_version": SCHEMA_VERSION, "record_type": "requirement_service_review", "dataset_split": "SERVICE",
            "notice_id": nid, "title": notice.get("title"), "source_system": notice.get("source"),
            "detail_url": notice.get("detail_url"), "is_open": is_open, "deadline": notice.get("deadline"),
            "priority_reasons": reasons, "_sort": list(key),
            "source_field": SOURCE_FIELD, "source_text": source_text, "source_hash": source_hash(source_text),
            "segments": segments, "prefill_candidates": cands + llm, "prefill_unanchored": unanchored,
            "gold_conditions": [], "missed_condition_candidates": [], "gold_logic_roots": [],
            "whole_notice_conditions_complete": False, "review_status": "UNREVIEWED", "adjudication_status": "PENDING",
            "reviewer": None, "reviewed_at": None, "review_comment": "", "stale_source": False}


def touched(row: dict) -> bool:
    """사람이 손댄 행인가. 이런 행은 다시 build해도 덮어쓰지 않는다."""
    return (row.get("review_status") != "UNREVIEWED" or row.get("adjudication_status") != "PENDING"
            or bool(row.get("gold_conditions")) or bool(row.get("missed_condition_candidates")) or bool(row.get("reviewer")))


def merge(new_rows: list[dict], old_rows: list[dict]) -> tuple[list[dict], Counter]:
    old = {r["notice_id"]: r for r in old_rows}
    stats: Counter = Counter()
    out = []
    for r in new_rows:
        prev = old.pop(r["notice_id"], None)
        if prev is None:
            stats["added"] += 1
            out.append(r)
        elif touched(prev):
            stats["kept_reviewed"] += 1
            if prev.get("source_hash") != r["source_hash"] and not prev.get("stale_source"):
                prev = {**prev, "stale_source": True}
                stats["marked_stale"] += 1
            out.append({**prev, "_sort": r["_sort"], "is_open": r["is_open"], "priority_reasons": r["priority_reasons"]})
        else:
            stats["refreshed"] += 1
            out.append(r)
    for prev in old.values():  # 이번 대상에서 빠진 공고: 손댄 행만 남긴다(검수 기록 보존)
        if touched(prev):
            stats["kept_outside_scope"] += 1
            out.append(prev)
        else:
            stats["dropped"] += 1
    out.sort(key=lambda r: r["_sort"])
    for i, r in enumerate(out, 1):
        r["priority_rank"] = i
    return out, stats


def build(engine=None, *, open_only: bool = False, limit: int | None = None, proposals_path: Path | None = None,
          queue: Path = QUEUE, today: str | None = None) -> dict:
    if engine is None:
        from tools.graphrag.engine import TODAY, Engine
        engine = Engine()
        today = today or TODAY
    today = today or date.today().isoformat()
    by: dict[str, list[dict]] = {}
    for c in engine.chunks:
        by.setdefault(c["notice_id"], []).append(c)
    proposals = load_proposals(proposals_path)
    rows, skipped = [], Counter()
    for n in engine.notices:
        if n.get("text_requirements", "unparsed") == "reviewed":
            skipped["already_reviewed"] += 1
            continue
        is_open = engine.is_open(n)
        if open_only and not is_open:
            skipped["closed"] += 1
            continue
        row = queue_row(n, by.get(n["notice_id"], []), is_open, today, proposals.get(n["notice_id"]))
        if row is None:
            skipped["no_source_text"] += 1
            continue
        rows.append(row)
    rows.sort(key=lambda r: r["_sort"])
    if limit:
        rows = rows[:limit]
    merged, stats = merge(rows, read_jsonl(queue))
    write_jsonl(queue, merged)
    report = {"built_at": datetime.now().isoformat(timespec="seconds"), "queue": str(queue.relative_to(ROOT)) if queue.is_relative_to(ROOT) else str(queue),
              "rows": len(merged), "candidates_this_run": len(rows), "skipped": dict(skipped), "merge": dict(stats),
              "prefill": dict(Counter(c["extraction_method"] for r in rows for c in r["prefill_candidates"])),
              "prefill_unanchored_llm": sum(r["prefill_unanchored"] for r in rows),
              "by_source": dict(Counter(r["source_system"] for r in rows)), "open": sum(r["is_open"] for r in rows)}
    (queue.parent / "queue_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


# ---------- 검수 결과 반영 ----------
def check_row(row: dict) -> list[str]:
    """VERIFIED 행 검사. 문제 목록(비면 통과)."""
    errs = []
    if row.get("stale_source"):
        errs.append("원문이 바뀐 뒤 다시 검수하지 않음(stale_source)")
    if not row.get("reviewer") or not row.get("reviewed_at"):
        errs.append("검수자·검수 시각 없음")
    else:
        try:
            datetime.fromisoformat(str(row["reviewed_at"]).replace("Z", "+00:00"))
        except ValueError:
            errs.append("검수 시각 형식 오류")
    if row.get("adjudication_status") not in DONE_STATUSES:
        errs.append(f"검수 결과 상태가 완료가 아님({row.get('adjudication_status')})")
    if row.get("source_hash") != source_hash(row.get("source_text", "")):
        errs.append("원문이 큐를 만든 뒤 바뀜(source_hash 불일치)")
    conds = row.get("gold_conditions", []) + row.get("missed_condition_candidates", [])
    if row.get("adjudication_status") == "CONFIRMED_NONE_IN_PROVIDED_TEXT" and conds:
        errs.append("'원문에 조건 없음'인데 조건이 있음")
    ids = set()
    text = row.get("source_text", "")
    for c in conds:
        ref = c.get("evidence_reference") or {}
        s, e = ref.get("start_char"), ref.get("end_char")
        if not isinstance(s, int) or not isinstance(e, int) or not (0 <= s < e <= len(text)) or text[s:e] != c.get("raw_text"):
            errs.append(f"근거 위치가 원문과 다름({c.get('gold_condition_id')})")
            continue
        if c.get("condition_type") not in CONDITION_TYPES | {"PREFERENCE", "UNCLASSIFIED"}:
            errs.append(f"조건 종류 오류({c.get('condition_type')})")
        if c.get("gold_condition_id") != make_id(row["notice_id"], c.get("condition_type"), s, e, c.get("raw_text")):
            errs.append(f"조건 id가 규칙과 다름({c.get('gold_condition_id')})")
        if c.get("review_status") != "VERIFIED":
            errs.append(f"검수하지 않은 조건({c.get('gold_condition_id')})")
        if c.get("gold_condition_id") in ids:
            errs.append(f"조건 id 중복({c.get('gold_condition_id')})")
        ids.add(c.get("gold_condition_id"))
    for root in row.get("gold_logic_roots", []):
        missing = [x for x in _refs(root) if x not in ids]
        if missing:
            errs.append(f"논리가 없는 조건을 가리킴({missing[0]})")
    return errs


def _refs(node: dict) -> list[str]:
    if node.get("node_type") == "CONDITION_REF":
        return [node.get("condition_id")]
    return [x for c in node.get("children", []) for x in _refs(c)]


def ingest(queue: Path = QUEUE, out_dir: Path | None = None) -> dict:
    out_dir = out_dir or (queue.parent / SERVICE_SPLIT)
    rows = read_jsonl(queue)
    cond_rows, logic_rows, rejected = [], [], []
    for r in rows:
        if r.get("review_status") != "VERIFIED":
            continue
        errs = check_row(r)
        if errs:
            rejected.append({"notice_id": r["notice_id"], "errors": errs})
            continue
        cond_rows.append({"notice_id": r["notice_id"], "source_field": r["source_field"],
                          "gold_conditions": r.get("gold_conditions", []),
                          "missed_condition_candidates": r.get("missed_condition_candidates", []),
                          "reviewer": r["reviewer"], "reviewed_at": r["reviewed_at"], "adjudication_status": r["adjudication_status"],
                          "whole_notice_conditions_complete": bool(r.get("whole_notice_conditions_complete")),
                          "source_hash": r["source_hash"], "review_comment": r.get("review_comment", "")})
        if r.get("gold_logic_roots"):
            logic_rows.append({"notice_id": r["notice_id"], "gold_logic_roots": r["gold_logic_roots"]})
    write_jsonl(out_dir / "reviewed_condition_gold.jsonl", cond_rows)
    write_jsonl(out_dir / "reviewed_logic_gold.jsonl", logic_rows)
    report = {"ingested_at": datetime.now().isoformat(timespec="seconds"), "queue_rows": len(rows),
              "verified": len(cond_rows) + len(rejected), "applied": len(cond_rows), "rejected": rejected,
              "whole_notice_complete": sum(1 for r in cond_rows if r["whole_notice_conditions_complete"]),
              "with_logic": len(logic_rows)}
    (out_dir / "ingest_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def status(queue: Path = QUEUE) -> dict:
    rows = read_jsonl(queue)
    return {"rows": len(rows), "review_status": dict(Counter(r.get("review_status") for r in rows)),
            "adjudication_status": dict(Counter(r.get("adjudication_status") for r in rows)),
            "stale": sum(1 for r in rows if r.get("stale_source")), "open": sum(1 for r in rows if r.get("is_open")),
            "top10": [{"rank": r.get("priority_rank"), "notice_id": r["notice_id"], "title": r.get("title"),
                       "reasons": r.get("priority_reasons")} for r in rows[:10]]}


# ---------- 입출력 ----------
def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--open-only", action="store_true")
    b.add_argument("--limit", type=int)
    b.add_argument("--proposals", type=Path, help="모델 추출 결과(predictions_after_validation.jsonl 또는 그 상위 폴더)")
    sub.add_parser("ingest")
    sub.add_parser("status")
    a = p.parse_args(argv)
    if a.cmd == "build":
        res = build(open_only=a.open_only, limit=a.limit, proposals_path=a.proposals)
    elif a.cmd == "ingest":
        res = ingest()
    else:
        res = status()
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
