# N0–N5 오프라인 정규화 실험

고정 DEVELOPMENT 10공고·62정답, P12 원본 응답 10건을 사용했다. 각 실험은 같은 원본에서 출발하며 기존 intermediate schema, attribute-normalization-v2, 후보·근거·날짜·중복·v1.1 schema·논리 변환 코드를 재사용한다. 운영 추출기·카탈로그·평가기·프롬프트는 변경하지 않았다.

## 계약 검토 및 고정

safe-condition-normalization-subset-v1은 draft-v1 전체를 승격하지 않은 실험용 부분집합이다. 기존22 속성 이름·category·의미 경계를 유지한다. 단위 표준 방향 YEAR/MONTH/DAY/PERCENT/PERSON 및 KRW/USD는 draft-v1의 명시적 정의에 근거하며 골든 값을 보고 선택하지 않았다. 값/금액 변환은 원문 숫자·단위를 함께 확인한다. 원본 field를 바꾸지 않고 기존 v2가 최종 속성 처리를 맡는다.

EXACT_ALIAS 22개는 기존 v2의 explicit alias/유일 casefold 처리와 모두 중복된다. N4는 NO_CHANGE다. EMPLOYMENT, REVENUE_FINANCIAL, 개인주소/사업장, 대표자/팀원, 신청주체/사업체 등 문맥 의존·의미 구분 관계를 치환하지 않는다. GraphRAG의 WITHIN/labels/ranges와 소문자 legacy container는 이 실험의 입력 범위가 아니다. 레거시 값 구조를 LLM intermediate와 섞지 않는다.

기존 최종 v1.1 스키마는 unit 문자열을 허용하며 BETWEEN은 lower/upper 각각 value/inclusive를 요구한다. EXISTS payload와 UNKNOWN operator 정책은 그대로다. strict evaluator도 수정하지 않았다. 새로운 단위·값의 표현을 기존 validator에 통과시킨 후 같은 evaluator로 측정했다.

## 전체 성능 — % 단위

| 실험 | TP | FP | FN | Precision | Recall | Micro F1 | Macro F1 | 부분 일치 | 예측 0개 공고 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| N0 P12 재현 | 1 | 31 | 61 | 3.1250 | 1.6129 | 2.1277 | 2.50 | 16 | 3 |
| N1 단위 | 3 | 29 | 59 | 9.3750 | 4.8387 | 6.3830 | 7.50 | 14 | 3 |
| N2 숫자·금액 | 1 | 31 | 61 | 3.1250 | 1.6129 | 2.1277 | 2.50 | 16 | 3 |
| N3 범위 | 1 | 31 | 61 | 3.1250 | 1.6129 | 2.1277 | 2.50 | 16 | 3 |
| N4 alias | 1 | 31 | 61 | 3.1250 | 1.6129 | 2.1277 | 2.50 | 16 | 3 |
| N5 통합 | 3 | 29 | 59 | 9.3750 | 4.8387 | 6.3830 | 7.50 | 14 | 3 |

각 실험은 통과 32·의미 보류 1·후보 검증 탈락 15개다. 별도로 178507의 원본 제안 10개는 응답 전체 중간 스키마 거절에 속하며 검증 후보로 세지 않는다. 합계 원본 제안은 58개다. 이번 실험에서 기존 탈락 후보의 복구는 0개이며 신규 후보가 생성된 것은 아니다.

## 실제 변환과 개선

N1은 KSTARTUP:176001의 업력 1 `년→YEAR`, 산업매출비중 10 `%→PERCENT` 두 후보를 변환했다. 원문 값·근거·span·연산자는 동일하다. 다음 두 기존 부분 일치 정답이 완전 일치가 됐다.

- GOLD:N3QF42LGMLZNFLXN35JBKWT5
- GOLD:YY7C3VVWNOHRCG33RVRBXZAK

이는 평가 이후 식별한 진단 ID이며 정규화 코드·규칙에 사용하지 않았다. FN 2개와 FP 2개가 해소됐다. 기존 TP 1개는 모든 실험에서 보존됐다.

N2는 같은 공고의 매출 `3억원→300000000 KRW` 한 후보를 정확한 Decimal 배율로 변환했다. 하지만 REVENUE_FINANCIAL과 정답 REVENUE의 속성 차이는 유지돼 신규 TP는 없다. 기존 FP 후보 ID가 새 ID로 바뀌었지만 동일한 원본 proposal에 대응하며 새 의미의 FP가 추가된 것은 아니다.

