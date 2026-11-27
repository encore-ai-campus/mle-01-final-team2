# 2-4E 최종 의미 보완 및 사람 승인 반영

## 5건의 필드 수정

| 공고 | 실제 수정값 | 남은 한계 |
|---|---|---|
| BIZINFO:125974 | 예비창업자·교육생의 `applicability_scope`를 가족 요건 적용 범위 `UNKNOWN`으로 수정. `unresolved_relations`에도 범위 미확정을 기록 | 진주시 지역 조건이 개인 주소인지 사업장인지 미확인 |
| BIZINFO:126490 | 지식재산 종류·유효성·보유·희망국가의 `applicability_scope`에 **동일 권리** 요건을 기록하고 미확정 관계 추가 | v1.1 AST가 권리별 동일성 연결을 실행할 수 없어 판정 비허용 |
| BIZINFO:126715 | 업력 `reference_date_type=APPLICATION_END`, `temporal_constraint.anchor_event=UNKNOWN`, `anchor_date_known=false` | 원문상 접수마감일이라는 이벤트는 확인됨. 정확한 날짜와 대응하는 anchor enum은 없음. 국내기업 전용 범위 유지 |
| KSTARTUP:177051 | 업력 `reference_date_type=PUBLICATION_DATE`, `anchor_event=UNKNOWN`. 창업일 2019-03-26~2026-03-25의 기존 보조 근거 유지 | 공고일의 실제 날짜와 대응하는 anchor enum은 미확인. 업력 조건 중복 생성 없음 |
| KSTARTUP:177447 | 연령·거주 기준의 `reference_date_type=UNKNOWN`, `anchor_event=APPLICATION`. 병역 예외 `effect_confirmed=true`, 상한 40/41/42세 유지 | 신청일을 접수 시작일로 오인하지 않음. 원문상 연장 효과는 명확하지만 `effect=UNKNOWN`, `application_mode=UNKNOWN`은 실행 가능한 연령 상한 대체 효과의 표현 한계. `decision_possible=false` 유지 |

미확정 관계 또는 표현 한계가 있는 조건은 개별 조건이 명시적이어도 전체 신청 자격을 TRUE로 확정할 수 없습니다. 향후 v1.1 의미 평가기는 동일 권리 연결, 조건부 범위, 실제 신청일 이벤트 및 연령 상한 대체 효과의 판정 정책을 정의해야 합니다. 미확정 관계를 정확한 AND/OR 정답으로 간주하지 않습니다.

## 승인 범위

- 2026-11-26 사람 승인: 묶음 1·2·5의 15개 공고, 실제 JSONL 기준 50개 조건.
- 기존 사전 검수 승인 5개 공고·33개 조건을 합쳐 누적 20개 공고·83개 조건.
- 묶음 3·4의 10개 공고·33개 조건은 `UNREVIEWED / PENDING` 유지.
- 승인 범위는 제공된 발췌문의 조건·논리·예외 의미입니다. 원문 완전성과 실제 신청 가능 여부를 확정하지 않았고 `decision_possible=false`를 유지했습니다.
- 승인 전 사본과 SHA-256: `revision_history/preapproval_bundles125_20261126/SNAPSHOT_MANIFEST.json`. 2-4E 수정 전 사본: `revision_history/pre_2-4E/SNAPSHOT_MANIFEST.json`.
- 검수자 식별자는 기존 사전 검수 승인 기록의 `bgm3167`을 재사용했습니다. 실제 개인 신원에 대한 독립적 증빙은 저장소에 없습니다.

## 검증 및 산출물

기존 `ingest_condition_gold_reviews.py`는 조건·논리 스키마, 원문 span, GOLD ID 결정성, 논리 루트와 예외 참조를 검증한 뒤 승인 대상 15건만 `reviewed_condition_gold.jsonl`, `reviewed_logic_gold.jsonl`에 기록했습니다. `ingest_report.json`은 검수 완료 15건·미검수 10건으로 기록합니다. 기존 승인 5건과 v1 입력·추출·논리 기준선은 변경하지 않았습니다.
