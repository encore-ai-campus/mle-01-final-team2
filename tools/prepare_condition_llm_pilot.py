"""Freeze a stratified 10-notice DEVELOPMENT pilot and same-sample baselines.

This preparation tool reads the finalized DEVELOPMENT goldset for sampling and
evaluation only. The LLM extractor consumes only pilot_notice_ids.json plus the
version-v1 extraction inputs; it never receives the gold records.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.evaluate_condition_pipeline import read_jsonl
from tools.evaluate_condition_pipeline_v11 import evaluate_records, preflight
from tools.extract_condition_candidates_llm import PROMPT_VERSION, system_prompt

GOLD_DIR = ROOT / "data/goldsets/conditions/v1.1/20261126/final30/development"
BASELINE_DIR = ROOT / "data/evaluations/conditions/v1.1/20261126/development/baseline_v1"
RULE_DIR = ROOT / "data/evaluations/conditions/v1.1/20261126/development/rule_improved_2_5c/experiment_E"
RULE_MANIFEST = ROOT / "data/evaluations/conditions/v1.1/20261126/development/rule_improved_2_5c/manifest.json"
INPUTS = ROOT / "data/condition_inputs/v1/20261125/extraction_inputs.jsonl"
SAMPLES = ROOT / "data/condition_inputs/v1/20261125/representative_samples.jsonl"
EVALUATION_IDS = ROOT / "data/goldsets/conditions/v1/20261126_balanced/evaluation/condition_review.jsonl"
SEED = 20261126
OUTPUT = ROOT / "data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development"

# Required diagnostic anchors and curated coverage slots. These exact records
# are selected from the finalized 30; deterministic seeded ranks resolve any
# future tied candidates within a slot.
ANCHORS = {
    "BIZINFO:PBLN_000000000118182": "Required high-impact failure case: organization branches, exception, AND/OR.",
    "KSTARTUP:178507": "Required high-impact failure case: applicant branches, exclusions, temporal duty and exception.",
}
STRATIFIED_SELECTION = {
    "BIZINFO:PBLN_000000000117168": "Region plus applicant address, sustained-date condition, and AND scope.",
    "BIZINFO:PBLN_000000000119490": "Employee threshold and regional hiring branches with AND/OR structure.",
    "BIZINFO:PBLN_000000000126490": "No existing rule candidates; same-right IP attributes and unresolved binding.",
    "BIZINFO:PBLN_000000000128028": "No existing rule candidates; applicant branches and basic/optional duties.",
    "KSTARTUP:176001": "Simple numeric, business-age, and revenue-share thresholds.",
    "KSTARTUP:176813": "Applicant/business OR branch, preference conditions, and an exception.",
    "KSTARTUP:177447": "Team age condition with military-service age-band exception and evidence duties.",
    "KSTARTUP:179386": "Preference condition, open industry scope, and unresolved requirement relation.",
}
SELECTED_REASONS = {**ANCHORS, **STRATIFIED_SELECTION}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def count_groups(node: Any) -> int:
    if isinstance(node, list):
        return sum(count_groups(x) for x in node)
    if not isinstance(node, dict):
        return 0
    return (1 if node.get("node_type") == "LOGICAL_GROUP" else 0) + sum(count_groups(v) for v in node.values())


def ops_in(node: Any) -> Counter:
    found: Counter = Counter()
    if isinstance(node, list):
        for item in node:
            found.update(ops_in(item))
    elif isinstance(node, dict):
        if node.get("node_type") == "LOGICAL_GROUP":
            found[node.get("operator", "UNKNOWN")] += 1
        for value in node.values():
            found.update(ops_in(value))
    return found


def _assert_frozen_inputs(gold_manifest: dict[str, Any]) -> dict[str, Any]:
    cond_path = ROOT / "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl"
    logic_path = ROOT / "data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl"
    readiness = preflight(GOLD_DIR, cond_path, logic_path)
    if readiness["status"] != "PASS":
        raise RuntimeError("Frozen v1.0 baseline preflight failed: " + ",".join(readiness["errors"]))
    rule_manifest = json.loads(RULE_MANIFEST.read_text(encoding="utf-8"))
    if rule_manifest.get("goldset_version") != gold_manifest.get("goldset_version") or rule_manifest.get("evaluation_split_used") is not False:
        raise RuntimeError("Rule experiment does not match finalized DEVELOPMENT goldset/version")
    for rel in ("development_conditions.jsonl", "logic/notice_condition_sets.jsonl"):
        path = RULE_DIR / rel
        registered = next((v for v in rule_manifest.get("outputs", {}).values()
                           if v.get("path", "").replace("\\", "/").endswith(f"/experiment_E/{rel}")), None)
        if not path.exists() or not registered or registered.get("sha256") != sha256(path):
            raise RuntimeError(f"Rule experiment prediction hash mismatch: {rel}")
    return {"frozen_baseline_preflight": readiness, "rule_manifest_sha256": sha256(RULE_MANIFEST),
            "rule_manifest_goldset_version": rule_manifest["goldset_version"]}


def build() -> dict[str, Any]:
    gold_manifest_path = GOLD_DIR / "manifest.json"
    gold_manifest = json.loads(gold_manifest_path.read_text(encoding="utf-8"))
    if gold_manifest.get("status") != "FINALIZED" or gold_manifest.get("dataset_split") != "DEVELOPMENT":
        raise RuntimeError("Finalized DEVELOPMENT goldset required")
    baseline_inputs = _assert_frozen_inputs(gold_manifest)

    gold_rows = read_jsonl(GOLD_DIR / "reviewed_condition_gold.jsonl")
    logic_rows = read_jsonl(GOLD_DIR / "reviewed_logic_gold.jsonl")
    gold_by_id = {r["notice_id"]: r for r in gold_rows}
    logic_by_id = {r["notice_id"]: r for r in logic_rows}
    if len(gold_by_id) != 30 or len(logic_by_id) != 30 or set(gold_by_id) != set(logic_by_id):
        raise RuntimeError("Finalized goldset must contain 30 matching condition and logic notices")
    if set(SELECTED_REASONS) - set(gold_by_id):
        raise RuntimeError("Pilot selection ID outside finalized 30-notice goldset")
    selected_ids = sorted(SELECTED_REASONS)
    by_source = Counter(gold_by_id[nid]["source_system"] for nid in selected_ids)
    if by_source != {"BIZINFO": 5, "KSTARTUP": 5}:
        raise RuntimeError(f"Pilot source allocation is invalid: {by_source}")

    dev_ids = {r["notice_id"] for r in read_jsonl(SAMPLES) if r.get("split") == "DEVELOPMENT"}
    eval_ids = {r["notice_id"] for r in read_jsonl(EVALUATION_IDS)}
    if not set(selected_ids) <= dev_ids or set(selected_ids) & eval_ids:
        raise RuntimeError("Pilot sample has a split mismatch or evaluation overlap")
    input_rows = {r["notice_id"]: r for r in read_jsonl(INPUTS)}
    if not set(selected_ids) <= set(input_rows):
        raise RuntimeError("Pilot notice missing from version-v1 extraction inputs")

    baseline_predictions = read_jsonl(ROOT / "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl")
    baseline_logic = read_jsonl(ROOT / "data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl")
    rule_predictions = read_jsonl(RULE_DIR / "development_conditions.jsonl")
    rule_logic = read_jsonl(RULE_DIR / "logic/notice_condition_sets.jsonl")
    # Shared evaluation implementation and policy; filter to this frozen sample in memory.
    sample_gold = [gold_by_id[nid] for nid in selected_ids]
    sample_logic_gold = [logic_by_id[nid] for nid in selected_ids]
    base_result = evaluate_records(sample_gold, sample_logic_gold, baseline_predictions, baseline_logic)
    rule_result = evaluate_records(sample_gold, sample_logic_gold, rule_predictions, rule_logic)
    base_counts = Counter(r["notice_id"] for r in baseline_predictions)
    rule_counts = Counter(r["notice_id"] for r in rule_predictions)
    for result, counts in ((base_result, base_counts), (rule_result, rule_counts)):
        for notice_detail in result["notices"]:
            notice_detail["prediction_count"] = counts[notice_detail["notice_id"]]

    source_titles = {nid: input_rows[nid].get("title") or "" for nid in selected_ids}
    rows = []
    for rank, nid in enumerate(selected_ids, 1):
        gold = gold_by_id[nid]
        conds = gold.get("gold_conditions", []) + gold.get("missed_condition_candidates", [])
        logic = logic_by_id[nid]
        base_num = sum(p["notice_id"] == nid for p in baseline_predictions)
        rule_num = sum(p["notice_id"] == nid for p in rule_predictions)
        rows.append({
            "rank": rank, "notice_id": nid, "source_system": gold["source_system"], "title": source_titles[nid],
            "selection_reason": SELECTED_REASONS[nid], "condition_count": len(conds),
            "condition_types": ";".join(f"{k}:{v}" for k, v in sorted(Counter(c["condition_type"] for c in conds).items())),
            "logical_operators": ";".join(f"{k}:{v}" for k, v in sorted(ops_in(logic.get("gold_logic_roots", [])).items())),
            "exception_count": len(logic.get("gold_exceptions", [])),
            "unresolved_relation_count": len(logic.get("unresolved_relations", [])),
            "baseline_prediction_count": base_num, "rule_E_prediction_count": rule_num,
            "no_rule_conditions_found": rule_num == 0,
            "source_excerpt_sha256": hashlib.sha256(input_rows[nid]["raw_text"].encode("utf-8")).hexdigest(),
        })
    OUTPUT.mkdir(parents=True, exist_ok=True)
    id_path = OUTPUT / "pilot_notice_ids.json"
    id_path.write_text(json.dumps(selected_ids, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (OUTPUT / "pilot_selection.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    comparison = metric_rows(base_result, rule_result)
    with (OUTPUT / "pilot_baseline_comparison.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(comparison[0]))
        writer.writeheader(); writer.writerows(comparison)
    condition_type_counts = Counter()
    exception_count = unresolved_count = logic_group_count = 0
    for nid in selected_ids:
        condition_row = gold_by_id[nid]
        conds = condition_row.get("gold_conditions", []) + condition_row.get("missed_condition_candidates", [])
        condition_type_counts.update(c["condition_type"] for c in conds)
        logic = logic_by_id[nid]
        exception_count += len(logic.get("gold_exceptions", []))
        unresolved_count += len(logic.get("unresolved_relations", []))
        logic_group_count += count_groups(logic.get("gold_logic_roots", []))
    total_conditions = sum(condition_type_counts.values())
    manifest = {
        "status": "PILOT_SAMPLE_FROZEN_PRE_CALL", "purpose": "DEVELOPMENT_DIAGNOSTIC_NOT_REPRESENTATIVE",
        "selection_seed": SEED, "selection_method": "Required failure anchors plus stratified diagnostic slots; no unresolved ties after slot constraints.",
        "tie_break_policy": "If future equally ranked candidates tie for a slot, sort by SHA256(seed|notice_id) ascending.",
        "notice_ids": selected_ids, "notice_count": len(selected_ids), "source_counts": dict(by_source),
        "selection_reasons": {nid: SELECTED_REASONS[nid] for nid in selected_ids},
        "condition_count": total_conditions, "condition_type_counts": dict(sorted(condition_type_counts.items())),
        "logical_group_count": logic_group_count, "logical_operator_counts": dict(sorted(sum((ops_in(logic_by_id[n].get("gold_logic_roots", [])) for n in selected_ids), Counter()).items())),
        "exception_count": exception_count, "unresolved_relation_count": unresolved_count,
        "rule_E_zero_prediction_notice_count": sum(r["no_rule_conditions_found"] for r in rows),
        "source_input": {"path": str(INPUTS.relative_to(ROOT)).replace("\\", "/"), "sha256": sha256(INPUTS),
                         "selected_excerpt_hashes": {r["notice_id"]: r["source_excerpt_sha256"] for r in rows}},
        "source_split_manifest_sha256": sha256(SAMPLES),
        "goldset": {"version": gold_manifest["goldset_version"], "manifest_sha256": sha256(gold_manifest_path),
                    "conditions_sha256": sha256(GOLD_DIR / "reviewed_condition_gold.jsonl"),
                    "logic_sha256": sha256(GOLD_DIR / "reviewed_logic_gold.jsonl")},
        "prediction_versions": {"baseline_v1": {
                "condition_path": "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl",
                "condition_sha256": sha256(ROOT / "data/condition_inputs/v1/20261125/extracted/improved/development_conditions.jsonl"),
                "logic_path": "data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl",
                "logic_sha256": sha256(ROOT / "data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl")},
            "rule_experiment_E": {"condition_path": str((RULE_DIR / "development_conditions.jsonl").relative_to(ROOT)).replace("\\", "/"),
                "condition_sha256": sha256(RULE_DIR / "development_conditions.jsonl"),
                "logic_path": str((RULE_DIR / "logic/notice_condition_sets.jsonl").relative_to(ROOT)).replace("\\", "/"),
                "logic_sha256": sha256(RULE_DIR / "logic/notice_condition_sets.jsonl"), "status": "EXPERIMENTAL_NOT_ADOPTED"}},
        "evaluation_policy": {"version": "1.1.0", "strict_tp": "EXACT_MATCH_ONLY", "evaluator_path": "tools/evaluate_condition_pipeline_v11.py",
                              "evaluator_sha256": sha256(ROOT / "tools/evaluate_condition_pipeline_v11.py"),
                              "baseline_preflight": baseline_inputs["frozen_baseline_preflight"]["status"],
                              "metrics_scope": "10 selected DEVELOPMENT notices only"},
        "independent_evaluation_overlap_checked_by_id_only": True,
        "independent_evaluation_semantic_content_used": False, "independent_evaluation_notices_scored": 0,
        "goldset_modified": False, "llm_called": False,
        "llm_execution_plan": {"mode": "llm_only", "provider_selected": False,
            "max_pilot_notices": 10, "max_api_requests": 12, "timeout_seconds": 60,
            "max_output_tokens": 800, "sdk_retries": 0, "format_validation_retries": 1,
            "preserve_raw_responses": True, "preserve_validated_intermediate": True,
            "preserve_pre_and_post_validation_candidates": True, "record_hold_reasons": True,
            "record_token_usage_and_elapsed_time": True, "prompt_version": PROMPT_VERSION,
            "prompt_sha256": hashlib.sha256(system_prompt().encode("utf-8")).hexdigest()},
        "baseline_v1_manifest_sha256": sha256(BASELINE_DIR / "manifest.json"),
        "rule_experiment_manifest_sha256": sha256(RULE_MANIFEST),
        "same_sample_baselines": {"baseline_v1": base_result["common"], "rule_experiment_E": rule_result["common"]},
        "selection_csv_sha256": sha256(OUTPUT / "pilot_selection.csv"),
        "ids_file_sha256": sha256(id_path), "baseline_comparison_csv_sha256": sha256(OUTPUT / "pilot_baseline_comparison.csv"),
    }
    manifest_path = OUTPUT / "pilot_manifest.json"
    readiness_text = readiness_document(manifest, rows, comparison)
    readiness_path = OUTPUT / "LLM_EXECUTION_READINESS.md"
    env_path = OUTPUT / "condition_llm_pilot.env.example"
    readiness_path.write_text(readiness_text, encoding="utf-8")
    env_path.write_text(env_example(), encoding="utf-8")
    manifest["preparation_artifacts"] = {
        path.name: sha256(path) for path in (id_path, OUTPUT / "pilot_selection.csv",
            OUTPUT / "pilot_baseline_comparison.csv", readiness_path, env_path)
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def _metric_record(name: str, scope: str, metric: dict[str, Any], macro_f1: float | None,
                   partial_count: int, misses: int, fp_notices: int, zero_pred: int) -> dict[str, Any]:
    return {"model": name, "scope": scope, "tp": metric["tp"], "fp": metric["fp"], "fn": metric["fn"],
            "precision": metric["precision"], "recall": metric["recall"], "f1": metric["f1"],
            "macro_f1": macro_f1, "partial_match_count": partial_count,
            "notices_with_misses": misses, "notices_with_false_positives": fp_notices,
            "zero_prediction_notices": zero_pred}


def metric_rows(base: dict[str, Any], rule: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for name, result in (("baseline_v1", base), ("rule_experiment_E", rule)):
        common = result["common"]
        details = result["notices"]
        macro_f1 = common["macro_by_notice"]["f1"]
        zero_pred = sum(d.get("prediction_count", 0) == 0 for d in details)
        output.append(_metric_record(name, "OVERALL", common["micro"], macro_f1, common["partial_count"],
                                     common["notices_with_misses"], common["notices_with_false_positives"], zero_pred))
        for source, metric in common["by_source"].items():
            group = [d for d in details if d["source_system"] == source]
            output.append(_metric_record(name, f"SOURCE:{source}", metric, None,
                                         sum(d["partial_count"] for d in group),
                                         sum(d["common"]["fn"] > 0 for d in group), sum(d["common"]["fp"] > 0 for d in group),
                                         sum(d.get("prediction_count", 0) == 0 for d in group)))
        for ctype, metric in common["by_condition_type"].items():
            output.append(_metric_record(name, f"TYPE:{ctype}", metric, None, 0, 0, 0, 0))
    return output


def env_example() -> str:
    return """# Pilot provider must be selected only after the user confirms model/service details.
