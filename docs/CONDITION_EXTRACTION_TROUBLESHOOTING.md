# 조건 추출 파이프라인 Troubleshooting

작성 기준일: 2026-11-27. 이 문서는 저장소의 P4 원본 응답, 요청 장부, runner/policy/bridge 코드를 대조한 진단 메모다. 기존 산출물은 변경하지 않았다.

## 1. 진단 우선순위

1. 실행 ID와 artifact path가 맞는지 확인한다.
2. 해당 실행의 manifest와 request ledger를 읽기 전용으로 대조한다.
3. `responses.jsonl`의 raw 응답을 JSON 파싱·hash 검증하고 notice별 산출물과 연결한다.
4. provider/intermediate schema 오류, conversion/validation 오류, technical Gate를 서로 다른 단계로 확인한다.
5. 어떤 상태도 성공으로 강제하거나 원본 응답을 직접 편집해 해결하지 않는다.

P4 root: `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3d5a_p4/`
Runner: `tools/run_condition_llm_p4_pilot.py`
Policy: `tools/condition_llm_next_policy.py`
Legacy bridge/validator: `tools/extract_condition_candidates_llm.py`

## 2. 요청 장부 및 응답 상태

2026-11-27 진단 시점 P4 `request_ledger.json`과 manifest 값:

| 항목 | 값 |
|---|---:|
| 별도 승인 상한 | 10 |
| 누적 used / remaining | 3 / 7 |
| reserved | 0 |
| succeeded / failed | 2 / 1 |
| API 호출 기록 | 3 |
| HTTP 200 응답 저장 | 3 |
| 기술 Gate | pass 2 / blocked 1 |
| 미실행 | 7 |

요청 ordinal 1=`BIZINFO:PBLN_000000000117168`, 2=`BIZINFO:PBLN_000000000118182`, 3=`BIZINFO:PBLN_000000000119490`. 모두 응답은 stop으로 끝났고 raw response hash는 manifest/ledger와 `responses.jsonl`에서 비교한다. 3번은 API 연결 실패가 아니다. 응답 및 JSON parse 이후 근거 고유성 검사에서 막혔다.

남은 고정 ID는 `BIZINFO:PBLN_000000000126490`, `BIZINFO:PBLN_000000000128028`, `KSTARTUP:176001`, `KSTARTUP:176813`, `KSTARTUP:177447`, `KSTARTUP:178507`, `KSTARTUP:179386`이다. `request_ledger.jsonl`도 사람이 읽을 수 있는 기록이므로 함께 보존한다.

부모 P12 장부는 별도 경로에서 13/13, remaining 0이며 SHA-256 `693d21e334481910e7c9d9f27d8fba4caf0c255ce028e2bfe3e5f0c726a73c3a`로 확인된 기록이 있다. P12 장부를 P4 장부에 복사하거나 P4 예산을 그 값으로 대체하지 않는다.

## 3. 117168·118182: SOURCE_FIELD_MISMATCH

### 재현된 처리 흐름

- P4 provider와 내부 intermediate schema 검증은 성공했고 P4 표준 후보는 각각 3개와 10개였다. 모델 출력 source_field 예시는 `소상공인`, `주소지`, `사업자등록증명원 소재지`, `BUSINESS_LOCATION`, `BUSINESS_TYPE` 등이다.
- trusted extraction input에는 해당 본문 evidence의 provenance path `condition_texts.eligibility.text`가 있다.
- `tools/extract_condition_candidates_llm.py:33`의 legacy `SOURCE_FIELD`는 `condition_texts.eligibility.text`로 고정이다. `_make_candidate` (`:765` 부근)는 불일치하면 값·근거 후속 검사를 하기 전에 `SOURCE_FIELD_MISMATCH`로 반환한다.
- P4 prompt의 source_field 설명은 모델이 provenance 위치 대신 속성 표현/라벨을 출력하는 것을 막지 못한다. 이는 P4 출력 계약과 기존 bridge의 인터페이스 불일치다. 허용 속성 검사를 무조건 통과시키는 문제와 다르다.
- 이 상태에서 review queue에는 원자 proposal 3+10개와 공고별 `INCOMPLETE_LOGIC_DUE_TO_HELD_CONDITIONS` 논리 상태 기록이 들어가 각각 4/11행이다. 총 15행을 모두 LLM unresolved proposal로 세면 안 된다.

