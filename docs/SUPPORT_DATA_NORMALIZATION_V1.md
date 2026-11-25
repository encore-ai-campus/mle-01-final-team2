# 지원사업 공통 데이터 정규화 v1

작성일: 2026-11-25

대상 스냅샷: `data/cleaned/20261124`
정규화 출력: `data/normalized/v1/20261124`

## 목적과 범위

K-Startup과 기업마당의 형식 차이를 출처 중립 스키마로 맞추되 출처별 의미와 미제공 상태를 보존한다. 원본·기존 정제 데이터는 읽기만 했고, 정규화 산출물은 별도 경로에 생성했다. API 호출, 기존 파이프라인 연결, DB 적재, 원본 덮어쓰기는 수행하지 않았다.

## 조사 데이터와 기존 구조

| 자료 | 레코드/항목 | 관찰 및 처리 |
|---|---:|---|
| 정제 공고 | 5,116 (BIZINFO 1,294, KSTARTUP 3,822) | 공통 공고 스키마의 입력 |
| 정제 청크 | 32,947 (BIZINFO 15,851, KSTARTUP 17,096) | 식별자와 원문 section을 보존하고 section 의미만 표준화 |
| 기존 값 정규화 후보 | 17,211 facts | 검수 전 후보 계층으로 유지. 신규 스키마로 재해석하거나 덮어쓰지 않음 |
| K-Startup 조건 후보 | 3,819 공고, 46,176 후보 조건 | 정제 공고 3,822건과 3건 차이. `not_found`는 조건 부재 확인으로 간주하지 않음 |
| 공개 공고 DB 적재 표본 | 90 notices 및 별도 Neo4j/Supabase 입력 | 본 스냅샷과 다른 입력 계약. 적재 코드 변경·실행하지 않음 |

`tools/preprocess_notices.py`는 현재 cleaned JSONL을 생성하는 원천 어댑터다. `tools/normalize_values.py`는 미검수 정규화 후보를 만드는 별도 단계다. GraphRAG 및 공개 공고 적재 코드는 서로 다른 데이터 계약을 소비하므로 이번 작업에서는 연결하지 않았다. IBK 규정용 Neo4j/Supabase 로더도 지원사업 정제 데이터 로더가 아니다.

## 확정한 공통 구조

- 공고와 청크 스키마는 각각 `schemas/support-data/support-notice-v1.schema.json`, `schemas/support-data/support-chunk-v1.schema.json`에 둔다.
- 출처별 매핑 및 의미 차이는 `schemas/support-data/source-field-mapping-v1.csv`에 기록했다.
- 구현은 `tools/normalize_support_data.py`; Python 표준 라이브러리와 기존 개인정보 정제 모듈을 사용하며 새 패키지 의존성은 추가하지 않았다.
- 생성 레코드는 `data/normalized/v1/20261124/notices.jsonl`, `chunks.jsonl`, `normalization_issues.jsonl`, `normalization_report.json`이다.
- ID는 원값을 보존한다. 공고 ID, 청크 ID, 공고 참조 사이에 생성 또는 재번호 부여가 없다.
- 결측 상태는 `PRESENT`, `EMPTY`, `NOT_COLLECTED`, 일부 호환 변환은 `DERIVED`로 별도 기록한다. 빈 문자열·null·빈 배열·false·0을 서로 대체하지 않는다.

## 필드 매핑과 의미 보존

### 일시 및 접수 상태

`fetched_at`, 공고일, 수정일, 접수 시작·종료, 마감은 `value`, `raw_value`, `precision`, `timezone`, `status`, `basis`를 갖는다. 날짜 원문은 DATE 정밀도이고 시간이나 시간대가 보충되지 않는다. K-Startup의 공고일과 수정일은 원천 미제공으로 null/`NOT_COLLECTED`다. BIZINFO가 명시적으로 null을 제공한 값은 `EMPTY`로 표시한다.

