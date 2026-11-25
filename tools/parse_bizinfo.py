#!/usr/bin/env python3
"""기업마당 원본 응답(collect_bizinfo.py 산출물)을 공고 단위 정규화 레코드로 변환한다 (표준 라이브러리만 사용).

입력 : data/bizinfo/raw/<run>/page_*.json  (기본: raw/LATEST가 가리키는 run)
출력 : data/bizinfo/parsed/<run>/notices.jsonl, attachments.jsonl, parse_report.json

설계 원칙
- 원문에 없는 값을 추론하지 않는다. 불확실한 값은 힌트 필드(*_hint)와 근거로만 남기고 확정하지 않는다.
- 해시태그의 지역 값은 '해시태그 값' 그대로 보존한다. 전국/지역 한정을 여기서 확정하지 않는다(region_scope_hint는 힌트).
- 첨부는 메타데이터만 만든다. 다운로드 토큰은 저장하지 않으며 파일은 내려받지 않는다.
- Neo4j/Supabase에 쓰지 않는다. 파일만 만든다.

사용 예:
    python tools/parse_bizinfo.py
    python tools/parse_bizinfo.py --raw data/bizinfo/raw/20261124_091601
    python tools/parse_bizinfo.py --prev data/bizinfo/parsed/<이전 run>/notices.jsonl
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import html
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path

KST = timezone(timedelta(hours=9))
REPO = Path(__file__).resolve().parent.parent
SOURCE = "BIZINFO"

# 행정안전부 행정표준코드(시도, code_version 20260701). 2026-07 개편으로 광주·전남은 통합시 1200000000.
SIDO_BY_TAG = {
    "서울": ("서울특별시", "1100000000"), "부산": ("부산광역시", "2600000000"), "대구": ("대구광역시", "2700000000"),
    "인천": ("인천광역시", "2800000000"), "전남광주": ("전남광주통합특별시", "1200000000"),
    "대전": ("대전광역시", "3000000000"), "울산": ("울산광역시", "3100000000"), "세종": ("세종특별자치시", "3600000000"),
    "경기": ("경기도", "4100000000"), "강원": ("강원특별자치도", "5100000000"), "충북": ("충청북도", "4300000000"),
    "충남": ("충청남도", "4400000000"), "전북": ("전북특별자치도", "5200000000"), "경북": ("경상북도", "4700000000"),
    "경남": ("경상남도", "4800000000"), "제주": ("제주특별자치도", "5000000000"),
}
LEGACY_REGION_TAGS = {"광주": "1200000000", "전남": "1200000000"}  # 개편 전 명칭
FIELD_TAGS = {"금융", "기술", "인력", "수출", "내수", "창업", "경영", "기타"}
SIDO_FULLNAME_TO_CODE = {v[0]: v[1] for v in SIDO_BY_TAG.values()}
CATEGORY_EXECUTORS = {  # 수행기관 필드(excInsttNm)에 기관명이 아닌 범주값이 들어오는 경우
    "기초자치단체": "LOCAL_GOVERNMENT_UNSPECIFIED",
    "직접수행": "SELF_OPERATED",
}
ROLE_TITLE_SUFFIXES = ("본부장", "센터장", "구청장", "시장", "군수", "도지사", "이사장", "원장", "단장", "소장", "지사장")


# ---------------------------------------------------------------- 텍스트 유틸
class _Text(HTMLParser):
    BLOCK = {"p", "div", "br", "li", "tr", "ul", "ol", "h1", "h2", "h3", "h4", "table"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == "br":  # 빈 단락(<p><br></p>)만 빈 줄이 되고, 이어진 단락 사이에는 빈 줄을 넣지 않는다
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCK and tag != "br":
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(s: str | None) -> str:
    """HTML 조각을 줄 단위 평문으로 바꾼다. ☞ 같은 기호는 보존한다."""
    if not s:
        return ""
    p = _Text()
    p.feed(s)
    p.close()
    text = html.unescape("".join(p.parts)).replace("\xa0", " ").replace("​", "")
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.replace("\r", "").split("\n")]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln); blank = False
        elif not blank and out:
            out.append(""); blank = True
    while out and out[-1] == "":
        out.pop()
    return "\n".join(out)


def sha256(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def norm_name(s: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", s or "")).strip()


def kst_iso(s: str | None) -> str | None:
    """'YYYY-MM-DD HH:MM:SS' -> ISO8601(+09:00)."""
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M:%S").replace(tzinfo=KST).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- 신청 기간
_RANGE = re.compile(r"(\d{4})[-.]?(\d{2})[-.]?(\d{2})\s*~\s*(\d{4})[-.]?(\d{2})[-.]?(\d{2})")
_STATUS_RULES = [  # 위에서부터 먼저 맞는 것
    ("UNTIL_BUDGET_EXHAUSTED", re.compile(r"예산")),
    ("FIRST_COME", re.compile(r"선착순")),
    ("UNTIL_FILLED", re.compile(r"모집\s*(완료|마감)|마감\s*시|모집규모|정원")),
    ("ALWAYS_OPEN", re.compile(r"상시|수시")),
    ("VARIES_OR_TBD", re.compile(r"상이|추후|별도|공지")),
]


def parse_period(raw: str | None) -> dict:
    """신청기간 원문 -> 시작·종료일, 마감 시각(해당일 23:59:59+09:00), 상태 종류. 날짜가 없으면 임의 값을 만들지 않는다."""
    raw = (raw or "").strip()
    out = {"deadline_raw": raw or None, "application_start_date": None, "application_end_date": None,
           "deadline_at": None, "apply_status_kind": "UNPARSED"}
    m = _RANGE.search(raw)
    if m:
        try:
            s = datetime(int(m[1]), int(m[2]), int(m[3])).date()
            e = datetime(int(m[4]), int(m[5]), int(m[6])).date()
        except ValueError:
            return out
        out.update(application_start_date=s.isoformat(), application_end_date=e.isoformat(),
                   deadline_at=f"{e.isoformat()}T23:59:59+09:00", apply_status_kind="DATE_RANGE")
        return out
    for kind, rx in _STATUS_RULES:
        if rx.search(raw):
            out["apply_status_kind"] = kind
            break
    return out


# ---------------------------------------------------------------- 본문 구조 (☞ 항목)
def split_blocks(text: str) -> dict:
    """평문을 ☞ 블록으로 나눈다. ☞ 앞의 줄은 intro, ※ 줄은 notes로 모은다."""
    intro, blocks, notes, cur = [], [], [], None
    for ln in text.split("\n"):
        if not ln:
            continue
        if ln.startswith("☞"):
            cur = {"head": ln.lstrip("☞").strip(), "items": []}
            blocks.append(cur)
        elif cur is not None:
            cur["items"].append(ln)
            if ln.startswith("※"):
                notes.append(ln)
        else:
            intro.append(ln)
            if ln.startswith("※"):
                notes.append(ln)
    return {"intro": intro, "blocks": blocks, "notes": notes}


def block_text(b: dict) -> str:
    return "\n".join([b["head"]] + b["items"]).strip()


# ---------------------------------------------------------------- 해시태그·지역
def classify_tags(tags: list[str], agency_names: set[str]) -> dict:
    region, field, year, agency, keyword = [], [], [], [], []
    for t in tags:
        if t in SIDO_BY_TAG or t in LEGACY_REGION_TAGS:
            region.append(t)
        elif t in FIELD_TAGS:
            field.append(t)
        elif re.fullmatch(r"20\d\d", t):
            year.append(t)
        elif t in agency_names:
            agency.append(t)
        else:
            keyword.append(t)
    current = {t for t in region if t in SIDO_BY_TAG}
    legacy = {t for t in region if t in LEGACY_REGION_TAGS}
    covers_all = all(k in current for k in SIDO_BY_TAG if k != "전남광주") and (
        "전남광주" in current or {"광주", "전남"} <= legacy)
    if covers_all:
        hint = "ALL_SIDO_TAGGED"  # 모든 시도 태그. 전국 사업일 수 있으나 본문 확인 전에는 확정하지 않는다
    elif region:
        hint = "SPECIFIC_SIDO_TAGGED"
    else:
        hint = "NO_REGION_TAG"
    return {"region": region, "field": field, "year": year, "agency": agency, "keyword": keyword,
            "region_scope_hint": hint}


# ---------------------------------------------------------------- 기관
def parse_executor(name: str | None) -> dict:
    n = norm_name(name or "")
    if not n:
        return {"executor_kind": "NONE", "executor_org_name": None, "executor_org_normalized": None, "executor_role_title": None}
    if n in CATEGORY_EXECUTORS:
        return {"executor_kind": CATEGORY_EXECUTORS[n], "executor_org_name": None, "executor_org_normalized": None,
                "executor_role_title": None, "executor_raw": n}
    base, role = n, None
    parts = n.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].endswith(ROLE_TITLE_SUFFIXES):
        base, role = parts
    return {"executor_kind": "ORG", "executor_org_name": base, "executor_org_normalized": base.casefold(),
            "executor_role_title": role, "executor_raw": n}


# ---------------------------------------------------------------- 첨부
_FILE_ID = re.compile(r"atchFileId=([A-Za-z0-9_]+)")
_FILE_SN = re.compile(r"fileSn=(\d+)")
_EXT_END = re.compile(r"\.[A-Za-z0-9]{1,5}$")


def split_file_names(s: str | None) -> list[str]:
    """'a.pdf@b.hwpx' 처럼 @로 이어진 파일명을 나눈다. 확장자로 끝나지 않는 조각은 다음 조각과 합친다."""
    if not s:
        return []
    names, buf = [], ""
    for piece in s.split("@"):
        buf = piece if not buf else buf + "@" + piece
        if _EXT_END.search(buf.strip()):
            names.append(buf.strip()); buf = ""
    if buf.strip():
        names.append(buf.strip())
    return names


def make_url(file_id: str, sn: str | None) -> str:
    u = f"https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId={file_id}"
    return u + (f"&fileSn={sn}" if sn is not None else "")


def parse_attachments(notice_id: str, item: dict) -> tuple[list[dict], list[str]]:
    warns: list[str] = []
    out: list[dict] = []

    def one(role, name, url, field_url, field_name, sn_hint=None):
        fid = (_FILE_ID.search(url).group(1) if url and _FILE_ID.search(url) else None)
        sn = sn_hint
        ext = _EXT_END.search(name).group(0)[1:].lower() if name and _EXT_END.search(name) else None
        key = f"{notice_id}|{role}|{fid}|{sn}|{name}"
        out.append({"attachment_id": "ATT:" + hashlib.sha1(key.encode("utf-8")).hexdigest()[:24],
                    "notice_id": notice_id, "source_system": SOURCE, "role": role, "file_name": name,
                    "file_extension": ext, "atch_file_id": fid, "file_sn": sn,
                    "source_url": make_url(fid, sn) if fid else None, "download_requires_token": True,
                    "source_field": field_name, "source_url_field": field_url})

    names = split_file_names(item.get("fileNm"))
    url = item.get("flpthNm") or ""
    sns = _FILE_SN.findall(url)
    if names and not url:
        warns.append("ATTACHMENT_NAME_WITHOUT_URL")
    if names and url:
        if len(names) != len(sns):
            warns.append(f"ATTACHMENT_COUNT_MISMATCH names={len(names)} urls={len(sns)}")
        for i, nm in enumerate(names):
            one("ATTACHMENT", nm, url, "flpthNm", "fileNm", sns[i] if i < len(sns) else None)
    pname, purl = item.get("printFileNm"), item.get("printFlpthNm") or ""
    if pname:
        psn = _FILE_SN.findall(purl)
        one("PRINT_BODY", norm_name(pname), purl, "printFlpthNm", "printFileNm", psn[0] if psn else None)
    return out, warns


# ---------------------------------------------------------------- 공고 한 건
def parse_item(item: dict, fetched_at: str) -> tuple[dict, list[dict], list[str]]:
    pid = item["pblancId"].strip()
    nid = f"{SOURCE}:{pid}"
    warns: list[str] = []

    summary_text = html_to_text(item.get("bsnsSumryCn"))
    parts = split_blocks(summary_text)
    first = block_text(parts["blocks"][0]) if parts["blocks"] else None
    if not parts["blocks"]:
        warns.append("NO_BULLET_BLOCK")
    apply_method = html_to_text(item.get("reqstMthPapersCn"))
    period = parse_period(item.get("reqstBeginEndDe"))
    if period["apply_status_kind"] == "UNPARSED":
        warns.append("PERIOD_UNPARSED")

    tags = [t.strip() for t in (item.get("hashtags") or "").split(",") if t.strip()]
    jr, ex = norm_name(item.get("jrsdInsttNm")), parse_executor(item.get("excInsttNm"))
    agency_names = {jr, ex.get("executor_org_name") or "", norm_name(item.get("excInsttNm"))} - {""}
    tc = classify_tags(tags, agency_names)
    region_codes = sorted({SIDO_BY_TAG[t][1] for t in tc["region"] if t in SIDO_BY_TAG} |
                          {LEGACY_REGION_TAGS[t] for t in tc["region"] if t in LEGACY_REGION_TAGS})

    attachments, aw = parse_attachments(nid, item)
    warns += aw
    apply_url = (item.get("rceptEngnHmpgUrl") or "").strip() or None
    if apply_url and not apply_url.lower().startswith("http"):
        warns.append("APPLY_URL_NOT_HTTP")

    raw_hash = sha256(item)
    content = {"title": norm_name(item.get("pblancNm")), "summary": summary_text, "apply_method": apply_method,
               "period": period["deadline_raw"], "target": item.get("trgetNm"), "apply_url": apply_url,
               "attachments": sorted(a["file_name"] for a in attachments)}
    rec = {
        "notice_id": nid, "source_system": SOURCE, "source_id": pid, "notice_kind": "SUPPORT",
        "title": content["title"], "detail_url": item.get("pblancUrl"),
        "published_at": kst_iso(item.get("creatPnttm")), "source_updated_at": kst_iso(item.get("updtPnttm")),
        "fetched_at": fetched_at, "version": 1, "is_latest": True,
        "content_hash": sha256(content), "raw_hash": raw_hash,
        **period,
        "summary": summary_text,
        "target_group_text": item.get("trgetNm"),  # 대상 유형 힌트(거친 값). 판정 근거로 쓰지 않는다
        "eligibility_criteria_text": first, "eligibility_basis": "first_bullet_block" if first else "none",
        "bullet_blocks": parts["blocks"], "intro_lines": parts["intro"], "notes": parts["notes"],
        "apply_method_text": apply_method or None, "apply_url": apply_url, "contact_text": norm_name(item.get("refrncNm")) or None,
        "support_category_major": item.get("pldirSportRealmLclasCodeNm"),
        "support_category_medium": item.get("pldirSportRealmMlsfcCodeNm"),
        "jurisdiction_org_name": jr, "jurisdiction_sido_code": SIDO_FULLNAME_TO_CODE.get(jr),
        **{k: v for k, v in ex.items() if k != "executor_raw"}, "executor_raw": ex.get("executor_raw"),
        "hashtags_raw": tags,
        "region_tags": tc["region"], "region_sido_codes_from_tags": region_codes, "region_scope_hint": tc["region_scope_hint"],
        "field_tags": tc["field"], "year_tags": tc["year"], "keyword_tags": tc["keyword"],
        "attachment_ids": [a["attachment_id"] for a in attachments],
        "view_count": int(item["inqireCo"]) if str(item.get("inqireCo", "")).isdigit() else None,
        "parse_warnings": warns,
    }
    return rec, attachments, warns


# ---------------------------------------------------------------- 실행
def load_raw(raw_dir: Path) -> tuple[list[dict], dict]:
    manifest = json.loads((raw_dir / "manifest.json").read_text(encoding="utf-8"))
    items: list[dict] = []
    for f in sorted(raw_dir.glob("page_*.json")):
        items += json.loads(f.read_text(encoding="utf-8")).get("jsonArray") or []
    return items, manifest


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--raw", help="raw run 디렉터리(기본: data/bizinfo/raw/LATEST)")
    ap.add_argument("--out", default=str(REPO / "data" / "bizinfo" / "parsed"))
    ap.add_argument("--prev", help="이전 notices.jsonl (버전 비교용)")
    args = ap.parse_args()

    raw_root = REPO / "data" / "bizinfo" / "raw"
    raw_dir = Path(args.raw) if args.raw else raw_root / (raw_root / "LATEST").read_text(encoding="utf-8").strip()
    items, manifest = load_raw(raw_dir)
    fetched_at = manifest["collected_at"]

    prev: dict[str, dict] = {}
    if args.prev:
        for ln in Path(args.prev).read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln); prev[r["notice_id"]] = r

    notices, atts, dup = {}, [], 0
    warn_counter: collections.Counter = collections.Counter()
    for it in items:
        if not it.get("pblancId"):
            warn_counter["ITEM_WITHOUT_ID"] += 1
            continue
        rec, a, w = parse_item(it, fetched_at)
        if rec["notice_id"] in notices:
            dup += 1
            atts = [x for x in atts if x["notice_id"] != rec["notice_id"]]
        old = prev.get(rec["notice_id"])
        if old:
            rec["version"] = old["version"] if old["content_hash"] == rec["content_hash"] else old["version"] + 1
            if rec["version"] != old["version"]:
                rec["supersedes_version"] = old["version"]
        notices[rec["notice_id"]] = rec
        atts += a
        for x in w:
            warn_counter[x.split(" ")[0]] += 1

    run = raw_dir.name
    out = Path(args.out) / run
    out.mkdir(parents=True, exist_ok=True)
    (out / "notices.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in notices.values()) + "\n", encoding="utf-8")
    (out / "attachments.jsonl").write_text("\n".join(json.dumps(a, ensure_ascii=False) for a in atts) + "\n", encoding="utf-8")

    N = list(notices.values())
    report = {
        "run": run, "parsed_at": datetime.now(KST).isoformat(timespec="seconds"), "raw_manifest_complete": manifest.get("complete"),
        "raw_items": len(items), "notices": len(N), "duplicates_dropped": dup, "attachments": len(atts),
        "warnings": dict(warn_counter),
        "apply_status_kind": dict(collections.Counter(r["apply_status_kind"] for r in N)),
        "region_scope_hint": dict(collections.Counter(r["region_scope_hint"] for r in N)),
        "executor_kind": dict(collections.Counter(r["executor_kind"] for r in N)),
        "with_eligibility_text": sum(1 for r in N if r["eligibility_criteria_text"]),
        "with_attachments": sum(1 for r in N if r["attachment_ids"]),
        "roles": dict(collections.Counter(a["role"] for a in atts)),
        "version_bumped": sum(1 for r in N if r.get("supersedes_version")),
        "missing_from_current_vs_prev": sorted(set(prev) - set(notices))[:50] if prev else None,
    }
    (out / "parse_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("출력:", out)


if __name__ == "__main__":
    main()
