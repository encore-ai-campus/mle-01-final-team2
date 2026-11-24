"""정리 파일을 읽어 공고·구조화 조건·검색 청크를 만든다.

입력:
- 기업마당: data/bizinfo/parsed/<run>/notices.jsonl (+ 로컬 전용 extracted/ 첨부 텍스트가 있으면 청크에 포함)
- K-Startup: data/kstartup/processed/kstartup_cleaned.jsonl (동료 정리본, 수정 요청 반영 전)

원칙: 원문에 없는 값을 만들지 않는다. 읽지 못한 값은 조건을 만들지 않고 `skipped`에 기록한다.
"""
from __future__ import annotations

import glob
import json
import os
import re
from collections import Counter
from pathlib import Path

from .evaluator import parse_age_options, parse_applicant_options, parse_business_age_options
from .regions import REPO, RegionGraph

BIZ = REPO / "data" / "bizinfo"
KST = REPO / "data" / "kstartup" / "processed" / "kstartup_cleaned.jsonl"
MIN_CHUNK = 20
MAX_CHUNK = 900
REDACT = re.compile(r"\[REDACTED[^\]]*\]")


def _jsonl(path: Path) -> list[dict]:
    # str.splitlines()는 문자열 안의 특수 줄바꿈에서 줄을 나누므로 \n으로만 나눈다
    return [json.loads(l) for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]


def _split(text: str) -> list[str]:
    """문단 단위로 나누되 MAX_CHUNK를 넘으면 줄 단위로 합쳐 자른다."""
    out, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > MAX_CHUNK and cur:
            out.append(cur.strip())
            cur = ""
        cur += line + "\n"
    if cur.strip():
        out.append(cur.strip())
    return out


def _chunk(notice_id: str, source: str, section: str, origin: str, text: str, start: int = 0) -> list[dict]:
    res = []
    for i, t in enumerate(_split(text)):
        if len(REDACT.sub("", t).strip()) < MIN_CHUNK:  # 대체 문자열만 있거나 너무 짧은 청크는 만들지 않는다
            continue
        res.append({"chunk_id": f"{notice_id}#{section}:{i}", "notice_id": notice_id, "source": source,
                    "section": section, "origin": origin, "text": t})
    return res


def load_bizinfo(rg: RegionGraph, skipped: Counter) -> tuple[list[dict], list[dict]]:
    run = (BIZ / "raw" / "LATEST").read_text().strip()
    rows = _jsonl(BIZ / "parsed" / run / "notices.jsonl")
    ext_dirs = sorted(glob.glob(str(BIZ / "extracted" / "*")))
    att: dict[str, list[dict]] = {}
    ed = Path(ext_dirs[-1]) if ext_dirs else None
    if ed and (ed / "extraction_report.json").exists():
        for it in json.loads((ed / "extraction_report.json").read_text(encoding="utf-8"))["items"]:
            if it["status"] in ("OK", "OK_OCR"):
                att.setdefault(it["notice_id"], []).append(it)
    notices, chunks = [], []
    for r in rows:
        nid = r["notice_id"]
        conds = []
        code = r.get("jurisdiction_sido_code")
        if code and f"REGION:{code}" in rg.nodes:  # 소관 기관이 시도일 때만. 해시태그는 근거로 쓰지 않는다(전 시도 태그 27%)
            conds.append({"cond_id": f"{nid}#C-region", "attribute": "region", "strength": "soft",
                          "value": {"concept_id": f"REGION:{code}"}, "source_field": "jrsdInsttNm",
                          "evidence": f"소관 기관 {r['jurisdiction_org_name']}"})
        else:
            skipped["bizinfo_no_region_condition"] += 1
        notices.append({"notice_id": nid, "source": "BIZINFO", "title": r["title"], "org": r.get("jurisdiction_org_name"),
                        "executor": r.get("executor_org_name") if r.get("executor_kind") == "ORG" else None,
                        "category": r.get("support_category_major"), "category_mid": r.get("support_category_medium"),
                        "deadline": (r.get("deadline_at") or "")[:10] or None, "apply_status_kind": r["apply_status_kind"],
                        "is_open": True, "detail_url": r["detail_url"], "fetched_at": r["fetched_at"],
                        "conditions": conds, "text_requirements": "unparsed",
                        "text_sources": {"api": True, "attachment": nid in att}})
        # 청크: API 요약·자격 문구, 첨부의 자격·제외·기준·기간·방법·혜택 구간
        chunks += _chunk(nid, "BIZINFO", "title_summary", "API", r["title"] + "\n" + (r.get("summary") or ""))
        chunks += _chunk(nid, "BIZINFO", "eligibility_api", "API", r.get("eligibility_criteria_text") or "")
        for it in att.get(nid, []):
            tp = ed / it["text_file"]
            try:
                t = tp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for s in it["sections"]:
                if s["label"] in ("ELIGIBILITY", "EXCLUSION", "CRITERION", "BENEFIT", "PERIOD", "METHOD"):
                    chunks += _chunk(nid, "BIZINFO", f"att_{s['label'].lower()}", "ATTACHMENT_OCR" if it["status"] == "OK_OCR" else "ATTACHMENT",
                                     t[s["start"]:s["end"]])
    return notices, chunks


