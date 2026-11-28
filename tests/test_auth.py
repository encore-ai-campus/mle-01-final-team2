"""로그인(A-01) 시험: Supabase 액세스 토큰 검증과 관리자 허용 목록. 시험용 ES256 키를 만들어 쓰고 네트워크(JWKS)는 부르지 않는다.

실행: python -m unittest tests.test_auth -v
"""
import sys
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jwt  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from api.core.config import Settings, get_settings  # noqa: E402
from api.dependencies import auth  # noqa: E402
from api.main import create_app  # noqa: E402

URL = "https://example.supabase.co"
KEY = ec.generate_private_key(ec.SECP256R1())
OTHER = ec.generate_private_key(ec.SECP256R1())
UID = "11111111-2222-3333-4444-555555555555"


def token(key=KEY, alg="ES256", **over):
    now = int(time.time())
    claims = {"sub": UID, "email": "Admin@Example.org", "aud": "authenticated", "iss": f"{URL}/auth/v1", "iat": now, "exp": now + 600,
              "role": "authenticated", **over}
    return jwt.encode({k: v for k, v in claims.items() if v is not None}, key, algorithm=alg, headers={"kid": "k1"})


class AuthTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(auth, "_jwks")
        jwks = p.start()
        self.addCleanup(p.stop)
        jwks.return_value.get_signing_key_from_jwt.return_value.key = KEY.public_key()
        self.jwks = jwks

    def client(self, **env):
        s = Settings(_env_file=None, SUPABASE_URL=URL, **env)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: s
        return TestClient(app)

    def me(self, c, tok):
        return c.get("/api/me", headers={"Authorization": f"Bearer {tok}"})

    def test_valid_token_gives_user(self):
        r = self.me(self.client(), token())
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual((r.json()["user_id"], r.json()["role"], r.json()["dev"]), (UID, "user", False))

    def test_admin_from_allowlist(self):
        self.assertEqual(self.me(self.client(ADMIN_EMAILS="x@y.z, admin@example.org"), token()).json()["role"], "admin")  # 대소문자 무시
        self.assertEqual(self.me(self.client(ADMIN_USER_IDS=UID), token(email=None)).json()["role"], "admin")
        c = self.client(ADMIN_EMAILS="admin@example.org")
        self.assertEqual(c.get("/api/admin/reviews", headers={"Authorization": f"Bearer {token(email='someone@else.org')}"}).status_code, 403)

    def test_client_role_claim_is_ignored(self):
        """토큰 안의 role·app_metadata로 관리자가 되지 않는다(허용 목록만 본다)."""
        r = self.me(self.client(), token(role="admin", app_metadata={"role": "admin"}))
        self.assertEqual(r.json()["role"], "user")

    def test_rejects_bad_tokens(self):
        c = self.client()
        cases = {
            "wrong key": token(key=OTHER),
            "expired": token(exp=int(time.time()) - 600),
            "wrong audience": token(aud="anon"),
            "wrong issuer": token(iss="https://evil.supabase.co/auth/v1"),
            "no sub": token(sub=None),
            "alg none": jwt.encode({"sub": UID, "aud": "authenticated", "iss": f"{URL}/auth/v1", "exp": int(time.time()) + 60}, None, algorithm="none"),
            "hs256 without secret": token(key="secret-for-test-only-0123456789abcdef", alg="HS256"),
        }
        for name, tok in cases.items():
            with self.subTest(name):
                r = self.me(c, tok)
                self.assertEqual(r.status_code, 401, r.text)
        self.assertEqual(self.me(c, token(exp=int(time.time()) - 600)).json()["detail"]["error"]["code"], "TOKEN_EXPIRED")
        self.assertEqual(c.get("/api/me", headers={"Authorization": "Basic abc"}).status_code, 401)

    def test_legacy_hs256_with_secret(self):
        secret = "secret-for-test-only-0123456789abcdef"
        r = self.me(self.client(SUPABASE_JWT_SECRET=secret), token(key=secret, alg="HS256"))
        self.assertEqual(r.status_code, 200, r.text)

    def test_token_wins_over_dev_auth(self):
        """로컬 개발 가짜 로그인이 켜져 있어도 토큰이 있으면 검증한다. X-Dev-Role은 토큰 사용자에게 효과가 없다."""
        c = self.client(APP_ENV="local", APP_DEV_AUTH=True)
        r = c.get("/api/me", headers={"Authorization": f"Bearer {token()}", "X-Dev-Role": "admin"})
        self.assertEqual((r.json()["user_id"], r.json()["role"]), (UID, "user"))
        self.assertEqual(self.me(c, token(key=OTHER)).status_code, 401)
        self.assertTrue(c.get("/api/me").json()["dev"])  # 토큰이 없으면 가짜 사용자

    def test_jwks_unreachable_is_503(self):
        self.jwks.return_value.get_signing_key_from_jwt.side_effect = jwt.PyJWKClientConnectionError("down")
        r = self.me(self.client(), token())
        self.assertEqual((r.status_code, r.json()["detail"]["error"]["code"]), (503, "AUTH_UNAVAILABLE"))

    def test_no_supabase_config_is_503(self):
        s = Settings(_env_file=None)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: s
        r = TestClient(app).get("/api/me", headers={"Authorization": f"Bearer {token()}"})
        self.assertEqual(r.status_code, 503)


class AuthConfigTest(unittest.TestCase):
    """로그인 화면용 공개 설정은 publishable·anon 키만 내보낸다."""

    def setUp(self):
        from api.routers import me

        p = mock.patch.object(me, "providers", return_value=["email"])
        p.start()
        self.addCleanup(p.stop)

    def get(self, **env):
        s = Settings(_env_file=None, SUPABASE_URL=URL, **env)
        app = create_app()
        app.dependency_overrides[get_settings] = lambda: s
        return TestClient(app).get("/api/auth/config").json()

    def test_publishable_key_is_public(self):
        d = self.get(SUPABASE_KEY="sb_publishable_abc", SUPABASE_SECRET_KEY="sb_secret_xyz")
        self.assertEqual((d["enabled"], d["url"], d["publishable_key"]), (True, URL, "sb_publishable_abc"))
        self.assertNotIn("sb_secret_xyz", str(d))
        self.assertEqual(d["providers"], ["email"])

    def test_secret_or_service_key_is_never_returned(self):
        service = jwt.encode({"role": "service_role"}, "x" * 32, algorithm="HS256")
        anon = jwt.encode({"role": "anon"}, "x" * 32, algorithm="HS256")
        for key in ("sb_secret_xyz", service, "plain"):
            with self.subTest(key=key[:12]):
                d = self.get(SUPABASE_KEY=key)
                self.assertEqual((d["enabled"], d["publishable_key"]), (False, None))
        self.assertEqual(self.get(SUPABASE_KEY=anon)["publishable_key"], anon)


if __name__ == "__main__":
    unittest.main()
