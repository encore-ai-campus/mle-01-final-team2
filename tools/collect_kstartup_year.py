"""Collect and structure K-Startup announcements for a publication-date window.

The public API currently documents application-window filters, not a publication
date filter. This collector therefore retrieves every API page and filters only
when an explicit publication date is present in the returned source record.
Unknown publication dates are retained in a separate JSONL for review.

Run: .venv/Scripts/python.exe tools/collect_kstartup_year.py
Options: --start YYYY-MM-DD --end YYYY-MM-DD --no-details
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "kstartup"
RAW = BASE / "raw"
DOCS = BASE / "documents"
PROCESSED = BASE / "processed"
REPORTS = BASE / "reports"
API_URL = "https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01"
PAGE_SIZE = 100
SEOUL = timezone(timedelta(hours=9))
DATE_FIELDS = ("pbanc_reg_dt", "pbanc_reg_ymd", "pbanc_regist_dt", "reg_dt", "reg_ymd")
SENSITIVE_KEYS = {"servicekey", "token", "access_token", "downloadtoken", "signature", "authorization"}
PII_PATTERNS = [
    re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    re.compile(r"(?<!\d)(?:\+?82[- .]?)?(?:0\d{1,2})[- .]?\d{3,4}[- .]?\d{4}(?!\d)"),
]


def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def redact_url(value: str) -> str:
    p = urlsplit(value)
    query = [(k, "[REDACTED]" if k.casefold() in SENSITIVE_KEYS else v) for k, v in parse_qsl(p.query, keep_blank_values=True)]
    return urlunsplit((p.scheme, p.netloc, p.path, urlencode(query), p.fragment))


def scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        if value.lower().startswith(("http://", "https://")):
            return redact_url(value)
        for pattern in PII_PATTERNS:
            value = pattern.sub("[REDACTED_CONTACT]", value)
    return value


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    text = re.sub(r"\D", "", str(value))[:8]
    if len(text) != 8:
        return None
    try:
        return datetime.strptime(text, "%Y%m%d").date()
    except ValueError:
        return None


def extract_rows(payload: Any) -> list[dict[str, Any]]:
    data = payload.get("data", []) if isinstance(payload, dict) else payload
    if isinstance(data, dict):
        data = data.get("item", data.get("data", data.get("items", [])))
    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ValueError("Unexpected API response shape")
    return [r for r in data if isinstance(r, dict)]


def request_page(session: requests.Session, key: str, page: int) -> dict[str, Any]:
    params = {"serviceKey": key, "page": page, "perPage": PAGE_SIZE, "returnType": "json"}
    last: Exception | None = None
    for attempt in range(5):
        try:
            response = session.get(API_URL, params=params, timeout=(10, 45))
            response.raise_for_status()
            body = response.json()
            if not isinstance(body, dict):
                raise ValueError("API response is not a JSON object")
            return body
        except Exception as exc:  # do not retain request URLs, which contain the API key
            status = getattr(getattr(exc, "response", None), "status_code", None)
            last = RuntimeError(f"request failed ({type(exc).__name__}, HTTP {status})")
            if attempt < 4:
                time.sleep(min(2 ** attempt, 16))
    assert last is not None
    raise last


def date_status(row: dict[str, Any], start: date, end: date) -> tuple[str, date | None, str | None]:
    present = [(field, parse_date(row.get(field))) for field in DATE_FIELDS if row.get(field) not in (None, "")]
    valid = [(field, value) for field, value in present if value]
    if not valid:
        return "publication_date_unavailable", None, None
    # If multiple explicit registration-like fields disagree, do not silently choose.
    if len({v for _, v in valid}) > 1:
        return "publication_date_conflict", None, ",".join(f for f, _ in valid)
    field, value = valid[0]
    assert value
    return ("in_window" if start <= value <= end else "outside_window"), value, field


def condition_records(row: dict[str, Any], source_url: str) -> list[dict[str, Any]]:
    mapping = {
        "eligibility": "aply_trgt_ctnt", "exclusions": "aply_excl_trgt_ctnt",
        "support_details": "support_ctnt", "application_method": "aply_mthd_onli_rcpt_istc",
        "region": "supt_regin", "business_age": "biz_enyy", "representative_age": "biz_trgt_age",
        "evaluation_criteria": "eval_method",
    }
    result = []
    for typ, field in mapping.items():
        raw = row.get(field)
        result.append({"condition_type": typ, "raw_text": scrub(raw) if raw else None,
                       "normalized_value": None, "source_type": "api",
                       "source_url": source_url, "page_number": None,
                       "review_status": "extracted_needs_review" if raw else "not_provided"})
    return result


def structure(row: dict[str, Any], start: date, end: date) -> tuple[dict[str, Any], dict[str, Any]]:
    announcement_id = str(row.get("pbanc_sn") or "").strip()
    detail = str(row.get("detl_pg_url") or "").strip()
    source_url = redact_url(detail) if detail else None
    status, pubdate, date_field = date_status(row, start, end)
    app_start = parse_date(row.get("pbanc_rcpt_bgng_dt"))
    app_end = parse_date(row.get("pbanc_rcpt_end_dt"))
    clean = {
        "announcement_id": announcement_id or None,
        "title": scrub(row.get("biz_pbanc_nm") or row.get("intg_pbanc_biz_nm")),
        "organization": scrub(row.get("pbanc_ntrp_nm") or row.get("sprv_inst")),
        "published_date": pubdate.isoformat() if pubdate else None,
        "publication_date_status": status,
        "publication_date_source_field": date_field,
        "application_start": app_start.isoformat() if app_start else None,
        "application_end": app_end.isoformat() if app_end else None,
        "region": scrub(row.get("supt_regin")), "business_age": scrub(row.get("biz_enyy")),
        "industry": scrub(row.get("supt_biz_clsfc")), "company_type": None,
        "representative_age": scrub(row.get("biz_trgt_age")),
        "eligibility": scrub(row.get("aply_trgt_ctnt")),
        "exclusions": scrub(row.get("aply_excl_trgt_ctnt")),
        "support_details": scrub(row.get("support_ctnt") or row.get("pbanc_ctnt")),
        "support_amount": None,
        "application_method": scrub(row.get("aply_mthd_onli_rcpt_istc") or row.get("aply_mthd_etc_istc")),
        "evaluation_criteria": scrub(row.get("eval_method")),
        "source_url": source_url,
        "evidence": condition_records(row, source_url or ""),
        "application_status": scrub(row.get("rcrt_prgs_yn")),
        "attachments": [], "api_source_fields": scrub(row),
    }
    return clean, {"announcement_id": announcement_id or None, "source_url": source_url,
                   "detail_status": "not_attempted", "attachment_status": "not_attempted", "error": None}


def fetch_detail(session: requests.Session, item: dict[str, Any], timeout: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Fetch public detail HTML and discover/download linked public documents."""
    url = item.get("source_url")
    if not url:
        item["detail_status"] = "missing_url"
        return item, []
    try:
        from bs4 import BeautifulSoup
        response = session.get(url, timeout=(10, timeout))
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        text = "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())
        item["detail_status"] = "success"
        item["detail_text"] = scrub(text)
        links = []
        for a in soup.select("a[href]"):
            href = requests.compat.urljoin(response.url, a.get("href", ""))
            name = a.get_text(" ", strip=True) or Path(urlsplit(href).path).name
            if re.search(r"\.(pdf|hwp|hwpx|docx?|xlsx?|zip)(?:$|[?#])", href, re.I):
                links.append({"url": redact_url(href), "name": scrub(name)})
        item["attachment_status"] = "discovered" if links else "none_found"
        item["attachments"] = links
        downloaded = []
        for link in links:
            try:
                file_response = session.get(link["url"], timeout=(10, timeout))
                file_response.raise_for_status()
                suffix = Path(urlsplit(link["url"]).path).suffix.lower() or ".bin"
                digest = hashlib.sha256((item.get("announcement_id", "") + link["url"]).encode()).hexdigest()[:16]
                target = DOCS / digest / ("source" + suffix)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(file_response.content)
                downloaded.append({**link, "local_path": str(target.relative_to(ROOT)),
                                   "size_bytes": len(file_response.content), "download_status": "success"})
            except Exception as exc:
                downloaded.append({**link, "download_status": "failed", "error": type(exc).__name__})
        item["attachments"] = downloaded
        return item, downloaded
    except Exception as exc:
        item["detail_status"] = "failed"
        item["attachment_status"] = "not_attempted"
        item["error"] = f"{type(exc).__name__}: {exc}"
        return item, []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2025-11-24")
    parser.add_argument("--end", default="2026-11-24")
    parser.add_argument("--no-details", action="store_true")
    parser.add_argument("--detail-limit", type=int, default=0, help="0 means all in-window announcements")
    parser.add_argument("--from-saved", action="store_true", help="rebuild structured outputs without re-querying API")
    parser.add_argument("--refresh", action="store_true", help="restart API pagination from page 1 and preserve repeated/unkeyed rows separately")
    args = parser.parse_args()
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start > end:
        parser.error("--start must be on or before --end")
    load_dotenv(ROOT / ".env", override=False)
    key = os.getenv("KSTARTUP_SERVICE_KEY") or os.getenv("G2B_SERVICE_KEY")
    if not key:
        print("Missing KSTARTUP_SERVICE_KEY (or legacy G2B_SERVICE_KEY)", file=sys.stderr)
        return 2
    for path in (RAW, DOCS, PROCESSED, REPORTS):
        path.mkdir(parents=True, exist_ok=True)

    raw_path = RAW / "kstartup_raw.jsonl"
    raw_by_id: dict[str, dict[str, Any]] = {}
    if raw_path.exists():
        for line in raw_path.read_text(encoding="utf-8").splitlines():
            try:
                obj = json.loads(line)
                if obj.get("pbanc_sn"):
                    raw_by_id[str(obj["pbanc_sn"])] = obj
            except json.JSONDecodeError:
                continue
    errors: list[dict[str, Any]] = []
    page_stats: list[dict[str, Any]] = []
    total_reported = None
    pages_seen: set[int] = set()
    prior_log_path = RAW / "kstartup_collection_log.json"
    if prior_log_path.exists() and not args.refresh:
        try:
            prior_log = json.loads(prior_log_path.read_text(encoding="utf-8"))
            page_stats = prior_log.get("pages", [])
            pages_seen = {int(p["page"]) for p in page_stats if p.get("page") is not None}
            errors = prior_log.get("errors", [])
            total_reported = prior_log.get("reported_total_count")
        except (OSError, ValueError, TypeError):
            pass
    duplicate_path = RAW / "kstartup_duplicate_or_unkeyed_rows.jsonl"
    duplicate_rows: list[dict[str, Any]] = []
    if duplicate_path.exists() and not args.refresh:
        for line in duplicate_path.read_text(encoding="utf-8").splitlines():
            try:
                duplicate_rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if args.refresh:
        raw_by_id = {}
        duplicate_rows = []
    start_page = 1 if args.refresh else max(pages_seen, default=0) + 1
    already_complete = total_reported is not None and sum(int(p.get("rows", 0)) for p in page_stats) >= int(total_reported)
    if already_complete:
        start_page = 10001
    session = requests.Session()
    session.headers.update({"User-Agent": "KStartupResearchCollector/1.0 (public OpenAPI)"})
    try:
        for page in range(start_page, start_page if args.from_saved else 10001):
            try:
                payload = request_page(session, key, page)
                rows = extract_rows(payload)
                total_reported = payload.get("totalCount", total_reported)
                pages_seen.add(page)
                new_ids = 0
                for row in rows:
                    rid = str(row.get("pbanc_sn") or "").strip()
                    if rid and rid not in raw_by_id:
                        new_ids += 1
                        raw_by_id[rid] = scrub(row)
                    else:
                        duplicate_rows.append({"source_page": page, "reason": "missing_announcement_id" if not rid else "repeated_announcement_id", "record": scrub(row)})
                page_stats.append({"page": page, "rows": len(rows), "new_unique_ids": new_ids,
                                   "retrieved_at": datetime.now(SEOUL).isoformat()})
                write_jsonl(raw_path, list(raw_by_id.values()))
                write_jsonl(duplicate_path, duplicate_rows)
                write_json(RAW / "kstartup_collection_log.json", {
                    "updated_at": datetime.now(SEOUL).isoformat(), "last_completed_page": page,
                    "reported_total_count": total_reported, "unique_records_saved": len(raw_by_id),
                    "pages": page_stats, "errors": errors,
                })
                if not rows or (len(rows) < PAGE_SIZE) or (total_reported is not None and len(raw_by_id) >= int(total_reported)):
                    break
                time.sleep(0.2)
            except Exception as exc:
                errors.append({"page": page, "error": f"{type(exc).__name__}: {exc}", "at": datetime.now(SEOUL).isoformat()})
                write_json(RAW / "kstartup_collection_log.json", {
                    "updated_at": datetime.now(SEOUL).isoformat(), "last_completed_page": max(pages_seen, default=0),
                    "reported_total_count": total_reported, "unique_records_saved": len(raw_by_id),
                    "pages": page_stats, "errors": errors,
                })
                if len(errors) >= 5:
                    break
                time.sleep(min(2 ** len(errors), 16))
    except KeyboardInterrupt:
        pass

    # Preserve undated/conflicting records separately; never substitute receipt dates.
    clean, undated, outside = [], [], []
    seen = set()
    for row in raw_by_id.values():
        rid = str(row.get("pbanc_sn") or "").strip()
        if not rid or rid in seen:
            continue
        seen.add(rid)
        item, detail = structure(row, start, end)
        if item["publication_date_status"] == "in_window":
            clean.append(item)
        elif item["publication_date_status"] == "outside_window":
            outside.append(item)
        else:
            undated.append(item)
    write_jsonl(PROCESSED / "kstartup_cleaned.jsonl", clean)
    write_jsonl(PROCESSED / "kstartup_publication_date_unavailable.jsonl", undated)
    write_jsonl(PROCESSED / "kstartup_conditions.jsonl", [
        {"announcement_id": x["announcement_id"], "conditions": x["evidence"], "source_url": x["source_url"]} for x in clean
    ])

    detail_log = []
    if not args.no_details and clean:
        candidates = clean[:args.detail_limit] if args.detail_limit > 0 else clean
        detailed = []
        for index, item in enumerate(candidates, start=1):
            log, _ = fetch_detail(session, {"announcement_id": item["announcement_id"], "source_url": item["source_url"]}, 30)
            # Full detail kept in a separate raw detail bundle; only source-linked fields are exposed here.
            item["detail_status"] = log.get("detail_status")
            item["attachments"] = log.get("attachments", [])
            detail_log.append({k: log.get(k) for k in ("announcement_id", "source_url", "detail_status", "attachment_status", "error", "attachments")})
            if log.get("detail_text"):
                detailed.append({"announcement_id": item["announcement_id"], "source_url": item["source_url"], "text": log["detail_text"]})
            if index % 25 == 0:
                write_jsonl(RAW / "kstartup_detail_pages.jsonl", detailed)
                write_jsonl(PROCESSED / "kstartup_cleaned.jsonl", clean)
            time.sleep(0.25)
        write_jsonl(RAW / "kstartup_detail_pages.jsonl", detailed)
        write_jsonl(PROCESSED / "kstartup_cleaned.jsonl", clean)
    write_json(RAW / "kstartup_api_metadata.json", {
        "endpoint": API_URL, "dataset_documentation": "https://www.data.go.kr/data/15125364/openapi.do",
        "collected_at": datetime.now(SEOUL).isoformat(), "requested_date_window": [start.isoformat(), end.isoformat()],
        "date_basis": "publication_date", "page_size": PAGE_SIZE, "pages_completed": sorted(pages_seen),
        "reported_total_count": total_reported, "unique_id_count": len(seen),
        "repeated_or_unkeyed_rows": len(duplicate_rows),
        "source_fields_observed": sorted({k for r in raw_by_id.values() for k in r}),
        "date_fields_checked": list(DATE_FIELDS), "documented_api_filters": [
            "pbanc_rcpt_bgng_dt::GTE (application receipt start)", "pbanc_rcpt_end_dt::LTE (application receipt end)",
            "rcrt_prgs_yn::EQ (recruitment status)"],
        "publication_date_filter_documented": False,
    })

    def present(field: str) -> int:
        return sum(bool(x.get(field)) for x in clean)
    api_rows_retrieved = sum(int(p.get("rows", 0)) for p in page_stats)
    summary = {
        "window": [start.isoformat(), end.isoformat()], "api_reported_total_count": total_reported,
        "api_rows_retrieved": api_rows_retrieved,
        "unique_api_records": len(seen), "pages_completed": len(pages_seen),
        "repeated_or_unkeyed_rows_preserved": len(duplicate_rows),
        "in_window_publication_date_records": len(clean), "out_of_window_records": len(outside),
        "publication_date_unavailable_or_conflicting": len(undated),
        "details_attempted": len(detail_log), "detail_success": sum(x.get("detail_status") == "success" for x in detail_log),
        "attachments_downloaded": sum(a.get("download_status") == "success" for x in detail_log for a in x.get("attachments", [])),
        "collection_errors": [] if already_complete else errors, "fields_present_in_window": {f: {"count": present(f), "rate": round(present(f)/len(clean), 4) if clean else None}
          for f in ("region", "business_age", "eligibility", "exclusions", "support_details", "support_amount", "evaluation_criteria")},
        "limitations": ["공식 API 문서는 등록일 필터와 등록일 응답 필드를 명시하지 않습니다.",
                        "등록일 확인 불가 레코드는 접수 시작일로 대체하지 않았으며 별도 JSONL로 분리했습니다.",
                        "PDF/HWP 텍스트 추출 및 수동 검증은 수행하지 않았습니다."]
    }
    write_json(REPORTS / "collection_summary.json", summary)
    write_jsonl(PROCESSED / "kstartup_chunks.jsonl", [])  # no unverified source text is made searchable
    with (REPORTS / "extraction_failures.csv").open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["announcement_id", "source_url", "detail_status", "attachment_status", "error"])
        writer.writeheader()
        writer.writerows(detail_log)
    md = ["# K-Startup 최근 1년 수집 요약", "", f"- 기준 기간: {start} ~ {end} (양 끝 포함)",
          f"- API reported totalCount: {total_reported}", f"- 페이지 응답 행 합계: {api_rows_retrieved}",
          f"- ID 중복 제거 후 보관 레코드: {len(seen)}",
          f"- 등록일 확인 및 기간 내: {len(clean)}", f"- 기간 외: {len(outside)}",
          f"- 등록일 미확인/충돌: {len(undated)}", f"- 상세 페이지 성공: {summary['detail_success']} / {summary['details_attempted']}",
          f"- 첨부 다운로드 성공: {summary['attachments_downloaded']}", f"- API 페이지 오류: {len(summary['collection_errors'])}", "",
          "## 제한 및 주의", "", *[f"- {x}" for x in summary["limitations"]], "",
          "## 산출물", "", "- `raw/kstartup_raw.jsonl`: API 원본 레코드(공개 토큰 및 연락처 패턴 제거)",
          "- `processed/kstartup_cleaned.jsonl`: 등록일로 기간 확인된 공고만 포함",
          "- `processed/kstartup_publication_date_unavailable.jsonl`: 등록일이 없거나 충돌하는 공고",
          "- `processed/kstartup_conditions.jsonl`: 출처 연결 조건 필드", "- `processed/kstartup_chunks.jsonl`: 검증 가능한 문서가 없어 현재 비어 있음"]
    (REPORTS / "collection_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    field_map = {
        "지역": "supt_regin", "업력": "biz_enyy", "신청 자격": "aply_trgt_ctnt",
        "신청 제외": "aply_excl_trgt_ctnt", "지원 내용": "support_ctnt",
        "평가 기준": "eval_method", "공고 등록일": "pbanc_reg_dt",
    }
    field_lines = []
    for label, field in field_map.items():
        count = sum(bool(r.get(field)) for r in raw_by_id.values())
        rate = count / len(raw_by_id) if raw_by_id else 0
        field_lines.append(f"| {label} (`{field}`) | {count:,} | {rate:.1%} |")
    quality = ["# K-Startup 데이터 품질 보고서", "", f"- API 응답 레코드 수 합계: {api_rows_retrieved:,}",
               f"- 공고 ID로 보관된 고유 레코드: {len(seen):,}",
               f"- ID 중복/누락 원본 행 별도 보존: {len(duplicate_rows):,}",
               f"- 요청 기간 등록일 확인 가능: {len(clean):,}",
               f"- 등록일 확인 불가/충돌: {len(undated):,}", "",
               "## 필드 보유율 (전체 고유 ID 레코드 기준)", "",
               "| 항목 | 보유 건수 | 보유율 |", "|---|---:|---:|", *field_lines, "",
               "## 검수", "", "- 날짜 범위 밖 포함 여부: 등록일 필드가 없어 판정 불가. 접수 시작일로 대체하지 않음.",
               "- 시작일/종료일 관계: API 접수 시작·종료 필드가 존재하는 경우에만 별도 후속 검증 필요.",
               "- 첨부파일: 날짜 범위 공고를 확정할 수 없어 수집 미실행.",
               "- PDF/HWP 추출 및 원문 대조: 미실행.",
               "- 개인정보: 공개 산출물 텍스트에서 이메일·전화번호 형식과 민감 URL 쿼리 값을 마스킹.",
               "- 검색 청크: 검증된 공고문 근거가 없어 0건 생성.", ""]
    (REPORTS / "data_quality_report.md").write_text("\n".join(quality), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if already_complete or not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
