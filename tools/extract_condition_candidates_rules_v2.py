"""Experimental general-purpose condition rules; frozen v1 baseline stays untouched."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/condition_inputs/v1/20261125"
BASELINE = DATA / "extracted/improved/development_conditions.jsonl"
SAMPLES = DATA / "representative_samples.jsonl"
INPUTS = DATA / "extraction_inputs.jsonl"
OUT = ROOT / "data/evaluations/conditions/v1.1/20261126/development/rule_improved_2_5c"

try:
    from tools.extract_condition_candidates import condition, read
except ModuleNotFoundError:
    from extract_condition_candidates import condition, read

MODES = ("A", "B", "C", "D", "E")
OPERATOR = {"이상": "GTE", "이하": "LTE", "초과": "GT", "미만": "LT", "이내": "LTE"}
NUM = r"(?P<n>\d[\d,]*(?:\.\d+)?)"
QUANT_RE = re.compile(
    rf"(?P<prefix>업력|창업\s*(?:후\s*)?|사업개시\s*후\s*|만\s*|연령\s*)"
    rf"\s*{NUM}\s*(?P<unit>년|개월|월|세)\s*(?P<op>이내|이하|이상|미만|초과)"
)
RANGE_RE = re.compile(r"(?P<lo>\d[\d,]*)\s*(?:세\s*)?(?P<lo_op>이상|초과)?\s*(?:~|〜|～|∼|부터|에서)\s*(?P<hi>\d[\d,]*)\s*(?P<unit>세|년)\s*(?P<hi_op>이내|이하|미만|초과|이상)?")
CHAINED_RANGE_RE = re.compile(r"(?P<lo>\d[\d,]*)\s*(?P<unit>세|년)\s*(?P<lo_op>이상|초과)\s*(?:(?:부터|~|〜|～|∼|에서|및)\s*)?(?P<hi>\d[\d,]*)\s*(?P=unit)\s*(?P<hi_op>이내|이하|미만|초과)")
EMPLOYEE_RE = re.compile(rf"(?P<prefix>근로자\s*수|근로자|종업원\s*수|고용인원|상시근로자)\s*{NUM}\s*명\s*(?P<op>이내|이하|이상|미만|초과)")
MONEY_RE = re.compile(rf"(?P<prefix>매출액|매출|부담금|자부담|지원금|투자금액|투자유치금액)\s*(?:은|이|가|:)?\s*{NUM}\s*(?P<unit>억원|만원|천원|원|USD|달러)\s*(?P<op>이내|이하|이상|미만|초과)", re.I)
PERCENT_RE = re.compile(rf"(?P<prefix>매출(?:액)?\s*(?:비중|비율|중)|산업\s*매출\s*비중)\s*{NUM}\s*%\s*(?P<op>이내|이하|이상|미만|초과)")
AGE_RE = re.compile(rf"(?P<prefix>만\s*){NUM}\s*세\s*(?P<op>이내|이하|이상|미만|초과)")

BUSINESS_TYPES = ("예비창업자", "예비 창업자", "창업기업", "창업 기업", "중소기업", "중견기업", "소상공인", "개인사업자", "법인사업자", "사회적기업", "예비사회적기업", "마을기업", "협동조합", "사회적협동조합")
APPLICANT_TYPES = ("개인", "법인", "대학", "연구기관", "비영리법인")
REGIONS = ("서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도", "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도", "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종", "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주")
NEGATIVE_ROLE = re.compile(r"추천\s*(?:대상|기업)|수혜\s*기업|지원\s*(?:기관|센터)|운영\s*기관|주관\s*기관|공동연구개발기관|전략산업|사업명")
LOCATION_CONTEXT = re.compile(r"신청자\s*(?:주소|거주)|대표자\s*(?:주소|거주)|사업장\s*(?:소재|주소)|본사\s*(?:소재|주소)|소재지|소재\s*기업|도내\s*기업|관내\s*기업|지역\s*기업")
APPLICANT_ADDRESS_CONTEXT = re.compile(r"신청자\s*(?:주소|거주)|대표자\s*(?:주소|거주)|신청자\s*주소지")
BUSINESS_SITE_CONTEXT = re.compile(r"사업장\s*(?:소재|주소)|본사\s*(?:소재|주소)|사업장\s*소재지|본사\s*소재지")
APPLICANT_CONTEXT = re.compile(r"신청(?:자|기업|기관)?|지원\s*대상|자격|대상\s*기업|참여\s*기업|기업은|사업자")
ELIGIBILITY_CONTEXT = re.compile(r"신청|지원\s*대상|자격|대상\s*(?:기업|자)|참여\s*기업|해당\s*기업")
EXCLUSION_MARKER = re.compile(r"지원\s*제외|신청\s*제외|참여\s*제한|지원\s*제한|제외\s*대상|신청할\s*수\s*없|지원받을\s*수\s*없")
PREFERENCE_MARKER = re.compile(r"우대|가점|우선\s*선정|우선\s*지원")


def _number(value: str) -> int | float:
    n = float(value.replace(",", ""))
    return int(n) if n.is_integer() else n


def _span(text: str, start: int, end: int) -> dict[str, Any]:
    return {"start": start, "end": end, "chunk_ids": []}


def _make(row: dict[str, Any], field: str | None, value: Any, operator: str | None,
          unit: str | None, start: int, end: int, *, kind="ELIGIBILITY", category=None,
          value_type=None) -> dict[str, Any]:
    raw = row["raw_text"][start:end]
    return condition(row["notice_id"], row, kind, category or field or "UNCLASSIFIED", field,
                     operator, value, value_type or ("NUMBER" if isinstance(value, (int, float)) else "STRING" if value is not None else "UNKNOWN"),
                     unit, raw, _span(row["raw_text"], start, end), confidence=0.64)


def _sentence_bounds(text: str, start: int, end: int) -> tuple[int, int]:
    left = max(text.rfind(mark, 0, start) for mark in ("\n", "。", "!", "?", "；", ";")) + 1
    candidates = [text.find(mark, end) for mark in ("\n", "。", "!", "?", "；", ";")]
    right = min((p + 1 for p in candidates if p >= 0), default=len(text))
    return left, right


def quantitative_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    text, out = row["raw_text"], []
    chained_ranges = list(CHAINED_RANGE_RE.finditer(text))
    for m in chained_ranges:
        context = text[max(0, m.start()-48):min(len(text), m.end()+20)]
        if m.group("unit") == "세":
            if not re.search(r"신청자|대표자|팀원|참가자|신청\s*대상|예비창업자|중장년", context):
                continue
            field = "APPLICANT_AGE"
        else:
            if not re.search(r"업력|창업|사업개시", context):
                continue
            field = "BUSINESS_AGE"
        value = {"lower": {"value": _number(m.group("lo")), "inclusive": m.group("lo_op") == "이상"},
                 "upper": {"value": _number(m.group("hi")), "inclusive": m.group("hi_op") in {"이내", "이하"}}}
        out.append(_make(row, field, value, "BETWEEN", "YEAR", m.start(), m.end(), value_type="RANGE"))
    for m in RANGE_RE.finditer(text):
        if any(m.start() < chained.end() and chained.start() < m.end() for chained in chained_ranges):
            continue
        context = text[max(0, m.start()-48):min(len(text), m.end()+20)]
        if m.group("unit") == "세":
            if not re.search(r"신청자|대표자|팀원|참가자|신청\s*대상|예비창업자|중장년", context):
                continue
            field = "APPLICANT_AGE"
        else:
            if not re.search(r"업력|창업|사업개시", context):
                continue
            field = "BUSINESS_AGE"
        lo, hi = _number(m.group("lo")), _number(m.group("hi"))
        lo_inclusive = m.group("lo_op") != "초과"
        hi_inclusive = m.group("hi_op") not in {"미만", "초과"}
        value = {"lower": {"value": lo, "inclusive": lo_inclusive},
                 "upper": {"value": hi, "inclusive": hi_inclusive}}
        out.append(_make(row, field, value, "BETWEEN", "YEAR", m.start(), m.end(), value_type="RANGE"))
    for rx in (QUANT_RE, AGE_RE):
        for m in rx.finditer(text):
            if any(m.start() < chained.end() and chained.start() < m.end() for chained in chained_ranges):
                continue
            prefix, unit, op = m.group("prefix"), m.groupdict().get("unit"), m.group("op")
            context = text[max(0, m.start()-32):min(len(text), m.end()+24)]
            if unit == "세" or prefix.startswith("만") or prefix == "연령":
                if not re.search(r"신청자|대표자|팀원|참가자|신청\s*대상|예비창업자|중장년|연령|나이", context):
                    continue
                field = "APPLICANT_AGE"
                norm_unit = "YEAR"
            else:
                field = "BUSINESS_AGE"
                norm_unit = "YEAR" if unit == "년" else "MONTH"
            out.append(_make(row, field, _number(m.group("n")), OPERATOR[op], norm_unit, m.start(), m.end()))
    for m in EMPLOYEE_RE.finditer(text):
        out.append(_make(row, "EMPLOYEE_COUNT", _number(m.group("n")), OPERATOR[m.group("op")], "PERSON", m.start(), m.end()))
    for m in PERCENT_RE.finditer(text):
        out.append(_make(row, "INDUSTRY_REVENUE_SHARE", _number(m.group("n")), OPERATOR[m.group("op")], "PERCENT", m.start(), m.end()))
    for m in MONEY_RE.finditer(text):
        prefix, raw_unit = m.group("prefix"), m.group("unit")
        if "매출" in prefix:
            field, category = "REVENUE", "REVENUE"
        else:
            field, category = "FINANCIAL_CAPACITY", "FINANCIAL_CAPACITY"
        unit = {"억원":"KRW", "만원":"KRW", "천원":"KRW", "원":"KRW", "USD":"USD", "달러":"USD"}[raw_unit]
        multiplier = {"억원":100_000_000, "만원":10_000, "천원":1_000, "원":1, "USD":1, "달러":1}[raw_unit]
        value = _number(m.group("n")) * multiplier
        start, end = m.start(), m.end()
        # Reference KRW in parentheses is supplemental normalization, not a second condition.
        out.append(_make(row, field, value, OPERATOR[m.group("op")], unit, start, end, category=category))
    return out


def categorical_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    text, out = row["raw_text"], []
    for phrase in BUSINESS_TYPES:
        for m in re.finditer(re.escape(phrase), text):
            left, right = _sentence_bounds(text, m.start(), m.end())
            context = text[left:right]
            if not ELIGIBILITY_CONTEXT.search(context) or NEGATIVE_ROLE.search(context):
                continue
            out.append(_make(row, "BUSINESS_TYPE", phrase.replace(" ", ""), "EQ", None, m.start(), m.end()))
    for phrase in APPLICANT_TYPES:
        for m in re.finditer(re.escape(phrase), text):
            left, right = _sentence_bounds(text, m.start(), m.end())
            context = text[left:right]
            if not APPLICANT_CONTEXT.search(context) or NEGATIVE_ROLE.search(context):
                continue
            out.append(_make(row, "APPLICANT_TYPE", phrase, "EQ", None, m.start(), m.end()))
    for region in REGIONS:
        for m in re.finditer(re.escape(region), text):
            left, right = _sentence_bounds(text, m.start(), m.end())
            context = text[left:right]
            local_context = text[max(left, m.start()-24):min(right, m.end()+24)]
            if LOCATION_CONTEXT.search(local_context) and not NEGATIVE_ROLE.search(context):
                applicant_markers = list(APPLICANT_ADDRESS_CONTEXT.finditer(local_context))
                business_markers = list(BUSINESS_SITE_CONTEXT.finditer(local_context))
                target_offset = m.start() - max(left, m.start()-24)
                applicant_distance = min((abs(target_offset-x.end()) for x in applicant_markers), default=10**9)
                business_distance = min((abs(target_offset-x.end()) for x in business_markers), default=10**9)
                if applicant_markers and applicant_distance < business_distance:
                    field = "APPLICANT_ADDRESS"
                else:
                    field = "BUSINESS_LOCATION"
                out.append(_make(row, field, region, "EQ", None, m.start(), m.end()))
    # Certification/licensing is emitted only when an explicit holder/qualification predicate exists.
    for m in re.finditer(r"[가-힣A-Za-z0-9·() ]{2,32}?(?:인증|면허|허가)(?:서)?(?:을|를)?\s*(?:보유|취득|소지)(?:한|하고)?", text):
        phrase = m.group()
        field = "LICENSE_STATUS" if any(x in phrase for x in ("면허", "허가")) else "CERTIFICATION"
        out.append(_make(row, field, phrase, "EQ", None, m.start(), m.end()))
    for m in re.finditer(r"사업자\s*등록(?:이|을|를)?\s*(?:완료(?:된|한)?|등록(?:된|한)?|유지(?:중|하는))", text):
        out.append(_make(row, "BUSINESS_REGISTRATION_STATUS", "REGISTERED", "EQ", None, m.start(), m.end()))
    for m in re.finditer(r"(?:프로그램|지원사업|보육센터|사업)에?\s*(?:참여(?:중|한|하고 있는)|입주(?:중|한|하고 있는))", text):
        value = "입주" if "입주" in m.group() else "참여"
        out.append(_make(row, "PROGRAM_PARTICIPATION", value, "EQ", None, m.start(), m.end()))
    for m in re.finditer(r"(?:사업계획서|사업자등록증|신청서|증빙서류|확인서|증명서)(?:를|을)?\s*제출(?:해야|하여야|한|하는|)", text):
        out.append(_make(row, "DOCUMENT_SUBMISSION", m.group().strip(), "EQ", None, m.start(), m.end()))
    for m in re.finditer(r"(?P<value>[가-힣A-Za-z0-9· ]{2,20}(?:산업|분야|업종))", text):
        value = m.group("value").strip()
        left, right = _sentence_bounds(text, m.start(), m.end())
        context = text[left:right]
        if ELIGIBILITY_CONTEXT.search(context) and not NEGATIVE_ROLE.search(context) and "사업분야" not in value:
            out.append(_make(row, "INDUSTRY", value, "EQ", None, m.start(), m.end()))
    return out


def _explicit_type(row: dict[str, Any], kind: str) -> list[dict[str, Any]]:
    text, rx = row["raw_text"], PREFERENCE_MARKER if kind == "PREFERENCE" else EXCLUSION_MARKER
    out = []
    for m in rx.finditer(text):
        start, end = _sentence_bounds(text, m.start(), m.end())
        raw = text[start:end].strip()
        trim = text[start:end]
        prefix = len(trim) - len(trim.lstrip())
        start += prefix
        if not raw:
            continue
        # Do not infer field/value from a marker alone. Preserve a review-only semantic clause.
        out.append(_make(row, None, None, None, None, start, start + len(raw), kind=kind, category="UNCLASSIFIED", value_type="UNKNOWN"))
    return out


def condition_type_review_candidates(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Marker-only clauses stay in a human queue until the applicable condition is known."""
    candidates = _explicit_type(row, "EXCLUSION") + _explicit_type(row, "PREFERENCE")
    for candidate in candidates:
        candidate["review_status"] = "NEEDS_REVIEW"
        candidate["decision_eligible"] = False
        candidate["logic_relation_status"] = "UNRESOLVED"
    return candidates


