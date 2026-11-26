# 2026-11-25 조건 데이터 작업 정리 및 파일 안내

## 작업 상태

2-1부터 2-5까지 조건 입력 구성, 추출, 논리 후보 생성, 사람 검수 패킷 작성, 평가기 구현을 진행했다. 자동 검증과 합성 데이터 테스트는 완료했다. **실제 조건의 사람 검수와 실제 성능 평가는 아직 수행하지 않았다.** 2-4 정답셋은 검수 완료 0건이며, 평가기는 이 상태에서 점수 계산을 차단하고 `NOT_COMPUTED`를 기록한다. 다음 작업은 검수 패킷의 원문과 근거를 사람이 확인하는 것이다.

기존 2-2/2-3 기준선은 유지했다. 평가용 20건에 대한 추출 결과를 만들거나 평가 규칙 개선에 사용하지 않았다. 원본·정규화 데이터, DB, 기존 운영 코드는 이번 평가기 작업에서 변경하지 않았다. Git 커밋과 푸시는 하지 않았다.

## 오늘의 작업 흐름

| 단계 | 작업 | 결과 |
|---|---|---|
| 2-1 | 출처별 공통 조건 입력, 보류 상태, 근거·후보 참조와 표본 구성 | 총 197,180건 중 기업마당·K-Startup 5,116건 입력, 나라장터 192,064건 원문 미확보 보류. 개발 80건, 평가 20건을 분리했다. |
| 2-1 보완 | 후보 참조 ID 충돌 원인 분석과 안정적 ID 생성 | 후보 원본 참조를 보존하고 신규 참조 ID 중복을 제거했다. 기존 후보는 검수 전 상태로 유지했다. |
| 2-2 | 규칙 기반 조건 추출과 품질 진단 | 개발용 80건만 대상으로 기준선 및 개선 결과, 진단·검수 자료를 생성했다. 평가용 표본은 사용하지 않았다. |
| 2-3 | 조건 후보의 논리 구조 후보 생성 | 개발용 후보에 대한 그룹·관계 및 미확정 검수 자료를 만들었다. 확정 논리나 자격 판정은 만들지 않았다. |
| 2-4 | 조건·논리 정답셋 검수 패킷과 반영 도구 | 개발 30건, 평가 20건 검수 자료를 분리해 만들었다. 현재 모두 미검수이며 정답 데이터는 비어 있다. |
| 2-5 | 추출·논리 평가 프로그램과 합성 검증 | 평가기는 정답셋 검수 상태를 먼저 확인한다. 합성 테스트를 통과했고, 실제 평가는 정답 부재로 차단된 상태를 기록했다. |

## 사람이 검수할 파일

검수 입력은 버전 경로 아래 `development`와 `evaluation` 각각에 있다.

- `data/goldsets/conditions/v1/20261125/development/condition_review.csv` 및 `.jsonl`: 개발용 30건의 조건 검수 패킷. 원문 조건과 후보를 대조하고 조건 유무·유형·속성·근거를 검수한다.
- `data/goldsets/conditions/v1/20261125/development/logic_review.csv` 및 `.jsonl`: 같은 개발용 30건의 논리 관계, 예외·단서 및 혜택 연결 검수 패킷.
- `data/goldsets/conditions/v1/20261125/evaluation/condition_review.csv` 및 `.jsonl`: 독립 평가용 20건의 조건 검수 패킷. 개발 표본과 분리해 보관한다.
- `data/goldsets/conditions/v1/20261125/evaluation/logic_review.csv` 및 `.jsonl`: 평가용 20건의 논리 검수 패킷.
- 각 집합의 `reviewed_condition_gold.jsonl`, `reviewed_logic_gold.jsonl`: 검수 반영 도구가 생성하는 정답 산출물. 현재 0건이므로 사람의 검수가 끝나기 전까지 평가 정답으로 사용할 수 없다.
- 각 집합의 `ingest_report.json`, 상위 `build_report.json`: 검수 상태와 반영 결과를 확인하는 보고 파일.