N3은 양 경계 포함 여부가 명시되지 않은 minimum/maximum을 보류했다. 하한·상한 flags와 원문 부등호가 일치하는 합성 사례는 변환할 수 있으나 실제 저장 응답에서는 안전 조건을 만족하는 신규 변환이 없었다. 178507은 UNKNOWN operator 때문에 모든 실험에서 전체 실패·빈 예측으로 유지했다. 제안 일부만 골라 복구하지 않았다.

N4는 공유 v2가 이미 모든 EXACT_ALIAS를 처리하므로 최종 후보 레코드가 N0와 완전히 같다. N5의 실제 변환은 N1 2건 + N2 1건이며 성능 개선은 N1의 두 건에서 발생했다. 조건 분해·지역 값·속성 의미·span 보정은 수행하지 않았다.

## 출처·유형

BIZINFO는 모든 실험에서 TP0/FP23/FN35, F1 0%다. KSTARTUP은 N0·N2·N3·N4의 TP1/FP8/FN26, F1 5.5556%에서 N1·N5의 TP3/FP6/FN24, F1 16.6667%로 변했다.

자격 조건은 N0의 TP1/FP30/FN55, F1 2.2989%에서 N1·N5의 TP3/FP28/FN53, F1 6.8966%가 됐다. 제외는 TP0/FP0/FN3, 우대는 TP0/FP1/FN3으로 변하지 않았다. 제외 Precision은 예측이 없어 미정의다. 출처별·조건 유형별 전체 수치는 experiment_metrics.csv 및 각 실험 evaluation.json에 담았다.

## 안전성·회귀

모든 arm에서 원본 응답·P12·draft-v1·개발용 골든셋·기존 스키마·운영 코드의 해시를 보존했다. 동일 입력의 정규화 반복 및 전체 replay 반복에서 후보·검증 상세·논리 제안이 일치했다. 원본 후보 객체를 변경하지 않았고 N5 정규화 순서의 정방향·역방향 비교에서 충돌이 없었다.

신규 스키마 오류, 근거/span 변경, 논리 참조 무결성 오류, temporal 변경, 원본 논리 그룹/예외/미해결 관계 손실, decision_eligible 증가 모두 0이다. 단위·값이 바뀌면 안정 ID도 달라지므로 기존 ID를 강제 유지하지 않고 old/new ID를 change log로 연결했다. 논리 참조는 같은 변환된 후보 ID로 재생성했다.

정규화 보류 로그는 '해당 변환을 적용하지 않음'을 뜻하며 후보 검수 보류 수와 구분한다. 예를 들어 원문 단위를 직접 확인할 수 없는 치환은 NO_TRANSFORM_POLICY_HOLD로 남기고 기존 후보 검증 결과를 유지한다.

새 합성 테스트 22개를 포함한 관련 회귀 테스트 81개와 기존 계약 검증 27개가 통과했다. 실제 9개 schema-valid 응답을 각 arm별로 독립 재처리했고 각 출력도 임시 경로에서 재현했다. 178507은 모든 arm에서 동일한 원본 실패 자료를 재사용했다.

## 한계 및 재현

논리 adapter는 수정하지 않았다. 기존 logical_roots와 최상위 그룹·예외 연결의 한계가 남아 있으므로 조건 F1 개선을 논리·AST 개선으로 해석하지 않는다. 표본은 개발용 10공고뿐이며 운영·독립 평가 성능으로 일반화할 수 없다. 기존 규칙 v1/E보다 여전히 낮다.

```powershell
.\.venv\Scripts\python.exe tools/run_condition_normalization_experiments.py --output-dir data/evaluations/conditions/v1.1/20261126/development/condition_normalization_reproduction
.\.venv\Scripts\python.exe -m unittest tests.test_condition_safe_normalization_experiment -q
```

출력 경로가 이미 존재하면 덮어쓰기를 거부한다. 최초 검증 실행은 *_initial_run에 보관하고, 최종 실행은 실험별 fingerprint에 arm과 활성 규칙을 명시했다. 요청 장부는 13/13·잔여0이며 실제 API 호출은 0회다.
