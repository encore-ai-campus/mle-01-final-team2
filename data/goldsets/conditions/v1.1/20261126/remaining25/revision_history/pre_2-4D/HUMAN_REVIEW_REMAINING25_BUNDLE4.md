# Development review bundle 4/5

Draft only: UNREVIEWED / PENDING. Provided source text is an excerpt with UNKNOWN completeness; completeness of the whole notice is not asserted.

## BIZINFO:PBLN_000000000126715 (BIZINFO)

### Notice title
2026년 산업기술국제협력(양자-스페인) 접수 공고

### Source excerpt (condition_texts.eligibility.text)
```text
기업, 대학, 연구기관, 의료기관(산업기술혁신사업 공통 운영요령 제2조(용어의 정의))
- 주관연구개발기관 및 공동연구개발기관 中 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과하고, 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유하고 있는 국내사업자
```

### Existing extracted candidates (frozen v1)
- `CND:HRCRNQLAG4IATHKU4GIYZJ2H` 창업 1년 이상 [ELIGIBILITY/BUSINESS_AGE] ? PARTIAL_MATCH; linked gold IDs: GOLD:3MRUKEGAWLDCW5KRDJ7TFNKK

### Proposed gold condition draft
- `GOLD:OUZHPRGZI23NUZECB6R54KV7` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["기업", "대학", "연구기관", "의료기관"]** ? 기업, 대학, 연구기관, 의료기관 (source span 0:18; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:3MRUKEGAWLDCW5KRDJ7TFNKK` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / GTE 1** ? 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과 (source span 73:121; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:AJ35WCRRZVN7L2ZSKRGNFG4K` **ELIGIBILITY / CERTIFICATION / CERTIFICATION / EQ "기업부설연구소 인정서"** ? 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유 (source span 125:158; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:OUZHPRGZI23NUZECB6R54KV7"}`

### Unresolved logical relations
- Business age and certification apply to domestic-company applicants; conditional scope within the broader applicant set needs review. (condition IDs: GOLD:OUZHPRGZI23NUZECB6R54KV7, GOLD:3MRUKEGAWLDCW5KRDJ7TFNKK, GOLD:AJ35WCRRZVN7L2ZSKRGNFG4K; source span 73:121)

### Differences and review questions
- Candidate `CND:HRCRNQLAG4IATHKU4GIYZJ2H`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## BIZINFO:PBLN_000000000126899 (BIZINFO)

### Notice title
[강원] 홍천군 2026년 사물인터넷(IoT) 측정기기 부착 지원사업 공고

### Source excerpt (condition_texts.eligibility.text)
```text
홍천군 관내 소재지의 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 중 IoT 측정기기 부착 의무 대상 사업장
```

### Existing extracted candidates (frozen v1)
- `CND:I2QXS2GLUWZY2LPNQT6EJWEV` 중소기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:LKWRFJ6A7XQD3ICB6HMSSM7O

### Proposed gold condition draft
- `GOLD:2FRP6BOHSIGFNYBR6HUG6I6V` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "홍천군"** ? 홍천군 관내 소재지 (source span 0:10; decision possible=True; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:LKWRFJ6A7XQD3ICB6HMSSM7O` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["중기업", "소기업"]** ? 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 (source span 12:41; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:FGIYR2BDYXJPX6JALIWWH23S` **ELIGIBILITY / REGULATORY_STATUS / REGULATORY_STATUS / EQ "IoT 측정기기 부착 의무 대상"** ? IoT 측정기기 부착 의무 대상 사업장 (source span 44:65; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:BIZINFO:PBLN_000000000126899:ELIGIBILITY:AND", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:2FRP6BOHSIGFNYBR6HUG6I6V"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:LKWRFJ6A7XQD3ICB6HMSSM7O"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:FGIYR2BDYXJPX6JALIWWH23S"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 65}, "observed_value_status": "AVAILABLE", "evidence_text": "홍천군 관내 소재지의 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 중 IoT 측정기기 부착 의무 대상 사업장"}}`

### Differences and review questions
- Candidate `CND:I2QXS2GLUWZY2LPNQT6EJWEV`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:177447 (KSTARTUP)

### Notice title
「2026년 서울시 지역연계형 청년 창업 지원사업」 <넥스트로컬 8기> 참여자 모집공고

### Source excerpt (condition_texts.eligibility.text)
```text
ㅇ 대상 : 서울시 거주 청년(만 19~39세)

※신청일 기준, 대상의 나이에 부합해야 함
※대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함
※주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출), 관련 증빙서류 별첨 필수
※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함
- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장
```

### Existing extracted candidates (frozen v1)
- `CND:BUCZM3BXYMTYNACDAS47T42D` 서울 [ELIGIBILITY/BUSINESS_LOCATION] ? PARTIAL_MATCH; linked gold IDs: GOLD:OGLHW4XF5FDTNNENTVL7FARE
- `CND:CUBRQ6S66FNJBGGF52NU2JGP` 대표자 및 팀원이 모두 만 19~39세 이하 [ELIGIBILITY/REPRESENTATIVE_AGE] ? PARTIAL_MATCH; linked gold IDs: GOLD:FJL2DEH3K3PIW6GMU3A5EJ5E

### Proposed gold condition draft
- `GOLD:FJL2DEH3K3PIW6GMU3A5EJ5E` **ELIGIBILITY / APPLICANT_AGE / APPLICANT_AGE / BETWEEN [19, 39]** ? 대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함 (source span 53:86; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:OGLHW4XF5FDTNNENTVL7FARE` **ELIGIBILITY / RESIDENCE / RESIDENCE / EQ "서울특별시"** ? 주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출) (source span 88:120; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:177447:REVIEW:AND:2", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:FJL2DEH3K3PIW6GMU3A5EJ5E"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:OGLHW4XF5FDTNNENTVL7FARE"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 239}, "observed_value_status": "AVAILABLE", "evidence_text": "ㅇ 대상 : 서울시 거주 청년(만 19~39세)\n\n※신청일 기준, 대상의 나이에 부합해야 함\n※대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함\n※주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출), 관련 증빙서류 별첨 필수\n※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함\n- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장"}}`

