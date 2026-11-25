"""Shared safety policies for public-notice ingestion and retrieval."""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass
from typing import Any, Iterable


EMAIL_RE = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
URL_TOKEN_RE = re.compile(r"(?i)([?&](?:downloadtoken|token|access_token|accesstoken|signature|x-amz-signature|authorization)=)[^&\s#]+")
PHONE_RE = re.compile(r"(?<!\d)(?:(?:\+82[- .]?)?0\d{1,2}[() .-]?\d{3,4}[- .]?\d{4}|1[568]\d{2}[- .]?\d{4})(?!\d)")
CONTACT_CONTEXT_RE = re.compile(
    r"(?P<label>담당자(?:명)?|담당|문의(?:처|자)?|연락처|접수문의|사업문의|신청문의)"
    r"\s*[:：]\s*(?P<name>[가-힣]{2,4})(?=\s*(?:\(|,|/|·|\n|$))"
)
CONTACT_UNKNOWN_RE = re.compile(r"(?P<label>담당자(?:명)?|담당|문의처|문의자|연락처|접수문의|사업문의|신청문의)\s*[:：]\s*(?P<tail>[^\r\n]{1,160})")
PERSON_KEYS = {"담당자", "담당자명", "contact_name", "manager_name", "person_name", "문의자"}
SEARCH_APPROVED_STATES = {"source_verified", "approved"}
REGION_STATUS = {"nationwide", "confirmed", "unknown", "review_required"}


@dataclass
class PrivacyReport:
    email_count: int = 0
    phone_count: int = 0
    url_token_count: int = 0
    contextual_name_count: int = 0
    ambiguous_context_count: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.email_count or self.phone_count or self.contextual_name_count)


def scrub_text(value: str, report: PrivacyReport | None = None) -> str:
    report = report or PrivacyReport()

    def mask(pattern: re.Pattern[str], text: str, attr: str) -> str:
        count = 0
        def replacement(_match: re.Match[str]) -> str:
            nonlocal count
            count += 1
            return "[개인정보 마스킹]"
        result = pattern.sub(replacement, text)
        setattr(report, attr, getattr(report, attr) + count)
        return result

    value = mask(EMAIL_RE, value, "email_count")
    value = mask(PHONE_RE, value, "phone_count")
    def mask_url_token(match: re.Match[str]) -> str:
        report.url_token_count += 1
        return match.group(1) + "[URL TOKEN REDACTED]"
    value = URL_TOKEN_RE.sub(mask_url_token, value)
    def mask_contact(match: re.Match[str]) -> str:
        report.contextual_name_count += 1
        return f"{match.group('label')}: [이름 마스킹]"
    value = CONTACT_CONTEXT_RE.sub(mask_contact, value)
    # Remove ambiguous contact-field contents as a whole; do not guess names.
    def mask_ambiguous_contact(match: re.Match[str]) -> str:
        if "[이름 마스킹]" in match.group("tail") or "[개인정보 마스킹]" in match.group("tail"):
            return match.group(0)
        report.ambiguous_context_count += 1
        return f"{match.group('label')}: [문의 정보 삭제]"
    value = CONTACT_UNKNOWN_RE.sub(mask_ambiguous_contact, value)
    return value


def sanitize_tree(value: Any, report: PrivacyReport | None = None, *, key: str = "") -> Any:
    """Recursively mask common PII; strings under person-name keys are masked whole."""
    report = report or PrivacyReport()
    if isinstance(value, dict):
        clean = {}
        for child_key, child in value.items():
            if str(child_key).casefold() in PERSON_KEYS and child:
                report.contextual_name_count += 1
                clean[child_key] = "[이름 마스킹]"
            else:
                clean[child_key] = sanitize_tree(child, report, key=str(child_key))
        return clean
    if isinstance(value, list):
        return [sanitize_tree(item, report, key=key) for item in value]
    if isinstance(value, tuple):
        return tuple(sanitize_tree(item, report, key=key) for item in value)
    if isinstance(value, set):
        return {sanitize_tree(item, report, key=key) for item in value}
    if isinstance(value, str):
        if key.casefold().endswith("_hash"):
            return value
        return scrub_text(value, report)
    return copy.deepcopy(value)


def condition_search_approved(record: dict[str, Any]) -> bool:
    """Missing/unknown review state is denied by default."""
    return (record.get("review_status") == "approved" and bool(record.get("reviewed_at"))
            and bool(record.get("reviewed_by")) and record.get("review_required") is False)


def searchable_text(api_text: str | None, conditions: Iterable[dict[str, Any]]) -> str:
    """Keep trusted source text and explicitly reviewed conditions only."""
    parts = [api_text.strip()] if api_text and api_text.strip() else []
    parts.extend(str(c.get("text", "")).strip() for c in conditions if condition_search_approved(c) and c.get("text"))
    return "\n\n".join(parts)


def scope_matches(region_status: str | None, scope_region_ids: Iterable[str],
                  business_region_ancestors: Iterable[str] | None,
                  operator: str | None = "OR") -> bool:
    """Unknown scopes never match; nationwide only matches when explicitly confirmed."""
    if region_status == "nationwide":
        return True
    if region_status != "confirmed" or not business_region_ancestors:
        return False
    scopes, ancestors = set(scope_region_ids), set(business_region_ancestors)
    return scopes.issubset(ancestors) if operator == "AND" else bool(scopes.intersection(ancestors))


def search_row_allowed(row: dict[str, Any], *, business_region_ancestors: Iterable[str] | None = None) -> bool:
    if row.get("privacy_status") != "cleared":
        return False
    if row.get("search_review_status") not in SEARCH_APPROVED_STATES:
        return False
    if business_region_ancestors is None:
        return True
    return scope_matches(row.get("region_scope_status"), row.get("region_scope_ids", []),
                         business_region_ancestors, row.get("region_scope_operator", "OR"))


def normalize_region_scope(explicit_text: str | None, region_ids: Iterable[str], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    """Only explicitly evidenced nationwide or mapped region text creates a scope."""
    text = (explicit_text or "").strip()
    ids = sorted(set(region_ids))
    if text == "전국" or re.search(r"(?:지원|신청|모집)\s*대상\s*(?:지역은\s*)?전국|전국\s*(?:소재|지역|기업).{0,12}(?:신청|지원|대상)", text):
        return {"status": "nationwide", "region_ids": [], "operator": "OR", "evidence": evidence}
    if ids and evidence:
        return {"status": "confirmed", "region_ids": ids, "operator": "OR", "evidence": evidence}
    return {"status": "unknown", "region_ids": [], "operator": None, "evidence": evidence}
