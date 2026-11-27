"""Prepare a gated R2 v2 continuation that retains zero-candidate notices.

--prepare is offline. Remaining calls require --run-remaining --authorize-api.
The inherited 13-request cap is never reset or extended by this script.
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

from tools import extract_condition_candidates_llm as llm  # noqa: E402
from tools import run_condition_llm_openai_pilot_r2_norm_v2 as base  # noqa: E402
from tools import run_condition_llm_openai_pilot_r2_norm_v2_recovery as prior  # noqa: E402
from tools import run_condition_llm_openai_pilot_r2 as pilot_r2  # noqa: E402

RUN_ID = "llm_pilot_2_5c3_r2_norm_v2_p8"
RUN_DIR = base.DEV / RUN_ID
SOURCE_DIR = prior.RUN_DIR
SOURCE_LEDGER = SOURCE_DIR / "request_ledger.json"
TOTAL_LIMIT = 13
ALREADY_USED = 7
P8_MAX_REQUESTS = 6
START_INDEX = 4
CLAIM_PATH = base.DEV / f".{RUN_ID}_claim.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    base.write_json_atomic(path, value)


def _refresh_gates(ids: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    lead_gate = base.tech_gate_for_replay_only(
        read_json(RUN_DIR / "lead_replay_v2/replay_report.json"), RUN_DIR / "lead_replay_v2")
    if lead_gate.get("status") != "PASS":
        raise RuntimeError("LEAD_TECHNICAL_GATE_FAILED")
    per_notice, quality = [], []
    for index in range(1, 4):
        out = RUN_DIR / f"notice_{index:02d}"
        offline = read_json(out / "attribute_replay_v2/replay_report.json")
        gate = base.tech_gate_for_notice(out, offline)
        write_json(out / "technical_gate.json", gate)
        if gate.get("status") != "PASS":
            raise RuntimeError(f"REUSED_NOTICE_TECHNICAL_GATE_FAILED:{ids[index]}")
        per_notice.append({"notice_id": ids[index], "status": gate["status"], "source": "REUSED_RESPONSE"})
        quality.append({"notice_id": ids[index], "state": gate["extraction_quality_state"],
                        "valid_candidate_count": gate["valid_candidate_count"],
                        "rejected_count": gate["rejected_count"]})
    return per_notice, quality


def _existing_state() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    source_manifest = read_json(SOURCE_DIR / "manifest.json")
    ledger = read_json(SOURCE_LEDGER)
    ids = read_json(pilot_r2.prior.PREPARATION / "pilot_notice_ids.json")
    if (source_manifest.get("status") != "RECOVERY_BLOCKED"
            or source_manifest.get("budget_increase_approved") is not True
            or ledger.get("limit") != TOTAL_LIMIT or ledger.get("used") != ALREADY_USED
            or len(ledger.get("attempts", [])) != ALREADY_USED
            or len(ledger.get("recovery_attempts", [])) != 2):
        raise RuntimeError("P7_RECOVERY_STATE_NOT_READY_FOR_P8")
    if len(ids) != 10:
        raise RuntimeError("PILOT_ID_COUNT_MISMATCH")
    for index in range(1, 4):
        out = SOURCE_DIR / f"notice_{index:02d}"
        raw = llm._read_jsonl(out / "raw_llm_responses.jsonl")
        report = read_json(out / "run_report.json")
        if len(raw) != 1 or raw[0].get("accepted") is not True or report.get("status_counts", {}).get("COMPLETED") != 1:
            raise RuntimeError(f"PRIOR_RESPONSE_NOT_COMPLETE:{ids[index]}")
    lead_rows = llm._read_jsonl(base.PARENT_RAW)
    if len(lead_rows) != 1 or lead_rows[0].get("accepted") is not True:
        raise RuntimeError("LEAD_RESPONSE_NOT_COMPLETE")
    return source_manifest, ledger, ids


def build_fingerprint() -> dict[str, Any]:
    source_manifest, ledger, ids = _existing_state()
    current_fp, audit = base.preflight()
    if current_fp.get("pilot_notice_ids") != ids:
        raise RuntimeError("FROZEN_PILOT_IDS_CHANGED")
    old_fp = source_manifest["fingerprint"]
    response_records = [{"notice_id": ids[0], "path": base.PARENT_RAW.relative_to(ROOT).as_posix(),
                        "sha256": digest(base.PARENT_RAW)}]
    response_records.extend({"notice_id": ids[i],
        "path": (SOURCE_DIR / f"notice_{i:02d}/raw_llm_responses.jsonl").relative_to(ROOT).as_posix(),
        "sha256": digest(SOURCE_DIR / f"notice_{i:02d}/raw_llm_responses.jsonl"),
        "technical_gate_before_p8": read_json(SOURCE_DIR / f"notice_{i:02d}/technical_gate.json").get("status")}
        for i in range(1, 4))
    return {
        "run_id": RUN_ID,
        "source_run_id": prior.RUN_ID,
        "source_manifest_sha256": digest(SOURCE_DIR / "manifest.json"),
        "source_ledger_sha256": digest(SOURCE_LEDGER),
        "source_blocked_gate_sha256": digest(SOURCE_DIR / "notice_03/technical_gate.json"),
        "source_request_limit": ledger["limit"], "source_used": ledger["used"],
        "p8_available_requests": TOTAL_LIMIT - ledger["used"],
        "existing_response_count": len(response_records),
        "existing_responses": response_records,
        "source_lead_replay_manifest_sha256": digest(base.REPLAY_V2 / "manifest.json"),
        "source_lead_replay_report_sha256": digest(base.REPLAY_V2 / "replay_report.json"),
        "extractor_sha256": digest(ROOT / "tools/extract_condition_candidates_llm.py"),
        "runner_sha256": digest(ROOT / "tools/run_condition_llm_openai_pilot_r2_norm_v2.py"),
        "p8_runner_sha256": digest(Path(__file__)),
        "normalization_rules_version": llm.ATTRIBUTE_NORMALIZATION_RULES_VERSION,
        "normalization_rules_sha256": llm.ATTRIBUTE_NORMALIZATION_RULES_SHA256,
        "attribute_catalog_sha256": hashlib.sha256("\n".join(sorted(llm.ATTRIBUTE_CATALOG)).encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(llm.system_prompt().encode("utf-8")).hexdigest(),
        "generation_settings": {key: read_json(base.PARENT_MANIFEST)["fingerprint"][key] for key in (
            "model_id", "reasoning_effort", "max_completion_tokens", "timeout_seconds", "json_mode", "sdk_retries")},
        "frozen_input_hashes": current_fp["frozen_input_hashes"],
        "strict_evaluator_sha256": current_fp["v11_evaluator_sha256"],
        "pilot_notice_ids": ids,
        "unexecuted_notice_ids": ids[4:],
        "p8_starting_request_ordinal": ledger["used"] + 1,
        "p8_final_request_ordinal": TOTAL_LIMIT,
        "api_call_count_at_preparation": 0,
        "source_preflight_audit_sha256": hashlib.sha256(json.dumps(audit, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest(),
    }


def prepare() -> dict[str, Any]:
    with base.successor_lock():
        fp = build_fingerprint()
        manifest_path = RUN_DIR / "manifest.json"
        if manifest_path.is_file():
            manifest = read_json(manifest_path)
            if manifest.get("fingerprint") != fp:
                ledger = read_json(RUN_DIR / "request_ledger.json")
                old_fp = manifest.get("fingerprint", {})
                changed = {key for key in set(old_fp) | set(fp) if old_fp.get(key) != fp.get(key)}
                if (ledger.get("used") != ALREADY_USED or ledger.get("p8_attempts")
                        or not changed.issubset({"runner_sha256", "p8_runner_sha256"})
                        or old_fp.get("source_ledger_sha256") != fp.get("source_ledger_sha256")):
                    raise RuntimeError("P8_FINGERPRINT_CHANGED_AFTER_REQUESTS; PRESERVING_EXISTING_P8_ARTIFACTS")
                old_manifest_hash = digest(manifest_path)
                history = RUN_DIR / "preparation_history" / f"revision_{manifest.get('preparation_revision', 1)}"
                history.mkdir(parents=True, exist_ok=True)
                shutil.copy2(manifest_path, history / "manifest.json")
                shutil.copy2(RUN_DIR / "preflight_report.json", history / "preflight_report.json")
                for index in range(1, 4):
                    shutil.copy2(RUN_DIR / f"notice_{index:02d}/technical_gate.json",
                                 history / f"notice_{index:02d}_technical_gate.json")
                shutil.copy2(CLAIM_PATH, history / "claim.json")
                ids = fp["pilot_notice_ids"]
                per_notice, quality = _refresh_gates(ids)
                manifest.update({"fingerprint": fp,
                    "preparation_revision": manifest.get("preparation_revision", 1) + 1,
                    "supersedes_manifest_sha256": old_manifest_hash,
                    "fingerprint_refresh_reason": "TECHNICAL_GATE_AND_LOGIC_TRACEABILITY_UPDATE_BEFORE_API_CALL",
                    "technical_gate": {"status": "PASS_FOR_REUSED_RESPONSES", "notices": per_notice,
                                       "decision_eligible": False},
                    "extraction_quality": quality})
                write_json(manifest_path, manifest)
                claim = read_json(CLAIM_PATH)
                claim["fingerprint_sha256"] = hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()
                write_json(CLAIM_PATH, claim)
                write_json(RUN_DIR / "preflight_report.json", {
                    "status": "PASS", "api_call_count": 0, "responses_reused": 4,
                    "unexecuted_notice_count": 6, "requests_used": ALREADY_USED,
                    "request_limit": TOTAL_LIMIT, "requests_remaining": TOTAL_LIMIT-ALREADY_USED,
                    "zero_valid_candidate_notice_ids": [ids[3]],
                    "technical_gate": "PASS_WITH_SEPARATE_EXTRACTION_QUALITY_STATE",
                    "fingerprint_refresh_reason": manifest["fingerprint_refresh_reason"],
                    "supersedes_manifest_sha256": old_manifest_hash,
                })
            return {"status": manifest["status"], "already_prepared": True,
                    "responses_reused": manifest["responses_reused"],
                    "remaining_notice_count": len(manifest["unexecuted_notice_ids"]),
                    "requests_used": manifest["cumulative_used"], "request_limit": manifest["request_limit"],
                    "preparation_revision": manifest.get("preparation_revision", 1), "api_call_count": 0}
        if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
            raise RuntimeError("P8_OUTPUT_EXISTS_WITHOUT_MANIFEST")
        source_manifest, source_ledger, ids = _existing_state()
        for index in range(1, 4):
            shutil.copytree(SOURCE_DIR / f"notice_{index:02d}", RUN_DIR / f"notice_{index:02d}")
        shutil.copytree(base.REPLAY_V2, RUN_DIR / "lead_replay_v2")
        per_notice, quality_summary = _refresh_gates(ids)
        inherited = copy.deepcopy(source_ledger)
        inherited["p8_attempts"] = []
        inherited["lineage"].update({"p8_run_id": RUN_ID, "p8_parent_run_id": prior.RUN_ID,
                                     "p8_source_ledger_sha256": digest(SOURCE_LEDGER),
                                     "p8_inherited_used": source_ledger["used"],
                                     "p8_request_limit": source_ledger["limit"],
                                     "p8_new_budget_granted": 0,
                                     "p8_allowed_ordinals": list(range(8, 14))})
        write_json(RUN_DIR / "request_ledger.json", inherited)
        claim = {"run_id": RUN_ID, "source_run_id": prior.RUN_ID,
                 "fingerprint_sha256": hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest(),
                 "source_ledger_sha256": digest(SOURCE_LEDGER), "remaining_budget_owner": RUN_ID}
        base.claim_single_successor(CLAIM_PATH, claim)
        manifest = {
            "run_id": RUN_ID, "status": "PREPARED_NO_API_CALLS",
            "preparation_revision": 1,
            "source_run_id": prior.RUN_ID, "source_status_preserved": source_manifest["status"],
            "request_limit": TOTAL_LIMIT, "parent_used": 3, "prior_child_used": 2,
            "prior_recovery_used": 2, "p8_used": 0, "cumulative_used": ALREADY_USED,
            "remaining_request_count": TOTAL_LIMIT-ALREADY_USED,
            "responses_reused": len(fp["existing_responses"]),
            "reused_notice_ids": ids[:4], "unexecuted_notice_ids": ids[4:],
            "api_call_count": 0, "fingerprint": fp,
            "technical_gate": {"status": "PASS_FOR_REUSED_RESPONSES", "notices": per_notice,
                               "decision_eligible": False},
            "extraction_quality": quality_summary,
            "policy_changes": {"attribute_catalog": False, "attribute_mapping": False,
                                "prompt": False, "candidate_validation": False,
                                "evaluation_criteria": False},
            "decision_eligible": False,
        }
        write_json(RUN_DIR / "manifest.json", manifest)
        write_json(RUN_DIR / "preflight_report.json", {
            "status": "PASS", "api_call_count": 0, "responses_reused": len(fp["existing_responses"]),
            "unexecuted_notice_count": len(ids[4:]), "requests_used": ALREADY_USED,
            "request_limit": TOTAL_LIMIT, "requests_remaining": TOTAL_LIMIT-ALREADY_USED,
            "zero_valid_candidate_notice_ids": [ids[3]],
            "technical_gate": "PASS_WITH_SEPARATE_EXTRACTION_QUALITY_STATE",
            "zero_valid_candidate_policy": "INCLUDE_IN_STRICT_EVALUATION",
        })
        return {"status": manifest["status"], "run_id": RUN_ID,
                "responses_reused": len(fp["existing_responses"]),
                "unexecuted_notice_count": len(ids[4:]), "requests_used": ALREADY_USED,
                "request_limit": TOTAL_LIMIT, "requests_remaining": TOTAL_LIMIT-ALREADY_USED,
                "api_call_count": 0}


class P8Budget(llm.RequestBudget):
    def __init__(self, notice_id: str):
        ledger = read_json(RUN_DIR / "request_ledger.json")
        self.notice_id, self.limit, self.used = notice_id, ledger["limit"], ledger["used"]
        self.last_request_ordinal = None

    def consume(self) -> bool:
        with base.successor_lock():
            path = RUN_DIR / "request_ledger.json"
            ledger = read_json(path)
            p8_attempts = ledger["p8_attempts"]
            if ledger["limit"] != TOTAL_LIMIT or ledger["used"] >= TOTAL_LIMIT or len(p8_attempts) >= P8_MAX_REQUESTS:
                return False
            ordinal = ledger["used"] + 1
            if ordinal not in range(ALREADY_USED + 1, TOTAL_LIMIT + 1):
                return False
            attempt = {"request_ordinal": ordinal, "notice_id": self.notice_id,
                       "state": "RESERVED_BEFORE_API_CALL", "p8_run_id": RUN_ID}
            ledger["used"] = ordinal
            ledger["attempts"].append(copy.deepcopy(attempt))
            ledger["p8_attempts"].append(copy.deepcopy(attempt))
            write_json(path, ledger)
            self.used = self.last_request_ordinal = ordinal
            return True


def finish_attempt(notice_id: str, state: str) -> dict[str, Any]:
    path = RUN_DIR / "request_ledger.json"
    ledger = read_json(path)
    rows = [a for a in ledger["p8_attempts"] if a["notice_id"] == notice_id and a["state"] == "RESERVED_BEFORE_API_CALL"]
    if len(rows) != 1:
        raise RuntimeError("P8_RESERVATION_STATE_MISMATCH")
    ordinal = rows[0]["request_ordinal"]
    rows[0]["state"] = state
    for attempt in ledger["attempts"]:
        if attempt.get("request_ordinal") == ordinal:
            attempt["state"] = state
    write_json(path, ledger)
    return ledger


async def _run_remaining_async(env: dict[str, str], fp: dict[str, Any]) -> dict[str, Any]:
    expected = read_json(base.PARENT_MANIFEST)["fingerprint"]
    provider = llm.OpenAIDirectProvider(api_key=env["OPENAI_API_KEY"], model=env["OPENAI_CHAT_MODEL"],
                                         timeout_s=expected["timeout_seconds"],
                                         max_completion_tokens=expected["max_completion_tokens"],
                                         reasoning_effort=expected["reasoning_effort"])
    try:
        manifest = read_json(RUN_DIR / "manifest.json")
        ids = fp["pilot_notice_ids"]
        for index, notice_id in enumerate(ids[START_INDEX:], start=START_INDEX):
            if build_fingerprint() != fp:
                raise RuntimeError("P8_FINGERPRINT_CHANGED_DURING_RUN")
            out = RUN_DIR / f"notice_{index:02d}"
            ledger = read_json(RUN_DIR / "request_ledger.json")
            prior_attempts = [r for r in ledger["p8_attempts"] if r["notice_id"] == notice_id]
            if prior_attempts:
                if len(prior_attempts) != 1 or prior_attempts[0]["state"] != "COMPLETED" or not (out / "run_report.json").is_file():
                    raise RuntimeError("P8_PRIOR_ATTEMPT_UNRESOLVED; REFUSING_DUPLICATE_REQUEST")
                continue
            if out.exists() and any(out.iterdir()):
                raise RuntimeError("P8_OUTPUT_EXISTS_WITHOUT_LEDGER_RESERVATION")
            report = await llm.run_pilot(provider, [notice_id], output_dir=out,
                                         request_budget=P8Budget(notice_id), max_format_attempts=1)
            state = "COMPLETED" if report.get("status_counts", {}).get("COMPLETED") == 1 else "FAILED_RESPONSE"
            ledger = finish_attempt(notice_id, state)
            manifest.update({"p8_used": len(ledger["p8_attempts"]), "cumulative_used": ledger["used"],
                             "remaining_request_count": ledger["limit"] - ledger["used"],
                             "api_call_count": len(ledger["p8_attempts"])})
            manifest["current_response_notice_ids"] = ids[:index + 1] if state == "COMPLETED" else ids[:index]
            manifest["current_unexecuted_notice_ids"] = ids[index + 1:]
            manifest["current_api_failure_notice_ids"] = [] if state == "COMPLETED" else [notice_id]
            if state != "COMPLETED":
                manifest["status"] = "P8_BLOCKED"
                manifest["failed_notice_id"] = notice_id
                write_json(RUN_DIR / "manifest.json", manifest)
                return {"status": "P8_BLOCKED", "failed_notice_id": notice_id,
                        "requests_used": ledger["used"], "api_call_count": len(ledger["p8_attempts"])}
            offline = base.replay_notice(out / "raw_llm_responses.jsonl", out)
            gate = base.tech_gate_for_notice(out, offline)
            write_json(out / "technical_gate.json", gate)
            manifest["current_technical_pass_notice_ids"] = ids[:index + 1] if gate.get("status") == "PASS" else ids[:index]
            manifest["current_technical_blocked_notice_ids"] = [] if gate.get("status") == "PASS" else [notice_id]
            if gate.get("status") != "PASS":
                manifest["status"] = "P8_BLOCKED"
                manifest["failed_notice_id"] = notice_id
                write_json(RUN_DIR / "manifest.json", manifest)
                return {"status": "P8_BLOCKED", "failed_notice_id": notice_id, "technical_gate": gate}
            write_json(RUN_DIR / "manifest.json", manifest)
        ids = fp["pilot_notice_ids"]
        gates = [read_json(RUN_DIR / f"notice_{i:02d}/technical_gate.json") for i in range(1, 10)]
        if len(gates) != 9 or any(gate.get("status") != "PASS" for gate in gates):
            manifest["status"] = "P8_BLOCKED"
            write_json(RUN_DIR / "manifest.json", manifest)
            return {"status": "P8_BLOCKED", "reason": "TECHNICAL_GATE_FAILED"}
        quality = [{"notice_id": ids[i],
                    "state": read_json(RUN_DIR / f"notice_{i:02d}/technical_gate.json").get("extraction_quality_state"),
                    "valid_candidate_count": read_json(RUN_DIR / f"notice_{i:02d}/technical_gate.json").get("valid_candidate_count")}
                   for i in range(1, 10)]
        ledger = read_json(RUN_DIR / "request_ledger.json")
        manifest.update({"status": "TEN_NOTICE_TECHNICAL_GATE_PASSED", "quality_by_notice": quality,
                         "cumulative_used": ledger["used"], "remaining_request_count": ledger["limit"]-ledger["used"],
                         "decision_eligible": False})
        gate = {"status": "PASS", "technical_notice_count": 10,
                "zero_valid_candidate_notice_ids": [q["notice_id"] for q in quality if q["valid_candidate_count"] == 0],
                "extraction_quality_separate": True, "decision_eligible": False}
        write_json(RUN_DIR / "technical_gate.json", gate)
        write_json(RUN_DIR / "manifest.json", manifest)
        return {"status": manifest["status"], "requests_used": ledger["used"],
                "api_call_count": len(ledger["p8_attempts"]), "technical_gate": gate}
    finally:
        await provider.aclose()


def run_remaining(env_file: Path, *, check_only: bool = False) -> dict[str, Any]:
    with base.successor_lock():
        fp = build_fingerprint()
        manifest = read_json(RUN_DIR / "manifest.json")
        if manifest.get("fingerprint") != fp:
            raise RuntimeError("P8_FINGERPRINT_CHANGED")
        if manifest.get("status") not in {"PREPARED_NO_API_CALLS", "P8_IN_PROGRESS"}:
            raise RuntimeError("P8_RUN_STATE_NOT_EXECUTABLE")
        claim = read_json(CLAIM_PATH)
        expected_claim = hashlib.sha256(json.dumps(fp, sort_keys=True).encode()).hexdigest()
        if claim.get("fingerprint_sha256") != expected_claim:
            raise RuntimeError("P8_BUDGET_CLAIM_MISMATCH")
        ledger = read_json(RUN_DIR / "request_ledger.json")
        if ledger.get("limit") != TOTAL_LIMIT or ledger.get("used") != ALREADY_USED + len(ledger["p8_attempts"]):
            raise RuntimeError("P8_LEDGER_INVALID")
        if check_only:
            return {"status": "EXECUTION_PREFLIGHT_PASS", "run_id": RUN_ID,
                    "source_run_id": fp.get("source_run_id"), "fingerprint_matches": True,
                    "claim_matches": True, "requests_used": ledger["used"],
                    "request_limit": ledger["limit"], "remaining": ledger["limit"] - ledger["used"],
                    "remaining_notice_ids": fp["pilot_notice_ids"][START_INDEX:],
                    "api_call_count": 0}
        env = llm.load_env_safely(env_file)
        expected_settings = read_json(base.PARENT_MANIFEST)["fingerprint"]
        if env.get("OPENAI_CHAT_MODEL") != expected_settings["model_id"] or not env.get("OPENAI_API_KEY"):
            raise RuntimeError("P8_PROVIDER_CONFIG_MISMATCH")
        manifest["status"] = "P8_IN_PROGRESS"
        write_json(RUN_DIR / "manifest.json", manifest)
        return asyncio.run(_run_remaining_async(env, fp))


def evaluate() -> dict[str, Any]:
    manifest = read_json(RUN_DIR / "manifest.json")
    gate = read_json(RUN_DIR / "technical_gate.json")
    ledger = read_json(RUN_DIR / "request_ledger.json")
    if manifest.get("status") != "TEN_NOTICE_TECHNICAL_GATE_PASSED" or gate.get("status") != "PASS":
        raise RuntimeError("P8_TECHNICAL_GATE_NOT_PASSED")
    if ledger.get("used") != TOTAL_LIMIT or len(ledger.get("p8_attempts", [])) != P8_MAX_REQUESTS:
        raise RuntimeError("P8_REQUEST_ACCOUNTING_MISMATCH")
    ids = read_json(pilot_r2.prior.PREPARATION / "pilot_notice_ids.json")
    gold = [r for r in pilot_r2.prior.read_jsonl(pilot_r2.prior.GOLD / "reviewed_condition_gold.jsonl") if r["notice_id"] in set(ids)]
    by_model = {}
    for name, path in (("baseline_v1", pilot_r2.prior.BASELINE_OUT), ("rule_experiment_E", pilot_r2.prior.RULE_E)):
        by_model[name] = [r for r in pilot_r2.prior.read_jsonl(path) if r["notice_id"] in set(ids)]
    post, intermediate = [], []
    lead_after = llm._read_jsonl(RUN_DIR / "lead_replay_v2/predictions_after_validation.jsonl")
    post.extend(row["candidate"] for row in lead_after)
    lead_before = llm._read_jsonl(RUN_DIR / "lead_replay_v2/predictions_before_validation.jsonl")
    intermediate.append({"notice_id": ids[0], "intermediate_response": {"conditions": [r["proposal"] for r in lead_before]}})
    for i, notice_id in enumerate(ids[1:], start=1):
        out = RUN_DIR / f"notice_{i:02d}"
        after = llm._read_jsonl(out / "attribute_replay_v2/predictions_after_validation.jsonl")
        post.extend(row["candidate"] for row in after)
        before = llm._read_jsonl(out / "attribute_replay_v2/predictions_before_validation.jsonl")
        intermediate.append({"notice_id": notice_id, "intermediate_response": {"conditions": [r["proposal"] for r in before]}})
    by_model["llm_pre_validation"] = pilot_r2.prior.prevalidation_predictions(intermediate, pilot_r2.prior.INPUTS)
    by_model["llm_post_validation"] = post
    results = {name: pilot_r2.prior.evaluate_conditions(gold, preds) for name, preds in by_model.items()}
    comparison, summaries = pilot_r2.prior.comparison_rows(results)
    pilot_r2.prior.write_csv(RUN_DIR / "pilot_baseline_comparison.csv", comparison)
    zero_ids = [q["notice_id"] for q in manifest.get("quality_by_notice", []) if q.get("valid_candidate_count") == 0]
    summary = {"status": "PILOT_COMPLETED", "run_id": RUN_ID, "notice_ids": ids,
               "zero_valid_candidate_notice_ids_included": zero_ids,
               "gold_condition_count": sum(len(r.get("gold_conditions", [])) + len(r.get("missed_condition_candidates", [])) for r in gold),
               "evaluation": summaries, "condition_metrics_only": True, "logic_semantics_scored": False,
               "independent_evaluation_data_used": False, "review_status": "UNREVIEWED", "decision_eligible": False}
    pilot_r2.prior.write_json(RUN_DIR / "evaluation_summary.json", summary)
    manifest["status"] = "PILOT_COMPLETED"
    manifest["evaluation_summary_sha256"] = digest(RUN_DIR / "evaluation_summary.json")
    write_json(RUN_DIR / "manifest.json", manifest)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--run-remaining", action="store_true")
    modes.add_argument("--evaluate", action="store_true")
    parser.add_argument("--authorize-api", action="store_true")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = parser.parse_args()
    if args.run_remaining and not args.authorize_api:
        parser.error("--run-remaining requires explicit --authorize-api")
    if args.authorize_api and not args.run_remaining:
        parser.error("--authorize-api applies only with --run-remaining")
    result = prepare() if args.prepare else run_remaining(args.env_file) if args.run_remaining else evaluate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