# Do not copy credential values into this tracked example.
#
# OpenAI-compatible self-hosted vLLM (existing path):
# CONDITION_LLM_PROVIDER=vllm_primary
# VLLM_BASE_URL=
# VLLM_MODEL=
# VLLM_API_KEY=
# VLLM_TIMEOUT_S=60
#
# Direct/external OpenAI-compatible API (separate explicit opt-in):
# This path sends notice excerpts to an external provider. No base URL or model
# is defaulted by the pilot. Confirm the real API model ID and endpoint first.
# CONDITION_LLM_PROVIDER=openai_direct
# CONDITION_LLM_OPENAI_BASE_URL=
# CONDITION_LLM_OPENAI_MODEL=
# CONDITION_LLM_OPENAI_API_KEY=
# CONDITION_LLM_OPENAI_TIMEOUT_S=60
"""


def readiness_document(manifest: dict[str, Any], rows: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> str:
    ids = "\n".join(f"- `{nid}` — {SELECTED_REASONS[nid]}" for nid in manifest["notice_ids"])
    fmt = lambda x: "—" if x is None else f"{x:.4f}"
    table = "\n".join(f"| {r['model']} | {r['scope']} | {r['tp']} | {r['fp']} | {r['fn']} | {fmt(r['precision'])} | {fmt(r['recall'])} | {fmt(r['f1'])} | {fmt(r['macro_f1'])} | {r['zero_prediction_notices']} |" for r in metrics)
    versions = {}
    for package in ("openai", "pydantic"):
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "NOT_INSTALLED"
    return f"""# LLM pilot execution readiness — 2026-11-26

