from __future__ import annotations

import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from tests.local_data import LLM_P8, needs
from tools import run_condition_llm_openai_pilot_r2_norm_v2_p8 as p8


class P8PreparationTests(unittest.TestCase):
    @needs(*LLM_P8)
    def test_prepared_run_reuses_four_responses_and_reserves_six_notices(self):
        manifest = p8.read_json(p8.RUN_DIR / "manifest.json")
        ledger = p8.read_json(p8.RUN_DIR / "request_ledger.json")
        self.assertEqual(manifest["status"], "PREPARED_NO_API_CALLS")
        self.assertEqual(manifest["responses_reused"], 4)
        self.assertEqual(len(manifest["unexecuted_notice_ids"]), 6)
        self.assertEqual(manifest["api_call_count"], 0)
        self.assertEqual((ledger["limit"], ledger["used"], len(ledger["p8_attempts"])), (13, 7, 0))
        self.assertEqual(manifest["cumulative_used"], ledger["used"])
        self.assertEqual(manifest["remaining_request_count"], 6)

    @needs(*LLM_P8)
    def test_126490_technical_gate_passes_while_quality_is_zero(self):
        gate = p8.read_json(p8.RUN_DIR / "notice_03/technical_gate.json")
        report = p8.read_json(p8.RUN_DIR / "notice_03/attribute_replay_v2/replay_report.json")
        self.assertEqual(gate["status"], "PASS")
        self.assertEqual(gate["extraction_quality_state"], "ZERO_VALID_CANDIDATES")
        self.assertEqual(gate["valid_candidate_count"], 0)
        self.assertEqual(gate["rejected_count"], 3)
        self.assertTrue(gate["evidence_ok"])
        self.assertTrue(gate["incomplete_logic_preserved"])
        self.assertEqual(report["accepted_unreviewed_count"], 0)
        self.assertEqual(report["rejected_count"], 3)

    @needs(*LLM_P8)
    def test_source_response_and_ledger_fingerprints_are_unchanged(self):
        fp = p8.read_json(p8.RUN_DIR / "manifest.json")["fingerprint"]
        self.assertEqual(fp["source_manifest_sha256"], p8.digest(p8.SOURCE_DIR / "manifest.json"))
        self.assertEqual(fp["source_ledger_sha256"], p8.digest(p8.SOURCE_LEDGER))
        self.assertEqual(len(fp["existing_responses"]), 4)
        for response in fp["existing_responses"]:
            self.assertEqual(response["sha256"], p8.digest(p8.ROOT / response["path"]))

    def test_concurrent_offline_budget_reservations_are_capped_at_six(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            attempts = [{"request_ordinal": ordinal, "notice_id": f"prior:{ordinal}", "state": "COMPLETED"}
                        for ordinal in range(1, 8)]
            p8.write_json(root / "request_ledger.json", {"limit": 13, "used": 7, "attempts": attempts,
                "recovery_attempts": [], "p8_attempts": []})
            with patch.object(p8, "RUN_DIR", root):
                def reserve(index: int):
                    return p8.P8Budget(f"offline:{index}").consume()
                with ThreadPoolExecutor(max_workers=8) as pool:
                    results = list(pool.map(reserve, range(8)))
            ledger = p8.read_json(root / "request_ledger.json")
            self.assertEqual(sum(results), 6)
            self.assertEqual([a["request_ordinal"] for a in ledger["p8_attempts"]], list(range(8, 14)))
            self.assertEqual(ledger["used"], 13)


if __name__ == "__main__":
    unittest.main()
