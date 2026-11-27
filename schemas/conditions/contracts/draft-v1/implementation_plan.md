# 후속 구현 계획

현재 상태: 계약 초안 및 합성 검증만 완료. 운영 추출기·카탈로그·스키마·adapter·평가기·프롬프트를 수정하지 않았으며 실제 응답을 재처리하거나 성능 평가하지 않았다. 요청 예산은 기존 13/13, 잔여 0이다.

## 단계별 승인·범위

| 개선 항목 | 구현 분류 | 기존 응답 재사용 | 선행 조건 |
|---|---|---|---|
| 22개 case-only 표기 | 즉시 오프라인 정규화 가능 | 가능; 이미 v2와 중복되는 범위가 많음 | 유일 매치·category·entity·ambiguity 검증 유지. 신규 성능 효과를 주장하지 않음 |
| YEAR/MONTH/PERCENT/PERSON·KRW 배율 | 즉시 오프라인 정규화 가능 | 명시적 단위/숫자에 한정 | 정확한 Decimal, 차원/배율/원본 보존, 중복환산 방지 |
| BETWEEN 키 변환 | 문맥 기반 검증 구현 필요 | 경계 flags와 원문이 확정된 응답만 | 양 경계·포함 여부가 없는 자료는 검수; 기본값 금지 |
| 신청주체/사업체/주소/사업장/본사·지점 | 문맥 기반 검증 구현 필요 + 사람 검수 | 원문 근거가 충분한 경우만 | entity·scope 규칙 및 source-field 증거 수준 확인 |
| EMPLOYMENT, REVENUE_FINANCIAL, 한글 labels | 문맥 기반 검증 구현 필요 | 원문 의미가 확정된 경우만 | 전역 alias 금지, 단계별 catalog semantic review |
| team_member_age / hiring / 협력관계 / 기술이전 가능 / IP권리 | 신규 카탈로그 승인 필요 + 사람 검수 | 현재는 보류/탈락 유지 | 출처 독립 의미 정의, 기존 속성과 구별 근거, 값·논리·시간 계약 확정 |
| unit 상태·지역 무제한·entity role의 새 저장 필드 | 신규 스키마 버전 필요 | 현재는 sidecar만 | 기존 구조와 충돌 없는 버전·migration 설계 |
| UNKNOWN operator와 속성 설명·JSON 구조 강제 | 프롬프트 개선 필요 | 기존 위반 응답 임의수정 불가 | 차기 실험의 프롬프트/생성 계약 버전 분리; 새 API 별도 승인 필요 |
| 조건 분해·최소 충분 근거·부정/예외 | 프롬프트 개선 필요 + 사람 검수 | 단순 정규화 범위 밖 | 원문 기반 논리 설계; 골든 span 직접 보정 금지 |
| 논리 평가 adapter 그룹·예외·관계 | 별도 기술 부채 | 오프라인 연결 검증 가능 | 조건 F1 작업과 분리, evaluator 버전·지표 계보 보존 |

## 권장 최소 오프라인 구현 순서

1. 계약의 용어·역할 경계에 대한 사람 검토를 완료하고 **운영 import 없는** 공통 registry 모듈을 별도 버전으로 만든다. 초기에는 기존22와 case-only만 구현한다. category mismatch와 모호성 보류를 유지한다.
2. 값/단위의 안전 부분집합(명시적 년/개월/%/명, KRW 배율)을 standalone 후보 변환기로 구현한다. 원본 및 전후 value/unit 해시·rule ID·근거를 보존하며 추출·근거·스키마·논리 검사 전체를 재사용한다. 금액은 원문 단위와 숫자를 함께 확인하고 이미 변환된 상태는 재변환하지 않는다.
3. 기존 원본 응답을 새 출력 경로에서만 재처리한다. 단위/값·속성 변환 성공과 후보 검증 성공을 구분하고 스키마 위반 응답 및 의미 보류를 그대로 보존한다. BEFORE/AFTER 추출기·normalizer·prompt·입력·평가기 해시를 새 manifest에 기록한다. 이번 단계에서는 이 재처리·채점을 하지 않았다.

위 최소 범위에서 제외할 것: BUSINESS_TYPE/APPLICANT_TYPE 전역 치환, 한국어 임의 번역, 도내 지명 채우기, 대표자→팀원 확장, 증빙→자격 사실 변환, UNKNOWN→null 수정, missing inclusive=True, 조건 분해 재생성, 골든에 맞춘 값/span 보정, 신규 카탈로그 운영 반영.

## 검증·재현 명령

```powershell
.\.venv\Scripts\python.exe schemas/conditions/contracts/draft-v1/validate_contract.py
```

build_contract.py는 신규 폴더에 초안을 생성한 이력용 도구다. 이미 존재하는 JSON/CSV를 덮어쓰지 않도록 설계돼 있다. contract_validation_report.json은 합성 사례 테스트 결과만 담는다. 실패 사례로 entity mismatch, category mismatch, UNKNOWN operator, 경계 누락, 빈 범위, 빈 IN 배열, EXISTS+boolean, 잘못된 단위 등을 거부하는 것을 확인한다.

## 기준선 관리

고정 10공고/62정답, 규칙 v1 F1 13.64%, E 14.12%, LLM 전 1.67%·후 2.13%, 후 TP1/FP31/FN61을 변경하지 않는다. 이는 기존 결과를 기록한 값이며 계약 테스트로 얻은 새 평가 점수가 아니다. manifest는 기존 P12·개발용 골든셋 파일을 해시로만 확인하고 독립 평가 20건을 읽지 않는다. 골든 레코드는 계약 생성·합성 검증의 입력으로 사용하지 않는다. 향후 효과는 새 버전 오프라인 실측 이후에만 보고한다.