## Frozen diagnostic sample

This 10-notice sample is for development failure diagnosis, not population-representative performance claims. It is selected from finalized goldset `conditions-development-v1.1-20261126-final30`; the extractor receives only notice IDs and v1 source inputs, never gold data.

Seed: `{SEED}`. Selection: two mandatory failure anchors plus source-stratified diagnostic coverage. The constrained slots had no unresolved ties; the seed and SHA-256 tie policy are recorded in `pilot_manifest.json`.

{ids}

Source allocation: BIZINFO 5, K-Startup 5. Evaluation overlap: 0. Rule E zero-prediction notices: {manifest['rule_E_zero_prediction_notice_count']}.

## Same-sample existing results

These are computed using `evaluate_condition_pipeline_v11.evaluate_records`, the existing v1.1 evaluator implementation and strict exact matching, with only the ten frozen IDs. They are not comparable as full-development 30-notice scores.

| Model | Scope | TP | FP | FN | Precision | Recall | F1 | Macro F1 | Zero-prediction notices |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{table}

## Provider and dependencies

The existing dependency files declare and pin `openai` and `pydantic` (`requirements.txt`, `requirements.lock.txt`). Current `.venv` versions: `openai {versions['openai']}`, `pydantic {versions['pydantic']}`. Use the repository's pinned environment setup to recreate the environment; the pilot does not install packages or call an API automatically.