### 오프라인 반사실 검사

원본 응답에 손대지 않고 메모리에서만 source_field를 입력의 trusted path로 설정한 뒤 기존 `validate_and_convert(..., apply_n1=False)`를 수행했다. 결과는 117168 3개, 118182 10개 후보 생성이며 기존 값/근거/연산자/날짜/스키마 검증을 적용한 결과다. 어떠한 출력 파일도 저장/수정하지 않았다. 이 검사는 모델의 제안이 정답이라는 뜻이 아니며, P12 후보를 답으로 사용한 것도 아니다.

P4 117168에는 소상공인, 대구시 신청자 주소, 대구시 사업장 위치와 고정일 temporal 정보가 포함된다. P12에서는 네 후보(주소/사업장 및 유지기간 분리)가 통과했으나 P4는 두 지역 조건에 temporal 의미를 결합해 표현한다. P12가 정답이라고 단정하지 않는다. P4 118182는 도내 위치, 영리기업, 사회적기업/협동조합 등 사업 조직 형태 9개 계열을 제안했으며, 마지막 8개는 P12에서 APPLICANT_TYPE으로 표현된 항목이 P4에서는 BUSINESS_TYPE으로 표현된 차이가 있다. 이 의미를 자동으로 교환하지 않는다.

### 최소 안전 수정 방향

P4 adapter가 원본의 추출 필드와 provenance를 분리한다. 각 proposal의 source path는 모델 문자열을 신뢰하지 말고 notice의 validated input evidence에서 부여한다(입력에서 유일하게 결정되지 않으면 보류). raw response는 그대로 두고 새 version/fingerprint/output lineage에서 전체 기존 validator를 다시 통과시킨다. 근거·field/category 의미·operator/value/unit·temporal·논리 및 schema 검증을 생략하지 않는다.

## 4. 119490: UNRESOLVED_EVIDENCE_NOT_UNIQUE

### 발생 단계와 직접 원인

119490은 HTTP 200, `finish_reason=stop`, JSON parse 성공, provider/internal schema 오류 0건이다. 총 4개 표준 조건과 3개 unresolved 조건이 응답에 있다. 차단은 P4 policy의 unresolved quote 처리 단계인 `tools/condition_llm_next_policy.py:187`에서 `source['raw_text'].count(q) != 1`이면 `ValueError('UNRESOLVED_EVIDENCE_NOT_UNIQUE')`를 던지는 검사다. 기존 legacy converter로 전달되기 전에 발생했다. 후보 속성 validation 또는 API 연결 실패가 아니다.

입력 원문에는 지역 분기 두 곳에 `5인 이상 우선지원대상기업에서`가 반복되고, 채용 문구 `청년을 정규직으로 채용 후`도 반복된다. 따라서 exact quote를 보존하더라도 특정 문맥 위치에 한 번만 붙일 수 없는 unresolved 후보가 있다. ordinal 3의 세 unresolved 중 해당 repeated quote를 포함하는 두 항목에서 모호성이 확인됐다. 가능한 span과 문맥을 원문 및 `extraction_inputs.jsonl`로 다시 확인한다. 실제 공고 전체 근거를 읽지 않은 채 첫 span으로 결론 내리면 안 된다.

표준 후보 4개에는 metro/non-metro `BUSINESS_LOCATION` IN/NOT_IN과 두 개의 `EMPLOYEE_COUNT >= 5 PERSON` 제안이 있다. 같은 직원 수 문구가 수도권/비수도권 각각에 반복되므로 이 표준 후보도 source_field를 고친 후 위치 ambiguity 검증에서 hold될 수 있다. 즉 unresolved만 고치는 것으로 충분하지 않다. 표준/미해결 후보 양쪽에서 동일한 근거 위치 ambiguity 정책이 필요하다.