검수 기준은 `docs/CONDITION_GOLDSET_REVIEW_GUIDE_V1.md`를 따른다. 모든 행은 자동 검수 결과가 아니라 사람의 검토가 필요한 미검수 상태다. 정보가 부족한 상태를 “조건 없음”으로 바꾸지 않는다.

## 파일별 안내

### 스키마 및 표준

- `schemas/conditions/condition-v1.schema.json`: 개별 조건 후보의 필드와 타입.
- `schemas/conditions/condition-common-v1.schema.json`: 공통 조건 구조.
- `schemas/conditions/condition-vocabularies-v1.schema.json`: 조건 유형, 카테고리, 연산자 등 표준 어휘.
- `schemas/conditions/logical-group-v1.schema.json`, `notice-condition-set-v1.schema.json`: 논리 그룹 및 공고별 조건 집합 구조.
- `schemas/conditions/condition-gold-review-v1.schema.json`, `logic-gold-review-v1.schema.json`: 사람의 조건·논리 검수 입력 구조.
- `schemas/conditions/source-field-mapping-v1.csv`: 출처별 필드 대응표.

### 입력·추출·논리 데이터

기본 경로: `data/condition_inputs/v1/20261125/`

- `extraction_inputs.jsonl`: 조건 추출기에 전달하는 공통 입력.
- `dispositions.jsonl`: 전체 공고의 추출 대상·보류 상태.
- `candidate_refs.jsonl`: 기존 정규화 후보와 새 참조 ID의 연결 정보.
- `representative_samples.jsonl`: 개발·평가 대표 표본과 split 정보.
- `g2b_deferred_samples.jsonl`: 나라장터 원문 미확보 보류 확인 표본.
- `kstartup_candidate_audit.jsonl`: K-Startup 기존 후보와 공고 연결 점검 자료.
- `analysis_report.json`: 2-1 분석 통계 요약.
- `extracted/development_conditions.jsonl`: 현재 개발 표본의 조건 추출 결과.
- `extracted/candidate_provenance.jsonl`: 추출 후보와 기존 후보·원문 근거 연결.
- `extracted/review_queue.jsonl`, `run_report.json`: 추출 검수 대기 목록과 실행 요약.
- `extracted/baseline/`, `extracted/improved/`: 2-2 개선 전·후 결과를 비교하기 위한 보존 산출물.
- `quality_diagnostics/diagnostic_report.json`: 추출 현황·후보 재사용·실패 유형 진단.
- `quality_diagnostics/human_review.csv`, `.jsonl`: 2-2 품질 검수를 위한 개발 자료.
- `quality_diagnostics/llm_assistance_candidates.jsonl`: 규칙만으로 판단하기 어려워 보조 검토가 필요한 후보. LLM 호출 결과가 아니다.
- `logic/`: 공고별 조건 집합, 그룹·관계 후보, 충돌·미확정·예외 검수 자료와 실행 보고서.

### 실행 도구

- `tools/prepare_condition_inputs.py`: 공통 추출 입력·상태·표본·후보 참조 생성 및 재생성.
- `tools/extract_condition_candidates.py`: 개발 표본의 규칙 기반 조건 후보 추출.
- `tools/diagnose_condition_extraction.py`: 추출 결과와 기존 후보를 진단하고 검수 자료 생성.
- `tools/build_condition_logic.py`: 추출된 조건 후보에서 논리 구조 검수 후보 생성.
- `tools/build_condition_gold_review.py`: 사람 검수 패킷과 기준선 manifest 생성.
- `tools/ingest_condition_gold_reviews.py`: 사람이 수정한 검수 패킷을 검증·반영해 gold 산출물 생성.
- `tools/evaluate_condition_pipeline.py`: 사전 검증, 조건 매칭, 추출·논리 지표 및 보고서 생성. 검수 완료 정답이 없으면 점수 계산을 차단한다.

