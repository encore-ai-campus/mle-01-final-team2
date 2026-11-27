# 사전 검수 5건 2차 수정 초안

> 모든 항목은 UNREVIEWED / PENDING입니다. 원문 발췌의 완전성은 UNKNOWN입니다. 논리 트리는 제안이며 신청 가능 판정을 수행하지 않습니다.

## 1. [달서구 중장년 기술창업센터] 예비창업자 교육 교육생 모집

공고 ID: `KSTARTUP:177469` / 출처: KSTARTUP

### 실제 조건 원문

```text
창업에 관심 있는 중장년(만 40세 이상) 예비창업자
```

### 기존 추출 후보와 수정 초안 대조

- `CND:WHRBQ2EXGXVCB4CGGZXYPLN3` `예비창업자` → **MATCH**: 예비창업자 개별 조건 일치. 연령·관심은 별도 누락

### 정답 조건 초안

- `GOLD:HH45KL6O5TMBFKCOKSP3PFXM` **ELIGIBILITY / FOUNDER_PROFILE / 연산자 미확정 / 값 None** · 적용: 신청자 정성 요건 · 결정 가능: False · 근거 `0:13` `창업에 관심 있는 중장년`. 창업 관심 정성 요건; 정보가 있다는 사실만으로 TRUE 불가
- `GOLD:F6FL67YCDDMVPJWEVNSKY2YP` **ELIGIBILITY / APPLICANT_AGE / GTE / 값 40** · 적용: 만 나이 · 결정 가능: True · 근거 `14:22` `만 40세 이상`. 기준일 미확인
- `GOLD:P57N2FFGCOAP35M56ZEZNJXI` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '예비창업자'** · 적용: 신청자 유형 · 결정 가능: True · 근거 `24:29` `예비창업자`. 

### 제안 논리 구조


```json
[
  {
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
    "review_status": "UNREVIEWED",
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
  }
]
```

### 최종 사람 검수

- 승인: [ ]  수정: [ ] 내용: ____________________  판단 불가: [ ] 사유: ____________________
- 검수자: ____________________  검수일: ____________________

## 2. 2026년 서강비즈니스센터 입주기업 모집(~4/5)

공고 ID: `KSTARTUP:176813` / 출처: KSTARTUP

### 실제 조건 원문

```text
ㅇ사업목적과 아이템이 「첨단기술 및 제품의 범위」에 속하는 예비창업자 또는 창업 7년 미만의 기업(입주신청일 현재)
ㅇ정부지원 타 보육센터 입주경험이 없는 자(지방 창업보육센터 제외)
ㅇ서강대학교와 산학협력사업 진행중인 기업 우대
ㅇ서강대학교와 기술이전 가능한 기업 우대
```

### 기존 추출 후보와 수정 초안 대조

- `CND:F77XTN5WHTCQTTNVTQ4V6NTF` `창업자 또는 창업 7년 미만` → **PARTIAL_MATCH**: 업력 기준일 입주신청일 현재 반영
- `CND:LHXAPWWGYLMBIB7JUAKN4G74` `예비창업자` → **MATCH**: 사람 확인 대기
- `CND:AA5EI662A5TEPVKB6UMUFRSG` `제외` → **FALSE_POSITIVE**: 지방 창업보육센터 경험은 예외
- `CND:BH26BINNLVA2VMM5VCQH5RZ5` `우대` → **PARTIAL_MATCH**: 두 우대를 개별 조건으로 분리

### 정답 조건 초안

