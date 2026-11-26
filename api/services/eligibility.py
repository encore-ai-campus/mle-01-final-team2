"""규칙 판정 서비스. 지금은 tools/graphrag 엔진을 감싼다.

규칙 평가기를 rules/ 패키지로 옮기면(기초 설계서 §13) 이 파일의 import만 바꾼다. 판정 로직을 여기에 다시 쓰지 않는다.
"""
from __future__ import annotations

from dataclasses import asdict
from typing import Protocol

from ..schemas.eligibility import EligibilityRequest, EligibilityResponse


class EligibilityService(Protocol):
    def judge(self, req: EligibilityRequest) -> EligibilityResponse: ...


class EngineEligibilityService:
    """tools.graphrag.engine.Engine 위의 얇은 어댑터. 엔진은 처음 쓸 때 한 번만 데이터를 읽는다."""

    def __init__(self, use_cleaned: bool | None = None):
        from tools.graphrag.engine import Engine  # 무거운 데이터 적재를 import 시점으로 당기지 않는다

        self._engine = Engine(use_cleaned=use_cleaned)

    def judge(self, req: EligibilityRequest) -> EligibilityResponse:
        from tools.graphrag.evaluator import Profile

        res = self._engine.query(Profile(**req.profile.model_dump()), req.question, req.top, req.include_closed, req.source)
        results = [
            {**{k: v for k, v in r.items() if k not in ("conditions", "chunks")},
             "conditions": [asdict(c) for c in r["conditions"]]}
            for r in res["results"]
        ]
        return EligibilityResponse(evaluated=res["evaluated"], candidates=res["candidates"], counts=res["counts"],
                                   results=results, input_layer=self._engine.input_layer)
