# 2-4A 마무리: 버전·검수 자료 호환성 확인

## 건너뛴 테스트 5개

전체 실행 기록은 99개 중 94개 통과, 5개 건너뜀, 실패 0개다. 다섯 건은 모두 `tests/test_api.py`의 테스트이며, `@unittest.skipUnless(HAS_DEPS, ...)`가 테스트 클래스 전체에 적용되어 있다. 현재 환경에서 `fastapi`, `httpx`, `pydantic_settings` 세 패키지가 모두 없다.

| 테스트 | 건너뛴 사유 | 필요한 환경/입력 | 기존에도 조건부였나 | 필수 데이터 버전 회귀인가 | 이번 단계 영향 |
|---|---|---|---|---|---|
| `TestApi.test_health` | API 테스트 의존 패키지 부재 | fastapi, httpx, pydantic-settings | 예. 클래스 skipUnless | 아니오 | API `/health` 계약 확인만 미실행 |
| `TestApi.test_eligibility_keeps_missing_values_as_unknown` | 동일 | 동일 | 예 | 아니오 | API 요청에서 missing→UNKNOWN 전달 확인만 미실행 |
| `TestApi.test_settings_read_existing_env_names` | 동일 | 동일 | 예 | 아니오 | 환경 설정 이름 호환 확인만 미실행 |
| `TestApi.test_health_reports_configuration_without_values` | 동일 | 동일 | 예 | 아니오 | `/health` 설정 정보 응답 확인만 미실행 |
| `TestApi.test_invalid_input_is_rejected` | 동일 | 동일 | 예 | 아니오 | API 입력 유효성 계약 확인만 미실행 |

이 다섯 테스트는 API 응용 계층 테스트이고, 조건 입력 생성, 기존 기준선 복구, v1.1 초안 스키마·참조 확인을 검증하는 필수 버전 회귀 테스트가 아니다. 테스트를 강제로 통과시키거나 skip을 제거하지 않았다. API 변경을 배포하는 작업에는 이 결과가 충분하지 않지만, 이번 데이터 버전 분리 완료를 막지는 않는다.

## `BIZINFO:PBLN_000000000118182` 후보 참조 4건

| 위치 | v1 과거 후보 | v2 현재 후보 | 비교 |
|---|---|---|---|
| 본문 위치 82 | `...FACT:b84cc8ab9022bde0dd99:0`, `company_size`, `{"label":"사회적기업"}` | `...FACT:2451afdc22b67f7344db:0`, `certification`, 같은 값 | 같은 원문 구간·정규화 값. 속성 분류 변경. |
| 본문 위치 121 | `...FACT:d90789f43a3eed9fbd36:0`, `company_size`, `{"label":"예비사회적기업"}` | `...FACT:6a117a9e39479ae3a057:0`, `certification`, 같은 값 | 같은 원문 구간·정규화 값. 속성 분류 변경. |
| 중복 근거 위치 90 | `...FACT:cc45e677d4f75c2f9c75:0`, `company_size`, `{"label":"사회적기업"}` | `...FACT:bb9e871e0cefeb488edf:0`, `certification`, 같은 값 | 같은 문구의 다른 원문 위치. 속성 분류 변경. |
| 중복 근거 위치 129 | `...FACT:cc1b0b34b40c07631f30:0`, `company_size`, `{"label":"예비사회적기업"}` | `...FACT:b361eda307a4a5b0c8ce:0`, `certification`, 같은 값 | 같은 문구의 다른 원문 위치. 속성 분류 변경. |

정규화 값·원문 근거·위치는 보존되고 candidate ID만 속성 변경에 따라 바뀌었다. 원문 좌표 및 문자열은 기존 정규화 사실에 대응한다. 자동 추출 후보 변경과 사람 검수 정답은 별개다.

v1.0과 v1.1 정답 초안은 각각 11개 조건, 같은 GOLD ID·값·원문 문구를 갖는다. v1.1은 이를 덮어쓰지 않았다. `condition_type=ELIGIBILITY`, 경기 지역, 영리 여부, 8개 조직 유형과 비영리 허용 3개 조직 유형의 논리 분기도 유지되며, 비영리 효과는 기존 OR AST에 반영된 상태(`AST_ONLY`)다. 예외와 논리 참조는 동일한 GOLD ID를 사용한다. 현재 후보 4건은 기존 정답 초안의 `existing_candidates`/alignment 목록에 추가되어 있지 않다. 이는 정답 조건 누락이 아니며 자동 후보 정렬만 최신 후보와 버전 대응하지 않은 상태다. 초안 재작성은 필요하지 않다. 다음 사람 검수 화면에서는 후보 ID를 데이터 버전별로 대응시키거나 본문 근거로 비교해야 한다. 자동 승인 금지와 UNREVIEWED/PENDING 상태를 유지한다.

