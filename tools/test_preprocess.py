"""preprocess_notices 단위 시험. 실행: python tools/test_preprocess.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from preprocess_notices import chunk, clean_text, iso_date, norm_for_fidelity, norm_title_key, signals, split_org  # noqa: E402


class CleanTests(unittest.TestCase):
    def test_crlf_entities_nbsp_zero_width(self):
        self.assertEqual(clean_text("기술개발(R&amp;D)\r\n○ 지원 내용​  \r\n\r\n\r\n끝"), "기술개발(R&D)\n○ 지원 내용\n\n끝")

    def test_none_and_empty(self):
        self.assertIsNone(clean_text(None))
        self.assertIsNone(clean_text("  \n "))

    def test_does_not_change_content(self):
        s = "창업 7년 이내 기업(공고일 기준)\n※ 예비창업자 가능"
        self.assertEqual(clean_text(s), s)

    def test_fidelity_ignores_only_whitespace_and_entities(self):
        self.assertEqual(norm_for_fidelity("A&amp;B\r\n C"), norm_for_fidelity("A&B C"))
        self.assertNotEqual(norm_for_fidelity("7년 이내"), norm_for_fidelity("5년 이내"))

    def test_iso_date(self):
        self.assertEqual(iso_date("20261118"), "2026-11-18")
        self.assertEqual(iso_date("2026-11-18"), "2026-11-18")
        self.assertIsNone(iso_date("2026/11/18"))
        self.assertIsNone(iso_date(None))


class OrgTests(unittest.TestCase):
    def test_title_split_keeps_raw(self):
        o = split_org("경기도일자리재단 남부사업본부장")
        self.assertEqual(o["org_names"], ["경기도일자리재단"])
        self.assertEqual(o["org_role_titles"], ["남부사업본부장"])
        self.assertEqual(o["org_raw"], "경기도일자리재단 남부사업본부장")
        self.assertIn("title_split", o["org_flags"])

    def test_multiple_orgs(self):
        o = split_org("파주시, (재)경기테크노파크")
        self.assertEqual(o["org_names"], ["파주시", "(재)경기테크노파크"])
        self.assertIn("multiple_orgs", o["org_flags"])

    def test_single_token_org_not_split(self):
        self.assertEqual(split_org("서울경제진흥원")["org_names"], ["서울경제진흥원"])


class GroupTests(unittest.TestCase):
    def test_title_key_ignores_year_round_and_extension(self):
        self.assertEqual(norm_title_key("2026년 3차 입주기업 모집 (연장)"), norm_title_key("2025년 1차 입주기업 모집"))

    def test_signals(self):
        self.assertEqual(signals("입주기업 모집 (연장)"), ["연장"])


class ChunkTests(unittest.TestCase):
    def test_short_and_redaction_only_dropped_ids_unique(self):
        self.assertEqual(chunk("N", "S", "x", "API", "창업교육", {}), [])
        self.assertEqual(chunk("N", "S", "x", "API", "[REDACTED_CONTACT]" * 3, {}), [])
        long = "\n".join(["창업 7년 이내 기업을 대상으로 사업화 자금을 지원합니다."] * 60)
        cs = chunk("N", "S", "x", "API", long, {})
        self.assertGreater(len(cs), 1)
        self.assertEqual(len({c["chunk_id"] for c in cs}), len(cs))
        self.assertTrue(all(len(c["text"]) <= 920 for c in cs))


if __name__ == "__main__":
    unittest.main()
