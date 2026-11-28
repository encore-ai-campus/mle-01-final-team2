"""응답 공통 meta(명세 §2.1). 화면의 수집 시각 배지와 면책 문구, 재현성(버전)에 쓴다.

명세의 전체 틀(`data`·`outcome`·`reason_codes`로 감싸기)은 화면·에이전트 응답 모양이 바뀌어 아직 하지 않았다.
지금은 기존 응답에 `meta`만 더한다(필드 추가라 이전 화면도 그대로 동작한다).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class ResponseMeta(BaseModel):
    data_as_of: dict[str, str] = Field(description="출처별 마지막 수집 시각(ISO, KST)")
    stale: bool = Field(description="수집 지연 한도(APP_STALE_HOURS)를 넘었는지")
    versions: dict[str, str | None] = Field(description="규칙·데이터·스키마·모델 버전")
    disclaimer: str
