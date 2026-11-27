# 논리 평가 adapter 전달 정합성

기존 P12 및 N0–N5 산출물을 읽기 전용으로 사용했다. 기존 strict evaluator와 조건 매칭 정책은 변경하지 않았다. 조건은 DEVELOPMENT 10공고·62정답으로 고정했다. 본 실험은 새로운 논리를 추출하지 않고 이미 생성된 구조의 평가 입력 연결을 개선한다.

## 실제 전달 경로

1. raw_llm_responses의 logic_sections는 proposal_index 기반 AND/OR/UNRESOLVED 제안이다. exceptions와 unresolved_relations가 별도로 존재한다.
2. 추출기의 _response_to_artifacts는 검증 후보 ID를 연결하고 탈락·보류 인덱스를 보존한다. logic_proposals에 원본/유효 논리 그룹, 예외, 미해결 인덱스·관계·완전성을 남긴다. 이 단계에서 일부 연산자가 UNRESOLVED로 바뀐 것은 기존 검증 정책이며 adapter가 바꾼 것이 아니다.
3. build_notice_set의 최상위 logic_sections[].root에는 실제 LOGICAL_GROUP과 children이 있다. 반면 condition_sets.*.logical_roots에는 동일 조건들이 평탄한 CONDITION_REF로 들어간다.
4. 기존 v1.1 evaluator의 _roots는 gold_logic_sections → logical_roots → condition_sets.*.logical_roots 순서다. 일반 logic_sections는 root 선택에서 읽지 않는다. P12 adapter는 notice_condition_sets를 그대로 전달했으므로 최상위 그룹이 있어도 평탄한 CONDITION_REF만 선택됐다.
5. _groups_and_edges는 LOGICAL_GROUP의 children에 대해서만 관계를 센다. 독립 CONDITION_REF는 그룹/edge 0개다. 따라서 기존 predicted_groups/edges=0은 데이터에 그룹이 없다는 증거가 아니었다. 별도의 section_semantics 코드는 logic_sections를 읽으므로 일부 구조 정보는 보이지만 주 group/edge 집계는 누락됐다.

관련 소스: tools/extract_condition_candidates_llm.py의 build_notice_set, tools/evaluate_condition_pipeline_v11.py의 _roots/compare_notice_logic, tools/evaluate_condition_pipeline.py의 _groups_and_edges/compare_logic.

## 개선 adapter v1

tools/condition_logic_evaluation_adapter.py는 존재하는 최상위 logic_sections.root를 그대로 평가 전용 logical_roots로 전달한다. v1 레코드처럼 최상위 sections가 없는 경우 기존 logical_roots/condition_sets roots를 유지한다. 조건·그룹 ID·연산자·children을 재분류하거나 평면 그룹을 중첩으로 조립하지 않는다. explicit GROUP_REF registry가 제공되는 합성 입력은 명시된 참조만 인라인하며, 실제 v1/v1.1은 재귀 inline AST를 사용한다.

기존 source record와 원본 proposal은 그대로 보존된다. 미해결 후보/예외/관계는 별도 audit에 유지하며 탈락 후보를 실행 가능한 CONDITION_REF로 생성하지 않는다. 모든 후보가 탈락한 그룹 5개는 unexecutable_groups에 원본 인덱스와 함께 남고 평가용 정상 그룹으로 생성하지 않는다. schema-invalid 응답의 원본 논리도 raw_logic_diagnostic에만 보존한다.

미해결 일부 자식이 있는 기존 UNRESOLVED 그룹은 생존한 참조를 가진 현재 AST 그대로 전달한다. 이것은 완전한 자격 판정으로 승인한 것이 아니다. 원본 제안과 unresolved indexes, 예외 적용 차단 상태는 audit에 함께 보존되고 decision_eligible=false다.

evaluation adapter record는 evaluator의 입력 transport이며 운영 notice-condition-set schema에 새로운 필드를 반영한 버전이 아니다. 운영 스키마/추출기에는 연결하지 않았다.

## 단계별 개수

| 단계 | L0 | L1 | L2 |
|---|---:|---:|---:|
| 원본 생성 논리 section/group 제안 | 20 | 20 | 20 |
| 원본 section membership links | 69 | 69 | 69 |
| 중간 스키마 통과 응답의 보존된 유효 proposal sections | 16 | 16 | 16 |
| 검증 후 실제 AST 그룹 | 10 | 10 | 10 |
| 검증 후 실제 AST parent-child edge | 43 | 43 | 43 |
| 평가 root로 전달된 그룹 | 0 | 10 | 10 |
| evaluator가 인식한 그룹 | 0 | 10 | 10 |
| 평가 root로 전달된 edge | 0 | 43 | 43 |
| evaluator가 인식한 edge | 0 | 43 | 43 |

원본의 section membership links와 AST edge는 같은 측정 단위가 아니다. 전자는 proposal_index 목록 및 명시된 child 참조 수이며 후자는 strict evaluator의 group-child 관계다. 20→16은 178507의 응답 전체 schema 거절에 따른 제외이며 원본 진단에는 보존됐다. 16→10은 전원 탈락한 그룹 5개와 검증 후 단일 CONDITION_REF인 section 1개의 차이다. 실제 저장 AST에 nested group은 0개이며 adapter는 이를 임의로 생성하지 않았다. 전체 공고별 흐름은 logic_transport_counts.csv에 기록했다.

## Strict 성능

