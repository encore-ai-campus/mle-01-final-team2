"""Prepare and execute the single, budget-inheriting R2 normalization-v2 child run.

No API request is made by --check, --offline-replay, or --prepare. Live calls
require the explicit --run-remaining --authorize-api pair.
"""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import sys
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import evaluate_condition_pipeline_v11 as v11  # noqa: E402
from tools import extract_condition_candidates_llm as llm  # noqa: E402
from tools import replay_condition_llm_attribute_normalization as replay  # noqa: E402
from tools import run_condition_llm_openai_pilot as pilot  # noqa: E402

DEV = ROOT / "data/evaluations/conditions/v1.1/20261126/development"
RUN_ID = "llm_pilot_2_5c3_r2_norm_v2"
RUN_DIR = DEV / RUN_ID
PARENT = DEV / "llm_pilot_2_5c3_r2"
PARENT_MANIFEST = PARENT / "manifest.json"
PARENT_LEDGER = PARENT / "request_ledger.json"
PARENT_GATE = PARENT / "lead_retry_gate.json"
PARENT_RAW = PARENT / "lead_retry/raw_llm_responses.jsonl"
REPLAY_V1 = DEV / "llm_pilot_2_5c3_r2_attribute_replay"
REPLAY_V2 = DEV / "llm_pilot_2_5c3_r2_attribute_replay_v2"
LOCK_PATH = DEV / ".llm_pilot_2_5c3_r2_budget_successor.lock"
CLAIM_PATH = DEV / "llm_pilot_2_5c3_r2_budget_successor.json"
TOTAL_LIMIT = 12
PARENT_USED = 3
_THREAD_LOCK = threading.RLock()
_LOCK_LOCAL = threading.local()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def write_jsonl_atomic(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
    os.replace(tmp, path)


@contextmanager
def successor_lock():
    """Cross-platform exclusive lock shared by every R2 successor invocation."""
    with _THREAD_LOCK:
        depth = getattr(_LOCK_LOCAL, "depth", 0)
        if depth:
            _LOCK_LOCAL.depth = depth + 1
            try:
                yield
            finally:
                _LOCK_LOCAL.depth -= 1
            return
        LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOCK_PATH.open("a+b") as stream:
            if os.name == "nt":
                import msvcrt
                stream.seek(0, os.SEEK_END)
                if stream.tell() == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_LOCK, 1)
                _LOCK_LOCAL.depth = 1
                try:
                    yield
                finally:
                    _LOCK_LOCAL.depth = 0
                    stream.seek(0)
                    msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
                _LOCK_LOCAL.depth = 1
                try:
                    yield
                finally:
                    _LOCK_LOCAL.depth = 0
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def verify_14_fixed_checks() -> tuple[list[str], dict[str, Any]]:
    ids = pilot.read_json(pilot.PREPARATION / "pilot_notice_ids.json")
    frozen = pilot.verify_frozen_inputs(ids)
    checks = frozen["checks"]
    if len(checks) != 14 or not all(checks.values()):
        raise RuntimeError("FIXED_INPUT_14_CHECKS_FAILED")
    return ids, frozen


def verify_v2_replay() -> dict[str, Any]:
    report_path = REPLAY_V2 / "replay_report.json"
    manifest_path = REPLAY_V2 / "manifest.json"
    if not report_path.is_file() or not manifest_path.is_file():
        raise RuntimeError("V2_OFFLINE_REPLAY_MISSING")
    report, manifest = read_json(report_path), read_json(manifest_path)
    if (report.get("status") != "OFFLINE_REPLAY_COMPLETE"
            or report.get("api_call_count") != 0
            or report.get("decision_eligible_true_count") != 0
            or manifest.get("normalization_rules_version") != "attribute-normalization-v2"
            or manifest.get("prior_failed_artifact_sha256", {}).get("lead_retry/raw_llm_responses.jsonl") != digest(PARENT_RAW)
            or manifest.get("prior_r2_manifest_sha256") != digest(PARENT_MANIFEST)
            or manifest.get("request_ledger_sha256_before") != digest(PARENT_LEDGER)
            or manifest.get("request_ledger_sha256_after") != digest(PARENT_LEDGER)
            or manifest.get("request_ledger_modified") is not False):
        raise RuntimeError("V2_OFFLINE_REPLAY_FINGERPRINT_MISMATCH")
    for name, expected in manifest.get("output_hashes", {}).items():
        if digest(REPLAY_V2 / name) != expected:
            raise RuntimeError(f"V2_REPLAY_OUTPUT_HASH_MISMATCH:{name}")
    if report.get("accepted_unreviewed_count", 0) <= 0:
        raise RuntimeError("V2_LEAD_HAS_NO_VALID_CANDIDATE")
    return {"report_sha256": digest(report_path), "manifest_sha256": digest(manifest_path),
            "outputs": manifest["output_hashes"]}


