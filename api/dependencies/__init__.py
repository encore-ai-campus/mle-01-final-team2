"""FastAPI 의존성. 시험에서는 app.dependency_overrides로 가짜 서비스·라우터·그래프를 넣는다."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends

from ..core.config import get_settings
from ..services.eligibility import EligibilityService, EngineEligibilityService, judge_for_agent
from ..services.notices import NoticeService


@lru_cache
def get_eligibility_service() -> EligibilityService:
    return EngineEligibilityService(use_cleaned=get_settings().use_cleaned)


@lru_cache
def get_notice_service() -> NoticeService:
    """공고 목록(N-01). 판정 서비스와 같은 엔진을 써서 데이터를 한 번만 읽는다."""
    return NoticeService(get_eligibility_service()._engine)


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


@lru_cache
def get_retriever():
    """하이브리드 검색기(BM25 + 벡터 RRF, agent/rag). 엔진 청크를 쓰므로 실제 엔진이 있을 때만 만든다.
    판정 서비스의 후보 검색에도 붙인다(설계서 §7 "후보 검색(하이브리드)"). 벡터 색인이 없으면 BM25만."""
    service = get_eligibility_service()
    engine = getattr(service, "_engine", None)
    if engine is None:
        return None
    from agent.rag import from_env

    r = from_env(engine.chunks, engine.bm25)
    if hasattr(service, "attach_retriever"):
        service.attach_retriever(r)
    return r


_ORCH: dict[tuple[int, int, int], object] = {}


def get_orchestrator(agent_graph=Depends(get_agent_graph), router=Depends(get_llm_router),
                     service: EligibilityService = Depends(get_eligibility_service)):
    """슈퍼바이저 오케스트레이터: 자격 판정(agent_graph) + 공고 질의(RAG) + 용어 정의. 같은 조합이면 한 번만 만든다."""
    engine = getattr(service, "_engine", None)
    retriever = get_retriever() if engine is not None else None
    key = (id(agent_graph), id(router), id(retriever))
    if key not in _ORCH:
        from agent.agents import build_definition, build_notice_qa, find_term, load_terms
        from agent.orchestrator import build_orchestrator, make_runners

        qa = None
        if retriever is not None:
            meta = lambda nid: engine.by_id.get(nid)  # noqa: E731
            qa = build_notice_qa(retriever, router, meta, lambda: {n["notice_id"] for n in engine.notices if engine.is_open(n)})
        terms_cache: dict = {}

        def terms() -> dict:
            if not terms_cache:
                try:
                    terms_cache.update(load_terms())
                except (OSError, KeyError, ValueError) as e:  # 법령 파일이 없는 환경(시험·CI): 정의 없음
                    import logging

                    logging.getLogger("jiwongak.definition").warning("definition terms unavailable: %s", type(e).__name__)
                    terms_cache["__empty__"] = None
            return {k: v for k, v in terms_cache.items() if v is not None}

        dg = build_definition(router, terms)
        _ORCH[key] = build_orchestrator(make_runners(agent_graph, qa, dg), router, is_term=lambda q: find_term(q, terms()) is not None)
    return _ORCH[key]
