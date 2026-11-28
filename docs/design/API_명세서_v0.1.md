# 백엔드 API 명세서 (v0.1 초안)

> 2팀 근거it · 지원각 · 작성 2026-11-25 · 상태: **초안(팀 검토 전)**
> 기준 문서: 화면설계서 v3.5(SCR-00~06, EX-01~06의 "API 연계(예시)"), 기획 보고서(FR-N·NFR-N·MR-N), 기초 설계서 §7.1(에이전트)·§7.3(응답 정책), 온톨로지 설계서 v0.2와 보완안
> 데이터 기준: 정리 층 `data/cleaned/20261124/`, 공통 정규화 v1 `data/normalized/v1/20261124/`, 나라장터 정리 층 `data/g2b_cleaned/20261124/`, 지역 사전 `data/사전/`
> 구현 전 설계다. 필드·경로는 화면설계서 예시를 따르되, 판정 결과 형식은 온톨로지 설계(3값, 조건 트리, 근거 경로)에 맞췄다.

---

## 1. 개요

| 항목 | 값 |
|---|---|
| 서버 | FastAPI (Python), AWS CPU 서버(Docker). 모델 서버(vLLM)는 RunPod (2026-11 팀 결정, 예전 값은 Cloud Run) |
| 기본 경로 | `/api` (버전은 `/api/v1`로 올릴지 팀 결정, §10) |
| 인증 | Supabase Auth(Google 로그인)가 발급한 JWT를 `Authorization: Bearer <token>`으로 보낸다. 서버는 JWT를 검증하고 역할(`user` / `admin`)을 서버 쪽 허용 목록으로 확인한다 |
| 형식 | JSON(UTF-8). 챗봇만 SSE(`text/event-stream`) |
| 시각 | ISO 8601, 한국 시각(`+09:00`). 날짜만 있는 값은 `YYYY-MM-DD` |
| 판정 | 조건은 `SATISFIED` / `UNSATISFIED` / `UNKNOWN`, 공고는 `ELIGIBLE` / `NOT_ELIGIBLE` / `NEEDS_CHECK`. **판정은 규칙 평가기(코드)가 하고 모델은 판정을 바꾸지 않는다** |
| 원칙 | 모든 판정에 출처·수집 시각·원문 링크(MR-N2), 참고용 면책(MR-N1), 규칙·사전·스키마 버전(NFR-N05)을 붙인다 |

### 1.1 엔드포인트 목록

| # | 메서드·경로 | 기능 | 화면 | 권한 | 우선순위 | 요구사항 |
|---|---|---|---|---|---|---|
| A-01 | `GET /api/me` | 로그인 사용자·역할 | SCR-00 | 로그인 | P0 | FR-N10 |
| A-02 | `GET` `POST` `/api/consents` · `PATCH /api/consents` | 필수·선택 동의 조회·등록·철회 | SCR-00-1, SCR-05 | 로그인 | P1 | FR-N16, NFR-N03 |
| N-01 | `GET /api/notices` | 공고 목록·검색 (지원사업 / 입찰) | SCR-01, 01-1 | 로그인 | P0 | FR-N01, FR-N05 |
| N-02 | `GET /api/notices/{notice_id}` | 공고 상세·원문 | SCR-02 | 로그인 | P0 | FR-N05, MR-N2 |
| N-03 | `GET /api/notices/{notice_id}/spans` | 판정에 쓴 원문 문장 위치 | SCR-02 | 로그인 | P0 | FR-N05 |
| N-04 | `GET /api/notices/{notice_id}/forms` | 공고가 요구하는 문서·공식 양식 | SCR-02, SCR-03 | 로그인 | P1 | FR-N20 |
| C-01 | `GET /api/concepts` | 개념 검색(지역·신청자 유형·인증·면허) | SCR-01, 01-1 입력칸 | 로그인 | P0 | FR-N03 |
| E-01 | `POST /api/eligibility` | 조건으로 맞는 공고 찾기(3값 목록) | SCR-01, 01-1 | 로그인 | P0 | FR-N04, FR-N09 |
| E-02 | `GET /api/eligibility/{notice_id}` | 한 공고의 조건별 검증 | SCR-02-1 | 로그인 | P0 | FR-N02, FR-N05 |
| E-03 | `GET /api/eligibility/{notice_id}/path` | 추론 과정·근거 경로 | SCR-02-2 | 로그인 | P0 | FR-N06, FR-N08 |
| E-04 | `POST /api/eligibility/clarify` | 되묻기 답변 반영 재판정 | SCR-02-1 | 로그인 | P0 | FR-N09 |
| E-05 | `POST /api/eligibility/what-if` | 값을 바꿔 보는 재판정(저장 안 함) | SCR-02-1 | 로그인 | P1 | FR-N07 |
| P-01 | `GET` `POST` `/api/profiles` · `PATCH` `DELETE /api/profiles/{profile_id}` | 내 조건 저장·관리 | SCR-01, SCR-05 | 로그인 + 선택 동의 | P1 | FR-N16 |
| H-01 | `POST /api/chat` (SSE) | 챗봇 | SCR-04 | 로그인 | P0 | FR-N18, FR-N13 |
| H-02 | `GET /api/conversations` · `GET` `DELETE /api/conversations/{id}` | 대화 이력 | SCR-04, SCR-05 | 로그인 + 선택 동의 | P1 | FR-N19 |
| D-01 | `POST /api/applications` · `GET /api/applications` | 작업 문서 만들기(내용 없음)·목록 | SCR-03, 03-1 | 로그인 | P1 | FR-N20, FR-N21 |
| D-02 | `GET` `PATCH` `DELETE /api/applications/{id}` | 초안 조회·수정·삭제 | SCR-03, 03-1 | 본인 | P1 | FR-N21 |
| D-03 | `POST /api/applications/{id}/fields/{field_id}/regenerate` | 항목 다시 쓰기 | SCR-03 | 본인 | P1 | FR-N20 |
| D-05 | `POST /api/applications/{id}/generate` | 양식 항목 순서대로 초안 생성 | SCR-03 | 본인 | P1 | FR-N20 |
| D-04 | `POST /api/applications/{id}/forms` 외 3개 | 공식 양식 올리기·항목 확인·삭제 | SCR-03-2 | 본인 | P1 | FR-N20, NFR-N07 |
| M-01 | `GET /api/admin/status` | 운영 현황·수집 상태 | SCR-06 | 관리자 | P0 | FR-N17, NFR-N01 |
| M-02 | `POST /api/admin/updates` · `GET /api/admin/updates/{run_id}` | 공고 업데이트 실행·진행 | SCR-06-1 | 관리자 | P1 | FR-N01, FR-N15 |
| M-03 | `POST /api/admin/reprocess` | 실패 건 재처리 | SCR-06 | 관리자 | P0 | FR-N17 |
| M-04 | `GET` `PATCH /api/admin/review/{notice_id}` · `POST /api/admin/review/{notice_id}/approve` | 요건 정규화 검수·승인 | SCR-06-2 | 관리자 | P1 | FR-N02, FR-N12 |
| M-05 | `GET /api/admin/ingest/{notice_id}/report` · `POST /api/admin/ingest/{notice_id}/approve` | 입수 시점 검증 | SCR-06-3 | 관리자 | P1 | FR-N11 |
| M-06 | `GET /api/admin/audit-logs` · `GET` `POST` `DELETE /api/admin/allowlist` | 감사 로그·관리자 허용 목록 | SCR-06-4 | 관리자 | P1 | FR-N12, MR-N5 |
| S-01 | `GET /api/meta` | 데이터 기준 시각·버전·면책 문구·구간 코드표 | 모든 화면 배지, 입력 선택지 | 공개 | P0 | NFR-N01, NFR-N05 |
| O-01 | `GET /api/admin/metrics` | 토큰·비용·응답 시간·사유 코드 집계 | SCR-06 관측·비용 | 관리자 | P1 | NFR-N06, NFR-N08 |
| O-02 | `GET /api/admin/evals` · `GET /api/admin/evals/{run_id}` | 평가 실행 결과(RAGAS·판정 정확도·속도) | SCR-06 요건 통계·평가(P2) | 관리자 | P1 | NFR-N06 |

