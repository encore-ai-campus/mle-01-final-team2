# 지원각 API (FastAPI)

판정은 규칙 평가기 코드가 하고(ADR-12), 모델은 추출·설명만 맡는다. 지금은 `tools/graphrag`의 엔진을 감싼 뼈대 위에 LangGraph 에이전트(`agent/`)와 모델 라우터(`agent/llm/`)를 붙였다.

## 구조 (기초 설계서 §13)

| 폴더 | 역할 | 상태 |
|---|---|---|
| `api/core/` | 설정(`config.py`, 기존 `.env` 이름을 읽음) | 있음 |
| `api/routers/` | 엔드포인트 | `GET /health`, `/health/llm`, `/health/graph`, `POST /api/eligibility`, `POST /api/chat`(SSE), `GET /api/graph/path`, `GET /api/concepts` |
| `api/schemas/` | 요청·응답 모델(Pydantic) | 판정·채팅 |
| `api/services/` | 판정 엔진 어댑터. 판정 로직은 여기 다시 쓰지 않고 엔진을 호출한다 | 엔진 어댑터, 공고 지목 판정 |
| `api/dependencies/` | FastAPI 의존성(시험에서 가짜로 교체) | 판정 서비스, 모델 라우터, 그래프 저장소, 에이전트 그래프 |
| `api/repositories/` | Neo4j·Supabase 접근 | Neo4j 읽기 전용(`graph.py`): 지역 목록·경로·정의·판정 서브그래프. Supabase는 아직 |
| `agent/graph.py` | LangGraph 에이전트(§7.1): 입력 가드 → 의도·조건 → 후보·규칙 평가 → 경로(`trace_path`) → 정의(`fetch_definition`) → 부족 조건 → 근거 검증 → 설명(문장 단위 출력 가드) | 있음 |
| `agent/llm/` | provider 어댑터(OpenAI 호환·템플릿), 역할별 폴백, 서킷브레이커, 데이터 정책 게이트(§3) | 있음 |
| `config/models.yaml` | 모델 레지스트리. 주소·모델 이름은 환경변수로 가리킨다 | 있음 |
| `deploy/mock_vllm/` | **vLLM 대역 서버**(OpenAI 호환, 진짜 모델 아님) | 있음 |
| `deploy/docker-compose.yml` | 로컬 구성: 웹 + API + 대역 서버 | 있음 |
| `web/` | 최소 사용자 웹(Next.js): 조건 입력 → 판정 카드·요건·경로·정의·설명. `/api/chat`은 Next 서버가 API로 SSE 중계 | 최소 화면 |

## 모델 호출 방식

API는 모델을 **OpenAI 호환 API**(`/v1/chat/completions`)로만 부른다. 로컬 LLM이 준비되기 전에는 대역 서버(`deploy/mock_vllm`)를 띄워 같은 방식으로 부르고, RunPod vLLM이 뜨면 환경변수만 바꾼다.

| 상황 | `VLLM_BASE_URL` | `VLLM_MODEL` |
|---|---|---|
| Docker 구성 안(자동) | `http://llm:8001/v1` | `mock-qwen` |
| 로컬에서 대역 서버 직접 실행 | `http://localhost:8001/v1` | `mock-qwen` |
| RunPod vLLM | `https://<pod-id>-8000.proxy.runpod.net/v1` | 서빙한 모델 이름 |

- `VLLM_BASE_URL`이 비어 있으면 모델 없이 **규칙 판정만** 낸다(`outcome=degraded`, "설명 생성 불가" 배너).
- 재시도는 한 계층에서만 한다. SDK 재시도는 끄고, 장애면 라우터가 다음 provider로, 구조화 출력 검증 실패면 1회만 다시 묻는다.
- 스트리밍은 첫 조각이 오기 전까지만 다음 provider로 넘긴다.
- 대역 서버 시험 표식: 질문에 `[[mock:error]]`를 넣으면 503, `[[mock:forbidden]]`이면 금지 표현이 섞인 답을 낸다(출력 가드 확인용).

## `POST /api/chat` 이벤트 (SSE)

`event: <종류>` + `data: {"type": "<종류>", ...}`. 판정·요건 이벤트가 설명 토큰보다 먼저 나간다.

