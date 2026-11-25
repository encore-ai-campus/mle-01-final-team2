# 정답셋 라벨링 가이드라인 (v0.1 초안)

> 목적: 공고 요건을 사람이 직접 정규화한 **정답**을 만들어 (1) 요건 추출 정확도, (2) 신청 자격 판정 정확도를 잰다.
> 상태: **초안.** 파일럿(§1)의 일치율을 보고 v0.2로 고친다. 수치·시간은 모두 가정이며 측정 전이다.
> 근거 문서: [MLE_2팀_기초 설계.md](MLE_2팀_기초%20설계.md) §4(스키마·3값 판정), [SAMPLE_그래프관계_분석.md](SAMPLE_그래프관계_분석.md)(F1~F15, D1~D5), [[도메인온톨로지] 설계서](%5B도메인온톨로지%5D%20MLE_도메인_온톨로지_설계서_2팀.md)

---

## 0. 원칙

| # | 원칙 | 이유 |
|---|---|---|
| 1 | **원본 문서를 사람이 읽고 쓴다.** 자동 추출 결과(`pdf_conditions_*`, 요건 후보 구간, OCR)는 보지 않는다. | 추출 결과를 보고 정답을 쓰면 평가가 오염된다 |
| 2 | **두 검수자가 서로 보지 않고 각자 쓴다.** 불일치는 나중에 협의한다. | 일치율이 규칙의 모호함을 보여 준다 |
| 3 | **원문에 없는 것은 만들지 않는다.** 불명확하면 `assumed`·`unparsed`·`open_ended`로 표시한다. | 거짓 확신이 `신청 가능` 오판으로 이어진다 |
| 4 | **근거 문장은 원문을 그대로 복사한다.** 요약하거나 고치지 않는다. | 근거 추적이 서비스의 핵심이다 |
| 5 | **법령·제도 용어의 뜻을 기억으로 쓰지 않는다.** 용어만 표시하고 정의는 원문 확인 후에 따로 만든다. | 법령 내용은 확인 전이다 |
| 6 | **합격선은 결과를 보기 전에 정한다.** | 결과에 맞춰 기준을 바꾸지 않기 위해 |

## 1. 후보와 진행 단계

후보는 `tools/select_goldset_candidates.py`가 시드 20261124로 뽑았고 같은 입력이면 같은 결과가 나온다. 결과는 `data/goldset/candidates_v0.1.csv`, 선정 근거는 `data/goldset/selection_report.json`에 있다(입력 파일 해시 포함).

| 구분 | 건수 | 내용 |
|---|---|---|
| **PILOT** | 10(기업마당 5, K-Startup 5) | 1단계. 두 검수자가 독립 라벨링해 일치율을 재고 이 가이드를 고친다 |
| **PRIMARY** | 20(PILOT 제외, 기업마당 10, K-Startup 10) | 2단계. 개정된 가이드(v0.2)로 라벨링 |
| **BACKUP** | 20(각 10) | 교체용 |

**선정 방식과 한계**
- 기업마당: 수집·추출을 마친 1,294건 중 990건이 후보 풀이다. 제외한 것: OCR이 필요한 공고 126건, 배포용 hwp 2건, 본문이 1,200자 미만이거나 20,000자를 넘는 공고 109건, 개인 대상으로 의심되는 공고 67건(D-5 제안). 풀의 특징은 정규식 **힌트**이며 정답이 아니다.
- 특징별 최소 건수를 채운다: N개 중 k개·열린 목록, 트랙, 법령 인용 다수, 제외 요건과 업력·연령 조건, 지역 한정+날짜 기간, 중앙부처, 기초자치단체 수행, 날짜 아닌 신청기간, 파일 형식(pdf·hwp·hwpx).
- **K-Startup은 동료가 만든 30건 중 15건이다.** 우리가 모집단 전체에서 뽑은 것이 아니라 대표성이 없다. K-Startup 원본 응답(`kstartup_30_raw.json`)은 아직 없다.
- 기업마당 API는 **마감 전 공고만** 준다. 공고가 내려가면 다시 받을 수 없으므로, 라벨링에 쓴 원본(`data/bizinfo/files/…`)과 추출 텍스트를 **고정 보관**한다(로컬, git 제외).
- "개인 대상" 판단은 키워드 힌트라 놓친 것이 있을 수 있다. 라벨링 중 개인 대상으로 확인되면 §1의 교체 규칙으로 바꾼다.

