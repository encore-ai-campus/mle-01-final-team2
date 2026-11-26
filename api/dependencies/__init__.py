"""FastAPI 의존성. 시험에서는 app.dependency_overrides로 가짜 서비스를 넣는다."""
from __future__ import annotations

from functools import lru_cache

from ..core.config import get_settings
from ..services.eligibility import EligibilityService, EngineEligibilityService


@lru_cache
def get_eligibility_service() -> EligibilityService:
    return EngineEligibilityService(use_cleaned=get_settings().use_cleaned)
