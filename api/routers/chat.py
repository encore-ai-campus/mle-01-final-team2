"""POST /api/chat (SSE): 질문·조건 → 에이전트 → 이벤트 스트림.

판정·요건 이벤트가 설명 토큰보다 먼저 나간다. 질문 본문·조건 값은 로그에 남기지 않는다.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ..dependencies import get_agent_graph
from ..schemas.chat import ChatRequest

router = APIRouter(prefix="/api", tags=["chat"])
log = logging.getLogger("jiwongak.chat")


def sse(ev: dict) -> str:
    return f"event: {ev.get('type', 'message')}\ndata: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest, graph=Depends(get_agent_graph)) -> StreamingResponse:
    from agent.graph import run_events

    async def stream():
        try:
            async for ev in run_events(graph, req.model_dump()):
                yield sse(ev)
        except Exception as e:  # 스트림 도중 예외는 error 이벤트로 알리고 끝낸다(내용은 남기지 않음)
            log.exception("chat stream failed: %s", type(e).__name__)
            yield sse({"type": "error", "code": "SERVICE_DEGRADED", "message": "일시적으로 답할 수 없습니다."})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
