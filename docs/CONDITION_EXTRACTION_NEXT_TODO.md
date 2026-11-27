# 조건 추출 파이프라인 후속 작업 목록

작성 기준일: 2026-11-27. P4의 기존 응답 3건, 실행 장부, 입력 evidence, 정책/bridge 코드를 대조한 순서다. API 실행은 아직 진행하지 않는다.

## 원칙

- P4 run `llm_pilot_2_5c3d5a_p4`와 기존 장부는 부모 기록으로 보존한다.
- raw P4 응답 3건, 첫 2건의 산출물, 119490의 차단 기록을 덮어쓰지 않는다.
- 수정 테스트 및 offline replay는 임시 디렉터리 또는 새 파생 run ID에서 진행한다.
- 원본 응답 수정, first evidence span 임의 선택, 스키마/근거 검사 완화, 골든셋 기반 보정은 금지한다.
- 현재 remaining 실행기를 수정·검증하기 전에는 7회 잔여 예산을 사용하지 않는다.

## P0 — 잔여 실행 전에 완료

| 순서 | 작업 | 완료 조건 | 검증 / 보존 |
|---:|---|---|---|
| 1 | P4 source_field와 trusted provenance를 분리 | validated extraction input의 evidence path에서 source_field/provenance를 안전하게 결정한다. 미결정이면 보류. 모델 field/value는 별도로 보존한다. | 117168·118182 raw 응답 오프라인 replay에서 3/10 후보 흐름을 확인하되 후보 내용에 대한 기존 전체 검증을 유지. raw hash 불변. 별도 lineage/fingerprint |
| 2 | 표준 및 unresolved evidence 다중 위치 처리 | 인용 0개/1개/복수개를 구별하고 모든 span·context를 기록한다. 복수면 후보 단위 review 상태. | 119490을 offline replay. 표준 EMPLOYEE_COUNT와 unresolved quotes 모두 점검. 첫 등장 자동 선택 없음, 그룹과 unresolved refs 보존 |
| 3 | P4 resume target 산출 | 요청 시도·응답 존재 ID를 ledger와 artifacts에서 읽어 실제 미실행 notice만 deterministic하게 선택한다. | 이미 시도한 ordinal 1–3을 재선택하지 않고 미실행 7개만 정렬 선택. 중복/동시 claim 차단 |
| 4 | 파생 실행 계보 및 fingerprint 고정 | 새 adapter/policy/runner hashes와 기존 응답·입력·prompt/schema/evaluator hash를 파생 manifest에 기록한다. 기존 P4 fingerprint 변경으로 가장하지 않는다. | CLI 사전검사에서 P4 부모, request ledger hash, run ID claim 및 입력 ID 순서 검증. mismatch는 block |
| 5 | P4 장부 승계·예산 점검 | 부모 P4 used3/limit10/remaining7을 보존·승계하고 추가 요청 없이 승인 상태를 확인한다. | ordinal 4–10만 사용. 실패 요청도 소비 처리. 신규 예산 생성/승인 없이 기존 승인 맥락과 lineage 확인 |
| 6 | 실제 CLI offline test | CLI 진입부터 fingerprint → remaining selection → 임시 ledger reservation → mock response → 검증/Gate → close까지 실행한다. | Test 전용 임시 ledger/path. mock이 real API로 fallback하지 않음. 실제 parent ledger의 테스트 예약 0건 |

각 P0 완료 전까지는 live API 호출하지 않는다. 수정 후 테스트에서 117168/118182 후보가 3개/10개가 나오는지 강제하지 않고, 기존 validator 결과를 기록한다. 근거 위치 불명확한 후보는 계속 미확정이다.

## P1 — P4 실행 및 오프라인 평가

