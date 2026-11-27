"""공고 API(명세 §4, 화면 SCR-01·SCR-02). N-01·N-02는 구현됨(api/services/notices.py), N-03은 아직 501을 낸다.

데이터: 정리층 `data/cleaned/`(공고 5,116건)·공통 v1. 엔진은 `tools/graphrag/engine.py`의 `Engine().notices`를 그대로 쓸 수 있다.
나중에는 Supabase(원문·검색)로 옮긴다(명세 §11, API-4).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.errors import api_error, not_implemented
from ..dependencies import get_notice_service
from ..dependencies.auth import CurrentUser, get_current_user
from ..schemas.notices import NoticeDetail, NoticeListResponse
from ..services.notices import NoticeService

router = APIRouter(prefix="/api", tags=["notices"])


@router.get("/notices", response_model=NoticeListResponse)
def list_notices(q: str | None = Query(default=None, max_length=100), source: str | None = Query(default=None, max_length=20),
                 include_closed: bool = False, page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100),
                 user: CurrentUser = Depends(get_current_user),
                 service: NoticeService = Depends(get_notice_service)) -> NoticeListResponse:
    """N-01 공고 목록·검색. 판정은 하지 않는다(판정은 E-01). 페이지는 page/size."""
    return service.list(q, source, include_closed, page, size)


@router.get("/notices/{notice_id}", response_model=NoticeDetail)
def get_notice(notice_id: str, user: CurrentUser = Depends(get_current_user),
               service: NoticeService = Depends(get_notice_service)) -> NoticeDetail:
    """N-02 공고 상세·원문 구역·첨부 상태. 없으면 404 NOT_FOUND."""
    detail = service.get(notice_id)
    if detail is None:
        raise api_error(404, "NOT_FOUND", "공고를 찾을 수 없습니다.", notice_id=notice_id)
    return detail


@router.get("/notices/{notice_id}/spans")
def get_notice_spans(notice_id: str, evaluation_id: str | None = Query(default=None, max_length=80),
                     user: CurrentUser = Depends(get_current_user)) -> dict:
    """N-03 판정에 쓴 원문 문장 위치. 조건의 evidence(청크 id·글자 위치)를 원문 위치로 바꾼다."""
    raise not_implemented("N-03", "evaluation_id의 조건 근거를 원문 문장 위치 목록으로 돌려준다")
