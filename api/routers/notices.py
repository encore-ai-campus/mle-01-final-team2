"""공고 API 뼈대(명세 §4, 화면 SCR-01·SCR-02). 지금은 모두 501을 낸다.

데이터: 정리층 `data/cleaned/`(공고 5,116건)·공통 v1. 엔진은 `tools/graphrag/engine.py`의 `Engine().notices`를 그대로 쓸 수 있다.
나중에는 Supabase(원문·검색)로 옮긴다(명세 §11, API-4).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.errors import not_implemented
from ..dependencies.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["notices"])


@router.get("/notices")
def list_notices(q: str | None = Query(default=None, max_length=100), source: str | None = Query(default=None, max_length=20),
                 include_closed: bool = False, page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100),
                 user: CurrentUser = Depends(get_current_user)) -> dict:
    """N-01 공고 목록·검색. 응답 항목은 명세 §3.3 NoticeSummary. 페이지 규칙은 §2.5."""
    raise not_implemented("N-01", "정리층 공고를 검색·필터해 NoticeSummary 목록과 페이지 정보를 돌려준다")


@router.get("/notices/{notice_id}")
def get_notice(notice_id: str, user: CurrentUser = Depends(get_current_user)) -> dict:
    """N-02 공고 상세·원문. 응답은 명세 §3.4 NoticeDetail. 없으면 404 NOT_FOUND."""
    raise not_implemented("N-02", "공고 1건의 상세·원문 구역·첨부 상태를 돌려준다")


@router.get("/notices/{notice_id}/spans")
def get_notice_spans(notice_id: str, evaluation_id: str | None = Query(default=None, max_length=80),
                     user: CurrentUser = Depends(get_current_user)) -> dict:
    """N-03 판정에 쓴 원문 문장 위치. 조건의 evidence(청크 id·글자 위치)를 원문 위치로 바꾼다."""
    raise not_implemented("N-03", "evaluation_id의 조건 근거를 원문 문장 위치 목록으로 돌려준다")
