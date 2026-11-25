"""Validate human-edited gold review packets and emit reviewed records only."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "data/goldsets/conditions/v1/20261125"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def make_id(notice_id: str, kind: str, start: int, end: int, raw_text: str) -> str:
    payload = json.dumps([notice_id, kind, start, end, raw_text], ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).digest()[:15]
    return "GOLD:" + base64.b32encode(digest).decode("ascii").rstrip("=")


def schema_validators() -> dict[str, Draft202012Validator]:
    directory = ROOT / "schemas/conditions"
    resources = []
    schemas = {}
    for path in sorted(directory.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[path.name] = schema
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    return {name: Draft202012Validator(schema, registry=registry, format_checker=FormatChecker())
            for name, schema in schemas.items() if name in {
                "condition-gold-review-v1.schema.json", "logic-gold-review-v1.schema.json"}}


def validate_review_packets(root: Path, split: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    key = split.lower()
    directory = root / key
    other = "evaluation" if key == "development" else "development"
    selected_ids = {row["notice_id"] for row in read_jsonl(directory / "condition_review.jsonl")}
    other_ids = {row["notice_id"] for row in read_jsonl(root / other / "condition_review.jsonl")}
    if selected_ids & other_ids:
        raise ValueError("development/evaluation notice overlap")
    condition_rows = read_jsonl(directory / "condition_review.jsonl")
    logic_rows = read_jsonl(directory / "logic_review.jsonl")
    validators = schema_validators()
    condition_validator = validators["condition-gold-review-v1.schema.json"]
    logic_validator = validators["logic-gold-review-v1.schema.json"]
    condition_by_notice: dict[str, dict[str, Any]] = {}
    logic_by_notice: dict[str, dict[str, Any]] = {}
    for row in condition_rows:
        errors = list(condition_validator.iter_errors(row))
        if errors:
            raise ValueError(f"invalid condition review row {row.get('notice_id')}: {errors[0].message}")
        if row["dataset_split"] != split.upper() or row["notice_id"] in condition_by_notice:
            raise ValueError("condition review split mismatch or duplicate notice_id")
        condition_by_notice[row["notice_id"]] = row
    for row in logic_rows:
        errors = list(logic_validator.iter_errors(row))
        if errors:
            raise ValueError(f"invalid logic review row {row.get('notice_id')}: {errors[0].message}")
        if row["dataset_split"] != split.upper() or row["notice_id"] in logic_by_notice:
            raise ValueError("logic review split mismatch or duplicate notice_id")
        logic_by_notice[row["notice_id"]] = row
    if condition_by_notice.keys() != logic_by_notice.keys():
        raise ValueError("condition and logic review notice sets differ")

    for nid, row in condition_by_notice.items():
        gold_ids: set[str] = set()
        for condition in row["gold_conditions"] + row["missed_condition_candidates"]:
            start, end = condition["evidence_reference"]["start_char"], condition["evidence_reference"]["end_char"]
            if end > len(row["source_text"]) or start >= end or row["source_text"][start:end] != condition["raw_text"]:
                raise ValueError(f"gold evidence span mismatch for {nid}")
            expected = make_id(nid, condition["condition_type"], start, end, condition["raw_text"])
            if condition["gold_condition_id"] != expected:
                raise ValueError(f"non-deterministic or candidate-derived gold ID for {nid}")
            if condition["gold_condition_id"] in gold_ids:
                raise ValueError(f"duplicate gold condition ID in {nid}")
            gold_ids.add(condition["gold_condition_id"])
        existing = {c["condition_id"] for c in row.get("existing_candidates", [])}
        for alignment in row["candidate_alignments"]:
            if split == "EVALUATION":
                raise ValueError("evaluation gold data must not contain candidate alignments")
            if alignment["candidate_id"] not in existing:
                raise ValueError(f"alignment references unknown extractor candidate for {nid}")
            if not set(alignment["gold_condition_ids"]) <= gold_ids:
                raise ValueError(f"alignment references unknown gold condition for {nid}")
        if row["review_status"] == "VERIFIED":
            if row["adjudication_status"] == "PENDING" or not row["reviewer"] or not row["reviewed_at"]:
                raise ValueError(f"verified review missing completion metadata for {nid}")
            datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00"))
            if row["adjudication_status"] == "CONFIRMED_NONE_IN_PROVIDED_TEXT" and (row["gold_conditions"] or row["missed_condition_candidates"]):
                raise ValueError(f"confirmed-empty annotation contains gold conditions for {nid}")
        elif row["adjudication_status"] != "PENDING":
            raise ValueError(f"non-pending adjudication requires verified human review for {nid}")

        logic = logic_by_notice[nid]
        if logic["source_text"] != row["source_text"]:
            raise ValueError(f"condition/logic source text mismatch for {nid}")
        if logic["review_status"] == "VERIFIED":
            if row["review_status"] != "VERIFIED" or logic["adjudication_status"] == "PENDING" or not logic["reviewer"] or not logic["reviewed_at"]:
                raise ValueError(f"verified logic review missing verified condition review or metadata for {nid}")
            datetime.fromisoformat(logic["reviewed_at"].replace("Z", "+00:00"))
            if not set(logic["condition_gold_ids"]) <= gold_ids:
                raise ValueError(f"logic review references unknown gold condition for {nid}")
            referenced_ids = _validate_logic_roots(logic["gold_logic_roots"], gold_ids)
            if referenced_ids != set(logic["condition_gold_ids"]):
                raise ValueError(f"gold logic roots do not cover declared condition IDs for {nid}")
            for exception in logic["gold_exceptions"]:
                start, end = exception["evidence_reference"]["start_char"], exception["evidence_reference"]["end_char"]
                if end > len(logic["source_text"]) or start >= end or logic["source_text"][start:end] != exception["raw_text"]:
                    raise ValueError(f"exception evidence span mismatch for {nid}")
                if not set(exception["applies_to_gold_ids"]) <= gold_ids:
                    raise ValueError(f"exception references unknown gold condition for {nid}")
            for benefit in logic["gold_benefits"]:
                start, end = benefit["evidence_reference"]["start_char"], benefit["evidence_reference"]["end_char"]
                if end > len(logic["source_text"]) or start >= end or logic["source_text"][start:end] != benefit["raw_text"]:
                    raise ValueError(f"benefit evidence span mismatch for {nid}")
                if not set(benefit["applies_when_gold_ids"]) <= gold_ids:
                    raise ValueError(f"benefit references unknown gold condition for {nid}")
            for unresolved in logic["unresolved_relations"]:
                if not set(unresolved["gold_condition_ids"]) <= gold_ids:
                    raise ValueError(f"unresolved relation references unknown gold condition for {nid}")
        elif logic["adjudication_status"] != "PENDING":
            raise ValueError(f"non-pending logic adjudication requires verified review for {nid}")

    reviewed_conditions = []
    reviewed_logic = []
    for nid, row in condition_by_notice.items():
        if row["review_status"] == "VERIFIED" and row["adjudication_status"] != "PENDING":
            reviewed_conditions.append({key: row[key] for key in (
                "schema_version", "dataset_split", "notice_id", "source_system", "source_field", "source_text",
                "source_text_completeness", "whole_notice_conditions_complete", "source_condition_status",
                "gold_conditions", "missed_condition_candidates", "candidate_alignments", "review_status",
                "adjudication_status", "reviewer", "reviewed_at", "revision_history", "review_comment")})
        logic = logic_by_notice[nid]
        if logic["review_status"] == "VERIFIED" and logic["adjudication_status"] != "PENDING":
            reviewed_logic.append({key: logic[key] for key in (
                "schema_version", "dataset_split", "notice_id", "source_system", "condition_gold_ids",
                "gold_logic_roots", "gold_exceptions", "gold_benefits", "unresolved_relations", "review_status",
                "adjudication_status", "reviewer", "reviewed_at", "revision_history", "review_comment")})
    report = {"split": split.upper(), "condition_review_rows": len(condition_rows), "logic_review_rows": len(logic_rows),
              "reviewed_condition_records": len(reviewed_conditions), "reviewed_logic_records": len(reviewed_logic),
              "unreviewed_records": sum(r["review_status"] != "VERIFIED" for r in condition_rows),
              "evaluation_candidate_data_present": any("existing_candidates" in r or r["candidate_alignments"] for r in condition_rows) if split == "EVALUATION" else False,
              "all_rows_schema_valid": True, "human_review_claimed_by_tool": False}
    return reviewed_conditions, reviewed_logic, report


def _validate_logic_roots(roots: list[dict[str, Any]], known_ids: set[str]) -> set[str]:
    seen_groups: set[str] = set()
    referenced: set[str] = set()
    stack = list(roots)
    while stack:
        node = stack.pop()
        if node["node_type"] == "CONDITION_REF":
            if node["condition_id"] not in known_ids:
                raise ValueError(f"dangling condition reference in gold logic: {node['condition_id']}")
            referenced.add(node["condition_id"])
        else:
            if node["group_id"] in seen_groups:
                raise ValueError(f"duplicate logical group id in gold logic: {node['group_id']}")
            seen_groups.add(node["group_id"])
            if node["operator"] == "NOT" and len(node["children"]) != 1:
                raise ValueError("NOT group must have exactly one child")
            if node["operator"] in {"AND", "OR"} and len(node["children"]) < 2:
                raise ValueError("AND/OR group must have at least two children")
            stack.extend(node["children"])
    return referenced


def ingest(root: Path = DEFAULT_ROOT, split: str = "development") -> dict[str, Any]:
    if split not in {"development", "evaluation"}:
        raise ValueError("split must be development or evaluation")
    reviewed_conditions, reviewed_logic, report = validate_review_packets(root, split)
    directory = root / split
    write_jsonl(directory / "reviewed_condition_gold.jsonl", reviewed_conditions)
    write_jsonl(directory / "reviewed_logic_gold.jsonl", reviewed_logic)
    (directory / "ingest_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--split", choices=["development", "evaluation"], required=True)
    args = parser.parse_args()
    print(json.dumps(ingest(args.root, args.split), ensure_ascii=False, indent=2))
