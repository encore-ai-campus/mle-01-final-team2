# 그래프·판정 도구 사용 안내 v0.1

| 항목 | 내용 |
|---|---|
| 목적 | 그래프 내보내기, Aura 점검·부분 적재, 검수 준비, 판정 회귀를 명령 한 줄씩 정리했다 |
| 대상 | `tools/` 아래 그래프·판정 도구. 수집·정규화 도구는 각 파일의 설명을 본다 |
| 설치 | `uv sync`([개발 시작 안내](GUIDE_개발시작_v0.1.md)). pip라면 `python -m pip install -r requirements-tools.txt` |
| 접속 정보 | Aura 도구는 `.env`의 `NEO4J_URI`·`NEO4J_USERNAME`(또는 `NEO4J_USER`)·`NEO4J_PASSWORD`를 읽는다. 값은 출력하지 않는다 |
| 공용 DB | Aura는 팀 공용이다. **쓰기(`--apply`)는 승인을 받은 뒤에만** 한다. 점검·dry-run은 읽기 전용이다 |

## 한눈에

| 하고 싶은 일 | 명령 | DB |
|---|---|---|
| 그래프 파일 만들기 | `python tools/graphrag/build.py export` | 안 씀 |
| SQL 베이스라인과 비교 | `python tools/graphrag/build.py compare` | 안 씀 |
| 적재 대상 건수 보기 | `python tools/graphrag/build.py stats` | 안 씀 |
| Aura 상태 점검 | `python tools/check_graph_neo4j.py` | 읽기 |
| 저장소 빌드와 Aura 비교 | `python tools/sync_graph_neo4j.py` | 읽기 |
| Aura를 저장소와 맞추기 | `... --apply [--prune] --confirm-host <호스트>` | **쓰기, 승인 필요** |
| 검수 준비표 다시 만들기 | `python tools/make_review_prep.py` | 안 씀 |
| 검수 결과 반영 | `python tools/ingest_condition_gold_reviews.py --split development` | 안 씀 |
| 규칙 선택지별 판정 영향 | `python tools/graphrag/rule_options_impact.py` | 안 씀 |
| 평가기 회귀 확인 | `python tools/graphrag/verdict_hash.py before.json` | 안 씀 |
| 시험 | `python -m unittest tools.test_graphrag tools.test_graph_ops tools.test_sync_graph` | 안 씀 |

## 1. 그래프 내보내기

```
python tools/graphrag/build.py export
```

- 결과: `data/graph/nodes.jsonl`, `edges.jsonl`, `manifest.json`. 적재 도구는 이 파일을 읽는다.
- 정리층 공고, 지역 사전, 법령 정의, 검수 정답(`data/goldsets/conditions/v1/20261125/`)이 바뀌면 다시 내보낸다.
- `compare`는 같은 구조 조건을 SQL로 평가해 그래프 평가기와 결과가 같은지 본다. 평가기를 고친 뒤 불일치가 0이어야 한다.

## 2. Aura 점검 (읽기 전용)

```
python tools/check_graph_neo4j.py                        # 레이블·관계 수, V0~V17 점검
python tools/check_graph_neo4j.py --save before.json     # 적재 전 스냅숏
python tools/check_graph_neo4j.py --compare before.json  # 적재 후 비교
python tools/check_graph_neo4j.py --check-definitions    # 정의 원문 해시를 로컬 조문과 대조
```

- `zero` 점검은 0이어야 정상이다. 실패하면 종료 코드 1.
- `known` 점검은 알려진 값(V15 1,294, V16a 34, V17 2, V25 4)에서 바뀌었는지만 경고한다. V9는 2026-11-27부터 `zero` 점검이다.
- 2026-11-27 판정 규칙 결정 반영 후: 노드 30,678, 관계 57,631(저장소 빌드와 같음). 그 전 2026-11-26 기준: 노드 32,605, 관계 56,995. 2026-11-27에 정의 23개의 검수 결과(`needs_review`·`review_status` 등)와 빠져 있던 정의 5개의 `source`를 올렸다(`--select ids --ids "^DEF:"`).

## 3. 적재·동기화 (기본은 비교만)

`tools/sync_graph_neo4j.py` 하나로 빈 DB 첫 적재와 이미 적재된 DB 맞추기를 모두 한다(2026-11-27에 옛 `load_graph_neo4j.py`·`load_graph_partial.py`를 합쳤다).

```
python tools/sync_graph_neo4j.py --offline                     # DB 없이 파일 검증과 건수만
python tools/sync_graph_neo4j.py --build                       # 다시 만들고 DB와 비교(읽기 전용)
python tools/sync_graph_neo4j.py --scope laws --show 10        # 범위를 줄이고 바뀌는 예시 10개씩
python tools/sync_graph_neo4j.py --with-rules                  # 정의 판정 기준(rule_json)까지 비교
python tools/sync_graph_neo4j.py --apply --confirm-host <NEO4J_URI의 호스트>   # 새로·바뀐 것만 쓴다
python tools/sync_graph_neo4j.py --apply --prune --confirm-host <호스트>       # DB에만 있는 요건·조건까지 지운다
```

| 범위(`--scope`) | 레이블 |
|---|---|
| `meta` | 공고·기관·분야·개념과 그 사이 관계 |
| `laws` | 법령·조문·별표·정의와 PART_OF·DEFINED_BY·CITES_LAW |
| `requirements` | 요건·조건과 HAS_REQUIREMENT·HAS_CONDITION·ABOUT |

