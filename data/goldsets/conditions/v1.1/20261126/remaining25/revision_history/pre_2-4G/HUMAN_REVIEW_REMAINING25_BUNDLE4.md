# Development review bundle 4/5

Human approval status is shown per notice. Approval covers the provided excerpt only; source completeness remains UNKNOWN and decision_possible remains false.

## BIZINFO:PBLN_000000000126715 (BIZINFO; VERIFIED)

### Notice title
2026년 산업기술국제협력(양자-스페인) 접수 공고

### Source excerpt
```text
기업, 대학, 연구기관, 의료기관(산업기술혁신사업 공통 운영요령 제2조(용어의 정의))
- 주관연구개발기관 및 공동연구개발기관 中 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과하고, 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유하고 있는 국내사업자
```

### Existing v1 candidates
- CND:HRCRNQLAG4IATHKU4GIYZJ2H: 창업 1년 이상

### Gold conditions
- `GOLD:NTM4C6LSAWVPGV3LWZKNLHOF` ELIGIBILITY / BUSINESS_TYPE / IN / ["기업", "대학", "연구기관", "의료기관"]; source [0:18] `기업, 대학, 연구기관, 의료기관`; review_status=VERIFIED; decision_possible=False
  - Scope: 지원 대상 기관 유형; 국내기업 추가조건은 별도 조건부 범위; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": 18, "evidence_text": "기업, 대학, 연구기관, 의료기관", "document_id": null, "evidence_id": null}]
