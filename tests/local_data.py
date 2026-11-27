"""로컬 전용 데이터가 있어야 도는 시험을 표시한다. 데이터가 없는 PC·CI에서는 오류 대신 건너뛴다.

로컬 전용 데이터(나라장터 정규화 스냅숏, api_samples 등)는 용량·저작권 때문에 git에 없다. 받는 방법은 docs/GUIDE_개발시작_v0.1.md.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G2B_SNAPSHOT = ROOT / "data" / "normalized" / "v1" / "20261125_g2b"
API_SAMPLES = ROOT / "api_samples" / "normalized"


def needs(*paths: Path):
    """paths가 모두 있을 때만 돈다. 클래스·메서드 모두에 붙일 수 있다."""
    missing = [p for p in paths if not p.exists()]
    return unittest.skipIf(missing, "로컬 전용 데이터 없음: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))