Install the locked project environment when package-index access is available:

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.lock.txt
```

The app's generic `OPENAI_*` settings are not read by this pilot. Provider configurations are separated: existing `vllm_primary`/`vllm_alt` use `VLLM_*`; the optional `openai_direct` path requires dedicated `CONDITION_LLM_OPENAI_*` variables, an explicit provider selection, and an explicit base URL and model ID. The latter is an external-data path. Neither provider is selected here. “OpenAI LUNA 5.6” remains an unverified working label; no API model ID, endpoint, or credential is inferred.

Copy the commented examples from `condition_llm_pilot.env.example` into an untracked local environment file only after confirming the provider. Set `CONDITION_LLM_PROVIDER` explicitly to `vllm_primary`, `vllm_alt`, or `openai_direct`; an unset provider is blocked. Never commit secrets.

## Run after provider confirmation

The following command will be enabled only after the provider-specific endpoint, model ID, credentials, and local client dependencies are configured. It is capped at ten notices and twelve API requests, with at most one format-validation retry per notice:

```powershell
.\\.venv\\Scripts\\python.exe tools/extract_condition_candidates_llm.py --execute --notice-ids-file data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development/pilot_notice_ids.json --pilot-manifest data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development/pilot_manifest.json --output-dir data/evaluations/conditions/v1.1/20261126/llm_pilot/development
```

Preflight without a call:

```powershell
.\\.venv\\Scripts\\python.exe tools/extract_condition_candidates_llm.py --check-config
```

The execution report will preserve the raw response attempts, validated intermediate response, v1.1 candidates, held/invalid reasons, per-notice elapsed time, retry/failure counts, token usage, prompt version/hash, and output hashes. All outputs remain unreviewed and decision-ineligible. No LLM output or LLM score has been produced in this preparation step.
"""


def main() -> int:
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT)
    args = parser.parse_args()
    OUTPUT = args.output_dir
    manifest = build()
    print(json.dumps({"status": manifest["status"], "notice_ids": manifest["notice_ids"],
                      "source_counts": manifest["source_counts"], "condition_count": manifest["condition_count"],
                      "llm_called": manifest["llm_called"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
