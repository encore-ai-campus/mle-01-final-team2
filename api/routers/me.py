"""A-01 `GET /api/me`: 로그인 사용자·역할(SCR-00). 인증 의존성(`api/dependencies/auth.py`)이 완성되면 그대로 동작한다."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..dependencies.auth import CurrentUser, get_current_user

router = APIRouter(prefix="/api", tags=["auth"])


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"user_id": user.user_id, "role": user.role, "dev": user.dev}
