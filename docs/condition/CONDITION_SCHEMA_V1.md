# 지원사업 조건 공통 스키마 v1 설계 및 데이터 분석

작성일: 2026-11-25
분석 기준: `data/normalized/v1/20261124` 정규화 스냅샷 및 관련 정제·청크 코드

## 1. 목적과 범위

K-Startup, 기업마당 및 향후 출처를 공통으로 다룰 수 있도록 자격·제외·우대 조건의 데이터 계약과 논리 표현을 정의했다. 이번 단계는 스키마, 필드 매핑, 표본과 검증에 한정한다. 기존 원본·정제 데이터는 수정하지 않았으며, 자동 조건 추출, 논리 파서, 자격 판정, DB 적재를 구현하지 않았다.

확인 기준 스냅샷은 공고 5,116건(BIZINFO 1,294건, KSTARTUP 3,822건), 청크 32,947건이다. 정규화 보고서는 공고 ID 중복 0, 고아 청크 0, 스키마 오류 0, 개인정보 잔존 탐지 0으로 기록한다. 이 수치는 조건 의미의 검수 완료를 뜻하지 않는다.

## 2. 생성·갱신 파일

- `schemas/conditions/condition-vocabularies-v1.schema.json`: 유형, 상태, 연산자, 혜택, 근거 종류 어휘
- `schemas/conditions/condition-common-v1.schema.json`: 조건, 근거, 논리식, 수집 상태, 공고별 준비도 공통 정의
- `schemas/conditions/condition-v1.schema.json`: 단일 조건 검증 진입점
- `schemas/conditions/logical-group-v1.schema.json`: 논리식 검증 진입점
- `schemas/conditions/notice-condition-set-v1.schema.json`: 공고별 조건 묶음 검증 진입점
- `schemas/conditions/source-field-mapping-v1.csv`: 출처별 원본 필드와 공통 경로 매핑
- `sample_data/conditions/actual-condition-samples.jsonl`: 정규화 데이터에서 발췌한 실제 원문 표본 7건
- `sample_data/conditions/synthetic-condition-samples.jsonl`: 복합 논리와 예외를 보여주는 합성 표본 3건
- `tools/build_condition_samples.py`: 고정 스냅샷의 선택된 행으로 실제 표본을 재생성하는 도구. 입력 데이터는 읽기 전용
- `tests/test_condition_schema.py`: 스키마·샘플·연결·개인정보 계약 테스트

공통 정의를 한 파일에 두고 작은 진입점 스키마에서 재사용하므로, 단일 조건과 공고 전체 묶음의 검증이 같은 필드 규칙을 공유한다. 카테고리는 닫힌 열거형 대신 대문자 ID 규칙을 사용해 새 분류를 구조 변경 없이 추가할 수 있다.

스키마 `$id`는 외부 웹 주소를 가장하지 않는 버전 고정 URN이다. 검증기는 관련 스키마 파일을 먼저 로드해 URI registry에 등록해야 하며, 테스트가 이 경로를 검증한다.

## 3. 공통 데이터 모델

공고 단위 레코드는 `condition_sets.eligibility`, `condition_sets.exclusion`, `condition_sets.preference`를 독립적으로 갖는다. 각 묶음은 조건 목록, 재귀 논리식 루트, 원문 근거, 정보 가용성·완전성·검수 상태와 판정 사용 가능 여부를 보관한다. 조건 객체에는 식별자, 유형, 분류, 판정 대상 필드, 비교 연산자와 값·타입·단위, 기준일, 개인정보를 제거한 원문, 출처·근거·청크 연결, 검색 및 판정 사용 여부를 기록한다.

초기 카테고리 ID는 `BUSINESS_TYPE`, `BUSINESS_LOCATION`, `BUSINESS_AGE`, `REPRESENTATIVE_AGE`, `INDUSTRY`, `REVENUE_FINANCIAL`, `EMPLOYMENT`, `CERTIFICATION`, `TAX_DEBT`, `BUSINESS_STATUS`, `DUPLICATE_BENEFIT`, `LEGAL_SANCTION`, `APPLICANT_TYPE`, `UNCLASSIFIED`를 사용한다. 필요하면 새 대문자 ID를 추가한다. 실제 표본은 원문만 확인됐고 조건 의미를 사람이 확정하지 않았으므로 `UNCLASSIFIED`로 둔다.

