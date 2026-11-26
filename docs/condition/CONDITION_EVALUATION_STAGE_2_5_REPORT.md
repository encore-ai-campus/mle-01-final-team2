# 2-5단계 조건 추출·논리 구조 평가기 구현 결과

## 결과

평가기와 preflight 차단 로직을 구현하고 합성 자료로 검증했다. 현재 2-4단계 검수 완료 정답은 0건이므로 실제 공고 성능 평가는 실행하지 않았다. 실제 정답이 비어 있거나 미검수면 시스템은 점수를 `0` 또는 `1`로 대체하지 않고 `NOT_COMPUTED`를 반환한다.

## 구현 파일

- `tools/evaluate_condition_pipeline.py`: 사전검증, 조건 매칭, 지표 산출, 논리 canonical 비교, 실패 분석, JSONL/JSON/Markdown 보고서 생성
- `tests/test_condition_evaluation.py`: 합성 알고리즘, 차단 동작, one-to-one, AST, 예외/우대 및 분할 안전성 검증
- `sample_data/conditions/condition-evaluation-synthetic-cases-v1.json`: 사람 검수 정답과 분리된 합성 기대값 사례
- `docs/condition/CONDITION_EVALUATION_PROGRAM_V1.md`: 평가 방법·명령·지표·한계 명세
- `data/evaluations/conditions/v1/20261125/development/`: 정답 부재로 차단된 preflight 결과

2-2 추출기, 2-3 논리 변환기, 2-4 골드셋 스키마와 평가 입력 형식은 재사용했다. 기존 2-2/2-3 기준선 파일은 변경하지 않았다. 개발용과 평가용 원문 ID를 교차 검사하고, 다른 split의 예측 ID가 섞이면 평가를 차단한다. 평가용 예측 파일은 생성하거나 읽지 않았다.

## 알고리즘 검증

- 의미 조건은 `notice_id` 내부 최대 일대일 매칭을 사용한다. 정답 하나를 여러 예측이 중복 정답 처리할 수 없다.
- FULL 매칭만 TP다. PARTIAL은 별도 진단으로 남고 FP/FN에도 반영된다.
- 텍스트/숫자 정규화, 연산자·기준값·단위·적용 대상·근거 비교를 분리한다. 미승인 단위 변환이나 임의 의미 동의어를 적용하지 않는다.
- Micro와 notice-macro, 출처·조건 유형·카테고리별 지표, 공고별 누락률 및 속성·근거 정확도를 출력한다.
- 논리 AST는 AND/OR 자식 순서와 동일 연산자 결합법칙 차이를 정규화한다. AND/OR 교체와 NOT 범위 변경은 불일치로 남긴다.
- 논리 relation edge, 그룹 및 공고 단위 exact, 중첩 구조, 예외 대상, 우대 혜택 연결, 미확정 과잉 사용을 따로 계산한다.
- 추출 성능과 `logic_oracle` 모드의 gold 조건 제공 논리 성능을 분리한다.

합성 통합 사례에서는 정답 1건에 대한 정확한 예측이 TP=1, FP=0, FN=0으로 계산되고 공고 단위 논리 구조 exact가 통과했다. 합성 케이스에는 누락, 과잉, 중복, 속성 mismatch, 논리 연산자 교체, 순서 정규화, NOT scope, 예외 대상, 미확정, 빈 정답 및 미검수 정답 차단이 포함된다. 이 결과는 실제 공고 성능이 아니다.

## 실행 결과 및 실제 평가 선행 조건

신규 평가 테스트 13개와 기존 54개, 총 67개 테스트를 모두 실행해 통과했다. 현재 개발·평가 검수 입력은 각각 미검수 30건과 20건이며 ingested gold 레코드는 0건이다. 실제 평가는 사람 검수 완료 상태, 원문 span과 gold ID 검증, 개발·평가 분리, 기준선 해시 일치, 고정된 prediction 파일과 코드 버전이 확인된 뒤에만 허용된다.

실제 현재 상태의 실행:

```powershell
.venv\Scripts\python.exe tools/evaluate_condition_pipeline.py --split development --preflight-only
.venv\Scripts\python.exe tools/evaluate_condition_pipeline.py --split development
```

두 명령은 준비 상태를 확인하고 정답이 없으면 점수를 내지 않는다. 실제 성능 평가는 사람 검수 완료 전까지 수행하지 않는다.
