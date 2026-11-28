"""E-02 조건별 검증표(명세 §3.6 ConditionCheck, 화면 SCR-02-1).

판정 결과의 조건마다 '내 값'과 값 출처를 붙인다. 값 출처(`my_value.source`):
- INPUT: 사용자가 그 값을 직접 넣었다
- DERIVED: 다른 입력에서 계산했다(사업 개시일 → 업력, 생년월일 → 만 나이, 중소기업 확인서 → 기업 유형)
- MISSING: 입력이 없다. 지금 입력 폼에 없는 속성(인증·서류 등)도 MISSING이다
값 출처는 화면 표시용이다. 판정은 규칙 평가기가 이미 냈고, 여기서 바꾸지 않는다.
"""
from __future__ import annotations

from collections import Counter

# 속성 → (직접 입력 필드, 계산에 쓰는 입력 필드)
FIELDS: dict[str, tuple[str | None, str | None]] = {
    "region": ("region", None),
    "business_age": ("business_age_years", "business_start_date"),
    "founder_age": ("founder_age", "birth_date"),
    "pre_founder": ("pre_founder", None),
    "applicant_type": ("applicant_type", None),
    "business_type": (None, "sme_status"),
}


def my_value(attribute: str, profile: dict) -> dict:
    direct, derived_from = FIELDS.get(attribute, (None, None))
    if direct and profile.get(direct) not in (None, "", []):
        return {"value": profile[direct], "source": "INPUT", "field": direct}
    if derived_from and profile.get(derived_from) not in (None, "", []):
        return {"value": profile[derived_from], "source": "DERIVED", "field": derived_from}
    return {"value": None, "source": "MISSING", "field": direct or derived_from}


def checks(result: dict, profile: dict) -> dict:
    """NoticeVerdict(dict) + 프로필(dict) → 검증표."""
    rows = []
    for c in result.get("conditions", []):
        rows.append({
            "cond_id": c["cond_id"], "attribute": c["attribute"], "strength": c.get("strength"),
            # 요구 값은 공고 근거(구조화 필드 값·조건 문구), 판정 이유는 규칙 평가기 설명이다(명세 §3.6 required·evidence)
            "required": {"label": c.get("evidence") or ""}, "my_value": my_value(c["attribute"], profile),
            "result": c["status"], "reason": c.get("reason") or "", "evidence": {"text": c.get("evidence") or ""},
            "path": c.get("path"), "flags": c.get("flags") or [],
        })
    return {"notice_id": result["notice_id"], "result": result, "checks": rows,
            "by_result": dict(Counter(r["result"] for r in rows)),
            "by_source": dict(Counter(r["my_value"]["source"] for r in rows))}
