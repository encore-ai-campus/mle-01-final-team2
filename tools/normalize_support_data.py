#!/usr/bin/env python3
"""Normalize cleaned support notices and chunks to the source-neutral v1 schema.

Reads data/cleaned/<snapshot>/ and writes data/normalized/v1/<snapshot>/.
It never edits the input snapshot or database loader files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from functools import lru_cache
from jsonschema import Draft202012Validator, FormatChecker
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    from tools.public_notice_pipeline import PrivacyReport, sanitize_tree
except ImportError:  # Running as `python tools/normalize_support_data.py`.
    from public_notice_pipeline import PrivacyReport, sanitize_tree

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SNAPSHOT = "20261124"
NORMALIZER_VERSION = "1.0"
OUTPUT_BASE = ROOT / "data" / "normalized" / "v1"

PII_EMAIL = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PII_PHONE = re.compile(r"(?<!\d)(?:\+?82[- .]?)?(?:0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}(?!\d)")
TOKEN_QUERY = re.compile(r"(?i)[?&](?:token|access_token|downloadtoken|servicekey|signature|authorization|api_key|apikey|client_secret)=([^&#\s]+)")
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
URL_END_PUNCTUATION = ".,;:!?)]}"
CONTACT_NAME_RE = re.compile(r"(?P<label>\uBB38\uC758\s*\uB2F4\uB2F9\uC790|\uC0AC\uC5C5\s*\uB2F4\uB2F9\uC790|\uC5F0\uB77D\s*\uB2F4\uB2F9\uC790|\uB2F4\uB2F9\uC790(?:\uBA85|\s*\uC774\uB984)?|\uC131\uBA85)\s*[:：]?\s*[\uAC00-\uD7A3]{2,4}")
SENSITIVE_QUERY_RE = re.compile(r"(?i)([?&](?:token|access_token|downloadtoken|servicekey|signature|authorization|api_key|apikey|client_secret)=)[^&#\s]+")
CONTACT_PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+?82[- .]?)?0\d{1,2}[() .-]?\d{3,4}[- .]?\d{4}|1[568]\d{2}[- .]?\d{4})(?!\d)")
CONTACT_EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
OFFICIAL_CONTACT_CONTEXT_RE = re.compile(r"\uB300\uD45C\s*\uC804\uD654|\uB300\uD45C\s*\uBC88\uD638|\uC0AC\uC5C5\s*\uBB38\uC758|\uC2E0\uCCAD\s*\uBB38\uC758|\uC811\uC218\s*\uBB38\uC758|\uBB38\uC758\s*\uCC98|\uB2F4\uB2F9\s*\uBD80\uC11C|\uBD80\uC11C\s*\uC804\uD654|\uAE30\uAD00\s*\uC804\uD654|\uACF5\uC2DD\s*\uBB38\uC758")
PERSONAL_CONTACT_CONTEXT_RE = re.compile(r"\uD734\uB300\s*\uC804\uD654|\uD734\uB300\uD3F0|\uAC1C\uC778\s*(?:\uC804\uD654|\uC774\uBA54\uC77C)|\uC131\uBA85|\uC9C1\uC811\s*\uC5F0\uB77D")

METHOD_FIELD_CODES = {
    "aply_mthd_onli_rcpt_istc": "ONLINE",
    "aply_mthd_eml_rcpt_istc": "EMAIL",
    "aply_mthd_vst_rcpt_istc": "IN_PERSON",
    "aply_mthd_pssr_rcpt_istc": "POST",
    "aply_mthd_fax_rcpt_istc": "FAX",
    "aply_mthd_etc_istc": "OTHER",
}
SECTION_MAP = {
    "title_summary": "NOTICE_SUMMARY",
    "title_body": "NOTICE_BODY",
    "eligibility_api": "ELIGIBILITY_API",
    "exclusion_api": "EXCLUSION_API",
    "preferred_api": "PREFERENCE_API",
    "support_details": "SUPPORT_DETAILS",
    "evaluation": "EVALUATION",
    "apply_method": "APPLICATION_METHOD",
    "att_preview": "ATTACHMENT_PREVIEW",
}
ATTACHMENT_ORIGINS = {"ATTACHMENT", "ATTACHMENT_OCR", "ATTACHMENT_PREVIEW"}
DATE_FORMATS = ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d", "%Y.%m.%d")


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    issues: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues.append({"file": path.name, "line": line_number, "issue": "INVALID_JSONL", "raw_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest()})
                continue
            if not isinstance(value, dict):
                issues.append({"file": path.name, "line": line_number, "issue": "NON_OBJECT_JSONL_RECORD", "raw_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest()})
                continue
            rows.append(value)
    return rows, issues


def field_status(row: dict[str, Any], key: str) -> str:
    if key not in row:
        return "NOT_COLLECTED"
    value = row[key]
    if value is None or (isinstance(value, str) and not value.strip()) or value == [] or value == {}:
        return "EMPTY"
    return "PRESENT"


def source_text(row: dict[str, Any], key: str) -> dict[str, Any]:
    status = field_status(row, key)
    value = row.get(key)
    if status == "PRESENT" and not isinstance(value, str):
        raise ValueError(f"{key}: expected source text string")
    return {"text": value if status == "PRESENT" else None, "availability": status}


@lru_cache(maxsize=8192)
def parse_date_string(text: str) -> date | None:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def timestamp(value: Any, *, source_present: bool, basis: str = "SOURCE") -> dict[str, Any]:
    raw = None if value is None else str(value)
    result = {"value": None, "raw_value": raw, "precision": "UNKNOWN", "timezone": None,
              "status": "NOT_COLLECTED" if not source_present else "EMPTY", "basis": "UNKNOWN" if not source_present else basis}
    if not source_present or value is None or (isinstance(value, str) and not value.strip()):
        return result
    text = str(value).strip()
    day = parse_date_string(text)
    if day is not None:
        result.update({"value": day.isoformat(), "precision": "DATE", "status": "PRESENT", "basis": basis})
        return result
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(normalized)
    except ValueError:
        result.update({"status": "UNPARSEABLE", "basis": basis})
        return result
    has_timezone = dt.tzinfo is not None and dt.utcoffset() is not None
    formatted = dt.isoformat()
    tz = None
    if has_timezone:
        offset = dt.strftime("%z")
        tz = f"{offset[:3]}:{offset[3:]}" if offset else None
        precision = "DATETIME_WITH_TIMEZONE"
    else:
        precision = "DATETIME"
    result.update({"value": formatted, "precision": precision, "timezone": tz, "status": "PRESENT", "basis": basis})
    return result


def is_end_of_day_derived(deadline: Any, end: Any) -> bool:
    if not isinstance(deadline, str) or not isinstance(end, str):
        return False
    end_date = parse_date_string(end)
    if not end_date:
        return False
    normalized_end = end_date.isoformat()
    return bool(re.fullmatch(re.escape(normalized_end) + r"T23:59:59(?:\.0+)?(?:\+09:00|\+0900)", deadline.strip()))


def normalize_deadline(row: dict[str, Any]) -> dict[str, Any]:
    raw = row.get("deadline_at")
    if is_end_of_day_derived(raw, row.get("application_end")):
        end_date = parse_date_string(str(row.get("application_end")))
        return {"value": end_date.isoformat() if end_date else None, "raw_value": str(raw),
                "precision": "DATE", "timezone": None, "status": "DERIVED_FROM_END_DATE",
                "basis": "APPLICATION_END_DATE"}
    return timestamp(raw, source_present="deadline_at" in row)


def scrubbed_url(value: Any, *, allowed_domain: str | None = None) -> tuple[str | None, str]:
    if value is None or value == "":
        return None, "EMPTY"
    if not isinstance(value, str):
        return str(value), "INVALID"
    text = SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", value.strip())
    try:
        parsed = urlparse(text)
        host = (parsed.hostname or "").casefold().rstrip(".")
        _ = parsed.port
    except ValueError:
        return None, "INVALID"
    domain_allowed = allowed_domain is None or host == allowed_domain or host.endswith("." + allowed_domain)
    valid = parsed.scheme.casefold() == "https" and bool(host) and domain_allowed and not parsed.username and not parsed.password and not any(c.isspace() for c in text) and "[REDACTED]" not in text
    if parsed.username is not None or parsed.password is not None:
        return None, "INVALID"
    # Preserve the URL exactly except for secrets; malformed values are flagged, never repaired.
    return text, "VALID" if valid else "INVALID"


def scrub_record_text(value: Any, report: PrivacyReport | None = None) -> Any:
    """Apply local PII patterns after the shared sanitizer, including labelled names/secrets."""
    if isinstance(value, dict):
        return {key: scrub_record_text(child, report) for key, child in value.items()}
    if isinstance(value, list):
        return [scrub_record_text(child, report) for child in value]
    if isinstance(value, str):
        if report is not None:
            report.contextual_name_count += len(CONTACT_NAME_RE.findall(value))
        value = CONTACT_NAME_RE.sub(lambda match: f"{match.group('label')} [이름 삭제]", value)
        return SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", value)
    return value


def extract_literal_urls(text: str | None, source_field: str) -> list[dict[str, str]]:
    if not text:
        return []
    result, seen = [], set()
    for match in URL_RE.findall(text):
        url = match.rstrip(URL_END_PUNCTUATION)
        if url and url not in seen:
            seen.add(url)
            result.append({"value": url, "purpose": "UNCLASSIFIED", "source_field": source_field})
    return result


def normalize_methods(row: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str]:
    raw_methods = row.get("apply_methods")
    entries: list[dict[str, Any]] = []
    if isinstance(raw_methods, dict):
        for source_field, raw_text in raw_methods.items():
            if raw_text is None or raw_text == "":
                continue
            text = raw_text if isinstance(raw_text, str) else json.dumps(raw_text, ensure_ascii=False, sort_keys=True)
            entries.append({"method_code": METHOD_FIELD_CODES.get(source_field, "UNCLASSIFIED"),
                            "raw_text": text, "source_field": str(source_field),
                            "urls": extract_literal_urls(text, str(source_field))})
        return entries, "PRESENT" if entries else "EMPTY"
    text = row.get("apply_method_text")
    if text:
        text_value = text if isinstance(text, str) else str(text)
        return ([{"method_code": "UNCLASSIFIED", "raw_text": text_value,
                  "source_field": "apply_method_text", "urls": extract_literal_urls(text_value, "apply_method_text")}], "DERIVED")
    if "apply_methods" in row or "apply_method_text" in row:
        return [], "EMPTY"
    return None, "NOT_COLLECTED"


def normalize_contacts(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Retain only contacts with explicit official-work context; quarantine ambiguity without its value."""
    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    field_names = ("contact_text", "contact_phone_raw")
    for source_field in field_names:
        text = row.get(source_field)
        if not isinstance(text, str) or not text.strip():
            continue
        matches = [("PHONE", match) for match in CONTACT_PHONE_RE.finditer(text)]
        matches.extend(("EMAIL", match) for match in CONTACT_EMAIL_RE.finditer(text))
        matches.sort(key=lambda item: item[1].start())
        for contact_type, match in matches:
            value = match.group(0).strip()
            left_separators = [text.rfind(separator, 0, match.start()) for separator in ("\n", ";", "|")]
            right_separators = [position for separator in ("\n", ";", "|")
                                if (position := text.find(separator, match.end())) >= 0]
            left = max(left_separators) + 1
            right = min(right_separators) if right_separators else len(text)
            window = text[left:right]
            has_personal_context = bool(PERSONAL_CONTACT_CONTEXT_RE.search(window) or CONTACT_NAME_RE.search(window))
            has_official_context = bool(OFFICIAL_CONTACT_CONTEXT_RE.search(window))
            source_department = row.get("operating_dept")
            source_department_pair = (str(row.get("source_system") or "").upper() == "KSTARTUP"
                                      and source_field == "contact_phone_raw"
                                      and isinstance(source_department, str) and bool(source_department.strip()))
            classification = ("PERSONAL" if has_personal_context else
                              "OFFICIAL_BUSINESS" if has_official_context or source_department_pair else "UNCLASSIFIED")
            basis = ("PERSONAL_LABEL_OR_NAME" if has_personal_context else
                     "SOURCE_CONTACT_DEPARTMENT_PAIR" if source_department_pair else
                     "EXPLICIT_OFFICIAL_CONTEXT" if has_official_context else "INSUFFICIENT_CONTEXT")
            key = (contact_type, value)
            item = candidates.setdefault(key, {"type": contact_type, "value": value,
                "classification": classification, "classification_basis": basis,
                "source_system": str(row.get("source_system") or "UNKNOWN"), "source_fields": [],
                "organization": None, "department": None})
            priority = {"UNCLASSIFIED": 0, "OFFICIAL_BUSINESS": 1, "PERSONAL": 2}
            if priority[classification] > priority[item["classification"]]:
                item["classification"] = classification
                item["classification_basis"] = basis
            if source_department_pair and classification == "OFFICIAL_BUSINESS":
                item["department"] = scrub_record_text(sanitize_tree(source_department))
            if source_field not in item["source_fields"]:
                item["source_fields"].append(source_field)
        if not matches:
            key = ("UNKNOWN", source_field)
            candidates[key] = {"type": "UNKNOWN", "value": None, "classification": "UNCLASSIFIED",
                "classification_basis": "INSUFFICIENT_CONTEXT", "source_system": str(row.get("source_system") or "UNKNOWN"),
                "source_fields": [source_field], "organization": None, "department": None}

    results = []
    for item in candidates.values():
        classification = item.pop("classification")
        value = item.pop("value")
        item["value"] = value if classification == "OFFICIAL_BUSINESS" else None
        if item["type"] == "PHONE" and value:
            item["normalized_value"] = re.sub(r"\D", "", value) if classification == "OFFICIAL_BUSINESS" else None
        elif item["type"] == "EMAIL" and value:
            local, sep, domain = value.partition("@")
            item["normalized_value"] = f"{local}@{domain.casefold()}" if classification == "OFFICIAL_BUSINESS" and sep else None
        else:
            item["normalized_value"] = None
        item["classification"] = classification
        item["review_status"] = {"OFFICIAL_BUSINESS": "AUTO_CLASSIFIED", "PERSONAL": "REDACTED",
                                  "UNCLASSIFIED": "NEEDS_REVIEW"}[classification]
        item["service_visibility"] = classification == "OFFICIAL_BUSINESS"
        results.append(item)
    return sorted(results, key=lambda item: (item["type"], item["source_fields"], item["value"] or ""))


