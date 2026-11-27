"""기능 뼈대 시험: 아직 구현 전인 엔드포인트가 501과 명세 ID를 내는지, 인증 의존성이 막을 곳을 막는지 본다.
구현을 마친 엔드포인트는 STUBS에서 빼고 진짜 시험을 쓴다.
실행: python -m unittest tests.test_api_skeleton -v
"""
import importlib.util
import unittest

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("fastapi", "httpx", "pydantic_settings"))

# (메서드, 경로, 명세 ID, 관리자 전용)
STUBS = [
    ("GET", "/api/notices/N:1/spans", "N-03", False),
    ("GET", "/api/eligibility/N:1", "E-02", False),
    ("GET", "/api/eligibility/N:1/path", "E-03", False),
    ("POST", "/api/eligibility/clarify", "E-04", False),
    ("GET", "/api/meta", "S-01", False),
    ("GET", "/api/admin/status", "M-01", True),
    ("POST", "/api/admin/reprocess", "M-03", True),
]


@unittest.skipUnless(HAS_DEPS, "fastapi·httpx·pydantic-settings가 설치되지 않았다(uv sync)")
class TestApiSkeleton(unittest.TestCase):
    def client(self, **env):
        from fastapi.testclient import TestClient

        from api.core.config import Settings, get_settings
        from api.main import create_app

        settings = Settings(_env_file=None, **env)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: settings
        return TestClient(app)

    def test_stubs_return_501_with_spec_id(self):
        c = self.client(APP_ENV="local", APP_DEV_AUTH=True)
        for method, path, spec, admin in STUBS:
            with self.subTest(path=path):
                r = c.request(method, path, headers={"X-Dev-Role": "admin"} if admin else {})
                self.assertEqual(r.status_code, 501)
                err = r.json()["detail"]["error"]
                self.assertEqual((err["code"], err["spec"]), ("NOT_IMPLEMENTED", spec))

    def test_login_required_without_dev_auth(self):
        c = self.client(APP_ENV="local")
        for method, path, _, _ in STUBS:
            if path == "/api/meta":  # 공개
                continue
            with self.subTest(path=path):
                self.assertEqual(c.request(method, path).status_code, 401)
        self.assertEqual(c.get("/api/me", headers={"Authorization": "Bearer x"}).status_code, 401)  # 검증 전에는 토큰도 통과 못 한다

    def test_dev_auth_only_in_local(self):
        self.assertEqual(self.client(APP_ENV="prod", APP_DEV_AUTH=True).get("/api/me").status_code, 401)
        r = self.client(APP_ENV="local", APP_DEV_AUTH=True).get("/api/me")
        self.assertEqual((r.status_code, r.json()["role"], r.json()["dev"]), (200, "user", True))

    def test_admin_routes_need_admin_role(self):
        c = self.client(APP_ENV="local", APP_DEV_AUTH=True)
        r = c.get("/api/admin/status")
        self.assertEqual((r.status_code, r.json()["detail"]["error"]["code"]), (403, "ROLE_DENIED"))


if __name__ == "__main__":
    unittest.main()
