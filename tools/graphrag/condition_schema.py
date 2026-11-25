"""조건 값 스키마 통일(설계서 4.3, O-11).

정리 층 읽기(`cleaned.py`·`evaluator.py`)는 K-Startup 선택형 필드를 옵션 목록 모양으로 들고 있다(`max_years`, `ranges`, `options`).
그래프 내보내기는 그 값을 값 정규화 층과 같은 형식(`operator` + `value` + `unit`)으로 바꿔 쓴다. 평가기는 옛 모양을 그대로 읽으므로 건드리지 않고,
옛 값은 `legacy_value`로 함께 남긴다. 같은 입력에서 두 모양의 숫자가 같은지는 시험으로 확인한다(`tools/test_graphrag.py`).

연산자는 보존한다: "N년미만"은 `LT`, "N년 이내"는 `LTE`. 둘을 `max_years` 하나에 섞으면 정확히 N년인 경우 결과가 달라진다.
"""
from __future__ import annotations

PRE_FOUNDER = "예비창업자"


def unify(attribute: str, legacy: dict) -> tuple[str, str | None, dict]:
    """옛 조건 값 -> (attribute, operator, value). operator가 None이면 판정에 쓸 수 없는 조건(UNKNOWN)이다."""
    if attribute == "region":
        return "region", "WITHIN", {"concept_id": legacy["concept_id"]}
    if attribute == "business_age":
        if legacy.get("all_options"):
            # 체크박스를 전부 고른 것은 제한 없음이 아니라 필터가 정보를 주지 않는 것이다(설계서 4.2). 조건으로 쓰지 않고 UNKNOWN으로 둔다.
            return "business_age", None, {"all_options": True}
        if legacy.get("max_years") is not None:
            return "business_age", "LT", {"value": legacy["max_years"], "unit": "YEAR"}
        return "applicant_type", "IN", {"labels": [PRE_FOUNDER]}  # 예비창업자만 고른 경우
    if attribute == "founder_age":
        ranges = [{"min": lo, "max": None if hi >= 200 else hi, "min_inclusive": True, "max_inclusive": False} for lo, hi in legacy["ranges"]]
        return "founder_age", "BETWEEN", {"ranges": ranges, "unit": "YEAR"}
    if attribute == "applicant_type":
        return "applicant_type", "IN", {"labels": list(legacy["options"])}
    raise ValueError(f"통일 규칙이 없는 속성: {attribute}")


def split_pre_founder(conditions: list[dict]) -> tuple[list[dict], dict | None]:
    """예비창업자를 허용하는 업력 조건을 분리한다.

    옵션이 "예비창업자, 1·2·3년미만"이면 업력 요건은 OR(applicant_type IN {예비창업자}, business_age LT 3)이다. 예비창업자를 별도 조건으로만 두면
    기본값 AND에 묶여 "예비창업자이면서 업력 3년 미만"이 되어 틀린다. 반환: (나머지 조건, 분리한 업력 조건 또는 None).
    """
    rest, age = [], None
    for c in conditions:
        v = c["value"]
        if c["attribute"] == "business_age" and v.get("pre_founder_allowed") and v.get("max_years") is not None and not v.get("all_options"):
            age = c
        else:
            rest.append(c)
    return rest, age
