import json
import tempfile
import unittest
from pathlib import Path

from tools.normalize_support_data import (
    normalize_chunk,
    normalize_notice,
    normalize_snapshot,
    pii_findings,
    load_validator,
    schema_errors,
)
from tools.public_notice_pipeline import PrivacyReport

ROOT = Path(__file__).resolve().parents[1]
NOTICE_VALIDATOR = load_validator(ROOT / "schemas/support-data/support-notice-v1.schema.json")
CHUNK_VALIDATOR = load_validator(ROOT / "schemas/support-data/support-chunk-v1.schema.json")


def validate_notice(record):
    return schema_errors(record, NOTICE_VALIDATOR)


def validate_chunk(record):
    return schema_errors(record, CHUNK_VALIDATOR)


class SupportDataNormalizationTests(unittest.TestCase):
    def test_v1_schema_files_are_valid_json(self):
        root = Path(__file__).resolve().parents[1]
        notice_schema = json.loads((root / "schemas/support-data/support-notice-v1.schema.json").read_text(encoding="utf-8"))
        chunk_schema = json.loads((root / "schemas/support-data/support-chunk-v1.schema.json").read_text(encoding="utf-8"))
        self.assertIn("contacts", notice_schema["properties"])
        self.assertIn("search_eligible", chunk_schema["properties"])

    def notice(self, source="KSTARTUP"):
        return {
            "notice_id": f"{source}:1", "source_system": source, "source_id": "1",
            "title": "샘플 공고", "title_raw": "샘플 공고", "detail_url": "https://www.k-startup.go.kr/notice/1",
            "published_at": None, "source_updated_at": None, "fetched_at": "2026-11-24",
            "application_start": "2026-11-01", "application_end": "2026-11-30",
            "deadline_at": "2026-11-30T23:59:59+09:00", "apply_status_kind": "DATE_RANGE",
            "apply_url": None, "guide_url": "https://www.k-startup.go.kr/guide/1",
            "apply_methods": {"aply_mthd_onli_rcpt_istc": "온라인 신청 https://apply.example.org/"},
            "org_raw": "기관", "org_names": ["기관"], "org_role_titles": [], "org_flags": [],
            "category_major": "기술", "category_medium": None, "region_raw": "서울",
            "region_concept_ids": ["R1"], "region_basis": "source_text", "region_scope_hint": None,
            "region_tags_hint": [], "structured": {"business_age_raw": "3년 이내", "founder_age_raw": None,
                "applicant_target_raw": "창업기업"}, "eligibility_text": "신청 대상 안내 담당자 홍길동 010-1234-5678 test@example.com",
            "exclusion_text": None, "preferred_text": None, "body_text": "본문", "support_text": None,
            "evaluation_text": None, "contact_phone_raw": "010-1234-5678", "contact_text": None,
            "attachments": {"count": None, "text_extracted": 0, "preview_only": None, "note": "미수집"},
        }

    def test_timestamp_precision_and_no_fabricated_timezone(self):
        record, _ = normalize_notice(self.notice(), [])
        self.assertEqual(record["timestamps"]["fetched_at"]["precision"], "DATE")
        self.assertIsNone(record["timestamps"]["fetched_at"]["timezone"])
        deadline = record["application_period"]["deadline"]
        self.assertEqual((deadline["value"], deadline["precision"], deadline["status"]),
                         ("2026-11-30", "DATE", "DERIVED_FROM_END_DATE"))
        self.assertEqual(validate_notice(record), [])

    def test_official_urls_require_https_and_source_domain(self):
        row = self.notice()
        row["detail_url"] = "http://www.k-startup.go.kr/notice/1"
        row["guide_url"] = "https://example.net/guide"
        row["apply_url"] = "https://apply.example.net/form"
        record, _ = normalize_notice(row, [])
        self.assertEqual(record["urls"]["url_status"],
                         {"apply_url": "VALID", "guide_url": "INVALID", "notice_url": "INVALID"})

    def test_source_semantics_and_absence_are_preserved(self):
        source_row = self.notice("BIZINFO")
        source_row.pop("exclusion_text")
        source_row["structured"] = {"target_group_text": "기업"}
        record, _ = normalize_notice(source_row, [])
        self.assertEqual(record["timestamps"]["published_at"]["status"], "EMPTY")
        self.assertEqual(record["urls"]["guide_url"], "https://www.k-startup.go.kr/guide/1")
        self.assertEqual(record["field_availability"]["condition_texts.exclusion"], "NOT_COLLECTED")
        self.assertEqual(record["field_availability"]["structured.business_age_raw"], "NOT_COLLECTED")
        self.assertEqual(record["attachments"]["count"], None)
        self.assertEqual(record["attachments"]["extraction_status"], "NOT_ATTEMPTED")
        self.assertEqual(record["contacts"][0]["classification"], "UNCLASSIFIED")
        self.assertIsNone(record["contacts"][0]["value"])
        self.assertEqual(record["contacts"][0]["review_status"], "NEEDS_REVIEW")
        self.assertEqual(record["urls"]["apply_methods"][0]["urls"][0]["purpose"], "UNCLASSIFIED")

    def test_contact_policy_preserves_only_explicit_official_context(self):
        row = self.notice()
        row["contact_text"] = (
            "\\uB300\\uD45C\\uC804\\uD654 02-1234-5678; "
            "\\uC0AC\\uC5C5\\uBB38\\uC758 office@example.org; "
            "\\uB2F4\\uB2F9\\uC790 \\uD64D\\uAE38\\uB3D9 \\uD734\\uB300\\uC804\\uD654 010-9999-8888"
        ).encode("ascii").decode("unicode_escape")
        row["contact_phone_raw"] = "010-7777-6666"
        record, _ = normalize_notice(row, [])
        contacts = record["contacts"]
        official = [contact for contact in contacts if contact["classification"] == "OFFICIAL_BUSINESS"]
        personal = [contact for contact in contacts if contact["classification"] == "PERSONAL"]
        unclassified = [contact for contact in contacts if contact["classification"] == "UNCLASSIFIED"]
        self.assertEqual({contact["value"] for contact in official}, {"02-1234-5678", "office@example.org"})
        self.assertEqual(len(personal), 1)
        self.assertIsNone(personal[0]["value"])
        self.assertEqual(personal[0]["review_status"], "REDACTED")
        self.assertEqual(len(unclassified), 1)
        self.assertIsNone(unclassified[0]["value"])
        self.assertEqual(unclassified[0]["review_status"], "NEEDS_REVIEW")
        self.assertEqual(pii_findings(record), [])

    def test_kstartup_contact_department_pair_is_business_context(self):
        row = self.notice("KSTARTUP")
        row["operating_dept"] = "SME Support Department"
        row["contact_phone_raw"] = "010-7777-6666"
        record, _ = normalize_notice(row, [])
        contact = next(contact for contact in record["contacts"] if contact["type"] == "PHONE")
        self.assertEqual(contact["classification"], "OFFICIAL_BUSINESS")
        self.assertEqual(contact["classification_basis"], "SOURCE_CONTACT_DEPARTMENT_PAIR")
        self.assertEqual(contact["department"], "SME Support Department")
        self.assertEqual(contact["value"], "010-7777-6666")

    def test_contact_payload_is_removed_from_non_contact_fields_and_scanned(self):
        row = self.notice()
        row["body_text"] = "\\uB2F4\\uB2F9\\uC790 \\uD64D\\uAE38\\uB3D9".encode("ascii").decode("unicode_escape")
        record, _ = normalize_notice(row, [])
        self.assertEqual(pii_findings(record), [])
        self.assertNotIn("010-1234-5678", json.dumps(record, ensure_ascii=False))
        self.assertNotIn("test@example.com", json.dumps(record, ensure_ascii=False))
        self.assertNotIn("홍길동", json.dumps(record, ensure_ascii=False))

    def test_chunk_sections_differ_and_attachment_is_quarantined(self):
        report = PrivacyReport()
        base = {"chunk_id": "c1", "notice_id": "n1", "source_system": "BIZINFO", "origin": "API",
                "text": "text 02-1234-5678 office@example.org", "content_hash": "abc", "region_concept_ids": [], "is_open": True}
        summary = normalize_chunk({**base, "section": "title_summary"}, report)
        body = normalize_chunk({**base, "section": "title_body"}, report)
        attachment = normalize_chunk({**base, "section": "att_eligibility@f0-1", "origin": "ATTACHMENT"}, report)
        self.assertEqual(summary["section"], "NOTICE_SUMMARY")
        self.assertEqual(body["section"], "NOTICE_BODY")
        self.assertEqual(attachment["section"], "ATTACHMENT_ELIGIBILITY")
        self.assertFalse(attachment["search_eligible"])
        self.assertNotIn("02-1234-5678", summary["text"])
        self.assertNotIn("office@example.org", summary["text"])
        self.assertEqual(validate_chunk(attachment), [])

    def test_snapshot_counts_ids_and_repeatability(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "input"
            source.mkdir()
            n = self.notice()
            c = {"chunk_id": "KSTARTUP:1#title_body:0", "notice_id": "KSTARTUP:1", "source_system": "KSTARTUP",
                 "section": "title_body", "origin": "API", "text": "공고 본문", "content_hash": "hash",
                 "is_open": None, "region_concept_ids": None}
            (source / "notices.jsonl").write_text(json.dumps(n, ensure_ascii=False) + "\n", encoding="utf-8")
            (source / "chunks.jsonl").write_text(json.dumps(c, ensure_ascii=False) + "\n", encoding="utf-8")
            out1, out2 = root / "one", root / "two"
            first = normalize_snapshot(source, out1)
            second = normalize_snapshot(source, out2)
            self.assertEqual(first["output_counts"], {"notices": 1, "chunks": 1, "issues": first["output_counts"]["issues"]})
            self.assertEqual(first["schema_validation_errors"], 0)
            self.assertEqual(first["privacy_residual_findings"], 0)
            self.assertEqual((out1 / "notices.jsonl").read_bytes(), (out2 / "notices.jsonl").read_bytes())
            self.assertEqual((out1 / "chunks.jsonl").read_bytes(), (out2 / "chunks.jsonl").read_bytes())


if __name__ == "__main__":
    unittest.main()
