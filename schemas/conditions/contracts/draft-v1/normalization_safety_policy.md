# 정규화 안전 정책 초안 v1

이 폴더의 alias와 값 규칙은 **자동 정규화 후보**이지 운영 승인된 규칙이 아니다. 기존 attribute-normalization-v2 및 모든 strict 기준은 유지한다.

## 속성 관계

- EXACT_ALIAS: 기존 22개 카탈로그의 유일한 소문자 표기만 자동 후보로 둔다. canonical category 일치 및 의미·entity 검증은 정규화 후에도 수행한다.
- CONTEXT_DEPENDENT: EMPLOYMENT, REVENUE_FINANCIAL, residence, 각종 증빙·이력·질적요건·한글 레이블은 CSV의 필수 문맥을 확인해야 한다. 단어만으로 치환하지 않는다.
- DISTINCT_CONCEPT: 신청주체/사업체 유형, 개인주소/사업장, 대표자/팀원, 거주/증빙, 자격/서류 의무, 사업자등록 사건/상태, 채용/사업참여, IP권리/인증은 전역 치환 금지다.
- NEW_ATTRIBUTE_REQUIRED: 팀원 나이, 채용 요구, 일반 협력관계, 기술이전 가능성, 지식재산권 요건은 범용 개념 후보다. 이 단계에서 카탈로그에 추가하지 않는다.
- UNSUPPORTED_OR_UNRESOLVED: 정의가 불명확한 한국어 속성 등은 원본과 검수 사유를 남기고 자동 대응하지 않는다.

같은 source가 여러 관계를 가질 수 있다. 예를 들어 협력사업의 **명시적 참여**는 PROGRAM_PARTICIPATION 문맥 매핑 검토가 가능하지만 **일반 양자 협력 관계**는 새 개념이다. CSV 행은 조건부 대안이며 자동 rule 우선순위가 아니다. EXACT_ALIAS source만 유일 타깃을 가져야 한다.

## 값·단위·연산자

원문 값·단위·연산자·속성·category·근거·변환 규칙 ID/버전·상태를 함께 기록한다. 의미 검증·원문 근거·단위·날짜·중복·schema·논리 검증은 모두 유지한다. 정규화 성공이 검증 성공이나 판정 승인으로 이어지지 않는다.

년→YEAR, 개월→MONTH, 명→PERSON, %→PERCENT는 해당 측정 차원이 확인된 경우만 후보로 한다. 세→YEAR는 연령 문맥, 월→MONTH는 기간 문맥, 개→COUNT는 세는 대상 구분이 필요하다. 개월과 년, 달력 월과 일, 만 나이와 연 나이를 숫자만 보고 환산하지 않는다.

원/천원/만원/억원→KRW는 값과 함께 정확한 Decimal 배율을 곱한다. 이미 KRW로 환산된 값을 다시 곱하지 않도록 원본/정규화 상태를 구분한다. 통화 간 환산·환율 보정은 범위 밖이며 달러는 US 달러 명시가 필요하다. 음수·무한대·NaN 및 boolean의 숫자 취급을 금지하고, 개수는 정수·0이상 기준을 적용한다. 수익률과 매출비중 같은 서로 다른 비율도 구분한다.

minimum/maximum 또는 min/max의 키 이름은 경계 포함 여부를 증명하지 않는다. 양 경계와 inclusive flags, 기준시점·단위가 원문/입력 계약으로 확정된 때만 lower/upper로 변환한다. 누락된 경계를 포함=True로 만들지 않는다. BETWEEN은 lower≤upper이고 빈 구간이 아니어야 한다. 일방 경계에는 GT/GTE/LT/LTE를 사용한다.

EXISTS/NOT_EXISTS는 기존 스키마와 같이 value=null, value_type=UNKNOWN을 유지한다. EXISTS+true를 기계적으로 null로 바꾸면 원본 위반을 숨길 수 있다. 명시적 상태 boolean의 EQ true/false와 존재 연산자는 다른 표현이다. operator=null은 연산자가 확정되지 않은 상태이며 항상 참이 아니다. 문자열 UNKNOWN은 operator enum 밖이며 null과 자동 동치가 아니다. 재현 가능한 출력 위반은 기존 실패 기록을 유지한다.

IN/NOT_IN은 원문이 대안 집합임을 보장하는 비어 있지 않은 배열이다. 서로 독립적인 의무를 IN 배열로 묶거나 문자열을 쉼표로 쪼개 AND/OR를 바꾸지 않는다. 표준 범주 코드는 namespace·버전·공식 매핑 근거가 있어야 하며 기존 raw label도 보존한다.

## 저장 호환성과 승인 경계

`unit_state=NONE/UNKNOWN/KNOWN`, 지역 `NO_RESTRICTION` 및 신규 entity/subtype은 이 초안의 sidecar 의미 구분이다. 기존 condition JSON에 새 필드나 enum을 추가하지 않았다. 현재 unit:null만으로 의미가 구분되지 않는 경우 sidecar 기록과 검수 상태로 보존한다. 운영 저장을 도입하려면 별도 스키마 버전 검토가 필요하다.

CONTEXT_DEPENDENT는 source-field-mapping의 문맥 정보를 사용하더라도 해당 정보가 조건 증거인지 먼저 확인해야 한다. 관할기관 주소·현재 날짜·수집일·골든 값을 추론 근거로 사용하지 않는다. 기준일, 평가/충족 시점, 기간 및 예외가 불명확하면 값을 채우지 않는다.

## 검증의 범위

validate_contract.py는 운영 validator가 아닌 합성 설계 검증용 oracle이다. JSON 구조, alias 충돌, enum 조합, 역할 경계, 단위/범위/논리의 보존을 검사하며 골든셋을 import하거나 파싱하지 않는다. 이 테스트 통과는 실제 추출 품질이나 정확도 개선의 실측 결과가 아니다.
