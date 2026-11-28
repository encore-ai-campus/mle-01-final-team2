"""로그인 사용자·역할 의존성(명세 A-01, 기초 설계서 §8 로그인·역할).

- `Authorization: Bearer <Supabase 액세스 토큰>`을 검증한다. 서명은 Supabase JWKS(`/auth/v1/.well-known/jwks.json`, 지금 프로젝트는 ES256)로,
  예전 HS256 프로젝트면 `SUPABASE_JWT_SECRET`으로 본다. 발급자(`<SUPABASE_URL>/auth/v1`)·대상(`authenticated`)·만료를 확인한다.
- 역할은 서버 쪽 허용 목록(`ADMIN_EMAILS`, `ADMIN_USER_IDS`)으로 정한다(명세 §1). 클라이언트가 보낸 역할 값은 믿지 않는다.
  Supabase `profiles` 표로 옮기는 일은 표를 만든 뒤에 한다(설계서 §5 SQL, 아직 표 없음).
- 거절한 관리자 접근은 로그(`jiwongak.audit`)에 남긴다. `audit_logs` 표가 생기면 거기에 쓴다.
- 토큰이 없을 때만, 로컬 개발(`APP_ENV=local` + `APP_DEV_AUTH=1`)에서 가짜 사용자로 통과시키고 `X-Dev-Role: admin`으로 관리자를 흉내 낸다.
  토큰이 있으면 로컬에서도 검증한다. 배포 환경(APP_ENV가 local이 아님)에서는 APP_DEV_AUTH를 켜도 가짜 사용자를 만들지 않는다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, Header

from ..core.config import Settings, get_settings
from ..core.errors import api_error

log = logging.getLogger("jiwongak.audit")
ASYMMETRIC = ["ES256", "RS256", "EdDSA"]


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str  # "user" | "admin"
    dev: bool = False  # 개발용 가짜 사용자면 True
    email: str | None = None


@lru_cache(maxsize=4)
def _jwks(url: str, apikey: str | None) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(f"{url}/auth/v1/.well-known/jwks.json", cache_keys=True, lifespan=600,
                           headers={"apikey": apikey} if apikey else None, timeout=10)


def signing_key(token: str, settings: Settings) -> tuple[object, list[str]]:
    """토큰 머리의 alg·kid로 검증 키를 고른다. 시험에서는 이 함수를 바꿔 끼운다."""
    alg = jwt.get_unverified_header(token).get("alg")
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise jwt.InvalidTokenError("HS256 token but no SUPABASE_JWT_SECRET")
        return settings.supabase_jwt_secret.get_secret_value(), ["HS256"]
    if alg not in ASYMMETRIC:
        raise jwt.InvalidTokenError(f"unsupported alg {alg}")
    key = settings.supabase_key.get_secret_value() if settings.supabase_key else None
    return _jwks(settings.supabase_url.rstrip("/"), key).get_signing_key_from_jwt(token).key, [alg]


def verify_token(token: str, settings: Settings) -> dict:
    key, algs = signing_key(token, settings)
    return jwt.decode(token, key, algorithms=algs, audience="authenticated", issuer=f"{settings.supabase_url.rstrip('/')}/auth/v1",
                      options={"require": ["exp", "sub", "iss", "aud"]}, leeway=30)


def get_current_user(settings: Settings = Depends(get_settings), authorization: str | None = Header(default=None),
                     x_dev_role: str | None = Header(default=None)) -> CurrentUser:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise api_error(401, "UNAUTHENTICATED", "Bearer 토큰이 필요합니다.")
        if not settings.auth_configured:
            raise api_error(503, "AUTH_NOT_CONFIGURED", "로그인 설정(SUPABASE_URL)이 없습니다.")
        try:
            claims = verify_token(token, settings)
        except jwt.ExpiredSignatureError:
            raise api_error(401, "TOKEN_EXPIRED", "로그인이 만료되었습니다. 다시 로그인하세요.") from None
        except (jwt.PyJWKClientError, OSError) as e:
            log.warning("jwks unavailable: %s", type(e).__name__)
            raise api_error(503, "AUTH_UNAVAILABLE", "로그인 확인 서버에 닿지 않습니다.") from None
        except jwt.InvalidTokenError as e:
            log.info("invalid token: %s", type(e).__name__)
            raise api_error(401, "UNAUTHENTICATED", "로그인 정보가 올바르지 않습니다.") from None
        uid, email = claims["sub"], claims.get("email")
        return CurrentUser(user_id=uid, role="admin" if settings.is_admin(uid, email) else "user", email=email)
    if settings.environment == "local" and settings.dev_auth:
        return CurrentUser(user_id="local-dev", role="admin" if x_dev_role == "admin" else "user", dev=True)
    raise api_error(401, "UNAUTHENTICATED", "로그인이 필요합니다.")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        log.warning("admin_denied user=%s dev=%s", user.user_id, user.dev)  # audit_logs(allowed=false) 대신. 이메일은 남기지 않는다
        raise api_error(403, "ROLE_DENIED", "관리자만 쓸 수 있습니다.")
    return user
