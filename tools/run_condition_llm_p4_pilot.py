"""Prepare/run the isolated P4 structured-output pilot (live calls are opt-in)."""
from __future__ import annotations

import argparse
import asyncio
import copy
import hashlib
import json
import os
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import condition_llm_next_policy as policy
from tools import condition_logic_evaluation_adapter as logic_adapter
from tools import evaluate_condition_pipeline_v11 as evaluator
from tools import run_condition_llm_openai_pilot as pilot
from tools import extract_condition_candidates_llm as legacy

RUN_ID = "llm_pilot_2_5c3d5a_p4"
SOURCE_RUN_ID = "llm_pilot_2_5c3_r2_p12"
OUT = ROOT / "data/evaluations/conditions/v1.1/20261126/development" / RUN_ID
DEV = OUT.parent
PILOT_PREP = ROOT / "data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development"
INPUTS = pilot.INPUTS
IDS_FILE = PILOT_PREP / "pilot_notice_ids.json"
POLICY_ARTIFACTS = policy.OUT
P12 = DEV / SOURCE_RUN_ID
GOLD_CONDITIONS = pilot.GOLD / "reviewed_condition_gold.jsonl"
GOLD_LOGIC = pilot.GOLD / "reviewed_logic_gold.jsonl"
LEDGER = OUT / "request_ledger.json"
MANIFEST = OUT / "manifest.json"
LOCK = DEV / f".{RUN_ID}.lock"
MODEL = "gpt-5.6-luna"
LIMIT = 10
SETTINGS = {"model": MODEL, "reasoning_effort": "low", "max_completion_tokens": 8192,
            "timeout_seconds": 180, "sdk_max_retries": 0, "response_format": "json_schema_strict"}
APPROVAL_TOKEN = "APPROVE_P4_10_REQUESTS"


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"INVALID_JSONL:{path}:{line_number}") from exc
    return rows


@contextmanager
def exclusive_lock(path: Path = LOCK):
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise RuntimeError("P4_RUN_ALREADY_CLAIMED_OR_LOCK_STALE") from exc
    try:
        os.write(fd, f"pid={os.getpid()}\n".encode())
        os.close(fd)
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def fixed_ids() -> list[str]:
    ids = read_json(IDS_FILE)
    source = read_json(P12 / "manifest.json")
    if ids != source["fingerprint"]["pilot_notice_ids"] or len(ids) != 10 or len(set(ids)) != 10:
        raise RuntimeError("P12_FIXED_NOTICE_IDS_CHANGED")
    return ids


def fingerprint() -> dict[str, Any]:
    ids = fixed_ids()
    input_rows = read_jsonl(INPUTS)
    by_id = {r["notice_id"]: r for r in input_rows}
    if len(by_id) != len(input_rows) or set(ids) - set(by_id):
        raise RuntimeError("FROZEN_INPUT_NOTICE_SET_INVALID")
    gold = read_jsonl(GOLD_CONDITIONS)
    gold_logic = read_jsonl(GOLD_LOGIC)
    idset = set(ids)
    gold = [r for r in gold if r["notice_id"] in idset]
    gold_logic = [r for r in gold_logic if r["notice_id"] in idset]
    condition_count = sum(len(r.get("gold_conditions", [])) + len(r.get("missed_condition_candidates", [])) for r in gold)
    roots = [root for row in gold_logic for root in evaluator._roots(row)]
    graph_counts = logic_adapter.tree_counts(roots)
    if (len(gold), condition_count, graph_counts["groups"], graph_counts["edges"]) != (10, 62, 24, 71):
        raise RuntimeError("FIXED_EVALUATION_DATA_MISMATCH")
    p12_manifest = read_json(P12 / "manifest.json")
    if p12_manifest.get("status") != "EVALUATION_READY":
        raise RuntimeError("P12_SOURCE_NOT_EVALUATION_READY")
    files = [INPUTS, IDS_FILE, PILOT_PREP / "pilot_manifest.json", pilot.GOLD / "manifest.json",
             GOLD_CONDITIONS, GOLD_LOGIC, pilot.BASELINE_OUT, pilot.BASELINE_LOGIC, pilot.RULE_E,
             pilot.RULE_E_LOGIC, Path(policy.__file__), Path(logic_adapter.__file__), Path(evaluator.__file__),
             ROOT / "tools/evaluate_condition_pipeline.py", Path(pilot.__file__), Path(legacy.__file__), Path(__file__),
             ROOT / "schemas/conditions/contracts/draft-v1/attribute_semantic_contract_v1.json",
             ROOT / "schemas/conditions/contracts/draft-v1/value_normalization_contract_v1.json",
             POLICY_ARTIFACTS / "provider_output_schema.json", POLICY_ARTIFACTS / "internal_output_schema.json",
             POLICY_ARTIFACTS / "P4_prompt.txt", P12 / "manifest.json", P12 / "request_ledger.json"]
    paths = {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(files))}
    return {"run_id": RUN_ID, "source_run_id": SOURCE_RUN_ID, "notice_ids": ids,
            "settings": SETTINGS, "policy_version": policy.VERSION, "policy_module_sha256": sha(Path(policy.__file__)),
            "prompt_sha256": sha(POLICY_ARTIFACTS / "P4_prompt.txt"),
            "provider_schema_sha256": sha(POLICY_ARTIFACTS / "provider_output_schema.json"),
            "internal_schema_sha256": sha(POLICY_ARTIFACTS / "internal_output_schema.json"),
            "attribute_contract_sha256": sha(ROOT / "schemas/conditions/contracts/draft-v1/attribute_semantic_contract_v1.json"),
            "normalization_version": "safe-condition-normalization-subset-v1:N1",
            "normalization_module_sha256": sha(ROOT / "tools/condition_safe_normalization_experiment.py"),
            "logic_adapter_version": logic_adapter.VERSION,
            "strict_evaluator_sha256": sha(Path(evaluator.__file__)),
            "condition_evaluator_sha256": sha(ROOT / "tools/evaluate_condition_pipeline.py"),
            "runner_sha256": sha(Path(__file__)),
            "files": paths, "fixed_counts": {"notices": len(ids), "gold_conditions": condition_count,
                "gold_logic_groups": graph_counts["groups"], "gold_logic_relations": graph_counts["edges"]},
            "input_order": ids, "decision_eligible": False}


