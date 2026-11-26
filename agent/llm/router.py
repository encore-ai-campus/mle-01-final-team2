"""역할별(answer·extract) primary + fallbacks, 서킷브레이커, 데이터 정책 게이트(기초 설계서 §3).

- 스트리밍은 **첫 조각이 오기 전까지만** 다음 provider로 넘긴다. 이미 화면에 나간 문장을 다른 모델로 이어 쓰지 않는다.
- answer 역할은 사용자 조건·판정 결과를 담으므로 external provider를 쓰지 않는다.
- 연속 N회 실패하면 cooldown_s 동안 그 provider를 건너뛰고, 시간이 지나면 한 건씩 다시 시도한다.
"""
from __future__ import annotations

import os
import time
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from .providers import (Completion, LLMError, LLMOutputError, Message, OpenAICompatProvider, Provider, ProviderUnavailable,
                        TemplateProvider)

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO / "config" / "models.yaml"
EXTERNAL_FORBIDDEN_ROLES = {"answer"}


class AllProvidersFailed(LLMError):
    """역할의 모든 provider가 실패(템플릿 단계도 없음)."""


@dataclass
class _Breaker:
    failures: int = 0
    opened_at: float | None = None


@dataclass
class StreamHandle:
    """열린 스트림. provider·fallback_depth는 관측(Langfuse 태그 예정)과 화면 배너에 쓴다."""
    provider: str
    fallback_depth: int
    degraded: bool                       # 템플릿 단계까지 내려옴 = 설명 없음
    tried: list[str] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    _first: str | None = None
    _rest: AsyncIterator[str] | None = None

    async def tokens(self) -> AsyncIterator[str]:
        if self._first is not None:
            yield self._first
        if self._rest is not None:
            async for t in self._rest:
                yield t


class LLMRouter:
    def __init__(self, providers: Mapping[str, Provider], roles: Mapping[str, list[str]], fail_threshold: int = 3,
                 cooldown_s: float = 30.0, clock=time.monotonic):
        self.providers, self.roles = dict(providers), {k: list(v) for k, v in roles.items()}
        self.fail_threshold, self.cooldown_s, self._clock = fail_threshold, cooldown_s, clock
        self._breakers: dict[str, _Breaker] = {n: _Breaker() for n in self.providers}

    # ---------- 선택 ----------
    def chain(self, role: str) -> list[Provider]:
        out = []
        for name in self.roles.get(role, []):
            p = self.providers.get(name)
            if p is None:
                continue  # 설정에서 꺼진 provider(환경변수 없음)
            if p.data_policy == "external" and role in EXTERNAL_FORBIDDEN_ROLES:
                continue  # 사용자 조건·판정 결과는 외부로 보내지 않는다
            out.append(p)
        return out

    def _open(self, name: str) -> bool:
        b = self._breakers[name]
        if b.opened_at is None:
            return False
        if self._clock() - b.opened_at >= self.cooldown_s:
            return False  # 반쯤 열림: 한 건 시도해 보고 결과로 닫거나 다시 연다
        return True

    def _ok(self, name: str) -> None:
        self._breakers[name] = _Breaker()

    def _fail(self, name: str) -> None:
        b = self._breakers[name]
        b.failures += 1
        if b.failures >= self.fail_threshold:
            b.opened_at = self._clock()

    def status(self) -> dict[str, str]:
        return {n: ("open" if self._open(n) else "closed") for n in self.providers}

    # ---------- 호출 ----------
    async def generate(self, role: str, messages: list[Message], schema: type[BaseModel] | None = None) -> Completion:
        tried = []
        for depth, p in enumerate(self.chain(role)):
            if self._open(p.name):
                continue
            tried.append(p.name)
            try:
                c = await p.generate(messages, schema)
                self._ok(p.name)
                return c
            except ProviderUnavailable:
                self._fail(p.name)
            except LLMOutputError:
                self._ok(p.name)  # 서버는 살아 있다. 출력 문제는 호출한 쪽이 unparsed로 처리한다
                raise
        raise AllProvidersFailed(f"{role}: 시도 {tried or '없음'}")

    async def open_stream(self, role: str, messages: list[Message]) -> StreamHandle:
        tried = []
        for depth, p in enumerate(self.chain(role)):
            if self._open(p.name):
                continue
            tried.append(p.name)
            if p.kind == "template":
                return StreamHandle(provider=p.name, fallback_depth=depth, degraded=True, tried=tried)
            usage: dict[str, int] = {}
            it = p.stream(messages, usage).__aiter__()
            try:
                first = await it.__anext__()
            except StopAsyncIteration:
                first = None
            except ProviderUnavailable:
                self._fail(p.name)
                continue
            self._ok(p.name)
            return StreamHandle(provider=p.name, fallback_depth=depth, degraded=False, tried=tried, usage=usage,
                                _first=first, _rest=it)
        raise AllProvidersFailed(f"{role}: 시도 {tried or '없음'}")

    async def health(self) -> dict[str, bool]:
        return {n: await p.health() for n, p in self.providers.items()}


def _env_map(env_file: Path | None) -> dict[str, str]:
    env: dict[str, str] = {}
    if env_file and env_file.exists():
        from dotenv import dotenv_values

        env.update({k: v for k, v in dotenv_values(env_file).items() if v is not None})
    env.update(os.environ)  # 실제 환경변수가 .env보다 우선(Docker·서버 배포)
    return env


def load_router(config_path: str | Path | None = None, env: Mapping[str, str] | None = None,
                env_file: Path | None = REPO / ".env", http_client=None) -> LLMRouter:
    """config/models.yaml을 읽어 라우터를 만든다. base_url·model 환경변수가 비어 있는 provider는 등록하지 않는다."""
    import yaml

    path = Path(config_path or os.environ.get("MODELS_CONFIG") or DEFAULT_CONFIG)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    env = dict(env) if env is not None else _env_map(env_file)
    providers: dict[str, Provider] = {}
    for name, p in (cfg.get("providers") or {}).items():
        if p.get("enabled") is False:
            continue
        if p["type"] == "template":
            providers[name] = TemplateProvider(name)
        elif p["type"] == "openai_compat":
            base_url, model = env.get(p.get("base_url_env", "")), env.get(p.get("model_env", ""))
            if not base_url or not model:
                continue
            timeout = float(env.get(p.get("timeout_s_env", ""), "") or p.get("timeout_s", 60))
            providers[name] = OpenAICompatProvider(
                name, base_url=base_url, model=model, api_key=env.get(p.get("api_key_env", "")) or None, timeout_s=timeout,
                data_policy=p.get("data_policy", "self_hosted"), json_schema=bool((p.get("capabilities") or {}).get("json_schema")),
                http_client=http_client)
        else:
            raise ValueError(f"알 수 없는 provider type: {p['type']} ({name})")
    roles = {r: [v["primary"], *v.get("fallbacks", [])] for r, v in (cfg.get("roles") or {}).items()}
    cb = cfg.get("circuit_breaker") or {}
    return LLMRouter(providers, roles, fail_threshold=int(cb.get("failures", 3)), cooldown_s=float(cb.get("cooldown_s", 30)))