## 현재 개발 추출·논리·검수 자료가 참조하는 버전

| 층 | 고정 버전/경로 | 참고 |
|---|---|---|
| 원본 정규화 snapshot | `20261125_g2b` 및 2026-11-24 정규화 값 파일 | `v1/20261125/analysis_report.json`에 입력 해시가 기록됨. |
| 조건 추출 입력 | `data/condition_inputs/v1/20261125/` | `representative_samples.jsonl`의 개발 표본 80건·평가 표본 20건과 `candidate_refs.jsonl` 17,211건을 고정 참조. |
| 추출·논리 결과 | `extracted/`, `extracted/improved/`, `logic/` 아래 기존 출력 | 모두 과거 v1 입력으로 산출된 결과. 신규 v2 후보를 혼합하지 않음. |
| 공통 조건 스키마 | 결과 JSON `schema_version=1.0` | 기존 추출·논리 결과의 형식 버전. |
| 추출기 | 코드 `tools/extract_condition_candidates.py`, Git 이력 기준 최근 커밋 `5a4ee56` | 실행 보고서의 `extraction_mode=RULE_BASED`; 구체 릴리스 버전 문자열 없음. 코드 SHA-256 `13cb692eb495cc440e94102bb9e6a7377657c75815e824300ba2a03457f17bef`. |
| 논리 변환기 | 코드 `tools/build_condition_logic.py`, Git 이력 기준 최근 커밋 `5a4ee56` | 산출 schema `1.0`; 별도 변환기 version 문자열 없음. 코드 SHA-256 `65d2e4f54ab77627c26a4443e3450a0cca0f178d66dc6c1e2e8b5291e7f30fd2`. |
| 정답셋 검수 자료 | v1.0과 별도 v1.1 사전 검수 5건 | v1.1 스키마 파일은 별도 버전. 조건·논리 결과 기반선으로 승격되지 않음. |
| 평가기 | `tools/evaluate_condition_pipeline.py`, `EVALUATOR_VERSION=1.0.0`, 최근 코드 커밋 `5a4ee56` | v1.1 preflight는 의미 평가 미구현 및 UNREVIEWED로 BLOCKED. 코드 SHA-256 `042a5c9f88176eba9a44757405167932cfc6d3396a0be4e4e4bb78fdd5477bca`. |

새 입력 버전은 별도의 후보 출력 `data/condition_inputs/v2/20261126/`에 고정했다. 입력 facts SHA-256은 `31452b47a592744245b2953ed4cf544567f771dc3f0868e54ae4215da59886e2`, 후보 출력은 17,253건, SHA-256 `f20acf5599785e4d3e9c7224359ba41e11a5ae01f867108470798064f4d1b51c`다. 이 출력은 `CANDIDATE_NEEDS_REVIEW`, `decision_eligible=false`이다. 따라서 평가 실행은 기존 기준선에서는 v1 입력·v1.0 정답·평가기 1.0을 별도 지정하고, 신규 데이터는 v2 후보 전용 테스트에서 해시·참조 무결성만 확인해야 한다. 두 버전 산출물을 하나의 평가 입력으로 섞지 않는다.

## 완료 판단

- 필수 회귀: 과거 기준선 재현, 현재 v2 내부 결정성, 전체 99개 회귀 모두 통과(94 passed, 5 skipped, 0 failed).
- 검수 5건: v1.1 스키마·논리 참조 검증 통과 기록 유지. 5건 모두 UNREVIEWED/PENDING이며 v1.1 의미 평가 점수는 차단.
- 보존 해시: 과거 입력 `c47bccc38ee373f756481a93e68e1a123a24d31f04ed1b4f198d3647930ac2e8`, 과거 후보 `5765dad05de72b8a44875353495e12224704da3f5b0067b955e1fb5e4b5c06e3`, 신규 입력·출력은 v2 manifest에 고정.
- 2-4A 기술 보완은 종료 가능하다. 의미가 바뀐 후보와 5건 정답 초안은 사람 검수 단계로 넘긴다. 건너뛴 5개는 선택적 API 의존성 테스트이며 이번 완료의 BLOCKER가 아니다.
