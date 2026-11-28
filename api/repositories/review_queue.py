"""요건 검수 큐 저장소(설계 docs/DESIGN_요건검수큐_v0.1.md, Q-1 임시 기본값: 로컬 jsonl).

큐 파일은 tools/requirement_review_queue.py build가 만든다. 이 저장소는 행 하나를 읽고 고쳐 쓴다.
- 파일 수정 시각으로 메모리 캐시를 맞춘다(다른 프로세스가 build를 다시 돌려도 따라간다).
- 쓰기는 잠금 + 임시 파일 교체(원자적)다. 읽은 줄을 그대로 들고 있다가 바뀐 행만 다시 직렬화한다(19MB 큐에서 전체 재직렬화를 피한다).
- 동시에 같은 공고를 고치면 나중 저장이 이긴다(검수자 2명 동시 작업은 Q-3과 함께 정한다).
- Supabase `review_queue`로 옮기면(Q-1 ②) 이 클래스만 바꾼다. 라우터는 그대로다.
"""
from __future__ import annotations

import json
import os
import threading
from collections.abc import Callable
from pathlib import Path


class ReviewQueueStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()
        self._mtime: float | None = None
        self._rows: list[dict] = []
        self._index: dict[str, int] = {}
        self._lines: list[str] = []  # 파일의 JSON 줄 그대로(행과 같은 순서)

    def _load(self) -> None:
        if not self.path.exists():
            self._rows, self._index, self._lines, self._mtime = [], {}, [], None
            return
        m = self.path.stat().st_mtime
        if m == self._mtime:
            return
        lines = [x for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]
        rows = [json.loads(x) for x in lines]
        self._rows, self._lines, self._index, self._mtime = rows, lines, {r["notice_id"]: i for i, r in enumerate(rows)}, m

    def available(self) -> bool:
        return self.path.exists()

    def rows(self) -> list[dict]:
        with self._lock:
            self._load()
            return list(self._rows)

    def get(self, notice_id: str) -> dict | None:
        with self._lock:
            self._load()
            i = self._index.get(notice_id)
            return None if i is None else dict(self._rows[i])

    def update(self, notice_id: str, fn: Callable[[dict], dict]) -> dict | None:
        """행 하나를 fn으로 바꿔 저장한다. 없으면 None."""
        with self._lock:
            self._load()
            i = self._index.get(notice_id)
            if i is None:
                return None
            new = fn(dict(self._rows[i]))
            rows, lines = list(self._rows), list(self._lines)
            rows[i], lines[i] = new, json.dumps(new, ensure_ascii=False, separators=(",", ":"))
            tmp = self.path.with_suffix(".jsonl.tmp")
            with tmp.open("w", encoding="utf-8", newline="\n") as f:
                f.write("\n".join(lines) + "\n")
            os.replace(tmp, self.path)
            self._rows, self._lines, self._mtime = rows, lines, self.path.stat().st_mtime
            return new