**화면설계서 예시와 다른 점**
- `POST /api/eligibility?type=bid`(화면설계서 SCR-01-1): 공고 종류는 요청 본문의 `type`으로 받는다. 쿼리 `type`도 같은 뜻으로 받아 준다.
- `GET·DELETE /api/applications`(SCR-03-1): 삭제는 문서 하나씩 `DELETE /api/applications/{id}`로 한다. 목록 전체 삭제 API는 두지 않는다(실수 방지).
- 화면설계서의 `GET /auth/google`은 서버 API가 아니라 Supabase Auth의 Google 로그인으로 처리한다(프론트에서 Supabase SDK 호출).
- `C-01`·`S-01`은 화면설계서에 없던 것으로, 입력칸 자동완성과 수집 시각 배지에 필요해 추가했다.

---

## 2. 공통 규칙

### 2.1 응답 틀

모든 JSON 응답은 같은 틀을 쓴다.

```json
{
  "data": { },
  "outcome": "answered",
  "display_status": null,
  "reason_codes": [],
  "meta": {
    "request_id": "req_01J...",
    "trace_id": "lf_8c2...",
    "data_as_of": { "BIZINFO": "2026-11-24T09:16:01+09:00", "KSTARTUP": "2026-11-24T00:00:00+09:00", "G2B": "2026-11-25T10:25:08+09:00" },
    "stale": false,
    "versions": { "rule": "0.1", "dictionary": "region-20261125", "schema": "support-notice-v1", "model": null },
    "disclaimer": "이 결과는 참고용입니다. 신청 가능 여부와 선정은 공고 원문과 주관 기관의 판단에 따릅니다."
  }
}
```

| 필드 | 뜻 |
|---|---|
| `outcome` | `answered`(정상) / `held`(확인 필요·판단 불가 계열) / `refused`(차단) / `degraded`(규칙 판정만 모드 등) / `failed`. 기초 설계서 §7.3 매핑 |
| `display_status` | 화면 상태 배지. 공고 판정(`ELIGIBLE` 등)과 **다른 축**이다(아래 2.3). 정상 응답이면 `null` |
| `reason_codes` | 아래 2.3의 코드. 공고 일부에만 해당하면 그 공고 항목에도 붙인다 |
| `meta.trace_id` | Langfuse 트레이스 ID. 토큰·속도 측정과 장애 추적(§10.1) |
| `meta.data_as_of` | 출처별 마지막 수집 시각. 화면의 수집 시각 배지(NFR-N01) |
| `meta.stale` | 수집 지연 한도를 넘으면 `true`와 함께 `STALE_DATA` |
| `meta.versions` | 재현성(NFR-N05). 판정을 만든 규칙 평가기·사전·스키마·모델 버전 |

### 2.2 오류

| HTTP | 언제 | `reason_codes` |
|---|---|---|
| 400 | 형식 오류, 필수값 누락 | `INVALID_INPUT`(필드 목록 포함) |
| 401 | 토큰 없음·만료 | `UNAUTHENTICATED` |
| 403 | 권한 없음 | `ROLE_DENIED` (EX-05). 어떤 데이터도 노출하지 않는다 |
| 404 | 공고·문서 없음, 다른 사용자의 자원 | `NOT_FOUND` (다른 사용자 자원도 존재를 드러내지 않게 404) |
| 409 | 업데이트 동시 실행, 마감·신청 불가 공고의 초안 생성 | `CONFLICT`, `NOT_APPLICABLE` |
| 422 | 개인정보·인젝션 입력 | `PII_BLOCKED`, `INJECTION_BLOCKED` (EX-04). 입력 값은 저장·기록하지 않는다 |
| 429 | 호출 과다 | `RATE_LIMITED` |
| 503 | 모델·그래프 장애 | `SERVICE_DEGRADED` (EX-06). 판정은 가능하면 규칙 판정만 모드로 200 |

```json
{ "data": null, "outcome": "refused", "reason_codes": ["PII_BLOCKED"],
  "error": { "message": "입력에 사업자등록번호나 연락처로 보이는 내용이 있어 처리하지 않았습니다. 번호를 빼고 지역·업종·업력처럼 범주로 다시 입력해 주세요.", "fields": ["free_text"] },
  "meta": { "request_id": "req_..." } }
```

### 2.3 사유 코드 (FR-N13, 기초 설계서 §7.3)

| 코드 | 화면 | 뜻 |
|---|---|---|
| `NO_MATCH` | EX-01 | 계층 확장 후에도 후보 0건 |
| `INSUFFICIENT_PROFILE` | EX-02 | 되묻기 2회 후에도 판정에 필요한 값 없음 |
| `REQ_UNPARSED` | EX-03 | 요건을 조건으로 해석하지 못함 |
| `CHAIN_BROKEN` | EX-03 | 정의 → 법령 연결이 끊김 |
| `PII_BLOCKED`, `INJECTION_BLOCKED`, `OUT_OF_SCOPE`, `LEGAL_ADVICE` | EX-04 | 입력 차단 |
| `ROLE_DENIED` | EX-05 | 권한 없음 |
| `STALE_DATA`, `SERVICE_DEGRADED`, `OUTPUT_BLOCKED` | EX-06 | 수집 지연, 장애, 출력 차단 |

화면 문구는 서버가 고정 템플릿으로 내려준다(`error.message` 또는 `data.notice_message`). 모델이 쓰지 않는다. 차단 규칙과 임계값은 응답에 넣지 않는다.

**판정 배지와 상태 배지를 섞지 않는다.** 입력 차단이나 권한 없음은 공고의 신청 자격을 평가한 결과가 아니므로 "신청 불가" 배지를 쓰지 않는다. 공고 판정(`verdict`)은 비우고 `display_status`로 표시한다.

| 상황 | `outcome` | `verdict` | `display_status` | 화면 배지 |
|---|---|---|---|---|
| EX-01 `NO_MATCH` | `held` | 없음 | `NO_RESULT` | 맞는 공고 없음 |
| EX-02·EX-03 (정보 부족·해석 실패) | `held` | 공고별 `NEEDS_CHECK` | `null` | 확인 필요 (공고 판정) |
| EX-04 입력 차단 | `refused` | 없음 | `INPUT_REJECTED` | **입력 처리 불가** |
| EX-05 권한 없음 | `refused` | 없음 | `ACCESS_DENIED` | **접근 권한 없음** |
| EX-06 지연·장애·출력 차단 | `answered`(경고) / `degraded` | 규칙 판정 유지 | `LIMITED` | 일부 기능 제한 |

### 2.4 ID 규칙

| 대상 | 형식 | 예 |
|---|---|---|
| 공고 | `{출처}:{원천 ID}` | `BIZINFO:PBLN_000000000128083`, `KSTARTUP:179839`, `G2B:R26BK01818055:000` |
| 지역 | `REGION:{법정동코드}`, 묶음 `REGION_GROUP:{로마자}` | `REGION:4111100000`, `REGION_GROUP:GWANGJU_OLD` |
| 신청자 유형·인증 | `APPLICANT_TYPE:{이름}`, `CERTIFICATION:{이름}` | `APPLICANT_TYPE:중소기업`, `CERTIFICATION:벤처기업` |
| 요건·조건 | `{notice_id}@v{버전}#R{n}`, `...#C{n}` | `BIZINFO:PBLN_000000000119999@v1#R1#C1` |
| 법령 | `LAW:{법령 ID}`, 조문 `LAW:{ID}#제{n}조`, 별표 `LAW:{ID}#별표{n}` | `LAW:281989#제2조` |