def load_kstartup(rg: RegionGraph, skipped: Counter) -> tuple[list[dict], list[dict]]:
    notices, chunks = [], []
    for r in _jsonl(KST):
        nid = f"KSTARTUP:{r['announcement_id']}"
        s = r["source_api_fields"]
        conds = []
        rid = rg.resolve_abbr(r.get("support_region_raw"))
        if rid:
            conds.append({"cond_id": f"{nid}#C-region", "attribute": "region", "strength": "soft", "value": {"concept_id": rid},
                          "source_field": "supt_regin", "evidence": f"supt_regin={r['support_region_raw']}"})
        else:
            skipped["kstartup_region_unmapped"] += 1
        ba = parse_business_age_options(r.get("business_age_raw"))
        if ba:
            conds.append({"cond_id": f"{nid}#C-business_age", "attribute": "business_age", "strength": "hard", "value": ba,
                          "source_field": "biz_enyy", "evidence": f"biz_enyy={r['business_age_raw']}"})
        else:
            skipped["kstartup_business_age_unparsed"] += 1
        ag = parse_age_options(s.get("biz_trgt_age"))
        if ag:
            conds.append({"cond_id": f"{nid}#C-founder_age", "attribute": "founder_age", "strength": "soft", "value": {"ranges": ag},
                          "source_field": "biz_trgt_age", "evidence": f"biz_trgt_age={s.get('biz_trgt_age')}"})
        else:
            skipped["kstartup_age_unparsed"] += 1
        ap = parse_applicant_options(r.get("support_target_raw"))
        if ap:
            conds.append({"cond_id": f"{nid}#C-applicant_type", "attribute": "applicant_type", "strength": "soft", "value": {"options": ap},
                          "source_field": "aply_trgt", "evidence": f"aply_trgt={r['support_target_raw']}"})
        else:
            skipped["kstartup_target_unparsed"] += 1
        notices.append({"notice_id": nid, "source": "KSTARTUP", "title": r["title"], "org": r.get("organization"),
                        "executor": None, "category": (r.get("support_category_raw") or "").replace("&amp;", "&"), "category_mid": None,
                        "deadline": r.get("application_end"), "apply_status_kind": "DATE_RANGE", "start": r.get("application_start"),
                        "is_open": r.get("application_status_raw") == "Y", "detail_url": r.get("detail_url"),
                        "fetched_at": "2026-11-24", "conditions": conds, "text_requirements": "unparsed",
                        "text_sources": {"api": True, "attachment": False}})
        t = r["title"] + "\n" + (r.get("announcement_body") or "")
        chunks += _chunk(nid, "KSTARTUP", "title_body", "API", t)
        for field, sec in (("eligibility_text", "eligibility_api"), ("support_details", "support_details"), ("evaluation_criteria", "evaluation")):
            chunks += _chunk(nid, "KSTARTUP", sec, "API", (r.get(field) or "").replace("\r\n", "\n").replace("\r", "\n"))
    return notices, chunks


def load_all(rg: RegionGraph | None = None) -> dict:
    rg = rg or RegionGraph()
    skipped: Counter = Counter()
    bn, bc = load_bizinfo(rg, skipped)
    kn, kc = load_kstartup(rg, skipped)
    return {"rg": rg, "notices": bn + kn, "chunks": bc + kc, "skipped": dict(skipped)}
