"""Contract and cross-reference tests for frozen condition schema samples."""
from __future__ import annotations

import json
import re
import sys
import unittest
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tests.local_data import G2B_FULL, G2B_SNAPSHOT, needs
from tools.normalize_support_data import pii_findings

SCHEMA_DIR = ROOT / "schemas" / "conditions"
SAMPLE_DIR = ROOT / "sample_data" / "conditions"
DATA_DIR = ROOT / "data" / "normalized" / "v1" / "20261124"
G2B_DATA_DIR = ROOT / "data" / "normalized" / "v1" / "20261125_g2b"
EXPECTED_COUNTS = {"notices": 5116, "chunks": 32947}
ROOT_SCHEMA = "notice-condition-set-v1.schema.json"
Record = dict[str, Any]


def _json(path: Path) -> Record:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected JSON object")
    return value


def _jsonl(path: Path) -> Iterator[Record]:
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{number}: expected object")
            yield row


def make_validator() -> Draft202012Validator:
    resources = {}
    root = None
    for path in sorted(SCHEMA_DIR.glob("*.schema.json")):
        schema = _json(path)
        Draft202012Validator.check_schema(schema)
        schema_id = schema["$id"]
        if schema_id in resources:
            raise ValueError(f"Duplicate schema ID: {schema_id}")
        resources[schema_id] = Resource.from_contents(schema)
        if path.name == ROOT_SCHEMA:
            root = schema
    if root is None:
        raise FileNotFoundError(SCHEMA_DIR / ROOT_SCHEMA)
    return Draft202012Validator(
        root, registry=Registry().with_resources(resources.items()),
        format_checker=FormatChecker(),
    )


def _compact(text: str) -> str:
    return " ".join(text.split())


def _error_locations(error):
    yield tuple(error.absolute_path)
    for child in error.context:
        yield from _error_locations(child)


class ConditionSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = make_validator()
        cls.actual = list(_jsonl(SAMPLE_DIR / "actual-condition-samples.jsonl"))
        cls.synthetic = list(_jsonl(SAMPLE_DIR / "synthetic-condition-samples.jsonl"))
        selected = {row["notice_id"] for row in cls.actual if row["source_system"] != "G2B"}
        cls.notices = {}
        cls.chunks = {}
        cls.counts = {}
        for kind, key, target in (
            ("notices", "notice_id", cls.notices),
            ("chunks", "chunk_id", cls.chunks),
        ):
            count = 0
            for row in _jsonl(DATA_DIR / f"{kind}.jsonl"):
                count += 1
                if row["notice_id"] not in selected:
                    continue
                identifier = row[key]
                if identifier in target:
                    raise ValueError(f"Duplicate selected {key}: {identifier}")
                target[identifier] = row
            cls.counts[kind] = count

    def assert_schema_valid(self, row: Record):
        errors = list(self.validator.iter_errors(row))
        self.assertFalse(errors, [(e.json_path, e.validator) for e in errors])

    def assert_mutation_rejected(self, baseline, mutate, expected_path):
        self.assert_schema_valid(baseline)
        candidate = deepcopy(baseline)
        mutate(candidate)
        self.assertNotEqual(candidate, baseline, "Mutation did not change baseline")
        errors = list(self.validator.iter_errors(candidate))
        self.assertTrue(errors, "Invalid mutation was accepted")
        paths = [p for e in errors for p in _error_locations(e)]
        self.assertTrue(any(p[:len(expected_path)] == expected_path for p in paths),
                        f"Expected error at {expected_path}; observed {paths}")

    def synthetic_row(self, notice_id):
        matches = [r for r in self.synthetic if r["notice_id"] == notice_id]
        self.assertEqual(len(matches), 1, notice_id)
        return matches[0]

    def test_schema_files_and_both_sample_sets_validate(self):
        for rows, kind, count in ((self.actual, "ACTUAL_SOURCE", 11),
                                  (self.synthetic, "SYNTHETIC_TEST", 3)):
            self.assertEqual(len(rows), count)
            self.assertEqual(len({r["notice_id"] for r in rows}), count)
            for row in rows:
                with self.subTest(notice_id=row["notice_id"]):
                    self.assertEqual(row["sample_metadata"]["kind"], kind)
                    self.assert_schema_valid(row)
                    self.assertEqual(pii_findings(row), [])
                    if kind == "SYNTHETIC_TEST":
                        for group in row["condition_sets"].values():
                            for condition in group["conditions"]:
                                self.assertIs(condition["search_eligible"], False)

    @needs(G2B_SNAPSHOT)
    def test_actual_samples_are_source_linked_and_unresolved(self):
        for row in self.actual:
            with self.subTest(notice_id=row["notice_id"]):
                is_g2b = row["source_system"] == "G2B"
                self.assertEqual(row["source_snapshot"], G2B_DATA_DIR.name if is_g2b else DATA_DIR.name)
                if is_g2b:
                    self.assert_g2b_sample_unresolved(row)
                    continue
                notice = self.notices[row["notice_id"]]
                self.assertEqual(row["source_system"], notice["source"]["source_system"])
                for key in ("eligibility_decision_eligible", "preference_assessment_eligible"):
                    self.assertIs(row["decision_readiness"][key], False)
                for name, group in row["condition_sets"].items():
                    with self.subTest(group=name):
                        original = notice["condition_texts"][name]
                        self.assertIs(group["decision_eligible"], False)
                        self.assertNotEqual(group["availability_status"], "NO_CONDITION_CONFIRMED")
                        if original["availability"] == "PRESENT":
                            self.assertEqual(group["availability_status"], "AVAILABLE")
                            self.assertTrue(group["conditions"])
                        else:
                            self.assertEqual(group["availability_status"], original["availability"])
                            self.assertFalse(group["conditions"])
                        for condition in group["conditions"]:
                            self.assertEqual(condition["notice_id"], row["notice_id"])
                            self.assertEqual(condition["raw_text"], original["text"])
                            self.assertIs(condition["decision_eligible"], False)
                            self.assertIsNone(condition["operator"])
                            self.assertIsNone(condition["value"])
                            src = condition["source"]
                            self.assertEqual(src["evidence_text"], original["text"])
                            self.assertEqual(src["source_system"], row["source_system"])
                            self.assertEqual(src["normalized_path"], f"condition_texts.{name}.text")
                            ids = src["chunk_ids"]
                            self.assertEqual(len(ids), len(set(ids)))
                            self.assertEqual(condition["search_eligible"], bool(ids))
                            self.assertEqual(src["source_kind"], "CHUNK" if ids else "NOTICE_FIELD")
                            for cid in ids:
                                chunk = self.chunks[cid]
                                self.assertEqual(chunk["notice_id"], row["notice_id"])
                                self.assertEqual(chunk["source_system"], row["source_system"])
                                self.assertIs(chunk["search_eligible"], True)
                                self.assertEqual(chunk["privacy_status"], "CLEARED")
                                self.assertNotIn(chunk["origin"], (None, "UNKNOWN", ""))
                                self.assertFalse(chunk["origin"].startswith("ATTACHMENT"))
                                self.assertTrue(_compact(original["text"]))
                                self.assertIn(_compact(original["text"]), _compact(chunk["text"]))
                for context in row["context_references"]:
                    self.assertIs(context["used_as_condition"], False)
                    value = notice
                    for key in context["source"]["normalized_path"].split("."):
                        value = value[key]
                    self.assertEqual(context["raw_value"], value)

    def assert_g2b_sample_unresolved(self, row):
        notice_path = G2B_DATA_DIR / "notices.jsonl"
        notice = next(n for n in _jsonl(notice_path) if n["notice_id"] == row["notice_id"])
        native = notice["source_metadata"]["source_specific"]["G2B"]
        self.assertEqual(row["source_system"], "G2B")
        self.assertIs(row["decision_readiness"]["eligibility_decision_eligible"], False)
        for name, group in row["condition_sets"].items():
            self.assertIs(group["decision_eligible"], False)
            if name != "eligibility":
                self.assertEqual(group["availability_status"], "NOT_COLLECTED")
                self.assertFalse(group["conditions"])
                continue
            self.assertEqual(len(group["conditions"]), 1)
            condition = group["conditions"][0]
            src = condition["source"]
            self.assertEqual(condition["condition_type"], "UNCLASSIFIED")
            self.assertIsNone(condition["operator"])
            self.assertIsNone(condition["value"])
            self.assertIs(condition["search_eligible"], False)
            self.assertIs(condition["decision_eligible"], False)
            self.assertEqual(src["source_system"], "G2B")
            self.assertEqual(src["source_kind"], "NOTICE_FIELD")
            self.assertEqual(src["chunk_ids"], [])
            path = src["normalized_path"].removeprefix("source_metadata.source_specific.G2B.")
            match = re.fullmatch(r"(licenses|regions)\[(\d+)\](?:\.(name))?", path)
            if match and match.group(1) == "licenses":
                expected = native["licenses"][int(match.group(2))]["name"]
            elif match and match.group(1) == "regions":
                expected = native["regions"][int(match.group(2))]
            else:
                expected = native[path]
            self.assertEqual(condition["raw_text"], str(expected))
            self.assertEqual(src["evidence_text"], str(expected))
            self.assertEqual(pii_findings(row), [])

    def test_synthetic_logic_and_exception_links_are_closed(self):
        for row in self.synthetic:
            with self.subTest(notice_id=row["notice_id"]):
                groups = row["condition_sets"]
                all_ids = [c["condition_id"] for g in groups.values() for c in g["conditions"]]
                ids = set(all_ids)
                self.assertEqual(len(all_ids), len(ids))
                group_ids = set()
                for name, group in groups.items():
                    local_ids = {c["condition_id"] for c in group["conditions"]}
                    referenced = set()
                    stack = list(group["logical_roots"])
                    while stack:
                        node = stack.pop()
                        if node["node_type"] == "CONDITION_REF":
                            self.assertIn(node["condition_id"], local_ids)
                            referenced.add(node["condition_id"])
                        else:
                            self.assertEqual(node["node_type"], "LOGICAL_GROUP")
                            self.assertNotIn(node["group_id"], group_ids)
                            group_ids.add(node["group_id"])
                            stack.extend(node["children"])
                    if group["decision_eligible"]:
                        self.assertEqual(referenced, local_ids)
                    for condition in group["conditions"]:
                        self.assertEqual(condition["notice_id"], row["notice_id"])
                        if group["decision_eligible"]:
                            self.assertIs(condition["decision_eligible"], True)
                        for qualifier in condition["qualifiers"]:
                            self.assertLessEqual(set(qualifier["applies_to_condition_ids"]), ids)
                        if condition["benefit"]:
                            self.assertLessEqual(set(condition["benefit"]["applies_when_condition_ids"]), ids)
                readiness = row["decision_readiness"]
                if readiness["eligibility_decision_eligible"]:
                    self.assertTrue(groups["eligibility"]["decision_eligible"] and groups["exclusion"]["decision_eligible"])
                if readiness["preference_assessment_eligible"]:
                    self.assertIs(groups["preference"]["decision_eligible"], True)

    def test_invalid_logic_and_unverified_no_condition_are_rejected(self):
        valid = self.synthetic_row("SYNTHETIC:AND-ELIGIBILITY")
        def bad_not(row):
            root = row["condition_sets"]["eligibility"]["logical_roots"][0]
            root.update(operator="NOT", children=[])
        def bad_absence(row):
            row["condition_sets"]["exclusion"]["review_status"] = "NEEDS_REVIEW"
        for mutate, path in ((bad_not, ("condition_sets", "eligibility", "logical_roots")),
                             (bad_absence, ("condition_sets", "exclusion"))):
            with self.subTest(case=mutate.__name__):
                self.assert_mutation_rejected(valid, mutate, path)

    def test_operator_shapes_and_unreviewed_attachment_search_are_rejected(self):
        valid = self.synthetic_row("SYNTHETIC:AND-ELIGIBILITY")
        attachment = self.synthetic_row("SYNTHETIC:UNRESOLVED-ATTACHMENT")
        def target(row):
            return row["condition_sets"]["eligibility"]["conditions"][0]
        def bad_in(row):
            target(row)["value"] = "서울"
        def bad_between(row):
            target(row).update(operator="BETWEEN", value_type="RANGE",
                               value={"lower": {"value": 1, "inclusive": True}})
        def bad_attachment(row):
            target(row)["search_eligible"] = True
        def bad_synthetic_search(row):
            target(row)["search_eligible"] = True
        synthetic_logic = self.synthetic_row("SYNTHETIC:OR-EXCEPTION-PREFERENCE")
        for baseline, mutate in ((valid, bad_in), (valid, bad_between), (attachment, bad_attachment),
                                 (synthetic_logic, bad_synthetic_search)):
            with self.subTest(case=mutate.__name__):
                self.assert_mutation_rejected(baseline, mutate,
                    ("condition_sets", "eligibility", "conditions", 0))

    def test_normalized_snapshot_counts_remain_expected(self):
        report = _json(DATA_DIR / "normalization_report.json")
        self.assertEqual(self.counts, EXPECTED_COUNTS)
        for kind, count in EXPECTED_COUNTS.items():
            self.assertEqual(report["output_counts"][kind], count)

    @needs(*G2B_FULL)
    def test_g2b_snapshot_report_is_clean_and_samples_are_distinct(self):
        report = _json(G2B_DATA_DIR / "normalization_report.json")
        self.assertEqual(report["output_counts"], {"notices": 197180, "chunks": 32947, "issues": 0})
        self.assertEqual(report["output_counts_by_source"]["G2B"], {"notices": 192064, "chunks": 0})
        self.assertTrue(report["publishable"])
        self.assertEqual(report["schema_validation_errors"], 0)
        self.assertEqual(report["privacy_residual_findings"], 0)
        self.assertEqual(report["duplicate_notice_ids"], 0)
        self.assertEqual(report["chunks_without_notice"], 0)
        self.assertFalse(report["attachment_downloads_performed"])
        self.assertFalse(report["attachment_text_extraction_performed"])
        g2b_ids = [row["notice_id"] for row in self.actual if row["source_system"] == "G2B"]
        self.assertEqual(len(g2b_ids), 4)
        self.assertEqual(len(set(g2b_ids)), len(g2b_ids))


if __name__ == "__main__":
    unittest.main()