### 2.5 페이지

목록은 `?limit=20&cursor=<불투명 문자열>`. 응답 `data.next_cursor`가 `null`이면 끝이다.

### 2.6 개인정보

- 사용자의 사업자등록번호·주민등록번호·연락처는 받지 않는다(MR-N3). 요청 본문 전체에 대해 서버가 다시 검사한다(프론트 검사만 믿지 않음).
- 조건 값은 범주형을 우선한다(지역 코드, 업력 구간 등).
- 조건과 대화는 **선택 동의**한 경우에만 저장한다. 판정 요청의 조건 값은 로그·트레이스에 본문으로 남기지 않는다.
- 공고의 공공기관 담당자 연락처는 공개 정보로 보고 그대로 보여 준다(팀 결정). 사용자 입력의 연락처와 구분한다.

---

## 3. 자원 모델

### 3.1 ApplicantProfile (지원사업 조건, SCR-01)

판정 입력. 그래프에 저장하지 않는다. 저장은 `P-01`로만, 조건 저장 동의 시. 화면(SCR-01 "내 기업 조건")의 입력 항목과 1:1로 맞췄다.

```json
{
  "kind": "SUPPORT",
  "region": { "id": "REGION:4120000000", "basis": "BUSINESS_LOCATION" },
  "industry_ids": ["INDUSTRY:C26"],
  "business_form": "CORPORATION",
  "company_size": "APPLICANT_TYPE:중소기업",
  "business_status": "OPERATING",
  "business_age": { "years": 2 },
  "founder_age": { "band": "AGE_30_39" },
  "employees": { "band": "EMP_10_49" },
  "revenue": { "band": "REV_1B_5B" },
  "certifications": { "known": true, "ids": ["CERTIFICATION:이노비즈"] },
  "tax_delinquent": "NO"
}
```

| 필드 | 화면 항목 | 형식 | 비고 |
|---|---|---|---|
| `region.id` | 소재지 | 개념 ID (`C-01`로 검색) | 사용자가 아는 가장 낮은 단위. 공고가 더 세밀하면 `UNKNOWN` |
| `region.basis` | (소재지 기준) | `BUSINESS_LOCATION` / `HEADQUARTERS` / `RESIDENCE` | 비우면 `BUSINESS_LOCATION`. 공고의 판단 기준과 다르면 `UNKNOWN` |
| `industry_ids` | 업종 | `INDUSTRY:{표준산업분류 코드}` | 업종 계층은 미구축(§11) |
| `business_form` | 기업 형태 | `CORPORATION`(법인) / `SOLE_PROPRIETOR`(개인사업자) / `NONE`(예비창업) | |
| `company_size` | 기업 형태 | `APPLICANT_TYPE:` 소기업·중기업·중소기업·중견기업·소상공인 | 계층 확장으로 소기업 → 중소기업 |
| `business_status` | | `PRE_FOUNDING` / `OPERATING` | 예비창업자 조건은 이 값으로 평가 |
| `business_age` | 업력 | `{years: n}` 또는 `{started_on: "YYYY-MM"}` 또는 `{band: 코드}` | `started_on`이면 공고 기준일마다 다시 계산 |
| `founder_age` | 대표자 연령 | `{value: n}` 또는 `{band: 코드}` | 만 나이 |
| `employees` | 직원 수 | `{band: 코드}` 또는 `{value: n}` | 상시근로자 |
| `revenue` | 매출 규모 | `{band: 코드}` 또는 `{value_krw: n}` | 직전 연도 기준 |
| `certifications` | 보유 인증 | `{known, ids}` | `known=false`면 인증 조건은 `UNKNOWN`. `known=true`에 `ids=[]`면 "없음" |
| `tax_delinquent` | 세금 체납 | `YES` / `NO` / `UNKNOWN` | 국세·지방세 체납 제외 요건 평가 |
| 빈 값 | | 필드 생략 | 그 값을 쓰는 조건은 `UNKNOWN`이 되고 되묻기 후보가 된다 |

**공고별 답변 (`notice_answers`)**

"동일 과제로 정부 지원을 받은 기업 제외"처럼 **공고나 사업에 따라 뜻이 달라지는 값**은 공통 프로필에 넣지 않는다. 어떤 사업이 "동일 과제"인지가 공고마다 달라서, 한 공고에서 받은 답을 다른 공고에 쓰면 틀린 판정이 된다.

```json
{ "notice_answers": { "KSTARTUP:179839": { "same_program_awarded": "NO" } } }
```

| 필드 | 값 | 규칙 |
|---|---|---|
| `same_program_awarded` | `YES` / `NO` / `UNKNOWN` | 그 공고의 동일 과제·중복 수혜 제외 요건 평가에만 쓴다 |

- 공고 ID를 키로 받고, **그 공고의 판정에만 적용**한다. 다른 공고에 자동으로 옮기지 않는다. 같은 사업의 다른 회차 공고(`related_group_id`)도 자동 적용하지 않고 다시 묻는다.
- 주로 되묻기(E-04)로 받는다. 답이 없으면 그 조건은 `UNKNOWN`이다.
- 판정 스냅샷(`evaluation_id`)에만 들어가고, 저장한 조건(`P-01`)에는 저장하지 않는다. 화면의 "이 조건 저장"에도 포함하지 않는다.
- 같은 규칙을 따를 값이 더 생기면(예: "본 사업 기참여 기업 제외") 이 목록에 추가한다.

**구간 코드 (화면 선택지와 같음)**

| 항목 | 코드 → 범위 |
|---|---|
| 직원 수 `EMP_*` | `EMP_0`=[0,0], `EMP_1_4`=[1,4], `EMP_5_9`=[5,9], `EMP_10_49`=[10,49], `EMP_50_99`=[50,99], `EMP_100_299`=[100,299], `EMP_300_PLUS`=[300,∞) |
| 매출 `REV_*` (원) | `REV_LT_100M`=[0,1억), `REV_100M_1B`=[1억,10억), `REV_1B_5B`=[10억,50억), `REV_5B_10B`=[50억,100억), `REV_10B_PLUS`=[100억,∞) |
| 대표자 연령 `AGE_*` | `AGE_LT_20`, `AGE_20_29`, `AGE_30_39`, `AGE_40_49`, `AGE_50_PLUS` (K-Startup의 39세 이하/40세 이상 경계와 맞춤) |
| 업력 `BAGE_*` | `BAGE_LT_1`, `BAGE_1_2`(1년 이상 2년 미만), `BAGE_2_3`, `BAGE_3_5`, `BAGE_5_7`, `BAGE_7_10`, `BAGE_10_PLUS` (K-Startup 옵션 경계와 맞춤) |

서버는 구간 코드를 범위 `[min, max]`로 바꿔 평가한다. 코드표는 `S-01 GET /api/meta`의 `bands`로 내려줘서 화면 선택지와 서버가 같은 표를 쓴다.

**구간 입력의 평가 규칙** (숫자 조건 `attribute OP t`)
- 범위의 모든 값이 조건을 만족하면 `SATISFIED`, 모든 값이 만족하지 않으면 `UNSATISFIED`, **경계 t가 범위 안에 걸치면 `UNKNOWN`**.
- 예: 직원 `EMP_10_49`
  - "10인 이상" → `SATISFIED`
  - "5인 이상 20인 미만" → `UNKNOWN`. 되묻기 후보가 되며, 되묻기는 정확한 값을 묻는다.
  - "300인 이상" → `UNSATISFIED`
- 정확한 값(`value`)이 오면 그 값으로 평가한다.

### 3.2 BidProfile (입찰 참가 조건, SCR-01-1)

