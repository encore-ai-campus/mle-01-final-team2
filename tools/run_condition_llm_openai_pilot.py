"""Run the frozen 10-notice OpenAI direct LLM pilot and same-sample strict evaluation."""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import evaluate_condition_pipeline as v10
from tools import evaluate_condition_pipeline_v11 as v11
from tools import extract_condition_candidates_llm as llm

PREPARATION = ROOT / "data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development"
GOLD = ROOT / "data/goldsets/conditions/v1.1/20261126/final30/development"
SAMPLES = ROOT / "data/condition_inputs/v1/20261125/representative_samples.jsonl"
INPUTS = ROOT / "data/condition_inputs/v1/20261125/extraction_inputs.jsonl"
BASELINE_OUT = ROOT / "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl"
BASELINE_LOGIC = ROOT / "data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl"
RULE_E = ROOT / "data/evaluations/conditions/v1.1/20261126/development/rule_improved_2_5c/experiment_E/development_conditions.jsonl"
RULE_E_LOGIC = ROOT / "data/evaluations/conditions/v1.1/20261126/development/rule_improved_2_5c/experiment_E/logic/notice_condition_sets.jsonl"
OUT = ROOT / "data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_localrun"
N_TOTAL = 5116
PRIOR_BLOCKED_CONNECTION_ATTEMPTS = 1


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return v10.read_jsonl(path)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def verify_frozen_inputs(ids: list[str]) -> dict[str, Any]:
    manifest = read_json(PREPARATION / "pilot_manifest.json")
    gold_manifest = read_json(GOLD / "manifest.json")
    checks: dict[str, bool] = {}
    checks["pilot_ids_match"] = manifest.get("notice_ids") == ids and len(ids) == 10 and len(set(ids)) == 10
    checks["pilot_id_file_hash"] = digest(PREPARATION / "pilot_notice_ids.json") == manifest.get("ids_file_sha256")
    checks["pilot_input_hash"] = digest(INPUTS) == manifest.get("source_input", {}).get("sha256")
    checks["gold_finalized"] = (gold_manifest.get("status"), gold_manifest.get("schema_version"), gold_manifest.get("dataset_split")) == ("FINALIZED", "1.1", "DEVELOPMENT")
    checks["gold_condition_hash"] = digest(GOLD / "reviewed_condition_gold.jsonl") == gold_manifest.get("outputs", {}).get("reviewed_condition_gold.jsonl", {}).get("sha256")
    checks["gold_logic_hash"] = digest(GOLD / "reviewed_logic_gold.jsonl") == gold_manifest.get("outputs", {}).get("reviewed_logic_gold.jsonl", {}).get("sha256")
    checks["baseline_condition_hash"] = digest(BASELINE_OUT) == manifest["prediction_versions"]["baseline_v1"]["condition_sha256"]
    checks["baseline_logic_hash"] = digest(BASELINE_LOGIC) == manifest["prediction_versions"]["baseline_v1"]["logic_sha256"]
    checks["rule_e_condition_hash"] = digest(RULE_E) == manifest["prediction_versions"]["rule_experiment_E"]["condition_sha256"]
    checks["rule_e_logic_hash"] = digest(RULE_E_LOGIC) == manifest["prediction_versions"]["rule_experiment_E"]["logic_sha256"]
    checks["v11_evaluator_hash"] = digest(ROOT / "tools/evaluate_condition_pipeline_v11.py") == manifest["evaluation_policy"]["evaluator_sha256"]
    split = read_jsonl(SAMPLES)
    dev_ids = {r["notice_id"] for r in split if r.get("split") == "DEVELOPMENT"}
    eval_ids = {r["notice_id"] for r in split if r.get("split") == "EVALUATION"}
    checks["pilot_development_only"] = set(ids) <= dev_ids and not set(ids) & eval_ids
    checks["pilot_source_balance"] = Counter(n.split(":", 1)[0] for n in ids) == {"BIZINFO": 5, "KSTARTUP": 5}
    checks["gold_notice_coverage"] = set(ids) <= set(gold_manifest.get("notice_ids", []))
    if not all(checks.values()):
        raise RuntimeError("FROZEN_INPUT_PREFLIGHT_FAILED:" + ",".join(k for k, v in checks.items() if not v))
    return {"checks": checks, "pilot_manifest_sha256": digest(PREPARATION / "pilot_manifest.json"),
            "gold_manifest_sha256": digest(GOLD / "manifest.json"), "input_sha256": digest(INPUTS),
            "baseline_condition_sha256": digest(BASELINE_OUT), "baseline_logic_sha256": digest(BASELINE_LOGIC),
            "rule_e_condition_sha256": digest(RULE_E), "rule_e_logic_sha256": digest(RULE_E_LOGIC),
            "gold_condition_sha256": digest(GOLD / "reviewed_condition_gold.jsonl"),
            "gold_logic_sha256": digest(GOLD / "reviewed_logic_gold.jsonl"),
            "v11_evaluator_sha256": digest(ROOT / "tools/evaluate_condition_pipeline_v11.py")}


