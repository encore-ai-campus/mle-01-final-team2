"""S-01 `GET /api/meta`(공개): 데이터 기준 시각·버전·면책 문구·구간 코드표. 지금은 501을 낸다."""
from __future__ import annotations

from fastapi import APIRouter

from ..core.errors import not_implemented

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
def meta() -> dict:
    """명세 §2.1 meta(data_as_of·versions·disclaimer)와 §3.1 구간 코드표를 돌려준다. 로그인 없이 연다."""
    raise not_implemented("S-01", "출처별 수집 시각, 규칙·사전·스키마 버전, 면책 문구, 입력 구간 코드표를 돌려준다")