```json
{
  "kind": "BID",
  "bid_kinds": ["GOODS", "SERVICE"],
  "region": { "id": "REGION:1120000000", "basis": "HEADQUARTERS", "branch_ids": [] },
  "licenses": ["LICENSE:0036"],
  "product_classes": ["G2B_PRODUCT:4321"],
  "direct_production": "YES",
  "company_size": "APPLICANT_TYPE:중소기업"
}
```

| 필드 | 화면 항목 | 형식 | 비고 |
|---|---|---|---|
| `bid_kinds` | 입찰 종류 | `GOODS`(물품) / `SERVICE`(용역) / `CONSTRUCTION`(공사), 여러 개 | **필터**로 쓴다(판정 조건 아님). 지금 데이터는 용역만 있음 |
| `region` | 소재지 | 개념 ID + 기준 | 나라장터 판단 기준이 `본사또는참여지사소재지`면 `branch_ids`까지 본다 |
| `licenses` | 보유 면허·업종 | `LICENSE:{나라장터 업종 코드}` | 면허 그룹이 둘 이상이면 AND/OR 검증 전이라 `UNKNOWN` |
| `product_classes` | 물품분류 | `G2B_PRODUCT:{물품분류번호}` | 물품 입찰의 분류 제한 평가. 물품분류 코드표는 미확보(§12) |
| `direct_production` | 직접생산 확인 | `YES` / `NO` / `UNKNOWN` | 직접생산 확인 요구 공고 평가 |
| `company_size` | 기업 구분 | `APPLICANT_TYPE:` 규모 개념 | 중소기업 제한 입찰 평가 |

### 3.3 NoticeSummary (목록 카드)

```json
{
  "notice_id": "BIZINFO:PBLN_000000000121785",
  "source_system": "BIZINFO",
  "type": "SUPPORT",
  "title": "[광주] 2026년 소규모 밀착 안전망 구축사업 참여기업 모집 공고",
  "organization": "전남광주통합특별시",
  "category": { "source_major": "경영", "source_medium": null },
  "period": { "start": "2026-11-20", "end": null, "deadline_at": null, "status_kind": "UNTIL_BUDGET_EXHAUSTED", "period_status": "OPEN_NO_DATE_DEADLINE" },
  "region_names": ["광주광역시"],
  "required_documents": ["신청서"],
  "detail_url": "https://www.bizinfo.go.kr/...",
  "fetched_at": "2026-11-24T09:16:01+09:00",
  "version": 1
}
```

입찰공고(`type=BID`)는 `bid` 블록을 더한다: `contract_method`, `award_method`, `demand_org`, `estimated_price`, `close_at`(일시), `open_at`, `license_raw`, `region_judgment_basis`, `requires_proposal`.

### 3.4 NoticeDetail (원문 보기)

`NoticeSummary` + 아래.

| 필드 | 설명 |
|---|---|
| `sections` | 원문 구역 목록: `{section, origin(API/ATTACHMENT/ATTACHMENT_OCR), text, source_span}` |
| `attachments` | `{file, format, status(OK/OCR_DONE/UNSUPPORTED…), pages, url}` |
| `contacts` | 공고의 담당 기관·연락처(공개 정보) |
| `supersedes` / `superseded_by` | 정정 공고 연결. 대체된 버전은 판정에서 제외 |
| `requirements_status` | `parsed` / `partial` / `unparsed` / `not_extracted` |

### 3.5 EligibilityResult (공고 1건 판정)

```json
{
  "notice_id": "BIZINFO:PBLN_000000000121785",
  "verdict": "ELIGIBLE",
  "summary": { "satisfied": 3, "unsatisfied": 0, "unknown": 0 },
  "decisive": [ { "cond_id": "...#R1#C1", "label": "광주광역시 소재", "result": "SATISFIED" } ],
  "unknown_items": [],
  "excluded_by": [],
  "tracks": null,
  "reason_codes": [],
  "evidence_source": "API+ATTACHMENT",
  "evaluated_at": "2026-11-25T14:02:11+09:00",
  "versions": { "rule": "0.1", "dictionary": "region-20261125" }
}
```

| 필드 | 설명 |
|---|---|
| `verdict` | 규칙 평가기 결과. 모델이 바꾸지 않는다 |
| `decisive` | 판정을 가른 조건(목록 카드의 "판정 이유") |
| `unknown_items` | 미확인 조건과 물어볼 값(`ask_field`). 되묻기 후보 |
| `excluded_by` | 제외 요건에 걸린 경우 그 요건 |
| `tracks` | 트랙이 있으면 트랙별 판정. 공고 판정은 트랙 합성(하나라도 ELIGIBLE이면 ELIGIBLE) |
| `evidence_source` | 근거 출처(`API` / `ATTACHMENT` / 둘 다). 출처별 확인 필요 비율 측정용 |

### 3.6 ConditionCheck (조건별 검증표 한 행, SCR-02-1)

```json
{
  "req_id": "BIZINFO:PBLN_000000000117956@v1#R1",
  "req_kind": "ELIGIBILITY",
  "logic": "OR",
  "exception_kind": "RELAXES_ELIGIBILITY",
  "cond_id": "BIZINFO:PBLN_000000000117956@v1#R1#C2",
  "attribute": "certification",
  "operator": "EXISTS",
  "required": { "concept_ids": ["CERTIFICATION:벤처기업", "CERTIFICATION:이노비즈", "CERTIFICATION:메인비즈", "CERTIFICATION:사회적기업"], "label": "벤처·이노비즈·메인비즈·사회적기업 중 하나" },
  "my_value": { "value": ["CERTIFICATION:이노비즈"], "source": "INPUT" },
  "result": "SATISFIED",
  "evidence": { "text": "※ 벤처기업, 이노비즈, 메인비즈, 사회적기업은 10인 미만이라도 참여 가능", "section": "eligibility_api", "span": [12, 48] },
  "ref_date_kind": null,
  "reason_codes": []
}
```

`my_value.source`는 화면의 값 출처 표시: `INPUT`(입력) / `DERIVED`(개념·정의로 도출, 예: 소기업 → 중소기업) / `MISSING`(미입력). `req_kind`가 `PREFERENCE`·`DOCUMENT`·`LIMIT`이면 판정에 쓰지 않고 별도 탭으로 보낸다.

### 3.7 ReasoningPath (추론 과정, SCR-02-2)

```json
{
  "notice_id": "BIZINFO:PBLN_000000000121785",
  "steps": [
    { "step": "INPUT", "items": [ { "field": "region_id", "value": "REGION:1227000000", "label": "전남광주통합특별시 남구" } ] },
    { "step": "CONCEPT", "paths": [ { "cond_id": "...#C1", "nodes": ["전남광주통합특별시 남구", "광주광역시(2026-07 이전)"], "rels": ["MEMBER_OF"], "hops": 1 } ] },
    { "step": "DEFINITION_LAW", "paths": [], "chain_status": "NOT_NEEDED" },
    { "step": "EVALUATE", "conditions": [ { "cond_id": "...#C1", "result": "SATISFIED" } ] },
    { "step": "COMBINE", "tree": { "logic": "AND", "result": "SATISFIED", "children": [ "..." ] } }
  ],
  "verdict": "ELIGIBLE",
  "graph": { "nodes": [ ], "edges": [ ] }
}
```

`DEFINITION_LAW` 단계는 정의 → 조문·별표 경로(`Concept -DEFINED_BY-> Definition -CITES_LAW-> LawArticle`)와 공고가 직접 인용한 조문을 준다. 끊기면 `chain_status=BROKEN`, 조건은 `UNKNOWN`, `reason_codes=["CHAIN_BROKEN"]`. `graph`는 화면 시각화용 노드·간선이다.

---

## 4. 공고 API

### N-01 `GET /api/notices`

