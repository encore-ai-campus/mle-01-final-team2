# 신규 데이터 파이프라인과 상위 법령 설계 v0.1

| 항목 | 내용 |
|---|---|
| 목적 | (1) 공고가 새로 들어오거나 바뀌었을 때 수집부터 Aura 반영까지 다시 도는 방법, (2) 법률 → 시행령 → 시행규칙 → 고시로 이어지는 상위 법령 구조와 개정 반영 방법을 정한다 |
| 상태 | **설계안.** 코드는 아직 바꾸지 않았다. §5의 팀 결정 항목(F-1~F-8)은 팀이 정한다 |
| 근거 | 2026-11-26 기준 코드 조사. 수집기·정리층·조건 추출·그래프 내보내기·적재 도구, 법령 수집기·`concepts_laws.py`·`definition_rules.py` |
| 관련 문서 | 온톨로지 설계서 §9(변경 관리), 스키마 정의서 §11·§12, `docs/PREPROCESS_정리층_설계와_결과_v0.1.md`, `docs/GUIDE_도구_사용안내_v0.1.md`, `data/지원사업_법령/데이터명세서.md` §10 |

---

## 1. 지금 상태 (2026-11-26)

### 1.1 공고 데이터

| 단계 | 도구 | 출력 | 다시 돌릴 때 문제 |
|---|---|---|---|
| 수집(기업마당) | `collect_bizinfo.py` | `data/bizinfo/raw/<실행시각>/` + `raw/LATEST` | 모집 중 공고만 준다. 마감된 공고는 기록 없이 사라진다 |
| 파싱(기업마당) | `parse_bizinfo.py` | `data/bizinfo/parsed/<실행>/` | `--prev`로 버전(`content_hash` 비교, `version+1`)을 붙일 수 있지만 한 번도 쓰지 않았다 |
| 수집(K-Startup) | `collect_kstartup_full.py` | `data/kstartup/raw/<날짜>_full/` | 서버 날짜 필터가 안 돼 매번 전체를 받는다. `LATEST` 포인터가 없다 |
| 수집(나라장터) | 저장소에 없음 | `data/g2b_monthly/<YYYY-MM>/`만 있음 | 수집 코드가 없다. ID에 출처 접두어가 없다 |
| 첨부 | `download_bizinfo_attachments.py`, `extract_attachment_text.py` | `data/bizinfo/files/<실행>/`, `extracted/<실행>/` | 파일 해시는 있지만, 바뀌지 않은 첨부를 다시 읽지 않는 캐시가 없다 |
| 정리층 | `preprocess_notices.py` | `data/cleaned/<날짜>/` + `cleaned/LATEST` | **`TODAY = "2026-11-24"`가 코드에 고정**되어 있어 다시 돌리면 같은 폴더를 덮어쓴다. K-Startup은 항상 `version=1` |
| 정규화·조건 입력 | `normalize_support_data.py`, `prepare_condition_inputs.py` 등 | `data/normalized/v1/<날짜>/`, `data/condition_inputs/v1/20261125/` | 입력·출력 날짜가 코드에 고정되어 있다. 바뀐 공고만 다시 추출할 수 없다 |
| 검수 정답 | `build_condition_gold_review.py`, `ingest_condition_gold_reviews.py` | `data/goldsets/conditions/v1/20261125/` | 기준선이 고정(`PRE_2_4_FROZEN`)이다. 원문이 바뀌어도 정답이 낡았다는 표시가 없다 |
| 그래프 | `graphrag/build.py export` | `data/graph/` | 매번 전체 재생성. Notice에 `version`·`content_hash`가 없고 `SUPERSEDES`도 없다. `engine.py`의 기준일도 고정 |
| 적재 | `load_graph_neo4j.py`, `load_graph_partial.py` | Aura | MERGE만 한다(지우기 없음). 그래서 마감·삭제된 공고의 노드는 그대로 남는다 |

자동 실행(스케줄)은 없다. CI는 시험만 돌린다.

### 1.2 법령 데이터

