# Development review bundle 4/5

Draft only: UNREVIEWED / PENDING. Source is a condition excerpt; completeness of the whole notice remains UNKNOWN.

## BIZINFO:PBLN_000000000126715 (BIZINFO)

### Notice title
2026년 산업기술국제협력(양자-스페인) 접수 공고

### Source excerpt (condition_texts.eligibility.text)
```text
기업, 대학, 연구기관, 의료기관(산업기술혁신사업 공통 운영요령 제2조(용어의 정의))
- 주관연구개발기관 및 공동연구개발기관 中 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과하고, 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유하고 있는 국내사업자
```

### Existing v1 candidates
- `CND:HRCRNQLAG4IATHKU4GIYZJ2H` 창업 1년 이상 [BUSINESS_AGE] ? PARTIAL_MATCH; gold: GOLD:3HUEFEUMXRG65C4ERUYF3QZM

### Gold condition draft
- `GOLD:NTM4C6LSAWVPGV3LWZKNLHOF` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["기업", "대학", "연구기관", "의료기관"]** ? 기업, 대학, 연구기관, 의료기관 (span 0:18; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:3HUEFEUMXRG65C4ERUYF3QZM` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / GTE 1** ? 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과 (span 73:121; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 접수마감일은 공고 발췌에 날짜 미기재. 국내기업에만 적용.
- `GOLD:W7UTQQGSTSDQWE6TTFAXCLGG` **ELIGIBILITY / CERTIFICATION / CERTIFICATION / EQ "기업부설연구소 인정서"** ? 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유 (span 125:158; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:NTM4C6LSAWVPGV3LWZKNLHOF"}`
- ELIGIBILITY / evaluation UNKNOWN / fulfillment UNKNOWN:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:0921DE8112B61EB145DB5631", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:3HUEFEUMXRG65C4ERUYF3QZM"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:W7UTQQGSTSDQWE6TTFAXCLGG"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 169}, "observed_value_status": "AVAILABLE", "evidence_text": "기업, 대학, 연구기관, 의료기관(산업기술혁신사업 공통 운영요령 제2조(용어의 정의))\n- 주관연구개발기관 및 공동연구개발기관 中 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과하고, 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유하고 있는 국내사업자"}}`

### Unresolved relations
- 업력·연구소 조건은 기관 유형 중 국내기업에게만 적용. 조건부 연결은 판정 비허용 상태로 유지. (IDs GOLD:NTM4C6LSAWVPGV3LWZKNLHOF,GOLD:3HUEFEUMXRG65C4ERUYF3QZM,GOLD:W7UTQQGSTSDQWE6TTFAXCLGG; span 73:121)

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## BIZINFO:PBLN_000000000126899 (BIZINFO)

### Notice title
[강원] 홍천군 2026년 사물인터넷(IoT) 측정기기 부착 지원사업 공고

### Source excerpt (condition_texts.eligibility.text)
```text
홍천군 관내 소재지의 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 중 IoT 측정기기 부착 의무 대상 사업장
```

### Existing v1 candidates
- `CND:I2QXS2GLUWZY2LPNQT6EJWEV` 중소기업 [BUSINESS_TYPE] ? PARTIAL_MATCH; gold: GOLD:HZ53XBKB4MYLIOEBBVU6PVLN

### Gold condition draft
- `GOLD:LO2DVXPVU5RGGJBPZELBXR7N` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "홍천군"** ? 홍천군 관내 소재지 (span 0:10; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:HZ53XBKB4MYLIOEBBVU6PVLN` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["중기업", "소기업"]** ? 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 (span 12:41; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:UEUE3CTKYGFJ6XMRJTRWU733` **ELIGIBILITY / REGULATORY_STATUS / REGULATORY_STATUS / EQ "IoT 측정기기 부착 의무 대상"** ? IoT 측정기기 부착 의무 대상 사업장 (span 44:65; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:900FD30C45559BF75FBBBFDB", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:LO2DVXPVU5RGGJBPZELBXR7N"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:HZ53XBKB4MYLIOEBBVU6PVLN"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:UEUE3CTKYGFJ6XMRJTRWU733"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 65}, "observed_value_status": "AVAILABLE", "evidence_text": "홍천군 관내 소재지의 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 중 IoT 측정기기 부착 의무 대상 사업장"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

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

### Existing v1 candidates
- `CND:BUCZM3BXYMTYNACDAS47T42D` 서울 [BUSINESS_LOCATION] ? UNRESOLVED; gold: none
- `CND:CUBRQ6S66FNJBGGF52NU2JGP` 대표자 및 팀원이 모두 만 19~39세 이하 [REPRESENTATIVE_AGE] ? UNRESOLVED; gold: none

### Gold condition draft
- `GOLD:UMIN5GYYJI25MI4RXWSOFKZQ` **ELIGIBILITY / APPLICANT_AGE / APPLICANT_AGE / BETWEEN [19, 39]** ? 대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함 (span 53:86; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: Age range is stated at application date; the exact calendar date and military-service extension effect require review.
- `GOLD:QBTTRF3JZNJMBATWCAT3JTGC` **ELIGIBILITY / RESIDENCE / RESIDENCE / EQ "서울특별시"** ? 주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출) (span 88:120; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:2DQHTBU7LBCMIF3TV7UBSOB7` **ELIGIBILITY / DOCUMENT_SUBMISSION / DOCUMENT_SUBMISSION / EQ "관련 증빙서류 제출"** ? 관련 증빙서류 별첨 필수 (span 122:135; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 증빙 제출 여부는 거주 자격 충족과 별도 관리.

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:FC615131CB83120CEB90CA56", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:UMIN5GYYJI25MI4RXWSOFKZQ"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:QBTTRF3JZNJMBATWCAT3JTGC"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:2DQHTBU7LBCMIF3TV7UBSOB7"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 239}, "observed_value_status": "AVAILABLE", "evidence_text": "ㅇ 대상 : 서울시 거주 청년(만 19~39세)\n\n※신청일 기준, 대상의 나이에 부합해야 함\n※대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함\n※주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출), 관련 증빙서류 별첨 필수\n※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함\n- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장"}}`

### Exceptions
- ※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함
- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장 ? {"upper_age_by_service_duration": [{"duration": "<1 YEAR", "upper_age": 40}, {"duration": ">=1 AND <2 YEARS", "upper_age": 41}, {"duration": ">=2 YEARS", "upper_age": 42}], "evidence_required": ["병적증명서", "전역증 등"]}; effect=UNKNOWN, application=UNKNOWN, targets=GOLD:UMIN5GYYJI25MI4RXWSOFKZQ

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

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

### Existing v1 candidates
- `CND:WLWLBIW554GDNEAWXEM3VNJQ` 창업기업 [BUSINESS_TYPE] ? FALSE_POSITIVE; gold: none

### Gold condition draft
- `GOLD:SJDYLI2CGQAITBHYLES4CBG3` **ELIGIBILITY / APPLICANT_TYPE / APPLICANT_TYPE / IN ["지방정부", "공공기관", "민간기관", "협·단체"]** ? 지방정부, 공공기관, 민간기관 및 협·단체 (span 63:86; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:Q7VA6LVCU7MDG6O4EPAR54ZB` **ELIGIBILITY / CREDIT_RATING / CREDIT_RATING / UNRESOLVED "B등급 이상"** ? 기업신용평가등급 'B등급' 이상 (span 101:118; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 등급 순서를 문자열 사전식 비교로 처리하지 않음. 등급 체계 매핑 미확인.
- `GOLD:A5ESK53EUM2F5O2DCLPVI4A2` **ELIGIBILITY / ORGANIZATION_CAPABILITY / RECOMMENDATION_CAPABILITY / UNRESOLVED ** ? 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 (span 121:157; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 추천 대상 창업기업을 신청기관의 사업자 유형으로 해석하지 않음.
- `GOLD:OKFYXEH7HYJI2G267KCSYI7B` **ELIGIBILITY / FINANCIAL_CAPACITY / FINANCIAL_CAPACITY / GTE 10000000** ? 협약금(기업당 10백만원) 부담이 가능한 (span 195:217; decision_possible=False; v1 comparison=MISSING in v1 candidates)

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:C70B8481EDF77108619BE5F3", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:SJDYLI2CGQAITBHYLES4CBG3"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:A5ESK53EUM2F5O2DCLPVI4A2"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:OKFYXEH7HYJI2G267KCSYI7B"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 241}, "observed_value_status": "AVAILABLE", "evidence_text": "※ 아래 3가지 자격조건을 모두 충족하여야 함\n① SWITCH  2026 'K-스타트업 통합관' 참여를 희망하는 지방정부, 공공기관, 민간기관 및 협·단체\n* 단, 민간기업의 경우 기업신용평가등급 'B등급' 이상\n② 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 지방정부, 공공기관, 민간기관 및 협·단체\n③ K-스타트업 통합관 협약금(기업당 10백만원) 부담이 가능한 지방정부, 공공기관, 민간기관 및 협·단체"}}`
- ELIGIBILITY / evaluation UNKNOWN / fulfillment UNKNOWN:

  `{"node_type": "CONDITION_REF", "condition_id": "GOLD:Q7VA6LVCU7MDG6O4EPAR54ZB"}`

### Unresolved relations
- 신용등급은 민간기업 신청기관에만 적용. AST상의 조건부 분기 표현을 보류. (IDs GOLD:SJDYLI2CGQAITBHYLES4CBG3,GOLD:Q7VA6LVCU7MDG6O4EPAR54ZB; span 101:118)

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## KSTARTUP:177857 (KSTARTUP)

### Notice title
26년 6월 스타트업 언론 홍보 지원사업 참가사 모집 공고(1차)

### Source excerpt (condition_texts.eligibility.text)
```text
1. 예비창업자
2. 창업 7년 이내 초기 기업
```

### Existing v1 candidates
- `CND:7V5GC6G2C4PZVYWA7QLEHKWD` 예비창업자 [BUSINESS_TYPE] ? MATCH; gold: GOLD:GFXFQQ34KQIJO7QQXX6QZN3W
- `CND:OIK3OPO2ZX3KOQMBOJ762KG6` 창업 7년 이내 [BUSINESS_AGE] ? PARTIAL_MATCH; gold: GOLD:XV7NNESGEASTNJF7W3QA6KTS

### Gold condition draft
- `GOLD:GFXFQQ34KQIJO7QQXX6QZN3W` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "예비창업자"** ? 예비창업자 (span 3:8; decision_possible=False; v1 comparison=MATCH)
- `GOLD:XV7NNESGEASTNJF7W3QA6KTS` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 7** ? 창업 7년 이내 초기 기업 (span 12:26; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:3DB73A4D20929E13654224EF", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:GFXFQQ34KQIJO7QQXX6QZN3W"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:XV7NNESGEASTNJF7W3QA6KTS"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 26}, "observed_value_status": "AVAILABLE", "evidence_text": "1. 예비창업자\n2. 창업 7년 이내 초기 기업"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 
