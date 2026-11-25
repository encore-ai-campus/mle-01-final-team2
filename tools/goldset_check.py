#!/usr/bin/env python3
"""정답셋 파일럿 라벨 점검 도구: 형식 검사, 두 검수자 일치율, 3값 판정 규칙 검증.

라벨 위치(가이드 §2): data/goldset/labels/<검수자>/A/<notice_id>.json (요건 추출),
                      data/goldset/labels/<검수자>/B/<notice_id>.json (프로필별 판정)
  notice_id의 ':'는 '_'로 쓴다. 프로필은 data/goldset/pilot/profiles.json(공통 8종)과 profiles_extra.json(공고별 경계·미입력 프로필).

명령
  python tools/goldset_check.py validate     # 형식·허용 값·근거 문장 일치 검사
  python tools/goldset_check.py agree        # 두 검수자 일치율(요건 F1, 조건 일치, 논리 일치, 판정 κ)
  python tools/goldset_check.py rules        # 규칙 평가기 vs 사람 판정(라벨 B)

주의: 이 도구의 규칙 평가 결과는 정답이 아니다. 정답은 사람이 쓴 라벨 B이며, 어긋난 곳은 규칙 버그인지 가이드 모호성인지 사람이 판단한다.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphrag.label_eval import ELIGIBLE, NEEDS_CHECK, NOT_ELIGIBLE, judge  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
LABELS = REPO / "data" / "goldset" / "labels"
PILOT = REPO / "data" / "goldset" / "pilot"

ATTRS = {"region", "zone", "industry", "applicant_type", "business_age", "founder_age", "company_size", "revenue", "employees", "certification", "prior_award", "registration", "other"}
OPS = {"EQ", "LT", "LTE", "GT", "GTE", "BETWEEN", "IN", "WITHIN", "IS_A", "EXISTS"}
KINDS = {"ELIGIBILITY", "EXCLUSION", "PREFERENCE", "DOCUMENT", "LIMIT", "CRITERION"}
LOGICS = {"AND", "OR", "NONE_OF", "AT_LEAST"}
REF_KINDS = {"NONE", "NOTICE_DATE", "DEADLINE", "PREV_YEAR", "OTHER"}
NEEDS_REF = {"business_age", "founder_age", "revenue", "employees"}
RESULTS = {"SATISFIED", "UNSATISFIED", "UNKNOWN"}
OVERALL = {ELIGIBLE, NOT_ELIGIBLE, NEEDS_CHECK}
REASONS = {"ASSUMED_LOGIC", "REQ_UNPARSED", "OPEN_ENDED", "PROFILE_MISSING_ATTR", "NEEDS_DEFINITION", "SOURCE_CONFLICT", "BOUNDARY_UNCLEAR", "TRACK_SPLIT"}


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def profiles() -> dict:
    out = {}
    for f in ("profiles.json", "profiles_extra.json"):
        p = PILOT / f
        if p.exists():
            for pr in load_json(p)["profiles"]:
                out[pr["profile_id"]] = pr
    return out


def reviewers() -> list[str]:
    return sorted(d.name for d in LABELS.iterdir() if d.is_dir()) if LABELS.exists() else []


def labels(reviewer: str, kind: str) -> dict[str, dict]:
    out = {}
    for p in sorted((LABELS / reviewer / kind).glob("*.json")) if (LABELS / reviewer / kind).exists() else []:
        d = load_json(p)
        out[d.get("notice_id", p.stem)] = d
    return out


def judgments_of(b: dict) -> list[dict]:
    if "judgments" in b:
        return b["judgments"]
    return [b] if "profile_id" in b else []


def packet_text(notice_id: str) -> str:
    p = PILOT / "packets" / (notice_id.replace(":", "_") + ".txt")
    return p.read_text(encoding="utf-8") if p.exists() else ""


# ------------------------------------------------------------------ validate
def validate_a(a: dict, packet: str) -> list[str]:
    errs = []
    for k in ("notice_id", "reviewer", "requirements", "ambiguities"):
        if k not in a:
            errs.append(f"필수 필드 없음: {k}")
    seen = set()
    ptxt = norm(packet)
    for r in a.get("requirements", []):
        rid = r.get("req_id", "?")
        if r.get("kind") not in KINDS:
            errs.append(f"{rid}: kind 값 오류 {r.get('kind')}")
        if r.get("logic") not in LOGICS:
            errs.append(f"{rid}: logic 값 오류 {r.get('logic')}")
        if r.get("logic") == "AT_LEAST" and not r.get("min_count"):
            errs.append(f"{rid}: AT_LEAST인데 min_count 없음")
        if not r.get("source_sentence"):
            errs.append(f"{rid}: source_sentence 없음(근거 필수)")
        elif ptxt and norm(r["source_sentence"]) not in ptxt:
            errs.append(f"{rid}: source_sentence가 자료 패킷에 그대로 없음(원문 복사 여부 확인, 첨부 원문에서 온 문장이면 패킷에 없을 수 있음)")
        for c in r.get("conditions", []):
            cid = c.get("cond_id", "?")
            if cid in seen:
                errs.append(f"{rid}/{cid}: cond_id 중복")
            seen.add(cid)
            if c.get("attribute") not in ATTRS:
                errs.append(f"{rid}/{cid}: attribute 허용 목록 밖 {c.get('attribute')}")
            if c.get("operator") not in OPS:
                errs.append(f"{rid}/{cid}: operator 허용 목록 밖 {c.get('operator')}")
            if c.get("attribute") in NEEDS_REF and c.get("ref_date_kind") in (None, "NONE") and r.get("kind") in ("ELIGIBILITY", "EXCLUSION"):
                errs.append(f"{rid}/{cid}: {c.get('attribute')}는 기준일(ref_date_kind)을 적어야 함(원문에 없으면 OTHER와 note)")
            if c.get("ref_date_kind") not in (None, *REF_KINDS):
                errs.append(f"{rid}/{cid}: ref_date_kind 값 오류")
            if c.get("attribute") in ("company_size", "applicant_type") and not c.get("needs_definition") and c.get("operator") == "IS_A":
                errs.append(f"{rid}/{cid}: 법령·제도 용어면 needs_definition=true (정의 뜻은 쓰지 않음)")
    if not a.get("requirements") and not a.get("ambiguities"):
        errs.append("요건이 없는데 ambiguities에 이유가 없음")
    return errs


def validate_b(b: dict, a: dict | None, profs: dict) -> list[str]:
    errs = []
    cond_ids = {c.get("cond_id") for r in (a or {}).get("requirements", []) for c in r.get("conditions", [])}
    js = judgments_of(b)
    if not js:
        errs.append("판정이 없음")
    for j in js:
        pid = j.get("profile_id")
        if pid not in profs:
            errs.append(f"{pid}: 알 수 없는 프로필(profiles.json/profiles_extra.json 확인)")
        if j.get("overall") not in OVERALL:
            errs.append(f"{pid}: overall 값 오류 {j.get('overall')}")
        for c in j.get("conditions", []):
            if c.get("result") not in RESULTS:
                errs.append(f"{pid}/{c.get('cond_ref')}: result 값 오류")
            if cond_ids and c.get("cond_ref") not in cond_ids:
                errs.append(f"{pid}: cond_ref {c.get('cond_ref')}가 라벨 A에 없음")
        for rc in j.get("reason_codes", []):
            if rc not in REASONS:
                errs.append(f"{pid}: reason_code 허용 목록 밖 {rc}")
    return errs


def cmd_validate() -> int:
    profs, total = profiles(), 0
    for rv in reviewers():
        A, B = labels(rv, "A"), labels(rv, "B")
        for nid, a in A.items():
            e = validate_a(a, packet_text(nid))
            total += len(e)
            print(f"[{rv}/A] {nid}: " + ("OK" if not e else f"{len(e)}건"))
            for x in e:
                print("   -", x)
        for nid, b in B.items():
            e = validate_b(b, A.get(nid), profs)
            total += len(e)
            print(f"[{rv}/B] {nid}: " + ("OK" if not e else f"{len(e)}건"))
            for x in e:
                print("   -", x)
    if not reviewers():
        print("라벨이 아직 없다:", LABELS)
    print("오류 합계:", total)
    return 1 if total else 0


# ------------------------------------------------------------------ agreement
def toks(s: str) -> set[str]:
    return set(re.findall(r"[가-힣A-Za-z0-9]+", s or ""))


def jaccard(a: str, b: str) -> float:
    x, y = toks(a), toks(b)
    return len(x & y) / len(x | y) if x | y else 0.0


def pair_reqs(ra: list[dict], rb: list[dict], th: float = 0.5) -> list[tuple[dict, dict]]:
    cand = sorted(((jaccard(a.get("source_sentence", ""), b.get("source_sentence", "")), i, j) for i, a in enumerate(ra) for j, b in enumerate(rb)), reverse=True)
    used_a, used_b, out = set(), set(), []
    for s, i, j in cand:
        if s < th or i in used_a or j in used_b:
            continue
        used_a.add(i)
        used_b.add(j)
        out.append((ra[i], rb[j]))
    return out


def cond_key(c: dict) -> tuple:
    return (c.get("attribute"), c.get("operator"), json.dumps(c.get("value"), sort_keys=True, ensure_ascii=False))


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if not n:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def agree_notice(a1: dict, a2: dict) -> dict:
    r1 = [r for r in a1.get("requirements", []) if r.get("kind") in ("ELIGIBILITY", "EXCLUSION")]
    r2 = [r for r in a2.get("requirements", []) if r.get("kind") in ("ELIGIBILITY", "EXCLUSION")]
    pairs = pair_reqs(r1, r2)
    tp = len(pairs)
    cs = cl = cn = lg = 0
    for x, y in pairs:
        k1, k2 = {cond_key(c) for c in x.get("conditions", [])}, {cond_key(c) for c in y.get("conditions", [])}
        at1, at2 = {c.get("attribute") for c in x.get("conditions", [])}, {c.get("attribute") for c in y.get("conditions", [])}
        cn += max(len(k1), len(k2))
        cs += len(k1 & k2)
        cl += len(at1 & at2)
        lg += all(x.get(f) == y.get(f) for f in ("kind", "logic", "logic_basis", "open_ended", "status"))
    return {"req_a": len(r1), "req_b": len(r2), "matched": tp, "cond_strict": cs, "cond_loose": cl, "cond_total": cn, "logic_match": lg}


def cmd_agree() -> int:
    rvs = reviewers()
    if len(rvs) < 2:
        print("라벨러가 2명 필요하다. 현재:", rvs)
        return 1
    r1, r2 = rvs[0], rvs[1]
    A1, A2, B1, B2 = labels(r1, "A"), labels(r2, "A"), labels(r1, "B"), labels(r2, "B")
    tot = Counter()
    per = {}
    for nid in sorted(set(A1) & set(A2)):
        m = agree_notice(A1[nid], A2[nid])
        per[nid] = m
        tot.update(m)
    P = tot["matched"] / tot["req_a"] if tot["req_a"] else 0
    R = tot["matched"] / tot["req_b"] if tot["req_b"] else 0
    F1 = 2 * P * R / (P + R) if P + R else 0
    jp = []
    for nid in sorted(set(B1) & set(B2)):
        d1 = {j["profile_id"]: j["overall"] for j in judgments_of(B1[nid])}
        d2 = {j["profile_id"]: j["overall"] for j in judgments_of(B2[nid])}
        jp += [(d1[p], d2[p]) for p in set(d1) & set(d2)]
    rep = {"reviewers": [r1, r2], "notices_compared": len(per), "requirement_F1": round(F1, 3),
           "condition_strict": round(tot["cond_strict"] / tot["cond_total"], 3) if tot["cond_total"] else None,
           "condition_loose": round(tot["cond_loose"] / tot["cond_total"], 3) if tot["cond_total"] else None,
           "logic_flags_match": round(tot["logic_match"] / tot["matched"], 3) if tot["matched"] else None,
           "judgment_pairs": len(jp), "judgment_agreement": round(sum(1 for a, b in jp if a == b) / len(jp), 3) if jp else None, "judgment_kappa": kappa(jp),
           "per_notice": per, "note": "합격선은 결과를 보기 전에 팀이 정해 가이드 §5 표에 적는다. 일치하지 않는 곳은 합의 회의에서 원문을 같이 보고 adjudication.csv에 남긴다."}
    (PILOT / "agreement_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "per_notice"}, ensure_ascii=False, indent=1))
    return 0


# ------------------------------------------------------------------ rules
def cmd_rules() -> int:
    profs = profiles()
    rows, mism = [], []
    cond_total = cond_match = 0
    for rv in reviewers():
        A, B = labels(rv, "A"), labels(rv, "B")
        for nid, b in B.items():
            a = A.get(nid)
            if not a:
                continue
            for j in judgments_of(b):
                pr = profs.get(j.get("profile_id"))
                if not pr:
                    continue
                v = judge(a, pr)
                ok = v.overall == j.get("overall")
                rows.append((rv, nid, j["profile_id"], j["overall"], v.overall, ok))
                for c in j.get("conditions", []):
                    cond_total += 1
                    cond_match += v.conditions.get(c.get("cond_ref")) == c.get("result")
                if not ok:
                    mism.append({"reviewer": rv, "notice_id": nid, "profile_id": j["profile_id"], "human": j["overall"], "rule": v.overall, "rule_reasons": v.reasons, "human_reasons": j.get("reason_codes", [])})
    n = len(rows)
    rep = {"pairs": n, "overall_match": round(sum(r[5] for r in rows) / n, 3) if n else None,
           "condition_match": round(cond_match / cond_total, 3) if cond_total else None,
           "confusion(human→rule)": dict(Counter(f"{r[3]}→{r[4]}" for r in rows)), "mismatches": mism,
           "note": "정답은 사람 판정(라벨 B)이다. 어긋난 곳은 규칙 버그, 가이드 모호성, 라벨 오류 중 어느 것인지 사람이 분류해 adjudication.csv에 남긴다."}
    (PILOT / "rules_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "validate"
    return {"validate": cmd_validate, "agree": cmd_agree, "rules": cmd_rules}.get(cmd, cmd_validate)()


if __name__ == "__main__":
    sys.exit(main())
