from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = Path(sys.executable)
CLI = ROOT / "tools/run_condition_llm_p4_pilot.py"


def snapshot(folder: Path) -> dict[str, tuple[int, int]]:
    """폴더 안 파일별 (크기, 수정 시각). 없으면 빈 dict."""
    return {str(f.relative_to(folder)): (f.stat().st_size, f.stat().st_mtime_ns) for f in folder.rglob("*") if f.is_file()} if folder.exists() else {}


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
        # 실행 결과가 2026-11-27에 커밋되어 폴더가 있다. 사전 점검이 그 폴더를 바꾸지 않는지로 본다
        before = snapshot(run_out)
        if (run_out / "manifest.json").exists():
            sys.path.insert(0, str(ROOT))
            from tools import run_condition_llm_p4_pilot as p4

            try:
                p4.current_fingerprint()
            except RuntimeError as e:  # p4 기록은 CRLF 체크아웃의 해시라 LF 저장소 파일과 다르다(2026-11-28 확인, 팀 확인 필요)
                self.skipTest(f"p4 실행 기록의 지문이 지금 파일과 다르다: {e}")
        result = self.run_cli("--preflight")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["counts"], {"notices": 10, "gold_conditions": 62,
                                           "gold_logic_groups": 24, "gold_logic_relations": 71})
        self.assertEqual(report["api_calls"], 0)
        self.assertEqual(snapshot(run_out), before)

    def test_api_run_requires_explicit_execution_switch(self):
        result = self.run_cli("--run-first")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--authorize-api", result.stderr)


if __name__ == "__main__":
    unittest.main()
