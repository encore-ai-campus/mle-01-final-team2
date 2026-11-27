# 개발 시작 안내 v0.1

| 항목 | 내용 |
|---|---|
| 대상 | 기능 개발을 새로 시작하는 팀원 |
| 작성 | 2026-11-27 |
| 함께 볼 문서 | [API 명세서](design/API_명세서_v0.1.md), [API 뼈대 안내](../api/README.md), [그래프·판정 도구 안내](GUIDE_도구_사용안내_v0.1.md), [kordoc 안내](GUIDE_kordoc_설치_v0.1.md) |

## 1. 준비물

| 도구 | 버전 | 용도 |
|---|---|---|
| git | 아무 버전 | |
| [uv](https://docs.astral.sh/uv/) | 0.11 이상 | 파이썬과 패키지 설치. Python 3.12도 uv가 받아 준다 |
| Node.js | 20 이상 | 웹(`web/`). 첨부를 새로 추출할 때만 kordoc에도 쓴다 |
| Docker | 선택 | 배포 구성 확인(`deploy/docker-compose.yml`)할 때만 |

uv 설치(Windows PowerShell):

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

macOS·Linux는 `curl -LsSf https://astral.sh/uv/install.sh | sh`.

## 2. 설치

저장소 루트에서 한 번 실행한다.

```powershell
uv sync
```

- `.python-version`(3.12)에 맞는 파이썬으로 저장소 루트에 `.venv`를 만든다. 그다음 `uv.lock`에 적힌 버전 그대로 서버·도구·시험 패키지를 모두 설치한다.
- 이미 pip로 만든 `.venv`가 있으면 uv가 그 환경을 lock에 맞게 고친다. lock에 없는 패키지는 지운다.
- 명령은 `uv run <명령>`으로 실행한다. 가상환경을 켜 두었다면(`.venv\Scripts\activate`) `python ...`으로 실행해도 된다.

| 하고 싶은 일 | 명령 |
|---|---|
| 서버 패키지만 설치(배포 이미지와 같게) | `uv sync --no-default-groups` |
| 패키지 추가 | `uv add <패키지>`(서버) 또는 `uv add --group tools <패키지>`(도구). 같은 범위를 `requirements*.txt`에도 적는다 |
| lock 다시 만들기 | `uv lock` |
| pip로 설치(uv를 못 쓸 때) | `python -m pip install -r requirements-dev.txt` |

`requirements*.txt`는 Docker 이미지(`api/Dockerfile`)와 CI가 쓴다. `pyproject.toml`과 범위가 다르면 `tools/test_project_deps.py`가 실패한다. 의존성을 바꿀 때는 `pyproject.toml`·`requirements*.txt`·`uv.lock`을 한 커밋에 같이 고친다.

웹:

```powershell
npm --prefix web ci
copy web\.env.example web\.env.local
```

## 3. 환경 변수

```powershell
copy .env.example .env
```

- `.env`는 git에 올리지 않는다. 값은 팀 안에서만 전한다. 비어 있어도 서버는 뜬다. 그때 그래프 경로·모델 설명은 빠지고, 판정은 로컬 데이터로 한다.
- 로그인 검증(A-01)이 구현되기 전에는 `APP_ENV=local`, `APP_DEV_AUTH=1`을 넣어야 로그인이 필요한 뼈대 엔드포인트를 호출할 수 있다. 이때 사용자는 가짜 `local-dev`가 된다. `X-Dev-Role: admin` 헤더를 붙이면 관리자로 바뀐다. 배포 환경에서는 켜지지 않는다.
- Aura(Neo4j)는 **팀 공용**이다. 읽기·dry-run은 자유지만 쓰기(`--apply`)는 팀 승인을 받은 뒤에만 한다.

## 4. 실행

| 무엇 | 명령 | 주소 |
|---|---|---|
| API | `uv run uvicorn api.main:app --reload --port 8000` | http://localhost:8000/docs |
| 웹 | `npm --prefix web run dev` | http://localhost:3000 |
| 모델 대역 서버(설명 생성 시험) | `uv run uvicorn deploy.mock_vllm.app:app --port 8001` | `.env`에 `VLLM_BASE_URL=http://localhost:8001/v1`, `VLLM_MODEL=mock-qwen` |

웹은 브라우저에서 API를 직접 부르지 않는다. 항상 Next 서버의 중계 라우트(`web/app/api/*/route.ts`)를 거친다. 같은 와이파이의 다른 기기에서는 `http://<내 PC IP>:3000`으로 열린다.

## 5. 시험

```powershell
uv run python -m unittest discover -s tests         # 서버·에이전트·조건(로컬 데이터가 없으면 해당 시험은 건너뜀)
uv run python -m unittest tools.test_graphrag tools.test_project_deps
npm --prefix web run typecheck
uv run ruff check . --select E9
```

CI(`.github/workflows/tools-tests.yml`)는 PR마다 `tools/test_*.py`와 데이터 없이 도는 `tests/` 시험을 돌린다. 문서만 바꾼 PR에서는 돌지 않는다.

## 6. 데이터

| 구분 | 위치 | git |
|---|---|---|
| 정리층 공고·청크, 지역 사전, 법령, 용어 사전, 정답셋 | `data/cleaned/`, `data/사전/`, `data/지원사업_법령/`, `data/ref/`, `data/goldsets/` | 있음. 판정·API는 이것만으로 돈다 |
| 그래프 내보내기 | `data/graph/nodes.jsonl`·`edges.jsonl` | 없음. `uv run python tools/graphrag/build.py export`로 만든다 |
| 첨부 원본·추출 글, K-Startup 원본, 나라장터 정규화 스냅숏, `api_samples/` | `data/bizinfo/files/`, `data/bizinfo/extracted/`, `data/kstartup/raw/`, `data/normalized/v1/20261125_g2b/` 등 | 없음(용량·저작권). 필요하면 팀 공유 묶음으로 받는다 |

로컬 전용 데이터가 필요한 시험에는 `tests/local_data.py`의 `@needs(...)`가 붙어 있다. 데이터가 없으면 오류 대신 건너뛴다.

## 7. 기능별 시작점

아직 구현하지 않은 엔드포인트는 뼈대만 있다. 호출하면 `501 NOT_IMPLEMENTED`와 명세 ID, 할 일(`todo`)을 돌려준다. 구현할 때 할 일은 네 가지다.

1. 해당 라우터 함수의 `raise not_implemented(...)`를 실제 코드로 바꾼다.
2. 로직은 `api/services/`에, DB 접근은 `api/repositories/`에 둔다.
3. `tests/test_api_skeleton.py`의 `STUBS`에서 그 줄을 빼고, 진짜 시험을 새로 쓴다.
4. 아래 표의 상태를 고친다.

| 기능 | 명세 | 우선 | API 파일 | 웹 화면 | 데이터·참고 | 상태 |
|---|---|---|---|---|---|---|
| 로그인·역할 | A-01 `GET /api/me` | P0 | `api/dependencies/auth.py`, `api/routers/me.py` | (Supabase Auth, 프론트 SDK) | Supabase JWT, `profiles.role`. 기초 설계서 §8 | 뼈대(개발용 가짜 로그인만) |
| 공고 목록·검색 | N-01 `GET /api/notices` | P0 | `api/routers/notices.py` | `web/app/notices/page.tsx` | `data/cleaned/`, `tools/graphrag/engine.py` | 뼈대 |
| 공고 상세·원문 | N-02 `GET /api/notices/{id}` | P0 | `api/routers/notices.py` | `web/app/notices/[id]/page.tsx` | 정리층 원문 구역 | 뼈대 |
| 근거 문장 위치 | N-03 `.../spans` | P0 | `api/routers/notices.py` | 상세 화면 | 조건 evidence | 뼈대 |
| 개념 검색 | C-01 `GET /api/concepts` | P0 | `api/routers/graph.py` | 판정 폼 | 지역 사전, 그래프 | 지역만 있음 |
| 조건으로 판정 | E-01 `POST /api/eligibility` | P0 | `api/routers/eligibility.py` | `web/app/eligibility/page.tsx` | 규칙 평가기 | 있음 |
| 조건별 검증표 | E-02 `GET /api/eligibility/{id}` | P0 | `api/routers/eligibility.py` | 상세 화면 | E-01 결과. `evaluation_id` 규칙(명세 §5.0) 먼저 | 뼈대 |
| 추론 경로 | E-03 `.../path` | P0 | `api/routers/eligibility.py` | 상세 화면 | `GET /api/graph/path`(있음)를 감싼다 | 뼈대 |
| 되묻기 재판정 | E-04 `POST /api/eligibility/clarify` | P0 | `api/routers/eligibility.py` | 상세 화면 | | 뼈대 |
| 챗봇 | H-01 `POST /api/chat`(SSE) | P0 | `api/routers/chat.py`, `agent/` | 홈(`web/app/page.tsx`) | 모델 대역 서버 | 있음(대역 모델) |
| 운영 현황 | M-01 `GET /api/admin/status` | P0 | `api/routers/admin.py` | `web/app/admin/page.tsx` | 수집 보고서, `/health/*` | 뼈대 |
| 실패 건 재처리 | M-03 `POST /api/admin/reprocess` | P0 | `api/routers/admin.py` | 운영자 화면 | 첨부 추출 보고서 | 뼈대 |
| 기준 시각·버전·면책 | S-01 `GET /api/meta` | P0 | `api/routers/meta.py` | 모든 화면 배지 | 수집 manifest | 뼈대 |
| P1 기능(동의·내 조건·대화 이력·신청 문서·what-if·검수) | 명세 §5~§9 | P1 | 새 라우터 파일 | | | 없음 |

오류 응답은 지금 `{"detail": {"error": {"code", "message"}}}` 모양이다(`api/core/errors.py`). 명세 §2.1의 공통 틀(`data`·`outcome`·`reason_codes`·`meta`)로 바꾸는 일은 따로 정해서 한 번에 한다.

## 8. 작업 규칙

- `main`에 직접 올리지 않는다. 브랜치(`feat/…`, `fix/…`, `docs/…`)에서 작업하고 PR을 연다. CI가 통과해야 머지한다. 머지한 브랜치는 지운다.
- 판정 규칙(평가기 해석)은 혼자 바꾸지 않는다. [판정 정규화 검토 목록](RULES_판정_정규화_검토목록_v0.1.md)에서 팀이 정한다.
- 평가용 정답(evaluation split)은 개발에 쓰지 않는다.
- 올리지 않는 것: `.env`, 첨부 원본·추출 글, `share/`, 개인 PC 경로가 들어간 메모.
