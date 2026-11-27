"""판정 API(명세 §5).

- E-01 `POST /api/eligibility`: 조건 폼 입력 → 규칙 판정(모델 없이, 설명 제외). 구현됨
- E-02·E-03·E-04: 뼈대(501). `evaluation_id` 규칙(명세 §5.0)을 먼저 정해야 한다(API-2: 단기 캐시 제안)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ..core.errors import not_implemented
from ..dependencies import get_eligibility_service
from ..dependencies.auth import CurrentUser, get_current_user
from ..schemas.eligibility import EligibilityRequest, EligibilityResponse
from ..services.eligibility import EligibilityService

router = APIRouter(prefix="/api", tags=["eligibility"])


@router.post("/eligibility", response_model=EligibilityResponse)
def eligibility(req: EligibilityRequest, service: EligibilityService = Depends(get_eligibility_service)) -> EligibilityResponse:
    return service.judge(req)


@router.post("/eligibility/clarify")
def eligibility_clarify(user: CurrentUser = Depends(get_current_user)) -> dict:
    """E-04 되묻기 답변 반영 재판정. 이전 evaluation_id + 답한 값 → 같은 공고들을 다시 판정."""
    raise not_implemented("E-04", "evaluation_id와 되묻기 답을 받아 프로필을 보충하고 다시 판정한다")


@router.get("/eligibility/{notice_id}")
def eligibility_detail(notice_id: str, evaluation_id: str | None = Query(default=None, max_length=80),
                       user: CurrentUser = Depends(get_current_user)) -> dict:
    """E-02 한 공고의 조건별 검증표(명세 §3.6 ConditionCheck). E-01 결과의 conditions를 화면용으로 펼친다."""
    raise not_implemented("E-02", "evaluation_id의 공고 1건 판정을 조건별 검증표로 돌려준다")


@router.get("/eligibility/{notice_id}/path")
def eligibility_path(notice_id: str, evaluation_id: str | None = Query(default=None, max_length=80),
                     user: CurrentUser = Depends(get_current_user)) -> dict:
    """E-03 추론 과정(명세 §3.7 ReasoningPath). 그래프 경로는 `GET /api/graph/path`가 이미 있어 그것을 감싸면 된다."""
    raise not_implemented("E-03", "evaluation_id 기준으로 /api/graph/path 서브그래프와 판정 단계를 묶어 돌려준다")
