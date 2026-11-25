#!/usr/bin/env python3
"""값 정규화 층: 정리층(data/cleaned/<날짜>/)을 읽어 공고별 '정규화 값 후보'를 만든다.

원칙
- 정리층은 건드리지 않는다. 이 층은 정리층 위에 따로 쌓고 언제든 다시 만들 수 있다.
- 모든 값은 **후보**다(review_status=unreviewed). 원문 문장(evidence_text)을 수정 없이 붙이고, 만든 직후 정리층 텍스트에
  그대로 있는지 100% 검사한다. 정답은 사람이 쓴 라벨이며 이 결과는 라벨러에게 보여 주지 않는다.
- 값의 출처를 구분한다: STRUCTURED(API의 선택형 필드), TEXT_RULE(본문·첨부 정규식), OCR_TEXT(OCR 첨부, 낮은 신뢰),
  PREVIEW_TEXT(배포용 문서 미리보기, 부분 텍스트).
- K-Startup 선택형 필드는 '조건'이 아니라 '검색 필터 체크박스'일 수 있다. 업력 옵션을 모두 고른 공고는 제한이 없는 것이 아니라
  필터가 정보를 주지 않는 것이므로(filter_informative=false) 판정에 쓰지 않는다.
- 법령·제도 용어의 뜻(정의)은 여기서 만들지 않는다. 용어 사전(data/ref/term_standard_v0.1.json)의 표기 일치만 찾는다.

출력(data/normalized/<날짜>/): notices_normalized.jsonl, normalization_report.json, conflicts_business_age.csv
사용: python tools/normalize_values.py [--cleaned data/cleaned/20261124]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphrag.evaluator import AGE_OPTION_RANGES, BUSINESS_AGE_ALL, APPLICANT_OPTIONS  # noqa: E402
from graphrag.extract_req import extract  # noqa: E402
from graphrag.regions import REPO  # noqa: E402

ORIGIN_SOURCE = {"API": "TEXT_RULE", "ATTACHMENT": "TEXT_RULE", "ATTACHMENT_OCR": "OCR_TEXT", "ATTACHMENT_PREVIEW": "PREVIEW_TEXT"}
SECTION_KIND = {"eligibility_api": "ELIGIBILITY", "exclusion_api": "EXCLUSION", "att_eligibility": "ELIGIBILITY", "att_exclusion": "EXCLUSION"}
APPLICANT_MAP = {"청소년": "APPLICANT_TYPE:청소년", "대학생": "APPLICANT_TYPE:대학생", "일반인": "APPLICANT_TYPE:일반인", "대학": "APPLICANT_TYPE:대학",
                 "연구기관": "APPLICANT_TYPE:연구기관", "일반기업": None, "1인 창조기업": "APPLICANT_TYPE:1인 창조기업"}
YOUTH_BANDS = [(0, 20), (20, 40), (40, 200)]


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").split("\n") if l.strip()]


def business_age_structured(raw: str | None) -> dict | None:
    """'예비창업자,1년미만,…' -> 상한·예비창업자 허용·필터 정보성. 알 수 없는 표기가 있으면 None."""
    if not raw:
        return None
    opts = [t.strip() for t in raw.split(",") if t.strip()]
    if not opts or any(o not in BUSINESS_AGE_ALL for o in opts):
        return {"raw": raw, "parse_status": "UNPARSED_OPTION"}
    years = [int(re.match(r"(\d+)", o).group(1)) for o in opts if o != "예비창업자"]
    allopt = set(opts) == BUSINESS_AGE_ALL
    return {"raw": raw, "parse_status": "OK", "pre_founder_allowed": "예비창업자" in opts, "upper_exclusive_years": max(years) if years else None,
            "options": opts, "all_options": allopt, "filter_informative": not allopt}


def founder_age_structured(raw: str | None) -> dict | None:
    if not raw:
        return None
    opts = [t.strip() for t in raw.split(",") if t.strip()]
    if not opts or any(o not in AGE_OPTION_RANGES for o in opts):
        return {"raw": raw, "parse_status": "UNPARSED_OPTION"}
    bands = sorted(AGE_OPTION_RANGES[o] for o in opts)
    allopt = len(set(opts)) == len(AGE_OPTION_RANGES)
    merged: list[list[int]] = []
    for lo, hi in bands:  # 이어지는 구간은 합친다
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    return {"raw": raw, "parse_status": "OK", "allowed_ranges_half_open": merged, "all_options": allopt, "filter_informative": not allopt}


def applicant_structured(raw: str | None) -> dict | None:
    if not raw:
        return None
    opts = [t.strip() for t in raw.split(",") if t.strip()]
    if not opts or any(o not in APPLICANT_OPTIONS for o in opts):
        return {"raw": raw, "parse_status": "UNPARSED_OPTION"}
    return {"raw": raw, "parse_status": "OK", "options": opts, "concept_ids": [APPLICANT_MAP[o] for o in opts if APPLICANT_MAP[o]],
            "unmapped_options": [o for o in opts if not APPLICANT_MAP[o]], "all_options": set(opts) == APPLICANT_OPTIONS}


def term_patterns() -> list[tuple[str, str, re.Pattern]]:
    d = json.loads((REPO / "data/ref/term_standard_v0.1.json").read_text(encoding="utf-8"))
    out = []
    for a in d["applicant_types"]:
        for surf in [a["label"], *a.get("aliases", [])]:
            if len(surf) >= 2:
                lookbehind = r"(?<!중)" if surf == "소기업" else ""  # '중소기업' 안의 '소기업' 방지
                out.append((a["concept_id"], surf, re.compile(lookbehind + re.escape(surf))))
    out.sort(key=lambda x: -len(x[1]))
    return out


def run(cleaned: Path) -> dict:
    out_dir = REPO / "data" / "normalized" / cleaned.name
    out_dir.mkdir(parents=True, exist_ok=True)
    notices = jl(cleaned / "notices.jsonl")
    chunks = jl(cleaned / "chunks.jsonl")
    by_n: dict[str, list[dict]] = defaultdict(list)
    for c in chunks:
        by_n[c["notice_id"]].append(c)
    terms = term_patterns()
    cnt: Counter = Counter()
    rows, conflicts = [], []
    bad_evidence = 0
    for n in notices:
        nid, src, st = n["notice_id"], n["source_system"], n.get("structured") or {}
        sources: list[tuple[str, str, str, str, str]] = []  # (text, kind, section, origin, source_kind)
        if n.get("eligibility_text"):
            sources.append((n["eligibility_text"], "ELIGIBILITY", "eligibility_api", "API", "TEXT_RULE"))
        if n.get("exclusion_text"):
            sources.append((n["exclusion_text"], "EXCLUSION", "exclusion_api", "API", "TEXT_RULE"))
        for c in by_n.get(nid, []):
            base = c["section"].split("@")[0]
            if base in ("att_eligibility", "att_exclusion") or (base == "att_preview"):
                kind = SECTION_KIND.get(base, "ELIGIBILITY")
                sources.append((c["text"], kind, base, c["origin"], ORIGIN_SOURCE.get(c["origin"], "TEXT_RULE")))
        facts, seen = [], set()
        for text, kind, section, origin, skind in sources:
            for f in extract(text, nid, src, origin, section, kind):
                key = (f["attribute"], f["operator"], json.dumps(f["value"], sort_keys=True, ensure_ascii=False), f["evidence_text"])
                if key in seen:
                    continue
                seen.add(key)
                if f["evidence_text"] not in text:
                    bad_evidence += 1
                    continue
                facts.append({"attribute": f["attribute"], "operator": f["operator"], "value": f["value"], "concept_id": f["concept"], "ambiguous": f["ambiguous"], "rule_id": f["rule_id"],
                              "kind": kind, "source_kind": skind, "section": section, "evidence_text": f["evidence_text"], "char_start": f["char_start"],
                              "review_status": "unreviewed", "trust": "LOW" if skind in ("OCR_TEXT", "PREVIEW_TEXT") else "RULE"})
        mentions, mseen = [], set()
        for text, kind, section, origin, skind in sources:
            if kind != "ELIGIBILITY":
                continue
            taken: list[tuple[int, int]] = []
            for cid, surf, pat in terms:
                for m in pat.finditer(text):
                    if any(a <= m.start() < b for a, b in taken) or (cid, section) in mseen:
                        continue
                    taken.append((m.start(), m.end()))
                    mseen.add((cid, section))
                    mentions.append({"concept_id": cid, "surface": surf, "section": section, "source_kind": skind})
        structured: dict = {}
        if src == "KSTARTUP":
            for key, fn, name in (("business_age_raw", business_age_structured, "business_age"), ("founder_age_raw", founder_age_structured, "founder_age"), ("applicant_target_raw", applicant_structured, "applicant_target")):
                v = fn(st.get(key))
                if v:
                    structured[name] = v
                    cnt[f"structured.{name}.{v['parse_status']}"] += 1
                    if v.get("all_options"):
                        cnt[f"structured.{name}.all_options"] += 1
            ba = structured.get("business_age")
            if ba and ba.get("parse_status") == "OK" and ba.get("upper_exclusive_years") and ba.get("filter_informative"):
                tn = [f["value"]["value"] for f in facts if f["attribute"] == "business_age" and f["operator"] in ("LTE", "LT") and f["kind"] == "ELIGIBILITY"]
                if tn:
                    mx = ba["upper_exclusive_years"]
                    kind = "consistent" if mx in tn else ("text_narrower" if max(tn) < mx else "text_wider")
                    cnt[f"business_age_text_vs_structured.{kind}"] += 1
                    if kind != "consistent":
                        conflicts.append({"notice_id": nid, "title": n["title"], "structured_raw": ba["raw"], "structured_upper_exclusive_years": mx, "text_bounds": ";".join(map(str, sorted(set(tn)))), "kind": kind})
        else:
            tg = st.get("target_group_text")
            if tg:
                structured["target_group_text"] = tg
        region = {"concept_ids": n.get("region_concept_ids", []), "source": n.get("region_source"), "raw": n.get("region_raw"), "scope_hint": n.get("region_scope_hint"),
                  "scope_confirmed": False if n.get("region_source") else None}
        if not region["concept_ids"]:
            cnt[f"region_missing.{src}"] += 1
        for f in facts:
            cnt[f"fact.{src}.{f['attribute']}"] += 1
        cnt[f"notice_with_fact.{src}"] += bool(facts)
        cnt[f"notice_with_term.{src}"] += bool(mentions)
        cnt[f"notice_total.{src}"] += 1
        rows.append({"notice_id": nid, "source_system": src, "is_open": n.get("is_open"), "structured_normalized": structured, "region": region, "facts": facts, "applicant_term_mentions": mentions,
                     "text_sources": sorted({f"{o}:{s}" for _, _, s, o, _ in sources}), "normalizer_version": "0.1"})
    (out_dir / "notices_normalized.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    with open(out_dir / "conflicts_business_age.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["notice_id", "title", "structured_raw", "structured_upper_exclusive_years", "text_bounds", "kind"])
        w.writeheader()
        w.writerows(conflicts)
    rep = {"cleaned_dir": str(cleaned.relative_to(REPO)), "notices": len(rows), "facts": sum(len(r["facts"]) for r in rows), "evidence_not_found_dropped": bad_evidence,
           "ambiguous_region_facts": sum(1 for r in rows for f in r["facts"] if f["attribute"] == "region" and f["ambiguous"]),
           "facts_by_source_kind": dict(Counter(f["source_kind"] for r in rows for f in r["facts"])),
           "counters": dict(sorted(cnt.items())), "note": "모든 값은 검수 전 후보다. K-Startup 선택형 필드는 필터 체크박스일 수 있어 all_options면 판정에 쓰지 않는다."}
    rep["ocr_review"] = ocr_review(out_dir)
    (out_dir / "normalization_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


def ocr_review(out_dir: Path, low_conf: float = 75.0, short_chars: int = 200) -> dict:
    """OCR로만 읽은 첨부 중 사람이 원본 이미지와 대조해야 할 것(신뢰도 낮음·글자 수 적음)을 목록으로 남긴다."""
    import glob
    ed = sorted(glob.glob(str(REPO / "data/bizinfo/extracted/*")))
    rp = Path(ed[-1]) / "extraction_report.json"
    items = json.loads(rp.read_text(encoding="utf-8"))["items"]
    ocr = [x for x in items if x["status"] == "OK_OCR"]
    rows = []
    for x in ocr:
        why = [w for w, c in (("LOW_CONF", x["ocr"]["mean_conf"] < low_conf), ("SHORT", x["chars"] < short_chars), ("TRUNCATED", x["ocr"].get("truncated"))) if c]
        if why:
            rows.append({"notice_id": x["notice_id"], "file": x["file"], "mean_conf": x["ocr"]["mean_conf"], "chars": x["chars"], "reasons": ",".join(why)})
    rows.sort(key=lambda r: r["mean_conf"])
    with open(out_dir / "ocr_review.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["notice_id", "file", "mean_conf", "chars", "reasons"])
        w.writeheader()
        w.writerows(rows)
    return {"ocr_files": len(ocr), "need_human_check": len(rows), "median_conf": sorted(x["ocr"]["mean_conf"] for x in ocr)[len(ocr) // 2], "thresholds": {"low_conf": low_conf, "short_chars": short_chars}}


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--cleaned", default=str(REPO / "data" / "cleaned" / "20261124"))
    a = ap.parse_args()
    print(json.dumps(run(Path(a.cleaned)), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
