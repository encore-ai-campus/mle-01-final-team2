"""S-01 `GET /api/meta`(공개): 데이터 기준 시각·버전·면책 문구·출처 이용 조건·구간 코드표."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.config import Settings, get_settings
from ..dependencies import get_eligibility_service
from ..services.meta import build_meta

router = APIRouter(prefix="/api", tags=["meta"])


def _snapshot() -> str | None:
    from tools.graphrag import cleaned

    if not cleaned.available():
        return None
    return (cleaned.CLEANED / "LATEST").read_text().strip()


@router.get("/meta")
def meta(settings: Settings = Depends(get_settings), service=Depends(get_eligibility_service)) -> dict:
    """명세 §2.1 meta와 §3.1 구간 코드표. 로그인 없이 연다. 구간 경계는 API-9 확정 전 임시 기본값."""
    engine = getattr(service, "_engine", None)
    notices = engine.notices if engine is not None else []
    return build_meta(notices, stale_hours=settings.stale_hours, model=settings.vllm_model, data_snapshot=_snapshot())
