"""N-01 공고 목록·N-02 상세(GET /api/notices, /api/notices/{id}). 가짜 엔진으로 필터·검색·정렬·페이지·원문 구역을 본다(실제 데이터·DB 없이)."""
import importlib.util
import unittest

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "pydantic_settings"))


class FakeEngine:
    """NoticeService가 쓰는 것(notices, chunks, by_id, is_open)만 흉내 낸다."""

    notices = [
        {"notice_id": "KSTARTUP:1", "source": "KSTARTUP", "title": "창업 도약 패키지", "org": "창업진흥원", "deadline": "2026-12-10", "is_open": True},
        {"notice_id": "BIZINFO:2", "source": "BIZINFO", "title": "수출 바우처", "org": "중진공", "deadline": "2026-12-01", "is_open": True},
        {"notice_id": "BIZINFO:3", "source": "BIZINFO", "title": "상시 컨설팅", "org": "창업진흥원", "deadline": None, "is_open": True},
        {"notice_id": "KSTARTUP:4", "source": "KSTARTUP", "title": "마감된 창업 공고", "org": "서울시", "deadline": "2026-10-01", "is_open": False},
    ]

    chunks = [
        {"chunk_id": "BIZINFO:2#eligibility_api:0", "notice_id": "BIZINFO:2", "section": "eligibility_api", "origin": "API", "text": "중소기업"},
        {"chunk_id": "BIZINFO:2#att_eligibility@f0-10:0", "notice_id": "BIZINFO:2", "section": "att_eligibility@f0-10", "origin": "ATTACHMENT",
         "text": "수출 실적 보유", "source_span": {"file": "a.hwpx", "start": 10, "end": 18}},
    ]
    by_id = {n["notice_id"]: n for n in notices}

    def is_open(self, n):
        return n["is_open"]


RAW = {"BIZINFO:2": {"application_start": "2026-11-20", "contact_text": "중진공 02-000-0000", "attachments": {"count": 1, "text_extracted": 1}}}


@unittest.skipUnless(HAS_DEPS, "fastapi·httpx·pydantic-settings가 설치되지 않았다(uv sync)")
class TestNotices(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from api.core.config import Settings, get_settings
        from api.dependencies import get_notice_service
        from api.main import create_app
        from api.services.notices import NoticeService

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, APP_ENV="local", APP_DEV_AUTH=True)
        app.dependency_overrides[get_notice_service] = lambda: NoticeService(FakeEngine(), raw=RAW)
        self.c = TestClient(app)

    def ids(self, **params):
        r = self.c.get("/api/notices", params=params)
        self.assertEqual(r.status_code, 200)
        return [i["notice_id"] for i in r.json()["items"]]

    def test_default_open_only_sorted_by_deadline(self):
        # 마감된 4번은 빠지고, 마감 가까운 순, 마감일 없는 3번은 맨 뒤
        self.assertEqual(self.ids(), ["BIZINFO:2", "KSTARTUP:1", "BIZINFO:3"])

    def test_include_closed(self):
        self.assertIn("KSTARTUP:4", self.ids(include_closed=True))

    def test_source_filter(self):
        self.assertEqual(self.ids(source="kstartup"), ["KSTARTUP:1"])  # 소문자도 된다

    def test_search_title_or_org(self):
        self.assertEqual(self.ids(q="창업"), ["KSTARTUP:1", "BIZINFO:3"])  # 1은 제목, 3은 기관

    def test_paging_and_total(self):
        body = self.c.get("/api/notices", params={"size": 2, "page": 2}).json()
        self.assertEqual(([i["notice_id"] for i in body["items"]], body["total"]), (["BIZINFO:3"], 3))

    def test_field_names_follow_spec(self):
        item = self.c.get("/api/notices").json()["items"][0]
        self.assertEqual((item["source_system"], item["organization"]), ("BIZINFO", "중진공"))

    def test_login_required(self):
        from api.core.config import Settings, get_settings

        self.c.app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, APP_ENV="local")
        self.assertEqual(self.c.get("/api/notices").status_code, 401)

    def test_detail_sections_and_raw_fields(self):
        r = self.c.get("/api/notices/BIZINFO:2")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual((d["title"], d["source_system"]), ("수출 바우처", "BIZINFO"))
        self.assertEqual([s["origin"] for s in d["sections"]], ["API", "ATTACHMENT"])
        self.assertEqual(d["sections"][1]["source_span"]["start"], 10)
        self.assertEqual((d["application_start"], d["contact_text"]), ("2026-11-20", "중진공 02-000-0000"))

    def test_detail_without_raw_or_chunks(self):
        d = self.c.get("/api/notices/KSTARTUP:1").json()
        self.assertEqual((d["sections"], d["contact_text"], d["requirements_status"]), ([], None, "unparsed"))

    def test_detail_closed_notice_still_viewable(self):
        self.assertFalse(self.c.get("/api/notices/KSTARTUP:4").json()["is_open"])

    def test_detail_not_found(self):
        r = self.c.get("/api/notices/X:1")
        self.assertEqual((r.status_code, r.json()["detail"]["error"]["code"]), (404, "NOT_FOUND"))


if __name__ == "__main__":
    unittest.main()