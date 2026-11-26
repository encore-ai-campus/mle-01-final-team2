"""규칙 기반 요건 후보 추출기 (2단계, 기계 후보).

출력은 정답이 아니라 **검수 전 후보**다. 모든 후보에 원문 문장(evidence_text, 수정 없이 복사)과 위치를 붙이고,
추출 직후 evidence_text가 원문에 그대로 있는지 100% 검사한다. 정답 라벨링 때는 이 결과를 라벨러에게 보여 주지 않는다(가이드 원칙).

사용: python tools/graphrag/extract_req.py   -> data/graph/requirement_candidates.jsonl, requirement_candidates_report.json,
                                              data/graph/conflicts_kstartup_business_age.csv
"""
from __future__ import annotations

import csv
import glob
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag.data import BIZ, _jsonl, KST  # noqa: E402
from graphrag.evaluator import parse_business_age_options  # noqa: E402
from graphrag.regions import REPO, RegionGraph  # noqa: E402

OUT = REPO / "data" / "graph"
RG = RegionGraph()

R_BAGE = re.compile(r"(?:업력|창업|설립)[^\n]{0,14}?(\d{1,2})\s*년\s*(이내|미만|이하)")
R_BAGE2 = re.compile(r"(\d{1,2})\s*년\s*(이내|미만|이하)[^\n]{0,8}?(?:창업|기업|업력)")
R_AGE = re.compile(r"만\s*(\d{1,2})\s*세\s*(이하|이상|미만|초과)")
R_LAW = re.compile(r"[「｢『]([^」｣』\n]{2,40})[」｣』]\s*((?:제\s*\d+\s*조(?:의\s*\d+)?)(?:\s*제\s*\d+\s*항)?)?")
R_EXCL = re.compile(r"제외|신청\s*불가|지원\s*불가|참여\s*제한|결격|불가능|제한\s*대상")
R_CERT = re.compile(r"벤처기업|이노비즈|메인비즈|확인서|인증서?|등록증|소상공인\s*확인")
CERTIFIED_STATUS = {"사회적기업", "여성기업", "장애인기업"}  # 설계서 4.3 분류 원칙(O-07)
R_SIZE = re.compile(r"(중소기업|소상공인|중견기업|소기업|중기업|사회적기업|여성기업|장애인기업)")
R_LOC_KW = re.compile(r"소재|관내|거주|본사|주소|사업장|소재지|이전")
R_SENT_END = "에이가의은는을를로과와도내권시도구군,·/()[]\"'“”‘’ \n.:;"

OP = {"이내": "LTE", "이하": "LTE", "미만": "LT", "이상": "GTE", "초과": "GT"}


def region_names() -> list[tuple[str, str | None, bool]]:
    """(표기, 개념ID or None, 모호) 목록. 모호한 표기는 개념을 확정하지 않는다."""
    by_name: dict[str, list[str]] = {}
    for rid, n in RG.nodes.items():
        if n.get("level") in ("SIDO", "SIGUNGU"):
            by_name.setdefault(n["name"], []).append(rid)
    out = []
    for name, ids in by_name.items():
        if len(name) >= 3:
            out.append((name, ids[0] if len(ids) == 1 else None, len(ids) > 1))
    for ab, rid in RG.sido_abbr.items():
        if ab != "전국" and len(ab) >= 2:
            out.append((ab, rid, False))
    out += [("광주", None, True), ("고성", None, True)]  # 광주(경기 광주시/구 광주광역시), 고성(강원/경남)은 모호
    out.sort(key=lambda x: -len(x[0]))
    return out


NAMES = region_names()


def find_regions(sent: str) -> list[tuple[str, str | None, bool]]:
    found, used = [], []
    for name, rid, amb in NAMES:
        i = sent.find(name)
        while i != -1:
            end = i + len(name)
            nxt = sent[end] if end < len(sent) else " "
            prev = sent[i - 1] if i > 0 else " "
            if nxt in R_SENT_END and not ("가" <= prev <= "힣" and len(name) <= 2) and not any(a <= i < b for a, b in used):
                found.append((name, rid, amb))
                used.append((i, end))
                break
            i = sent.find(name, i + 1)
    return found


