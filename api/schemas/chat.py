"""POST /api/chat 요청. 응답은 SSE 이벤트 스트림이다(기초 설계서 §8 스트리밍).

이벤트: ask, verdict, requirement, path, token, banner, usage, done, error.
각 이벤트는 `event: <종류>` 줄과 `data: {"type": "<종류>", ...}` 줄로 보낸다.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from .eligibility import ApplicantProfile


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000, description="질문. 개인정보(번호·연락처)는 넣지 않는다")
    profile: ApplicantProfile = Field(default_factory=ApplicantProfile, description="조건 폼 입력(범주형)")
    notice_id: str | None = Field(default=None, max_length=80, description="특정 공고를 지목하면 검색 없이 그 공고만 판정")
    top: int = Field(default=5, ge=1, le=20)
    include_closed: bool = False
    ask_count: int = Field(default=0, ge=0, le=2, description="이미 되물은 횟수(최대 2회)")
