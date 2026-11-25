# 조건 추출·논리 구조 평가기 v1

## 용도와 안전 조건

`tools/evaluate_condition_pipeline.py`는 2-2 조건 후보와 2-3 논리 결과를 2-4단계에서 사람이 검수한 정답에 비교한다. 현재 정답 행이 0건이므로 이번 검증은 합성 테스트로 제한한다. 빈 정답, 미검수, 불완전 정답 또는 평가 대상 0건은 점수 0/100이 아니라 `BLOCKED` 및 `NOT_COMPUTED`로 보고한다. 평가 전 preflight가 통과하기 전에는 예측 파일을 열지 않는다.

평가 범위는 검수된 `source_text`에 한정된다. 공고 전체 원문이 불완전하거나 조건이 미확인된 건은 조건 없음으로 취급하지 않는다. `UNDECIDABLE`과 `EXCLUDED`는 사유와 함께 점수 집계에서 제외한다. 평가 대상 출처에 원문이 없는 나라장터 공고는 포함하지 않는다.

## 실행 모드

- `end_to_end`: 조건 후보를 gold 조건과 일대일 대응한 뒤, 완전 매칭으로 확인된 조건 ID 매핑만 논리 비교에 사용한다. 미추출 조건은 FN 및 그에 따른 논리 참조 누락으로 반영한다.
- `logic_oracle`: 이미 검수된 gold condition ID를 입력 조건으로 제공한다고 가정하고 논리 변환만 평가한다. 조건 추출 성능은 계산하지 않는다.

실제 개발용/평가용 실행 예:

```powershell
.venv\Scripts\python.exe tools/evaluate_condition_pipeline.py --split development --preflight-only
.venv\Scripts\python.exe tools/evaluate_condition_pipeline.py --split development --condition-predictions <dev_conditions.jsonl> --logic-predictions <dev_logic.jsonl> --mode end_to_end
.venv\Scripts\python.exe tools/evaluate_condition_pipeline.py --split evaluation --condition-predictions <eval_conditions.jsonl> --logic-predictions <eval_logic.jsonl> --mode end_to_end
```

평가용 예측 입력은 독립 검수 완료 후 별도 생성·동결한다. 프로그램은 다른 분할의 공고 ID가 예측 파일에 섞이면 점수 생성을 차단한다. 기존 평가용 표본 추출·추출기 출력은 이번 작업에서 생성하지 않았다.

## 사전 조건 검사

평가 전에 검수 입력 JSON Schema, `VERIFIED` 상태와 완료 판정, 개발·평가 notice 분리, notice/gold ID 중복, 원문 span 및 gold ID, 조건·논리 검수 자료 일치, ingested gold 출력과 원본 검수 파일 동기화, 기준선 SHA-256을 확인한다. 추출기, 논리 변환기 및 평가기 소스 해시, goldset 기준 manifest 해시, 예측 파일 해시는 실행 메타데이터에 기록한다. 기준선 해시 불일치도 점수 생성 차단 사유다.

현재 실행을 재현하려면 먼저 JSONL 검수 자료를 사람이 수정하고 다음 명령으로 검증·반영한다.

```powershell
.venv\Scripts\python.exe tools/ingest_condition_gold_reviews.py --split development
.venv\Scripts\python.exe tools/ingest_condition_gold_reviews.py --split evaluation
```

## 조건 매칭 및 지표

매칭은 같은 `notice_id` 안에서 수행하며 최대 카디널리티 일대일 배정으로 중복 TP를 막는다. 결정적 비교 키는 조건 유형, 분류, 판정 필드, 연산자, 값·타입, 단위, 기준일 유형·값, 적용 대상이다. 텍스트는 Unicode NFKC 및 공백 정규화, 숫자는 Decimal 표준화, `IN` 집합 값은 순서 무시로 비교한다. 단위 환산이나 자연어 동의어 추정은 승인된 별도 표준표가 없으면 하지 않는다.

위 의미 필드가 같고 근거 원문 필드·span까지 일치하면 FULL 매칭(TP)이다. 의미 필드가 다르거나 근거가 부분적으로만 맞는 경우 PARTIAL 진단 쌍으로 기록하지만 TP로 계산하지 않는다. 미대응 예측은 FP, 미대응 정답은 FN이다. 부분 쌍도 각각 FP와 FN으로 남긴다. 중복 예측은 정답 1건에 하나만 대응하고 나머지는 FP다.

Micro P/R/F1은 합산 TP/FP/FN으로 계산한다. Macro는 notice별 지표의 정의된 값 평균이다. 분모가 0인 Precision/Recall은 `null`과 사유로 둔다. 예측과 gold가 모두 없을 때 F1도 `null`; gold가 있는데 예측이 없어 TP=0이면 F1=0, Precision은 `null`, Recall은 0이다. 출처·유형·카테고리별 지표 및 공고별 누락률을 함께 기록한다. 속성 정확도와 근거 정확도는 FULL/PARTIAL로 대응된 쌍을 분모로 별도 산출한다.

## 논리 비교 및 실패 분류

`CONDITION_REF`는 end-to-end 완전 조건 매핑 후 gold ID로 치환한다. 논리 그룹 ID는 의미 비교에서 제외한다. AND/OR 자식은 정렬하고 동일 연산자 중첩은 평탄화한다. 서로 다른 연산자 경계 및 NOT 범위는 유지한다. 관계 지표는 부모 그룹 signature와 자식 signature edge를 비교하며, 그룹 exact 및 공고 단위 AST exact도 별도로 산출한다.

예외는 원문·적용 gold 대상·연결 상태가 같아야 일치한다. 우대 혜택 연결도 혜택 원문과 적용 대상 조건으로 비교한다. `UNRESOLVED`는 정답도 미확정일 때 적절한 미확정으로 세며, 정답 관계가 결정되어 있는데 예측이 미확정이면 과잉 미확정으로 집계한다. 예외 대상 오류 및 미확정 관계를 일반 논리 엣지와 혼합하지 않고 전용 지표로 출력한다.

조건 실패 분류는 조건 누락, 과잉 추출, 유형, 속성, 연산자, 값/단위, 기준일, 근거 오류다. 부분 매칭 쌍은 해당 mismatch의 가장 먼저 발견된 항목으로 대표 분류하고, 전체 차이 목록은 상세 레코드에 보존한다. 논리 edge 누락/과잉, operator/group 차이, exception/benefit 대상 차이, overcautious unresolved는 논리 결과에 별도로 남긴다.

## 산출물

실제 정답이 준비된 분할에서 실행하면 다음 파일을 만든다.

- `evaluation_summary.json`: overall, micro/macro, 출처·유형·카테고리, 논리 지표 및 버전 정보
- `condition_matches.jsonl`: gold/prediction 일대일 및 부분 매칭
- `notice_details.jsonl`: 공고별 조건 지표와 실패 목록
- `failures.jsonl`: 누락·과잉·속성 오류 사례
- `logic_details.jsonl`: 공고별 AST, 엣지, 그룹, 예외, 혜택 및 미확정 비교
- `excluded_notices.json`, `not_evaluated_notices.json`: 제외 및 미검수/미완료 상태 목록
- `evaluation_report.md`: 요약 보고서

합성 케이스의 예상 결과는 `sample_data/conditions/condition-evaluation-synthetic-cases-v1.json`에 정의한다. 합성 지표는 실제 공고 결과 경로에 저장하지 않고, 실제 성능으로 보고하지 않는다.