| 항목 | 현재 |
|---|---|
| 수집 | `law_web_collector.py`(법제처 웹 본문), `law_api_collector.py`(공공데이터포털 목록·별표 PDF). **현행본만** 받는다 |
| 종류 | `ExternalLaw` 44개 = 법률 22 + 대통령령(시행령) 22. 시행규칙·고시·훈령·조례 0 |
| 노드 | 조문 2,325, 별표 59, 정의 23. 조문·별표에는 `text_hash`가 있다 |
| 버전 | `law_id = LAW:<법령일련번호>`. 일련번호가 개정마다 바뀌므로 새 판은 새 노드가 되지만 이전 판과 잇는 관계가 없다. 법령ID(판과 무관한 ID)와 공포일은 수집 기록에만 있고 그래프에 없다. 부칙은 버린다 |
| 상하위 | 법률과 시행령은 이름("○○법 시행령")으로만 짝지어진다. 위임("대통령령으로 정하는") 연결은 없다. 검수 시트에서 위임 위치를 손으로 셌다 |
| 공고 → 법령 | 공고 본문의 법령 인용 640건이 `law_citations_pending.jsonl`에 있지만 그래프에 넣지 않았다(`CITES` 0) |
| 판정 쓰임 | 중소기업 기준(`definition_rules.json`)이 시행령 제3조·제8조·별표 1·3을 문자열과 해시로 가리킨다. 그래프 관계는 아니다 |

---

## 2. 원칙

1. **스냅숏은 고치지 않는다.** 실행할 때마다 새 폴더(`<YYYYMMDD_HHMMSS>`)를 만들고 `LATEST`만 옮긴다. 되돌리기는 `LATEST`를 이전 폴더로 바꾸면 된다.
2. **바뀐 것만 다시 처리한다.** 앞 스냅숏과 비교해 `NEW / CHANGED / UNCHANGED / CLOSED / DISAPPEARED`를 정하고, 비싼 단계(첨부 OCR, 조건 추출, 검수)는 `NEW`·`CHANGED`만 돈다.
3. **ID는 바뀌지 않고, 버전이 바뀐다.** 공고 ID(`BIZINFO:…`, `KSTARTUP:…`, `G2B:…`)는 그대로 두고 내용이 바뀌면 `version`을 올린다. 법령은 판(일련번호)마다 노드를 두고 판끼리 `SUPERSEDES`로 잇는다.
4. **지우지 않고 표시한다.** 공용 DB(Aura)에 지우기를 하지 않는다. 마감·사라진 공고와 지난 판은 상태 속성(`status`, `is_current`)으로 표시하고, 평가기와 검색은 현재 것만 쓴다.
5. **판정 규칙과 정답은 사람이 지킨다.** 원문이 바뀐 공고의 검수 정답은 자동으로 고치지 않고 "다시 검수" 대기열로 보낸다. 평가용 정답(블라인드)은 고정한다.
6. **Aura 쓰기는 승인 뒤에만.** 파이프라인은 dry-run 결과와 변경 보고서까지 만들고 멈춘다. 적재는 사람이 `--apply --confirm-host`로 한다.

---

## 3. 신규 데이터 파이프라인

### 3.1 흐름

```
[1 수집] ─> [2 파싱·첨부] ─> [3 정리층] ─> [4 차이 계산] ─┬─> [5 정규화·조건 추출(NEW·CHANGED만)]
                                                       │          │
                                                       │          v
                                                       │   [6 검수 대기열(바뀐 정답 STALE 표시)]
                                                       v          │
                                              [7 그래프 내보내기(버전·상태)] <┘
                                                       │
                                                       v
                                       [8 점검·dry-run·판정 영향 보고]  ── 승인 ──> [9 부분 적재] ─> [10 적재 후 점검]
```

### 3.2 단계별 규칙

