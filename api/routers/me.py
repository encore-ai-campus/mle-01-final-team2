"""A-01 `GET /api/me`: 로그인 사용자·역할(SCR-00). 토큰 검증·역할은 `api/dependencies/auth.py`."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..core.config import Settings, get_settings
from ..dependencies.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"user_id": user.user_id, "role": user.role, "dev": user.dev, "email": user.email}


def _public_key(settings: Settings) -> str | None:
    """브라우저에 내보내도 되는 키만 돌려준다: 새 publishable 키, 또는 예전 anon JWT(role=anon). 서비스·비밀 키는 절대 내보내지 않는다."""
    if not settings.supabase_key:
        return None
    k = settings.supabase_key.get_secret_value()
    if k.startswith("sb_publishable_"):
        return k
    if k.count(".") == 2:
        import jwt

        try:
            if jwt.decode(k, options={"verify_signature": False}).get("role") == "anon":
                return k
        except jwt.InvalidTokenError:
            return None
    return None


_PROVIDERS: dict[str, tuple[float, list[str]]] = {}


def providers(url: str, key: str) -> list[str]:
    """Supabase Auth에서 켜 둔 로그인 방법(공개 /auth/v1/settings). 5분 동안 기억한다. 닿지 않으면 이메일만 있다고 본다."""
    import json
    import time
    import urllib.request

    hit = _PROVIDERS.get(url)
    if hit and time.monotonic() - hit[0] < 300:
        return hit[1]
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/auth/v1/settings", headers={"apikey": key})
        with urllib.request.urlopen(req, timeout=5) as r:  # noqa: S310 (설정한 Supabase 주소만 부른다)
            ext = json.load(r).get("external", {})
        out = sorted(k for k, v in ext.items() if v is True)
    except (OSError, ValueError):
        return ["email"]
    _PROVIDERS[url] = (time.monotonic(), out)
    return out


@router.get("/auth/config")
def auth_config(settings: Settings = Depends(get_settings)) -> dict:
    """웹 로그인 화면이 Supabase Auth를 부를 때 쓰는 공개 설정. 로그인 전에 부르므로 인증이 없다."""
    key = _public_key(settings)
    enabled = bool(settings.supabase_url and key)
    return {"enabled": enabled, "url": settings.supabase_url if enabled else None, "publishable_key": key if enabled else None,
            "providers": providers(settings.supabase_url, key) if enabled else []}