조건 유형은 `ELIGIBILITY`, `EXCLUSION`, `PREFERENCE`, `UNCLASSIFIED`다. 분류가 모호하면 강제 분류하지 않는다. 연산자는 논리 `AND`/`OR`/`NOT`/`UNRESOLVED`와 비교 `EQ`/`NEQ`/`GT`/`GTE`/`LT`/`LTE`/`IN`/`NOT_IN`/`BETWEEN`/`EXISTS`/`NOT_EXISTS`를 지원한다. `NOT`은 자식 1개, `AND`와 `OR`은 자식 2개 이상이다. `IN`은 비어 있지 않은 배열, `BETWEEN`은 하한·상한 및 각각의 포함 여부를 요구한다.

예외·단서는 원문과 적용 대상 조건 ID를 qualifier로 남기며, 연결을 확정할 수 없으면 `UNRESOLVED`다. 우대 혜택은 `BONUS_POINTS`, `PRIORITY_SELECTION`, `FINANCIAL_BENEFIT`, `OTHER`, `UNKNOWN`으로 구분한다. 가점은 수치·단위·조건 연결을 별도 benefit 객체에 담는다. 조건식 전체를 원문만으로 추정하지 않는다.

## 4. 정보 상태와 판정 정책

| 상태 | 의미 | 확정 판정 |
|---|---|---|
| `AVAILABLE` | 원문 또는 후보 정보가 존재 | 검수·완전성·구조 조건이 모두 갖춰진 경우만 가능 |
| `NOT_COLLECTED` | 해당 필드를 수집하지 않음 | 불가 |
| `EMPTY` | 원본 필드가 비었거나 null | 조건 없음으로 간주하지 않음 |
| `NOT_EXTRACTED` | 자료는 있으나 내용을 확보하지 못함 | 불가 |
| `NO_CONDITION_CONFIRMED` | 충분한 근거로 조건이 없음을 검수 완료 | 완전성 및 검수 완료와 근거가 있어야 함 |
| `UNKNOWN` | 상태를 판단할 자료가 부족함 | 불가 |

완전성(`COMPLETE`/`PARTIAL`/`UNKNOWN`)과 검수(`UNREVIEWED`/`NEEDS_REVIEW`/`VERIFIED`/`REJECTED`)는 가용성과 별도 축이다. 원문이 존재해도 미검수면 최종 판정에 쓸 수 없다. 확인되지 않은 제외 조건은 자격 판정 준비도를 막는다. 우대 조건 미확인은 기본 자격 판정과 분리하며, 미확인을 “우대 없음” 또는 “부적격”으로 해석하지 않는다. `NO_CONDITION_CONFIRMED`는 근거 문장·완전성·검수 완료를 요구하도록 스키마를 제한했다.

기준일은 `PUBLICATION_DATE`, `APPLICATION_START`, `APPLICATION_END`, `SPECIFIC_DATE`, `RULE`, `UNKNOWN`과 정밀도를 함께 기록한다. 원문에 없는 날짜·시각을 만들어내지 않는다. 연령·업력 기준일이 확인되지 않으면 `UNKNOWN`이다. 행정기관 소재지로 신청 대상 지역을 추론하지 않는다. `context_references`에 원본 값을 조건이 아닌 문맥(`used_as_condition=false`)으로 보관할 수 있다.

첨부 출처의 조건은 검수 완료 전에는 검색 청크에 노출할 수 없도록 `search_eligible=false` 계약을 둔다. 본문 필드 또는 청크에서 온 검색 가능성과 확정 판정 사용 가능성은 별도 필드다.

검색 가능 조건은 실제 `CHUNK` 근거와 기존 chunk ID를 가져야 하며, `search_reason=SOURCE_CHUNK_AVAILABLE`여야 한다. 합성 테스트 출처는 인덱싱 대상이 아니므로 항상 `search_eligible=false`다. 이 규칙은 표본을 실제 검색 자료로 오인하거나 연결되지 않은 텍스트를 검색 가능하다고 표시하는 것을 막는다.

## 5. 출처별 매핑과 데이터 확보 현황

상세 매핑은 `schemas/conditions/source-field-mapping-v1.csv`를 기준으로 한다.