| # | 단계 | 입력 → 출력 | 규칙 | 바꿀 코드 |
|---|---|---|---|---|
| 1 | 수집 | API → `data/<출처>/raw/<run>/` + `LATEST` | 출처마다 같은 폴더 규칙과 `manifest.json`(쪽별 sha256, 총건수, `complete`)을 쓴다. `complete=false`면 다음 단계로 가지 않는다 | K-Startup에 `raw/LATEST`. 나라장터 수집기를 저장소에 넣는다(`tools/g2b/`) |
| 2 | 파싱·첨부 | raw → `parsed/<run>/`, `files/<run>/`, `extracted/<run>/` | `parse_bizinfo.py --prev`를 항상 쓴다. 첨부는 파일 sha256이 같으면 이전 추출 텍스트를 그대로 쓴다(OCR 다시 안 함) | 첨부 캐시: `data/bizinfo/extracted/_cache/<sha256>.txt` |
| 3 | 정리층 | parsed·raw → `data/cleaned/<run>/` + `LATEST` | 기준일은 `--as-of`(기본 오늘)로 받는다. `fetched_at`은 실제 수집 시각 | `preprocess_notices.py`·`engine.py`의 고정 `TODAY` 제거 |
| 4 | 차이 계산 | `cleaned/<prev>` vs `cleaned/<run>` → `data/runs/<run>/delta.jsonl` | §3.3 상태표. 공고마다 `notice_id, status, prev_hash, new_hash, changed_fields` | 새 도구 `tools/pipeline/diff_snapshots.py` |
| 5 | 정규화·조건 추출 | `delta`의 NEW·CHANGED만 | 조건 ID는 이미 원문 해시 기반이라 같은 원문이면 같은 ID다. 바뀐 공고는 조건 집합을 통째로 새로 만들고 이전 집합은 `is_current=false` | 날짜 고정 경로를 `--snapshot`·`--only-ids`로 |
| 6 | 검수 대기열 | `delta` + 정답셋 → `data/goldsets/.../stale.jsonl` | 검수 정답이 있는 공고가 CHANGED면 그 정답을 `STALE`로 표시하고 대기열에 넣는다. STALE 정답은 그래프에 넣지 않는다(재검수 전까지 `structured_only`로 판정) | `gold_bridge`가 STALE을 건너뛰게 |
| 7 | 그래프 내보내기 | 정리층 + 조건 + 정답 → `data/graph/` | Notice에 `version`, `content_hash`, `status`, `first_seen`, `last_seen`. 바뀐 공고의 이전 요건은 `is_current=false`로 남기고 새 요건과 `SUPERSEDES`로 잇는다 | `build.py export`에 속성 추가, `manifest.json`에 `run_id`·`prev_run_id` |
| 8 | 점검·보고 | `data/graph/` + Aura(읽기) | `check_graph_neo4j.py --save`, `load_graph_partial.py --select delta`(dry-run), `verdict_hash.py`·`rule_options_impact.py`로 판정 변화 보고 → `data/runs/<run>/report.md` | 부분 적재에 `--select delta`(delta에 든 공고와 그 요건·조건) |
| 9 | 부분 적재 | 승인 뒤 `--apply --confirm-host` | MERGE. 상태 바뀐 공고는 속성만 고친다(지우지 않음) | — |
| 10 | 적재 후 점검 | `check_graph_neo4j.py --compare` | `zero` 점검 0, 바뀐 건수가 보고서와 같은지 | — |

한 번에 돌리는 진입점은 `tools/pipeline/run_update.py --sources bizinfo kstartup [--as-of YYYY-MM-DD] [--until report]`로 둔다. 각 단계는 지금처럼 따로 돌릴 수 있게 두고, 진입점은 순서와 실행 기록(`data/runs/<run>/run.json`: 단계별 시작·끝·입력 해시·건수·종료 코드)만 맡는다. 기본은 8단계(보고)에서 멈춘다.

### 3.3 공고 상태 판정

| 상태 | 조건 | 처리 |
|---|---|---|
| `NEW` | 이번에 처음 본 `notice_id` | 전 단계 처리 |
| `CHANGED` | 있던 ID인데 `content_hash`가 다름 | `version+1`, `supersedes_version`. 조건 다시 추출, 검수 정답은 STALE |
| `UNCHANGED` | 해시 같음 | `last_seen`만 갱신. 비싼 단계 건너뜀 |
| `CLOSED` | 원천이 마감 표시(K-Startup `rcrt_prgs_yn=N`)하거나, 기업마당에서 사라졌고 마감일이 기준일 이전 | `status=CLOSED`. 평가기·검색에서 제외(지금도 모집 중만 평가) |
| `DISAPPEARED` | 원천에서 사라졌는데 마감일이 아직 안 지났거나 없음 | `status=DISAPPEARED`, 결과 화면에 "원천에서 내려감, 확인 필요". 3회 연속이면 사람이 확인(F-2) |
| `REOPENED` | CLOSED·DISAPPEARED였는데 다시 나타남 | 해시 비교 후 CHANGED 또는 UNCHANGED로 처리하고 `status`를 되돌린다 |

