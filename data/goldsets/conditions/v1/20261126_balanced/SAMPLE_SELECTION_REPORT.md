# 개발용 검수 표본 균형 조정 보고

- 난수 시드: `20261126`
- 선정 알고리즘: within each source, seeded shuffle and greedy maximum feature coverage; fill to quota 15
- 개발 모집단: 80건 (BIZINFO 40, KSTARTUP 40)
- 기존 검수 30건: BIZINFO 28, KSTARTUP 2
- 신규 검수 30건: BIZINFO 15, KSTARTUP 15
- 평가 20건 ID 변경: 없음; 개발 중복: 0
- source_text UTF-8 decode 실패/U+FFFD: 0 (개발 80건)

선정은 출처별 quota를 고정하고, 각 출처 안에서 seed 기반 셔플 순서에 따른 greedy maximum coverage로 미추출·단일/복수 후보·제외·우대·관계·단서 특성을 넓혔다. 모두 포함되지 않은 결측 유형은 다음과 같다.

- NO_EXTRACTION: 8건
- LOGIC_UNRESOLVED: 30건
- SINGLE_CANDIDATE: 9건
- MULTIPLE_CANDIDATES: 13건
- RELATION_REVIEW: 13건
- QUALIFIER: 3건
- EXCLUSION: 3건
- PREFERENCE: 2건

표본 모집단의 원문 완전성은 모두 `UNKNOWN`이며, 상세 공고문 참조 등 발췌문 밖 기준은 정답 없음으로 간주하지 않았다.

## 기존 표본 비교

전체 80건별 신규/기존 선택 여부, 공고명, 추출 후보 수·유형 및 검수 다양성 표식은 `development_sample_comparison.csv`에 있다. 기존 ID 목록은 `selection_report.json`에 보존했다.

## 미포함/제한 유형

- 복합 조건이면서 논리 결합이 명시되지 않는 유형: 후보는 포함되었으나 AND/OR를 자동 확정하지 않고 미확정으로 남겼다.
- 원문 완전성 확인: 80건 모두 발췌 자료라 `UNKNOWN`; 전체 공고 완전성으로 분류할 수 없다.
- 후보 상충: relation/qualifier review 신호가 포함되었으나 기존 후보가 모두 실제 상충을 뜻하지 않아 상충 확정 사례 수로 보고하지 않는다.
- 명시적 후보 상충 그룹: 기존 `conflict_review.jsonl`은 0건이므로 실제 상충 사례를 표본 요건으로 억지 포함하지 않았다.
- 의미상 조건 없는 공고: 미추출 후보가 있는 사례를 선정했으며, 조건 부재 사례로 라벨링하지 않는다.

## 5건 사전 검수 선정

|공고 ID|출처|유형|
|---|---|---|
|`KSTARTUP:177469`|K-Startup|단일 자격 기준(연령)|
|`KSTARTUP:176813`|K-Startup|복합 조건, 우대 후보, 논리 관계 검수|
|`BIZINFO:PBLN_000000000118927`|기업마당|조건 미추출|
|`KSTARTUP:178507`|K-Startup|제외·예외·단서|
|`BIZINFO:PBLN_000000000118182`|기업마당|비영리 허용 단서, 복합/미확정 관계|

표본 선정 비교와 선정 기준은 `selection_report.json` 및 CSV에 보존했다. 신규 패킷은 별도 `20261126_balanced` 경로에 작성했으며 20261125 패킷/평가 split은 덮어쓰지 않았다.

## 검수 자료 검증

- 5건 원문: strict UTF-8 정상, U+FFFD 0, 모든 조건·예외 evidence span 일치
- 조건·논리 JSON Schema 오류: 0
- 개발/평가 중복: 0; 개발 80건과 평가 20건 분할 변경: 0
- 평가 패킷의 원본·신규 SHA-256: 동일
- 기존 기준선 입력 5개 SHA-256: 동일
- ingest 도구: 5건 통과, 승인/반영 조건 0건, 사람 검수 주장 없음
- `tests.test_condition_gold_review`: 5 tests passed
- 생성기 재사용을 위해 선택된 개발 ID JSON 입력 옵션을 추가했다. 기본 동작은 기존 30건 목록을 그대로 사용한다.

5건별 Markdown 및 기존 호환 CSV/JSONL은 `precheck5/development/` 아래에 있다. 5건 독립 ingest 검증용 복사본 평가 packet은 `precheck5/evaluation/`에 있으며 원본 평가 데이터는 수정하지 않았다.
