#!/usr/bin/env python3
"""Normalize cleaned support notices and chunks to the source-neutral v1 schema.

Reads data/cleaned/<snapshot>/ and writes data/normalized/v1/<snapshot>/.
It never edits the input snapshot or database loader files.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import tempfile
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

MOBILE_RE = re.compile(r"(?<!\d)01[016789][- .]?\d{3,4}[- .]?\d{4}(?!\d)")
# 담당자 이름 문맥 바로 뒤(같은 줄 40자 안)에 붙은 전화·이메일은 개인 연락처로 보고 지운다. 기관 대표 연락처는 지우지 않는다.
NAME_TAIL_CONTACT_RE = re.compile(r"(?P<label>문의\s*담당자|사업\s*담당자|연락\s*담당자|담당자(?:명|\s*이름)?|성명)\s*[:：]?\s*[가-힣]{2,4}(?P<tail>[^\n/;|]{0,40})")
PERSON_KEYS = {"담당자", "담당자명", "contact_name", "manager_name", "person_name", "문의자"}
URL_STATUS_VALUES = ("VALID", "INVALID", "EMPTY", "NOT_COLLECTED", "SCHEME_MISSING", "INSECURE_HTTP", "NOT_A_URL")
HOSTLIKE_RE = re.compile(r"^[\w.-]+\.[a-z]{2,}(?::\d+)?(?:[/?#]|$)", re.IGNORECASE)

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
    """URL을 원문 그대로(비밀값만 가림) 보존하고 상태를 분류한다. 고치거나 만들어 내지 않는다.

    VALID: https + 호스트(+ allowed_domain이 있으면 그 도메인). 외부 기관 URL도 https면 VALID이며 호스트를 검증했다는 뜻은 아니다.
    SCHEME_MISSING: `event-us.kr/..`처럼 도메인으로 보이지만 스킴이 없음. INSECURE_HTTP: http. NOT_A_URL: URL이 아닌 문자열(제목 등).
    INVALID: 자격 정보가 들어 있거나 파싱 불가, 허용 도메인 밖(allowed_domain 지정 시), 공백 포함.
    """
    if value is None or value == "":
        return None, "EMPTY"
    if not isinstance(value, str):
        return str(value), "INVALID"
    text = SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", value.strip())
    scheme_match = re.match(r"^([a-zA-Z][a-zA-Z0-9+.-]*)://", text)
    if not scheme_match:
        return text, ("SCHEME_MISSING" if HOSTLIKE_RE.match(text) and not any(c.isspace() for c in text) else "NOT_A_URL")
    try:
        parsed = urlparse(text)
        host = (parsed.hostname or "").casefold().rstrip(".")
        _ = parsed.port
    except ValueError:
        return None, "INVALID"
    if parsed.username is not None or parsed.password is not None:
        return None, "INVALID"
    if not host or any(c.isspace() for c in text) or "[REDACTED]" in text:
        return text, "INVALID"
    if allowed_domain is not None and not (host == allowed_domain or host.endswith("." + allowed_domain)):
        return text, "INVALID"
    scheme = parsed.scheme.casefold()
    if scheme == "http":
        return text, "INSECURE_HTTP"
    return text, "VALID" if scheme == "https" else "INVALID"


def scrub_text_public(value: str, report: PrivacyReport | None = None) -> str:
    """공개 공고용 정리. 기관 연락처(전화·이메일)는 그대로 두고, 개인 이름 문맥과 그 뒤에 붙은 연락처, URL 토큰만 지운다."""
    report = report or PrivacyReport()

    def drop_tail(match: re.Match[str]) -> str:
        tail = match.group("tail")
        n_phone, n_mail = len(PII_PHONE.findall(tail)), len(PII_EMAIL.findall(tail))
        report.phone_count += n_phone
        report.email_count += n_mail
        tail = PII_EMAIL.sub("[개인정보 마스킹]", PII_PHONE.sub("[개인정보 마스킹]", tail))
        report.contextual_name_count += 1
        return f"{match.group('label')} [이름 삭제]" + tail

    value = NAME_TAIL_CONTACT_RE.sub(drop_tail, value)
    return SENSITIVE_QUERY_RE.sub(r"\1[REDACTED]", value)


def sanitize_tree_public(value: Any, report: PrivacyReport | None = None, *, key: str = "") -> Any:
    """sanitize_tree의 공개 공고용 대체. 이름 키는 통째로 가리고, 문자열은 scrub_text_public만 적용한다."""
    report = report or PrivacyReport()
    if isinstance(value, dict):
        out = {}
        for child_key, child in value.items():
            if str(child_key).casefold() in PERSON_KEYS and child:
                report.contextual_name_count += 1
                out[child_key] = "[이름 마스킹]"
            else:
                out[child_key] = sanitize_tree_public(child, report, key=str(child_key))
        return out
    if isinstance(value, list):
        return [sanitize_tree_public(item, report, key=key) for item in value]
    if isinstance(value, str):
        return value if key.casefold().endswith("_hash") else scrub_text_public(value, report)
    return value


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
        last_end, last_org = 0, None
        for contact_type, match in matches:
            value = match.group(0).strip()
            window_separators = ("\n", ";", "|", "/")
            left_separators = [text.rfind(separator, 0, match.start()) for separator in window_separators]
            right_separators = [position for separator in window_separators
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
            # 공공기관 공고의 연락처 필드(contact_text/contact_phone_raw)에 적힌 전화·이메일은 개인 맥락 표지가 없으면 기관 연락처로 본다.
            classification = ("PERSONAL" if has_personal_context else "OFFICIAL_BUSINESS")
            basis = ("PERSONAL_LABEL_OR_NAME" if has_personal_context else
                     "SOURCE_CONTACT_DEPARTMENT_PAIR" if source_department_pair else
                     "EXPLICIT_OFFICIAL_CONTEXT" if has_official_context else "SOURCE_PUBLIC_AGENCY_CONTACT_FIELD")
            # 기관명은 연락처 바로 앞 문구를 그대로 쓴다(추정 아님). 앞 문구가 없으면 같은 구획의 앞 연락처 기관을 이어 쓴다.
            segment_start = max(left, last_end)
            prefix = text[segment_start:match.start()].strip(" ,:-·()[]")
            prefix = re.sub(r"(?:대표\s*)?(?:전화번호|전화|연락처|문의|TEL|Tel|tel)\s*$", "", prefix).strip(" ,:-·()[]")
            if prefix and re.search(r"[가-힣]", prefix) and not re.search(r"\d", prefix) and 2 <= len(prefix) <= 40:
                organization = prefix
            elif left <= last_end and last_org:
                organization = last_org
            else:
                organization = None
            last_end, last_org = match.end(), organization
            key = (contact_type, value)
            item = candidates.setdefault(key, {"type": contact_type, "value": value,
                "classification": classification, "classification_basis": basis,
                "source_system": str(row.get("source_system") or "UNKNOWN"), "source_fields": [],
                "organization": None, "department": None})
            priority = {"UNCLASSIFIED": 0, "OFFICIAL_BUSINESS": 1, "PERSONAL": 2}
            if priority[classification] > priority[item["classification"]]:
                item["classification"] = classification
                item["classification_basis"] = basis
            if classification == "OFFICIAL_BUSINESS" and item["organization"] is None:
                if organization:
                    item["organization"] = scrub_record_text(sanitize_tree_public(organization))
                elif source_department_pair:
                    names = row.get("org_names")
                    first = names[0] if isinstance(names, list) and names else row.get("org_raw")
                    item["organization"] = first if isinstance(first, str) and first.strip() else None
            if source_department_pair and classification == "OFFICIAL_BUSINESS":
                item["department"] = scrub_record_text(sanitize_tree_public(source_department))
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
    official_domain = {"KSTARTUP": "k-startup.go.kr", "BIZINFO": "bizinfo.go.kr", "G2B": "g2b.go.kr"}.get(str(source_system).upper())
    guide_url, guide_url_status = scrubbed_url(row.get("guide_url"))  # 안내 URL은 외부 기관 페이지일 수 있어 도메인을 제한하지 않는다
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
        "region": {"raw": row.get("region_raw"), "concept_ids": row.get("region_concept_ids"), "source": row.get("region_source"),
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
    safe_record = scrub_record_text(sanitize_tree_public(record, report), report)
    safe_record["contacts"] = contacts
    if not safe_record.get("notice_id"):
        issues.append({"notice_id": None, "issue": "MISSING_NOTICE_ID"})
    for url_field, status in (("guide_url", guide_url_status), ("apply_url", apply_url_status), ("notice_url", notice_url_status)):
        shown = safe_record["urls"][url_field]
        code = {"INVALID": "INVALID_OR_MALFORMED_URL", "SCHEME_MISSING": "URL_SCHEME_MISSING",
                "INSECURE_HTTP": "URL_INSECURE_HTTP", "NOT_A_URL": "URL_FIELD_NOT_A_URL"}.get(status)
        if code and shown:
            issues.append({"notice_id": row.get("notice_id"), "field": f"urls.{url_field}", "issue": code, "value": shown})
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
    safe_record = scrub_record_text(sanitize_tree_public(record, privacy_report), privacy_report)
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
            # 기관 연락처는 본문에 남기는 것이 정책이다. 담당자 이름 문맥 바로 뒤에 붙은 전화·이메일만 개인 정보로 본다.
            if not allow_official_contact:
                for named in NAME_TAIL_CONTACT_RE.finditer(value):
                    if PII_EMAIL.search(named.group("tail")) or PII_PHONE.search(named.group("tail")):
                        findings.append(f"{path}: contact next to personal name")
                        break
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

    url_counts = Counter((row["source"]["source_system"], field, status)
                         for row in notices for field, status in row["urls"]["url_status"].items())
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

    # 검수 대기열: 값 없이 사유만 적는다. 검수 담당과 절차는 docs/SUPPORT_DATA_NORMALIZATION_V1.md의 "검수 대기열" 절을 따른다.
    review_queue = []
    for notice in notices:
        for contact in notice["contacts"]:
            if contact["review_status"] == "NEEDS_REVIEW":
                review_queue.append({"kind": "CONTACT", "notice_id": notice["notice_id"], "reason": contact["classification_basis"],
                                     "type": contact["type"], "source_fields": contact["source_fields"]})
    for chunk in chunks:
        if chunk["privacy_status"] == "REVIEW_REQUIRED":
            review_queue.append({"kind": "CHUNK", "chunk_id": chunk["chunk_id"], "notice_id": chunk["notice_id"],
                                 "reason": "PRIVACY_REVIEW_REQUIRED"})
    text_contacts = Counter()
    for row in [*notices, *chunks]:
        blob = json.dumps({k: v for k, v in row.items() if k != "contacts"}, ensure_ascii=False)
        text_contacts["emails_kept_in_text"] += len(PII_EMAIL.findall(blob))
        text_contacts["phones_kept_in_text"] += len(CONTACT_PHONE_RE.findall(blob))
        text_contacts["mobile_numbers_kept_in_text"] += len(MOBILE_RE.findall(blob))

    output_dir.mkdir(parents=True, exist_ok=True)
    notice_path, chunk_path = output_dir / "notices.jsonl", output_dir / "chunks.jsonl"
    blocking = {"SCHEMA_VALIDATION", "PII_REMAINS_AFTER_SCRUB", "DUPLICATE_NOTICE_IDS",
                "DUPLICATE_CHUNK_IDS", "CHUNK_WITHOUT_NOTICE", "INVALID_JSONL", "NON_OBJECT_JSONL_RECORD"}
    publishable = not any(i.get("issue") in blocking for i in issues)
    if publishable:
        write_jsonl(notice_path, notices)
        write_jsonl(chunk_path, chunks)
    write_jsonl(output_dir / "normalization_issues.jsonl", issues)
    write_jsonl(output_dir / "review_queue.jsonl", review_queue)

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
        "contact_text_policy": {"official_contacts_masked_in_text": False, "personal_name_context_removed": True,
                                "kept_in_text": dict(text_contacts)},
        "url_status_by_source": {f"{src}:{field}:{status}": n for (src, field, status), n in sorted(url_counts.items())},
        "review_queue_items": len(review_queue),
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


def _g2b_string(value: Any, *, field: str, notice_id: str, issues: list[dict[str, Any]]) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    issues.append({"notice_id": notice_id, "field": field, "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(value).__name__})
    return None


def _g2b_source_metadata(row: dict[str, Any], issues: list[dict[str, Any]]) -> dict[str, Any]:
    nid = str(row.get("notice_id") or "")
    licenses = row.get("licenses")
    regions = row.get("regions")
    documents = row.get("documents")
    if not isinstance(licenses, list):
        issues.append({"notice_id": nid, "field": "licenses", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(licenses).__name__})
        licenses = []
    if not isinstance(regions, list):
        issues.append({"notice_id": nid, "field": "regions", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(regions).__name__})
        regions = []
    if not isinstance(documents, list):
        issues.append({"notice_id": nid, "field": "documents", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(documents).__name__})
        documents = []

    license_rows = []
    for index, item in enumerate(licenses):
        if not isinstance(item, dict):
            issues.append({"notice_id": nid, "field": f"licenses[{index}]", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(item).__name__})
            continue
        permitted = item.get("permitted_industries")
        if permitted is not None and not isinstance(permitted, str):
            issues.append({"notice_id": nid, "field": f"licenses[{index}].permitted_industries", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(permitted).__name__})
            permitted = None
        license_rows.append({
            "group": _g2b_string(item.get("group"), field=f"licenses[{index}].group", notice_id=nid, issues=issues),
            "name": _g2b_string(item.get("name"), field=f"licenses[{index}].name", notice_id=nid, issues=issues),
            "permitted_industries": permitted,
        })

    region_rows = []
    for index, value in enumerate(regions):
        if not isinstance(value, str):
            issues.append({"notice_id": nid, "field": f"regions[{index}]", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(value).__name__})
            continue
        region_rows.append(value)

    document_rows = []
    for index, item in enumerate(documents):
        if not isinstance(item, dict):
            issues.append({"notice_id": nid, "field": f"documents[{index}]", "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(item).__name__})
            continue
        raw_url = item.get("url")
        safe_url, url_status = scrubbed_url(raw_url, allowed_domain="g2b.go.kr")
        if url_status == "INVALID":
            issues.append({"notice_id": nid, "field": f"documents[{index}].url", "issue": "INVALID_G2B_DOCUMENT_URL"})
            safe_url = None
        document_rows.append({
            "name": _g2b_string(item.get("name"), field=f"documents[{index}].name", notice_id=nid, issues=issues),
            "source": _g2b_string(item.get("source"), field=f"documents[{index}].source", notice_id=nid, issues=issues),
            "url": safe_url,
            "url_status": url_status,
        })

    def text(field: str):
        return _g2b_string(row.get(field), field=field, notice_id=nid, issues=issues)

    for field in ("is_negotiated", "is_cancelled"):
        value = row.get(field)
        if value is not None and not isinstance(value, bool):
            issues.append({"notice_id": nid, "field": field, "issue": "INVALID_G2B_FIELD_TYPE", "input_type": type(value).__name__})

    return {
        "bid_notice_no": text("bid_notice_no"), "bid_notice_ord": text("bid_notice_ord"),
        "category": text("category"), "notice_kind": text("notice_kind"), "service_division": text("service_division"),
        "procurement_large": text("procurement_large"), "procurement_mid": text("procurement_mid"),
        "procurement_detail": text("procurement_detail"), "industry_limit_yn": text("industry_limit_yn"),
        "participation_limit_yn": text("participation_limit_yn"), "license_status": text("license_status"),
        "licenses": license_rows, "region_status": text("region_status"), "regions": region_rows,
        "region_basis": text("region_basis"), "notice_at": text("notice_at"), "close_at": text("close_at"),
        "open_at": text("open_at"), "contract_method": text("contract_method"), "award_method": text("award_method"),
        "estimated_price": text("estimated_price"), "is_negotiated": row.get("is_negotiated"),
        "is_cancelled": row.get("is_cancelled"), "documents": document_rows,
    }


def normalize_g2b_notice(row: dict[str, Any], issues: list[dict[str, Any]]) -> tuple[dict[str, Any], PrivacyReport]:
    """Map one existing monthly G2B record without deriving bid conditions."""
    raw_id = row.get("notice_id")
    bid_no, bid_ord = row.get("bid_notice_no"), row.get("bid_notice_ord")
    if not all(isinstance(value, str) and value.strip() for value in (raw_id, bid_no, bid_ord)):
        issues.append({"notice_id": raw_id, "issue": "INVALID_G2B_NOTICE_ID"})
        safe_no = str(bid_no or raw_id or "MISSING")
        safe_ord = str(bid_ord or "UNKNOWN")
    else:
        safe_no, safe_ord = bid_no, bid_ord
    notice_id = f"G2B:{safe_no}:{safe_ord}"
    if row.get("source_system") != "G2B":
        issues.append({"notice_id": notice_id, "field": "source_system", "issue": "UNEXPECTED_G2B_SOURCE_SYSTEM"})

    notice_org = row.get("notice_org") if isinstance(row.get("notice_org"), str) else None
    demand_org = row.get("demand_org") if isinstance(row.get("demand_org"), str) else None
    contact_emails = [value for value in (row.get("contact_email"), row.get("demand_contact_email"))
                      if isinstance(value, str) and value.strip()]
    raw_documents = row.get("documents") if isinstance(row.get("documents"), list) else []
    common_row = {
        "notice_id": notice_id, "source_system": "G2B", "source_id": raw_id,
        "title": row.get("title"), "title_raw": row.get("title"), "published_at": row.get("notice_at"),
        "deadline_at": row.get("close_at"), "detail_url": row.get("detail_url"),
        "org_raw": notice_org,
        "org_names": [value for value in (notice_org, demand_org) if value],
        "org_role_titles": [role for value, role in ((notice_org, "NOTICE_ORGANIZATION"), (demand_org, "DEMAND_ORGANIZATION")) if value],
        "category_major": row.get("category"), "category_medium": row.get("service_division"),
        "region_raw": None, "region_concept_ids": None, "region_basis": row.get("region_basis"),
        # Contact person names are deliberately not copied. Phone/email values are only passed
        # to the existing classifier, which withholds ambiguous values from service output.
        "contact_phone_raw": row.get("contact_phone") if isinstance(row.get("contact_phone"), str) else None,
        "contact_text": "; ".join(contact_emails) if contact_emails else None,
        "attachments": {"count": len(raw_documents), "text_extracted": None, "preview_only": None,
                        "note": "공유 월별 입력에는 첨부 텍스트가 포함되지 않음"},
        "source_record_id": raw_id,
    }
    normalized, privacy_report = normalize_notice(common_row, issues)
    normalized["notice_type"] = "PROCUREMENT_BID"
    normalized["source_metadata"]["legacy_deadline_at"] = None
    normalized["source_metadata"]["source_specific"] = {"G2B": _g2b_source_metadata(row, issues)}
    for field in ("industry_limit_yn", "participation_limit_yn", "license_status", "licenses",
                  "region_status", "regions", "region_basis", "documents", "contract_method",
                  "award_method", "estimated_price", "notice_kind", "open_at", "is_cancelled"):
        normalized["field_availability"][f"source_metadata.source_specific.G2B.{field}"] = field_status(row, field)
    # Sanitize source-native fields as well as common fields before any file is written.
    ext = normalized["source_metadata"]["source_specific"]
    normalized["source_metadata"]["source_specific"] = scrub_record_text(sanitize_tree(ext, privacy_report), privacy_report)
    return normalized, privacy_report


def _atomic_jsonl_writer(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    stream = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent,
                                         delete=False, prefix=f".{path.name}.", suffix=".tmp")
    return stream, Path(stream.name)


def _write_jsonl_row(stream, row: dict[str, Any]) -> None:
    stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")


def normalize_g2b_archive(g2b_dir: Path, support_dir: Path, output_dir: Path,
                          *, schema_dir: Path | None = None) -> dict[str, Any]:
    """Create a new three-source normalized snapshot from shared G2B files and the frozen support snapshot."""
    g2b_dir, support_dir, output_dir = g2b_dir.resolve(), support_dir.resolve(), output_dir.resolve()
    if output_dir == g2b_dir or output_dir.is_relative_to(g2b_dir):
        raise ValueError("Output directory must be outside G2B input data")
    if output_dir == support_dir or output_dir.is_relative_to(support_dir):
        raise ValueError("Output directory must be outside the existing normalized support snapshot")
    schema_dir = schema_dir or ROOT / "schemas" / "support-data"
    notice_validator = load_validator(schema_dir / "support-notice-v1.schema.json")
    chunk_validator = load_validator(schema_dir / "support-chunk-v1.schema.json")
    base_notice_path, base_chunk_path = support_dir / "notices.jsonl", support_dir / "chunks.jsonl"
    if not base_notice_path.is_file() or not base_chunk_path.is_file():
        raise FileNotFoundError(f"Expected notices.jsonl and chunks.jsonl in {support_dir}")
    month_files = sorted(g2b_dir.glob("*/notices.jsonl"))
    if not month_files:
        raise FileNotFoundError(f"No monthly notices.jsonl files in {g2b_dir}")

    base_notices, base_issues = read_jsonl(base_notice_path)
    base_chunks, chunk_issues = read_jsonl(base_chunk_path)
    issues = [*base_issues, *chunk_issues]
    base_report_path = support_dir / "normalization_report.json"
    base_report = json.loads(base_report_path.read_text(encoding="utf-8")) if base_report_path.is_file() else {}
    notice_ids: set[str] = set()
    source_counts: Counter[str] = Counter()
    redactions: Counter[str] = Counter(base_report.get("privacy_redactions", {}))
    contacts_by_source: dict[str, Counter[str]] = {
        name: Counter(counts) for name, counts in base_report.get("contact_processing_by_source", {}).items()
    }
    contact_name_fields_omitted = 0
    executor_name_fields_omitted = 0

    output_dir.mkdir(parents=True, exist_ok=True)
    notice_path, chunk_path = output_dir / "notices.jsonl", output_dir / "chunks.jsonl"
    notice_stream, notice_temp = _atomic_jsonl_writer(notice_path)
    chunk_stream, chunk_temp = _atomic_jsonl_writer(chunk_path)
    try:
        for row in base_notices:
            row = dict(row)
            row["notice_type"] = "SUPPORT_PROGRAM"
            notice_id = row.get("notice_id")
            if not isinstance(notice_id, str) or notice_id in notice_ids:
                issues.append({"notice_id": notice_id, "issue": "DUPLICATE_OR_INVALID_NOTICE_ID"})
            else:
                notice_ids.add(notice_id)
            source = row.get("source", {}).get("source_system", "UNKNOWN")
            source_counts[f"notice:{source}"] += 1
            for message in schema_errors(row, notice_validator):
                issues.append({"notice_id": notice_id, "issue": "SCHEMA_VALIDATION", "detail": message})
            for finding in pii_findings(row):
                issues.append({"notice_id": notice_id, "issue": "PII_REMAINS_AFTER_SCRUB", "detail": finding})
            _write_jsonl_row(notice_stream, row)

        chunk_counts: Counter[str] = Counter()
        chunk_ids: set[str] = set()
        for row in base_chunks:
            chunk_id = row.get("chunk_id")
            if chunk_id in chunk_ids:
                issues.append({"chunk_id": chunk_id, "issue": "DUPLICATE_CHUNK_ID"})
            chunk_ids.add(chunk_id)
            if row.get("notice_id") not in notice_ids:
                issues.append({"chunk_id": row.get("chunk_id"), "issue": "CHUNK_WITHOUT_NOTICE"})
            chunk_counts[row.get("source_system", "UNKNOWN")] += 1
            for message in schema_errors(row, chunk_validator):
                issues.append({"chunk_id": row.get("chunk_id"), "issue": "SCHEMA_VALIDATION", "detail": message})
            for finding in pii_findings(row):
                issues.append({"chunk_id": row.get("chunk_id"), "issue": "PII_REMAINS_AFTER_SCRUB", "detail": finding})
            _write_jsonl_row(chunk_stream, row)
        monthly_counts: dict[str, int] = {}
        g2b_aux_counts = Counter()
        g2b_flag_counts = Counter()
        notice_date_min, notice_date_max = None, None
        g2b_count = 0
        for month_file in month_files:
            month = month_file.parent.name
            monthly_counts[month] = 0
            with month_file.open(encoding="utf-8") as stream:
                for line_number, line in enumerate(stream, 1):
                    if not line.strip():
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        issues.append({"file": month_file.name, "month": month, "line": line_number,
                                       "issue": "INVALID_JSONL", "raw_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest()})
                        continue
                    if not isinstance(raw, dict):
                        issues.append({"file": month_file.name, "month": month, "line": line_number,
                                       "issue": "NON_OBJECT_JSONL_RECORD", "raw_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest()})
                        continue
                    monthly_counts[month] += 1
                    g2b_count += 1
                    for field in ("licenses", "regions", "documents"):
                        value = raw.get(field)
                        if isinstance(value, list):
                            g2b_aux_counts[f"{field}_rows_nonempty"] += bool(value)
                            g2b_aux_counts[f"{field}_items"] += len(value)
                    for field in ("industry_limit_yn", "participation_limit_yn", "license_status", "region_status", "is_cancelled"):
                        g2b_flag_counts[f"{field}:{raw.get(field)}"] += 1
                    for field in ("contact_name", "executor_name", "contact_phone", "contact_email", "demand_contact_email"):
                        g2b_flag_counts[f"{field}:present"] += raw.get(field) not in (None, "")
                    date_value = raw.get("notice_at")
                    if isinstance(date_value, str) and date_value:
                        day = date_value[:10]
                        notice_date_min = min(notice_date_min, day) if notice_date_min else day
                        notice_date_max = max(notice_date_max, day) if notice_date_max else day
                    if raw.get("contact_name") not in (None, ""):
                        contact_name_fields_omitted += 1
                    if raw.get("executor_name") not in (None, ""):
                        executor_name_fields_omitted += 1

                    normalized, privacy_report = normalize_g2b_notice(raw, issues)
                    notice_id = normalized["notice_id"]
                    if notice_id in notice_ids:
                        issues.append({"notice_id": notice_id, "issue": "DUPLICATE_NOTICE_ID"})
                        continue
                    notice_ids.add(notice_id)
                    source_counts["notice:G2B"] += 1
                    contact_stats = contacts_by_source.setdefault("G2B", Counter())
                    contact_stats["contact_candidates_found"] += len(normalized["contacts"])
                    contact_stats["official_business_contacts_preserved"] += sum(c["classification"] == "OFFICIAL_BUSINESS" for c in normalized["contacts"])
                    contact_stats["personal_identifiers_redacted"] += sum(c["classification"] == "PERSONAL" for c in normalized["contacts"])
                    contact_stats["unclassified_contacts_queued"] += sum(c["classification"] == "UNCLASSIFIED" for c in normalized["contacts"])
                    redactions.update({"emails": privacy_report.email_count, "phones": privacy_report.phone_count,
                                       "url_tokens": privacy_report.url_token_count, "contextual_names": privacy_report.contextual_name_count,
                                       "ambiguous_contexts": privacy_report.ambiguous_context_count})
                    for message in schema_errors(normalized, notice_validator):
                        issues.append({"notice_id": notice_id, "issue": "SCHEMA_VALIDATION", "detail": message})
                    for finding in pii_findings(normalized):
                        issues.append({"notice_id": notice_id, "issue": "PII_REMAINS_AFTER_SCRUB", "detail": finding})
                    _write_jsonl_row(notice_stream, normalized)

        # Verify the shared monthly manifest and related flattened files against the records used.
        manifest_path = g2b_dir / "manifest.csv"
        manifest_mismatches = []
        manifest_rows = {}
        if manifest_path.is_file():
            with manifest_path.open(encoding="utf-8-sig", newline="") as stream:
                for item in csv.DictReader(stream):
                    manifest_rows[item.get("month", "")] = item
            for month, actual in monthly_counts.items():
                declared = manifest_rows.get(month, {}).get("notices.jsonl_rows")
                if declared is not None and int(declared) != actual:
                    manifest_mismatches.append({"month": month, "file": "notices.jsonl", "declared": int(declared), "actual": actual})
        else:
            issues.append({"issue": "G2B_MANIFEST_NOT_FOUND"})

        flat_counts = {}
        for filename in ("notices.csv", "licenses.csv", "regions.csv"):
            total = 0
            for csv_path in sorted(g2b_dir.glob(f"*/{filename}")):
                with csv_path.open(encoding="utf-8-sig", newline="") as stream:
                    total += sum(1 for _ in csv.DictReader(stream))
            flat_counts[filename] = total
        jsonl_license_items = g2b_aux_counts["licenses_items"]
        jsonl_region_items = g2b_aux_counts["regions_items"]
        if flat_counts.get("notices.csv") != g2b_count:
            manifest_mismatches.append({"file": "notices.csv", "declared": flat_counts.get("notices.csv"), "actual": g2b_count})
        if flat_counts.get("licenses.csv") != jsonl_license_items:
            manifest_mismatches.append({"file": "licenses.csv", "declared": flat_counts.get("licenses.csv"), "actual": jsonl_license_items})
        if flat_counts.get("regions.csv") != jsonl_region_items:
            manifest_mismatches.append({"file": "regions.csv", "declared": flat_counts.get("regions.csv"), "actual": jsonl_region_items})

        notice_stream.flush()
        chunk_stream.flush()
        notice_stream.close()
        chunk_stream.close()

        blocking = {"SCHEMA_VALIDATION", "PII_REMAINS_AFTER_SCRUB", "DUPLICATE_NOTICE_ID", "DUPLICATE_CHUNK_ID", "DUPLICATE_OR_INVALID_NOTICE_ID",
                    "INVALID_G2B_NOTICE_ID", "INVALID_G2B_FIELD_TYPE", "UNEXPECTED_G2B_SOURCE_SYSTEM", "CHUNK_WITHOUT_NOTICE",
                    "INVALID_JSONL", "NON_OBJECT_JSONL_RECORD", "INVALID_G2B_DOCUMENT_URL"}
        publishable = not any(issue.get("issue") in blocking for issue in issues)
        if publishable:
            notice_temp.replace(notice_path)
            chunk_temp.replace(chunk_path)
        else:
            notice_temp.unlink(missing_ok=True)
            chunk_temp.unlink(missing_ok=True)

        input_files = [base_notice_path, base_chunk_path, *month_files]
        if manifest_path.is_file():
            input_files.append(manifest_path)
        input_files.extend(sorted(g2b_dir.glob("*/notices.csv")))
        input_files.extend(sorted(g2b_dir.glob("*/licenses.csv")))
        input_files.extend(sorted(g2b_dir.glob("*/regions.csv")))
        counts_by_source = {source: {"notices": source_counts[f"notice:{source}"],
                                     "chunks": chunk_counts[source]}
                            for source in ("BIZINFO", "KSTARTUP", "G2B")}
        totals = {"notices": sum(value["notices"] for value in counts_by_source.values()),
                  "chunks": len(base_chunks), "issues": len(issues)}
        report = {
            "normalizer_version": NORMALIZER_VERSION, "run_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "input_sources": {"support_snapshot": report_input_path(base_notice_path),
                              "support_report": report_input_path(base_report_path) if base_report_path.is_file() else None,
                              "g2b_monthly_dir": report_input_path(g2b_dir / "manifest.csv")},
            "input_sha256": {report_input_path(path): sha256_file(path) for path in input_files},
            "input_counts": {"support_notices": len(base_notices), "support_chunks": len(base_chunks),
                             "g2b_notices": g2b_count, "g2b_chunks": 0, "g2b_notices_by_month": monthly_counts,
                             "g2b_related_items": dict(g2b_aux_counts)},
            "g2b_notice_date_range": {"earliest": notice_date_min, "latest": notice_date_max},
            "g2b_flat_file_rows": flat_counts,
            "g2b_list_vs_flat_file_mismatches": manifest_mismatches,
            "g2b_field_value_counts": dict(g2b_flag_counts),
            "g2b_condition_candidate_counts": {
                "license_notice_count": g2b_aux_counts["licenses_rows_nonempty"],
                "license_item_count": g2b_aux_counts["licenses_items"],
                "region_notice_count": g2b_aux_counts["regions_rows_nonempty"],
                "region_item_count": g2b_aux_counts["regions_items"],
                "industry_limit_yes": g2b_flag_counts["industry_limit_yn:Y"],
                "participation_limit_yes": g2b_flag_counts["participation_limit_yn:Y"],
                "natural_language_eligibility_records": 0,
                "exclusion_text_records": 0,
                "preference_or_score_text_records": 0,
            },
            "output_counts": totals, "output_counts_by_source": counts_by_source,
            "duplicate_notice_ids": sum(i.get("issue") in {"DUPLICATE_NOTICE_ID", "DUPLICATE_OR_INVALID_NOTICE_ID"} for i in issues),
            "duplicate_chunk_ids": sum(i.get("issue") == "DUPLICATE_CHUNK_ID" for i in issues),
            "chunks_without_notice": sum(c.get("notice_id") not in notice_ids for c in base_chunks),
            "contact_processing_by_source": {k: dict(v) for k, v in contacts_by_source.items()},
            "unclassified_contact_review_coverage": {
                **base_report.get("unclassified_contact_review_coverage", {}),
                "G2B": 1.0,
            },
            "g2b_contact_name_fields_omitted": contact_name_fields_omitted,
            "g2b_executor_name_fields_omitted": executor_name_fields_omitted,
            "g2b_contact_phone_fields_withheld_for_review": g2b_flag_counts["contact_phone:present"],
            "privacy_redactions": dict(redactions),
            "schema_validation_errors": sum(i.get("issue") == "SCHEMA_VALIDATION" for i in issues),
            "privacy_residual_findings": sum(i.get("issue") == "PII_REMAINS_AFTER_SCRUB" for i in issues),
            "attachment_downloads_performed": False, "attachment_text_extraction_performed": False,
            "condition_extraction_performed": False, "database_writes_performed": False,
            "publishable": publishable, "output_files_updated": publishable,
        }
        write_jsonl(output_dir / "normalization_issues.jsonl", issues)
        (output_dir / "normalization_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report
    except Exception:
        if not notice_stream.closed:
            notice_stream.close()
        if not chunk_stream.closed:
            chunk_stream.close()
        notice_temp.unlink(missing_ok=True)
        chunk_temp.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", default=DEFAULT_SNAPSHOT, help="cleaned snapshot directory name (default: 20261124)")
    parser.add_argument("--input-dir", type=Path, help="override data/cleaned/<snapshot>")
    parser.add_argument("--output-dir", type=Path, help="override data/normalized/v1/<snapshot>")
    parser.add_argument("--schema-dir", type=Path, default=ROOT / "schemas" / "support-data")
    parser.add_argument("--g2b-monthly-dir", type=Path, help="normalize existing data/g2b_monthly inputs and combine with a frozen normalized support snapshot")
    parser.add_argument("--support-normalized-dir", type=Path, help="existing BIZINFO/K-Startup normalized snapshot used with --g2b-monthly-dir")
    args = parser.parse_args(argv)
    if args.g2b_monthly_dir:
        if not args.support_normalized_dir:
            parser.error("--support-normalized-dir is required with --g2b-monthly-dir")
        output_dir = args.output_dir or (OUTPUT_BASE / "20261125_g2b")
        report = normalize_g2b_archive(args.g2b_monthly_dir, args.support_normalized_dir, output_dir,
                                       schema_dir=args.schema_dir)
        print(json.dumps({"output_dir": str(output_dir), **report}, ensure_ascii=False, indent=2))
        return 0 if report["publishable"] else 1
    if args.support_normalized_dir:
        parser.error("--support-normalized-dir is only valid with --g2b-monthly-dir")
    input_dir = args.input_dir or (ROOT / "data" / "cleaned" / args.snapshot)
    output_dir = args.output_dir or (OUTPUT_BASE / args.snapshot)
    report = normalize_snapshot(input_dir, output_dir, schema_dir=args.schema_dir)
    print(json.dumps({"output_dir": str(output_dir), **report}, ensure_ascii=False, indent=2))
    return 0 if report["publishable"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