def normalize_attachments(row: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any] | None:
    if "attachments" not in row:
        return None
    raw = row.get("attachments")
    if raw is None:
        return {"count": None, "text_extracted": None, "preview_only": None, "note": None,
                "collection_status": "UNKNOWN", "extraction_status": "UNKNOWN", "review_status": "UNKNOWN"}
    if not isinstance(raw, dict):
        issues.append({"notice_id": row.get("notice_id"), "field": "attachments", "issue": "UNEXPECTED_ATTACHMENT_SHAPE", "input_type": type(raw).__name__})
        return {"count": None, "text_extracted": None, "preview_only": None, "note": str(raw),
                "collection_status": "UNKNOWN", "extraction_status": "UNKNOWN", "review_status": "UNKNOWN"}

    def count(key: str) -> int | None:
        v = raw.get(key)
        if v is None:
            return None
        if isinstance(v, bool) or not isinstance(v, int) or v < 0:
            issues.append({"notice_id": row.get("notice_id"), "field": f"attachments.{key}", "issue": "INVALID_COUNT", "input_type": type(v).__name__})
            return None
        return v

    total, extracted, preview = count("count"), count("text_extracted"), count("preview_only")
    if total is not None and any(v is not None and v > total for v in (extracted, preview)):
        issues.append({"notice_id": row.get("notice_id"), "issue": "INVALID_ATTACHMENT_COUNTS"})
        extracted = extracted if extracted is None or extracted <= total else None
        preview = preview if preview is None or preview <= total else None
    if total is None:
        collection = "NOT_COLLECTED"
        extraction = "NOT_ATTEMPTED"
        review = "UNKNOWN"
    elif total == 0:
        collection = "COLLECTED"
        extraction = "NO_ATTACHMENTS"
        review = "NOT_APPLICABLE"
    else:
        collection = "COLLECTED"
        if extracted is None:
            extraction = "UNKNOWN"
        elif extracted == 0 and (preview or 0) == 0:
            extraction = "NOT_ATTEMPTED"
        elif extracted < total:
            extraction = "PARTIAL"
        else:
            extraction = "COMPLETE"
        review = "UNREVIEWED" if extracted else "UNKNOWN"
    note = raw.get("note")
    return {"count": total, "text_extracted": extracted, "preview_only": preview,
            "note": note if isinstance(note, str) else None, "collection_status": collection,
            "extraction_status": extraction, "review_status": review}