- `GOLD:3HUEFEUMXRG65C4ERUYF3QZM` ELIGIBILITY / BUSINESS_AGE / GTE / 1; source [73:121] `국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과`; review_status=VERIFIED; decision_possible=False
  - Scope: 주관·공동연구개발기관 중 국내기업만; 접수마감일 현재; reference_date_type=APPLICATION_END; temporal={"anchor_event": "UNKNOWN", "fixed_reference_date": null, "offset_value": 1, "offset_unit": "YEAR", "operator": "GTE", "inclusive": true, "applies_to": "Application submission deadline (closing date), actual calendar date unknown; no exact anchor-event enum.", "anchor_date_known": false}
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 73, "end_char": 121, "evidence_text": "국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과", "document_id": null, "evidence_id": null}]
- `GOLD:W7UTQQGSTSDQWE6TTFAXCLGG` ELIGIBILITY / CERTIFICATION / EQ / "기업부설연구소 인정서"; source [125:158] `한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유`; review_status=VERIFIED; decision_possible=False
  - Scope: 주관·공동연구개발기관 중 국내기업만; 한국산업기술진흥협회 발급 인정서; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 125, "end_char": 158, "evidence_text": "한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:78F8CED914A482235ACF",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "CONDITION_REF",
      "condition_id": "GOLD:NTM4C6LSAWVPGV3LWZKNLHOF"
    },
    "review_status": "VERIFIED"
  },
  {
    "section_id": "SECTION:51681137CFD0A03E30B8",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "UNKNOWN",
    "fulfillment_phase": "UNKNOWN",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:0921DE8112B61EB145DB5631",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:3HUEFEUMXRG65C4ERUYF3QZM"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:W7UTQQGSTSDQWE6TTFAXCLGG"
        }
      ],
      "review_status": "VERIFIED",
      "evidence": {
        "source_system": "BIZINFO",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 169
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "기업, 대학, 연구기관, 의료기관(산업기술혁신사업 공통 운영요령 제2조(용어의 정의))\n- 주관연구개발기관 및 공동연구개발기관 中 국내기업은 접수마감일 현재 사업자등록증 및 법인등기부등본 기준으로 창업 1년 이상 경과하고, 한국산업기술진흥협회가 발급한 “기업부설연구소 인정서“를 보유하고 있는 국내사업자"
      }
    },
    "review_status": "VERIFIED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [],
  "unresolved_relations": [
    {
      "relation_id": "REL:43CB79D2C290A8B1A4E3",
      "gold_condition_ids": [
        "GOLD:NTM4C6LSAWVPGV3LWZKNLHOF",
        "GOLD:3HUEFEUMXRG65C4ERUYF3QZM",
        "GOLD:W7UTQQGSTSDQWE6TTFAXCLGG"
      ],
      "evidence_reference": {
        "start_char": 73,
        "end_char": 121
      },
      "reason": "업력·연구소 조건은 기관 유형 중 국내기업에게만 적용. 조건부 연결은 판정 비허용 상태로 유지.",
      "review_comment": "Unresolved; excluded from automated decision pending human review."
    }
  ]
}
```

### Review decision
Human approved on 2026-11-26.

## BIZINFO:PBLN_000000000126899 (BIZINFO; VERIFIED)

### Notice title
[강원] 홍천군 2026년 사물인터넷(IoT) 측정기기 부착 지원사업 공고

### Source excerpt
```text
홍천군 관내 소재지의 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 중 IoT 측정기기 부착 의무 대상 사업장
```

### Existing v1 candidates
- CND:I2QXS2GLUWZY2LPNQT6EJWEV: 중소기업

### Gold conditions
- `GOLD:LO2DVXPVU5RGGJBPZELBXR7N` ELIGIBILITY / BUSINESS_LOCATION / EQ / "홍천군"; source [0:10] `홍천군 관내 소재지`; review_status=VERIFIED; decision_possible=False
  - Scope: 사업장 소재지; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": 10, "evidence_text": "홍천군 관내 소재지", "document_id": null, "evidence_id": null}]
- `GOLD:HZ53XBKB4MYLIOEBBVU6PVLN` ELIGIBILITY / BUSINESS_TYPE / IN / ["중기업", "소기업"]; source [12:41] `「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업`; review_status=VERIFIED; decision_possible=False
  - Scope: 법령상 기업 규모; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 12, "end_char": 41, "evidence_text": "「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업", "document_id": null, "evidence_id": null}]
- `GOLD:UEUE3CTKYGFJ6XMRJTRWU733` ELIGIBILITY / REGULATORY_STATUS / EQ / "IoT 측정기기 부착 의무 대상"; source [44:65] `IoT 측정기기 부착 의무 대상 사업장`; review_status=VERIFIED; decision_possible=False
  - Scope: 법정 부착 의무 사업장; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 44, "end_char": 65, "evidence_text": "IoT 측정기기 부착 의무 대상 사업장", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:E4B2A29037F3423EBECC",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:900FD30C45559BF75FBBBFDB",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:LO2DVXPVU5RGGJBPZELBXR7N"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:HZ53XBKB4MYLIOEBBVU6PVLN"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:UEUE3CTKYGFJ6XMRJTRWU733"
        }
      ],
      "review_status": "VERIFIED",
      "evidence": {
        "source_system": "BIZINFO",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 65
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "홍천군 관내 소재지의 「중소기업기본법」시행령 제3조제1항에 따른 중ㆍ소기업 중 IoT 측정기기 부착 의무 대상 사업장"
      }
    },
    "review_status": "VERIFIED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [],
  "unresolved_relations": []
}
```

### Review decision
Human approved on 2026-11-26.

## KSTARTUP:177447 (KSTARTUP; VERIFIED)

### Notice title
「2026년 서울시 지역연계형 청년 창업 지원사업」 <넥스트로컬 8기> 참여자 모집공고

### Source excerpt
```text
ㅇ 대상 : 서울시 거주 청년(만 19~39세)

※신청일 기준, 대상의 나이에 부합해야 함
※대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함
※주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출), 관련 증빙서류 별첨 필수
※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함
- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장
```

### Existing v1 candidates
- CND:BUCZM3BXYMTYNACDAS47T42D: 서울
- CND:CUBRQ6S66FNJBGGF52NU2JGP: 대표자 및 팀원이 모두 만 19~39세 이하

