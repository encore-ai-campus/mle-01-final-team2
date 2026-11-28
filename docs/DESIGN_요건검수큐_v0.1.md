# 요건 검수 큐 설계 (B-3 ②) v0.1

작성 2026-11-28. 대상은 본문 요건이 검수되지 않아 판정이 `REQ_UNPARSED`(확인 필요)로 남는 공고다.
근거 결정:
- B-3(2026-11-27): 모델이 추출하고 사람이 검수한다. 검수 전에는 `REQ_UNPARSED`로 두고 원문을 표시한다. 원문 표시는 PR #63에서 구현했다.
- D-1: 발췌만 검수했으면 `partially_reviewed`로 두고 `ELIGIBLE`을 만들지 않는다.

이 문서는 검수가 끝난 공고가 `reviewed`로 올라가 판정에 쓰이기까지의 흐름과 첫 구현 범위를 정한다. **사용자 결정 필요(팀 검토 전)** 항목은 §6에 모았다.

## 1. 지금 상태 (2026-11-28 측정)

| 항목 | 값 |
|---|---|
| 서비스 공고 | 5,116건 (K-Startup 3,822, 기업마당 1,294) |
| 본문 요건 미검수 | 5,086건(`unparsed`). 발췌 검수 30건(`partially_reviewed`)도 여전히 `REQ_UNPARSED`다 |
| 큐에 들어간 공고 | 4,752건. 이 가운데 모집 중 1,414건이다. 출처별로는 기업마당 1,270건, K-Startup 3,482건이다 |
| 큐에서 빠진 공고 | 364건. 자격·제외 구역 원문이 없어서다. 원문 링크만 안내한다 |
| 규칙 사전 채움 | 후보 17,565개(기업 규모 3,698, 제외 3,463, 인증 3,000, 법령 인용 2,752, 지역 2,468, 업력 1,787, 대표자 나이 397). 사전 채움이 0개인 공고는 1,271건이다 |
| 모델 사전 채움 | 파일럿 P12 후보 60개 중 44개(73%)가 큐 원문에서 위치를 찾지 못했다(위치 없이 표시). 파일럿 입력 원문(`condition_texts.eligibility.text`)과 서비스 원문(청크)의 층이 달라서다 |
| 원문 길이(공고당) | 중앙값 103자, 상위 10% 938자, 최대 23,073자. K-Startup은 대개 공고 요약 1구역뿐이다 |
| 판정 변화 | 없음. 검수 반영이 0건이므로 판정 해시가 바꾸기 전과 같다(768,450개, `a49dc340…`) |

추출 정확도 기준선(`docs/CONDITION_EXTRACTION_HANDOVER.md` §3, 개발 파일럿 10건·정답 62개 strict):

| 추출 방식 | F1 |
|---|---|
| 규칙 | 13.6~14.1% |
| 모델 P12 | 2.1% |
| 모델 P12 + N1 | 6.4% |

그래서 사전 채움은 **검수자가 고를 후보**일 뿐이다. 판정에는 쓰지 않는다(`decision_possible=false`).

## 2. 흐름

```
판정 엔진 공고·청크 ─┐
규칙 추출(extract_req) ┼─ build ─▶ 큐(queue.jsonl, 행 = 공고 1건, UNREVIEWED)
모델 추출(선택, --proposals) ┘                 │
                                    검수자: 조건 작성·근거 위치·논리·공고 전체 확인 여부 → VERIFIED
                                              │
                                 ingest(행 단위 검사, 실패 행은 건너뜀)
                                              ▼
              data/reviews/requirements/service/reviewed_condition_gold.jsonl · reviewed_logic_gold.jsonl
                                              │  gold_bridge.load_all()  (골든셋과 합침, 겹치면 골든셋 우선)
                                              ▼
                 Engine: gold_requirements 부착
                   - 공고 전체 확인 → text_requirements=reviewed → REQ_UNPARSED 해제
                   - 발췌 검수 → partially_reviewed → 계속 확인 필요
```