def normalized_source(row: dict[str, Any]) -> dict[str, Any]:
    source = row.get("source_system")
    return {"source_system": str(source) if source is not None else "UNKNOWN",
            "source_id": None if row.get("source_id") is None else str(row.get("source_id"))}


def normalize_notice(row: dict[str, Any], issues: list[dict[str, Any]]) -> tuple[dict[str, Any], PrivacyReport]:
    source_system = row.get("source_system") or "UNKNOWN"
    fetched_present = "fetched_at" in row
    published_not_provided = str(source_system).upper() == "KSTARTUP" and row.get("published_at") in (None, "")
    source_updated_not_provided = str(source_system).upper() == "KSTARTUP" and row.get("source_updated_at") in (None, "")
    apply_url, apply_url_status = scrubbed_url(row.get("apply_url"))
    official_domain = {"KSTARTUP": "k-startup.go.kr", "BIZINFO": "bizinfo.go.kr"}.get(str(source_system).upper())
    guide_url, guide_url_status = scrubbed_url(row.get("guide_url"), allowed_domain="k-startup.go.kr" if source_system == "KSTARTUP" else official_domain)
    notice_url, notice_url_status = scrubbed_url(row.get("detail_url"), allowed_domain=official_domain)
    flags = row.get("guide_url_flags") or []
    if "guide_url_malformed" in flags:
        guide_url_status = "INVALID"
    methods, method_status = normalize_methods(row)

    structured_raw = row.get("structured") if isinstance(row.get("structured"), dict) else {}
    structured = {key: structured_raw.get(key) for key in
                  ("target_group_text", "business_age_raw", "founder_age_raw", "applicant_target_raw")}
    condition_fields = {"eligibility": "eligibility_text", "exclusion": "exclusion_text", "preference": "preferred_text"}
    condition_texts = {name: source_text(row, key) for name, key in condition_fields.items()}
    content = {name: source_text(row, key) for name, key in
               (("summary_text", "summary_text"), ("body_text", "body_text"), ("support_text", "support_text"), ("evaluation_text", "evaluation_text"))}

    contacts = normalize_contacts(row)

    field_availability: dict[str, str] = {}
    for key in ("published_at", "source_updated_at", "fetched_at", "application_start", "application_end", "deadline_at",
                "detail_url", "apply_url", "guide_url", "apply_method_text", "contact_text", "contact_phone_raw",
                "category_major", "category_medium", "region_raw", "region_concept_ids"):
        if key == "published_at" and published_not_provided or key == "source_updated_at" and source_updated_not_provided:
            field_availability[key] = "NOT_COLLECTED"
        else:
            field_availability[key] = field_status(row, key)
    field_availability.update({
        "urls.apply_methods": method_status,
        "attachments": field_status(row, "attachments"),
        "structured.target_group_text": field_status(structured_raw, "target_group_text"),
        "structured.business_age_raw": field_status(structured_raw, "business_age_raw"),
        "structured.founder_age_raw": field_status(structured_raw, "founder_age_raw"),
        "structured.applicant_target_raw": field_status(structured_raw, "applicant_target_raw"),
    })
    for name, key in condition_fields.items():
        field_availability[f"condition_texts.{name}"] = field_status(row, key)
    contact_input_state = [field_status(row, key) for key in ("contact_text", "contact_phone_raw")]
    field_availability["contacts"] = ("PRESENT" if "PRESENT" in contact_input_state else
                                       "EMPTY" if "EMPTY" in contact_input_state else "NOT_COLLECTED")
    for name in ("summary_text", "body_text", "support_text", "evaluation_text"):
        source_key = {"summary_text": "summary_text", "body_text": "body_text", "support_text": "support_text", "evaluation_text": "evaluation_text"}[name]
        field_availability[f"content.{name}"] = field_status(row, source_key)

    record = {
        "schema_version": "1.0", "record_type": "notice", "notice_id": row.get("notice_id"),
        "source": normalized_source(row), "title": row.get("title"), "title_raw": row.get("title_raw"),
        "timestamps": {
            "fetched_at": timestamp(row.get("fetched_at"), source_present=fetched_present),
            "published_at": timestamp(row.get("published_at"), source_present=("published_at" in row and not published_not_provided)),
            "source_updated_at": timestamp(row.get("source_updated_at"), source_present=("source_updated_at" in row and not source_updated_not_provided)),
        },
        "application_period": {
            "start": timestamp(row.get("application_start"), source_present="application_start" in row),
            "end": timestamp(row.get("application_end"), source_present="application_end" in row),
            "deadline": normalize_deadline(row),
            "status_kind": row.get("apply_status_kind"), "is_open": row.get("is_open"), "period_status": row.get("period_status"),
        },
        "urls": {"apply_url": apply_url, "guide_url": guide_url, "notice_url": notice_url,
                 "apply_methods": methods, "apply_method_text": row.get("apply_method_text"),
                 "url_status": {"apply_url": apply_url_status, "guide_url": guide_url_status, "notice_url": notice_url_status}},
        "organization": {
            "raw": row.get("org_raw"), "names": row.get("org_names"), "role_titles": row.get("org_role_titles"),
            "flags": row.get("org_flags"), "executor_name": row.get("executor_org_name"), "executor_kind": row.get("executor_kind"),
            "operating_department": row.get("operating_dept"), "organization_kind": row.get("org_kind"),
        },
        "category": {"source_major": row.get("category_major"), "source_medium": row.get("category_medium")},
        "region": {"raw": row.get("region_raw"), "concept_ids": row.get("region_concept_ids"), "basis": row.get("region_basis"),
                   "scope_hint": row.get("region_scope_hint"), "tags_hint": row.get("region_tags_hint")},
        "structured": structured, "condition_texts": condition_texts, "content": content,
        "attachments": normalize_attachments(row, issues),
        "contacts": [],
        "field_availability": field_availability,
        "source_metadata": {
            "source_record_id": row.get("source_record_id"), "version": row.get("version"), "is_latest": row.get("is_latest"),
            "raw_hash": row.get("raw_hash"), "source_run": row.get("source_run"), "content_hash": row.get("content_hash"),
            "related_group_id": row.get("related_group_id"), "is_integrated": row.get("is_integrated"),
            "program_name": row.get("program_name"), "legacy_deadline_at": row.get("deadline_at"),
            "guide_url_flags": row.get("guide_url_flags"),
        },
        "normalizer_version": NORMALIZER_VERSION,
    }
    report = PrivacyReport()
    safe_record = scrub_record_text(sanitize_tree(record, report), report)
    safe_record["contacts"] = contacts
    if not safe_record.get("notice_id"):
        issues.append({"notice_id": None, "issue": "MISSING_NOTICE_ID"})
    if guide_url_status == "INVALID" and guide_url:
        issues.append({"notice_id": row.get("notice_id"), "field": "urls.guide_url", "issue": "INVALID_OR_MALFORMED_URL", "value": safe_record["urls"]["guide_url"]})
    deadline = safe_record["application_period"]["deadline"]
    if deadline["status"] == "DERIVED_FROM_END_DATE":
        issues.append({"notice_id": row.get("notice_id"), "field": "application_period.deadline", "issue": "LEGACY_END_OF_DAY_TIMESTAMP_DERIVED_FROM_DATE", "raw_value": deadline["raw_value"]})
    return safe_record, report


