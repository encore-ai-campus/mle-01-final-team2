"""Generate and strictly score A-E extraction experiments against fixed development gold."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import build_condition_logic, evaluate_condition_pipeline, evaluate_condition_pipeline_v11  # noqa: E402
from tools.extract_condition_candidates_rules_v2 import OUT, run_all  # noqa: E402

GOLD_DIR = ROOT / "data/goldsets/conditions/v1.1/20261126/final30/development"
BASELINE_DIR = ROOT / "data/evaluations/conditions/v1.1/20261126/development/baseline_v1"
V1 = ROOT / "data/condition_inputs/v1/20261125"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metric_row(mode: str, result: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    common, base_common = result["common"], baseline["common"]
    return {
        "experiment": mode,
        "tp": common["micro"]["tp"], "fp": common["micro"]["fp"], "fn": common["micro"]["fn"],
        "precision": common["micro"]["precision"], "recall": common["micro"]["recall"], "f1": common["micro"]["f1"],
        "macro_f1": common["macro_by_notice"]["f1"],
        "baseline_tp_retained": sum(n["common"]["tp"] for n in result["notices"]) >= base_common["micro"]["tp"],
        "partial_matches": sum(n.get("partial_count", 0) for n in result["notices"]),
        "zero_prediction_notices": sum(n["common"]["tp"] + n["common"]["fp"] == 0 for n in result["notices"]),
        "safety_error_count": sum(len(n.get("safety_errors", [])) for n in result["notices"]),
        "bizinfo_f1": common["by_source"].get("BIZINFO", {}).get("f1"),
        "kstartup_f1": common["by_source"].get("KSTARTUP", {}).get("f1"),
        "eligibility_tp": common["by_condition_type"].get("ELIGIBILITY", {}).get("tp", 0),
        "eligibility_fp": common["by_condition_type"].get("ELIGIBILITY", {}).get("fp", 0),
        "exclusion_tp": common["by_condition_type"].get("EXCLUSION", {}).get("tp", 0),
        "exclusion_fp": common["by_condition_type"].get("EXCLUSION", {}).get("fp", 0),
        "preference_tp": common["by_condition_type"].get("PREFERENCE", {}).get("tp", 0),
        "preference_fp": common["by_condition_type"].get("PREFERENCE", {}).get("fp", 0),
    }


def remaining_failures(result: dict[str, Any], gold_rows: list[dict[str, Any]],
                       prediction_rows: list[dict[str, Any]], path: Path) -> None:
    gold_by_notice = {r["notice_id"]: r for r in gold_rows}
    pred_by_id = {p["condition_id"]: p for p in prediction_rows}
    records = []

    def add(nid: str, failure_type: str, gold_id: str | None, pred_id: str | None, differences: list[str] | None = None):
        g_row = gold_by_notice[nid]
        gold_items = {c.get("gold_condition_id") or c.get("condition_id"): c
                      for c in g_row.get("gold_conditions", []) + g_row.get("missed_condition_candidates", [])}
        g, p = gold_items.get(gold_id), pred_by_id.get(pred_id)
        origin = g_row.get("source_text", "")
        target = g or p or {}
        loc = (g or {}).get("evidence_reference") or (p or {}).get("source", {}).get("location") or {}
        start, end = loc.get("start_char", loc.get("start", 0)), loc.get("end_char", loc.get("end", 0))
        excerpt = origin[start:end] if isinstance(start, int) and isinstance(end, int) and end >= start else ""
        records.append({
            "notice_id": nid, "source_system": g_row["source_system"], "failure_type": failure_type,
            "gold_id": gold_id, "prediction_id": pred_id,
            "gold_field": (g or {}).get("field"), "prediction_field": (p or {}).get("field"),
            "gold_condition": json.dumps(g, ensure_ascii=False, sort_keys=True) if g else "",
            "prediction_condition": json.dumps(p, ensure_ascii=False, sort_keys=True) if p else "",
            "source_excerpt": excerpt, "differences": ";".join(differences or []),
            "failure_cause": "STRICT_UNMATCHED_OR_PARTIAL", "cause_confidence": "SYMPTOM_ONLY"
        })

    for notice in result["notices"]:
        nid = notice["notice_id"]
        partial_gold, partial_pred = set(), set()
        for pair in notice["pairs"]:
            if pair["status"] == "PARTIAL_MATCH":
                partial_gold.add(pair["gold_id"]); partial_pred.add(pair["prediction_id"])
                add(nid, "PARTIAL_MATCH_STRICT_FN_AND_FP", pair["gold_id"], pair["prediction_id"], pair.get("differences"))
        for gid in notice["false_negative_ids"]:
            if gid not in partial_gold:
                add(nid, "FALSE_NEGATIVE", gid, None)
        for pid in notice["false_positive_ids"]:
            if pid not in partial_pred:
                add(nid, "FALSE_POSITIVE", None, pid)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]) if records else ["notice_id", "failure_type"])
        writer.writeheader(); writer.writerows(records)


def evaluate(output_dir: Path = OUT) -> dict[str, Any]:
    output_dir = Path(output_dir)
    # All extraction output is generated before the gold directory is read.
    generation = run_all(output_dir)

    gold_condition_rows = read_jsonl(GOLD_DIR / "reviewed_condition_gold.jsonl")
    gold_logic_rows = read_jsonl(GOLD_DIR / "reviewed_logic_gold.jsonl")
    base_predictions = read_jsonl(V1 / "extracted/improved/development_conditions.jsonl")
    base_logic = read_jsonl(V1 / "logic/notice_condition_sets.jsonl")
    rows_by_id = {r["notice_id"]: r for r in read_jsonl(V1 / "extraction_inputs.jsonl")}
    baseline_result = evaluate_condition_pipeline_v11.evaluate_records(
        gold_condition_rows, gold_logic_rows, base_predictions, base_logic)

    # The logic transformer is reused as-is; only its input path is changed in memory.
    original_conditions_path, original_out = build_condition_logic.CONDITIONS, build_condition_logic.OUT
    results: dict[str, Any] = {}
    rows = []
    try:
        for mode in ("A", "B", "C", "D", "E"):
            prediction_path = output_dir / f"experiment_{mode}/development_conditions.jsonl"
            logic_dir = output_dir / f"experiment_{mode}/logic"
            build_condition_logic.CONDITIONS = prediction_path
            build_condition_logic.build(logic_dir)
            predictions = read_jsonl(prediction_path)
            logic_predictions = read_jsonl(logic_dir / "notice_condition_sets.jsonl")
            schema_validator = evaluate_condition_pipeline.schema_validators()["condition-v1.schema.json"]
            schema_errors = sum(len(list(schema_validator.iter_errors(c))) for c in predictions)
            evidence_errors = 0
            condition_ids = [c.get("condition_id") for c in predictions]
            duplicate_condition_ids = len(condition_ids) - len(set(condition_ids))
            for c in predictions:
                src = c.get("source", {})
                loc = src.get("location") or {}
                start, end = loc.get("start_char"), loc.get("end_char")
                original = rows_by_id.get(c.get("notice_id"))
                if (original is None or not isinstance(start, int) or not isinstance(end, int)
                        or start < 0 or end < start
                        or original["raw_text"][start:end] != c.get("raw_text")
                        or c.get("raw_text") != src.get("evidence_text")):
                    evidence_errors += 1
            scored = evaluate_condition_pipeline_v11.evaluate_records(
                gold_condition_rows, gold_logic_rows, predictions, logic_predictions)
            (output_dir / f"experiment_{mode}/evaluation_summary.json").write_text(
                json.dumps(scored, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            info = metric_row(mode, scored, baseline_result)
            info["prediction_sha256"] = sha256(prediction_path)
            info["schema_errors"] = schema_errors
            info["evidence_integrity_errors"] = evidence_errors
            info["duplicate_condition_ids"] = duplicate_condition_ids
            info["all_review_status_unreviewed"] = all(c.get("review_status") in {"UNREVIEWED", "NEEDS_REVIEW"} for c in predictions)
            info["decision_eligible_true_count"] = sum(c.get("decision_eligible") is True for c in predictions)
            info["prediction_count"] = len(predictions)
            info["logic_structure_exact_notices"] = sum(n["logic"].get("notice_structure_exact") is True for n in scored["notices"])
            info["_result"] = scored
            results[mode] = info
            rows.append(info)
    finally:
        build_condition_logic.CONDITIONS = original_conditions_path
        build_condition_logic.OUT = original_out

    remaining_failures(results["E"]["_result"], gold_condition_rows,
                       read_jsonl(output_dir / "experiment_E/development_conditions.jsonl"),
                       output_dir / "remaining_failure_analysis.csv")
    for info in results.values():
        info.pop("_result", None)

    with (output_dir / "experiment_comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = {
        "status": "COMPLETED_DEVELOPMENT_EXPERIMENTS",
        "policy_version": "1.1.0",
        "data_version": "v1",
        "scored_notice_count": 30,
        "development_split_size": 80,
        "gold_ids_used_during_generation": False,
        "evaluation_split_used": False,
        "legacy_mode_default_enabled": False,
        "baseline": baseline_result["common"]["micro"],
        "baseline_macro_f1": baseline_result["common"]["macro_by_notice"]["f1"],
        "integrity": {"all_modes_schema_errors_zero": all(r["schema_errors"] == 0 for r in results.values()),
                      "all_modes_evidence_integrity_errors_zero": all(r["evidence_integrity_errors"] == 0 for r in results.values()),
                      "all_modes_duplicate_condition_ids_zero": all(r["duplicate_condition_ids"] == 0 for r in results.values()),
                      "all_review_states_pending": all(r["all_review_status_unreviewed"] for r in results.values()),
                      "decision_eligible_true_count": sum(r["decision_eligible_true_count"] for r in results.values())},
        "experiments": results,
        "generation_summary": generation,
    }
    (output_dir / "experiment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.output_dir), ensure_ascii=False, indent=2))
