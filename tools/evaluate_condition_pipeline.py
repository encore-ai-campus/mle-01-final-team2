"""Guarded evaluation for condition extraction and logical structure outputs.

Real metrics are only produced from verified, complete human-reviewed gold records.
Synthetic fixtures call the same matching/canonicalization functions but are reported separately.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
GOLD_ROOT = ROOT / "data/goldsets/conditions/v1/20261125"
OUTPUT_ROOT = ROOT / "data/evaluations/conditions/v1/20261125"
BASELINE_MANIFEST = GOLD_ROOT / "baseline_manifest.json"
EVALUATOR_VERSION = "1.0.0"
REVIEWED_COMPLETE = {"REVIEWED_COMPLETE", "CONFIRMED_NONE_IN_PROVIDED_TEXT"}
EXCLUDED_STATUSES = {"UNDECIDABLE", "EXCLUDED"}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = unicodedata.normalize("NFKC", str(value))
    return re.sub(r"\s+", " ", text).strip()


def normalize_value(value: Any, *, operator: str | None = None) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        try:
            number = Decimal(str(value)).normalize()
            return str(number)
        except InvalidOperation:
            return normalize_string(value)
    if isinstance(value, str):
        text = normalize_string(value)
        if text is None:
            return None
        try:
            number = Decimal(text.replace(",", "")).normalize()
            return str(number)
        except InvalidOperation:
            return text
    if isinstance(value, list):
        values = [normalize_value(x) for x in value]
        if operator in {"IN", "NOT_IN"}:
            return sorted(values, key=lambda x: json.dumps(x, ensure_ascii=False, sort_keys=True))
        return values
    if isinstance(value, dict):
        return {normalize_string(k): normalize_value(v) for k, v in sorted(value.items())}
    return normalize_string(value)


def _candidate_source(candidate: dict[str, Any]) -> dict[str, Any]:
    return candidate.get("source") or {}


def semantic_signature(record: dict[str, Any], *, gold: bool) -> tuple[Any, ...]:
    if gold:
        reference_value = record.get("reference_date")
        reference_type = record.get("reference_date_type", "UNKNOWN")
        category = record.get("category", record.get("category_id"))
        applies_to = record.get("applicability_scope", record.get("applies_to", record.get("applicant_target")))
        operator = record.get("operator")
        value = record.get("value")
    else:
        ref = record.get("reference_date") or {}
        reference_value = ref.get("value")
        reference_type = ref.get("date_type", "UNKNOWN")
        category = record.get("category_id", record.get("category"))
        applies_to = record.get("applicability_scope", record.get("applies_to", record.get("applicant_target")))
        operator = record.get("operator")
        value = record.get("value")
    return (
        normalize_string(record.get("condition_type")),
        normalize_string(category),
        normalize_string(record.get("field")),
        normalize_string(operator),
        normalize_value(value, operator=operator),
        normalize_string(record.get("value_type")),
        normalize_string(record.get("unit")),
        normalize_string(reference_type),
        normalize_string(reference_value),
        normalize_string(applies_to),
    )


def evidence(candidate: dict[str, Any], *, gold: bool) -> tuple[str | None, int | None, int | None, str | None]:
    if gold:
        ref = candidate.get("evidence_reference") or {}
        return (normalize_string(candidate.get("source_field")), ref.get("start_char"), ref.get("end_char"),
                normalize_string(candidate.get("raw_text")))
    src = _candidate_source(candidate)
    loc = src.get("location") or {}
    return (normalize_string(src.get("source_field")), loc.get("start_char"), loc.get("end_char"),
            normalize_string(src.get("evidence_text", candidate.get("raw_text"))))


def evidence_exact(gold: dict[str, Any], predicted: dict[str, Any]) -> bool:
    gs, ps = evidence(gold, gold=True), evidence(predicted, gold=False)
    return gs == ps


def evidence_overlaps(gold: dict[str, Any], predicted: dict[str, Any]) -> bool:
    gs, ps = evidence(gold, gold=True), evidence(predicted, gold=False)
    if gs[0] != ps[0] or gs[1] is None or gs[2] is None or ps[1] is None or ps[2] is None:
        return False
    return max(gs[1], ps[1]) < min(gs[2], ps[2])


def semantic_differences(gold: dict[str, Any], predicted: dict[str, Any]) -> list[str]:
    gs, ps = semantic_signature(gold, gold=True), semantic_signature(predicted, gold=False)
    labels = ["condition_type", "category", "field", "operator", "value", "value_type", "unit",
              "reference_date_type", "reference_date", "applicability_scope"]
    return [label for label, g, p in zip(labels, gs, ps) if g != p]


def _maximum_matching(edges: dict[int, list[int]]) -> list[tuple[int, int]]:
    """Return a maximum-cardinality one-to-one bipartite matching, deterministically."""
    right_to_left: dict[int, int] = {}

    def visit(left: int, seen: set[int]) -> bool:
        for right in edges.get(left, []):
            if right in seen:
                continue
            seen.add(right)
            if right not in right_to_left or visit(right_to_left[right], seen):
                right_to_left[right] = left
                return True
        return False

    for left in sorted(edges):
        visit(left, set())
    return sorted((left, right) for right, left in right_to_left.items())


def match_conditions(gold_conditions: list[dict[str, Any]], predicted_conditions: list[dict[str, Any]]) -> dict[str, Any]:
    """Two-pass one-to-one matching; partial pairs are diagnostics, never TPs."""
    full_edges: dict[int, list[int]] = {}
    for gi, gold in enumerate(gold_conditions):
        for pi, prediction in enumerate(predicted_conditions):
            if semantic_differences(gold, prediction) == [] and evidence_exact(gold, prediction):
                full_edges.setdefault(gi, []).append(pi)
    full_pairs = _maximum_matching(full_edges)
    used_gold = {g for g, _ in full_pairs}
    used_predictions = {p for _, p in full_pairs}

    partial_edges: dict[int, list[int]] = {}
    partial_info: dict[tuple[int, int], list[str]] = {}
    for gi, gold in enumerate(gold_conditions):
        if gi in used_gold:
            continue
        for pi, prediction in enumerate(predicted_conditions):
            if pi in used_predictions:
                continue
            gs, ps = semantic_signature(gold, gold=True), semantic_signature(prediction, gold=False)
            same_identity = gs[:3] == ps[:3]
            if not same_identity:
                continue
            diffs = semantic_differences(gold, prediction)
            if evidence_overlaps(gold, prediction) or (not diffs and evidence(gold, gold=True)[3] == evidence(prediction, gold=False)[3]):
                partial_edges.setdefault(gi, []).append(pi)
                partial_info[(gi, pi)] = diffs + ([] if evidence_exact(gold, prediction) else ["evidence"])
    partial_pairs = _maximum_matching(partial_edges)
    pairs = [{"gold_index": gi, "prediction_index": pi, "match_status": "FULL",
              "gold_condition_id": gold_conditions[gi].get("gold_condition_id"),
              "prediction_condition_id": predicted_conditions[pi].get("condition_id"), "differences": []}
             for gi, pi in full_pairs]
    pairs.extend({"gold_index": gi, "prediction_index": pi, "match_status": "PARTIAL",
                  "gold_condition_id": gold_conditions[gi].get("gold_condition_id"),
                  "prediction_condition_id": predicted_conditions[pi].get("condition_id"),
                  "differences": partial_info[(gi, pi)]} for gi, pi in partial_pairs)
    return {"full_pairs": full_pairs, "partial_pairs": partial_pairs, "pairs": pairs,
            "unmatched_gold": [i for i in range(len(gold_conditions)) if i not in {g for g, _ in full_pairs}],
            "unmatched_predictions": [i for i in range(len(predicted_conditions)) if i not in {p for _, p in full_pairs}]}


def prf(tp: int, fp: int, fn: int) -> dict[str, Any]:
    p_den, r_den = tp + fp, tp + fn
    precision = tp / p_den if p_den else None
    recall = tp / r_den if r_den else None
    if not p_den and not r_den:
        f1 = None
    elif tp == 0:
        f1 = 0.0
    else:
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall is not None and precision + recall else None
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1,
            "precision_status": "DEFINED" if p_den else "NO_PREDICTIONS",
            "recall_status": "DEFINED" if r_den else "NO_GOLD_CONDITIONS"}


def _mean(values: list[float | None]) -> float | None:
    defined = [v for v in values if v is not None]
    return sum(defined) / len(defined) if defined else None


def _group_scores(notices: list[dict[str, Any]], key_fn) -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for notice in notices:
        for group_key in set(key_fn(notice)):
            groups[str(group_key)].append(notice)
    result = {}
    for group, rows in sorted(groups.items()):
        result[group] = prf(sum(r["tp"] for r in rows), sum(r["fp"] for r in rows), sum(r["fn"] for r in rows))
    return result


def evaluate_conditions(records: list[dict[str, Any]], predictions_by_notice: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    details = []
    all_pairs: list[tuple[dict[str, Any], dict[str, Any], str]] = []
    for record in records:
        nid = record["notice_id"]
        gold = record.get("gold_conditions", []) + record.get("missed_condition_candidates", [])
        predicted = predictions_by_notice.get(nid, [])
        match = match_conditions(gold, predicted)
        tp = len(match["full_pairs"])
        fp, fn = len(predicted) - tp, len(gold) - tp
        per_notice = {"notice_id": nid, "source_system": record["source_system"], "gold_count": len(gold),
                      "prediction_count": len(predicted), "tp": tp, "fp": fp, "fn": fn,
                      "miss_rate": (fn / len(gold)) if gold else None,
                      "metrics": prf(tp, fp, fn), "pairs": match["pairs"],
                      "failure_cases": []}
        for gi, pi in match["partial_pairs"]:
            all_pairs.append((gold[gi], predicted[pi], "PARTIAL"))
        for gi, pi in match["full_pairs"]:
            all_pairs.append((gold[gi], predicted[pi], "FULL"))
        for gi in match["unmatched_gold"]:
            per_notice["failure_cases"].append({"failure_type": "MISSING_CONDITION", "gold_condition_id": gold[gi].get("gold_condition_id")})
        for pi in match["unmatched_predictions"]:
            per_notice["failure_cases"].append({"failure_type": "OVER_EXTRACTION", "prediction_condition_id": predicted[pi].get("condition_id")})
        for pair in match["pairs"]:
            if pair["match_status"] == "PARTIAL":
                mapping = {"condition_type": "WRONG_CONDITION_TYPE", "category": "CONDITION_ATTRIBUTE_ERROR",
                           "field": "CONDITION_ATTRIBUTE_ERROR", "operator": "COMPARISON_OPERATOR_ERROR",
                           "value": "VALUE_OR_UNIT_ERROR", "value_type": "VALUE_OR_UNIT_ERROR", "unit": "VALUE_OR_UNIT_ERROR",
                           "reference_date": "REFERENCE_DATE_ERROR", "reference_date_type": "REFERENCE_DATE_ERROR",
                           "applicability_scope": "CONDITION_ATTRIBUTE_ERROR", "evidence": "EVIDENCE_ERROR"}
                per_notice["failure_cases"].append({"failure_type": mapping.get(pair["differences"][0], "CONDITION_ATTRIBUTE_ERROR"),
                                                    "gold_condition_id": pair["gold_condition_id"],
                                                    "prediction_condition_id": pair["prediction_condition_id"],
                                                    "differences": pair["differences"]})
        per_notice["failure_cases"] = _deduplicate_failures(per_notice["failure_cases"])
        details.append(per_notice)
    tp, fp, fn = (sum(r[k] for r in details) for k in ("tp", "fp", "fn"))
    macro = {k: _mean([r["metrics"][k] for r in details]) for k in ("precision", "recall", "f1")}
    partial_count = sum(r["match_status"] == "PARTIAL" for row in details for r in row["pairs"])
    field_stats = {}
    for position, name in enumerate(("condition_type", "category", "field", "operator", "value", "value_type", "unit", "reference_date_type", "reference_date", "applicability_scope")):
        comparable = [(g, p) for g, p, _ in all_pairs]
        matches = sum(semantic_signature(g, gold=True)[position] == semantic_signature(p, gold=False)[position] for g, p in comparable)
        field_stats[name] = {"correct": matches, "compared": len(comparable), "accuracy": matches / len(comparable) if comparable else None,
                             "status": "DEFINED" if comparable else "NO_ALIGNED_PAIRS"}
    field_stats["evidence"] = {"correct": sum(evidence_exact(g, p) for g, p, _ in all_pairs), "compared": len(all_pairs),
                               "accuracy": sum(evidence_exact(g, p) for g, p, _ in all_pairs) / len(all_pairs) if all_pairs else None,
                               "status": "DEFINED" if all_pairs else "NO_ALIGNED_PAIRS"}
    categories = lambda r: [normalize_string(c.get("category", c.get("category_id"))) for c in r.get("gold_conditions", []) + r.get("missed_condition_candidates", [])]
    types = lambda r: [normalize_string(c.get("condition_type")) for c in r.get("gold_conditions", []) + r.get("missed_condition_candidates", [])]
    sources = lambda r: [r["source_system"]]
    return {"notice_count": len(records), "micro": prf(tp, fp, fn), "macro_by_notice": macro,
            "by_source": _group_scores(details, lambda r: [r["source_system"]]),
            "by_condition_type": _score_by_gold_dimension(records, predictions_by_notice, "condition_type"),
            "by_category": _score_by_gold_dimension(records, predictions_by_notice, "category"),
            "partial_match_diagnostics": {"count": partial_count, "included_in_tp": False},
            "field_accuracy": field_stats,
            "notice_condition_omission": {"mean_miss_rate": _mean([r["miss_rate"] for r in details]),
                                          "notices_with_misses": sum(r["fn"] > 0 for r in details),
                                          "per_notice": [{"notice_id": r["notice_id"], "miss_rate": r["miss_rate"], "fn": r["fn"], "gold_count": r["gold_count"]} for r in details]},
            "notices": details}


def _deduplicate_failures(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = set()
    output = []
    for row in rows:
        key = (row.get("failure_type"), row.get("gold_condition_id"), row.get("prediction_condition_id"))
        if key not in seen:
            seen.add(key)
            output.append(row)
    return output


def _score_by_gold_dimension(records: list[dict[str, Any]], predictions_by_notice: dict[str, list[dict[str, Any]]], field: str) -> dict[str, Any]:
    labels = set()
    for record in records:
        for condition in record.get("gold_conditions", []) + record.get("missed_condition_candidates", []):
            labels.add(normalize_string(condition.get(field, condition.get("category_id") if field == "category" else None)))
    for candidates in predictions_by_notice.values():
        for candidate in candidates:
            fallback = candidate.get("category", candidate.get("category_id")) if field == "category" else None
            labels.add(normalize_string(candidate.get(field, fallback)))
    output = {}
    for label in sorted(x for x in labels if x is not None):
        tp = fp = fn = 0
        for record in records:
            gold_all = record.get("gold_conditions", []) + record.get("missed_condition_candidates", [])
            pred_all = predictions_by_notice.get(record["notice_id"], [])
            gold = [c for c in gold_all if normalize_string(c.get(field, c.get("category_id") if field == "category" else None)) == label]
            pred = [c for c in pred_all if normalize_string(c.get(field, c.get("category", c.get("category_id")) if field == "category" else None)) == label]
            matched = match_conditions(gold, pred)
            tp += len(matched["full_pairs"])
            fp += len(pred) - len(matched["full_pairs"])
            fn += len(gold) - len(matched["full_pairs"])
        output[label] = prf(tp, fp, fn)
    return output


def _canonical(node: dict[str, Any], id_map: dict[str, str]) -> tuple[Any, ...]:
    if node["node_type"] == "CONDITION_REF":
        raw = node["condition_id"]
        return ("REF", id_map.get(raw, raw))
    op = node["operator"]
    children = [_canonical(child, id_map) for child in node["children"]]
    if op in {"AND", "OR"}:
        flattened = []
        for child in children:
            if len(child) == 2 and child[0] == op:
                flattened.extend(child[1])
            else:
                flattened.append(child)
        children = flattened
    if op in {"AND", "OR", "UNRESOLVED"}:
        children = sorted(children, key=repr)
    return (op, tuple(children))


def _root_list(roots: list[dict[str, Any]], id_map: dict[str, str]) -> tuple[Any, ...]:
    return tuple(sorted((_canonical(r, id_map) for r in roots), key=repr))


def _groups_and_edges(roots: list[dict[str, Any]], id_map: dict[str, str]) -> tuple[Counter, Counter, Counter]:
    groups: Counter = Counter()
    edges: Counter = Counter()
    unresolved: Counter = Counter()

    def leaves(ast: tuple[Any, ...]) -> tuple[str, ...]:
        if ast[0] == "REF":
            return (ast[1],)
        return tuple(sorted(x for child in ast[1] for x in leaves(child)))

    def walk(node: dict[str, Any], parent_sig: Any = ("ROOT",)):
        if node["node_type"] != "LOGICAL_GROUP":
            return _canonical(node, id_map)
        current = _canonical(node, id_map)
        groups[current] += 1
        if node["operator"] == "UNRESOLVED":
            unresolved[leaves(current)] += 1
        for child in node["children"]:
            child_sig = walk(child, current)
            edges[(current, child_sig)] += 1
        return current

    for root in roots:
        walk(root)
    return groups, edges, unresolved


def _extract_roots(prediction_record: dict[str, Any]) -> list[dict[str, Any]]:
    if "logical_roots" in prediction_record:
        return prediction_record["logical_roots"]
    roots = []
    for collection in prediction_record.get("condition_sets", {}).values():
        roots.extend(collection.get("logical_roots", []))
    return roots


def _prediction_unresolved(roots: list[dict[str, Any]], id_map: dict[str, str]) -> Counter:
    _, _, counts = _groups_and_edges(roots, id_map)
    return counts


def _qualifier_exceptions(prediction_record: dict[str, Any], id_map: dict[str, str]) -> Counter:
    result: Counter = Counter()
    for condition in _prediction_conditions(prediction_record):
        for qualifier in condition.get("qualifiers", []):
            if qualifier.get("qualifier_type") not in {"EXCEPTION", "CAVEAT"}:
                continue
            targets = tuple(sorted(id_map.get(x, x) for x in qualifier.get("applies_to_condition_ids", [])))
            result[(normalize_string(qualifier.get("raw_text")), targets, qualifier.get("linkage_status"))] += 1
    return result


def _prediction_conditions(prediction_record: dict[str, Any]) -> list[dict[str, Any]]:
    conditions = prediction_record.get("conditions", [])
    if not conditions:
        conditions = [c for group in prediction_record.get("condition_sets", {}).values() for c in group.get("conditions", [])]
    return conditions


def compare_logic(gold_roots: list[dict[str, Any]], predicted_roots: list[dict[str, Any]],
                  id_map: dict[str, str] | None = None, *, gold_exceptions: list[dict[str, Any]] | None = None,
                  gold_benefits: list[dict[str, Any]] | None = None,
                  gold_unresolved_relations: list[dict[str, Any]] | None = None,
                  prediction_record: dict[str, Any] | None = None,
                  generation_possible: bool = False) -> dict[str, Any]:
    mapping = id_map or {}
    g_ast, p_ast = _root_list(gold_roots, {}), _root_list(predicted_roots, mapping)
    g_groups, g_edges, g_unresolved = _groups_and_edges(gold_roots, {})
    p_groups, p_edges, p_unresolved = _groups_and_edges(predicted_roots, mapping)
    common_groups = sum((g_groups & p_groups).values())
    group_total = sum(g_groups.values())
    pred_group_total = sum(p_groups.values())
    common_edges = sum((g_edges & p_edges).values())
    edge_scores = prf(common_edges, sum(p_edges.values()) - common_edges, sum(g_edges.values()) - common_edges)
    gold_unresolved = Counter(tuple(sorted(x.get("gold_condition_ids", []))) for x in (gold_unresolved_relations or []))
    # The reviewed unresolved relation queue is authoritative; an unresolved AST group is
    # also a gold unresolved relation when no separate relation row was recorded.
    if not gold_unresolved:
        gold_unresolved = g_unresolved.copy()
    unresolved_correct = sum((gold_unresolved & p_unresolved).values())
    unresolved_gold = sum(gold_unresolved.values())
    unresolved_pred = sum(p_unresolved.values())
    exception_gold = Counter()
    for exception in gold_exceptions or []:
        exception_gold[(normalize_string(exception.get("raw_text")), tuple(sorted(exception.get("applies_to_gold_ids", []))), exception.get("linkage_status"))] += 1
    exception_pred = _qualifier_exceptions(prediction_record or {}, mapping)
    exception_tp = sum((exception_gold & exception_pred).values())
    # Benefits are linked from preference conditions; support both top-level synthetic and schema-native records.
    benefits_gold = Counter()
    for benefit in gold_benefits or []:
        benefits_gold[(normalize_string(benefit.get("raw_text")), tuple(sorted(benefit.get("applies_when_gold_ids", []))))] += 1
    benefits_pred = Counter()
    for condition in _prediction_conditions(prediction_record or {}):
        benefit = condition.get("benefit")
        if benefit:
            benefits_pred[(normalize_string(benefit.get("raw_text")), tuple(sorted(mapping.get(x, x) for x in benefit.get("applies_when_condition_ids", []))))] += 1
    benefit_tp = sum((benefits_gold & benefits_pred).values())
    return {"logical_relation": edge_scores,
            "operator_accuracy": {"correct_groups": common_groups, "predicted_groups": pred_group_total,
                                 "gold_groups": group_total, "accuracy": common_groups / group_total if group_total else None,
                                 "status": "DEFINED" if group_total else "NO_GOLD_GROUPS"},
            "logical_group_exact": {"correct": common_groups, "predicted": pred_group_total, "gold": group_total,
                                    "precision": common_groups / pred_group_total if pred_group_total else None,
                                    "recall": common_groups / group_total if group_total else None},
            "notice_structure_exact": g_ast == p_ast,
            "nested_structure_exact": {"gold_nested_groups": sum(1 for g in g_groups if _has_nested(g)),
                                       "predicted_nested_groups": sum(1 for g in p_groups if _has_nested(g)),
                                       "exact": Counter({g: n for g, n in g_groups.items() if _has_nested(g)}) == Counter({g: n for g, n in p_groups.items() if _has_nested(g)})},
            "exceptions": prf(exception_tp, sum(exception_pred.values()) - exception_tp, sum(exception_gold.values()) - exception_tp),
            "preference_benefit_links": prf(benefit_tp, sum(benefits_pred.values()) - benefit_tp, sum(benefits_gold.values()) - benefit_tp),
            "unresolved_handling": {"correct": unresolved_correct, "predicted": unresolved_pred, "gold": unresolved_gold,
                                    "precision": unresolved_correct / unresolved_pred if unresolved_pred else None,
                                    "recall": unresolved_correct / unresolved_gold if unresolved_gold else None,
                                    "overcautious_unresolved": sum((p_unresolved - gold_unresolved).values())},
            "logic_generation_possible": generation_possible, "gold_root_count": len(gold_roots),
            "prediction_root_count": len(predicted_roots)}


def _has_nested(ast: tuple[Any, ...]) -> bool:
    return ast[0] != "REF" and any(child[0] != "REF" or _has_nested(child) for child in ast[1])


def schema_validators() -> dict[str, Draft202012Validator]:
    directory = ROOT / "schemas/conditions"
    resources, schemas = [], {}
    for path in sorted(directory.glob("*.schema.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        resources.append((schema["$id"], Resource.from_contents(schema)))
        schemas[path.name] = schema
    registry = Registry().with_resources(resources)
    return {name: Draft202012Validator(schema, registry=registry, format_checker=FormatChecker()) for name, schema in schemas.items()}


def preflight(split: str, gold_root: Path = GOLD_ROOT) -> dict[str, Any]:
    if split not in {"development", "evaluation"}:
        raise ValueError("split must be development or evaluation")
    gold_dir = gold_root / split
    review_path = gold_dir / "condition_review.jsonl"
    logic_review_path = gold_dir / "logic_review.jsonl"
    condition_path = gold_dir / "reviewed_condition_gold.jsonl"
    logic_path = gold_dir / "reviewed_logic_gold.jsonl"
    baseline_path = gold_root / "baseline_manifest.json"
    report: dict[str, Any] = {"split": split.upper(), "score_status": "BLOCKED", "blocking_reasons": [],
                              "reviewed_gold_conditions": 0, "reviewed_gold_logic_notices": 0,
                              "excluded_by_status": {}, "baseline_hashes_valid": False}
    missing = [str(p) for p in (review_path, logic_review_path, condition_path, logic_path, baseline_path) if not p.exists()]
    if missing:
        report["blocking_reasons"].append({"code": "MISSING_GOLD_ARTIFACTS", "paths": missing})
        return report
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    mismatches = []
    for item in baseline.get("files", {}).values():
        source = ROOT / item["path"]
        if not source.exists() or sha256(source) != item["sha256"]:
            mismatches.append(item["path"])
    report["baseline_hashes_valid"] = not mismatches
    if mismatches:
        report["blocking_reasons"].append({"code": "BASELINE_HASH_MISMATCH", "paths": mismatches})
    own_review = read_jsonl(review_path)
    own_logic_review = read_jsonl(logic_review_path)
    other_split = "evaluation" if split == "development" else "development"
    other_ids = {r["notice_id"] for r in read_jsonl(gold_root / other_split / "condition_review.jsonl")}
    own_ids = [r["notice_id"] for r in own_review]
    if len(own_ids) != len(set(own_ids)) or set(own_ids) & other_ids:
        report["blocking_reasons"].append({"code": "NOTICE_ID_DUPLICATE_OR_SPLIT_OVERLAP"})
    if {r["notice_id"] for r in own_logic_review} != set(own_ids):
        report["blocking_reasons"].append({"code": "CONDITION_LOGIC_REVIEW_SET_MISMATCH"})
    condition_records, logic_records = read_jsonl(condition_path), read_jsonl(logic_path)
    for name, rows in (("condition", condition_records), ("logic", logic_records)):
        notice_ids = [r.get("notice_id") for r in rows]
        if len(notice_ids) != len(set(notice_ids)):
            report["blocking_reasons"].append({"code": f"DUPLICATE_{name.upper()}_GOLD_NOTICE_ID"})
    report["reviewed_gold_conditions"] = sum(len(r.get("gold_conditions", [])) + len(r.get("missed_condition_candidates", [])) for r in condition_records)
    report["reviewed_gold_logic_notices"] = len(logic_records)
    validators = schema_validators()
    schema_errors = []
    for row in own_review:
        schema_errors.extend(list(validators["condition-gold-review-v1.schema.json"].iter_errors(row)))
    for row in own_logic_review:
        schema_errors.extend(list(validators["logic-gold-review-v1.schema.json"].iter_errors(row)))
    for row in condition_records:
        if row.get("review_status") != "VERIFIED" or row.get("dataset_split") != split.upper() or row.get("adjudication_status") not in REVIEWED_COMPLETE:
            schema_errors.append(ValueError(f"gold condition record is not complete and verified: {row.get('notice_id')}"))
    for row in logic_records:
        if row.get("review_status") != "VERIFIED" or row.get("dataset_split") != split.upper() or row.get("adjudication_status") not in REVIEWED_COMPLETE:
            schema_errors.append(ValueError(f"gold logic record is not complete and verified: {row.get('notice_id')}"))
    try:
        from tools.ingest_condition_gold_reviews import validate_review_packets
        expected_conditions, expected_logic, _ = validate_review_packets(gold_root, split)
        if condition_records != expected_conditions or logic_records != expected_logic:
            schema_errors.append(ValueError("ingested gold outputs are stale or do not match reviewed source packets"))
    except (ValueError, KeyError, FileNotFoundError) as exc:
        schema_errors.append(ValueError(f"gold review packet integrity check failed: {exc}"))
    all_gold_ids = [c.get("gold_condition_id") for row in condition_records
                    for c in row.get("gold_conditions", []) + row.get("missed_condition_candidates", [])]
    if len(all_gold_ids) != len(set(all_gold_ids)):
        schema_errors.append(ValueError("duplicate gold condition IDs across notices"))
    if schema_errors:
        report["blocking_reasons"].append({"code": "GOLD_SCHEMA_OR_REVIEW_STATUS_INVALID", "count": len(schema_errors)})
    statuses = Counter(r.get("adjudication_status", "MISSING") for r in own_review)
    review_statuses = Counter(r.get("review_status", "MISSING") for r in own_review)
    report["status_counts"] = {"adjudication": dict(statuses), "review": dict(review_statuses)}
    report["excluded_by_status"] = {k: v for k, v in statuses.items() if k in EXCLUDED_STATUSES}
    complete_ids = {r["notice_id"] for r in condition_records if r.get("adjudication_status") in REVIEWED_COMPLETE}
    complete_logic_ids = {r["notice_id"] for r in logic_records if r.get("adjudication_status") in REVIEWED_COMPLETE}
    if not complete_ids:
        report["blocking_reasons"].append({"code": "NO_VERIFIED_COMPLETE_GOLDSET"})
    if complete_ids != complete_logic_ids:
        report["blocking_reasons"].append({"code": "CONDITION_LOGIC_GOLD_COVERAGE_MISMATCH"})
    if report["blocking_reasons"]:
        report["score_status"] = "BLOCKED"
    else:
        report["score_status"] = "READY"
        report["eligible_notice_count"] = len(complete_ids)
    return report


def evaluate(split: str, *, gold_root: Path = GOLD_ROOT, output_root: Path = OUTPUT_ROOT,
             condition_predictions_path: Path | None = None, logic_predictions_path: Path | None = None,
             mode: str = "end_to_end") -> dict[str, Any]:
    if mode not in {"end_to_end", "logic_oracle"}:
        raise ValueError("mode must be end_to_end or logic_oracle")
    readiness = preflight(split, gold_root)
    out_dir = output_root / split
    out_dir.mkdir(parents=True, exist_ok=True)
    if readiness["score_status"] != "READY":
        result = {"evaluation_status": "BLOCKED", "score_status": "NOT_COMPUTED", "preflight": readiness,
                  "run_config": {"split": split.upper(), "mode": mode, "predictions_opened": False},
                  "notice_count": 0, "condition_metrics": None, "logic_metrics": None,
                  "excluded_notices": (_excluded_notices(gold_root / split / "condition_review.jsonl") if (gold_root / split / "condition_review.jsonl").exists() else []),
                  "not_evaluated_notices": (_not_evaluated_notices(gold_root / split / "condition_review.jsonl") if (gold_root / split / "condition_review.jsonl").exists() else []),
                  "run_metadata": _run_metadata(None, None, gold_root / "baseline_manifest.json"),
                  "reason": "No accuracy value is assigned when verified complete gold is unavailable."}
        save_report(result, out_dir)
        return result
    if logic_predictions_path is None or (mode == "end_to_end" and condition_predictions_path is None):
        result = {"evaluation_status": "BLOCKED", "score_status": "NOT_COMPUTED", "preflight": readiness,
                  "run_config": {"split": split.upper(), "mode": mode, "predictions_opened": False},
                  "notice_count": 0, "condition_metrics": None, "logic_metrics": None,
                  "run_metadata": _run_metadata(condition_predictions_path, logic_predictions_path, gold_root / "baseline_manifest.json"),
                  "reason": "Prediction files are required only after gold preflight passes."}
        save_report(result, out_dir)
        return result

    condition_predictions = read_jsonl(condition_predictions_path) if condition_predictions_path else []
    logic_predictions = read_jsonl(logic_predictions_path)
    other_split = "evaluation" if split == "development" else "development"
    other_ids = {r["notice_id"] for r in read_jsonl(gold_root / other_split / "condition_review.jsonl")}
    prediction_ids = {r.get("notice_id") for r in condition_predictions + logic_predictions}
    foreign_ids = sorted(prediction_ids & other_ids)
    if foreign_ids:
        result = {"evaluation_status": "BLOCKED", "score_status": "NOT_COMPUTED", "preflight": readiness,
                  "run_config": {"split": split.upper(), "mode": mode, "predictions_opened": True},
                  "notice_count": 0, "condition_metrics": None, "logic_metrics": None,
                  "blocking_reasons": [{"code": "PREDICTION_SPLIT_LEAKAGE", "notice_ids": foreign_ids}],
                  "run_metadata": _run_metadata(condition_predictions_path, logic_predictions_path, gold_root / "baseline_manifest.json"),
                  "reason": "Prediction records from the other split are never scored."}
        save_report(result, out_dir)
        return result
    pred_by_notice: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for prediction in condition_predictions:
        pred_by_notice[prediction["notice_id"]].append(prediction)
    gold_conditions = [r for r in read_jsonl(gold_root / split / "reviewed_condition_gold.jsonl")
                       if r.get("adjudication_status") in REVIEWED_COMPLETE]
    gold_logic = {r["notice_id"]: r for r in read_jsonl(gold_root / split / "reviewed_logic_gold.jsonl")
                  if r.get("adjudication_status") in REVIEWED_COMPLETE}
    logic_by_notice = {r["notice_id"]: r for r in logic_predictions}
    condition_result = evaluate_conditions(gold_conditions, pred_by_notice) if mode == "end_to_end" else None
    # Establish only full, one-to-one condition ID translations for end-to-end graph scoring.
    id_maps: dict[str, dict[str, str]] = {}
    for gold_row in gold_conditions:
        nid = gold_row["notice_id"]
        if mode == "logic_oracle":
            id_maps[nid] = {c["gold_condition_id"]: c["gold_condition_id"] for c in gold_row.get("gold_conditions", [])}
        else:
            matches = match_conditions(gold_row.get("gold_conditions", []) + gold_row.get("missed_condition_candidates", []), pred_by_notice.get(nid, []))
            all_gold = gold_row.get("gold_conditions", []) + gold_row.get("missed_condition_candidates", [])
            id_maps[nid] = {pred_by_notice[nid][pi]["condition_id"]: all_gold[gi]["gold_condition_id"]
                            for gi, pi in matches["full_pairs"]}
    logic_details = []
    for gold_row in gold_logic.values():
        nid = gold_row["notice_id"]
        pred = logic_by_notice.get(nid, {})
        roots = _extract_roots(pred)
        compare = compare_logic(gold_row.get("gold_logic_roots", []), roots, id_maps.get(nid, {}),
                                gold_exceptions=gold_row.get("gold_exceptions", []),
                                gold_benefits=gold_row.get("gold_benefits", []),
                                gold_unresolved_relations=gold_row.get("unresolved_relations", []),
                                prediction_record=pred, generation_possible=nid in logic_by_notice)
        logic_details.append({"notice_id": nid, **compare})
    result = {"evaluation_status": "COMPLETED", "score_status": "COMPUTED",
              "split": split.upper(), "mode": mode, "run_config": {"split": split.upper(), "mode": mode,
              "predictions_opened": True}, "preflight": readiness,
              "condition_metrics": condition_result,
              "logic_metrics": _aggregate_logic(logic_details), "logic_by_notice": logic_details,
              "excluded_notices": _excluded_notices(gold_root / split / "condition_review.jsonl"),
              "not_evaluated_notices": _not_evaluated_notices(gold_root / split / "condition_review.jsonl"),
              "evaluation_scope": "SOURCE_TEXT_ONLY", "not_a_qualification_decision": True,
              "run_metadata": _run_metadata(condition_predictions_path, logic_predictions_path,
                                             gold_root / "baseline_manifest.json")}
    save_report(result, out_dir)
    return result


def _aggregate_logic(details: list[dict[str, Any]]) -> dict[str, Any]:
    if not details:
        return {"notice_count": 0, "status": "NO_EVALUABLE_LOGIC_RECORDS"}
    metrics = {}
    for key in ("logical_relation", "exceptions", "preference_benefit_links"):
        tp = sum(r[key]["tp"] for r in details)
        fp = sum(r[key]["fp"] for r in details)
        fn = sum(r[key]["fn"] for r in details)
        metrics[key] = prf(tp, fp, fn)
    operator_values = [r["operator_accuracy"]["accuracy"] for r in details if r["operator_accuracy"]["accuracy"] is not None]
    group_total = sum(r["logical_group_exact"]["gold"] for r in details)
    group_pred = sum(r["logical_group_exact"]["predicted"] for r in details)
    group_correct = sum(r["logical_group_exact"]["correct"] for r in details)
    generation_den = len(details)
    gold_unres = sum(r["unresolved_handling"]["gold"] for r in details)
    pred_unres = sum(r["unresolved_handling"]["predicted"] for r in details)
    correct_unres = sum(r["unresolved_handling"]["correct"] for r in details)
    return {"notice_count": len(details), **metrics,
            "operator_accuracy": {"accuracy": _mean(operator_values), "compared_groups": sum(r["operator_accuracy"]["gold_groups"] for r in details)},
            "logical_group_exact": {"correct": group_correct, "predicted": group_pred, "gold": group_total,
                                    "precision": group_correct / group_pred if group_pred else None,
                                    "recall": group_correct / group_total if group_total else None,
                                    "exact_rate": group_correct / group_total if group_total else None},
            "notice_structure_exact_rate": sum(r["notice_structure_exact"] for r in details) / len(details),
            "nested_structure_exact_rate": _mean([1.0 if r["nested_structure_exact"]["exact"] else 0.0 for r in details if r["nested_structure_exact"]["gold_nested_groups"]]),
            "unresolved_handling": {"correct": correct_unres, "predicted": pred_unres, "gold": gold_unres,
                                    "precision": correct_unres / pred_unres if pred_unres else None,
                                    "recall": correct_unres / gold_unres if gold_unres else None,
                                    "overcautious_unresolved": sum(r["unresolved_handling"]["overcautious_unresolved"] for r in details)},
            "logic_generation_possible_rate": sum(r["logic_generation_possible"] for r in details) / generation_den if generation_den else None,
            "status": "DEFINED" if details else "NO_EVALUABLE_LOGIC_RECORDS"}


def _excluded_notices(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    return [{"notice_id": r["notice_id"], "source_system": r["source_system"],
             "adjudication_status": r.get("adjudication_status", "PENDING"),
             "review_status": r.get("review_status", "UNREVIEWED"),
             "reason": r.get("review_comment")} for r in rows
            if r.get("adjudication_status") in EXCLUDED_STATUSES]


def _not_evaluated_notices(path: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(path)
    return [{"notice_id": r["notice_id"], "source_system": r["source_system"],
             "adjudication_status": r.get("adjudication_status", "PENDING"),
             "review_status": r.get("review_status", "UNREVIEWED"),
             "reason": r.get("review_comment")} for r in rows
            if r.get("adjudication_status") not in REVIEWED_COMPLETE or r.get("review_status") != "VERIFIED"]


def _run_metadata(condition_path: Path | None, logic_path: Path | None, baseline_manifest: Path = BASELINE_MANIFEST) -> dict[str, Any]:
    files = ["tools/extract_condition_candidates.py", "tools/build_condition_logic.py", "tools/evaluate_condition_pipeline.py"]
    return {"evaluator_version": EVALUATOR_VERSION,
            "code_sha256": {name: sha256(ROOT / name) for name in files},
            "prediction_files": (({str(condition_path): sha256(condition_path)} if condition_path and condition_path.exists() else {}) |
                                 ({str(logic_path): sha256(logic_path)} if logic_path and logic_path.exists() else {})),
            "baseline_manifest_sha256": sha256(baseline_manifest) if baseline_manifest.exists() else None}


def save_report(result: dict[str, Any], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "evaluation_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    details = (result.get("condition_metrics") or {}).get("notices", [])
    write_jsonl(out_dir / "notice_details.jsonl", details)
    failures = [failure | {"notice_id": notice["notice_id"]} for notice in details for failure in notice.get("failure_cases", [])]
    write_jsonl(out_dir / "failures.jsonl", failures)
    write_jsonl(out_dir / "condition_matches.jsonl", [pair | {"notice_id": row["notice_id"]}
                for row in details for pair in row.get("pairs", [])])
    write_jsonl(out_dir / "logic_details.jsonl", result.get("logic_by_notice", []))
    (out_dir / "excluded_notices.json").write_text(json.dumps(result.get("excluded_notices", []), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out_dir / "not_evaluated_notices.json").write_text(json.dumps(result.get("not_evaluated_notices", []), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# 조건 추출·논리 구조 평가 결과", "", f"상태: `{result.get('score_status')}`", ""]
    if result.get("score_status") != "COMPUTED":
        lines += ["사람 검수 완료 정답이 없어 성능 점수를 산출하지 않았습니다.", "",
                  "차단 사유: " + ", ".join(x["code"] for x in result.get("preflight", {}).get("blocking_reasons", [])), ""]
    else:
        cm = result["condition_metrics"]["micro"]
        lines += [f"조건 추출 micro: P={cm['precision']} R={cm['recall']} F1={cm['f1']}",
                  f"논리 구조 완전 일치율: {result['logic_metrics']['notice_structure_exact_rate']}",
                  "점수 범위는 제공된 원문 구간이며 신청 자격 판정 결과가 아닙니다.", ""]
    (out_dir / "evaluation_report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=["development", "evaluation"], required=True)
    parser.add_argument("--gold-root", type=Path, default=GOLD_ROOT)
    parser.add_argument("--output-root", type=Path, default=OUTPUT_ROOT)
    parser.add_argument("--condition-predictions", type=Path)
    parser.add_argument("--logic-predictions", type=Path)
    parser.add_argument("--mode", choices=["end_to_end", "logic_oracle"], default="end_to_end")
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    readiness = preflight(args.split, args.gold_root)
    if args.preflight_only:
        print(json.dumps(readiness, ensure_ascii=False, indent=2))
        return 0
    # Evaluate() performs preflight before opening any prediction file.
    result = evaluate(args.split, gold_root=args.gold_root, output_root=args.output_root,
                      condition_predictions_path=args.condition_predictions,
                      logic_predictions_path=args.logic_predictions, mode=args.mode)
    print(json.dumps({"evaluation_status": result["evaluation_status"], "score_status": result["score_status"],
                      "report_dir": str(args.output_root / args.split)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
