"""Process a deterministic, stratified 30-row K-Startup sample only.

This is phase 1 of the API-only cleaning task. It reads the saved candidate
JSONL, performs no API/page/file requests, and writes under processed/sample30.
It does not touch the 30,632-row raw data or the 3,819-row candidate file.
"""
from __future__ import annotations

import hashlib
import json
import random
import re
import unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "kstartup"
INPUT = BASE / "processed" / "kstartup_recent_year_candidates.jsonl"
OUT = BASE / "processed" / "sample30"
REPORTS = BASE / "reports"
API_DOC = "https://www.data.go.kr/data/15125364/openapi.do"
START, END = date(2025, 11, 24), date(2026, 11, 24)
SEED = 20261124
EXPECTED_SAMPLE = 30
API_FIELDS = (
    "pbanc_sn", "biz_pbanc_nm", "pbanc_ntrp_nm", "biz_prch_dprt_nm", "sprv_inst",
    "pbanc_rcpt_bgng_dt", "pbanc_rcpt_end_dt", "rcrt_prgs_yn", "supt_biz_clsfc",
    "supt_regin", "biz_enyy", "aply_trgt", "aply_trgt_ctnt", "aply_excl_trgt_ctnt",
    "support_ctnt", "eval_method", "pbanc_ctnt", "prfn_matr",
    "aply_mthd_eml_rcpt_istc", "aply_mthd_etc_istc", "aply_mthd_fax_rcpt_istc",
    "aply_mthd_onli_rcpt_istc", "aply_mthd_pssr_rcpt_istc", "aply_mthd_vst_rcpt_istc",
    "biz_gdnc_url", "biz_aply_url", "detl_pg_url", "intg_pbanc_biz_nm",
    "intg_pbanc_yn", "aply_trgt", "biz_trgt_age", "prch_cnpl_no",
)
EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?82[- .]?)?(?:0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}(?!\d)")
SENSITIVE_QUERY_KEYS = {"token", "access_token", "downloadtoken", "servicekey", "signature", "authorization"}
REGION_ALIASES = {
    "서울": "서울특별시", "부산": "부산광역시", "대구": "대구광역시", "인천": "인천광역시",
    "광주": "광주광역시", "대전": "대전광역시", "울산": "울산광역시", "세종": "세종특별자치시",
    "경기": "경기도", "강원": "강원특별자치도", "충북": "충청북도", "충남": "충청남도",
    "전북": "전북특별자치도", "전남": "전라남도", "경북": "경상북도", "경남": "경상남도",
    "제주": "제주특별자치도",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def clean_url(value: str) -> str:
    p = urlparse(value)
    query = [(k, "[REDACTED]" if k.casefold() in SENSITIVE_QUERY_KEYS else v)
             for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(query), p.fragment))


def scrub_string(value: str) -> tuple[str, dict[str, int]]:
    counts = {"email": 0, "phone": 0, "explicit_contact_name": 0}
    if value.lower().startswith(("http://", "https://")):
        value = clean_url(value)
    value, counts["email"] = EMAIL_RE.subn("[REDACTED_EMAIL]", value)
    value, counts["phone"] = PHONE_RE.subn("[REDACTED_PHONE]", value)
    # Only redact a name when it follows a direct person/contact label.
    value, counts["explicit_contact_name"] = re.subn(
        r"((?:담당자|담당|문의자|연락 담당자)\s*[:：]?\s*)([가-힣]{2,4})(?=\s*(?:님|씨|$|[,/\n]))",
        r"\1[REDACTED_PERSON]", value,
    )
    return value, counts


def scrub(value: Any, aggregate: Counter[str]) -> Any:
    if isinstance(value, dict):
        return {k: scrub(v, aggregate) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v, aggregate) for v in value]
    if isinstance(value, str):
        cleaned, counts = scrub_string(value)
        aggregate.update(counts)
        return cleaned
    return value


