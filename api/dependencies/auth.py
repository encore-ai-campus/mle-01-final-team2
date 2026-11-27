"""로그인 사용자·역할 의존성(명세 A-01, 기초 설계서 §8 로그인·역할).

할 일(A-01 담당):
  1. `Authorization: Bearer <Supabase JWT>`를 `SUPABASE_JWT_SECRET`로 검증한다(서명·만료·aud).
  2. 검증된 `sub`로 Supabase `profiles`를 매 요청 조회해 역할(`user`/`admin`)을 정한다. 클라이언트가 보낸 역할 값은 믿지 않는다.
  3. 거절한 관리자 접근은 `audit_logs`(allowed=false)에 남긴다.

지금은 검증을 구현하지 않았다. 그래서 토큰이 있어도 401을 낸다.
로컬 개발에서만 `APP_ENV=local` + `APP_DEV_AUTH=1`이면 가짜 사용자로 통과시키고, `X-Dev-Role: admin` 헤더로 관리자 흉내를 낸다.
배포 환경(APP_ENV가 local이 아님)에서는 APP_DEV_AUTH를 켜도 통과시키지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header

from ..core.config import Settings, get_settings
from ..core.errors import api_error


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    role: str  # "user" | "admin"
    dev: bool = False  # 개발용 가짜 사용자면 True


def get_current_user(settings: Settings = Depends(get_settings), authorization: str | None = Header(default=None),
                     x_dev_role: str | None = Header(default=None)) -> CurrentUser:
    if settings.environment == "local" and settings.dev_auth:
        return CurrentUser(user_id="local-dev", role="admin" if x_dev_role == "admin" else "user", dev=True)
    if not authorization:
        raise api_error(401, "UNAUTHENTICATED", "로그인이 필요합니다.")
    raise api_error(401, "UNAUTHENTICATED", "토큰 검증이 아직 구현되지 않았습니다(A-01).")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if user.role != "admin":
        raise api_error(403, "ROLE_DENIED", "관리자만 쓸 수 있습니다.")
    return user
