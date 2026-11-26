from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.config import Settings, get_settings

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