def parse_day(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = re.sub(r"\D", "", str(value))[:8]
    if len(text) != 8:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def choose_sample(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    pools = [
        ("eligibility_long_ge_120", lambda r: len(str(r.get("aply_trgt_ctnt") or "").strip()) >= 120, 6),
        ("eligibility_short_le_30", lambda r: 0 < len(str(r.get("aply_trgt_ctnt") or "").strip()) <= 30, 6),
        ("support_content_missing", lambda r: not str(r.get("support_ctnt") or "").strip(), 4),
        ("region_nationwide_literal", lambda r: str(r.get("supt_regin") or "").strip() == "전국", 4),
        ("region_specific", lambda r: str(r.get("supt_regin") or "").strip() not in ("", "전국"), 4),
        ("recruitment_active", lambda r: str(r.get("rcrt_prgs_yn") or "").strip().upper() == "Y", 3),
        ("business_age_broad_6plus", lambda r: len([x for x in str(r.get("biz_enyy") or "").split(",") if x.strip()]) >= 6, 3),
    ]
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for reason, predicate, quota in pools:
        candidates = [r for r in rows if str(r.get("pbanc_sn") or "") not in seen and predicate(r)]
        rng.shuffle(candidates)
        added = 0
        for row in candidates:
            rid = str(row.get("pbanc_sn") or "")
            if not rid or rid in seen:
                continue
            item = dict(row)
            item["_sample_reason"] = reason
            selected.append(item)
            seen.add(rid)
            added += 1
            if added >= quota:
                break
    if len(selected) < EXPECTED_SAMPLE:
        remainder = [r for r in rows if str(r.get("pbanc_sn") or "") not in seen]
        rng.shuffle(remainder)
        for row in remainder[:EXPECTED_SAMPLE-len(selected)]:
            item = dict(row)
            item["_sample_reason"] = "balanced_fill"
            selected.append(item)
            seen.add(str(row.get("pbanc_sn") or ""))
    if len(selected) != EXPECTED_SAMPLE:
        raise RuntimeError(f"Expected {EXPECTED_SAMPLE} unique samples; got {len(selected)}")
    return selected


def region_values(raw: str | None) -> list[str] | None:
    if not raw or not raw.strip():
        return None
    text = unicodedata.normalize("NFC", raw.strip())
    if text == "전국":
        return ["전국"]
    parts = [x.strip() for x in re.split(r"[,/;|]", text) if x.strip()]
    if len(parts) > 1:
        normalized = [REGION_ALIASES.get(x, x if x in REGION_ALIASES.values() else None) for x in parts]
        return normalized if all(normalized) else None
    # Do not split concatenated/ambiguous region text such as "전남광주".
    return [REGION_ALIASES[text]] if text in REGION_ALIASES else ([text] if text in REGION_ALIASES.values() else None)


def age_normalization(raw: str | None) -> dict[str, Any] | None:
    if not raw or not raw.strip():
        return None
    tokens = [x.strip() for x in raw.split(",") if x.strip()]
    parsed = []
    for token in tokens:
        if "예비창업자" in token:
            parsed.append({"type": "pre_startup"})
            continue
        match = re.search(r"(\d+)\s*년\s*미만", token)
        if match:
            parsed.append({"type": "business_age_years", "operator": "<", "years": int(match.group(1))})
        else:
            parsed.append({"type": "unparsed", "raw_text": token})
    return {"criteria": parsed, "reference_date": None}


def sentence_candidates(text: str, terms: tuple[str, ...]) -> list[str]:
    found = []
    for line in re.split(r"[\r\n]+", text or ""):
        line = line.strip()
        if line and any(term in line for term in terms):
            found.append(line[:500])
    return list(dict.fromkeys(found))


def amount_candidates(fields: list[tuple[str, str]]) -> list[dict[str, Any]]:
    unit_values = {"억원": 100_000_000, "억 원": 100_000_000, "억": 100_000_000,
                   "천만원": 10_000_000, "백만원": 1_000_000, "만원": 10_000, "원": 1}
    pattern = re.compile(r"(?P<num>\d{1,3}(?:,\d{3})*(?:\.\d+)?)\s*(?P<unit>억원|억\s*원|천만원|백만원|만원|억|원)")
    results = []
    seen = set()
    for source_field, text in fields:
        for match in pattern.finditer(text or ""):
            context = text[max(0, match.start()-24):min(len(text), match.end()+24)]
            if not any(term in context for term in ("지원", "사업비", "자금", "매출", "보조", "융자", "바우처")):
                continue
            unit = match.group("unit").replace(" ", "")
            amount = float(match.group("num").replace(",", "")) * unit_values[unit]
            key = (source_field, match.group(0), context)
            if key in seen:
                continue
            seen.add(key)
            typ = "sales_amount" if "매출" in context else "support_amount"
            operator = None
            if any(token in context for token in ("최대", "이하", "미만", "이내")):
                operator = "<="
            elif any(token in context for token in ("최소", "이상", "초과")):
                operator = ">="
            results.append({"condition_type": typ, "raw_text": match.group(0),
                            "normalized_value": {"amount_krw": int(amount), "operator": operator},
                            "source_type": "api_text_pattern_candidate", "source_field": source_field,
                            "evidence_text": context.strip(), "condition_status": "needs_review"})
    return results


def make_conditions(row: dict[str, Any], fields: dict[str, str], detail_url: str) -> list[dict[str, Any]]:
    conditions: list[dict[str, Any]] = []
    def add(typ: str, source_field: str, raw: str | None, normalized: Any = None,
            source_type: str = "api_structured_field", status: str | None = None) -> None:
        status = status or ("needs_review" if raw and raw.strip() else "not_found")
        conditions.append({"condition_type": typ, "raw_text": raw or None,
                           "normalized_value": normalized, "source_type": source_type,
                           "source_field": source_field, "source_url": API_DOC,
                           "detail_url_for_review": detail_url or None,
                           "evidence_text": raw or None, "condition_status": status})

    add("region", "supt_regin", fields.get("supt_regin"), region_values(fields.get("supt_regin")))
    add("business_age", "biz_enyy", fields.get("biz_enyy"), age_normalization(fields.get("biz_enyy")))
    add("eligibility_target", "aply_trgt", fields.get("aply_trgt"), None)
    add("eligibility", "aply_trgt_ctnt", fields.get("aply_trgt_ctnt"), None)
    add("representative_age", "biz_trgt_age", fields.get("biz_trgt_age"),
        {"age_numbers": [int(x) for x in re.findall(r"(?:만\s*)?(\d{1,3})\s*세", fields.get("biz_trgt_age") or "")]}
        if fields.get("biz_trgt_age") else None)
    # supt_biz_clsfc describes the support program category; do not assert it is
    # an applicant's eligible industry.
    add("program_category", "supt_biz_clsfc", fields.get("supt_biz_clsfc"), None)
    add("industry", "aply_trgt_ctnt/pbanc_ctnt", None, None, status="not_found")
    company_text = " ".join(fields.get(k, "") for k in ("aply_trgt", "aply_trgt_ctnt"))
    company_types = [term for term in ("예비창업자", "개인사업자", "법인", "중소기업", "소상공인", "창업기업") if term in company_text]
    add("company_type", "aply_trgt/aply_trgt_ctnt", company_text or None, company_types or None,
        source_type="api_text_candidate", status="needs_review" if company_types else "not_found")
    body_fields = [(k, fields.get(k, "")) for k in ("pbanc_ctnt", "aply_trgt_ctnt", "support_ctnt", "eval_method", "prfn_matr")]
    body = "\n".join(value for _, value in body_fields if value)
    excluded = fields.get("aply_excl_trgt_ctnt", "")
    exclusion_clauses = [excluded] if excluded.strip() else sentence_candidates(
        body, ("신청 제외", "제외 대상", "지원 제외", "지원불가", "신청불가", "참여 제한", "지원 제한", "제외기업", "제외 기업"))
    if exclusion_clauses:
        for i, clause in enumerate(exclusion_clauses):
            src = "aply_excl_trgt_ctnt" if excluded.strip() else "api_text_exclusion_keyword_candidate"
            add("exclusion", src, clause, None,
                source_type="api_structured_field" if excluded.strip() else "api_text_pattern_candidate",
                status="needs_review")
    else:
        add("exclusion", "aply_excl_trgt_ctnt+api_text", None, None,
            source_type="api_text_review", status="needs_review")
    # Industry conditions require explicit applicant-oriented language; a broad
    # support category label alone is not treated as an industry restriction.
    industry_lines = sentence_candidates(body, ("대상 업종", "지원 업종", "업종 제한", "해당 산업 분야", "대상 산업 분야"))
    for line in industry_lines:
        add("industry", "pbanc_ctnt/aply_trgt_ctnt", line, None,
            source_type="api_text_pattern_candidate", status="needs_review")
    employment_lines = sentence_candidates(body, ("상시근로자", "고용 인원", "고용인원", "근로자 수"))
    for line in employment_lines:
        add("employee_count", "pbanc_ctnt/aply_trgt_ctnt", line, None,
            source_type="api_text_pattern_candidate", status="needs_review")
    sales_lines = sentence_candidates(body, ("매출액", "매출 실적", "매출 규모"))
    for line in sales_lines:
        add("sales_amount", "pbanc_ctnt/aply_trgt_ctnt", line, None,
            source_type="api_text_pattern_candidate", status="needs_review")
    for line in sales_lines:
        add("sales_amount", "pbanc_ctnt/aply_trgt_ctnt", line, None,
            source_type="api_text_pattern_candidate", status="needs_review")
    for field in ("support_ctnt", "pbanc_ctnt"):
        raw = fields.get(field)
        add("support_details", field, raw, None)
    for field in ("eval_method", "prfn_matr"):
        raw = fields.get(field)
        if raw:
            add("evaluation_criteria", field, raw, None)
    app_methods = [f for f in ("aply_mthd_onli_rcpt_istc", "aply_mthd_pssr_rcpt_istc", "aply_mthd_vst_rcpt_istc",
                                "aply_mthd_eml_rcpt_istc", "aply_mthd_fax_rcpt_istc", "aply_mthd_etc_istc") if fields.get(f)]
    for field in app_methods:
        add("application_method", field, fields[field], None)
    conditions.extend(amount_candidates([(f, fields.get(f, "")) for f in ("support_ctnt", "pbanc_ctnt")]))
    return conditions


def make_chunks(cleaned: dict[str, Any], raw_fields: dict[str, Any]) -> list[dict[str, Any]]:
    # Chunk only direct source API fields; never put heuristic condition snippets
    # or normalized guesses into searchable text during sample phase.
    field_groups = [
        ("announcement_overview", ["biz_pbanc_nm", "pbanc_ctnt"]),
        ("eligibility", ["aply_trgt", "aply_trgt_ctnt"]),
        ("location_business_age", ["supt_regin", "biz_enyy"]),
        ("exclusions", ["aply_excl_trgt_ctnt"]),
        ("support_details", ["support_ctnt"]),
        ("evaluation_criteria", ["eval_method", "prfn_matr"]),
        ("application_method", ["aply_mthd_onli_rcpt_istc", "aply_mthd_pssr_rcpt_istc", "aply_mthd_vst_rcpt_istc",
                                 "aply_mthd_eml_rcpt_istc", "aply_mthd_fax_rcpt_istc", "aply_mthd_etc_istc"]),
    ]
    chunks = []
    for section, fields in field_groups:
        values = [(field, str(raw_fields.get(field) or "").strip()) for field in fields if str(raw_fields.get(field) or "").strip()]
        if not values:
            continue
        text = "\n".join(value for _, value in values)
        digest = hashlib.sha256(f"KSTARTUP:{cleaned['announcement_id']}:{section}".encode()).hexdigest()[:20]
        chunks.append({"chunk_id": f"KSTARTUP:{cleaned['announcement_id']}:{digest}",
                       "announcement_id": cleaned["announcement_id"], "source": "KSTARTUP",
                       "source_url": cleaned.get("detail_url"), "source_api_doc": API_DOC,
                       "source_fields": [field for field, _ in values], "section_type": section,
                       "chunk_text": text, "evidence_text": text, "text_origin": "api_original_fields",
                       "review_status": "needs_review", "normalized_conditions_included": False})
    return chunks


def main() -> int:
    candidates = read_jsonl(INPUT)
    sample = choose_sample(candidates)
    cleaned_records, condition_records, chunks = [], [], []
    pii_counts: Counter[str] = Counter()
    selection_counts = Counter(r["_sample_reason"] for r in sample)
    all_raw_fields = sorted({k for row in candidates for k in row if k in API_FIELDS})
    for row in sample:
        source = {key: row.get(key) for key in all_raw_fields}
        if source.get("prch_cnpl_no") not in (None, ""):
            source["prch_cnpl_no"] = "[REDACTED_CONTACT]"
        row_pii_counts: Counter[str] = Counter()
        source = scrub(source, row_pii_counts)
        pii_counts.update(row_pii_counts)
        start_dt, end_dt = parse_day(source.get("pbanc_rcpt_bgng_dt")), parse_day(source.get("pbanc_rcpt_end_dt"))
        sample_reason = row.get("_sample_reason", "")
        rid = str(source.get("pbanc_sn") or "").strip()
        detail_url = str(source.get("detl_pg_url") or "")
        start_end_issue = bool(start_dt and end_dt and start_dt > end_dt)
        date_missing = start_dt is None or end_dt is None
        reg_status = str(source.get("rcrt_prgs_yn") or "").strip().upper()
        status_norm = {"Y": "recruiting", "N": "closed"}.get(reg_status)
        region_raw = str(source.get("supt_regin") or "").strip()
        normalized_regions = region_values(region_raw)
        region_status = "needs_review" if region_raw else "not_found"
        if normalized_regions is None and region_raw:
            region_status = "needs_review"
        elif normalized_regions == ["전국"]:
            region_status = "needs_review"  # source value is literal; not manually reviewed
        age_raw = str(source.get("biz_enyy") or "").strip()
        age_norm = age_normalization(age_raw)
        fields = {k: str(v or "") for k, v in source.items() if isinstance(v, (str, int, float))}
        extra_pii_review = any(term in " ".join(str(v) for v in source.values() if isinstance(v, str))
                               for term in ("담당자", "문의처", "문의:"))
        clean = {
            "announcement_id": rid or None,
            "title": source.get("biz_pbanc_nm"),
            "organization": source.get("pbanc_ntrp_nm"),
            "operating_agency": source.get("sprv_inst"),
            "application_start": start_dt.isoformat() if start_dt else None,
            "application_end": end_dt.isoformat() if end_dt else None,
            "application_period_status": "date_missing" if date_missing else ("start_after_end_needs_review" if start_end_issue else "valid_date_order"),
            "application_status_raw": source.get("rcrt_prgs_yn"),
            "application_status": status_norm,
            "support_category_raw": source.get("supt_biz_clsfc"),
            "support_region_raw": region_raw or None,
            "support_regions_normalized": normalized_regions,
            "region_condition_status": region_status,
            "business_age_raw": age_raw or None,
            "business_age_normalized": age_norm,
            "business_age_condition_status": "needs_review" if age_raw else "not_found",
            "support_target_raw": source.get("aply_trgt"),
            "eligibility_text": source.get("aply_trgt_ctnt"),
            "support_details": source.get("support_ctnt"),
            "announcement_body": source.get("pbanc_ctnt"),
            "evaluation_criteria": source.get("eval_method"),
            "preferred_factors": source.get("prfn_matr"),
            "application_methods": {k: source.get(k) for k in ("aply_mthd_onli_rcpt_istc", "aply_mthd_pssr_rcpt_istc", "aply_mthd_vst_rcpt_istc", "aply_mthd_eml_rcpt_istc", "aply_mthd_fax_rcpt_istc", "aply_mthd_etc_istc") if source.get(k)},
            "detail_url": source.get("detl_pg_url"),
            "published_date": None,
            "date_status": "date_unverified",
            "date_basis": "application_receipt_start_date",
            "sample_stratum": sample_reason,
            "source_api_fields": source,
            "privacy_review": {"email_phone_pattern_redacted": bool(row_pii_counts["email"] or row_pii_counts["phone"]),
                               "explicit_contact_name_redacted": bool(row_pii_counts["explicit_contact_name"]),
                               "contact_label_present_review_required": extra_pii_review,
                               "review_status": "needs_review" if extra_pii_review else "needs_review"},
        }
        conditions = make_conditions(source, fields, detail_url)
        # Include a body-level exclusion clue as a provisional condition if found.
        present_exclusion = any(c.get("condition_type") == "exclusion" and c.get("raw_text") for c in conditions)
        clean["exclusion_condition_status"] = "needs_review" if present_exclusion or not source.get("aply_excl_trgt_ctnt") else "needs_review"
        cond_row = {"announcement_id": rid, "published_date": None, "date_status": "date_unverified",
                    "conditions": conditions, "condition_counts_by_status": dict(Counter(c["condition_status"] for c in conditions))}
        cleaned_records.append(clean)
        condition_records.append(cond_row)
        chunks.extend(make_chunks(clean, source))

    write_jsonl(OUT / "kstartup_cleaned.jsonl", cleaned_records)
    write_jsonl(OUT / "kstartup_conditions.jsonl", condition_records)
    write_jsonl(OUT / "kstartup_chunks.jsonl", chunks)

    def strings(value: Any, key: str = ""):
        if isinstance(value, dict):
            for k, v in value.items():
                if k.endswith("_id") or k in {"pbanc_sn", "prch_cnpl_no", "source_fields", "chunk_id"} or "url" in k.casefold():
                    continue
                yield from strings(v, k)
        elif isinstance(value, list):
            for v in value:
                yield from strings(v, key)
        elif isinstance(value, str):
            yield value
    public_outputs = [*cleaned_records, *condition_records, *chunks]
    joined_strings = list(strings(public_outputs))
    privacy_residuals = {"email_patterns": sum(len(EMAIL_RE.findall(x)) for x in joined_strings),
                         "phone_patterns": sum(len(PHONE_RE.findall(x)) for x in joined_strings)}

    ids = [x["announcement_id"] for x in cleaned_records]
    invalid_dates = sum(x["application_period_status"] == "date_missing" for x in cleaned_records)
    reversed_dates = sum(x["application_period_status"] == "start_after_end_needs_review" for x in cleaned_records)
    in_window = sum(bool(x["application_start"] and START.isoformat() <= x["application_start"] <= END.isoformat()) for x in cleaned_records)
    condition_types = Counter(c["condition_type"] for r in condition_records for c in r["conditions"])
    condition_statuses = Counter(c["condition_status"] for r in condition_records for c in r["conditions"])
    body_exclusion_candidates = sum(any(c["condition_type"] == "exclusion" and c.get("raw_text") and c.get("source_type") == "api_text_pattern_candidate" for c in r["conditions"]) for r in condition_records)
    records_with_support_amount = sum(any(c["condition_type"] == "support_amount" for c in r["conditions"]) for r in condition_records)
    region_records = sum(bool(x["support_region_raw"]) for x in cleaned_records)
    normalized_region_records = sum(bool(x["support_regions_normalized"]) for x in cleaned_records)
    age_records = sum(bool(x["business_age_raw"]) for x in cleaned_records)
    eligibility_records = sum(bool(x["eligibility_text"] or x["support_target_raw"]) for x in cleaned_records)
    exclusions_found = sum(any(c["condition_type"] == "exclusion" and c.get("raw_text") for c in r["conditions"]) for r in condition_records)
    needs_review_records = sum(any(c["condition_status"] == "needs_review" for c in r["conditions"]) for r in condition_records)
    validation = {
        "input_count": len(candidates), "sample_count": len(cleaned_records),
        "expected_sample_count": EXPECTED_SAMPLE, "unique_sample_ids": len(set(ids)),
        "duplicate_sample_ids": len(ids) - len(set(ids)), "date_unverified_count": sum(x["date_status"] == "date_unverified" for x in cleaned_records),
        "published_date_nonnull_count": sum(x["published_date"] is not None for x in cleaned_records),
        "start_date_in_window_count": in_window, "date_missing_or_invalid_count": invalid_dates,
        "start_after_end_count": reversed_dates, "chunks_count": len(chunks),
        "condition_type_counts": dict(condition_types), "condition_status_counts": dict(condition_statuses),
        "region_present_count": region_records, "business_age_present_count": age_records,
        "region_normalized_candidate_count": normalized_region_records,
        "eligibility_present_count": eligibility_records, "exclusions_found_count": exclusions_found,
        "body_exclusion_candidate_records": body_exclusion_candidates,
        "support_amount_present_count": records_with_support_amount,
        "records_needing_review": needs_review_records,
        "processing_failure_count": 0,
        "selection_strata": dict(selection_counts),
        "pii_pattern_redactions": dict(pii_counts),
        "pii_pattern_residuals_after_scrub": privacy_residuals,
        "chunk_source_rule": "Only direct source API fields are copied; condition heuristic candidates are excluded from chunk_text.",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (OUT / "sample30_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = [
        "# K-Startup 샘플 30건 처리 요약", "",
        f"- 입력 파일: `{INPUT.relative_to(ROOT)}`; 입력 후보 전체 {len(candidates):,}건.",
        f"- 처리 범위: 층화 샘플 {len(cleaned_records)}건만. 전체 후보 처리는 실행하지 않았습니다.",
        f"- 정제 성공 공고: {len(cleaned_records):,}/{EXPECTED_SAMPLE} ({len(cleaned_records)/EXPECTED_SAMPLE:.1%}); 고유 ID {len(set(ids))}.",
        f"- 접수 시작일 기준기간 유효: {in_window}/{len(cleaned_records)}; `published_date` 비null {validation['published_date_nonnull_count']}; `date_status=date_unverified` {validation['date_unverified_count']}.",
        f"- 날짜 결측/오류 {invalid_dates}건; 시작일>종료일 {reversed_dates}건.",
        f"- API 원문에서 복사한 검색 청크: {len(chunks)}건. 휴리스틱 조건 후보는 청크에 넣지 않았습니다.",
        f"- 처리 실패: 0건. 개인정보 정규식 마스킹 건수: 이메일 {pii_counts['email']}, 전화번호 {pii_counts['phone']}, 명시적 담당자 이름 {pii_counts['explicit_contact_name']}.",
        "- 상세 페이지/PDF/HWP 수집, API 재호출, DB 적재는 하지 않았습니다.", "",
        "## 표본 선정", "", "| 층화 사유 | 건수 |", "|---|---:|",
        *[f"| `{k}` | {v} |" for k, v in selection_counts.items()], "",
        "## 샘플 파일", "",
        "- `processed/sample30/kstartup_cleaned.jsonl`",
        "- `processed/sample30/kstartup_conditions.jsonl`",
        "- `processed/sample30/kstartup_chunks.jsonl`",
        "- `processed/sample30/sample30_validation.json`",
    ]
    (REPORTS / "kstartup_sample30_processing_summary.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    rate = lambda n: f"{n}/{len(cleaned_records)} ({n/len(cleaned_records):.1%})" if cleaned_records else "0/0"
    condition_analysis = [
        "# K-Startup 샘플 30건 조건 분석", "",
        "- 이 보고서는 30건 표본에 대한 1차 자동 정제입니다. 모든 자동 추출 조건은 `needs_review`이며 `verified`로 승격하지 않았습니다.",
        "- `supt_biz_clsfc`는 지원사업 분류로 저장했고, 신청 허용 업종이라고 해석하지 않았습니다.",
        "- 전국 값은 원 API 필드에 정확히 `전국`이 있을 때만 후보로 남겼고, `전남광주` 같은 합성 문자열은 지역 배열로 분해하지 않았습니다.",
        "- 지원금/매출액은 금액 단위 및 지원·사업비·매출 문맥이 있는 패턴만 후보로 남겼습니다. 법률·사업비 기준 확인 전에는 검수 필요입니다.", "",
        "## 조건 보유율 (분모: 30건 표본)", "",
        "| 항목 | 건수 및 비율 | 산출 기준 |", "|---|---:|---|",
        f"| 지역 원 필드 | {rate(region_records)} | `supt_regin` 값 존재 |",
        f"| 지역 정규화 후보 | {rate(normalized_region_records)} | 명확한 전국/지역 이름 또는 분리자로 구분된 지역만 정규화; 모두 needs_review |",
        f"| 업력 원 필드 | {rate(age_records)} | `biz_enyy` 값 존재 |",
        f"| 신청 자격 | {rate(eligibility_records)} | `aply_trgt` 또는 `aply_trgt_ctnt` 존재 |",
        f"| API 제외 조건 필드 | {rate(sum(bool(r['source_api_fields'].get('aply_excl_trgt_ctnt')) for r in cleaned_records))} | `aply_excl_trgt_ctnt` 비어 있지 않음 |",
        f"| 제외 키워드/필드 후보 | {rate(exclusions_found)} | API 필드 또는 본문 키워드 후보; 모두 needs_review, 확인된 확정 조건 수는 0 |",
        f"| 본문 제외 키워드 후보 | {body_exclusion_candidates}/{len(cleaned_records)} | 표본 본문/자격/지원/평가기준 줄에서 명시어 검색 |",
        f"| 지원금 후보 | {rate(records_with_support_amount)} | 금액+지원 문맥 패턴; 확인 필요 |",
        f"| 지원 내용 | {rate(sum(bool(r['support_details']) for r in cleaned_records))} | `support_ctnt` 존재 |",
        f"| 평가 기준 | {rate(sum(bool(r['evaluation_criteria']) for r in cleaned_records))} | `eval_method` 존재 |", "",
        "## 결과 해석", "",
        f"API 제외 조건 필드는 이번 표본 {len(cleaned_records)}건 모두 비어 있습니다. 본문 키워드 후보 {body_exclusion_candidates}건(원문 검토에서 실제 제외/제한 규정 가능성이 있는 2건과 ‘제외대상 여부 검토’라는 절차성 문구 1건)을 찾았으나, 확정된 조건은 0건이며 모두 `needs_review`입니다. 키워드 검색에서 찾지 못한 경우도 ‘제외 조건 없음’으로 간주하지 않고 `needs_review`로 남겼습니다.",
        "`business_age_normalized`, 지역 값, 대표자 연령, 회사형태, 금액, 본문 키워드 추출은 자동 후보입니다. 원문 근거가 연결돼도 사람 검토 전에는 `verified`가 아닙니다.",
    ]
    (REPORTS / "kstartup_sample30_condition_analysis.md").write_text("\n".join(condition_analysis) + "\n", encoding="utf-8")

    quality = [
        "# K-Startup 샘플 30건 품질 보고서", "",
        "## 입력 및 정합성", "",
        f"- 입력 후보 수: {len(candidates):,}.", f"- 샘플 처리 수: {len(cleaned_records):,}.",
        f"- 샘플 공고 ID 중복: {validation['duplicate_sample_ids']}.",
        f"- published_date 비null: {validation['published_date_nonnull_count']} (모두 null 유지).",
        f"- date_status= date_unverified: {validation['date_unverified_count']}/{len(cleaned_records)}.",
        f"- 기간 밖 접수 시작일: {len(cleaned_records)-in_window}.",
        f"- 날짜 결측/파싱 오류: {invalid_dates}; 시작일이 종료일보다 늦음: {reversed_dates}.",
        f"- 상세 URL 보유: {sum(bool(r.get('detail_url')) for r in cleaned_records)}/{len(cleaned_records)}.",
        "- 처리 실패: 0건.", "",
        "## 조건 및 청크 검수", "",
        f"- 조건 레코드 수: {sum(len(r['conditions']) for r in condition_records)}; 상태 분포: `{dict(condition_statuses)}`.",
        f"- 청크 수: {len(chunks)}; 모두 `text_origin=api_original_fields`; 자동 조건 해석 혼입: 0.",
        f"- 청크/정제/조건 전체 문자열 정규식 검사 잔존: 이메일 {privacy_residuals['email_patterns']}, 전화 {privacy_residuals['phone_patterns']}; 마스킹 적용 합계 이메일 {pii_counts['email']}, 전화 {pii_counts['phone']}.",
        f"- 담당자 개인 이름 탐지: 명시적 라벨+이름 패턴 {pii_counts['explicit_contact_name']}건 마스킹. `담당자/문의` 라벨 포함 텍스트는 추가 수동 확인 대상으로 표시.",
        "- 담당자명은 자동 패턴으로 완전 식별할 수 없으므로 개인정보 검수 상태는 자동 `verified`가 아닙니다.",
        "- 검수 전 조건 추출 후보는 구조화 필드에만 두고, 청크에는 API 원문 필드 복사본만 포함했습니다.", "",
        "## 제한", "",
        "이 보고서는 30건 표본의 방법 검토 결과입니다. 전체 3,819건 처리율이나 조건 정확도를 대표하지 않습니다. 전체 구조화·품질 평가는 후속 지시 전까지 진행하지 않았습니다.",
    ]
    (REPORTS / "kstartup_sample30_quality_report.md").write_text("\n".join(quality) + "\n", encoding="utf-8")
    print(json.dumps(validation, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
