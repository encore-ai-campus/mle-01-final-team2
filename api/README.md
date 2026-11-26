# 지원각 API (FastAPI)

판정은 규칙 평가기 코드가 하고(ADR-12), 모델은 추출·설명만 맡는다. 지금은 `tools/graphrag`의 엔진을 감싼 뼈대다.

## 구조 (기초 설계서 §13)

| 폴더 | 역할 | 상태 |
|---|---|---|
| `core/` | 설정(`config.py`, 환경변수 접두사 `JIWONGAK_`) | 있음 |
| `routers/` | 엔드포인트 | `GET /health`, `POST /api/eligibility` |
| `schemas/` | 요청·응답 모델(Pydantic) | 판정 입력·응답 |
| `services/` | 업무 로직 어댑터. 판정 로직은 여기 다시 쓰지 않고 엔진을 호출한다 | 엔진 어댑터 |
| `dependencies/` | FastAPI 의존성(시험에서 가짜로 교체) | 판정 서비스 |
| `repositories/` | Neo4j·Supabase 접근 | 비어 있음 |
| `Dockerfile` | AWS CPU 서버용 이미지(포트 8000, 비root 실행, 헬스체크) | 빌드 안 해 봄 |

## 배포 구성 (팀 결정)

| 구성 | 위치 | API가 읽는 환경변수 |
|---|---|---|
| API(이 서버) | AWS CPU 서버, Docker | `APP_ENV`, `APP_CORS_ORIGINS`, `APP_USE_CLEANED` |
| LLM | RunPod GPU의 vLLM(OpenAI 호환) | `VLLM_BASE_URL`, `VLLM_API_KEY`, `VLLM_MODEL`, `VLLM_TIMEOUT_S` |
| 그래프 | Neo4j Aura | `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE` |
| 원문·사용자 | Supabase | `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SECRET_KEY`, `SUPABASE_JWT_SECRET` |

Neo4j·Supabase 이름은 적재 스크립트가 쓰는 기존 `.env`와 같다. `/health`는 설정이 있는지만 `true/false`로 알리고 값은 내보내지 않는다. vLLM 값은 모델이 정해지기 전까지 비워 둔다.

아직 없는 것: `POST /api/chat`(SSE, LangGraph 에이전트), `GET /api/notices/{id}`, `GET /api/graph/path`, `GET /api/concepts`, `/admin/*`, 로그인(JWT 검증).

## 실행

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\pip install -r requirements-dev.txt
```

```powershell
.venv\Scripts\uvicorn api.main:app --reload
```

`http://localhost:8000/docs`에서 시험해 볼 수 있다. 판정 데이터는 `data/cleaned`(없으면 원본 파서 결과)를 읽으므로 데이터가 있는 PC에서만 실제 결과가 나온다.

## 시험

```powershell
.venv\Scripts\python -m unittest tests.test_api -v
```

가짜 판정 서비스를 넣어 데이터 없이 돈다. fastapi가 설치되지 않은 환경에서는 건너뛴다.

## 의존성 파일

| 파일 | 용도 |
|---|---|
| `requirements.txt` | API·에이전트 실행(범위 지정) |
| `requirements.lock.txt` | 위 범위를 실제로 설치해 해석된 버전(Docker가 사용) |
| `requirements-tools.txt` | 수집·정규화·첨부 추출·문서 도구 |
| `requirements-dev.txt` | 위 둘 + 시험 도구 |