두 출처의 기존 `deadline_at` 4,201건은 접수 종료일에 `23:59:59+09:00`를 덧붙인 값과 일치했다. 이 값은 실제 원천 시간으로 가장하지 않고 종료일 기준 `DERIVED_FROM_END_DATE` / `DATE`로 표현하며 원문 값도 `source_metadata.legacy_deadline_at`과 정규화 timestamp의 `raw_value`에 보존했다.

### 청크 section

`title_summary`(BIZINFO 요약 청크)와 `title_body`(K-Startup 공고본문 청크)는 역할과 내용 길이가 달라 각각 `NOTICE_SUMMARY`, `NOTICE_BODY`로 유지한다. 두 값을 같은 section으로 합치지 않는다. API 조건·지원·평가·신청방법 section은 공통 이름으로 매핑하고, 첨부 section의 접미 위치 정보는 `section_original`에 보존한다.

### URL, 연락처, 분류, 지역

- `detail_url`은 `notice_url`, 명시적으로 제공된 `apply_url`은 신청 URL, `guide_url`은 안내 URL이다. 없는 URL을 생성하거나 신청 방법 본문에서 신청 URL로 추론하지 않는다. 신청 방법 텍스트에 포함된 URL은 용도 `UNCLASSIFIED`로만 보존한다.
- URL은 HTTPS와 호스트를 검사한다. 공고 상세 URL은 K-Startup은 `k-startup.go.kr`, 기업마당은 `bizinfo.go.kr` 계열 호스트만 VALID다. 안내 URL도 출처 공식 도메인에 제한하며, 외부 신청 URL은 HTTPS면 유지하되 호스트 검증을 완료한 것으로 표시하지 않는다. INVALID URL을 고치거나 요청하지 않는다.
- `contact_text`, `contact_phone_raw`는 `contacts[]`로 변환한다. 전화번호 형식이나 이메일 도메인만으로 분류하지 않고, `대표전화`, `사업문의`, `신청문의`, `문의처`처럼 명시된 공식 업무 문맥 또는 K-Startup 원천의 연락처 전화번호와 연락 부서 필드 쌍이 있는 경우만 `OFFICIAL_BUSINESS`로 보존한다. 이 값은 공고 메타데이터에만 두고 청크에서는 제외한다.
- 명시적 개인 문맥이나 담당자 이름과 가까운 연락처는 값과 개인 이름을 출력하지 않고 `PERSONAL`/`REDACTED`로 집계한다. 공식·개인 여부를 확인할 문맥이 부족하면 값은 출력하지 않고 `UNCLASSIFIED`/`NEEDS_REVIEW`, `service_visibility=false`로 검수 대기열에 둔다. 이 때문에 원문 값이 필요한 검수는 접근 통제된 기존 cleaned 입력에서 수행한다.
- 공식 연락처의 `normalized_value`는 전화번호의 구분 문자를 제거하거나 이메일 도메인만 소문자로 바꾼다. 원본 표기는 `value`에 유지한다. 기관명과 부서명은 출처 필드가 명시적으로 연결되지 않아 이번 스냅샷에서는 추정하지 않고 null로 둔다.
- 연락처가 본문·조건·청크 등 다른 텍스트 필드에 나타나면 해당 텍스트에서는 전화번호·이메일을 마스킹하고 담당자 이름 문맥을 제거한다. 연락처 원본 필드 자체는 이번 변경으로 수정하지 않았다.
- BIZINFO 원본 API `refrncNm`은 기존 파서가 `contact_text`로 옮긴 값임을 확인했다. K-Startup 원본 API의 `prch_cnpl_no`와 `biz_prch_dprt_nm`이 정제 필드 `contact_phone_raw` 및 `operating_dept`에 각각 연결되는 것도 확인해 부서와 연락처 쌍의 근거로 사용했다. 원본 파일은 수정하지 않았다.
- 이번 입력에서 공식 업무 문맥 또는 출처 부서/전화 필드 쌍으로 분류해 보존한 연락처는 BIZINFO 219건, K-Startup 3,695건이다. BIZINFO 개인 연락처 후보 2건은 값과 이름을 제거했다. 미분류 연락처는 BIZINFO 2,000건, K-Startup 119건이며 모두 검수 대기열에 등록되어 검수 등록률은 100%다. 세부 수치는 실행 보고서의 `contact_processing_by_source`와 `unclassified_contact_review_coverage`에 기록한다.
- 분류는 `category.source_major/source_medium`에 원출처 값을 그대로 둔다. 통합 분류 체계는 확정하지 않는다.
- `region.raw`, concept ID, basis, scope/tag hint를 분리한다. 소관기관 소재지를 신청 대상 지역으로 승격하지 않는다.

