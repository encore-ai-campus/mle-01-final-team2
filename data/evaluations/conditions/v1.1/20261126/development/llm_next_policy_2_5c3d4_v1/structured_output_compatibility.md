# Structured Outputs 호환성 조사

확인일: 2026-11-27. 실제 API 요청 없이 공식 자료·설치 코드·SDK MockTransport로 조사했다.

## 공식 근거

- [Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs): JSON mode는 JSON 문법을, Structured Outputs는 지원되는 schema의 형식을 제약한다. root는 object, 모든 property는 required, object의 additionalProperties=false가 필요하다. nullable union으로 선택적 의미를 표현할 수 있다. allOf/if/then/else/not 등 일부 조합은 지원하지 않아 내부 검증과 분리해야 한다. refusal·incomplete/API 오류 및 업무 의미 검증은 별도 처리해야 한다.
- [GPT-5.6 Luna model](https://developers.openai.com/api/docs/models/gpt-5.6-luna): Structured Outputs 지원을 명시한다. 문서상 모델 기능과 현재 계정의 실제 접근 권한은 별개다.
- [Chat Completions reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create): response_format을 통한 JSON 형식 설정 경로를 사용한다.

본 구현의 Provider schema는 이 지원 부분집합에 맞춰 보수적으로 작성했고 추가 cross-field 제약은 internal schema와 Python에서 검사한다. 문서상 지원을 확인했지만 **실제 서버가 이 구체적 schema를 수락했는지는 미검증**이다.

## 로컬 SDK 근거

openai 2.54.0, httpx 0.28.1, jsonschema 4.26.0이다. AsyncCompletions.create의 response_format 인자와 설치된 SDK 타입을 확인했다. 실제 AsyncOpenAI가 json_schema/name/strict/schema 및 json_object 요청 body를 MockTransport로 직렬화하는 것을 테스트했다. SDK max_retries=0, reasoning_effort=low, max_completion_tokens=8192, timeout180은 기존 설정과 같다.

NextPolicyClient는 offline-test-key와 MockTransport만 허용한다. 실제 network transport를 전달하면 생성 단계에서 차단된다. 실제 자격 증명이나 .env를 읽지 않으며 live CLI와 예산 장부를 만들지 않았다. 실서비스 연결에는 별도 승인된 실행기와 공통 요청 잠금/장부/계보 관리가 필요하다.

## 호환성 판단

| 항목 | 확인 수준 |
|---|---|
| 모델의 Structured Outputs 기능 | 공식 문서상 지원 |
| SDK response_format 직렬화 | 실제 SDK + MockTransport 확인 |
| Provider schema 구조 | 로컬 JSON Schema 문법 및 제한 키워드/required/object 검사 통과 |
| 필드·값·날짜·근거·참조 | 내부 schema와 기존 Python validator 연결 확인 |
| 서버의 schema 수락/계정 접근 | 실제 API 미호출로 미확인 |
| 모델이 올바른 의미·최소 span·중첩을 생성하는지 | 미측정 |

응답이 stop이 아니거나 refusal이면 변환하지 않는다. JSON mode에서도 같은 내부 검증을 적용하며 포맷을 잘못 생성한 응답을 임의 수정하지 않는다. 178507의 기존 UNKNOWN 응답을 이 스키마에 맞춰 고치거나 재처리하지 않았다.
