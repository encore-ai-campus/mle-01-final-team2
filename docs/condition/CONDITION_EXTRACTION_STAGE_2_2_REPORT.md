# 2-2단계 조건 추출기 구현 및 초기 검증

작성일: 2026-11-25. 추출기: `tools/extract_condition_candidates.py`; 개발 산출물: `data/condition_inputs/v1/20261125/extracted/`.

## 범위

기존 2-1 공통 입력, 조건 스키마 및 후보 ID를 재사용했다. 개발용 80건(기업마당 40, K-Startup 40)만 추출했다. 평가용 20건은 결과 생성·규칙 처리에 사용하지 않았다(표본 파일에서 DEVELOPMENT 항목만 추출기에 전달). 전체 5,116건 일괄 추출과 나라장터 메타데이터 추출은 하지 않았다.

## 구현과 산출물

- 문장/문단/목록 라인을 보존하며 조건 매칭 구간의 원문 시작·종료 문자 위치를 기록한다. 제목·불릿·연결 문구를 제거하거나 논리 트리로 바꾸지 않는다.
- 자격, 제외, 우대 유형의 표면 표현을 분류하고, 기업 유형·지역·업력·대표자 연령·매출·고용 규칙을 제한적으로 적용한다. 경계 의미나 기준일이 불명확하면 수치값을 만들지 않는다.
- condition v1 객체를 출력한다. 모든 추출 후보는 미검수이고 `decision_eligible=false`; 논리 상태는 `UNRESOLVED`다.
- 후보 원문 일치 참조는 `candidate_provenance.jsonl`에 새 조건 ID와 2-1 후보 ID를 연결한다. 기존 후보 ID는 변경하지 않는다.
- LLM 제공자 인터페이스는 실패-폐쇄 방식의 미설정 구현이다. 호출/외부 API 사용은 없으며 실제 LLM 추출은 미검증이다.

산출 파일: `development_conditions.jsonl`(84 후보), `candidate_provenance.jsonl`(84), `review_queue.jsonl`(29 공고), `run_report.json`.

## 초기 결과

| 지표 | 결과 |
|---|---:|
| 개발용 입력 처리 | 80/80, 처리 실패 0 |
| 후보 | 84 (ELIGIBILITY 75, EXCLUSION 6, PREFERENCE 3) |
| 카테고리 | BUSINESS_TYPE 50, BUSINESS_AGE 14, BUSINESS_LOCATION 8, REPRESENTATIVE_AGE 2, REVENUE_FINANCIAL 1, UNCLASSIFIED 9 |
| 판정 허용 후보 | 0 |
| 개별 객체 스키마 오류 | 0/84 |
| LLM 호출 | 미설정, 0회 |

후보 수는 규칙 매칭 산출량이며 정답 라벨이 없어 정확도/재현율로 해석하지 않는다. 규칙 적용이 어려워도 패턴이 없는 공고, 상세 예외 및 범위 문구는 검수 대기열에 남긴다. 문자열 단위 패턴 기반 분류는 의미 판정이 아니다.

## 테스트

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_condition_extractor tests.test_condition_inputs tests.test_normalize_support_data tests.test_public_notice_pipeline tests.test_g2b_normalization tests.test_condition_schema -v
```

결과: **40 tests passed**. 추가로 실제 개발 추출 결과 84개를 condition v1 스키마로 검사해 오류 0건을 확인했다. 테스트에는 수치 경계, 기업 유형/지역, 유형 분류, 근거 오프셋, 미검수 차단, 결정성 및 LLM 미설정 실패-폐쇄가 포함된다.

## 남은 문제와 다음 단계

- 초기 규칙은 작은 어휘 집합만 다루며, 범위 연산(BETWEEN), 복수 지역 집합, 단위 환산, 기준일 해석, 조건 문장 상위/하위 범위 연결은 보수적으로 미해결로 둔다.
- 특정 연령 표현에서 `세`와 년령 기준일이 확정되지 않으면 구조화하지 않는다. 복합문·예외 연결은 원문 구간으로만 보존한다. AND/OR/NOT 트리는 생성하지 않았다.
- 현재 개발 결과는 초기 규칙 피복 확인용이며 별도 사람 검수 및 정답셋이 필요하다. 평가용 20건은 보존하고 규칙 튜닝에 사용하지 않는다.
- LLM 공급자 설정이 없어 복잡 문장 LLM 추출은 미수행이다.

2-2단계의 제한된 규칙 기반 추출 및 개발 표본 검증은 완료됐다. 2-3단계에서는 후보 원문·목록 계층·상위 구간을 이용해 논리 관계를 검수 가능하게 표현할 수 있다. 단, 후보가 자동으로 검증된 조건이 되거나 판정에 사용되는 단계는 아니다.