- `GOLD:UUO4VKZ34CFAU3U3V45ME6XD` **ELIGIBILITY / BUSINESS_TECHNOLOGY_SCOPE / 연산자 미확정 / 값 None** · 적용: 공통 자격 · 결정 가능: False · 근거 `1:32` `사업목적과 아이템이 「첨단기술 및 제품의 범위」에 속하는`. 첨단기술 범위 세부 정의 미수집; 판정 UNKNOWN
- `GOLD:RBSON2DWXS3FIAMA2NIJKW37` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '예비창업자'** · 적용: OR 분기 · 결정 가능: True · 근거 `33:38` `예비창업자`. 
- `GOLD:CLG4YUJX3JBDNDXIIAIMP6HK` **ELIGIBILITY / BUSINESS_AGE / LT / 값 7** · 적용: OR 분기 · 결정 가능: True · 근거 `42:54` `창업 7년 미만의 기업`. 입주신청일 현재
- `GOLD:UTDHOPDVHP5NDS7BL2XQ773U` **ELIGIBILITY / RESTRICTED_GOV_INCUBATOR_EXPERIENCE_COUNT / EQ / 값 0** · 적용: 공통 자격 · 결정 가능: True · 근거 `66:102` `정부지원 타 보육센터 입주경험이 없는 자(지방 창업보육센터 제외)`. 지방 센터 이력만 제외하여 계산. 다른 제한 대상 정부 센터 이력이 있으면 0이 아님
- `GOLD:A3WST6DTWQKFYMUD6DWLMKYK` **PREFERENCE / SOGANG_ACADEMIC_COOPERATION / 연산자 미확정 / 값 None** · 적용: 우대 1 · 결정 가능: False · 근거 `104:128` `서강대학교와 산학협력사업 진행중인 기업 우대`. 우대 점수/중복 미확인
- `GOLD:VXO7CQZP4XQO64HSS7XBZ2CI` **PREFERENCE / SOGANG_TECH_TRANSFER_POSSIBILITY / 연산자 미확정 / 값 None** · 적용: 우대 2 · 결정 가능: False · 근거 `130:151` `서강대학교와 기술이전 가능한 기업 우대`. 우대 점수/중복 미확인

### 제안 논리 구조


```json
[
  {
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
        "review_status": "UNREVIEWED",
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
    "review_status": "UNREVIEWED",
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
  }
]
```
- 예외 `지방 창업보육센터 제외` → ['GOLD:UTDHOPDVHP5NDS7BL2XQ773U']. 입주 이력별 기관 필터: 지방 창업보육센터 경험만 제외; 다른 정부지원 센터 경험은 제한
- 우대 `서강대학교와 산학협력사업 진행중인 기업 우대`; 점수/중복 적용 미확인
- 우대 `서강대학교와 기술이전 가능한 기업 우대`; 점수/중복 적용 미확인

### 최종 사람 검수

- 승인: [ ]  수정: [ ] 내용: ____________________  판단 불가: [ ] 사유: ____________________
- 검수자: ____________________  검수일: ____________________

## 3. [강원] 2026년 직장문화ㆍ환경개선지원사업 참여기업 모집 공고

공고 ID: `BIZINFO:PBLN_000000000118927` / 출처: BIZINFO

### 실제 조건 원문

```text
도내 가족친화 및 일ㆍ생활 균형을 실천하는 기업
※ 자세한 지원대상 공고문 참조
```

### 기존 추출 후보와 수정 초안 대조

- 기존 후보 없음. 원문 기준 자격 후보를 새로 기록함.

### 정답 조건 초안

- `GOLD:HBL5D5ZJI7UTI2IAXLZRRRTK` **ELIGIBILITY / BUSINESS_LOCATION / EQ / 값 '강원도'** · 적용: 사업장 지역 · 결정 가능: False · 근거 `0:2` `도내`. 제목 [강원] + 본문 도내 복수 근거. 현 스키마의 단일 span은 본문만 참조
- `GOLD:I6BFAXO5QDH553LCFFVUKGJ2` **ELIGIBILITY / FAMILY_FRIENDLY_PRACTICE / 연산자 미확정 / 값 None** · 적용: 기업 실천 · 결정 가능: False · 근거 `3:7` `가족친화`. 정성 자격의 충족 기준 미수집. 정보 존재만으로 TRUE 불가
- `GOLD:AGZY7KXCI5HI4DUEJPPMTBIW` **ELIGIBILITY / WORK_LIFE_BALANCE_PRACTICE / 연산자 미확정 / 값 None** · 적용: 기업 실천 · 결정 가능: False · 근거 `10:26` `일ㆍ생활 균형을 실천하는 기업`. 정성 자격의 충족 기준 미수집. 정보 존재만으로 TRUE 불가

### 제안 논리 구조


```json
[
  {
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
    "review_status": "UNREVIEWED",
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
  }
]
```
- 미확정: 상세 기준 및 전체 판정은 공고문 확인 필요

