# 배포 점검 안내 v0.1

작성 2026-11-28. API는 AWS CPU 서버(Docker), 웹은 Vercel, LLM은 RunPod vLLM, 그래프는 Neo4j Aura, 로그인·사용자는 Supabase다(팀 결정).
이 문서는 배포 직전에 확인할 설정을 모은다. 실제 배포는 각 계정이 있어야 해서 아직 하지 않았다.

## 1. 자동 점검

```powershell
.venv\Scripts\python -m api.core.deploy_check --env prod --online
```

- 값은 출력하지 않고 있음·없음·모양만 본다. ERROR가 있으면 종료 코드가 1이다.
- API는 시작할 때 같은 점검을 돌려 로그(`jiwongak.deploy`)에 남긴다.
- `--online`은 Supabase 서명 키(JWKS)에 닿는지도 본다.

| 수준 | 점검 |
|---|---|
| ERROR(배포) | `SUPABASE_URL` 없음 또는 https 아님 |
| ERROR(배포) | `SUPABASE_KEY`가 publishable 키가 아님 |
| ERROR(항상) | `SUPABASE_KEY`에 비밀(서비스) 키를 넣음 |
| ERROR(배포) | `ADMIN_EMAILS`·`ADMIN_USER_IDS`가 비어 관리자가 없음 |
| WARN | `APP_DEV_AUTH` 켜짐 |
| WARN | `APP_CORS_ORIGINS`에 `*`·localhost |
| WARN | LLM·Neo4j 설정 없음 |
| WARN | 검수 큐 파일 없음 |

## 2. API (AWS, Docker)

| 변수 | 배포 값 | 이유 |
|---|---|---|
| `APP_ENV` | `prod` | local이 아니면 개발용 가짜 로그인이 꺼진다. 토큰 없는 요청은 401 |
| `APP_DEV_AUTH` | 비움 | 배포에서는 무시되지만 혼동을 막는다 |
| `SUPABASE_URL`, `SUPABASE_KEY` | 팀 프로젝트 주소, publishable 키 | 토큰 검증과 로그인 화면 공개 설정 |
| `SUPABASE_SECRET_KEY` | 서버에만 | 브라우저로 내보내지 않는다 |
| `ADMIN_EMAILS` | 관리자 이메일(쉼표) | 검수 화면 접근 |
| `APP_CORS_ORIGINS` | `["https://<웹 주소>"]` | 브라우저는 웹 서버만 부르므로 사실상 쓰이지 않지만 좁혀 둔다 |
| `VLLM_*`, `EMBED_*`, `NEO4J_*` | 각 서비스 값 | 설명 문장·벡터 검색·근거 경로 |

- 컨테이너는 `data/`를 읽기 전용으로, `data/reviews/`만 쓰기로 붙인다(`deploy/docker-compose.yml`과 같게).
- 검수 반영(ingest)은 API를 다시 띄우지 않아도 판정 엔진이 바로 다시 읽는다. 다만 API 프로세스가 여러 개면 요청을 받은 프로세스만 다시 읽는다. 워커는 1개로 두거나, 반영 뒤 `POST /api/admin/reviews/reload`를 프로세스마다 부른다.

## 3. 웹 (Vercel)

| 변수 | 배포 값 | 이유 |
|---|---|---|
| `API_BASE_URL` | `https://<API 주소>` | Next 서버가 API를 부른다. 브라우저로는 내보내지 않는다 |
| `DEV_ADMIN` | **넣지 않는다** | 로컬 개발용 관리자 흉내 헤더. API가 prod면 무시하지만 넣지 않는다 |

Supabase 주소·키는 웹에 넣지 않는다. 웹이 API(`/api/auth/config`)에서 받는다.

## 4. Supabase (대시보드, 계정 필요)

- Authentication → URL Configuration
  - Site URL: 배포 웹 주소
  - Redirect URLs: `https://<웹 주소>/login`, `http://localhost:3000/login`
- Google 로그인: 2026-11-30(월)에 동료 계정으로 켠다(`docs/REVIEW_팀검토_주말임시결정과_남은결정_v0.1.md` 3부). Google Cloud OAuth의 승인된 origin에 배포 웹 주소도 넣는다.

## 5. 배포 뒤 확인

1. `GET /health`, `/health/llm`, `/health/graph`, `/health/index`
2. 로그인하지 않고 `POST /api/eligibility` → 401
3. 웹 `/login`에서 로그인 → 머리글에 이메일 표시, 관리자면 "(관리자)"
4. `/admin/reviews` 목록이 열리는지
