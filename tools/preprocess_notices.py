#!/usr/bin/env python3
"""기업마당·K-Startup 원본을 공통 스키마의 '정리 층'으로 만든다 (표준 라이브러리 + tools/graphrag만 사용).

원칙
- 원본(raw)과 파싱 결과(parsed)는 바꾸지 않고 새 폴더(data/cleaned/<날짜>/)에 쓴다. 같은 입력이면 같은 결과(멱등).
- 정리는 **되돌릴 수 있는 것**만 한다: 줄바꿈·HTML 엔티티·공백, 필드 이름·ID 규칙, 기관명 분리, 날짜 형식, 상태 계산.
- 값을 추론하거나 정규화를 확정하지 않는다(나이·업력·업종 값, 옵션 관계, 요건 승인은 골든셋 뒤). 원문 값은 `*_raw`로 보존한다.
- 공공기관 연락처는 가리지 않는다(팀 결정). `[REDACTED…]` 같은 대체 문자열을 만들지 않는다.
- K-Startup은 동료 정리본이 아니라 원본(data/kstartup/raw/<날짜>_full)에서 다시 정리한다.
- 모집 중인 K-Startup 공고는 접수 시작일이 1년 이전이어도 포함한다.

사용: python tools/preprocess_notices.py [--kstartup-raw data/kstartup/raw/20261124_full]
출력: data/cleaned/<날짜>/notices.jsonl, chunks.jsonl, cleaning_report.json, org_split_review.csv, related_groups.csv (로컬 전용)
"""
from __future__ import annotations

import argparse
import csv
import glob
import hashlib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from graphrag.regions import REPO, RegionGraph  # noqa: E402

BIZ = REPO / "data" / "bizinfo"
TODAY = "2026-11-24"
MIN_CHUNK, MAX_CHUNK = 20, 900
TITLE_SUFFIX = ("본부장", "팀장", "센터장", "원장", "대표", "이사장", "처장", "국장", "부장", "과장", "실장", "소장", "단장", "관장", "총장", "학장", "담당")
ENTITY = re.compile(r"&(?:[a-zA-Z]{2,8}|#\d{1,5});")
REDACT = re.compile(r"\[REDACTED[^\]]*\]")
APPLY_LABELS = {"aply_mthd_onli_rcpt_istc": "온라인 접수", "aply_mthd_eml_rcpt_istc": "이메일 접수", "aply_mthd_vst_rcpt_istc": "방문 접수",
                "aply_mthd_pssr_rcpt_istc": "우편 접수", "aply_mthd_fax_rcpt_istc": "팩스 접수", "aply_mthd_etc_istc": "기타 접수"}
ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍﻿"), None)


def sha(obj) -> str:
    b = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def clean_text(s: str | None) -> str | None:
    """줄바꿈·엔티티·공백만 정리한다. 내용은 바꾸지 않는다."""
    if s is None:
        return None
    s = html.unescape(s).translate(ZERO_WIDTH).replace(" ", " ").replace("\r\n", "\n").replace("\r", "\n")
    s = "\n".join(line.rstrip() for line in s.split("\n"))
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s or None


def norm_for_fidelity(s: str | None) -> str:
    """원본과 정리본이 '공백·엔티티 차이'만 있는지 비교하는 기준."""
    return re.sub(r"\s+", " ", html.unescape(s or "").replace(" ", " ").translate(ZERO_WIDTH)).strip()