순서: 1) `check_graph_neo4j.py --save before.json` → 2) `sync_graph_neo4j.py --build --report plan.json`으로 비교, 승인 받기 → 3) `--apply [--prune] --confirm-host` → 4) `check_graph_neo4j.py --compare before.json`.

- 시작할 때 판정 옵션(`evaluator.DEFAULT_OPTIONS`)을 출력한다.
- 중복 노드·중복 관계·끝점 없는 관계·시그니처 위반이 있으면 쓰지 않는다(종료 코드 2). 같은 키를 다른 레이블이 쓰거나 지울 것이 `--max-delete`(기본 5,000)를 넘으면 종료 코드 3.
- 지우기는 `--prune`일 때 `--prune-labels`(기본 Requirement·Condition)만. 검수 요건은 지우지 않는다. DB에만 있는 속성은 `--drop-extra-props`일 때만 지운다.
- 쓴 뒤 다시 비교하고 `zero` 점검을 돌린다. 실패하면 종료 코드 5.

## 4. 검수 패킷

```
python tools/make_review_prep.py                                    # docs/REVIEW_검수패킷_준비표_v0.1.md
python tools/ingest_condition_gold_reviews.py --split development   # 검수 결과 검증·반영
python tools/ingest_condition_gold_reviews.py --split evaluation
```

- 준비표의 개발용 30건에는 원문·링크·기존 후보·확인 포인트가 있고, 평가용 20건은 블라인드라 원문·링크만 있다.
- 검수는 `condition_review.jsonl`·`logic_review.jsonl`을 고친다(CSV는 읽기용). 가이드는 `docs/CONDITION_GOLDSET_REVIEW_GUIDE_V1.md`.
- 반영 뒤 `build.py export`를 다시 하고, 판정 영향은 아래 5·6으로 본다.

## 5. 규칙 선택지별 판정 영향

```
python tools/graphrag/rule_options_impact.py   # data/eval/rule_options_impact.json, 선택지마다 한 줄 출력
```

- 회의 결정 시트(`docs/MEETING_판정규칙_결정시트_2026-11-27.md`)의 "바뀌는 것" 숫자를 만든다.
- 모집 중 공고 × 무작위 프로필 300개(시드 고정)와 대표 프로필 6개로, 선택지 하나만 바꿨을 때 판정·조건이 바뀐 수를 센다. 몇 분 걸린다.
- 선택지는 `tools/graphrag/evaluator.py`의 `RuleOptions`다. 기본값이 지금 동작이고, 코드에서 바꿔 볼 때는:

```python
from graphrag.evaluator import RuleOptions, evaluate_notice
opts = RuleOptions(a1_kstartup_region="hard")
evaluate_notice(notice, profile, rg, opts)        # 또는 Engine().evaluate_all(profile, opts=opts)
```

| 필드 | 결정 시트 | 선택지(첫 값 = 기본) |
|---|---|---|
| `c1_pre_founder_not_in_options` | C-1 | `unsat`, `unknown` |
| `c2_business_age_all_options` | C-2 | `unknown`, `satisfied`, `drop` |
| `c3_age_all_options` | C-3 | `satisfied`, `unknown` |
| `c4_applicant_all_options` | C-4 | `satisfied`, `flag`, `unknown` |
| `c6_bizinfo_org_region` | C-6 | `soft`, `drop` |
| `a1_kstartup_region` | A-1 | `soft`, `hard` |
| `a3_pre_founder_missing_with_age` | A-3 | `unsat`, `unknown` |
| `a6_unreviewed_group` | A-6 | `flag`, `unknown` |

회의에서 정하면 `RuleOptions`의 기본값을 바꾸고 `tools/test_graphrag.py`의 `RuleOptionTests`에 사례를 더한다.

## 6. 평가기 회귀 확인

```
python tools/graphrag/verdict_hash.py before.json     # 고치기 전
python tools/graphrag/verdict_hash.py after.json      # 고친 뒤 → 두 파일의 sha256이 같아야 한다
python tools/graphrag/verdict_hash.py out.json --profiles 50 --gold <검수 정답 복사본 폴더>
```

- 고정 시드 프로필 150개 × 전체 공고(+ 합성 검수 조건 7개)의 판정·이유·조건 상태를 해시 하나로 줄인다. 리팩터링처럼 **판정이 바뀌면 안 되는** 수정에 쓴다.
- 검수가 진행 중이면 정답 폴더가 바뀌어 해시도 바뀐다. 전후 비교 동안은 `--gold`로 같은 복사본을 쓴다.
- 일부러 규칙을 바꿨다면 해시는 달라진다. 바뀐 건수는 5의 영향 계산이나 `build.py compare`로 본다.

## 7. 시험과 CI

```
python -m unittest tools.test_graphrag tools.test_graph_ops
python -m unittest tests.test_api tests.test_agent tests.test_condition_evaluation tests.test_condition_extractor tests.test_g2b_normalization tests.test_normalize_support_data
ruff check tools/graphrag tools/check_graph_neo4j.py tools/sync_graph_neo4j.py tools/test_sync_graph.py --select F,E9
```

- CI(`.github/workflows/tools-tests.yml`)는 PR과 main 푸시마다 위 시험과 ruff를 돌린다. DB·비밀값은 쓰지 않는다.
- `tests/`의 나머지 파일(`test_condition_inputs`, `test_condition_logic` 등)은 로컬 전용 데이터(`data/condition_inputs/v1/`, `api_samples/normalized/`)가 있어야 해서 CI에 넣지 않았다.
- `test_api`·`test_agent`는 서버 의존성(fastapi, httpx, langgraph 등)이 없으면 건너뛴다. 로컬에서 돌리려면 `requirements-dev.txt`를 설치한다.
