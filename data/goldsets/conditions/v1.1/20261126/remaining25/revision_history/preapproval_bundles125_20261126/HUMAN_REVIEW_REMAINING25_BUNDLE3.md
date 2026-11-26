# Development review bundle 3/5

Draft only: UNREVIEWED / PENDING. Source is a condition excerpt; completeness of the whole notice remains UNKNOWN.

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

### Existing v1 candidates
- No candidate record; this is not evidence that no condition exists.

### Gold condition draft
- `GOLD:XRWVSMMAS3FHYNAVYSFCQBQN` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["사회적기업", "예비사회적기업"]** ? 「사회적기업 육성법」에 따른 (예비)사회적기업 (span 34:59; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:VDE4TE5IYGKOQHNY4C5CW3ID` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / IN ["마을기업", "예비마을기업"]** ? 「마을기업 육성 및 지원에 관한 법률」에 따른 (예비)마을기업 (span 61:95; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요
- `GOLD:3B5ZWMZCK2MPZSUVJYFW6DTQ` **ELIGIBILITY / BUSINESS_TYPE / BUSINESS_TYPE / EQ "사회적협동조합"** ? 「협동조합 기본법」에 따른 사회적협동조합 (span 97:119; decision_possible=False; v1 comparison=MISSING in v1 candidates)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:0D96759CD88AF74EFCE48F1F", "operator": "OR", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:XRWVSMMAS3FHYNAVYSFCQBQN"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:VDE4TE5IYGKOQHNY4C5CW3ID"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:3B5ZWMZCK2MPZSUVJYFW6DTQ"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "BIZINFO", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 119}, "observed_value_status": "AVAILABLE", "evidence_text": "근로자 5인 미만 기업(70%), 5인 이상 기업(30%)\n-「사회적기업 육성법」에 따른 (예비)사회적기업\n-「마을기업 육성 및 지원에 관한 법률」에 따른 (예비)마을기업\n-「협동조합 기본법」에 따른 사회적협동조합"}}`

### Benefits needing review
- 근로자 5인 미만 기업(70%) ? UNKNOWN; 70%/30% 의미와 적용 대상이 미확인. 지원율·선정 비율로 추론 금지.
- 5인 이상 기업(30%) ? UNKNOWN; 70%/30% 의미와 적용 대상이 미확인. 지원율·선정 비율로 추론 금지.

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 

## BIZINFO:PBLN_000000000125974 (BIZINFO)

### Notice title
[경남] 진주시 2026년 발달장애인 가족창업 컨설팅 지원 모집 공고

### Source excerpt
```text
진주시 지역의 발달장애인 가족공동 창업기업, 예비창업자 및 창업특화교육 참여 교육생
```

### Existing v1 candidates
- CND:EREHCCODQMCTWPCEDVASQPZT: 창업기업
- CND:YA2B4MNZ5TSFGXYXRKREMLLR: 예비창업자

### Revised gold conditions (UNREVIEWED)
- `GOLD:TEFDTMO53JINEPFKJCJ2JIPB` ELIGIBILITY / BUSINESS_TYPE / EQ / "발달장애인 가족공동 창업기업"; source [0:23] `진주시 지역의 발달장애인 가족공동 창업기업`; decision_possible=False
  - Scope: 발달장애인 가족공동 창업기업 분기에만 가족 요건 적용; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": 23, "evidence_text": "진주시 지역의 발달장애인 가족공동 창업기업", "document_id": null, "evidence_id": null}]
- `GOLD:DJO7I3DBIWHR4KBGFNHIPS66` ELIGIBILITY / BUSINESS_TYPE / EQ / "예비창업자"; source [25:30] `예비창업자`; decision_possible=False
  - Scope: 신청자 분기 B; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 25, "end_char": 30, "evidence_text": "예비창업자", "document_id": null, "evidence_id": null}]