| 항목 | BIZINFO | K-Startup | 해석 제한 |
|---|---|---|---|
| 자격 원문 | `bsnsSumryCn`에서 파싱된 `condition_texts.eligibility.text` | `aply_trgt_ctnt` → 동일 공통 경로 | BIZINFO는 첫 bullet 블록 파싱 결과라 부분 범위, K-Startup은 전체 원문 범위를 검수하지 않아 완전성 미확정 |
| 제외 원문 | 미수집 (`NOT_COLLECTED`) | `aply_excl_trgt_ctnt`가 null/공백 (`EMPTY`) | 두 상태 모두 제외 조건이 없다는 확인이 아님 |
| 우대 원문 | 미수집 (`NOT_COLLECTED`) | `prfn_matr`가 null/공백 (`EMPTY`) | 실제 무조건을 확정한 공고는 없음 |
| 지역 | `region.raw` 없음. 일부 `concept_ids`는 `jurisdiction_org_sido` 기반 | `supt_regin` 원문과 basis 보존 | BIZINFO 행정 관할 태그는 신청 지역 조건으로 사용 불가 |
| 업력·대표자 연령·신청 대상 | `target_group_text`만 별도 제공. 업력·연령 원문 없음 | `biz_enyy`, `biz_trgt_age`, `aply_trgt` 계열 값이 structured 원문 필드에 보존 | 의미가 다른 원문 필드는 서로 대체하지 않음 |
| 조건 청크 | 자격 API 청크 1,196건 / 1,196 공고 | 자격 API 청크 3,487건 / 3,482 공고 | 원문이 있어도 청크가 없는 공고는 BIZINFO 98건, K-Startup 340건. 공고 레코드의 원문 근거는 유지 |

| 출처 | 전체 공고 | 자격 원문 보유 | 제외 원문 보유 | 우대 원문 보유 | 복합·예외 표식 후보 | 정보 부족 |
|---|---:|---:|---:|---:|---:|---:|
| BIZINFO | 1,294 | 1,294 | 0 | 0 | 복합 표식 702, 예외 표식 89, 둘 중 하나 이상 734 | 1,294 |
| K-Startup | 3,822 | 3,822 | 0 | 0 | 복합 표식 2,440, 예외 표식 257, 둘 중 하나 이상 2,483 | 3,822 |

복합·예외 수는 원문 문자열의 표식 탐색에 따른 **후보 수**일 뿐 실제 논리 조건을 확인한 수가 아니다. BIZINFO 자격 원문이 있다고 해서 전체 조건 본문이 수집된 것은 아니다. 제외·우대의 “원문 보유 0건”은 현재 정규화 필드에서 조건 문장을 확보한 공고 수를 뜻하며, 실제 사업에 조건이 없다는 의미가 아니다. 이번 단계에서 조건이 없음을 `NO_CONDITION_CONFIRMED`로 확정한 데이터는 0건이다. 조건 정보를 모두 검수 완료한 공고도 0건이다.

추가로 기존 후보 데이터 `data/normalized/20261124/notices_normalized.jsonl`에는 17,211개 정규화 후보가 있으며 전부 미검수다. 구 K-Startup 조건 후보는 3,819개 공고에 46,176행(27,945 `needs_review`, 18,231 `not_found`)이다. `not_found`는 조건 없음의 근거가 아니다. 후보 데이터는 실제 판정 및 이 샘플에서 검증된 조건으로 취급하지 않았다.

## 6. 청크·근거·지역·일자 위험 분석

