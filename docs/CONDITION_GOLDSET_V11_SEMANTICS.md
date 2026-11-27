# 조건 정답 검수 스키마 v1.1 의미 규약 (2026-11-26)

## 범위와 호환성

`condition-common-v1.schema.json`, v1.0 검수 스키마 및 자료는 그대로 둔다. v1.1은 공통 조건 객체(`condition-common-v1.1.schema.json`, `condition-v1.1.schema.json`, `notice-condition-set-v1.1.schema.json`)와 검수 패킷 스키마 두 개를 별도 버전으로 추가한다. 기존 AND/OR/NOT, EQ/IN/BETWEEN, 조건 유형은 재사용한다. `gold_logic_roots`는 호환용 투영이며, v1.1에서는 `gold_logic_sections[].root`와 순서 및 내용이 같아야 한다. 루트 배열 순서나 group_id의 문자열로 유형을 추론하지 않는다. 공통 공고 객체의 `logic_sections`도 같은 구역 구조를 사용한다.

| v1.0 필드/상태 | v1.1 추가 필드 | 의미 및 필수성 |
|---|---|---|
| `schema_version=1.0` | `schema_version=1.1`, `evaluation_version=1.1` | 패킷별 필수. 점수 비교 버전을 고정한다. |
| `condition_type`, `gold_logic_roots` | `gold_logic_sections[]` | 논리 구역별 유형, 평가·이행 시점, 루트, 검수 상태. 필수. 여러 이행 시점이 섞인 구역의 이행 시점은 `UNKNOWN`이고 조건별 시점을 확인한다. 사후 의무는 구역 유형 `POST_SELECTION_OBLIGATION`으로 둔다. |
| `applicability_scope`, `reference_date` | `evaluation_phase`, `fulfillment_phase`, `requirement_kind` | 조건별 필수. 평가 시점과 실제 이행 시점, 현재 상태/미래 가능성/이행 의무를 구별한다. 확인 불가 시 `UNKNOWN`. |
| `reference_date`, `reference_date_type` | `temporal_constraint` | 필수 키, 값은 null 가능. 기준 이벤트/고정 날짜/상대 기간/단위/연산자/경계 포함/적용 대상/이벤트 날짜 확인 여부. |
| `evidence_reference` | `evidence_references[]` | 조건과 예외별 필수. PRIMARY/SUPPORTING/CONTEXT 역할과 문서, 필드, 문자 좌표, 실제 근거 문자열, 기존 evidence ID를 보존한다. 기존 단일 근거는 PRIMARY로 옮긴다. |
| `gold_exceptions[].applies_to_gold_ids` | `effect`, `effect_target`, `replacement`, `precondition`, `effect_confirmed`, `application_mode` | 예외별 필수. 기존 대상 참조는 유지한다. `AST_ONLY`는 AST에 반영된 효과를 다시 적용하지 않는다. `EFFECT_ONLY`는 별도 효과로 적용한다. |
| `decision_possible` | `structure_capable`, `facts_sufficient`, `external_reference` | 조건별 필수. 형식 구조화, 판정 사실의 충분성, 외부 문서 수집 여부를 분리한다. 외부 참조는 null 가능. |

원문의 상대 기한은 달력상 월로 보존한다. `3 MONTH`를 `90 DAY`로 치환하지 않는다. 기준 이벤트 날짜가 없으면 실제 마감일은 `UNKNOWN`이다. 원문에 없는 절대일이나 외부 법령 세부 요건을 생성하지 않는다. `NOT_COLLECTED`는 해당 요건의 부재를 뜻하지 않는다.

## 결정론적 판정 명세

이 문서는 판정 엔진 구현이 아니다. 향후 엔진은 조건별로 `structure_capable`, `facts_sufficient`, `review_status`, 평가 결과를 별도로 관리한다. 결과는 `TRUE`, `FALSE`, `UNKNOWN` 세 값이다. 누락된 사실은 부재나 0으로 대체하지 않는다. `EXISTS`는 입력 사실의 존재를 검사하므로 정성 요건의 충족을 대신하지 않는다. `ELIGIBILITY=TRUE`는 자격 충족, `EXCLUSION=TRUE`는 제외 사유 해당을 뜻한다. 우대의 `UNKNOWN`은 신청 자격의 `FALSE`가 아니다.

AND: 하나라도 FALSE면 FALSE, 모두 TRUE면 TRUE, 나머지는 UNKNOWN. OR: 하나라도 TRUE면 TRUE, 모두 FALSE면 FALSE, 나머지는 UNKNOWN. NOT: TRUE/FALSE 반전, UNKNOWN은 UNKNOWN. `UNREVIEWED` 또는 `NEEDS_REVIEW`는 실제 확정 판정에 사용할 수 없다. 발췌문의 전체 자격/제외 완전성이 `UNKNOWN`이면 확인된 조건을 모두 충족해도 전체 신청 가능을 확정하지 않는다. `FUTURE_FEASIBILITY`는 신청 시 미래 이행 가능성을 평가하며, 현재 이행 완료를 요구하지 않는다. `FULFILLMENT_OBLIGATION`은 해당 사후 단계에서 확인한다.

예외 `EXCLUDE_FROM_SCOPE`는 적용 대상 이력에서 해당 범주만 제거한다. 다른 제한 대상 이력은 남는다. `REPLACE_DEADLINE`은 지정된 조건의 기한 속성만 바꾼다. `WAIVE_REQUIREMENT`도 대상과 전제에만 적용한다. `AST_ONLY` 예외는 설명 및 근거용이므로 재적용하지 않는다. 예외 효과가 미확정이면 `UNKNOWN`으로 둔다.

## 변환 및 평가 정책

v1.0에서 v1.1로의 자동 변환은 기본 근거, 기존 조건·논리와 검수 대기 상태를 보존하는 것까지만 안전하다. 단계, 이행 성격, 외부 문서 수집 여부, 예외 효과는 원문 확인 없이 추론하지 않고 `UNKNOWN`/null로 둔다. 이번 5건의 추가 값은 기존 원문과 이전 검수 의견을 다시 대조한 수동 초안이다. 전체 데이터에 일괄 적용하지 않는다.

검수 반영 도구는 버전별 스키마를 선택하고, v1.1의 구역 참조·근거 위치를 검증한다. 기존 v1.0 입력과 검증 경로는 유지한다. 기존 평가기의 v1.0 완전 일치·부분 일치 정의는 바꾸지 않는다. v1.1의 신규 의미 필드, 구역 유형, 복수 근거를 비교하는 점수 규칙은 아직 구현되지 않았으므로 v1.1 평가 사전 점검은 명시적으로 `BLOCKED`/`NOT_COMPUTED` 처리한다. 복수 근거는 평가 시 PRIMARY의 위치 정확성과 SUPPORTING 근거의 집합 일치를 별도 기준으로 설계해야 한다. 보조 근거 누락을 완전 일치로 간주해서는 안 된다. 버전별 기준이 다르면 점수 직접 비교를 금한다.

## 남은 표현·검증 한계

- 판정 엔진, 사용자 사실 모델, 기한 계산기, 외부 법령 수집기는 이 범위에 없다.
- `application_mode`의 실제 효과 적용은 명세만 있으며 실행하지 않는다.
- 발췌문만으로 전체 공고 자격의 완전성, 정성 요건의 충족 기준, 법령 세부 제외 내용, 우대 점수·중복 적용은 확정할 수 없다.
- v1.1의 `external_reference.reference_text`는 원문 발췌 또는 참조 표식이며 외부 문서의 내용을 뜻하지 않는다.
