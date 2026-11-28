"""청크 임베딩 색인(로컬 파일). Supabase pgvector(`notice_chunks`)로 옮기기 전의 같은 역할이다(기초 설계서 §3·§8).

파일: <index_dir>/<index_name>/vectors.npy(float16, L2 정규화) · ids.json(청크 id 순서) · sha.json(내용 해시) · meta.json
- 청크 id는 엔진(tools/graphrag/data.py)이 만든 `<notice_id>#<section>:<i>`를 그대로 쓴다.
- 다시 만들 때 내용 해시가 같은 청크는 임베딩하지 않는다(설계서 §5 index 단계 "같은 청크는 다시 만들지 않음").
- 색인은 원문을 담지 않는다(벡터와 id만). 원문은 엔진 청크에서 찾는다.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable, Iterable
from pathlib import Path

import numpy as np

from .embedder import MAX_CHARS, Embedder


def sha(text: str) -> str:
    return hashlib.sha256(text[:MAX_CHARS].encode("utf-8")).hexdigest()[:16]


class DenseIndex:
    def __init__(self, ids: list[str], vectors: np.ndarray, meta: dict | None = None):
        self.ids = ids
        self.pos = {cid: i for i, cid in enumerate(ids)}
        self.vectors = vectors.astype(np.float32)  # 검색 때는 float32로 계산한다
        self.meta = meta or {}

    def __len__(self) -> int:
        return len(self.ids)

    @classmethod
    def load(cls, path: Path) -> DenseIndex | None:
        if not (path / "vectors.npy").exists():
            return None
        ids = json.loads((path / "ids.json").read_text(encoding="utf-8"))
        meta = json.loads((path / "meta.json").read_text(encoding="utf-8")) if (path / "meta.json").exists() else {}
        return cls(ids, np.load(path / "vectors.npy"), meta)

    def search(self, qvec: Iterable[float], allowed: Callable[[str], bool] | None = None, top: int = 50) -> list[tuple[str, float]]:
        q = np.asarray(list(qvec), dtype=np.float32)
        n = float(np.linalg.norm(q)) or 1.0
        scores = self.vectors @ (q / n)
        order = np.argsort(-scores)
        out: list[tuple[str, float]] = []
        for i in order:
            cid = self.ids[int(i)]
            if allowed is not None and not allowed(cid):
                continue
            out.append((cid, float(scores[int(i)])))
            if len(out) >= top:
                break
        return out


def build(chunks: list[dict], embedder: Embedder, path: Path, batch: int = 256,
          log: Callable[[str], None] = print) -> dict:
    """청크 전부를 임베딩해 저장한다. 이미 있는 색인에서 내용 해시가 같은 벡터는 다시 쓴다."""
    path.mkdir(parents=True, exist_ok=True)
    old_vec: dict[str, np.ndarray] = {}
    if (path / "vectors.npy").exists() and (path / "sha.json").exists():
        o_ids = json.loads((path / "ids.json").read_text(encoding="utf-8"))
        o_sha = json.loads((path / "sha.json").read_text(encoding="utf-8"))
        o_vecs = np.load(path / "vectors.npy")
        old_vec = {f"{cid}|{h}": o_vecs[i] for i, (cid, h) in enumerate(zip(o_ids, o_sha))}

    ids = [c["chunk_id"] for c in chunks]
    shas = [sha(c["text"]) for c in chunks]
    vecs: list[np.ndarray | None] = [old_vec.get(f"{cid}|{h}") for cid, h in zip(ids, shas)]
    todo = [i for i, v in enumerate(vecs) if v is None]
    log(f"청크 {len(ids)}개, 재사용 {len(ids) - len(todo)}개, 새로 임베딩 {len(todo)}개")
    t0 = time.monotonic()
    for k in range(0, len(todo), batch):
        part = todo[k:k + batch]
        embs = embedder.embed([chunks[i]["text"] for i in part])
        for i, e in zip(part, embs):
            v = np.asarray(e, dtype=np.float32)
            vecs[i] = (v / (np.linalg.norm(v) or 1.0)).astype(np.float16)
        if (k // batch) % 10 == 0:
            log(f"  {min(k + batch, len(todo))}/{len(todo)} ({time.monotonic() - t0:.0f}s)")
    mat = np.vstack(vecs).astype(np.float16) if vecs else np.zeros((0, embedder.cfg.dim or 1), dtype=np.float16)
    np.save(path / "vectors.npy", mat)
    (path / "ids.json").write_text(json.dumps(ids, ensure_ascii=False), encoding="utf-8")
    (path / "sha.json").write_text(json.dumps(shas), encoding="utf-8")
    meta = {"model": embedder.cfg.model, "dim": int(mat.shape[1]) if mat.size else embedder.cfg.dim, "chunks": len(ids),
            "embedded_now": len(todo), "truncated": sum(len(c["text"]) > MAX_CHARS for c in chunks),
            "max_chars": MAX_CHARS, "built_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    (path / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    return meta
