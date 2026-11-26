"""API 뼈대 시험. 실제 데이터 없이 가짜 판정 서비스를 넣어 돌린다.
실행: python -m unittest tests.test_api -v   (fastapi·httpx가 없으면 건너뛴다)
"""
import importlib.util
import unittest

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "pydantic_settings"))


class FakeService:
    def __init__(self):
        self.last = None

    def judge(self, req):
        from api.schemas.eligibility import EligibilityResponse

        self.last = req
        return EligibilityResponse(evaluated=2, candidates=1, counts={"NEEDS_CHECK": 1, "NOT_ELIGIBLE": 1}, input_layer="fake", results=[{
            "notice_id": "N:1", "verdict": "NEEDS_CHECK", "structured": "UNKNOWN", "reasons": ["MISSING_INPUT"], "score": None,
            "conditions": [{"cond_id": "N:1#C1", "attribute": "region", "status": "UNKNOWN", "strength": "hard", "reason": "지역 미입력"}]}])


@unittest.skipUnless(HAS_DEPS, "fastapi·httpx·pydantic-settings가 설치되지 않았다(pip install -r requirements-dev.txt)")
class TestApi(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient

        from api.dependencies import get_eligibility_service
        from api.main import create_app

        self.fake = FakeService()
        app = create_app()
        app.dependency_overrides[get_eligibility_service] = lambda: self.fake
        self.client = TestClient(app)

    def test_health(self):
        r = self.client.get("/health")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "ok")

    def test_eligibility_keeps_missing_values_as_unknown(self):
        r = self.client.post("/api/eligibility", json={"profile": {"business_age_years": 3}})
        self.assertEqual(r.status_code, 200)
        self.assertIsNone(self.fake.last.profile.region)  # 비운 값은 None(모름)으로 전달되고 기본값을 채우지 않는다
        body = r.json()
        self.assertEqual(body["results"][0]["verdict"], "NEEDS_CHECK")
        self.assertEqual(body["results"][0]["conditions"][0]["status"], "UNKNOWN")

    def test_settings_read_existing_env_names(self):
        import os
        from unittest import mock

        from api.core.config import Settings

        env = {"NEO4J_URI": "neo4j+s://example.databases.neo4j.io", "NEO4J_USERNAME": "u", "SUPABASE_URL": "https://x.supabase.co",
               "VLLM_BASE_URL": "https://pod-8000.proxy.runpod.net/v1", "VLLM_MODEL": "m"}
        with mock.patch.dict(os.environ, env, clear=True):
            s = Settings(_env_file=None)
        self.assertEqual((s.neo4j_uri, s.neo4j_user, s.supabase_url), (env["NEO4J_URI"], "u", env["SUPABASE_URL"]))
        self.assertTrue(s.llm_configured)
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(Settings(_env_file=None).llm_configured)

    def test_health_reports_configuration_without_values(self):
        body = self.client.get("/health").json()
        self.assertEqual(set(body["configured"]), {"neo4j", "supabase", "llm"})
        self.assertTrue(all(isinstance(v, bool) for v in body["configured"].values()))

    def test_invalid_input_is_rejected(self):
        self.assertEqual(self.client.post("/api/eligibility", json={"profile": {"founder_age": -1}}).status_code, 422)
        self.assertEqual(self.client.post("/api/eligibility", json={"profile": {}, "source": "NARA"}).status_code, 422)


if __name__ == "__main__":
    unittest.main()
