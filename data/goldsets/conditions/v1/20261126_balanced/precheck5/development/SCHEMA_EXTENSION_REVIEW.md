# 기존 스키마 확장 검토 목록 (미변경)

| 표현 필요 | 현재 초안에서의 임시 보존 | 필요한 확장 |
|---|---|---|
| 신청 당시 자격과 선정/입주 이후 의무 구분 | `applicability_scope` 자연어 값 | `condition_phase` enum (APPLICATION, SELECTION, POST_SELECTION, POST_MOVE_IN 등) |
| 신청일/입주신청일/입주개시일/계약체결일 기준 | 기준일이 명시되면 reference_date, 상대 이벤트는 scope/comment | event anchor 및 relative duration 구조(예: event=OCCUPANCY_START, offset=30 days) |
| 178507의 업력 제한과 2019-07-08 각주 근거를 동일 조건에 연결 | 한 gold condition; 보조 span 좌표는 review_comment | condition당 `evidence_references[]` 및 evidence role (primary/supporting) |
| 전국(지역 제한 없음) | 판정 조건에서 제외하고 문맥으로 기록 | `ANY`/`NO_RESTRICTION` operator 또는 비제약 context 표현 |
| 118927 공고명 [강원] + 본문 도내 | 조건 본문 span + comment/title 출처 표시 | 여러 source_field에 걸친 provenance reference |
| 118182의 일부 IN 대안에만 적용되는 비영리 예외 | 세 유형 EQ를 별도 condition으로 만들어 예외 링크 | 예외가 IN 집합 일부에 적용되는 subset/value-level scope |
| 법령 준용으로 발췌 밖에 있는 세부 제외조건 | EXCLUSION + decision_possible=false | 외부 문서 참조 상태와 세부 원문 근거 연결 |
| 정성요건의 조건 유형과 판정가능성 분리 | ELIGIBILITY와 decision_possible=false 병행 | schema상 표현 가능; 별도 확장 불필요 |

이번 수정은 기존 schema만 사용했으며 공통 schema는 변경하지 않았다.

## 2차 의미 검수 추가

- 논리 루트 배열에는 `ELIGIBILITY`/`EXCLUSION` 종류와 신청·선정·입주 이후 단계 필드가 없다.
- `gold_exceptions.applies_to_gold_ids`는 대상 연결만 기록한다. 기본 조건 완화나 특정 입주 이력의 제외 효과는 표현하지 못한다.
- 조건 하나에 제목과 본문, 본문과 각주처럼 여러 근거 위치를 구조적으로 연결할 수 없다.
- 상대 기한의 기준 이벤트·기간 및 판정 결과 `UNKNOWN`을 나타낼 구조가 없다.
- `EXISTS`/`NOT_EXISTS`의 입력 사실 모델과 `EXCLUSION=TRUE`가 제외라는 판정 규약이 필요하다.