| 쿼리 | 설명 |
|---|---|
| `type` | `SUPPORT`(기본) / `BID` |
| `q` | 공고명·기관 검색 |
| `status` | `open`(기본) / `closed` / `all`. `open`은 모집 중 + 날짜 없는 모집 중(기간 확인) |
| `source` | `BIZINFO`, `KSTARTUP`, `G2B` (여러 개 가능) |
| `region_id` | 지역 조건이 이 지역을 포함하는 공고(계층 확장 적용) |
| `sort` | `deadline`(기본, 마감 임박순) / `published` |
| `limit`, `cursor` | 페이지 |

응답 `data`: `{ "items": [NoticeSummary], "next_cursor": "...", "counts": { "open": 1452, "open_no_date": 915 }  // 값은 예시 }`. 판정은 하지 않는다(판정은 E-01).

### N-02 `GET /api/notices/{notice_id}`

`NoticeDetail`. 대체된 버전을 요청하면 최신 버전 ID를 `superseded_by`로 알려 준다. 원문 파싱 실패 시 `requirements_status=unparsed`와 원본 링크, `reason_codes=["REQ_UNPARSED"]`.

### N-03 `GET /api/notices/{notice_id}/spans?evaluation_id=...`

판정에 쓴 원문 문장의 위치: `{evaluation_id, spans: [{cond_id, result, section, start, end, text}]}`. 원문 하이라이트용. 조건 값을 쿼리에 넣지 않으려고 판정 결과 ID(`evaluation_id`)를 넘긴다. 응답에 받은 `evaluation_id`를 그대로 돌려줘서 화면이 다른 탭과 같은 판정인지 확인할 수 있다(§5.0).

### N-04 `GET /api/notices/{notice_id}/forms`

공고가 요구하는 문서와 공식 양식: `{required_documents: ["신청서","사업계획서"], forms: [{form_id, name, format, source(AUTO/USER_UPLOAD), fields_detected}], action: "APPLICATION" | "BUSINESS_PLAN" | "PROPOSAL" | "NONE" | "FORM_CHECK_NEEDED"}`. 화면의 신청 문서 버튼 규칙(화면설계서 §3.3)을 서버가 정한다. K-Startup은 자동 수집하지 않으므로 `FORM_CHECK_NEEDED`.

---

## 5. 판정 API

### 5.0 `evaluation_id` 규칙 (모든 탭이 같은 판정을 보게)

- `evaluation_id`는 **한 번 만든 판정 결과의 고정된 스냅샷**이다. 같은 ID의 결과는 바뀌지 않는다.
- 조건이 바뀌는 요청(E-01 새 검색, E-04 되묻기 답변, E-05 가정 값)은 **항상 새 `evaluation_id`를 발급**한다. 새 ID에는 `parent_evaluation_id`(이전 ID)와 `changed_fields`가 붙는다.
- 화면은 새 ID를 받으면 **현재 판정 ID를 바꾸고**, 검증표(E-02)·추론 과정(E-03)·원문 하이라이트(N-03)를 모두 새 ID로 다시 불러온다. 세 API는 응답에 요청받은 `evaluation_id`를 그대로 돌려주므로, 화면은 ID가 다른 응답을 버린다(이전 결과 혼동 방지).
- E-05(가정 값)로 만든 ID는 `hypothetical=true`다. 화면의 "현재 판정"으로 바꾸지 않고 비교 패널에만 쓴다. 신청 문서 생성(D-01)에는 쓸 수 없다(`409`).
- 이전 ID는 TTL(예: 30분, API-2) 동안 조회할 수 있고, 지나면 `410 Gone` + `EVALUATION_EXPIRED`.
- 조건 값은 이 캐시에만 두고 로그·트레이스에 남기지 않는다. 저장 동의와 무관하다.

### E-01 `POST /api/eligibility`

조건으로 맞는 공고를 찾는다. **LLM을 쓰지 않는다**(입력 검증 → 모집 중 필터 → 계층 확장 → 정의·법령 → 규칙 평가 → 3값 목록).

요청:
```json
{
  "type": "SUPPORT",
  "profile": { "kind": "SUPPORT", "region": { "id": "REGION:4111100000" }, "company_size": "APPLICANT_TYPE:소기업", "business_form": "CORPORATION", "business_status": "OPERATING", "business_age": { "years": 2 }, "employees": { "band": "EMP_5_9" }, "tax_delinquent": "NO" },
  "profile_id": null,
  "filters": { "status": "open", "source": ["BIZINFO", "KSTARTUP"], "q": null },
  "verdicts": ["ELIGIBLE", "NEEDS_CHECK"],
  "limit": 20, "cursor": null
}
```

`profile` 대신 저장한 `profile_id`를 줄 수 있다(둘 다 오면 `profile` 우선, 저장값은 바뀌지 않음). `type=BID`이면 `profile`은 `BidProfile`이고, `bid_kinds`(입찰 종류)는 후보 필터로 먼저 적용한다. 쿼리 `?type=bid`도 같은 뜻으로 받는다.

응답 `data`:
```json
{
  "evaluation_id": "ev_01J...",
  "items": [ { "notice": { "...NoticeSummary" }, "result": { "...EligibilityResult" } } ],
  "counts": { "ELIGIBLE": 41, "NEEDS_CHECK": 212, "NOT_ELIGIBLE": 1199 },
  "searched": { "notices": 1452, "sources": ["BIZINFO", "KSTARTUP"], "as_of": "2026-11-24T09:16:01+09:00" },
  "next_cursor": "..."
}
```

- 후보 0건이면 `outcome=held`, `reason_codes=["NO_MATCH"]`, `data.searched`(찾아본 범위)와 `data.relax_hints`(어느 조건을 풀면 후보가 생기는지)를 준다(EX-01).
- 기간이 지난 공고는 기본 제외, 날짜 없는 공고는 `period_status=OPEN_NO_DATE_DEADLINE`로 표시한다.
- `evaluation_id`의 규칙은 §5.0을 따른다.

### E-02 `GET /api/eligibility/{notice_id}?evaluation_id=...`

한 공고의 조건별 검증표: `{ result: EligibilityResult, checks: [ConditionCheck], by_kind: { ELIGIBILITY: n, EXCLUSION: n, PREFERENCE: n, DOCUMENT: n, LIMIT: n }, other_requirements: [ … 판정에 쓰지 않는 우대·서류·한도 … ] }`.

`evaluation_id`가 만료되면 `410 Gone` + `reason_codes=["EVALUATION_EXPIRED"]`로 알려 주고, 프론트는 E-01을 다시 부르거나 `POST`로 조건을 함께 보낸다(`POST /api/eligibility/{notice_id}`, 본문은 E-01의 `profile`).

### E-03 `GET /api/eligibility/{notice_id}/path?evaluation_id=...`

`ReasoningPath`. 같은 입력이면 같은 경로를 돌려준다(재현성). 경로 계산은 그래프 DB(Neo4j)에서 한다.

### E-04 `POST /api/eligibility/clarify`

되묻기 답변을 반영해 다시 판정한다. 최대 2회(서버가 `ask_count`로 센다).

요청: `{ "evaluation_id": "ev_A", "notice_id": "...", "answers": { "employees": { "value": 12 }, "tax_delinquent": "NO" } }`
응답:
```json
{
  "evaluation_id": "ev_B",
  "parent_evaluation_id": "ev_A",
  "changed_fields": ["employees", "tax_delinquent"],
  "before": { "...EligibilityResult (ev_A)" },
  "after": { "...EligibilityResult (ev_B)" },
  "next_questions": [ { "field": "certifications", "label": "보유한 인증", "input": "MULTI_SELECT", "choices": [ "..." ] } ],
  "ask_count": 1
}
```

