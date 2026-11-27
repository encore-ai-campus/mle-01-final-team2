"""공고 목록·상세 API의 임시 로컬 데이터 구현.

기업마당, K-Startup, 나라장터 공고 조회를 지원한다.
정규화층에서 공개가 허용된 청크만 상세 응답에 포함한다.
평가 스냅샷 저장소 연결 전까지 N-03은 501로 유지한다.
"""

from __future__ import annotations

from collections import Counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.errors import not_implemented
from ..dependencies import get_notice_engine
from ..dependencies.auth import CurrentUser, get_current_user


router = APIRouter(prefix="/api", tags=["notices"])

SUPPORTED_SOURCES = frozenset({
    "BIZINFO",
    "KSTARTUP",
    "G2B",
})

SEARCH_FIELDS = ("notice_id", "title", "org")

Notice = dict[str, Any]
Chunk = dict[str, Any]

UserDep = Annotated[CurrentUser, Depends(get_current_user)]
EngineDep = Annotated[Any, Depends(get_notice_engine)]


def _api_error(
    status_code: int,
    code: str,
    message: str,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={
            "error": {
                "code": code,
                "message": message,
            }
        },
    )


def _normalize_source(source: str | None) -> str | None:
    """출처 필터를 정규화하고 빈 입력은 무시한다."""

    normalized = (source or "").strip().upper()

    if not normalized:
        return None

    if normalized not in SUPPORTED_SOURCES:
        supported = ", ".join(sorted(SUPPORTED_SOURCES))

        raise _api_error(
            400,
            "INVALID_SOURCE",
            f"source는 다음 중 하나여야 합니다: {supported}",
        )

    return normalized


def _matches_query(notice: Notice, needle: str) -> bool:
    return not needle or any(
        needle in str(notice.get(field) or "").casefold()
        for field in SEARCH_FIELDS
    )


def _sort_key(notice: Notice) -> tuple:
    deadline = notice.get("deadline")

    return (
        deadline is None,
        deadline or "9999-12-31",
        notice.get("title") or "",
        notice["notice_id"],
    )


def _status_key(notice: Notice, is_open: bool) -> str:
    if not is_open:
        return "closed"

    return (
        "open_with_deadline"
        if notice.get("deadline")
        else "open_no_date"
    )


def _is_visible_chunk(chunk: Chunk) -> bool:
    """정규화층에서 공개 가능 상태가 확정된 청크만 허용한다."""

    origin = str(chunk.get("origin") or "").strip().upper()
    text = chunk.get("text")

    return (
        chunk.get("privacy_status") == "CLEARED"
        and chunk.get("search_eligible") is True
        and bool(origin)
        and origin != "UNKNOWN"
        and not origin.startswith("ATTACHMENT")
        and isinstance(text, str)
        and bool(text.strip())
    )


def _get_notice_chunks(
    notice_id: str,
    engine: Any,
) -> list[Chunk]:
    """정규화된 공개용 청크 인덱스를 사용한다."""

    index = getattr(engine, "public_chunks_by_notice", None)

    if index is None:
        raise _api_error(
            503,
            "PUBLIC_CONTENT_UNAVAILABLE",
            "공고 본문의 공개용 데이터가 준비되지 않았습니다.",
        )

    return [
        chunk
        for chunk in index.get(notice_id, ())
        if chunk.get("notice_id") == notice_id
        and _is_visible_chunk(chunk)
    ]


