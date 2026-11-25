from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from tools.normalize_support_data import (
    load_validator,
    normalize_g2b_archive,
    normalize_g2b_notice,
    normalize_notice,
    pii_findings,
    schema_errors,
    write_jsonl,
)

ROOT = Path(__file__).resolve().parents[1]
NOTICE_VALIDATOR = load_validator(ROOT / "schemas/support-data/support-notice-v1.schema.json")


def g2b_row(**overrides):
    row = {
        "notice_id": "R26TEST-000", "source_system": "G2B", "bid_notice_no": "R26TEST",
        "bid_notice_ord": "000", "category": "용역", "notice_kind": "등록공고",
        "service_division": "일반용역", "procurement_large": "기타", "procurement_mid": "기타",
        "procurement_detail": "정보서비스", "industry_limit_yn": "Y", "participation_limit_yn": "N",
        "title": "시험 용역 입찰", "notice_org": "시험기관", "demand_org": "수요기관",
        "notice_at": "2026-11-20 09:00:00", "close_at": "2026-12-01 10:00:00",
        "open_at": "2026-12-01 11:00:00", "contract_method": "제한경쟁", "award_method": "적격심사",
        "estimated_price": "50000000", "is_negotiated": False, "is_cancelled": False,
        "license_status": "observed",
        "licenses": [{"group": "시험", "name": "시험업 면허", "permitted_industries": "업종 1"}],
        "region_status": "observed", "regions": ["서울특별시"], "region_basis": "본사소재지",
        "documents": [{"name": "공고문.pdf", "source": "첨부", "url": "https://www.g2b.go.kr/file/1"}],
        "detail_url": "https://www.g2b.go.kr/notice/1", "contact_name": "홍길동",
        "contact_phone": "02-1234-5678", "contact_email": None, "demand_contact_email": None,
        "executor_name": "김철수",
    }
    row.update(overrides)
    return row


class G2BNormalizationTests(unittest.TestCase):
    def test_g2b_specific_fields_are_preserved_and_agency_contact_kept_and_person_names_removed(self):
        issues = []
        normalized, _ = normalize_g2b_notice(g2b_row(), issues)
        self.assertEqual(schema_errors(normalized, NOTICE_VALIDATOR), [])
        self.assertEqual(normalized["notice_type"], "PROCUREMENT_BID")
        self.assertEqual(normalized["source"]["source_system"], "G2B")
        self.assertEqual(normalized["source"]["source_id"], "R26TEST-000")
        self.assertEqual(normalized["notice_id"], "G2B:R26TEST:000")
        g2b = normalized["source_metadata"]["source_specific"]["G2B"]
        self.assertEqual(g2b["licenses"][0]["permitted_industries"], "업종 1")
        self.assertEqual(g2b["regions"], ["서울특별시"])
        self.assertEqual(g2b["documents"][0]["url_status"], "VALID")
        self.assertEqual(normalized["urls"]["url_status"]["notice_url"], "VALID")
        self.assertEqual(normalized["attachments"]["count"], 1)
        self.assertEqual(normalized["attachments"]["extraction_status"], "UNKNOWN")
        self.assertEqual(normalized["condition_texts"]["eligibility"]["availability"], "NOT_COLLECTED")
        phone = next(c for c in normalized["contacts"] if c["type"] == "PHONE")
        self.assertEqual(phone["classification"], "OFFICIAL_BUSINESS")  # 기관 연락처는 보존한다(담당자 이름만 제거)
        self.assertEqual(phone["value"], "02-1234-5678")
        serialized = json.dumps(normalized, ensure_ascii=False)
        self.assertNotIn("홍길동", serialized)
        self.assertNotIn("김철수", serialized)
        self.assertEqual(pii_findings(normalized), [])
        self.assertFalse(issues)

    def test_nonofficial_document_url_is_withheld(self):
        issues = []
        normalized, _ = normalize_g2b_notice(
            g2b_row(documents=[{"name": "x.pdf", "source": "첨부", "url": "http://example.net/x"}]), issues
        )
        document = normalized["source_metadata"]["source_specific"]["G2B"]["documents"][0]
        self.assertIsNone(document["url"])
        self.assertEqual(document["url_status"], "INVALID")
        self.assertIn("INVALID_G2B_DOCUMENT_URL", [issue["issue"] for issue in issues])

    def test_archive_builds_combined_snapshot_without_changing_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            support_dir = root / "support"
            support_dir.mkdir()
            support, _ = normalize_notice({
                "notice_id": "BIZINFO:1", "source_system": "BIZINFO", "source_id": "1", "title": "지원사업",
            }, [])
            write_jsonl(support_dir / "notices.jsonl", [support])
            write_jsonl(support_dir / "chunks.jsonl", [])
            g2b_dir = root / "g2b"
            month = g2b_dir / "2026-11"
            month.mkdir(parents=True)
            (month / "notices.jsonl").write_text(json.dumps(g2b_row(), ensure_ascii=False) + "\n", encoding="utf-8")
            for filename, header, row in (
                ("notices.csv", ["notice_id"], ["R26TEST-000"]),
                ("licenses.csv", ["notice_id"], ["R26TEST-000"]),
                ("regions.csv", ["notice_id"], ["R26TEST-000"]),
            ):
                with (month / filename).open("w", encoding="utf-8", newline="") as stream:
                    writer = csv.writer(stream)
                    writer.writerow(header)
                    writer.writerow(row)
            with (g2b_dir / "manifest.csv").open("w", encoding="utf-8", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=["month", "notices.jsonl_rows", "notices.csv_rows", "licenses.csv_rows", "regions.csv_rows"])
                writer.writeheader()
                writer.writerow({"month": "2026-11", "notices.jsonl_rows": 1, "notices.csv_rows": 1, "licenses.csv_rows": 1, "regions.csv_rows": 1})
            input_bytes = (month / "notices.jsonl").read_bytes()
            output = root / "combined"
            report = normalize_g2b_archive(g2b_dir, support_dir, output)
            rows = [json.loads(line) for line in (output / "notices.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertTrue(report["publishable"])
            self.assertEqual(len(rows), 2)
            self.assertEqual({row["notice_type"] for row in rows}, {"SUPPORT_PROGRAM", "PROCUREMENT_BID"})
            self.assertEqual(report["output_counts_by_source"]["G2B"], {"notices": 1, "chunks": 0})
            self.assertEqual(report["output_counts"]["chunks"], 0)
            self.assertEqual((month / "notices.jsonl").read_bytes(), input_bytes)
            self.assertFalse(report["attachment_downloads_performed"])
            self.assertFalse(report["attachment_text_extraction_performed"])
            self.assertFalse(report["database_writes_performed"])


if __name__ == "__main__":
    unittest.main()