`answers`의 값 형식은 §3.1·§3.2 필드와 같다(구간 코드 또는 정확한 값). 공고별 값(`same_program_awarded` 등)은 `answers.notice_answers`로 보내며, 요청의 `notice_id` 공고에만 적용된다(§3.1 공고별 답변). 구간 입력 때문에 `UNKNOWN`이 된 조건이면 `next_questions`의 `input`은 정확한 숫자(`NUMBER`)를 묻는다. 답변은 이번 판정에만 쓰고, 저장한 조건(`P-01`)을 바꾸지 않는다. 저장하려면 사용자가 따로 저장한다.

2회 뒤에도 부족하면 `NEEDS_CHECK` + `reason_codes=["INSUFFICIENT_PROFILE"]`(EX-02). `next_questions`는 판정을 바꾸는 값만, 한 번에 3개 이하.

### E-05 `POST /api/eligibility/what-if` (P1)

요청: `{ "evaluation_id": "ev_A", "notice_ids": ["..."], "changes": { "tax_delinquent": "NO", "certifications": { "known": true, "ids": ["CERTIFICATION:벤처기업"] } } }` → `{ "evaluation_id": "ev_W", "hypothetical": true, "parent_evaluation_id": "ev_A", "items": [ { notice_id, before, after, changed_conditions } ] }`. 가정값은 저장하지 않고, 현재 판정을 바꾸지 않는다(§5.0).

---

## 6. 챗봇 API

### H-01 `POST /api/chat` (SSE)

요청:
```json
{ "conversation_id": null, "message": "수원 장안구 소기업인데 지금 신청할 수 있는 공고 있어?", "profile_id": null, "profile": null, "context_notice_id": null }
```

응답: `text/event-stream`. 이벤트 순서:

| 이벤트 | 데이터 | 설명 |
|---|---|---|
| `meta` | `{conversation_id, message_id, route}` | `route`: `ELIGIBILITY` / `SEARCH` / `EVIDENCE` / `APPLICATION` (Router 분기) |
| `ask` | `{questions:[…], ask_count}` | 되묻기. 사용자가 답하면 같은 대화로 다시 `POST` |
| `results` | `{items:[{notice, result}], evaluation_id}` | 규칙 평가기 판정(버튼 E-01과 같은 파이프라인) |
| `token` | `{text}` | 설명 문장 스트리밍(모델). 판정을 바꾸지 못함 |
| `evidence` | `{citations:[{notice_id, section, span, text}]}` | 답변에 쓴 원문 |
| `notice` | `{reason_code, message}` | 고정 템플릿 안내(차단·보류·장애) |
| `done` | `{outcome, display_status, reason_codes, usage, timing, trace_id}` | 끝. `usage`·`timing`은 §10.1 |
| `error` | `{reason_code}` | 스트림 중 장애. 이미 보낸 `results`는 유효(규칙 판정 유지) |

- 입력 가드(`PII_BLOCKED`, `INJECTION_BLOCKED`, `OUT_OF_SCOPE`, `LEGAL_ADVICE`)에 걸리면 `notice` + `done(outcome=refused)`만 보내고 끝낸다.
- 출력 가드(`OUTPUT_BLOCKED`)에 걸리면 1회 재생성, 다시 걸리면 안전 템플릿으로 바꾼다. 차단된 초안은 보내지 않는다. 그래서 `token`은 출력 가드를 통과한 문장 단위로 보낸다(완전한 글자 단위 스트리밍과 맞바꿈, §10).
- 모델 장애 시 `results`와 `notice(SERVICE_DEGRADED)`만 보내는 규칙 판정만 모드.

### H-02 대화 이력 (P1)

`GET /api/conversations` → `[{conversation_id, title, updated_at, message_count}]`, `GET /api/conversations/{id}` → 메시지 목록, `DELETE /api/conversations/{id}` → 204. 대화 저장 동의(`store_conversations`)를 한 사용자만 저장된다. 동의하지 않았으면 대화는 세션 동안만 유지되고 목록은 항상 비어 있다.

---

## 7. 내 조건·동의 API

### P-01 `/api/profiles` (P1)

| 메서드·경로 | 요청 | 응답 |
|---|---|---|
| `GET /api/profiles?kind=SUPPORT` | | `[{profile_id, name, kind, summary, is_default, updated_at}]` |
| `POST /api/profiles` | `{name, profile, is_default}` | 201 `{profile_id}`. 조건 저장 동의(`store_conditions`)가 없으면 `403` + `CONSENT_REQUIRED` |
| `PATCH /api/profiles/{id}` | 바꿀 필드 | 200 |
| `DELETE /api/profiles/{id}` | | 204. 기본 조건을 지워도 다른 조건을 자동으로 기본 지정하지 않음 |

저장은 Supabase `user_conditions`(RLS로 본인만). 사업자번호·연락처 같은 식별 정보 필드는 스키마에 없다.

### A-02 `/api/consents`

```json
{ "required": { "terms": true, "privacy": true },
  "optional": { "store_conditions": false, "store_conversations": false, "store_documents": false },
  "updated_at": "2026-11-25T14:00:00+09:00" }
```

선택 동의는 **저장 대상별로 3개**로 나눈다. 저장하는 데이터의 성격(조건 값, 대화 문장, 회사 자료가 들어간 초안)과 철회 시 지울 범위가 달라서다.

| 선택 동의 | 저장하는 것 | 동의하지 않으면 | 화면 |
|---|---|---|---|
| `store_conditions` 조건 저장 | 이름 붙인 기업 조건(`P-01`) | 조건을 매번 입력. 판정은 정상 | SCR-00-1, SCR-01 "이 조건 저장", SCR-05 |
| `store_conversations` 대화 저장 | 챗봇 대화(`H-02`) | 대화는 세션 동안만 유지 | SCR-00-1, SCR-04, SCR-05 |
| `store_documents` 신청 문서 보관 | 신청 문서 초안과 올린 양식 파일(`D-*`) | 초안·양식은 **임시 문서**로 만들어 24시간 뒤 자동 삭제. 목록(SCR-03-1)에 보이지 않음 | SCR-00-1, SCR-03, SCR-03-1 |

`POST`(첫 동의), `PATCH`(변경). 선택 동의를 철회하면 서버가 그 항목의 저장 데이터를 즉시 삭제하고 `{deleted: {profiles: 2, conversations: 5, documents: 1, form_files: 1}}`를 돌려준다. 화면설계서 SCR-00-1·SCR-05·SCR-03-1도 같은 세 항목으로 반영했다(화면설계서 v3.5 변경 이력).

---

## 8. 신청 문서 API (P1)

### 8.1 순서: 작업 문서 먼저, 생성은 나중

공식 양식을 먼저 올리는 흐름(SCR-03-2)과 자동 양식으로 바로 쓰는 흐름(SCR-03)을 같은 순서로 맞춘다. **초안 내용을 만드는 일(생성)을 문서 만들기와 분리**한다.

```
① POST /api/applications                      빈 작업 문서 생성 (자격 게이트, 내용 없음)  → application_id
② (양식 직접 올리기) POST /api/applications/{id}/forms        → form_id, 인식 항목
   (양식 확인)       GET·PATCH /api/applications/{id}/forms/{form_id}[/fields]
   (자동 양식)       ①에서 form_source=AUTO면 공고 첨부 양식을 서버가 붙임
   (양식 없음)       form_source=DEFAULT_OUTLINE → 기본 목차
③ POST /api/applications/{id}/generate        선택한 양식 항목 순서대로 초안 생성
④ PATCH, regenerate, 제출 전 점검             편집
```

| 상태 `status` | 뜻 | 다음 |
|---|---|---|
| `FORM_PENDING` | 작업 문서만 있음. 양식 미정 | 양식 올리기 / 자동 양식 / 기본 목차 선택 |
| `FORM_READY` | 양식 항목 확인 완료 | `generate` |
| `DRAFTING` | 생성 중 | 완료 대기(진행 조회 `GET`) |
| `DRAFT` | 초안 있음 | 편집·점검 |

