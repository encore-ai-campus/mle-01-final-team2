# 2-1단계 조건 추출 입력 최종 검증

작성일: 2026-11-25. 입력 생성 도구 `tools/prepare_condition_inputs.py`; 별도 입력 산출 경로 `data/condition_inputs/v1/20261125/`. 원본 및 정규화 스냅샷은 읽기 전용으로 사용했다.

## 생성 및 범위

| 출처 | 전체 | 추출 입력 | 보류 |
|---|---:|---:|---:|
| 기업마당 | 1,294 | 1,294 | 0 |
| K-Startup | 3,822 | 3,822 | 0 |
| 나라장터 | 192,064 | 0 | 192,064 |
| 합계 | 197,180 | 5,116 | 192,064 |

산출물: `extraction_inputs.jsonl`(5,116), `dispositions.jsonl`(197,180), `candidate_refs.jsonl`(17,211), `representative_samples.jsonl`(100), `g2b_deferred_samples.jsonl`(4), `kstartup_candidate_audit.jsonl`(ID 대조), `analysis_report.json`. 표본은 시드 25112026으로 출처별 개발 40·평가 10, 총 개발 80·평가 20이다. 각 입력 원문은 통합 공고의 `condition_texts.eligibility.text`를 그대로 보존하며, 검수 전·판정 비허용으로 표시했다. 자격 원문 청크를 정확히 포함한 검색 가능 청크만 참조하며, 원문 필드 참조는 항상 포함한다.

## 후보 ID 충돌 원인 및 수정

기존 ID `notice_id:attribute:char_start`는 출처 필드/섹션을 포함하지 않았고, 위치가 각 텍스트 원천에서 다시 0부터 매겨졌다. 따라서 서로 다른 섹션의 `company_size` 후보가 같은 ID를 받았으며 일부 중복 추출 행도 같은 위치를 공유했다. 대표 충돌 `BIZINFO:PBLN_000000000115994:company_size:0`은 API 자격 본문의 “국내 중소ㆍ중견기업”과 첨부 자격 본문의 “국내중소·중견기업중 스마트공장 구축이 필요한 제조기업”으로, 원문과 섹션이 서로 달랐다. 이는 삭제/병합할 동일 후보가 아니라 ID_COLLISION이다.

전체 기존 ID를 재계산하면 후보 17,211건 중 기존 ID 고유값 15,319개, 중복 그룹 1,246개, 추가 충돌 항목 1,892건이다. 중복 그룹은 근거/해석 차이에 따라 `MULTIPLE_EVIDENCE` 690, `CONFLICTING_CANDIDATE` 365, `ID_COLLISION` 191, `EXACT_DUPLICATE` 0건으로 분류됐다. 수정 ID는 공고 ID, 출처 종류, 섹션/필드, 문자 위치, 속성, 조건 종류, 추출 규칙, 원문, 정규화 값을 정렬 JSON으로 직렬화해 SHA-256 해시하며, 완전히 같은 반복 레코드만 occurrence ordinal로 구분한다. 각 후보에 `legacy_candidate_ref`를 함께 기록해 이전 ID 대응을 보존한다. 후보 수는 17,211건으로 동일하고 삭제된 원본 후보는 없다. 수정 후 신규 ID 중복은 0건이다.

## 기존 후보 분석 및 공백

- 기존 값 후보 17,211건은 입력 원문과 추적 가능한 추출 후보로 재사용하되 전부 검수 전 상태로 유지한다. OCR_TEXT 67건은 검수 대상으로 별도 관리해야 한다.
- K-Startup 조건 파일은 3,819개 공고, 후보 46,176개(NEEDS_REVIEW 27,945, NOT_FOUND 18,231)다. 중복 ID 0, 통합 스냅샷에 없는 추가 ID 0. 스냅샷 공고 3건 `KSTARTUP:171419`, `KSTARTUP:173424`, `KSTARTUP:175366`은 후보 파일에 없지만 원문 자격 텍스트가 있어 입력 5,116건에는 포함된다. `not_found`는 조건 부재로 변환하지 않는다.
- 후보 계층의 검수 결과는 전부 자동화 결과 그대로 보존하며 확정 판정 허용 상태는 생성하지 않았다.

## 문장 패턴 통계

아래는 자격 원문 문자열에 패턴이 하나 이상 발견된 공고 수이며 유형은 중복될 수 있다. 검수된 논리 조건 수가 아니다.

| 문자열 패턴 | 공고 수 |
|---|---:|
| AND 후보 | 2,043 |
| OR 후보 | 1,402 |
| NOT/제외 표현 | 383 |
| 예외/단서 표현 | 214 |
| 수치/범위 표현 | 2,223 |
| 지역 | 1,853 |
| 업력/연령 | 1,385 |
| 우대/가점 | 239 |

## 검증 및 제한

대상/보류 ID는 전체 197,180개와 정확히 일치하고 상호 배타적이다. 입력 ID 5,116개, 보류 192,064개, 후보 참조 17,211개, 표본 100개 모두 중복 0. 원문 필드와 청크 참조는 실제 스냅샷을 대조하고, 청크는 공고 ID가 일치하는지 검사했다. 개인 연락처 값은 통합 스냅샷 정책에 따라 노출되지 않으며, 샘플/입력은 모두 `UNREVIEWED`, `decision_eligible=false`다. 나라장터는 입력에 포함되지 않고 192,064건 전부 원문 미수집 보류다.

결정성 검사에서 별도 임시 경로 재생성 결과와 모든 JSONL 산출물 바이트 해시가 일치했다. `analysis_report.json`의 실행 시점 등 변동 메타데이터는 없으며 동일하다.

실행 명령:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_condition_inputs tests.test_normalize_support_data tests.test_public_notice_pipeline tests.test_g2b_normalization tests.test_condition_schema -v
```

결과: **35 tests passed**. 조건 추출기/논리 변환/판정기는 구현하지 않았다. 입력 구성 검증은 완료되어 2-2단계 개발 착수 가능하다. 다만 평가 표본 20건은 모델/규칙 튜닝과 분리해 보관해야 하며, 원문 해석에 대한 사람 검수는 다음 단계의 독립 검증으로 수행해야 한다.
