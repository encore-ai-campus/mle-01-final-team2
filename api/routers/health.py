from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.config import Settings, get_settings
from ..dependencies import get_graph_repo, get_llm_router

router = APIRouter(tags=["health"])


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    """서버 생존 확인. 외부 저장소에는 접속하지 않고 설정이 있는지만 알린다(값은 내보내지 않는다)."""
    return {
        "status": "ok",
        "environment": settings.environment,
        "configured": {
            "neo4j": bool(settings.neo4j_uri),
            "supabase": bool(settings.supabase_url),
            "llm": settings.llm_configured,
        },
    }


@router.get("/health/llm")
async def health_llm(router_=Depends(get_llm_router)) -> dict:
    """모델 provider 연결 확인(실제로 /v1/models를 부른다). 주소·키는 내보내지 않고 이름과 상태만 알린다."""
    return {"providers": await router_.health(), "breakers": router_.status(), "roles": router_.roles}


@router.get("/health/graph")
async def health_graph(repo=Depends(get_graph_repo)) -> dict:
    """Neo4j 연결 확인(RETURN 1). 주소는 내보내지 않는다."""
    import asyncio

    if repo is None:
        return {"configured": False, "reachable": False}
    return {"configured": True, "reachable": await asyncio.to_thread(repo.ping)}
