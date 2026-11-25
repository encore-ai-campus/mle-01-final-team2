from __future__ import annotations

import json
import sys
import tempfile
import unittest
import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.build_condition_gold_review import OUTPUT, build, read_jsonl
from tools.ingest_condition_gold_reviews import ingest, make_id, validate_review_packets
from tools.normalize_support_data import pii_findings


class ConditionGoldReviewTests(unittest.TestCase):
    def test_development_evaluation_packets_are_separate_and_evaluation_is_blind(self):
        dev = read_jsonl(OUTPUT / "development/condition_review.jsonl")
        ev = read_jsonl(OUTPUT / "evaluation/condition_review.jsonl")
        dev_logic = read_jsonl(OUTPUT / "development/logic_review.jsonl")
        ev_logic = read_jsonl(OUTPUT / "evaluation/logic_review.jsonl")
        self.assertEqual((len(dev), len(ev), len(dev_logic), len(ev_logic)), (30, 20, 30, 20))
        self.assertFalse({r["notice_id"] for r in dev} & {r["notice_id"] for r in ev})
        self.assertTrue(all("existing_candidates" in row for row in dev))
        self.assertTrue(all("existing_candidates" not in row for row in ev))
        self.assertTrue(all("existing_logic_roots" in row for row in dev_logic))
        self.assertTrue(all("existing_logic_roots" not in row for row in ev_logic))
        with (OUTPUT / "evaluation/condition_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            self.assertNotIn("existing_candidates", next(csv.reader(stream)))
        with (OUTPUT / "evaluation/logic_review.csv").open(encoding="utf-8-sig", newline="") as stream:
            header = next(csv.reader(stream))
            self.assertFalse(any(name.startswith("existing_") for name in header))
        self.assertTrue(all(row["review_status"] == "UNREVIEWED" and row["adjudication_status"] == "PENDING" for row in dev + ev))
        self.assertTrue(all(row["whole_notice_conditions_complete"] is False for row in dev + ev))

    def test_review_packets_validate_and_privacy_scan_clean(self):
        for split in ("development", "evaluation"):
            directory = OUTPUT / split
            conditions = read_jsonl(directory / "condition_review.jsonl")
            logic = read_jsonl(directory / "logic_review.jsonl")
            _, _, report = validate_review_packets(OUTPUT, split)
            self.assertTrue(report["all_rows_schema_valid"])
            for row in conditions + logic:
                self.assertEqual(pii_findings(row), [], row["notice_id"])

    def test_gold_ids_are_stable_and_independent_namespace(self):
        a = make_id("NOTICE:1", "ELIGIBILITY", 0, 4, "기업 조건")
        b = make_id("NOTICE:1", "ELIGIBILITY", 0, 4, "기업 조건")
        c = make_id("NOTICE:1", "EXCLUSION", 0, 4, "기업 조건")
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertTrue(a.startswith("GOLD:"))

    def test_pending_review_ingestion_emits_no_gold_truth(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            for split in ("development", "evaluation"):
                result = ingest(root, split)
                self.assertEqual(result["reviewed_condition_records"], 0)
                self.assertEqual(result["reviewed_logic_records"], 0)
                self.assertEqual(read_jsonl(root / split / "reviewed_condition_gold.jsonl"), [])
                self.assertEqual(read_jsonl(root / split / "reviewed_logic_gold.jsonl"), [])
        self.assertTrue((OUTPUT / "baseline_manifest.json").exists())

    def test_review_ingest_rejects_cross_split_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            build(root)
            dev = read_jsonl(root / "development/condition_review.jsonl")
            evaluation = read_jsonl(root / "evaluation/condition_review.jsonl")
            evaluation[0]["notice_id"] = dev[0]["notice_id"]
            with (root / "evaluation/condition_review.jsonl").open("w", encoding="utf-8") as stream:
                for row in evaluation:
                    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            with self.assertRaisesRegex(ValueError, "overlap"):
                validate_review_packets(root, "development")


if __name__ == "__main__":
    unittest.main()