### Exceptions and qualifiers
- 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함
- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장 ? applies to GOLD:FJL2DEH3K3PIW6GMU3A5EJ5E; effect=UNKNOWN, application=UNKNOWN (source span 140:239)

### Differences and review questions
- Candidate `CND:BUCZM3BXYMTYNACDAS47T42D`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:CUBRQ6S66FNJBGGF52NU2JGP`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:177506 (KSTARTUP)

### Notice title
SWITCH 2026 K-스타트업 통합관 참여기관 모집공고

### Source excerpt (condition_texts.eligibility.text)
```text
※ 아래 3가지 자격조건을 모두 충족하여야 함
① SWITCH  2026 'K-스타트업 통합관' 참여를 희망하는 지방정부, 공공기관, 민간기관 및 협·단체
* 단, 민간기업의 경우 기업신용평가등급 'B등급' 이상
② 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 지방정부, 공공기관, 민간기관 및 협·단체
③ K-스타트업 통합관 협약금(기업당 10백만원) 부담이 가능한 지방정부, 공공기관, 민간기관 및 협·단체
```

### Existing extracted candidates (frozen v1)
- `CND:WLWLBIW554GDNEAWXEM3VNJQ` 창업기업 [ELIGIBILITY/BUSINESS_TYPE] ? PARTIAL_MATCH; linked gold IDs: GOLD:JWLQDEXXQLVXF6EUNKQFDZ2X

### Proposed gold condition draft
- `GOLD:VJSL6VQ2CY43HZWX4AEKBSDK` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["지방정부", "공공기관", "민간기관", "협·단체"]** ? 지방정부, 공공기관, 민간기관 및 협·단체 (source span 63:86; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:GET3L77TXXYGYGWP7JPMN4SL` **ELIGIBILITY / CREDIT_RATING / CREDIT_RATING / GTE "B"** ? 민간기업의 경우 기업신용평가등급 'B등급' 이상 (source span 92:118; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)
- `GOLD:JWLQDEXXQLVXF6EUNKQFDZ2X` **ELIGIBILITY / QUALITATIVE_QUALIFICATION / RECOMMENDATION_CAPABILITY / UNRESOLVED ** ? 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 (source span 121:157; decision possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:CX2TXKJW7NGX3OHWTMFULSKM` **ELIGIBILITY / FINANCIAL_CAPACITY / FINANCIAL_CAPACITY / GTE 10000000** ? K-스타트업 통합관 협약금(기업당 10백만원) 부담이 가능한 (source span 184:217; decision possible=False; v1 comparison=MISSING: no corresponding v1 candidate)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:177506:REVIEW:AND:3", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:VJSL6VQ2CY43HZWX4AEKBSDK"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:JWLQDEXXQLVXF6EUNKQFDZ2X"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:CX2TXKJW7NGX3OHWTMFULSKM"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 241}, "observed_value_status": "AVAILABLE", "evidence_text": "※ 아래 3가지 자격조건을 모두 충족하여야 함\n① SWITCH  2026 'K-스타트업 통합관' 참여를 희망하는 지방정부, 공공기관, 민간기관 및 협·단체\n* 단, 민간기업의 경우 기업신용평가등급 'B등급' 이상\n② 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 지방정부, 공공기관, 민간기관 및 협·단체\n③ K-스타트업 통합관 협약금(기업당 10백만원) 부담이 가능한 지방정부, 공공기관, 민간기관 및 협·단체"}}`

### Unresolved logical relations
- Private-company-only credit-rating condition is conditional; retain unresolved for human review. (condition IDs: GOLD:VJSL6VQ2CY43HZWX4AEKBSDK, GOLD:GET3L77TXXYGYGWP7JPMN4SL; source span 87:118)

### Differences and review questions
- Candidate `CND:WLWLBIW554GDNEAWXEM3VNJQ`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 

## KSTARTUP:177857 (KSTARTUP)

### Notice title
26년 6월 스타트업 언론 홍보 지원사업 참가사 모집 공고(1차)

### Source excerpt (condition_texts.eligibility.text)
```text
1. 예비창업자
2. 창업 7년 이내 초기 기업
```

### Existing extracted candidates (frozen v1)
- `CND:7V5GC6G2C4PZVYWA7QLEHKWD` 예비창업자 [ELIGIBILITY/BUSINESS_TYPE] ? MATCH; linked gold IDs: GOLD:7RQ7V57XGFGV3Y2OURGYGGR2
- `CND:OIK3OPO2ZX3KOQMBOJ762KG6` 창업 7년 이내 [ELIGIBILITY/BUSINESS_AGE] ? PARTIAL_MATCH; linked gold IDs: GOLD:JIBE67W3DZUHFIJJBYZP6QR5

### Proposed gold condition draft
- `GOLD:7RQ7V57XGFGV3Y2OURGYGGR2` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "예비창업자"** ? 예비창업자 (source span 3:8; decision possible=True; v1 comparison=MATCH)
- `GOLD:JIBE67W3DZUHFIJJBYZP6QR5` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 7** ? 창업 7년 이내 초기 기업 (source span 12:26; decision possible=False; v1 comparison=PARTIAL_MATCH)

### Proposed logic draft
- ELIGIBILITY / evaluation=APPLICATION / fulfillment=APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "DRAFT:KSTARTUP:177857:REVIEW:OR:2", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:7RQ7V57XGFGV3Y2OURGYGGR2"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:JIBE67W3DZUHFIJJBYZP6QR5"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 26}, "observed_value_status": "AVAILABLE", "evidence_text": "1. 예비창업자\n2. 창업 7년 이내 초기 기업"}}`

### Differences and review questions
- Candidate `CND:7V5GC6G2C4PZVYWA7QLEHKWD`: MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Candidate `CND:OIK3OPO2ZX3KOQMBOJ762KG6`: PARTIAL_MATCH ? 원문 구절 겹침 기준 자동 정렬 초안; 사람 확인 필요
- Verify omissions, candidate semantics, branch scope, external-document details, and source completeness. Automatic alignment is not a confirmed error or approval.

### Reviewer input
- Approve: [ ]
- Amendments: 
- Unable to decide / reason: 
- Reviewer / date: 
