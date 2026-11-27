# Development review bundle 5/5

Draft only: UNREVIEWED / PENDING. Provided source text is an excerpt with UNKNOWN completeness; completeness of the whole notice is not asserted.

## BIZINFO:PBLN_000000000127992 (BIZINFO)

### Notice title
2027년 정보통신 및 정보문화 유공 정부포상 계획 공고

### Source excerpt (condition_texts.eligibility.text)
```text
(정보통신 분야) 인공지능, 정보방송통신, 국가지능정보화, 우정사업 등의 발전에 기여한 공적이 뛰어난 단체 등
- (정보문화 분야) 디지털 격차ㆍ역기능 해소 및 디지털 역량 강화 등을 통해 디지털 포용사회 구현과 건전한 정보문화 창달에 기여한 다음과 같은 공적을 갖춘 자
※ 자세한 지원대상 공고문 참조
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:WGNQGGKYCEHX3FRVOVGZQKCH` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / QUALITATIVE_QUALIFICATION / UNRESOLVED ** ? (정보통신 분야) 인공지능, 정보방송통신, 국가지능정보화, 우정사업 등의 발전에 기여한 공적이 뛰어난 단체 등 (source span 0:61; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:O5D7HOP6ADCGWG5B6OCVQ755` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / QUALITATIVE_QUALIFICATION / UNRESOLVED ** ? (정보문화 분야) 디지털 격차ㆍ역기능 해소 및 디지털 역량 강화 등을 통해 디지털 포용사회 구현과 건전한 정보문화 창달에 기여한 다음과 같은 공적을 갖춘 자 (source span 64:151; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000127992:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:WGNQGGKYCEHX3FRVOVGZQKCH"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:O5D7HOP6ADCGWG5B6OCVQ755"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 169}, "observed_value_status": "AVAILABLE", "evidence_text": "(정보통신 분야) 인공지능, 정보방송통신, 국가지능정보화, 우정사업 등의 발전에 기여한 공적이 뛰어난 단체 등\n- (정보문화 분야) 디지털 격차ㆍ역기능 해소 및 디지털 역량 강화 등을 통해 디지털 포용사회 구현과 건전한 정보문화 창달에 기여한 다음과 같은 공적을 갖춘 자\n※ 자세한 지원대상 공고문 참조"}}`

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000128028 (BIZINFO)

### Notice title
[부산] 중구 2027년 수산자원보호직불제 사업 신청 공고

### Source excerpt (condition_texts.eligibility.text)
```text
강화된 자원보호 의무를 이행하는 어업인 등
-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사
- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:5BFWC5SXK6MU7BD7A36WCQZJ` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "등록 어업인 등"** ? 어업경영 관련 정보 등을 등록한 어업인 등 (source span 62:85; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:QWK3F4JGCTGIXEDM6MWT35TV` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "상법상 회사"** ? 「상법」상 회사 (source span 134:142; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:5KY7TQOG3I7VEULEWH4CEGR5` **ELIGIBILITY / LICENSE_STATUS / LICENSE_STATUS / IN ["면허", "허가"]** ? 면허 또는 허가를 받은 (source span 122:134; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:AVCG3GCFCF7U4UHZ2FRYLF7A` **ELIGIBILITY / COMPLIANCE_PLAN / COMPLIANCE_PLAN / GTE 2** ? 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등 (source span 186:220; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000128028:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000128028:REVIEW:OR:2", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:5BFWC5SXK6MU7BD7A36WCQZJ"}, {"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000128028:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:QWK3F4JGCTGIXEDM6MWT35TV"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:5KY7TQOG3I7VEULEWH4CEGR5"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 220}, "observed_value_status": "AVAILABLE", "evidence_text": "강화된 자원보호 의무를 이행하는 어업인 등\n-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사\n- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 220}, "observed_value_status": "AVAILABLE", "evidence_text": "강화된 자원보호 의무를 이행하는 어업인 등\n-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사\n- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등"}}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:AVCG3GCFCF7U4UHZ2FRYLF7A"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 220}, "observed_value_status": "AVAILABLE", "evidence_text": "강화된 자원보호 의무를 이행하는 어업인 등\n-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사\n- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등"}}`

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:178610 (KSTARTUP)

### Notice title
2026년 제4회 창업기업성장지원센터(이노플러스 스테이지) 신규 입주기업 모집공고

### Source excerpt (condition_texts.eligibility.text)
```text
- 제조업(스마트제조, 제조AI 등)
- 지식기반산업(지식산업, 첨단기술활용 산업)
- 정보통신산업
- 전문, 과학 및 기술 서비스업 등
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:Y5GO5I454WCKML6LGVI7G72I` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "제조업"** ? 제조업(스마트제조, 제조AI 등) (source span 2:20; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:NQOBW7Y7AB7YMG6JPAUO7OOC` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "지식기반산업"** ? 지식기반산업(지식산업, 첨단기술활용 산업) (source span 23:46; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:C7IJFUJW4KHO7YDQNHPFKXYO` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "정보통신산업"** ? 정보통신산업 (source span 49:55; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:26PDCSCANWILCWQ7E5UNPRYS` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "전문·과학·기술 서비스업 등"** ? 전문, 과학 및 기술 서비스업 등 (source span 58:76; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:178610:REVIEW:OR:4", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:Y5GO5I454WCKML6LGVI7G72I"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:NQOBW7Y7AB7YMG6JPAUO7OOC"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:C7IJFUJW4KHO7YDQNHPFKXYO"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:26PDCSCANWILCWQ7E5UNPRYS"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 76}, "observed_value_status": "AVAILABLE", "evidence_text": "- 제조업(스마트제조, 제조AI 등)\n- 지식기반산업(지식산업, 첨단기술활용 산업)\n- 정보통신산업\n- 전문, 과학 및 기술 서비스업 등"}}`

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:179386 (KSTARTUP)

### Notice title
2026년 창업-Bus 프로그램「강원브릿지 화요IR」 참여기업 모집

### Source excerpt (condition_texts.eligibility.text)
```text
창업 7년 이내 초격차 창업기업
※ 중점분야: 바이오·헬스, AI·빅데이터
※ 강원 7대 전략산업(바이오·헬스, 반도체, 미래에너지, 미래모빌리티, 방위산업, 기후테크, 푸드테크) 분야 기업 우대
```

### Existing extracted candidates (frozen v1)
- `CND:WCH2XWWHUIKN72BIERPWKSNC` 창업 7년 이내 [ELIGIBILITY/BUSINESS_AGE] ? MATCH; linked gold IDs: GOLD:ZNK5ALL3XXGKDMAN4NCOK6BA
- `CND:UZVVBGQJZQPGZWI36PNRQETP` 창업기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:TW2XUI7IKQZYDPUQ6HL62D2J
- `CND:KF7GL6UKP2LSISJWOOBBS5EP` 우대 [PREFERENCE/None] ? PARTIAL_MATCH; linked gold IDs: GOLD:55FIMTAFAQ44FEON4VAZA4JE
- `CND:Q4C23HXVQPRL44C5YF2VY4UL` 강원 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:55FIMTAFAQ44FEON4VAZA4JE

### Proposed gold condition draft
- `GOLD:TW2XUI7IKQZYDPUQ6HL62D2J` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "초격차 창업기업"** ? 초격차 창업기업 (source span 9:17; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:ZNK5ALL3XXGKDMAN4NCOK6BA` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 7** ? 창업 7년 이내 (source span 0:8; decision possible=False; v1 comparison=MATCH)
- `GOLD:V4P56GNGWH45ESY5NP5DNOLN` **ELIGIBILITY / INDUSTRY / INDUSTRY / IN ["바이오·헬스", "AI·빅데이터"]** ? 바이오·헬스, AI·빅데이터 (source span 26:41; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:55FIMTAFAQ44FEON4VAZA4JE` **PREFERENCE / INDUSTRY / INDUSTRY / IN ["바이오·헬스", "반도체", "미래에너지", "미래모빌리티", "방위산업", "기후테크", "푸드테크"]** ? 강원 7대 전략산업(바이오·헬스, 반도체, 미래에너지, 미래모빌리티, 방위산업, 기후테크, 푸드테크) 분야 기업 우대 (source span 44:109; decision possible=False; v1 comparison=PARTIAL_MATCH,PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:179386:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:TW2XUI7IKQZYDPUQ6HL62D2J"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:ZNK5ALL3XXGKDMAN4NCOK6BA"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 109}, "observed_value_status": "AVAILABLE", "evidence_text": "창업 7년 이내 초격차 창업기업\n※ 중점분야: 바이오·헬스, AI·빅데이터\n※ 강원 7대 전략산업(바이오·헬스, 반도체, 미래에너지, 미래모빌리티, 방위산업, 기후테크, 푸드테크) 분야 기업 우대"}}`
- PREFERENCE / evaluation=SELECTION / fulfillment=SELECTION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:55FIMTAFAQ44FEON4VAZA4JE"}`

### Unresolved logical relations
- Focus-sector statement may scope the program but is not explicitly mandatory. (condition IDs: GOLD:TW2XUI7IKQZYDPUQ6HL62D2J, GOLD:ZNK5ALL3XXGKDMAN4NCOK6BA, GOLD:V4P56GNGWH45ESY5NP5DNOLN; source span 26:41)

### Differences and review questions
- Candidate `CND:WCH2XWWHUIKN72BIERPWKSNC`: MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:UZVVBGQJZQPGZWI36PNRQETP`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:KF7GL6UKP2LSISJWOOBBS5EP`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:Q4C23HXVQPRL44C5YF2VY4UL`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:179676 (KSTARTUP)

### Notice title
2026 별별상상 스타트업 챌린지

### Source excerpt (condition_texts.eligibility.text)
```text
전국의 대학생 및 대학원생 누구나 지원 가능
```

### Existing extracted candidates (frozen v1)
- `CND:BQMMBZFKARDMWVKXF2T3YFR4` 전국 [ELIGIBILITY/BUSINESS_LOCATION] ? UNRESOLVED; linked gold IDs: none / review required

### Proposed gold condition draft
- `GOLD:OPXJYC4TEGPSVOAKAV2W5HMP` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["대학생", "대학원생"]** ? 대학생 및 대학원생 (source span 4:14; decision possible=True; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:OPXJYC4TEGPSVOAKAV2W5HMP"}`

### Differences and review questions
- Candidate `CND:BQMMBZFKARDMWVKXF2T3YFR4`: UNRESOLVED ? 독립 정답 초안의 어느 조건과 대응하는지 원문 기반 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 
