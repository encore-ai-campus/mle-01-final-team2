# Precheck 5 — v1.1 human approval recorded

- Approval date: 2026-11-26
- Reviewer identifier from repository git configuration: `bgm3167`
- Scope: semantic review of conditions, logic and exceptions in the provided source excerpts; 5 notices and 33 conditions.
- This is annotation approval only. It does not establish whole-notice completeness, fill unknown facts, or confirm application eligibility. Existing `decision_possible` values remain unchanged.
- Pre-approval snapshot: `approval_history/preapproval_20261126/`
- v1.0 source: `data/goldsets/conditions/v1/20261126_balanced/precheck5/development/`

## KSTARTUP:177469 — VERIFIED

### Source excerpt

```text
창업에 관심 있는 중장년(만 40세 이상) 예비창업자
```

### Approved conditions

| ID | Type | Field / operator / value | Evaluation / fulfillment | Decision possible | Evidence |
|---|---|---|---|---|---|
| `GOLD:HH45KL6O5TMBFKCOKSP3PFXM` | ELIGIBILITY | FOUNDER_PROFILE / None / null | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[0:13] `창업에 관심 있는 중장년` |
| `GOLD:F6FL67YCDDMVPJWEVNSKY2YP` | ELIGIBILITY | APPLICANT_AGE / GTE / 40 | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[14:22] `만 40세 이상` |
| `GOLD:P57N2FFGCOAP35M56ZEZNJXI` | ELIGIBILITY | BUSINESS_TYPE / EQ / "예비창업자" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[24:29] `예비창업자` |

### Approved logic and exceptions

```json
{
  "gold_logic_sections": [
    {
      "section_id": "eligibility",
      "condition_type": "ELIGIBILITY",
      "evaluation_phase": "APPLICATION",
      "fulfillment_phase": "APPLICATION",
      "root": {
        "node_type": "LOGICAL_GROUP",
        "group_id": "DRAFT:KSTARTUP:177469:SECOND:AND",
        "operator": "AND",
        "children": [
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:HH45KL6O5TMBFKCOKSP3PFXM"
          },
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:F6FL67YCDDMVPJWEVNSKY2YP"
          },
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:P57N2FFGCOAP35M56ZEZNJXI"
          }
        ],
        "review_status": "VERIFIED",
        "evidence": {
          "source_system": "KSTARTUP",
          "source_kind": "NOTICE_FIELD",
          "source_field": "condition_texts.eligibility.text",
          "normalized_path": "condition_texts.eligibility.text",
          "evidence_id": "KSTARTUP:177469:second-review",
          "chunk_ids": [],
          "location": {
            "start_char": 0,
            "end_char": 29
          },
          "observed_value_status": "AVAILABLE",
          "evidence_text": "창업에 관심 있는 중장년(만 40세 이상) 예비창업자"
        }
      },
      "review_status": "VERIFIED"
    }
  ],
  "gold_exceptions": []
}
```

## KSTARTUP:176813 — VERIFIED

### Source excerpt

```text
ㅇ사업목적과 아이템이 「첨단기술 및 제품의 범위」에 속하는 예비창업자 또는 창업 7년 미만의 기업(입주신청일 현재)
ㅇ정부지원 타 보육센터 입주경험이 없는 자(지방 창업보육센터 제외)
ㅇ서강대학교와 산학협력사업 진행중인 기업 우대
ㅇ서강대학교와 기술이전 가능한 기업 우대
```

### Approved conditions