### Gold conditions
- `GOLD:UMIN5GYYJI25MI4RXWSOFKZQ` ELIGIBILITY / APPLICANT_AGE / BETWEEN / [19, 39]; source [53:86] `대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함`; review_status=VERIFIED; decision_possible=False
  - Scope: 대표자 및 모든 팀원 각각 만 19~39세; 신청일 기준; reference_date_type=UNKNOWN; temporal={"anchor_event": "APPLICATION", "fixed_reference_date": null, "offset_value": null, "offset_unit": null, "operator": null, "inclusive": true, "applies_to": "대표자와 모든 팀원 각각; 군복무 예외는 개인별 적용", "anchor_date_known": false}
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 53, "end_char": 86, "evidence_text": "대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함", "document_id": null, "evidence_id": null}, {"role": "SUPPORTING", "source_field": "condition_texts.eligibility.text", "start_char": 7, "end_char": 26, "evidence_text": "서울시 거주 청년(만 19~39세)", "document_id": null, "evidence_id": null}]
- `GOLD:QBTTRF3JZNJMBATWCAT3JTGC` ELIGIBILITY / RESIDENCE / EQ / "서울특별시"; source [88:120] `주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출)`; review_status=VERIFIED; decision_possible=False
  - Scope: 서울 거주 증빙 대상 범위(대표자/팀원) 원문상 불명확; reference_date_type=UNKNOWN; temporal={"anchor_event": "APPLICATION", "fixed_reference_date": null, "offset_value": null, "offset_unit": null, "operator": null, "inclusive": true, "applies_to": "주민등록등본 기준 서울 거주; 적용 대상 개인 범위 미확인", "anchor_date_known": false}
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 88, "end_char": 120, "evidence_text": "주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출)", "document_id": null, "evidence_id": null}]
- `GOLD:2DQHTBU7LBCMIF3TV7UBSOB7` ELIGIBILITY / DOCUMENT_SUBMISSION / EQ / "관련 증빙서류 제출"; source [122:135] `관련 증빙서류 별첨 필수`; review_status=VERIFIED; decision_possible=False
  - Scope: 신청 시 증빙 제출; 거주 자격 자체와 구분; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 122, "end_char": 135, "evidence_text": "관련 증빙서류 별첨 필수", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:826D61B57FFACA29F69C",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:FC615131CB83120CEB90CA56",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:UMIN5GYYJI25MI4RXWSOFKZQ"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:QBTTRF3JZNJMBATWCAT3JTGC"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:2DQHTBU7LBCMIF3TV7UBSOB7"
        }
      ],
      "review_status": "VERIFIED",
      "evidence": {
        "source_system": "KSTARTUP",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 239
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "ㅇ 대상 : 서울시 거주 청년(만 19~39세)\n\n※신청일 기준, 대상의 나이에 부합해야 함\n※대표자 및 팀원이 모두 만 19~39세 이하의 청년이어야 함\n※주민등록등본상 서울거주로 확인(신청일 날짜 기준으로 제출), 관련 증빙서류 별첨 필수\n※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함\n- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장"
      }
    },
    "review_status": "VERIFIED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [
    {
      "raw_text": "※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함\n- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장",
      "evidence_reference": {
        "start_char": 136,
        "end_char": 239
      },
      "applies_to_gold_ids": [
        "GOLD:UMIN5GYYJI25MI4RXWSOFKZQ"
      ],
      "linkage_status": "LINKED",
      "review_status": "VERIFIED",
      "review_comment": "The source clearly confirms an individual upper-age extension to 40/41/42 by service duration, with evidence. Existing effect enum cannot execute threshold substitution; application_mode UNKNOWN and decision blocked. Teamwide age requirement remains.",
      "effect": "UNKNOWN",
      "effect_target": "해당 개인의 APPLICANT_AGE 상한",
      "replacement": {
        "upper_age_by_service_duration": [
          {
            "duration": "<1 YEAR",
            "upper_age": 40
          },
          {
            "duration": ">=1 AND <2 YEARS",
            "upper_age": 41
          },
          {
            "duration": ">=2 YEARS",
            "upper_age": 42
          }
        ],
        "evidence_required": [
          "병적증명서",
          "전역증 등"
        ]
      },
      "precondition": "해당 개인의 군복무기간 및 병적증명서/전역증 등 확인",
      "effect_confirmed": true,
      "application_mode": "UNKNOWN",
      "evidence_references": [
        {
          "role": "PRIMARY",
          "source_field": "condition_texts.eligibility.text",
          "start_char": 136,
          "end_char": 239,
          "evidence_text": "※단, 군필자의 경우(병적증명서, 전역증 등 별도 제출) 상한 연령을 다음과 같이 연장함\n- ①군복무기간 1년 미만 : 1세, ②1년 이상~2년 미만 : 2세, ③2년이상 : 3세 연장",
          "document_id": null,
          "evidence_id": null
        }
      ]
    }
  ],
  "unresolved_relations": []
}
```

### Review decision
Human approved on 2026-11-26.

## KSTARTUP:177506 (KSTARTUP; VERIFIED)

### Notice title
SWITCH 2026 K-스타트업 통합관 참여기관 모집공고

### Source excerpt
```text
※ 아래 3가지 자격조건을 모두 충족하여야 함
① SWITCH  2026 'K-스타트업 통합관' 참여를 희망하는 지방정부, 공공기관, 민간기관 및 협·단체
* 단, 민간기업의 경우 기업신용평가등급 'B등급' 이상
② 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 지방정부, 공공기관, 민간기관 및 협·단체
③ K-스타트업 통합관 협약금(기업당 10백만원) 부담이 가능한 지방정부, 공공기관, 민간기관 및 협·단체
```

### Existing v1 candidates
- CND:WLWLBIW554GDNEAWXEM3VNJQ: 창업기업

### Gold conditions
- `GOLD:SJDYLI2CGQAITBHYLES4CBG3` ELIGIBILITY / APPLICANT_TYPE / IN / ["지방정부", "공공기관", "민간기관", "협·단체"]; source [63:86] `지방정부, 공공기관, 민간기관 및 협·단체`; review_status=VERIFIED; decision_possible=False
  - Scope: 통합관 참여 신청기관 유형; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 63, "end_char": 86, "evidence_text": "지방정부, 공공기관, 민간기관 및 협·단체", "document_id": null, "evidence_id": null}]
- `GOLD:Q7VA6LVCU7MDG6O4EPAR54ZB` ELIGIBILITY / CREDIT_RATING / None / "B등급 이상"; source [101:118] `기업신용평가등급 'B등급' 이상`; review_status=VERIFIED; decision_possible=False
  - Scope: 민간기업인 신청기관에만 적용; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 101, "end_char": 118, "evidence_text": "기업신용평가등급 'B등급' 이상", "document_id": null, "evidence_id": null}]
- `GOLD:A5ESK53EUM2F5O2DCLPVI4A2` ELIGIBILITY / RECOMMENDATION_CAPABILITY / None / null; source [121:157] `전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한`; review_status=VERIFIED; decision_possible=False
  - Scope: 신청기관의 적격 창업기업 발굴·추천 역량; 추천기업은 신청자 유형이 아님; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 121, "end_char": 157, "evidence_text": "전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한", "document_id": null, "evidence_id": null}]
- `GOLD:OKFYXEH7HYJI2G267KCSYI7B` ELIGIBILITY / FINANCIAL_CAPACITY / GTE / 10000000; source [195:217] `협약금(기업당 10백만원) 부담이 가능한`; review_status=VERIFIED; decision_possible=False
  - Scope: 기업당 납부 가능성; 추천기업 수와 총액은 원문에서 미확인; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 195, "end_char": 217, "evidence_text": "협약금(기업당 10백만원) 부담이 가능한", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:26494104424A855C96BF",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:C70B8481EDF77108619BE5F3",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:SJDYLI2CGQAITBHYLES4CBG3"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:A5ESK53EUM2F5O2DCLPVI4A2"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:OKFYXEH7HYJI2G267KCSYI7B"
        }
      ],
      "review_status": "VERIFIED",
      "evidence": {
        "source_system": "KSTARTUP",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 241
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "※ 아래 3가지 자격조건을 모두 충족하여야 함\n① SWITCH  2026 'K-스타트업 통합관' 참여를 희망하는 지방정부, 공공기관, 민간기관 및 협·단체\n* 단, 민간기업의 경우 기업신용평가등급 'B등급' 이상\n② 전시회별 전시 기준에 충족하는 창업기업을 발굴하고, 추천이 가능한 지방정부, 공공기관, 민간기관 및 협·단체\n③ K-스타트업 통합관 협약금(기업당 10백만원) 부담이 가능한 지방정부, 공공기관, 민간기관 및 협·단체"
      }
    },
    "review_status": "VERIFIED"
  },
  {
    "section_id": "SECTION:600BD9DB34CB56CD3CF8",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "UNKNOWN",
    "fulfillment_phase": "UNKNOWN",
    "root": {
      "node_type": "CONDITION_REF",
      "condition_id": "GOLD:Q7VA6LVCU7MDG6O4EPAR54ZB"
    },
    "review_status": "VERIFIED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [],
  "unresolved_relations": [
    {
      "relation_id": "REL:CABF2E9E4AF07394414A",
      "gold_condition_ids": [
        "GOLD:SJDYLI2CGQAITBHYLES4CBG3",
        "GOLD:Q7VA6LVCU7MDG6O4EPAR54ZB"
      ],
      "evidence_reference": {
        "start_char": 101,
        "end_char": 118
      },
      "reason": "신용등급은 민간기업 신청기관에만 적용. AST상의 조건부 분기 표현을 보류.",
      "review_comment": "Unresolved; excluded from automated decision pending human review."
    }
  ]
}
```