- API 자격 청크는 모두 `search_eligible=true`, `privacy_status=CLEARED`이나 `content_review_status=UNREVIEWED`다. 따라서 검색용 보존이 판정 가능을 뜻하지 않게 했다.
- 제외·우대 API 청크는 확인되지 않았다. 일부 첨부 자격/제외 청크는 모두 검색 제외 및 미검수 상태이며, 개인정보 검토 필요 표식도 있다. 이번 설계의 확정 판정 근거로 사용하지 않는다.
- 현재 정규화에는 공고 ID와 청크의 연결은 있지만, 조건 단위 근거 ID·문자 위치는 일관되게 제공되지 않는다. 새 모델은 이를 nullable evidence ID, chunk ID 목록, 원문 위치로 분리하고 출처 원문 필드까지 추적한다.
- BIZINFO `region.raw`는 1,294건 모두 비어 있고, `concept_ids` 964건은 행정기관 소재지 기반이며 나머지 330건은 없다. 신청대상 지역을 확정할 수 없다.
- K-Startup은 지역 원문 3,822건 및 업력/대표자 연령/신청 대상 원문이 구조화 필드에 존재하지만, 원문과 단순 후보를 보존할 뿐 자동 조건화하지 않는다.
- 접수 시작·종료일이 확인되는 BIZINFO는 379건, 미확인은 915건이다. K-Startup은 3,822건의 접수일 값을 보유한다. K-Startup `fetched_at`은 날짜 정밀도이며 BIZINFO는 시간대 포함 일시다. `fetched_at`은 공고 게시일 또는 연령·업력 기준일 대용으로 사용할 수 없다.
- 기존 이슈 장부 7,344건 분류: `LEGACY_END_OF_DAY_TIMESTAMP_DERIVED_FROM_DATE` 4,201건(BIZINFO 379, K-Startup 3,822)은 날짜를 기존 코드가 종료 시각으로 표현한 흔적으로, 날짜 수준 기준일에는 NON_BLOCKER이나 정밀한 시각 비교에는 보정 전 BLOCKER다. 정규화 기한 날짜는 DATE로 유지해야 한다. `INVALID_OR_MALFORMED_URL` 3,143건은 모두 K-Startup `guide_url`로, malformed/no-host 2,597, 비HTTPS 48, 허용 도메인 외 HTTPS 498이다. 안내 URL 품질 문제는 조건 스키마 설계에는 NON_BLOCKER이며, 해당 URL을 조건 근거로 요청하거나 외부 이동하지 않는다.

데이터 제공 범위 차이(EXPECTED_DIFFERENCE): BIZINFO의 제외·우대 미수집, K-Startup 필드의 빈 값, 출처별 날짜 정밀도, BIZINFO 지역 원문 부재, 구조화 원문 필드 차이. 문제 레코드를 임의 보충하지 않고 가용성·근거 상태로 보존한다.

## 7. BLOCKER / NON_BLOCKER / EXPECTED_DIFFERENCE

### BLOCKER — 실제 자격 판정에 앞서 해결 필요

1. 자격 원문은 있지만 조건 단위로 검수·구조화된 자료가 없다. 17,211개 기존 후보도 전부 미검수다. 현재 데이터로 자동 자격 판정 정확성을 보장할 수 없다. 다음 단계에서 표본 수작업 라벨, 조건 문장 경계·근거 연결 및 검수 워크플로가 필요하다.
2. 제외 원문은 BIZINFO에서 미수집이고 K-Startup에서는 비어 있는 값으로 제공된다. 어떤 공고도 제외 조건 없음이 검수 확정되지 않았다. 최종 적격 판정 전 출처 원문·공식 상세 본문·해당 시 문서 근거를 확보하고 검수해야 한다.
3. BIZINFO 자격 원문은 첫 bullet 블록으로 제한된 파싱 결과라 완전성 보장이 없다. 조건 전체 본문을 확인하지 못하면 단독으로 판정 근거가 될 수 없다.
4. 일부 텍스트는 본문 청크 또는 개별 evidence ID와 연결되지 않는다(원문은 공고 필드에 보존). 판정용 추적성을 위해 근거 수집·문자 구간 연결 및 미검수 표시가 필요하다.
5. 기준일을 요구하는 업력·연령 조건에서 신뢰할 날짜가 원문에 없으면 평가할 수 없다. 접수일이나 수집일을 임의 대입하지 않도록 해야 한다.

### NON_BLOCKER — 병행 개선

- K-Startup `guide_url` 3,143건의 무결성/허용 도메인 이슈는 별도 URL 정비 대상이다. 현재 스키마는 해당 URL을 조건 출처로 사용하지 않으므로 설계 진행 자체는 막지 않는다.
- 날짜→종료시각 구형 표현은 날짜 정밀도 보존으로 관리할 수 있다. 시각 단위 판정에는 사용하지 않는다.
- 복합·예외 정규식 표식은 라벨링 대상의 우선순위 설정에만 활용할 수 있으며, 논리 구조의 정답으로 사용할 수 없다.

### EXPECTED_DIFFERENCE — 출처 범위 차이

