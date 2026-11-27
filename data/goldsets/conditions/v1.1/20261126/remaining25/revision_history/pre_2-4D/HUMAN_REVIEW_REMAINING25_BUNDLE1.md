# Development review bundle 1/5

Draft only: UNREVIEWED / PENDING. Provided source text is an excerpt with UNKNOWN completeness; completeness of the whole notice is not asserted.

## BIZINFO:PBLN_000000000117168 (BIZINFO)

### Notice title
[대구] 2025년 4차 소상공인 맞춤형 출산ㆍ양육지원 사업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
대구시에 주소와 사업장을 둔 소상공인
- 2024. 1. 1. 이전부터 대구시에 사업자등록증명원 소재지 및 주소지 유지
※ 상세 사업별 신청자격 공고문 참조
```

### Existing extracted candidates (frozen v1)
- `CND:HVOJVP4HNCG5ZE2VX63J5DTM` 소상공인 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:WA4MUCSQMLINK5MCYXOV7J2H
- `CND:JRG6EAAJCDPQ2BWRACAES6AU` 대구 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:WA4MUCSQMLINK5MCYXOV7J2H, GOLD:6FNBWH577C3LKMREEPTCFSLF, GOLD:37KN77IUAVWI2WDPE6DWS4RR

### Proposed gold condition draft
- `GOLD:WA4MUCSQMLINK5MCYXOV7J2H` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "소상공인"** ? 대구시에 주소와 사업장을 둔 소상공인 (source span 0:20; decision possible=False; v1 comparison=PARTIAL_MATCH,PARTIAL_MATCH)
- `GOLD:6FNBWH577C3LKMREEPTCFSLF` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "대구광역시"** ? 대구시에 주소와 사업장을 둔 (source span 0:15; decision possible=True; v1 comparison=PARTIAL_MATCH)
- `GOLD:37KN77IUAVWI2WDPE6DWS4RR` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "대구광역시"** ? 2024. 1. 1. 이전부터 대구시에 사업자등록증명원 소재지 및 주소지 유지 (source span 23:66; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000117168:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:WA4MUCSQMLINK5MCYXOV7J2H"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:6FNBWH577C3LKMREEPTCFSLF"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:37KN77IUAVWI2WDPE6DWS4RR"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 87}, "observed_value_status": "AVAILABLE", "evidence_text": "대구시에 주소와 사업장을 둔 소상공인\n- 2024. 1. 1. 이전부터 대구시에 사업자등록증명원 소재지 및 주소지 유지\n※ 상세 사업별 신청자격 공고문 참조"}}`

### Differences and review questions
- Candidate `CND:HVOJVP4HNCG5ZE2VX63J5DTM`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:JRG6EAAJCDPQ2BWRACAES6AU`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000117340 (BIZINFO)

### Notice title
[경북] 칠곡군 2026년 설대비 중소기업 운전자금(이차보전) 지원 계획 공고

### Source excerpt (condition_texts.eligibility.text)
```text
칠곡군 내 사업장(사업자등록증명원의 소재지, 매출액)을 둔 ｢중소기업기본법｣ 상의 중소기업
※ 자세한 지원대상 공고문 참조
```

### Existing extracted candidates (frozen v1)
- `CND:4YEL3C5ZJZHDSBBSSUDZFN7E` 중소기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:YRXKOCUU7NH2PS6LFDKLYTH7

### Proposed gold condition draft
- `GOLD:4IRET4MFEZ67YKEEZZ3AISR6` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "칠곡군"** ? 칠곡군 내 사업장 (source span 0:9; decision possible=True; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:OBOOLQOWKVFSF2TP553ZOZ4H` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / UNRESOLVED ** ? 사업자등록증명원의 소재지, 매출액 (source span 10:28; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:YRXKOCUU7NH2PS6LFDKLYTH7` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "중소기업"** ? ｢중소기업기본법｣ 상의 중소기업 (source span 33:50; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000117340:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:4IRET4MFEZ67YKEEZZ3AISR6"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:OBOOLQOWKVFSF2TP553ZOZ4H"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:YRXKOCUU7NH2PS6LFDKLYTH7"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 68}, "observed_value_status": "AVAILABLE", "evidence_text": "칠곡군 내 사업장(사업자등록증명원의 소재지, 매출액)을 둔 ｢중소기업기본법｣ 상의 중소기업\n※ 자세한 지원대상 공고문 참조"}}`

### Differences and review questions
- Candidate `CND:4YEL3C5ZJZHDSBBSSUDZFN7E`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000117526 (BIZINFO)

### Notice title
[경남] 2026년 소상공인 정책자금 운용계획 공고

### Source excerpt (condition_texts.eligibility.text)
```text
경남 도내에 소재하고 있는 「소상공인기본법」 제2조에 따른 소상공인
※ 세부사업별 지원대상 상이 (공고문 참조)
```

### Existing extracted candidates (frozen v1)
- `CND:3Q2O7JBBJMQN5DDJVBGGW3MB` 소상공인 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:7PE2UC2SZLOYARHXYWY5FTW5
- `CND:RH7LVE5TUYU3YZWCHXXGH2WE` 경남 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:G6VPI3DJDP6M35SY4OUAJCXH

### Proposed gold condition draft
- `GOLD:G6VPI3DJDP6M35SY4OUAJCXH` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "경상남도"** ? 경남 도내에 소재하고 있는 (source span 0:14; decision possible=True; v1 comparison=PARTIAL_MATCH)
- `GOLD:7PE2UC2SZLOYARHXYWY5FTW5` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "소상공인"** ? 「소상공인기본법」 제2조에 따른 소상공인 (source span 15:37; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000117526:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:G6VPI3DJDP6M35SY4OUAJCXH"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:7PE2UC2SZLOYARHXYWY5FTW5"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 62}, "observed_value_status": "AVAILABLE", "evidence_text": "경남 도내에 소재하고 있는 「소상공인기본법」 제2조에 따른 소상공인\n※ 세부사업별 지원대상 상이 (공고문 참조)"}}`

### Differences and review questions
- Candidate `CND:3Q2O7JBBJMQN5DDJVBGGW3MB`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:RH7LVE5TUYU3YZWCHXXGH2WE`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:176001 (KSTARTUP)