| ID | Type | Field / operator / value | Evaluation / fulfillment | Decision possible | Evidence |
|---|---|---|---|---|---|
| `GOLD:UUO4VKZ34CFAU3U3V45ME6XD` | ELIGIBILITY | BUSINESS_TECHNOLOGY_SCOPE / None / null | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[1:32] `사업목적과 아이템이 「첨단기술 및 제품의 범위」에 속하는` |
| `GOLD:RBSON2DWXS3FIAMA2NIJKW37` | ELIGIBILITY | BUSINESS_TYPE / EQ / "예비창업자" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[33:38] `예비창업자` |
| `GOLD:CLG4YUJX3JBDNDXIIAIMP6HK` | ELIGIBILITY | BUSINESS_AGE / LT / 7 | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[42:54] `창업 7년 미만의 기업` |
| `GOLD:UTDHOPDVHP5NDS7BL2XQ773U` | ELIGIBILITY | RESTRICTED_GOV_INCUBATOR_EXPERIENCE_COUNT / EQ / 0 | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[66:102] `정부지원 타 보육센터 입주경험이 없는 자(지방 창업보육센터 제외)` |
| `GOLD:A3WST6DTWQKFYMUD6DWLMKYK` | PREFERENCE | SOGANG_ACADEMIC_COOPERATION / None / null | SELECTION / SELECTION | False | PRIMARY condition_texts.eligibility.text[104:128] `서강대학교와 산학협력사업 진행중인 기업 우대` |
| `GOLD:VXO7CQZP4XQO64HSS7XBZ2CI` | PREFERENCE | SOGANG_TECH_TRANSFER_POSSIBILITY / None / null | SELECTION / SELECTION | False | PRIMARY condition_texts.eligibility.text[130:151] `서강대학교와 기술이전 가능한 기업 우대` |

### Approved logic and exceptions

```json
{
  "gold_logic_sections": [
    {
      "section_id": "eligibility",
      "condition_type": "ELIGIBILITY",
      "evaluation_phase": "APPLICATION",
      "fulfillment_phase": "APPLICATION",
      "root": {
        "node_type": "LOGICAL_GROUP",
        "group_id": "DRAFT:KSTARTUP:176813:COMMON_AND",
        "operator": "AND",
        "children": [
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:UUO4VKZ34CFAU3U3V45ME6XD"
          },
          {
            "node_type": "LOGICAL_GROUP",
            "group_id": "DRAFT:KSTARTUP:176813:FOUNDER_OR_COMPANY",
            "operator": "OR",
            "children": [
              {
                "node_type": "CONDITION_REF",
                "condition_id": "GOLD:RBSON2DWXS3FIAMA2NIJKW37"
              },
              {
                "node_type": "CONDITION_REF",
                "condition_id": "GOLD:CLG4YUJX3JBDNDXIIAIMP6HK"
              }
            ],
            "review_status": "VERIFIED",
            "evidence": {
              "source_system": "KSTARTUP",
              "source_kind": "NOTICE_FIELD",
              "source_field": "condition_texts.eligibility.text",
              "normalized_path": "condition_texts.eligibility.text",
              "evidence_id": "KSTARTUP:176813:review-draft",
              "chunk_ids": [],
              "location": {
                "start_char": 33,
                "end_char": 54
              },
              "observed_value_status": "AVAILABLE",
              "evidence_text": "예비창업자 또는 창업 7년 미만의 기업"
            }
          },
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:UTDHOPDVHP5NDS7BL2XQ773U"
          }
        ],
        "review_status": "VERIFIED",
        "evidence": {
          "source_system": "KSTARTUP",
          "source_kind": "NOTICE_FIELD",
          "source_field": "condition_texts.eligibility.text",
          "normalized_path": "condition_texts.eligibility.text",
          "evidence_id": "KSTARTUP:176813:review-draft",
          "chunk_ids": [],
          "location": {
            "start_char": 0,
            "end_char": 102
          },
          "observed_value_status": "AVAILABLE",
          "evidence_text": "ㅇ사업목적과 아이템이 「첨단기술 및 제품의 범위」에 속하는 예비창업자 또는 창업 7년 미만의 기업(입주신청일 현재)\nㅇ정부지원 타 보육센터 입주경험이 없는 자(지방 창업보육센터 제외)"
        }
      },
      "review_status": "VERIFIED"
    },
    {
      "section_id": "preference_1",
      "condition_type": "PREFERENCE",
      "evaluation_phase": "SELECTION",
      "fulfillment_phase": "SELECTION",
      "root": {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:A3WST6DTWQKFYMUD6DWLMKYK"
      },
      "review_status": "VERIFIED"
    },
    {
      "section_id": "preference_2",
      "condition_type": "PREFERENCE",
      "evaluation_phase": "SELECTION",
      "fulfillment_phase": "SELECTION",
      "root": {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:VXO7CQZP4XQO64HSS7XBZ2CI"
      },
      "review_status": "VERIFIED"
    }
  ],
  "gold_exceptions": [
    {
      "raw_text": "지방 창업보육센터 제외",
      "evidence_reference": {
        "start_char": 89,
        "end_char": 101
      },
      "applies_to_gold_ids": [
        "GOLD:UTDHOPDVHP5NDS7BL2XQ773U"
      ],
      "linkage_status": "LINKED",
      "review_status": "VERIFIED",
      "review_comment": "입주 이력별 기관 필터: 지방 창업보육센터 경험만 제외; 다른 정부지원 센터 경험은 제한",
      "effect": "EXCLUDE_FROM_SCOPE",
      "effect_target": "RESTRICTED_GOV_INCUBATOR_EXPERIENCE_COUNT",
      "replacement": null,
      "precondition": "EXPERIENCE_RECORD_IS_LOCAL_INCUBATOR",
      "effect_confirmed": true,
      "application_mode": "EFFECT_ONLY",
      "evidence_references": [
        {
          "role": "PRIMARY",
          "source_field": "condition_texts.eligibility.text",
          "start_char": 89,
          "end_char": 101,
          "evidence_text": "지방 창업보육센터 제외",
          "document_id": null,
          "evidence_id": null
        }
      ]
    }
  ]
}
```

