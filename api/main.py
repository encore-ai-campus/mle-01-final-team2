"""앱 생성. 실행: uvicorn api.main:app --reload (저장소 루트에서)

엔드포인트 현황은 docs/GUIDE_개발시작_v0.1.md "기능별 시작점"에 있다. 뼈대만 있는 엔드포인트는 501 NOT_IMPLEMENTED를 낸다.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import get_settings
from .routers import admin, chat, eligibility, graph, health, me, meta, notices, reviews


def _log_deploy_problems(settings) -> None:
    """배포 설정 문제를 시작할 때 알린다(값은 남기지 않는다). 점검 내용은 api/core/deploy_check.py."""
    import logging

    from .core.deploy_check import problems

    log = logging.getLogger("jiwongak.deploy")
    for level, msg in problems(settings):
        (log.error if level == "ERROR" else log.warning)("deploy check: %s", msg)


def create_app() -> FastAPI:
    settings = get_settings()
    _log_deploy_problems(settings)
    app = FastAPI(title=settings.app_name, version="0.1.0")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST", "PUT"], allow_headers=["*"])
    app.include_router(health.router)
    app.include_router(eligibility.router)
    app.include_router(chat.router)
    app.include_router(graph.router)
    app.include_router(me.router)
    app.include_router(notices.router)
    app.include_router(meta.router)
    app.include_router(admin.router)
    app.include_router(reviews.router)
    return app


app = create_app()
