# 기준선 무결성 진단

작성일: 2026-11-26

## 결론

고정된 조건 정답, 예측, 설정 및 v1.1 평가기로 기준선 평가를 다시 계산했다. TP/FP/FN과 Precision·Recall·F1은 고정 요약과 일치했다. `failure_analysis.csv`는 manifest가 고정한 바이트와 다르며, 재생성 결과와의 차이는 줄바꿈이나 BOM만으로 설명되지 않는다. 이 파일은 점수 기준선의 원본 진단 자료로 검증할 수 없으므로 현재 파일이나 manifest를 덮어쓰지 않았다.

## 파일 및 해시

| 대상 | 크기 | SHA-256 |
|---|---:|---|
| manifest가 기대한 `failure_analysis.csv` | 111,613 bytes | `f4c8594943c1e280d91ea607467a2d3aca55f68aed281aa720ed6160a0156e6e` |
| 현재 baseline 파일 | 112,657 bytes | `fcb0651a69d9fd73c9e2e31af0dd7e89688acfe2900211b83cafc62b1f8d2452` |
| 고정 입력에서 별도 재생성 | 143,788 bytes | `5f6db9a008d3096200f929e842cbdf314e1a6aae0a55aeca56fbe6f36f341418` |
| 고정 `evaluation_summary.json` | — | `4d194c7267374c7e6416a9a9e02eaf3603724474bc2ebcd2da9adf0154848fb2` |

재생성 CSV는 `baseline_recheck/failure_analysis_regenerated.csv`에 보존했다. 비교 기계 판독 자료는 `baseline_recheck/baseline_csv_comparison.json`이다.

## 의미 및 직렬화 비교

- 기존 및 재생성 CSV 각각 189행이며 컬럼 구성과 행 식별키 189개가 같다. 빠지거나 추가된 행은 없다.
- 유형별 행 수도 동일하다: FN 106, FP 36, Partial Match 18, Logic Failure 29.
- 전체 행에서 동일한 바이트/필드 행은 없었다. 다른 필드는 `differences` 171행, `evidence_status` 29행, `cause_confidence` 189행, `source_excerpt` 29행, `failure_cause` 36행이다.
- 두 파일 모두 UTF-8 BOM과 마지막 개행을 가진다. 각 행 구분의 CRLF 수는 190으로 같지만, 인용된 진단 문자열 안 LF 수는 기존 677, 재생성 745였다. 따라서 인코딩 표식·행 정렬만의 차이가 아니다.
- 재평가 요약의 점수는 고정 요약과 같고, 고정 요약 파일 해시도 그대로다. 즉 점수 입력의 변화는 관측되지 않았다.

## 원인 분류 및 영향

분류: `DIAGNOSTIC_ROW_CONTENT_DIFF` (진단 행 내용 차이). 원래 CSV를 manifest 생성 후 누가/어떤 과정으로 바꾸었는지는 저장소 기록만으로 입증하지 못했다. 현재 CSV의 원인 주석·근거 진단 값이 재생성 값과 달라진 점은 관측 사실이며, manifest 고정 뒤 진단 주석이 변경되었을 가능성이 있지만 이는 추정이다. 순수 직렬화 차이로 판정하지 않는다.

기존의 TP 10, FP 36, FN 106, Precision 21.7391%, Recall 8.6207%, F1 12.3457%는 별도 재실행으로 재현되었다. 그러므로 이 파일 불일치가 점수를 바꿨다는 증거는 없다. 다만 과거 `failure_analysis.csv`의 원래 행별 설명을 검증할 수 없으므로 해당 CSV를 권위 있는 실패 원인 정답 자료로 사용하지 않는다. 새로 생성된 비교용 분석물은 실험 경로에서 별도 사용한다.

## 보존

baseline_v1 파일, manifest, 골든셋 및 예측 기준선은 수정하지 않았다. 모든 재생성 자료와 실험 결과는 `legacy_augmented_2_5c2b/` 아래에 분리했다.
