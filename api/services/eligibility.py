"""규칙 판정 서비스. 지금은 tools/graphrag 엔진을 감싼다.

규칙 평가기를 rules/ 패키지로 옮기면(기초 설계서 §13) 이 파일의 import만 바꾼다. 판정 로직을 여기에 다시 쓰지 않는다.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from ..schemas.eligibility import ApplicantProfile, EligibilityRequest, EligibilityResponse

META = ("title", "source", "detail_url", "fetched_at", "deadline")
# REQ_UNPARSED 공고에 붙일 자격 요건 원문 구역(앞 순서 우선). 판정은 바꾸지 않는다(결정 B-3: 검수 전에는 원문 표시)
UNPARSED_SECTIONS = (("eligibility_api", "신청 자격(공고 요약)"), ("att_eligibility", "첨부 공고문 · 신청 자격"),
                     ("att_exclusion", "첨부 공고문 · 신청 제외 대상"))
MAX_UNPARSED = 3
UNPARSED_CHARS = 600


def unparsed_excerpts(chunks: list[dict]) -> list[dict]:
    """한 공고의 청크에서 자격·제외 구역을 골라 원문 발췌로 돌려준다. 같은 글은 한 번만."""
    out, seen = [], set()
    for kind, label in UNPARSED_SECTIONS:
        for c in chunks:
            if c["section"].split("@")[0] != kind:
                continue
            text = " ".join(c["text"].split())
            if len(text) < 15 or text[:80] in seen:
                continue
            seen.add(text[:80])
            cut = text if len(text) <= UNPARSED_CHARS else text[:UNPARSED_CHARS].rstrip() + "…"
            out.append({"chunk_id": c["chunk_id"], "section": c["section"], "label": label, "text": cut})
            if len(out) >= MAX_UNPARSED:
                return out
    return out


class EligibilityService(Protocol):
    def judge(self, req: EligibilityRequest) -> EligibilityResponse: ...

    def judge_notice(self, notice_id: str, profile: ApplicantProfile) -> EligibilityResponse: ...


class NoticeNotFound(KeyError):
    pass


class EngineEligibilityService:
    """tools.graphrag.engine.Engine 위의 얇은 어댑터. 엔진은 처음 쓸 때 한 번만 데이터를 읽는다."""

    def __init__(self, use_cleaned: bool | None = None, retriever=None):
        from tools.graphrag.engine import Engine  # 무거운 데이터 적재를 import 시점으로 당기지 않는다

        self._engine = Engine(use_cleaned=use_cleaned)
        self.retriever = retriever  # agent.rag.HybridRetriever. None이면 엔진의 BM25만 쓴다(attach_retriever로 붙인다)
        self._chunks_by: dict[str, list[dict]] | None = None

    def attach_retriever(self, retriever) -> None:
        self.retriever = retriever

    def _notice_chunks(self, notice_id: str) -> list[dict]:
        if self._chunks_by is None:
            by: dict[str, list[dict]] = {}
            for c in self._engine.chunks:
                by.setdefault(c["notice_id"], []).append(c)
            self._chunks_by = by
        return self._chunks_by.get(notice_id, [])

    def _row(self, r: dict) -> dict:
        n = self._engine.by_id.get(r["notice_id"], {})
        unparsed = unparsed_excerpts(self._notice_chunks(r["notice_id"])) if "REQ_UNPARSED" in r.get("reasons", []) else []
        return {**{k: v for k, v in r.items() if k not in ("conditions", "chunks")},
                **{k: n.get(k) for k in META}, "conditions": [asdict(c) for c in r["conditions"]], "unparsed_text": unparsed}

    def judge(self, req: EligibilityRequest) -> EligibilityResponse:
        from tools.graphrag.evaluator import Profile

        res = self._engine.query(Profile(**req.profile.model_dump()), req.question, req.top, req.include_closed, req.source,
                                 search=self.retriever.search if self.retriever is not None else None)
        return EligibilityResponse(evaluated=res["evaluated"], candidates=res["candidates"], counts=res["counts"],
                                   results=[self._row(r) for r in res["results"]], input_layer=self._engine.input_layer)

    def judge_notice(self, notice_id: str, profile: ApplicantProfile) -> EligibilityResponse:
        """사용자가 공고를 지목하면 검색 없이 그 공고만 판정한다(§7, 마감 여부와 관계없이)."""
        from datetime import date

        from tools.graphrag.engine import TODAY
        from tools.graphrag.evaluator import Profile, evaluate_notice

        n = self._engine.by_id.get(notice_id)
        if n is None:
            raise NoticeNotFound(notice_id)
        r = evaluate_notice(n, Profile(**profile.model_dump()), self._engine.rg, today=date.fromisoformat(TODAY))
        return EligibilityResponse(evaluated=1, candidates=int(r["verdict"] != "NOT_ELIGIBLE"), counts={r["verdict"]: 1},
                                   results=[self._row(r)], input_layer=self._engine.input_layer)


def judge_for_agent(service: EligibilityService):
    """에이전트가 쓰는 판정 함수(agent.graph.Judge). 에이전트는 api 패키지를 모르고 dict만 주고받는다."""

    def judge(profile: dict, question: str = "", top: int = 5, notice_id: str | None = None,
              include_closed: bool = False) -> dict:
        prof = ApplicantProfile(**{k: v for k, v in profile.items() if k in ApplicantProfile.model_fields})
        if notice_id:
            try:
                return service.judge_notice(notice_id, prof).model_dump()
            except NoticeNotFound:
                return {"evaluated": 0, "candidates": 0, "counts": {}, "results": []}
        res = service.judge(EligibilityRequest(profile=prof, question=question, top=top, include_closed=include_closed))
        return res.model_dump()

    return judge