def direct_dependency_inventory() -> list[dict[str, Any]]:
    prep_manifest_path = pilot.PREPARATION / "pilot_manifest.json"
    prep = read_json(prep_manifest_path)
    parent_frozen = read_json(PARENT_MANIFEST)["fingerprint"]["frozen_inputs"]
    gold_manifest_path = pilot.GOLD / "manifest.json"
    gold = read_json(gold_manifest_path)
    replay_manifest = read_json(REPLAY_V2 / "manifest.json")
    v1_manifest = read_json(REPLAY_V1 / "manifest.json")
    expected_by_path: dict[Path, str | None] = {
        pilot.PREPARATION / "pilot_notice_ids.json": prep.get("ids_file_sha256"),
        prep_manifest_path: parent_frozen.get("pilot_manifest_sha256"),
        pilot.INPUTS: parent_frozen.get("input_sha256"),
        pilot.SAMPLES: replay_manifest.get("fixed_inputs", {}).get("representative_samples_sha256"),
        gold_manifest_path: parent_frozen.get("gold_manifest_sha256"),
        pilot.GOLD / "reviewed_condition_gold.jsonl": gold.get("outputs", {}).get("reviewed_condition_gold.jsonl", {}).get("sha256"),
        pilot.GOLD / "reviewed_logic_gold.jsonl": gold.get("outputs", {}).get("reviewed_logic_gold.jsonl", {}).get("sha256"),
        pilot.BASELINE_OUT: prep.get("prediction_versions", {}).get("baseline_v1", {}).get("condition_sha256"),
        pilot.BASELINE_LOGIC: prep.get("prediction_versions", {}).get("baseline_v1", {}).get("logic_sha256"),
        pilot.RULE_E: prep.get("prediction_versions", {}).get("rule_experiment_E", {}).get("condition_sha256"),
        pilot.RULE_E_LOGIC: prep.get("prediction_versions", {}).get("rule_experiment_E", {}).get("logic_sha256"),
        ROOT / "tools/evaluate_condition_pipeline_v11.py": prep.get("evaluation_policy", {}).get("evaluator_sha256"),
        ROOT / "tools/extract_condition_candidates_llm.py": None,
        PARENT_MANIFEST: v1_manifest.get("prior_r2_manifest_sha256"),
        PARENT_LEDGER: v1_manifest.get("request_ledger_sha256_before"),
        PARENT_GATE: v1_manifest.get("prior_failed_artifact_sha256", {}).get("lead_retry_gate.json"),
        PARENT_RAW: v1_manifest.get("prior_failed_artifact_sha256", {}).get("lead_retry/raw_llm_responses.jsonl"),
        REPLAY_V1 / "manifest.json": None,
        REPLAY_V2 / "manifest.json": None,
        REPLAY_V2 / "replay_report.json": replay_manifest.get("output_hashes", {}).get("replay_report.json"),
    }
    for name, expected in replay_manifest.get("output_hashes", {}).items():
        expected_by_path[REPLAY_V2 / name] = expected
    rows = []
    for path, expected in expected_by_path.items():
        exists = path.is_file()
        actual = digest(path) if exists else None
        rows.append({"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
                     "exists": exists, "readable": exists, "expected_sha256": expected,
                     "actual_sha256": actual, "status": "PASS" if exists and (expected is None or expected == actual) else "BLOCKED"})
    return rows


def verify_parent_lineage() -> dict[str, Any]:
    manifest, ledger, gate = read_json(PARENT_MANIFEST), read_json(PARENT_LEDGER), read_json(PARENT_GATE)
    if manifest.get("status") != "LEAD_BLOCKED" or gate.get("status") != "BLOCKED":
        raise RuntimeError("PARENT_R2_GATE_OR_STATUS_CHANGED")
    if (manifest.get("requests_used") != PARENT_USED or ledger.get("limit") != TOTAL_LIMIT
            or ledger.get("used") != PARENT_USED or len(ledger.get("attempts", [])) != PARENT_USED
            or [a.get("request_ordinal") for a in ledger["attempts"]] != [1, 2, 3]):
        raise RuntimeError("PARENT_REQUEST_LEDGER_UNEXPECTED")
    raw_rows = llm._read_jsonl(PARENT_RAW)
    if len(raw_rows) != 1 or raw_rows[0].get("notice_id") != pilot.read_json(pilot.PREPARATION / "pilot_notice_ids.json")[0]:
        raise RuntimeError("PARENT_LEAD_RESPONSE_MISMATCH")
    if REPLAY_V1.is_dir():
        v1 = read_json(REPLAY_V1 / "replay_report.json")
        v1_manifest = read_json(REPLAY_V1 / "manifest.json")
        if v1_manifest.get("prior_failed_artifact_sha256", {}).get("lead_retry/raw_llm_responses.jsonl") != digest(PARENT_RAW):
            raise RuntimeError("V1_REPLAY_SOURCE_MISMATCH")
    return {"manifest_sha256": digest(PARENT_MANIFEST), "ledger_sha256": digest(PARENT_LEDGER),
            "gate_sha256": digest(PARENT_GATE), "raw_response_sha256": digest(PARENT_RAW),
            "status": manifest["status"], "parent_used": ledger["used"], "request_limit": ledger["limit"],
            "prior_attempts": copy.deepcopy(ledger["attempts"]),
            "parent_continuation_blocked": True}


