# 조건 의미 평가 v1.1 정책

평가기 구현: `tools/evaluate_condition_pipeline_v11.py`. 정책 버전 `1.1.0`. v1.0 평가기와 테스트는 유지한다. 기본 실행은 사전 점검만 수행하며, 실제 개발용 점수 계산에는 명시적인 `--execute`가 필요하다.

## 입력과 호환성

| v1.1 정답 | v1.0 예측 | 비교 정책 |
|---|---|---|
| `condition_type` | `condition_type` | 동일 enum만 일치. EXCLUSION의 TRUE는 제외 사유 해당이다. |
| `category` | `category_id` | 동일 코드만 일치. |
| `field` | `field` | 동일 속성만 일치. `BUSINESS_TYPE`과 `APPLICANT_TYPE` 등 의미가 다른 필드는 매핑하지 않는다. 승인된 별칭 매핑은 현재 0개다. |
| `operator`, `value`, `unit` | 같은 필드 | 연산자·단위 정확 일치. 수치 표면형과 IN 집합 순서는 기존 정규화 함수로 비교한다. MONTH를 DAY로 환산하지 않는다. |
| `source_field`, 기본 `evidence_reference` | `source.source_field`, `source.location`, `source.evidence_text` | 필드·문자 범위·문구가 모두 같아야 정확 근거. 같은 문구의 다른 위치는 정확 일치가 아니다. |
| v1.1 확장 필드 | v1.0에 없음 | `UNSUPPORTED_V1_0` 또는 필드별 `unsupported`로 집계한다. 정답으로 인정하지 않는다. |

기존 후보 alignment는 평가의 정답 판정에 사용하지 않는다. 정답과 예측은 공고 안에서 ID로 정렬한 뒤 최대 일대일 매칭한다. **EXACT_MATCH**는 위 공통 필드와 기본 근거가 모두 같을 때만 strict TP다. 같은 속성에 원문 겹침 또는 동일 문구가 있으나 필드/근거 차이가 있으면 **PARTIAL_MATCH**로 기록하며 TP에 포함하지 않는다. 남은 정답과 예측은 각각 FN·FP다. 복합 조건의 분해 차이와 일대다 대응은 partial 진단으로 남는다.

## 지표와 분모

Micro precision=`TP/(TP+FP)`, recall=`TP/(TP+FN)`, F1은 두 값의 조화평균이다. 예측이 없으면 precision은 `null`, 정답이 없으면 recall은 `null`, 둘 다 없으면 F1도 `null`이다. Macro는 정의된 공고별 값만 평균한다. 출처·조건 유형·속성별 지표는 각 그룹의 TP/FP/FN으로 다시 계산한다. 공고별 누락·오추출 수를 별도로 보고한다. Partial은 FP와 FN 양쪽에 남아 strict 점수를 올리지 않는다.

## 논리 구조

조건 ID는 일대일 매칭으로 정답 ID에 대응시킨 뒤 AST를 비교한다. AND/OR의 자식 순서는 무시하고 동일 연산자의 연속 중첩은 결합법칙에 따라 평탄화한다. NOT 범위, AND/OR 교체 및 다른 분기 구조는 불일치다. 그룹 ID·구역 ID 문자열은 의미 비교에서 제외한다. 기본 구조의 완전 일치, 그룹·간선·조건 참조 일치를 따로 기록한다. v1.1 구역 유형·평가 및 충족 시점이 예측에 없으면 `UNSUPPORTED_V1_0`이다. 미확정 관계는 확정 AND/OR 정답으로 취급하지 않는다.

## 확장 의미·시간·예외

조건의 적용 범위, 평가·충족 시점, 현재 상태/미래 능력/사후 의무, 기준일 유형, 실제 날짜, 시간 기준 이벤트, 절대일·기간·단위·연산자·포함 경계, 복수 근거, 외부 참조를 공통 필드와 **별도 분모**로 집계한다. 정답이 null/UNKNOWN이면 `unknown`; 대응 예측이 없으면 `no_aligned_prediction`; 예측 스키마에 필드가 없으면 `unsupported`; 값이 있으면 `evaluable`과 `correct`를 기록한다. 신청일은 접수 시작일·접수마감일과 동일하지 않다. 공고일 이벤트가 알려졌으나 달력 날짜가 없는 경우도 구별한다. 업력 조건의 날짜 보조 근거는 별도 조건으로 세지 않는다.

예외는 대상 ID, 전제, 효과, 효과 대상, 대체값, 원문상 효과 확정 여부, 실행 방식의 조합을 비교한다. 예외 존재만으로 일치시키지 않는다. 개인·팀, 동일 권리·서로 다른 권리의 결합은 미확정 관계 및 적용 범위로 검사한다. `effect_confirmed=true`와 `effect=UNKNOWN`은 원문 효과가 명확해도 실행 표현이 미지원일 수 있음을 뜻한다. 정성 근거의 의미적 적절성은 자동으로 확정하지 않고 `NEEDS_HUMAN_REVIEW`로 표시한다. 위치 일치와 의미 검수는 별도 결과다.

## 불확실성·안전성

미수집→조건 없음, UNKNOWN→확정, 미확정 관계→확정 AND/OR, 불완전 원문→COMPLETE, 판정 비허용→판정 가능, 제외 의미 반전, 우대→필수, 사후 의무→신청 자격, 예외 범위 확대, 실행 미지원 예외의 실행을 별도 오류 코드로 기록한다. 의미 검수 승인은 실제 신청 가능 판정 허가가 아니다. 원문 완전성 UNKNOWN이면 모든 확인 조건이 참이어도 전체 신청 가능 여부는 확정되지 않는다.

## 설정·출력·실행

설정: `configs/condition_evaluation_v11_development.json`. 기본 명령은 사전 점검 전용이다.

```powershell
.venv/Scripts/python.exe tools/evaluate_condition_pipeline_v11.py
```

후속 평가 단계에서만 아래 명령으로 고정 개발용 v1 예측과 v1.1 정답을 비교한다. `--execute`가 없으면 점수가 계산되지 않는다.

```powershell
.venv/Scripts/python.exe tools/evaluate_condition_pipeline_v11.py --execute --output data/evaluations/conditions/v1.1/20261126/development_report.json
```

출력 JSON은 `policy_version`, `common`(micro, macro, 출처·유형·속성별 지표), `extended`(필드별 target/evaluable/correct/unsupported/unknown/no_aligned_prediction), `safety`(오류 코드별 건수), `notices`(공고별 매칭·근거·논리 진단)로 구성한다. 사전 점검은 정답셋 FINALIZED, manifest·원본·입력·추출·논리 SHA-256, 개발용 ID, 평가용 ID 비중복과 예측 스키마 버전을 확인한다. 실패 시 점수를 생성하지 않는다.
