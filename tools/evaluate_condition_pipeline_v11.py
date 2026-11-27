"""Version 1.1 semantic evaluation. Importable for synthetic cases; CLI defaults to preflight.

Real prediction scoring requires an explicit --execute flag and frozen v1 baseline files.
The v1.0 evaluator is intentionally left unchanged.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.evaluate_condition_pipeline import (
    _canonical, _maximum_matching, compare_logic, evidence, evidence_exact,
    evidence_overlaps, normalize_value, prf, read_jsonl,
)

GOLD = ROOT / "data/goldsets/conditions/v1.1/20261126/final30/development"
BASELINE = ROOT / "data/goldsets/conditions/v1/20261126_balanced/baseline_manifest.json"
DEVELOPMENT = ROOT / "data/goldsets/conditions/v1/20261126_balanced/development/condition_review.jsonl"
EVALUATION = ROOT / "data/goldsets/conditions/v1/20261126_balanced/evaluation/condition_review.jsonl"
POLICY_VERSION = "1.1.0"
DEFAULT_CONFIG = ROOT / "configs/condition_evaluation_v11_development.json"

# These are semantically identical across the two schemas. In particular,
# BUSINESS_TYPE and APPLICANT_TYPE are distinct and are never aliased.
FIELD_ALIASES: dict[str, str] = {}
COMMON_FIELDS = ("condition_type", "category", "field", "operator", "value", "unit")
EXTENDED_FIELDS = ("applicability_scope", "evaluation_phase", "fulfillment_phase",
                   "requirement_kind", "reference_date_type", "reference_date",
                   "temporal_constraint.anchor_event", "temporal_constraint.fixed_reference_date",
                   "temporal_constraint.offset_value", "temporal_constraint.offset_unit",
                   "temporal_constraint.operator", "temporal_constraint.inclusive",
                   "evidence_references", "external_reference")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_rows(path: Path) -> dict[str, dict[str, Any]]:
    rows = read_jsonl(path)
    result = {r["notice_id"]: r for r in rows}
    if len(rows) != len(result):
        raise ValueError(f"duplicate notice ID in {path}")
    return result


def preflight(gold_dir: Path = GOLD, conditions_path: Path | None = None,
              logic_path: Path | None = None) -> dict[str, Any]:
    """Read only. Never opens independent evaluation text or computes scores."""
    errors: list[str] = []
    manifest_path = gold_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (manifest.get("status"), manifest.get("schema_version"), manifest.get("dataset_split")) != ("FINALIZED", "1.1", "DEVELOPMENT"):
        errors.append("GOLDSET_NOT_FINALIZED_V11_DEVELOPMENT")
    outputs = manifest.get("outputs", {})
    for name in ("reviewed_condition_gold.jsonl", "reviewed_logic_gold.jsonl"):
        path = gold_dir / name
        if not path.exists() or outputs.get(name, {}).get("sha256") != digest(path):
            errors.append(f"OUTPUT_HASH_MISMATCH:{name}")
    for entry in manifest.get("component_inputs", {}).values():
        path = ROOT / entry["path"]
        if not path.exists() or digest(path) != entry["sha256"]:
            errors.append(f"COMPONENT_HASH_MISMATCH:{path}")
    for key in ("normalized_snapshot", "condition_input_v1"):
        entry = manifest.get(key, {})
        path = ROOT / entry.get("path", "__missing__")
        if not path.exists() or digest(path) != entry.get("sha256"):
            errors.append(f"INPUT_HASH_MISMATCH:{key}")
    frozen = manifest.get("extractor_logic_baseline", {})
    for entry in frozen.get("files", {}).values():
        path = ROOT / entry["path"]
        if not path.exists() or digest(path) != entry["sha256"]:
            errors.append(f"BASELINE_HASH_MISMATCH:{path}")
    cond = _unique_rows(gold_dir / "reviewed_condition_gold.jsonl")
    logic = _unique_rows(gold_dir / "reviewed_logic_gold.jsonl")
    dev_ids = set(_unique_rows(DEVELOPMENT))
    eval_ids = set(_unique_rows(EVALUATION))  # IDs only; no semantic use.
    if set(cond) != set(logic) or set(cond) != dev_ids or set(cond) & eval_ids:
        errors.append("GOLD_NOTICE_SET_MISMATCH")
    count = sum(len(r["gold_conditions"]) + len(r["missed_condition_candidates"]) for r in cond.values())
    if (len(cond), count) != (30, 116) or (manifest.get("notice_count"), manifest.get("condition_count")) != (30, 116):
        errors.append("GOLD_COUNT_MISMATCH")
    if any(r.get("review_status") != "VERIFIED" or r.get("adjudication_status") != "REVIEWED_COMPLETE" for r in [*cond.values(), *logic.values()]):
        errors.append("UNAPPROVED_GOLD")
    if any(c.get("review_status") != "VERIFIED" for r in cond.values() for c in r.get("gold_conditions", []) + r.get("missed_condition_candidates", [])):
        errors.append("UNAPPROVED_GOLD_CONDITION")
    for supplied, key in ((conditions_path, "extracted_conditions"), (logic_path, "notice_condition_sets")):
        if supplied is None:
            continue
        expected = frozen.get("files", {}).get(key, {})
        if not supplied.exists() or digest(supplied) != expected.get("sha256"):
            errors.append(f"PREDICTION_VERSION_OR_HASH_MISMATCH:{key}")
        else:
            rows = read_jsonl(supplied)
            if any(r.get("schema_version") != "1.0" for r in rows):
                errors.append(f"PREDICTION_SCHEMA_MISMATCH:{key}")
            if {r.get("notice_id") for r in rows} & eval_ids:
                errors.append(f"EVALUATION_SPLIT_MIXED:{key}")
            development_80 = {r["notice_id"] for r in read_jsonl(ROOT / "data/condition_inputs/v1/20261125/representative_samples.jsonl") if r["split"] == "DEVELOPMENT"}
            if not {r.get("notice_id") for r in rows} <= development_80:
                errors.append(f"PREDICTION_SPLIT_MISMATCH:{key}")
    return {"status": "PASS" if not errors else "BLOCKED", "errors": errors,
            "goldset_version": manifest.get("goldset_version"), "policy_version": POLICY_VERSION,
            "notice_count": len(cond), "condition_count": count,
            "scores_computed": False}


def _common_value(record: dict[str, Any], field: str) -> Any:
    value = record.get("category_id") if field == "category" and "category_id" in record else record.get(field)
    if field == "field":
        value = FIELD_ALIASES.get(value, value)
    if field == "value":
        return normalize_value(value, operator=record.get("operator"))
    return value


def common_differences(gold: dict[str, Any], pred: dict[str, Any]) -> list[str]:
    return [f for f in COMMON_FIELDS if _common_value(gold, f) != _common_value(pred, f)]


def _identity(record: dict[str, Any]) -> str:
    return record.get("gold_condition_id") or record.get("condition_id") or ""


def match_notice(gold: list[dict[str, Any]], predicted: list[dict[str, Any]]) -> dict[str, Any]:
    """Stable maximum-cardinality matching; partial pairs never count as strict TPs."""
    gs = sorted(gold, key=_identity)
    ps = sorted(predicted, key=_identity)
    exact = {i: [j for j, p in enumerate(ps) if not common_differences(g, p) and evidence_exact(g, p)] for i, g in enumerate(gs)}
    full = _maximum_matching(exact)
    used_g, used_p = {i for i, _ in full}, {j for _, j in full}
    partial_edges: dict[int, list[int]] = {}
    for i, g in enumerate(gs):
        if i in used_g:
            continue
        for j, p in enumerate(ps):
            if j in used_p or g.get("field") != p.get("field"):
                continue
            if evidence_overlaps(g, p) or evidence(g, gold=True)[3] == evidence(p, gold=False)[3]:
                partial_edges.setdefault(i, []).append(j)
    partial = _maximum_matching(partial_edges)
    pairs = []
    for status, matched in (("EXACT_MATCH", full), ("PARTIAL_MATCH", partial)):
        for i, j in matched:
            differences = common_differences(gs[i], ps[j])
            if not evidence_exact(gs[i], ps[j]):
                differences.append("evidence")
            pairs.append({"status": status, "gold_id": _identity(gs[i]), "prediction_id": _identity(ps[j]),
                          "gold": gs[i], "prediction": ps[j], "differences": differences})
    tp = len(full)
    return {"pairs": pairs, "unmatched_gold": [_identity(g) for i, g in enumerate(gs) if i not in used_g],
            "unmatched_predictions": [_identity(p) for j, p in enumerate(ps) if j not in used_p],
            "metrics": prf(tp, len(ps) - tp, len(gs) - tp),
            "partial_count": len(partial), "id_map": {_identity(pair["prediction"]): pair["gold_id"] for pair in pairs}}


def _field_value(record: dict[str, Any], name: str) -> Any:
    if name == "reference_date_type" and isinstance(record.get("reference_date"), dict):
        return record["reference_date"].get("date_type", _MISSING)
    if name == "reference_date" and isinstance(record.get("reference_date"), dict):
        return record["reference_date"].get("value", _MISSING)
    current: Any = record
    for part in name.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


_MISSING = object()


def compare_extended(gold: list[dict[str, Any]], pairs: list[dict[str, Any]]) -> dict[str, Any]:
    aligned = {p["gold_id"]: p["prediction"] for p in pairs}
    per_field: dict[str, Counter] = {f: Counter() for f in EXTENDED_FIELDS}
    for g in gold:
        for field in EXTENDED_FIELDS:
            target = per_field[field]
            gv = _field_value(g, field)
            if gv is _MISSING or gv is None or gv == "UNKNOWN":
                target["unknown"] += 1
                continue
            target["target"] += 1
            pred = aligned.get(_identity(g))
            if pred is None:
                target["no_aligned_prediction"] += 1
                continue
            pv = _field_value(pred, field)
            if pv is _MISSING:
                target["unsupported"] += 1
            elif pv is None or pv == "UNKNOWN":
                target["unknown_prediction"] += 1
            else:
                target["evaluable"] += 1
                if normalize_value(gv) == normalize_value(pv):
                    target["correct"] += 1
    keys = ("target", "evaluable", "correct", "unsupported", "unknown",
            "unknown_prediction", "no_aligned_prediction")
    return {f: {key: v[key] for key in keys} for f, v in per_field.items()}


def evidence_diagnostics(pair: dict[str, Any]) -> str:
    g, p = pair["gold"], pair["prediction"]
    if evidence_exact(g, p):
        return "EXACT_SPAN"
    ge, pe = evidence(g, gold=True), evidence(p, gold=False)
    if ge[3] == pe[3] and ge[1:3] != pe[1:3]:
        return "WRONG_BRANCH_OR_LOCATION"
    if evidence_overlaps(g, p):
        return "OVERLAPPING_SPAN"
    return "DIFFERENT_EVIDENCE"


def _roots(pred: dict[str, Any]) -> list[dict[str, Any]]:
    if "gold_logic_sections" in pred:
        return [s["root"] for s in pred["gold_logic_sections"]]
    if "logical_roots" in pred:
        return pred["logical_roots"]
    return [root for block in pred.get("condition_sets", {}).values() for root in block.get("logical_roots", [])]


def compare_notice_logic(gold: dict[str, Any], pred: dict[str, Any], id_map: dict[str, str]) -> dict[str, Any]:
    roots = _roots(pred)
    base = compare_logic(gold["gold_logic_roots"], roots, id_map,
                         gold_exceptions=gold.get("gold_exceptions", []),
                         gold_benefits=gold.get("gold_benefits", []),
                         gold_unresolved_relations=gold.get("unresolved_relations", []),
                         prediction_record=pred, generation_possible=bool(pred))
    gold_sections = gold.get("gold_logic_sections", [])
    pred_sections = pred.get("gold_logic_sections") or pred.get("logic_sections")
    if pred_sections is None:
        base["section_semantics"] = {"status": "UNSUPPORTED_V1_0", "target": len(gold_sections)}
    else:
        g = sorted((s["condition_type"], s["evaluation_phase"], s["fulfillment_phase"], _canonical(s["root"], {})) for s in gold_sections)
        p = sorted((s["condition_type"], s["evaluation_phase"], s["fulfillment_phase"], _canonical(s["root"], id_map)) for s in pred_sections)
        base["section_semantics"] = {"status": "EVALUATED", "exact": g == p, "target": len(gold_sections)}
    def exception_signature(row: dict[str, Any], predicted: bool) -> tuple[Any, ...]:
        targets = row.get("applies_to_gold_ids", row.get("applies_to_condition_ids", []))
        return (tuple(sorted(id_map.get(x, x) if predicted else x for x in targets)), row.get("precondition"),
                row.get("effect"), row.get("effect_target"), normalize_value(row.get("replacement")),
                row.get("effect_confirmed"), row.get("application_mode"))
    base["exception_effects"] = {"target": len(gold.get("gold_exceptions", [])),
                                 "status": "EVALUATED" if "gold_exceptions" in pred else "UNSUPPORTED_V1_0",
                                 "exact": sorted((exception_signature(x, False) for x in gold.get("gold_exceptions", [])), key=repr) ==
                                          sorted((exception_signature(x, True) for x in pred.get("gold_exceptions", [])), key=repr)
                                          if "gold_exceptions" in pred else None}
    gold_relations = {tuple(sorted(x["gold_condition_ids"])) for x in gold.get("unresolved_relations", [])}
    if "unresolved_relations" in pred:
        pred_relations = {tuple(sorted(id_map.get(cid, cid) for cid in x.get("gold_condition_ids", x.get("condition_ids", [])))) for x in pred["unresolved_relations"]}
        base["unresolved_relation_semantics"] = {"status": "EVALUATED", "target": len(gold_relations),
                                                  "exact": gold_relations == pred_relations}
    else:
        base["unresolved_relation_semantics"] = {"status": "UNSUPPORTED_V1_0", "target": len(gold_relations)}
    return base


def safety_diagnostics(gold: dict[str, Any], prediction: dict[str, Any], match: dict[str, Any],
                       gold_logic: dict[str, Any] | None = None, pred_logic: dict[str, Any] | None = None) -> list[str]:
    issues: set[str] = set()
    if gold.get("whole_notice_conditions_complete") is False and (
        prediction.get("whole_notice_conditions_complete") is True or prediction.get("completeness_status") == "COMPLETE"
    ):
        issues.add("UNSUPPORTED_COMPLETENESS_CLAIM")
    if gold.get("source_condition_status") == "NOT_COLLECTED" and prediction.get("source_condition_status") == "CONFIRMED_NONE":
        issues.add("MISSING_AS_NONE")
    for pair in match["pairs"]:
        g, p = pair["gold"], pair["prediction"]
        if g.get("condition_type") == "EXCLUSION" and p.get("condition_type") != "EXCLUSION":
            issues.add("EXCLUSION_DIRECTION_OR_TYPE_CHANGED")
        if g.get("condition_type") == "PREFERENCE" and p.get("condition_type") == "ELIGIBILITY":
            issues.add("PREFERENCE_AS_REQUIRED")
        if g.get("requirement_kind") == "FULFILLMENT_OBLIGATION" and p.get("evaluation_phase") == "APPLICATION":
            issues.add("POST_SELECTION_AS_APPLICATION")
        if g.get("decision_possible") is False and p.get("decision_eligible") is True:
            issues.add("DECISION_BLOCK_BYPASSED")
        if (g.get("operator") is None or g.get("value_type") == "UNKNOWN") and p.get("decision_eligible") is True:
            issues.add("UNKNOWN_AS_DEFINITE")
        if g.get("field") != p.get("field") and g.get("field") == "APPLICANT_TYPE":
            issues.add("APPLICANT_TARGET_CONFUSED")
        if g.get("source_completeness") == "UNKNOWN" and p.get("completeness_status") == "COMPLETE":
            issues.add("UNKNOWN_AS_DEFINITE")
    if gold_logic and pred_logic:
        unresolved = gold_logic.get("unresolved_relations", [])
        if unresolved and pred_logic.get("logic_relation_status") == "RESOLVED":
            issues.add("UNRESOLVED_AS_DEFINITE")
        pred_roots = _roots(pred_logic)
        def leaves(node: dict[str, Any]) -> set[str]:
            if node["node_type"] == "CONDITION_REF":
                return {match["id_map"].get(node["condition_id"], node["condition_id"])}
            return set().union(*(leaves(ch) for ch in node["children"]))
        def definite_groups(node: dict[str, Any]) -> list[set[str]]:
            if node["node_type"] != "LOGICAL_GROUP":
                return []
            here = [leaves(node)] if node["operator"] in {"AND", "OR"} else []
            return here + [group for ch in node["children"] for group in definite_groups(ch)]
        for relation in unresolved:
            target = set(relation.get("gold_condition_ids", []))
            if len(target) > 1 and any(target == group for root in pred_roots for group in definite_groups(root)):
                issues.add("UNRESOLVED_AS_DEFINITE")
        gold_exception_targets = [set(e.get("applies_to_gold_ids", [])) for e in gold_logic.get("gold_exceptions", [])]
        for ex in pred_logic.get("gold_exceptions", []):
            targets = set(match["id_map"].get(x, x) for x in ex.get("applies_to_gold_ids", ex.get("applies_to_condition_ids", [])))
            if any(gold_targets < targets for gold_targets in gold_exception_targets):
                issues.add("EXCEPTION_SCOPE_EXPANDED")
        if any(e.get("effect") == "UNKNOWN" and e.get("effect_confirmed") for e in gold_logic.get("gold_exceptions", [])) and pred_logic.get("decision_eligible") is True:
            issues.add("UNSUPPORTED_EXCEPTION_EXECUTED")
    return sorted(issues)


def evaluate_records(gold_rows: list[dict[str, Any]], logic_rows: list[dict[str, Any]],
                     prediction_rows: list[dict[str, Any]], logic_prediction_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Pure evaluator used by synthetic tests and, later, explicit production execution."""
    notice_ids = {r["notice_id"] for r in gold_rows}
    prediction_rows = [r for r in prediction_rows if r["notice_id"] in notice_ids]
    by_pred: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for p in prediction_rows:
        by_pred[p["notice_id"]].append(p)
    by_logic_pred = {r["notice_id"]: r for r in logic_prediction_rows}
    by_logic_gold = {r["notice_id"]: r for r in logic_rows}
    details = []
    for row in sorted(gold_rows, key=lambda x: x["notice_id"]):
        nid = row["notice_id"]
        gs = row.get("gold_conditions", []) + row.get("missed_condition_candidates", [])
        pred = by_pred.get(nid, [])
        matched = match_notice(gs, pred)
        logic_result = compare_notice_logic(by_logic_gold[nid], by_logic_pred.get(nid, {}), matched["id_map"])
        details.append({"notice_id": nid, "source_system": row["source_system"], "common": matched["metrics"],
                        "partial_count": matched["partial_count"], "pairs": [{k: v for k, v in pair.items() if k not in {"gold", "prediction"}} | {"evidence_status": evidence_diagnostics(pair), "evidence_semantic_status": "NEEDS_HUMAN_REVIEW"} for pair in matched["pairs"]],
                        "false_negative_ids": matched["unmatched_gold"], "false_positive_ids": matched["unmatched_predictions"],
                        "extended": compare_extended(gs, matched["pairs"]), "logic": logic_result,
                        "safety_errors": safety_diagnostics(row, {"conditions": pred, **by_logic_pred.get(nid, {})}, matched,
                                                             by_logic_gold[nid], by_logic_pred.get(nid, {}))})
    micro = prf(*(sum(d["common"][key] for d in details) for key in ("tp", "fp", "fn")))
    macro = {key: sum(v for d in details if (v := d["common"][key]) is not None) / max(1, sum(d["common"][key] is not None for d in details)) if any(d["common"][key] is not None for d in details) else None for key in ("precision", "recall", "f1")}
    by_source = {}
    for source in sorted({d["source_system"] for d in details}):
        group = [d for d in details if d["source_system"] == source]
        by_source[source] = prf(*(sum(d["common"][k] for d in group) for k in ("tp", "fp", "fn")))
    ext = {field: dict(sum((Counter(d["extended"].get(field, {})) for d in details), Counter())) for field in EXTENDED_FIELDS}
    def dimension(field: str) -> dict[str, Any]:
        keys = {str(g.get(field)) for row in gold_rows for g in row.get("gold_conditions", []) + row.get("missed_condition_candidates", [])}
        keys |= {str(p.get(field if field != "category" else "category_id")) for p in prediction_rows}
        result = {}
        for key in sorted(keys):
            gold_count = sum(str(g.get(field)) == key for row in gold_rows for g in row.get("gold_conditions", []) + row.get("missed_condition_candidates", []))
            pred_count = sum(str(p.get(field if field != "category" else "category_id")) == key for p in prediction_rows)
            tp = sum(pair["status"] == "EXACT_MATCH" and str(next((g.get(field) for row in gold_rows for g in row.get("gold_conditions", []) + row.get("missed_condition_candidates", []) if _identity(g) == pair["gold_id"]), None)) == key for d in details for pair in d["pairs"])
            result[key] = prf(tp, pred_count - tp, gold_count - tp)
        return result
    return {"policy_version": POLICY_VERSION, "common": {"micro": micro, "macro_by_notice": macro, "by_source": by_source,
            "by_condition_type": dimension("condition_type"), "by_field": dimension("field"),
            "partial_count": sum(d["partial_count"] for d in details), "notice_count": len(details),
            "notices_with_misses": sum(d["common"]["fn"] > 0 for d in details),
            "notices_with_false_positives": sum(d["common"]["fp"] > 0 for d in details)},
            "extended": ext, "safety": dict(Counter(error for d in details for error in d["safety_errors"])),
            "notices": details}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--gold-dir", type=Path)
    parser.add_argument("--condition-predictions", type=Path)
    parser.add_argument("--logic-predictions", type=Path)
    parser.add_argument("--execute", action="store_true", help="Explicitly score frozen development predictions; never used in 2-5A")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config.get("policy_version") != POLICY_VERSION or config.get("dataset_split") != "DEVELOPMENT":
        parser.error("unsupported policy or dataset split in configuration")
    gold_dir = args.gold_dir or ROOT / config["gold_dir"]
    condition_path = args.condition_predictions or ROOT / config["condition_predictions"]
    logic_path = args.logic_predictions or ROOT / config["logic_predictions"]
    readiness = preflight(gold_dir, condition_path, logic_path)
    if readiness["status"] != "PASS" or not args.execute:
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
        return 0 if readiness["status"] == "PASS" else 2
    result = evaluate_records(read_jsonl(gold_dir / "reviewed_condition_gold.jsonl"),
                              read_jsonl(gold_dir / "reviewed_logic_gold.jsonl"),
                              read_jsonl(condition_path), read_jsonl(logic_path))
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
