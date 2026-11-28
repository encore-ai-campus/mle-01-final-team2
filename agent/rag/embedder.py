"""임베딩 어댑터(기초 설계서 §3 "Embedder"). OpenAI 호환 /v1/embeddings만 쓴다.

- 로컬: LLM 게이트웨이(deploy/llm_gateway)의 /v1/embeddings → text-embedding-3-small.
- 운영: 임베딩 모델(KURE-v1·bge-m3·multilingual-e5 후보, ADR-1)을 vLLM·TEI 같은 OpenAI 호환 서버로 띄우면 주소만 바꾼다.
- 설정은 config/models.yaml의 embedding 절이 가리키는 환경변수에서 읽는다. 비어 있으면 None(→ BM25만).
- 재시도는 하지 않는다(SDK 재시도도 끔). 실패하면 호출한 쪽이 BM25로 낮춘다.
"""
from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MAX_CHARS = 2000  # 청크 앞부분만 임베딩한다(입력 한도·비용). 잘린 청크 수는 색인 meta에 남긴다


class EmbeddingError(Exception):
    pass


@dataclass
class EmbedConfig:
    base_url: str
    model: str
    api_key: str | None
    dim: int | None
    index_dir: Path

    @property
    def index_name(self) -> str:
        safe = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in self.model)
        return f"dense_{safe}_{self.dim or 'native'}"

    @property
    def index_path(self) -> Path:
        return self.index_dir / self.index_name


def config_from_env(env: Mapping[str, str] | None = None, config_path: Path | None = None) -> EmbedConfig | None:
    import yaml

    from agent.llm.router import DEFAULT_CONFIG, _env_map

    env = dict(env) if env is not None else _env_map(REPO / ".env")
    cfg = yaml.safe_load(Path(config_path or os.environ.get("MODELS_CONFIG") or DEFAULT_CONFIG).read_text(encoding="utf-8"))
    e = cfg.get("embedding") or {}
    model = env.get(e.get("model_env", "EMBED_MODEL"))
    base = env.get(e.get("base_url_env", "EMBED_BASE_URL")) or env.get("VLLM_BASE_URL")
    if not model or not base:
        return None
    dim = env.get(e.get("dim_env", "EMBED_DIM"))
    idx = env.get(e.get("index_dir_env", "RAG_INDEX_DIR"))
    return EmbedConfig(base_url=base, model=model, api_key=env.get(e.get("api_key_env", "EMBED_API_KEY")) or env.get("VLLM_API_KEY") or None,
                       dim=int(dim) if dim else None, index_dir=Path(idx) if idx else REPO / "data" / "index")


class Embedder:
    """동기 클라이언트. 검색은 스레드에서 부르고(엔진 검색이 동기), 색인 생성은 배치로 부른다."""

    def __init__(self, cfg: EmbedConfig, timeout_s: float = 30.0, http_client=None):
        from openai import OpenAI

        self.cfg = cfg
        self._client = OpenAI(base_url=cfg.base_url, api_key=cfg.api_key or "EMPTY", timeout=timeout_s, max_retries=0,
                              http_client=http_client)

    def __repr__(self) -> str:  # 주소·키를 남기지 않는다
        return f"Embedder(model={self.cfg.model!r}, dim={self.cfg.dim})"

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        import openai

        kw = {"dimensions": self.cfg.dim} if self.cfg.dim else {}
        try:
            r = self._client.embeddings.create(model=self.cfg.model, input=[t[:MAX_CHARS] or " " for t in texts], **kw)
        except openai.OpenAIError as e:
            raise EmbeddingError(type(e).__name__) from e
        return [d.embedding for d in sorted(r.data, key=lambda d: d.index)]
