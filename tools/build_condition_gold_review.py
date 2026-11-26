"""Create separated, unreviewed human annotation packets for condition gold data."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "data/condition_inputs/v1/20261125"
SAMPLES = BASE / "representative_samples.jsonl"
DEV_PACKET = BASE / "logic/human_logic_review.jsonl"
DEV_LOGIC = BASE / "logic/relation_review.jsonl"
DEV_QUALIFIERS = BASE / "logic/qualifier_candidates.jsonl"
DEV_CONDITIONS = BASE / "extracted/improved/development_conditions.jsonl"
OUTPUT = ROOT / "data/goldsets/conditions/v1/20261125"
BASELINE_FILES = {
    "extracted_conditions": BASE / "extracted/improved/development_conditions.jsonl",
    "notice_condition_sets": BASE / "logic/notice_condition_sets.jsonl",
    "relation_review": BASE / "logic/relation_review.jsonl",
    "qualifier_candidates": BASE / "logic/qualifier_candidates.jsonl",
    "run_report": BASE / "logic/run_report.json",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(row.get(k), ensure_ascii=False) if isinstance(row.get(k), (dict, list)) else row.get(k)
                             for k in columns})


def baseline_manifest() -> dict[str, Any]:
    manifest = {"baseline_name": "PRE_2_4_FROZEN", "files": {}}
    for name, path in BASELINE_FILES.items():
        content = path.read_bytes()
        entry: dict[str, Any] = {"path": path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(content).hexdigest()}
        if path.suffix == ".jsonl":
            entry["record_count"] = sum(1 for line in content.splitlines() if line.strip())
        else:
            entry["record"] = json.loads(content.decode("utf-8"))
        manifest["files"][name] = entry
    manifest["expected_counts"] = {"development_notices": 80, "condition_candidates": 98,
                                    "eligibility": 89, "exclusion": 6, "preference": 3,
                                    "no_extraction": 26, "logic_groups": 25,
                                    "and": 2, "or": 5, "unresolved": 18, "qualifier_candidates": 5,
                                    "tests_passed": 49}
    return manifest


def condition_review_row(sample: dict[str, Any], *, split: str, candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    raw = sample["raw_text"]
    row: dict[str, Any] = {
        "schema_version": "1.0", "record_type": "condition_gold_review", "dataset_split": split,
        "data_kind": "ACTUAL_SOURCE",
        "notice_id": sample["notice_id"], "source_system": sample["source_system"],
        "source_field": "condition_texts.eligibility.text", "source_text": raw,
        "provided_text_scope": "SAMPLED_CONDITION_TEXT_EXCERPT",
        "source_text_completeness": "UNKNOWN", "whole_notice_conditions_complete": False,
        "source_condition_status": "AVAILABLE" if raw.strip() else "EMPTY",
        "evidence_reference": {"source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": len(raw)},
        "gold_conditions": [], "missed_condition_candidates": [], "candidate_alignments": [],
        "review_status": "UNREVIEWED", "adjudication_status": "PENDING",
        "reviewer": None, "reviewed_at": None, "revision_history": [], "review_comment": None,
    }
    if split == "DEVELOPMENT":
        row["existing_candidates"] = candidates or []
    return row


def logic_review_row(sample: dict[str, Any], condition_row: dict[str, Any], *, split: str,
                     existing_logic: dict[str, Any] | None = None,
                     relation_candidates: list[dict[str, Any]] | None = None,
                     qualifier_candidates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "schema_version": "1.0", "record_type": "logic_gold_review", "dataset_split": split,
        "data_kind": "ACTUAL_SOURCE",
        "notice_id": sample["notice_id"], "source_system": sample["source_system"],
        "source_text": sample["raw_text"], "condition_gold_ids": [],
        "gold_logic_roots": [], "gold_exceptions": [], "gold_benefits": [], "unresolved_relations": [],
        "review_status": "UNREVIEWED", "adjudication_status": "PENDING",
        "reviewer": None, "reviewed_at": None, "revision_history": [], "review_comment": None,
    }
    if split == "DEVELOPMENT":
        row["existing_condition_candidates"] = condition_row["existing_candidates"]
        row["existing_logic_roots"] = existing_logic["condition_sets"] if existing_logic else {}
        row["existing_relation_candidates"] = relation_candidates or []
        row["existing_qualifier_candidates"] = qualifier_candidates or []
    return row


def build(output: Path = OUTPUT, development_ids_path: Path | None = None) -> dict[str, Any]:
    samples = read_jsonl(SAMPLES)
    dev = [r for r in samples if r.get("split") == "DEVELOPMENT"]
    evaluation = [r for r in samples if r.get("split") == "EVALUATION"]
    if len(dev) != 80 or len(evaluation) != 20:
        raise ValueError(f"Unexpected split counts: development={len(dev)} evaluation={len(evaluation)}")

    # Only the development packet branch reads model/extractor output files.
    dev_existing = read_jsonl(DEV_PACKET)
    dev_conditions = read_jsonl(DEV_CONDITIONS)
    dev_logic = {r["notice_id"]: r for r in read_jsonl(BASE / "logic/notice_condition_sets.jsonl")}
    relations: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(DEV_LOGIC):
        relations.setdefault(row["notice_id"], []).append(row)
    qualifiers: dict[str, list[dict[str, Any]]] = {}
    for row in read_jsonl(DEV_QUALIFIERS):
        qualifiers.setdefault(row["notice_id"], []).append(row)
    by_notice: dict[str, list[dict[str, Any]]] = {}
    for row in dev_conditions:
        by_notice.setdefault(row["notice_id"], []).append(row)
    if development_ids_path is not None:
        selected_ids = json.loads(development_ids_path.read_text(encoding="utf-8"))
        if not isinstance(selected_ids, list) or len(selected_ids) != 30 or len(set(selected_ids)) != 30:
            raise ValueError("Development ID file must contain exactly 30 unique notice IDs")
        samples_by_id = {r["notice_id"]: r for r in dev}
        missing = sorted(set(selected_ids) - samples_by_id.keys())
        if missing:
            raise ValueError(f"Selected IDs are not in DEVELOPMENT: {missing}")
        dev_existing = [{"notice_id": nid, "raw_text": samples_by_id[nid]["raw_text"]} for nid in selected_ids]
    elif len(dev_existing) != 30:
        raise ValueError(f"Expected the existing 30-notice development review set, got {len(dev_existing)}")
    dev_ids = {r["notice_id"] for r in dev}
    eval_ids = {r["notice_id"] for r in evaluation}
    if dev_ids & eval_ids:
        raise ValueError("Development/evaluation sample overlap")
    if not {r["notice_id"] for r in dev_existing} <= dev_ids:
        raise ValueError("Development review packet contains a non-development notice")
    for row in dev_existing:
        sample = next(s for s in dev if s["notice_id"] == row["notice_id"])
        if row.get("raw_text") != sample["raw_text"] or row["notice_id"] not in dev_logic:
            raise ValueError(f"development review evidence mismatch for {row['notice_id']}")

    dev_map = {r["notice_id"]: r for r in dev}
    dev_condition_review = [condition_review_row(dev_map[r["notice_id"]], split="DEVELOPMENT",
                                                 candidates=by_notice.get(r["notice_id"], [])) for r in dev_existing]
    dev_review_ids = [r["notice_id"] for r in dev_condition_review]
    dev_logic_review = [logic_review_row(dev_map[nid], condition_row=condition,
                                         split="DEVELOPMENT", existing_logic=dev_logic[nid],
                                         relation_candidates=relations.get(nid, []),
                                         qualifier_candidates=qualifiers.get(nid, []))
                        for nid, condition in ((r["notice_id"], r) for r in dev_condition_review)]

    # Evaluation packets are constructed only from representative_samples.jsonl raw text.
    # No extraction, candidate-provenance, logic, or diagnostic file is read in this branch.
    evaluation_condition_review = [condition_review_row(sample, split="EVALUATION") for sample in evaluation]
    evaluation_logic_review = [logic_review_row(sample, condition_row=condition, split="EVALUATION")
                               for sample, condition in zip(evaluation, evaluation_condition_review)]

    for split, condition_rows, logic_rows in (
        ("development", dev_condition_review, dev_logic_review),
        ("evaluation", evaluation_condition_review, evaluation_logic_review),
    ):
        directory = output / split
        write_jsonl(directory / "condition_review.jsonl", condition_rows)
        write_jsonl(directory / "logic_review.jsonl", logic_rows)
        if split == "DEVELOPMENT":
            condition_columns = ["notice_id", "source_system", "source_field", "source_text", "existing_candidates",
                                 "gold_conditions", "missed_condition_candidates", "candidate_alignments", "review_status",
                                 "adjudication_status", "reviewer", "reviewed_at", "review_comment"]
            logic_columns = ["notice_id", "source_system", "source_text", "existing_condition_candidates",
                             "existing_logic_roots", "existing_relation_candidates", "existing_qualifier_candidates",
                             "condition_gold_ids", "gold_logic_roots", "gold_exceptions", "gold_benefits", "unresolved_relations",
                             "review_status", "adjudication_status", "reviewer", "reviewed_at", "review_comment"]
        else:
            condition_columns = ["notice_id", "source_system", "source_field", "source_text", "provided_text_scope",
                                 "source_text_completeness", "gold_conditions", "missed_condition_candidates",
                                 "review_status", "adjudication_status", "reviewer", "reviewed_at", "review_comment"]
            logic_columns = ["notice_id", "source_system", "source_text", "condition_gold_ids", "gold_logic_roots",
                             "gold_exceptions", "gold_benefits", "unresolved_relations", "review_status", "adjudication_status",
                             "reviewer", "reviewed_at", "review_comment"]
        write_csv(directory / "condition_review.csv", condition_rows, condition_columns)
        write_csv(directory / "logic_review.csv", logic_rows, logic_columns)
    output.mkdir(parents=True, exist_ok=True)
    (output / "baseline_manifest.json").write_text(json.dumps(baseline_manifest(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    manifest = {"development_notices": len(dev_condition_review), "evaluation_notices": len(evaluation_condition_review),
                "development_logic_notices": len(dev_logic_review), "evaluation_logic_notices": len(evaluation_logic_review),
                "development_evaluation_overlap": len(dev_ids & eval_ids),
                "evaluation_contains_model_outputs": False, "human_reviews_completed": 0,
                "development_records_unreviewed": sum(r["review_status"] == "UNREVIEWED" for r in dev_condition_review),
                "evaluation_records_unreviewed": sum(r["review_status"] == "UNREVIEWED" for r in evaluation_condition_review),
                "baseline_frozen": True, "reviewed_gold_conditions": 0}
    (output / "build_report.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    parser.add_argument("--development-ids", type=Path, default=None,
                        help="Optional UTF-8 JSON array of 30 existing DEVELOPMENT notice IDs")
    args = parser.parse_args()
    print(json.dumps(build(args.output_dir, args.development_ids), ensure_ascii=False, indent=2))
