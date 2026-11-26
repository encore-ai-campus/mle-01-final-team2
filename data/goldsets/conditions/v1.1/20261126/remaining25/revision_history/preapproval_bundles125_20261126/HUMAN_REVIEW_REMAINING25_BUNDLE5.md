# Development review bundle 5/5

Draft only: UNREVIEWED / PENDING. Source is a condition excerpt; completeness of the whole notice remains UNKNOWN.

## BIZINFO:PBLN_000000000127992 (BIZINFO)

### Notice title
2027년 정보통신 및 정보문화 유공 정부포상 계획 공고

### Source excerpt (condition_texts.eligibility.text)
```text
(정보통신 분야) 인공지능, 정보방송통신, 국가지능정보화, 우정사업 등의 발전에 기여한 공적이 뛰어난 단체 등
- (정보문화 분야) 디지털 격차ㆍ역기능 해소 및 디지털 역량 강화 등을 통해 디지털 포용사회 구현과 건전한 정보문화 창달에 기여한 다음과 같은 공적을 갖춘 자
※ 자세한 지원대상 공고문 참조
```

### Existing v1 candidates
- No candidate record; this is not evidence that no condition exists.

### Gold condition draft
- `GOLD:ZFO33UY2FOFDR3EUY3IL7I7B` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / QUALITATIVE_QUALIFICATION / UNRESOLVED ** ? (정보통신 분야) 인공지능, 정보방송통신, 국가지능정보화, 우정사업 등의 발전에 기여한 공적이 뛰어난 단체 등 (span 0:61; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 분야별 구체 공적 기준은 상세 공고문 미수집으로 UNKNOWN.
- `GOLD:6RAWCPUTX3CXN7GKVIWHKY5J` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / QUALITATIVE_QUALIFICATION / UNRESOLVED ** ? (정보문화 분야) 디지털 격차ㆍ역기능 해소 및 디지털 역량 강화 등을 통해 디지털 포용사회 구현과 건전한 정보문화 창달에 기여한 다음과 같은 공적을 갖춘 자 (span 64:151; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 분야별 구체 공적 기준은 상세 공고문 미수집으로 UNKNOWN.

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:F8C2D5CB3C7DC49C907BFC4F", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:ZFO33UY2FOFDR3EUY3IL7I7B"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:6RAWCPUTX3CXN7GKVIWHKY5J"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 169}, "observed_value_status": "AVAILABLE", "evidence_text": "(정보통신 분야) 인공지능, 정보방송통신, 국가지능정보화, 우정사업 등의 발전에 기여한 공적이 뛰어난 단체 등\n- (정보문화 분야) 디지털 격차ㆍ역기능 해소 및 디지털 역량 강화 등을 통해 디지털 포용사회 구현과 건전한 정보문화 창달에 기여한 다음과 같은 공적을 갖춘 자\n※ 자세한 지원대상 공고문 참조"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## BIZINFO:PBLN_000000000128028 (BIZINFO)

### Notice title
[부산] 중구 2027년 수산자원보호직불제 사업 신청 공고

### Source excerpt (condition_texts.eligibility.text)
```text
강화된 자원보호 의무를 이행하는 어업인 등
-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사
- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등
```

### Existing v1 candidates
- No candidate record; this is not evidence that no condition exists.

### Gold condition draft
- `GOLD:2OTFWPYD5V3ZWNU3VCZ4T4XY` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "등록 어업인 등"** ? 어업경영 관련 정보 등을 등록한 어업인 등 (span 62:85; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:H2CEZ2GPY6OJL7PGCHYX7LQQ` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "상법상 회사"** ? 「상법」상 회사 (span 134:142; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:5ZJTE4BIUAX3EUSQ5ITDADN3` **ELIGIBILITY / LICENSE_STATUS / LICENSE_STATUS / IN ["면허", "허가"]** ? 면허 또는 허가를 받은 (span 122:134; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:FYNJKZMSMVCDXR7TNUWZ47GV` **ELIGIBILITY / COMPLIANCE_STATUS / COMPLIANCE_STATUS / UNRESOLVED ** ? 강화된 자원보호 의무를 이행하는 어업인 등 (span 0:23; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 실제 의무 이행과 이행계획서 제출을 별도 조건으로 보존.
- `GOLD:V4RWLG7CMNSKJ2JGFZXY2PGU` **ELIGIBILITY / COMPLIANCE_PLAN_CONTENT / COMPLIANCE_PLAN_CONTENT / EQ "기본의무 포함"** ? 기본의무 (span 186:190; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:E4CL7MPMP5KOLIG4HDGYGSEC` **ELIGIBILITY / OPTIONAL_DUTY_COUNT / OPTIONAL_DUTY_COUNT / GTE 2** ? 2개 이상의 선택의무 (span 192:203; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:WQMKMUOWL2FYX3PID6ZG5JB5` **ELIGIBILITY / DOCUMENT_SUBMISSION / DOCUMENT_SUBMISSION / EQ "이행계획서 제출"** ? 이행계획서를 제출한 (span 204:214; decision_possible=False; v1 comparison=MISSING in v1 candidates)

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:85F8FB3BEEF8DCF181DCC323", "operator": "AND", "children": [{"node_type": "LOGICAL_GROUP", "group_id": "AST:0F34580068E7DAD3AA05E218", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:2OTFWPYD5V3ZWNU3VCZ4T4XY"}, {"node_type": "LOGICAL_GROUP", "group_id": "AST:2EF6C48D0751D3CDD72999CD", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:H2CEZ2GPY6OJL7PGCHYX7LQQ"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:5ZJTE4BIUAX3EUSQ5ITDADN3"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 220}, "observed_value_status": "AVAILABLE", "evidence_text": "강화된 자원보호 의무를 이행하는 어업인 등\n-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사\n- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등"}}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 220}, "observed_value_status": "AVAILABLE", "evidence_text": "강화된 자원보호 의무를 이행하는 어업인 등\n-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사\n- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등"}}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:FYNJKZMSMVCDXR7TNUWZ47GV"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:V4RWLG7CMNSKJ2JGFZXY2PGU"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:E4CL7MPMP5KOLIG4HDGYGSEC"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:WQMKMUOWL2FYX3PID6ZG5JB5"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 220}, "observed_value_status": "AVAILABLE", "evidence_text": "강화된 자원보호 의무를 이행하는 어업인 등\n-「농어업경영체 육성 및 지원에 관한 법률」제4조제1항제2호에 따라 어업경영 관련 정보 등을 등록한 어업인 등과「수산업법」제7조ㆍ제40조 및「내수면어업법」제6조ㆍ제9조에 따라 면허 또는 허가를 받은「상법」상 회사\n- 법 시행령 제6조에 따라 해양수산부장관이 정하여 고시하는 준수의무 중에서 기본의무와 2개 이상의 선택의무 이행계획서를 제출한 어업인 등"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

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

### Existing v1 candidates
- No candidate record; this is not evidence that no condition exists.

### Gold condition draft
- `GOLD:DU2HLVAYWPB6SKGAML6OVCZT` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "제조업"** ? 제조업(스마트제조, 제조AI 등) (span 2:20; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:2WU5YEFDVE7UDITJV6EULMRF` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "지식기반산업"** ? 지식기반산업(지식산업, 첨단기술활용 산업) (span 23:46; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:XZKE244L734HHYEPDRD6GFTT` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "정보통신산업"** ? 정보통신산업 (span 49:55; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:XHAXFTDSRBRHA5EOJ24RXVKE` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "전문·과학·기술 서비스업 등"** ? 전문, 과학 및 기술 서비스업 등 (span 58:76; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:106B9E14861F73D031613966", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:DU2HLVAYWPB6SKGAML6OVCZT"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:2WU5YEFDVE7UDITJV6EULMRF"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:XZKE244L734HHYEPDRD6GFTT"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:XHAXFTDSRBRHA5EOJ24RXVKE"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 76}, "observed_value_status": "AVAILABLE", "evidence_text": "- 제조업(스마트제조, 제조AI 등)\n- 지식기반산업(지식산업, 첨단기술활용 산업)\n- 정보통신산업\n- 전문, 과학 및 기술 서비스업 등"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## KSTARTUP:179386 (KSTARTUP)

### Notice title
2026년 창업-Bus 프로그램「강원브릿지 화요IR」 참여기업 모집

### Source excerpt (condition_texts.eligibility.text)
```text
창업 7년 이내 초격차 창업기업
※ 중점분야: 바이오·헬스, AI·빅데이터
※ 강원 7대 전략산업(바이오·헬스, 반도체, 미래에너지, 미래모빌리티, 방위산업, 기후테크, 푸드테크) 분야 기업 우대
```

### Existing v1 candidates
- `CND:WCH2XWWHUIKN72BIERPWKSNC` 창업 7년 이내 [BUSINESS_AGE] ? MATCH; gold: GOLD:3QRRTUPV5LYHVHJELE2BPBZ4
- `CND:UZVVBGQJZQPGZWI36PNRQETP` 창업기업 [BUSINESS_TYPE] ? PARTIAL_MATCH; gold: GOLD:4PHRWOONTBVTFZAQ5BJAHJQB
- `CND:KF7GL6UKP2LSISJWOOBBS5EP` 우대 [None] ? UNRESOLVED; gold: none
- `CND:Q4C23HXVQPRL44C5YF2VY4UL` 강원 [BUSINESS_LOCATION] ? UNRESOLVED; gold: none

### Gold condition draft
- `GOLD:4PHRWOONTBVTFZAQ5BJAHJQB` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "초격차 창업기업"** ? 초격차 창업기업 (span 9:17; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:3QRRTUPV5LYHVHJELE2BPBZ4` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 7** ? 창업 7년 이내 (span 0:8; decision_possible=False; v1 comparison=MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:RBZS3UUFH5NAU6JE3BBRORZA` **ELIGIBILITY / INDUSTRY / INDUSTRY / IN ["바이오·헬스", "AI·빅데이터"]** ? 바이오·헬스, AI·빅데이터 (span 26:41; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:BX7MXK4OPKU5KLAOI53KHSPV` **PREFERENCE / INDUSTRY / INDUSTRY / IN ["바이오·헬스", "반도체", "미래에너지", "미래모빌리티", "방위산업", "기후테크", "푸드테크"]** ? 강원 7대 전략산업(바이오·헬스, 반도체, 미래에너지, 미래모빌리티, 방위산업, 기후테크, 푸드테크) 분야 기업 우대 (span 44:109; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 우대 문구는 확인되나 배점·중복 적용 및 판정 세부는 미수집

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:8900CEF28432AC7B6512EE45", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:4PHRWOONTBVTFZAQ5BJAHJQB"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:3QRRTUPV5LYHVHJELE2BPBZ4"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 109}, "observed_value_status": "AVAILABLE", "evidence_text": "창업 7년 이내 초격차 창업기업\n※ 중점분야: 바이오·헬스, AI·빅데이터\n※ 강원 7대 전략산업(바이오·헬스, 반도체, 미래에너지, 미래모빌리티, 방위산업, 기후테크, 푸드테크) 분야 기업 우대"}}`
- ELIGIBILITY / evaluation UNKNOWN / fulfillment UNKNOWN:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:RBZS3UUFH5NAU6JE3BBRORZA"}`
- PREFERENCE / evaluation SELECTION / fulfillment SELECTION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:BX7MXK4OPKU5KLAOI53KHSPV"}`

### Unresolved relations
- Focus-sector statement may scope the program but is not explicitly mandatory. (IDs GOLD:4PHRWOONTBVTFZAQ5BJAHJQB,GOLD:3QRRTUPV5LYHVHJELE2BPBZ4,GOLD:RBZS3UUFH5NAU6JE3BBRORZA; span 26:41)

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## KSTARTUP:179676 (KSTARTUP)

### Notice title
2026 별별상상 스타트업 챌린지

### Source excerpt (condition_texts.eligibility.text)
```text
전국의 대학생 및 대학원생 누구나 지원 가능
```

### Existing v1 candidates
- `CND:BQMMBZFKARDMWVKXF2T3YFR4` 전국 [BUSINESS_LOCATION] ? UNRESOLVED; gold: none

### Gold condition draft
- `GOLD:CKKR3STQYAYFKUA7VJTUWM6F` **ELIGIBILITY / APPLICANT_TYPE / APPLICANT_TYPE / IN ["대학생", "대학원생"]** ? 대학생 및 대학원생 (span 4:14; decision_possible=False; v1 comparison=MISSING in v1 candidates)

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:CKKR3STQYAYFKUA7VJTUWM6F"}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 
