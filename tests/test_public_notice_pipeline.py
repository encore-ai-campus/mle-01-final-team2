from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT))
from tests.local_data import API_SAMPLES, needs  # noqa: E402
from public_notice_pipeline import (  # noqa: E402
    PrivacyReport, condition_search_approved, sanitize_tree, scope_matches, searchable_text,
)


class PrivacyAndReviewTests(unittest.TestCase):
    def test_common_privacy_mask_preserves_support_requirements(self):
        report = PrivacyReport()
        clean = sanitize_tree({"application_method": "온라인 신청", "body": "담당자: 홍길동 (010-1234-5678), test@example.org"}, report)
        self.assertEqual(clean["application_method"], "온라인 신청")
        self.assertNotIn("홍길동", clean["body"])
        self.assertNotIn("010-1234-5678", clean["body"])
        self.assertNotIn("test@example.org", clean["body"])
        self.assertEqual((report.email_count, report.phone_count, report.contextual_name_count), (1, 1, 1))

    def test_signed_download_tokens_are_removed(self):
        report = PrivacyReport()
        clean = sanitize_tree({"source_url": "https://example.org/file?downloadToken=secret123&x=1"}, report)
        self.assertNotIn("secret123", clean["source_url"])
        self.assertEqual(report.url_token_count, 1)

    def test_missing_review_status_is_denied(self):
        self.assertFalse(condition_search_approved({"text": "조건"}))
        self.assertFalse(condition_search_approved({"review_status": "approved", "text": "조건"}))
        self.assertTrue(condition_search_approved({
            "review_status": "approved", "reviewed_at": "2026-11-24T10:00:00+09:00",
            "reviewed_by": "reviewer", "review_required": False, "text": "조건",
        }))

    def test_only_approved_conditions_enter_search_text(self):
        result = searchable_text("API 원문", [
            {"review_status": "unreviewed", "text": "미검수 조건"},
            {"review_status": "approved", "reviewed_at": "now", "reviewed_by": "user", "review_required": False, "text": "검수 조건"},
        ])
        self.assertIn("API 원문", result)
        self.assertIn("검수 조건", result)
        self.assertNotIn("미검수 조건", result)

    def test_region_scope_requires_explicit_evidence_and_correct_ancestor(self):
        seongdong = {"KR:REGION:1100000000", "KR:REGION:1120000000", "KR:REGION:1121500000"}
        self.assertTrue(scope_matches("nationwide", [], seongdong))
        self.assertTrue(scope_matches("confirmed", ["KR:REGION:4719000000"], {"KR:REGION:4719000000"}))
        self.assertTrue(scope_matches("confirmed", ["KR:REGION:1100000000", "KR:REGION:1121500000"], seongdong, "AND"))
        self.assertFalse(scope_matches("confirmed", ["KR:REGION:1100000000", "KR:REGION:4719000000"], seongdong, "AND"))
        self.assertFalse(scope_matches("confirmed", ["KR:REGION:4719000000"], seongdong))
        self.assertFalse(scope_matches("unknown", [], seongdong))
        self.assertFalse(scope_matches("review_required", ["KR:REGION:1100000000"], seongdong))


@needs(API_SAMPLES)
class RealSamplePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.graph = json.loads((ROOT / "api_samples/normalized/neo4j_import.json").read_text(encoding="utf-8"))
        cls.chunks = json.loads((ROOT / "api_samples/normalized/supabase_public_notice_chunks.json").read_text(encoding="utf-8"))

    def test_three_real_sources_are_present_and_search_gates_are_explicit(self):
        self.assertEqual(len(self.graph["notices"]), 90)
        self.assertEqual({x["source_system"] for x in self.graph["notices"]}, {"G2B", "KSTARTUP", "BIZINFO"})
        self.assertEqual(len(self.chunks), 90)
        self.assertTrue(all(x.get("search_review_status") in {"source_verified", "approved"} for x in self.chunks))
        self.assertTrue(all(x.get("privacy_status") == "cleared" for x in self.chunks))
        self.assertFalse(any("자동 추출 후보" in x["chunk_text"] for x in self.chunks))
        self.assertFalse(any("eligibility_candidate_text" in x for x in self.chunks))

    def test_real_text_and_metadata_have_no_detected_pii(self):
        report = PrivacyReport()
        sanitize_tree(self.graph, report)
        sanitize_tree(self.chunks, report)
        candidate_path = ROOT / "api_samples/normalized/condition_candidates.json"
        sanitize_tree(json.loads(candidate_path.read_text(encoding="utf-8")), report)
        self.assertEqual((report.email_count, report.phone_count, report.contextual_name_count, report.ambiguous_context_count), (0, 0, 0, 0))

    def test_unreviewed_conditions_are_quarantined_from_search_files(self):
        candidates = json.loads((ROOT / "api_samples/normalized/condition_candidates.json").read_text(encoding="utf-8"))
        self.assertTrue(candidates)
        self.assertTrue(all(c.get("review_status") == "unreviewed" and c.get("searchable") is False for c in candidates))
        self.assertFalse(any("pdf_conditions_json" in n or "eligibility_candidate_text" in n for n in self.graph["notices"]))
        self.assertFalse(any("후보" in c["chunk_text"] for c in self.chunks))

    def test_region_hierarchy_and_bizinfo_region_fail_closed(self):
        region_ids = {r["region_id"] for r in self.graph["regions"]}
        relations = self.graph["relationships"]
        self.assertIn("KR:NATIONWIDE", region_ids)
        self.assertTrue(any(r["type"] == "HAS_SUBREGION" and r["from_id"] == "KR:NATIONWIDE" and r["to_id"].startswith("KR:REGION:") for r in relations))
        seongdong = next(r for r in self.graph["regions"] if r["name"] == "성동구")
        seoul = next(r for r in self.graph["regions"] if r["level"] == "SIDO" and r["name"].startswith("서울"))
        self.assertTrue(any(r["type"] == "HAS_SUBREGION" and r["from_id"] == seoul["region_id"] and r["to_id"] == seongdong["region_id"] for r in relations))
        gumi = next(n for n in self.graph["notices"] if n["notice_id"] == "BIZINFO:PBLN_000000000120707")
        self.assertEqual(gumi["region_scope_status"], "unknown")
        self.assertFalse(any(r["type"] == "TARGETS_REGION" and r["from_id"].startswith("BIZINFO:") for r in relations))

    def test_source_region_adapter_requires_explicit_fields(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import transform_public_notices as transform
        regions, _, aliases = transform.make_region_table()
        ids, _, _ = transform.source_region_ids("G2B", {"rgnLmtBidLocplcJdgmBssNm": "서울특별시"}, aliases, regions)
        self.assertEqual(ids, ["KR:REGION:1100000000"])
        ids, _, _ = transform.source_region_ids("G2B", {"rgnLmtBidLocplcJdgmBssNm": "전국"}, aliases, regions)
        self.assertEqual(ids, ["KR:NATIONWIDE"])
        ids, _, _ = transform.source_region_ids("BIZINFO", {"hashtags": "서울, 경기"}, aliases, regions)
        self.assertEqual(ids, [])


if __name__ == "__main__":
    unittest.main()