## BIZINFO:PBLN_000000000118927 — VERIFIED

### Source excerpt

```text
도내 가족친화 및 일ㆍ생활 균형을 실천하는 기업
※ 자세한 지원대상 공고문 참조
```

### Approved conditions

| ID | Type | Field / operator / value | Evaluation / fulfillment | Decision possible | Evidence |
|---|---|---|---|---|---|
| `GOLD:HBL5D5ZJI7UTI2IAXLZRRRTK` | ELIGIBILITY | BUSINESS_LOCATION / EQ / "강원도" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[0:2] `도내`; SUPPORTING title[1:3] `강원` |
| `GOLD:I6BFAXO5QDH553LCFFVUKGJ2` | ELIGIBILITY | FAMILY_FRIENDLY_PRACTICE / None / null | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[3:7] `가족친화` |
| `GOLD:AGZY7KXCI5HI4DUEJPPMTBIW` | ELIGIBILITY | WORK_LIFE_BALANCE_PRACTICE / None / null | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[10:26] `일ㆍ생활 균형을 실천하는 기업` |

### Approved logic and exceptions

```json
{
  "gold_logic_sections": [
    {
      "section_id": "eligibility",
      "condition_type": "ELIGIBILITY",
      "evaluation_phase": "APPLICATION",
      "fulfillment_phase": "APPLICATION",
      "root": {
        "node_type": "LOGICAL_GROUP",
        "group_id": "DRAFT:BIZINFO:PBLN_000000000118927:AND",
        "operator": "AND",
        "children": [
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:HBL5D5ZJI7UTI2IAXLZRRRTK"
          },
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:I6BFAXO5QDH553LCFFVUKGJ2"
          },
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:AGZY7KXCI5HI4DUEJPPMTBIW"
          }
        ],
        "review_status": "VERIFIED",
        "evidence": {
          "source_system": "BIZINFO",
          "source_kind": "NOTICE_FIELD",
          "source_field": "condition_texts.eligibility.text",
          "normalized_path": "condition_texts.eligibility.text",
          "evidence_id": "BIZINFO:PBLN_000000000118927:review-draft",
          "chunk_ids": [],
          "location": {
            "start_char": 0,
            "end_char": 26
          },
          "observed_value_status": "AVAILABLE",
          "evidence_text": "도내 가족친화 및 일ㆍ생활 균형을 실천하는 기업"
        }
      },
      "review_status": "VERIFIED"
    }
  ],
  "gold_exceptions": []
}
```

## KSTARTUP:178507 — VERIFIED

### Source excerpt

```text
전국 19세 이상 45세 이하 2026. 7. 7.(화) 기준, 사업 개시일로부터 7년이 지나지 아니한* 기업/예비창업자 *2019. 7. 8. 이후 사업을 개시한 창업기업
· 예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자
· 기 창업자는 신청일 기준 사업자등록이 완료되어야 하며, 사업장 소재지의 제한 없음
· 최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함 ※단, 해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료
· 지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)
· 국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가
· 최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)
```

### Approved conditions