def lines_of(text: str):
    pos = 0
    for raw in text.split("\n"):
        s = raw.strip()
        if s:
            yield pos + raw.index(s[0]), s
        pos += len(raw) + 1


def evid(line: str, m: re.Match | None = None) -> str:
    if len(line) <= 400 or m is None:
        return line[:400]
    a = max(0, m.start() - 150)
    return line[a:m.end() + 150]


def extract(text: str, notice_id: str, source: str, origin: str, section: str, kind: str) -> list[dict]:
    res = []

    def add(rule, attr, op, value, concept, amb, ev, pos):
        res.append({"notice_id": notice_id, "source": source, "evidence_origin": origin, "section": section, "kind": kind,
                    "rule_id": rule, "attribute": attr, "operator": op, "value": value, "concept": concept, "ambiguous": amb,
                    "evidence_text": ev, "char_start": pos, "extraction_method": "rule", "review_status": "unreviewed"})

    for pos, line in lines_of(text):
        for m in list(R_BAGE.finditer(line)) + list(R_BAGE2.finditer(line)):
            add("bage_years", "business_age", OP[m.group(2)], {"value": int(m.group(1)), "unit": "YEAR"}, None, False, evid(line, m), pos)
            break
        for m in R_AGE.finditer(line):
            add("founder_age", "founder_age", OP[m.group(2)], {"value": int(m.group(1)), "unit": "YEAR"}, None, False, evid(line, m), pos)
        if R_LOC_KW.search(line):
            for name, rid, amb in find_regions(line):
                add("region_loc", "region", "WITHIN", {"label": name}, rid, amb, evid(line), pos)
        for m in R_LAW.finditer(line):
            add("law_cite", "law_reference", "CITES", {"law": m.group(1).strip(), "article": (m.group(2) or "").replace(" ", "") or None}, None, False, evid(line, m), pos)
        if kind == "EXCLUSION" or (kind == "ELIGIBILITY" and R_EXCL.search(line)):
            if R_EXCL.search(line):
                add("exclusion_text", "exclusion", "TEXT_ONLY", {"text_only": True}, None, False, evid(line, R_EXCL.search(line)), pos)
        if R_CERT.search(line):
            m = R_CERT.search(line)
            add("certification", "certification", "EXISTS", {"label": m.group(0)}, None, False, evid(line, m), pos)
        m = R_SIZE.search(line)
        if m and kind == "ELIGIBILITY":
            if m.group(1) in CERTIFIED_STATUS:  # 인증·확인서를 발급받아야 성립하는 지위는 규모가 아니라 certification(CERTIFICATION)이다
                add("certification", "certification", "EXISTS", {"label": m.group(1)}, None, False, evid(line, m), pos)
            else:
                add("company_size", "company_size", "IS_A", {"label": m.group(1)}, None, False, evid(line, m), pos)
    return res


