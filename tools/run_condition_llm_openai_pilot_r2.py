"""Staged, explicitly authorized R2 pilot. No API call occurs without --lead/--continue."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from pathlib import Path

ROOT_PATH = Path(__file__).resolve().parents[1]
if str(ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(ROOT_PATH))

from tools import extract_condition_candidates_llm as llm
from tools import run_condition_llm_openai_pilot as prior

ROOT = prior.ROOT
OUT = ROOT / "data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_r2"
FAILED = ROOT / "data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_localrun/manifest.json"
RUN_ID = "llm_pilot_2_5c3_r2"
LIMIT = 12
CHANGE_FILE = "retry_code_change.json"


def fingerprint(ids: list[str], model: str) -> dict:
    frozen = prior.verify_frozen_inputs(ids)
    if model != "gpt-5.6-luna":
        raise RuntimeError("R2_MODEL_MISMATCH")
    if json.loads(FAILED.read_text(encoding="utf-8")).get("status") != "PILOT_INCOMPLETE_NO_SCORING":
        raise RuntimeError("FAILED_RUN_REFERENCE_CHANGED")
    prompt_sha = hashlib.sha256(llm.system_prompt().encode()).hexdigest()
    old_prompt_sha = prior.read_json(FAILED.parent / "run_report.json").get("prompt_sha256")
    if prompt_sha != old_prompt_sha:
        raise RuntimeError("PROMPT_CHANGED_FROM_FAILED_RUN")
    return {"run_id": RUN_ID, "model_id": model, "reasoning_effort": "low", "max_completion_tokens": 8192,
            "timeout_seconds": 180, "json_mode": "json_object", "sdk_retries": 0,
            "prompt_sha256_before": old_prompt_sha,
            "prompt_sha256_after": prompt_sha,
            "failed_run_manifest_sha256": prior.digest(FAILED), "frozen_inputs": frozen,
            "runner_sha256": prior.digest(Path(__file__)),
            "extractor_sha256": prior.digest(ROOT / "tools/extract_condition_candidates_llm.py"),
            "evaluator_sha256": frozen["v11_evaluator_sha256"], "notice_ids": ids}


class LedgerBudget(llm.RequestBudget):
    def __init__(self, path: Path):
        self.path = path
        existing = prior.read_json(path) if path.exists() else {"limit": LIMIT, "used": 0, "attempts": []}
        if existing["limit"] != LIMIT or existing["used"] != len(existing["attempts"]):
            raise RuntimeError("REQUEST_LEDGER_INVALID")
        self.limit, self.used, self.attempts = LIMIT, existing["used"], existing["attempts"]
        self.label = "UNSET"

    def consume(self) -> bool:
        if self.used >= self.limit:
            return False
        self.used += 1
        self.attempts.append({"request_ordinal": self.used, "notice_id": self.label,
                              "state": "RESERVED_BEFORE_API_CALL"})
        prior.write_json(self.path, {"limit": self.limit, "used": self.used, "attempts": self.attempts})
        return True


def stage_state(path: Path) -> tuple[dict, list[dict]]:
    report = prior.read_json(path / "run_report.json")
    rows = prior.read_jsonl(path / "per_notice_execution.jsonl")
    return report, rows


def assert_same_run(manifest_path: Path, expected: dict) -> dict:
    manifest = prior.read_json(manifest_path)
    original = manifest.get("fingerprint", {})
    if original != expected:
        allowed = {"runner_sha256", "extractor_sha256"}
        if any(original.get(k) != expected.get(k) for k in set(original) | set(expected) if k not in allowed):
            raise RuntimeError("R2_INPUT_OR_SETTINGS_CHANGED")
        change_path = manifest_path.parent / CHANGE_FILE
        if not change_path.exists():
            raise RuntimeError("R2_CODE_CHANGE_NOT_RECORDED")
        change = prior.read_json(change_path)
        if (change.get("change_type") != "CONNECTION_ERROR_LEAD_RETRY_ONLY"
                or change.get("old_runner_sha256") != original.get("runner_sha256")
                or change.get("old_extractor_sha256") != original.get("extractor_sha256")
                or change.get("new_runner_sha256") != expected.get("runner_sha256")
                or change.get("new_extractor_sha256") != expected.get("extractor_sha256")):
            raise RuntimeError("R2_CODE_CHANGE_RECORD_MISMATCH")
    return manifest


def prepare_retry(out: Path, ids: list[str], fp: dict) -> int:
    manifest = prior.read_json(out / "manifest.json")
    original = manifest.get("fingerprint", {})
    if manifest.get("status") != "LEAD_BLOCKED" or (out / CHANGE_FILE).exists():
        raise RuntimeError("RETRY_PREPARATION_NOT_ALLOWED")
    if any(original.get(k) != fp.get(k) for k in set(original) | set(fp)
           if k not in {"runner_sha256", "extractor_sha256"}):
        raise RuntimeError("R2_INPUT_OR_SETTINGS_CHANGED")
    ledger_path = out / "request_ledger.json"
    budget = LedgerBudget(ledger_path)
    if (budget.used != 2 or [a["notice_id"] for a in budget.attempts] !=
            ["SYNTHETIC:STRUCTURED_JSON_PREFLIGHT", ids[0]]):
        raise RuntimeError("PRIOR_REQUEST_LEDGER_UNEXPECTED")
    if prior.read_json(out / "synthetic_preflight.json").get("status") != "PASS":
        raise RuntimeError("SYNTHETIC_PREFLIGHT_NOT_PASSED")
    report, rows = stage_state(out / "lead")
    raw_rows = prior.read_jsonl(out / "lead/raw_llm_responses.jsonl")
    if (report["failure_count"] != 1 or rows[0]["status"] != "CONNECTION_ERROR"
            or rows[0]["error_code"] != "APIConnectionError"
            or len(raw_rows) != 1 or raw_rows[0].get("response_attempts")
            or prior.read_jsonl(out / "lead/llm_condition_predictions.jsonl")
            or prior.read_json(out / "lead_gate.json")["status"] != "BLOCKED"
            or (out / "lead_retry").exists()):
        raise RuntimeError("PRIOR_LEAD_IS_NOT_RETRYABLE_CONNECTION_ERROR")
    prior.write_json(out / CHANGE_FILE, {
        "change_type": "CONNECTION_ERROR_LEAD_RETRY_ONLY", "original_fingerprint_preserved": True,
        "old_runner_sha256": original["runner_sha256"], "new_runner_sha256": fp["runner_sha256"],
        "old_extractor_sha256": original["extractor_sha256"], "new_extractor_sha256": fp["extractor_sha256"],
        "purpose": "One explicit retry of the lead notice after APIConnectionError, with sanitized connection diagnostics",
        "changed_functions_and_cli": ["assert_same_run", "prepare_retry", "retry_lead", "resume", "evaluate",
                                     "OpenAIDirectProvider.generate", "extract_notice", "--prepare-retry", "--retry-lead"],
        "prior_ledger_sha256": prior.digest(ledger_path), "prior_status": manifest["status"],
        "prior_requests_used": budget.used, "approval_record": "User request 2-5C-3C-R2-P1 dated 2026-11-26; API call deferred to local explicit --retry-lead",
        "unchanged_fingerprint_fields": {k: v for k, v in original.items() if k not in {"runner_sha256", "extractor_sha256"}},
    })
    return 0


def provider_from_env(env_file: Path) -> llm.OpenAIDirectProvider:
    env = llm.load_env_safely(env_file)
    if not env.get("OPENAI_API_KEY") or env.get("OPENAI_CHAT_MODEL") != "gpt-5.6-luna":
        raise RuntimeError("R2_OPENAI_CONFIGURATION_MISSING_OR_MODEL_CHANGED")
    return llm.OpenAIDirectProvider(api_key=env["OPENAI_API_KEY"], model=env["OPENAI_CHAT_MODEL"],
                                    timeout_s=180, max_completion_tokens=8192, reasoning_effort="low")


def technical_gate(path: Path, report: dict) -> bool:
    rows = prior.read_jsonl(path / "per_notice_execution.jsonl")
    raw_rows = prior.read_jsonl(path / "raw_llm_responses.jsonl")
    return bool(report["failure_count"] == 0 and report["condition_count"] > 0
        and report["schema_error_count"] == 0 and report["held_review_queue"] == 0
        and not prior.read_jsonl(path / "rejected_candidates.jsonl")
        and rows and rows[0]["status"] == "COMPLETED"
        and raw_rows and raw_rows[0]["response_attempts"] and raw_rows[0]["response_attempts"][0]
        and rows[0].get("provider_metadata", {}).get("finish_reason") != "length"
        and report["decision_eligible_true_count"] == 0)


def lead(out: Path, env_file: Path, ids: list[str], fp: dict) -> int:
    if out.exists() and any(out.iterdir()):
        raise RuntimeError("R2_OUTPUT_ALREADY_EXISTS")
    out.mkdir(parents=True)
    prior.write_json(out / "manifest.json", {"status": "LEAD_STARTED", "fingerprint": fp,
                                               "request_limit": LIMIT, "prior_run_budget_reused": False})
    budget = LedgerBudget(out / "request_ledger.json")
    provider = provider_from_env(env_file)
    synthetic_row = {"notice_id": "SYNTHETIC:STRUCTURED_JSON_PREFLIGHT", "source_system": "SYNTHETIC",
                     "title": "Synthetic preflight only", "raw_text": "Applicants must be at least 18 years old.",
                     "completeness_status": "UNKNOWN"}
    budget.label = synthetic_row["notice_id"]
    try:
        parsed, attempts, usage, raw = asyncio.run(llm.call_and_parse(provider, synthetic_row,
                                               max_format_attempts=1, request_budget=budget))
    except llm.ExtractionFailure as exc:
        prior.write_json(out / "preflight_failure.json", {"status": exc.status, "error_code": exc.detail_code,
                          "provider_metadata": provider.last_response, "provider_error": provider.last_error,
                          "request_ordinal": budget.used})
        return 2
    prior.write_json(out / "synthetic_preflight.json", {"status": "PASS", "request_ordinal": budget.used,
                   "model_id": provider.model, "usage": usage, "provider_metadata": provider.last_response,
                   "response_text_length": len(raw[-1]) if raw else 0})
    budget.label = ids[0]
    report = asyncio.run(llm.run_pilot(provider, [ids[0]], output_dir=out / "lead", request_budget=budget,
                                       max_format_attempts=1))
    valid = technical_gate(out / "lead", report)
    prior.write_json(out / "lead_gate.json", {"status": "PASS" if valid else "BLOCKED",
                     "notice_id": ids[0], "request_ordinal": budget.used,
                     "reason": None if valid else "TECHNICAL_OUTPUT_OR_EVIDENCE_VALIDATION_FAILED",
                     "condition_count": report["condition_count"], "schema_error_count": report["schema_error_count"],
                     "held_review_queue": report["held_review_queue"]})
    manifest = prior.read_json(out / "manifest.json")
    manifest["status"] = "LEAD_PASSED" if valid else "LEAD_BLOCKED"
    manifest["requests_used"] = budget.used
    prior.write_json(out / "manifest.json", manifest)
    return 0 if valid else 2


def retry_lead(out: Path, env_file: Path, ids: list[str], fp: dict) -> int:
    manifest = assert_same_run(out / "manifest.json", fp)
    if manifest.get("status") != "LEAD_BLOCKED" or (out / "lead_retry").exists():
        raise RuntimeError("LEAD_RETRY_NOT_ALLOWED")
    change = prior.read_json(out / CHANGE_FILE)
    budget = LedgerBudget(out / "request_ledger.json")
    if (budget.used != 2 or prior.digest(out / "request_ledger.json") != change["prior_ledger_sha256"]
            or [a["notice_id"] for a in budget.attempts] !=
            ["SYNTHETIC:STRUCTURED_JSON_PREFLIGHT", ids[0]] or budget.limit - budget.used < 10):
        raise RuntimeError("LEAD_RETRY_BUDGET_OR_LEDGER_MISMATCH")
    if (prior.read_json(out / "synthetic_preflight.json")["status"] != "PASS"
            or prior.read_json(out / "lead_gate.json")["status"] != "BLOCKED"):
        raise RuntimeError("LEAD_RETRY_PREFLIGHT_OR_GATE_MISMATCH")
    report, rows = stage_state(out / "lead")
    raw_rows = prior.read_jsonl(out / "lead/raw_llm_responses.jsonl")
    if (report["failure_count"] != 1 or rows[0]["status"] != "CONNECTION_ERROR"
            or rows[0]["error_code"] != "APIConnectionError"
            or len(raw_rows) != 1 or raw_rows[0].get("response_attempts")):
        raise RuntimeError("LEAD_RETRY_CAUSE_MISMATCH")
    budget.label = ids[0]
    provider = provider_from_env(env_file)
    retry_report = asyncio.run(llm.run_pilot(provider, [ids[0]], output_dir=out / "lead_retry",
                                             request_budget=budget, max_format_attempts=1))
    valid = technical_gate(out / "lead_retry", retry_report)
    prior.write_json(out / "lead_retry_gate.json", {"status": "PASS" if valid else "BLOCKED",
                     "notice_id": ids[0], "request_ordinal": budget.used,
                     "condition_count": retry_report["condition_count"],
                     "error_status_counts": retry_report["status_counts"],
                     "remaining_request_budget": LIMIT - budget.used})
    manifest["status"] = "LEAD_PASSED" if valid else "LEAD_BLOCKED"
    manifest["requests_used"] = budget.used
    manifest["lead_retry_used"] = True
    prior.write_json(out / "manifest.json", manifest)
    return 0 if valid else 2


def resume(out: Path, env_file: Path, ids: list[str], fp: dict) -> int:
    manifest = assert_same_run(out / "manifest.json", fp)
    if manifest["status"] not in {"LEAD_PASSED", "REMAINING_IN_PROGRESS"}:
        raise RuntimeError("LEAD_GATE_NOT_PASSED")
    gate_path = out / "lead_retry_gate.json" if (out / "lead_retry_gate.json").exists() else out / "lead_gate.json"
    if prior.read_json(gate_path)["status"] != "PASS":
        raise RuntimeError("LEAD_GATE_NOT_PASSED")
    budget = LedgerBudget(out / "request_ledger.json")
    provider = provider_from_env(env_file)
    for index, nid in enumerate(ids[1:], 1):
        path = out / f"notice_{index:02d}"
        if path.exists():
            report, rows = stage_state(path)
            if report["failure_count"] or rows[0]["notice_id"] != nid:
                raise RuntimeError("PRIOR_NOTICE_FAILED_OR_MISMATCHED; no duplicate call allowed")
            continue
        if any(a["notice_id"] == nid for a in budget.attempts):
            raise RuntimeError("REQUEST_RESERVED_WITHOUT_RESULT; manual audit required before another call")
        manifest["status"] = "REMAINING_IN_PROGRESS"
        prior.write_json(out / "manifest.json", manifest)
        budget.label = nid
        report = asyncio.run(llm.run_pilot(provider, [nid], output_dir=path,
                                           request_budget=budget, max_format_attempts=1))
        manifest["requests_used"] = budget.used
        prior.write_json(out / "manifest.json", manifest)
        if report["failure_count"] or report["schema_error_count"]:
            prior.write_json(out / "remaining_failure.json", {"notice_id": nid, "status": "STOPPED",
                              "request_ordinal": budget.used, "report": report["status_counts"],
                              "unprocessed_notice_ids": ids[index + 1:]})
            return 2
    manifest["status"] = "ALL_TEN_EXTRACTED"
    manifest["requests_used"] = budget.used
    prior.write_json(out / "manifest.json", manifest)
    return 0


def evaluate(out: Path, ids: list[str], fp: dict) -> int:
    manifest = assert_same_run(out / "manifest.json", fp)
    if manifest["status"] != "ALL_TEN_EXTRACTED":
        raise RuntimeError("TEN_NOTICE_EXTRACTION_NOT_COMPLETE")
    effective_lead = out / "lead_retry" if (out / "lead_retry_gate.json").exists() else out / "lead"
    paths = [effective_lead] + [out / f"notice_{i:02d}" for i in range(1, 10)]
    for p in paths:
        report, _ = stage_state(p)
        if report["failure_count"] or report["schema_error_count"]:
            raise RuntimeError("EXTRACTION_OR_VALIDATION_FAILURE")
    gold = [r for r in prior.read_jsonl(prior.GOLD / "reviewed_condition_gold.jsonl") if r["notice_id"] in set(ids)]
    outputs = {}
    for name, path in (("baseline_v1", prior.BASELINE_OUT), ("rule_experiment_E", prior.RULE_E)):
        outputs[name] = [r for r in prior.read_jsonl(path) if r["notice_id"] in set(ids)]
    intermediate = [r for p in paths for r in prior.read_jsonl(p / "intermediate_responses.jsonl")]
    outputs["llm_pre_validation"] = prior.prevalidation_predictions(intermediate, prior.INPUTS)
    outputs["llm_post_validation"] = [r for p in paths for r in prior.read_jsonl(p / "llm_condition_predictions.jsonl")]
    evaluated = {name: prior.evaluate_conditions(gold, rows) for name, rows in outputs.items()}
    comparison, summaries = prior.comparison_rows(evaluated)
    prior.write_csv(out / "pilot_baseline_comparison.csv", comparison)
    prior.write_json(out / "evaluation_summary.json", {"status": "PILOT_COMPLETED", "run_id": RUN_ID,
                     "notice_ids": ids, "gold_condition_count": 62, "evaluation": summaries,
                     "condition_metrics_only": True, "logic_semantics_scored": False})
    manifest["status"] = "PILOT_COMPLETED"
    manifest["evaluation_summary_sha256"] = prior.digest(out / "evaluation_summary.json")
    manifest["request_ledger_sha256"] = prior.digest(out / "request_ledger.json")
    prior.write_json(out / "manifest.json", manifest)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for flag in ("check", "lead", "prepare-retry", "retry-lead", "continue", "evaluate"):
        modes.add_argument("--" + flag, action="store_true")
    parser.add_argument("--authorize-new-budget", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    out = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    ids = prior.read_json(prior.PREPARATION / "pilot_notice_ids.json")
    env = llm.load_env_safely()
    fp = fingerprint(ids, env.get("OPENAI_CHAT_MODEL", ""))
    if args.check:
        readable = {str(p.relative_to(ROOT)): p.is_file() and bool(p.open("rb").read(1))
                    for p in (prior.INPUTS, prior.SAMPLES, prior.GOLD / "reviewed_condition_gold.jsonl", FAILED)}
        print(json.dumps({"status": "PASS", "readable_inputs": readable, "fingerprint": fp,
                          "api_called": False, "existing_budget_reused": False}, ensure_ascii=False, indent=2))
        return 0
    if args.lead:
        if not args.authorize_new_budget:
            parser.error("--lead requires explicit --authorize-new-budget after user approval")
        return lead(out, ROOT / ".env", ids, fp)
    if getattr(args, "prepare_retry"):
        return prepare_retry(out, ids, fp)
    if getattr(args, "retry_lead"):
        return retry_lead(out, ROOT / ".env", ids, fp)
    if getattr(args, "continue"):
        return resume(out, ROOT / ".env", ids, fp)
    return evaluate(out, ids, fp)


if __name__ == "__main__":
    raise SystemExit(main())