def prevalidation_predictions(intermediate_rows: list[dict[str, Any]], input_path: Path) -> list[dict[str, Any]]:
    inputs = {r["notice_id"]: r for r in read_jsonl(input_path)}
    predictions = []
    for result in intermediate_rows:
        nid = result["notice_id"]
        source = inputs[nid]["raw_text"]
        for index, proposed in enumerate(result.get("intermediate_response", {}).get("conditions", [])):
            quote = next(iter(proposed.get("evidence_quotes", [])), None)
            starts: list[int] = []
            at = 0
            while quote:
                at = source.find(quote, at)
                if at < 0:
                    break
                starts.append(at)
                at += 1
            start = starts[0] if len(starts) == 1 else None
            end = start + len(quote) if start is not None and quote else None
            predictions.append({
                "condition_id": f"RAW:{nid}:{index}", "notice_id": nid,
                "condition_type": proposed.get("condition_type"), "category_id": proposed.get("category_id"),
                "field": proposed.get("field"), "operator": proposed.get("operator"),
                "value": proposed.get("value"), "value_type": proposed.get("value_type"),
                "unit": proposed.get("unit"), "raw_text": quote,
                "source": {"source_field": proposed.get("source_field"), "location": {"start_char": start, "end_char": end},
                           "evidence_text": quote},
                "reference_date": {"value": proposed.get("reference_date"), "date_type": proposed.get("reference_date_type", "UNKNOWN")},
                "applicability_scope": proposed.get("applicability_scope"),
            })
    return predictions