**교체 규칙**: 다음 경우에만 BACKUP과 바꾼다. (1) 본문이 아닌 첨부 대부분에 요건이 있는데 파일을 읽을 수 없다, (2) 개인 대상 공고다, (3) 원문이 요건을 담고 있지 않다(안내문·행사 안내). 사유를 `data/goldset/replacements.csv`에 적는다. 결과를 보고 어려운 공고를 빼지 않는다.

## 2. 작업 절차 (공고 한 건)

1. `candidates_v0.1.csv`에서 `local_original`(원본 파일)과 `url`(공고 원문)을 연다. K-Startup은 `url`과 API 필드를 본다.
2. **읽는 순서**: ① 원본 첨부 → ② 공고 원문 페이지 → ③ API 요약. 자동 추출 텍스트는 검색용으로만 쓰고 정답의 근거로 삼지 않는다.
3. 시작·종료 시각을 `time_minutes`에 기록한다(가정 15~30분/건이 맞는지 측정한다).
4. **라벨 A**(§3)를 JSON으로 쓴다. 다 쓴 뒤에 **라벨 B**(§4)를 쓴다.
5. 다른 검수자의 파일은 열지 않는다. 저장 위치: `data/goldset/labels/<검수자>/A/<notice_id>.json`, `…/B/<notice_id>.json` (`:`는 `_`로 바꾼다).

## 3. 라벨 A: 요건 추출

### 3.1 구조

```json
{
  "notice_id": "BIZINFO:PBLN_000000000119999",
  "reviewer": "A",
  "time_minutes": 18,
  "read": ["공고문.pdf p.1-3"],
  "tracks": [],
  "requirements": [
    {
      "req_id": "R1", "kind": "ELIGIBILITY", "logic": "AND", "logic_basis": "assumed", "min_count": null,
      "status": "parsed", "open_ended": false,
      "source_sentence": "초격차 분야 업력 7년 이내 창업기업(공고일 기준)", "source": "공고문.pdf p.1",
      "conditions": [
        {"cond_id": "C1", "attribute": "business_age", "operator": "LTE", "value": {"value": 7, "unit": "YEAR"}, "ref_date_kind": "NOTICE_DATE", "negate": false, "concept": null, "needs_definition": false, "note": ""},
        {"cond_id": "C2", "attribute": "applicant_type", "operator": "IS_A", "value": {"label": "창업기업"}, "ref_date_kind": "NONE", "negate": false, "concept": "APPLICANT_TYPE:창업기업", "needs_definition": true, "note": "창업기업의 법적 정의는 원문 확인 필요"}
      ]
    }
  ],
  "source_conflicts": [],
  "ambiguities": ["'초격차 분야'가 어떤 업종 목록인지 문서에 없음"]
}
```

### 3.2 필드 규칙

| 필드 | 값·규칙 |
|---|---|
| `kind` | `ELIGIBILITY`(신청 자격), `EXCLUSION`(신청 제외), `PREFERENCE`(우대, 판정에 쓰지 않음), `DOCUMENT`(제출 서류), `LIMIT`(지원 한도·횟수·입주 후 의무), `CRITERION`(평가·선정 기준). **자격과 제외만 판정에 쓰므로 이 둘을 가장 정확히 쓴다.** 서류·평가·우대는 있는지만 표시하고 조건으로 풀지 않는다 |
| `logic` | `AND`, `OR`, `NONE_OF`(제외 요건: 하나라도 해당하면 제외), `AT_LEAST`(`min_count`에 k) |
| `logic_basis` | 원문에 "모두", "하나 이상", "다음 중 N개" 등이 **명시**되면 `explicit`. 조건을 나열만 했으면 `assumed`(AND로 적되 가정임을 표시) |
| `status` | `parsed`, `unparsed`("자세한 내용은 공고문 참조"처럼 읽을 수 없는 요건. 이런 **자격 요건**이 있으면 판정은 `NEEDS_CHECK`). 읽은 곳에 요건이 아예 없으면 `requirements`를 비우고 `ambiguities`에 이유를 쓴다 |
| `open_ended` | 목록이 "…등"으로 끝나 전체를 알 수 없으면 `true`. 이 요건은 `신청 가능`을 만들지 못한다 |
| `source_sentence` | 원문 그대로 복사. 한 요건에 여러 문장이면 `;`로 잇지 말고 핵심 문장 하나, 나머지는 `source_extra`(배열)에 |
| `source` | 파일명·쪽, 또는 API 필드명(K-Startup) |
| `tracks` | 대상별로 조건·지원 규모가 다르면 트랙으로 나눈다(예: "농업인은 …, 농업법인은 추가로 …"). 트랙 안의 요건은 `track_id`를 붙인다. 공통 요건은 트랙 밖에 둔다 |
| `source_conflicts` | API 구조화 필드(예: K-Startup `biz_enyy`, `supt_regin`)와 본문이 다르면 **본문을 따르고** 충돌을 기록한다 |
| `ambiguities` | 라벨러가 확신하지 못한 곳. 이 목록이 가이드 개정의 재료다. 빈 칸으로 두지 않는다 |

