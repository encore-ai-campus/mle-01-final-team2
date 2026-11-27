# Development review bundle 2/5

Draft only: UNREVIEWED / PENDING. Provided source text is an excerpt with UNKNOWN completeness; completeness of the whole notice is not asserted.

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

### Existing extracted candidates (frozen v1)
- `CND:E6OXO4IHXZRGP4APAN42BAEP` 서울특별시 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:UXVEFSAFJQFCZ55Y43ESQGSK
- `CND:44GR2V7FN67RRVDEF7ALASB5` 인천광역시 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:UXVEFSAFJQFCZ55Y43ESQGSK
- `CND:3ZW23MK72GLPRBMEMBDWZY6Q` 경기도 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:UXVEFSAFJQFCZ55Y43ESQGSK
- `CND:OOK7DGIRZ364DCFZEWUJQYHO` 제외 [EXCLUSION/None] ? PARTIAL_MATCH; linked gold IDs: GOLD:S7Z5SLKNDLFIJQUE6HF6KWOV

### Proposed gold condition draft
- `GOLD:Q25NJPQFQZXJ4RDOBEUDR3DV` **ELIGIBILITY / EMPLOYEE_COUNT / EMPLOYEE_COUNT / GTE 5** ? 5인 이상 우선지원대상기업 (source span 58:72; decision possible=True; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:UXVEFSAFJQFCZ55Y43ESQGSK` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / IN ["서울특별시", "인천광역시", "경기도"]** ? (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업 (source span 18:55; decision possible=True; v1 comparison=PARTIAL_MATCH,PARTIAL_MATCH,PARTIAL_MATCH)
- `GOLD:S7Z5SLKNDLFIJQUE6HF6KWOV` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / NOT_IN ["서울특별시", "인천광역시", "경기도"]** ? (비수도권) 수도권 제외한 지역에 소재하는 기업 (source span 96:122; decision possible=True; v1 comparison=PARTIAL_MATCH)
- `GOLD:E52JNG2PBM7SIC4GZUSCSPD6` **ELIGIBILITY / HIRE_STATUS / HIRE_STATUS / UNRESOLVED ** ? 취업애로청년을 정규직으로 채용 후 (source span 75:93; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:HWY2DUJDGEMAQB4EUNSPMCGX` **ELIGIBILITY / HIRE_STATUS / HIRE_STATUS / UNRESOLVED ** ? 청년을 정규직으로 채용 후 (source span 79:93; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000119490:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:Q25NJPQFQZXJ4RDOBEUDR3DV"}, {"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000119490:REVIEW:OR:2", "operator": "OR", "children": [{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000119490:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:UXVEFSAFJQFCZ55Y43ESQGSK"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:E52JNG2PBM7SIC4GZUSCSPD6"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}, {"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000119490:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:S7Z5SLKNDLFIJQUE6HF6KWOV"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:HWY2DUJDGEMAQB4EUNSPMCGX"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 174}, "observed_value_status": "AVAILABLE", "evidence_text": "5인 이상 우선지원대상 기업\n- (수도권) 수도권(서울특별시, 인천광역시, 경기도)에 소재하는 기업이며 5인 이상 우선지원대상기업에서 취업애로청년을 정규직으로 채용 후\n- (비수도권) 수도권 제외한 지역에 소재하는 기업이며 5인 이상 우선지원대상기업에서 청년을 정규직으로 채용 후\n※ 자세한 지원대상 공고문 참조"}}`

### Differences and review questions
- Candidate `CND:E6OXO4IHXZRGP4APAN42BAEP`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:44GR2V7FN67RRVDEF7ALASB5`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:3ZW23MK72GLPRBMEMBDWZY6Q`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:OOK7DGIRZ364DCFZEWUJQYHO`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000122876 (BIZINFO)

### Notice title
2026년 2차 일반 물류바우처 사업 참여기업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
「중소기업기본법」제2조 및 시행령 제3조에 따른 중소기업
```

### Existing extracted candidates (frozen v1)
- `CND:D3DFWCZ3JFNPPOMBDNVI4JC7` 중소기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:IXU4JVQXEOMH7N6YNP3UCXXT

### Proposed gold condition draft
- `GOLD:IXU4JVQXEOMH7N6YNP3UCXXT` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "중소기업"** ? 「중소기업기본법」제2조 및 시행령 제3조에 따른 중소기업 (source span 0:31; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:IXU4JVQXEOMH7N6YNP3UCXXT"}`

