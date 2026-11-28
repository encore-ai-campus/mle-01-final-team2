"""요건 검수 큐 API(/api/admin/reviews) 시험. 임시 큐 파일과 합성 공고만 쓴다. 네트워크·엔진 없이 돈다.

실행: python -m unittest tests.test_review_api -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from api.dependencies import get_eligibility_service, get_review_store  # noqa: E402
from api.dependencies.auth import CurrentUser, get_current_user  # noqa: E402
from api.main import create_app  # noqa: E402
from api.repositories.review_queue import ReviewQueueStore  # noqa: E402
from tests.test_requirement_review_queue import NID, row  # noqa: E402
from tools import requirement_review_queue as Q  # noqa: E402

URL = f"/api/admin/reviews/{NID}"


class ReviewApiTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.queue = Path(self.tmp.name) / "queue.jsonl"
        self.row = row()
        other = {**row(), "notice_id": "KSTARTUP:2", "title": "다른 공고", "source_system": "KSTARTUP", "is_open": False}
        Q.write_jsonl(self.queue, [{**self.row, "priority_rank": 1}, {**other, "priority_rank": 2}])
        self.app = create_app()
        self.store = ReviewQueueStore(self.queue)
        self.app.dependency_overrides[get_review_store] = lambda: self.store
        self.role = "admin"
        self.app.dependency_overrides[get_current_user] = lambda: CurrentUser("검수자A", self.role)
        self.engine = mock.Mock()
        self.engine.reload_reviews.return_value = {"before": 30, "after": 31, "reviewed": 1}
        self.app.dependency_overrides[get_eligibility_service] = lambda: SimpleNamespace(_engine=self.engine)
        self.c = TestClient(self.app)

    def tearDown(self):
        self.tmp.cleanup()

    def span(self, quote):
        s = self.row["source_text"].index(quote)
        return s, s + len(quote)

    def put(self, action, conds, **kw):
        body = {"action": action, "conditions": conds, "whole_notice_conditions_complete": True, **kw}
        return self.c.put(URL, json=body)

    def age_cond(self, value=3):
        s, e = self.span("창업 3년 이내")
        return {"condition_type": "ELIGIBILITY", "field": "BUSINESS_AGE", "operator": "LTE", "value": value, "start_char": s, "end_char": e}

    def test_list_filters_and_counts(self):
        d = self.c.get("/api/admin/reviews").json()
        self.assertEqual(d["total"], 2)
        self.assertEqual(d["counts"], {"UNREVIEWED": 2})
        self.assertEqual([x["notice_id"] for x in self.c.get("/api/admin/reviews?open_only=true").json()["items"]], [NID])
        self.assertEqual(self.c.get("/api/admin/reviews?source=KSTARTUP").json()["total"], 1)
        self.assertEqual(self.c.get("/api/admin/reviews?q=다른").json()["items"][0]["notice_id"], "KSTARTUP:2")

    def test_detail_has_source_and_catalog(self):
        d = self.c.get(URL).json()
        self.assertEqual(d["review"]["source_text"], self.row["source_text"])
        self.assertNotIn("_sort", d["review"])
        self.assertIn("BUSINESS_AGE", {f["field"] for f in d["fields"]})
        self.assertEqual(self.c.get("/api/admin/reviews/NOPE:1").status_code, 404)

    def test_non_admin_is_denied(self):
        self.role = "user"
        self.assertEqual(self.c.get("/api/admin/reviews").status_code, 403)
        self.assertEqual(self.put("save", []).status_code, 403)

    def test_save_draft_then_verify_then_ingest(self):
        r = self.put("save", [self.age_cond()])
        self.assertEqual(r.status_code, 200, r.text)
        saved = self.store.get(NID)
        self.assertEqual(saved["review_status"], "NEEDS_REVIEW")
        g = saved["gold_conditions"][0]
        self.assertEqual(g["raw_text"], "창업 3년 이내")  # 근거는 서버가 원문에서 자른다
        self.assertEqual(g["review_status"], "UNREVIEWED")
        r = self.put("verify", [self.age_cond()])
        self.assertEqual(r.status_code, 200, r.text)
        v = self.store.get(NID)
        self.assertEqual((v["review_status"], v["adjudication_status"], v["reviewer"]), ("VERIFIED", "REVIEWED_COMPLETE", "검수자A"))
        self.assertEqual(Q.check_row(v), [])
        rep = self.c.post("/api/admin/reviews/ingest").json()
        self.assertEqual((rep["verified"], rep["applied"]), (1, 1))
        self.assertEqual(rep["reloaded"]["after"], 31)  # 엔진이 바로 다시 읽는다
        self.engine.reload_reviews.assert_called_once()
        applied = Q.read_jsonl(Path(self.tmp.name) / "service" / "reviewed_condition_gold.jsonl")
        self.assertEqual(applied[0]["notice_id"], NID)
        # 다시 작업하면 반영 대상에서 빠진다
        self.assertEqual(self.put("reopen", []).json()["review"]["review_status"], "NEEDS_REVIEW")
        self.assertEqual(self.c.post("/api/admin/reviews/ingest").json()["applied"], 0)

    def test_or_logic_groups_eligibility(self):
        s, e = self.span("대구광역시 소재")
        region = {"condition_type": "ELIGIBILITY", "field": "BUSINESS_LOCATION", "operator": "IN", "value": "대구광역시", "start_char": s, "end_char": e}
        r = self.put("verify", [self.age_cond(), region], logic="OR")
        self.assertEqual(r.status_code, 200, r.text)
        root = self.store.get(NID)["gold_logic_roots"][0]
        self.assertEqual(root["operator"], "OR")
        self.assertEqual(len(root["children"]), 2)
        self.assertEqual(self.store.get(NID)["gold_conditions"][1]["value"], ["대구광역시"])

    def test_invalid_values_are_rejected(self):
        bad = self.put("save", [self.age_cond("세 살")])
        self.assertEqual(bad.status_code, 422)
        self.assertIn("숫자", bad.json()["detail"]["error"]["errors"][0])
        out = self.put("save", [{**self.age_cond(), "end_char": 10_000}])
        self.assertEqual(out.status_code, 422)
        self.assertEqual(self.store.get(NID)["review_status"], "UNREVIEWED")  # 실패하면 저장하지 않는다
        dup = self.put("save", [self.age_cond(), self.age_cond()])
        self.assertEqual(dup.status_code, 422)

    def test_verify_needs_conditions_or_none_flag(self):
        self.assertEqual(self.put("verify", []).status_code, 422)
        r = self.put("verify", [], none_in_text=True)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.store.get(NID)["adjudication_status"], "CONFIRMED_NONE_IN_PROVIDED_TEXT")
        self.assertEqual(self.put("verify", [self.age_cond()], none_in_text=True).status_code, 422)

    def test_failed_check_keeps_draft(self):
        """원문이 바뀐(stale) 행은 검수 완료 검사에 걸리고, 작업 중으로만 저장된다."""
        self.store.update(NID, lambda r: {**r, "stale_source": True})
        r = self.put("verify", [self.age_cond()])
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.json()["detail"]["error"]["code"], "REVIEW_CHECK_FAILED")
        kept = self.store.get(NID)
        self.assertEqual(kept["review_status"], "NEEDS_REVIEW")
        self.assertEqual(len(kept["gold_conditions"]), 1)

    def test_store_survives_external_rewrite(self):
        self.assertEqual(self.store.get(NID)["title"], "합성 공고")
        rows = Q.read_jsonl(self.queue)
        rows[0]["title"] = "바뀐 제목"
        import os
        import time

        Q.write_jsonl(self.queue, rows)
        st = self.queue.stat()
        os.utime(self.queue, (st.st_atime, st.st_mtime + 5))  # 파일 시각 해상도가 낮은 환경 대비
        time.sleep(0)
        self.assertEqual(self.store.get(NID)["title"], "바뀐 제목")
        self.assertEqual(json.loads(self.queue.read_text(encoding="utf-8").splitlines()[0])["title"], "바뀐 제목")

    def test_make_id_matches_goldset_rule(self):
        from tools.ingest_condition_gold_reviews import make_id as gold_make_id

        for args in ((NID, "ELIGIBILITY", 0, 5, "대구광역시"), ("KSTARTUP:1", "EXCLUSION", 10, 42, "체납 기업 제외 ✓")):
            self.assertEqual(Q.make_id(*args), gold_make_id(*args))


if __name__ == "__main__":
    unittest.main()