### 3.3 attribute·operator (허용 목록)

| 구분 | 값 |
|---|---|
| `attribute` | `region`, `zone`, `industry`, `applicant_type`, `business_age`, `founder_age`, `company_size`, `revenue`, `employees`, `certification`, `prior_award`, `registration`, `other` |
| 제안 5종(D-4, 확정 전) | `tenure_years`, `career_years`, `capital`, `funding_stage`, `membership` → **v0.1에서는 `other`에 쓰고 `note`에 제안 이름을 적는다.** 사용 빈도를 보고 D-4를 정한다 |
| `operator` | `EQ`, `LT`, `LTE`, `GT`, `GTE`, `BETWEEN`, `IN`, `WITHIN`(공간 포함), `IS_A`(종류), `EXISTS` |
| `ref_date_kind` | `NONE`, `NOTICE_DATE`(공고일), `DEADLINE`(접수 마감일), `PREV_YEAR`(전년도), `OTHER`(불명확). 업력·연령·매출·종업원처럼 기준일이 필요한 속성은 반드시 적는다 |

### 3.4 값 정규화 규칙

| 상황 | 규칙 |
|---|---|
| "7년 이내" / "7년 미만" | `이내` = `LTE 7`, `미만` = `LT 7`. **원문 표현이 다르면 다르게 쓴다.** 구조화 필드와 본문이 다르면 `source_conflicts`에 적는다 |
| "만 18세 이상 ~ 만 40세 미만" | `BETWEEN` + `min_inclusive: true`, `max_inclusive: false` |
| 연령에 출생연도 범위가 병기 | 조건 하나로 쓰고 출생연도 범위는 `note`에 보존한다. 출생연도가 있으면 그것을 우선한다(F11) |
| 금액·인원 | 원 단위 정수와 `unit`(`KRW`, `PERSON`). "10인 미만" = `LT 10` |
| 열거 "A, B, C" | 하나라도(OR) 해당이면 `IN`. 모두 충족해야 하면 조건을 나눠 `AND` |
| 지역 | `WITHIN` + 개념 라벨. 거주·사업장 소재·주민등록 등 **기준이 다르면** `note`에 기준을 쓴다. "관내", "소재"를 해석해 확대하지 않는다 |
| 지역 개념이 코드표에 없음(예: 옛 "광주광역시") | `concept`를 비우고 `note`에 원문 표기를 쓴다. 억지로 다른 지역에 대응시키지 않는다 |
| "~이거나/또는" 으로 분기 | 요건을 `OR`로 쓰고 분기마다 조건 묶음. 예시 §6-2 |
| 선정 후 의무(예: "60일 이내 본사 이전") | 신청 자격이 아니므로 `kind: LIMIT`, `note`에 "선정 후 의무" |
| 조건 없음("관심 있는 누구나") | 조건을 만들지 않는다. 확인할 수 없는 표현("관심", "의지")은 조건이 아니다 |
| 오탈자·동음이의 | 원문 그대로 `source_sentence`에 두고 `note`에 추정 의미를 적는다 |
| 법령·제도 용어("중소기업", "소상공인", "여성기업") | `needs_definition: true`. 뜻은 쓰지 않는다 |