### 평가기 검증 및 보고

- `tests/test_condition_evaluation.py`: 평가 매칭, 지표, 논리 비교, 차단 및 split 안전성 단위 테스트.
- `sample_data/conditions/condition-evaluation-synthetic-cases-v1.json`: 기대값을 정의한 합성 테스트 사례. 실제 공고 평가 결과로 해석하지 않는다.
- `docs/condition/CONDITION_EVALUATION_PROGRAM_V1.md`: 평가 방법, 지표, 명령과 제한 사항.
- `docs/condition/CONDITION_EVALUATION_STAGE_2_5_REPORT.md`: 2-5 구현·검증 결과와 실제 평가 선행 조건.
- `data/evaluations/conditions/v1/20261125/development/evaluation_summary.json`: 현재 정답셋 부재로 `BLOCKED` / `NOT_COMPUTED`인 실행 결과.
- 같은 폴더의 `evaluation_report.md`, `condition_matches.jsonl`, `notice_details.jsonl`, `logic_details.jsonl`, `failures.jsonl`, `excluded_notices.json`, `not_evaluated_notices.json`: 평가 실행 시 생성하는 상세 결과 파일. 현재 성능 점수가 담긴 결과가 아니다.

### 단계별 보고서

- `docs/condition/CONDITION_INPUTS_STAGE_2_1_FINAL.md`: 입력 구성, 대상·보류 집계, 후보 참조 ID 충돌 수정 내역.
- `docs/condition/CONDITION_EXTRACTION_STAGE_2_2_REPORT.md`, `docs/condition/CONDITION_EXTRACTION_QUALITY_STAGE_2_2.md`: 초기 추출기 및 품질 진단 결과.
- `docs/condition/CONDITION_LOGIC_STAGE_2_3_REPORT.md`, `docs/condition/CONDITION_LOGIC_RULES_STAGE_2_3.md`: 논리 후보 생성 결과와 적용 규칙.
- `docs/condition/CONDITION_GOLDSET_STAGE_2_4_REPORT.md`, `docs/CONDITION_GOLDSET_REVIEW_GUIDE_V1.md`: 검수 패킷 구성, 상태, 사람 검수 기준.
- `docs/condition/CONDITION_SCHEMA_V1.md`: 공통 조건 스키마 설명.
- `docs/data/G2B_SUPPORT_COMPATIBILITY_V1.md`: 나라장터 데이터의 호환성 및 원문 미확보 제한.

## 검증 결과와 다음 진행

- 2-5 신규 테스트 13개와 기존 회귀 테스트 54개, 총 67개 통과.
- 합성 검증은 조건 일치·누락·과잉·중복, 속성 불일치, 논리 연산자·순서·NOT 범위, 예외 대상, 미확정 상태 및 빈·미검수 정답 차단을 확인했다. 합성 결과는 실제 정확도로 보고하지 않는다.
- 개발용 사전 검증은 검수 완료 조건 0건, 논리 정답 0건으로 `NO_VERIFIED_COMPLETE_GOLDSET` 차단 사유를 냈다. 기준선 해시는 유효했다.
- 다음은 위 CSV/JSONL 검수 패킷에 사람이 원문 근거 기반으로 검수 결과를 입력하고, `tools/ingest_condition_gold_reviews.py`로 정합성을 검사하는 작업이다. 검수 완료 뒤에만 평가기의 실제 점수 실행이 가능하다.

## 작업 트리 참고

작업 기록 작성 시점에 Git에는 여러 미커밋 변경 및 미추적 파일이 있었다. 이 문서는 변경 파일을 정리하는 용도이며 파일을 stage하거나 커밋하지 않았다. 상태 확인 없이 변경 전체를 한 번에 커밋하지 말고, 이후 작업에서는 파일별 소유 범위를 확인한다.
