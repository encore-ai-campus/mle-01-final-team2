"""오류 응답 모양. 기존 라우터와 같이 `HTTPException(detail={"error": {"code", "message"}})`를 쓴다(응답은 `{"detail": {"error": ...}}`).

명세(docs/design/API_명세서_v0.1.md §2.2)의 공통 응답 틀(`data`·`outcome`·`reason_codes`·`meta`)로 바꾸는 일은 아직 하지 않았다.
바꿀 때는 이 파일과 web/lib/upstream.ts를 함께 고친다.
"""
from __future__ import annotations

from fastapi import HTTPException


def api_error(status: int, code: str, message: str, **extra) -> HTTPException:
    return HTTPException(status, detail={"error": {"code": code, "message": message, **extra}})


def not_implemented(spec_id: str, todo: str) -> HTTPException:
    """뼈대만 있는 엔드포인트. 명세 ID(N-01 등)와 할 일을 알려 준다. 구현하면 이 호출을 지운다."""
    return api_error(501, "NOT_IMPLEMENTED", f"{spec_id}는 아직 구현 전입니다.", spec=spec_id, todo=todo)