### 최종 사람 검수

- 승인: [ ]  수정: [ ] 내용: ____________________  판단 불가: [ ] 사유: ____________________
- 검수자: ____________________  검수일: ____________________

## 4. [청년창업지원센터 상주올래] 2026 입주기업 모집

공고 ID: `KSTARTUP:178507` / 출처: KSTARTUP

### 실제 조건 원문

```text
전국 19세 이상 45세 이하 2026. 7. 7.(화) 기준, 사업 개시일로부터 7년이 지나지 아니한* 기업/예비창업자 *2019. 7. 8. 이후 사업을 개시한 창업기업
· 예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자
· 기 창업자는 신청일 기준 사업자등록이 완료되어야 하며, 사업장 소재지의 제한 없음
· 최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함 ※단, 해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료
· 지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)
· 국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가
· 최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)
```

### 기존 추출 후보와 수정 초안 대조

- `CND:7JY337WSVIQOWASD75J3XBUD` `예비창업자` → **MATCH**: 사람 확인 대기
- `CND:XFMX64TWAJXTYNE4ZMTMDGIF` `창업기업` → **MATCH**: 사람 확인 대기
- `CND:KWCB7IE2Y65REOCIVH7KONW5` `전국` → **FALSE_POSITIVE**: 전국은 지역 제한 없음. 조건값 확인 불필요
- `CND:OAGVVLW22ZLPWV46AUOLHOJS` `지원제외` → **UNRESOLVED**: 사람 확인 대기
- `CND:DNQ2I756A7TOBEMOIMJ6QSAA` `중소기업` → **FALSE_POSITIVE**: 법령명에서 파생된 오추출
- `CND:CZXVSBG3QPOCJO77ZRYCWLOD` `불가` → **PARTIAL_MATCH**: 중복입주, 적용시점 및 범위 불명

### 정답 조건 초안

- `GOLD:M7PXG6623INOEMITL3AOE3CK` **ELIGIBILITY / APPLICANT_AGE / BETWEEN / 값 {'lower': {'value': 19, 'inclusive': True}, 'upper': {'value': 45, 'inclusive': True}}** · 적용: 연령 · 결정 가능: False · 근거 `3:16` `19세 이상 45세 이하`. 기준일은 있으나 범위 미확인
- `GOLD:FE24B2OORHELAJRV66G7VJPC` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '예비창업자'** · 적용: 신청 OR 분기 · 결정 가능: True · 근거 `62:67` `예비창업자`. 
- `GOLD:DIZ2L732LLD4GHZKMKVWGAML` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '창업기업'** · 적용: 신청 OR 분기 · 결정 가능: True · 근거 `92:96` `창업기업`. 
- `GOLD:RKY5YC5WF6UKLIPCFCPOBLSC` **ELIGIBILITY / BUSINESS_AGE / LT / 값 7** · 적용: 창업기업 OR 분기 · 결정 가능: True · 근거 `36:61` `사업 개시일로부터 7년이 지나지 아니한* 기업`. 동일 업력 제한의 footnote 근거 {'start_char': 69, 'end_char': 96}; 중복집계 안 함
- `GOLD:V4K4AAIB7KG32LIHAEKQMZIU` **ELIGIBILITY / BUSINESS_REGISTRATION / 연산자 미확정 / 값 None** · 적용: 예비창업자 / 입주 후 3개월 · 결정 가능: False · 근거 `99:133` `예비창업자의 경우 입주 후 3개월 이내 사업자등록이 가능한 자`. 예비창업자는 입주 후 3개월 내 등록 가능. 현재 등록 완료 요구 아님
- `GOLD:UTYFQJK6CDHOFA3MZKFI3DFP` **ELIGIBILITY / BUSINESS_REGISTRATION_COMPLETED / EQ / 값 True** · 적용: 창업기업 / 신청일 · 결정 가능: True · 근거 `136:165` `기 창업자는 신청일 기준 사업자등록이 완료되어야 하며`. 기창업자에게만 신청일 현재 완료 요구
- `GOLD:IZGLBYNHDYFKYAW7RWGYQUCJ` **ELIGIBILITY / BUSINESS_LOCATION / EQ / 값 '청년창업지원센터 상주올래 입주공간'** · 적용: 선정 후 / 입주개시일+30일 · 결정 가능: False · 근거 `184:252` `최종선정 기업은 입주개시일 기준 30일 이내에 본점 또는 지점의 주소지를 청년창업지원센터 상주올래 입주공간으로 이전해야 함`. 선정 후 주소이전 의무; 신청 자격 판정에 사용 불가
- `GOLD:XNGCLJRMJ6SBOJFO6PQZI5SF` **EXCLUSION / 속성 미확정 / 연산자 미확정 / 값 None** · 적용: 신청 제외 · 결정 가능: False · 근거 `304:345` `지원제외 대상 : 중소기업창업 지원법 시행령 준용(6p 지원제외대상 참고)`. 6쪽 세부기준 미수집
- `GOLD:64HML7YO6L4FES5PLPUTFK2O` **EXCLUSION / DUPLICATE_OCCUPANCY / EQ / 값 True** · 적용: 시점/범위 미확인 · 결정 가능: False · 근거 `348:381` `국가, 지방자치단체, 공공기관의 창업지원시설에 중복입주 불가`. 해당하면 EXCLUSION TRUE; 시점/범위 미확인
- `GOLD:XNGYEKKQZZIRCEYLRC7XBPHS` **EXCLUSION / DUPLICATE_OCCUPANCY / EQ / 값 True** · 적용: 선정 후 / 본점지점 · 결정 가능: False · 근거 `384:432` `최종 선정된 기업은 상주올래와 타창업지원시설에 중복입주 불가(본점 및 지점 모두 포함)`. 해당하면 EXCLUSION TRUE; 선정 후 / 본점지점

