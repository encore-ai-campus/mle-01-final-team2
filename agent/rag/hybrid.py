"""하이브리드 검색: BM25(전문) + 벡터(임베딩) → RRF(기초 설계서 §7 "후보 검색(하이브리드)").

- 정형 조건(마감·상태·불가 판정)은 호출한 쪽이 먼저 걸러 `allowed_notices`로 넘긴다(유사도보다 선행).
- 벡터 색인이나 임베딩 서버가 없거나 실패하면 BM25만으로 낮춘다(`mode="bm25"`). 검색은 모델 호출 없이도 된다.
- RRF: score = Σ w / (k + rank). k=60(관례값), 가중치는 평가셋으로 정할 때까지 1:1(팀 결정 전).
- `search()`는 엔진(tools/graphrag/engine.py)의 BM25.search와 같은 모양([(score, chunk)])이라 그대로 바꿔 끼운다.
"""
from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from collections.abc import Iterable

from .dense import DenseIndex
from .embedder import EmbedConfig, Embedder, EmbeddingError

log = logging.getLogger("jiwongak.rag")
K_RRF = 60
POOL = 100  # 각 검색기에서 받아 오는 후보 수


class HybridRetriever:
    def __init__(self, chunks: list[dict], bm25, dense: DenseIndex | None = None, embedder: Embedder | None = None,
                 k: int = K_RRF, w_bm25: float = 1.0, w_dense: float = 1.0):
        self.chunks, self.bm25, self.dense, self.embedder = chunks, bm25, dense, embedder
        self.by_id = {c["chunk_id"]: c for c in chunks}
        self.k, self.w_bm25, self.w_dense = k, w_bm25, w_dense
        self._qcache: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()
        self.last_error: str | None = None

    @property
    def dense_ready(self) -> bool:
        return self.dense is not None and self.embedder is not None and len(self.dense) > 0

    def status(self) -> dict:
        return {"dense": self.dense_ready, "chunks": len(self.chunks),
                "indexed": len(self.dense) if self.dense is not None else 0,
                "model": (self.dense.meta.get("model") if self.dense is not None else None),
                "dim": (self.dense.meta.get("dim") if self.dense is not None else None),
                "last_error": self.last_error}

    def _qvec(self, query: str) -> list[float] | None:
        with self._lock:
            if query in self._qcache:
                self._qcache.move_to_end(query)
                return self._qcache[query]
        try:
            v = self.embedder.embed([query])[0]  # type: ignore[union-attr]
        except EmbeddingError as e:
            self.last_error = str(e)
            log.warning("query embedding failed: %s", e)
            return None
        with self._lock:
            self._qcache[query] = v
            if len(self._qcache) > 256:
                self._qcache.popitem(last=False)
        self.last_error = None
        return v

    def search_detailed(self, query: str, allowed_notices: Iterable[str] | None = None, top: int = 20) -> dict:
        allowed = set(allowed_notices) if allowed_notices is not None else None
        bm = self.bm25.search(query, allowed, top=POOL)
        rows: dict[str, dict] = {}
        for rank, (s, c) in enumerate(bm, 1):
            rows[c["chunk_id"]] = {"chunk": c, "rank_bm25": rank, "bm25": round(s, 3), "rank_dense": None, "dense": None}
        mode = "bm25"
        if self.dense_ready and query.strip():
            qv = self._qvec(query)
            if qv is not None:
                mode = "hybrid"
                ok = (lambda cid: (c := self.by_id.get(cid)) is not None and c["notice_id"] in allowed) if allowed is not None \
                    else (lambda cid: cid in self.by_id)
                for rank, (cid, s) in enumerate(self.dense.search(qv, ok, top=POOL), 1):  # type: ignore[union-attr]
                    r = rows.setdefault(cid, {"chunk": self.by_id[cid], "rank_bm25": None, "bm25": None})
                    r["rank_dense"], r["dense"] = rank, round(s, 4)
        for r in rows.values():
            r["score"] = (self.w_bm25 / (self.k + r["rank_bm25"]) if r["rank_bm25"] else 0.0) + \
                         (self.w_dense / (self.k + r["rank_dense"]) if r.get("rank_dense") else 0.0)
        hits = sorted(rows.values(), key=lambda r: -r["score"])[:top]
        return {"mode": mode, "hits": hits}

    def search(self, query: str, allowed_notices: set[str] | None = None, top: int = 20) -> list[tuple[float, dict]]:
        return [(h["score"], h["chunk"]) for h in self.search_detailed(query, allowed_notices, top)["hits"]]


def from_env(chunks: list[dict], bm25, cfg: EmbedConfig | None = None) -> HybridRetriever:
    """설정이 있고 색인 파일이 있으면 벡터까지, 아니면 BM25만 쓰는 검색기."""
    from .embedder import config_from_env

    cfg = cfg if cfg is not None else config_from_env()
    if cfg is None:
        return HybridRetriever(chunks, bm25)
    dense = DenseIndex.load(cfg.index_path)
    if dense is None:
        log.warning("dense index not found (%s); BM25 only. build: python -m agent.rag.build_index", cfg.index_name)
        return HybridRetriever(chunks, bm25)
    return HybridRetriever(chunks, bm25, dense, Embedder(cfg))
