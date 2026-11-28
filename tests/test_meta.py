"""S-01 `GET /api/meta` 시험. 엔진은 가짜 공고 몇 개로 바꿔 끼운다.

실행: python -m unittest tests.test_meta -v
"""
import importlib.util
import sys
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "pydantic_settings"))

NOTICES = [
    {"source": "BIZINFO", "fetched_at": "2026-11-24T09:16:01+09:00"},
    {"source": "BIZINFO", "fetched_at": "2026-11-23T08:00:00+09:00"},
    {"source": "KSTARTUP", "fetched_at": "2026-11-24"},
    {"source": "G2B", "fetched_at": None},
]


class BuildMetaTest(unittest.TestCase):
    def test_latest_fetch_per_source(self):
        from api.services.meta import data_as_of

        self.assertEqual(data_as_of(NOTICES), {"BIZINFO": "2026-11-24T09:16:01+09:00", "KSTARTUP": "2026-11-24T00:00:00+09:00"})

    def test_stale_only_when_limit_set(self):
        from api.services.meta import KST, build_meta

        now = datetime(2026, 11, 28, tzinfo=KST)
        self.assertFalse(build_meta(NOTICES, now=now)["stale"])
        self.assertTrue(build_meta(NOTICES, stale_hours=48, now=now)["stale"])
        self.assertFalse(build_meta(NOTICES, stale_hours=24 * 7, now=now)["stale"])

    def test_bands_are_contiguous_and_cover_spec_codes(self):
        from api.services.meta import BANDS

        self.assertEqual([b["code"] for b in BANDS["EMP"]][:2], ["EMP_0", "EMP_1_4"])
        self.assertEqual({k: len(v) for k, v in BANDS.items()}, {"EMP": 7, "REV": 5, "AGE": 5, "BAGE": 7})
        for kind, bands in BANDS.items():
            with self.subTest(kind=kind):
                self.assertIsNone(bands[-1]["max"])  # 마지막 구간은 위쪽 끝 없음
                for a, b in zip(bands, bands[1:]):  # 빈틈·겹침 없음
                    self.assertEqual(b["min"], a["max"] if a.get("max_exclusive") else a["max"] + 1)


@unittest.skipUnless(HAS_DEPS, "fastapi·httpx·pydantic-settings가 설치되지 않았다(uv sync)")
class MetaApiTest(unittest.TestCase):
    def test_public_without_login(self):
        from fastapi.testclient import TestClient

        from api.core.config import Settings, get_settings
        from api.dependencies import get_eligibility_service
        from api.main import create_app

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, APP_ENV="prod", VLLM_MODEL="m")
        app.dependency_overrides[get_eligibility_service] = lambda: SimpleNamespace(_engine=SimpleNamespace(notices=NOTICES))
        r = TestClient(app).get("/api/meta")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertLessEqual({"data_as_of", "stale", "versions", "disclaimer", "sources", "bands"}, set(body))
        self.assertEqual(body["versions"]["model"], "m")
        self.assertEqual({s["source"] for s in body["sources"]}, {"BIZINFO", "KSTARTUP", "G2B"})


    def test_notice_and_eligibility_responses_carry_meta(self):
        from fastapi.testclient import TestClient

        from api.core.config import Settings, get_settings
        from api.dependencies import get_eligibility_service, get_notice_service
        from api.dependencies.auth import CurrentUser, get_current_user
        from api.main import create_app
        from api.schemas.eligibility import EligibilityResponse
        from api.schemas.notices import NoticeListResponse

        engine = SimpleNamespace(notices=NOTICES)
        svc = SimpleNamespace(_engine=engine, judge=lambda req: EligibilityResponse(evaluated=0, candidates=0, counts={}, results=[],
                                                                                    input_layer="cleaned"))
        notices = SimpleNamespace(list=lambda *a: NoticeListResponse(items=[], page=1, size=20, total=0))
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
        app.dependency_overrides[get_eligibility_service] = lambda: svc
        app.dependency_overrides[get_notice_service] = lambda: notices
        app.dependency_overrides[get_current_user] = lambda: CurrentUser("u", "user")
        c = TestClient(app)
        for r in (c.get("/api/notices"), c.post("/api/eligibility", json={"profile": {}})):
            with self.subTest(path=r.request.url.path):
                self.assertEqual(r.status_code, 200)
                meta = r.json()["meta"]
                self.assertEqual(meta["data_as_of"]["BIZINFO"], "2026-11-24T09:16:01+09:00")
                self.assertEqual(set(meta), {"data_as_of", "stale", "versions", "disclaimer"})


if __name__ == "__main__":
    unittest.main()