def run() -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    cands: list[dict] = []
    texts: dict[tuple, str] = {}
    run_id = (BIZ / "raw" / "LATEST").read_text().strip()
    for r in _jsonl(BIZ / "parsed" / run_id / "notices.jsonl"):
        t = r.get("eligibility_criteria_text") or ""
        texts[(r["notice_id"], "eligibility_api")] = t
        cands += extract(t, r["notice_id"], "BIZINFO", "API", "eligibility_api", "ELIGIBILITY")
    ed = sorted(glob.glob(str(BIZ / "extracted" / "*")))
    if ed:
        ed = Path(ed[-1])
        for it in json.loads((ed / "extraction_report.json").read_text(encoding="utf-8"))["items"]:
            if it["status"] not in ("OK", "OK_OCR"):
                continue
            try:
                t = (ed / it["text_file"]).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for s in it["sections"]:
                if s["label"] in ("ELIGIBILITY", "EXCLUSION"):
                    seg = t[s["start"]:s["end"]]
                    key = (it["notice_id"], f"att_{s['label'].lower()}_{s['start']}")
                    texts[key] = seg
                    cands += extract(seg, it["notice_id"], "BIZINFO", "ATTACHMENT_OCR" if it["status"] == "OK_OCR" else "ATTACHMENT",
                                     f"att_{s['label'].lower()}", s["label"])
    kst = _jsonl(KST)
    for r in kst:
        nid = f"KSTARTUP:{r['announcement_id']}"
        t = (r.get("eligibility_text") or "").replace("\r\n", "\n").replace("\r", "\n")
        texts[(nid, "eligibility_api")] = t
        cands += extract(t, nid, "KSTARTUP", "API", "eligibility_api", "ELIGIBILITY")
    # 원문 일치 검사: evidence_text가 해당 구간 텍스트에 그대로 있어야 한다
    bad = 0
    by_notice_sections: dict[str, list[str]] = {}
    for (nid, _), t in texts.items():
        by_notice_sections.setdefault(nid, []).append(t)
    for c in cands:
        if not any(c["evidence_text"] in t for t in by_notice_sections.get(c["notice_id"], [])):
            bad += 1
            c["review_status"] = "evidence_not_found"
    for i, c in enumerate(cands):
        c["candidate_id"] = f"RC-{i:06d}"
    (OUT / "requirement_candidates.jsonl").write_text("\n".join(json.dumps(c, ensure_ascii=False) for c in cands) + "\n", encoding="utf-8")
    # 커버리지
    notices_by_src = {"BIZINFO": len({k[0] for k in texts if k[0].startswith("BIZINFO")}), "KSTARTUP": len(kst)}
    with_c = {s: len({c["notice_id"] for c in cands if c["source"] == s}) for s in notices_by_src}
    by_attr = Counter((c["source"], c["attribute"]) for c in cands)
    conflicts = kstartup_conflicts(kst, cands)
    rep = {"candidates": len(cands), "evidence_not_found": bad, "notices": notices_by_src, "notices_with_candidate": with_c,
           "by_source_attribute": {f"{k[0]}:{k[1]}": v for k, v in sorted(by_attr.items())},
           "ambiguous_region_candidates": sum(1 for c in cands if c["attribute"] == "region" and c["ambiguous"]),
           "unresolved_region_candidates": sum(1 for c in cands if c["attribute"] == "region" and not c["concept"]),
           "kstartup_business_age_conflict": conflicts}
    (OUT / "requirement_candidates_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def kstartup_conflicts(kst: list[dict], cands: list[dict]) -> dict:
    """구조화 업력(biz_enyy)의 최대 옵션과 본문에서 뽑은 업력 상한이 어긋나는 공고(CQ-13 source_conflict 후보)."""
    txt: dict[str, list[dict]] = {}
    for c in cands:
        if c["source"] == "KSTARTUP" and c["attribute"] == "business_age":
            txt.setdefault(c["notice_id"], []).append(c)
    rows, cnt = [], Counter()
    for r in kst:
        nid = f"KSTARTUP:{r['announcement_id']}"
        ba = parse_business_age_options(r.get("business_age_raw"))
        if not ba or nid not in txt:
            cnt["no_text_or_unparsed"] += 1
            continue
        mx = ba["max_years"]
        tn = [c["value"]["value"] for c in txt[nid] if c["operator"] in ("LTE", "LT")]
        if not tn or mx is None:
            cnt["no_upper_bound_in_text"] += 1
            continue
        tmin, tmax = min(tn), max(tn)
        kind = "consistent" if (tmax == mx or tmin == mx) else ("text_narrower" if tmax < mx else "text_wider")
        cnt[kind] += 1
        if kind != "consistent":
            rows.append({"notice_id": nid, "title": r["title"], "structured_max_years": mx, "structured_raw": r["business_age_raw"],
                         "text_bounds": ";".join(map(str, sorted(set(tn)))), "kind": kind, "evidence": txt[nid][0]["evidence_text"][:160]})
    with open(OUT / "conflicts_kstartup_business_age.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["notice_id", "title", "structured_max_years", "structured_raw", "text_bounds", "kind", "evidence"])
        w.writeheader()
        w.writerows(rows)
    return dict(cnt)


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))
