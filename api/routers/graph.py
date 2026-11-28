"""GET /api/graph/path(판정 경로 서브그래프), GET /api/concepts(입력 폼용 개념 목록).

전체 그래프가 아니라 질의에 쓰인 경로만 내려보낸다(기초 설계서 §8 그래프 시각화).
"""
from __future__ import annotations

import asyncio
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Query

from ..dependencies import get_graph_repo
from ..dependencies.auth import CurrentUser, get_current_user
from ..repositories.graph import GraphUnavailable

router = APIRouter(prefix="/api", tags=["graph"])


def _unavailable(detail: str = "그래프 DB에 연결할 수 없습니다.") -> HTTPException:
    return HTTPException(503, detail={"error": {"code": "SERVICE_DEGRADED", "message": detail}})


@router.get("/graph/path")
async def graph_path(user: CurrentUser = Depends(get_current_user), notice_id: str = Query(max_length=80),
                     region: str | None = Query(default=None, max_length=40), repo=Depends(get_graph_repo)) -> dict:
    """공고 → 요건 → 조건 → 개념(사용자 지역 → 조건 지역 경로 강조) → 정의 → 조문 → 법령."""
    if repo is None:
        raise _unavailable("그래프 DB가 설정되지 않았습니다(NEO4J_*).")
    try:
        sg = await asyncio.to_thread(repo.notice_subgraph, notice_id, region)
    except GraphUnavailable:
        raise _unavailable()
    if not sg["nodes"]:
        raise HTTPException(404, detail={"error": {"code": "NO_MATCH", "message": "공고를 찾지 못했습니다."}})
    return sg


@lru_cache
def _local_regions() -> list[dict]:
    from tools.graphrag.regions import RegionGraph

    rg = RegionGraph()
    return [{"id": rid, "name": rg.name(rid), "full_name": None, "level": None, "parent": None} for rid in sorted(rg.nodes)]


@router.get("/concepts")
async def concepts(user: CurrentUser = Depends(get_current_user), scheme: str = Query(default="region", pattern="^region$"),
                   repo=Depends(get_graph_repo)) -> dict:
    """입력 폼용 지역 목록. 그래프가 없거나 닿지 않으면 내장 지역 사전을 쓴다."""
    if repo is not None:
        try:
            return {"scheme": scheme, "source": "neo4j", "items": await asyncio.to_thread(repo.regions)}
        except GraphUnavailable:
            pass
    return {"scheme": scheme, "source": "local", "items": _local_regions()}