## 4. 라벨 B: 신청 자격 판정

**가상 프로필 × 공고**에 대해 사람이 공고를 읽고 판정한다. **라벨 A에서 계산하지 않는다**(순환 방지). 라벨 A를 쓴 뒤에도 A를 열어 보지 않고 공고 원문으로 판정한다.

### 4.1 프로필 필드

`region`(시군구까지), `business_status`(`예비창업자`/`사업자`), `business_age_years`(소수 가능), `founder_age`(만 나이), `company_size`(`소상공인`/`소기업`/`중기업`/`중견`), `industry`, `employees`, `revenue_krw`, `certifications`(배열), `gender`, `special_group`(배열). **값이 없는 필드는 "미입력"이다.** 미입력이 필요한 조건에는 판정할 수 없어 `UNKNOWN`이다.

### 4.2 공통 프로필 8종 (가상)

| ID | 요약 |
|---|---|
| P1 | 서울 성동구, 법인 제조업, 업력 2년, 대표 만 35세, 소기업, 직원 8명 |
| P2 | 경북 구미시, 개인사업자 도소매업, 업력 8년, 대표 만 45세, 소상공인, 직원 3명 |
| P3 | 사업자 없음(예비창업자), 경남 창원시 거주, 만 24세 |
| P4 | 광주 남구, 법인 서비스업, 업력 5년, 만 39세, 중기업(구 광주광역시 지역) |
| P5 | 충북 청주시, 법인 IT업, 업력 0.5년, 만 29세, 벤처기업 확인서 보유 |
| P6 | 경기 성남시, 여성 대표 법인, 업력 정확히 3년, 만 40세 정각(경계값) |
| P7 | 대전, 사회적기업 인증, 업력 10년, 직원 12명, 연 매출 30억 원 |
| P8 | 제주시, 양식업 예정자(사업자 미등록), 만 36세 |

### 4.3 공고당 5개 프로필 배정 규칙

1. 공고의 **조건에 맞을 것 같은** 프로필 1개 이상
2. **맞지 않을 것 같은** 프로필 1개 이상
3. **경계값**: 공고의 수치(예: 업력 7년, 만 39세)에 맞춘 프로필을 새로 만들어 1개(`PX-<공고번호끝6자리>-1`)
4. **미입력**을 일부러 넣은 프로필 1개(필요한 속성을 비워 `UNKNOWN`/`NEEDS_CHECK`가 나오게)
5. 나머지는 위 공통 프로필에서 고른다

두 검수자는 **같은 5개 프로필**을 쓴다(배정은 파일럿 때 한 사람이 정해 `data/goldset/profiles_assignment.csv`에 두고 공유한다).

### 4.4 판정값과 작성

- 조건별: `SATISFIED` / `UNSATISFIED` / `UNKNOWN`. 공고별: `ELIGIBLE` / `NOT_ELIGIBLE` / `NEEDS_CHECK`(트랙이 있으면 트랙별로 쓰고 합성한다).
- 합성 규칙은 기초 설계서 §4.2를 따른다: `AND`(모두 충족이면 충족, 하나라도 불충족이면 불충족, 그 외 미확인), `OR`, `NONE_OF`(제외), `AT_LEAST(k)`(충족 s≥k면 충족, s+미확인<k면 불충족), 트랙은 하나라도 `ELIGIBLE`이면 `ELIGIBLE`. `logic_basis: assumed`, `unparsed` 자격 요건, `open_ended` 요건이 `ELIGIBLE`을 만들 상황이면 **`NEEDS_CHECK`**.
- **`NEEDS_CHECK`는 정답이다.** 판정하기 어렵다고 억지로 `ELIGIBLE`/`NOT_ELIGIBLE`로 쓰지 않는다.
- 사용자가 상위 지역(경상북도)만 입력했는데 조건이 하위 지역(구미시)이면 `UNKNOWN`, 서로 다른 가지면 `UNSATISFIED`(기초 설계서 H3).

