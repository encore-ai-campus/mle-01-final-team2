"""공고 목록·검색(N-01)과 상세(N-02). 판정은 하지 않는다(판정은 E-01).

엔진(tools/graphrag/engine.py)이 읽어 둔 정리층 공고를 걸러서 페이지로 자르고, 상세는 원문 구역(청크)과
정리층 원본의 접수 시작일·연락처·첨부 상태를 붙인다. DB에는 접근하지 않는다.
"""
from __future__ import annotations

from collections import defaultdict

from ..schemas.notices import NoticeDetail, NoticeListResponse, NoticeSection, NoticeSummary


def load_cleaned_raw() -> dict[str, dict]:
    """정리층 원본 공고(notices.jsonl)를 ID별로 읽는다. 엔진이 버린 필드(접수 시작일·연락처·첨부 상태)용. 없으면 빈 dict."""
    from tools.graphrag import cleaned

    if not cleaned.available():
        return {}
    d = cleaned.CLEANED / (cleaned.CLEANED / "LATEST").read_text().strip()
    return {r["notice_id"]: r for r in cleaned._jsonl(d / "notices.jsonl")}


class NoticeService:
    def __init__(self, engine, raw: dict[str, dict] | None = None):
        self._engine = engine  # 판정 서비스와 같은 엔진을 같이 쓴다(데이터를 두 번 읽지 않게)
        self._raw = raw        # 정리층 원본. None이면 처음 상세를 볼 때 읽는다
        self._chunks = None    # 공고 ID → 원문 구역 목록. 처음 상세를 볼 때 만든다
    
    def _summary(self, n: dict) -> NoticeSummary:
        """엔진 공고 dict → 명세 이름의 카드 1장."""
        return NoticeSummary(
            notice_id=n["notice_id"],
            source_system=n["source"],
            title=n["title"],
            organization=n.get("org"),
            category=n.get("category"),
            deadline=n.get("deadline"),
            is_open=self._engine.is_open(n),
            detail_url=n.get("detail_url"),
            fetched_at=n.get("fetched_at"),
        )

    def list(self, q: str | None, source: str | None, include_closed: bool, page: int, size: int) -> NoticeListResponse:
        rows = self._engine.notices

        if not include_closed:                                     # ① 마감 거르기
            rows = [n for n in rows if self._engine.is_open(n)]
        if source:                                                 # ② 출처
            rows = [n for n in rows if n["source"] == source.upper()]
        if q:                                                      # ③ 검색어
            q = q.strip()
            rows = [n for n in rows if q in (n.get("title") or "") or q in (n.get("org") or "")]

        # ④ 마감일 있는 것 먼저(가까운 순), 없는 것은 뒤로. 같으면 ID 순으로 고정
        rows = sorted(rows, key=lambda n: (n.get("deadline") is None, n.get("deadline") or "", n["notice_id"]))

        start = (page - 1) * size                                  # ⑤ 페이지
        items = [self._summary(n) for n in rows[start:start + size]]
        return NoticeListResponse(items=items, page=page, size=size, total=len(rows))

    def _sections_of(self, notice_id: str) -> list[dict]:
        if self._chunks is None:  # 청크 3만여 개를 공고별로 한 번만 묶어 둔다
            self._chunks = defaultdict(list)
            for c in getattr(self._engine, "chunks", []):
                self._chunks[c["notice_id"]].append(c)
        return self._chunks.get(notice_id, [])

    def get(self, notice_id: str) -> NoticeDetail | None:
        """N-02 공고 상세. 없는 ID면 None(라우터가 404로 바꾼다)."""
        n = self._engine.by_id.get(notice_id)
        if n is None:
            return None
        if self._raw is None:
            self._raw = load_cleaned_raw()
        r = self._raw.get(notice_id, {})
        sections = [NoticeSection(chunk_id=c["chunk_id"], section=c["section"], origin=c["origin"], text=c["text"],
                                source_span=c.get("source_span")) for c in self._sections_of(notice_id)]
        return NoticeDetail(
            **self._summary(n).model_dump(),   # 카드 필드 9개는 N-01과 똑같이
            application_start=r.get("application_start"),
            period_status=r.get("period_status"),
            apply_url=r.get("apply_url"),
            contact_text=r.get("contact_text"),
            attachments=r.get("attachments"),
            requirements_status=n.get("text_requirements") or "unparsed",
            sections=sections,
        )
    