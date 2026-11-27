"""공고 목록 응답(GET /api/notices, 명세 §3.3 NoticeSummary).

명세의 region_names·required_documents·period.start는 지금 정리층 데이터에 없어 빠져 있다.
페이지는 뼈대대로 page/size를 쓴다(명세 §2.5의 limit/cursor는 나중에).
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class NoticeSummary(BaseModel):
    """목록 카드 1장."""

    notice_id: str = Field(description="공고 ID (예: BIZINFO:PBLN_000000000128083)")
    source_system: str = Field(description="출처: BIZINFO / KSTARTUP")
    title: str
    organization: str | None = Field(default=None, description="소관 기관")
    category: str | None = Field(default=None, description="지원 분야(원천 대분류)")
    deadline: str | None = Field(default=None, description="마감일 YYYY-MM-DD. 없으면 상시·예산 소진 시 등")
    is_open: bool = Field(description="모집 중 여부(기준일 기준)")
    detail_url: str | None = Field(default=None, description="원천 상세 페이지")
    fetched_at: str | None = Field(default=None, description="수집 시각")


class NoticeListResponse(BaseModel):
    items: list[NoticeSummary]
    page: int
    size: int
    total: int = Field(description="필터를 적용한 뒤 전체 공고 수")

class NoticeSection(BaseModel):
    """원문 구역 1개(정리층 청크). N-03 근거 위치가 source_span을 쓴다."""

    chunk_id: str
    section: str = Field(description="구역 이름: eligibility_api, support_details, att_eligibility@f0-1612 …")
    origin: str = Field(description="API / ATTACHMENT")
    text: str
    source_span: dict | list | None = Field(default=None, description="첨부 원문 안의 위치. API 구역은 없음")


class NoticeDetail(NoticeSummary):
    """N-02 공고 상세. NoticeSummary를 물려받고 원문을 더한다."""

    application_start: str | None = Field(default=None, description="접수 시작일")
    period_status: str | None = Field(default=None, description="OPEN_WITH_DEADLINE 등")
    apply_url: str | None = None
    contact_text: str | None = Field(default=None, description="담당 기관·연락처(공개 정보, 가리지 않음)")
    attachments: dict | None = Field(default=None, description="첨부 상태: count, text_extracted, preview_only, note")
    requirements_status: str = Field(description="본문 요건 정규화 상태: parsed / partial / unparsed")
    sections: list[NoticeSection]