```json
{"notice_id": "BIZINFO:PBLN_000000000119999", "reviewer": "A", "profile_id": "P1",
 "conditions": [{"cond_ref": "C1", "result": "SATISFIED", "why": "업력 2년 ≤ 7년"}, {"cond_ref": "C2", "result": "UNKNOWN", "why": "창업기업 요건의 정의 확인 필요"}],
 "overall": "NEEDS_CHECK", "reason_codes": ["ASSUMED_LOGIC", "NEEDS_DEFINITION"]}
```

`reason_codes`: `ASSUMED_LOGIC`, `REQ_UNPARSED`, `OPEN_ENDED`, `PROFILE_MISSING_ATTR`, `NEEDS_DEFINITION`, `SOURCE_CONFLICT`, `BOUNDARY_UNCLEAR`, `TRACK_SPLIT`.

## 5. 일치율 측정(파일럿 10건)

| 지표 | 정의 | 합격선 |
|---|---|---|
| 요건 일치 | 두 검수자의 `ELIGIBILITY`·`EXCLUSION` 요건이 같은 요건인지(원문 문장이 같은 구절을 가리키는지)로 짝지어 F1 | `[ ]` |
| 조건 일치 | 짝지어진 요건 안에서 `attribute`+`operator`+`value`가 같은 조건의 비율(엄격), `attribute`만 같은 비율(느슨) | `[ ]` |
| 논리·플래그 일치 | `logic`, `logic_basis`, `open_ended`, `status` | `[ ]` |
| 판정 일치 | 같은 (공고, 프로필) 쌍의 공고별 판정 일치율과 Cohen's κ | `[ ]` |

- **합격선은 파일럿 결과를 보기 전에 팀이 정해 이 표에 적는다.**
- 불일치는 둘이 원문을 같이 보고 합의하며, 합의 결과와 이유를 `data/goldset/adjudication.csv`에 남긴다. 가이드의 어느 규칙이 모호했는지 분류해 v0.2에 반영한다.
- 파일럿에서 일치율이 낮으면 규칙을 고치고 **파일럿을 다시** 한다(PRIMARY로 넘어가지 않는다).

## 6. 실물 예시 (후보가 아닌 공고)

원문은 `data/bizinfo/parsed/…/notices.jsonl`의 API 자격 문구이며 요약해 옮기지 않았다. 아래 정규화는 **내 해석(검수 전)** 이다.

**6-1. `BIZINFO:PBLN_000000000119999` 인천 창업-BuS** — 문구: "초격차 분야 업력 7년 이내 창업기업(공고일 기준)"
- R1(ELIGIBILITY, AND, `assumed`): C1 `business_age LTE 7`, `ref_date_kind: NOTICE_DATE`; C2 `applicant_type IS_A 창업기업`(`needs_definition`); C3 `industry`는 "초격차 분야"가 업종 목록인지 불명 → `attribute: other`, `note`에 쓰고 `ambiguities`에 기록.

**6-2. `BIZINFO:PBLN_000000000120707` 구미시 스타트업 제작센터** — 문구: "구미 소재 창업기업 중 업력 7년 이내 창업기업 (신청일 기준) / 구미(본사)로 이전 계획 기업 / 타 지역 창업기업의 경우 선정 후 60일 이내 구미 본사 이전 必"
- R1(ELIGIBILITY, `OR`): 분기1 = {`region WITHIN 구미`, `business_age LTE 7` `ref_date_kind: OTHER`("신청일 기준"은 DEADLINE이 아니라 신청일이라 OTHER로 두고 note)}, 분기2 = {본사 이전 계획 `other`}.
- R2(LIMIT): "선정 후 60일 이내 구미 본사 이전" = 선정 후 의무.
- 본문의 "구미"와 API 해시태그(지역 전부)가 충돌 → `source_conflicts`에 기록, 본문을 따른다.

