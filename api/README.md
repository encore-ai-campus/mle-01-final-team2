# 지원각 API (FastAPI)

판정은 규칙 평가기 코드가 하고(ADR-12), 모델은 추출·설명만 맡는다. 지금은 `tools/graphrag`의 엔진을 감싼 뼈대 위에 **오케스트레이터(감독)** 와 내부 에이전트 3개(자격 판정·공고 질의 RAG·용어 정의), 하이브리드 검색(`agent/rag/`), 모델 라우터(`agent/llm/`)를 붙였다.

## 구조 (기초 설계서 §13)

| 폴더 | 역할 | 상태 |
|---|---|---|
| `api/core/` | 설정(`config.py`, 기존 `.env` 이름을 읽음) | 있음 |
| `api/routers/` | 엔드포인트 | 구현: `GET /health`, `/health/llm`, `/health/graph`, `POST /api/eligibility`, `POST /api/chat`(SSE), `GET /api/graph/path`, `GET /api/concepts`, `GET /api/me`(개발용 로그인). 뼈대(501): 공고 N-01~03, 판정 E-02~04, 운영 M-01·M-03, 메타 S-01. 현황표는 [개발 시작 안내 §7](../docs/GUIDE_개발시작_v0.1.md#7-기능별-시작점) |
| `api/schemas/` | 요청·응답 모델(Pydantic) | 판정·채팅 |
| `api/services/` | 판정 엔진 어댑터. 판정 로직은 여기 다시 쓰지 않고 엔진을 호출한다 | 엔진 어댑터, 공고 지목 판정 |
| `api/dependencies/` | FastAPI 의존성(시험에서 가짜로 교체) | 판정 서비스, 모델 라우터, 그래프 저장소, 에이전트 그래프, 로그인·역할(`auth.py`, JWT 검증 전) |
| `api/repositories/` | Neo4j·Supabase 접근 | Neo4j 읽기 전용(`graph.py`): 지역 목록·경로·정의·판정 서브그래프. Supabase는 아직 |
| `agent/orchestrator.py` | **감독 오케스트레이터**(LangGraph): 입력 가드 → 계획(규칙 → 모호하면 모델 `route` 역할 구조화 출력 → 기본 판정) → 에이전트 실행 → 반성(다시 계획·다음·멈춤, 최대 3단계) → 마무리(`done` 1개). 판정 후보 상위 3개를 공고 질의 범위로 넘긴다 | 있음 |
| `agent/agents/notice_qa.py` | **공고 질의 에이전트**(CRAG): 검색 → 근거 채점 → (질의 재작성 1회) → 근거 없으면 보류(`NO_EVIDENCE`) → 답변(`[청크id]` 인용) → 인용 검증 | 있음 |
| `agent/agents/definition.py` | **용어 정의 에이전트**: 법령 원문 정의(`[def#용어]` 인용). 사전에 없으면 공고 질의로 다시 계획 | 있음 |
| `agent/rag/` | 하이브리드 검색: BM25(`tools/graphrag/search.py`) + 밀집 벡터(numpy 색인) → RRF 결합. 색인·임베딩이 없으면 BM25만 | 있음 |
| `agent/graph.py` | 자격 판정 에이전트(§7.1): 입력 가드 → 의도·조건 → 후보·규칙 평가 → 경로(`trace_path`) → 정의(`fetch_definition`) → 부족 조건 → 근거 검증 → 설명(문장 단위 출력 가드) | 있음 |
| `agent/llm/` | provider 어댑터(OpenAI 호환·템플릿), 역할별 폴백, 서킷브레이커, 데이터 정책 게이트(§3) | 있음 |
| `config/models.yaml` | 모델 레지스트리. 주소·모델 이름은 환경변수로 가리킨다 | 있음 |
| `deploy/llm_gateway/` | **LLM 게이트웨이**(vLLM 자리, OpenAI 호환): 뒤에서 외부 모델 gpt-6-luna(설명)·text-embedding-3-small(임베딩)을 부른다. 추론 모델 차이(`max_tokens`→`max_completion_tokens`, `temperature` 미지원)를 흡수한다 | 있음 |
| `deploy/mock_vllm/` | **vLLM 대역 서버**(OpenAI 호환, 진짜 모델 아님, 키 없이 시험) | 있음 |
| `deploy/docker-compose.yml` | 로컬 구성: 웹 + API + LLM 게이트웨이(대역 서버는 `--profile mock`) | 있음 |
| `web/` | 사용자 웹(Next.js): 채팅(오케스트레이션 진행·판정 카드·검색 근거·인용), 공고 목록·상세(섹션·경로 그래프·공고 질의), 운영 상태(`/admin`), 요건 검수(`/admin/reviews`). `/api/chat`은 Next 서버가 API로 SSE 중계. `/eligibility`는 모델 없이 규칙 판정만 하는 PoC 화면(2026-11-27 회의 결정 입력 포함) | 최소 화면 |

## 모델 호출 방식

API는 모델을 **OpenAI 호환 API**(`/v1/chat/completions`, `/v1/embeddings`)로만 부른다. RunPod vLLM(Qwen)이 뜨기 전에는 LLM 게이트웨이(외부 gpt-6-luna)나 대역 서버를 같은 방식으로 부르고, RunPod가 뜨면 환경변수만 바꾼다.

| 상황 | `VLLM_BASE_URL` | `VLLM_MODEL` | `VLLM_DATA_POLICY` |
|---|---|---|---|
| Docker 구성 안(자동, 게이트웨이) | `http://llm:8001/v1` | `gpt-6-luna` | `external` + `LLM_ALLOW_EXTERNAL_ANSWER=1` |
| Docker 대역 서버(`--profile mock`, `LLM_URL`·`LLM_MODEL` 덮어쓰기) | `http://llm-mock:8001/v1` | `mock-qwen` | 비움 |
| 로컬에서 대역 서버 직접 실행 | `http://localhost:8001/v1` | `mock-qwen` | 비움 |
| RunPod vLLM | `https://<pod-id>-8000.proxy.runpod.net/v1` | 서빙한 모델 이름 | `self_hosted`(기본) |

- 외부 모델 허용은 **사용자 결정(2026-11-28, 로컬 시험 전용, 팀 검토 전)** 이다. 보내는 것은 질문 문장·조건별 평가 결과·공개 공고 원문이며, 입력 가드가 번호·연락처를 먼저 막는다. 허용이 없으면 외부 provider는 설명 역할에서 건너뛴다.
- 역할: `answer`(설명·공고 질의·정의), `route`(모호한 질문 분류, 구조화 출력), 임베딩은 `config/models.yaml`의 `embedding`.
- `VLLM_BASE_URL`이 비어 있으면 모델 없이 **규칙 판정만** 낸다(`outcome=degraded`, "설명 생성 불가" 배너).
- 재시도는 한 계층에서만 한다. SDK 재시도는 끄고, 장애면 라우터가 다음 provider로, 구조화 출력 검증 실패면 1회만 다시 묻는다.
- 스트리밍은 첫 조각이 오기 전까지만 다음 provider로 넘긴다.
- 대역 서버 시험 표식: 질문에 `[[mock:error]]`를 넣으면 503, `[[mock:forbidden]]`이면 금지 표현이 섞인 답을 낸다(출력 가드 확인용).

## `POST /api/chat` 이벤트 (SSE)

`event: <종류>` + `data: {"type": "<종류>", ...}`. 요청 `agent`는 `auto`(기본)·`eligibility`·`notice_qa`·`definition`. 에이전트마다 근거 이벤트(판정·검색)가 설명 토큰보다 먼저 나가고, `done`은 마지막에 1개만 나간다.

| 이벤트 | 내용 |
|---|---|
| `route` | 계획: `plan`(에이전트 순서), `method`(`rule`·`llm`·`default`·`replan`), `intent` |
| `agent` | 에이전트 시작·끝(`name`, `status`, 끝이면 `outcome`·`reason_code`) |
| `retrieval` | 공고 질의 검색 결과: 청크 id·공고 제목·섹션·밀집 유사도·BM25/밀집 순위·본문 앞부분, `mode`(`hybrid`·`bm25`) |
| `citation` | 답변이 실제로 인용한 청크 id |
| `ask` | 되묻기(조건이 하나도 없을 때, 최대 2회) |
| `verdict` | 공고별 판정, 미확인 조건 id, 출처 주소, 수집 시각. `REQ_UNPARSED`면 `unparsed_text`(자동으로 해석하지 못한 자격·제외 요건 원문 구역 최대 3개, 판정에는 쓰지 않음). 설명은 이 구역 id를 `[id]`로 인용해 사용자가 확인할 항목을 짚는다 |
| `requirement` | 조건별 평가 값, 사유, 원문 근거 |
| `path` | 지역 계층 경로. Neo4j가 있으면 `source: "neo4j"`(사용자 지역 → `WITHIN`·`MEMBER_OF` ≤3 hop → 조건 지역), 없거나 장애면 `source: "evaluator"` |
| `definition` | 조건 개념의 정의 → 법령 조문(`law`, `article_no`, `law_url`). 법령이 끊기면 `broken: true` |
| `token` | 설명 문장(`agent`로 어느 에이전트 답인지 표시). 출력 가드를 통과한 문장만 나간다. 고정 문구는 `source: "template"` |
| `banner` | `SERVICE_DEGRADED`, `OUTPUT_BLOCKED`, `STALE_DATA`, `EVIDENCE_MISSING`, `GRAPH_UNAVAILABLE` |
| `usage` | 입력·출력 토큰 수 |
| `done` | `outcome`, `reason_code`(마지막 에이전트 기준), `agents`, `plan`, `route_method`, `intent`, `runs`(에이전트별 결과), `tools_used`, `provider`, `fallback_depth`, `prompt_version` |

## 그래프 (Neo4j Aura, 읽기 전용)

`.env`에 `NEO4J_URI`·`NEO4J_USERNAME`(또는 `NEO4J_USER`)·`NEO4J_PASSWORD`가 있으면 요청 때 Aura를 읽는다. 없으면 경로는 평가기 결과로, 정의는 생략하고 판정은 그대로 나온다.

- `GET /api/concepts?scheme=region`: 입력 폼 지역 목록(그래프가 없으면 내장 지역 사전). 지역 id는 `REGION:<법정동코드>` 형식이다.
- `GET /api/graph/path?notice_id=&region=`: 공고 → 요건 → 조건 → 개념(→ 사용자 지역 경로) → 정의 → 조문 → 법령 서브그래프(`nodes`, `edges`). 그래프 미설정 503, 공고 없음 404.
- `GET /health/graph`: 연결만 확인한다(주소는 내보내지 않는다).

## RAG 색인

공고 청크(약 3.3만 개)의 밀집 벡터 색인을 호스트에서 한 번 만든다(`data/index/`, git 제외). 바뀐 청크만 다시 임베딩한다.

```powershell
$env:EMBED_BASE_URL="http://localhost:8001/v1"; .venv\Scripts\python -m agent.rag.build_index
```

- 게이트웨이(`docker compose ... up llm`)가 떠 있어야 한다. `--open-only`는 접수 중 공고만 색인한다.
- 색인 상태: `GET /health/index`(`dense`, 청크 수, 마지막 오류). 색인이 없거나 임베딩이 실패하면 BM25만 쓴다.
- 근거 채점 기준(실측): 밀집 유사도 0.50 이상(공고를 지목했으면 0.30), BM25만일 때는 질의어 겹침 0.50 이상.

## 로그인 (A-01)

웹(`/login`)이 Supabase Auth로 로그인하고, 우리 API를 부를 때 `Authorization: Bearer <액세스 토큰>`을 붙인다(`web/lib/auth.ts`의 `apiFetch`).

- API는 토큰을 Supabase JWKS(ES256)로 검증한다. 발급자·대상(`authenticated`)·만료를 확인한다(`api/dependencies/auth.py`). 예전 HS256 프로젝트면 `SUPABASE_JWT_SECRET`.
- 역할은 서버 허용 목록 `ADMIN_EMAILS`·`ADMIN_USER_IDS`로 정한다. 토큰 안의 역할 값은 보지 않는다.
- `GET /api/auth/config`: 로그인 화면용 공개 설정(Supabase 주소, publishable 키, 켜 둔 로그인 방법). 서비스·비밀 키는 내보내지 않는다.
- `GET /api/me`: 로그인 사용자·역할·이메일.
- 로컬 개발(`APP_ENV=local` + `APP_DEV_AUTH=1`)에서 토큰이 없으면 개발용 사용자(`X-Dev-Role: admin`이면 관리자)다. 토큰이 있으면 로컬에서도 검증한다.
- 오류: 토큰 없음·잘못됨 401, 만료 401 `TOKEN_EXPIRED`, 관리자 아님 403 `ROLE_DENIED`, JWKS에 닿지 않음 503.

## 요건 검수 큐 (관리자)

`/api/admin/reviews`(`api/routers/reviews.py`)는 REQ_UNPARSED 공고의 요건을 사람이 조건으로 옮기는 검수 API다. 웹 화면은 `/admin/reviews`다. 설계·화면 설명은 `docs/DESIGN_요건검수큐_v0.1.md` §5-1에 있다.

- `GET /api/admin/reviews`(`status`·`source`·`open_only`·`q`·`offset`·`limit`), `GET /api/admin/reviews/{id}`, `PUT /api/admin/reviews/{id}`(`action`: save·verify·reopen), `POST /api/admin/reviews/ingest`.
- 큐 파일(`data/reviews/requirements/queue.jsonl`)이 없으면 503이다. 관리자가 아니면 403이다. 로컬 개발에서는 `X-Dev-Role: admin`.
- ingest 뒤 API를 다시 띄워야 판정에 반영된다.

아직 없는 것: `/admin/runs`·`/admin/reprocess`, `profiles`·`audit_logs` 표, what-if(P1), 출력 가드 1회 재생성, Langfuse 기록, 그래프 시각화(지금 웹은 간선 표로만 보여 준다).

## 실행 (Docker, 권장)

저장소 맨 위에서 Docker Desktop(WSL 2)을 켠 뒤 실행한다. 판정 데이터(`data/`)는 읽기 전용으로 붙는다.

```powershell
docker compose -f deploy/docker-compose.yml up --build
```

- 웹: `http://localhost:3000` (브라우저 → web → api → LLM 게이트웨이 → gpt-6-luna). `.env`에 `OPEN_API`(또는 `OPENAI_API_KEY`)가 있어야 한다
- 키 없이: `docker compose -f deploy/docker-compose.yml --profile mock up --build`에 셸 환경변수 `LLM_URL=http://llm-mock:8001/v1`, `LLM_MODEL=mock-qwen`, `LLM_DATA_POLICY=self_hosted`, `LLM_ALLOW_EXTERNAL=`
- API: `http://localhost:8000/docs`, 모델 연결 확인: `http://localhost:8000/health/llm`, 그래프 연결 확인: `http://localhost:8000/health/graph`
- 게이트웨이: `http://localhost:8001/v1/models`, 대역 서버(mock): `http://localhost:8002/v1/models`, 검색 색인: `http://localhost:8000/health/index`
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
.venv\Scripts\python -m unittest tests.test_api tests.test_agent tests.test_orchestration -v
```

대역 서버를 같은 프로세스에서 OpenAI 호환 API로 부르므로 네트워크·GPU·데이터 없이 돈다. 패키지가 없으면 건너뛴다.

## 의존성 파일

| 파일 | 용도 |
|---|---|
| `requirements.txt` | API·에이전트 실행(범위 지정) |
| `requirements.lock.txt` | 위 범위를 실제로 설치해 해석된 버전(Docker가 사용) |
| `requirements-tools.txt` | 수집·정규화·첨부 추출·문서 도구 |
| `requirements-dev.txt` | 위 둘 + 시험 도구 |