- `GOLD:ELW44XRIKVDP6WGGDXLQNUKZ` ELIGIBILITY / PROGRAM_PARTICIPATION / EQ / "창업특화교육 참여 교육생"; source [33:46] `창업특화교육 참여 교육생`; decision_possible=False
  - Scope: Family modifier applicability to trainees is UNKNOWN.; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 33, "end_char": 46, "evidence_text": "창업특화교육 참여 교육생", "document_id": null, "evidence_id": null}]
- `GOLD:DGZZY3OLVW4MRFC5EBWS563S` ELIGIBILITY / BUSINESS_LOCATION / EQ / "진주시"; source [0:6] `진주시 지역`; decision_possible=False
  - Scope: 진주시 지역; 개인 주소·사업장 등 적용 대상 미확인; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": 6, "evidence_text": "진주시 지역", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:76E08D37C77A1384E3DD",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:75344E36B45C5075829E1DF6",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:DGZZY3OLVW4MRFC5EBWS563S"
        },
        {
          "node_type": "LOGICAL_GROUP",
          "group_id": "AST:1458ECEC3821BA67EB4C1613",
          "operator": "OR",
          "children": [
            {
              "node_type": "CONDITION_REF",
              "condition_id": "GOLD:TEFDTMO53JINEPFKJCJ2JIPB"
            },
            {
              "node_type": "CONDITION_REF",
              "condition_id": "GOLD:DJO7I3DBIWHR4KBGFNHIPS66"
            },
            {
              "node_type": "CONDITION_REF",
              "condition_id": "GOLD:ELW44XRIKVDP6WGGDXLQNUKZ"
            }
          ],
          "review_status": "UNREVIEWED",
          "evidence": {
            "source_system": "BIZINFO",
            "source_kind": "NOTICE_FIELD",
            "source_field": "condition_texts.eligibility.text",
            "normalized_path": "condition_texts.eligibility.text",
            "evidence_id": null,
            "chunk_ids": [],
            "location": {
              "start_char": 0,
              "end_char": 46
            },
            "observed_value_status": "AVAILABLE",
            "evidence_text": "진주시 지역의 발달장애인 가족공동 창업기업, 예비창업자 및 창업특화교육 참여 교육생"
          }
        }
      ],
      "review_status": "UNREVIEWED",
      "evidence": {
        "source_system": "BIZINFO",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 46
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "진주시 지역의 발달장애인 가족공동 창업기업, 예비창업자 및 창업특화교육 참여 교육생"
      }
    },
    "review_status": "UNREVIEWED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [],
  "unresolved_relations": [
    {
      "relation_id": "REL:9CD6B138B1A00C0315F6",
      "gold_condition_ids": [
        "GOLD:TEFDTMO53JINEPFKJCJ2JIPB",
        "GOLD:DJO7I3DBIWHR4KBGFNHIPS66",
        "GOLD:ELW44XRIKVDP6WGGDXLQNUKZ"
      ],
      "evidence_reference": {
        "start_char": 0,
        "end_char": 23
      },
      "reason": "The source does not establish whether the developmental-disability family qualifier also applies to prospective founders or trainees.",
      "review_comment": "Unresolved; excluded from automated decision pending human review."
    },
    {
      "relation_id": "REL:0556F7DD9A4A3DA55CB9",
      "gold_condition_ids": [
        "GOLD:DGZZY3OLVW4MRFC5EBWS563S"
      ],
      "evidence_reference": {
        "start_char": 0,
        "end_char": 6
      },
      "reason": "진주시 지역이 개인 주소지인지 사업장인지 원문에서 특정되지 않음.",
      "review_comment": "Unresolved; excluded from automated decision pending human review."
    }
  ]
}
```

### Human review
Approval / correction / unable to determine: __________


## BIZINFO:PBLN_000000000126490 (BIZINFO)

### Notice title
2026년 K-소비재 수출기업 대상 한류편승행위 대응 지원사업 참여기업 모집 변경 공고

### Source excerpt
```text
대한민국에 사업자로 등록된 중소ㆍ중견기업 중 지원 희망 국가 내 유효한 지식재산권(상표ㆍ디자인)을 보유한 기업
```

### Existing v1 candidates
- None in the v1 candidate file.

### Revised gold conditions (UNREVIEWED)
- `GOLD:G7UCL7P2QR2S644ZNOOMIA6X` ELIGIBILITY / BUSINESS_REGISTRATION_STATUS / EQ / "대한민국에 사업자 등록"; source [0:14] `대한민국에 사업자로 등록된`; decision_possible=False
  - Scope: 사업자 등록 관할; 사업장 소재와 구분; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": 14, "evidence_text": "대한민국에 사업자로 등록된", "document_id": null, "evidence_id": null}]
- `GOLD:VKMSFSS6WQWCAH3F3CCYWKII` ELIGIBILITY / BUSINESS_TYPE / IN / ["중소기업", "중견기업"]; source [15:22] `중소ㆍ중견기업`; decision_possible=False
  - Scope: 신청기업 유형; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 15, "end_char": 22, "evidence_text": "중소ㆍ중견기업", "document_id": null, "evidence_id": null}]
- `GOLD:IUI7OJRR3CKO27RGPIGAQ7PL` ELIGIBILITY / IP_RIGHT_COUNTRY / EQ / "신청자가 선택한 지원 희망 국가와 권리 유효 국가 일치"; source [25:35] `지원 희망 국가 내`; decision_possible=False
  - Scope: All IP-right attributes must belong to the SAME right and selected destination country; cross-right combination is not allowed.; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 25, "end_char": 35, "evidence_text": "지원 희망 국가 내", "document_id": null, "evidence_id": null}]
- `GOLD:CD7GO4EYSLWUYM7X2X7Y7P5P` ELIGIBILITY / IP_RIGHT_VALIDITY / EQ / "유효"; source [36:45] `유효한 지식재산권`; decision_possible=False
  - Scope: All IP-right attributes must belong to the SAME right and selected destination country; cross-right combination is not allowed.; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 36, "end_char": 45, "evidence_text": "유효한 지식재산권", "document_id": null, "evidence_id": null}]
- `GOLD:KLBG2PGX6LPQBHAAWRGRFEWO` ELIGIBILITY / IP_RIGHT_TYPE / IN / ["상표", "디자인"]; source [46:52] `상표ㆍ디자인`; decision_possible=False
  - Scope: All IP-right attributes must belong to the SAME right and selected destination country; cross-right combination is not allowed.; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 46, "end_char": 52, "evidence_text": "상표ㆍ디자인", "document_id": null, "evidence_id": null}]
- `GOLD:JBVFWBQQPQE2BAT5W3QT2FMJ` ELIGIBILITY / IP_RIGHT_OWNERSHIP / EQ / "신청기업이 권리 보유"; source [55:61] `보유한 기업`; decision_possible=False
  - Scope: All IP-right attributes must belong to the SAME right and selected destination country; cross-right combination is not allowed.; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 55, "end_char": 61, "evidence_text": "보유한 기업", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:BC3627EF592468C9852B",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:1951871774C945D2F405793F",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:G7UCL7P2QR2S644ZNOOMIA6X"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:VKMSFSS6WQWCAH3F3CCYWKII"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:IUI7OJRR3CKO27RGPIGAQ7PL"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:CD7GO4EYSLWUYM7X2X7Y7P5P"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:KLBG2PGX6LPQBHAAWRGRFEWO"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:JBVFWBQQPQE2BAT5W3QT2FMJ"
        }
      ],
      "review_status": "UNREVIEWED",
      "evidence": {
        "source_system": "BIZINFO",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 61
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "대한민국에 사업자로 등록된 중소ㆍ중견기업 중 지원 희망 국가 내 유효한 지식재산권(상표ㆍ디자인)을 보유한 기업"
      }
    },
    "review_status": "UNREVIEWED"
  }
]
```