def current_fingerprint() -> dict[str, Any]:
    stored = read_json(MANIFEST)
    actual = fingerprint()
    if actual != stored.get("fingerprint"):
        expected = stored.get("fingerprint", {})
        diff = sorted(k for k in set(actual) | set(expected) if actual.get(k) != expected.get(k))
        raise RuntimeError("P4_FINGERPRINT_CHANGED:" + ",".join(diff))
    return actual


def verify_preflight(require_manifest: bool = True) -> dict[str, Any]:
    fp = fingerprint()
    saved_provider = read_json(POLICY_ARTIFACTS / "provider_output_schema.json")
    saved_internal = read_json(POLICY_ARTIFACTS / "internal_output_schema.json")
    saved_prompt = (POLICY_ARTIFACTS / "P4_prompt.txt").read_text(encoding="utf-8")
    if saved_provider != policy.provider_schema() or saved_internal != policy.internal_schema():
        raise RuntimeError("P4_SCHEMA_ARTIFACT_FINGERPRINT_MISMATCH")
    if saved_prompt != policy.system_prompt("P4") + "\n":
        raise RuntimeError("P4_PROMPT_ARTIFACT_FINGERPRINT_MISMATCH")
    if require_manifest:
        current_fingerprint()
        ledger = read_json(LEDGER)
        if ledger.get("run_id") != RUN_ID or ledger.get("limit") != LIMIT:
            raise RuntimeError("P4_LEDGER_ID_OR_LIMIT_MISMATCH")
    import importlib.metadata
    from openai.resources.chat.completions import AsyncCompletions
    from openai.types import ResponseFormatJSONSchema
    import inspect
    params = inspect.signature(AsyncCompletions.create).parameters
    # Construct the exact SDK value without making a request.
    schema_option = ResponseFormatJSONSchema(type="json_schema", json_schema={
        "name": "condition_next_policy_v1", "strict": True, "schema": policy.provider_schema()})
    schema_dump = schema_option.model_dump(exclude_none=True, by_alias=True)
    if "response_format" not in params or schema_dump.get("type") != "json_schema":
        raise RuntimeError("SDK_STRUCTURED_OUTPUT_SERIALIZATION_UNAVAILABLE")
    for name, schema in (("provider", policy.provider_schema()), ("internal", policy.internal_schema())):
        policy.Draft202012Validator.check_schema(schema)
    provider_json = json.dumps(policy.provider_schema(), ensure_ascii=False)
    forbidden = [token for token in ("\"allOf\"", "\"if\"", "\"then\"", "\"else\"", "\"uniqueItems\"") if token in provider_json]
    if forbidden:
        raise RuntimeError("UNSUPPORTED_PROVIDER_SCHEMA_CONSTRAINT:" + ",".join(forbidden))
    if SETTINGS != {"model": "gpt-5.6-luna", "reasoning_effort": "low", "max_completion_tokens": 8192,
                    "timeout_seconds": 180, "sdk_max_retries": 0, "response_format": "json_schema_strict"}:
        raise RuntimeError("FROZEN_MODEL_SETTINGS_CHANGED")
    return {"status": "PASS", "run_id": RUN_ID, "source_run_id": SOURCE_RUN_ID,
            "notice_ids": fp["notice_ids"], "counts": fp["fixed_counts"],
            "sdk": {k: importlib.metadata.version(k) for k in ("openai", "httpx", "jsonschema")},
            "response_format_serialized": {"type": schema_dump.get("type"),
                "json_schema_name": schema_dump.get("json_schema", {}).get("name"),
                "strict": schema_dump.get("json_schema", {}).get("strict"),
                "schema_root_type": schema_dump.get("json_schema", {}).get("schema", {}).get("type")},
            "response_format_parameter": True,
            "provider_schema_enum_values": sum(len(v.get("enum", [])) for v in _walk_dicts(policy.provider_schema())),
            "provider_schema_unsupported_constraints": forbidden,
            "internal_schema_uses_additional_local_constraints": True,
            "server_schema_acceptance": "NOT_TESTED; first live request is compatibility gate",
            "client_timeout_seconds": 180, "sdk_max_retries": 0,
            "api_calls": 0, "fingerprint_sha256": sha_bytes(json.dumps(fp, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode())}


def _walk_dicts(value):
    if isinstance(value, dict):
        yield value
        for item in value.values():
            yield from _walk_dicts(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_dicts(item)


def prepare() -> dict[str, Any]:
    with exclusive_lock():
        if OUT.exists():
            raise FileExistsError(f"Refusing to overwrite P4 run: {OUT}")
        check = verify_preflight(require_manifest=False)
        fp = fingerprint()
        OUT.mkdir(parents=True)
        ledger = {"run_id": RUN_ID, "source_run_id": SOURCE_RUN_ID, "limit": LIMIT, "used": 0,
                  "approved": False, "reserved": 0, "succeeded": 0, "failed": 0,
                  "remaining": 0, "attempts": [], "api_call_count": 0,
                  "status": "INACTIVE_APPROVAL_REQUIRED", "decision_eligible": False}
        write_json(LEDGER, ledger)
        manifest = {"run_id": RUN_ID, "source_run_id": SOURCE_RUN_ID,
                    "status": "PREPARED_NO_API_CALLS", "fingerprint": fp, "request_limit": LIMIT,
                    "budget_status": "INACTIVE_APPROVAL_REQUIRED", "api_call_count": 0,
                    "cumulative_used": 0, "remaining_request_count": 0,
                    "prepared_first_notice_id": fp["notice_ids"][0],
                    "prepared_remaining_notice_ids": fp["notice_ids"][1:],
                    "response_received_notice_ids": [], "technical_pass_notice_ids": [],
                    "technical_block_notice_ids": [], "evaluation_eligible_notice_ids": [],
                    "evaluation_ready": False, "decision_eligible": False}
        write_json(MANIFEST, manifest)
        write_json(OUT / "preflight_report.json", check)
        write_json(OUT / "experiment_plan.json", {"policy": "P4 integrated only", "run_id": RUN_ID,
            "source_run_id": SOURCE_RUN_ID, "sample_notice_ids": fp["notice_ids"],
            "fixed_evaluation": fp["fixed_counts"], "arms": [
                {"id": "P4_WITHOUT_N1", "postprocess": "P4 policy and validators; no N1"},
                {"id": "P4_WITH_N1", "postprocess": "same raw P4 response plus safe N1"}],
            "raw_response_reuse_between_arms": True, "request_count": 10,
            "first_notice_gate": fp["notice_ids"][0], "model_settings": SETTINGS,
            "strict_condition_evaluator": "tools/evaluate_condition_pipeline_v11.py",
            "logic_adapter": logic_adapter.VERSION, "decision_eligible": False})
        write_json(OUT / "baseline_comparison_contract.json", {"notices": 10, "gold_conditions": 62,
            "gold_logic_groups": 24, "gold_logic_relations": 71,
            "rule_v1_f1": 0.1364, "rule_E_f1": 0.1412, "P12_f1": 0.021277,
            "N1_f1": 0.063830, "pilot_precision_target": 0.60, "pilot_recall_target": 0.50,
            "development_only_not_independent_evaluation": True, "criteria_changed": False})
        (OUT / "execution_runbook.md").write_text(
            "# P4 파일럿 실행 순서\n\n"
            "아래 API 실행 명령은 별도 사용자 승인 후에만 사용합니다. 현재 신규 요청 장부는 비활성 상태입니다.\n\n"
            "```powershell\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --preflight\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --offline-self-test\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --prepare\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --approve-budget --approval-token APPROVE_P4_10_REQUESTS --approval-reference '사용자 승인 날짜와 근거'\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --run-first --authorize-api\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --check-first\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --run-remaining --authorize-api\n"
            ".\\.venv\\Scripts\\python.exe tools/run_condition_llm_p4_pilot.py --evaluate\n"
            "```\n\n"
            "첫 응답에서 기술 Gate가 PASS가 아니면 나머지 9건은 차단됩니다. `--run-first`와 `--run-remaining`은 실제 API를 호출합니다.\n",
            encoding="utf-8", newline="\n")
        write_json(OUT / "budget_proposal.json", {"proposed_new_requests": 10, "approved_requests": 0,
            "status": "PROPOSAL_ONLY", "first_request_included": True, "automatic_retries": 0,
            "historical_p12_usage": "13/13; preserved", "cost_estimate_usd": {"scenario_low": 0.045794,
            "scenario_high": 0.123684, "not_a_hard_bound": True, "input_usd_per_million": 0.20,
            "output_usd_per_million_including_reasoning": 1.20, "assumptions": "P4 planning tokens only; no cache discount"},
            "cost_source": "https://developers.openai.com/api/docs/models/gpt-5.6-luna"})
        return {"status": manifest["status"], "run_id": RUN_ID, "api_calls": 0,
                "budget_activated": False, "preflight": check["status"]}


def approve_budget(token: str, approval_reference: str) -> dict[str, Any]:
    with exclusive_lock():
        current_fingerprint()
        if token != APPROVAL_TOKEN or not approval_reference.strip():
            raise RuntimeError("EXPLICIT_P4_BUDGET_APPROVAL_REQUIRED")
        ledger = read_json(LEDGER)
        if ledger["approved"] or ledger["used"] or ledger["attempts"]:
            raise RuntimeError("P4_BUDGET_ALREADY_ACTIVATED_OR_USED")
        ledger.update({"approved": True, "remaining": LIMIT, "status": "APPROVED_UNUSED",
                       "approval": {"approved_limit": LIMIT, "approval_reference": approval_reference,
                                    "approved_at_utc": datetime.now(timezone.utc).isoformat(),
                                    "explicit_confirmation_token": token}})
        write_json(LEDGER, ledger)
        manifest = read_json(MANIFEST)
        manifest.update({"budget_status": "APPROVED_UNUSED", "remaining_request_count": LIMIT,
                         "budget_approval": ledger["approval"]})
        write_json(MANIFEST, manifest)
        return {"status": "APPROVED_UNUSED", "limit": LIMIT, "used": 0, "remaining": LIMIT}


class P4Client:
    def __init__(self, api_key: str, *, mock_transport=None):
        import httpx
        from openai import AsyncOpenAI
        self.http = httpx.AsyncClient(transport=mock_transport, timeout=180) if mock_transport is not None else None
        self.client = AsyncOpenAI(api_key=api_key, http_client=self.http, max_retries=0, timeout=180)
        self.model = MODEL

    async def extract(self, source: dict[str, Any]):
        from tools.condition_llm_next_policy import system_prompt, provider_schema
        response = await self.client.chat.completions.create(model=self.model, reasoning_effort="low",
            max_completion_tokens=8192,
            response_format={"type": "json_schema", "json_schema": {"name": "condition_next_policy_v1",
                "strict": True, "schema": provider_schema()}},
            messages=[{"role": "system", "content": system_prompt("P4")},
                      {"role": "user", "content": json.dumps({"notice_text": source["raw_text"]}, ensure_ascii=False)}])
        return response

    async def aclose(self):
        await self.client.close()


def reserve(notice_id: str) -> int:
    current_fingerprint()
    ledger = read_json(LEDGER)
    if not ledger.get("approved"):
        raise RuntimeError("P4_BUDGET_NOT_APPROVED")
    if ledger["used"] >= ledger["limit"]:
        raise RuntimeError("P4_REQUEST_BUDGET_EXHAUSTED")
    if any(x["notice_id"] == notice_id for x in ledger["attempts"]):
        raise RuntimeError("P4_DUPLICATE_NOTICE_CALL_BLOCKED")
    ordinal = ledger["used"] + 1
    attempt = {"run_id": RUN_ID, "request_ordinal": ordinal, "notice_id": notice_id,
               "reserved_at_utc": datetime.now(timezone.utc).isoformat(), "response_status": "RESERVED",
               "http_status": None, "provider_request_id": None, "finish_reason": None,
               "usage": None, "duration_ms": None, "raw_response_sha256": None,
               "intermediate_schema_status": None, "final_candidate_status": None, "technical_gate_status": None}
    ledger["attempts"].append(attempt)
    ledger["used"] += 1
    ledger["reserved"] += 1
    ledger["remaining"] = ledger["limit"] - ledger["used"]
    ledger["api_call_count"] = ledger["used"]
    ledger["status"] = "IN_PROGRESS"
    write_json(LEDGER, ledger)
    append_jsonl(OUT / "request_ledger.jsonl", attempt)
    manifest = read_json(MANIFEST)
    manifest["cumulative_used"] = ledger["used"]
    manifest["remaining_request_count"] = ledger["remaining"]
    manifest["api_call_count"] = ledger["api_call_count"]
    manifest["status"] = "IN_PROGRESS"
    write_json(MANIFEST, manifest)
    return ordinal


def update_attempt(ordinal: int, **fields) -> None:
    ledger = read_json(LEDGER)
    row = next(r for r in ledger["attempts"] if r["request_ordinal"] == ordinal)
    row.update(fields)
    if fields.get("response_status") in {"TECHNICAL_PASS", "EVALUABLE_EXTRACTION_FAILURE"}:
        ledger["succeeded"] += 1
    elif fields.get("response_status") not in {"RESERVED", None}:
        ledger["failed"] += 1
    ledger["reserved"] = sum(r["response_status"] == "RESERVED" for r in ledger["attempts"])
    ledger["status"] = "IN_PROGRESS" if ledger["reserved"] else "ACTIVE"
    write_json(LEDGER, ledger)
    append_jsonl(OUT / "request_ledger.jsonl", {"run_id": RUN_ID, "request_ordinal": ordinal,
        "notice_id": row["notice_id"], "event": "RESULT_RECORDED", "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        **fields})
    manifest = read_json(MANIFEST)
    manifest["cumulative_used"] = ledger["used"]
    manifest["remaining_request_count"] = ledger["limit"] - ledger["used"]
    manifest["api_call_count"] = ledger["api_call_count"]
    write_json(MANIFEST, manifest)


def process_response(source: dict[str, Any], response, *, ordinal: int, started: float) -> dict[str, Any]:
    notice_id = source["notice_id"]
    usage = response.usage.model_dump(mode="json") if response.usage else None
    choice = response.choices[0] if response.choices else None
    message = choice.message if choice else None
    text = message.content if message and isinstance(message.content, str) else ""
    metadata = {"run_id": RUN_ID, "request_ordinal": ordinal, "notice_id": notice_id,
                "http_status": 200, "provider_request_id": getattr(response, "_request_id", None),
                "finish_reason": choice.finish_reason if choice else None,
                "usage": usage, "duration_ms": round((time.perf_counter() - started) * 1000),
                "raw_response_sha256": sha_bytes(text.encode("utf-8"))}
    ndir = OUT / f"notice_{ordinal:02d}"
    raw = {**metadata, "response_text": text, "refusal": getattr(message, "refusal", None)}
    write_json(ndir / "raw_response.json", raw)  # persisted before parsing/validation
    append_jsonl(OUT / "responses.jsonl", raw)
    if not choice or choice.finish_reason != "stop" or raw["refusal"]:
        reason = "OUTPUT_TOKEN_LIMIT" if choice and choice.finish_reason == "length" else "OUTPUT_INCOMPLETE_OR_REFUSAL"
        update_attempt(ordinal, **metadata, response_status=reason,
                       intermediate_schema_status="NOT_RUN", final_candidate_status="NOT_RUN", technical_gate_status="BLOCKED")
        return {"status": "BLOCKED", "notice_id": notice_id, "reason": "OUTPUT_INCOMPLETE_OR_REFUSAL"}
    try:
        payload = json.loads(text)
        write_json(ndir / "provider_parsed.json", payload)
        outputs = {}
        for label, n1 in (("without_n1", False), ("with_n1", True)):
            outputs[label] = policy.validate_and_convert(source, payload, apply_n1=n1)
        for label, result in outputs.items():
            write_json(ndir / f"{label}.json", result)
            append_jsonl(OUT / f"predictions_{label}.jsonl", {"notice_id": notice_id, "conditions": result["conditions"]})
            append_jsonl(OUT / f"logic_{label}.jsonl", {"notice_id": notice_id,
                "logic_sections": result["evaluation_record"].get("logic_sections", []),
                "decision_eligible": False, "exceptions": result["exceptions"],
                "unresolved_relations": result["unresolved_relations"],
                "logic_completeness": result["logic_completeness"]})
        review_summary = outputs["with_n1"]["candidate_review_queue"]
        review = list(review_summary.get("held_items", [])) + outputs["with_n1"]["unresolved_conditions"]
        write_json(ndir / "review_queue.json", review)
        write_json(ndir / "reference_audit.json", outputs["with_n1"]["reference_audit"])
        gate = {"notice_id": notice_id, "request_ordinal": ordinal, "status": "PASS",
            "http_response_received": True, "provider_schema_response_received": True,
            "response_generation_complete": True, "json_parse": "PASS",
            "raw_response_persisted_before_validation": True, "intermediate_and_internal_schema": "PASS",
            "final_v11_condition_validation": "PASS", "candidate_traceability": True,
            "unsupported_attributes_preserved_for_review": True,
            "evidence_validation": "PASS", "logic_reference_integrity": "PASS",
            "decision_eligible": False, "zero_valid_candidate_count_is_not_a_technical_failure": True,
            "candidate_count": len(outputs["with_n1"]["conditions"]),
            "review_queue_count": len(review), "reference_audit": outputs["with_n1"]["reference_audit"]}
        write_json(ndir / "technical_gate.json", gate)
        status = "TECHNICAL_PASS"  # zero valid candidates is allowed when response validates and is traceable
        manifest = read_json(MANIFEST)
        manifest["response_received_notice_ids"] = list(dict.fromkeys(manifest["response_received_notice_ids"] + [notice_id]))
        manifest["technical_pass_notice_ids"] = list(dict.fromkeys(manifest["technical_pass_notice_ids"] + [notice_id]))
        manifest["evaluation_eligible_notice_ids"] = list(dict.fromkeys(manifest["evaluation_eligible_notice_ids"] + [notice_id]))
        update_attempt(ordinal, **metadata, response_status=status,
                       intermediate_schema_status="PASS", final_candidate_status="VALIDATED_OR_REVIEW_QUEUED",
                       technical_gate_status="PASS", decision_eligible=False)
        write_json(MANIFEST, manifest)
        write_json(OUT / "manifest.json", manifest)
        return {"status": status, "notice_id": notice_id, "candidate_count": len(outputs["with_n1"]["conditions"]),
                "review_queue_count": len(review), "decision_eligible": False}
    except Exception as exc:
        # Preserve the raw payload and record typed failures; do not coerce them into ordinary empty extraction.
        err = {"notice_id": notice_id, "request_ordinal": ordinal,
               "error_class": type(exc).__name__, "error_code": str(exc).split(":", 1)[0]}
        write_json(ndir / "processing_error.json", err)
        manifest = read_json(MANIFEST)
        manifest["response_received_notice_ids"] = list(dict.fromkeys(manifest["response_received_notice_ids"] + [notice_id]))
        manifest["technical_block_notice_ids"] = list(dict.fromkeys(manifest["technical_block_notice_ids"] + [notice_id]))
        from jsonschema import ValidationError
        if isinstance(exc, ValidationError):
            parsed_payload = json.loads(text)
            provider_errors = list(policy.Draft202012Validator(policy.provider_schema()).iter_errors(parsed_payload))
            stage = "PROVIDER_SCHEMA" if provider_errors else "INTERNAL_SCHEMA"
            reproduced = provider_errors
            if not reproduced:
                normalized = copy.deepcopy(parsed_payload)
                source_text = source["raw_text"]
                for i, condition in enumerate(normalized.get("conditions", [])):
                    normalized["conditions"][i] = policy.safe.normalize(condition, "N1", source_text)[0]
                reproduced = list(policy.Draft202012Validator(policy.internal_schema(),
                    format_checker=policy.FormatChecker()).iter_errors(normalized))
            if reproduced:
                errors = [{"schema": stage, "path": list(error.absolute_path), "message": error.message,
                           "validator": error.validator, "validator_value": error.validator_value}
                          for error in reproduced]
                write_json(ndir / "schema_errors.json", errors)
                write_json(ndir / "evaluable_failure.json", {**err, "status": "SCHEMA_VALIDATION_ERROR",
                    "response_received": True, "json_parsed": True, "schema_stage": stage,
                    "schema_errors": errors, "prediction_policy": "EMPTY_PREDICTIONS",
                    "evaluation_eligible": True, "decision_eligible": False})
                manifest["evaluation_eligible_notice_ids"] = list(dict.fromkeys(manifest["evaluation_eligible_notice_ids"] + [notice_id]))
                write_json(MANIFEST, manifest)
                update_attempt(ordinal, **metadata, response_status="EVALUABLE_EXTRACTION_FAILURE",
                    intermediate_schema_status="FAIL_REPRODUCED", final_candidate_status="EMPTY_PREDICTIONS",
                    technical_gate_status="EXTRACTION_FAILED", evaluation_eligible=True, schema_errors=errors)
                return {"status": "EVALUABLE_EXTRACTION_FAILURE", "notice_id": notice_id,
                        "schema_stage": stage, "decision_eligible": False}
        write_json(MANIFEST, manifest)
        status = "SCHEMA_OR_VALIDATION_ERROR" if isinstance(exc, (ValueError, ValidationError, json.JSONDecodeError)) else "VALIDATOR_INTERNAL_ERROR"
        update_attempt(ordinal, **metadata, response_status=status, intermediate_schema_status="FAIL",
                       final_candidate_status="NOT_CREATED", technical_gate_status="BLOCKED", error=err)
        return {"status": "BLOCKED", **err}


async def execute(notice_ids: list[str], *, api_key: str | None = None, mock_transport=None) -> list[dict[str, Any]]:
    inputs = {r["notice_id"]: r for r in read_jsonl(INPUTS)}
    key = api_key or os.environ.get("OPENAI_API_KEY")
    if mock_transport is None and not key:
        raise RuntimeError("OPENAI_API_KEY_REQUIRED")
    client = P4Client(key or "offline-test-key", mock_transport=mock_transport)
    results = []
    try:
        for nid in notice_ids:
            ordinal = reserve(nid)
            started = time.perf_counter()
            try:
                response = await client.extract(inputs[nid])
            except Exception as exc:
                from openai import APIStatusError
                from openai import APIConnectionError
                status = "PROVIDER_SCHEMA_REJECTED" if isinstance(exc, APIStatusError) and exc.status_code == 400 else (
                    "API_CONNECTION_ERROR" if isinstance(exc, APIConnectionError) else "PROVIDER_REQUEST_ERROR")
                update_attempt(ordinal, response_status=status,
                               duration_ms=round((time.perf_counter() - started) * 1000),
                               error_class=type(exc).__name__, error_code=status,
                               technical_gate_status="BLOCKED")
                results.append({"status": "BLOCKED", "notice_id": nid, "error_class": type(exc).__name__})
                break
            result = process_response(inputs[nid], response, ordinal=ordinal, started=started)
            results.append(result)
            if result["status"] not in {"TECHNICAL_PASS", "EVALUABLE_EXTRACTION_FAILURE"}:
                break
    finally:
        await client.aclose()
    return results


def check_first() -> dict[str, Any]:
    current_fingerprint()
    manifest = read_json(MANIFEST)
    first = manifest["fingerprint"]["notice_ids"][0]
    ledger = read_json(LEDGER)
    attempt = next((a for a in ledger["attempts"] if a["notice_id"] == first), None)
    passed = bool(attempt and attempt["technical_gate_status"] == "PASS")
    return {"status": "FIRST_NOTICE_TECHNICAL_PASS" if passed else "FIRST_NOTICE_NOT_PASSED",
            "notice_id": first, "ordinal": attempt["request_ordinal"] if attempt else None,
            "http_status": attempt.get("http_status") if attempt else None,
            "provider_request_id": attempt.get("provider_request_id") if attempt else None,
            "schema": attempt.get("intermediate_schema_status") if attempt else None,
            "technical_gate": attempt.get("technical_gate_status") if attempt else None,
            "decision_eligible": False}


def evaluate() -> dict[str, Any]:
    current_fingerprint()
    manifest = read_json(MANIFEST)
    ids = manifest["fingerprint"]["notice_ids"]
    ledger = read_json(LEDGER)
    if len(manifest["evaluation_eligible_notice_ids"]) != 10 or ledger["used"] != 10:
        raise RuntimeError("P4_TEN_NOTICE_EVALUATION_ELIGIBILITY_REQUIRED")
    gold = [r for r in pilot.read_jsonl(GOLD_CONDITIONS) if r["notice_id"] in set(ids)]
    gold_logic = [r for r in pilot.read_jsonl(GOLD_LOGIC) if r["notice_id"] in set(ids)]
    metrics = {}
    prevalidation = {}
    for arm in ("without_n1", "with_n1"):
        predictions = [c for row in read_jsonl(OUT / f"predictions_{arm}.jsonl") for c in row["conditions"]]
        logic_rows = read_jsonl(OUT / f"logic_{arm}.jsonl")
        result = evaluator.evaluate_records(gold, gold_logic, predictions, logic_rows)
        metrics[arm] = result
        write_json(OUT / f"evaluation_{arm}.json", result)
        raw_rows = []
        for ordinal, notice_id in enumerate(ids, 1):
            payload = read_json(OUT / f"notice_{ordinal:02d}/provider_parsed.json")
            raw_payload = copy.deepcopy(payload)
            if arm == "with_n1":
                for i, condition in enumerate(raw_payload["conditions"]):
                    raw_payload["conditions"][i] = policy.safe.normalize(condition, "N1",
                        next(r["raw_text"] for r in read_jsonl(INPUTS) if r["notice_id"] == notice_id))[0]
            raw_rows.append({"notice_id": notice_id, "intermediate_response": raw_payload})
        raw_predictions = pilot.prevalidation_predictions(raw_rows, INPUTS)
        pre_result = evaluator.evaluate_records(gold, gold_logic, raw_predictions, logic_rows)
        prevalidation[arm] = pre_result
        write_json(OUT / f"evaluation_prevalidation_{arm}.json", pre_result)
        write_json(OUT / f"predictions_prevalidation_{arm}.json", raw_predictions)
    summary = {"run_id": RUN_ID, "source_run_id": SOURCE_RUN_ID,
        "evaluation_notice_count": 10, "gold_condition_count": 62, "gold_logic_group_count": 24,
        "gold_logic_relation_count": 71,
        "technical_success_count": len(manifest["technical_pass_notice_ids"]),
        "evaluable_extraction_failure_count": sum(r.get("response_status") == "EVALUABLE_EXTRACTION_FAILURE" for r in ledger["attempts"]),
        "conditions": {k: {"prevalidation": prevalidation[k]["common"]["micro"],
                            "postvalidation": metrics[k]["common"]["micro"]} for k in metrics},
        "macro_f1": {k: {"prevalidation": prevalidation[k]["common"]["macro_by_notice"]["f1"],
                          "postvalidation": metrics[k]["common"]["macro_by_notice"]["f1"]} for k in metrics},
        "partial_match_count": {k: {"prevalidation": prevalidation[k]["common"]["partial_count"],
                                    "postvalidation": metrics[k]["common"]["partial_count"]} for k in metrics},
        "zero_prediction_notices": {k: sum(not any(r["notice_id"] == nid and r["conditions"] for r in read_jsonl(OUT / f"predictions_{k}.jsonl")) for nid in ids) for k in metrics},
        "logic": {k: {"groups": _aggregate_logic(v["notices"], "logical_group_exact"),
                      "relations": _aggregate_logic(v["notices"], "logical_relation"),
                      "notice_ast_exact": sum(bool(n["logic"]["notice_structure_exact"]) for n in v["notices"]),
                      "notice_count": len(v["notices"]), "unsupported_extensions": "Preserved; semantic extensions not rescored",
                      "decision_eligible": False} for k, v in metrics.items()},
        "evaluation_policy": "EXISTING_STRICT_V11_AND_VERSIONED_LOGIC_ADAPTER",
        "decision_eligible": False}
    write_json(OUT / "evaluation_summary.json", summary)
    manifest.update({"status": "EVALUATED", "evaluation_ready": True, "decision_eligible": False})
    write_json(MANIFEST, manifest)
    return summary


def _aggregate_logic(notices: list[dict[str, Any]], key: str) -> dict[str, Any]:
    if key == "logical_relation":
        tp = sum(n["logic"][key]["tp"] for n in notices)
        fp = sum(n["logic"][key]["fp"] for n in notices)
        fn = sum(n["logic"][key]["fn"] for n in notices)
        return {"tp": tp, "fp": fp, "fn": fn, **evaluator.prf(tp, fp, fn)}
    correct = sum(n["logic"][key]["correct"] for n in notices)
    predicted = sum(n["logic"][key]["predicted"] for n in notices)
    gold = sum(n["logic"][key]["gold"] for n in notices)
    return {"correct": correct, "predicted": predicted, "gold": gold,
            "precision": correct / predicted if predicted else None,
            "recall": correct / gold if gold else None,
            "f1": 2 * correct / (predicted + gold) if predicted + gold else None}


def main(argv: list[str] | None = None) -> int:
    global OUT, DEV, LEDGER, MANIFEST, LOCK
    ap = argparse.ArgumentParser(description=__doc__)
    actions = ap.add_mutually_exclusive_group(required=True)
    for action in ("preflight", "prepare", "approve-budget", "check-first", "run-first", "run-remaining", "evaluate", "offline-self-test"):
        actions.add_argument("--" + action, action="store_true")
    ap.add_argument("--approval-token")
    ap.add_argument("--approval-reference")
    ap.add_argument("--authorize-api", action="store_true")
    ap.add_argument("--env-file", type=Path, default=ROOT / ".env")
    ap.add_argument("--output-dir", type=Path, default=OUT)
    args = ap.parse_args(argv)
    if args.output_dir != OUT:
        OUT = args.output_dir.resolve()
        DEV = OUT.parent
        LEDGER = OUT / "request_ledger.json"
        MANIFEST = OUT / "manifest.json"
        LOCK = DEV / f".{OUT.name}.lock"
    if args.preflight:
        result = verify_preflight(require_manifest=(OUT / "manifest.json").exists())
    elif args.prepare:
        result = prepare()
    elif args.approve_budget:
        result = approve_budget(args.approval_token or "", args.approval_reference or "")
    elif args.check_first:
        result = check_first()
    elif args.run_first or args.run_remaining:
        if not args.authorize_api:
            ap.error("live execution requires --authorize-api")
        with exclusive_lock():
            current_fingerprint()
            ledger = read_json(LEDGER)
            if not ledger.get("approved"):
                raise RuntimeError("P4_BUDGET_NOT_APPROVED")
            ids = read_json(MANIFEST)["fingerprint"]["notice_ids"]
            first = ids[0]
            if args.run_first:
                if ledger["attempts"]:
                    raise RuntimeError("P4_FIRST_REQUEST_ALREADY_RESERVED")
                selected = [first]
            else:
                if check_first()["status"] != "FIRST_NOTICE_TECHNICAL_PASS":
                    raise RuntimeError("P4_FIRST_NOTICE_GATE_BLOCKED")
                selected = ids[1:]
            from tools.extract_condition_candidates_llm import load_env_safely
            env = load_env_safely(args.env_file)
            if not env.get("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY_REQUIRED")
            results = asyncio.run(execute(selected, api_key=env["OPENAI_API_KEY"]))
            result = {"results": results, "client_created_once": True, "sequential": True,
                      "event_loops": 1, "client_closed": True}
    elif args.evaluate:
        result = evaluate()
    else:
        result = offline_self_test()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def offline_self_test() -> dict[str, Any]:
    """CLI-callable, ten-notice MockTransport integration in an isolated temp tree."""
    import tempfile
    import httpx
    from unittest.mock import patch
    from openai import AsyncOpenAI
    # Validate the exact SDK serialization/request path without touching the prepared run or ledger.
    count = {"requests": 0}
    def handler(request):
        count["requests"] += 1
        body = json.loads(request.content)
        assert body["model"] == MODEL and body["reasoning_effort"] == "low"
        assert body["max_completion_tokens"] == 8192
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True
        notice_text = json.loads(body["messages"][1]["content"])["notice_text"]
        payload = {"schema_version": policy.VERSION, "status": "NO_CONDITIONS_FOUND",
            "source_state": "NOT_STATED", "conditions": [], "unresolved_conditions": [],
            "logic_groups": [], "logic_sections": [], "exceptions": [], "unresolved_relations": [],
            "logic_completeness": "PROPOSAL_ONLY", "decision_eligible": False}
        return httpx.Response(200, json={"id": f"mock-{count['requests']}", "object": "chat.completion",
            "created": 1, "model": MODEL, "choices": [{"index": 0,
                "message": {"role": "assistant", "content": json.dumps(payload)}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25, "total_tokens": 40,
                "completion_tokens_details": {"reasoning_tokens": 5}}}, headers={"x-request-id": f"req-{count['requests']}"})
    with tempfile.TemporaryDirectory(prefix="p4-offline-") as tmp:
        temp_out = Path(tmp) / RUN_ID
        global OUT, DEV, LEDGER, MANIFEST, LOCK
        old = OUT, DEV, LEDGER, MANIFEST, LOCK
        OUT = temp_out; DEV = temp_out.parent; LEDGER = OUT / "request_ledger.json"; MANIFEST = OUT / "manifest.json"; LOCK = DEV / ".test.lock"
        try:
            # Full prepare -> explicit approval -> mocked execution -> strict evaluation, all in temp storage.
            p12_tree_before = {p.relative_to(P12).as_posix(): sha(p) for p in P12.rglob("*") if p.is_file()}
            prepared = prepare()
            check = read_json(OUT / "preflight_report.json")
            if read_json(LEDGER)["approved"]:
                raise AssertionError("PREPARE_MUST_NOT_ACTIVATE_BUDGET")
            try:
                approve_budget("", "")
            except RuntimeError as exc:
                if str(exc) != "EXPLICIT_P4_BUDGET_APPROVAL_REQUIRED":
                    raise
            else:
                raise AssertionError("BUDGET_APPROVAL_MUST_REQUIRE_EXPLICIT_TOKEN_AND_REFERENCE")
            if read_json(LEDGER)["approved"]:
                raise AssertionError("INVALID_APPROVAL_CHANGED_BUDGET")
            approve_budget(APPROVAL_TOKEN, "offline-self-test-only")
            fp = read_json(MANIFEST)["fingerprint"]
            ids = fp["notice_ids"]
            transport = httpx.MockTransport(handler)
            with exclusive_lock():
                first_results = asyncio.run(execute(ids[:1], api_key="offline-key", mock_transport=transport))
            first_gate = check_first()
            if first_gate["status"] != "FIRST_NOTICE_TECHNICAL_PASS":
                raise AssertionError({"first_results": first_results, "first_gate": first_gate})
            with exclusive_lock():
                remaining_results = asyncio.run(execute(ids[1:], api_key="offline-key", mock_transport=httpx.MockTransport(handler)))
            results = first_results + remaining_results
            per_notice = []
            # The driver loop normally stops at a failed technical Gate; mocked outputs pass and use one client/loop.
            if any(r.get("status") != "TECHNICAL_PASS" for r in results):
                raise AssertionError({"results": results, "ledger": read_json(LEDGER),
                                      "manifest": read_json(MANIFEST)})
            eval_result = evaluate()
            ledger = read_json(LEDGER)
            saved = read_json(MANIFEST)
            p12_tree_after = {p.relative_to(P12).as_posix(): sha(p) for p in P12.rglob("*") if p.is_file()}
            assert len(results) == 10 and count["requests"] == 10
            assert ledger["used"] == 10 and ledger["limit"] == 10 and ledger["remaining"] == 0
            assert len(ledger["attempts"]) == 10 and all(x["technical_gate_status"] == "PASS" for x in ledger["attempts"])
            assert saved["api_call_count"] == ledger["api_call_count"] == 10
            assert len(read_jsonl(OUT / "responses.jsonl")) == 10
            assert len(read_jsonl(OUT / "predictions_without_n1.jsonl")) == 10
            assert len(read_jsonl(OUT / "predictions_with_n1.jsonl")) == 10
            assert p12_tree_before == p12_tree_after
            return {"status": "PASS", "mode": "MOCKTRANSPORT_TEMP_DIRECTORY_ONLY", "requests": count["requests"],
                "first_gate_passed_before_remaining_9": True, "one_loop_and_client_per_batch": True,
                "serialized_structured_schema": True,
                "raw_response_saved_before_validation": True, "n1_and_non_n1_replay": True,
                "strict_evaluation_path": bool(eval_result), "ledger_manifest_consistent": True,
                "budget_requires_explicit_approval": True, "all_existing_p12_artifacts_untouched": True,
                "actual_api_calls": 0,
                "preflight": check["status"], "test_evaluation_is_not_a_performance_result": True}
        finally:
            OUT, DEV, LEDGER, MANIFEST, LOCK = old


if __name__ == "__main__":
    raise SystemExit(main())
