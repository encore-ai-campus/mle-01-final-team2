"""Build review-only logical structure candidates from the 2-2 development output.

No rule in this module resolves application logic or makes conditions decision eligible.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import re
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/condition_inputs/v1/20261125"
CONDITIONS = BASE / "extracted/improved/development_conditions.jsonl"
INPUTS = BASE / "extraction_inputs.jsonl"
SAMPLES = BASE / "representative_samples.jsonl"
HUMAN_REVIEW = BASE / "quality_diagnostics/human_review.jsonl"
OUT = BASE / "logic"

TYPE_TO_KEY = {"ELIGIBILITY": "eligibility", "EXCLUSION": "exclusion", "PREFERENCE": "preference"}
QUALIFIER_RE = re.compile(r"(?:다만|단서|예외|제외하고|제외한다|해당하지 않|우대|가점)")
CONNECTOR_AND = re.compile(r"(?:모두\s*(?:충족|만족)|동시에|각각\s*충족|및\s*)")
CONNECTOR_OR = re.compile(r"(?:중\s*하나|택\s*일|또는|혹은|\bOR\b)", re.I)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).digest()[:15]
    # Base32 avoids phone-number false positives in privacy scanners while remaining stable.
    return prefix + base64.b32encode(digest).decode("ascii").rstrip("=")


def source_reference(condition: dict[str, Any]) -> dict[str, Any]:
    src = condition["source"]
    return {key: src[key] for key in (
        "source_system", "source_kind", "source_field", "normalized_path", "evidence_id",
        "chunk_ids", "location", "observed_value_status", "evidence_text",
    )}


def empty_source(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("evidence") or [{}]
    ev = evidence[0]
    return {
        "source_system": row["source_system"], "source_kind": ev.get("source_kind", "NOTICE_FIELD"),
        "source_field": ev.get("path"), "normalized_path": ev.get("path"),
        "evidence_id": f"{row['notice_id']}:condition-source", "chunk_ids": ev.get("chunk_ids", []),
        "location": None, "observed_value_status": row.get("availability_status", "UNKNOWN"),
        "evidence_text": ev.get("text"),
    }


def build_collection(kind: str, conditions: list[dict[str, Any]], row: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    # Ambiguous classifications are retained in the eligibility slot, matching the v1
    # contract's established convention; their condition_type remains UNCLASSIFIED.
    if kind == "ELIGIBILITY":
        selected = [c for c in conditions if c["condition_type"] in ("ELIGIBILITY", "UNCLASSIFIED")]
    else:
        selected = [c for c in conditions if c["condition_type"] == kind]
    evidence_map = {json.dumps(source_reference(c), ensure_ascii=False, sort_keys=True): source_reference(c) for c in selected}
    refs = [{"node_type": "CONDITION_REF", "condition_id": c["condition_id"]} for c in selected]
    groups: list[dict[str, Any]] = []
    if len(refs) == 1:
        roots = refs
    elif len(refs) > 1:
        spans = [c.get("source", {}).get("location") or {} for c in selected]
        start = min((s.get("start_char") for s in spans if isinstance(s.get("start_char"), int)), default=None)
        end = max((s.get("end_char") for s in spans if isinstance(s.get("end_char"), int)), default=None)
        text = row.get("raw_text", "")
        context = text[max(0, start or 0):end] if end is not None else ""
        and_hint = bool(CONNECTOR_AND.search(context))
        or_hint = bool(CONNECTOR_OR.search(context))
        operator = "UNRESOLVED"
        hint = "AMBIGUOUS_OR_NO_EXPLICIT_CONNECTOR"
        if and_hint != or_hint:
            operator = "AND" if and_hint else "OR"
            hint = "EXPLICIT_CONNECTOR_CANDIDATE"
        gid = stable_id("LGC:", row["notice_id"], kind, operator, sorted(c["condition_id"] for c in selected))
        group_evidence = None
        if context and start is not None and end is not None:
            group_evidence = source_reference(selected[0])
            group_evidence["location"] = {"start_char": start, "end_char": end}
            group_evidence["evidence_text"] = context
        groups.append({"group_id": gid, "notice_id": row["notice_id"], "condition_type": kind,
                       "operator_candidate": operator, "hint_status": hint,
                       "condition_ids": [c["condition_id"] for c in selected],
                       "evidence": group_evidence, "evidence_text": context or None, "review_status": "NEEDS_REVIEW",
                       "decision_eligible": False})
        roots = [{"node_type": "LOGICAL_GROUP", "group_id": gid, "operator": operator,
                  "children": refs, "review_status": "NEEDS_REVIEW", "evidence": group_evidence}]
    else:
        roots = []
    source_evidence = list(evidence_map.values()) if selected else [empty_source(row)]
    availability = "AVAILABLE" if selected else "NOT_EXTRACTED"
    collection = {
        "condition_type": kind, "availability_status": availability,
        "completeness_status": "PARTIAL", "review_status": "NEEDS_REVIEW",
        "structure_status": "PARTIALLY_STRUCTURED" if selected else "UNSTRUCTURED",
        "logic_status": "UNRESOLVED", "conditions": selected, "logical_roots": roots,
        "source_evidence": source_evidence, "decision_eligible": False,
        "insufficient_reasons": ["AUTOMATIC_LOGIC_CANDIDATE_REQUIRES_HUMAN_REVIEW"] if selected else ["NO_RULE_MATCH_DOES_NOT_CONFIRM_ABSENCE"],
    }
    return collection, groups


def validate_graph(record: dict[str, Any]) -> None:
    all_condition_ids: set[str] = set()
    seen_groups: set[str] = set()
    for collection in record["condition_sets"].values():
        if any(c.get("notice_id") != record["notice_id"] for c in collection["conditions"]):
            raise ValueError(f"condition belongs to another notice in {record['notice_id']}")
        ids = [c["condition_id"] for c in collection["conditions"]]
        if len(ids) != len(set(ids)):
            raise ValueError(f"duplicate condition ids in {record['notice_id']}")
        all_condition_ids.update(ids)
        if collection["decision_eligible"]:
            raise ValueError("review-only output must not be decision eligible")
        referenced: set[str] = set()
        stack = list(collection["logical_roots"])
        while stack:
            node = stack.pop()
            if node["node_type"] == "CONDITION_REF":
                if node["condition_id"] not in ids:
                    raise ValueError(f"dangling reference {node['condition_id']}")
                referenced.add(node["condition_id"])
            else:
                gid = node["group_id"]
                if gid in seen_groups:
                    raise ValueError(f"duplicate group id {gid}")
                seen_groups.add(gid)
                if node["operator"] == "NOT" and len(node["children"]) != 1:
                    raise ValueError("NOT requires exactly one child")
                if node["operator"] in ("AND", "OR") and len(node["children"]) < 2:
                    raise ValueError(f"{node['operator']} requires at least two children")
                stack.extend(node["children"])
        if referenced != set(ids):
            raise ValueError(f"condition reference coverage mismatch {record['notice_id']}")
    if record["decision_readiness"] != {
        "eligibility_decision_eligible": False,
        "preference_assessment_eligible": False,
        "limiting_reasons": ["LOGICAL_STRUCTURE_REQUIRES_HUMAN_REVIEW"],
    }:
        raise ValueError("decision readiness must remain disabled")


def make_schema_validator() -> Draft202012Validator:
    resources = []
    root_schema = None
    for path in sorted((ROOT / "schemas/conditions").glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        resources.append((schema["$id"], Resource.from_contents(schema)))
        if path.name == "notice-condition-set-v1.schema.json":
            root_schema = schema
    if root_schema is None:
        raise FileNotFoundError("notice-condition-set-v1.schema.json")
    return Draft202012Validator(root_schema, registry=Registry().with_resources(resources),
                                format_checker=FormatChecker())


def build(output_dir: Path = OUT) -> dict[str, Any]:
    started = time.perf_counter()
    samples = [r for r in read_jsonl(SAMPLES) if r.get("split") == "DEVELOPMENT"]
    if len(samples) != 80:
        raise ValueError(f"Expected exactly 80 development samples, got {len(samples)}")
    schema_validator = make_schema_validator()
    inputs = {r["notice_id"]: r for r in read_jsonl(INPUTS)}
    candidates = read_jsonl(CONDITIONS)
    by_notice: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        by_notice[candidate["notice_id"]].append(candidate)
    records, relation_rows, qualifier_rows, notice_review_rows = [], [], [], []
    op_counts: Counter[str] = Counter()
    for sample in samples:
        nid = sample["notice_id"]
        row = inputs[nid]
        cs = by_notice.get(nid, [])
        sets, groups = {}, []
        for kind, key in TYPE_TO_KEY.items():
            collection, candidates_groups = build_collection(kind, cs, row)
            sets[key] = collection
            groups.extend(candidates_groups)
        for group in groups:
            relation_rows.append(group)
            op_counts[group["operator_candidate"]] += 1
        notice_review_rows.append({"notice_id": nid, "source_system": row["source_system"],
                                   "condition_candidate_count": len(cs),
                                   "status": "UNRESOLVED_REVIEW_REQUIRED" if cs else "NO_RULE_MATCH_NOT_ABSENCE",
                                   "candidate_condition_ids": [c["condition_id"] for c in cs],
                                   "logical_group_ids": [g["group_id"] for g in groups],
                                   "review_status": "UNREVIEWED", "decision_eligible": False})
        for match in QUALIFIER_RE.finditer(row.get("raw_text", "")):
            start = match.start()
            line_start = row["raw_text"].rfind("\n", 0, start) + 1
            line_end = row["raw_text"].find("\n", match.end())
            if line_end < 0:
                line_end = len(row["raw_text"])
            exact = row["raw_text"][line_start:line_end].strip()
            qualifier_rows.append({"candidate_id": stable_id("QCF:", nid, line_start, exact),
                                   "notice_id": nid, "raw_text": exact, "start_char": line_start,
                                   "end_char": line_end, "candidate_condition_ids": [c["condition_id"] for c in cs],
                                   "linkage_status": "UNRESOLVED", "review_status": "NEEDS_REVIEW",
                                   "decision_eligible": False, "detection_method": "LEXICAL_REVIEW_CANDIDATE"})
        record = {
            "schema_version": "1.0", "record_type": "notice_condition_set", "notice_id": nid,
            "source_system": row["source_system"], "source_snapshot": row.get("source_snapshot"),
            "condition_sets": sets,
            "decision_readiness": {"eligibility_decision_eligible": False,
                                   "preference_assessment_eligible": False,
                                   "limiting_reasons": ["LOGICAL_STRUCTURE_REQUIRES_HUMAN_REVIEW"]},
            "sample_metadata": {"kind": "ACTUAL_SOURCE", "label": "DEVELOPMENT_REVIEW_ONLY"},
        }
        validate_graph(record)
        errors = list(schema_validator.iter_errors(record))
        if errors:
            raise ValueError(f"schema validation failed for {nid}: {errors[0].message}")
        records.append(record)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(output_dir / "notice_condition_sets.jsonl", records)
    write_jsonl(output_dir / "relation_review.jsonl", relation_rows)
    write_jsonl(output_dir / "unresolved_logic_review.jsonl", notice_review_rows)
    write_jsonl(output_dir / "qualifier_candidates.jsonl", qualifier_rows)
    # Audit map includes every source candidate ID, including UNCLASSIFIED candidates.
    write_jsonl(output_dir / "condition_group_map.jsonl", [
        {"notice_id": r["notice_id"], "condition_id": c["condition_id"],
         "condition_type": c["condition_type"], "group_slot": "eligibility" if c["condition_type"] == "UNCLASSIFIED" else TYPE_TO_KEY[c["condition_type"]],
         "candidate_ref_preserved": c["condition_id"], "mapping_status": "PRESERVED_REVIEW_CANDIDATE",
         "review_status": "UNREVIEWED", "decision_eligible": False}
        for r in records for key in ("eligibility", "exclusion", "preference") for c in r["condition_sets"][key]["conditions"]
    ])
    # Extend the existing 30-notice review packet without changing its human-review state.
    existing_review = read_jsonl(HUMAN_REVIEW)
    review_ids = list(dict.fromkeys(r["notice_id"] for r in existing_review))
    record_by_id = {r["notice_id"]: r for r in records}
    input_by_id = inputs
    packet = []
    for nid in review_ids:
        if nid not in record_by_id:
            raise ValueError(f"review packet notice is outside DEVELOPMENT: {nid}")
        record = record_by_id[nid]
        packet.append({"notice_id": nid, "source_system": record["source_system"],
                       "raw_text": input_by_id[nid].get("raw_text"),
                       "condition_candidates": [c for key in ("eligibility", "exclusion", "preference") for c in record["condition_sets"][key]["conditions"]],
                       "proposed_logic": {key: value["logical_roots"] for key, value in record["condition_sets"].items()},
                       "relation_review": [g for g in relation_rows if g["notice_id"] == nid],
                       "qualifier_candidates": [q for q in qualifier_rows if q["notice_id"] == nid],
                       "reviewer_logic_correction": None, "review_status": "UNREVIEWED", "review_comment": None})
    write_jsonl(output_dir / "human_logic_review.jsonl", packet)
    csv_path = output_dir / "human_logic_review.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=["notice_id", "source_system", "raw_text", "condition_candidates",
                                                  "proposed_logic", "relation_review", "qualifier_candidates",
                                                  "reviewer_logic_correction", "review_status", "review_comment"])
        writer.writeheader()
        for row in packet:
            writer.writerow({key: json.dumps(row[key], ensure_ascii=False) if isinstance(row[key], (list, dict)) else row[key]
                             for key in writer.fieldnames})
    counts = Counter(c["condition_type"] for c in candidates)
    source_counts = Counter(c["source"]["source_system"] for c in candidates)
    by_evidence: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for c in candidates:
        loc = c.get("source", {}).get("location") or {}
        key = (c["notice_id"], c.get("source", {}).get("evidence_id"), loc.get("start_char"),
               loc.get("end_char"), c.get("field"), c.get("category_id"))
        by_evidence[key].append(c)
    conflicts = []
    for key, group in by_evidence.items():
        interpretations = {(c.get("operator"), json.dumps(c.get("value"), ensure_ascii=False, sort_keys=True)) for c in group}
        if len(group) > 1 and len(interpretations) > 1:
            conflicts.append({"conflict_id": stable_id("CFL:", key, sorted(c["condition_id"] for c in group)),
                              "notice_id": group[0]["notice_id"], "condition_ids": [c["condition_id"] for c in group],
                              "reason": "SAME_EVIDENCE_DIFFERENT_INTERPRETATION", "review_status": "NEEDS_REVIEW",
                              "decision_eligible": False})
    write_jsonl(output_dir / "conflict_review.jsonl", conflicts)
    report = {"development_notices": len(records), "source_condition_candidates": len(candidates),
              "conditions_in_sets": sum(len(s["conditions"]) for r in records for s in r["condition_sets"].values()),
              "condition_types": dict(sorted(counts.items())), "source_condition_candidates_by_source": dict(sorted(source_counts.items())),
              "condition_group_map_records": len(candidates),
              "notices_without_extracted_candidates": sum(not by_notice.get(s["notice_id"]) for s in samples),
              "logical_groups": len(relation_rows), "relation_candidates_by_operator": dict(sorted(op_counts.items())),
              "qualifier_candidates": len(qualifier_rows), "notice_review_queue_records": len(notice_review_rows),
              "human_review_packet_notices": len(packet), "conflicting_candidate_groups": len(conflicts),
              "all_decision_eligible_false": True,
              "evaluation_records_used": False, "g2b_conditions_generated": 0,
              "schema_validation": "PASSED_ALL_80_RECORDS", "human_review": "NOT_PERFORMED",
              "elapsed_seconds": round(time.perf_counter() - started, 3)}
    (output_dir / "run_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUT)
    print(json.dumps(build(parser.parse_args().output_dir), ensure_ascii=False, indent=2))
