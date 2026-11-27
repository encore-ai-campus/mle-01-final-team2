"""Offline replay of a saved LLM response through condition attribute normalization."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import extract_condition_candidates_llm as llm

R2 = ROOT / "data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_r2"
DEFAULT_INPUT = R2 / "lead_retry/raw_llm_responses.jsonl"
DEFAULT_OUTPUT = ROOT / "data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_r2_attribute_replay"
BASELINE_EXTRACTOR_SHA256_BEFORE_P3 = "7d04ff05e165dc88e4ccd1994eb9efbf7c752c3085aa68a701acace200ec995a"
EXTRACTOR_SHA256_BEFORE_NORMALIZATION_V2 = "0ba4640d939994207a2e39588a282ee35a9beba78ab8ca0333ea46b98ce65141"
PRIOR_ARTIFACTS = (
    "manifest.json", "request_ledger.json", "lead_retry_gate.json",
    "lead_retry/raw_llm_responses.jsonl", "lead_retry/intermediate_responses.jsonl",
    "lead_retry/predictions_before_validation.jsonl", "lead_retry/validation_details.jsonl",
    "lead_retry/rejected_candidates.jsonl", "lead_retry/review_queue.jsonl",
    "lead_retry/logic_proposals.jsonl", "lead_retry/run_report.json",
)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl_write(path: Path, rows: list[dict[str, Any]]) -> None:
    llm._write_jsonl(path, rows)


def _response_from_file(path: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    rows = llm._read_jsonl(path)
    if len(rows) != 1:
        raise ValueError(f"Expected one saved response row, found {len(rows)}")
    source = rows[0]
    if "intermediate_response" in source:
        response = copy.deepcopy(source["intermediate_response"])
        response_sha = hashlib.sha256(json.dumps(response, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode("utf-8")).hexdigest()
        return response, response_sha, source
    attempts = source.get("response_attempts")
    if not isinstance(attempts, list) or not attempts:
        raise ValueError("Raw response row has no response_attempts")
    parse_errors = []
    for text in reversed(attempts):
        if not isinstance(text, str):
            continue
        try:
            response = json.loads(text)
            if isinstance(response, dict):
                return response, hashlib.sha256(text.encode("utf-8")).hexdigest(), source
        except json.JSONDecodeError as exc:
            parse_errors.append(str(exc))
    raise ValueError(f"No JSON object found in response attempts: {parse_errors[-1:]}")


def _evidence_status(row: dict[str, Any], proposal: dict[str, Any]) -> str:
    quotes = proposal.get("evidence_quotes")
    if not isinstance(quotes, list) or not quotes:
        return "MISSING_QUOTES"
    for quote in quotes:
        offsets = llm._all_offsets(row["raw_text"], quote)
        if not offsets:
            return "NOT_IN_SOURCE"
        if len(offsets) != 1:
            return "LOCATION_AMBIGUOUS"
    return "PASS"


def replay(input_path: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, Any]:
    input_path, output_dir = Path(input_path), Path(output_dir)
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"Refusing to overwrite replay output: {output_dir}")

    r2_manifest_path = R2 / "manifest.json"
    ledger_path = R2 / "request_ledger.json"
    r2_manifest_before = digest(r2_manifest_path)
    ledger_before = digest(ledger_path)
    prior_hashes = {name: digest(R2 / name) for name in PRIOR_ARTIFACTS}
    input_sha = digest(input_path)
    source_inputs_sha = digest(llm.INPUTS)
    sample_sha = digest(llm.SAMPLES)
    extractor_after_sha = digest(ROOT / "tools/extract_condition_candidates_llm.py")
    replay_tool_sha = digest(Path(__file__))

    response, response_sha, response_row = _response_from_file(input_path)
    notice_id = response_row.get("notice_id")
    if not notice_id:
        raise ValueError("Saved response has no notice_id")
    input_rows = {row["notice_id"]: row for row in llm._read_jsonl(llm.INPUTS)}
    source_row = input_rows.get(notice_id)
    if source_row is None:
        raise ValueError(f"No frozen extraction input for {notice_id}")
    intermediate_errors = sorted(llm.INTERMEDIATE_VALIDATOR.iter_errors(response),
                                 key=lambda error: list(map(str, error.path)))
    if intermediate_errors:
        raise ValueError("Saved response failed intermediate schema validation: " +
                         "; ".join(error.message for error in intermediate_errors))
    original_response_sha = hashlib.sha256(json.dumps(response, ensure_ascii=False, sort_keys=True,
                                                       separators=(",", ":")).encode("utf-8")).hexdigest()
    artifacts = llm._response_to_artifacts(source_row, response)
    if original_response_sha != hashlib.sha256(json.dumps(response, ensure_ascii=False, sort_keys=True,
                                                           separators=(",", ":")).encode("utf-8")).hexdigest():
        raise RuntimeError("Replay mutated the source response object")

    index_to_id = {int(index): candidate_id
                   for index, candidate_id in artifacts["logic_proposal"]["index_to_condition_id"].items()}
    candidate_by_id = {candidate["condition_id"]: candidate for candidate in artifacts["conditions"]}
    candidate_schema_errors = llm.validate_artifacts(
        artifacts["conditions"], [artifacts["notice_set"]] if artifacts["notice_set"] else [])
    failed_notice_schema = any(error["kind"] == "notice_set" for error in candidate_schema_errors)
    failed_candidate_schema = bool(candidate_schema_errors)

    before_rows, after_rows, validation_rows, rejected_rows = [], [], [], []
    normalization_rows = []
    for index, original in enumerate(response["conditions"]):
        normalized = artifacts["normalized_response"]["conditions"][index]
        normalization = artifacts["attribute_normalization"][index]
        mapping_reason = artifacts["attribute_normalization_reasons"][index]
        candidate_id = index_to_id.get(index)
        candidate = candidate_by_id.get(candidate_id) if candidate_id else None
        shape_issue = None
        evidence_status = _evidence_status(source_row, original)
        if mapping_reason is None:
            shape_issue = llm._check_value_shape(normalized)
        elif mapping_reason == "ATTRIBUTE_SEMANTIC_AMBIGUITY":
            shape_issue = "BLOCKED_BY_ATTRIBUTE_SEMANTIC_AMBIGUITY"
        else:
            shape_issue = mapping_reason
        temporal_preserved = (
            original.get("reference_date_type") == normalized.get("reference_date_type")
            and original.get("reference_date") == normalized.get("reference_date")
            and original.get("temporal_constraint") == normalized.get("temporal_constraint")
        )
        is_temporal = bool(original.get("reference_date") or original.get("temporal_constraint"))
        final_schema_status = ("PASS" if candidate and not failed_candidate_schema else
                               "FAIL" if candidate and failed_candidate_schema else
                               "NOT_APPLICABLE_HELD_BEFORE_CANDIDATE")
        if mapping_reason == "ATTRIBUTE_SEMANTIC_AMBIGUITY":
            final_status, final_reason = "HELD_FOR_REVIEW", mapping_reason
        elif candidate and not failed_candidate_schema:
            final_status, final_reason = "ACCEPTED_UNREVIEWED", None
        elif candidate and failed_candidate_schema:
            final_status, final_reason = "REJECTED", "V11_SCHEMA_VALIDATION_ERROR"
        elif mapping_reason:
            final_status, final_reason = "REJECTED", mapping_reason
        else:
            final_status, final_reason = "REJECTED", shape_issue or "EVIDENCE_OR_SEMANTIC_VALIDATION_FAILED"

        before_rows.append({"notice_id": notice_id, "proposal_index": index,
                            "proposal": copy.deepcopy(original), "validation_status": "PENDING"})
        normalization_rows.append({"notice_id": notice_id, **normalization})
        detail = {
            "notice_id": notice_id, "proposal_index": index,
            "original_field": original.get("field"), "normalized_field": normalization.get("normalized_field"),
            "original_category_id": original.get("category_id"),
            "mapping_rule_id": normalization.get("mapping_rule_id"),
            "mapping_rule_version": normalization.get("mapping_rule_version"),
            "mapping_status": normalization.get("mapping_status"),
            "attribute_catalog_validation": "PASS" if mapping_reason is None else "HELD" if mapping_reason == "ATTRIBUTE_SEMANTIC_AMBIGUITY" else "FAIL",
            "condition_type_validation": "PASS" if original.get("condition_type") in llm.CONDITION_TYPES else "FAIL",
            "value_operator_unit_validation": "PASS" if shape_issue is None else "BLOCKED" if str(shape_issue).startswith("BLOCKED_") else "FAIL",
            "value_operator_unit_reason": shape_issue,
            "evidence_quote_validation": evidence_status,
            "date_temporal_validation": "PASS" if temporal_preserved else "FAIL",
            "date_temporal_present": is_temporal,
            "date_temporal_preserved": temporal_preserved,
            "v11_schema_validation": final_schema_status,
            "candidate_id": candidate_id,
            "final_status": final_status, "reason": final_reason,
            "review_status": "NEEDS_REVIEW" if final_status == "HELD_FOR_REVIEW" else "UNREVIEWED",
            "decision_eligible": False,
        }
        validation_rows.append(detail)
        if candidate and final_status == "ACCEPTED_UNREVIEWED":
            after_rows.append({"notice_id": notice_id, "proposal_index": index, "candidate": candidate,
                               "review_status": "UNREVIEWED", "decision_eligible": False})
        elif final_status == "REJECTED":
            rejected_rows.append({**detail, "proposal": copy.deepcopy(original)})

    held = artifacts["review_queue"]["held_items"] if artifacts["review_queue"] else []
    if failed_notice_schema:
        held = [*held, {"notice_id": notice_id, "status": "V11_NOTICE_SET_SCHEMA_VALIDATION_ERROR",
                        "review_status": "NEEDS_REVIEW", "decision_eligible": False}]
    logic_rows = [artifacts["logic_proposal"]]
    review_queue = ([{"notice_id": notice_id, "source_system": source_row["source_system"],
                      "status": "CANDIDATE_REVIEW_REQUIRED", "held_count": len(held), "held_items": held,
                      "source_completeness": source_row.get("completeness_status", "UNKNOWN"),
                      "review_status": "NEEDS_REVIEW", "decision_eligible": False}] if held else [])

    output_dir.mkdir(parents=True, exist_ok=True)
    files = {
        "attribute_normalization.jsonl": normalization_rows,
        "predictions_before_validation.jsonl": before_rows,
        "predictions_after_validation.jsonl": after_rows,
        "validation_details.jsonl": validation_rows,
        "rejected_candidates.jsonl": rejected_rows,
        "review_queue.jsonl": review_queue,
        "logic_proposals.jsonl": logic_rows,
    }
    for name, rows in files.items():
        jsonl_write(output_dir / name, rows)

    r2_manifest_after = digest(r2_manifest_path)
    ledger_after = digest(ledger_path)
    original_prompt_sha = llm._read_jsonl(R2 / "lead_retry/raw_llm_responses.jsonl")[0].get("prompt_sha256")
    run_report_path = R2 / "lead_retry/run_report.json"
    original_prompt_sha = original_prompt_sha or json.loads(run_report_path.read_text(encoding="utf-8")).get("prompt_sha256")
    artifact_hashes = {name: digest(output_dir / name) for name in files}
    accepted_count = sum(row["final_status"] == "ACCEPTED_UNREVIEWED" for row in validation_rows)
    held_count = sum(row["final_status"] == "HELD_FOR_REVIEW" for row in validation_rows)
    rejected_count = sum(row["final_status"] == "REJECTED" for row in validation_rows)
    report = {
        "status": "OFFLINE_REPLAY_COMPLETE", "notice_id": notice_id,
        "proposal_count": len(validation_rows), "accepted_unreviewed_count": accepted_count,
        "held_for_review_count": held_count, "rejected_count": rejected_count,
        "v11_schema_error_count": len(candidate_schema_errors),
        "incomplete_logic": artifacts["logic_proposal"]["logical_completeness"] == "INCOMPLETE",
        "decision_eligible_true_count": 0, "api_call_count": 0,
        "goldset_read": False, "evaluation_data_read": False,
        "source_response_sha256": response_sha, "intermediate_response_sha256": original_response_sha,
        "output_hashes": artifact_hashes,
    }
    (output_dir / "replay_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "replay_id": output_dir.name, "source_run_id": "llm_pilot_2_5c3_r2",
        "source_notice_id": notice_id, "source_file": str(input_path.relative_to(ROOT)) if input_path.is_relative_to(ROOT) else input_path.as_posix(),
        "source_response_sha256": response_sha,
        "prior_r2_manifest_sha256": r2_manifest_before,
        "prior_r2_manifest_sha256_after": r2_manifest_after,
        "prior_failed_artifact_sha256": prior_hashes,
        "normalization_rules_version": llm.ATTRIBUTE_NORMALIZATION_RULES_VERSION,
        "normalization_rules_sha256": llm.ATTRIBUTE_NORMALIZATION_RULES_SHA256,
        "extractor_sha256_before_p3": BASELINE_EXTRACTOR_SHA256_BEFORE_P3,
        "extractor_sha256_after_p3": extractor_after_sha,
        "extractor_sha256_before_normalization_v2": EXTRACTOR_SHA256_BEFORE_NORMALIZATION_V2,
        "extractor_sha256_after_normalization_v2": extractor_after_sha,
        "source_r2_fingerprint_extractor_sha256": json.loads(r2_manifest_path.read_text(encoding="utf-8"))["fingerprint"]["extractor_sha256"],
        "replay_tool_sha256": replay_tool_sha,
        "prompt_sha256": original_prompt_sha,
        "fixed_inputs": {"extraction_inputs_sha256": source_inputs_sha, "representative_samples_sha256": sample_sha},
        "api_call_count": 0,
        "request_ledger_sha256_before": ledger_before, "request_ledger_sha256_after": ledger_after,
        "request_ledger_modified": ledger_before != ledger_after,
        "output_hashes": {**artifact_hashes, "replay_report.json": digest(output_dir / "replay_report.json")},
        "review_status": "UNREVIEWED", "decision_eligible": False,
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if r2_manifest_before != r2_manifest_after or ledger_before != ledger_after:
        raise RuntimeError("Replay unexpectedly changed R2 manifest or request ledger")
    if digest(input_path) != input_sha:
        raise RuntimeError("Replay unexpectedly changed the source response")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Saved raw_llm_responses.jsonl or intermediate_responses.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = replay(args.input, args.output_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