def build_fingerprint(ids: list[str], frozen: dict[str, Any], parent: dict[str, Any], replay_info: dict[str, Any]) -> dict[str, Any]:
    parent_manifest = read_json(PARENT_MANIFEST)
    parent_fp = parent_manifest["fingerprint"]
    return {
        "run_id": RUN_ID,
        "parent_run_id": parent_manifest["fingerprint"]["run_id"],
        "parent_manifest_sha256": parent["manifest_sha256"],
        "parent_request_ledger_sha256": parent["ledger_sha256"],
        "parent_failed_gate_sha256": parent["gate_sha256"],
        "parent_raw_response_sha256": parent["raw_response_sha256"],
        "normalization_rules_version": llm.ATTRIBUTE_NORMALIZATION_RULES_VERSION,
        "normalization_rules_sha256": llm.ATTRIBUTE_NORMALIZATION_RULES_SHA256,
        "extractor_sha256": digest(ROOT / "tools/extract_condition_candidates_llm.py"),
        "runner_sha256": digest(Path(__file__)),
        "prompt_sha256": hashlib.sha256(llm.system_prompt().encode("utf-8")).hexdigest(),
        "model_id": parent_fp["model_id"],
        "reasoning_effort": parent_fp["reasoning_effort"],
        "max_completion_tokens": parent_fp["max_completion_tokens"],
        "timeout_seconds": parent_fp["timeout_seconds"],
        "json_mode": parent_fp["json_mode"],
        "sdk_retries": parent_fp["sdk_retries"],
        "frozen_input_hashes": frozen,
        "pilot_notice_ids": ids,
        "parent_replay_v2": replay_info,
        "v1_replay_sha256": digest(REPLAY_V1 / "manifest.json"),
        "v11_evaluator_sha256": digest(ROOT / "tools/evaluate_condition_pipeline_v11.py"),
    }


def preflight() -> tuple[dict[str, Any], dict[str, Any]]:
    ids, frozen = verify_14_fixed_checks()
    parent = verify_parent_lineage()
    replay_info = verify_v2_replay()
    fp = build_fingerprint(ids, frozen, parent, replay_info)
    if fp["prompt_sha256"] != parent_fp_prompt():
        raise RuntimeError("PROMPT_CHANGED_FROM_PARENT_R2")
    dependencies = direct_dependency_inventory()
    if not all(row["status"] == "PASS" for row in dependencies):
        raise RuntimeError("DIRECT_PILOT_DEPENDENCY_HASH_CHECK_FAILED")
    return fp, {"fixed_input_checks": frozen["checks"], "direct_dependencies": dependencies,
                "parent": parent, "replay_v2": replay_info, "api_call_count": 0}


def parent_fp_prompt() -> str:
    return read_json(PARENT_MANIFEST)["fingerprint"]["prompt_sha256_after"]


def validate_saved_fingerprint(saved: dict[str, Any], current: dict[str, Any]) -> None:
    if saved != current:
        changed = sorted(k for k in set(saved) | set(current) if saved.get(k) != current.get(k))
        raise RuntimeError("CHILD_FINGERPRINT_CHANGED:" + ",".join(changed))


