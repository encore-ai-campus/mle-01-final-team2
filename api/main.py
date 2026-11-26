"""앱 생성. 실행: uvicorn api.main:app --reload (저장소 루트에서)

아직 없는 엔드포인트(기초 설계서 §8 Python API 초안): GET /api/notices/{id}, GET /api/graph/path, GET /api/concepts,
/admin/*, 로그인(Supabase JWT 검증).
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .routers import chat, eligibility, graph, health


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"], allow_headers=["*"])
    app.include_router(health.router)
    app.include_router(eligibility.router)
    app.include_router(chat.router)
    app.include_router(graph.router)
    return app


app = create_app()