### Review decision
Human approved on 2026-11-26.

## KSTARTUP:177857 (KSTARTUP; VERIFIED)

### Notice title
26년 6월 스타트업 언론 홍보 지원사업 참가사 모집 공고(1차)

### Source excerpt
```text
1. 예비창업자
2. 창업 7년 이내 초기 기업
```

### Existing v1 candidates
- CND:7V5GC6G2C4PZVYWA7QLEHKWD: 예비창업자
- CND:OIK3OPO2ZX3KOQMBOJ762KG6: 창업 7년 이내

### Gold conditions
- `GOLD:GFXFQQ34KQIJO7QQXX6QZN3W` ELIGIBILITY / BUSINESS_TYPE / EQ / "예비창업자"; source [3:8] `예비창업자`; review_status=VERIFIED; decision_possible=False
  - Scope: 신청자 분기 A; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 3, "end_char": 8, "evidence_text": "예비창업자", "document_id": null, "evidence_id": null}]
- `GOLD:XV7NNESGEASTNJF7W3QA6KTS` ELIGIBILITY / BUSINESS_AGE / LTE / 7; source [12:26] `창업 7년 이내 초기 기업`; review_status=VERIFIED; decision_possible=False
  - Scope: 신청자 분기 B 업력; 초기기업의 정량 정의 미수집; reference_date_type=UNKNOWN; temporal={"anchor_event": "UNKNOWN", "fixed_reference_date": null, "offset_value": 7, "offset_unit": "YEAR", "operator": "LTE", "inclusive": true, "applies_to": "신청자 분기 B 업력; 초기기업의 정량 정의 미수집", "anchor_date_known": false}
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 12, "end_char": 26, "evidence_text": "창업 7년 이내 초기 기업", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:3EB03DE40E1511E28626",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:3DB73A4D20929E13654224EF",
      "operator": "OR",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:GFXFQQ34KQIJO7QQXX6QZN3W"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:XV7NNESGEASTNJF7W3QA6KTS"
        }
      ],
      "review_status": "VERIFIED",
      "evidence": {
        "source_system": "KSTARTUP",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 26
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "1. 예비창업자\n2. 창업 7년 이내 초기 기업"
      }
    },
    "review_status": "VERIFIED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [],
  "unresolved_relations": []
}
```

### Review decision
Human approved on 2026-11-26.