### 8.2 API

| 메서드·경로 | 요청 | 응답·규칙 |
|---|---|---|
| `POST /api/applications` | `{notice_id, document_type, evaluation_id, form_source: "AUTO" \| "UPLOAD" \| "DEFAULT_OUTLINE"}` | 201 `{application_id, status, temporary, expires_at}`. **자격 게이트:** `evaluation_id`의 판정이 `NOT_ELIGIBLE`이거나 마감이면 `409 NOT_APPLICABLE`, `NEEDS_CHECK`면 `warnings`를 붙여 진행. 가정 값 판정(`hypothetical`)은 `409`. `store_documents` 동의가 없으면 `temporary=true`(24시간) |
| `POST /api/applications/{id}/forms` | `multipart/form-data` (HWP·HWPX·PDF·DOCX) | 201 `{form_id, fields_detected:[{field_id, label, order, input_kind}]}`. 형식·크기·악성 파일 검사, 본인 전용 비공개 저장. 파일 안의 지시문은 실행하지 않는다. 파싱 실패 시 `fields_detected=[]` + 기본 목차 안내 |
| `GET /api/applications/{id}/forms/{form_id}` · `PATCH /api/applications/{id}/forms/{form_id}/fields` · `DELETE /api/applications/{id}/forms/{form_id}` | 항목 이름·순서 수정 | 확인이 끝나면 `status=FORM_READY` |
| `POST /api/applications/{id}/generate` | `{profile_id 또는 profile, company_facts}` | 202 `{status: "DRAFTING"}` → 끝나면 `DRAFT`. 양식 항목 순서대로 생성. 입력에 없는 수치·실적은 `[입력 필요]`로 남긴다. `FORM_PENDING`이면 `409` |
| `GET /api/applications` | | 본인 문서 목록 `{application_id, notice_id, document_type, status, blanks, deadline_at, form_changed}`. 임시 문서는 나오지 않음 |
| `GET /api/applications/{id}` | | 양식 항목 순서대로 `fields:[{field_id, label, status(AUTO/DONE/BLANK/MANUAL), text, sources:[…]}]`, `checks`(빈칸·직접 작성·근거 없는 수치·확정 표현) |
| `PATCH /api/applications/{id}` | `{fields:[{field_id, text}]}` | 200 |
| `DELETE /api/applications/{id}` | | 204 (올린 양식 파일도 삭제) |
| `POST /api/applications/{id}/fields/{field_id}/regenerate` | `{instruction}` | 새 초안 문장 |

회사명·대표자·사업자번호·연락처·서명 항목은 `status=MANUAL`로 두고 저장하지 않는다. 시스템이 대신 제출하지 않는다. 공고나 양식이 정정되면 `form_changed=true`로 다시 확인하게 한다.

---

## 9. 운영자 API (관리자만)

모든 운영자 API는 서버에서 역할을 확인하고, 일반 사용자는 `403 ROLE_DENIED`. 변경 작업은 감사 로그에 남는다.

### M-01 `GET /api/admin/status` (P0)

```json
{
  "sources": [
    { "source": "BIZINFO", "last_success_at": "2026-11-24T09:16:01+09:00", "last_run": { "run_id": "...", "status": "SUCCESS", "fetched": 1294, "new": 12, "changed": 3, "failed": 0 }, "stale": false },
    { "source": "KSTARTUP", "...": "..." },
    { "source": "G2B", "...": "..." }
  ],
  "queues": { "review_pending": 37, "reprocess_pending": 2, "unparsed": 118 },
  "period_status": { "open_with_deadline": 916, "open_no_date": 915, "closed": 3664 },
  "observability": { "langfuse_url": "...", "gpu_running": false }
}
```

### M-02 공고 업데이트 (P1)

`POST /api/admin/updates` `{sources: ["BIZINFO","KSTARTUP","G2B"]}` → `202 {run_id}`. 실행 중이면 `409 CONFLICT`(동시 실행 방지). `GET /api/admin/updates/{run_id}` → `{status, steps:[{name, status, count}], summary:{new, changed, duplicate_skipped, failed}, by_source:[…]}`. 중복은 공고 ID + 내용 해시로 판별하고, 바뀐 공고는 새 버전으로 보존한다.

### M-03 `POST /api/admin/reprocess` (P0)

`{run_id 또는 notice_ids, stage: "FETCH" | "EXTRACT" | "NORMALIZE"}` → `202 {job_id}`. 실패 건만 다시 처리한다.

### M-04 요건 정규화 검수 (P1)

`GET /api/admin/review?status=pending&sort=confidence` 목록, `GET /api/admin/review/{notice_id}` → `{notice, source_sections, requirement_tree, candidates_by_source}`, `PATCH /api/admin/review/{notice_id}` `{requirement_tree, ref_date_kind, tracks}`, `POST /api/admin/review/{notice_id}/approve` `{decision: "APPROVE" | "REJECT", comment}`. 승인된 요건만 그래프에 적재한다. 조건 트리 형식은 온톨로지 보완안 O-05·O-11·O-16을 따른다(제외 요건 내부 논리 보존, 값 스키마, `exception_kind`).

### M-05 입수 시점 검증 (P1)

`GET /api/admin/ingest/{notice_id}/report` → `{previous_version, current_version, requirement_diff:[…], impact:{changed_verdicts, by_profile:[…]}, definition_check:[…]}`. 영향 판정은 실제 사용자 조건이 아니라 **평가용 가상 프로필**로 계산한다. `POST /api/admin/ingest/{notice_id}/approve` 시 `SUPERSEDES` 연결.

### M-06 감사 로그·허용 목록 (P1)

`GET /api/admin/audit-logs?actor=&action=&from=&to=` → `[{at, actor, action, target, result}]`(수정·삭제 API 없음, 사용자 조건 내용은 기록하지 않음). `GET` `POST` `DELETE /api/admin/allowlist` → 관리자 이메일 허용 목록. 본인 권한은 바꿀 수 없다(`409`).

---

## 10. 개념·메타 API

### C-01 `GET /api/concepts?scheme=REGION&q=장안`

입력칸 자동완성. 지역은 별칭 사전(`data/사전/지역_별칭사전.csv`)으로 찾는다.

```json
{ "items": [ { "concept_id": "REGION:4111100000", "label": "경기도 수원시 장안구", "level": "GU", "parent_id": "REGION:4111000000", "matched_alias": "장안구" } ] }
```

모호한 이름(`서구` 등)은 후보를 모두 돌려주고 `ambiguous: true`를 붙인다. `scheme`: `REGION`, `APPLICANT_TYPE`, `CERTIFICATION`, `LICENSE`, `INDUSTRY`.

### S-01 `GET /api/meta` (공개)

`{data_as_of, stale, versions, disclaimer, sources:[{source, terms_url}], bands:{EMP:[…], REV:[…], AGE:[…], BAGE:[…]}}`. 로그인 전 화면(SCR-00)의 참고용 고지, 모든 화면의 수집 시각 배지, 입력칸의 구간 선택지(§3.1)에 쓴다. 화면과 서버가 같은 구간 표를 쓰게 하려고 선택지를 하드코딩하지 않는다.

### 10.1 관측·평가 (토큰 사용량, 속도, RAGAS)

평가 자체는 API 밖(평가 스크립트·CI)에서 하고, API는 **측정에 필요한 값을 남기고 꺼내 주는 일**만 한다.

