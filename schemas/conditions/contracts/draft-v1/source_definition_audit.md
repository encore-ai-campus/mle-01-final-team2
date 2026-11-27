# 기존 표현 체계 전수 조사

이 폴더는 `DRAFT_NOT_DEPLOYED` 계약 초안이다. 운영 스키마·카탈로그의 대체물이 아니며 현재 허용 집합은 LLM의 기존 22개를 그대로 열거했다. 속성별 설명·타입·연산자·단위·역할은 기존 정의를 좁혀 해석한 **검토 대상 의미 계약**이다. 모든 조합을 기존 validator가 이미 강제한다고 주장하지 않는다. JSON의 definition_status와 compatibility_note가 이 구분을 명시한다.

## 정의 위치와 중복

| 출처 | 실제 정의·타입·연산자·범위 | 중복·차이 |
|---|---|---|
| condition-v1 / condition-common-v1 | category_id는 대문자 패턴의 열린 어휘, field는 nullable string. 비교 연산자 enum, value_type enum, IN 비어 있지 않은 배열, BETWEEN lower/upper + inclusive, EXISTS/NOT_EXISTS는 value=null 및 UNKNOWN | 속성별 의미·타입·연산자 표가 없음 |
| condition-v1.1 / condition-common-v1.1 | 같은 열린 속성 계약; evaluation_phase/fulfillment_phase/requirement_kind/temporal/evidence/external reference 추가 | 구조 의미가 확장됐지만 닫힌 속성 목록은 없음. v1 공통 정의를 복사·확장한 별도 파일이므로 향후 동기화 필요 |
| condition-vocabularies-v1 | condition types, operators, value types, source/review/reference 상태 공유 | operator 일반 enum에는 논리 연산자도 있으나 condition.operator는 comparisonOperator/null만 사용 |
| CONDITION_SCHEMA_V1.md | 초기 14개 카테고리 문서화 | BUSINESS_TYPE, BUSINESS_LOCATION, BUSINESS_AGE, REPRESENTATIVE_AGE, INDUSTRY, REVENUE_FINANCIAL, EMPLOYMENT, CERTIFICATION, TAX_DEBT, BUSINESS_STATUS, DUPLICATE_BENEFIT, LEGAL_SANCTION, APPLICANT_TYPE, UNCLASSIFIED. LLM22와 같지 않음 |
| 규칙 v1 PATTERNS | 사업체/소재지/업력/대표자 연령/매출/고용 중심; EMPLOYMENT, REVENUE_FINANCIAL 사용. 매출 값과 원래 원/만원/억원을 유지; 인원 PERSON, 나이/기간 YEAR | 연산자 한글→GT/GTE/LT/LTE 사전이 별도로 있음. 대표자 세의 단위를 YEAR로 표준화함 |
| rules_v2 (실험 A–E) | APPLICANT_AGE, BUSINESS_AGE, EMPLOYEE_COUNT, INDUSTRY_REVENUE_SHARE, REVENUE, FINANCIAL_CAPACITY, BUSINESS_TYPE, APPLICANT_TYPE, APPLICANT_ADDRESS, BUSINESS_LOCATION, LICENSE_STATUS, CERTIFICATION, BUSINESS_REGISTRATION_STATUS, PROGRAM_PARTICIPATION, DOCUMENT_SUBMISSION, INDUSTRY 등 | YEAR/MONTH/PERSON/PERCENT, KRW 배율 적용. BETWEEN lower/upper inclusive. 사업체/신청자 단어 목록·주소 문맥이 내부 정의됨. 원래 카탈로그와 의미가 일부 겹치지만 공유 registry를 import하지 않음 |
| LLM ATTRIBUTE_CATALOG | 기존 22개 닫힌 목록; field/category 일치 검사 | 각 속성의 상세 의미 설명은 프롬프트에 없고 이름 목록 중심. 같은 연산자/type enum이 스키마와 코드에 중복됨 |
| attribute-normalization-v2 | applicant_address/business_location 명시 alias + 유일 casefold; APPLICANT_TYPE의 규모 표현 모호성 보류 | category는 대소문자 자동 보정하지 않음. catalog membership은 의미 적합성의 충분조건이 아님 |
| LLM _check_value_shape | 타입·연산자 교차 검사, BETWEEN key 정확성, EXISTS payload 제약, 날짜 기준 검사 | 금액/단위/지역 이름을 일반적으로 정규화하지 않음 |
| legacy_augmented FIELD_MAP | company_size→BUSINESS_TYPE는 IS_A 레이블일 때, founder_age→REPRESENTATIVE_AGE, business_age→BUSINESS_AGE. 숫자 YEAR만 허용 | 이름만 보고 global alias로 합치면 위험. company_size는 크기, founder/대표자 역할은 맥락이 다름 |
| graphrag/condition_schema.unify | 별도 소문자 region/business_age/founder_age/applicant_type, WITHIN, labels/ranges/value 내부 unit 등 | 같은 business_age 이름이어도 저장 구조가 다름. founder_age 상한은 min inclusive/max exclusive. 이 경로의 alias는 LLM field alias와 구분해야 함 |
| conditions/source-field-mapping | 원본 API 필드→공통 원문 경로·가용성·문맥 매핑 | semantic field alias 목록이 아님. 관할기관 소재지를 신청지역으로 쓰면 안 됨. 구조화 hint는 근거 없는 조건으로 승격 불가 |
| support-data/source-field-mapping | notice/chunk 정규화 경로 및 타입·출처 매핑 | 조건 의미 매핑과 별도 층. name이 같아도 혼합 금지 |
| v1 평가기 | 기존 semantic_signature에 value_type·reference/scope 등의 필드 포함 | v1.1 평가와 동일 지표라고 혼용 금지 |
| v1.1 평가기 | COMMON_FIELDS=(condition_type, category, field, operator, value, unit) + exact evidence; FIELD_ALIASES 비어 있음; extended 필드는 별도 | 문법적 숫자/배열 정규화만 존재. 단위·통화배율·속성 의미 자동 정규화 없음 |
| prevalidation adapter | raw field/operator/value/unit, 첫 인용문 유일 span. extended 필드 일부만 전달 | 검증 후는 v2 속성 정규화·조건 검증 경로. 전후 표현 체계가 동일하지 않음 |

