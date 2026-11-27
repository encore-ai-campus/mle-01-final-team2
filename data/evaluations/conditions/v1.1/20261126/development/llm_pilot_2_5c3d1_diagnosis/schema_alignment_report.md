# P12 표현·평가 계약 진단

대상은 DEVELOPMENT 10공고, 정답 62조건이다. 저장된 평가 함수에 같은 입력을 전달해 규칙 v1/E, LLM 검증 전/후의 summary 전체가 일치함을 확인했다. 기존 평가 CLI는 manifest를 갱신하므로 실행하지 않았다. 독립 평가 20건은 읽지 않았다.

## Strict 완전 일치 계약

`evaluate_condition_pipeline_v11.COMMON_FIELDS`는 condition_type, category, field, operator, value, unit이다. 예측 category는 category_id를 사용한다. 추가로 evidence_exact가 source_field, 시작·종료 span, 정규화된 근거 문자열 전체 일치를 요구한다. 문자열 공백/Unicode·숫자와 IN 배열 순서 정규화는 있으나 지역 별칭, 통화 배율, 단위 번역, 개념별 속성 매핑은 없다. 부분 일치는 같은 field와 근거 중첩/동일 인용으로 연결하며 TP에 포함되지 않는다. 부분 일치는 의미 동등성 판정이 아니다.

value_type, applicability_scope, temporal_constraint, evaluation_phase, fulfillment_phase, requirement_kind는 조건 micro F1의 완전 일치 필드가 아니다. value_type은 추출 검증에서 사용되고 다른 항목은 extended 진단에 사용된다. 따라서 날짜·유지 조건을 잘 보존해도 본 조건 F1은 상승하지 않을 수 있다. 이는 현재 명시된 평가 계약이며 이번에 변경하지 않았다.

## 원본–검증 전–검증 후의 차이

검증 전 58제안은 원본 field/value/operator/unit을 기존 prevalidation_predictions에 전달한다. 이 adapter는 대문자 표준 속성 정규화를 하지 않고, 첫 evidence_quote를 원문에서 검색해 유일한 위치를 선택한다. 178507의 스키마 위반 제안 10개도 원본 그대로 포함된다.

검증 후 32후보는 속성 정규화 v2, 후보 검증·중복 처리·스키마 검증을 거친 레코드다. 178507은 0후보다. 작은따옴표/코드 문자열 표현과 관계없이 비교 데이터는 UTF-8 JSON 값이다. 전후 점수는 표현 정규화와 후보 필터링 효과가 함께 포함되어 있으며 순수한 제거 효과 실험이 아니다. 대문자 정규화 때문에 부분 일치가 3→16으로 늘어날 수 있다.

## 확인된 표현 불일치

| 계층 | 실제 사례 | 진단 |
|---|---|---|
| field 의미 | 사회적기업 등 8개를 APPLICANT_TYPE, 정답은 BUSINESS_TYPE | 대소문자 문제가 아닌 속성 분류 계약 차이. 두 속성을 전역 alias로 합치면 안 됨 |
| field 개념 | 영리기업→BUSINESS_TYPE, 정답 FOR_PROFIT_STATUS; 우선지원대상기업→BUSINESS_TYPE, 정답 SUPPORTING_COMPANY_STATUS | 값의 의미에 맞는 카탈로그 구분 필요 |
| 카탈로그 범위 | HIRE_STATUS, IP_RIGHT_*, COMPLIANCE_*, SOGANG_*, REVENUE 등 골든 개념과 22개 추출 카탈로그 차이 | 평가기는 골든 속성을 보유하지만 LLM 허용 계약은 더 좁다. 골든셋이 잘못됐다고 확정할 근거는 아님 |
| 원본 field | 기업 유형/사업자 등록/지식재산권, hiring_target, team_member_age 등 | 검증에서 미지원 속성 탈락. 한국어 JSON 손상 아님 |
| 값 | 대구시↔대구광역시, 「상법」상 회사↔상법상 회사 | 일부 표기 정규화 후보. 도내→경기도는 문맥 해석이므로 단순 문자열 alias로 금지 |
| 단위·배율 | 년↔YEAR, %↔PERCENT, 명↔PERSON, 3억원↔300000000 KRW | 단위와 값 배율을 함께 검증해야 함 |
| 범위 값 | minimum/maximum, min/max, 리스트, lower/upper 객체 혼재 | 기존 BETWEEN 검증 및 평가 normalize_value가 이 표현들을 자동 통일하지 않음 |
| 원문 인용 | 정답은 최소 구절, LLM은 복수 조건이 들어간 긴 문장 | 16부분 일치 중 14건에 evidence 차이. 사실 근거 존재와 strict span 일치는 별개 |
| 분해 | 지식재산권 1제안↔국가·유효성·종류·소유 4정답; 이행계획서에 의무내용/개수 결합 | 단순 alias만으로 1:다 조건을 복구할 수 없음 |
| 유형 | 179386의 바이오·헬스/AI·빅데이터를 PREFERENCE로 생성, 정답 ELIGIBILITY | 모델의 유형/분기 해석 오류이며 정규화 문제가 아님 |

## 178507 및 177447

178507은 operator=UNKNOWN 한 오류로 응답 전체가 거절되어 정답 10개가 FN이다. 개별 제안에는 LTE 7↔LT 7, 조건 IN 묶음, EXISTS+BOOLEAN, 단위 years 등 추가 차이도 존재한다. enum 한 항목만 수정하면 10 TP가 생긴다고 해석할 수 없다. 원본은 수정하지 않았다.

177447은 대표자 나이 BETWEEN minimum/maximum 구조 1건, 나머지 미지원 field 4건으로 모두 탈락했다. 정답은 대표자와 팀원 나이를 한 조건으로 묶고 있어 구조 정규화 이후에도 역할·분해 차이를 검토해야 한다. 관련 증빙서류와 거주/병역 증빙의 대응은 확정하기 어려워 FN 1건을 OTHER_OR_UNRESOLVED로 남겼다.

## 평가 연동 결함과 영향 범위

조건 F1에 대한 구현 결함은 이번 재현에서 확인되지 않았다. strict span 일치와 빈 FIELD_ALIASES는 현재 계약이다. 검증 전 adapter가 v1.1 extended 필드 대부분을 전달하지 않는 제한은 있다. 따라서 전후 extended 성능을 동일 입력 표현으로 비교해서는 안 된다.

논리 평가는 `_roots()`가 condition_sets.*.logical_roots를 사용한다. 이 레코드는 평탄한 조건 참조지만 실제 LOGICAL_GROUP은 최상위 logic_sections.root에 저장된다. 예외/미해결 관계는 별도 logic_proposals에 보존되나 평가 adapter는 notice_condition_sets만 전달한다. 이 때문에 예측 논리 그룹이 0개로 측정되고 exception_effects/unresolved_relation_semantics는 UNSUPPORTED_V1_0으로 표시된다. 이 문제는 논리/AST 지표에 영향을 주며 조건 F1 2.13%의 직접 원인은 아니다. 이번에는 수정하거나 점수를 다시 보정하지 않았다.

FN/FP의 진단 대응은 CSV에 명시한 수동 분석용 연결이다. 골든셋에서 속성·값을 역보정하는 추출 규칙으로 사용하지 않았다.