| ID | Type | Field / operator / value | Evaluation / fulfillment | Decision possible | Evidence |
|---|---|---|---|---|---|
| `GOLD:M7PXG6623INOEMITL3AOE3CK` | ELIGIBILITY | APPLICANT_AGE / BETWEEN / {"lower": {"value": 19, "inclusive": true}, "upper": {"value": 45, "inclusive": true}} | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[3:16] `19세 이상 45세 이하`; CONTEXT condition_texts.eligibility.text[17:28] `2026. 7. 7.` |
| `GOLD:FE24B2OORHELAJRV66G7VJPC` | ELIGIBILITY | BUSINESS_TYPE / EQ / "예비창업자" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[62:67] `예비창업자` |
| `GOLD:DIZ2L732LLD4GHZKMKVWGAML` | ELIGIBILITY | BUSINESS_TYPE / EQ / "창업기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[92:96] `창업기업` |
| `GOLD:RKY5YC5WF6UKLIPCFCPOBLSC` | ELIGIBILITY | BUSINESS_AGE / LT / 7 | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[36:61] `사업 개시일로부터 7년이 지나지 아니한* 기업`; SUPPORTING condition_texts.eligibility.text[69:80] `2019. 7. 8.` |
| `GOLD:V4K4AAIB7KG32LIHAEKQMZIU` | ELIGIBILITY | BUSINESS_REGISTRATION / None / null | APPLICATION / POST_MOVE_IN | False | PRIMARY condition_texts.eligibility.text[99:133] `예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자` |
| `GOLD:UTYFQJK6CDHOFA3MZKFI3DFP` | ELIGIBILITY | BUSINESS_REGISTRATION_COMPLETED / EQ / true | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[136:165] `기 창업자는 신청일 기준 사업자등록이 완료되어야 하며` |
| `GOLD:IZGLBYNHDYFKYAW7RWGYQUCJ` | ELIGIBILITY | BUSINESS_LOCATION / EQ / "청년창업지원센터 상주올래 입주공간" | POST_SELECTION / POST_SELECTION | False | PRIMARY condition_texts.eligibility.text[184:252] `최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함` |
| `GOLD:XNGCLJRMJ6SBOJFO6PQZI5SF` | EXCLUSION | None / None / null | UNKNOWN / UNKNOWN | False | PRIMARY condition_texts.eligibility.text[304:345] `지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)` |
| `GOLD:64HML7YO6L4FES5PLPUTFK2O` | EXCLUSION | DUPLICATE_OCCUPANCY / EQ / true | UNKNOWN / UNKNOWN | False | PRIMARY condition_texts.eligibility.text[348:381] `국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가` |
| `GOLD:XNGYEKKQZZIRCEYLRC7XBPHS` | EXCLUSION | DUPLICATE_OCCUPANCY / EQ / true | POST_SELECTION / POST_SELECTION | False | PRIMARY condition_texts.eligibility.text[384:432] `최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)` |

### Approved logic and exceptions

