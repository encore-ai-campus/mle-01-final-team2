# 조건 추출·논리 구조 정답셋 검수 가이드 v1

## 검수 파일과 분리

2-4단계 자료는 `data/goldsets/conditions/v1/20261125/development/`와 `evaluation/`에 물리적으로 분리한다. 개발용 30건에는 기존 조건·논리 후보가 참고 자료로 포함된다. 평가용 20건은 대표 표본의 원문, 출처, 빈 정답 입력란만 포함한다. 평가 CSV에는 기존 후보 열조차 두지 않는다. 평가 정답은 규칙·프롬프트 개발에 사용하지 않는다.

합성 논리 테스트는 실제 표본과 결합하지 않는다. 스키마 예시와 합성 테스트는 `sample_data/conditions/synthetic-condition-samples.jsonl`에 따로 유지한다.

## 원문 범위와 정답 작성

각 입력의 `source_text`는 표본용으로 확보된 조건 원문 구간이다. 공고 전체 조건 원문이 완전하다는 보장이 없으므로 `source_text_completeness=UNKNOWN`, `whole_notice_conditions_complete=false`를 유지한다. 검수자는 이 범위 안에서 확인 가능한 자격·제외·우대 조건을 빠짐없이 추가한다. 원문 밖의 첨부 문서나 추정 정보로 보완하지 않는다. 전체 조건 없음은 판정할 수 없고, “제공된 구간에 조건 문구 없음”과 “공고 전체에 조건 없음”을 혼동하지 않는다.

각 조건은 기존 공통 조건 스키마의 필드에 맞춰 작성한다. `gold_condition_id`는 추출기 ID와 별개 namespace를 쓴다. ID는 `notice_id`, 조건 유형, 원문 위치, 원문 구간을 고정 JSON 직렬화한 SHA-256 해시의 Base32 앞 15바이트로 만든다. 원문 위치가 수정되면 ID도 재생성한다. 근거는 `source_text[start_char:end_char]`와 정확히 같아야 한다.

기존 공통 condition 레코드로 내보낼 때 `gold_condition_id`는 `condition_id`, `category`는 `category_id`, `evidence_reference`는 `source.location`, `source_field`는 `source.source_field` 및 `source.normalized_path`, 원문 구간은 `raw_text`와 `source.evidence_text`로 대응한다. 적용 대상은 `applicability_scope`에 별도 기록하고, 공통 스키마 변환 시 의미를 보존할 수 없으면 `qualifiers` 또는 추가 필드 검토 대상으로 둔다. `review_status`는 기존 vocabulary를 그대로 사용한다. 검수 행의 `decision_possible`은 구조화 가능성 메모이며 운영 필드 `decision_eligible`로 복사하지 않는다. 검수자가 확인하지 않은 기본값을 자동으로 채우지 않는다.

추출기 후보의 정답 대응은 `candidate_alignments`에 둔다. `MATCH`, `PARTIAL_MATCH`, `FALSE_POSITIVE`, `DUPLICATE`, `UNRESOLVED`를 사용한다. 한 정답이 후보 여러 개에 대응하는 경우에도 중복 예측은 각각 표시한다. 누락 조건은 `gold_conditions`에 새 정답으로 넣고 후보 대응을 만들지 않는다. 목적·지원 내용·신청 방법은 자격 조건으로 잘못 넣지 않는다.

조건의 `decision_possible`는 해당 문구를 구조화할 수 있는지 기록하는 검수 속성일 뿐 서비스 신청 자격 판정을 허용하지 않는다. 근거만 확인되고 의미를 확정할 수 없으면 `UNCLASSIFIED` 또는 `UNDECIDABLE`로 남기고 의견을 쓴다.

## 논리 구조와 예외

조건을 먼저 검수한 뒤 `condition_gold_ids`로 정답 조건을 연결한다. `gold_logic_roots`는 공통 스키마의 `logicalExpression` 형식을 따른다. `CONDITION_REF.condition_id`에는 대응하는 `gold_condition_id`를 넣는다. AND/OR/NOT와 중첩 그룹은 원문의 명시적 연결 및 문맥 근거가 있을 때만 사용한다. 문장 나열만으로 AND/OR를 가정하지 않는다.

예외·단서는 `gold_exceptions`에 별도로 기록한다. 원문 구간을 정확히 보존하고, 대상 조건을 특정할 수 있을 때만 `linkage_status=LINKED`와 gold ID를 입력한다. 대상이 모호하면 빈 대상 목록과 `UNRESOLVED`를 유지하고 이유를 적는다. 논리 관계 자체를 확정할 수 없는 경우 `unresolved_relations`에 근거와 사유를 기록한다. 우대 혜택은 `gold_benefits`에 원문·값·단위와 적용되는 우대 gold ID를 따로 기록하고, 우대 조건과 자격 조건을 합치지 않는다.