def evaluate_conditions(gold_rows: list[dict[str, Any]], pred_rows: list[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    by_pred: dict[str, list[dict[str, Any]]] = {}
    for row in pred_rows:
        by_pred.setdefault(row["notice_id"], []).append(row)
    details, failures = [], []
    for row in sorted(gold_rows, key=lambda r: r["notice_id"]):
        gold = row.get("gold_conditions", []) + row.get("missed_condition_candidates", [])
        preds = by_pred.get(row["notice_id"], [])
        match = v11.match_notice(gold, preds)
        details.append({"notice_id": row["notice_id"], "source_system": row["source_system"],
                        "condition_count": len(gold), "prediction_count": len(preds), **match["metrics"],
                        "partial_match_count": match["partial_count"],
                        "exact_matches": [p["gold_id"] + "=" + p["prediction_id"] for p in match["pairs"] if p["status"] == "EXACT_MATCH"],
                        "partial_matches": [p["gold_id"] + "=" + p["prediction_id"] for p in match["pairs"] if p["status"] == "PARTIAL_MATCH"],
                        "false_negative_ids": match["unmatched_gold"], "false_positive_ids": match["unmatched_predictions"]})
        for pair in match["pairs"]:
            if pair["status"] != "EXACT_MATCH":
                failures.append({"notice_id": row["notice_id"], "source_system": row["source_system"], "status": pair["status"],
                                 "gold_id": pair["gold_id"], "prediction_id": pair["prediction_id"],
                                 "differences": ";".join(pair["differences"]),
                                 "gold": json.dumps(pair["gold"], ensure_ascii=False, sort_keys=True),
                                 "prediction": json.dumps(pair["prediction"], ensure_ascii=False, sort_keys=True)})
        gold_by_id = {v11._identity(g): g for g in gold}
        pred_by_id = {v11._identity(p): p for p in preds}
        for gid in match["unmatched_gold"]:
            failures.append({"notice_id": row["notice_id"], "source_system": row["source_system"], "status": "FALSE_NEGATIVE",
                             "gold_id": gid, "prediction_id": "", "differences": "CONDITION_MISSING",
                             "gold": json.dumps(gold_by_id.get(gid, {}), ensure_ascii=False, sort_keys=True), "prediction": ""})
        for pid in match["unmatched_predictions"]:
            failures.append({"notice_id": row["notice_id"], "source_system": row["source_system"], "status": "FALSE_POSITIVE",
                             "gold_id": "", "prediction_id": pid, "differences": "NO_EXACT_OR_PARTIAL_MATCH",
                             "gold": "", "prediction": json.dumps(pred_by_id.get(pid, {}), ensure_ascii=False, sort_keys=True)})
    def summary(subset: list[dict[str, Any]]) -> dict[str, Any]:
        metrics = v11.prf(*(sum(d[k] for d in subset) for k in ("tp", "fp", "fn")))
        defined = [d["f1"] for d in subset if d["f1"] is not None]
        return {**metrics, "notice_count": len(subset), "macro_f1": sum(defined) / len(defined) if defined else None,
                "partial_match_count": sum(d["partial_match_count"] for d in subset),
                "notices_with_misses": sum(d["fn"] > 0 for d in subset),
                "notices_with_false_positives": sum(d["fp"] > 0 for d in subset),
                "zero_prediction_notices": sum(d["prediction_count"] == 0 for d in subset)}
    overall = summary(details)
    per_source = {s: summary([d for d in details if d["source_system"] == s]) for s in sorted({d["source_system"] for d in details})}
    types = sorted({str(c.get("condition_type")) for r in gold_rows for c in r.get("gold_conditions", []) + r.get("missed_condition_candidates", [])} |
                   {str(c.get("condition_type")) for c in pred_rows})
    per_type = {}
    for kind in types:
        target = sum(c.get("condition_type") == kind for r in gold_rows for c in r.get("gold_conditions", []) + r.get("missed_condition_candidates", []))
        predicted = [c for c in pred_rows if c.get("condition_type") == kind]
        tp = sum(pair == 1 for d in details for pair in [])
        # Reuse one-to-one exact matching at the notice level for TP by type.
        for row in gold_rows:
            matching = v11.match_notice([c for c in row.get("gold_conditions", []) + row.get("missed_condition_candidates", []) if c.get("condition_type") == kind],
                                       [c for c in by_pred.get(row["notice_id"], []) if c.get("condition_type") == kind])
            tp += matching["metrics"]["tp"]
        per_type[kind] = v11.prf(tp, len(predicted) - tp, target - tp)
    return {"micro": overall, "by_source": per_source, "by_condition_type": per_type}, details, failures


def comparison_rows(named: dict[str, tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows, summaries = [], {}
    for name, (summary, details, _) in named.items():
        summaries[name] = summary
        rows.append({"model": name, "scope": "OVERALL", **summary["micro"]})
        for source, metrics in summary["by_source"].items():
            rows.append({"model": name, "scope": f"SOURCE:{source}", **metrics})
        for kind, metrics in summary["by_condition_type"].items():
            rows.append({"model": name, "scope": f"TYPE:{kind}", **metrics})
    return rows, summaries


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    output = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    if output.exists() and any(output.iterdir()):
        parser.error("output directory must be new or empty; refusing to overwrite pilot artifacts")
    ids_path = PREPARATION / "pilot_notice_ids.json"
    ids = read_json(ids_path)
    frozen = verify_frozen_inputs(ids)
    status = llm.llm_connection_status(args.env_file, provider_override="openai_direct")
    if not status["configured"]:
        raise SystemExit("BLOCKED_CONFIGURATION: missing OpenAI key/model or installed SDK; values were not displayed")
    env = llm.load_env_safely(args.env_file)
    model = env["OPENAI_CHAT_MODEL"]
    provider = llm.configured_provider(args.env_file, provider_override="openai_direct")
    # One initial connection attempt was blocked by the local network sandbox.
    # Count that attempt against the global cap; this run gets the 11 remaining.
    budget = llm.RequestBudget(12 - PRIOR_BLOCKED_CONNECTION_ATTEMPTS)
    started = time.monotonic()
    synthetic_row = {"notice_id": "SYNTHETIC:STRUCTURED_JSON_PREFLIGHT", "source_system": "SYNTHETIC",
                     "title": "Synthetic preflight only", "raw_text": "Applicants must be at least 18 years old.",
                     "completeness_status": "UNKNOWN"}
    try:
        synthetic, attempts, usage, _ = asyncio.run(llm.call_and_parse(provider, synthetic_row,
                        max_format_attempts=1, request_budget=budget))
        if not isinstance(synthetic, dict) or not isinstance(synthetic.get("conditions"), list):
            raise RuntimeError("SYNTHETIC_STRUCTURED_OUTPUT_INVALID")
    except llm.ExtractionFailure as exc:
        output.mkdir(parents=True, exist_ok=True)
        write_json(output / "preflight_blocker.json", {"status": "BLOCKED_STRUCTURED_JSON_PREFLIGHT",
                    "error_code": exc.detail_code, "error_type": exc.status,
                    "model_id": model, "current_run_request_attempts": budget.used,
                    "prior_connection_attempts_conservatively_reserved": PRIOR_BLOCKED_CONNECTION_ATTEMPTS,
                    "prior_connection_attempt_delivery_confirmed": False,
                    "conservative_total_request_count": PRIOR_BLOCKED_CONNECTION_ATTEMPTS + budget.used,
                    "request_limit": 12,
                    "secret_logged": False})
        raise SystemExit("BLOCKED_STRUCTURED_JSON_PREFLIGHT: check recorded without saving credentials")
    preflight_record = {"model_access": "PASS via successful synthetic completion", "synthetic_structured_json": "PASS",
                        "synthetic_valid_intermediate": True, "synthetic_attempts": attempts,
                        "synthetic_token_usage": usage, "requests_used_before_pilot": budget.used,
                        "current_run_request_budget": budget.limit, "global_request_limit": 12,
                        "prior_blocked_connection_attempts": PRIOR_BLOCKED_CONNECTION_ATTEMPTS,
                        "prior_blocked_connection_attempt_delivery_confirmed": False,
                        "elapsed_ms": round((time.monotonic() - started) * 1000),
                        "model_id": model, "endpoint": "OpenAI official SDK default", "secret_logged": False}
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "api_preflight.json", preflight_record)
    run_started = time.monotonic()
    run_report = asyncio.run(llm.run_pilot(provider, ids, output_dir=output, request_budget=budget, max_format_attempts=1))
    total_request_attempts = PRIOR_BLOCKED_CONNECTION_ATTEMPTS + run_report["api_request_count"]
    if total_request_attempts > 12 or run_report["notice_count"] != 10:
        raise RuntimeError("PILOT_BUDGET_OR_SCOPE_VIOLATION")
    run_report["api_request_count_current_run_attempts"] = run_report["api_request_count"]
    run_report["prior_connection_attempts_reserved"] = PRIOR_BLOCKED_CONNECTION_ATTEMPTS
    run_report["prior_connection_attempt_delivery_confirmed"] = False
    run_report["api_request_count_conservative_total"] = total_request_attempts
    write_json(output / "run_report.json", run_report)
    if run_report["failure_count"]:
        outputs = [p for p in output.iterdir() if p.is_file() and p.name != "manifest.json"]
        write_json(output / "manifest.json", {
            "status": "PILOT_INCOMPLETE_NO_SCORING", "model_id": model,
            "notice_ids": ids, "notice_status_counts": run_report["status_counts"],
            "api_request_count_current_run_attempts": run_report["api_request_count"],
            "prior_connection_attempts_reserved": PRIOR_BLOCKED_CONNECTION_ATTEMPTS,
            "prior_connection_attempt_delivery_confirmed": False,
            "api_request_count_conservative_total": total_request_attempts,
            "request_limit": 12, "output_hashes": {p.name: digest(p) for p in sorted(outputs)},
            "gold_data_read": False, "scores_computed": False, "secret_written": False,
        })
        (output / "PILOT_INCOMPLETE_REPORT.md").write_text(
            "# LLM pilot incomplete — no scoring\n\nAt least one frozen notice call failed. Partial outputs and failure codes are preserved; no baseline or goldset scoring was performed.\n",
            encoding="utf-8")
        return 2

    # Evaluation data is opened only after all LLM predictions have been persisted.
    gold = [r for r in read_jsonl(GOLD / "reviewed_condition_gold.jsonl") if r["notice_id"] in set(ids)]
    baseline = [r for r in read_jsonl(BASELINE_OUT) if r["notice_id"] in set(ids)]
    rule_e = [r for r in read_jsonl(RULE_E) if r["notice_id"] in set(ids)]
    prevalidation = prevalidation_predictions(read_jsonl(output / "intermediate_responses.jsonl"), INPUTS)
    postvalidation = read_jsonl(output / "llm_condition_predictions.jsonl")
    evaluated = {}
    for name, preds in (("baseline_v1", baseline), ("rule_experiment_E", rule_e),
                        ("llm_pre_validation", prevalidation), ("llm_post_validation", postvalidation)):
        summary, details, failures = evaluate_conditions(gold, preds)
        evaluated[name] = (summary, details, failures)
    comparison, summaries = comparison_rows(evaluated)
    write_csv(output / "pilot_baseline_comparison.csv", comparison)
    condition_details = [{"system": system, **row} for system, (_, details, _) in evaluated.items() for row in details]
    write_csv(output / "condition_match_details.csv", condition_details)
    all_failures = [{"system": system, **row} for system, (_, _, failures) in evaluated.items() for row in failures]
    write_csv(output / "failure_analysis.csv", all_failures)

    total_usage = run_report.get("usage", {})
    avg_in = total_usage.get("prompt_tokens", 0) / max(1, len(ids))
    avg_out = total_usage.get("completion_tokens", 0) / max(1, len(ids))
    estimated_in = round(avg_in * N_TOTAL)
    estimated_out = round(avg_out * N_TOTAL)
    extrapolated_cost = (estimated_in * 0.20 + estimated_out * 1.20) / 1_000_000
    duration_rows = read_jsonl(output / "per_notice_execution.jsonl")
    report = {
        "status": "PILOT_COMPLETED", "mode": "llm_only", "model_id": model,
        "provider": "openai_direct", "endpoint": "OpenAI official SDK default",
        "structured_output_mode": "Chat Completions JSON object mode; local v1.1 intermediate schema validation",
        "sample_notice_ids": ids, "source_counts": {"BIZINFO": 5, "KSTARTUP": 5},
        "sample_is_diagnostic_not_representative": True, "condition_gold_count": sum(len(r.get("gold_conditions", [])) + len(r.get("missed_condition_candidates", [])) for r in gold),
        "request_count_including_initial_blocked_attempt_and_synthetic": total_request_attempts, "request_limit": 12,
        "current_run_request_attempts": run_report["api_request_count"],
        "prior_connection_attempts_conservatively_reserved": PRIOR_BLOCKED_CONNECTION_ATTEMPTS,
        "prior_connection_attempt_delivery_confirmed": False,
        "sdk_retries": 0, "notice_format_retries": 0, "prompt_sha256": run_report["prompt_sha256"],
        "usage": total_usage, "elapsed_ms": sum(r["duration_ms"] for r in duration_rows),
        "wall_elapsed_ms": round((time.monotonic() - run_started) * 1000),
        "evaluation": summaries, "condition_metrics_only": True, "logic_semantics_scored": False,
        "cost_estimate": {"pricing_source": "OpenAI GPT-5.6 Luna model page", "input_usd_per_million": 0.20,
                          "output_usd_per_million": 1.20, "notices_extrapolated": N_TOTAL,
                          "pilot_mean_input_tokens_per_notice": avg_in, "pilot_mean_output_tokens_per_notice": avg_out,
                          "estimated_total_input_tokens": estimated_in, "estimated_total_output_tokens": estimated_out,
                          "estimated_usd": round(extrapolated_cost, 6),
                          "caveat": "Pilot is diagnostic and enriched for failure types; this is a rough extrapolation, excluding caching and any prompt/input distribution shift."},
        "frozen_inputs": frozen, "gold_data_sent_to_model": False,
        "evaluation_split_used": False, "notice_count_scored": 10,
        "all_candidates_unreviewed": True, "decision_eligible_true_count": 0,
        "secret_or_endpoint_customized": False,
    }
    write_json(output / "evaluation_summary.json", report)
    report_lines = ["# OpenAI LLM structured extraction pilot (2026-11-26)", "",
                    f"- Model: `{model}`", "- Scope: fixed development diagnostic sample of 10 notices (5 BIZINFO, 5 K-Startup); not representative.",
                    f"- Conservative request tally: {total_request_attempts}/12, including one earlier connection attempt whose delivery was not confirmed.",
                    f"- Prompt tokens: {total_usage.get('prompt_tokens', 0)}; completion tokens: {total_usage.get('completion_tokens', 0)}.",
                    f"- Elapsed notice time: {report['elapsed_ms']} ms.", "- No logic semantic score was calculated.",
                    f"- Rough 5,116-notice cost estimate: USD {extrapolated_cost:.6f}, extrapolated from this diagnostic sample; do not treat as quote.", "",
                    "## Strict condition metrics", "", "| System | TP | FP | FN | Precision | Recall | F1 | Macro F1 | Partial |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, value in summaries.items():
        m = value["micro"]
        report_lines.append(f"| {name} | {m['tp']} | {m['fp']} | {m['fn']} | {m['precision']:.4f} | {m['recall']:.4f} | {m['f1']:.4f} | {m['macro_f1']:.4f} | {m['partial_match_count']} |")
    report_lines += ["", "## Artifacts", "", "See `pilot_baseline_comparison.csv`, `condition_match_details.csv`, `failure_analysis.csv`, raw response and pre/post-validation JSONL files, `run_report.json`, and `manifest.json`.",
                     "", "All LLM candidates remain `UNREVIEWED`; the output is not an applicant decision.", ""]
    (output / "LLM_PILOT_REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")
    outputs = [p for p in output.iterdir() if p.is_file() and p.name != "manifest.json"]
    manifest = {"status": "PILOT_COMPLETED", "model_id": model, "prompt_version": llm.PROMPT_VERSION,
                "prompt_sha256": run_report["prompt_sha256"], "evaluation_policy": v11.POLICY_VERSION,
                "notice_ids": ids, "request_count": total_request_attempts,
                "current_run_request_attempts": run_report["api_request_count"],
                "prior_connection_attempts_conservatively_reserved": PRIOR_BLOCKED_CONNECTION_ATTEMPTS,
                "prior_connection_attempt_delivery_confirmed": False, "request_limit": 12,
                "input_hashes": frozen, "output_hashes": {p.name: digest(p) for p in sorted(outputs)},
                "secret_written": False, "gold_sent_to_model": False, "evaluation_split_used": False}
    write_json(output / "manifest.json", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
