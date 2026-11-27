"""Prepare and (only after explicit approvals) recover the blocked R2 v2 pilot.

--prepare is offline and keeps the active cap at 12. A separate
--approve-budget-increase command records the user's authorization to raise it
to 13; live requests additionally require --run-recovery --authorize-api.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import evaluate_condition_pipeline_v11 as v11  # noqa: E402
from tools import extract_condition_candidates_llm as llm  # noqa: E402
from tools import run_condition_llm_openai_pilot_r2_norm_v2 as base  # noqa: E402
from tools import run_condition_llm_openai_pilot_r2 as pilot  # noqa: E402

RUN_ID = "llm_pilot_2_5c3_r2_norm_v2_recovery_v1"
RUN_DIR = base.DEV / RUN_ID
SOURCE_DIR = base.RUN_DIR
SOURCE_LEDGER = SOURCE_DIR / "request_ledger.json"
CLAIM_PATH = base.DEV / f".{RUN_ID}_claim.json"
ACTIVE_LIMIT = 12
APPROVED_LIMIT = 13
PARENT_USED = 3
PRIOR_CHILD_USED = 2


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    base.write_json_atomic(path, value)


def _source_state() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    source_manifest = read_json(SOURCE_DIR / "manifest.json")
    source_ledger = read_json(SOURCE_LEDGER)
    ids = base.read_json(pilot.prior.PREPARATION / "pilot_notice_ids.json")
    if source_manifest.get("status") != "REMAINING_BLOCKED":
        raise RuntimeError("SOURCE_RUN_NOT_BLOCKED_AS_EXPECTED")
    if source_ledger.get("limit") != ACTIVE_LIMIT or source_ledger.get("used") != 5:
        raise RuntimeError("SOURCE_LEDGER_STATE_CHANGED")
    if len(source_ledger.get("attempts", [])) != 5 or len(source_ledger.get("child_attempts", [])) != PRIOR_CHILD_USED:
        raise RuntimeError("SOURCE_LEDGER_ATTEMPT_COUNT_MISMATCH")
    success = SOURCE_DIR / "notice_01"
    success_report = read_json(success / "run_report.json")
    success_raw = llm._read_jsonl(success / "raw_llm_responses.jsonl")
    if (success_report.get("status_counts", {}).get("COMPLETED") != 1 or len(success_raw) != 1
            or success_raw[0].get("accepted") is not True):
        raise RuntimeError("PRIOR_SUCCESS_RESPONSE_NOT_VERIFIED")
    failure = SOURCE_DIR / "notice_02"
    failure_raw = llm._read_jsonl(failure / "raw_llm_responses.jsonl")
    if (len(failure_raw) != 1 or failure_raw[0].get("accepted") is not False
            or source_ledger["child_attempts"][1].get("state") != "FAILED_RESPONSE"):
        raise RuntimeError("PRIOR_FAILED_ATTEMPT_NOT_VERIFIED")
    return source_manifest, source_ledger, ids


def recovery_fingerprint() -> dict[str, Any]:
    source_manifest, source_ledger, ids = _source_state()
    current_fp, audit = base.preflight()
    if len(ids) != 10 or current_fp.get("pilot_notice_ids") != ids:
        raise RuntimeError("RECOVERY_PILOT_IDENTITY_MISMATCH")
    old_fp = source_manifest["fingerprint"]
    success_dir = SOURCE_DIR / "notice_01"
    failed_dir = SOURCE_DIR / "notice_02"
    frozen_paths = [
        pilot.prior.INPUTS, pilot.prior.SAMPLES, pilot.prior.PREPARATION / "pilot_notice_ids.json",
        pilot.prior.PREPARATION / "pilot_manifest.json", pilot.prior.GOLD / "manifest.json",
        pilot.prior.GOLD / "reviewed_condition_gold.jsonl", pilot.prior.GOLD / "reviewed_logic_gold.jsonl",
        pilot.prior.BASELINE_OUT, pilot.prior.BASELINE_LOGIC,
        pilot.prior.RULE_E, pilot.prior.RULE_E_LOGIC,
        ROOT / "tools/evaluate_condition_pipeline_v11.py",
    ]
    return {
        "run_id": RUN_ID,
        "parent_run_id": old_fp["parent_run_id"],
        "blocked_run_id": base.RUN_ID,
        "blocked_manifest_sha256": digest(SOURCE_DIR / "manifest.json"),
        "blocked_ledger_sha256": digest(SOURCE_LEDGER),
        "blocked_gate_sha256": digest(SOURCE_DIR / "technical_gate.json") if (SOURCE_DIR / "technical_gate.json").exists() else None,
        "prior_success_raw_sha256": digest(success_dir / "raw_llm_responses.jsonl"),
        "prior_success_report_sha256": digest(success_dir / "run_report.json"),
        "prior_failure_raw_sha256": digest(failed_dir / "raw_llm_responses.jsonl"),
        "prior_failure_report_sha256": digest(failed_dir / "run_report.json"),
        "previous_extractor_sha256": old_fp["extractor_sha256"],
        "previous_runner_sha256": old_fp["runner_sha256"],
        "extractor_sha256": digest(ROOT / "tools/extract_condition_candidates_llm.py"),
        "runner_sha256": digest(ROOT / "tools/run_condition_llm_openai_pilot_r2_norm_v2.py"),
        "recovery_runner_sha256": digest(Path(__file__)),
        "normalization_rules_version": current_fp["normalization_rules_version"],
        "normalization_rules_sha256": current_fp["normalization_rules_sha256"],
        "prompt_sha256": current_fp["prompt_sha256"],
        "generation_settings": {key: old_fp[key] for key in (
            "model_id", "reasoning_effort", "max_completion_tokens", "timeout_seconds", "json_mode", "sdk_retries")},
        "fixed_input_hashes": {path.relative_to(ROOT).as_posix(): digest(path) for path in frozen_paths},
        "strict_evaluator_sha256": digest(v11.__file__ and Path(v11.__file__)),
        "baseline_hashes": {path.relative_to(ROOT).as_posix(): digest(path) for path in frozen_paths[7:11]},
        "pilot_notice_ids": ids,
        "existing_cumulative_used": source_ledger["used"],
        "active_limit_before_approval": ACTIVE_LIMIT,
        "proposed_limit_after_approval": APPROVED_LIMIT,
        "api_call_count_at_preparation": 0,
        "source_preflight_sha256": hashlib.sha256(json.dumps(audit, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
    }


def _validate_saved(fp: dict[str, Any]) -> None:
    manifest = read_json(RUN_DIR / "manifest.json")
    if manifest.get("fingerprint") != fp:
        raise RuntimeError("RECOVERY_FINGERPRINT_CHANGED")
    if digest(SOURCE_LEDGER) != fp["blocked_ledger_sha256"]:
        raise RuntimeError("BLOCKED_SOURCE_LEDGER_CHANGED")


def prepare() -> dict[str, Any]:
    with base.successor_lock():
        fp = recovery_fingerprint()
        if (RUN_DIR / "manifest.json").is_file():
            _validate_saved(fp)
            manifest = read_json(RUN_DIR / "manifest.json")
            return {"status": manifest["status"], "already_prepared": True,
                    "active_limit": manifest["active_limit"], "used": manifest["cumulative_used"],
                    "remaining": manifest["active_remaining"], "api_call_count": 0}
        if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
            raise RuntimeError("RECOVERY_OUTPUT_EXISTS_WITHOUT_MANIFEST")
        source_manifest, source_ledger, ids = _source_state()
        success_dir = SOURCE_DIR / "notice_01"
        shutil.copytree(success_dir, RUN_DIR / "notice_01")
        history = RUN_DIR / "provenance/prior_failed_attempt_notice_02_ordinal_5"
        shutil.copytree(SOURCE_DIR / "notice_02", history)
        ledger = copy.deepcopy(source_ledger)
        ledger["lineage"].update({
            "recovery_run_id": RUN_ID,
            "blocked_source_run_id": base.RUN_ID,
            "blocked_source_ledger_sha256": digest(SOURCE_LEDGER),
            "prior_used": source_ledger["used"],
            "active_limit": ACTIVE_LIMIT,
            "proposed_limit": APPROVED_LIMIT,
            "budget_increase_approved": False,
            "new_budget_granted": 0,
        })
        ledger["recovery_attempts"] = []
        write_json(RUN_DIR / "request_ledger.json", ledger)
        claim = {"run_id": RUN_ID, "fingerprint_sha256": hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest(),
                 "source_ledger_sha256": digest(SOURCE_LEDGER), "exclusive_successor": True}
        base.claim_single_successor(CLAIM_PATH, claim)
        manifest = {
            "run_id": RUN_ID, "status": "PREPARED_AWAITING_BUDGET_APPROVAL",
            "source_run_id": base.RUN_ID, "source_status_preserved": source_manifest["status"],
            "request_limit": ACTIVE_LIMIT, "active_limit": ACTIVE_LIMIT,
            "proposed_limit": APPROVED_LIMIT, "budget_increase_approved": False,
            "parent_used": PARENT_USED, "prior_child_used": PRIOR_CHILD_USED,
            "recovery_used": 0, "cumulative_used": source_ledger["used"],
            "active_remaining": ACTIVE_LIMIT - source_ledger["used"],
            "additional_responses_required": len(ids) - 2,
            "requests_required_after_existing_attempts": len(ids) - 2,
            "budget_increase_required": 1,
            "reused_success_notice_ids": [ids[1]], "retry_notice_ids": [ids[2]],
            "unexecuted_notice_ids": ids[3:], "api_call_count": 0,
            "fingerprint": fp,
            "policy_unchanged": {"model": True, "prompt": True, "normalization": True,
                                 "evidence_validation": True, "strict_evaluator": True},
            "decision_eligible": False,
        }
        write_json(RUN_DIR / "manifest.json", manifest)
        write_json(RUN_DIR / "preflight_report.json", {
            "status": "PASS_AWAITING_BUDGET_APPROVAL", "api_call_count": 0,
            "existing_responses_preserved": 2, "existing_failure_preserved": True,
            "active_limit": ACTIVE_LIMIT, "active_remaining": ACTIVE_LIMIT - source_ledger["used"],
            "proposed_limit": APPROVED_LIMIT, "budget_increase_applied": False,
            "additional_responses_required": len(ids) - 2,
            "reason_budget_shortfall": (len(ids) - 2) - (ACTIVE_LIMIT-source_ledger["used"]),
        })
        return {"status": manifest["status"], "run_id": RUN_ID,
                "active_limit": ACTIVE_LIMIT, "used": source_ledger["used"],
                "active_remaining": ACTIVE_LIMIT-source_ledger["used"],
                "proposed_limit": APPROVED_LIMIT, "api_call_count": 0}


def approve_budget_increase() -> dict[str, Any]:
    with base.successor_lock():
        fp = recovery_fingerprint()
        _validate_saved(fp)
        manifest = read_json(RUN_DIR / "manifest.json")
        ledger = read_json(RUN_DIR / "request_ledger.json")
        if manifest.get("budget_increase_approved") is True:
            return {"status": manifest["status"], "already_approved": True, "request_limit": ledger["limit"]}
        if manifest.get("status") != "PREPARED_AWAITING_BUDGET_APPROVAL":
            raise RuntimeError("BUDGET_APPROVAL_NOT_AVAILABLE_IN_CURRENT_STATE")
        if ledger.get("used") != 5 or ledger.get("limit") != ACTIVE_LIMIT:
            raise RuntimeError("RECOVERY_LEDGER_CHANGED_BEFORE_APPROVAL")
        ledger["limit"] = APPROVED_LIMIT
        ledger["lineage"].update({"active_limit": APPROVED_LIMIT, "budget_increase_approved": True,
                                  "new_budget_granted": 1, "allowed_ordinals": list(range(6, 14))})
        ledger["budget_approval"] = {"explicit_cli_approval": True, "previous_limit": ACTIVE_LIMIT,
                                     "approved_limit": APPROVED_LIMIT, "prior_usage_preserved": 5}
        manifest.update({"status": "PREPARED_API_AUTHORIZATION_REQUIRED", "request_limit": APPROVED_LIMIT,
                         "active_limit": APPROVED_LIMIT, "budget_increase_approved": True,
                         "active_remaining": APPROVED_LIMIT-ledger["used"], "budget_approval_recorded": True})
        write_json(RUN_DIR / "request_ledger.json", ledger)
        write_json(RUN_DIR / "manifest.json", manifest)
        return {"status": manifest["status"], "request_limit": APPROVED_LIMIT,
                "used": ledger["used"], "remaining": APPROVED_LIMIT-ledger["used"], "api_call_count": 0}


class RecoveryBudget(llm.RequestBudget):
    def __init__(self, notice_id: str):
        ledger = read_json(RUN_DIR / "request_ledger.json")
        self.notice_id = notice_id
        self.limit, self.used = ledger["limit"], ledger["used"]
        self.last_request_ordinal = None

    def consume(self) -> bool:
        with base.successor_lock():
            path = RUN_DIR / "request_ledger.json"
            ledger = read_json(path)
            if ledger["limit"] != APPROVED_LIMIT or ledger["used"] >= APPROVED_LIMIT:
                return False
            if not ledger.get("lineage", {}).get("budget_increase_approved"):
                return False
            if len(ledger["recovery_attempts"]) >= APPROVED_LIMIT - 5:
                return False
            ordinal = ledger["used"] + 1
            if ordinal not in range(6, 14):
                return False
            row = {"request_ordinal": ordinal, "notice_id": self.notice_id,
                   "state": "RESERVED_BEFORE_API_CALL", "recovery_run_id": RUN_ID}
            ledger["used"] = ordinal
            ledger["attempts"].append(copy.deepcopy(row))
            ledger["recovery_attempts"].append(copy.deepcopy(row))
            write_json(path, ledger)
            self.used, self.last_request_ordinal = ordinal, ordinal
            return True


def _finish(notice_id: str, state: str) -> dict[str, Any]:
    path = RUN_DIR / "request_ledger.json"
    ledger = read_json(path)
    rows = [r for r in ledger["recovery_attempts"] if r["notice_id"] == notice_id and r["state"] == "RESERVED_BEFORE_API_CALL"]
    if len(rows) != 1:
        raise RuntimeError("RECOVERY_RESERVATION_MISMATCH")
    ordinal = rows[0]["request_ordinal"]
    rows[0]["state"] = state
    for row in ledger["attempts"]:
        if row.get("request_ordinal") == ordinal:
            row["state"] = state
    write_json(path, ledger)
    return ledger


async def _run_batch(env: dict[str, str], fp: dict[str, Any]) -> dict[str, Any]:
    expected = read_json(base.PARENT_MANIFEST)["fingerprint"]
    provider = llm.OpenAIDirectProvider(api_key=env["OPENAI_API_KEY"], model=env["OPENAI_CHAT_MODEL"],
                                         timeout_s=expected["timeout_seconds"],
                                         max_completion_tokens=expected["max_completion_tokens"],
                                         reasoning_effort=expected["reasoning_effort"])
    try:
        ids = fp["pilot_notice_ids"]
        manifest = read_json(RUN_DIR / "manifest.json")
        for index, notice_id in enumerate(ids[2:], start=2):
            current = recovery_fingerprint()
            if current != fp:
                raise RuntimeError("RECOVERY_FINGERPRINT_CHANGED_DURING_RUN")
            out = RUN_DIR / f"notice_{index:02d}"
            ledger = read_json(RUN_DIR / "request_ledger.json")
            existing = [a for a in ledger["recovery_attempts"] if a["notice_id"] == notice_id]
            if existing:
                if len(existing) != 1 or existing[0]["state"] != "COMPLETED" or not (out / "run_report.json").is_file():
                    raise RuntimeError("RECOVERY_ATTEMPT_UNRESOLVED; REFUSING_DUPLICATE_REQUEST")
                continue
            if out.exists() and any(out.iterdir()):
                raise RuntimeError("RECOVERY_NOTICE_OUTPUT_EXISTS_WITHOUT_RESERVATION")
            budget = RecoveryBudget(notice_id)
            report = await llm.run_pilot(provider, [notice_id], output_dir=out,
                                         request_budget=budget, max_format_attempts=1)
            state = "COMPLETED" if report.get("status_counts", {}).get("COMPLETED") == 1 else "FAILED_RESPONSE"
            ledger = _finish(notice_id, state)
            manifest["recovery_used"] = len(ledger["recovery_attempts"])
            manifest["cumulative_used"] = ledger["used"]
            manifest["active_remaining"] = ledger["limit"] - ledger["used"]
            manifest["api_call_count"] = len(ledger["recovery_attempts"])
            if state != "COMPLETED":
                manifest["status"] = "RECOVERY_BLOCKED"
                manifest["failed_notice_id"] = notice_id
                write_json(RUN_DIR / "manifest.json", manifest)
                return {"status": "RECOVERY_BLOCKED", "failed_notice_id": notice_id,
                        "used": ledger["used"], "api_call_count": manifest["api_call_count"]}
            offline = base.replay_notice(out / "raw_llm_responses.jsonl", out)
            gate = base.tech_gate_for_notice(out, offline)
            write_json(out / "technical_gate.json", gate)
            if gate["status"] != "PASS":
                manifest["status"] = "RECOVERY_BLOCKED"
                manifest["failed_notice_id"] = notice_id
                write_json(RUN_DIR / "manifest.json", manifest)
                return {"status": "RECOVERY_BLOCKED", "failed_notice_id": notice_id,
                        "technical_gate": gate, "used": ledger["used"]}
            write_json(RUN_DIR / "manifest.json", manifest)
        ledger = read_json(RUN_DIR / "request_ledger.json")
        gates = [read_json(RUN_DIR / f"notice_{i:02d}/technical_gate.json") for i in range(1, 10)]
        if len(gates) != 9 or any(g.get("status") != "PASS" for g in gates):
            manifest["status"] = "RECOVERY_BLOCKED"
            write_json(RUN_DIR / "manifest.json", manifest)
            return {"status": "RECOVERY_BLOCKED", "reason": "NOTICE_TECHNICAL_GATE_FAILED",
                    "completed_notice_count": sum(g.get("status") == "PASS" for g in gates)}
        manifest.update({"status": "TEN_NOTICE_TECHNICAL_GATE_PASSED", "cumulative_used": ledger["used"],
                         "active_remaining": ledger["limit"]-ledger["used"],
                         "api_call_count": len(ledger["recovery_attempts"]), "decision_eligible": False})
        write_json(RUN_DIR / "technical_gate.json", {"status": "PASS", "notice_count": 10,
                    "decision_eligible": False, "actual_support_decision_approved": False})
        write_json(RUN_DIR / "manifest.json", manifest)
        return {"status": manifest["status"], "used": ledger["used"],
                "api_call_count": manifest["api_call_count"], "decision_eligible": False}
    finally:
        await provider.aclose()


def run_recovery(env_file: Path) -> dict[str, Any]:
    with base.successor_lock():
        fp = recovery_fingerprint()
        _validate_saved(fp)
        manifest = read_json(RUN_DIR / "manifest.json")
        ledger = read_json(RUN_DIR / "request_ledger.json")
        if not manifest.get("budget_increase_approved") or ledger.get("limit") != APPROVED_LIMIT:
            raise RuntimeError("EXPLICIT_BUDGET_APPROVAL_REQUIRED")
        if manifest.get("status") not in {"PREPARED_API_AUTHORIZATION_REQUIRED", "RECOVERY_IN_PROGRESS"}:
            raise RuntimeError("RECOVERY_RUN_STATE_NOT_EXECUTABLE")
        env = llm.load_env_safely(env_file)
        expected = read_json(base.PARENT_MANIFEST)["fingerprint"]
        if env.get("OPENAI_CHAT_MODEL") != expected["model_id"] or not env.get("OPENAI_API_KEY"):
            raise RuntimeError("RECOVERY_PROVIDER_CONFIG_MISMATCH")
        manifest["status"] = "RECOVERY_IN_PROGRESS"
        write_json(RUN_DIR / "manifest.json", manifest)
        return asyncio.run(_run_batch(env, fp))


def evaluate_recovery() -> dict[str, Any]:
    manifest = read_json(RUN_DIR / "manifest.json")
    gate = read_json(RUN_DIR / "technical_gate.json")
    ledger = read_json(RUN_DIR / "request_ledger.json")
    if manifest.get("status") != "TEN_NOTICE_TECHNICAL_GATE_PASSED" or gate.get("status") != "PASS":
        raise RuntimeError("RECOVERY_TECHNICAL_GATE_NOT_PASSED")
    if ledger.get("used") != 13 or len(ledger.get("recovery_attempts", [])) != 8:
        raise RuntimeError("TEN_NOTICE_REQUEST_ACCOUNTING_MISMATCH")
    ids = base.read_json(pilot.prior.PREPARATION / "pilot_notice_ids.json")
    gold = [row for row in pilot.prior.read_jsonl(pilot.prior.GOLD / "reviewed_condition_gold.jsonl") if row["notice_id"] in set(ids)]
    by_model = {}
    for name, path in (("baseline_v1", pilot.prior.BASELINE_OUT), ("rule_experiment_E", pilot.prior.RULE_E)):
        by_model[name] = [row for row in pilot.prior.read_jsonl(path) if row["notice_id"] in set(ids)]
    post, intermediate = [], []
    lead_after = llm._read_jsonl(base.REPLAY_V2 / "predictions_after_validation.jsonl")
    post.extend(row["candidate"] for row in lead_after)
    lead_before = llm._read_jsonl(base.REPLAY_V2 / "predictions_before_validation.jsonl")
    intermediate.append({"notice_id": ids[0], "intermediate_response": {"conditions": [r["proposal"] for r in lead_before]}})
    for i, notice_id in enumerate(ids[1:], start=1):
        out = RUN_DIR / f"notice_{i:02d}"
        after = llm._read_jsonl(out / "attribute_replay_v2/predictions_after_validation.jsonl")
        post.extend(row["candidate"] for row in after)
        before = llm._read_jsonl(out / "attribute_replay_v2/predictions_before_validation.jsonl")
        intermediate.append({"notice_id": notice_id, "intermediate_response": {"conditions": [r["proposal"] for r in before]}})
    by_model["llm_pre_validation"] = pilot.prior.prevalidation_predictions(intermediate, pilot.prior.INPUTS)
    by_model["llm_post_validation"] = post
    evaluated = {name: pilot.prior.evaluate_conditions(gold, rows) for name, rows in by_model.items()}
    comparison, summaries = pilot.prior.comparison_rows(evaluated)
    pilot.prior.write_csv(RUN_DIR / "pilot_baseline_comparison.csv", comparison)
    summary = {"status": "PILOT_COMPLETED", "run_id": RUN_ID, "notice_ids": ids,
               "gold_condition_count": sum(len(row.get("gold_conditions", [])) + len(row.get("missed_condition_candidates", [])) for row in gold),
               "evaluation": summaries, "condition_metrics_only": True, "logic_semantics_scored": False,
               "independent_evaluation_data_used": False, "review_status": "UNREVIEWED", "decision_eligible": False}
    pilot.prior.write_json(RUN_DIR / "evaluation_summary.json", summary)
    manifest["status"] = "PILOT_COMPLETED"
    manifest["evaluation_summary_sha256"] = digest(RUN_DIR / "evaluation_summary.json")
    write_json(RUN_DIR / "manifest.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--approve-budget-increase", action="store_true")
    modes.add_argument("--run-recovery", action="store_true")
    modes.add_argument("--evaluate", action="store_true")
    parser.add_argument("--authorize-api", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if args.run_recovery and not args.authorize_api:
        parser.error("--run-recovery requires explicit --authorize-api")
    if args.authorize_api and not args.run_recovery:
        parser.error("--authorize-api applies only with --run-recovery")
    result = (prepare() if args.prepare else approve_budget_increase() if args.approve_budget_increase
              else run_recovery(args.env_file) if args.run_recovery else evaluate_recovery())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
