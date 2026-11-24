"""조건 평가기: 조건별 3값(SATISFIED/UNSATISFIED/UNKNOWN)과 공고별 판정.

원칙(기초 설계서 §4.2, 온톨로지 설계서 §4.3):
- 못 읽거나 모르는 값은 충족으로 보지 않는다(UNKNOWN). 'UNKNOWN'을 '제한 없음'으로 바꾸지 않는다.
- 판정은 모델이 아니라 이 코드가 한다.
- strength=hard 조건이 UNSATISFIED일 때만 NOT_ELIGIBLE. soft 조건의 불충족은 NEEDS_CHECK(사유 기록).
- 본문 요건이 추출되지 않은 공고(text_requirements=unparsed)는 ELIGIBLE을 만들지 않는다(REQ_UNPARSED).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .regions import RegionGraph

SAT, UNSAT, UNK = "SATISFIED", "UNSATISFIED", "UNKNOWN"
ELIGIBLE, NOT_ELIGIBLE, NEEDS_CHECK = "ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_CHECK"

AGE_OPTION_RANGES = {  # K-Startup 대상 연령 옵션 -> [lo, hi)
    "만 20세 미만": (0, 20),
    "만 20세 이상 ~ 만 39세 이하": (20, 40),
    "만 40세 이상": (40, 200),
}
BUSINESS_AGE_ALL = {"예비창업자", "1년미만", "2년미만", "3년미만", "5년미만", "7년미만", "10년미만"}
APPLICANT_OPTIONS = {"청소년", "대학생", "일반인", "대학", "연구기관", "일반기업", "1인 창조기업"}
BOUNDARY_YEARS = 0.5  # 기준일(공고일·마감일·신청일)이 불명이라 임계값 ±0.5년은 UNKNOWN


@dataclass
class Profile:
    """가상 신청자 프로필. None이면 입력하지 않은 값(UNKNOWN)."""
    region: str | None = None            # 사업장 소재지 개념 ID (예: REGION:1127000000)
    business_age_years: float | None = None
    pre_founder: bool | None = None       # 사업자등록 전 예비창업자
    founder_age: int | None = None
    applicant_type: str | None = None     # K-Startup 신청 대상 값 중 하나


@dataclass
class CondResult:
    cond_id: str
    attribute: str
    status: str
    strength: str
    reason: str
    evidence: str = ""
    path: list[str] | None = None
    flags: list[str] = field(default_factory=list)


def parse_business_age_options(raw: str | None) -> dict | None:
    """'예비창업자,1년미만,...' -> {'pre_founder_allowed', 'max_years', 'all_options', 'options'}. 못 읽으면 None."""
    if not raw:
        return None
    opts = [t.strip() for t in raw.split(",") if t.strip()]
    if not opts or any(o not in BUSINESS_AGE_ALL for o in opts):
        return None
    years = [int(re.match(r"(\d+)", o).group(1)) for o in opts if o != "예비창업자"]
    return {"pre_founder_allowed": "예비창업자" in opts, "max_years": max(years) if years else None,
            "all_options": set(opts) == BUSINESS_AGE_ALL, "options": opts}


def parse_age_options(raw: str | None) -> list[tuple[int, int]] | None:
    if not raw:
        return None
    opts = [t.strip() for t in raw.split(",") if t.strip()]
    if not opts or any(o not in AGE_OPTION_RANGES for o in opts):
        return None
    return [AGE_OPTION_RANGES[o] for o in opts]


def parse_applicant_options(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    opts = [t.strip() for t in raw.split(",") if t.strip()]
    return opts if opts and all(o in APPLICANT_OPTIONS for o in opts) else None


def evaluate_condition(cond: dict, prof: Profile, rg: RegionGraph) -> CondResult:
    a, strength = cond["attribute"], cond.get("strength", "soft")
    base = dict(cond_id=cond["cond_id"], attribute=a, strength=strength, evidence=cond.get("evidence", ""))
    v = cond["value"]
    if a == "region":
        target = v["concept_id"]
        flags = ["unreviewed_group"] if rg.is_unreviewed(target) else []
        if target == "REGION:NATIONWIDE":
            return CondResult(**base, status=SAT, reason="전국 대상", flags=flags)
        if prof.region is None:
            return CondResult(**base, status=UNK, reason="사업장 소재지 미입력", flags=flags)
        anc = rg.ancestors(prof.region)
        if target in anc:
            return CondResult(**base, status=SAT, reason=f"{rg.name(prof.region)} → {rg.name(target)} ({anc[target]} hop)",
                              path=rg.path(prof.region, target), flags=flags)
        if prof.region in rg.ancestors(target):
            return CondResult(**base, status=UNK, reason="입력한 지역이 조건 지역보다 상위라 하위 조건 충족 여부를 알 수 없음(H3)", flags=flags)
        return CondResult(**base, status=UNSAT, reason=f"{rg.name(prof.region)} → {rg.name(target)} 경로 없음(속하지 않음)", flags=flags)
    if a == "business_age":
        o = v
        if prof.pre_founder is True:
            if o["pre_founder_allowed"]:
                return CondResult(**base, status=SAT, reason="예비창업자 허용")
            return CondResult(**base, status=UNSAT, reason="예비창업자 불가(업력 옵션에 예비창업자 없음)")
        age = prof.business_age_years
        if age is None:
            return CondResult(**base, status=UNK, reason="업력 미입력")
        mx = o["max_years"]
        if mx is None:
            return CondResult(**base, status=UNSAT, reason="예비창업자 전용")
        if age < mx - BOUNDARY_YEARS:
            return CondResult(**base, status=SAT, reason=f"업력 {age:g}년 < {mx}년미만")
        if age < mx + BOUNDARY_YEARS:
            return CondResult(**base, status=UNK, reason=f"업력 {age:g}년이 {mx}년 경계 근처이고 기준일을 알 수 없음")
        if o["all_options"]:
            return CondResult(**base, status=UNK, reason=f"옵션을 모두 나열했지만 최대 {mx}년미만이라 업력 {age:g}년의 해석이 모호함(전체 나열=제한 없음 규칙은 미검증)",
                              flags=["all_options_ambiguous"])
        return CondResult(**base, status=UNSAT, reason=f"업력 {age:g}년 ≥ {mx}년미만")
    if a == "founder_age":
        if prof.founder_age is None:
            return CondResult(**base, status=UNK, reason="대표자 연령 미입력")
        ok = any(lo <= prof.founder_age < hi for lo, hi in v["ranges"])
        return CondResult(**base, status=SAT if ok else UNSAT, reason=f"연령 {prof.founder_age}세 " + ("허용 구간" if ok else "허용 구간 밖"))
    if a == "applicant_type":
        if prof.applicant_type is None:
            return CondResult(**base, status=UNK, reason="신청자 유형 미입력")
        ok = prof.applicant_type in v["options"]
        return CondResult(**base, status=SAT if ok else UNSAT, reason=f"{prof.applicant_type} " + ("허용" if ok else "허용 목록에 없음"))
    return CondResult(**base, status=UNK, reason=f"평가 규칙 없는 속성 {a}")


def evaluate_notice(notice: dict, prof: Profile, rg: RegionGraph) -> dict:
    """공고 판정. 구조화 조건만 평가하며 본문 요건이 없으면 ELIGIBLE을 만들지 않는다."""
    results = [evaluate_condition(c, prof, rg) for c in notice.get("conditions", [])]
    hard_fail = [r for r in results if r.strength == "hard" and r.status == UNSAT]
    soft_fail = [r for r in results if r.strength != "hard" and r.status == UNSAT]
    unknown = [r for r in results if r.status == UNK]
    if hard_fail:
        structured, verdict = "FAIL", NOT_ELIGIBLE
    elif soft_fail or unknown:
        structured, verdict = "UNKNOWN", NEEDS_CHECK
    else:
        structured, verdict = "PASS", NEEDS_CHECK
    reasons = []
    if notice.get("text_requirements", "unparsed") != "reviewed":
        reasons.append("REQ_UNPARSED")  # 본문·첨부 요건 미추출/미검수 → ELIGIBLE 금지
    if soft_fail:
        reasons.append("SOFT_CONDITION_UNSATISFIED")
    if unknown:
        reasons.append("UNKNOWN_CONDITION")
    if verdict == NEEDS_CHECK and not reasons:
        verdict = ELIGIBLE
    return {"notice_id": notice["notice_id"], "verdict": verdict, "structured": structured, "reasons": reasons,
            "conditions": results, "n_conditions": len(results)}
