"""규칙 판정 서비스. 지금은 tools/graphrag 엔진을 감싼다.

규칙 평가기를 rules/ 패키지로 옮기면(기초 설계서 §13) 이 파일의 import만 바꾼다. 판정 로직을 여기에 다시 쓰지 않는다.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from ..schemas.eligibility import ApplicantProfile, EligibilityRequest, EligibilityResponse

META = ("title", "source", "detail_url", "fetched_at", "deadline")


class EligibilityService(Protocol):
    def judge(self, req: EligibilityRequest) -> EligibilityResponse: ...

    def judge_notice(self, notice_id: str, profile: ApplicantProfile) -> EligibilityResponse: ...


class NoticeNotFound(KeyError):
    pass


class EngineEligibilityService:
    """tools.graphrag.engine.Engine 위의 얇은 어댑터. 엔진은 처음 쓸 때 한 번만 데이터를 읽는다."""

    def __init__(self, use_cleaned: bool | None = None):
        from tools.graphrag.engine import Engine  # 무거운 데이터 적재를 import 시점으로 당기지 않는다

        self._engine = Engine(use_cleaned=use_cleaned)

    def _row(self, r: dict) -> dict:
        n = self._engine.by_id.get(r["notice_id"], {})
        return {**{k: v for k, v in r.items() if k not in ("conditions", "chunks")},
                **{k: n.get(k) for k in META}, "conditions": [asdict(c) for c in r["conditions"]]}

    def judge(self, req: EligibilityRequest) -> EligibilityResponse:
        from tools.graphrag.evaluator import Profile

        res = self._engine.query(Profile(**req.profile.model_dump()), req.question, req.top, req.include_closed, req.source)
        return EligibilityResponse(evaluated=res["evaluated"], candidates=res["candidates"], counts=res["counts"],
                                   results=[self._row(r) for r in res["results"]], input_layer=self._engine.input_layer)

    def judge_notice(self, notice_id: str, profile: ApplicantProfile) -> EligibilityResponse:
        """사용자가 공고를 지목하면 검색 없이 그 공고만 판정한다(§7, 마감 여부와 관계없이)."""
        from tools.graphrag.evaluator import Profile, evaluate_notice

        n = self._engine.by_id.get(notice_id)
        if n is None:
            raise NoticeNotFound(notice_id)
        r = evaluate_notice(n, Profile(**profile.model_dump()), self._engine.rg)
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
