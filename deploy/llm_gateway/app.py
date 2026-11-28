"""로컬 LLM 게이트웨이: vLLM과 같은 OpenAI 호환 API를 열고, 뒤에서는 외부 OpenAI 모델(gpt-6-luna)을 부른다.

RunPod vLLM(Qwen)이 준비되기 전에 API 서버를 **실제 모델**로 시험하기 위한 서버다(사용자 결정 2026-11-28, 로컬 시험 전용).
API 서버는 이 서버를 vLLM처럼 부른다(`VLLM_BASE_URL=http://llm:8001/v1`). RunPod로 옮길 때는 API 서버의
VLLM_BASE_URL·VLLM_MODEL만 바꾸고 이 컨테이너는 뺀다.

- 열어 두는 경로: GET /health, GET /v1/models, POST /v1/chat/completions(스트리밍 포함), POST /v1/embeddings
- 요청의 model 이름은 SERVED_MODEL(기본 gpt-6-luna)·SERVED_EMBED_MODEL만 받는다(vLLM의 --served-model-name과 같은 동작).
- 최신 OpenAI 모델과 vLLM의 파라미터 차이를 맞춘다: max_tokens → max_completion_tokens.
  모델이 temperature 같은 값을 받지 않으면(400) 그 값을 빼고 한 번만 다시 보낸다.
- 키: UPSTREAM_API_KEY, 없으면 OPENAI_API_KEY, 없으면 OPEN_API(기존 .env 이름). 값은 로그·응답에 남기지 않는다.
- GATEWAY_API_KEY를 주면 들어오는 요청의 Bearer 키를 검사한다(vLLM --api-key와 같은 동작).
- 요청·응답 본문은 로그에 남기지 않는다(경로·상태 코드·걸린 시간만).

실행: uvicorn deploy.llm_gateway.app:app --port 8001   (저장소 루트에서)
"""
from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

log = logging.getLogger("llm_gateway")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

UPSTREAM = os.environ.get("UPSTREAM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
UPSTREAM_MODEL = os.environ.get("UPSTREAM_MODEL", "gpt-6-luna")
SERVED_MODEL = os.environ.get("SERVED_MODEL", UPSTREAM_MODEL)
UPSTREAM_EMBED_MODEL = os.environ.get("UPSTREAM_EMBED_MODEL", "text-embedding-3-small")
SERVED_EMBED_MODEL = os.environ.get("SERVED_EMBED_MODEL", UPSTREAM_EMBED_MODEL)
TIMEOUT_S = float(os.environ.get("UPSTREAM_TIMEOUT_S", "120"))
GATEWAY_KEY = os.environ.get("GATEWAY_API_KEY") or None
DROPPABLE = ("temperature", "top_p", "presence_penalty", "frequency_penalty", "reasoning_effort", "stream_options")
# 추론형 모델은 max_completion_tokens 안에서 추론 토큰을 먼저 쓴다. vLLM식 max_tokens(답 길이)에 이만큼 더 얹는다
REASONING_BUDGET = int(os.environ.get("UPSTREAM_REASONING_BUDGET", "1024"))
REASONING_EFFORT = os.environ.get("UPSTREAM_REASONING_EFFORT", "low") or None  # 비우면 보내지 않는다
_dropped: set[str] = set()  # 상류가 거부한 파라미터. 한 번 거부되면 다음 요청부터 처음부터 뺀다


def _upstream_key() -> str | None:
    for name in ("UPSTREAM_API_KEY", "OPENAI_API_KEY", "OPEN_API"):
        v = (os.environ.get(name) or "").strip().strip('"').strip("'")
        if v:
            return v
    return None


_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_app):
    yield
    if _client is not None:
        await _client.aclose()


app = FastAPI(title="LLM gateway (vLLM-compatible, upstream OpenAI)", lifespan=lifespan)


def client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(base_url=UPSTREAM, timeout=httpx.Timeout(TIMEOUT_S, connect=10.0))
    return _client


def _err(status: int, message: str, kind: str = "invalid_request_error") -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"message": message, "type": kind}})


def _auth(authorization: str | None) -> None:
    if GATEWAY_KEY and authorization != f"Bearer {GATEWAY_KEY}":
        raise HTTPException(401, detail={"error": {"message": "invalid api key", "type": "invalid_request_error"}})


def _headers() -> dict[str, str]:
    key = _upstream_key()
    if not key:
        raise HTTPException(503, detail={"error": {"message": "upstream api key is not set", "type": "ServiceUnavailable"}})
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def translate_chat(body: dict) -> dict:
    """vLLM식 요청 → 상류 모델 요청. 들어온 dict는 바꾸지 않는다."""
    out = {k: v for k, v in body.items() if k not in ("max_tokens", "model")}
    out["model"] = UPSTREAM_MODEL
    if body.get("max_tokens") is not None and "max_completion_tokens" not in body:
        out["max_completion_tokens"] = int(body["max_tokens"]) + REASONING_BUDGET
    if REASONING_EFFORT and "reasoning_effort" not in body:
        out["reasoning_effort"] = REASONING_EFFORT
    for k in _dropped:
        out.pop(k, None)
    # vLLM 전용 확장 필드는 상류가 모르므로 뺀다
    for k in ("guided_json", "guided_regex", "guided_choice", "repetition_penalty", "top_k", "min_p"):
        out.pop(k, None)
    return out