**6-3. `BIZINFO:PBLN_000000000126517` 김해시 소상공인 육성자금** — 문구: "김해시에 사업장을 두고 사업자등록을 한 소상공인 / 광업ㆍ제조업ㆍ건설업ㆍ운수업 : 상시종업원 10인 미만 업체 / 그 외의 업종 : 상시종업원 5인 미만 업체"
- 업종에 따라 **종업원 기준이 달라지는** 구조: 트랙 또는 조건부 요건(`industry IN {광업, 제조업, 건설업, 운수업}` → `employees LT 10`, 그 외 → `employees LT 5`)으로 쓴다. 어느 쪽으로 쓸지 `ambiguities`에 이유와 함께 적는다(이런 선택의 불일치가 곧 개정할 규칙이다).
- 지원제외 대상(휴·폐업, 지방세 체납, 기존 육성자금 수혜 업체 등)은 별도 `EXCLUSION`, `logic: NONE_OF`.

**6-4. `BIZINFO:PBLN_000000000117985` 방송광고비 할인지원** — 문구: "벤처기업, 이노비즈, 메인비즈 등 중 하나 이상의 확인서를 보유한 기업 중 최근 6개월간 지상파 전국권 방송광고 집행이 없는 기업"
- R1(ELIGIBILITY, `OR`, `explicit`("하나 이상"), `open_ended: true`("등")): `certification EXISTS` ×3.
- R2(EXCLUSION, `NONE_OF`): "최근 6개월간 지상파 전국권 방송광고 집행" 해당 시 제외. `ref_date_kind`는 기준 시점이 불명이면 `OTHER`.
- 이 공고는 "자세한 지원대상 출처 바로가기 링크 참조" 문구도 있어 **링크 안 내용이 요건의 일부일 수 있음**을 `ambiguities`에 적는다.

## 7. 점검 체크리스트(제출 전)

- [ ] `source_sentence`가 원문과 글자 단위로 같다
- [ ] 기준일이 필요한 속성(`business_age`, `founder_age`, `revenue`, `employees`)에 `ref_date_kind`가 있다
- [ ] `logic_basis`가 `explicit`인 곳은 원문에 명시 표현이 있다
- [ ] "…등"으로 끝나는 목록은 `open_ended: true`
- [ ] 법령·제도 용어에는 `needs_definition: true`, 뜻을 쓰지 않았다
- [ ] 자격·제외 요건을 빠뜨리지 않았다(서류·평가·우대는 있는지만)
- [ ] 라벨 B의 `NEEDS_CHECK`에는 `reason_codes`가 있다
- [ ] 다른 검수자 파일과 자동 추출 결과를 보지 않았다
- [ ] `time_minutes`를 적었다

## 8. 팀이 정해야 할 것

| # | 결정 | 제안 |
|---|---|---|
| G-1 | 검수자 2인 지정, 일정 | 파일럿 10건 × 2인. 팀원이 3명이므로 라벨러 2명 + 라벨을 쓰지 않는 배정·점검 1명으로 나눈다(제안은 PILOT 안내서 §3) |
| G-2 | 파일럿 합격선(§5 표) | 결과를 보기 전에 합의 |
| G-3 | 공통 프로필 8종 확정 | 이 초안 그대로 시작해 고친다 |
| G-4 | K-Startup 원본 응답 확보 | 동료에게 `kstartup_30_raw.json` 요청. 모집단 대표성은 없음을 문서화 |
| G-5 | D-4(속성 허용 목록), D-5(개인 대상 제외) | 파일럿의 `other` 사용 빈도를 보고 결정 |
| G-6 | 라벨 파일 저장소 위치 | `data/goldset/labels/`는 git에 올리되, 원본 파일과 추출 텍스트는 올리지 않는다 |

## 9. 한계

- 후보 선정은 정규식 힌트와 시드 고정 탐욕 선택이다. 모집단을 대표하는 확률 표본이 아니라 **특징을 고르게 덮도록 고른 표본**이므로 비율 주장에 쓰지 않는다.
- K-Startup은 동료 표본 30건에서만 뽑았다.
- 가이드의 규칙 상당수(예: `이내`/`미만`, 업종별 조건부 요건)는 사례 몇 건에서 정한 것이라 파일럿에서 바뀔 수 있다.
- 법령 기준(중소기업·소상공인·여성기업 등)은 원문을 확인하지 않았고 이 가이드는 그 해석을 라벨러에게 맡기지 않는다.
- 정답셋이 있어도 그래프가 SQL보다 필요하다는 증거가 되지는 않는다. 같은 질문 세트로 SQL 베이스라인과 비교해야 한다.
