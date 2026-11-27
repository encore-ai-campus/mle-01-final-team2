"""운영자 API 뼈대(명세 §9, 화면 SCR-06). 관리자만 쓴다(`require_admin`). 지금은 501을 낸다."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.errors import not_implemented
from ..dependencies.auth import CurrentUser, require_admin

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/status")
def admin_status(user: CurrentUser = Depends(require_admin)) -> dict:
    """M-01 운영 현황·수집 상태. 출처별 마지막 수집 시각, 실패 건수, Aura·모델 상태(`/health/*`)를 모은다."""
    raise not_implemented("M-01", "수집 보고서(data/*/manifest·report)와 health 결과를 모아 운영 현황을 돌려준다")


@router.post("/reprocess")
def admin_reprocess(user: CurrentUser = Depends(require_admin)) -> dict:
    """M-03 실패 건 재처리. 첨부 추출 실패(`extract_attachment_text.py` 보고서) 등을 다시 돌린다. 동시 실행은 409 CONFLICT."""
    raise not_implemented("M-03", "실패 건 목록을 받아 재처리 작업을 시작하고 run_id를 돌려준다")
