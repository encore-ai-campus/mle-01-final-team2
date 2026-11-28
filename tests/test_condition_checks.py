"""E-02 `POST /api/eligibility/{notice_id}` 조건별 검증표 시험. 가짜 판정 서비스를 쓴다.

실행: python -m unittest tests.test_condition_checks -v
"""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "pydantic_settings"))

RESULT = {"notice_id": "N:1", "verdict": "NEEDS_CHECK", "structured": "UNKNOWN", "reasons": ["UNKNOWN_CONDITION"], "conditions": [
    {"cond_id": "C1", "attribute": "region", "status": "SATISFIED", "strength": "hard", "reason": "서울 안", "evidence": "서울 소재", "path": ["a", "b"], "flags": []},
    {"cond_id": "C2", "attribute": "business_age", "status": "SATISFIED", "strength": "hard", "reason": "7년 이내", "evidence": "창업 7년 이내", "path": None, "flags": []},
    {"cond_id": "C3", "attribute": "founder_age", "status": "UNKNOWN", "strength": "hard", "reason": "나이 모름", "evidence": "만 39세 이하", "path": None, "flags": []},
    {"cond_id": "C4", "attribute": "certification", "status": "UNKNOWN", "strength": "soft", "reason": "규칙 없음", "evidence": "벤처기업", "path": None, "flags": ["gold"]},
]}


class ChecksTest(unittest.TestCase):
    def test_value_source(self):
        from api.services.condition_checks import checks

        out = checks(RESULT, {"region": "REGION:1100000000", "business_start_date": "2024-01-01"})
        src = {r["cond_id"]: r["my_value"]["source"] for r in out["checks"]}
        self.assertEqual(src, {"C1": "INPUT", "C2": "DERIVED", "C3": "MISSING", "C4": "MISSING"})
        self.assertEqual(out["by_result"], {"SATISFIED": 2, "UNKNOWN": 2})
        self.assertEqual(out["checks"][0]["evidence"]["text"], "서울 소재")
        self.assertEqual(out["checks"][0]["required"]["label"], "서울 소재")
        self.assertEqual(out["checks"][0]["reason"], "서울 안")

    def test_direct_input_wins_over_derived(self):
        from api.services.condition_checks import my_value

        self.assertEqual(my_value("business_age", {"business_age_years": 3, "business_start_date": "2020-01-01"})["source"], "INPUT")
        self.assertEqual(my_value("business_type", {"sme_status": "certified"}), {"value": "certified", "source": "DERIVED", "field": "sme_status"})


@unittest.skipUnless(HAS_DEPS, "fastapi·httpx·pydantic-settings가 설치되지 않았다(uv sync)")
class ChecksApiTest(unittest.TestCase):
    def test_post_returns_checks_and_404(self):
        from fastapi.testclient import TestClient

        from api.core.config import Settings, get_settings
        from api.dependencies import get_eligibility_service
        from api.main import create_app
        from api.schemas.eligibility import EligibilityResponse
        from api.services.eligibility import NoticeNotFound

        def judge_notice(notice_id, profile):
            if notice_id != "N:1":
                raise NoticeNotFound(notice_id)
            return EligibilityResponse(evaluated=1, candidates=1, counts={"NEEDS_CHECK": 1}, results=[RESULT], input_layer="cleaned")

        app = create_app()
        app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None, APP_ENV="local", APP_DEV_AUTH=True)
        app.dependency_overrides[get_eligibility_service] = lambda: SimpleNamespace(_engine=SimpleNamespace(notices=[]), judge_notice=judge_notice)
        c = TestClient(app)
        r = c.post("/api/eligibility/N:1", json={"profile": {"region": "REGION:1100000000"}})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["result"]["verdict"], "NEEDS_CHECK")
        self.assertEqual(body["checks"][0]["my_value"]["source"], "INPUT")
        self.assertIn("disclaimer", body["meta"])
        self.assertEqual(c.post("/api/eligibility/N:2", json={"profile": {}}).status_code, 404)
        self.assertEqual(c.post("/api/eligibility/clarify", json={}).status_code, 501)  # 되묻기는 아직 뼈대


if __name__ == "__main__":
    unittest.main()