실제 경로·소스 해시는 attribute_definition_inventory.csv 및 contract_build_metadata.json에 기록했다. 22개 canonical 항목별 의미·사용 가능한 연산자/type/unit/범위는 attribute_semantic_contract_v1.json을 기준으로 검토한다.

## 열린 스키마·초기 어휘·닫힌 카탈로그의 관계

EMPLOYMENT는 근로자 수인 경우만 EMPLOYEE_COUNT 후보로 검토한다. 고용 여부나 채용 행위이면 다른 개념이다. TAX_DEBT, BUSINESS_STATUS, DUPLICATE_BENEFIT, LEGAL_SANCTION은 초기 문서에는 있으나 현재 LLM22에 없다. 이 초안에 운영 속성으로 추가하지 않으며 아래 의미로 별도 검토 대상에 둔다.

| 초기 문서 전용 이름 | 일반 의미·제안 타입 | 관련 기존 개념과 경계 | 조치 |
|---|---|---|---|
| TAX_DEBT | 조세 체납 상태; 상태 문자열/명시적 boolean | FINANCIAL_CAPACITY와 다름 | 범용 필요성 및 카탈로그 승인 전 HOLD |
| BUSINESS_STATUS | 휴폐업 등 영업 상태; 상태 문자열 | BUSINESS_REGISTRATION_STATUS와 다름 | 상태 코드/기준일 계약 필요 |
| DUPLICATE_BENEFIT | 지원·혜택 중복 수혜 상태 | DUPLICATE_OCCUPANCY는 입주 중복만 | 별도 개념 검토 |
| LEGAL_SANCTION | 법적 제재·제한 상태 | 인증/사업자등록/조세와 다름 | 제재 종류·기간·관할 근거 필요 |

이 네 항목은 기존 문서의 상태 기록이며 파일럿 정답을 보고 추가한 속성이 아니다. 신규 semantics가 승인돼도 열린 구조 스키마상 새 category_id가 들어가는 것과 추출기 카탈로그 허용은 별개다. 새 필수 메타데이터나 저장 상태를 추가할 때만 구조 스키마 버전을 별도로 검토한다.

## 자동 치환 금지 경계

APPLICANT_TYPE/BUSINESS_TYPE, APPLICANT_ADDRESS/BUSINESS_LOCATION, REPRESENTATIVE_AGE/TEAM_MEMBER_AGE, 거주 사실/증빙 사실, 자격 사실/서류 제출 의무, 사업자등록 사건/등록 상태는 서로 다른 개념이다. 기관·신청자·대표자·사업장·본사·지점·팀원 역할을 보존한다. 신규 속성 후보는 이 역할·관계 차이가 출처와 무관하게 필요한 경우로 한정하며 아직 승인하지 않는다.

## 별도 기술 부채: 논리 평가 adapter

3D-1에서 확인한 logical_roots의 평탄한 조건 참조 전달, 최상위 logic_sections.root 연결, 별도 exceptions 및 unresolved_relations 연결을 별도 작업으로 둔다. v1.0 경로의 v1.1 예외 효과/미해결 관계/시점 필드 미지원도 명시해야 한다. 조건 strict F1과 논리 평가 연동 지표는 구분하며 이 계약 단계에서 코드를 수정하거나 점수를 보정하지 않는다.