`content_hash`에 넣는 필드는 지금 정리층 규칙(제목·요약·신청 방법·기간·대상·신청 URL·첨부 이름)을 유지하되, **첨부 파일 sha256 목록**을 더한다(첨부만 바뀐 정정 공고를 잡기 위해, F-1).

나라장터는 `<공고번호>-<차수>`에서 차수가 정정 회차다. ID는 `G2B:<공고번호>`로 두고 차수를 `version`으로 쓴다(F-3).

### 3.4 그래프 변경 (Notice 층)

| 대상 | 추가 속성·관계 | 비고 |
|---|---|---|
| `Notice` | `version`, `content_hash`, `status`(OPEN·CLOSED·DISAPPEARED), `first_seen`, `last_seen`, `run_id` | 키(`notice_id`)는 그대로 |
| `Requirement` | `is_current`, `version` | 바뀐 공고의 새 요건 ID에 `#v<버전>`을 붙인다 |
| `(:Requirement)-[:SUPERSEDES]->(:Requirement)` | 새 판 → 이전 판 | **같은 `notice_id`의 내용이 바뀐 경우.** 공고 노드는 하나로 두고 요건 단위로 판을 잇는다 |
| `(:Notice)-[:SUPERSEDES]->(:Notice)` | 새 공고 → 이전 공고, 이전은 `is_latest=false` | **재공고·연장처럼 원천이 새 ID를 준 경우.** 온톨로지 설계서 §5의 정의 그대로다. 제목 유사도 묶음(`related_groups`)은 후보이고 사람이 확인한 것만 만든다 |
| 점검 쿼리 | V18: `is_current=true` 요건이 공고당 판 하나뿐. V19: `status=OPEN`인데 마감일이 기준일 이전 0 | `check_graph_neo4j.py`에 추가 |

평가기는 `is_current=true` 요건만 읽고, 결과에 `notice.version`, `last_seen`, 기준일을 함께 낸다(VAL-07·VAL-08).

### 3.5 실행 주기와 자리

| 항목 | 안 |
|---|---|
| 주기 | 처음에는 **주 1회 수동**(`run_update.py --until report` → 보고서 확인 → 승인 → 적재). 마감 임박 공고가 많아지면 매일 수집·차이 계산만 자동화 |
| 자리 | GitHub Actions에는 로컬 전용 데이터와 Aura 비밀값을 두지 않는다. 자동화한다면 API 서버(AWS)의 예약 실행에서 1~8단계까지만 돌린다(F-4) |
| 보관 | raw·parsed·첨부 원본은 로컬 전용(git 제외). `data/runs/<run>/`의 `run.json`·`delta` 요약·`report.md`는 작아서 커밋할 수 있다(F-5) |
| 실패 | 단계가 실패하면 `LATEST`를 옮기지 않는다. 다음 실행은 마지막 성공 스냅숏과 비교한다 |

### 3.6 수용 기준

- 같은 원천으로 두 번 돌리면 두 번째 `delta`는 전부 `UNCHANGED`이고 그래프 파일 해시가 같다.
- 공고 하나의 본문을 바꾼 시험 스냅숏으로 돌리면 `CHANGED` 1건, 요건 `SUPERSEDES` 1개, 그 공고 정답 STALE 1건이 나온다.
- 공고 하나를 뺀 시험 스냅숏으로 돌리면 마감일에 따라 `CLOSED` 또는 `DISAPPEARED`가 나온다.
- 적재 후 `check_graph_neo4j.py --compare`에서 V18·V19가 0이다.

---

## 4. 상위 법령 설계

### 4.1 법령 계층

