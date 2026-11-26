# 2-4단계 정답셋 검수 자료 구축 결과

## 완료 상태

자동 검수 자료와 검증·반영 도구를 생성했다. 사람의 원문 검수는 아직 제공되지 않았으므로 정답셋은 확정되지 않았다. 현재 검수 완료 행과 실제 gold condition은 0건이며, 성능 수치도 산출하지 않았다.

## 구성

| 집합 | 공고 수 | 조건 검수 | 논리 검수 | 기존 추출/논리 결과 표시 |
|---|---:|---:|---:|---|
| 개발 | 30 | 30 | 30 | 표시 |
| 독립 평가 | 20 | 20 | 20 | 미포함 |
| 합성 회귀 | 기존 별도 관리 | 기존 별도 관리 | 기존 별도 관리 | 실제 공고 평가와 분리 |

개발과 평가 공고 ID 교집합은 0이다. 평가용 JSONL 및 CSV는 원문 기반 입력만 담고 기존 후보, 관계 출력, 진단 자료를 포함하지 않는다. 평가용 생성 경로는 `representative_samples.jsonl`의 `EVALUATION` 원문만 사용한다. 나라장터는 기존 원문 미확보 정책에 따라 제외했다.

검수 원문은 표본용 조건 텍스트이며 전체 공고 조건의 완전성이 확인되지 않았다. 모든 행은 `source_text_completeness=UNKNOWN`, `whole_notice_conditions_complete=false`, `review_status=UNREVIEWED`, `adjudication_status=PENDING`이다. 따라서 조건 미확인을 조건 없음으로 만들지 않는다.

## 기준선 보존

기존 2-2/2-3 결과를 수정하지 않았다. `baseline_manifest.json`에 기존 추출 98건, 논리 그룹 후보 25건 등 기준선 카운트 및 입력 파일 SHA-256을 기록했다. 기존 49개 테스트 통과 상태도 기준선 메타데이터에 남겼다.

## 추가·수정 파일

- `tools/build_condition_gold_review.py`: 개발 30건/평가 20건 분리 검수 패킷과 기준선 manifest 생성
- `tools/ingest_condition_gold_reviews.py`: 수정한 JSONL 검수 자료의 스키마·ID·원문 span·참조·상태 검증, 검수 완료 행만 별도 반영
- `schemas/conditions/condition-gold-review-v1.schema.json`: 조건 주석 검수 입력 구조
- `schemas/conditions/logic-gold-review-v1.schema.json`: 논리·예외 검수 입력 구조
- `tests/test_condition_gold_review.py`: 분리, 블라인드, 골드 ID, 무검수 미반영, 개인정보 테스트
- `docs/CONDITION_GOLDSET_REVIEW_GUIDE_V1.md`: 작성·검수 및 평가 매칭 기준
- `data/goldsets/conditions/v1/20261125/`: 기준선, 분리된 JSONL/CSV 패킷, 반영 보고서

정답 condition 구조는 새 운영 스키마를 만들지 않고 기존 공통 condition 필드와 조건 ID를 재사용한다. 주석 입력 스키마는 검수 중 필요한 `gold_condition_id`, 수정·추가 조건, 누락 후보, 기존 후보 대응을 담는다. 논리 트리 참조는 gold ID를 기존 스키마의 `CONDITION_REF.condition_id` 값으로 사용한다. Gold ID는 extractor namespace와 분리된 `GOLD:` 결정적 ID다.

## 검증 결과

- 검수 입력 JSON Schema: 개발 60행, 평가 40행 통과
- split 분리 및 교집합: 0
- 평가 자료의 추출기·논리 후보 필드: 0
- 개인정보 스캔: 개발·평가 검수 입력에서 발견 0
- 검수 상태 자동 VERIFIED: 0
- 검수 완료 골드 조건 및 논리 기록: 0
- 입력 수정 후 재검증 경로: `tools/ingest_condition_gold_reviews.py --split {development|evaluation}`
- 테스트: 신규 5개 및 기존 49개, 총 54개 전체 통과 (`Ran 54 tests in 81.523s`)

## 평가 방식 및 2-5단계

Precision/Recall/F1, 의미 조건 1:1 매칭, 필드별 정확도, 근거 span, canonical 논리 트리, 예외 링크 및 미확정 관계 점수 기준은 `CONDITION_GOLDSET_REVIEW_GUIDE_V1.md`에 사전 정의했다. 검수 완료 정답이 없는 현재는 성능 측정할 수 없다.

자동 자료 준비는 끝났다. 2-5단계의 실제 평가 점수 산출은 개발용 30건의 원문 검수와 블라인드 평가용 20건의 독립 검수·정답 확정 이후 가능하다. 평가용 정답은 개발 규칙·프롬프트 튜닝에 사용하지 않는다.
