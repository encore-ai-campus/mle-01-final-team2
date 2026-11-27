from __future__ import annotations

import unittest

from tools import run_condition_llm_openai_pilot_r2_norm_v2 as base
from tools import run_condition_llm_openai_pilot_r2_norm_v2_recovery as recovery


class RecoveryPreparationTests(unittest.TestCase):
    def test_p7_branch_keeps_approved_limit_and_preserves_zero_candidate_block(self):
        manifest = recovery.read_json(recovery.RUN_DIR / "manifest.json")
        ledger = recovery.read_json(recovery.RUN_DIR / "request_ledger.json")
        self.assertEqual(manifest["status"], "RECOVERY_BLOCKED")
        self.assertTrue(manifest["budget_increase_approved"])
        self.assertEqual((manifest["active_limit"], manifest["cumulative_used"], manifest["active_remaining"]),
                         (13, 7, 6))
        self.assertEqual(ledger["limit"], 13)
        self.assertEqual(ledger["used"], 7)
        self.assertEqual(len(ledger["recovery_attempts"]), 2)

    def test_existing_success_and_failure_are_referenced_without_changing_source(self):
        manifest = recovery.read_json(recovery.RUN_DIR / "manifest.json")
        source_manifest = recovery.read_json(recovery.SOURCE_DIR / "manifest.json")
        source_ledger = recovery.read_json(recovery.SOURCE_LEDGER)
        self.assertEqual(manifest["fingerprint"]["blocked_manifest_sha256"], recovery.digest(recovery.SOURCE_DIR / "manifest.json"))
        self.assertEqual(manifest["fingerprint"]["blocked_ledger_sha256"], recovery.digest(recovery.SOURCE_LEDGER))
        self.assertEqual(source_manifest["status"], "REMAINING_BLOCKED")
        self.assertEqual(source_ledger["used"], 5)
        self.assertEqual(recovery.digest(recovery.RUN_DIR / "notice_01/raw_llm_responses.jsonl"),
                         recovery.digest(recovery.SOURCE_DIR / "notice_01/raw_llm_responses.jsonl"))
        self.assertTrue((recovery.RUN_DIR / "provenance/prior_failed_attempt_notice_02_ordinal_5/raw_llm_responses.jsonl").is_file())

    def test_unapproved_recovery_budget_cannot_reserve_in_isolated_ledger(self):
        import tempfile
        from pathlib import Path
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "request_ledger.json"
            recovery.write_json(path, {"limit": 13, "used": 7, "recovery_attempts": [],
                "lineage": {"budget_increase_approved": False}})
            with patch.object(recovery, "RUN_DIR", Path(tmp)):
                budget = recovery.RecoveryBudget("offline-test")
                self.assertFalse(budget.consume())
            self.assertEqual(recovery.read_json(path)["used"], 7)

    def test_old_blocked_run_and_parent_gate_are_unchanged(self):
        before = {path: base.digest(path) for path in (base.PARENT_MANIFEST, base.PARENT_LEDGER,
                                                        base.PARENT_GATE, recovery.SOURCE_DIR / "manifest.json",
                                                        recovery.SOURCE_LEDGER)}
        self.assertEqual(base.read_json(base.PARENT_MANIFEST)["status"], "LEAD_BLOCKED")
        self.assertEqual(recovery.read_json(recovery.SOURCE_DIR / "manifest.json")["status"], "REMAINING_BLOCKED")
        self.assertEqual(before, {path: base.digest(path) for path in before})


if __name__ == "__main__":
    unittest.main()