1. P0의 fingerprint/claim/preflight가 통과하고 기존의 별도 P4 10회 승인과 7회 remaining이 증명되면, **기존 응답이 있는 공고를 건너뛰고** 실제 미실행 7건만 순차 실행한다. 자동 retry·병렬 호출을 사용하지 않는다.
2. 각 응답마다 raw hash, request ordinal, response state, intermediate schema, 검증/hold/reject counts, technical Gate를 기록한다. 응답이 schema violation이면 원본 후보를 임의 부분 복구하지 않는다.
3. 10건 응답/평가 eligibility가 충족되면 동일 P4 원본 응답으로 `P4 without N1` 및 `P4 with N1`을 분리 재처리한다. 원본 P4 결과 및 P12 비교 기준은 보존한다.
4. 기존 strict condition evaluator와 논리 adapter를 사용해 10건 평가. TP/FP/FN, precision/recall/F1, partial, source/type breakdown, group/edge/AST, unresolved/unsupported, zero prediction, evaluation inclusion을 모두 보고한다.
5. 검수 queue 117168/118182, P4와 P12 표현 차이, source_field 파생, 중복 근거 및 스키마 실패를 분류한다. P12 accepted 후보를 정답으로 사용하지 않는다.
6. P4 결과는 같은 개발용 10건의 실험 결과로만 보고하고 독립 평가 성능으로 기술하지 않는다.

## P2 — 품질 개선 이후 별도 승인

- 30건 개발용 전체 평가를 pilot10 평가와 분리 수행.
- 20건 독립 검증은 개발 중 접근/튜닝 금지; 평가 계획 승인과 입력 고정 이후 최종 검증 단계에서만 진행.
- 규칙 E + P4 하이브리드 후보 설계 및 별도 fingerprint 실험. 두 추출 정책의 raw output을 합치지 않고 source lineage를 보존한다.
- 한글 field/category 의미 일치, 미지원 속성, range/unit/operator, applicant type/business type, residence/evidence, logical exceptions를 명시적으로 사람 검수한다.
- 공고 전체 조건 추출, 판정 엔진/DB 연동은 실험 결과와 인간 검수 정책이 승인된 후 별도 범위로 수행한다.

## P4 완료 기준

- 기존 P4 장부/응답/manifest의 hash와 부모 상태가 그대로 확인됨.
- 10개 고정 ID 전부가 응답 또는 명시적 추적 가능한 평가 가능한 실패 상태에 속함. 미실행/추적불가 오류 없음.
- 응답별 technical Gate와 추출 품질을 별도로 보고. 유효 후보 0건, 검수 보류, 재현 가능한 model schema error를 성공 추출로 간주하지 않음.
- 근거 span·후보 ID·논리 참조 무결성, v1.1 schema, strict evaluator 입력 검사 통과. unresolved는 unresolved로 남고 `decision_eligible=false`.
- API response 성공, 기술적 처리 성공, evaluation inclusion, 지원 자격 판정 승인을 별도 지표로 보고.
- N1/without N1, P12, rules v1/E가 명시적 동일 평가 계약으로 비교되고 성능 수치를 독립 성능처럼 표현하지 않음.

## 사용할 주요 자료

- P4 runner/policy/legacy converter: `tools/run_condition_llm_p4_pilot.py`, `tools/condition_llm_next_policy.py`, `tools/extract_condition_candidates_llm.py`
- P4 장부/raw response: `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3d5a_p4/`
- 고정 input: `data/condition_inputs/v2/20261126/extraction_inputs.jsonl`
- goldset(manual review only): `data/goldsets/conditions/v1.1/20261126/final30/development/`
- evaluator: `tools/evaluate_condition_pipeline_v11.py`; policy: `docs/CONDITION_EVALUATION_V11_POLICY.md`
- 세부 장애/오프라인 counterfactual: [Troubleshooting](CONDITION_EXTRACTION_TROUBLESHOOTING.md)
- 전체 계보·성능표·환경·Git 공유 분류: [Handover](CONDITION_EXTRACTION_HANDOVER.md)

## 명령 사용 주의

현재 코드에서 안전한 P4 확인은 다음과 같다.

```powershell
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --preflight
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --offline-self-test
```

현재 `--run-remaining --authorize-api`는 attempted ordinal을 다시 고를 수 있어 수정 전 실행하지 않는다. 후속 담당자는 runner와 `--help`를 다시 확인하고, 수정된 파생 CLI에만 API 전 단계까지 offline 검증된 실제 미실행 대상 명령을 문서화해야 한다. API 승인/사용량은 기존 장부와 별도로 재설정하지 않는다.