def normalize_section(original: str) -> str:
    base = original.split("@", 1)[0]
    if base in SECTION_MAP:
        return SECTION_MAP[base]
    if base.startswith("att_"):
        token = base.removeprefix("att_").upper()
        return f"ATTACHMENT_{token}"
    return "SOURCE_DEFINED"


def normalize_chunk(row: dict[str, Any], privacy_report: PrivacyReport) -> dict[str, Any]:
    origin = str(row.get("origin") or "UNKNOWN")
    is_attachment = origin.upper().startswith("ATTACHMENT") or str(row.get("section") or "").lower().startswith("att_")
    record = {
        "schema_version": "1.0", "record_type": "chunk", "chunk_id": row.get("chunk_id"),
        "notice_id": row.get("notice_id"), "source_system": row.get("source_system") or "UNKNOWN",
        "section": normalize_section(str(row.get("section") or "")), "section_original": str(row.get("section") or ""),
        "origin": origin, "text": row.get("text") if isinstance(row.get("text"), str) else "",
        "source_content_hash": row.get("content_hash"), "is_open": row.get("is_open"),
        "region_concept_ids": row.get("region_concept_ids"),
        "privacy_status": "CLEARED", "search_eligible": not is_attachment,
        "content_review_status": "UNREVIEWED", "normalizer_version": NORMALIZER_VERSION,
    }
    safe_record = scrub_record_text(sanitize_tree(record, privacy_report), privacy_report)
    if (pii_findings(safe_record) or privacy_report.ambiguous_context_count
            or row.get("privacy_status") == "REVIEW_REQUIRED"):
        safe_record["privacy_status"] = "REVIEW_REQUIRED"
    if (safe_record["privacy_status"] != "CLEARED" or not safe_record["text"].strip()
            or origin.upper() == "UNKNOWN" or row.get("search_eligible") is False):
        safe_record["search_eligible"] = False
    return safe_record