### Differences and review questions
- Candidate `CND:D3DFWCZ3JFNPPOMBDNVI4JC7`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000125094 (BIZINFO)

### Notice title
[울산] 2026년 하반기 중소기업 밀집지역 위기대응 체계 구축사업 Stand-up 맞춤지원 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
울산광역시 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역 소재 중소기업
```

### Existing extracted candidates (frozen v1)
- `CND:YCHP7B3P5Q4A4WJX7ITQU4I6` 중소기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:AEC5F4O6FEYGGBAY5TD3XF5Y, GOLD:RBIE2PQYWEPYELACE2C6LD3Y
- `CND:LW6JFQQ4LKHZJ3GMGJTOREE7` 울산광역시 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:AEC5F4O6FEYGGBAY5TD3XF5Y

### Proposed gold condition draft
- `GOLD:AEC5F4O6FEYGGBAY5TD3XF5Y` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "울산광역시 내 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역"** ? 울산광역시 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역 소재 중소기업 (source span 0:50; decision possible=False; v1 comparison=PARTIAL_MATCH,PARTIAL_MATCH)
- `GOLD:RBIE2PQYWEPYELACE2C6LD3Y` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "중소기업"** ? 중소기업 (source span 33:37; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000125094:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:AEC5F4O6FEYGGBAY5TD3XF5Y"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:RBIE2PQYWEPYELACE2C6LD3Y"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 50}, "observed_value_status": "AVAILABLE", "evidence_text": "울산광역시 2026년 하반기 Stand-up 맞춤지원 대상 중소기업 밀집지역 소재 중소기업"}}`

### Differences and review questions
- Candidate `CND:YCHP7B3P5Q4A4WJX7ITQU4I6`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:LW6JFQQ4LKHZJ3GMGJTOREE7`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:176482 (KSTARTUP)

### Notice title
[CJ온스타일] 2026 ON:CUBATING K-뷰티 · 웰니스 브랜드 모집

### Source excerpt (condition_texts.eligibility.text)
```text
국내·외 판로 확장이 필요한 K-뷰티·웰니스 브랜드
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:3MMK6VXRFDT267NNY6G6GYBA` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / MARKET_EXPANSION_NEED / UNRESOLVED ** ? 국내·외 판로 확장이 필요한 (source span 0:15; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:JAOZOFSTU3HAOXQZBIQF67L2` **ELIGIBILITY / INDUSTRY / BRAND_SECTOR / IN ["K-뷰티", "웰니스"]** ? K-뷰티·웰니스 브랜드 (source span 16:28; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:176482:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:3MMK6VXRFDT267NNY6G6GYBA"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:JAOZOFSTU3HAOXQZBIQF67L2"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 28}, "observed_value_status": "AVAILABLE", "evidence_text": "국내·외 판로 확장이 필요한 K-뷰티·웰니스 브랜드"}}`

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:176659 (KSTARTUP)

### Notice title
2026년 서울시 창업허브 통합 설명회 개최

### Source excerpt (condition_texts.eligibility.text)
```text
서울 소재 중소기업 및 스타트업 등
```

### Existing extracted candidates (frozen v1)
- `CND:ASA356OE3P2OXP5Q2YB2EPOS` 중소기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:5PUPDR6IG455WSHB5TMWY3AX
- `CND:D4FGTPDRPH2FTH4EBGDCO5BU` 서울 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:PVHD6HYAHT7S2P4QAL37SZMB

### Proposed gold condition draft
- `GOLD:PVHD6HYAHT7S2P4QAL37SZMB` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "서울특별시"** ? 서울 소재 (source span 0:5; decision possible=True; v1 comparison=PARTIAL_MATCH)
- `GOLD:5PUPDR6IG455WSHB5TMWY3AX` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["중소기업", "스타트업"]** ? 중소기업 및 스타트업 등 (source span 6:19; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:176659:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:PVHD6HYAHT7S2P4QAL37SZMB"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:5PUPDR6IG455WSHB5TMWY3AX"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 19}, "observed_value_status": "AVAILABLE", "evidence_text": "서울 소재 중소기업 및 스타트업 등"}}`

### Differences and review questions
- Candidate `CND:ASA356OE3P2OXP5Q2YB2EPOS`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:D4FGTPDRPH2FTH4EBGDCO5BU`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 
