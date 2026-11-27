# Adapter 후속 적용 권고

평가 전용 condition-logic-evaluation-adapter-v1을 후속 평가 경로 후보로 추천한다. 기존 strict evaluator의 _canonical/그룹·edge signature/조건 매칭 기준은 그대로 두고, 실제 저장된 최상위 root를 전달한다. 운영 추출기와 기존 결과를 자동 변경하지 않았다.

채택 근거는 점수 상승이 아니라 실제 구조의 누락 없는 전달, 원본·미해결·예외 보존, 무결성 검사, 정확한 합성 AST의 기대 점수, 실제 출력 반복 재현성이다. P12는 10그룹·43관계를 생성했지만 기존 root 선택에서 그룹·edge가 0개로 인식됐다. 개선 후 이들이 정상 인식돼 FP로 집계되는 것이 정확한 진단이다.

## 후속 작업 우선순위

1. 조건 의미 계약과 분해 품질을 먼저 개선한다. L1/L2에서 정답 그룹24 중23에 연결되지 않은 조건이 있다. 그룹/edge signature는 모든 자손 identity를 포함하므로 단일 조건 불일치가 그룹 전체 실패로 확대된다.
2. 저장된 평면 AND/OR, 대안 분기와 공통 조건, 예외의 정확한 중첩 생성을 별도 실험으로 검토한다. 이번 adapter는 정답을 보고 재중첩하지 않았으며 실제 nested group0이라는 사실을 유지한다.
3. 예외 효과·범위, unresolved relation 의미, phase/completeness correctness는 별도의 버전된 v1.1 평가 계약을 합의한 뒤 구현한다. 보존 중인 객체를 근거로 성공·실패 점수를 먼저 만들지 않는다.

## 비교 해석

L1과 L2의 논리 점수가 같은 것은 단위 정규화가 무효라는 뜻이 아니다. 기존 evaluator는 partial condition pair도 id_map에 넣으므로 N1의 신규 exact 두 개가 L1에서도 연결돼 있었다. 조건 F1은 2.1277→6.3830%로 다르고 adapter는 그 점수를 변경하지 않았다.

규칙 v1/E의 구조 비교는 가능하다. v1은 group exact1/24·edgeTP2, E는 group exact0/24·edgeTP0이다. 조건 F1이 더 높은 E가 논리도 더 좋다고 가정하지 않는다. 공고 AST exact는 양쪽 모두0/10이며, 원래 rule AST의 설계/그룹 경계를 그대로 평가한 결과다. v1.1 예외/시점 의미는 비교 제한을 명시한다.

## 범위와 안전장치

없는 조건/그룹, 중복 그룹 ID·중복 child, 순환, orphan, 부모-자식 구조 누락, unresolved/exception target 누락은 error로 차단한다. 공유 조건이 서로 다른 그룹에 나타나는 것은 허용하며 동일 그룹에서의 중복 child와 구분한다. valid ID 변경은 이미 재생성된 source artifact의 참조를 확인할 뿐 임의로 추정 연결하지 않는다.

전원 탈락 그룹은 원래 제안/인덱스/미해결 상태만 보존하고 실행 가능한 group을 만들지 않는다. 일부만 남은 기존 UNRESOLVED 그룹도 completeness·예외 적용 차단을 그대로 보존한다. 평가 입력의 decision_eligible은 항상 false다.

LLM/규칙 코드, 모델, 프롬프트, N1 정책, 카탈로그, strict 기준, 골든셋, DB는 수정하지 않았다. 독립 평가20건은 사용하지 않았고 실제 API 호출·예산 변경·커밋·푸시는 없다.
