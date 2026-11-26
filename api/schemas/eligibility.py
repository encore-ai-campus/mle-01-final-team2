"""조건 입력과 규칙 판정 응답(POST /api/eligibility). 모델 없이 규칙 평가기 결과만 담는다."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Verdict = Literal["ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_CHECK"]
CondStatus = Literal["SATISFIED", "UNSATISFIED", "UNKNOWN"]


class ApplicantProfile(BaseModel):
    """신청자 조건. 비워 둔 값(None)은 '모름'이며 '제한 없음'으로 보지 않는다."""

    region: str | None = Field(default=None, description="사업장 소재지 개념 ID (예: REGION:1127000000)")
    business_age_years: float | None = Field(default=None, ge=0, description="업력(년)")
    pre_founder: bool | None = Field(default=None, description="사업자등록 전 예비창업자")
    founder_age: int | None = Field(default=None, ge=0, le=120, description="대표자 만 나이")
    applicant_type: str | None = Field(default=None, description="신청 대상 유형")


class EligibilityRequest(BaseModel):
    profile: ApplicantProfile
    question: str = Field(default="", max_length=500, description="검색어(선택). 비우면 판정만 한다")
    top: int = Field(default=10, ge=1, le=50)
    include_closed: bool = False
    source: Literal["BIZINFO", "KSTARTUP"] | None = None


class ConditionResult(BaseModel):
    cond_id: str
    attribute: str
    status: CondStatus
    strength: str
    reason: str
    evidence: str = ""
    path: list[str] | None = None
    flags: list[str] = []


class NoticeVerdict(BaseModel):
    notice_id: str
    verdict: Verdict
    structured: str
    reasons: list[str]
    conditions: list[ConditionResult]
    score: float | None = None


class EligibilityResponse(BaseModel):
    evaluated: int
    candidates: int
    counts: dict[str, int]
    results: list[NoticeVerdict]
    input_layer: str = Field(description="판정에 쓴 데이터 층(cleaned / parsed)")
