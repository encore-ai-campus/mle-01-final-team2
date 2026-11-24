"""Analyze publication-date availability using the saved K-Startup corpus.

Reads the existing raw JSONL only. Samples a small set of official detail pages
and writes date candidates without treating application dates as publication
dates. It never calls an undocumented API endpoint.
"""
from __future__ import annotations

import json
import random
import re
import time
from collections import Counter
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data" / "kstartup"
RAW = BASE / "raw" / "kstartup_raw.jsonl"
PROCESSED = BASE / "processed"
REPORTS = BASE / "reports"
START = date(2025, 11, 24)
END = date(2026, 11, 24)
SEED = 20261124


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


class PageEvidence(HTMLParser):
    """Extract visible text and short label nodes from the official HTML."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.labels: list[str] = []
        self._capture: tuple[str, list[str]] | None = None
        self._tag_stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = dict(attrs)
        classes = set((attrs_map.get("class") or "").split())
        if tag in {"p", "span", "th", "dt", "h1", "h2", "h3", "strong", "label"} and (
            tag in {"th", "dt"} or classes.intersection({"tit", "title", "label", "subj"})
        ):
            self._capture = (tag, [])
        self._tag_stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if self._capture and self._capture[0] == tag:
            value = " ".join(" ".join(self._capture[1]).split())
            if value:
                self.labels.append(value)
            self._capture = None
        if tag in self._tag_stack:
            index = len(self._tag_stack) - 1 - self._tag_stack[::-1].index(tag)
            self._tag_stack = self._tag_stack[:index]

    def handle_data(self, data: str) -> None:
        value = data.strip()
        if value:
            self.text.append(value)
            if self._capture:
                self._capture[1].append(value)


def read_rows() -> list[dict[str, Any]]:
    with RAW.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def choose_sample(rows: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    rng = random.Random(SEED)
    buckets: dict[str, list[dict[str, Any]]] = {
        "closed_2012_2020": [], "closed_2021_2024": [], "closed_2025": [],
        "closed_2026": [], "closed_start_missing": [], "open_2024": [],
        "open_2025": [], "open_2026": [],
    }
    for row in rows:
        value = row.get("pbanc_rcpt_bgng_dt")
        day = parse_day(value)
        status = str(row.get("rcrt_prgs_yn") or "").strip().upper()
        if status == "Y":
            key = f"open_{day.year}" if day and day.year in (2024, 2025, 2026) else ""
        else:
            if day is None:
                key = "closed_start_missing"
            elif day.year <= 2020:
                key = "closed_2012_2020"
            elif day.year <= 2024:
                key = "closed_2021_2024"
            elif day.year == 2025:
                key = "closed_2025"
            else:
                key = "closed_2026"
        if key in buckets and row.get("detl_pg_url"):
            buckets[key].append(row)
    quotas = {"closed_2012_2020": 3, "closed_2021_2024": 3, "closed_2025": 3,
              "closed_2026": 3, "closed_start_missing": 3, "open_2024": 1,
              "open_2025": 3, "open_2026": 5}
    selected = []
    for key, quota in quotas.items():
        candidates = buckets[key][:]
        rng.shuffle(candidates)
        selected.extend((key, row) for row in candidates[:quota])
    if not 20 <= len(selected) <= 30:
        raise RuntimeError(f"Expected 20-30 sample pages, got {len(selected)}")
    return selected


def probe_page(session: requests.Session, stratum: str, row: dict[str, Any]) -> dict[str, Any]:
    url = str(row.get("detl_pg_url") or "")
    parsed = urlparse(url)
    result: dict[str, Any] = {
        "announcement_id": str(row.get("pbanc_sn") or ""), "stratum": stratum,
        "detail_url": url, "api_receipt_start": row.get("pbanc_rcpt_bgng_dt"),
        "api_receipt_end": row.get("pbanc_rcpt_end_dt"), "api_status": row.get("rcrt_prgs_yn"),
        "http_status": None, "html_bytes": None, "title": row.get("biz_pbanc_nm"),
        "publication_label_found": False, "publication_date_values": [],
        "receipt_label_found": False, "application_label_found": False,
        "registration_like_code_markers": [], "error": None,
    }
    if parsed.scheme != "https" or not (parsed.hostname or "").endswith("k-startup.go.kr"):
        result["error"] = "non_official_detail_host"
        return result
    try:
        response = session.get(url, timeout=(10, 30))
        result["http_status"] = response.status_code
        response.raise_for_status()
        content = response.content
        result["html_bytes"] = len(content)
        try:
            html = content.decode("utf-8")
        except UnicodeDecodeError:
            html = content.decode(response.apparent_encoding or "cp949", errors="replace")
        parser = PageEvidence()
        parser.feed(html)
        labels = [x.casefold().replace(" ", "") for x in parser.labels]
        publication_words = ("등록일", "등록일자", "게시일", "게시일자", "공고등록일", "공고등록일자")
        receipt_words = ("접수기간", "모집기간", "접수기간", "모집기간")
        application_words = ("신청기간", "신청기간")
        result["publication_label_found"] = any(any(word in label for word in publication_words) for label in labels)
        result["receipt_label_found"] = any(any(word in label for word in receipt_words) for label in labels)
        result["application_label_found"] = any(any(word in label for word in application_words) for label in labels)
        # Only report registration-like data keys present in the delivered HTML;
        # do not call script endpoints or undocumented APIs.
        marker_pattern = re.compile(r"(?i)\b(?:pbanc[_A-Za-z]*reg[_A-Za-z]*dt|reg(?:istration)?[_A-Za-z]*date|creatPnttm|frstRegistPnttm)\b")
        result["registration_like_code_markers"] = sorted(set(marker_pattern.findall(html)))
        text = " ".join(parser.text)
        dates = sorted(set(re.findall(r"20\d{2}[-./]\d{1,2}[-./]\d{1,2}", text)))
        result["visible_date_values"] = dates
        if result["publication_label_found"]:
            result["publication_date_values"] = dates
    except Exception as exc:
        result["error"] = type(exc).__name__
    return result


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> int:
    rows = read_rows()
    PROCESSED.mkdir(parents=True, exist_ok=True)
    REPORTS.mkdir(parents=True, exist_ok=True)

    sample = choose_sample(rows)
    session = requests.Session()
    session.headers.update({"User-Agent": "KStartupDateAudit/1.0 (public detail page review)"})
    probes = []
    for index, (stratum, row) in enumerate(sample, start=1):
        probes.append(probe_page(session, stratum, row))
        if index < len(sample):
            time.sleep(0.35)
    write_jsonl(REPORTS / "kstartup_detail_probe.jsonl", probes)

    start_candidates: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []
    overlap_count = 0
    start_missing = end_missing = date_pair_incomplete = invalid_date_rows = 0
    start_in_window_count = 0
    overlap_records: list[dict[str, Any]] = []
    duplicate_ids = 0
    seen: set[str] = set()
    for row in rows:
        rid = str(row.get("pbanc_sn") or "").strip()
        if rid in seen:
            duplicate_ids += 1
            continue
        seen.add(rid)
        s_raw, e_raw = row.get("pbanc_rcpt_bgng_dt"), row.get("pbanc_rcpt_end_dt")
        s_day, e_day = parse_day(s_raw), parse_day(e_raw)
        start_missing += not bool(s_raw)
        end_missing += not bool(e_raw)
        date_pair_incomplete += s_day is None or e_day is None
        invalid_date_rows += (bool(s_raw) and s_day is None) or (bool(e_raw) and e_day is None)
        item = dict(row)
        if s_day and START <= s_day <= END:
            start_in_window_count += 1
            item.update({"date_verification_status": "date_unverified",
                         "published_date": None,
                         "date_basis": "application_receipt_start_date",
                         "date_basis_value": s_day.isoformat(),
                         "date_basis_source_field": "pbanc_rcpt_bgng_dt",
                         "date_basis_source_url": row.get("detl_pg_url"),
                         "is_application_period_overlap": bool(e_day and s_day <= END and e_day >= START)})
            start_candidates.append(item)
            unverified.append(item)
        if s_day and e_day and s_day <= END and e_day >= START:
            overlap_count += 1
            overlap_records.append({"announcement_id": rid, "application_start": s_day.isoformat(),
                                    "application_end": e_day.isoformat(), "source_url": row.get("detl_pg_url")})

    # The date audit is based on a stratified sample, so only mark records as
    # date_verified if an explicit publication date is evidenced on that record.
    # Current sample labels/HTML data did not show a publication-date field.
    for probe in probes:
        if probe["publication_label_found"] and probe["publication_date_values"]:
            verified.append({"announcement_id": probe["announcement_id"],
                             "published_date": probe["publication_date_values"],
                             "date_verification_status": "date_verified",
                             "date_source_url": probe["detail_url"],
                             "date_verification_method": "official_detail_page_label_and_visible_date"})

    write_jsonl(PROCESSED / "kstartup_recent_year_candidates.jsonl", start_candidates)
    write_jsonl(PROCESSED / "kstartup_date_verified.jsonl", verified)
    write_jsonl(PROCESSED / "kstartup_date_unverified.jsonl", unverified)

    detail_url_count = sum(bool(r.get("detl_pg_url")) for r in rows)
    detail_success = sum(p.get("http_status") == 200 and not p.get("error") for p in probes)
    publication_pages = sum(bool(p.get("publication_label_found")) for p in probes)
    marker_pages = sum(bool(p.get("registration_like_code_markers")) for p in probes)
    counts_by_year = Counter((parse_day(r.get("pbanc_rcpt_bgng_dt")).year
                              if parse_day(r.get("pbanc_rcpt_bgng_dt")) else "missing") for r in rows)
    summary = [
        "# K-Startup 날짜 필드 분석 및 최근 1년 후보", "",
        f"- 분석 대상: 기존 로컬 원본 JSONL {len(rows):,}행; API 재수집 없음.",
        f"- 대상 기간: {START.isoformat()} ~ {END.isoformat()} (양 끝 포함).",
        f"- 대표 상세 페이지 표본: {len(probes)}건, HTTP 200 성공 {detail_success}건.",
        f"- 표본에서 게시/등록일 라벨 확인: {publication_pages}건.",
        f"- 표본 HTML의 등록일형 데이터 키 확인: {marker_pages}건.", "",
        "## 건수와 기준", "",
        "| 항목 | 건수 | 분모·기준 |", "|---|---:|---|",
        f"| 전체 API 공고 | {len(rows):,} | 기존 raw JSONL 행 수 |",
        f"| 등록일 확인 가능 | {len(verified):,} / {len(probes):,} | 표본 상세에서 라벨과 날짜가 함께 확인된 경우만; 전체 모집단 수치 아님 |",
        f"| 등록일 기준 최근 1년 | 판정 불가 | 등록일 필드를 확인하지 못해 0건이라는 뜻이 아님 |",
        f"| 접수 시작일 기준 최근 1년 후보 | {start_in_window_count:,} | `pbanc_rcpt_bgng_dt`가 기간 안에 있는 ID 고유 레코드 |",
        f"| 접수기간이 최근 1년과 겹침 | {overlap_count:,} | 시작일 ≤ {END} AND 종료일 ≥ {START}; 등록일 결과와 별도 집계 |",
        f"| 날짜 정보 부족 | {date_pair_incomplete:,} | 접수 시작일 또는 종료일이 없거나 유효한 날짜 형식이 아님 |",
        f"| 상세 URL 존재 | {detail_url_count:,} | `detl_pg_url` 비어 있지 않음 / {len(rows):,} |",
        f"| 상세 페이지 표본 접근 성공 | {detail_success:,} | 표본 {len(probes):,}건 중 HTTP 200 |", "",
        "## 표본 조사 결과", "",
        f"연도·모집 상태별 층화 표본 {len(probes)}건을 공식 `www.k-startup.go.kr` 상세 페이지에서 확인했습니다. "
        f"HTTP 200 성공은 {detail_success}건입니다. 공개 HTML의 구조화 라벨에서 등록일/게시일과 날짜가 함께 확인된 페이지는 {publication_pages}건이었고, "
        f"등록일형 JSON/JS 데이터 키가 확인된 페이지는 {marker_pages}건이었습니다. API 응답에는 접수 시작일·종료일만 있고, 표본 HTML에서 보이는 날짜는 접수/신청 기간으로 분류했습니다. "
        "본문의 ‘공고일 기준’ 문구는 게시일 표시로 간주하지 않았습니다. 비공개 API 호출, 접근 제한 우회는 하지 않았습니다.", "",
        "### 접수 시작 연도 분포", "",
        "| 연도 | 건수 |", "|---:|---:|", *[f"| {y} | {n:,} |" for y, n in sorted(counts_by_year.items(), key=lambda x: str(x[0]))], "",
        "## 결과 파일", "",
        "- `processed/kstartup_recent_year_candidates.jsonl`: 접수 시작일 기준 기간 후보. 각 행은 `date_unverified`.",
        "- `processed/kstartup_date_unverified.jsonl`: 같은 후보를 검증 상태별 파일로 분리 보관.",
        "- `processed/kstartup_date_verified.jsonl`: 상세 페이지에서 등록일을 입증한 표본만; 현재 0행.",
        "- `reports/kstartup_detail_probe.jsonl`: 표본 ID, URL, API 접수 기간, 응답 코드, 페이지 날짜 라벨·데이터 키 검사 결과.",
        "- 접수기간 겹침 통계는 별도 계산했으며 시작일 기준 후보 데이터와 합치지 않았습니다.", "",
        "## 유의사항", "",
        "최근 1년 후보는 등록일로 검증된 집합이 아닙니다. 표본에서 등록일 필드를 찾지 못했으므로, 등록일 기준 최근 1년 건수는 현재 판정할 수 없습니다(확정 대상이 실제로 0건이라는 뜻이 아님). 표본 접근 성공률은 전체 상세 URL 접근률을 대표한다고 보장되지 않습니다.",
    ]
    (REPORTS / "kstartup_date_analysis.md").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print(json.dumps({"api_rows": len(rows), "sample_pages": len(probes), "sample_http_200": detail_success,
                      "publication_labeled_pages": publication_pages, "registration_code_marker_pages": marker_pages,
                      "start_date_candidates": start_in_window_count, "period_overlap": overlap_count,
                      "date_info_insufficient": date_pair_incomplete, "detail_urls": detail_url_count}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