### 제안 논리 구조

배열 순서: 신청 자격 트리, 신청 제외 트리, 입주 후 등록 가능 의무, 선정 후 주소 이전 의무, 선정 후 중복입주 제외. 단계 구분은 현재 AST 스키마에 없으므로 적용 범위를 별도로 확인해야 합니다.

```json
[
  {
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
            "node_type": "CONDITION_REF",
            "condition_id": "GOLD:FE24B2OORHELAJRV66G7VJPC"
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
            "review_status": "UNREVIEWED",
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
        "review_status": "UNREVIEWED",
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
    "review_status": "UNREVIEWED",
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
  {
    "node_type": "LOGICAL_GROUP",
    "group_id": "DRAFT:KSTARTUP:178507:SECOND:APPLICATION_EXCLUSION",
    "operator": "OR",
    "children": [
      {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:XNGCLJRMJ6SBOJFO6PQZI5SF"
      },
      {
        "node_type": "CONDITION_REF",
        "condition_id": "GOLD:64HML7YO6L4FES5PLPUTFK2O"
      }
    ],
    "review_status": "UNREVIEWED",
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
  {
    "node_type": "CONDITION_REF",
    "condition_id": "GOLD:V4K4AAIB7KG32LIHAEKQMZIU"
  },
  {
    "node_type": "CONDITION_REF",
    "condition_id": "GOLD:IZGLBYNHDYFKYAW7RWGYQUCJ"
  },
  {
    "node_type": "CONDITION_REF",
    "condition_id": "GOLD:XNGYEKKQZZIRCEYLRC7XBPHS"
  }
]
```
- 예외 `해외기업․기업부설연구소의 경우 입주계약체결일로부터 3개월 이내에 이전등록을 완료` → ['GOLD:IZGLBYNHDYFKYAW7RWGYQUCJ']. 해외기업/기업부설연구소의 이전등록 기한 예외

### 최종 사람 검수

- 승인: [ ]  수정: [ ] 내용: ____________________  판단 불가: [ ] 사유: ____________________
- 검수자: ____________________  검수일: ____________________

## 5. [경기] 2026년 사회적경제조직 특례보증 및 이차보전 지원 사업 공고

공고 ID: `BIZINFO:PBLN_000000000118182` / 출처: BIZINFO

### 실제 조건 원문

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

### 기존 추출 후보와 수정 초안 대조

- `CND:5ERHYIDNO5JBJZQI7IW5TOCD` `경기도` → **MATCH**: 제목 [경기]+본문 도내