| 단계 | `law_kind` | 예 | 법제처 수집 대상 | 지금 |
|---|---|---|---|---|
| 법률 | `ACT` | 중소기업기본법 | 법령(`law`) | 22 |
| 대통령령 | `DECREE` | 중소기업기본법 시행령 | 법령(`law`) | 22 |
| 총리령·부령 | `RULE` | ○○법 시행규칙 | 법령(`law`) | 0 |
| 행정규칙 | `ADMIN_RULE` | 중소기업 범위 및 확인에 관한 규정(고시), 신산업 창업 분야 고시 | 행정규칙(`admrul`) | 0 |
| 자치법규 | `ORDINANCE` | 시·도 창업 지원 조례 | 자치법규(`ordin`) | 0, **1차 범위 밖** |

수집 우선순위는 "판정 규칙이 실제로 가리키는 것"이다. 1순위는 `definition_rules.json`·정의 23개가 위임으로 가리키는 시행령 조문과 고시(중소기업 범위 고시, 초기창업기업 관련 시행령 조문), 2순위는 공고 인용 640건 중 상위 빈도 법령의 시행규칙, 3순위는 조례(지역 조건이 조례를 근거로 할 때).

### 4.2 노드·관계

```
(:ExternalLaw {law_kind:'ACT'})  <-[:ENFORCES]-  (:ExternalLaw {law_kind:'DECREE'})  <-[:ENFORCES]-  (:ExternalLaw {law_kind:'RULE'})
        ^  PART_OF                                     ^  PART_OF
(:LawArticle 법 제2조②) -[:DELEGATES_TO {phrase:'대통령령으로 정하는'}]-> (:LawArticle 시행령 제3조)
                                                                              ^
(:Definition 중소기업) -[:CITES_LAW {role:'basis'}]-> 법 제2조                   │ CITES_LAW {role:'criteria'}
                       ─────────────────────────────────────────────────────────┘
(:ExternalLaw 판 n+1) -[:SUPERSEDES]-> (:ExternalLaw 판 n)        (:Requirement) -[:CITES]-> (:LawArticle | :ExternalLaw)
```

| 대상 | 추가 | 설명 |
|---|---|---|
| `ExternalLaw` | `law_kind`, `law_master_id`(법령ID, 판과 무관), `version_seq`(법령일련번호), `promulgated_date`, `effective_date`, `effective_until`, `is_current`, `text_hash`(조문 해시를 순서대로 이은 해시) | 키 `law_id = LAW:<일련번호>`는 유지. 같은 `law_master_id`의 판들이 한 법령이다 |
| `LawArticle` | `chapter`(지금 버림), `amend_marks`(조문 끝 `[개정 …]` 목록) | 부칙은 `LawArticle {is_addendum:true}`로 따로 받는다(경과조치 확인용) |
| `ENFORCES` | 하위 법령 → 상위 법령 | 시행령·시행규칙 제1조("이 영은 「○○법」에서 위임된 사항…")에서 상위 법령명을 읽어 만든다. 이름 짝짓기보다 확실하다 |
| `DELEGATES_TO` | 상위 조문 → 하위 조문, `{phrase, basis, confidence}` | §4.3 |
| `SUPERSEDES` | 새 판 → 이전 판 | 같은 `law_master_id`에서 `effective_date` 순 |
| `CITES_LAW` | `role` 속성 추가: `basis`(정의 본문), `criteria`(세부 기준), `exception`(제외) | 중소기업 정의는 법 제2조(`basis`) + 시행령 제3조·제8조·별표 1·3(`criteria`) |
| `CITES` | 공고 요건 → 조문·법령 | 대기 중인 인용 640건을 적재. 조문 단위 430건은 `LawArticle`, 법령 단위 210건은 `ExternalLaw` |

`definition_rules.json`의 `basis` 문자열은 위 `CITES_LAW {role:'criteria'}`의 `article_id`·`text_hash`와 같은 값을 가리키게 바꾼다. 그러면 "중소기업 판정에 쓰인 시행령 조문이 개정됐나"를 그래프 한 번으로 묻는다(CQ-05·CQ-15).

### 4.3 위임 연결 추출