def unsupported_param(resp_json: dict) -> str | None:
    """400 오류 본문에서 '지원하지 않는 파라미터' 이름을 찾는다. 없으면 None."""
    err = (resp_json or {}).get("error") or {}
    param = err.get("param")
    msg = (err.get("message") or "").lower()
    if param in DROPPABLE:
        return param
    for p in DROPPABLE:
        if p in msg and ("unsupported" in msg or "not support" in msg or "does not support" in msg or "only the default" in msg):
            return p
    return None


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "model": SERVED_MODEL, "embed_model": SERVED_EMBED_MODEL, "upstream_key": bool(_upstream_key())}


@app.get("/v1/models")
def models(authorization: str | None = Header(default=None)) -> dict:
    _auth(authorization)
    now = int(time.time())
    return {"object": "list", "data": [{"id": SERVED_MODEL, "object": "model", "created": now, "owned_by": "gateway"},
                                       {"id": SERVED_EMBED_MODEL, "object": "model", "created": now, "owned_by": "gateway"}]}


async def _post_json(path: str, payload: dict) -> httpx.Response:
    return await client().post(path, json=payload, headers=_headers())


@app.post("/v1/chat/completions")
async def chat(request: Request, authorization: str | None = Header(default=None)):
    _auth(authorization)
    body = await request.json()
    if body.get("model") != SERVED_MODEL:
        return _err(404, f"model {body.get('model')} not found", "NotFoundError")
    payload = translate_chat(body)
    t0 = time.monotonic()

    if not body.get("stream"):
        for _ in range(len(DROPPABLE) + 1):
            try:
                r = await _post_json("/chat/completions", payload)
            except httpx.HTTPError as e:
                log.warning("chat upstream error %s", type(e).__name__)
                return _err(503, "upstream unavailable", "ServiceUnavailable")
            if r.status_code == 400 and (p := unsupported_param(_safe_json(r))) and p in payload:
                payload.pop(p)
                _dropped.add(p)
                continue
            break
        log.info("chat status=%s ms=%d", r.status_code, (time.monotonic() - t0) * 1000)
        data = _safe_json(r)
        if r.status_code == 200 and isinstance(data, dict):
            data["model"] = SERVED_MODEL
        return JSONResponse(status_code=r.status_code, content=data)

    # 스트리밍: 첫 응답 상태를 보고 지원하지 않는 파라미터면 빼고 다시 연다(조각을 보내기 전이므로 안전)
    for _ in range(len(DROPPABLE) + 1):
        try:
            req = client().build_request("POST", "/chat/completions", json=payload, headers=_headers())
            resp = await client().send(req, stream=True)
        except httpx.HTTPError as e:
            log.warning("chat stream upstream error %s", type(e).__name__)
            return _err(503, "upstream unavailable", "ServiceUnavailable")
        if resp.status_code == 200:
            break
        raw = await resp.aread()
        await resp.aclose()
        try:
            data = json.loads(raw)
        except ValueError:
            data = {"error": {"message": "upstream error", "type": "upstream"}}
        if resp.status_code == 400 and (p := unsupported_param(data)) and p in payload:
            payload.pop(p)
            _dropped.add(p)
            continue
        log.info("chat stream status=%s", resp.status_code)
        return JSONResponse(status_code=resp.status_code, content=data)

    async def relay():
        try:
            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    yield "data: [DONE]\n\n"
                    break
                try:
                    obj = json.loads(data)
                    obj["model"] = SERVED_MODEL
                    yield f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"
                except ValueError:
                    continue
        except httpx.HTTPError as e:
            log.warning("chat stream cut %s", type(e).__name__)
        finally:
            await resp.aclose()
            log.info("chat stream done ms=%d", (time.monotonic() - t0) * 1000)

    return StreamingResponse(relay(), media_type="text/event-stream")


@app.post("/v1/embeddings")
async def embeddings(request: Request, authorization: str | None = Header(default=None)):
    _auth(authorization)
    body = await request.json()
    if body.get("model") != SERVED_EMBED_MODEL:
        return _err(404, f"model {body.get('model')} not found", "NotFoundError")
    payload = {**body, "model": UPSTREAM_EMBED_MODEL}
    try:
        r = await _post_json("/embeddings", payload)
    except httpx.HTTPError as e:
        log.warning("embed upstream error %s", type(e).__name__)
        return _err(503, "upstream unavailable", "ServiceUnavailable")
    data = _safe_json(r)
    if r.status_code == 200 and isinstance(data, dict):
        data["model"] = SERVED_EMBED_MODEL
    log.info("embed status=%s n=%s", r.status_code, len(body.get("input") or []) if isinstance(body.get("input"), list) else 1)
    return JSONResponse(status_code=r.status_code, content=data)


def _safe_json(r: httpx.Response):
    try:
        return r.json()
    except ValueError:
        return {"error": {"message": "upstream returned non-json", "type": "upstream"}}
