# 차기 프롬프트 변경 보고서

정책 버전: condition-next-extraction-policy-v1. 별도 실험용 구현이며 운영 프롬프트·추출기는 그대로 유지한다. P0는 기존 system_prompt의 바이트 동일 복사본이다. P1/P2/P3/P4는 새 wire 계약을 공유하며 실제 모델 호출이나 성능 평가를 수행하지 않았다.

## 기존 문제와 개선 근거

| 기존 계약 | 관측된 문제와 영향 | 차기 정책 |
|---|---|---|
| field는 nullable string, category는 대문자 pattern | 이름 목록이 있어도 한글 field나 hiring_target 등 임의 field 생성 가능 | 표준 조건의 field/category는 기존22 enum, 내부에서 일치 확인 |
| 카탈로그 이름만 프롬프트에 열거 | 신청주체/사업체, 영리 여부, 등록 사건/상태 혼동 | 22개 의미·entity·operator/type/unit·예시·반례를 기존 draft에서 삽입 |
| 일반적인 UNKNOWN 사용 지시 | operator UNKNOWN으로 응답 전체 중간 스키마 거절 | operator의 UNKNOWN 금지. 표준 조건은 허용 enum, 미해결 큐는 null |
| value={} | EXISTS+boolean, 범위 키·타입 차이 | typed scalar/array/range union, 내부 연산자·value_type 교차 검증 |
| 단위 규칙 설명 부족 | 년/YEAR, %/PERCENT 때문에 strict 불일치 | 표준 단위 요청, 실험 경로에서만 검증된 N1 안전 변환 옵션 |
| BETWEEN 구조·경계 지시 부족 | minimum/maximum, 포함 여부 불명확 | lower/upper.value/inclusive를 명시, 불명확하면 큐로 보류 |
| 분해 기준·근거 범위 추상적 | 여러 술어가 긴 value/문장에 합쳐짐 | 주체·속성·값·시점·scope별 원자, 최소 충분 주 근거 및 보조 근거 |
| 평면 logic_sections 인덱스 | 공통 조건/대체 경로/예외의 중첩이 불충분 | group_id/children/root_ref로 명시적 그래프. 원문 없는 중첩 금지 |
| 미지원 개념의 표현 경로 부족 | 유사한 속성으로 강제 매핑 또는 전체 거절 | unresolved_conditions에 원문·근거·제안명·주체·유형·사유·검수 상태 보존 |

근거는 3D-1 진단과 3D-2C/3D-3 보고서다. 해당 실패의 정답 값·span을 프롬프트 예시나 보정 규칙으로 복사하지 않았다. 합성 사례는 울산 사업장/연구기관 또는 업력4년/증빙/환경산업 우대 등 별도 문장이다.

## 프롬프트 10개 영역

역할, 원문 근거, 속성 의미, 연산자·값, 조건 유형, 원자 분해, 인용, 그룹·예외, 불확실성, 출력 형식으로 구성했다. P4_prompt.txt가 통합 정책이다. instructions의 실제 모델 효과는 미측정이다. Python 검증은 형식·교차 필드·근거 존재·참조를 검사하지만 모든 의미/최소 충분 구절의 정답성을 증명하지 않는다.

미지원 신규 후보5개는 여전히 미승인이다. 제안 속성 문자열은 발견 기록에만 허용하며 표준 conditions에 새 속성을 넣지 못한다. NO_CONDITIONS_FOUND는 발견되지 않았다는 뜻이며 완전한 조건 부재 확인이 아니다. 명시적 지역 무제한은 EXPLICIT_NO_RESTRICTION 큐 항목으로 보존하며 긍정적 지역조건·지역 UNKNOWN으로 바꾸지 않는다.

## 크기 증가

P0는 6,503문자/6,503 UTF-8 bytes다. P1/P2의 순수 정책 prompt는 11,396문자/12,732bytes, P3/P4는 12,993문자/14,329bytes다. P4는 P0 대비 +6,490문자/+7,826bytes다. Provider schema compact JSON은 9,051bytes다.

JSON mode P1/P3에는 출력 schema를 system 메시지에 덧붙인다. Structured P2/P4는 response_format으로 전달한다. 따라서 순수 prompt 증가와 schema 포함 요청 크기는 구분해야 한다. P4의 prompt+schema는 23,380bytes다. tiktoken이 설치돼 있지 않아 모델 토큰을 정확히 측정하지 않았다. 2–6 UTF-8 bytes/token 가정의 계획 범위는 P0 약1,084–3,252, P4 약3,897–11,690 tokens이며 서버 프레이밍·실제 tokenizer의 보장된 범위가 아니다. 상세는 prompt_size_and_token_estimate.json을 참조한다.

같은 byte/token 가정을 양쪽에 적용한 증가량은 순수 정책 prompt 약1,305–3,913tokens, 새 schema payload까지 포함한 요청 표현 약2,813–8,438tokens다. 실제 모델 tokenizer로 측정한 차이가 아니며 공고 본문은 이 증가량에 포함하지 않았다.

## ABI/기준선

새 root/그래프/미해결 큐는 기존 중간 JSON의 drop-in 교체가 아니다. 표준 condition 객체만 기존 형식으로 투영하여 검증하고 신규 그래프는 별도 브리지로 처리한다. 기존 P12 스키마·strict evaluator·N1 구현을 수정하지 않았다. 새 프롬프트로 기존 응답을 재해석하거나 기존 점수를 보정하지 않았다.