## 상태·수정 이력

초기 패킷은 모두 `review_status=UNREVIEWED`, `adjudication_status=PENDING`이다. 검수를 완료한 사람만 `review_status=VERIFIED`와 완료 상태를 입력하고 `reviewer`, ISO 8601 `reviewed_at`, 의견 및 `revision_history`를 남긴다. 판단 불가와 평가 제외는 각각 `UNDECIDABLE`, `EXCLUDED`로 표시하고 사유를 기록한다. `VERIFIED`는 원문 기준 검수가 끝났다는 뜻이며 신청 자격 판정에 바로 사용할 수 있다는 뜻이 아니다.

JSONL을 기준 입력으로 수정한다. CSV는 읽기·검토 편의용 산출물이다. 수정된 JSONL에 대해 다음 명령을 실행하면 스키마, 원문 위치, ID, 공고·논리·예외 참조를 검증한다. 검수 미완료 행은 골드 결과로 내보내지 않는다.

```powershell
.venv\Scripts\python.exe tools/ingest_condition_gold_reviews.py --split development
.venv\Scripts\python.exe tools/ingest_condition_gold_reviews.py --split evaluation
```

## 평가 정책 (2-5단계 사전 정의)

### 조건 추출

- 평가 모집단은 검수 완료(`VERIFIED`)된 공고·조건만으로 구성한다. 미검수, 판단 불가, 제외 건수를 출처와 함께 별도 보고한다.
- 대응은 공고 단위 1:1 매칭으로 한다. 조건 유형, 카테고리, 필드, 연산자, 값, 타입, 단위 및 기준일이 의미상 일치하고 동일 근거를 가리켜야 전체 조건 일치로 계산한다. 한 예측을 두 정답에 중복 대응하지 않는다.
- 문자열은 Unicode NFKC 정규화, 공백 접기, 앞뒤 공백 제거 후 비교한다. 숫자는 Decimal로 정규화한다. 단위 변환은 검수된 동일 차원 단위표가 있을 때만 허용한다. 의미가 달라질 수 있는 표현을 자동 동의어 처리하지 않는다.
- TP는 1:1 정답 대응 예측, FP는 대응되지 않은 예측(중복 후보 포함), FN은 대응되지 않은 정답으로 정의한다. Precision=TP/(TP+FP), Recall=TP/(TP+FN), F1은 두 값의 조화평균이다. 분모가 0이면 0으로 대체하지 않고 N/A로 표시한다.
- 유형·카테고리별 Precision/Recall/F1은 해당 축에 대해 같은 1:1 대응을 집계한다. 필드별 정확도(유형, 연산자, 값/타입, 단위, 기준일)와 원문 span 정확도는 조건 일치율과 분리해 보고한다.
- 의미상 일부만 일치하는 후보는 전체 정확 조건으로 세지 않는다. 사람 검수 대응 표기 `PARTIAL_MATCH`는 별도 오류 분석에 포함한다.

### 논리 구조

- 논리 구조 비교는 정답 조건 ID를 예측 조건의 1:1 대응으로 치환한 후 수행한다.
- AND와 OR는 교환 법칙을 적용해 자식 노드의 canonical 표현을 정렬한다. 같은 연산자의 중첩은 평탄화해 괄호 표기 차이를 허용한다. 서로 다른 연산자 경계와 NOT의 범위는 보존한다.
- 논리 연산자 정확성, 부모·자식 엣지 F1, 그룹 전체 canonical 완전 일치율, 중첩 구조 일치율, NOT scope, 예외 연결 정확도를 각각 보고한다.
- 예외 대상 누락·오연결은 정확 일치가 아니다. 미확정 정답에서 시스템이 확정 연산자를 낸 경우 오류로 집계한다. 시스템이 미확정을 냈을 때 정답도 미확정이면 미확정 처리 일치다.
- 실제 공고 정답 통계와 합성 테스트 통계를 합산하지 않는다. 이번 단계에서는 사람 정답이 없으므로 Precision/Recall/F1 또는 논리 정확도 수치를 산출하지 않는다.

## 남은 검수 작업

개발용 30건과 평가용 20건 모두 현재 검수 대기다. 30건 개발 패킷은 후보 탐색과 규칙 개선에 쓸 수 있다. 평가용 원문 패킷은 별도 검수자 또는 블라인드 절차로 독립 주석한 뒤 고정하고, 2-5단계의 최종 평가 전까지 튜닝 대상에서 제외한다. 필요 시 나머지 개발 표본 50건만 추가 검수한다.
