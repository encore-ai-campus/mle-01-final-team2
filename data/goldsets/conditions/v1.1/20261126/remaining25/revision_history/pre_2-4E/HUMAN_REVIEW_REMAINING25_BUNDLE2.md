# Development review bundle 2/5

Draft only: UNREVIEWED / PENDING. Source is a condition excerpt; completeness of the whole notice remains UNKNOWN.

## BIZINFO:PBLN_000000000119490 (BIZINFO)

### Notice title
2026년 청년일자리도약장려금 참여기업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
5인 이상 우선지원대상 기업
- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후
- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후
※ 자세한 지원대상 공고문 참조
```

### Existing v1 candidates
- `CND:E6OXO4IHXZRGP4APAN42BAEP` 서울특별시 [BUSINESS_LOCATION] ? PARTIAL_MATCH; gold: GOLD:4CNJ6NBNNIINQ3U2XXXGKKD6
- `CND:44GR2V7FN67RRVDEF7ALASB5` 인천광역시 [BUSINESS_LOCATION] ? PARTIAL_MATCH; gold: GOLD:4CNJ6NBNNIINQ3U2XXXGKKD6
- `CND:3ZW23MK72GLPRBMEMBDWZY6Q` 경기도 [BUSINESS_LOCATION] ? PARTIAL_MATCH; gold: GOLD:4CNJ6NBNNIINQ3U2XXXGKKD6
- `CND:OOK7DGIRZ364DCFZEWUJQYHO` 제외 [None] ? FALSE_POSITIVE; gold: none

### Gold condition draft
- `GOLD:ZOC6BM43M3Z7H3ZQD73ZTCWK` **ELIGIBILITY / EMPLOYEE_COUNT / EMPLOYEE_COUNT / GTE 5** ? 5인 이상 (span 0:5; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:5ME3M7JJ3EHSU4EDM3RBR67A` **ELIGIBILITY / SUPPORTING_COMPANY_STATUS / SUPPORTING_COMPANY_STATUS / EQ "우선지원대상기업"** ? 우선지원대상 기업 (span 6:15; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:4CNJ6NBNNIINQ3U2XXXGKKD6` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / IN ["서울특별시", "인천광역시", "경기도"]** ? (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업 (span 18:55; decision_possible=False; v1 comparison=PARTIAL_MATCH,PARTIAL_MATCH,PARTIAL_MATCH)
- `GOLD:BNSAZ3SCURPTDENMJRN3CU2M` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / NOT_IN ["서울특별시", "인천광역시", "경기도"]** ? (비수도권) 수도권 제외한 지역에 소재하는 기업 (span 96:122; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:DQ63JDCGDQXMWOWP67DEFR26` **ELIGIBILITY / HIRE_STATUS / HIRE_STATUS / UNRESOLVED ** ? 취업애로청년을 정규직으로 채용 후 (span 75:93; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 채용 이후 조건. 신청 시 평가 여부와 정확한 단계 미확인.
- `GOLD:SIL562G3O4GDPSSAVOQYZQPR` **ELIGIBILITY / HIRE_STATUS / HIRE_STATUS / UNRESOLVED ** ? 청년을 정규직으로 채용 후 (span 142:156; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 비수도권 채용 문구. 신청 시 평가 여부와 정확한 단계 미확인.

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:6491F5E3F72B410A73E6A1C4", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:ZOC6BM43M3Z7H3ZQD73ZTCWK"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:5ME3M7JJ3EHSU4EDM3RBR67A"}, {"node_type": "LOGICAL_GROUP", "group_id": "AST:11BCEA2EF68E39AEE2A458FA", "operator": "OR", "children": [{"node_type": "LOGICAL_GROUP", "group_id": "AST:DF6239466845E91C4F8F7922", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:4CNJ6NBNNIINQ3U2XXXGKKD6"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:DQ63JDCGDQXMWOWP67DEFR26"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}, {"node_type": "LOGICAL_GROUP", "group_id": "AST:4E7B1E9C535C8BF959E8EF6A", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:BNSAZ3SCURPTDENMJRN3CU2M"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:SIL562G3O4GDPSSAVOQYZQPR"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## BIZINFO:PBLN_000000000122876 (BIZINFO)

### Notice title
2026년 2차 일반 물류바우처 사업 참여기업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
「중소기업기본법」제2조 및 시행령 제3조에 따른 중소기업
```

### Existing v1 candidates
- `CND:D3DFWCZ3JFNPPOMBDNVI4JC7` 중소기업 [BUSINESS_TYPE] ? PARTIAL_MATCH; gold: GOLD:LS2K3AZSTGCS73VZ7FP4VHJQ

### Gold condition draft
- `GOLD:LS2K3AZSTGCS73VZ7FP4VHJQ` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "중소기업"** ? 「중소기업기본법」제2조 및 시행령 제3조에 따른 중소기업 (span 0:31; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:LS2K3AZSTGCS73VZ7FP4VHJQ"}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## BIZINFO:PBLN_000000000125094 (BIZINFO)

### Notice title
[울산] 2026년 하반기 중소기업 밀집지역 위기대응 체계 구축사업 Stand-up 맞춤지원 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
울산광역시 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역 소재 중소기업
```

### Existing v1 candidates
- `CND:YCHP7B3P5Q4A4WJX7ITQU4I6` 중소기업 [BUSINESS_TYPE] ? MATCH; gold: GOLD:WWI7E7WYQT7HIWXI6FEF5HLP
- `CND:LW6JFQQ4LKHZJ3GMGJTOREE7` 울산광역시 [BUSINESS_LOCATION] ? PARTIAL_MATCH; gold: GOLD:EXOY2ZS2JTJGPLQ5MBEKSS55

### Gold condition draft
- `GOLD:EXOY2ZS2JTJGPLQ5MBEKSS55` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "울산광역시 내 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역"** ? 울산광역시 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역 소재 중소기업 (span 0:50; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:WWI7E7WYQT7HIWXI6FEF5HLP` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "중소기업"** ? 중소기업 (span 33:37; decision_possible=False; v1 comparison=MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:7113FE391539958FF87B3151", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:EXOY2ZS2JTJGPLQ5MBEKSS55"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:WWI7E7WYQT7HIWXI6FEF5HLP"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 50}, "observed_value_status": "AVAILABLE", "evidence_text": "울산광역시 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역 소재 중소기업"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## KSTARTUP:176482 (KSTARTUP)

### Notice title
[CJ온스타일] 2026 ON:CUBATING K-뷰티 · 웰니스 브랜드 모집

### Source excerpt (condition_texts.eligibility.text)
```text
국내·외 판로 확장이 필요한 K-뷰티·웰니스 브랜드
```

### Existing v1 candidates
- No candidate record; this is not evidence that no condition exists.

### Gold condition draft
- `GOLD:PRLDREXY4VK4PQM3LGNAEXSY` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / MARKET_EXPANSION_NEED / UNRESOLVED ** ? 국내·외 판로 확장이 필요한 (span 0:15; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:22TNQD3I4E5RRBSFHNQQP4DD` **ELIGIBILITY / INDUSTRY / BRAND_SECTOR / IN ["K-뷰티", "웰니스"]** ? K-뷰티·웰니스 브랜드 (span 16:28; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:F25861D920759A584AB0721A", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:PRLDREXY4VK4PQM3LGNAEXSY"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:22TNQD3I4E5RRBSFHNQQP4DD"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 28}, "observed_value_status": "AVAILABLE", "evidence_text": "국내·외 판로 확장이 필요한 K-뷰티·웰니스 브랜드"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## KSTARTUP:176659 (KSTARTUP)

### Notice title
2026년 서울시 창업허브 통합 설명회 개최

### Source excerpt (condition_texts.eligibility.text)
```text
서울 소재 중소기업 및 스타트업 등
```

### Existing v1 candidates
- `CND:ASA356OE3P2OXP5Q2YB2EPOS` 중소기업 [BUSINESS_TYPE] ? PARTIAL_MATCH; gold: GOLD:AXVMIDI43OATF5QS5JEJYHD5
- `CND:D4FGTPDRPH2FTH4EBGDCO5BU` 서울 [BUSINESS_LOCATION] ? PARTIAL_MATCH; gold: GOLD:LQ6WGJFWKFP57QHDO6PQ7MPL

### Gold condition draft
- `GOLD:LQ6WGJFWKFP57QHDO6PQ7MPL` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "서울특별시"** ? 서울 소재 (span 0:5; decision_possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:AXVMIDI43OATF5QS5JEJYHD5` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["중소기업", "스타트업"]** ? 중소기업 및 스타트업 등 (span 6:19; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:B435EB9E05C52589E65C9EBE", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:LQ6WGJFWKFP57QHDO6PQ7MPL"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:AXVMIDI43OATF5QS5JEJYHD5"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 19}, "observed_value_status": "AVAILABLE", "evidence_text": "서울 소재 중소기업 및 스타트업 등"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 