```json
{
  "gold_logic_sections": [
    {
      "section_id": "eligibility",
      "condition_type": "ELIGIBILITY",
      "evaluation_phase": "APPLICATION",
      "fulfillment_phase": "UNKNOWN",
      "root": {
        "node_type": "LOGICAL_GROUP",
        "group_id": "DRAFT:KSTARTUP:178507:SECOND:APPLICATION_ELIGIBILITY",
        "operator": "AND",
        "children": [
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:M7PXG6623INOEMITL3AOE3CK"
          },
          {
            "node_type": "LOGICAL_GROUP",
            "group_id": "DRAFT:KSTARTUP:178507:SECOND:TYPE_OR",
            "operator": "OR",
            "children": [
              {
                "node_type": "LOGICAL_GROUP",
                "group_id": "DRAFT:KSTARTUP:178507:FOUNDER_FEASIBILITY",
                "operator": "AND",
                "children": [
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:FE24B2OORHELAJRV66G7VJPC"
                  },
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:V4K4AAIB7KG32LIHAEKQMZIU"
                  }
                ],
                "review_status": "VERIFIED",
                "evidence": null
              },
              {
                "node_type": "LOGICAL_GROUP",
                "group_id": "DRAFT:KSTARTUP:178507:SECOND:COMPANY",
                "operator": "AND",
                "children": [
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:DIZ2L732LLD4GHZKMKVWGAML"
                  },
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:RKY5YC5WF6UKLIPCFCPOBLSC"
                  },
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:UTYFQJK6CDHOFA3MZKFI3DFP"
                  }
                ],
                "review_status": "VERIFIED",
                "evidence": {
                  "source_system": "KSTARTUP",
                  "source_kind": "NOTICE_FIELD",
                  "source_field": "condition_texts.eligibility.text",
                  "normalized_path": "condition_texts.eligibility.text",
                  "evidence_id": "KSTARTUP:178507:second-review",
                  "chunk_ids": [],
                  "location": {
                    "start_char": 0,
                    "end_char": 432
                  },
                  "observed_value_status": "AVAILABLE",
                  "evidence_text": "전국 19세 이상 45세 이하 2026. 7. 7.(화) 기준, 사업 개시일로부터 7년이 지나지 아니한* 기업/예비창업자 *2019. 7. 8. 이후 사업을 개시한 창업기업\n· 예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자\n· 기 창업자는 신청일 기준 사업자등록이 완료되어야 하며, 사업장 소재지의 제한 없음\n· 최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함 ※단, 해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료\n· 지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)\n· 국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가\n· 최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)"
                }
              }
            ],
            "review_status": "VERIFIED",
            "evidence": {
              "source_system": "KSTARTUP",
              "source_kind": "NOTICE_FIELD",
              "source_field": "condition_texts.eligibility.text",
              "normalized_path": "condition_texts.eligibility.text",
              "evidence_id": "KSTARTUP:178507:second-review",
              "chunk_ids": [],
              "location": {
                "start_char": 0,
                "end_char": 432
              },
              "observed_value_status": "AVAILABLE",
              "evidence_text": "전국 19세 이상 45세 이하 2026. 7. 7.(화) 기준, 사업 개시일로부터 7년이 지나지 아니한* 기업/예비창업자 *2019. 7. 8. 이후 사업을 개시한 창업기업\n· 예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자\n· 기 창업자는 신청일 기준 사업자등록이 완료되어야 하며, 사업장 소재지의 제한 없음\n· 최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함 ※단, 해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료\n· 지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)\n· 국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가\n· 최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)"
            }
          }
        ],
        "review_status": "VERIFIED",
        "evidence": {
          "source_system": "KSTARTUP",
          "source_kind": "NOTICE_FIELD",
          "source_field": "condition_texts.eligibility.text",
          "normalized_path": "condition_texts.eligibility.text",
          "evidence_id": "KSTARTUP:178507:second-review",
          "chunk_ids": [],
          "location": {
            "start_char": 0,
            "end_char": 432
          },
          "observed_value_status": "AVAILABLE",
          "evidence_text": "전국 19세 이상 45세 이하 2026. 7. 7.(화) 기준, 사업 개시일로부터 7년이 지나지 아니한* 기업/예비창업자 *2019. 7. 8. 이후 사업을 개시한 창업기업\n· 예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자\n· 기 창업자는 신청일 기준 사업자등록이 완료되어야 하며, 사업장 소재지의 제한 없음\n· 최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함 ※단, 해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료\n· 지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)\n· 국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가\n· 최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)"
        }
      },
      "review_status": "VERIFIED"
    },
    {
      "section_id": "exclusion_1",
      "condition_type": "EXCLUSION",
      "evaluation_phase": "UNKNOWN",
      "fulfillment_phase": "UNKNOWN",
      "root": {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:XNGCLJRMJ6SBOJFO6PQZI5SF"
      },
      "review_status": "VERIFIED"
    },
    {
      "section_id": "exclusion_2",
      "condition_type": "EXCLUSION",
      "evaluation_phase": "UNKNOWN",
      "fulfillment_phase": "UNKNOWN",
      "root": {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:64HML7YO6L4FES5PLPUTFK2O"
      },
      "review_status": "VERIFIED"
    },
    {
      "section_id": "exclusion_3",
      "condition_type": "EXCLUSION",
      "evaluation_phase": "POST_SELECTION",
      "fulfillment_phase": "POST_SELECTION",
      "root": {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:XNGYEKKQZZIRCEYLRC7XBPHS"
      },
      "review_status": "VERIFIED"
    },
    {
      "section_id": "address_transfer",
      "condition_type": "POST_SELECTION_OBLIGATION",
      "evaluation_phase": "POST_SELECTION",
      "fulfillment_phase": "POST_SELECTION",
      "root": {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:IZGLBYNHDYFKYAW7RWGYQUCJ"
      },
      "review_status": "VERIFIED"
    }
  ],
  "gold_exceptions": [
    {
      "raw_text": "해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료",
      "evidence_reference": {
        "start_char": 257,
        "end_char": 301
      },
      "applies_to_gold_ids": [
        "GOLD:IZGLBYNHDYFKYAW7RWGYQUCJ"
      ],
      "linkage_status": "LINKED",
      "review_status": "VERIFIED",
      "review_comment": "해외기업/기업부설연구소의 이전등록 기한 예외",
      "effect": "REPLACE_DEADLINE",
      "effect_target": "BUSINESS_LOCATION.temporal_constraint",
      "replacement": {
        "anchor_event": "CONTRACT_SIGNING",
        "offset_value": 3,
        "offset_unit": "MONTH",
        "operator": "LTE",
        "inclusive": true
      },
      "precondition": "FOREIGN_COMPANY_OR_CORPORATE_RESEARCH_INSTITUTE",
      "effect_confirmed": true,
      "application_mode": "EFFECT_ONLY",
      "evidence_references": [
        {
          "role": "PRIMARY",
          "source_field": "condition_texts.eligibility.text",
          "start_char": 257,
          "end_char": 301,
          "evidence_text": "해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료",
          "document_id": null,
          "evidence_id": null
        }
      ]
    }
  ]
}
```

