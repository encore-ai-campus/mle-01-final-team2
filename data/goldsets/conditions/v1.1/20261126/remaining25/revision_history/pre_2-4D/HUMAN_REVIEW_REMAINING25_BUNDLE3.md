# Development review bundle 3/5

Draft only: UNREVIEWED / PENDING. Provided source text is an excerpt with UNKNOWN completeness; completeness of the whole notice is not asserted.

## BIZINFO:PBLN_000000000125345 (BIZINFO)

### Notice title
[전남광주] 2026년 전남형 신중년 사회연대경제 노동통합 모델 구축사업 참여기업 상시 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
근로자 5인 미만 기업(70%), 5인 이상 기업(30%)
-「사회적기업 육성법」에 따른 (예비)사회적기업
-「마을기업 육성 및 지원에 관한 법률」에 따른 (예비)마을기업
-「협동조합 기본법」에 따른 사회적협동조합
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:QILPWLAURFLWKK6USNXHUTI2` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "(예비)사회적기업"** ? 「사회적기업 육성법」에 따른 (예비)사회적기업 (source span 34:59; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:TV2WLDT3Y3WUKK5KBPF6XMBO` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "(예비)마을기업"** ? 「마을기업 육성 및 지원에 관한 법률」에 따른 (예비)마을기업 (source span 61:95; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:AFLTVT7ZE22UK57IVT4RQPR6` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "사회적협동조합"** ? 「협동조합 기본법」에 따른 사회적협동조합 (source span 97:119; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000125345:REVIEW:OR:3", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:QILPWLAURFLWKK6USNXHUTI2"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:TV2WLDT3Y3WUKK5KBPF6XMBO"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:AFLTVT7ZE22UK57IVT4RQPR6"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 119}, "observed_value_status": "AVAILABLE", "evidence_text": "근로자 5인 미만 기업(70%), 5인 이상 기업(30%)\n-「사회적기업 육성법」에 따른 (예비)사회적기업\n-「마을기업 육성 및 지원에 관한 법률」에 따른 (예비)마을기업\n-「협동조합 기본법」에 따른 사회적협동조합"}}`

### Benefit information requiring review
- 근로자 5인 미만 기업(70%), 5인 이상 기업(30%) ? UNKNOWN; Percentage meaning and link to applicant types are unconfirmed.

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000125974 (BIZINFO)

### Notice title
[경남] 진주시 2026년 발달장애인 가족창업 컨설팅 지원 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
진주시 지역의 발달장애인 가족공동 창업기업, 예비창업자 및 창업특화교육 참여 교육생
```

### Existing extracted candidates (frozen v1)
- `CND:EREHCCODQMCTWPCEDVASQPZT` 창업기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:JQPFXPMHGRFQLLPZ4EBCNCEV
- `CND:YA2B4MNZ5TSFGXYXRKREMLLR` 예비창업자 [ELIGIBILITY/BUSINESS_TYPE] ? MATCH; linked gold IDs: GOLD:OZIOM7JAW5KM23PWBC5YUT3C

### Proposed gold condition draft
- `GOLD:JQPFXPMHGRFQLLPZ4EBCNCEV` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "발달장애인 가족공동 창업기업"** ? 진주시 지역의 발달장애인 가족공동 창업기업 (source span 0:23; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:OZIOM7JAW5KM23PWBC5YUT3C` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "예비창업자"** ? 예비창업자 (source span 25:30; decision possible=True; v1 comparison=MATCH)
- `GOLD:NSA4756D2VZX3JZZVVIM4H5C` **ELIGIBILITY / PROGRAM_PARTICIPATION / PROGRAM_PARTICIPATION / EQ "창업특화교육 참여 교육생"** ? 창업특화교육 참여 교육생 (source span 33:46; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:ASRB34IDETZ6ZUCZAT25W4UJ` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "진주시"** ? 진주시 지역 (source span 0:6; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000125974:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:ASRB34IDETZ6ZUCZAT25W4UJ"}, {"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000125974:REVIEW:OR:3", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:JQPFXPMHGRFQLLPZ4EBCNCEV"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:OZIOM7JAW5KM23PWBC5YUT3C"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:NSA4756D2VZX3JZZVVIM4H5C"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 46}, "observed_value_status": "AVAILABLE", "evidence_text": "진주시 지역의 발달장애인 가족공동 창업기업, 예비창업자 및 창업특화교육 참여 교육생"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 46}, "observed_value_status": "AVAILABLE", "evidence_text": "진주시 지역의 발달장애인 가족공동 창업기업, 예비창업자 및 창업특화교육 참여 교육생"}}`

### Differences and review questions
- Candidate `CND:EREHCCODQMCTWPCEDVASQPZT`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:YA2B4MNZ5TSFGXYXRKREMLLR`: MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000126490 (BIZINFO)

### Notice title
2026년 K-소비재 수출기업 대상 한류편승행위 대응 지원사업 참여기업 모집 변경 공고

### Source excerpt (condition_texts.eligibility.text)
```text
대한민국에 사업자로 등록된 중소ㆍ중견기업 중 지원 희망 국가 내 유효한 지식재산권(상표ㆍ디자인)을 보유한 기업
```

### Existing extracted candidates (frozen v1)
- No candidate record. This does not mean no condition exists.

### Proposed gold condition draft
- `GOLD:7JXRJAMLGQABMO6OHTS2CEGS` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "대한민국 사업자 등록"** ? 대한민국에 사업자로 등록된 (source span 0:14; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:TSYHK4T7RJ2XBQGWA7EU2Q4O` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["중소기업", "중견기업"]** ? 중소ㆍ중견기업 (source span 15:22; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:J7D5IMG7Q6H7WALYUIRI6JDH` **ELIGIBILITY / INTELLECTUAL_PROPERTY / IP_RIGHT / IN ["상표", "디자인"]** ? 지원 희망 국가 내 유효한 지식재산권(상표ㆍ디자인)을 보유한 기업 (source span 25:61; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000126490:REVIEW:AND:3", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:7JXRJAMLGQABMO6OHTS2CEGS"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:TSYHK4T7RJ2XBQGWA7EU2Q4O"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:J7D5IMG7Q6H7WALYUIRI6JDH"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 61}, "observed_value_status": "AVAILABLE", "evidence_text": "대한민국에 사업자로 등록된 중소ㆍ중견기업 중 지원 희망 국가 내 유효한 지식재산권(상표ㆍ디자인)을 보유한 기업"}}`

### Differences and review questions
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:177051 (KSTARTUP)

### Notice title
「2026년 지역주도형 AI대전환사업」 AI솔루션 보급·확산사업 지원기업 통합모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
공고일 기준 창업 후 7년* 이내의 AI 솔루션 보유한 창업기업
* 신청가능 창업(설립)일 기준:’19.03.26.~’26.03.25.
```

### Existing extracted candidates (frozen v1)
- `CND:VUJBIE7AWNXWTHHJDGDKHLKR` 창업기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:MXHPIXUQU3VRTGNMXR3MVNN4

### Proposed gold condition draft
- `GOLD:KMYL5S47TTGV6E5T5E5FTCLJ` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 7** ? 공고일 기준 창업 후 7년* 이내 (source span 0:18; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:MXHPIXUQU3VRTGNMXR3MVNN4` **ELIGIBILITY / AI_SOLUTION / AI_SOLUTION / EQ "AI 솔루션 보유"** ? AI 솔루션 보유한 창업기업 (source span 20:35; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:177051:FINAL:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:KMYL5S47TTGV6E5T5E5FTCLJ"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:MXHPIXUQU3VRTGNMXR3MVNN4"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 75}, "observed_value_status": "AVAILABLE", "evidence_text": "공고일 기준 창업 후 7년* 이내의 AI 솔루션 보유한 창업기업\n* 신청가능 창업(설립)일 기준:’19.03.26.~’26.03.25."}}`

### Differences and review questions
- Candidate `CND:VUJBIE7AWNXWTHHJDGDKHLKR`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:177292 (KSTARTUP)

### Notice title
2026년 제1회 S.Challenge IR 참여 기업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
핀테크 분야 사업을 영위하고, 서울에 소재(본사 기준)한 창업 3년 이내 기업
```

### Existing extracted candidates (frozen v1)
- `CND:MEQEGWDTWUOAQG23Z7C4UGY5` 창업 3년 이내 [ELIGIBILITY/BUSINESS_AGE] ? PARTIAL_MATCH; linked gold IDs: GOLD:Z6DZ6QZPZF6NTDDWF3ST2VPE
- `CND:GFXGZMMUHLY7JXDOAWTE5JP2` 서울 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:D54ISVFK4QZSWPTFW5YZBAXT

### Proposed gold condition draft
- `GOLD:MMNY4QGNQSYP6YPOS6ACZVQ7` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "핀테크"** ? 핀테크 분야 사업을 영위하고 (source span 0:15; decision possible=True; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:D54ISVFK4QZSWPTFW5YZBAXT` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "서울특별시"** ? 서울에 소재(본사 기준)한 (source span 17:31; decision possible=True; v1 comparison=PARTIAL_MATCH)
- `GOLD:Z6DZ6QZPZF6NTDDWF3ST2VPE` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 3** ? 창업 3년 이내 기업 (source span 32:43; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:177292:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:MMNY4QGNQSYP6YPOS6ACZVQ7"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:D54ISVFK4QZSWPTFW5YZBAXT"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:Z6DZ6QZPZF6NTDDWF3ST2VPE"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 43}, "observed_value_status": "AVAILABLE", "evidence_text": "핀테크 분야 사업을 영위하고, 서울에 소재(본사 기준)한 창업 3년 이내 기업"}}`

### Differences and review questions
- Candidate `CND:MEQEGWDTWUOAQG23Z7C4UGY5`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:GFXGZMMUHLY7JXDOAWTE5JP2`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 
