"""POST /api/eligibility: 조건 폼 입력 → 규칙 판정(모델 없이, 설명 제외)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies import get_eligibility_service
from ..schemas.eligibility import EligibilityRequest, EligibilityResponse
from ..services.eligibility import EligibilityService

router = APIRouter(prefix="/api", tags=["eligibility"])


@router.post("/eligibility", response_model=EligibilityResponse)
def eligibility(req: EligibilityRequest, service: EligibilityService = Depends(get_eligibility_service)) -> EligibilityResponse:
    return service.judge(req)