| 평가 | 측정 위치 | API가 하는 일 |
|---|---|---|
| 토큰 사용량·비용 | Langfuse 트레이스(NFR-N06) | 모든 응답 `meta.trace_id`, 챗봇 `done.usage` |
| 속도 | Langfuse + 서버 측정 | 챗봇 `done.timing`, 판정 API는 트레이스에 단계별 시간 |
| RAGAS (충실도, 답변 관련성, 문맥 정밀도·재현율) | 평가 스크립트(평가셋 일괄 실행) | 관리자 평가 모드에서 검색 문맥과 답변을 함께 반환 |
| 판정 정확도(골드셋 일치) | 평가 스크립트 | 판정 API 결과를 그대로 비교 |
| 결과 조회 | 운영 현황 화면 | `O-01`, `O-02` |

**챗봇 `done` 이벤트의 측정 값**

```json
{ "usage": { "model": "qwen-qlora-awq", "input_tokens": 1830, "output_tokens": 412, "llm_calls": 2 },
  "timing": { "total_ms": 4210, "first_token_ms": 980, "stages_ms": { "guard_in": 12, "search": 140, "evaluate": 35, "generate": 3810, "guard_out": 25 } },
  "trace_id": "lf_8c2..." }
```

판정 API(E-01~E-05)는 LLM을 쓰지 않으므로 토큰은 0이고, 단계별 시간만 트레이스에 남긴다.

**평가 모드 (관리자만):** `POST /api/chat`에 `"eval": true`를 주면 `done` 앞에 `eval` 이벤트로 `{question, contexts:[{chunk_id, text}], answer, results}`를 보낸다. RAGAS 계산에 필요한 질문·검색 문맥·답변 묶음이다. 일반 사용자 요청에서는 무시한다. 평가 질문에는 실제 사용자 조건을 쓰지 않고 가상 프로필만 쓴다.

**O-01 `GET /api/admin/metrics?from=&to=&group=day`:** `{items:[{date, requests, llm_calls, input_tokens, output_tokens, cost_estimate, latency_ms:{p50, p95}, first_token_ms:{p50, p95}, reason_codes:{…}}]}`. Langfuse 집계를 옮겨 온다.

**O-02 `GET /api/admin/evals`, `GET /api/admin/evals/{run_id}`:** `eval_runs`에 저장된 결과. `{run_id, at, dataset, model, versions, metrics:{faithfulness, answer_relevancy, context_precision, context_recall, verdict_accuracy, latency_p95_ms, tokens_per_answer}, cases_url}`. **평가 실행은 API로 열지 않는다**(평가 스크립트·CI가 실행하고 결과만 저장). 화면에서 돌리면 GPU 비용이 예상 밖으로 나갈 수 있어서다.

RAGAS의 점수 계산도 판정용 LLM을 부른다. 외부 API를 쓸지, 우리 모델로 할지는 데이터 정책 결정이다(API-10).

---

## 11. 지금 데이터로 구현할 수 있는 범위

| API | 지금 가능한 것 | 아직 없는 것 |
|---|---|---|
| N-01, N-02 | 정리 층·공통 v1 5,116건 + 나라장터 4,845건의 목록·상세·원문 구역·첨부 상태 | 버전 이력(`SUPERSEDES`)은 재수집 후 |
| C-01 | 지역 코드표 318행·별칭 639개, 신청자 유형 용어 사전 | 면허 코드표, 업종 계층 |
| E-01~E-03 | 구조화 필드 조건(K-Startup 업력·연령·지역·신청 대상, 기업마당 소관 지역, 나라장터 면허·지역)으로 판정, 지역 계층·묶음 경로 | **본문·첨부 요건의 조건 트리**(정규화 검수 전), 정의 → 법령 연결(법령 데이터는 있음, 조문 ID 연결 전). 그전에는 본문 요건이 있는 공고 대부분이 `NEEDS_CHECK` + `REQ_UNPARSED` |
| H-01 | 판정·검색 경로 | 모델 서빙(RunPod), 가드레일 |
| D-* | 공고별 요구 문서 추정(첨부 파일명·낙찰방법) | 양식 항목 인식, 초안 생성 |
| M-01, M-02 | 수집기(나라장터 `tools/g2b`, 기업마당·K-Startup 수집 스크립트)와 실행 결과 | 실행 이력 테이블(`ingest_runs`) |

그래프 vs SQL 비교 실험(`experiments/graph_vs_sql/`)에서 같은 지식을 넣으면 두 방식의 판정이 같았다. 그래서 E-01의 후보 필터는 SQL(Supabase)로, E-03의 근거 경로와 정의 → 법령은 그래프(Neo4j)로 나누는 구성을 제안한다(§12).

---

## 12. 팀 결정이 필요한 항목

| # | 결정 | 선택지 | 제안 |
|---|---|---|---|
| API-1 | 버전 경로 | `/api` / `/api/v1` | `/api/v1` (스키마 변경에 대비) |
| API-2 | 판정 결과 보관 | 매번 재계산 / `evaluation_id` 단기 캐시 | 단기 캐시(예: 30분). 조건 값은 캐시에만, 로그에 남기지 않음 |
| API-3 | SSE 출력 단위 | 글자 단위 / 문장 단위(출력 가드 후) | 문장 단위. 차단된 문장이 화면에 나갔다가 지워지는 일을 막음 |
| API-4 | 판정 저장소 분담 | 전부 Neo4j / 후보 필터는 Supabase, 경로는 Neo4j | 분담(비교 실험 근거) |
| API-5 | 면허 코드표 | 나라장터 업종 코드 그대로 / 별도 개념 사전 | 업종 코드 그대로(`LICENSE:{코드}`) + 이름 사전 |
| API-6 | 업력 입력 | 연수 / 창업 연월 | 창업 연월(기준일마다 다시 계산). 연수 입력도 허용 |
| API-7 | 공통 v1 스키마 연락처 | 마스킹 유지 / 공공기관 연락처 공개 | 팀 결정(공공기관 담당자 연락처는 가리지 않음)에 맞춰 v1 정규화 수정 필요 |
| API-8 | 운영자 공고 수동 업로드 | 없음(화면설계서 비고) / P2 | 없음 |
| API-9 | 구간 코드 경계 | §3.1 제안 / 다른 구간 | 화면 선택지와 같게 확정 후 `S-01`로 배포 |
| API-10 | RAGAS 판정 모델 | 외부 API / 자체 Qwen | 공개 공고 문장과 가상 프로필만 쓰는 조건에서 팀 결정 |
| API-11 | 물품분류·면허 코드표 | 나라장터 코드 그대로 / 별도 사전 | 코드 그대로 + 이름 사전(지금 데이터는 용역만) |

## 13. 변경 이력

| 일자 | 버전 | 내용 |
|---|---|---|
| 2026-11-25 | v0.1 | 화면설계서 v3.5의 API 연계 예시를 기준으로 초안 작성. 응답 틀·사유 코드·자원 모델, 엔드포인트 26묶음(화면설계서 예시 전부 포함), `C-01`·`S-01` 추가 |
| 2026-11-25 | v0.1.1 | 검토 반영: ① 입력 형식 확정(구간 코드와 경계 걸침 시 UNKNOWN, 세금 체납·동일 과제 수혜, 입찰 종류·물품분류·직접생산) ② 신청 문서 순서(작업 문서 → 양식 → 생성, `generate` 추가) ③ `evaluation_id` 스냅샷 규칙(재판정은 새 ID, 모든 탭이 같은 ID 사용) ④ 선택 동의 3개(조건·대화·신청 문서) ⑤ 판정 배지와 상태 배지 분리(`display_status`: 입력 처리 불가·접근 권한 없음), 관측·평가 절(§10.1, `O-01`·`O-02`) 추가 |
| 2026-11-25 | v0.1.2 | 재검토 반영: 동일 과제 수혜를 공통 프로필에서 빼고 공고별 답변(`notice_answers`)으로 분리, 다른 공고에 자동 적용 금지. 동의 3항목은 화면설계서 반영 완료로 정리 |
