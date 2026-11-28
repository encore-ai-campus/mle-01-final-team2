"""배포 설정 점검. 값은 출력하지 않고 "있음/없음/모양"만 본다.

- API가 시작할 때 문제를 로그로 남긴다(`api/main.py`). 배포 환경(APP_ENV가 local이 아님)에서 ERROR가 있으면 시작은 하되 크게 알린다.
- 손으로 돌리기: `python -m api.core.deploy_check` (지금 환경변수·.env 기준), `--env prod`로 배포 기준 점검, `--online`이면 Supabase JWKS에 닿는지도 본다.

웹(Vercel)의 환경변수는 이 점검이 볼 수 없다. 웹은 `API_BASE_URL`(https 배포 API 주소)만 넣고 `DEV_ADMIN`은 넣지 않는다(docs/GUIDE_배포점검_v0.1.md).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from .config import Settings

ROOT = Path(__file__).resolve().parents[2]


def _key_kind(settings: Settings) -> str:
    if not settings.supabase_key:
        return "none"
    k = settings.supabase_key.get_secret_value()
    if k.startswith("sb_publishable_"):
        return "publishable"
    if k.startswith("sb_secret_"):
        return "secret"
    if k.count(".") == 2:
        import jwt

        try:
            return {"anon": "publishable", "service_role": "secret"}.get(jwt.decode(k, options={"verify_signature": False}).get("role"), "other")
        except jwt.InvalidTokenError:
            return "other"
    return "other"


def problems(settings: Settings, env: str | None = None) -> list[tuple[str, str]]:
    """[(ERROR|WARN, 설명)]. env를 주면 그 환경 기준으로 본다(기본은 settings.environment)."""
    env = env or settings.environment
    prod = env != "local"
    out: list[tuple[str, str]] = []
    err = "ERROR" if prod else "WARN"

    if prod and settings.dev_auth:
        out.append(("WARN", "APP_DEV_AUTH가 켜져 있습니다. 배포 환경에서는 무시되지만 비워 두세요."))
    if not settings.supabase_url:
        out.append((err, "SUPABASE_URL이 없습니다. 로그인 토큰을 검증할 수 없어 로그인이 필요한 API가 모두 막힙니다."))
    elif not settings.supabase_url.startswith("https://"):
        out.append((err, "SUPABASE_URL이 https가 아닙니다."))
    kind = _key_kind(settings)
    if kind == "secret":
        out.append(("ERROR", "SUPABASE_KEY가 비밀(서비스) 키입니다. 로그인 화면용 publishable 키를 넣고 비밀 키는 SUPABASE_SECRET_KEY에 두세요."))
    elif kind in ("none", "other"):
        out.append((err, "SUPABASE_KEY가 publishable 키가 아닙니다. 웹 로그인 화면이 꺼집니다."))
    if not (settings.admin_emails.strip() or settings.admin_user_ids.strip()):
        out.append((err, "ADMIN_EMAILS·ADMIN_USER_IDS가 비어 있습니다. 관리자 화면(검수 큐)에 아무도 못 들어갑니다."))
    if prod and any(o == "*" or o.startswith("http://localhost") for o in settings.cors_origins):
        out.append(("WARN", "APP_CORS_ORIGINS에 *나 localhost가 있습니다. 브라우저는 웹 서버만 부르므로 배포 웹 주소만 두세요."))
    if not settings.llm_configured:
        out.append(("WARN", "VLLM_BASE_URL·VLLM_MODEL이 없습니다. 판정은 되지만 설명 문장이 고정 문구로만 나갑니다."))
    if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password):
        out.append(("WARN", "NEO4J_* 설정이 없습니다. 근거 경로 그래프와 용어 정의가 빠집니다."))
    queue = ROOT / "data" / "reviews" / "requirements" / "queue.jsonl"
    if not queue.exists():
        out.append(("WARN", "검수 큐(data/reviews/requirements/queue.jsonl)가 없습니다. 검수 화면이 503을 냅니다(build로 만든다)."))
    return out


def jwks_reachable(settings: Settings) -> str | None:
    """Supabase 서명 키를 받아 오면 None, 아니면 이유."""
    if not settings.supabase_url:
        return "SUPABASE_URL 없음"
    from ..dependencies.auth import _jwks

    try:
        key = settings.supabase_key.get_secret_value() if settings.supabase_key else None
        keys = _jwks(settings.supabase_url.rstrip("/"), key).get_signing_keys()
        return None if keys else "서명 키가 비어 있음"
    except Exception as e:  # noqa: BLE001 — 점검 도구라 이유만 보인다
        return type(e).__name__


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="배포 설정 점검(값은 출력하지 않음)")
    ap.add_argument("--env", help="이 환경 기준으로 점검(예: prod). 기본은 APP_ENV")
    ap.add_argument("--online", action="store_true", help="Supabase JWKS에 닿는지도 본다")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    s = Settings()
    ps = problems(s, a.env)
    if a.online:
        why = jwks_reachable(s)
        if why:
            ps.append(("ERROR", f"Supabase 서명 키(JWKS)를 받지 못했습니다: {why}"))
    if a.json:
        print(json.dumps([{"level": lv, "message": m} for lv, m in ps], ensure_ascii=False, indent=2))
    else:
        print(f"환경: {a.env or s.environment}")
        for lv, m in ps:
            print(f"[{lv}] {m}")
        print("문제 없음" if not ps else f"ERROR {sum(lv == 'ERROR' for lv, _ in ps)}개, WARN {sum(lv == 'WARN' for lv, _ in ps)}개")
    return 1 if any(lv == "ERROR" for lv, _ in ps) else 0


if __name__ == "__main__":
    sys.exit(main())