1. **상위 조문 표시**: 법률 조문에서 "대통령령으로 정하는", "총리령으로", "○○부령으로 정하는", "○○부장관이 정하여 고시하는"을 찾아 위임 후보로 둔다(`phrase`).
2. **하위 조문 대응**: 시행령 조문은 보통 "법 제2조제1항제1호에서 '대통령령으로 정하는 …'이란"처럼 상위 조문을 직접 적는다. 이 "법 제N조(제M항)" 참조를 읽어 `DELEGATES_TO`를 만든다(`basis='explicit_ref'`, `confidence=high`).
   지금 데이터로 확인한 값(2026-11-26): 시행령 22개의 제1조가 모두 위임 문구와 상위 법률명을 담고 있고(→ `ENFORCES` 22개를 규칙으로 만들 수 있음), 시행령 조문 925개 중 700개(76%)가 "법 제N조"를 직접 적는다.
3. **참조가 없는 경우**: 조문 제목·용어가 겹치는 후보만 `basis='title_match'`, `confidence=low`로 두고 사람이 검수한다(정의 검수 시트의 "위임 기준" 칸과 합친다).
4. **고시**: "고시하는" 위임은 행정규칙을 수집한 뒤 고시 제1조(목적)의 근거 조문으로 잇는다.

옛 도구(`tools/old/convert_ibk.py`)의 위임 후보 추출을 참고하되, 새 도구는 `tools/graphrag/law_hierarchy.py`로 두고 결과를 `data/graph/law_delegations.jsonl`에 쓴다. 점검: V20 `DELEGATES_TO`의 시작은 상위 `law_kind`, 끝은 하위 `law_kind`(역방향 0), V21 `ENFORCES` 순환 0.

### 4.4 개정 반영 (법령 갱신 주기)

| 단계 | 규칙 |
|---|---|
| 감지 | 월 1회 `law_api_collector.py`로 대상 법령의 현행 법령일련번호를 받는다. 저장한 `version_seq`와 다르면 개정이다 |
| 수집 | 새 판 본문·별표·부칙을 받아 새 `ExternalLaw` 노드(새 `law_id`)와 조문을 만든다. 이전 판은 `is_current=false`, `effective_until = 새 판 시행일 - 1일` |
| 비교 | 조문별 `text_hash`를 비교해 바뀐 조문 목록을 만든다 |
| 영향 | 바뀐 조문을 `CITES_LAW`로 가리키는 정의, 그 정의를 쓰는 규칙(`rule_json`), 그 정의 개념을 `ABOUT`으로 가리키는 조건을 찾는다. 정의는 `needs_review=true`로 되돌리고 보고서에 적는다 |
| 판정 | 검수 전까지 그 정의를 쓰는 조건을 어떻게 할지는 F-7 |
| 시행 전 개정 | 공포됐지만 시행 전인 판은 수집하되 `is_current=false`, `effective_date`가 미래. 기준일이 시행일을 지나면 현행으로 바꾼다 |

### 4.5 공고 기준일과 적용 판

공고에 맞는 법령 판은 **기준일**로 고른다. 기준일은 B-2 결정(본문에 표현이 있을 때만 채움)을 따르고, 없으면 공고일로 한다.

```
적용 판 = 같은 law_master_id 중 effective_date <= 기준일 < effective_until(없으면 무한)
```

- 그 판을 가지고 있으면 그 판의 정의·기준으로 판정한다.
- 가지고 있지 않으면(지금처럼 현행본만 있는데 현행 시행일이 기준일보다 늦음) 조건을 UNKNOWN으로 두고 `flags=['law_version_unavailable']`를 단다. 지금 데이터명세서 §10의 "공고일 기준으로 다른 판이 적용되는 경우 판단할 수 없다"를 판정 결과에 드러내는 것이다.
- 부칙 경과조치("종전의 규정에 따른다")는 자동 해석하지 않는다. 부칙이 있는 개정이면 보고서에 표시하고 사람이 본다.

### 4.6 판정에서 법령의 역할

- **공고가 자격을 정하고, 법령은 용어의 뜻을 정한다.** "중소기업"이라고 쓴 공고의 조건은 법령 정의(중소기업기본법 + 시행령 기준)로 판정한다. 공고가 따로 범위를 좁히거나 넓히면(예: "매출 50억 이하 중소기업") 공고 조건을 함께 건다(AND).
- 하위 법령이 상위 법령과 어긋나 보여도 평가기가 효력을 판단하지 않는다. 그런 경우는 검수 대상으로만 표시한다.
- 위임으로 정해진 세부 기준이 없는 정의(예: 초기창업기업의 시행령 조문을 아직 못 찾음)는 판정에 쓰지 않고 UNKNOWN이다.
- 모델은 법령을 판정하지 않는다. 법령 원문 요약·설명만 하고, 근거는 `CITES_LAW` 경로의 조문 원문과 링크로 낸다.