| 실험 | 그룹 TP/FP/FN | 그룹 P/R/F1 | 관계 TP/FP/FN | 관계 P/R/F1 | 그룹 exact | 공고 AST exact |
|---|---|---|---|---|---|---|
| L0 P12 + 기존 | 0/0/24 | 미정의/0/0 | 0/0/71 | 미정의/0/0 | 0/24 | 0/10 |
| L1 P12 + 개선 | 0/10/24 | 0/0/0 | 0/43/71 | 0/0/0 | 0/24 | 0/10 |
| L2 N1 + 개선 | 0/10/24 | 0/0/0 | 0/43/71 | 0/0/0 | 0/24 | 0/10 |
| 규칙 v1 + 같은 계약 | 1/7/23 | 12.50%/4.1667%/6.25% | 2/19/69 | 9.5238%/2.8169%/4.3478% | 1/24 | 0/10 |
| 규칙 E + 같은 계약 | 0/7/24 | 0/0/0 | 0/19/71 | 0/0/0 | 0/24 | 0/10 |

L0 상세 평가 레코드 전체가 기존 strict_logic_and_condition_report.json과 일치했다. L1·L2는 이제 생성된 그룹과 관계가 FP로 인식된다. 이것은 연동 개선 효과이며 모델 생성 성능 개선이나 기존 구조의 악화가 아니다.

L0/L1 조건 F1은 2.1277%(TP1/FP31/FN61), L2는 6.3830%(TP3/FP29/FN59)로 보존됐다. 기존 evaluator의 condition id_map에는 exact뿐 아니라 partial 대응도 들어간다. N1에서 TP로 바뀐 두 조건은 L1에서도 partial로 연결돼 있었으므로 L2의 조건 개선이 이번 논리 점수에는 추가 영향을 주지 않았다. 이 정책을 바꾸지 않았다.

## 남는 실패의 구분

logic_failure_analysis.csv에는 공고별 복수 진단과 정답 그룹별 주원인을 따로 기록했다. L1/L2의 미일치 정답 그룹 24개 중 23개는 현재 evaluator id_map에도 연결되지 않은 정답 노드를 포함한다. 나머지 1개는 그룹 membership/분해 단위 차이다. 이는 edge FN 71개를 상호 배타적으로 분배한 결과가 아니며, 한 미일치 노드가 그룹 전체 signature와 모든 edge를 무효화할 수 있다.

- 조건 누락/표현 차이: 미지원 속성, 사업체/신청자 유형 차이, schema 거절로 조건 대응이 부족하다. 부분 연결까지 허용하는 기존 매핑에도 정답 참조가 남는다.
- 실제 구조 차이: 118182는 전체 AND, 유형 OR, 공통조건 AND의 평면 root 3개다. 정답의 공통 AND 내부 OR/예외 중첩으로 재해석하지 않았다. source는 평면이므로 이 차이는 모델 출력/분해 구조 문제다.
- 미해결 논리: 117168, 119490, 176813 등은 탈락·보류 후보 또는 원래 관계 미확정 때문에 UNRESOLVED를 보존한다. 이를 AND/OR 확정으로 바꿔 점수를 만들지 않았다.
- 그룹/관계 미지원: 예외의 실제 효과, 적용 범위 의미, 미해결 관계 의미, 완전성의 정답 여부, 시점별 논리 변화는 별도 v1.1 의미 계약 검토 전에는 미측정이다.

규칙 v1/E는 저장된 재귀 그룹이 collection.logical_roots에 있으므로 같은 transport fallback과 동일 strict 기준으로 구조 비교가 가능하다. 다만 규칙의 v1 레코드에는 LLM proposal_index 추적, v1.1 예외 효과/시점 메타데이터가 없어 의미 확장 성능까지 동일하게 비교할 수 없다.

## 미지원 및 보존

schema 통과 9개 응답에서 예외 객체 5개·미해결 관계 7개를 audit로 보존했다. CSV의 unsupported_semantic_objects=12는 이 두 종류만 합산한 값이다. 논리 완전성 레코드 9개와 phase-annotated sections 11개는 중복되는 메타데이터여서 별도 보고한다. 미지원 의미 항목을 새 TP/FP/FN이나 자동 성공으로 계산하지 않았다. 기존 evaluator가 반환하는 qualifier/예외 진단 값은 상세 파일에 남지만 이 실험의 의미 효과 점수로 사용하지 않는다.

v1/v1.1 common schema는 재귀 LOGICAL_GROUP/CONDITION_REF, group_id, operator, children을 정의한다. v1.1 logic-gold 스키마의 예외 효과·단계·관계 속성은 구조가 존재한다는 사실만으로 자동 의미 평가가 가능해지는 것은 아니다. 해당 정보의 연결·보존과 correctness scoring을 구분한다.

## 검증·재현

새 합성 테스트 19개가 AND/OR, 다중 root, 중첩, 공유 조건, 예외, 미해결, 전원 탈락, 없는 그룹/조건, 중복, 순환, orphan, ID 변경을 검사했다. 정확한 합성 AST는 기존 evaluator에서 기대 TP 및 exact를 얻었다. 기존 평가·정규화·추출 회귀를 포함한 133개 테스트가 통과했다. 동일 입력 반복 평가도 레코드 전체가 일치했다.

기존 P12·N0–N5·원본 논리·근거·span·날짜·temporal·개발용 골든셋·strict evaluator의 해시를 보존했다. 실제 참조 무결성 오류0, API0, 예산13/13·잔여0이다. 새 실험은 기존 출력에 덮어쓰지 않았다. 최종 코드 이전의 개발 중 실행은 별도 *_initial_run 및 *_diagnostic_revision 경로에 보관했다.

```powershell
.\.venv\Scripts\python.exe tools/run_logic_adapter_experiments.py --output-dir data/evaluations/conditions/v1.1/20261126/development/logic_adapter_reproduction
.\.venv\Scripts\python.exe -m unittest tests.test_condition_logic_evaluation_adapter -q
```

기존 출력 경로는 덮어쓰기를 거부한다.