## BIZINFO:PBLN_000000000118182 — VERIFIED

### Source excerpt

```text
사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음
- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)
-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업
-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)
-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업
-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업
-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)
-「국민기초생활보장법」 제18조에 의한 자활기업
-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업
```

### Approved conditions

| ID | Type | Field / operator / value | Evaluation / fulfillment | Decision possible | Evidence |
|---|---|---|---|---|---|
| `GOLD:O53W5ZPOQ3J4GMSQ2ACMSFOJ` | ELIGIBILITY | BUSINESS_LOCATION / EQ / "경기도" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[5:7] `도내`; SUPPORTING title[1:3] `경기` |
| `GOLD:AK6QCETSJGS72OBGPPVH3DRQ` | ELIGIBILITY | FOR_PROFIT_STATUS / EQ / "영리기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[33:41] `영리기업인 경우` |
| `GOLD:VPS4NR5FIET4BQFGJ4YRBTER` | ELIGIBILITY | BUSINESS_TYPE / EQ / "사회적기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[82:120] `- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)` |
| `GOLD:BP3Y47M5FUWWJYFGJHP3D2DF` | ELIGIBILITY | BUSINESS_TYPE / EQ / "예비사회적기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[121:154] `-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업` |
| `GOLD:JB3FUI37RSO2M425UG5TFERN` | ELIGIBILITY | BUSINESS_TYPE / EQ / "협동조합" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[155:189] `-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)` |
| `GOLD:YN5LOI5WGWIRFPR5NFKMYFSG` | ELIGIBILITY | BUSINESS_TYPE / EQ / "마을기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[190:220] `-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업` |
| `GOLD:BWZKRDSI567HUS6IFN4GJ3HL` | ELIGIBILITY | BUSINESS_TYPE / EQ / "예비마을기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[221:253] `-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업` |
| `GOLD:UOAGRRT2R3XTU2SNSXFR242C` | ELIGIBILITY | BUSINESS_TYPE / EQ / "소비자생활협동조합" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[254:296] `-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)` |
| `GOLD:5JIPAID7CCBFOU3RIOTPMKOI` | ELIGIBILITY | BUSINESS_TYPE / EQ / "자활기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[297:323] `-「국민기초생활보장법」 제18조에 의한 자활기업` |
| `GOLD:A4WSO43TKQWP7ID5FPS7U7HO` | ELIGIBILITY | BUSINESS_TYPE / EQ / "소셜벤처기업" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[324:356] `-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업` |
| `GOLD:MD6SUB2ZEWNHTSQA4KVOGP3K` | ELIGIBILITY | FOR_PROFIT_STATUS / EQ / "비영리사업자" | APPLICATION / APPLICATION | False | PRIMARY condition_texts.eligibility.text[65:81] `비영리사업자도 지원할 수 있음` |