원본 논리는 metropolitan AND group이 condition refs 0,1 및 unresolved refs 0,1을 갖고, nonmetropolitan AND group은 refs 2,3 및 unresolved refs 0,2를 갖는다. 두 branch는 OR root `g_location_branches`로 연결된다. exception 또는 별도 unresolved_relations는 없다. 원본 3개 unresolved 후보와 그룹 참조를 보존해야 한다.

### 안전한 처리 제안

- 모든 가능한 span(시작·끝 인덱스와 주변 문맥)을 계산해 provenance에 기록한다.
- span이 0개면 `EVIDENCE_NOT_FOUND`, 2개 이상이면 `EVIDENCE_LOCATION_AMBIGUOUS` 등 명시적 검수 상태를 유지한다.
- 원본 quote, proposal index, 그룹·예외 관계, 미해결 상태, 원문 근거는 보존한다.
- 위치 모호성이 공고 전체 실행을 중단시키지 않도록 오류/검수 결과를 후보 단위로 표현하되, 근거 검사를 제거하지 않으며 후보를 검증 성공으로 승격하지 않는다.
- first match를 고르지 않는다. 변경은 policy 버전 및 execution fingerprint를 분리하고 확보한 raw 응답을 오프라인 재생한다.

## 5. 재개 로직 위험

P4 runner의 `--run-remaining` 선택 지점은 `tools/run_condition_llm_p4_pilot.py:653` 부근이며 현재 `selected = ids[1:]`이다. 이 로직은 고정 순서의 첫 notice 하나만 건너뛰고 나머지 아홉을 다시 선택한다. 이미 ordinal 2, 3을 요청한 상태라 장부의 duplicate notice/ordinal claim 방지에 의해 차단될 수 있다. 그러므로 현재 상태에서 `--run-remaining --authorize-api` 실행은 금지한다.

후속 수정은 장부의 응답 확보/요청 시도와 원본 응답 artifact를 합쳐서 실제 미실행 ID만 deterministic하게 만든다. 이미 응답이 있는 ID는 성공 여부와 무관하게 재호출하지 않는다. 실패 요청을 예산에서 되돌리지 않는다. 번호 4–10 또는 ledger가 제공하는 예약 ordinal만 전달한다. 동시 실행은 금지하고 기존 P4 장부 및 fingerprint를 그대로 사용하지 말고 파생 run ID/fingerprint에서 offline claim 검증을 한다.

## 6. 평가 및 상태 해석

- 117168/118182의 `TECHNICAL_PASS`는 처리 경로·응답/Gate 상태이지 후보 품질이 입증됐다는 뜻이 아니다. 현재 저장 결과는 두 notice 모두 최종 유효 후보 0이며 검수 queue가 존재한다.
- 119490은 응답 수신은 성공했으나 후보 단계 근거 유일성 처리에서 blocked다. HTTP response 성공과 기술 Gate 성공은 서로 다른 통계다.
- 전체 P4 evaluator가 `P4_TEN_NOTICE_EVALUATION_ELIGIBILITY_REQUIRED`로 차단되는 것은 10개 대상이 준비되지 않아 예상된 동작이다. Gate를 강제로 PASS하거나 평가 대상을 줄이지 않는다.
- P4 결과를 P12의 10건 평가 결과와 혼합하지 않는다.
- 후보를 재처리할 때 기존 strict evaluator, 기존 v1.1 schema, 근거/span 및 논리 참조 검사, N1 비교 경로를 유지한다.

## 7. 후속 검증 명령과 실행 금지 명령

API를 호출하지 않는 현재 상태 확인:

```powershell
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --preflight
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --offline-self-test
Get-Content -Raw -Encoding UTF8 data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3d5a_p4/request_ledger.json
```

현재 runner의 remaining은 실제 요청 경로다. 다음 명령은 source_field/근거 ambiguity/재개 ID 로직이 새 파생 계보에서 수정·오프라인 검증되기 전 실행하지 않는다.

```powershell
# 실행 금지 상태: 실 API 요청을 보냄
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --run-remaining --authorize-api
```

실행 환경의 `.env` 값을 출력하거나 커밋하지 않는다. 이 troubleshooting 문서 작성 과정에서는 API를 호출하지 않았다.
