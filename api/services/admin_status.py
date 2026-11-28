"""M-01 운영 현황(명세 §9, 화면 SCR-06). 지금 있는 파일에서 모은다. 수집 기록 표(`ingest_runs`)가 생기면 출처별 실행 기록을 그쪽으로 바꾼다.

- 출처별 수집: 엔진이 읽은 공고의 출처별 마지막 수집 시각(`fetched_at`)과 건수, 정리 보고서(`data/cleaned/<스냅샷>/cleaning_report.json`)의 입력 실행 이름.
  새로 들어온·바뀐 건수는 실행 기록이 없어 null이다.
- 대기열: 요건 검수 큐(검수 전·작업 중), 첨부 추출 실패(`data/bizinfo/extracted/*/extraction_report.json`의 OK가 아닌 파일), 본문 요건 미검수 공고.
- 기간 상태: 정리층 공고의 `period_status`를 엔진에 있는 공고만 센다.
- 관측: Langfuse·GPU는 아직 연결 전이라 null이다.
파일이 없으면 그 항목만 null로 두고 나머지는 돌려준다.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from .meta import KST, _parse

SOURCES = ("BIZINFO", "KSTARTUP", "G2B")
PENDING = {"UNREVIEWED", "NEEDS_REVIEW"}


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def extraction_failures(root: Path) -> dict | None:
    """첨부 추출 보고서들에서 OK가 아닌 파일 수(상태별). 보고서가 하나도 없으면 None."""
    reports = sorted(root.glob("*/extraction_report.json")) if root.exists() else []
    if not reports:
        return None
    by_status: Counter = Counter()
    for f in reports:
        r = _read_json(f) or {}
        for status, n in (r.get("status") or {}).items():
            if not str(status).startswith("OK"):
                by_status[status] += n
    return {"failed": sum(by_status.values()), "by_status": dict(by_status), "reports": len(reports)}


def build_status(notices: list[dict], *, queue_rows: list[dict] | None, raw: dict[str, dict] | None, cleaning_report: dict | None,
                 extraction: dict | None, stale_hours: float = 0, now: datetime | None = None) -> dict:
    now = now or datetime.now(KST)
    latest: dict[str, datetime] = {}
    counts: Counter = Counter()
    for n in notices:
        counts[n["source"]] += 1
        dt = _parse(n.get("fetched_at"))
        if dt and (n["source"] not in latest or dt > latest[n["source"]]):
            latest[n["source"]] = dt
    inputs = (cleaning_report or {}).get("inputs") or {}
    run_of = {"BIZINFO": inputs.get("bizinfo_run"), "KSTARTUP": inputs.get("kstartup_raw")}
    sources = []
    for s in SOURCES:
        dt = latest.get(s)
        stale = bool(stale_hours and dt and (now - dt).total_seconds() > stale_hours * 3600)
        sources.append({
            "source": s, "in_service": s in counts, "last_success_at": dt.astimezone(KST).isoformat() if dt else None,
            "last_run": {"run_id": run_of.get(s), "status": "SUCCESS" if dt else None, "fetched": counts.get(s, 0),
                         "new": None, "changed": None, "failed": None} if s in counts else None,
            "stale": stale,
        })
    review = Counter(r.get("review_status") for r in queue_rows) if queue_rows is not None else None
    queues = {
        "review_pending": sum(v for k, v in review.items() if k in PENDING) if review is not None else None,
        "review_done": review.get("VERIFIED", 0) if review is not None else None,
        "review_total": sum(review.values()) if review is not None else None,
        "reprocess_pending": extraction["failed"] if extraction else None,
        "reprocess_by_status": extraction["by_status"] if extraction else None,
        "unparsed": sum(1 for n in notices if (n.get("text_requirements") or "unparsed") != "reviewed"),
    }
    period = None
    if raw:
        c = Counter((raw.get(n["notice_id"]) or {}).get("period_status") or "UNKNOWN" for n in notices)
        period = {"open_with_deadline": c.get("OPEN_WITH_DEADLINE", 0), "open_no_date": c.get("OPEN_NO_DATE_DEADLINE", 0),
                  "closed": c.get("CLOSED", 0), "other": sum(v for k, v in c.items()
                                                             if k not in ("OPEN_WITH_DEADLINE", "OPEN_NO_DATE_DEADLINE", "CLOSED"))}
    return {"checked_at": now.isoformat(timespec="seconds"), "notices": len(notices), "sources": sources, "queues": queues,
            "period_status": period, "observability": {"langfuse_url": None, "gpu_running": None},
            "notes": ["새로 들어온·바뀐 건수는 수집 기록 표(ingest_runs)가 생기면 채운다(M-02)",
                      "Langfuse·GPU 상태는 연결 전이라 비어 있다"]}
