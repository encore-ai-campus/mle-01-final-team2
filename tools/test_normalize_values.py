"""normalize_values 단위 시험. 실행: python -m unittest tools.test_normalize_values -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from normalize_values import applicant_structured, business_age_structured, founder_age_structured, term_patterns  # noqa: E402


class TestStructured(unittest.TestCase):
    def test_business_age_all_options_not_informative(self):
        v = business_age_structured("예비창업자,1년미만,2년미만,3년미만,5년미만,7년미만,10년미만")
        self.assertTrue(v["all_options"])
        self.assertFalse(v["filter_informative"])

    def test_business_age_upper(self):
        v = business_age_structured("예비창업자,3년미만")
        self.assertEqual((v["upper_exclusive_years"], v["pre_founder_allowed"], v["filter_informative"]), (3, True, True))
        v = business_age_structured("1년미만,2년미만,3년미만,5년미만,7년미만")
        self.assertEqual((v["upper_exclusive_years"], v["pre_founder_allowed"]), (7, False))

    def test_business_age_pre_only(self):
        v = business_age_structured("예비창업자")
        self.assertIsNone(v["upper_exclusive_years"])
        self.assertTrue(v["pre_founder_allowed"])

    def test_business_age_unknown_option(self):
        self.assertEqual(business_age_structured("15년미만")["parse_status"], "UNPARSED_OPTION")
        self.assertIsNone(business_age_structured(None))

    def test_founder_age_ranges(self):
        v = founder_age_structured("만 20세 이상 ~ 만 39세 이하")
        self.assertEqual(v["allowed_ranges_half_open"], [[20, 40]])
        v = founder_age_structured("만 20세 이상 ~ 만 39세 이하,만 40세 이상")
        self.assertEqual(v["allowed_ranges_half_open"], [[20, 200]])
        self.assertFalse(v["all_options"])
        v = founder_age_structured("만 20세 미만,만 20세 이상 ~ 만 39세 이하,만 40세 이상")
        self.assertTrue(v["all_options"])
        self.assertFalse(v["filter_informative"])

    def test_applicant(self):
        v = applicant_structured("일반기업,1인 창조기업")
        self.assertEqual(v["concept_ids"], ["APPLICANT_TYPE:1인 창조기업"])
        self.assertEqual(v["unmapped_options"], ["일반기업"])  # 일반기업은 중소기업과 동일시하지 않는다
        self.assertEqual(applicant_structured("외계인")["parse_status"], "UNPARSED_OPTION")


class TestTerms(unittest.TestCase):
    def test_small_company_not_inside_sme(self):
        pats = [p for cid, s, p in term_patterns() if s == "소기업"]
        self.assertTrue(pats)
        self.assertIsNone(pats[0].search("중소기업"))
        self.assertIsNotNone(pats[0].search("소기업 및 소상공인"))


if __name__ == "__main__":
    unittest.main()
