"""조건 평가기: 조건별 3값(SATISFIED/UNSATISFIED/UNKNOWN)과 공고별 판정.

원칙(기초 설계서 §4.2, 온톨로지 설계서 §4.3):
- 못 읽거나 모르는 값은 충족으로 보지 않는다(UNKNOWN). 'UNKNOWN'을 '제한 없음'으로 바꾸지 않는다.
- 판정은 모델이 아니라 이 코드가 한다.
- strength=hard 조건이 UNSATISFIED일 때만 NOT_ELIGIBLE. soft 조건의 불충족은 NEEDS_CHECK(사유 기록).
- 본문 요건이 추출되지 않은 공고(text_requirements=unparsed)는 ELIGIBLE을 만들지 않는다(REQ_UNPARSED).
- 사람이 검수한 본문 요건(`gold_bridge`)은 `gold_requirements`로 들어오며 정답 논리 트리로 합친다. 발췌 검수라 ELIGIBLE을 풀지 않는다.
- 공고 판정은 그래프와 같은 요건 단위로 한다(`condition_schema.requirement_groups`). 요건마다 `logic`(AND/OR)으로 조건 결과를 합친다.
  예: "예비창업자, 3년미만" 업력은 R2 = OR(업력 3년 미만, 예비창업자)이다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

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


@dataclass
class Profile:
    """가상 신청자 프로필. None이면 입력하지 않은 값(UNKNOWN)."""
    region: str | None = None            # 사업장 소재지 개념 ID (예: REGION:1127000000)
    business_age_years: float | None = None
    pre_founder: bool | None = None       # 사업자등록 전 예비창업자
    founder_age: int | None = None
    applicant_type: str | None = None     # K-Startup 신청 대상 값 중 하나
    sme_facts: dict | None = None         # 중소기업 판정 입력(definition_rules.evaluate_sme의 facts). 입력 항목은 팀 검토 E-5


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


H3_REASON = "입력한 지역이 조건 지역보다 상위라 하위 조건 충족 여부를 알 수 없음(H3)"


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


def evaluate_condition(cond: dict, prof: Profile, rg: RegionGraph) -> CondResult:
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


CMP = {"LT": lambda a, b: a < b, "LTE": lambda a, b: a <= b, "GT": lambda a, b: a > b, "GTE": lambda a, b: a >= b, "EQ": lambda a, b: a == b}
INVERT = {SAT: UNSAT, UNSAT: SAT, UNK: UNK}


def evaluate_gold_condition(cond: dict, prof: Profile, rg: RegionGraph) -> CondResult:
    """검수 정답에서 온 조건(`gold_bridge.to_condition`). 제외 조건(negate)은 '해당함'을 요건 불충족으로 뒤집는다."""
    a, v = cond["attribute"], cond["value"]
    base = _base(cond, flags=["gold"])
    status, reason, path = UNK, f"평가 규칙 없는 속성 {a}", None
    if v.get("unsupported"):
        pass
    elif a in ("business_age", "founder_age"):
        x = prof.business_age_years if a == "business_age" else prof.founder_age
        if a == "business_age" and prof.pre_founder is True:
            reason = "예비창업자의 업력 조건 해석은 미정(팀 검토 D-4)"
        elif x is None:
            reason = "업력 미입력" if a == "business_age" else "대표자 연령 미입력"
        elif a == "business_age" and abs(x - v["value"]) < BOUNDARY_YEARS:
            reason = f"업력 {x:g}년이 {v['value']:g}년 경계 근처이고 기준일을 알 수 없음"
        else:
            ok = CMP[v["op"]](x, v["value"])
            status, reason = (SAT if ok else UNSAT), f"{x:g} {v['op']} {v['value']:g}: " + ("충족" if ok else "불충족")
    elif a == "business_type" and v.get("labels"):
        status, reason, extra = _business_type(v["labels"], prof)
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


def _business_type(labels: list[str], prof: Profile) -> tuple[str, str, list[str]]:
    """기업 유형 조건. 법령 판정 기준(rule_json)이 있는 중소기업만 판정하고 나머지 유형은 UNKNOWN이다.
    여러 유형 중 하나(IN)면 중소기업 충족일 때만 충족이고, 불충족이어도 다른 유형을 몰라 UNKNOWN이다."""
    if SME_LABEL not in labels:
        return UNK, f"판정 기준이 없는 기업 유형({', '.join(labels)})", []
    from .definition_rules import evaluate_sme, load_rule
    rule = load_rule()
    if rule is None:
        return UNK, "중소기업 판정 기준 파일 없음", []
    if not prof.sme_facts:
        return UNK, "중소기업 판정 입력(업종·매출·자산 등) 없음", []
    r = evaluate_sme(rule, prof.sme_facts)
    detail = "; ".join(f"{s['id']} {s['status']}" for s in r["steps"])
    flags = ["draft_rule"] if rule.get("status") == "draft" else []
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


def _evaluate_in_group(cond: dict, logic: str, prof: Profile, rg: RegionGraph) -> CondResult:
    """요건 안의 조건 하나. OR 요건(R2)에서는 업력과 예비창업자를 각각 따로 본다."""
    if cond.get("pre_founder"):
        base = _base(cond, attribute="applicant_type")
        if prof.pre_founder is True:
            return CondResult(**base, status=SAT, reason="예비창업자")
        if prof.pre_founder is False:
            return CondResult(**base, status=UNSAT, reason="예비창업자 아님")
        if prof.business_age_years is not None:  # 업력을 입력했으면 이미 사업자가 있다
            return CondResult(**base, status=UNSAT, reason="업력 입력(사업자 있음)")
        return CondResult(**base, status=UNK, reason="예비창업자 여부 미입력")
    if logic == "OR" and cond["attribute"] == "business_age":
        if prof.pre_founder is True:  # 예비창업자 허용은 같은 요건의 예비창업자 조건이 맡는다
            return CondResult(**_base(cond), status=UNSAT, reason="예비창업자라 업력 조건 대상 아님(같은 요건의 예비창업자 조건으로 판단)")
    return evaluate_condition(cond, prof, rg)


def _tally(req_id: str, status: str, rs: list[CondResult], hard_fail: list, soft_fail: list, unknown: list) -> None:
    """요건 단위로 합친 결과를 사유 목록에 넣는다. 요건 안에 hard 조건이 있으면 hard 불충족이다."""
    if status == UNSAT:
        (hard_fail if any(r.strength == "hard" for r in rs) else soft_fail).append(req_id)
    elif status == UNK:
        unknown.append(req_id)


def evaluate_notice(notice: dict, prof: Profile, rg: RegionGraph) -> dict:
    """공고 판정. 구조화 조건만 평가하며 본문 요건이 없으면 ELIGIBLE을 만들지 않는다.

    요건마다 조건 결과를 `logic`으로 합친다. AND 요건은 조건별 강도(hard/soft)를 그대로 보고, OR 요건은 합친 결과를 요건 강도로 본다
    (요건 안 조건의 강도는 같다). OR 요건이 충족되면 그 안의 불충족 조건은 사유가 되지 않는다.
    """
    results, requirements = [], []
    hard_fail, soft_fail, unknown = [], [], []
    for req_id, logic, basis, conds in requirement_groups(notice["notice_id"], notice.get("conditions", [])):
        rs = [_evaluate_in_group(c, logic, prof, rg) for c in conds]
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
        rs = [evaluate_gold_condition(c, prof, rg) for c in g["conditions"]]
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
            "conditions": results, "n_conditions": len(results), "requirements": requirements}