### Exceptions and unresolved relations
```json
{
  "gold_exceptions": [],
  "unresolved_relations": [
    {
      "relation_id": "REL:039608534073653DFF10",
      "gold_condition_ids": [
        "GOLD:IUI7OJRR3CKO27RGPIGAQ7PL",
        "GOLD:CD7GO4EYSLWUYM7X2X7Y7P5P",
        "GOLD:KLBG2PGX6LPQBHAAWRGRFEWO",
        "GOLD:JBVFWBQQPQE2BAT5W3QT2FMJ"
      ],
      "evidence_reference": {
        "start_char": 25,
        "end_char": 61
      },
      "reason": "Same-entity binding is required across IP type, validity, ownership and selected destination country. v1.1 AST cannot enforce shared-right identity.",
      "review_comment": "Do not permit a full eligibility decision by combining properties from different IP rights."
    }
  ]
}
```

### Human review
Approval / correction / unable to determine: __________


## KSTARTUP:177051 (KSTARTUP)

### Notice title
「2026년 지역주도형 AI대전환사업」 AI솔루션 보급·확산사업 지원기업 통합모집 공고

### Source excerpt
```text
공고일 기준 창업 후 7년* 이내의 AI 솔루션 보유한 창업기업
* 신청가능 창업(설립)일 기준:’19.03.26.~’26.03.25.
```

