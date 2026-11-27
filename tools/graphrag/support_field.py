"""지원분야 통합 분류(검색 필터 전용, 판정에는 쓰지 않는다).

기업마당 대분류 8개를 표준으로 삼고 K-Startup 분류 11개를 대응시킨다(`data/ref/term_standard_v0.1.json`의
`support_field_mapping(proposed)`). 2026-11-27 회의(B-5)로 정했다:
- 행사ㆍ네트워크 → 기타
- 판로ㆍ해외진출 → 공고마다 나눈다. 해외 키워드가 있으면 수출, 국내 판로 키워드만 있으면 내수, 둘 다 없으면 내수·수출
"""
from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path

TERMS = Path(__file__).resolve().parents[2] / "data" / "ref" / "term_standard_v0.1.json"


@lru_cache(maxsize=1)
def _mapping() -> dict:
    return json.loads(TERMS.read_text(encoding="utf-8"))["support_field_mapping(proposed)"]


def normalize_category(raw: str | None) -> str:
    return html.unescape(raw or "").replace("·", "ㆍ").strip()


def support_fields(source: str, category: str | None, text: str = "") -> list[str]:
    """공고 하나의 표준 지원분야 목록. 기업마당은 대분류 그대로, K-Startup은 매핑표와 공고별 나눔 규칙을 쓴다."""
    m = _mapping()
    cat = normalize_category(category)
    if not cat:
        return []
    if source == "BIZINFO":
        return [cat] if cat in m["standard"] else ["기타"]
    split = m.get("per_notice_split", {}).get(cat)
    if split:
        overseas = re.search(split["수출"], text or "", re.I)
        domestic = re.search(split["내수"], text or "")
        if overseas:
            return ["수출"]
        if domestic:
            return ["내수"]
        return ["내수", "수출"]
    return list(m["kstartup_to_standard"].get(cat, ["기타"]))
