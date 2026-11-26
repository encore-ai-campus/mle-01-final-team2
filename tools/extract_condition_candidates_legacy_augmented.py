"""Generate a DEVELOPMENT-only legacy-candidate proposal set from pinned data v1.

The historical baseline extractor is deliberately not changed. This runner imports
its rule output, then admits only legacy facts with exact, unique evidence in the
same v1 extraction input and a narrow, explicit attribute/operator mapping.
Everything remains UNREVIEWED and decision-ineligible.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    from tools.extract_condition_candidates import condition as make_condition
    from tools.extract_condition_candidates import extract_one, read
except ModuleNotFoundError:  # direct script invocation places tools/ on sys.path
    from extract_condition_candidates import condition as make_condition
    from extract_condition_candidates import extract_one, read

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/condition_inputs/v1/20261125"
INPUT = DATA / "extraction_inputs.jsonl"
SAMPLES = DATA / "representative_samples.jsonl"
LEGACY = DATA / "candidate_refs.jsonl"
LEGACY_SOURCE = ROOT / "data/normalized/20261124/notices_normalized.jsonl"
BASELINE = DATA / "extracted/improved/development_conditions.jsonl"
OUTPUT = ROOT / "data/condition_inputs/v1/20261125/extracted/legacy_augmented"

# This is a deliberately small, fail-closed mapping into the existing v1 schema.
FIELD_MAP = {
    "company_size": ("BUSINESS_TYPE", "IS_A"),
    "business_age": ("BUSINESS_AGE", None),
    "founder_age": ("REPRESENTATIVE_AGE", None),
}
COMPARISON_OPERATORS = {"EQ", "NEQ", "GT", "GTE", "LT", "LTE"}
REVIEWED_TYPE = {"ELIGIBILITY"}
AMBIGUOUS_SCOPE_MARKERS = ("추천", "지원기관", "주관기관", "공동연구개발기관")


def jsonl(path: Path):
    yield from read(path)


def stable_candidate_id(notice_id: str, start: int, end: int, field: str,
                        operator: str, value: Any, unit: str | None) -> str:
    payload = json.dumps([notice_id, start, end, field, operator, value, unit],
                         ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).digest()[:15]
    return "LGCND:" + base64.b32encode(digest).decode("ascii").rstrip("=")


def _source_facts_by_key(records: list[dict[str, Any]]) -> dict[tuple, list[dict[str, Any]]]:
    out: dict[tuple, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        for fact in record.get("facts", []):
            key = (record.get("notice_id"), fact.get("attribute"), fact.get("char_start"),
                   fact.get("evidence_text"))
            out[key].append(fact)
    return out


def _all_offsets(text: str, needle: str) -> list[int]:
    if not needle:
        return []
    starts: list[int] = []
    at = 0
    while True:
        at = text.find(needle, at)
        if at < 0:
            return starts
        starts.append(at)
        at += 1


def _mapped_values(candidate: dict[str, Any], fact: dict[str, Any]) -> tuple[str, str, str, Any, str, str | None] | None:
    attribute = candidate.get("attribute")
    mapped = FIELD_MAP.get(attribute)
    if mapped is None:
        return None
    field, fixed_op = mapped
    original_operator = fact.get("operator")
    nv = candidate.get("normalized_value")
    if attribute == "company_size":
        if original_operator != "IS_A" or not isinstance(nv, dict) or not isinstance(nv.get("label"), str):
            return None
        return "ELIGIBILITY", field, "EQ", nv["label"], "STRING", None
    if original_operator not in COMPARISON_OPERATORS or not isinstance(nv, dict):
        return None
    value, unit = nv.get("value"), nv.get("unit")
    if not isinstance(value, (int, float)) or isinstance(value, bool) or unit != "YEAR":
        return None
    if candidate.get("kind") not in REVIEWED_TYPE:
        return None
    return "ELIGIBILITY", field, original_operator, value, "NUMBER", unit


def validate_legacy_candidate(candidate: dict[str, Any], input_row: dict[str, Any],
                              source_facts: dict[tuple, list[dict[str, Any]]]) -> dict[str, Any]:
    """Validate one v1 legacy row. Returns disposition and optional proposal."""
    notice_id = candidate.get("notice_id")
    evidence = candidate.get("evidence_text") or ""
    base = {
        "notice_id": notice_id, "candidate_ref": candidate.get("candidate_ref"),
        "legacy_candidate_ref": candidate.get("legacy_candidate_ref"),
        "source_system": candidate.get("source_system"), "attribute": candidate.get("attribute"),
        "legacy_kind": candidate.get("kind"), "legacy_operator": None,
        "normalized_value": candidate.get("normalized_value"), "source_file": candidate.get("source_file"),
        "source_field": candidate.get("source_field"), "source_position": candidate.get("source_position"),
        "evidence_text": evidence, "candidate_review_status": candidate.get("review_status"),
        "disposition": None, "reason": None, "proposed_condition_id": None,
        "proposal": None, "rule_condition_ids_merged": [],
    }
    if input_row is None or notice_id != input_row.get("notice_id"):
        return {**base, "disposition": "HOLD_NOTICE_MISMATCH", "reason": "no same-notice v1 extraction input"}
    if candidate.get("source_system") != input_row.get("source_system"):
        return {**base, "disposition": "HOLD_SOURCE_SYSTEM_MISMATCH", "reason": "source system differs"}
    if not str(candidate.get("candidate_ref", "")).startswith(notice_id + ":") or not str(candidate.get("legacy_candidate_ref", "")).startswith(notice_id + ":"):
        return {**base, "disposition": "HOLD_CANDIDATE_REFERENCE_MISMATCH", "reason": "candidate reference is not namespaced to the same notice"}
    if "20261124" not in str(candidate.get("source_file", "")):
        return {**base, "disposition": "HOLD_DATA_VERSION_MISMATCH", "reason": "candidate does not reference pinned v1 legacy snapshot"}
    key = (notice_id, candidate.get("attribute"), candidate.get("source_position"), evidence)
    facts = source_facts.get(key, [])
    if not facts:
        return {**base, "disposition": "HOLD_SOURCE_FACT_MISMATCH", "reason": "candidate does not resolve to source fact at recorded location"}
    fact_signatures = {(f.get("operator"), json.dumps(f.get("value"), sort_keys=True, ensure_ascii=False), bool(f.get("ambiguous"))) for f in facts}
    if len(fact_signatures) != 1:
        return {**base, "disposition": "HOLD_SOURCE_FACT_CONFLICT", "reason": "multiple distinct source facts share legacy location"}
    fact = facts[0]
    base["legacy_operator"] = fact.get("operator")
    if candidate.get("normalized_value") != fact.get("value"):
        return {**base, "disposition": "HOLD_NORMALIZED_VALUE_MISMATCH", "reason": "candidate value differs from source fact value"}
    if fact.get("ambiguous") is True:
        return {**base, "disposition": "HOLD_AMBIGUOUS_SOURCE_FACT", "reason": "legacy source fact is explicitly ambiguous"}
    if fact.get("review_status", "").upper() == "VERIFIED" or candidate.get("review_status", "").upper() == "VERIFIED":
        # Do not propagate a legacy status as human approval in this proposal pipeline.
        return {**base, "disposition": "HOLD_UNEXPECTED_VERIFIED_STATUS", "reason": "legacy approval status requires independent provenance check"}
    if candidate.get("kind") not in REVIEWED_TYPE:
        return {**base, "disposition": "HOLD_CONDITION_POLARITY", "reason": "only ELIGIBILITY facts are admitted by this narrow mode"}
    if candidate.get("attribute") == "region":
        return {**base, "disposition": "HOLD_REGION_SCOPE", "reason": "legacy region does not distinguish applicant address, business site, service area, or agency location"}
    if candidate.get("attribute") not in FIELD_MAP:
        return {**base, "disposition": "HOLD_ATTRIBUTE_UNSUPPORTED", "reason": "attribute mapping is not approved in this mode"}
    if any(marker in evidence for marker in AMBIGUOUS_SCOPE_MARKERS):
        return {**base, "disposition": "HOLD_APPLICANT_SCOPE", "reason": "text mentions recommendation/supporting organization scope; applicant mapping unresolved"}
    offsets = _all_offsets(input_row.get("raw_text", ""), evidence)
    if not offsets:
        return {**base, "disposition": "HOLD_EVIDENCE_NOT_IN_INPUT", "reason": "exact evidence text absent from current v1 extraction input"}
    if len(offsets) != 1:
        return {**base, "disposition": "HOLD_EVIDENCE_AMBIGUOUS", "reason": "exact evidence text appears more than once in input"}
    start = offsets[0]
    if start != candidate.get("source_position"):
        return {**base, "disposition": "HOLD_POSITION_MISMATCH", "reason": "current input location differs from legacy source position"}
    mapped = _mapped_values(candidate, fact)
    if mapped is None:
        return {**base, "disposition": "HOLD_UNSTRUCTURED_VALUE_OR_OPERATOR", "reason": "value/operator cannot be represented with an explicit v1 mapping"}
    kind, field, operator, value, value_type, unit = mapped
    if operator not in COMPARISON_OPERATORS:
        return {**base, "disposition": "HOLD_INVALID_OPERATOR", "reason": "mapped comparison operator is outside v1 vocabulary"}
    if candidate.get("attribute") == "company_size" and not isinstance(value, str):
        return {**base, "disposition": "HOLD_INVALID_VALUE", "reason": "company-size value is not a string label"}
    end = start + len(evidence)
    cid = stable_candidate_id(notice_id, start, end, field, operator, value, unit)
    category = field
    condition = make_condition(notice_id, input_row, kind, category, field, operator, value,
                               value_type, unit, evidence,
                               {"start": start, "end": end, "chunk_ids": []}, confidence=None)
    condition["condition_id"] = cid
    condition["review_status"] = "UNREVIEWED"
    condition["decision_eligible"] = False
    condition["source"]["source_field"] = "condition_texts.eligibility.text"
    condition["source"]["normalized_path"] = "condition_texts.eligibility.text"
    condition["source"]["evidence_id"] = f"{notice_id}:eligibility-source"
    return {**base, "disposition": "ADMITTED_PROPOSAL", "reason": "same-notice source fact, exact unique evidence/location, and v1 mapping validated; semantic review still pending",
            "proposed_condition_id": cid, "proposal": condition, "source_field": "condition_texts.eligibility.text"}


def semantic_signature(c: dict[str, Any]) -> tuple:
    return (c.get("notice_id"), c.get("condition_type"), c.get("field"), c.get("operator"),
            json.dumps(c.get("value"), ensure_ascii=False, sort_keys=True), c.get("unit"))


def overlaps(a: dict[str, Any], b: dict[str, Any]) -> bool:
    aa, ab = a["source"]["location"]["start_char"], a["source"]["location"]["end_char"]
    ba, bb = b["source"]["location"]["start_char"], b["source"]["location"]["end_char"]
    return aa < bb and ba < ab


def reconcile_proposals(rule_conditions: list[dict[str, Any]],
                        candidate_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """Merge exact duplicates, hold value conflicts, and preserve separate spans."""
    result = list(rule_conditions)
    states: dict[str, str] = {}
    conflict_bins: dict[tuple, set[str]] = defaultdict(set)
    for p in candidate_rows:
        loc = p["source"]["location"]
        key = (p["notice_id"], p["field"], p["operator"], loc["start_char"], loc["end_char"])
        conflict_bins[key].add(json.dumps(p["value"], ensure_ascii=False, sort_keys=True))
    for p in candidate_rows:
        pid = p["condition_id"]
        loc = p["source"]["location"]
        key = (p["notice_id"], p["field"], p["operator"], loc["start_char"], loc["end_char"])
        if len(conflict_bins[key]) > 1:
            states[pid] = "HOLD_VALUE_CONFLICT"
            continue
        matches = [r for r in result if semantic_signature(r) == semantic_signature(p) and overlaps(r, p)]
        if matches or any(r.get("condition_id") == pid for r in result):
            states[pid] = "DUPLICATE_RULE"
            continue
        result.append(p)
        states[pid] = "ADMITTED_PROPOSAL"
    return result, states


def run(output_dir: Path = OUTPUT) -> dict[str, Any]:
    inputs = {r["notice_id"]: r for r in jsonl(INPUT)}
    samples = [r for r in jsonl(SAMPLES) if r.get("split") == "DEVELOPMENT"]
    dev_ids = {r["notice_id"] for r in samples}
    if len(dev_ids) != 80:
        raise ValueError(f"expected frozen DEVELOPMENT 80, found {len(dev_ids)}")
    legacy_source = [r for r in jsonl(LEGACY_SOURCE) if r.get("notice_id") in dev_ids]
    source_facts = _source_facts_by_key(legacy_source)
    baseline_by_notice: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in jsonl(BASELINE):
        if c.get("notice_id") in dev_ids:
            baseline_by_notice[c["notice_id"]].append(c)
    legacy_rows = [r for r in jsonl(LEGACY) if r.get("notice_id") in dev_ids]

    dispositions: list[dict[str, Any]] = []
    proposals: dict[str, list[dict[str, Any]]] = defaultdict(list)
    # Stable source ordering is important for reproducible dispositions and output.
    for c in sorted(legacy_rows, key=lambda x: (x["notice_id"], x.get("source_position", -1), x.get("attribute", ""), x.get("candidate_ref", ""))):
        d = validate_legacy_candidate(c, inputs.get(c["notice_id"]), source_facts)
        if d.get("proposal"):
            proposals[c["notice_id"]].append(d["proposal"])
        dispositions.append(d)

    final_conditions: list[dict[str, Any]] = []
    provenance: list[dict[str, Any]] = []
    seen_condition_ids: set[str] = set()
    disposition_by_candidate = {d["candidate_ref"]: d for d in dispositions}
    for sample in samples:
        nid = sample["notice_id"]
        rule_conditions = extract_one(inputs[nid])
        all_rules, reconcile_status = reconcile_proposals(rule_conditions, proposals.get(nid, []))
        for d in dispositions:
            pid = d.get("proposed_condition_id")
            if pid in reconcile_status and reconcile_status[pid] != "ADMITTED_PROPOSAL":
                d["disposition"] = reconcile_status[pid]
                if reconcile_status[pid] == "DUPLICATE_RULE":
                    d["reason"] = "same semantic condition and overlapping evidence already emitted by rule extractor or earlier identical candidate"
                    d["rule_condition_ids_merged"] = [c["condition_id"] for c in rule_conditions if semantic_signature(c) == semantic_signature(d.get("proposal") or {})]
                else:
                    d["reason"] = "multiple normalized values share same notice, attribute, operator, and evidence span"
                d["proposal"] = None
        for c in all_rules:
            if c["condition_id"] in seen_condition_ids:
                raise ValueError(f"duplicate condition_id: {c['condition_id']}")
            seen_condition_ids.add(c["condition_id"])
            c["review_status"] = "UNREVIEWED"
            c["decision_eligible"] = False
            final_conditions.append(c)
            provenance.append({"condition_id": c["condition_id"], "notice_id": nid,
                               "extraction_method": "RULE_BASELINE" if c in rule_conditions else "LEGACY_PROPOSAL",
                               "legacy_candidate_refs": sorted({d["candidate_ref"] for d in dispositions if d.get("proposed_condition_id") == c["condition_id"] or c["condition_id"] in d.get("rule_condition_ids_merged", [])}),
                               "review_status": "UNREVIEWED", "decision_eligible": False})

    # Remove nested proposal payloads from the public disposition file but retain IDs and audit facts.
    public_dispositions = [{k: v for k, v in d.items() if k != "proposal"} for d in dispositions]
    output_dir.mkdir(parents=True, exist_ok=True)
    def dump_jsonl(name: str, rows: list[dict[str, Any]]) -> None:
        with (output_dir / name).open("w", encoding="utf-8", newline="\n") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    dump_jsonl("development_conditions.jsonl", final_conditions)
    dump_jsonl("candidate_provenance.jsonl", provenance)
    dump_jsonl("legacy_candidate_disposition.jsonl", public_dispositions)
    disposition_counts: dict[str, int] = defaultdict(int)
    for d in public_dispositions:
        disposition_counts[d["disposition"]] += 1
    report = {
        "mode": "legacy_augmented", "data_version": "v1", "schema_version": "1.0",
        "development_notice_count": len(dev_ids), "legacy_candidate_count": len(legacy_rows),
        "baseline_rule_condition_count": sum(map(len, baseline_by_notice.values())),
        "output_condition_count": len(final_conditions), "admitted_legacy_proposal_count": disposition_counts.get("ADMITTED_PROPOSAL", 0),
        "merged_duplicate_candidate_count": disposition_counts.get("DUPLICATE_RULE", 0),
        "held_or_rejected_candidate_count": len(legacy_rows) - disposition_counts.get("ADMITTED_PROPOSAL", 0) - disposition_counts.get("DUPLICATE_RULE", 0),
        "dispositions": dict(sorted(disposition_counts.items())),
        "decision_eligible_true_count": sum(c.get("decision_eligible") is True for c in final_conditions),
        "verified_count": sum(c.get("review_status") == "VERIFIED" for c in final_conditions),
        "gold_or_evaluation_ids_read_during_extraction": False,
        "data_v2_used": False,
        "llm_calls": 0,
    }
    (output_dir / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    fields = list(public_dispositions[0]) if public_dispositions else []
    with (output_dir / "legacy_candidate_diagnostics.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for d in public_dispositions:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, separators=(",", ":")) if isinstance(v, (dict, list)) else v for k, v in d.items()})
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