### structured 및 첨부 메타데이터

- `target_group_text`, `business_age_raw`, `founder_age_raw`, `applicant_target_raw`를 분리한다. 기업마당의 대상 그룹 텍스트를 K-Startup의 신청 대상 필드로 복사하지 않는다. 없는 출처 값은 null이며 availability에서 미수집 여부를 구별한다.
- 첨부파일 원문이나 문서 본문은 신규로 추출·다운로드하지 않는다. 첨부 청크 12,305개는 `search_eligible=false`로 격리했다. count가 null이면 0으로 바꾸지 않고 `NOT_COLLECTED`/`NOT_ATTEMPTED`로 둔다. 0개가 명시된 경우만 `NO_ATTACHMENTS`를 쓴다.

## 변환 결과 및 검증

입력 SHA-256은 보고서에 기록했다. 변환 결과 공고 5,116건, 청크 32,947건이며 출처별 입력/출력 건수가 일치한다. 공고 ID 중복 0, 청크 ID 중복 0, 공고 참조가 없는 청크 0, 스키마 검사 오류 0이다. 개인정보 검사는 개인/미분류 연락처 원문이 아닌 모든 출력 텍스트에서 잔존 0건이며, 명시적 업무 문맥으로 자동 분류된 공식 연락처는 의도적으로 공고 metadata에 보존한다. API 텍스트 청크 20,642개만 검색 허용되며 첨부 청크는 검수 전 검색에서 제외했다. 저장된 출력 집계는 `normalization_report.json`에 있다.

자동 검토 issue는 아래 유형을 포함한다.

- 기존 마감 시각을 종료일에서 유래한 날짜로 표시한 기록 4,201건(정보성 근거 기록)
- HTTPS/출처 공식 도메인 기준을 통과하지 못했거나 URL 형식이 잘못된 값 3,143건(값은 임의 수정하지 않음)
- 기존 조건 후보 파일의 공고 3건 차이
- BIZINFO/K-Startup 간 원천 필드 제공 범위 차이 및 과거 K-Startup `guide_url_malformed` 플래그

기존 `data/normalized/20261124` 값 후보는 계속 검수 전 상태다. K-Startup의 `not_found`는 추출 규칙이 후보를 찾지 못한 상태일 뿐 원문에 조건이 없다는 확정값이 아니다. 이 단계에서는 조건 후보를 조건 판단에 쓰거나 고치지 않았다.

## 테스트

`tests/test_normalize_support_data.py`는 날짜 정밀도와 시간대 비생성, 출처별 미수집/빈 값, URL 용도 및 공식 URL 규칙, 공식·개인·미분류 연락처 처리, 청크 연락처 제거, section 구분, 첨부 검색 격리, ID·건수 무결성 및 반복 실행 바이트 동일성을 검증한다. 출력은 별도 임시 디렉터리에서 생성해 원본 데이터 파일을 바꾸지 않는다.

## 후속 영향과 남은 작업

신규 정규화 출력은 기존 GraphRAG·검색·Neo4j·Supabase 코드에 아직 연결하지 않았다. 소비자별 필드 계약을 비교하는 별도 마이그레이션 작업이 필요하다. 입력 cleaned 파일에는 기존 개인정보 필드가 있으므로 신규 출력의 개인정보 기준을 입력 정책에 소급 적용한 것은 아니다. URL의 허용 호스트와 외부 신청 사이트 정책, 연락처 문맥 이름 탐지 범위, source별 상태값을 추가 데이터 출처를 붙이기 전에 검토해야 한다.

논리 조건 스키마 단계는 이 공통 데이터 스키마 및 미검수 데이터 사용 정책을 바탕으로 별도 진행한다.
