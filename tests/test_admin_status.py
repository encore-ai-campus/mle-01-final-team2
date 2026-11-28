"""M-01 `GET /api/admin/status` 시험. 가짜 공고·큐·보고서만 쓴다.

실행: python -m unittest tests.test_admin_status -v
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "pydantic_settings"))

NOTICES = [
    {"notice_id": "B:1", "source": "BIZINFO", "fetched_at": "2026-11-24T09:16:01+09:00", "text_requirements": "reviewed"},
    {"notice_id": "B:2", "source": "BIZINFO", "fetched_at": "2026-11-23T08:00:00+09:00"},
    {"notice_id": "K:1", "source": "KSTARTUP", "fetched_at": "2026-11-24", "text_requirements": "unparsed"},
]
RAW = {"B:1": {"period_status": "OPEN_WITH_DEADLINE"}, "B:2": {"period_status": "OPEN_NO_DATE_DEADLINE"},
       "K:1": {"period_status": "CLOSED"}, "X:9": {"period_status": "CLOSED"}}  # 엔진에 없는 공고는 세지 않는다
QUEUE = [{"review_status": "UNREVIEWED"}, {"review_status": "NEEDS_REVIEW"}, {"review_status": "VERIFIED"}]


class BuildStatusTest(unittest.TestCase):
    def build(self, **kw):
        from api.services.admin_status import build_status
        from api.services.meta import KST

        args = {"queue_rows": QUEUE, "raw": RAW, "cleaning_report": {"inputs": {"bizinfo_run": "R1", "kstartup_raw": "R2"}},
                "extraction": {"failed": 2, "by_status": {"DISTRIBUTION_DOC_UNSUPPORTED": 2}, "reports": 1},
                "now": datetime(2026, 11, 28, tzinfo=KST)}
        return build_status(NOTICES, **{**args, **kw})

    def test_sources_queues_period(self):
        s = self.build()
        by = {x["source"]: x for x in s["sources"]}
        self.assertEqual(by["BIZINFO"]["last_success_at"], "2026-11-24T09:16:01+09:00")
        self.assertEqual((by["BIZINFO"]["last_run"]["fetched"], by["BIZINFO"]["last_run"]["run_id"]), (2, "R1"))
        self.assertIsNone(by["BIZINFO"]["last_run"]["new"])  # 실행 기록 표가 없어 모른다
        self.assertFalse(by["G2B"]["in_service"])
        self.assertIsNone(by["G2B"]["last_run"])
        self.assertEqual(s["queues"], {"review_pending": 2, "review_done": 1, "review_total": 3, "reprocess_pending": 2,
                                       "reprocess_by_status": {"DISTRIBUTION_DOC_UNSUPPORTED": 2}, "unparsed": 2})
        self.assertEqual(s["period_status"], {"open_with_deadline": 1, "open_no_date": 1, "closed": 1, "other": 0})

    def test_missing_files_become_null(self):
        s = self.build(queue_rows=None, raw={}, cleaning_report=None, extraction=None)
        self.assertIsNone(s["queues"]["review_pending"])
        self.assertIsNone(s["queues"]["reprocess_pending"])
        self.assertIsNone(s["period_status"])
        self.assertIsNone(s["sources"][0]["last_run"]["run_id"])

    def test_stale_only_when_limit_set(self):
        self.assertFalse(any(x["stale"] for x in self.build()["sources"]))
        self.assertTrue(self.build(stale_hours=48)["sources"][0]["stale"])

    def test_extraction_failures_reads_reports(self):
        from api.services.admin_status import extraction_failures

        with tempfile.TemporaryDirectory() as d:
            self.assertIsNone(extraction_failures(Path(d)))
            for run, status in (("r1", {"OK": 3, "OK_OCR": 1, "FAILED": 1}), ("r2", {"OK": 1, "DISTRIBUTION_DOC_UNSUPPORTED": 2})):
                (Path(d) / run).mkdir()
                (Path(d) / run / "extraction_report.json").write_text(json.dumps({"status": status}), encoding="utf-8")
            self.assertEqual(extraction_failures(Path(d)),
                             {"failed": 3, "by_status": {"FAILED": 1, "DISTRIBUTION_DOC_UNSUPPORTED": 2}, "reports": 2})


@unittest.skipUnless(HAS_DEPS, "fastapi·httpx·pydantic-settings가 설치되지 않았다(uv sync)")
class AdminStatusApiTest(unittest.TestCase):
    def test_admin_only_and_shape(self):
        from fastapi.testclient import TestClient

        from api.core.config import Settings, get_settings
        from api.dependencies import cleaned_raw, get_eligibility_service, get_review_store
        from api.main import create_app

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, APP_ENV="local", APP_DEV_AUTH=True)
        app.dependency_overrides[get_eligibility_service] = lambda: SimpleNamespace(_engine=SimpleNamespace(notices=NOTICES))
        app.dependency_overrides[get_review_store] = lambda: SimpleNamespace(available=lambda: True, rows=lambda: QUEUE)
        cleaned_raw.cache_clear()
        c = TestClient(app)
        self.assertEqual(c.get("/api/admin/status").status_code, 403)  # 일반 사용자
        r = c.get("/api/admin/status", headers={"X-Dev-Role": "admin"})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["notices"], 3)
        self.assertEqual(body["queues"]["review_pending"], 2)
        self.assertEqual({s["source"] for s in body["sources"]}, {"BIZINFO", "KSTARTUP", "G2B"})


if __name__ == "__main__":
    unittest.main()
