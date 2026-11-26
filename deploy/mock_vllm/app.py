"""vLLM 대역 서버: OpenAI 호환 API(/v1/models, /v1/chat/completions)를 흉내 낸다.

RunPod vLLM이 준비되기 전에 API·에이전트를 같은 코드로 개발·시험하기 위한 서버다. 진짜 모델이 아니다.
- 답은 결정적이다. 에이전트 프롬프트의 <context>{...}</context> JSON을 읽어 판정·미확인 조건을 문장으로 옮긴다.
- 스트리밍(SSE, data: ... / data: [DONE])과 stream_options.include_usage를 지원한다.
- response_format(json_schema)이나 'JSON 객체 하나만 출력' 지시가 있으면 스키마의 필수 필드를 채운 JSON을 낸다.
- 장애 흉내: 환경변수 MOCK_FAIL=1이면 항상 503, MOCK_TOKEN_DELAY_MS로 조각 사이 지연.
  시험용 표식: 마지막 user 메시지에 [[mock:error]]가 있으면 503, [[mock:forbidden]]이면 금지 표현이 섞인 답.

실행: uvicorn deploy.mock_vllm.app:app --port 8001   (저장소 루트에서)
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

MODEL = os.environ.get("MOCK_MODEL", "mock-qwen")
API_KEY = os.environ.get("MOCK_API_KEY")  # 주면 Bearer 키를 검사(vLLM --api-key와 같은 동작)

app = FastAPI(title="mock vLLM (OpenAI compatible)")

VERDICT_KO = {"ELIGIBLE": "평가한 요건을 모두 충족하는 것으로 나왔습니다", "NOT_ELIGIBLE": "충족하지 않는 요건이 있습니다",
              "NEEDS_CHECK": "확인이 필요한 요건이 남아 있습니다"}


def _auth(authorization: str | None) -> None:
    if API_KEY and authorization != f"Bearer {API_KEY}":
        raise HTTPException(401, detail={"error": {"message": "invalid api key", "type": "invalid_request_error"}})


def _context(messages: list[dict]) -> dict | None:
    for m in reversed(messages):
        found = re.search(r"<context>(.*?)</context>", m.get("content") or "", re.S)
        if found:
            try:
                return json.loads(found.group(1))
            except ValueError:
                return None
    return None


def _explain(ctx: dict) -> str:
    out = []
    for n in ctx.get("notices", [])[:5]:
        title = n.get("title") or n.get("notice_id")
        line = f"「{title}」은(는) {VERDICT_KO.get(n.get('verdict'), '판정을 확인해야 합니다')}."
        gaps = [c for c in n.get("conditions", []) if c.get("status") != "SATISFIED"][:3]
        if gaps:
            line += " " + " ".join(f"{c.get('attribute')} 조건은 {c.get('reason') or c.get('status')}입니다 [{c.get('cond_id')}]."
                                   for c in gaps)
        out.append(line)
    if not out:
        return "평가 결과가 비어 있어 설명할 내용이 없습니다."
    out.append("최종 신청 가능 여부는 공고 원문과 주관 기관에서 확인해 주세요.")
    return " ".join(out)


def _fill(schema: dict, defs: dict | None = None):
    defs = defs if defs is not None else schema.get("$defs", {})
    if "$ref" in schema:
        return _fill(defs[schema["$ref"].split("/")[-1]], defs)
    if "anyOf" in schema:
        return _fill(schema["anyOf"][0], defs)
    if "enum" in schema:
        return schema["enum"][0]
    t = schema.get("type")
    if t == "object":
        props = schema.get("properties", {})
        return {k: _fill(props[k], defs) for k in schema.get("required", list(props))}
    return {"string": "", "integer": 0, "number": 0, "boolean": False, "array": [], "null": None}.get(t, None)


def _reply(body: dict) -> str:
    messages = body.get("messages", [])
    last_user = next((m.get("content") or "" for m in reversed(messages) if m.get("role") == "user"), "")
    rf = body.get("response_format") or {}
    if rf.get("type") == "json_schema":
        return json.dumps(_fill(rf["json_schema"]["schema"]), ensure_ascii=False)
    for m in messages:
        if m.get("role") == "system" and "JSON 객체 하나만 출력" in (m.get("content") or ""):
            try:
                return json.dumps(_fill(json.loads(m["content"].split("\n", 1)[1])), ensure_ascii=False)
            except (ValueError, IndexError, KeyError):
                return "{}"
    if "[[mock:forbidden]]" in last_user:
        return "이 공고는 조건이 맞습니다. 지원금을 받을 수 있습니다. 반드시 선정됩니다."
    ctx = _context(messages)
    if ctx is not None:
        return _explain(ctx)
    return f"(대역 서버 응답) 질문을 받았습니다: {last_user[:80]}"


def _pieces(text: str) -> list[str]:
    return re.findall(r"\S+\s*", text) or [text]


def _usage(body: dict, text: str) -> dict:
    p = sum(len(m.get("content") or "") for m in body.get("messages", [])) // 2
    c = max(1, len(text) // 2)
    return {"prompt_tokens": p, "completion_tokens": c, "total_tokens": p + c}


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL}


@app.get("/v1/models")
def models(authorization: str | None = Header(default=None)):
    _auth(authorization)
    return {"object": "list", "data": [{"id": MODEL, "object": "model", "created": 0, "owned_by": "mock"}]}


@app.post("/v1/chat/completions")
async def chat(request: Request, authorization: str | None = Header(default=None)):
    _auth(authorization)
    body = await request.json()
    if body.get("model") != MODEL:
        return JSONResponse(status_code=404, content={"error": {"message": f"model {body.get('model')} not found",
                                                                "type": "NotFoundError"}})
    last_user = next((m.get("content") or "" for m in reversed(body.get("messages", [])) if m.get("role") == "user"), "")
    if os.environ.get("MOCK_FAIL") == "1" or "[[mock:error]]" in last_user:
        return JSONResponse(status_code=503, content={"error": {"message": "mock failure", "type": "ServiceUnavailable"}})
    text = _reply(body)
    cid, created = f"chatcmpl-{uuid.uuid4().hex[:12]}", int(time.time())
    if not body.get("stream"):
        return {"id": cid, "object": "chat.completion", "created": created, "model": MODEL,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
                "usage": _usage(body, text)}

    delay = float(os.environ.get("MOCK_TOKEN_DELAY_MS", "0")) / 1000
    include_usage = bool((body.get("stream_options") or {}).get("include_usage"))

    async def events():
        def chunk(delta: dict, finish=None):
            return {"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL,
                    "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}

        yield f"data: {json.dumps(chunk({'role': 'assistant', 'content': ''}), ensure_ascii=False)}\n\n"
        for piece in _pieces(text):
            if delay:
                await asyncio.sleep(delay)
            yield f"data: {json.dumps(chunk({'content': piece}), ensure_ascii=False)}\n\n"
        yield f"data: {json.dumps(chunk({}, 'stop'), ensure_ascii=False)}\n\n"
        if include_usage:
            u = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL, "choices": [],
                 "usage": _usage(body, text)}
            yield f"data: {json.dumps(u, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
