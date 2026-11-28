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


# 판정·목록 API의 자유 입력(검색어)도 챗봇과 같은 입력 가드를 거친다(명세 §2.2·§2.6, 기초 설계 §7.3 #7).
# 식별 정보·지시 주입만 막는다. 범위 밖·법률 자문 규칙은 검색어에 맞지 않아 쓰지 않는다. 걸린 입력 값은 기록하지 않는다.
BLOCK_CODES = ("PII_BLOCKED", "INJECTION_BLOCKED")


def guard_text(text: str | None) -> None:
    if not text:
        return
    from agent.guards import input_guard
    from agent.templates import TEXT

    code = input_guard(text)
    if code in BLOCK_CODES:
        raise api_error(422, code, TEXT[code])
