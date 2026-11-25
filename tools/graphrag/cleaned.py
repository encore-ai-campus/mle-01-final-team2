"""정리 층(data/cleaned/<날짜>/)에서 공고·구조화 조건·청크를 읽는다. 엔진이 원본 파서 대신 이 층을 쓰게 한다.

조건 규칙(hard/soft)은 data.py와 같다. 정리 층에는 정규화 확정값이 없고 `*_raw` 문자열만 있으므로 여기서 옵션 목록을 읽는다.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .evaluator import parse_age_options, parse_applicant_options, parse_business_age_options
from .regions import REPO, RegionGraph

CLEANED = REPO / "data" / "cleaned"


def available() -> bool:
    return (CLEANED / "LATEST").exists() and (CLEANED / (CLEANED / "LATEST").read_text().strip() / "notices.jsonl").exists()


def _jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").split("\n") if l.strip()]


def load_cleaned(rg: RegionGraph | None = None) -> dict:
    rg = rg or RegionGraph()
    d = CLEANED / (CLEANED / "LATEST").read_text().strip()
    skipped: Counter = Counter()
    notices = []
    for r in _jsonl(d / "notices.jsonl"):
        nid, st = r["notice_id"], r.get("structured") or {}
        conds = []
        if r["region_concept_ids"]:
            conds.append({"cond_id": f"{nid}#C-region", "attribute": "region", "strength": "soft", "value": {"concept_id": r["region_concept_ids"][0]},
                          "source_field": r["region_basis"], "evidence": f"{r['region_basis']}={r.get('region_raw') or r['org_raw']}"})
        elif r["source_system"] == "KSTARTUP":
            skipped["kstartup_region_unmapped"] += 1
        else:
            skipped["bizinfo_no_region_condition"] += 1
        if r["source_system"] == "KSTARTUP":
            ba = parse_business_age_options(st.get("business_age_raw"))
            if ba:
                conds.append({"cond_id": f"{nid}#C-business_age", "attribute": "business_age", "strength": "hard", "value": ba,
                              "source_field": "biz_enyy", "evidence": f"biz_enyy={st['business_age_raw']}"})
            else:
                skipped["kstartup_business_age_unparsed"] += 1
            ag = parse_age_options(st.get("founder_age_raw"))
            if ag:
                conds.append({"cond_id": f"{nid}#C-founder_age", "attribute": "founder_age", "strength": "soft", "value": {"ranges": ag},
                              "source_field": "biz_trgt_age", "evidence": f"biz_trgt_age={st['founder_age_raw']}"})
            else:
                skipped["kstartup_age_unparsed"] += 1
            ap = parse_applicant_options(st.get("applicant_target_raw"))
            if ap:
                conds.append({"cond_id": f"{nid}#C-applicant_type", "attribute": "applicant_type", "strength": "soft", "value": {"options": ap},
                              "source_field": "aply_trgt", "evidence": f"aply_trgt={st['applicant_target_raw']}"})
            else:
                skipped["kstartup_target_unparsed"] += 1
        notices.append({"notice_id": nid, "source": r["source_system"], "title": r["title"], "org": (r["org_names"] or [None])[0],
                        "executor": r.get("executor_org_name"), "category": r.get("category_major"), "category_mid": r.get("category_medium"),
                        "deadline": r.get("application_end"), "apply_status_kind": r["apply_status_kind"], "is_open": r["is_open"],
                        "detail_url": r["detail_url"], "fetched_at": r["fetched_at"], "conditions": conds, "text_requirements": "unparsed",
                        "text_sources": {"api": True, "attachment": bool((r.get("attachments") or {}).get("text_extracted"))},
                        "related_group_id": r.get("related_group_id")})
    chunks = [{**c, "source": c["source_system"]} for c in _jsonl(d / "chunks.jsonl")]
    return {"rg": rg, "notices": notices, "chunks": chunks, "skipped": dict(skipped), "cleaned_dir": str(d)}