### 4.7 구현 순서

| 순서 | 할 일 | 산출물 | 완료 기준 |
|---|---|---|---|
| L1 | 수집 기록의 법령ID·공포일을 행마다 넣고, `law_kind`·`version_seq`·`is_current`를 그래프에 추가 | `concepts_laws.py` | 44개 모두 `law_master_id` 있음 |
| L2 | `ENFORCES` 생성(시행령 제1조 파싱) | `law_hierarchy.py` | 시행령 22개 모두 상위 법률과 연결 |
| L3 | 위임 연결 추출(`explicit_ref` 먼저) | `law_delegations.jsonl` | 정의 검수 시트의 위임 수와 대조 |
| L4 | 정의 `CITES_LAW role`과 `definition_rules.json` `basis`를 조문 ID로 | 정의·규칙 | 중소기업 규칙 근거 5개가 그래프 조문과 해시까지 일치 |
| L5 | 고시 수집(중소기업 범위 고시, 신산업 창업 분야 고시) | `admrul` 수집 | `ADMIN_RULE` 2개 이상 |
| L6 | 공고 인용 `CITES` 적재 | 640건 | V-점검 끝점 없음 0 |
| L7 | 개정 감지·영향 보고(월 1회) | `law_update_report.md` | 시험용 판 바꿔치기로 영향 정의 목록이 나옴 |
| L8 | 기준일 판 선택과 `law_version_unavailable` 표시 | 평가기 | VAL-07 충족 |

L1~L4는 지금 있는 데이터로 할 수 있다. L5 이후는 수집이 필요하고, Aura 반영은 모두 승인 대상이다.

---

## 5. 팀 결정이 필요한 항목

| ID | 질문 | 제안 |
|---|---|---|
| F-1 | `content_hash`에 첨부 파일 해시를 넣나? | 넣는다(첨부만 바꾼 정정 공고를 잡음) |
| F-2 | 원천에서 사라졌지만 마감 전인 공고(`DISAPPEARED`)를 몇 번 뒤에 닫나? | 3회 연속이면 사람이 확인하고 닫는다. 그 전에는 결과에 "확인 필요" |
| F-3 | 나라장터 ID를 `G2B:<공고번호>` + 차수 = 버전으로 바꾸나? | 바꾼다(다른 출처와 같은 규칙) |
| F-4 | 정기 실행을 어디서 하나? | 처음엔 주 1회 수동. 자동화하면 AWS API 서버 예약 실행으로 보고서까지만 |
| F-5 | `data/runs/<run>/` 요약을 git에 넣나? | `run.json`·`report.md`만 넣고 원본·delta 전체는 로컬 |
| F-6 | 법령 범위를 어디까지 넓히나? | 1차: 규칙·정의가 가리키는 시행령·고시. 조례는 지역 조건이 근거로 쓸 때만 |
| F-7 | 정의 근거 조문이 개정되어 재검수 전일 때 그 정의를 쓰는 조건은? | 이전 판이 시행 중인 기간의 공고는 이전 판으로, 새 판 이후 공고는 UNKNOWN(검수 뒤 해제) |
| F-8 | 기준일이 없는 공고의 법령 판 기준일은? | 공고일(B-2와 함께 결정) |

---

## 6. 문서 반영

| 문서 | 반영 |
|---|---|
| 온톨로지 설계서 §9 | "신규 데이터 갱신"·"상위 법령과 개정" 소절 추가(이 문서 요약) |
| 스키마 정의서 §12 | 미완료 항목에 파이프라인(P1)·법령 계층(P1)·개정 반영(P2) 추가 |
| 정리층 문서 §5 한계 | 고정 기준일·차이 계산 없음과 이 설계의 단계 3·4 연결 |
| 도구 사용 안내 | 도구가 생기면(`run_update.py`, `diff_snapshots.py`, `law_hierarchy.py`) 명령 추가 |
