"""환경 설정. 값은 환경변수(또는 저장소 루트 .env)에서 읽고, 비밀 값은 코드·로그에 남기지 않는다.

배포 구성(팀 결정): API = AWS CPU 서버(Docker), LLM = RunPod GPU의 vLLM(OpenAI 호환 API), 그래프 = Neo4j Aura, 원문·사용자 = Supabase.
외부 저장소 변수 이름은 적재 스크립트(tools/sync_graph_neo4j.py)가 쓰는 기존 .env 이름을 그대로 쓴다.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def _env(*names: str):
    return Field(default=None, validation_alias=AliasChoices(*names))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # 앱 자체 설정(접두사 APP_)
    app_name: str = Field(default="지원각 API", validation_alias="APP_NAME")
    environment: str = Field(default="local", validation_alias="APP_ENV", description="local / dev / prod")
    # 판정 데이터 입력 층. 정리 층(data/cleaned)이 있으면 그것을 쓴다(tools/graphrag/engine.py). 비우면 자동 선택
    use_cleaned: bool | None = Field(default=None, validation_alias="APP_USE_CLEANED")
    # 브라우저는 Next.js 서버(Vercel)만 호출한다. 로컬 개발용 허용 출처만 둔다
    cors_origins: list[str] = Field(default=["http://localhost:3000"], validation_alias="APP_CORS_ORIGINS")
    # 로컬 개발용 가짜 로그인(api/dependencies/auth.py). APP_ENV=local일 때만 효과가 있다
    dev_auth: bool = Field(default=False, validation_alias="APP_DEV_AUTH")
    # 수집 지연 한도(시간). 넘으면 S-01 meta.stale=true. 수집 주기 미정이라 기본 0(끔)
    stale_hours: float = Field(default=0, validation_alias="APP_STALE_HOURS")

    # Neo4j Aura(기존 .env 이름)
    neo4j_uri: str | None = _env("NEO4J_URI")
    neo4j_user: str | None = _env("NEO4J_USERNAME", "NEO4J_USER")
    neo4j_password: SecretStr | None = _env("NEO4J_PASSWORD")
    neo4j_database: str | None = _env("NEO4J_DATABASE")

    # Supabase(기존 .env 이름). 서비스 키는 서버에서만 쓴다
    supabase_url: str | None = _env("SUPABASE_URL")
    supabase_key: SecretStr | None = _env("SUPABASE_KEY")
    supabase_secret_key: SecretStr | None = _env("SUPABASE_SECRET_KEY")
    supabase_jwt_secret: SecretStr | None = _env("SUPABASE_JWT_SECRET")  # 예전 HS256 프로젝트만. 지금 프로젝트는 ES256(JWKS)라 비워 둔다
    # 관리자 허용 목록(명세 §1 "역할은 서버 쪽 허용 목록으로 확인"). 쉼표로 구분. 비우면 관리자 없음
    admin_emails: str = Field(default="", validation_alias="ADMIN_EMAILS")
    admin_user_ids: str = Field(default="", validation_alias="ADMIN_USER_IDS")

    # RunPod vLLM(OpenAI 호환 엔드포인트). 모델 크기·GPU가 정해지기 전에는 비워 둔다
    vllm_base_url: str | None = _env("VLLM_BASE_URL")  # 예: https://<pod-id>-8000.proxy.runpod.net/v1
    vllm_api_key: SecretStr | None = _env("VLLM_API_KEY")
    vllm_model: str | None = _env("VLLM_MODEL")
    vllm_timeout_s: float = Field(default=60.0, validation_alias="VLLM_TIMEOUT_S")

    @property
    def auth_configured(self) -> bool:
        return bool(self.supabase_url)

    def is_admin(self, user_id: str, email: str | None) -> bool:
        ids = {x.strip() for x in self.admin_user_ids.split(",") if x.strip()}
        emails = {x.strip().lower() for x in self.admin_emails.split(",") if x.strip()}
        return user_id in ids or bool(email and email.lower() in emails)

    @property
    def llm_configured(self) -> bool:
        return bool(self.vllm_base_url and self.vllm_model)


@lru_cache
def get_settings() -> Settings:
    return Settings()