- 출처가 제공하지 않는 조건 필드와 상세도 차이, 빈 값 표기 방식 차이, 날짜 정밀도 차이, 지역 원문의 제공 여부 차이.
- 상태를 통일하되 출처에 없는 값은 null 또는 `NOT_COLLECTED`/`UNKNOWN`으로 둔다. 출처의 의미와 범위를 단일 값으로 강제 통합하지 않는다.

## 8. 실제·합성 표본 구성

실제 표본 7건은 원문 비교·근거 연결·검수 제한을 보여준다. 실제 조건의 분류, 연산자, 값, AND/OR 관계를 추정하지 않는다. 일부 K-Startup 표본에는 지역·업력·대표자 연령 원문이 `context_references`로 보존되며 `used_as_condition=false`다. 원문은 정규화 데이터에 적용된 개인정보 제거 상태 그대로 복사한다.

합성 표본 3건은 실제 사업과 무관하다. AND 자격과 검수 완료된 미해당 제외, 중첩 OR/AND와 연결된 예외·5점 가점, 미검수 첨부 후보·미추출 제외 정보를 각각 표현한다. 모든 합성 레코드는 `SYNTHETIC_TEST`이며 합성 근거 ID를 사용하고 검색 대상에서 제외한다.

## 9. 검증 결과

`python -m unittest tests.test_condition_schema -v` 실행 결과 **6개 테스트 통과**. 가상환경의 `pytest` 모듈은 설치되어 있지 않아 표준 라이브러리 `unittest` 러너로 실행했다.

검증 항목:

- JSON Schema Draft 2020-12 문법 및 모든 샘플 스키마 일치
- 실제/합성 표본 분리 및 실제 공고 원문·청크 ID 연결
- 공고 내 중복 표본 ID 방지
- 합성 논리 참조, 예외 및 혜택 적용 조건 연결 무결성
- 스키마가 잘못된 `NOT` 자식 수와 미검수 `NO_CONDITION_CONFIRMED`를 거부
- 배열이 아닌 `IN`, 상한이 빠진 `BETWEEN`, 미검수 첨부 검색 노출을 거부
- 청크 근거가 없는 검색 노출 및 합성 데이터의 검색 노출을 거부
- 기존 PII 검사 함수에 따른 표본 개인정보 잔존 0건
- 정규화 보고서의 공고 5,116건·청크 32,947건 보존 확인

이 검증은 스키마·표본 계약을 검사한다. 전체 공고를 변환하거나 의미를 검증하지 않는다. 기존 normalized 입력 및 정제 데이터를 쓰거나 다시 생성하지 않았다.

## 10. 착수 판단 및 다음 단계

**스키마 설계는 완료했고 1단계 구현 작업 착수는 가능하다.** 다만 데이터 기반 확정 자격 판정은 BLOCKER가 해소되기 전까지 불가하다. 다음 단계는 자동 판정기가 아니라 먼저 제한된 표본에 대한 사람 검수 데이터셋과 원문 근거 위치를 만들고, BIZINFO 상세 조건 범위 및 제외·우대 정보가 확보되는지 출처별로 확인하는 순서가 안전하다. 스키마 검수에서 필드 누락이 발견되면 버전을 관리해 확장한다.

현재 JSON Schema는 형식·필수 상태 계약을 강제하지만, 모든 조건 필드 간 의미적 일관성이나 전체 참조 무결성은 테스트 코드가 추가 검사한다. 향후 적재 전용 validator에서 공고 ID 중복, 조건 ID 전역 유일성, logical root 참조, evidence ID 존재를 교차 검사해야 한다.


## ???? ?? ??? ?? (2026-11-25)

???? ?? ?? ????? ??? ?? ???????? ??? ???? ??, ???????? ?? ??? ? ??? ??? ????. ?? ?? ???? ???? ???. ?? ???? ?? `UNCLASSIFIED`, `UNKNOWN`, `UNREVIEWED`, `NOT_COLLECTED` ??? ?? source path? ??? ???? ?? ???? ??? ???? ???? ???.

?? ??? ????? ??, ??, ?? ?? ??, ?? ?? ??? ?? ?? ??? ?? ????. ?? ??? ?? ?? ? ?? ?????, ???? ?? ???????? ??? `NOT_COLLECTED`? ???. ?? ??? ?? ??? `G2B_SUPPORT_COMPATIBILITY_V1.md`? ????.
