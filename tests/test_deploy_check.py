"""배포 설정 점검(api/core/deploy_check.py) 시험. 값은 만들어 넣고 네트워크는 쓰지 않는다.

실행: python -m unittest tests.test_deploy_check -v
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import jwt  # noqa: E402

from api.core.config import Settings  # noqa: E402
from api.core.deploy_check import problems  # noqa: E402

GOOD = dict(SUPABASE_URL="https://x.supabase.co", SUPABASE_KEY="sb_publishable_abc", ADMIN_EMAILS="a@b.c", ADMIN_USER_IDS="",
            VLLM_BASE_URL="https://llm/v1", VLLM_MODEL="m", NEO4J_URI="neo4j+s://g", NEO4J_USERNAME="u", NEO4J_PASSWORD="p",
            APP_CORS_ORIGINS=["https://app.example.org"])


def levels(env="prod", **over):
    s = Settings(_env_file=None, **{**GOOD, **over})
    return [(lv, m) for lv, m in problems(s, env) if "queue.jsonl" not in m]  # 큐 파일은 로컬 데이터라 시험에서 뺀다


class DeployCheckTest(unittest.TestCase):
    def test_good_prod_settings_pass(self):
        self.assertEqual(levels(), [])

    def test_missing_auth_is_error_in_prod_warn_in_local(self):
        self.assertIn("ERROR", {lv for lv, _ in levels(SUPABASE_URL=None)})
        self.assertEqual({lv for lv, _ in levels("local", SUPABASE_URL=None)}, {"WARN"})
        self.assertIn("ERROR", {lv for lv, _ in levels(ADMIN_EMAILS="")})

    def test_secret_key_as_public_key_is_always_error(self):
        service = jwt.encode({"role": "service_role"}, "x" * 32, algorithm="HS256")
        for key in ("sb_secret_abc", service):
            for env in ("prod", "local"):
                with self.subTest(env=env):
                    self.assertIn("ERROR", {lv for lv, _ in levels(env, SUPABASE_KEY=key)})

    def test_dev_auth_and_localhost_cors_warn_in_prod(self):
        msgs = " ".join(m for _, m in levels(APP_DEV_AUTH=True, APP_CORS_ORIGINS=["http://localhost:3000"]))
        self.assertIn("APP_DEV_AUTH", msgs)
        self.assertIn("APP_CORS_ORIGINS", msgs)

    def test_messages_never_contain_values(self):
        out = " ".join(m for _, m in levels(SUPABASE_KEY="sb_secret_TOPSECRET", ADMIN_EMAILS=""))
        self.assertNotIn("TOPSECRET", out)
        self.assertNotIn("x.supabase.co", out)


if __name__ == "__main__":
    unittest.main()