### Existing v1 candidates
- CND:VUJBIE7AWNXWTHHJDGDKHLKR: 창업기업

### Revised gold conditions (UNREVIEWED)
- `GOLD:SJF7RZ7LU57D5SYSQ722BT5R` ELIGIBILITY / BUSINESS_AGE / LTE / 7; source [0:18] `공고일 기준 창업 후 7년* 이내`; decision_possible=False
  - Scope: 공고일 기준 업력; reference_date_type=PUBLICATION_DATE; temporal={"anchor_event": "UNKNOWN", "fixed_reference_date": null, "offset_value": 7, "offset_unit": "YEAR", "operator": "LTE", "inclusive": true, "applies_to": "Notice publication date; exact calendar date unknown; startup-date interval 2019-03-26 through 2026-03-25 retained as supporting evidence.", "anchor_date_known": false}
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 0, "end_char": 18, "evidence_text": "공고일 기준 창업 후 7년* 이내", "document_id": null, "evidence_id": null}, {"role": "SUPPORTING", "source_field": "condition_texts.eligibility.text", "start_char": 38, "end_char": 75, "evidence_text": "신청가능 창업(설립)일 기준:’19.03.26.~’26.03.25.", "document_id": null, "evidence_id": null}]
- `GOLD:EI3KFA22GXNDKHHJ5ERL5MRA` ELIGIBILITY / AI_SOLUTION / EQ / "AI 솔루션 보유"; source [20:35] `AI 솔루션 보유한 창업기업`; decision_possible=False
  - Scope: 보유 상태; reference_date_type=UNKNOWN; temporal=null
  - Evidence: [{"role": "PRIMARY", "source_field": "condition_texts.eligibility.text", "start_char": 20, "end_char": 35, "evidence_text": "AI 솔루션 보유한 창업기업", "document_id": null, "evidence_id": null}]

