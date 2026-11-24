from datetime import date
import unittest

from tools.collect_kstartup_year import date_status, parse_date, structure


class KStartupDateTests(unittest.TestCase):
    def test_parse_yyyymmdd_date(self):
        self.assertEqual(parse_date("20261124"), date(2026, 11, 24))

    def test_invalid_date_is_not_normalized_to_another_day(self):
        self.assertIsNone(parse_date("20260230"))

    def test_receipt_date_is_not_used_as_publication_date(self):
        row = {"pbanc_rcpt_bgng_dt": "20261124"}
        status, value, field = date_status(row, date(2025, 11, 24), date(2026, 11, 24))
        self.assertEqual((status, value, field), ("publication_date_unavailable", None, None))

    def test_explicit_registration_date_is_inclusive_at_window_edges(self):
        row = {"pbanc_reg_dt": "20251124"}
        self.assertEqual(date_status(row, date(2025, 11, 24), date(2026, 11, 24))[0], "in_window")

    def test_conflicting_registration_dates_need_review(self):
        row = {"pbanc_reg_dt": "20251124", "reg_ymd": "20251125"}
        status, value, field = date_status(row, date(2025, 11, 24), date(2026, 11, 24))
        self.assertEqual(status, "publication_date_conflict")
        self.assertIsNone(value)
        self.assertEqual(field, "pbanc_reg_dt,reg_ymd")

    def test_structure_keeps_unknown_publication_date_null(self):
        row = {"pbanc_sn": "sample-1", "biz_pbanc_nm": "sample", "pbanc_rcpt_bgng_dt": "20261124"}
        item, _ = structure(row, date(2025, 11, 24), date(2026, 11, 24))
        self.assertIsNone(item["published_date"])
        self.assertEqual(item["application_start"], "2026-11-24")
        self.assertEqual(item["publication_date_status"], "publication_date_unavailable")