def iso_date(d: str | None) -> str | None:
    if not d:
        return None
    d = d.strip()
    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(d[:10] if fmt == "%Y-%m-%d" else d, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def split_org(raw: str | None) -> dict:
    """K-Startup 기관 문자열 -> 기관 목록과 직함. 규칙으로만 나누고 원문은 보존한다."""
    raw = (raw or "").strip()
    names, roles, flags = [], [], []
    for part in [p.strip() for p in raw.split(",") if p.strip()]:
        toks = part.split()
        if len(toks) >= 2 and toks[-1].endswith(TITLE_SUFFIX):
            names.append(" ".join(toks[:-1]))
            roles.append(toks[-1])
            flags.append("title_split")
        else:
            names.append(part)
            roles.append(None)
    if len(names) > 1:
        flags.append("multiple_orgs")
    return {"org_raw": raw, "org_names": names, "org_role_titles": roles, "org_flags": sorted(set(flags))}


def norm_title_key(title: str) -> str:
    t = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", title)
    t = re.sub(r"20\d\d\s*년?|제?\s*\d+\s*(?:차|회|기|분기)|상반기|하반기|연장|재공고|재모집|추가\s*모집|모집\s*공고|공고|모집|안내|\s+", "", t)
    return t


def signals(title: str) -> list[str]:
    return [k for k in ("연장", "재공고", "재모집", "추가모집", "추가 모집", "정정", "변경") if k in title]


def chunk(nid: str, source: str, section: str, origin: str, text: str | None, meta: dict, span: dict | None = None) -> list[dict]:
    if not text:
        return []
    out, cur, i = [], "", 0
    def flush():
        nonlocal cur, i
        t = cur.strip()
        if len(REDACT.sub("", t).strip()) >= MIN_CHUNK:
            c = {"chunk_id": f"{nid}#{section}:{i}", "notice_id": nid, "source_system": source, "section": section, "origin": origin, "text": t,
                 "content_hash": sha(t.encode("utf-8")), **meta}
            if span:
                c["source_span"] = span
            out.append(c)
            i += 1
        cur = ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > MAX_CHUNK and cur:
            flush()
        cur += line + "\n"
    flush()
    return out


def clean_bizinfo(rg: RegionGraph, report: Counter, changed: Counter) -> tuple[list[dict], list[dict]]:
    run = (BIZ / "raw" / "LATEST").read_text().strip()
    rows = [json.loads(l) for l in (BIZ / "parsed" / run / "notices.jsonl").read_text(encoding="utf-8").split("\n") if l.strip()]
    all_ed = sorted(glob.glob(str(BIZ / "extracted" / "*")))
    ed = [d for d in all_ed if not Path(d).name.startswith("00_manual_")]  # 00_manual_*: 사람이 내려받아 보충한 첨부(최신 추출 폴더 선택에 끼지 않게 앞에 정렬)
    supp = [Path(d) for d in all_ed if Path(d).name.startswith("00_manual_")]
    att: dict[str, list[dict]] = defaultdict(list)
    prev: dict[str, list[dict]] = defaultdict(list)
    edir = Path(ed[-1]) if ed else None
    if edir and (edir / "extraction_report.json").exists():
        for it in json.loads((edir / "extraction_report.json").read_text(encoding="utf-8"))["items"]:
            if it["status"] in ("OK", "OK_OCR"):
                att[it["notice_id"]].append(it)
            elif it["status"] == "DISTRIBUTION_DOC_UNSUPPORTED":
                prev[it["notice_id"]].append(it)  # 배포용 hwp: 본문은 복사 방지 대상이라 읽지 않고, 파일에 저장된 미리보기(PrvText)만 쓴다
    for sd in supp:
        if (sd / "extraction_report.json").exists():
            for it in json.loads((sd / "extraction_report.json").read_text(encoding="utf-8"))["items"]:
                if it["status"] in ("OK", "OK_OCR") and it.get("notice_id"):
                    it["_dir"] = str(sd)
                    it["origin_note"] = "MANUAL_SUPPLEMENT"
                    att[it["notice_id"]].append(it)
                    prev.pop(it["notice_id"], None) if it["notice_id"] in prev and "공고문" in it["file"] else None  # 본문이 PDF로 보충되면 미리보기는 쓰지 않는다
    raw_title = {}
    for pg in sorted(glob.glob(str(BIZ / "raw" / run / "page_*.json"))):
        for it in json.loads(Path(pg).read_text(encoding="utf-8"))["jsonArray"]:
            raw_title[it["pblancId"]] = it["pblancNm"]
    notices, chunks = [], []
    for r in rows:
        nid = r["notice_id"]
        code = r.get("jurisdiction_sido_code")
        region_ids = [f"REGION:{code}"] if code and f"REGION:{code}" in rg.nodes else []
        texts = {k: clean_text(r.get(k)) for k in ("summary", "eligibility_criteria_text", "apply_method_text", "contact_text")}
        for k in texts:
            if texts[k] != r.get(k):
                changed[f"bizinfo.{k}"] += 1
        t_raw = raw_title.get(r["source_id"], r["title"])
        title = re.sub(r"\s+", " ", t_raw).strip()
        if title != t_raw:
            changed["bizinfo.title"] += 1
        n = {"notice_id": nid, "source_system": "BIZINFO", "source_id": r["source_id"], "title": title, "title_raw": t_raw,
             "detail_url": r["detail_url"], "published_at": r.get("published_at"), "source_updated_at": r.get("source_updated_at"),
             "application_start": r.get("application_start_date"), "application_end": r.get("application_end_date"), "deadline_at": r.get("deadline_at"),
             "apply_status_kind": r["apply_status_kind"], "is_open": True,
             "period_status": "OPEN_WITH_DEADLINE" if r.get("deadline_at") else "OPEN_NO_DATE_DEADLINE",
             "org_raw": r.get("jurisdiction_org_name"), "org_names": [r["jurisdiction_org_name"]] if r.get("jurisdiction_org_name") else [], "org_role_titles": [None], "org_flags": [],
             "executor_org_name": r.get("executor_org_name") if r.get("executor_kind") == "ORG" else None, "executor_kind": r.get("executor_kind"),
             "category_major": r.get("support_category_major"), "category_medium": r.get("support_category_medium"),
             "region_raw": None, "region_concept_ids": region_ids, "region_basis": "jurisdiction_org_sido" if region_ids else None,
             "region_scope_hint": r.get("region_scope_hint"), "region_tags_hint": r.get("region_tags"),
             "structured": {"target_group_text": r.get("target_group_text")},
             "eligibility_text": texts["eligibility_criteria_text"], "body_text": texts["summary"], "support_text": None, "evaluation_text": None,
             "apply_method_text": texts["apply_method_text"], "apply_url": r.get("apply_url"), "contact_text": texts["contact_text"],
             "is_integrated": None, "program_name": None, "attachments": {"count": len(r.get("attachment_ids", [])), "text_extracted": len(att.get(nid, [])), "preview_only": len(prev.get(nid, []))},
             "fetched_at": r["fetched_at"], "version": r["version"], "is_latest": r["is_latest"], "raw_hash": r["raw_hash"], "source_run": run}
        n["content_hash"] = sha({k: n[k] for k in ("title", "eligibility_text", "body_text", "apply_method_text", "application_start", "application_end", "category_major")})
        notices.append(n)
        meta = {"is_open": True, "region_concept_ids": region_ids}
        chunks += chunk(nid, "BIZINFO", "title_summary", "API", f"{title}\n{texts['summary'] or ''}", meta)
        chunks += chunk(nid, "BIZINFO", "eligibility_api", "API", texts["eligibility_criteria_text"], meta)
        chunks += chunk(nid, "BIZINFO", "apply_method", "API", texts["apply_method_text"], meta)
        for fi, it in enumerate(att.get(nid, [])):
            try:
                t = (Path(it.get("_dir") or edir) / it["text_file"]).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                report["bizinfo_attachment_text_unreadable"] += 1
                continue
            for s in it["sections"]:
                if s["label"] in ("ELIGIBILITY", "EXCLUSION", "CRITERION", "BENEFIT", "PERIOD", "METHOD"):
                    chunks += chunk(nid, "BIZINFO", f"att_{s['label'].lower()}@f{fi}-{s['start']}", "ATTACHMENT_OCR" if it["status"] == "OK_OCR" else "ATTACHMENT",
                                    clean_text(t[s["start"]:s["end"]]), meta, {"file": it["file"], "start": s["start"], "end": s["end"]})
        for it in prev.get(nid, []):
            t = read_preview(it["file"])
            if t:
                report["bizinfo_distribution_doc_preview_chunks"] += 1
                chunks += chunk(nid, "BIZINFO", "att_preview", "ATTACHMENT_PREVIEW", clean_text(t), meta, {"file": it["file"], "note": "배포용 문서의 저장된 미리보기(앞 1,022자). 본문 전체가 아니며 요건 판정 근거로 쓰지 않는다"})
    return notices, chunks


def read_preview(fname: str) -> str:
    """배포용 hwp의 PrvText(문서가 스스로 저장한 평문 미리보기)를 읽는다. 본문 암호는 풀지 않는다."""
    import olefile
    for f in sorted(glob.glob(str(BIZ / "files" / "*" / fname))):
        try:
            return olefile.OleFileIO(f).openstream("PrvText").read().decode("utf-16le", errors="replace")
        except Exception:
            continue
    return ""


def clean_kstartup(rg: RegionGraph, kraw: Path, report: Counter, changed: Counter) -> tuple[list[dict], list[dict], list[dict]]:
    allr = [json.loads(l) for l in (kraw / "announcements_all.jsonl").read_text(encoding="utf-8").split("\n") if l.strip()]
    one = {str(r["pbanc_sn"]) for r in (json.loads(l) for l in (kraw / "announcements_1y.jsonl").read_text(encoding="utf-8").split("\n") if l.strip())}
    sel = [r for r in allr if str(r["pbanc_sn"]) in one or r.get("rcrt_prgs_yn") == "Y"]
    report["kstartup_selected_by_1y"] = len(one)
    report["kstartup_added_open_outside_1y"] = len(sel) - len(one)
    notices, chunks, org_review = [], [], []
    for r in sel:
        sn = str(r["pbanc_sn"])
        nid = f"KSTARTUP:{sn}"
        T = {k: clean_text(r.get(k)) for k in ("pbanc_ctnt", "aply_trgt_ctnt", "aply_excl_trgt_ctnt", "prfn_matr", "support_ctnt", "eval_method")}
        for k, v in T.items():
            if v != r.get(k):
                changed[f"kstartup.{k}"] += 1
        title = re.sub(r"\s+", " ", r["biz_pbanc_nm"]).strip()
        if title != r["biz_pbanc_nm"]:
            changed["kstartup.title"] += 1
        cat = clean_text(r.get("supt_biz_clsfc"))
        if cat != r.get("supt_biz_clsfc"):
            changed["kstartup.supt_biz_clsfc"] += 1
        org = split_org(r.get("pbanc_ntrp_nm"))
        if org["org_flags"]:
            org_review.append({"notice_id": nid, "org_raw": org["org_raw"], "org_names": " | ".join(org["org_names"]), "role_titles": " | ".join(x or "" for x in org["org_role_titles"]), "flags": ",".join(org["org_flags"])})
        start, end = iso_date(r.get("pbanc_rcpt_bgng_dt")), iso_date(r.get("pbanc_rcpt_end_dt"))
        is_open = r.get("rcrt_prgs_yn") == "Y"
        rid = rg.resolve_abbr(r.get("supt_regin"))
        if not rid and r.get("supt_regin"):
            report["kstartup_region_unmapped"] += 1
        am = {k: clean_text(r.get(k)) for k in ("aply_mthd_onli_rcpt_istc", "aply_mthd_eml_rcpt_istc", "aply_mthd_vst_rcpt_istc", "aply_mthd_pssr_rcpt_istc", "aply_mthd_fax_rcpt_istc", "aply_mthd_etc_istc")}
        am = {k: v for k, v in am.items() if v}
        gu = r.get("biz_gdnc_url")
        flags = []
        if gu and re.match(r"https?://https?:?/", gu):
            flags.append("guide_url_malformed")
        n = {"notice_id": nid, "source_system": "KSTARTUP", "source_id": sn, "title": title, "title_raw": r["biz_pbanc_nm"],
             "detail_url": r.get("detl_pg_url"), "published_at": None, "source_updated_at": None,
             "application_start": start, "application_end": end, "deadline_at": f"{end}T23:59:59+09:00" if end else None,
             "apply_status_kind": "DATE_RANGE" if start and end else "UNPARSED", "is_open": is_open,
             "period_status": ("OPEN_WITH_DEADLINE" if is_open else "CLOSED") if end else "NO_DATE",
             **org, "executor_org_name": None, "executor_kind": None, "operating_dept": clean_text(r.get("biz_prch_dprt_nm")),
             "org_kind": r.get("sprv_inst"), "category_major": cat, "category_medium": None,
             "region_raw": r.get("supt_regin"), "region_concept_ids": [rid] if rid else [], "region_basis": "supt_regin" if rid else None,
             "region_scope_hint": None, "region_tags_hint": None,
             "structured": {"business_age_raw": r.get("biz_enyy"), "founder_age_raw": r.get("biz_trgt_age"), "applicant_target_raw": r.get("aply_trgt")},
             "eligibility_text": T["aply_trgt_ctnt"], "exclusion_text": T["aply_excl_trgt_ctnt"], "preferred_text": T["prfn_matr"], "body_text": T["pbanc_ctnt"],
             "support_text": T["support_ctnt"], "evaluation_text": T["eval_method"], "apply_method_text": "\n".join(f"{APPLY_LABELS[k]}: {v}" for k, v in am.items()) or None,
             "apply_methods": am, "apply_url": r.get("biz_aply_url"), "guide_url": gu, "guide_url_flags": flags,
             "contact_phone_raw": r.get("prch_cnpl_no"), "contact_text": None,
             "is_integrated": r.get("intg_pbanc_yn") == "Y", "program_name": clean_text(r.get("intg_pbanc_biz_nm")),
             "attachments": {"count": None, "text_extracted": 0, "note": "API에 첨부 칸이 없고 robots.txt가 첨부 경로를 금지"},
             "fetched_at": TODAY, "version": 1, "is_latest": True, "raw_hash": sha(r), "source_run": kraw.name}
        n["content_hash"] = sha({k: n[k] for k in ("title", "eligibility_text", "body_text", "support_text", "evaluation_text", "apply_method_text", "application_start", "application_end", "category_major")})
        notices.append(n)
        meta = {"is_open": is_open, "region_concept_ids": n["region_concept_ids"]}
        chunks += chunk(nid, "KSTARTUP", "title_body", "API", f"{title}\n{T['pbanc_ctnt'] or ''}", meta)
        for key, sec in (("aply_trgt_ctnt", "eligibility_api"), ("aply_excl_trgt_ctnt", "exclusion_api"), ("prfn_matr", "preferred_api"), ("support_ctnt", "support_details"), ("eval_method", "evaluation")):
            chunks += chunk(nid, "KSTARTUP", sec, "API", T[key], meta)
        chunks += chunk(nid, "KSTARTUP", "apply_method", "API", n["apply_method_text"], meta)
    return notices, chunks, org_review


def related_groups(notices: list[dict]) -> list[dict]:
    """제목이 비슷하고 기관이 같은 공고 묶음 **후보**. SUPERSEDES를 확정하지 않는다."""
    buckets: dict[str, list[dict]] = defaultdict(list)
    for n in notices:
        org = n["org_names"][0] if n["org_names"] else ""
        key = norm_title_key(n["title"])
        if len(key) >= 8 and org:
            buckets[sha(f"{org}|{key}".encode())[:10]].append(n)
    rows = []
    for gid, ns in buckets.items():
        if len(ns) < 2:
            continue
        for n in ns:
            n["related_group_id"] = f"RG:{gid}"
        for n in ns:
            rows.append({"related_group_id": f"RG:{gid}", "notice_id": n["notice_id"], "title": n["title"], "org": n["org_names"][0],
                         "signals": ",".join(signals(n["title"])), "start": n.get("application_start") or ""})
    for n in notices:
        n.setdefault("related_group_id", None)
    return rows


def validate(notices: list[dict], chunks: list[dict], kraw: Path, report: dict) -> dict:
    v = {}
    ids = [n["notice_id"] for n in notices]
    v["notice_count"] = len(ids)
    v["notice_id_duplicates"] = len(ids) - len(set(ids))
    cids = [c["chunk_id"] for c in chunks]
    v["chunk_count"] = len(cids)
    v["chunk_id_duplicates"] = len(cids) - len(set(cids))
    idset = set(ids)
    v["chunks_without_notice"] = sum(1 for c in chunks if c["notice_id"] not in idset)
    v["chunks_shorter_than_min"] = sum(1 for c in chunks if len(c["text"]) < MIN_CHUNK)
    txt_fields = ("title", "eligibility_text", "exclusion_text", "preferred_text", "body_text", "support_text", "evaluation_text", "apply_method_text", "contact_text")
    v["texts_with_CR"] = sum(1 for n in notices for f in txt_fields if n.get(f) and "\r" in n[f])
    v["texts_with_html_entity"] = sum(1 for n in notices for f in txt_fields if n.get(f) and ENTITY.search(n[f]))
    v["texts_with_REDACTED"] = sum(1 for n in notices for f in txt_fields if n.get(f) and REDACT.search(n[f])) + sum(1 for c in chunks if REDACT.search(c["text"]))
    # 원본 충실도: 공백·엔티티 차이를 무시하면 원본과 같아야 한다
    allr = {str(json.loads(l)["pbanc_sn"]): json.loads(l) for l in (kraw / "announcements_all.jsonl").read_text(encoding="utf-8").split("\n") if l.strip()}
    mapping = {"eligibility_text": "aply_trgt_ctnt", "body_text": "pbanc_ctnt", "support_text": "support_ctnt", "evaluation_text": "eval_method", "preferred_text": "prfn_matr", "exclusion_text": "aply_excl_trgt_ctnt"}
    fid_bad = fid_all = 0
    for n in notices:
        if n["source_system"] != "KSTARTUP":
            continue
        raw = allr[n["source_id"]]
        for f, rf in mapping.items():
            fid_all += 1
            if norm_for_fidelity(n.get(f)) != norm_for_fidelity(raw.get(rf)):
                fid_bad += 1
        fid_all += 2
        fid_bad += (n["detail_url"] != raw.get("detl_pg_url")) + (n["guide_url"] != raw.get("biz_gdnc_url"))
    v["kstartup_fidelity_fields_checked"] = fid_all
    v["kstartup_fidelity_mismatch"] = fid_bad
    v["notices_by_source"] = dict(Counter(n["source_system"] for n in notices))
    v["open_by_source"] = dict(Counter(n["source_system"] for n in notices if n["is_open"]))
    v["start_after_end"] = sum(1 for n in notices if n["application_start"] and n["application_end"] and n["application_start"] > n["application_end"])
    v["open_but_deadline_passed"] = sum(1 for n in notices if n["is_open"] and n["application_end"] and n["application_end"] < TODAY)
    v["chunks_by_source_section"] = {f"{k[0]}:{k[1]}": c for k, c in sorted(Counter((c["source_system"], c["section"]) for c in chunks).items())}
    sz = sorted(len(c["text"]) for c in chunks)
    v["chunk_len_min_median_p95_max"] = [sz[0], sz[len(sz) // 2], sz[int(len(sz) * .95)], sz[-1]]
    return v


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--kstartup-raw", default=str(REPO / "data/kstartup/raw/20261124_full"))
    args = ap.parse_args()
    kraw = Path(args.kstartup_raw)
    rg = RegionGraph()
    report, changed = Counter(), Counter()
    bn, bc = clean_bizinfo(rg, report, changed)
    kn, kc, org_review = clean_kstartup(rg, kraw, report, changed)
    notices, chunks = bn + kn, bc + kc
    rel = related_groups(notices)
    out = REPO / "data" / "cleaned" / TODAY.replace("-", "")
    out.mkdir(parents=True, exist_ok=True)
    for name, rows in (("notices.jsonl", notices), ("chunks.jsonl", chunks)):
        (out / name).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    for name, rows in (("org_split_review.csv", org_review), ("related_groups.csv", rel)):
        with open(out / name, "w", encoding="utf-8-sig", newline="") as f:
            if rows:
                w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    (REPO / "data" / "cleaned" / "LATEST").write_text(out.name, encoding="utf-8")
    rep = {"cleaned_at": datetime.now().isoformat(timespec="seconds"), "inputs": {"bizinfo_run": (BIZ / "raw" / "LATEST").read_text().strip(), "kstartup_raw": kraw.name},
           "counts": dict(report), "fields_changed_by_cleaning": dict(sorted(changed.items())),
           "org_split": {"kstartup_with_flags": len(org_review), "title_split": sum(1 for r in org_review if "title_split" in r["flags"]), "multiple_orgs": sum(1 for r in org_review if "multiple_orgs" in r["flags"])},
           "related_group_candidates": {"groups": len({r["related_group_id"] for r in rel}), "notices": len(rel), "with_extension_or_regong_signal": sum(1 for r in rel if r["signals"])},
           "guide_url_malformed": sum(1 for n in kn if n["guide_url_flags"]),
           "validation": validate(notices, chunks, kraw, report)}
    (out / "cleaning_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