- 판정 규칙은 그대로다. 검수 조건은 골든셋과 같은 변환(`gold_bridge.to_condition`)과 강도 규칙(D-2, 업력만 hard)을 따른다.
- 우대·미분류 조건은 판정에 옮기지 않는다. 제외 조건은 해당하면 불충족이다.
- 같은 공고가 골든셋과 서비스 검수에 모두 있으면 골든셋을 쓴다(Q-4).

## 3. 큐 행 모양 (`requirement-service-review-1.0`)

조건·논리 필드는 골든셋 검수 양식(`condition-gold-review-v1.1`)과 같은 이름이다. 그래서 `gold_bridge`를 고치지 않고 읽는다. 골든셋 스키마의 `dataset_split`은 `DEVELOPMENT|EVALUATION`뿐이므로, 서비스 큐는 별도 `record_type`과 `dataset_split=SERVICE`를 쓴다. 평가 정답과 섞이지 않게 하기 위해서다.

| 필드 | 뜻 |
|---|---|
| `notice_id`, `title`, `source_system`, `detail_url`, `is_open`, `deadline` | 공고 정보 |
| `priority_rank`, `priority_reasons` | 검수 순서(Q-2) |
| `source_text`, `source_hash`, `segments[]` | 원문(자격·제외 구역 청크를 고치지 않고 `\n\n`으로 이음)과 구역별 위치·조건 종류. 해시는 다시 만들 때 원문 변경 감지에 쓴다 |
| `prefill_candidates[]` | 규칙(`extraction_method=rule`)·모델(`llm`) 후보. 근거 위치는 원문 기준이다. 여러 번 나오는 근거는 첫 위치를 고르지 않고 위치 없이 둔다. 규칙 후보는 문장 위치(`evidence_reference`, 문맥용)와 조건 문구 위치(`condition_reference`·`condition_text`, 예: "창업 7년 미만의 기업")를 함께 싣고, **채택하면 조건 문구 위치가 근거가 된다**. 「중소기업기본법」처럼 법령 이름 속 규모 낱말은 후보로 내지 않는다. 모델 후보의 단위 표기(명·%·억원 등)는 정답셋 코드(PERSON·PERCENT·KRW, 금액은 원 단위)로 바꾸고 원래 표기는 `unit_raw`에 남긴다(임시 기본값 2026-11-28, 팀 검토 전) |
| `gold_conditions[]`, `missed_condition_candidates[]` | **검수자가 쓴다.** id는 `make_id(notice_id, 종류, 시작, 끝, 근거문)`(골든셋과 같은 결정적 규칙)이고, 조건마다 `review_status=VERIFIED` |
| `gold_logic_roots[]` | 검수자가 쓰는 요건 논리(AND/OR). 없으면 AND로 가정한다(`logic_basis=assumed`) |
| `whole_notice_conditions_complete` | **공고 전체의 자격 조건을 확인했는가.** 참일 때만 `reviewed`가 된다(Q-3) |
| `review_status`, `adjudication_status`, `reviewer`, `reviewed_at`, `review_comment` | 검수 상태. 완료는 `REVIEWED_COMPLETE` 또는 `CONFIRMED_NONE_IN_PROVIDED_TEXT`(원문에 자격 조건 없음) |
| `stale_source` | 검수한 뒤 원문이 바뀌었다는 표시. 다시 검수하기 전에는 반영하지 않는다 |

## 4. 안전 규칙 (구현됨)

1. **사람이 손댄 행은 덮어쓰지 않는다.** `build`를 다시 돌려도 검수 중이거나 완료된 행은 남긴다. 원문 해시가 바뀌면 `stale_source=true`만 켠다. 대상에서 빠진 공고도 손댄 행은 남긴다.
2. **ingest는 행 단위로 fail-closed다.** 아래 중 하나라도 걸리면 그 공고는 반영하지 않고 사유를 보고서(`ingest_report.json`)에 남긴다.
   - 검수자·검수 시각이 없음
   - 완료 상태가 아님
   - 원문 해시가 다름, 또는 `stale_source`
   - 근거 위치와 원문이 다름
   - 조건 id가 규칙과 다름
   - 조건이 VERIFIED가 아님
   - 조건 id가 중복됨
   - 논리가 없는 조건을 가리킴
   - "조건 없음"으로 표시했는데 조건이 있음