def claim_single_successor(claim_path: Path, claim: dict[str, Any]) -> bool:
    """Create one lineage claim; return False only for the exact same claim."""
    if claim_path.exists():
        if read_json(claim_path) != claim:
            raise RuntimeError("R2_BUDGET_ALREADY_CLAIMED_BY_ANOTHER_OR_CHANGED_CHILD")
        return False
    claim_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(claim_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        if read_json(claim_path) != claim:
            raise RuntimeError("R2_BUDGET_ALREADY_CLAIMED_BY_ANOTHER_OR_CHANGED_CHILD")
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(claim, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return True


def prepare() -> dict[str, Any]:
    fp, audit = preflight()
    lead_gate = tech_gate_for_replay_only(read_json(REPLAY_V2 / "replay_report.json"), REPLAY_V2)
    if lead_gate.get("status") != "PASS" or lead_gate.get("decision_eligible") is not False:
        raise RuntimeError("V2_LEAD_TECHNICAL_GATE_FAILED")
    with successor_lock():
        if CLAIM_PATH.exists():
            claim = read_json(CLAIM_PATH)
            if claim.get("run_id") != RUN_ID:
                raise RuntimeError("R2_BUDGET_ALREADY_CLAIMED_BY_ANOTHER_OR_CHANGED_CHILD")
            if (RUN_DIR / "manifest.json").is_file():
                manifest = read_json(RUN_DIR / "manifest.json")
                if claim.get("fingerprint") == fp:
                    validate_saved_fingerprint(manifest["fingerprint"], fp)
                    return {"status": manifest["status"], "already_prepared": True,
                            "api_call_count": manifest.get("api_call_count", 0),
                            "remaining_requests": TOTAL_LIMIT-read_json(RUN_DIR / "request_ledger.json")["used"]}
                ledger = read_json(RUN_DIR / "request_ledger.json")
                if (manifest.get("api_call_count") != 0 or ledger.get("child_attempts")
                        or ledger.get("used") != PARENT_USED
                        or digest(PARENT_LEDGER) != fp["parent_request_ledger_sha256"]):
                    raise RuntimeError("CHILD_FINGERPRINT_CHANGED_AFTER_REQUESTS; continuation blocked")
                history = RUN_DIR / "preparation_history"
                history.mkdir(parents=True, exist_ok=True)
                old_hash = hashlib.sha256((RUN_DIR / "manifest.json").read_bytes()).hexdigest()
                archive_manifest = history / f"manifest_{old_hash}.json"
                archive_claim = history / f"claim_{old_hash}.json"
                if not archive_manifest.exists():
                    archive_manifest.write_bytes((RUN_DIR / "manifest.json").read_bytes())
                if not archive_claim.exists():
                    archive_claim.write_bytes(CLAIM_PATH.read_bytes())
                claim["fingerprint"] = fp
                claim["preparation_revision"] = manifest.get("preparation_revision", 1) + 1
                claim["supersedes_manifest_sha256"] = old_hash
                write_json_atomic(CLAIM_PATH, claim)
                manifest["status"] = "PREPARED_NO_API_CALLS"
                manifest["fingerprint"] = fp
                manifest["preparation_revision"] = claim["preparation_revision"]
                manifest["supersedes_manifest_sha256"] = old_hash
                manifest["api_call_count"] = 0
                manifest["preflight_audit"] = audit
                manifest["technical_gate"] = {"status": "LEAD_PASS_REMAINING_9_PENDING",
                                               "lead_gate": lead_gate, "decision_eligible": False}
                write_json_atomic(RUN_DIR / "manifest.json", manifest)
                write_json_atomic(RUN_DIR / "preflight_report.json", {
                    "status": "PASS", "fixed_input_check_count": 14,
                    "fixed_input_checks": audit["fixed_input_checks"],
                    "direct_dependencies": audit["direct_dependencies"],
                    "api_call_count": 0, "parent_status": audit["parent"]["status"],
                    "parent_gate": "BLOCKED", "parent_ledger_preserved": True,
                    "remaining_requests": TOTAL_LIMIT-PARENT_USED,
                    "lead_technical_gate": lead_gate,
                    "v2_replay_sha256": audit["replay_v2"]["manifest_sha256"],
                    "preparation_revision": claim["preparation_revision"],
                    "supersedes_manifest_sha256": old_hash,
                })
                return {"status": "PREPARED_NO_API_CALLS", "run_id": RUN_ID,
                        "preparation_revision": claim["preparation_revision"],
                        "supersedes_manifest_sha256": old_hash,
                        "remaining_requests": TOTAL_LIMIT-PARENT_USED, "api_call_count": 0}
            raise RuntimeError("SUCCESSOR_CLAIM_EXISTS_WITHOUT_CHILD_MANIFEST")
        if RUN_DIR.exists() and any(RUN_DIR.iterdir()):
            raise RuntimeError("CHILD_OUTPUT_ALREADY_EXISTS_WITHOUT_VALID_CLAIM")
        claim = {"run_id": RUN_ID, "parent_run_id": "llm_pilot_2_5c3_r2",
                 "parent_request_ledger_sha256": fp["parent_request_ledger_sha256"],
                 "parent_requests_used": PARENT_USED, "cumulative_limit": TOTAL_LIMIT,
                 "child_request_limit": TOTAL_LIMIT - PARENT_USED, "fingerprint": fp,
                 "preparation_revision": 1}
        # Create the one-successor claim exclusively while holding the cross-process lock.
        claim_single_successor(CLAIM_PATH, claim)
        RUN_DIR.mkdir(parents=True, exist_ok=True)
        parent_ledger = read_json(PARENT_LEDGER)
        child_ledger = {
            "limit": TOTAL_LIMIT, "used": PARENT_USED,
            "attempts": copy.deepcopy(parent_ledger["attempts"]),
            "lineage": {"parent_run_id": "llm_pilot_2_5c3_r2",
                        "parent_ledger_sha256": fp["parent_request_ledger_sha256"],
                        "parent_used": PARENT_USED, "child_limit": TOTAL_LIMIT - PARENT_USED,
                        "new_budget_granted": 0, "allowed_ordinals": list(range(4, 13))},
            "child_attempts": [],
        }
        write_json_atomic(RUN_DIR / "request_ledger.json", child_ledger)
        write_json_atomic(RUN_DIR / "manifest.json", {
            "run_id": RUN_ID, "status": "PREPARED_NO_API_CALLS",
            "parent_run_id": "llm_pilot_2_5c3_r2", "request_limit": TOTAL_LIMIT,
            "parent_requests_used": PARENT_USED, "child_request_limit": TOTAL_LIMIT-PARENT_USED,
            "api_call_count": 0, "preparation_revision": 1, "fingerprint": fp,
            "technical_gate": {"status": "LEAD_PASS_REMAINING_9_PENDING",
                               "lead_gate": lead_gate, "decision_eligible": False},
            "preflight_audit": audit,
        })
        write_json_atomic(RUN_DIR / "preflight_report.json", {
            "status": "PASS", "fixed_input_check_count": 14,
            "fixed_input_checks": audit["fixed_input_checks"],
            "direct_dependencies": audit["direct_dependencies"], "api_call_count": 0,
            "parent_status": audit["parent"]["status"], "parent_gate": "BLOCKED",
            "parent_ledger_preserved": True, "remaining_requests": TOTAL_LIMIT-PARENT_USED,
            "v2_replay_sha256": audit["replay_v2"]["manifest_sha256"], "preparation_revision": 1,
            "lead_technical_gate": lead_gate,
        })
        return {"status": "PREPARED_NO_API_CALLS", "run_id": RUN_ID,
                "remaining_requests": TOTAL_LIMIT-PARENT_USED, "api_call_count": 0}


def check_dependencies() -> dict[str, Any]:
    fp, audit = preflight()
    return {"status": "PASS", "run_id": RUN_ID, "api_call_count": 0,
            "fixed_input_check_count": 14, "fixed_input_checks": audit["fixed_input_checks"],
            "direct_dependencies": audit["direct_dependencies"],
            "parent": audit["parent"], "replay_v2": audit["replay_v2"], "fingerprint": fp}


class ChildLedgerBudget(llm.RequestBudget):
    def __init__(self, path: Path, notice_id: str):
        self.path, self.notice_id = path, notice_id
        ledger = read_json(path)
        self.limit, self.used = ledger["limit"], ledger["used"]
        self.label = notice_id
        self.last_request_ordinal = None

    def consume(self) -> bool:
        with successor_lock():
            ledger = read_json(self.path)
            if ledger["limit"] != TOTAL_LIMIT or ledger["used"] >= TOTAL_LIMIT:
                return False
            if len(ledger["child_attempts"]) >= TOTAL_LIMIT-PARENT_USED:
                return False
            ordinal = ledger["used"] + 1
            if ordinal not in range(4, 13):
                return False
            ledger["used"] = ordinal
            ledger["child_attempts"].append({"request_ordinal": ordinal, "notice_id": self.notice_id,
                                              "state": "RESERVED_BEFORE_API_CALL"})
            ledger["attempts"].append(copy.deepcopy(ledger["child_attempts"][-1]))
            write_json_atomic(self.path, ledger)
            self.used = ordinal
            self.last_request_ordinal = ordinal
            return True


def finish_request(path: Path, notice_id: str, state: str) -> None:
    with successor_lock():
        ledger = read_json(path)
        matches = [a for a in ledger["child_attempts"] if a["notice_id"] == notice_id]
        if len(matches) != 1 or matches[0]["state"] != "RESERVED_BEFORE_API_CALL":
            raise RuntimeError("CHILD_LEDGER_RESERVATION_STATE_MISMATCH")
        matches[0]["state"] = state
        matches[0]["result_recorded_at_request_ordinal"] = matches[0]["request_ordinal"]
        for row in ledger["attempts"]:
            if row.get("request_ordinal") == matches[0]["request_ordinal"]:
                row["state"] = state
        write_json_atomic(path, ledger)


def validate_child_ledger(ledger: dict[str, Any], parent_hash: str) -> None:
    child = ledger.get("child_attempts", [])
    expected_ordinals = list(range(PARENT_USED + 1, PARENT_USED + 1 + len(child)))
    if (ledger.get("limit") != TOTAL_LIMIT or ledger.get("used") != PARENT_USED + len(child)
            or len(child) > TOTAL_LIMIT - PARENT_USED
            or [a.get("request_ordinal") for a in child] != expected_ordinals
            or len({a.get("notice_id") for a in child}) != len(child)
            or ledger.get("lineage", {}).get("parent_ledger_sha256") != parent_hash
            or ledger.get("lineage", {}).get("new_budget_granted") != 0):
        raise RuntimeError("CHILD_REQUEST_LEDGER_INVALID")


def tech_gate_for_notice(output_dir: Path, offline_report: dict[str, Any]) -> dict[str, Any]:
    run_report = pilot.read_json(output_dir / "run_report.json")
    execution = pilot.read_jsonl(output_dir / "per_notice_execution.jsonl")
    raw_rows = llm._read_jsonl(output_dir / "raw_llm_responses.jsonl")
    validations = llm._read_jsonl(output_dir / "validation_details.jsonl")
    before = llm._read_jsonl(output_dir / "predictions_before_validation.jsonl")
    replay_details = llm._read_jsonl(output_dir / "attribute_replay_v2/validation_details.jsonl")
    logic = llm._read_jsonl(output_dir / "attribute_replay_v2/logic_proposals.jsonl")
    original_count = len(before)
    statuses_accounted = len(validations) == original_count and len(replay_details) == original_count
    source_evidence_ok = all(row.get("evidence_quote_validation") == "PASS" for row in replay_details)
    date_ok = all(row.get("date_temporal_preserved") is True for row in replay_details)
    accepted = offline_report.get("accepted_unreviewed_count", 0)
    held = offline_report.get("held_for_review_count", 0)
    rejected = offline_report.get("rejected_count", 0)
    accounted = accepted + held + rejected == offline_report.get("proposal_count") == original_count
    unaccepted_indexes = {row.get("proposal_index") for row in replay_details
                          if row.get("final_status") != "ACCEPTED_UNREVIEWED"
                          and isinstance(row.get("proposal_index"), int)}
    logical_ok = False
    structure_checks = {}
    if len(raw_rows) == 1 and len(logic) == 1:
        try:
            original = json.loads(raw_rows[0]["response_attempts"][-1])
            mapping = {int(k): v for k, v in logic[0]["index_to_condition_id"].items()}
            expected = llm.preserve_logic_references(original, mapping)
            states = {str(row["proposal_index"]): (
                "ACCEPTED_UNREVIEWED" if row.get("final_status") == "ACCEPTED_UNREVIEWED" else
                "HELD_FOR_REVIEW" if row.get("reason") == "ATTRIBUTE_SEMANTIC_AMBIGUITY" else
                "REJECTED_OR_DEDUPLICATED") for row in replay_details}
            expected["proposal_validation_states"] = states
            for exception in expected["exception_resolution"]:
                exception["target_candidate_validation_states"] = {
                    str(index): states.get(str(index), "INVALID_INDEX")
                    for index in exception["original_target_condition_indexes"]}
            structure_checks = {key: logic[0].get(key) == value for key, value in expected.items()}
            logical_ok = (all(structure_checks.values()) and not expected["invalid_reference_indexes"]
                          and set(expected["unresolved_condition_indexes"]) == unaccepted_indexes)
        except (KeyError, ValueError, TypeError):
            logical_ok = False
    quality_state = "CANDIDATES_AVAILABLE" if accepted > 0 else "ZERO_VALID_CANDIDATES"
    quality_gate = "REVIEW_REQUIRED" if accepted == 0 else "UNREVIEWED_CANDIDATES"
    pass_gate = bool(
        run_report.get("failure_count") == 0 and run_report.get("schema_error_count") == 0
        and execution and execution[0].get("status") == "COMPLETED"
        and raw_rows and raw_rows[0].get("response_attempts")
        and accounted and statuses_accounted
        and source_evidence_ok and date_ok and logical_ok
        and offline_report.get("v11_schema_error_count") == 0
        and offline_report.get("api_call_count") == 0
        and offline_report.get("decision_eligible_true_count") == 0
        and all(row.get("decision_eligible") is False for row in replay_details)
        and all(row.get("decision_eligible") is False for row in validations)
    )
    return {"status": "PASS" if pass_gate else "BLOCKED", "api_response_present": bool(raw_rows and raw_rows[0].get("response_attempts")),
            "json_parse_and_execution_ok": bool(execution and execution[0].get("status") == "COMPLETED" and run_report.get("failure_count") == 0),
            "all_proposals_accounted": accounted and statuses_accounted,
            "valid_candidate_count": accepted, "held_count": held, "rejected_count": rejected,
            "extraction_quality_state": quality_state, "extraction_quality_gate": quality_gate,
            "evidence_ok": source_evidence_ok, "date_temporal_preserved": date_ok,
            "schema_error_count": offline_report.get("v11_schema_error_count"),
            "incomplete_logic_preserved": logical_ok,
            "logic_structure_checks": structure_checks,
            "decision_eligible_true_count": 0,
            "decision_eligible": False,
            "reason": None if pass_gate else "TECHNICAL_VALIDATION_OR_TRACEABILITY_FAILURE"}


def replay_notice(raw_path: Path, output_dir: Path) -> dict[str, Any]:
    return replay.replay(raw_path, output_dir / "attribute_replay_v2")


async def _run_remaining_batch(env: dict[str, str], fp: dict[str, Any], manifest: dict[str, Any],
                              ledger_path: Path) -> dict[str, Any]:
    expected = read_json(PARENT_MANIFEST)["fingerprint"]
    provider = llm.OpenAIDirectProvider(api_key=env["OPENAI_API_KEY"], model=env["OPENAI_CHAT_MODEL"],
                                         timeout_s=expected["timeout_seconds"],
                                         max_completion_tokens=expected["max_completion_tokens"],
                                         reasoning_effort=expected["reasoning_effort"])
    try:
        for index, notice_id in enumerate(fp["pilot_notice_ids"][1:], start=1):
            current_fp, _ = preflight()
            validate_saved_fingerprint(manifest["fingerprint"], current_fp)
            ledger = read_json(ledger_path)
            validate_child_ledger(ledger, fp["parent_request_ledger_sha256"])
            out = RUN_DIR / f"notice_{index:02d}"
            prior_attempts = [a for a in ledger["child_attempts"] if a["notice_id"] == notice_id]
            if prior_attempts:
                if len(prior_attempts) != 1 or prior_attempts[0]["state"] != "COMPLETED" or not (out / "run_report.json").is_file():
                    raise RuntimeError("PRIOR_CHILD_RESERVATION_UNRESOLVED; refusing duplicate API call")
                continue
            if out.exists() and any(out.iterdir()):
                raise RuntimeError("NOTICE_OUTPUT_EXISTS_WITHOUT_LEDGER_RESERVATION")
            budget = ChildLedgerBudget(ledger_path, notice_id)
            report = await llm.run_pilot(provider, [notice_id], output_dir=out,
                                          request_budget=budget, max_format_attempts=1)
            raw_path = out / "raw_llm_responses.jsonl"
            request_state = "COMPLETED" if report.get("status_counts", {}).get("COMPLETED") == 1 else "FAILED_RESPONSE"
            finish_request(ledger_path, notice_id, request_state)
            ledger = read_json(ledger_path)
            validate_child_ledger(ledger, fp["parent_request_ledger_sha256"])
            if request_state != "COMPLETED":
                manifest["status"] = "REMAINING_BLOCKED"
                manifest["requests_used"] = ledger["used"]
                write_json_atomic(RUN_DIR / "manifest.json", manifest)
                return {"status": "BLOCKED", "failed_notice_id": notice_id,
                        "request_ordinal": ledger["used"], "api_call_count": len(ledger["child_attempts"])}
            current_fp, _ = preflight()
            validate_saved_fingerprint(manifest["fingerprint"], current_fp)
            offline = replay_notice(raw_path, out)
            gate = tech_gate_for_notice(out, offline)
            write_json_atomic(out / "technical_gate.json", gate)
            if gate["status"] != "PASS":
                manifest["status"] = "REMAINING_BLOCKED"
                manifest["requests_used"] = ledger["used"]
                write_json_atomic(RUN_DIR / "manifest.json", manifest)
                return {"status": "BLOCKED", "failed_notice_id": notice_id,
                        "request_ordinal": ledger["used"], "technical_gate": gate,
                        "api_call_count": len(ledger["child_attempts"])}
        ledger = read_json(ledger_path)
        validate_child_ledger(ledger, fp["parent_request_ledger_sha256"])
        current_fp, _ = preflight()
        validate_saved_fingerprint(manifest["fingerprint"], current_fp)
        manifest["requests_used"] = ledger["used"]
        manifest["api_call_count"] = len(ledger["child_attempts"])
        manifest["status"] = "TEN_NOTICE_TECHNICAL_GATE_PENDING"
        write_json_atomic(RUN_DIR / "manifest.json", manifest)
        gate = evaluate_ten_notice_gate()
        write_json_atomic(RUN_DIR / "technical_gate.json", gate)
        manifest["technical_gate"] = {"status": gate["status"], "decision_eligible": False}
        manifest["status"] = "TEN_NOTICE_TECHNICAL_GATE_PASSED" if gate["status"] == "PASS" else "REMAINING_BLOCKED"
        write_json_atomic(RUN_DIR / "manifest.json", manifest)
        return {"status": manifest["status"], "api_call_count": manifest["api_call_count"],
                "requests_used": ledger["used"], "technical_gate": gate}
    finally:
        await provider.aclose()


def run_remaining(env_file: Path) -> dict[str, Any]:
    with successor_lock():
        fp, _ = preflight()
        manifest = read_json(RUN_DIR / "manifest.json")
        validate_saved_fingerprint(manifest["fingerprint"], fp)
        if manifest.get("status") not in {"PREPARED_NO_API_CALLS", "REMAINING_IN_PROGRESS"}:
            raise RuntimeError("CHILD_RUN_STATE_NOT_EXECUTABLE")
        claim = read_json(CLAIM_PATH)
        if claim.get("run_id") != RUN_ID or claim.get("fingerprint") != fp:
            raise RuntimeError("BUDGET_SUCCESSOR_CLAIM_MISMATCH")
        ledger_path = RUN_DIR / "request_ledger.json"
        ledger = read_json(ledger_path)
        validate_child_ledger(ledger, fp["parent_request_ledger_sha256"])
        if digest(PARENT_LEDGER) != fp["parent_request_ledger_sha256"]:
            raise RuntimeError("PARENT_LEDGER_CHANGED_AFTER_PREPARATION")
        env = llm.load_env_safely(env_file)
        expected = read_json(PARENT_MANIFEST)["fingerprint"]
        if env.get("OPENAI_CHAT_MODEL") != expected["model_id"] or not env.get("OPENAI_API_KEY"):
            raise RuntimeError("CHILD_PROVIDER_CONFIG_MISMATCH")
        manifest["status"] = "REMAINING_IN_PROGRESS"
        write_json_atomic(RUN_DIR / "manifest.json", manifest)
        return asyncio.run(_run_remaining_batch(env, fp, manifest, ledger_path))


def evaluate_ten_notice_gate() -> dict[str, Any]:
    ids = pilot.read_json(pilot.PREPARATION / "pilot_notice_ids.json")
    lead_report = read_json(REPLAY_V2 / "replay_report.json")
    lead_status = tech_gate_for_replay_only(lead_report, REPLAY_V2)
    per_notice = []
    if lead_status["status"] != "PASS":
        return {"status": "BLOCKED", "reason": "LEAD_REPLAY_TECHNICAL_GATE_FAILED", "decision_eligible": False}
    per_notice.append({"notice_id": ids[0], "status": "PASS", "source": "OFFLINE_REPLAY"})
    for index, notice_id in enumerate(ids[1:], start=1):
        gate_path = RUN_DIR / f"notice_{index:02d}" / "technical_gate.json"
        if not gate_path.is_file():
            return {"status": "BLOCKED", "reason": "NOTICE_GATE_MISSING", "notice_id": notice_id,
                    "completed_notice_count": len(per_notice), "decision_eligible": False}
        gate = read_json(gate_path)
        per_notice.append({"notice_id": notice_id, "status": gate.get("status")})
        if gate.get("status") != "PASS":
            return {"status": "BLOCKED", "reason": "NOTICE_TECHNICAL_GATE_FAILED", "notice_id": notice_id,
                    "completed_notice_count": len(per_notice), "decision_eligible": False}
    return {"status": "PASS", "notice_count": len(per_notice), "notices": per_notice,
            "decision_eligible": False, "actual_support_decision_approved": False}


def tech_gate_for_replay_only(report: dict[str, Any], replay_dir: Path) -> dict[str, Any]:
    details = llm._read_jsonl(replay_dir / "validation_details.jsonl")
    logic = llm._read_jsonl(replay_dir / "logic_proposals.jsonl")
    accounted = report.get("accepted_unreviewed_count", 0) + report.get("held_for_review_count", 0) + report.get("rejected_count", 0) == report.get("proposal_count") == len(details)
    pass_gate = bool(report.get("api_call_count") == 0 and report.get("v11_schema_error_count") == 0
                     and report.get("accepted_unreviewed_count", 0) > 0 and accounted
                     and report.get("decision_eligible_true_count") == 0
                     and all(d.get("evidence_quote_validation") == "PASS" for d in details)
                     and all(d.get("date_temporal_preserved") for d in details)
                     and (not report.get("held_for_review_count") or all(
                         l.get("logical_completeness") == "INCOMPLETE" and l.get("unresolved_condition_indexes")
                         for l in logic)))
    return {"status": "PASS" if pass_gate else "BLOCKED", "decision_eligible": False,
            "valid_candidate_count": report.get("accepted_unreviewed_count", 0),
            "held_count": report.get("held_for_review_count", 0), "proposals_accounted": accounted}


def evaluate_ten() -> dict[str, Any]:
    fp, _ = preflight()
    manifest = read_json(RUN_DIR / "manifest.json")
    validate_saved_fingerprint(manifest["fingerprint"], fp)
    if read_json(CLAIM_PATH).get("fingerprint") != fp:
        raise RuntimeError("BUDGET_SUCCESSOR_CLAIM_MISMATCH")
    validate_child_ledger(read_json(RUN_DIR / "request_ledger.json"), fp["parent_request_ledger_sha256"])
    gate = read_json(RUN_DIR / "technical_gate.json")
    if gate.get("status") != "PASS" or gate.get("decision_eligible") is not False:
        raise RuntimeError("TEN_NOTICE_TECHNICAL_GATE_NOT_PASSED")
    ids = pilot.read_json(pilot.PREPARATION / "pilot_notice_ids.json")
    gold = [row for row in pilot.read_jsonl(pilot.GOLD / "reviewed_condition_gold.jsonl") if row["notice_id"] in set(ids)]
    by_model = {}
    for name, path in (("baseline_v1", pilot.BASELINE_OUT), ("rule_experiment_E", pilot.RULE_E)):
        by_model[name] = [row for row in pilot.read_jsonl(path) if row["notice_id"] in set(ids)]
    post, intermediate = [], []
    lead_after = llm._read_jsonl(REPLAY_V2 / "predictions_after_validation.jsonl")
    post.extend(row["candidate"] for row in lead_after)
    lead_before = llm._read_jsonl(REPLAY_V2 / "predictions_before_validation.jsonl")
    intermediate.append({"notice_id": ids[0], "intermediate_response": {"conditions": [r["proposal"] for r in lead_before]}})
    for i, notice_id in enumerate(ids[1:], start=1):
        out = RUN_DIR / f"notice_{i:02d}"
        after = llm._read_jsonl(out / "attribute_replay_v2/predictions_after_validation.jsonl")
        post.extend(row["candidate"] for row in after)
        before = llm._read_jsonl(out / "attribute_replay_v2/predictions_before_validation.jsonl")
        intermediate.append({"notice_id": notice_id, "intermediate_response": {"conditions": [r["proposal"] for r in before]}})
    by_model["llm_pre_validation"] = pilot.prevalidation_predictions(intermediate, pilot.INPUTS)
    by_model["llm_post_validation"] = post
    evaluated = {name: pilot.evaluate_conditions(gold, rows) for name, rows in by_model.items()}
    comparison, summaries = pilot.comparison_rows(evaluated)
    pilot.write_csv(RUN_DIR / "pilot_baseline_comparison.csv", comparison)
    summary = {"status": "PILOT_COMPLETED", "run_id": RUN_ID, "notice_ids": ids,
               "gold_condition_count": sum(len(row.get("gold_conditions", [])) + len(row.get("missed_condition_candidates", [])) for row in gold),
               "evaluation": summaries, "condition_metrics_only": True,
               "logic_semantics_scored": False, "independent_evaluation_data_used": False,
               "review_status": "UNREVIEWED", "decision_eligible": False}
    pilot.write_json(RUN_DIR / "evaluation_summary.json", summary)
    manifest = read_json(RUN_DIR / "manifest.json")
    manifest["status"] = "PILOT_COMPLETED"
    manifest["evaluation_summary_sha256"] = digest(RUN_DIR / "evaluation_summary.json")
    write_json_atomic(RUN_DIR / "manifest.json", manifest)
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    modes = ap.add_mutually_exclusive_group(required=True)
    modes.add_argument("--check", action="store_true")
    modes.add_argument("--offline-replay", action="store_true")
    modes.add_argument("--prepare", action="store_true")
    modes.add_argument("--run-remaining", action="store_true")
    modes.add_argument("--evaluate", action="store_true")
    ap.add_argument("--authorize-api", action="store_true")
    ap.add_argument("--env-file", type=Path, default=ROOT / ".env")
    args = ap.parse_args()
    if args.offline_replay:
        result = replay.replay(PARENT_RAW, REPLAY_V2)
    elif args.check:
        result = check_dependencies()
    elif args.prepare:
        result = prepare()
    elif args.run_remaining:
        if not args.authorize_api:
            ap.error("--run-remaining requires explicit --authorize-api")
        result = run_remaining(args.env_file)
    elif args.evaluate:
        result = evaluate_ten()
    else:
        raise AssertionError("unreachable")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
