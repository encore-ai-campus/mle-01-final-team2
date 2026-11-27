from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv/Scripts/python.exe"
CLI = ROOT / "tools/run_condition_llm_p4_pilot.py"


class P4PilotPreparationCliTests(unittest.TestCase):
    def run_cli(self, *args: str):
        return subprocess.run([str(PYTHON), str(CLI), *args], cwd=ROOT, text=True,
                              encoding="utf-8", capture_output=True, check=False, timeout=90)

    def test_cli_mock_end_to_end_uses_temp_ledger_and_no_network(self):
        result = self.run_cli("--offline-self-test")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["requests"], 10)
        self.assertTrue(report["strict_evaluation_path"])
        self.assertTrue(report["ledger_manifest_consistent"])
        self.assertEqual(report["actual_api_calls"], 0)

    def test_preflight_is_read_only_and_pins_the_expected_sample(self):
        run_out = ROOT / "data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3d5a_p4"
        self.assertFalse(run_out.exists())
        result = self.run_cli("--preflight")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["counts"], {"notices": 10, "gold_conditions": 62,
                                           "gold_logic_groups": 24, "gold_logic_relations": 71})
        self.assertEqual(report["api_calls"], 0)
        self.assertFalse(run_out.exists())

    def test_api_run_requires_explicit_execution_switch(self):
        result = self.run_cli("--run-first")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--authorize-api", result.stderr)


if __name__ == "__main__":
    unittest.main()
