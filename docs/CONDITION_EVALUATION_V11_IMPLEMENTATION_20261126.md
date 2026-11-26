# 2-5A v1.1 의미 평가기 구현 결과 (2026-11-26)

## 구현

- 새 모듈: `tools/evaluate_condition_pipeline_v11.py`. 기존 v1.0의 수치·값 정규화, 최대 일대일 매칭, AST 정규화, Precision/Recall/F1 함수를 재사용한다. v1.0 평가기와 추출·논리 기준선은 수정하지 않았다.
- 설정: `configs/condition_evaluation_v11_development.json`.
- 호환성·분모·출력 정책: `docs/CONDITION_EVALUATION_V11_POLICY.md`.
- 합성 사례 20개: `tests/test_condition_evaluation_v11.py`. 실제 개발용 점수는 계산하지 않았다.

공통 필드 Exact/Partial과 strict TP, 출처·유형·속성별 결과, AST 구조, v1.1 확장 필드의 평가 가능·미지원·미확인 집계, 안전성 오류, 근거 span 진단을 분리했다. v1.0에 없는 구역 시점·예외 효과·복수 근거 등은 정답으로 인정하지 않고 미지원으로 보고한다. 근거 문구의 의미적 적절성은 자동 확정하지 않는다.

## 사전 점검 및 테스트

`python tools/evaluate_condition_pipeline_v11.py` 사전 점검 결과: `PASS`, FINALIZED 개발용 공고 30건·조건 116개, 점수 계산 `false`. 정답셋 manifest와 실제 JSONL, 기존 v1 예측 파일, 정규화·조건 입력·추출·논리 기준선 해시가 일치했다. 독립 평가용 20건은 공고 ID 비중복 확인에만 사용했다.

- 전체 `unittest discover`: 127개 실행, 122개 통과, 기존 선택적 API 의존 테스트 5개 건너뜀, 실패 0개.
- 기존 평가 테스트와 신규 합성 테스트: 33개 통과(기존 13개, 신규 20개).
- 조건 정답셋 SHA-256: `8450df33455daced4c5e95ca2a51ca262e88c53476c7a8a18e38b3164a52ee76`.
- 논리 정답셋 SHA-256: `e74adee73086cf1304ecee9d06f988c0f6af86c4149a9c7eb439e6a9509e08e3`.
- 기존 candidate_refs SHA-256: `5765dad05de72b8a44875353495e12224704da3f5b0067b955e1fb5e4b5c06e3`.

## 실행 준비

기본 명령은 사전 점검만 실행한다. 후속 단계에서 평가를 승인받아 실행할 때는 정책 문서의 `--execute --output ...` 명령을 사용한다. 실제 개발용 30건에 대한 예측·정답 매칭, 성능 점수, 판정 엔진은 이번 단계에서 수행하지 않았다.