### Notice title
2026년 글로벌 스포츠 강소기업 육성 지원(해외진출 역량강화) 사업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
- 업력 만 1년 이상
- 전체 매출액 중 스포츠산업 비중 10% 이상
- 최근 결산년도 매출액 3억원 이상
- 중소기업기본법에 의한 중소기업
```

### Existing extracted candidates (frozen v1)
- `CND:H2T5HOP6DDQW7IG7WF3W2PFE` 업력 만 1년 이상 [ELIGIBILITY/BUSINESS_AGE] ? MATCH; linked gold IDs: GOLD:GTUJ4YS2WERIWEGPR5IWLL4N
- `CND:Z3DLRYMGSCRBVNJHXRPVXDI7` 매출액 3억원 이상 [ELIGIBILITY/REVENUE_FINANCIAL] ? PARTIAL_MATCH; linked gold IDs: GOLD:PSEQQSRQDMUEYNKBUWYQQA7W
- `CND:L32RLGA23VMTZMZ6K6MHYGL2` 중소기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:VJ6SFJL6XU3F7SJK2GOZ3KMR

### Proposed gold condition draft
- `GOLD:GTUJ4YS2WERIWEGPR5IWLL4N` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / GTE 1** ? 업력 만 1년 이상 (source span 2:12; decision possible=False; v1 comparison=MATCH)
- `GOLD:NSM4O7B5KBQNUH62LVDYZEOH` **ELIGIBILITY / INDUSTRY_REVENUE_SHARE / INDUSTRY_REVENUE_SHARE / GTE 10** ? 전체 매출액 중 스포츠산업 비중 10% 이상 (source span 15:39; decision possible=True; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:PSEQQSRQDMUEYNKBUWYQQA7W` **ELIGIBILITY / REVENUE / REVENUE / GTE 300000000** ? 최근 결산년도 매출액 3억원 이상 (source span 42:60; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:VJ6SFJL6XU3F7SJK2GOZ3KMR` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "중소기업"** ? 중소기업기본법에 의한 중소기업 (source span 63:79; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:176001:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:GTUJ4YS2WERIWEGPR5IWLL4N"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:NSM4O7B5KBQNUH62LVDYZEOH"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:PSEQQSRQDMUEYNKBUWYQQA7W"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:VJ6SFJL6XU3F7SJK2GOZ3KMR"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 79}, "observed_value_status": "AVAILABLE", "evidence_text": "- 업력 만 1년 이상\n- 전체 매출액 중 스포츠산업 비중 10% 이상\n- 최근 결산년도 매출액 3억원 이상\n- 중소기업기본법에 의한 중소기업"}}`

### Differences and review questions
- Candidate `CND:H2T5HOP6DDQW7IG7WF3W2PFE`: MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:Z3DLRYMGSCRBVNJHXRPVXDI7`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:L32RLGA23VMTZMZ6K6MHYGL2`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:176387 (KSTARTUP)

### Notice title
앤틀러코리아 ANTLER FORGE 참여 기업 모집 | 팀 당 6억원 규모 투자

### Source excerpt (condition_texts.eligibility.text)
```text
아래 조건 중 하나 이상 충족한 팀/2년 미만 기업
1. 피지컬ai 관련 하드웨어, 소프트웨어 등 딥테크 분야의 혁신적인 기술력을 보유한 엔지니어링 기반 창업팀
2. 시장의 실제 수요를 증명하고, $400,000 이상(한화 약 5억 원 이상)의 투자를 유치하고자 하는 초기 기업

*선발 프로세스는 지원서 접수 순으로 진행되며, 선발 인원 충족 시 조기에 마감될 수 있으니 빠른 지원을 권장합니다.
* 해당 프로그램은 이미 제품을 개발 중이거나 초기 모델을 보유한 팀에게 최적화되어 있습니다. 단순한 아이디어 단계를 넘어, 실제 구현 가능한 기술력을 바탕으로 빠르게 시장에 진입하고자 하는 팀을 환영합니다. 프로그램 기간 중 유의미한 고객 지표나 실제 수요가 확인될 경우, 즉시 최대 50만 달러 규모(6억원 규모)의 투자 심사가 진행됩니다.

대상 산업
• Physical AI
• 로보틱스
• 반도체
• 모빌리티 및 스마트 인프라
• 게임, e스포츠
• 생물의학 및 의료
• 항공우주 및 방위
• 기타 시스템 또는 첨단 산업
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:VFGVALA6MP3DXEVBXX3I273D` **ELIGIBILITY / APPLICANT_PROFILE / QUALITATIVE_QUALIFICATION / UNRESOLVED ** ? 피지컬ai 관련 하드웨어, 소프트웨어 등 딥테크 분야의 혁신적인 기술력을 보유한 엔지니어링 기반 창업팀 (source span 32:89; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:J22QYJVQ33XBM6WI4725KUZG` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LT 2** ? 2년 미만 기업 (source span 20:28; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:P4XSMPQ64OULFW33DZ2DNNEX` **ELIGIBILITY / INVESTMENT_INTENT / QUALITATIVE_QUALIFICATION / UNRESOLVED ** ? 시장의 실제 수요를 증명하고, $400,000 이상(한화 약 5억 원 이상)의 투자를 유치하고자 하는 초기 기업 (source span 93:155; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:V6MH6TLZWTDR6PRUJJERFDSQ` **ELIGIBILITY / INDUSTRY / INDUSTRY / IN ["Physical AI", "로보틱스", "반도체", "모빌리티 및 스마트 인프라", "게임·e스포츠", "생물의학 및 의료", "항공우주 및 방위", "기타 시스템 또는 첨단 산업"]** ? 대상 산업
• Physical AI
• 로보틱스
• 반도체
• 모빌리티 및 스마트 인프라
• 게임, e스포츠
• 생물의학 및 의료
• 항공우주 및 방위
• 기타 시스템 또는 첨단 산업 (source span 417:519; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:176387:FINAL:OR:2", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:VFGVALA6MP3DXEVBXX3I273D"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:P4XSMPQ64OULFW33DZ2DNNEX"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 519}, "observed_value_status": "AVAILABLE", "evidence_text": "아래 조건 중 하나 이상 충족한 팀/2년 미만 기업\n1. 피지컬ai 관련 하드웨어, 소프트웨어 등 딥테크 분야의 혁신적인 기술력을 보유한 엔지니어링 기반 창업팀\n2. 시장의 실제 수요를 증명하고, $400,000 이상(한화 약 5억 원 이상)의 투자를 유치하고자 하는 초기 기업\n\n*선발 프로세스는 지원서 접수 순으로 진행되며, 선발 인원 충족 시 조기에 마감될 수 있으니 빠른 지원을 권장합니다.\n* 해당 프로그램은 이미 제품을 개발 중이거나 초기 모델을 보유한 팀에게 최적화되어 있습니다. 단순한 아이디어 단계를 넘어, 실제 구현 가능한 기술력을 바탕으로 빠르게 시장에 진입하고자 하는 팀을 환영합니다. 프로그램 기간 중 유의미한 고객 지표나 실제 수요가 확인될 경우, 즉시 최대 50만 달러 규모(6억원 규모)의 투자 심사가 진행됩니다.\n\n대상 산업\n• Physical AI\n• 로보틱스\n• 반도체\n• 모빌리티 및 스마트 인프라\n• 게임, e스포츠\n• 생물의학 및 의료\n• 항공우주 및 방위\n• 기타 시스템 또는 첨단 산업"}}`

### Unresolved logical relations
- Target industry list relation to the two alternatives is not specified. (condition IDs: GOLD:VFGVALA6MP3DXEVBXX3I273D, GOLD:P4XSMPQ64OULFW33DZ2DNNEX, GOLD:V6MH6TLZWTDR6PRUJJERFDSQ; source span 423:436)
- The 2-year company-age modifier may scope only the early-company branch; exact relation needs review. (condition IDs: GOLD:J22QYJVQ33XBM6WI4725KUZG, GOLD:P4XSMPQ64OULFW33DZ2DNNEX; source span 20:28)

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 
