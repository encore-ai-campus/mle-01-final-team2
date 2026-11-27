"""goldset_judge_llm: 네트워크 없이 프롬프트와 후처리를 본다. 실행: python -m unittest tools.test_goldset_judge_llm"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goldset_judge_llm as J  # noqa: E402

NID = "KSTARTUP:171725"
HAS_PACKET = (J.G.PILOT / "packets" / "KSTARTUP_171725.txt").exists()  # 원문 패킷은 로컬 전용(git 제외)


class JudgeTests(unittest.TestCase):
    @unittest.skipUnless(HAS_PACKET, "원문 패킷 없음(로컬 전용)")
    def test_prompt_has_packet_and_profiles_not_human_labels(self):
        profs, assign = J.G.profiles(), J.assigned_profiles()
        u = J.user_prompt(NID, "B", profs, assign[NID])
        self.assertIn("전주시", u)
        self.assertIn(assign[NID][0], u)
        self.assertNotIn("labels/song", u)
        self.assertNotIn("labels/baek", u)

    def test_finish_marks_model_and_cleans_reasons(self):
        d = {"judgments": [{"profile_id": "P1", "overall": "NOT_ELIGIBLE", "reason_codes": ["SOURCE_CONFLICT"]},
                           {"profile_id": "P9", "overall": "ELIGIBLE"}]}
        out = J.finish(d, NID, "B", "m", ["P1"])
        self.assertEqual(out["reviewer"], "model:m")
        self.assertEqual([j["profile_id"] for j in out["judgments"]], ["P1"])  # 배정 밖 프로필은 버린다
        self.assertEqual(out["judgments"][0]["reason_codes"], [])
        self.assertIsNone(out["time_minutes"])

    def test_system_prompt_lists_allowed_values(self):
        s = J.system_prompt()
        for v in ("BOUNDARY_UNCLEAR", "NONE_OF", "YEAR_AGE", "applicant_type"):
            self.assertIn(v, s)


if __name__ == "__main__":
    unittest.main()
