"""운영자 API(명세 §9, 화면 SCR-06). 관리자만 쓴다(`require_admin`). M-01은 구현, M-03은 아직 501이다."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.config import Settings, get_settings
from ..core.errors import not_implemented
from ..dependencies import cleaned_raw, data_snapshot, get_eligibility_service, get_review_store
from ..dependencies.auth import CurrentUser, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/status")
def admin_status(user: CurrentUser = Depends(require_admin), settings: Settings = Depends(get_settings),
                 service=Depends(get_eligibility_service), store=Depends(get_review_store)) -> dict:
    """M-01 운영 현황·수집 상태: 출처별 마지막 수집 시각·건수, 검수·재처리 대기열, 기간 상태. 없는 파일 항목은 null."""
    from tools.graphrag import cleaned

    from ..services.admin_status import _read_json, build_status, extraction_failures

    engine = getattr(service, "_engine", None)
    notices = engine.notices if engine is not None else []
    snap = data_snapshot()
    report = _read_json(cleaned.CLEANED / snap / "cleaning_report.json") if snap else None
    return build_status(notices, queue_rows=store.rows() if store.available() else None, raw=cleaned_raw(), cleaning_report=report,
                        extraction=extraction_failures(cleaned.REPO / "data" / "bizinfo" / "extracted"),
                        stale_hours=settings.stale_hours)


@router.post("/reprocess")
def admin_reprocess(user: CurrentUser = Depends(require_admin)) -> dict:
    """M-03 실패 건 재처리. 첨부 추출 실패(`extract_attachment_text.py` 보고서) 등을 다시 돌린다. 동시 실행은 409 CONFLICT."""
    raise not_implemented("M-03", "실패 건 목록을 받아 재처리 작업을 시작하고 run_id를 돌려준다")
