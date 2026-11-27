"""사람이 쓴 라벨 A(요건·조건 JSON)를 가상 프로필에 대해 규칙으로 평가한다 (정답셋 파일럿의 '3값 판정 규칙 검증'용).

가이드 §4.4의 합성 규칙을 그대로 구현한다. 이 평가 결과를 사람이 쓴 라벨 B(독립 판정)와 비교해
- 규칙이 가이드와 어긋나는 곳(규칙 버그),
- 라벨러가 규칙과 다르게 판정한 곳(가이드 모호성 또는 라벨 오류)
을 찾는 것이 목적이다. 정답은 라벨 B이며 이 모듈의 결과는 정답이 아니다.

규칙(요약)
- 조건: SATISFIED / UNSATISFIED / UNKNOWN. 프로필에 값이 없으면(None) UNKNOWN.
- 요건 논리: AND, OR, NONE_OF(하나라도 해당하면 제외), AT_LEAST(k).
- `open_ended`는 열린 목록만 넓힌다. AND 요건에서 닫힌 속성(지역·업력·연령·매출·직원 수) 조건이 불충족이거나 제외(NONE_OF)에 해당하면 불충족을 확정한다.
- 연령 값에 basis=YEAR_AGE(연 나이)가 있으면 만 나이와 만 나이+1이 갈릴 때 미확인(BOUNDARY_UNCLEAR).
- 예비창업자의 업력: 하한 조건(1년 이상 등)은 불충족, 상한 조건은 미확인.
- `unparsed` 자격 요건, 조건이 둘 이상인데 `logic_basis=assumed`, `open_ended`가 ELIGIBLE을 만들 상황이면 NEEDS_CHECK.
- 트랙: 하나라도 ELIGIBLE이면 ELIGIBLE, 전부 NOT_ELIGIBLE이면 NOT_ELIGIBLE, 그 외 NEEDS_CHECK.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .regions import RegionGraph

SAT, UNSAT, UNK = "SATISFIED", "UNSATISFIED", "UNKNOWN"
ELIGIBLE, NOT_ELIGIBLE, NEEDS_CHECK = "ELIGIBLE", "NOT_ELIGIBLE", "NEEDS_CHECK"
SIZE_UNDER_SME = {"소기업", "중기업"}  # 중소기업기본법 제2조 제2항: 중소기업은 소기업과 중기업으로 구분(로컬 법령 원문)
SUFFIX = ("특별자치시", "특별자치도", "특별시", "광역시", "시", "군", "구", "도")

_RG: RegionGraph | None = None


def rg() -> RegionGraph:
    global _RG
    if _RG is None:
        _RG = RegionGraph()
    return _RG


def resolve_region(text: str | None) -> tuple[str | None, bool]:
    """지역 표기 -> (개념 ID, 모호/미해소). '경북 구미시'처럼 시도+시군구가 함께 있으면 마지막 단어(시군구)를 우선한다."""
    if not text:
        return None, True
    g = rg()
    tokens = [t for t in re.split(r"\s+", text.strip()) if t]
    if len(tokens) > 1:  # '광주 남구'처럼 상위 지역이 앞에 있으면 동명 시군구를 그 안에서 좁힌다
        parent, _ = resolve_region(" ".join(tokens[:-1]))
        last = tokens[-1]
        if parent:
            ids = []
            for c in (last, re.sub("(" + "|".join(SUFFIX) + ")$", "", last)):
                ids = [r for r in g.find_by_name(c) if g.nodes[r].get("level") in ("SIDO", "SIGUNGU") and parent in g.ancestors(r)]
                if not ids and len(c) >= 2:
                    ids = [r for s in ("시", "군", "구") for r in g.find_by_name(c + s) if g.nodes[r].get("level") == "SIGUNGU" and parent in g.ancestors(r)]
                if len(ids) == 1:
                    return ids[0], False
    for tok in reversed(tokens):
        cands = [tok, re.sub("(" + "|".join(SUFFIX) + ")$", "", tok)]
        for c in cands:
            if not c:
                continue
            rid = g.sido_abbr.get(c) or g.legacy_abbr.get(c)
            if rid:
                return rid, False
            ids = [r for r in g.find_by_name(c) if g.nodes[r].get("level") in ("SIDO", "SIGUNGU")]
            if not ids and len(c) >= 2:
                ids = [r for s in ("시", "군", "구") for r in g.find_by_name(c + s) if g.nodes[r].get("level") == "SIGUNGU"]
            if len(ids) == 1:
                return ids[0], False
            if len(ids) > 1:
                return None, True  # 동명 시군구(동구 등)는 확정하지 않는다
    return None, True


def num(v) -> float | None:
    if isinstance(v, dict):
        v = v.get("value", v.get("min"))
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def compare(x: float, op: str, v: dict) -> bool | None:
    if op == "BETWEEN":
        lo, hi = num(v.get("min")), num(v.get("max"))
        if lo is None or hi is None:
            return None
        lo_ok = x >= lo if v.get("min_inclusive", True) else x > lo
        hi_ok = x <= hi if v.get("max_inclusive", True) else x < hi
        return lo_ok and hi_ok
    t = num(v)
    if t is None:
        return None
    return {"LT": x < t, "LTE": x <= t, "GT": x > t, "GTE": x >= t, "EQ": x == t}.get(op)


def is_lower_bound(op: str, v: dict) -> bool:
    """업력 0년이 떨어지는 하한 조건인가(GTE 1, GT 0, BETWEEN 1~3 등)."""
    if op in ("GT", "GTE", "EQ"):
        t = num(v)
        return t is not None and (t > 0 if op != "GT" else t >= 0)
    if op == "BETWEEN":
        lo = num(v.get("min"))
        return lo is not None and (lo > 0 if v.get("min_inclusive", True) else lo >= 0)
    return False


CLOSED_ATTRS = {"region", "zone", "business_age", "founder_age", "revenue", "employees"}  # 값이 닫혀 있어 '등'으로 넓어지지 않는 속성


def is_closed(c: dict) -> bool:
    """조건(또는 그룹)의 잎 조건이 모두 닫힌 속성인가."""
    if c.get("children"):
        return all(is_closed(ch) for ch in c["children"])
    return c.get("attribute") in CLOSED_ATTRS


def eval_condition(c: dict, prof: dict) -> tuple[str, list[str]]:
    """조건 하나 -> (결과, 플래그)."""
    a, op, v = c.get("attribute"), c.get("operator"), c.get("value") or {}
    flags: list[str] = []
    res = UNK
    if a == "business_age":
        x = prof.get("business_age_years")
        if prof.get("business_status") == "예비창업자":
            # 사업자등록 전이라 업력이 없다. 하한(1년 이상 등)은 못 넘으므로 불충족, 상한(7년 이내 등)에 예비창업자가 드는지는 공고 정의 문제라 미확인
            res = UNSAT if is_lower_bound(op, v) else UNK
        elif x is not None:
            ok = compare(float(x), op, v)
            res = UNK if ok is None else (SAT if ok else UNSAT)
    elif a == "founder_age":
        x = prof.get("founder_age")
        if x is not None:
            ok = compare(float(x), op, v)
            if isinstance(v, dict) and v.get("basis") == "YEAR_AGE":
                # 연 나이(출생연도 기준, 예: '1975년 12월 31일 이전 출생')는 만 나이와 같거나 1 많다. 두 경우가 갈리면 확정하지 않는다
                ok2 = compare(float(x) + 1, op, v)
                if ok != ok2:
                    ok = None
                    flags.append("BOUNDARY_UNCLEAR")
            res = UNK if ok is None else (SAT if ok else UNSAT)
    elif a == "employees":
        x = prof.get("employees")
        if x is not None:
            ok = compare(float(x), op, v)
            res = UNK if ok is None else (SAT if ok else UNSAT)
    elif a == "revenue":
        x = prof.get("revenue_krw")
        if x is not None:
            ok = compare(float(x), op, v)
            res = UNK if ok is None else (SAT if ok else UNSAT)
    elif a == "region":
        user, amb_u = resolve_region(prof.get("region"))
        target, amb_t = resolve_region(v.get("label") if isinstance(v, dict) else None)
        if user is None or target is None:
            res = UNK
        elif target == "REGION:NATIONWIDE":
            res = SAT
        else:
            anc = rg().ancestors(user)
            if target in anc:
                res = SAT
                if rg().is_unreviewed(target):
                    flags.append("unreviewed_group")
            elif user in rg().ancestors(target):
                res = UNK  # 입력 지역이 조건 지역보다 상위(H3)
            else:
                res = UNSAT
    elif a in ("company_size", "applicant_type"):
        label = (v.get("label") if isinstance(v, dict) else None) or ""
        size, status = prof.get("company_size"), prof.get("business_status")
        if label == "예비창업자":
            res = UNK if status is None else (SAT if status == "예비창업자" else UNSAT)
        elif size is None:
            res = UNK
        elif size == label:
            res = SAT
        elif label == "중소기업":
            res = SAT if size in SIZE_UNDER_SME else (UNSAT if size == "중견" else UNK)
        elif label in SIZE_UNDER_SME | {"중견"} and size in SIZE_UNDER_SME | {"중견"}:
            res = UNSAT
        else:
            res = UNK  # 소상공인과 소기업의 포함 관계 등은 법령 원문이 없어 확정하지 않는다
        if c.get("needs_definition") and res == SAT and label not in ("예비창업자",):
            flags.append("NEEDS_DEFINITION")
    elif a == "certification":
        certs = prof.get("certifications")
        label = re.sub(r"\s", "", (v.get("label") if isinstance(v, dict) else "") or "")
        if certs is not None and label:
            res = SAT if any(label in re.sub(r"\s", "", x) or re.sub(r"\s", "", x) in label for x in certs) else UNSAT
    elif a == "industry":
        ind = prof.get("industry")
        labels = v.get("labels") if isinstance(v, dict) and v.get("labels") else [v.get("label")] if isinstance(v, dict) and v.get("label") else []
        if ind and labels:
            hit = any(ind in l or l in ind for l in labels if l)
            res = SAT if hit else UNK  # 업종 포함 관계는 사전이 없어 불일치를 확정하지 않는다
    if c.get("negate") and res in (SAT, UNSAT):
        res = UNSAT if res == SAT else SAT
    return res, flags


def combine(logic: str, vals: list[str], min_count: int | None = None) -> str:
    """하위 결과(SATISFIED/UNSATISFIED/UNKNOWN)를 논리로 합친다."""
    s, u, k = vals.count(SAT), vals.count(UNSAT), vals.count(UNK)
    if not vals:
        return UNK
    if logic == "AND":
        return UNSAT if u else (SAT if s == len(vals) else UNK)
    if logic == "OR":
        return SAT if s else (UNSAT if u == len(vals) else UNK)
    if logic == "NONE_OF":  # 하나라도 해당하면 제외: 해당(SAT)이 있으면 불충족, 모두 해당 안 함이면 충족
        return UNSAT if s else (SAT if u == len(vals) else UNK)
    if logic == "AT_LEAST":
        kmin = int(min_count or 1)
        return SAT if s >= kmin else (UNSAT if s + k < kmin else UNK)
    return UNK


MAX_GROUP_DEPTH = 3  # 요건 아래 그룹 중첩 한도(설계서 4.5)


def eval_node(c: dict, prof: dict, results: dict, flags: set, depth: int = 0) -> str:
    """조건 트리의 노드 하나. `children`이 있으면 그룹(logic으로 합침), 없으면 원자 조건."""
    if c.get("children"):
        if depth >= MAX_GROUP_DEPTH:
            flags.add("DEPTH_EXCEEDED")
            res = UNK
        else:
            vals = [eval_node(ch, prof, results, flags, depth + 1) for ch in c["children"]]
            res = combine(c.get("logic", "AND"), vals, c.get("min_count"))
            if c.get("logic_basis") == "assumed" and len(vals) > 1:
                flags.add("ASSUMED_LOGIC")
    else:
        res, fl = eval_condition(c, prof)
        flags.update(fl)
    results[c.get("cond_id")] = res
    return res


def eval_requirement(r: dict, prof: dict) -> dict:
    conds = r.get("conditions", [])
    results: dict = {}
    flags: set = set()
    tops = [eval_node(c, prof, results, flags) for c in conds]
    vals = list(results.values())
    if r.get("status") == "unparsed" or not conds:
        out = UNK
    else:
        out = combine(r.get("logic", "AND"), tops, r.get("min_count"))
    reasons = set()
    if r.get("status") == "unparsed":
        reasons.add("REQ_UNPARSED")
    if r.get("logic_basis") == "assumed" and len(conds) > 1:
        reasons.add("ASSUMED_LOGIC")
    if "ASSUMED_LOGIC" in flags:
        reasons.add("ASSUMED_LOGIC")
    if r.get("open_ended"):
        reasons.add("OPEN_ENDED")
        logic = r.get("logic", "AND")
        closed_fail = logic == "AND" and any(t == UNSAT and is_closed(c) for t, c in zip(tops, conds))
        if out == UNSAT and logic != "NONE_OF" and not closed_fail:
            out = UNK  # 목록이 열려 있어 불충족을 확정할 수 없다
        # 제외(NONE_OF)에 해당한 것, 닫힌 조건(지역·업력·연령 등)이 AND에서 불충족인 것은 '등'과 상관없이 확정한다
    if "NEEDS_DEFINITION" in flags:
        reasons.add("NEEDS_DEFINITION")
    if "BOUNDARY_UNCLEAR" in flags:
        reasons.add("BOUNDARY_UNCLEAR")
    if UNK in vals and not reasons:
        reasons.add("PROFILE_MISSING_ATTR")
    return {"req_id": r.get("req_id"), "kind": r.get("kind"), "result": out, "conditions": results, "reasons": sorted(reasons), "track_id": r.get("track_id")}


@dataclass
class Verdict:
    overall: str
    reasons: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)
    tracks: dict = field(default_factory=dict)
    preferences: dict = field(default_factory=dict)  # 우대(PREFERENCE) 요건별 3값. 판정(overall)에는 쓰지 않는다


def judge_track(reqs: list[dict]) -> tuple[str, list[str]]:
    reasons: set[str] = set()
    status = SAT
    for r in reqs:
        if r["kind"] not in ("ELIGIBILITY", "EXCLUSION"):
            continue  # 우대·서류·평가·한도는 판정에 쓰지 않는다
        reasons.update(r["reasons"])
        if r["result"] == UNSAT:
            return NOT_ELIGIBLE, sorted(reasons)
        if r["result"] == UNK:
            status = UNK
    if status == SAT and reasons & {"REQ_UNPARSED", "ASSUMED_LOGIC", "OPEN_ENDED", "NEEDS_DEFINITION"}:
        return NEEDS_CHECK, sorted(reasons)
    return (ELIGIBLE if status == SAT else NEEDS_CHECK), sorted(reasons)


def judge(label_a: dict, prof: dict) -> Verdict:
    reqs = [eval_requirement(r, prof) for r in label_a.get("requirements", [])]
    cond_results = {k: v for r in reqs for k, v in r["conditions"].items()}
    prefs = {r["req_id"]: r["result"] for r in reqs if r["kind"] == "PREFERENCE"}
    track_ids = [t.get("track_id") for t in label_a.get("tracks", []) if t.get("track_id")]
    common = [r for r in reqs if not r.get("track_id")]
    if not track_ids:
        overall, reasons = judge_track(common)
        return Verdict(overall, reasons, cond_results, {}, prefs)
    per = {}
    for t in track_ids:
        per[t] = judge_track(common + [r for r in reqs if r.get("track_id") == t])
    vals = [v[0] for v in per.values()]
    overall = ELIGIBLE if ELIGIBLE in vals else (NOT_ELIGIBLE if all(v == NOT_ELIGIBLE for v in vals) else NEEDS_CHECK)
    reasons = sorted({x for v in per.values() for x in v[1]} | {"TRACK_SPLIT"})
    return Verdict(overall, reasons, cond_results, {t: v[0] for t, v in per.items()}, prefs)