3. **골든셋과 분리한다.** 서비스 검수 결과는 `data/reviews/`에 두고 평가 정답(`data/goldsets/`)에 넣지 않는다. 판정 회귀 해시(`verdict_hash.py`)는 골든셋만 본다.
4. **로컬 전용이다.** 큐 원문에 첨부 추출 텍스트가 들어 있으므로 `data/reviews/`는 git에서 제외했다. 팀 공유는 Supabase `review_queue`로 옮길 때 한다(Q-1).
5. **Aura에는 쓰지 않는다.** 서비스 판정은 엔진이 파일에서 읽는다. 검수 요건을 그래프(Requirement·Condition)에 적재할지는 Q-6이다.

## 5. 사용법

```powershell
.venv\Scripts\python tools\requirement_review_queue.py build              # 전체(4,752건)
.venv\Scripts\python tools\requirement_review_queue.py build --open-only  # 모집 중만
.venv\Scripts\python tools\requirement_review_queue.py build --proposals data\evaluations\conditions\v1.1\20261126\development\llm_pilot_2_5c3_r2_p12
.venv\Scripts\python tools\requirement_review_queue.py status
.venv\Scripts\python tools\requirement_review_queue.py ingest             # VERIFIED 행 → service/reviewed_*.jsonl
```

`ingest`(CLI) 뒤에는 API를 다시 띄우거나 `POST /api/admin/reviews/reload`를 부르면 반영된 공고의 판정이 바뀐다. 검수 화면의 반영 버튼은 둘을 한 번에 한다. 시험은 `tests/test_requirement_review_queue.py`(9개)에 있다. 큐 만들기·덮어쓰기 방지·ingest 검사와 검수부터 판정까지의 전체 경로를 다룬다.

### 5-1. 검수 화면 (`/admin/reviews`)

관리자 화면에서 jsonl을 직접 고치지 않고 검수한다. API는 `/api/admin/reviews`(`api/routers/reviews.py`)이고 관리자만 쓴다. 로그인(A-01)한 관리자(`ADMIN_EMAILS`)만 쓴다. 로컬 개발에서는 로그인하지 않아도 web이 `DEV_ADMIN=1`일 때 `x-dev-role: admin`을 붙여 관리자로 동작한다.

| 화면 | 하는 일 |
|---|---|
| 목록 | 우선순위 순 큐. 상태(검수 전·작업 중·검수 완료)·출처·모집 중·검색어로 거른다. **판정에 반영(ingest)** 버튼은 반영 파일을 쓰고 판정 엔진이 바로 다시 읽게 한다(API 재시작 불필요) |
| 한 건 | 왼쪽에 원문(구역별), 오른쪽에 사전 채움 후보·조건·검수 결과가 있다 |
| 근거 고르기 | 원문을 드래그하고 "자격/제외 조건으로 추가"를 누른다. 또는 후보의 **채택**을 누른다. 위치를 찾지 못한 후보는 채택할 수 없다 |
| 조건 | 종류(자격·제외·우대), 속성, 연산자, 값을 적는다. 판정 규칙이 있는 속성은 업력·대표자 나이·소재지·기업 유형뿐이다. 나머지는 "(판정 안 함)"으로 표시되고 평가기에서 확인 필요가 된다 |
| 검수 결과 | 자격 조건 사이 AND/OR, "원문에 판정할 자격 조건 없음", "공고 전체의 자격 조건을 확인했음"(Q-3 안내 포함), 메모 |
| 버튼 | **작업 중 저장**(NEEDS_REVIEW), **검수 완료**(VERIFIED), **다시 작업**(검수 완료를 되돌림) |

