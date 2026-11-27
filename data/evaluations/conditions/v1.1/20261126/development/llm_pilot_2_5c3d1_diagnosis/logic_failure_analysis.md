# 실제 논리 측정값과 실패 원인

P12 strict_logic_and_condition_report.json 전체를 같은 입력과 기존 evaluate_records로 재현하여 레코드 일치를 확인했다.

| 지표 | 실제 저장된 결과 |
|---|---|
| 관계/edge | TP 0 / FP 0 / FN 71. Precision 미정의, Recall 0, F1 0 |
| 논리 그룹 exact | correct 0 / predicted 0 / gold 24. Precision 미정의, Recall 0. 별도 group F1은 저장되지 않음 |
| 공고 구조(AST) exact | 0/10; notice_structure_exact가 모두 false |
| 예외 연결 | TP 0 / FP 0 / FN 4. Precision 미정의, Recall/F1 0 |
| 우대 benefit 연결 | TP 0 / FP 0 / FN 2 |
| 예외 효과 | 모든 공고 UNSUPPORTED_V1_0. 실제 효과 정확도 미측정 |
| 미해결 관계 의미 | 모든 공고 UNSUPPORTED_V1_0. 실제 의미 정확도 미측정 |

관계 TP/FP/FN은 저장된 공고별 수치의 합계다. Precision을 0으로 채우지 않았다. nested_structure_exact=true인 단순 공고는 양쪽 nested 그룹이 0인 경우이므로 전체 AST 성공으로 세지 않았다.

## 별도 원인

1. 조건 연결 실패: 조건 exact TP가 1개뿐이다. 조건이 없거나 대응되지 않으면 정상 논리 결합도 연결 점수를 얻기 어렵다. evaluator id_map에는 부분 일치 대응도 들어가므로 조건 exact 하나만으로 모든 논리 실패를 설명할 수는 없다.
2. 평가 입력 연결: 최상위 logic_sections의 그룹이 _roots()에 전달되지 않고 condition_sets의 평탄한 참조가 사용된다. 모델의 실제 그룹이 없어져 predicted_groups=0인 상태다. 이 상태의 0점을 순수 모델 결합 정확도라고 해석하면 안 된다.
3. 실제 모델 구조 차이: 118182는 전체 조건 AND, 사업체 유형 OR, 공통조건 AND를 별도 평면 그룹으로 제안한다. 정답의 공통 AND 안에 대안 OR/예외가 들어가는 중첩과 다르다. 176813은 모델부터 자격 결합을 UNRESOLVED로 제안했다. 이 부분은 평가 입력을 연결해도 원래 모델 구조의 불확실성이 남는다.
4. 예외/미해결 관계 표현: 원본 exceptions 및 unresolved_relations는 논리 제안 파일에 남지만 gold_exceptions와 condition_ids 기반의 평가 계약으로 전달되지 않는다. 원본이 없다고 단정하지 않는다. 탈락한 예외 대상은 검증 후보로 승격해서도 안 된다.

9개 스키마 통과 응답의 논리 제안을 확인했다. 모두 원본 예외 객체와 원본 미해결 관계가 보존됐고 그룹 개수도 유지됐다. 탈락·보류 후보는 unresolved_condition_indexes에 보존되며 예외 대상 미해결 시 application_allowed=false다. 178507은 스키마 거절이므로 원본 raw만 보존되고 실행 가능한 논리 산출물은 없다. 공고별 상세는 diagnosis_summary.json의 logic_preservation에 기록했다.

권장 후속 작업은 평가 adapter의 root/예외/관계 계약 테스트다. 모델 결합 개선과 분리하여 기존 응답으로 검증하고, 수정된 지표는 기존 결과를 보존한 새 평가 버전에서 보고해야 한다. 이번 단계에서는 점수나 adapter를 수정하지 않았다.