### 정답 조건 초안

- `GOLD:O53W5ZPOQ3J4GMSQ2ACMSFOJ` **ELIGIBILITY / BUSINESS_LOCATION / EQ / 값 '경기도'** · 적용: 사업장 소재 · 결정 가능: True · 근거 `5:7` `도내`. 제목 [경기] + 도내
- `GOLD:AK6QCETSJGS72OBGPPVH3DRQ` **ELIGIBILITY / FOR_PROFIT_STATUS / EQ / 값 '영리기업'** · 적용: 기본 영리 원칙 · 결정 가능: True · 근거 `33:41` `영리기업인 경우`. 
- `GOLD:VPS4NR5FIET4BQFGJ4YRBTER` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '사회적기업'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `82:120` `- 「사회적기업 육성법」 제2조에 의한 사회적기업(비영리사업자 가능)`. 
- `GOLD:BP3Y47M5FUWWJYFGJHP3D2DF` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '예비사회적기업'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `121:154` `-「경기도 사회적경제 기본조례」 제2조에 의한 예비사회적기업`. 
- `GOLD:JB3FUI37RSO2M425UG5TFERN` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '협동조합'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `155:189` `-「협동조합기본법」 제2조에 의한 협동조합(비영리사업자 가능)`. 
- `GOLD:YN5LOI5WGWIRFPR5NFKMYFSG` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '마을기업'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `190:220` `-「경기도 사회적경제 기본조례」 제2조에 의한 마을기업`. 
- `GOLD:BWZKRDSI567HUS6IFN4GJ3HL` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '예비마을기업'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `221:253` `-「경기도 사회적경제 기본조례」 제2조에 의한 예비마을기업`. 
- `GOLD:UOAGRRT2R3XTU2SNSXFR242C` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '소비자생활협동조합'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `254:296` `-「소비자생활협동조합법」 제2조에 의한 소비자생활협동조합(비영리사업자 가능)`. 
- `GOLD:5JIPAID7CCBFOU3RIOTPMKOI` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '자활기업'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `297:323` `-「국민기초생활보장법」 제18조에 의한 자활기업`. 
- `GOLD:A4WSO43TKQWP7ID5FPS7U7HO` **ELIGIBILITY / BUSINESS_TYPE / EQ / 값 '소셜벤처기업'** · 적용: 8개 조직 유형 OR 대안 · 결정 가능: True · 근거 `324:356` `-「벤처기업육성에 관한 특별법」 제2조에 의한 소셜벤처기업`. 
- `GOLD:MD6SUB2ZEWNHTSQA4KVOGP3K` **ELIGIBILITY / FOR_PROFIT_STATUS / EQ / 값 '비영리사업자'** · 적용: 예외 허용 3개 조직 유형 · 결정 가능: True · 근거 `65:81` `비영리사업자도 지원할 수 있음`. 

### 제안 논리 구조

의미: 경기도 사업장 AND ((영리기업 AND 8개 유형 OR) OR (비영리사업자 AND 허용 3개 유형 OR)).

```json
[
  {
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
                "review_status": "UNREVIEWED",
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
            "review_status": "UNREVIEWED",
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
                "review_status": "UNREVIEWED",
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
            "review_status": "UNREVIEWED",
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
        "review_status": "UNREVIEWED",
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
    "review_status": "UNREVIEWED",
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
]
```
- 예외 `다만, 비영리사업자 가능으로 표시된 경우 비영리사업자도 지원할 수 있음` → ['GOLD:AK6QCETSJGS72OBGPPVH3DRQ', 'GOLD:MD6SUB2ZEWNHTSQA4KVOGP3K', 'GOLD:VPS4NR5FIET4BQFGJ4YRBTER', 'GOLD:JB3FUI37RSO2M425UG5TFERN', 'GOLD:UOAGRRT2R3XTU2SNSXFR242C']. 영리 요건 완화 효과는 OR AST에 명시; 비영리 허용은 3개 조직 유형만

### 최종 사람 검수

- 승인: [ ]  수정: [ ] 내용: ____________________  판단 불가: [ ] 사유: ____________________
- 검수자: ____________________  검수일: ____________________