def _context_safe(c: dict[str, Any], row: dict[str, Any]) -> bool:
    field, raw = c.get("field"), c.get("raw_text", "")
    if field == "BUSINESS_LOCATION":
        left, right = _sentence_bounds(row["raw_text"], c["source"]["location"]["start_char"], c["source"]["location"]["end_char"])
        context = row["raw_text"][left:right]
        return bool(LOCATION_CONTEXT.search(context)) and not bool(NEGATIVE_ROLE.search(context)) and "전국" not in context
    if field == "BUSINESS_TYPE":
        left, right = _sentence_bounds(row["raw_text"], c["source"]["location"]["start_char"], c["source"]["location"]["end_char"])
        context = row["raw_text"][left:right]
        return not bool(NEGATIVE_ROLE.search(context))
    if field == "UNCLASSIFIED" and c.get("condition_type") not in {"EXCLUSION", "PREFERENCE"}:
        return False
    return True


def _dedupe(conditions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    kept, seen = [], set()
    for c in conditions:
        loc = c.get("source", {}).get("location") or {}
        value = c.get("value")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
        key = (c.get("notice_id"), c.get("condition_type"), c.get("field"), c.get("operator"),
               json.dumps(value, ensure_ascii=False, sort_keys=True), c.get("unit"),
               loc.get("start_char"), loc.get("end_char"))
        if key in seen:
            continue
        seen.add(key)
        kept.append(c)
    return kept


def extract_experiment(row: dict[str, Any], baseline: list[dict[str, Any]], mode: str) -> list[dict[str, Any]]:
    if mode not in MODES:
        raise ValueError(f"Unknown experiment mode: {mode}")
    base = list(baseline)
    if mode in {"A", "D", "E"}:
        base.extend(quantitative_candidates(row))
    if mode in {"B", "D", "E"}:
        base.extend(categorical_candidates(row))
    if mode in {"C", "E"}:
        base = [c for c in base if _context_safe(c, row)]
    if mode in {"D", "E"}:
        # D is the evidence-integrity variant: keep only candidates whose exact source span round-trips.
        text = row["raw_text"]
        base = [c for c in base if isinstance(c.get("source", {}).get("location"), dict)
                and text[c["source"]["location"]["start_char"]:c["source"]["location"]["end_char"]] == c.get("source", {}).get("evidence_text") == c.get("raw_text")]
    return _dedupe(base)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return list(read(path))


def run_all(output_dir: Path = OUT) -> dict[str, Any]:
    output_dir = Path(output_dir).resolve()
    rows = {r["notice_id"]: r for r in load_jsonl(INPUTS)}
    dev = [r for r in load_jsonl(SAMPLES) if r.get("split") == "DEVELOPMENT"]
    if len({r["notice_id"] for r in dev}) != 80:
        raise ValueError("Pinned v1 DEVELOPMENT split must contain 80 unique notices")
    baseline_by_notice: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in load_jsonl(BASELINE):
        baseline_by_notice[c["notice_id"]].append(c)
    summary = {"modes": {}, "data_version": "v1", "development_notices": 80,
               "evaluation_ids_read_during_extraction": False, "gold_ids_read_during_extraction": False,
               "review_status": "UNREVIEWED", "decision_eligible_true": 0}
    for mode in MODES:
        predictions, type_review = [], []
        for sample in dev:
            row = rows[sample["notice_id"]]
            predictions.extend(extract_experiment(row, baseline_by_notice.get(sample["notice_id"], []), mode))
            if mode in {"C", "E"}:
                type_review.extend(condition_type_review_candidates(row))
        out = output_dir / f"experiment_{mode}"
        out.mkdir(parents=True, exist_ok=True)
        ppath = out / "development_conditions.jsonl"
        ppath.write_text("".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n" for c in predictions), encoding="utf-8", newline="\n")
        if mode in {"C", "E"}:
            (out / "condition_type_review_candidates.jsonl").write_text(
                "".join(json.dumps(c, ensure_ascii=False, separators=(",", ":")) + "\n" for c in type_review),
                encoding="utf-8", newline="\n")
        summary["modes"][mode] = {"prediction_count": len(predictions), "prediction_path": str(ppath.relative_to(ROOT)),
                                  "sha256": hashlib.sha256(ppath.read_bytes()).hexdigest(),
                                  "condition_type_review_candidates": len(type_review),
                                  "condition_types": dict(__import__("collections").Counter(c["condition_type"] for c in predictions)),
                                  "fields": dict(__import__("collections").Counter(c.get("field") or "UNCLASSIFIED" for c in predictions))}
    (output_dir / "generation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(run_all(args.output_dir), ensure_ascii=False, indent=2))
