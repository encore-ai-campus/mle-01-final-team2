"""로컬 전용 데이터가 있어야 도는 시험을 표시한다. 데이터가 없는 PC·CI에서는 오류 대신 건너뛴다.

로컬 전용 데이터(나라장터 정규화 스냅숏, api_samples 등)는 용량·저작권 때문에 git에 없다. 받는 방법은 docs/GUIDE_개발시작_v0.1.md.
"""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G2B_SNAPSHOT = ROOT / "data" / "normalized" / "v1" / "20261125_g2b"
API_SAMPLES = ROOT / "api_samples" / "normalized"
# notices.jsonl만 git(LFS)에 있다(PR #39). 청크·정규화 보고서까지 있어야 하는 시험은 이 묶음으로 건너뛴다
G2B_FULL = (G2B_SNAPSHOT / "notices.jsonl", G2B_SNAPSHOT / "chunks.jsonl", G2B_SNAPSHOT / "normalization_report.json")
# LLM 파일럿 실행 기록(실제 OpenAI 호출 결과·요청 장부). 실행한 PC에만 있고 git에는 없다(2026-11-28 확인).
# 가짜로 만들면 실제 실행 기록처럼 보이므로 만들지 않고, 없으면 해당 시험을 건너뛴다.
LLM_DEV = ROOT / "data" / "evaluations" / "conditions" / "v1.1" / "20261126" / "development"
LLM_R2_GATE = LLM_DEV / "llm_pilot_2_5c3_r2" / "lead_retry_gate.json"
LLM_P8 = (LLM_DEV / "llm_pilot_2_5c3_r2_norm_v2_p8" / "manifest.json", LLM_DEV / "llm_pilot_2_5c3_r2_norm_v2_p8" / "request_ledger.json")
LLM_RECOVERY = LLM_DEV / "llm_pilot_2_5c3_r2_norm_v2_recovery_v1" / "manifest.json"
LLM_P12_CLAIM = LLM_DEV / ".llm_pilot_2_5c3_r2_p12_claim.json"


def needs(*paths: Path):
    """paths가 모두 있을 때만 돈다. 클래스·메서드 모두에 붙일 수 있다."""
    missing = [p for p in paths if not p.exists()]
    return unittest.skipIf(missing, "로컬 전용 데이터 없음: " + ", ".join(str(p.relative_to(ROOT)) for p in missing))