### Logic sections
```json
[
  {
    "section_id": "SECTION:51BE114551E9F1942F75",
    "condition_type": "ELIGIBILITY",
    "evaluation_phase": "APPLICATION",
    "fulfillment_phase": "APPLICATION",
    "root": {
      "node_type": "LOGICAL_GROUP",
      "group_id": "AST:6B4562412688802851B85167",
      "operator": "AND",
      "children": [
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:SJF7RZ7LU57D5SYSQ722BT5R"
        },
        {
          "node_type": "CONDITION_REF",
          "condition_id": "GOLD:EI3KFA22GXNDKHHJ5ERL5MRA"
        }
      ],
      "review_status": "UNREVIEWED",
      "evidence": {
        "source_system": "KSTARTUP",
        "source_kind": "NOTICE_FIELD",
        "source_field": "condition_texts.eligibility.text",
        "normalized_path": "condition_texts.eligibility.text",
        "evidence_id": null,
        "chunk_ids": [],
        "location": {
          "start_char": 0,
          "end_char": 75
        },
        "observed_value_status": "AVAILABLE",
        "evidence_text": "공고일 기준 창업 후 7년* 이내의 AI 솔루션 보유한 창업기업\n* 신청가능 창업(설립)일 기준:’19.03.26.~’26.03.25."
      }
    },
    "review_status": "UNREVIEWED"
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

### Human review
Approval / correction / unable to determine: __________


## KSTARTUP:177292 (KSTARTUP)

### Notice title
2026년 제1회 S.Challenge IR 참여 기업 모집 공고

### Source excerpt (condition_texts.eligibility.text)
```text
핀테크 분야 사업을 영위하고, 서울에 소재(본사 기준)한 창업 3년 이내 기업
```

### Existing v1 candidates
- `CND:MEQEGWDTWUOAQG23Z7C4UGY5` 창업 3년 이내 [BUSINESS_AGE] ? PARTIAL_MATCH; gold: GOLD:IQQ5CZERF3KW2QBCVURFBWQN
- `CND:GFXGZMMUHLY7JXDOAWTE5JP2` 서울 [BUSINESS_LOCATION] ? PARTIAL_MATCH; gold: GOLD:ZRLT2LIHZFF7ISFRX3ATJUBK

### Gold condition draft
- `GOLD:KEG2YFCRW2FHGMRB5EHCKOH7` **ELIGIBILITY / INDUSTRY / INDUSTRY / EQ "핀테크"** ? 핀테크 분야 사업을 영위하고 (span 0:15; decision_possible=False; v1 comparison=MISSING in v1 candidates)
- `GOLD:ZRLT2LIHZFF7ISFRX3ATJUBK` **ELIGIBILITY / BUSINESS_LOCATION / BUSINESS_LOCATION / EQ "서울특별시"** ? 서울에 소재(본사 기준)한 (span 17:31; decision_possible=False; v1 comparison=PARTIAL_MATCH)
- `GOLD:IQQ5CZERF3KW2QBCVURFBWQN` **ELIGIBILITY / BUSINESS_AGE / BUSINESS_AGE / LTE 3** ? 창업 3년 이내 기업 (span 32:43; decision_possible=False; v1 comparison=PARTIAL_MATCH)
  - Review note: 발췌문만으로 구체 충족 사실·세부 기준을 확정할 수 없음; 사람 검수 필요

### Logic draft
- ELIGIBILITY / evaluation APPLICATION / fulfillment APPLICATION:

  `{"node_type": "LOGICAL_GROUP", "group_id": "AST:8CCF410B199F14E85559D000", "operator": "AND", "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:KEG2YFCRW2FHGMRB5EHCKOH7"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:ZRLT2LIHZFF7ISFRX3ATJUBK"}, {"node_type": "CONDITION_REF", "condition_id": "GOLD:IQQ5CZERF3KW2QBCVURFBWQN"}], "review_status": "UNREVIEWED", "evidence": {"source_system": "KSTARTUP", "source_kind": "NOTICE_FIELD", "source_field": "condition_texts.eligibility.text", "normalized_path": "condition_texts.eligibility.text", "evidence_id": null, "chunk_ids": [], "location": {"start_char": 0, "end_char": 43}, "observed_value_status": "AVAILABLE", "evidence_text": "핀테크 분야 사업을 영위하고, 서울에 소재(본사 기준)한 창업 3년 이내 기업"}}`

### Review/status
자동 작성 초안. 제공 발췌 전체를 기준으로 작성했으며 공고 전체 조건 완전성은 확정하지 않음. 사람 검수 대기.

Approve: [ ]  Amend:  Unable to decide:  Reviewer/date: 