@lru_cache(maxsize=4)
def load_validator(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def schema_errors(record: dict[str, Any], validator: Draft202012Validator) -> list[str]:
    return [f"{error.json_path}: {error.validator}" for error in validator.iter_errors(record)]


def pii_findings(value: Any, path: str = "", *, allow_official_contact: bool = False) -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if (str(key).casefold() in {"contact_text", "contact_phone_raw", "contact_name", "manager_name", "person_name"}
                    and child not in (None, "", False, "PRESENT", "EMPTY", "NOT_COLLECTED")):
                findings.append(f"{path}.{key}: forbidden contact payload")
            allow_value = (key in {"value", "normalized_value"} and
                           value.get("classification") == "OFFICIAL_BUSINESS" and
                           value.get("service_visibility") is True)
            findings.extend(pii_findings(child, f"{path}.{key}", allow_official_contact=allow_value))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(pii_findings(child, f"{path}[{index}]", allow_official_contact=allow_official_contact))
    elif isinstance(value, str):
        if path.rsplit(".", 1)[-1] not in {"raw_hash", "content_hash", "source_content_hash"}:
            if not allow_official_contact and PII_EMAIL.search(value): findings.append(f"{path}: email")
            if not allow_official_contact and CONTACT_PHONE_RE.search(value): findings.append(f"{path}: phone")
            if any(match.group(1) != "[REDACTED]" for match in TOKEN_QUERY.finditer(value)): findings.append(f"{path}: URL token")
            if CONTACT_NAME_RE.search(value): findings.append(f"{path}: personal name context")
    return findings


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def report_input_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return f"{path.parent.name}/{path.name}"


def normalize_snapshot(input_dir: Path, output_dir: Path, *, schema_dir: Path | None = None) -> dict[str, Any]:
    schema_dir = schema_dir or ROOT / "schemas" / "support-data"
    notice_validator = load_validator(schema_dir / "support-notice-v1.schema.json")
    chunk_validator = load_validator(schema_dir / "support-chunk-v1.schema.json")
    if input_dir.resolve() == output_dir.resolve():
        raise ValueError("Input and output directories must differ")
    input_notices = input_dir / "notices.jsonl"
    input_chunks = input_dir / "chunks.jsonl"
    if not input_notices.is_file() or not input_chunks.is_file():
        raise FileNotFoundError(f"Expected notices.jsonl and chunks.jsonl in {input_dir}")
    notices_raw, issues = read_jsonl(input_notices)
    chunks_raw, chunk_read_issues = read_jsonl(input_chunks)
    issues.extend(chunk_read_issues)

    notices, redactions = [], Counter()
    contacts_by_source: dict[str, Counter[str]] = {}
    for raw in notices_raw:
        row, privacy_report = normalize_notice(raw, issues)
        notices.append(row)
        source = row["source"]["source_system"]
        contact_counts = contacts_by_source.setdefault(source, Counter())
        contact_counts["contact_candidates_found"] += len(row["contacts"])
        contact_counts["official_business_contacts_preserved"] += sum(c["classification"] == "OFFICIAL_BUSINESS" for c in row["contacts"])
        contact_counts["personal_identifiers_redacted"] += sum(c["classification"] == "PERSONAL" for c in row["contacts"])
        contact_counts["unclassified_contacts_queued"] += sum(c["classification"] == "UNCLASSIFIED" for c in row["contacts"])
        contact_counts["contact_person_name_occurrences_redacted"] += sum(
            len(CONTACT_NAME_RE.findall(raw.get(field, ""))) for field in ("contact_text", "contact_phone_raw")
            if isinstance(raw.get(field), str))
        redactions.update({"emails": privacy_report.email_count, "phones": privacy_report.phone_count,
                           "url_tokens": privacy_report.url_token_count, "contextual_names": privacy_report.contextual_name_count,
                           "ambiguous_contexts": privacy_report.ambiguous_context_count})

    notice_ids = [row.get("notice_id") for row in notices]
    notice_id_set = set(notice_ids)
    counts = Counter()
    notice_id_counts = Counter(notice_ids)
    duplicate_notice_groups = sum(v > 1 for v in notice_id_counts.values())
    if duplicate_notice_groups:
        issues.append({"issue": "DUPLICATE_NOTICE_IDS", "count": duplicate_notice_groups})

    chunks, chunk_id_list = [], []
    for raw in chunks_raw:
        privacy_report = PrivacyReport()
        row = normalize_chunk(raw, privacy_report)
        chunks.append(row)
        chunk_id_list.append(row.get("chunk_id"))
        redactions.update({"emails": privacy_report.email_count, "phones": privacy_report.phone_count,
                           "url_tokens": privacy_report.url_token_count, "contextual_names": privacy_report.contextual_name_count,
                           "ambiguous_contexts": privacy_report.ambiguous_context_count})
        if row.get("notice_id") not in notice_id_set:
            issues.append({"chunk_id": row.get("chunk_id"), "notice_id": row.get("notice_id"), "issue": "CHUNK_WITHOUT_NOTICE"})
        counts[f"section:{row['source_system']}:{row['section']}:{row['origin']}"] += 1
        errors = schema_errors(row, chunk_validator)
        for message in errors:
            issues.append({"chunk_id": row.get("chunk_id"), "issue": "SCHEMA_VALIDATION", "detail": message})
        for finding in pii_findings(row):
            issues.append({"chunk_id": row.get("chunk_id"), "issue": "PII_REMAINS_AFTER_SCRUB", "detail": finding})

    for row in notices:
        counts[f"notice:{row['source']['source_system']}"] += 1
        for field, entry in row["field_availability"].items():
            counts[f"field_status:{row['source']['source_system']}:{field}:{entry}"] += 1
        errors = schema_errors(row, notice_validator)
        for message in errors:
            issues.append({"notice_id": row.get("notice_id"), "issue": "SCHEMA_VALIDATION", "detail": message})
        for finding in pii_findings(row):
            issues.append({"notice_id": row.get("notice_id"), "issue": "PII_REMAINS_AFTER_SCRUB", "detail": finding})

    duplicate_chunk_ids = len(chunk_id_list) - len(set(chunk_id_list))
    if duplicate_chunk_ids:
        issues.append({"issue": "DUPLICATE_CHUNK_IDS", "count": duplicate_chunk_ids})
    source_notice_counts = Counter(row["source"]["source_system"] for row in notices)
    source_chunk_counts = Counter(row["source_system"] for row in chunks)
    source_record_counts = {source: {"notices": source_notice_counts[source], "chunks": source_chunk_counts[source]}
                            for source in sorted(set(source_notice_counts) | set(source_chunk_counts))}
    contact_queue_coverage = {}
    totals, queued = Counter(), Counter()
    for notice in notices:
        source = notice["source"]["source_system"]
        for contact in notice["contacts"]:
            if contact["classification"] == "UNCLASSIFIED":
                totals[source] += 1
                queued[source] += contact["review_status"] == "NEEDS_REVIEW"
    for source in sorted(contacts_by_source):
        contact_queue_coverage[source] = queued[source] / totals[source] if totals[source] else 1.0

    output_dir.mkdir(parents=True, exist_ok=True)
    notice_path, chunk_path = output_dir / "notices.jsonl", output_dir / "chunks.jsonl"
    blocking = {"SCHEMA_VALIDATION", "PII_REMAINS_AFTER_SCRUB", "DUPLICATE_NOTICE_IDS",
                "DUPLICATE_CHUNK_IDS", "CHUNK_WITHOUT_NOTICE", "INVALID_JSONL", "NON_OBJECT_JSONL_RECORD"}
    publishable = not any(i.get("issue") in blocking for i in issues)
    if publishable:
        write_jsonl(notice_path, notices)
        write_jsonl(chunk_path, chunks)
    write_jsonl(output_dir / "normalization_issues.jsonl", issues)

    report = {
        "normalizer_version": NORMALIZER_VERSION,
        "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "input_snapshot": input_dir.name,
        "input_paths": {"notices": report_input_path(input_notices), "chunks": report_input_path(input_chunks)},
        "input_sha256": {"notices": sha256_file(input_notices), "chunks": sha256_file(input_chunks)},
        "input_counts": {"notices": len(notices_raw), "chunks": len(chunks_raw)},
        "output_counts": {"notices": len(notices), "chunks": len(chunks), "issues": len(issues)},
        "output_counts_by_source": source_record_counts,
        "duplicate_notice_id_records": duplicate_notice_groups,
        "duplicate_chunk_ids": duplicate_chunk_ids,
        "chunks_without_notice": sum(1 for c in chunks if c.get("notice_id") not in notice_id_set),
        "chunk_sections": {k.removeprefix("section:"): v for k, v in sorted(counts.items()) if k.startswith("section:")},
        "field_availability": {k.removeprefix("field_status:"): v for k, v in sorted(counts.items()) if k.startswith("field_status:")},
        "privacy_redactions": dict(redactions),
        "contact_processing_by_source": {source: dict(contact_counts) for source, contact_counts in sorted(contacts_by_source.items())},
        "unclassified_contact_review_coverage": contact_queue_coverage,
        "search_eligible_chunks": sum(bool(c["search_eligible"]) for c in chunks),
        "attachment_chunks_quarantined": sum(c["origin"] in ATTACHMENT_ORIGINS and not c["search_eligible"] for c in chunks),
        "schema_validation_errors": sum(i.get("issue") == "SCHEMA_VALIDATION" for i in issues),
        "privacy_residual_findings": sum(i.get("issue") == "PII_REMAINS_AFTER_SCRUB" for i in issues),
        "database_writes_performed": False,
        "publishable": publishable,
        "output_files_updated": publishable,
    }
    report_path = output_dir / "normalization_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="cleaned snapshot directory name (default: 20261124)")
    parser.add_argument("--input-dir", type=Path, help="override data/cleaned/<snapshot>")
    parser.add_argument("--output-dir", type=Path, help="override data/normalized/v1/<snapshot>")
    parser.add_argument("--schema-dir", type=Path, default=ROOT / "schemas" / "support-data")
    args = parser.parse_args(argv)
    input_dir = args.input_dir or (ROOT / "data" / "cleaned" / args.snapshot)
    output_dir = args.output_dir or (OUTPUT_BASE / args.snapshot)
    report = normalize_snapshot(input_dir, output_dir, schema_dir=args.schema_dir)
    print(json.dumps({"output_dir": str(output_dir), **report}, ensure_ascii=False, indent=2))
    return 0 if report["publishable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
