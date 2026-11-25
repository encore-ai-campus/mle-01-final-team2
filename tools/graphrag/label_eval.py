"""사람이 쓴 라벨 A(요건·조건 JSON)를 가상 프로필에 대해 규칙으로 평가한다 (정답셋 파일럿의 '3값 판정 규칙 검증'용).

가이드 §4.4의 합성 규칙을 그대로 구현한다. 이 평가 결과를 사람이 쓴 라벨 B(독립 판정)와 비교해
- 규칙이 가이드와 어긋나는 곳(규칙 버그),
- 라벨러가 규칙과 다르게 판정한 곳(가이드 모호성 또는 라벨 오류)
을 찾는 것이 목적이다. 정답은 라벨 B이며 이 모듈의 결과는 정답이 아니다.

규칙(요약)
- 조건: SATISFIED / UNSATISFIED / UNKNOWN. 프로필에 값이 없으면(None) UNKNOWN.
- 요건 논리: AND, OR, NONE_OF(하나라도 해당하면 제외), AT_LEAST(k).
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


def eval_condition(c: dict, prof: dict) -> tuple[str, list[str]]:
    """조건 하나 -> (결과, 플래그)."""
    a, op, v = c.get("attribute"), c.get("operator"), c.get("value") or {}
    flags: list[str] = []
    res = UNK
    if a == "business_age":
        x = prof.get("business_age_years")
        if x is not None and prof.get("business_status") != "예비창업자":
            ok = compare(float(x), op, v)
            res = UNK if ok is None else (SAT if ok else UNSAT)
    elif a == "founder_age":
        x = prof.get("founder_age")
        if x is not None:
            ok = compare(float(x), op, v)
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


def eval_requirement(r: dict, prof: dict) -> dict:
    conds = r.get("conditions", [])
    results, flags = {}, set()
    for c in conds:
        rs, fl = eval_condition(c, prof)
        results[c.get("cond_id")] = rs
        flags.update(fl)
    vals = list(results.values())
    s, u, k = vals.count(SAT), vals.count(UNSAT), vals.count(UNK)
    logic = r.get("logic", "AND")
    if r.get("status") == "unparsed" or not conds:
        out = UNK
    elif logic == "AND":
        out = UNSAT if u else (SAT if s == len(vals) else UNK)
    elif logic == "OR":
        out = SAT if s else (UNSAT if u == len(vals) else UNK)
    elif logic == "NONE_OF":  # 하나라도 해당하면 제외: 해당(SAT)이 있으면 불충족, 모두 해당 안 함이면 충족
        out = UNSAT if s else (SAT if u == len(vals) else UNK)
    elif logic == "AT_LEAST":
        kmin = int(r.get("min_count") or 1)
        out = SAT if s >= kmin else (UNSAT if s + k < kmin else UNK)
    else:
        out = UNK
    reasons = set()
    if r.get("status") == "unparsed":
        reasons.add("REQ_UNPARSED")
    if r.get("logic_basis") == "assumed" and len(conds) > 1:
        reasons.add("ASSUMED_LOGIC")
    if r.get("open_ended"):
        reasons.add("OPEN_ENDED")
        if out == UNSAT:
            out = UNK  # 목록이 열려 있어 불충족을 확정할 수 없다
    if "NEEDS_DEFINITION" in flags:
        reasons.add("NEEDS_DEFINITION")
    if UNK in vals and not reasons:
        reasons.add("PROFILE_MISSING_ATTR")
    return {"req_id": r.get("req_id"), "kind": r.get("kind"), "result": out, "conditions": results, "reasons": sorted(reasons), "track_id": r.get("track_id")}


@dataclass
class Verdict:
    overall: str
    reasons: list[str] = field(default_factory=list)
    conditions: dict = field(default_factory=dict)
    tracks: dict = field(default_factory=dict)


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
    track_ids = [t.get("track_id") for t in label_a.get("tracks", []) if t.get("track_id")]
    common = [r for r in reqs if not r.get("track_id")]
    if not track_ids:
        overall, reasons = judge_track(common)
        return Verdict(overall, reasons, cond_results)
    per = {}
    for t in track_ids:
        per[t] = judge_track(common + [r for r in reqs if r.get("track_id") == t])
    vals = [v[0] for v in per.values()]
    overall = ELIGIBLE if ELIGIBLE in vals else (NOT_ELIGIBLE if all(v == NOT_ELIGIBLE for v in vals) else NEEDS_CHECK)
    reasons = sorted({x for v in per.values() for x in v[1]} | {"TRACK_SPLIT"})
    return Verdict(overall, reasons, cond_results, {t: v[0] for t, v in per.items()})
