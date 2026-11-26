"""FastAPI 의존성. 시험에서는 app.dependency_overrides로 가짜 서비스·라우터·그래프를 넣는다."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from ..core.config import get_settings
from ..services.eligibility import EligibilityService, EngineEligibilityService, judge_for_agent


@lru_cache
def get_eligibility_service() -> EligibilityService:
    return EngineEligibilityService(use_cleaned=get_settings().use_cleaned)


@lru_cache
def get_llm_router():
    """config/models.yaml + 환경변수로 만든 모델 라우터. VLLM_BASE_URL이 없으면 템플릿 단계만 남는다(설명 없이 판정만)."""
    from agent.llm import load_router

    return load_router()


@lru_cache
def get_graph_repo():
    """Neo4j 읽기 전용 저장소. NEO4J_* 설정이 없으면 None(경로는 평가기 결과로, 정의는 생략)."""
    from ..repositories.graph import from_settings

    return from_settings(get_settings())


_GRAPHS: dict[tuple[int, int, int], object] = {}


def get_agent_graph(service: EligibilityService = Depends(get_eligibility_service), router=Depends(get_llm_router),
                    graph=Depends(get_graph_repo)):
    """판정 서비스·모델 라우터·그래프 저장소를 묶은 에이전트 그래프. 같은 조합이면 한 번만 만든다."""
    key = (id(service), id(router), id(graph))
    if key not in _GRAPHS:
        from agent.graph import build_graph

        _GRAPHS[key] = build_graph(judge_for_agent(service), router, graph)
    return _GRAPHS[key]
