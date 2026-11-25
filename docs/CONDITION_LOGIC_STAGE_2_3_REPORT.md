# 2-3단계 조건 논리 구조 후보 생성 결과

## 결과 요약

개발용 공고 80건의 2-2단계 개선 조건 후보 98건을 기존 조건 스키마의 공고별 조건 집합 및 검수용 논리 후보로 변환했다. 후보 98건을 전부 결과에 보존했다. 평가용 20건 및 나라장터 192,064건은 입력 처리에 사용하지 않았으며, 기존 입력·정규화·추출 산출물은 수정하지 않았다.

사람 검수는 수행하지 않았다. 생성된 구조는 모두 검수 후보이며, 확정된 논리 관계나 신청 자격 판정 결과가 아니다.

## 입력·결과 통계

| 항목 | 결과 |
|---|---:|
| 개발용 공고 처리 | 80 |
| 입력 조건 후보 | 98 |
| 자격 조건 후보 | 89 |
| 제외 조건 후보 | 6 |
| 우대 조건 후보 | 3 |
| 후보 미추출 공고 | 26 |
| 출력 조건 후보 | 98 |
| 복수 조건 논리 그룹 후보 | 25 |
| AND 후보 | 2 |
| OR 후보 | 5 |
| UNRESOLVED 후보 | 18 |
| NOT 자동 생성 | 0 |
| 예외·단서 원문 후보 | 5 |
| 동일 근거 상충 해석 묶음 | 0 |
| 사람 검수 패킷 | 30 공고 |
| 판정 허용 후보 | 0 |

출처별 후보: 기업마당 37건, K-Startup 61건. 두 출처 모두 개발 표본에 포함되어 있다.

나머지 조건 후보는 단일 조건 루트로 연결했다. 관계 그룹 후보 25건의 AND/OR는 명시 연결 어휘에 기반한 제안이며 전부 `NEEDS_REVIEW`다. 어휘만으로 그룹을 만들 수 없는 경우 `UNRESOLVED`로 보존했다. 후보 미추출 26건은 `NOT_EXTRACTED` 및 미확인 사유로 기록했으며 조건 없음으로 해석하지 않았다.

## 구현 파일과 산출물

- `tools/build_condition_logic.py`: 개발용 조건 후보 변환, 결정적 ID, 예외 후보 생성, 그래프 검증 및 검수 패킷 생성
- `tests/test_condition_logic.py`: 스키마, 참조 무결성, 후보 보존, 중첩 논리 연산자, 개인정보 및 재생성 테스트
- `docs/CONDITION_LOGIC_RULES_STAGE_2_3.md`: 관계 후보 생성과 검수 규칙
- `data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl`: 공고별 80건
- `data/condition_inputs/v1/20261125/logic/relation_review.jsonl`: AND/OR/UNRESOLVED 관계 그룹 후보 25건
- `data/condition_inputs/v1/20261125/logic/unresolved_logic_review.jsonl`: 개발용 공고 80건 처리 상태
- `data/condition_inputs/v1/20261125/logic/qualifier_candidates.jsonl`: 예외·단서 후보 5건, 대상 연결 미확정
- `data/condition_inputs/v1/20261125/logic/conflict_review.jsonl`: 동일 근거 해석 충돌 후보 0건
- `data/condition_inputs/v1/20261125/logic/condition_group_map.jsonl`: 후보 ID 98건과 조건 슬롯 매핑
- `data/condition_inputs/v1/20261125/logic/human_logic_review.jsonl`: 기존 30건 검수 대상에 추출 결과 및 논리 후보 연결
- `data/condition_inputs/v1/20261125/logic/human_logic_review.csv`: 위 자료의 검수용 CSV
- `data/condition_inputs/v1/20261125/logic/run_report.json`: 실행 통계

검수 패킷에는 원문, 개별 조건 후보, 제안 논리 트리, 관계·예외 후보와 검수자 입력 필드를 포함한다. 모든 사람 검수 상태는 `UNREVIEWED`로 유지한다.

## 검증

다음 검증을 수행했다.

- 공고 레코드 80건이 기존 공통 조건 JSON Schema 통과
- 원본 후보 ID 집합과 출력 조건 ID 집합 동일: 98/98
- 잘못된 공고 내부 조건 참조 및 누락 참조: 0건
- 복수 조건 그룹 ID 중복: 0건
- 판정 허용 상태: 0건
- `NO_CONDITION_CONFIRMED`로 변환된 미추출 공고: 0건
- 기존 30건 검수 대상 패킷 구성: 30/30, 사람 검수 자동 완료 처리: 0건
- 개인정보 탐지 검사에서 출력 공고 레코드·검수 패킷·단서 후보 발견: 0건
- 고정 입력 재실행 결과 공고 조건 집합 동일
- 중첩 AND/OR/NOT 예시 AST의 참조 및 연산자 구조 검증 통과

실행 명령:

```powershell
.venv\Scripts\python.exe tools/build_condition_logic.py
.venv\Scripts\python.exe -m unittest tests.test_condition_logic tests.test_condition_extractor tests.test_condition_inputs tests.test_normalize_support_data tests.test_public_notice_pipeline tests.test_g2b_normalization tests.test_condition_schema -v
```

최종 실행 결과: 신규 2-3단계 테스트 8개와 기존 정규화·스키마·추출기 회귀 테스트 41개, 총 49개가 모두 통과했다. 생략된 테스트는 없다.

## 구조 및 제한 사항

기존 스키마는 재사용했으며 새 스키마 버전은 추가하지 않았다. 그룹 연산자는 재귀적으로 표현할 수 있고, `NOT`은 스키마 검증과 합성 AST 테스트에서 지원된다. 다만 실제 공고 데이터에는 부정 표현의 범위와 의미를 안전하게 결정할 정보가 부족해 NOT 그룹을 자동 생성하지 않았다. 여러 조건의 단순 나열 또는 다른 원문 필드에서 추출된 후보를 AND/OR로 강제 결합하지 않았다.

현재 데이터에서 동일 근거 상충 후보는 발견되지 않았다. 이는 기존 후보 전체의 의미 충돌이 없다는 뜻이 아니며, 동일 근거·동일 구간에서 자동 검출 가능한 구조적 상충만 0건이라는 의미다. 기존 30건 검수 자료는 자동 결과와 연결했으며 검수 정답으로 간주하지 않는다.

따라서 2-3단계의 자동 구조 후보 생성기와 무결성 검증 구현은 완료했다. 논리 관계의 의미 정확도 검증 및 조건 판정은 사람 검수 후속 작업이며 이번 단계의 완료 근거로 주장하지 않는다. 평가 표본을 쓰지 않고 추가 규칙 최적화를 하지 않았다.