@router.get("/notices")
def list_notices(
    user: UserDep,
    engine: EngineDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    source: Annotated[str | None, Query(max_length=20)] = None,
    include_closed: bool = False,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> dict[str, Any]:
    """N-01 공고 목록 및 검색. 자격 판정은 수행하지 않는다."""

    source_filter = _normalize_source(source)
    needle = (q or "").strip().casefold()

    rows: list[tuple[Notice, bool]] = []
    counts: Counter[str] = Counter()

    for notice in engine.notices:
        notice_source = str(
            notice.get("source") or ""
        ).strip().upper()

        if source_filter and notice_source != source_filter:
            continue

        if not _matches_query(notice, needle):
            continue

        is_open = engine.is_open(notice)

        if not include_closed and not is_open:
            continue

        rows.append((notice, is_open))
        counts[_status_key(notice, is_open)] += 1

    rows.sort(key=lambda item: _sort_key(item[0]))

    total = len(rows)
    offset = (page - 1) * size

    return {
        "items": [
            _summary(notice, engine, is_open=is_open)
            for notice, is_open in rows[offset:offset + size]
        ],
        "page": page,
        "size": size,
        "total": total,
        "pages": (total + size - 1) // size,
        "counts": dict(counts),
    }


@router.get("/notices/{notice_id}")
def get_notice(
    notice_id: str,
    user: UserDep,
    engine: EngineDep,
) -> dict[str, Any]:
    """N-02 공고 상세 및 공개용 원문 청크 조회."""

    notice = engine.by_id.get(notice_id)

    if notice is None:
        raise _api_error(
            404,
            "NOT_FOUND",
            "공고를 찾을 수 없습니다.",
        )

    chunks = _get_notice_chunks(notice_id, engine)

    sections = [
        {
            "section": chunk.get("section"),
            "origin": chunk.get("origin"),
            "text": chunk["text"],
            "source_span": None,
        }
        for chunk in chunks
    ]

    return {
        **_summary(notice, engine),
        "sections": sections,
        "attachments": [],
        "contacts": [],
        "supersedes": None,
        "superseded_by": None,
        "requirements_status": "unparsed",
    }


@router.get("/notices/{notice_id}/spans")
def get_notice_spans(
    notice_id: str,
    user: UserDep,
    evaluation_id: Annotated[
        str | None,
        Query(max_length=80),
    ] = None,
) -> dict[str, Any]:
    """N-03 평가 스냅샷 저장소 연결 이후 구현한다."""

    raise not_implemented(
        "N-03",
        "evaluation_id 스냅샷에서 판정 근거의 원문 위치를 조회한다",
    )


def _region_names(
    notice: Notice,
    engine: Any,
) -> list[str]:
    """지역 식별자의 중복을 제거하고 명칭으로 변환한다."""

    region_ids: dict[str, None] = {}

    for condition in notice.get("conditions") or []:
        if condition.get("attribute") != "region":
            continue

        value = condition.get("value")

        if not isinstance(value, dict):
            continue

        region_id = value.get("concept_id")

        if isinstance(region_id, str) and region_id:
            region_ids[region_id] = None

    return [
        engine.rg.name(region_id)
        for region_id in region_ids
    ]


def _notice_type(notice: Notice) -> str:
    """원본 공고 유형을 우선 보존한다."""

    notice_type = notice.get("notice_type")

    if isinstance(notice_type, str) and notice_type.strip():
        return notice_type

    source = str(notice.get("source") or "").upper()

    if source in {"BIZINFO", "KSTARTUP"}:
        return "SUPPORT"

    return "UNKNOWN"


def _summary(
    notice: Notice,
    engine: Any,
    *,
    is_open: bool | None = None,
) -> dict[str, Any]:
    deadline = notice.get("deadline")

    if is_open is None:
        is_open = engine.is_open(notice)

    period_status = (
        "OPEN_WITH_DEADLINE"
        if is_open and deadline
        else "OPEN_NO_DATE_DEADLINE"
        if is_open
        else "CLOSED"
    )

    return {
        "notice_id": notice["notice_id"],
        "source_system": notice.get("source"),
        "type": _notice_type(notice),
        "title": notice.get("title"),
        "organization": notice.get("org"),
        "category": {
            "source_major": notice.get("category"),
            "source_medium": notice.get("category_mid"),
        },
        "period": {
            "start": notice.get("start"),
            "end": deadline,
            "deadline_at": deadline,
            "status_kind": notice.get("apply_status_kind"),
            "period_status": period_status,
        },
        "region_names": _region_names(notice, engine),
        "required_documents": [],
        "detail_url": notice.get("detail_url"),
        "fetched_at": notice.get("fetched_at"),
        "version": 1,
    }