### Approved logic and exceptions

```json
{
  "gold_logic_sections": [
    {
      "section_id": "eligibility",
      "condition_type": "ELIGIBILITY",
      "evaluation_phase": "APPLICATION",
      "fulfillment_phase": "APPLICATION",
      "root": {
        "node_type": "LOGICAL_GROUP",
        "group_id": "DRAFT:BIZINFO:PBLN_000000000118182:SECOND:REGION_AND_BRANCH",
        "operator": "AND",
        "children": [
          {
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:O53W5ZPOQ3J4GMSQ2ACMSFOJ"
          },
          {
            "node_type": "LOGICAL_GROUP",
            "group_id": "DRAFT:BIZINFO:PBLN_000000000118182:SECOND:PROFIT_OR_NONPROFIT",
            "operator": "OR",
            "children": [
              {
                "node_type": "LOGICAL_GROUP",
                "group_id": "DRAFT:BIZINFO:PBLN_000000000118182:SECOND:PROFIT_AND",
                "operator": "AND",
                "children": [
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:AK6QCETSJGS72OBGPPVH3DRQ"
                  },
                  {
                    "node_type": "LOGICAL_GROUP",
                    "group_id": "DRAFT:BIZINFO:PBLN_000000000118182:SECOND:ALL8_OR",
                    "operator": "OR",
                    "children": [
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:VPS4NR5FIET4BQFGJ4YRBTER"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:BP3Y47M5FUWWJYFGJHP3D2DF"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:JB3FUI37RSO2M425UG5TFERN"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:YN5LOI5WGWIRFPR5NFKMYFSG"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:BWZKRDSI567HUS6IFN4GJ3HL"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:UOAGRRT2R3XTU2SNSXFR242C"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:5JIPAID7CCBFOU3RIOTPMKOI"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:A4WSO43TKQWP7ID5FPS7U7HO"
                      }
                    ],
                    "review_status": "VERIFIED",
                    "evidence": {
                      "source_system": "BIZINFO",
                      "source_kind": "NOTICE_FIELD",
                      "source_field": "condition_texts.eligibility.text",
                      "normalized_path": "condition_texts.eligibility.text",
                      "evidence_id": "BIZINFO:PBLN_000000000118182:second-review",
                      "chunk_ids": [],
                      "location": {
                        "start_char": 0,
                        "end_char": 356
                      },
                      "observed_value_status": "AVAILABLE",
                      "evidence_text": "사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음\n- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업\n-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업\n-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)\n-「국민기초생활보장법」 제18조에 의한 자활기업\n-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업"
                    }
                  }
                ],
                "review_status": "VERIFIED",
                "evidence": {
                  "source_system": "BIZINFO",
                  "source_kind": "NOTICE_FIELD",
                  "source_field": "condition_texts.eligibility.text",
                  "normalized_path": "condition_texts.eligibility.text",
                  "evidence_id": "BIZINFO:PBLN_000000000118182:second-review",
                  "chunk_ids": [],
                  "location": {
                    "start_char": 0,
                    "end_char": 356
                  },
                  "observed_value_status": "AVAILABLE",
                  "evidence_text": "사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음\n- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업\n-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업\n-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)\n-「국민기초생활보장법」 제18조에 의한 자활기업\n-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업"
                }
              },
              {
                "node_type": "LOGICAL_GROUP",
                "group_id": "DRAFT:BIZINFO:PBLN_000000000118182:SECOND:NONPROFIT_AND",
                "operator": "AND",
                "children": [
                  {
                    "node_type": "CONDITION_REF",
                    "condition_id": "GOLD:MD6SUB2ZEWNHTSQA4KVOGP3K"
                  },
                  {
                    "node_type": "LOGICAL_GROUP",
                    "group_id": "DRAFT:BIZINFO:PBLN_000000000118182:SECOND:ALLOWED3_OR",
                    "operator": "OR",
                    "children": [
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:VPS4NR5FIET4BQFGJ4YRBTER"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:JB3FUI37RSO2M425UG5TFERN"
                      },
                      {
                        "node_type": "CONDITION_REF",
                        "condition_id": "GOLD:UOAGRRT2R3XTU2SNSXFR242C"
                      }
                    ],
                    "review_status": "VERIFIED",
                    "evidence": {
                      "source_system": "BIZINFO",
                      "source_kind": "NOTICE_FIELD",
                      "source_field": "condition_texts.eligibility.text",
                      "normalized_path": "condition_texts.eligibility.text",
                      "evidence_id": "BIZINFO:PBLN_000000000118182:second-review",
                      "chunk_ids": [],
                      "location": {
                        "start_char": 0,
                        "end_char": 356
                      },
                      "observed_value_status": "AVAILABLE",
                      "evidence_text": "사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음\n- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업\n-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업\n-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)\n-「국민기초생활보장법」 제18조에 의한 자활기업\n-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업"
                    }
                  }
                ],
                "review_status": "VERIFIED",
                "evidence": {
                  "source_system": "BIZINFO",
                  "source_kind": "NOTICE_FIELD",
                  "source_field": "condition_texts.eligibility.text",
                  "normalized_path": "condition_texts.eligibility.text",
                  "evidence_id": "BIZINFO:PBLN_000000000118182:second-review",
                  "chunk_ids": [],
                  "location": {
                    "start_char": 0,
                    "end_char": 356
                  },
                  "observed_value_status": "AVAILABLE",
                  "evidence_text": "사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음\n- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업\n-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업\n-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)\n-「국민기초생활보장법」 제18조에 의한 자활기업\n-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업"
                }
              }
            ],
            "review_status": "VERIFIED",
            "evidence": {
              "source_system": "BIZINFO",
              "source_kind": "NOTICE_FIELD",
              "source_field": "condition_texts.eligibility.text",
              "normalized_path": "condition_texts.eligibility.text",
              "evidence_id": "BIZINFO:PBLN_000000000118182:second-review",
              "chunk_ids": [],
              "location": {
                "start_char": 0,
                "end_char": 356
              },
              "observed_value_status": "AVAILABLE",
              "evidence_text": "사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음\n- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업\n-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업\n-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)\n-「국민기초생활보장법」 제18조에 의한 자활기업\n-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업"
            }
          }
        ],
        "review_status": "VERIFIED",
        "evidence": {
          "source_system": "BIZINFO",
          "source_kind": "NOTICE_FIELD",
          "source_field": "condition_texts.eligibility.text",
          "normalized_path": "condition_texts.eligibility.text",
          "evidence_id": "BIZINFO:PBLN_000000000118182:second-review",
          "chunk_ids": [],
          "location": {
            "start_char": 0,
            "end_char": 356
          },
          "observed_value_status": "AVAILABLE",
          "evidence_text": "사업장이 도내에 소재하는 기업 중 다음 중 하나에 해당하는 영리기업인 경우,다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음\n- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업\n-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)\n-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업\n-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업\n-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)\n-「국민기초생활보장법」 제18조에 의한 자활기업\n-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업"
        }
      },
      "review_status": "VERIFIED"
    }
  ],
  "gold_exceptions": [
    {
      "raw_text": "다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음",
      "evidence_reference": {
        "start_char": 42,
        "end_char": 81
      },
      "applies_to_gold_ids": [
        "GOLD:AK6QCETSJGS72OBGPPVH3DRQ",
        "GOLD:MD6SUB2ZEWNHTSQA4KVOGP3K",
        "GOLD:VPS4NR5FIET4BQFGJ4YRBTER",
        "GOLD:JB3FUI37RSO2M425UG5TFERN",
        "GOLD:UOAGRRT2R3XTU2SNSXFR242C"
      ],
      "linkage_status": "LINKED",
      "review_status": "VERIFIED",
      "review_comment": "영리 요건 완화 효과는 OR AST에 명시; 비영리 허용은 3개 조직 유형만",
      "effect": "WAIVE_REQUIREMENT",
      "effect_target": "PROFIT_STATUS",
      "replacement": null,
      "precondition": "NONPROFIT_AND_ALLOWED_THREE_ORGANIZATION_TYPES",
      "effect_confirmed": true,
      "application_mode": "AST_ONLY",
      "evidence_references": [
        {
          "role": "PRIMARY",
          "source_field": "condition_texts.eligibility.text",
          "start_char": 42,
          "end_char": 81,
          "evidence_text": "다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음",
          "document_id": null,
          "evidence_id": null
        }
      ]
    }
  ]
}
```