| 이벤트 | 내용 |
|---|---|
| `ask` | 되묻기(조건이 하나도 없을 때, 최대 2회) |
| `verdict` | 공고별 판정, 미확인 조건 id, 출처 주소, 수집 시각 |
| `requirement` | 조건별 평가 값, 사유, 원문 근거 |
| `path` | 지역 계층 경로. Neo4j가 있으면 `source: "neo4j"`(사용자 지역 → `WITHIN`·`MEMBER_OF` ≤3 hop → 조건 지역), 없거나 장애면 `source: "evaluator"` |
| `definition` | 조건 개념의 정의 → 법령 조문(`law`, `article_no`, `law_url`). 법령이 끊기면 `broken: true` |
| `token` | 설명 문장. 출력 가드를 통과한 문장만 나간다. 고정 문구는 `source: "template"` |
| `banner` | `SERVICE_DEGRADED`, `OUTPUT_BLOCKED`, `STALE_DATA`, `EVIDENCE_MISSING`, `GRAPH_UNAVAILABLE` |
| `usage` | 입력·출력 토큰 수 |
| `done` | `outcome`, `reason_code`, `tools_used`, `provider`, `fallback_depth`, `prompt_version` |

## 그래프 (Neo4j Aura, 읽기 전용)

`.env`에 `NEO4J_URI`·`NEO4J_USER`·`NEO4J_PASSWORD`가 있으면 요청 때 Aura를 읽는다. 없으면 경로는 평가기 결과로, 정의는 생략하고 판정은 그대로 나온다.

- `GET /api/concepts?scheme=region`: 입력 폼 지역 목록(그래프가 없으면 내장 지역 사전). 지역 id는 `REGION:<법정동코드>` 형식이다.
- `GET /api/graph/path?notice_id=&region=`: 공고 → 요건 → 조건 → 개념(→ 사용자 지역 경로) → 정의 → 조문 → 법령 서브그래프(`nodes`, `edges`). 그래프 미설정 503, 공고 없음 404.
- `GET /health/graph`: 연결만 확인한다(주소는 내보내지 않는다).

아직 없는 것: `GET /api/notices/{id}`, `/admin/*`, 로그인(JWT 검증), what-if(P1), 출력 가드 1회 재생성, Langfuse 기록, 그래프 시각화(지금 웹은 간선 표로만 보여 준다).

## 실행 (Docker, 권장)

저장소 맨 위에서 Docker Desktop(WSL 2)을 켠 뒤 실행한다. 판정 데이터(`data/`)는 읽기 전용으로 붙는다.

```powershell
docker compose -f deploy/docker-compose.yml up --build
```

- 웹: `http://localhost:3000` (브라우저 → web → api → 대역 서버)
- API: `http://localhost:8000/docs`, 모델 연결 확인: `http://localhost:8000/health/llm`, 그래프 연결 확인: `http://localhost:8000/health/graph`
- 대역 서버: `http://localhost:8001/v1/models`
- 끄기:

```powershell
docker compose -f deploy/docker-compose.yml down
```

## 실행 (Docker 없이)

```powershell
python -m venv .venv
```

```powershell
.venv\Scripts\pip install -r requirements-dev.txt
```

대역 서버를 먼저 띄운다(창 하나).

```powershell
.venv\Scripts\uvicorn deploy.mock_vllm.app:app --port 8001
```

다른 창에서 `.env`에 `VLLM_BASE_URL=http://localhost:8001/v1`, `VLLM_MODEL=mock-qwen`을 두고 API를 띄운다.

```powershell
.venv\Scripts\uvicorn api.main:app --reload
```

판정 데이터는 `data/cleaned`(없으면 원본 파서 결과)를 읽으므로 데이터가 있는 PC에서만 실제 결과가 나온다.

웹만 따로 띄울 때(API가 8000에 떠 있어야 한다). `web/.env.example`을 `web/.env.local`로 복사한다.

```powershell
cd web; npm install; npm run dev
```

## 시험

```powershell
.venv\Scripts\python -m unittest tests.test_api tests.test_agent -v
```

대역 서버를 같은 프로세스에서 OpenAI 호환 API로 부르므로 네트워크·GPU·데이터 없이 돈다. 패키지가 없으면 건너뛴다.

## 의존성 파일

| 파일 | 용도 |
|---|---|
| `requirements.txt` | API·에이전트 실행(범위 지정) |
| `requirements.lock.txt` | 위 범위를 실제로 설치해 해석된 버전(Docker가 사용) |
| `requirements-tools.txt` | 수집·정규화·첨부 추출·문서 도구 |
| `requirements-dev.txt` | 위 둘 + 시험 도구 |
