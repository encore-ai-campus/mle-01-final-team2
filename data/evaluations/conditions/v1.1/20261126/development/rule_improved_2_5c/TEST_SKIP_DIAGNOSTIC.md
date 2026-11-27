# 전체 테스트 skip 진단

진단일: 2026-11-26

## 현재 실행 결과

전체 회귀 실행에서 193개 테스트를 발견했고, 165개 통과, 28개 skip, 실패 0개였다. 기준선 고정 manifest는 127개 발견, 122개 통과, 5개 skip을 기록한다. 따라서 현재 skip 28개 중 기존 5개를 제외한 23개가 신규 skip이다.

## Skip된 테스트 그룹

| 기준 | 테스트 파일/그룹 | 건수 | 사유 | 추출·정규화 필수 검증인가? |
|---|---|---:|---|---|
| 기존 5개 | `tests/test_api.py::TestApi` | 5 | `fastapi`, `httpx`, `pydantic-settings` 미설치 | 아니오. API 선택 의존성 테스트 |
| 신규 23개 | `tests/test_agent.py`의 `TestRouter`, `TestAgent`, `TestGraphApi`, `TestGraphRag`, `TestChatApi` | 23 | `openai`, `langgraph`, `fastapi`, `httpx`, `pyyaml` 중 일부 미설치로 파일 내 `skipUnless(HAS_DEPS)` 적용 | 아니오. Agent/API/그래프 선택 의존성 테스트 |

신규 23개는 `tests/test_agent.py`에 있는 다음 테스트 메서드에 해당한다: `test_generate_and_stream_through_openai_api`, `test_falls_back_when_primary_fails`, `test_stream_falls_to_template_when_all_models_fail`, `test_circuit_breaker_opens_after_repeated_failures`, `test_structured_output_is_validated`, `test_load_router_skips_unconfigured_providers`, `test_verdict_comes_before_explanation_tokens`, `test_verdict_is_not_changed_by_model`, `test_pii_is_refused_without_search`, `test_injection_and_legal_are_refused`, `test_asks_when_profile_is_empty`, `test_profile_values_from_question`, `test_forbidden_sentence_is_never_shown`, `test_model_down_still_returns_rule_verdict`, `test_no_match_is_held`, `test_stale_data_banner`, `test_paths_and_definitions_come_from_graph`, `test_graph_down_falls_back_to_evaluator_path`, `test_without_graph_uses_evaluator_path`, `test_path_without_graph_is_503`, `test_path_returns_subgraph`, `test_concepts_fall_back_to_local_regions`, `test_chat_streams_sse_events`.

## 단계 영향

Skip은 추출기, 값 정규화, 출처 근거, 스키마, 평가기 및 신규 규칙 단위 테스트가 아니라 선택형 Agent/API 통합 테스트에 국한됐다. 신규 추출 규칙은 별도 25개 필수 합성 테스트를 직접 실행해 통과 여부를 확인했다. LLM/Agent 통합에 대한 보장은 제공하지 않으며 이번 작업은 외부 LLM을 호출하지 않았다.
