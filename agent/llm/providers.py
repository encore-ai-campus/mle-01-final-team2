"""Provider 어댑터. 인터페이스는 generate(messages, schema=None)·stream(messages)·health() 세 가지다(§3).

- OpenAICompatProvider: vLLM(RunPod)·대체 호스트·대역 서버처럼 OpenAI 호환 API(/v1/chat/completions)를 쓰는 서버 전부.
- TemplateProvider: 모델을 부르지 않는다. 라우터가 이것까지 내려오면 '설명 없이 규칙 판정만'(degraded)이다.

재시도는 한 계층에서만 한다(§7.1): SDK 자체 재시도는 끄고(max_retries=0), 구조화 출력 검증 실패만 여기서 1회 다시 묻는다.
연결·시간 초과 같은 장애는 라우터가 다음 provider로 넘긴다.
"""
from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

Message = dict[str, str]  # {"role": "system|user|assistant", "content": "..."}


class LLMError(Exception):
    """모델 호출 실패의 공통 부모."""


class ProviderUnavailable(LLMError):
    """연결 실패·시간 초과·5xx·인증 실패처럼 provider를 바꿔야 하는 오류."""


class LLMOutputError(LLMError):
    """응답은 왔지만 스키마 검증을 1회 재시도 뒤에도 통과하지 못함(→ 요건은 unparsed로)."""


@dataclass
class Completion:
    text: str
    provider: str
    model: str | None = None
    parsed: BaseModel | None = None
    usage: dict[str, int] = field(default_factory=dict)


class Provider(Protocol):
    name: str
    kind: str          # openai_compat / template
    data_policy: str   # self_hosted / external

    async def generate(self, messages: list[Message], schema: type[BaseModel] | None = None) -> Completion: ...

    def stream(self, messages: list[Message], usage: dict[str, int] | None = None) -> AsyncIterator[str]: ...

    async def health(self) -> bool: ...


_JSON_BLOCK = re.compile(r"\{.*\}", re.S)


def _json_instruction(schema: type[BaseModel]) -> str:
    return ("다음 JSON 스키마에 맞는 JSON 객체 하나만 출력한다. 설명 문장, 코드 블록 표시(```)를 붙이지 않는다.\n"
            + json.dumps(schema.model_json_schema(), ensure_ascii=False))


def _parse(text: str, schema: type[BaseModel]) -> BaseModel:
    m = _JSON_BLOCK.search(text)
    return schema.model_validate_json(m.group(0) if m else text)


class OpenAICompatProvider:
    kind = "openai_compat"

    def __init__(self, name: str, base_url: str, model: str, api_key: str | None = None, timeout_s: float = 60.0,
                 data_policy: str = "self_hosted", json_schema: bool = False, http_client: Any = None,
                 temperature: float = 0.2, max_tokens: int = 800):
        from openai import AsyncOpenAI  # 설치 안 된 환경에서도 패키지 import는 되게 한다

        self.name, self.model, self.data_policy = name, model, data_policy
        self.json_schema, self.temperature, self.max_tokens = json_schema, temperature, max_tokens
        # vLLM은 --api-key를 주지 않으면 키를 검사하지 않지만 SDK는 값이 필요하다
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key or "EMPTY", timeout=timeout_s, max_retries=0,
                                   http_client=http_client)

    def __repr__(self) -> str:  # 키·주소를 로그에 남기지 않는다
        return f"OpenAICompatProvider(name={self.name!r}, model={self.model!r})"

    async def _create(self, **kw):
        import openai

        try:
            return await self._client.chat.completions.create(model=self.model, temperature=self.temperature,
                                                              max_tokens=self.max_tokens, **kw)
        except (openai.APIConnectionError, openai.APITimeoutError, openai.AuthenticationError,
                openai.PermissionDeniedError, openai.NotFoundError, openai.RateLimitError, openai.InternalServerError) as e:
            raise ProviderUnavailable(f"{self.name}: {type(e).__name__}") from e
        except openai.APIStatusError as e:  # 그 밖의 4xx(요청 형식 오류)는 다른 provider로 넘겨도 같으므로 그대로 알린다
            raise LLMError(f"{self.name}: HTTP {e.status_code}") from e

    async def generate(self, messages: list[Message], schema: type[BaseModel] | None = None) -> Completion:
        msgs = list(messages)
        kw: dict[str, Any] = {}
        if schema is not None:
            if self.json_schema:
                kw["response_format"] = {"type": "json_schema",
                                         "json_schema": {"name": schema.__name__, "schema": schema.model_json_schema()}}
            else:
                msgs = [{"role": "system", "content": _json_instruction(schema)}, *msgs]
        last_err: Exception | None = None
        for attempt in range(2 if schema is not None else 1):  # 구조화 출력 검증 실패만 1회 다시 묻는다
            r = await self._create(messages=msgs, **kw)
            text = (r.choices[0].message.content or "") if r.choices else ""
            usage = {"prompt_tokens": r.usage.prompt_tokens, "completion_tokens": r.usage.completion_tokens} if r.usage else {}
            if schema is None:
                return Completion(text=text, provider=self.name, model=r.model, usage=usage)
            try:
                return Completion(text=text, provider=self.name, model=r.model, parsed=_parse(text, schema), usage=usage)
            except (ValidationError, ValueError) as e:
                last_err = e
                msgs = [*msgs, {"role": "assistant", "content": text},
                        {"role": "user", "content": "출력이 스키마 검증을 통과하지 못했다. 스키마에 맞는 JSON 객체만 다시 출력한다."}]
        raise LLMOutputError(f"{self.name}: 스키마 검증 실패") from last_err

    async def stream(self, messages: list[Message], usage: dict[str, int] | None = None) -> AsyncIterator[str]:
        """설명 텍스트 조각을 낸다. usage dict를 넘기면 마지막 청크의 토큰 수를 채운다(vLLM stream_options 지원 시)."""
        import openai

        s = await self._create(messages=messages, stream=True, stream_options={"include_usage": True})
        try:
            async for chunk in s:
                if chunk.usage and usage is not None:
                    usage.update(prompt_tokens=chunk.usage.prompt_tokens, completion_tokens=chunk.usage.completion_tokens)
                if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except (openai.APIConnectionError, openai.APITimeoutError) as e:
            raise ProviderUnavailable(f"{self.name}: 스트림 중단 {type(e).__name__}") from e

    async def health(self) -> bool:
        try:
            await self._client.models.list()
            return True
        except Exception:
            return False


class TemplateProvider:
    """모델 없이 끝내는 마지막 단계. 텍스트를 만들지 않는다(설명은 에이전트의 고정 템플릿이 대신한다)."""

    kind = "template"

    def __init__(self, name: str = "rule_template"):
        self.name, self.data_policy = name, "self_hosted"

    async def generate(self, messages, schema=None) -> Completion:
        return Completion(text="", provider=self.name)

    async def stream(self, messages, usage=None):
        return
        yield  # 비동기 제너레이터로 만들기 위한 줄

    async def health(self) -> bool:
        return True
