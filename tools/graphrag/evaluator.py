"""조건 평가기: 조건별 3값(SATISFIED/UNSATISFIED/UNKNOWN)과 공고별 판정.

원칙(기초 설계서 §4.2, 온톨로지 설계서 §4.3):
- 못 읽거나 모르는 값은 충족으로 보지 않는다(UNKNOWN). 'UNKNOWN'을 '제한 없음'으로 바꾸지 않는다.
- 판정은 모델이 아니라 이 코드가 한다.
- strength=hard 조건이 UNSATISFIED일 때만 NOT_ELIGIBLE. soft 조건의 불충족은 NEEDS_CHECK(사유 기록).
- 본문 요건이 추출되지 않은 공고(text_requirements=unparsed)는 ELIGIBLE을 만들지 않는다(REQ_UNPARSED).
- 사람이 검수한 본문 요건(`gold_bridge`)은 `gold_requirements`로 들어오며 정답 논리 트리로 합친다. 공고 전체 확인이 없으면(D-1 ②)
  ELIGIBLE을 풀지 않는다. 강도는 구조화 필드와 같은 속성 규칙이다(D-2 ③). 검수 조건이 있는 속성은 구조화 조건보다 우선한다(본문 우선).
- 공고 판정은 그래프와 같은 요건 단위로 한다(`condition_schema.requirement_groups`). 요건마다 `logic`(AND/OR)으로 조건 결과를 합친다.
  예: "예비창업자, 3년미만" 업력은 R2 = OR(업력 3년 미만, 예비창업자)이다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date

from .condition_schema import requirement_groups
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


@dataclass(frozen=True)
class RuleOptions:
    """판정 규칙 선택지(`docs/MEETING_판정규칙_결정시트_2026-11-27.md`). 기본값은 2026-11-27 팀 회의 결정이다.

    예비창업자 관련(C-1·A-3·D-4)은 신규창업 확장 기능으로 미뤄 회의 전 동작을 그대로 둔다. 선택지별 영향은 `rule_options_impact.py`로 잰다.
    """
    c1_pre_founder_not_in_options: str = "unsat"    # C-1(보류) 업력 옵션에 예비창업자가 없을 때 예비창업자: unsat | unknown
    c2_business_age_all_options: str = "satisfied"  # C-2(결정 ②) 업력 옵션 전부 선택: satisfied(제한 없음) | unknown | drop(조건 없음)
    c3_age_all_options: str = "satisfied"           # C-3(결정 ③) 연령 옵션 전부 선택: satisfied | unknown. 본문 요건이 오면 본문 우선(body_priority)
    c4_applicant_all_options: str = "satisfied"     # C-4(결정 ①) 신청 대상 옵션 전부 선택: satisfied | flag(충족 + all_options 표시) | unknown
    c6_bizinfo_org_region: str = "drop"             # C-6(결정 ② 후 ③) 기업마당 소관 기관 시도: drop(검색 필터로만) | soft
    a1_kstartup_region: str = "soft"                # A-1(결정: 강도 유지 + 본문 우선) K-Startup 지원 지역 강도: soft | hard
    a3_pre_founder_missing_with_age: str = "unsat"  # A-3(보류) 예비창업자 여부 미입력 + 업력 입력: unsat | unknown
    a6_unreviewed_group: str = "unknown"            # A-6(결정 ②) 미검수 지역 묶음 충족: unknown | flag(충족 + 표시)
    body_priority: str = "on"                       # A-1·C-3·C-6③: 검수된 본문 조건이 있는 속성은 구조화 필드 조건을 쓰지 않는다: on | off
    d2_gold_strength: str = "by_attribute"          # D-2(결정 ③) 검수 조건 강도: by_attribute(구조화 필드와 같은 규칙, 업력만 hard) | soft
    e2_sales_margin: str = "unknown_5pct"           # E-2(결정 ②) 중소기업 매출 기준 ±5%: unknown_5pct | exact


DEFAULT_OPTIONS = RuleOptions()
OPTION_CHOICES = {"c1_pre_founder_not_in_options": ("unsat", "unknown"), "c2_business_age_all_options": ("satisfied", "unknown", "drop"),
                  "c3_age_all_options": ("satisfied", "unknown"), "c4_applicant_all_options": ("satisfied", "flag", "unknown"),
                  "c6_bizinfo_org_region": ("drop", "soft"), "a1_kstartup_region": ("soft", "hard"),
                  "a3_pre_founder_missing_with_age": ("unsat", "unknown"), "a6_unreviewed_group": ("unknown", "flag"),
                  "body_priority": ("on", "off"), "d2_gold_strength": ("by_attribute", "soft"), "e2_sales_margin": ("unknown_5pct", "exact")}
STRUCTURED_HARD = {"business_age"}  # A-1: 구조화 필드 중 hard는 업력뿐이다. D-2 ③으로 검수 조건도 같은 규칙을 쓴다
SME_STATUSES = {"certified", "expected"}  # E-5: 중소기업확인서 보유 / 중소기업 예정(확인서 미보유)
ALL_AGE_RANGES = sorted(AGE_OPTION_RANGES.values())


@dataclass
class Profile:
    """가상 신청자 프로필. None이면 입력하지 않은 값(UNKNOWN)."""
    region: str | None = None            # 사업장 소재지 개념 ID (예: REGION:1127000000)
    business_age_years: float | None = None
    pre_founder: bool | None = None       # 사업자등록 전 예비창업자
    founder_age: int | None = None
    applicant_type: str | list[str] | None = None  # K-Startup 신청 대상 값. A-5 ②: 여러 개를 받고 하나라도 맞으면 충족
    sme_facts: dict | None = None         # 중소기업 상세 입력(definition_rules.evaluate_sme의 facts). E-5 ②: 선택 입력
    sme_status: str | None = None         # E-5 ②: certified(중소기업확인서 보유) | expected(중소기업 예정, 확인서 없음)
    business_start_date: date | str | None = None  # A-2: 사업 개시일을 넣으면 업력을 기준일로 정확히 계산한다
    birth_date: date | str | None = None  # A-4·D-5: 대표자 생년월일을 넣으면 만 나이를 기준일로 계산한다

    def types(self) -> set[str]:
        t = self.applicant_type
        return set() if t is None else ({t} if isinstance(t, str) else set(t))


def _as_date(x) -> date | None:
    if x is None or isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x)[:10])
    except ValueError:
        return None


def anniversary(start: date, years: int) -> date:
    """start에서 years년 뒤 같은 날(2월 29일은 2월 28일)."""
    try:
        return start.replace(year=start.year + years)
    except ValueError:
        return start.replace(year=start.year + years, day=28)


def full_age(birth: date, ref: date) -> int:
    """만 나이."""
    return ref.year - birth.year - ((ref.month, ref.day) < (birth.month, birth.day))


def reference_dates(notice: dict | None, today: date | None = None) -> list[date]:
    """기준일 후보. 공고마다 기준일(공고일·마감일·신청일)이 달라 오늘(신청일)과 마감일을 함께 본다(B-2: 본문에 표현이 있을 때만 확정).
    마감일이 지났으면 마감일만 쓴다."""
    today = today or date.today()
    dl = _as_date((notice or {}).get("deadline"))
    if dl is None:
        return [today]
    return [dl] if dl < today else sorted({today, dl})


def _same(statuses: list[str]) -> str:
    """기준일마다 결과가 같을 때만 확정한다."""
    return statuses[0] if len(set(statuses)) == 1 else UNK


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


H3_REASON = "입력한 지역이 조건 지역보다 상위라 충족 여부를 알 수 없음(H3). 시군구까지 입력하면 확인할 수 있음"


def _base(cond: dict, attribute: str | None = None, **extra) -> dict:
    """CondResult 공통 필드."""
    return dict(cond_id=cond["cond_id"], attribute=attribute or cond["attribute"], strength=cond.get("strength", "soft"),
                evidence=cond.get("evidence", ""), **extra)


def region_match(region: str, targets: list[str], rg: RegionGraph) -> tuple[str, str | None]:
    """사용자 지역이 조건 지역 중 하나에 속하는지. (SAT, 맞은 지역) / (UNK, None: 사용자 지역이 더 상위, H3) / (UNSAT, None)."""
    anc = rg.ancestors(region)
    hit = next((t for t in targets if t in anc or t == "REGION:NATIONWIDE"), None)
    if hit:
        return SAT, hit
    if any(region in rg.ancestors(t) for t in targets):
        return UNK, None
    return UNSAT, None


def _business_age_by_date(start: date, mx: int, refs: list[date]) -> tuple[str, str]:
    """사업 개시일로 'mx년 미만'을 기준일마다 계산한다(A-2)."""
    limit = anniversary(start, mx)
    st = _same([SAT if r < limit else UNSAT for r in refs])
    days = ", ".join(r.isoformat() for r in refs)
    if st == UNK:
        return UNK, f"사업 개시일 {start} 기준 {mx}년이 되는 날({limit})이 기준일 후보({days}) 사이에 있어 기준일을 알아야 함"
    return st, f"사업 개시일 {start}, {mx}년이 되는 날 {limit}, 기준일 {days}: " + ("미만" if st == SAT else "넘음")


def evaluate_condition(cond: dict, prof: Profile, rg: RegionGraph, opts: RuleOptions = DEFAULT_OPTIONS,
                       refs: list[date] | None = None) -> CondResult:
    refs = refs or reference_dates(None)
    a = cond["attribute"]
    base = _base(cond)
    v = cond["value"]
    if a == "region":
        target = v["concept_id"]
        flags = ["unreviewed_group"] if rg.is_unreviewed(target) else []
        if target == "REGION:NATIONWIDE":
            return CondResult(**base, status=SAT, reason="전국 대상", flags=flags)
        if prof.region is None:
            return CondResult(**base, status=UNK, reason="사업장 소재지 미입력", flags=flags)
        status, hit = region_match(prof.region, [target], rg)
        if status == SAT and flags and opts.a6_unreviewed_group == "unknown":
            return CondResult(**base, status=UNK, reason=f"{rg.name(target)}은(는) 구성 검수 전 묶음이라 확정하지 않음(A-6)", flags=flags)
        if status == SAT:
            hops = rg.ancestors(prof.region)[target]
            return CondResult(**base, status=SAT, reason=f"{rg.name(prof.region)} → {rg.name(target)} ({hops} hop)",
                              path=rg.path(prof.region, target), flags=flags)
        if status == UNK:
            return CondResult(**base, status=UNK, reason=H3_REASON, flags=flags)
        return CondResult(**base, status=UNSAT, reason=f"{rg.name(prof.region)} → {rg.name(target)} 경로 없음(속하지 않음)", flags=flags)
    if a == "business_age":
        o = v
        if prof.pre_founder is True:
            if o["pre_founder_allowed"]:
                return CondResult(**base, status=SAT, reason="예비창업자 허용")
            if opts.c1_pre_founder_not_in_options == "unknown":
                return CondResult(**base, status=UNK, reason="업력 옵션에 예비창업자가 없지만 사업자등록 전이라 업력을 판정하지 않음(C-1)")
            return CondResult(**base, status=UNSAT, reason="예비창업자 불가(업력 옵션에 예비창업자 없음)")
        if o["all_options"] and opts.c2_business_age_all_options == "satisfied":
            return CondResult(**base, status=SAT, reason="업력 옵션을 모두 골라 제한 없음으로 봄(C-2)", flags=["all_options"])
        start = _as_date(prof.business_start_date)
        age = prof.business_age_years
        if age is None and start is None:
            return CondResult(**base, status=UNK, reason="업력 미입력")
        mx = o["max_years"]
        if mx is None:
            return CondResult(**base, status=UNSAT, reason="예비창업자 전용")
        if start is not None:
            st, why = _business_age_by_date(start, mx, refs)
            if st == UNSAT and o["all_options"]:
                return CondResult(**base, status=UNK, reason=why + ". 옵션을 모두 나열해 해석이 모호함", flags=["all_options_ambiguous"])
            return CondResult(**base, status=st, reason=why)
        if age < mx - BOUNDARY_YEARS:
            return CondResult(**base, status=SAT, reason=f"업력 {age:g}년 < {mx}년미만")
        if age < mx + BOUNDARY_YEARS:
            return CondResult(**base, status=UNK, reason=f"업력 {age:g}년이 {mx}년 경계 근처이고 기준일을 알 수 없음")
        if o["all_options"]:
            return CondResult(**base, status=UNK, reason=f"옵션을 모두 나열했지만 최대 {mx}년미만이라 업력 {age:g}년의 해석이 모호함(전체 나열=제한 없음 규칙은 미검증)",
                              flags=["all_options_ambiguous"])
        return CondResult(**base, status=UNSAT, reason=f"업력 {age:g}년 ≥ {mx}년미만")
    if a == "founder_age":
        birth = _as_date(prof.birth_date)
        if prof.founder_age is None and birth is None:
            return CondResult(**base, status=UNK, reason="대표자 연령 미입력")
        if sorted(map(tuple, v["ranges"])) == ALL_AGE_RANGES and opts.c3_age_all_options == "unknown":
            return CondResult(**base, status=UNK, reason="연령 옵션을 모두 골라 필터가 정보를 주지 않음(C-3)", flags=["all_options"])
        if birth is not None:  # A-4: 생년월일이 있으면 기준일마다 만 나이를 계산한다
            ages = [full_age(birth, r) for r in refs]
            st = _same([SAT if any(lo <= x < hi for lo, hi in v["ranges"]) else UNSAT for x in ages])
            shown = "~".join(str(x) for x in sorted(set(ages)))
            if st == UNK:
                return CondResult(**base, status=UNK, reason=f"기준일에 따라 만 {shown}세라 허용 구간 경계에 걸림")
            return CondResult(**base, status=st, reason=f"만 {shown}세(생년월일 기준) " + ("허용 구간" if st == SAT else "허용 구간 밖"))
        ok = any(lo <= prof.founder_age < hi for lo, hi in v["ranges"])
        return CondResult(**base, status=SAT if ok else UNSAT, reason=f"연령 {prof.founder_age}세 " + ("허용 구간" if ok else "허용 구간 밖"))
    if a == "applicant_type":
        types = prof.types()
        if not types:
            return CondResult(**base, status=UNK, reason="신청자 유형 미입력")
        if set(v["options"]) == APPLICANT_OPTIONS and opts.c4_applicant_all_options != "satisfied":
            if opts.c4_applicant_all_options == "unknown":
                return CondResult(**base, status=UNK, reason="신청 대상 옵션을 모두 골라 필터가 정보를 주지 않음(C-4)", flags=["all_options"])
            base["flags"] = ["all_options"]
        hit = [t for t in v["options"] if t in types]  # A-5 ②: 하나라도 맞으면 충족
        if hit:
            return CondResult(**base, status=SAT, reason=f"{', '.join(hit)} 허용")
        return CondResult(**base, status=UNSAT, reason=f"{', '.join(sorted(types))} 허용 목록에 없음")
    return CondResult(**base, status=UNK, reason=f"평가 규칙 없는 속성 {a}")


CMP = {"LT": lambda a, b: a < b, "LTE": lambda a, b: a <= b, "GT": lambda a, b: a > b, "GTE": lambda a, b: a >= b, "EQ": lambda a, b: a == b}
INVERT = {SAT: UNSAT, UNSAT: SAT, UNK: UNK}


def gold_strength(attribute: str, opts: RuleOptions = DEFAULT_OPTIONS) -> str:
    """D-2 ③: 검수 조건의 강도는 구조화 필드와 같은 속성 규칙을 쓴다(업력만 hard)."""
    return "hard" if opts.d2_gold_strength == "by_attribute" and attribute in STRUCTURED_HARD else "soft"


def _gold_years(a: str, v: dict, prof: Profile, refs: list[date]) -> tuple[str, str]:
    """검수 조건의 업력·연령 비교. 사업 개시일·생년월일이 있으면 기준일마다 계산한다(A-2·A-4)."""
    n, op = v["value"], v["op"]
    if a == "business_age":
        start = _as_date(prof.business_start_date)
        if start is not None and float(n).is_integer():
            limit = anniversary(start, int(n))
            rel = {"LT": lambda r: r < limit, "LTE": lambda r: r <= limit, "GT": lambda r: r > limit,
                   "GTE": lambda r: r >= limit, "EQ": lambda r: r == limit}[op]
            st = _same([SAT if rel(r) else UNSAT for r in refs])
            if st == UNK:
                return UNK, f"사업 개시일 {start} 기준 {n:g}년이 되는 날({limit})이 기준일 후보 사이에 있음"
            return st, f"사업 개시일 {start}, {n:g}년이 되는 날 {limit}: {op} " + ("충족" if st == SAT else "불충족")
        x = prof.business_age_years
        if x is None:
            return UNK, "업력 미입력"
        if abs(x - n) < BOUNDARY_YEARS:
            return UNK, f"업력 {x:g}년이 {n:g}년 경계 근처이고 기준일을 알 수 없음"
        ok = CMP[op](x, n)
        return (SAT if ok else UNSAT), f"{x:g} {op} {n:g}: " + ("충족" if ok else "불충족")
    birth = _as_date(prof.birth_date)
    xs = [full_age(birth, r) for r in refs] if birth is not None else ([prof.founder_age] if prof.founder_age is not None else [])
    if not xs:
        return UNK, "대표자 연령 미입력"
    st = _same([SAT if CMP[op](x, n) else UNSAT for x in xs])
    shown = "~".join(str(x) for x in sorted(set(xs)))
    if st == UNK:
        return UNK, f"기준일에 따라 만 {shown}세라 {op} {n:g} 경계에 걸림"
    return st, f"{shown} {op} {n:g}: " + ("충족" if st == SAT else "불충족")


def evaluate_gold_condition(cond: dict, prof: Profile, rg: RegionGraph, opts: RuleOptions = DEFAULT_OPTIONS,
                            refs: list[date] | None = None) -> CondResult:
    """검수 정답에서 온 조건(`gold_bridge.to_condition`). 제외 조건(negate)은 '해당함'을 요건 불충족으로 뒤집는다."""
    refs = refs or reference_dates(None)
    a, v = cond["attribute"], cond["value"]
    base = _base(cond, flags=["gold"])
    base["strength"] = gold_strength(a, opts)
    status, reason, path = UNK, f"평가 규칙 없는 속성 {a}", None
    if v.get("unsupported"):
        pass
    elif a in ("business_age", "founder_age"):
        if a == "business_age" and prof.pre_founder is True:
            reason = "예비창업자의 업력 조건 해석은 신규창업 확장 기능에서 정함(D-4 보류)"
        else:
            status, reason = _gold_years(a, v, prof, refs)
    elif a == "business_type" and v.get("labels"):
        status, reason, extra = _business_type(v["labels"], prof, opts)
        base["flags"] = base["flags"] + extra
    elif a == "region":
        if v["unresolved"] or not v["concept_ids"]:
            reason = f"지역 표기를 개념으로 확정하지 못함({', '.join(v['unresolved']) or '없음'})"
        elif prof.region is None:
            reason = "사업장 소재지 미입력"
        else:
            status, hit = region_match(prof.region, v["concept_ids"], rg)
            if hit:
                path = rg.path(prof.region, hit) if hit in rg.ancestors(prof.region) else None
                reason = f"{rg.name(prof.region)} → {rg.name(hit)}"
            else:
                reason = H3_REASON if status == UNK else f"{rg.name(prof.region)}은(는) {', '.join(v['labels'])}에 속하지 않음"
    if cond.get("negate"):
        status, reason = INVERT[status], "제외 조건: " + reason
    return CondResult(**base, status=status, reason=reason, path=path)


SME_LABEL = "중소기업"


def _business_type(labels: list[str], prof: Profile, opts: RuleOptions = DEFAULT_OPTIONS) -> tuple[str, str, list[str]]:
    """기업 유형 조건. 법령 판정 기준(rule_json)이 있는 중소기업만 판정하고 나머지 유형은 UNKNOWN이다.
    여러 유형 중 하나(IN)면 중소기업 충족일 때만 충족이고, 불충족이어도 다른 유형을 몰라 UNKNOWN이다.

    E-5 ②: 중소기업확인서 보유가 먼저다. 기준(별표)은 해마다 바뀔 수 있어 확인서를 우선하고, 상세 입력은 확인서가 없을 때만 쓴다.
    '중소기업 예정'(확인서 없음)은 상세 입력이 없으면 확인 필요다."""
    if SME_LABEL not in labels:
        return UNK, f"판정 기준이 없는 기업 유형({', '.join(labels)})", []
    if prof.sme_status == "certified":
        return SAT, "중소기업확인서 보유(E-5)", ["sme_certificate"]
    from .definition_rules import evaluate_sme, load_rule
    rule = load_rule()
    expected = ["sme_expected"] if prof.sme_status == "expected" else []
    if rule is None:
        return UNK, "중소기업 판정 기준 파일 없음", expected
    if not prof.sme_facts:
        if expected:
            return UNK, "중소기업 예정(확인서 없음). 신청 전에 중소기업확인서를 받아야 함", expected
        return UNK, "중소기업확인서 보유 여부나 판정 입력(업종·매출·자산 등) 없음", []
    r = evaluate_sme(rule, prof.sme_facts, sales_margin=0.05 if opts.e2_sales_margin == "unknown_5pct" else 0.0)
    detail = "; ".join(f"{s['id']} {s['status']}" for s in r["steps"])
    flags = (["draft_rule"] if rule.get("status") == "draft" else []) + expected
    if r["status"] == UNSAT and len(labels) > 1:
        return UNK, f"중소기업 아님({detail}). 다른 유형({', '.join(x for x in labels if x != SME_LABEL)})은 판정 기준 없음", flags
    return r["status"], f"중소기업 판정 {r['status']} ({r['rule_id']}: {detail})", flags


def evaluate_tree(node: dict, by_id: dict[str, str]) -> str:
    """정답 논리 트리(AND/OR/NOT/UNRESOLVED)를 3값으로 계산한다. UNRESOLVED는 판정하지 않는다."""
    if node["node_type"] == "CONDITION_REF":
        return by_id.get(node["condition_id"], UNK)
    kids = [evaluate_tree(c, by_id) for c in node["children"]]
    if node["operator"] == "NOT":
        return INVERT[kids[0]]
    return combine(node["operator"], kids)


def combine(logic: str, statuses: list[str]) -> str:
    """조건 결과(3값)를 요건 논리로 합친다. 모르는 값은 결과를 확정하지 못할 때만 UNKNOWN으로 남는다."""
    if not statuses:
        return UNK
    if logic == "AND":
        return UNSAT if UNSAT in statuses else (SAT if all(s == SAT for s in statuses) else UNK)
    if logic == "OR":
        return SAT if SAT in statuses else (UNSAT if all(s == UNSAT for s in statuses) else UNK)
    return UNK  # 규칙 없는 논리는 판정하지 않는다


def _evaluate_in_group(cond: dict, logic: str, prof: Profile, rg: RegionGraph, opts: RuleOptions = DEFAULT_OPTIONS,
                       refs: list[date] | None = None) -> CondResult:
    """요건 안의 조건 하나. OR 요건(R2)에서는 업력과 예비창업자를 각각 따로 본다."""
    if cond.get("pre_founder"):
        base = _base(cond, attribute="applicant_type")
        if prof.pre_founder is True:
            return CondResult(**base, status=SAT, reason="예비창업자")
        if prof.pre_founder is False:
            return CondResult(**base, status=UNSAT, reason="예비창업자 아님")
        if prof.business_age_years is not None or prof.business_start_date is not None:  # 업력을 입력했으면 이미 사업자가 있다
            if opts.a3_pre_founder_missing_with_age == "unknown":
                return CondResult(**base, status=UNK, reason="예비창업자 여부 미입력(A-3)")
            return CondResult(**base, status=UNSAT, reason="업력 입력(사업자 있음)")
        return CondResult(**base, status=UNK, reason="예비창업자 여부 미입력")
    if logic == "OR" and cond["attribute"] == "business_age":
        if prof.pre_founder is True:  # 예비창업자 허용은 같은 요건의 예비창업자 조건이 맡는다
            return CondResult(**_base(cond), status=UNSAT, reason="예비창업자라 업력 조건 대상 아님(같은 요건의 예비창업자 조건으로 판단)")
    return evaluate_condition(cond, prof, rg, opts, refs)


def body_attributes(notice: dict) -> set[str]:
    """검수된 본문 조건이 다루는 속성. 판정 규칙이 있는 조건만 센다(값을 못 읽은 조건은 구조화 필드를 대신하지 못한다)."""
    return {c["attribute"] for g in notice.get("gold_requirements", []) for c in g["conditions"] if not c["value"].get("unsupported")}


def apply_condition_options(notice: dict, opts: RuleOptions) -> list[dict]:
    """조건 목록 단계에서 적용하는 선택지(C-2 drop, C-6 drop, A-1 hard, 본문 우선). 바꿀 것이 없으면 원래 목록을 그대로 돌려준다.

    본문 우선(A-1 결정 메모, C-3 ③, C-6 ③): K-Startup API 조건 필드와 본문이 다를 수 있어, 검수된 본문 조건이 있는 속성은 구조화 조건을 쓰지 않는다.
    """
    conds = notice.get("conditions", [])
    body = body_attributes(notice) if opts.body_priority == "on" else set()
    if (opts.c2_business_age_all_options != "drop" and opts.c6_bizinfo_org_region == "soft" and opts.a1_kstartup_region == "soft"
            and not body):
        return conds
    out, src = [], notice.get("source")
    for c in conds:
        a = c["attribute"]
        if a in body:
            continue
        if a == "business_age" and c["value"].get("all_options") and opts.c2_business_age_all_options == "drop":
            continue
        if a == "region" and src == "BIZINFO" and opts.c6_bizinfo_org_region == "drop":
            continue
        if a == "region" and src == "KSTARTUP" and opts.a1_kstartup_region == "hard":
            c = {**c, "strength": "hard"}
        out.append(c)
    return out


def _tally(req_id: str, status: str, rs: list[CondResult], hard_fail: list, soft_fail: list, unknown: list) -> None:
    """요건 단위로 합친 결과를 사유 목록에 넣는다. 요건 안에 hard 조건이 있으면 hard 불충족이다."""
    if status == UNSAT:
        (hard_fail if any(r.strength == "hard" for r in rs) else soft_fail).append(req_id)
    elif status == UNK:
        unknown.append(req_id)


def evaluate_notice(notice: dict, prof: Profile, rg: RegionGraph, opts: RuleOptions = DEFAULT_OPTIONS, today: date | None = None) -> dict:
    """공고 판정. 구조화 조건만 평가하며 본문 요건이 없으면 ELIGIBLE을 만들지 않는다.

    요건마다 조건 결과를 `logic`으로 합친다. AND 요건은 조건별 강도(hard/soft)를 그대로 보고, OR 요건은 합친 결과를 요건 강도로 본다
    (요건 안 조건의 강도는 같다). OR 요건이 충족되면 그 안의 불충족 조건은 사유가 되지 않는다.
    """
    results, requirements = [], []
    hard_fail, soft_fail, unknown = [], [], []
    refs = reference_dates(notice, today)
    kept = apply_condition_options(notice, opts)
    kept_ids = {c["cond_id"] for c in kept}
    overridden = [c["cond_id"] for c in notice.get("conditions", []) if c["cond_id"] not in kept_ids and c["attribute"] in body_attributes(notice)
                  and opts.body_priority == "on"]
    for req_id, logic, basis, conds in requirement_groups(notice["notice_id"], kept):
        rs = [_evaluate_in_group(c, logic, prof, rg, opts, refs) for c in conds]
        results += rs
        status = combine(logic, [r.status for r in rs])
        requirements.append({"req_id": req_id, "logic": logic, "logic_basis": basis, "status": status, "cond_ids": [r.cond_id for r in rs]})
        if logic == "AND":
            hard_fail += [r for r in rs if r.strength == "hard" and r.status == UNSAT]
            soft_fail += [r for r in rs if r.strength != "hard" and r.status == UNSAT]
            unknown += [r for r in rs if r.status == UNK]
        else:
            _tally(req_id, status, rs, hard_fail, soft_fail, unknown)
    for g in notice.get("gold_requirements", []):  # 사람이 검수한 본문 요건(gold_bridge). 요건 단위로 합친다
        rs = [evaluate_gold_condition(c, prof, rg, opts, refs) for c in g["conditions"]]
        results += rs
        status = evaluate_tree(g["logic_tree"], {r.cond_id: r.status for r in rs})
        requirements.append({"req_id": g["req_id"], "logic": g["logic_tree"].get("operator", "ATOM"), "logic_basis": g["logic_basis"],
                             "status": status, "cond_ids": [r.cond_id for r in rs], "source": "gold"})
        _tally(g["req_id"], status, rs, hard_fail, soft_fail, unknown)
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
            "conditions": results, "n_conditions": len(results), "requirements": requirements,
            "overridden_by_body": overridden, "reference_dates": [r.isoformat() for r in refs]}
