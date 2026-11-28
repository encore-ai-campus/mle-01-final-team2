"""청크 임베딩 색인 만들기. 저장소 루트에서 실행한다(LLM 게이트웨이가 떠 있어야 한다).

  python -m agent.rag.build_index                 # 전체 청크(공고 요약·요건·신청 방법·첨부 구역)
  python -m agent.rag.build_index --open-only     # 모집 중 공고 청크만(빠른 시험용)

설정: EMBED_BASE_URL(없으면 VLLM_BASE_URL)·EMBED_MODEL·EMBED_DIM·RAG_INDEX_DIR. 로컬 예:
  EMBED_BASE_URL=http://localhost:8001/v1  EMBED_MODEL=text-embedding-3-small  EMBED_DIM=512
같은 내용의 청크는 다시 임베딩하지 않으므로 중간에 끊겨도 다시 실행하면 이어서 만든다(저장은 끝에 한 번).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--open-only", action="store_true", help="모집 중 공고 청크만")
    ap.add_argument("--batch", type=int, default=256)
    a = ap.parse_args(argv)

    sys.path.insert(0, str(REPO))
    from tools.graphrag.engine import Engine

    from .dense import build
    from .embedder import Embedder, config_from_env

    cfg = config_from_env()
    if cfg is None:
        print("EMBED_MODEL과 EMBED_BASE_URL(또는 VLLM_BASE_URL)을 설정하세요.", file=sys.stderr)
        return 2
    eng = Engine()
    chunks = eng.chunks
    if a.open_only:
        open_ids = {n["notice_id"] for n in eng.notices if eng.is_open(n)}
        chunks = [c for c in chunks if c["notice_id"] in open_ids]
    meta = build(chunks, Embedder(cfg, timeout_s=120), cfg.index_path, batch=a.batch)
    print(json.dumps({**meta, "index": cfg.index_name, "input_layer": eng.input_layer}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