- 근거 문장과 조건 id는 서버가 원문[시작:끝]에서 잘라 만든다. 화면이 보낸 근거 글은 믿지 않는다.
- 검수 완료는 ingest와 같은 검사(`check_row`)를 통과해야 한다. 통과하지 못하면 422와 문제 목록을 보이고 작업 중으로만 저장한다.
- 저장은 큐 파일 전체를 임시 파일로 쓰고 바꾼다(원자적). 읽은 줄을 들고 있다가 바뀐 행만 다시 직렬화한다. 19MB 큐에서 저장 0.30초 → 0.11초(로컬 PC), Docker 컨테이너에서는 약 0.37초(Windows 폴더를 붙여 파일 쓰기가 느리다, 2026-11-28). Supabase로 옮기면(Q-1 ②) 행 단위 저장이 된다.
- docker에서는 api에 `data/reviews`만 쓰기로 붙였다. 나머지 `data`는 읽기 전용이다.
- 시험은 `tests/test_review_api.py`(10개)에 있다. 목록·필터, 관리자 아님 403, 저장→검수 완료→ingest→다시 작업, OR 논리, 잘못된 값·위치·중복, 조건 없음 표시, 검사 실패 시 작업 중 저장, id 규칙이 골든셋과 같은지를 다룬다.

## 6. 사용자 결정 필요(팀 검토 전)

지금 코드는 아래 **임시 기본값**으로 동작한다. 바꾸려면 표시한 곳만 고치면 된다.

| # | 결정할 것 | 선택지 | 임시 기본값 | 고칠 곳 |
|---|---|---|---|---|
| Q-1 | 큐 저장소 | ① 로컬 jsonl(지금) ② Supabase `review_queue` 테이블(설계서 §3 저장소 표) | ① 첫 구현. 팀이 같이 검수하려면 ②가 필요하다. 테이블은 만들지 않았다 | `QUEUE`, `read_jsonl`·`write_jsonl` |
| Q-2 | 검수 순서 | ① 모집 중 → 마감 14일 이내 → 마감일 ② 조회 많은 공고 ③ 판정 후보에 자주 나온 공고 | ① + 판정 일치율 측정용 파일럿 공고(`data/goldset/pilot/pilot_assignment.csv`)를 맨 앞에(임시 기본값 2026-11-28, 팀 검토 전) | `priority()` |
| Q-3 | 공고 전체 확인(`reviewed`) 기준 | ① 검수자 1명이 원문 전체를 보고 체크 ② 2명이 일치해야 함 ③ 1명 + 표본 이중 검수 | 정하지 않았다. 코드는 체크 여부만 본다. 큐 원문이 공고 전체가 아닐 수 있다(K-Startup은 첨부 본문이 청크에 없다). 체크 전에 공고 원문 링크를 확인하도록 안내해야 한다 | 검수 화면 안내, `check_row()` |
| Q-4 | 골든셋과 서비스 검수가 겹칠 때 | ① 골든셋 우선 ② 나중 검수 우선 | ① | `gold_bridge.load_all()` |
| Q-5 | 사전 채움 | ① 규칙만 ② 규칙 + 모델(비용·F1 낮음) ③ 사전 채움 없이 검수(편향 방지) | ① 기본, ②는 `--proposals`로 선택 | `build()` |
| Q-6 | 검수 요건의 Aura 적재 | ① 서비스는 파일만, 그래프는 나중 ② 적재(쓰기 승인 필요) | ① | `sync_graph_neo4j.py`(미변경) |
| Q-7 | "원문에 자격 조건 없음" + 공고 전체 확인 | 본문 요건이 없다고 보고 `ELIGIBLE`을 허용할지 | 허용(규칙상 그렇게 된다). 잘못 체크하면 오판이 커지므로 Q-3과 함께 정한다 | `check_row()` |

## 7. 다음 단계

1. ~~검수 화면~~ 구현함(§5-1). 관리자 로그인(A-01)과 재시작 없는 반영도 붙였다(2026-11-28). 남은 것: 검수자 2명 동시 작업 처리(Q-3).
2. **Q-1이 ②로 정해지면** Supabase `review_queue` 마이그레이션을 하고, build·ingest의 입출력을 DB로 바꾼다.
3. **모델 사전 채움.** 서비스 원문(청크)을 입력으로 다시 추출해 위치 불일치(73%)를 없앤다. P4 계보의 남은 장애(`CONDITION_EXTRACTION_TROUBLESHOOTING.md`)를 먼저 해결해야 한다.
4. **검수율과 판정 변화 측정.** 반영 전후 `verdict_hash.py`와 `rule_options_impact.py`로 몇 건이 확인 필요에서 바뀌었는지 기록한다.
