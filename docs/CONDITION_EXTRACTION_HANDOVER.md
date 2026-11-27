# 조건 추출·평가 파이프라인 인수인계

작성 기준일: 2026-11-27
기준 저장소: 현재 작업 트리, 브랜치 `handover/condition-extraction` (기존 `main` HEAD `11634d17225010719becd2f4dd85d4077d8420e7`에서 생성)
목적: 후속 담당자가 조건 데이터, 추출기, 평가 결과와 현재 P4 파일럿을 구분해 이어서 작업할 수 있도록 현재 구현과 증거 위치를 정리한다.

## 1. 지금 상태 한눈에 보기

- 개발용 파일럿 10건·정답 조건 62개 strict 평가 기준은 규칙 v1 F1 13.64%, 개선 규칙 E 14.12%, LLM P12 2.13%, P12+N1 6.38%다. P4는 아직 전체 응답 10건이 없으므로 미측정이다.
- P12 장부는 13/13 사용, 잔여 0회다. 별도 계보인 `llm_pilot_2_5c3d5a_p4`는 10회 예산 중 3회 예약/사용 기록, 3건 HTTP 200 응답 보존, 기술 Gate 통과 2건, 차단 1건, 미실행 7건, 잔여 7회다.
- P4 117168 및 118182는 응답과 기술 Gate는 정상이나 현재 bridge가 `source_field` 인터페이스 차이로 표준 후보를 모두 거부했다. 인메모리 진단에서는 입력 evidence의 고정 source path를 부여한 뒤 기존 검증을 실행해 각각 3개·10개 후보가 만들어졌다. 이 결과는 저장된 산출물에 반영되지 않았다.
- P4 119490은 원문에 반복되는 근거 문구를 유일한 위치로 특정하지 못해 중단됐다. 첫 출현 위치 선택은 안전하지 않으며, 근거 후보 위치와 미확정 상태를 보존하는 별도 수정 및 파생 fingerprint가 필요하다.
- P4 `--run-remaining`은 현재 `ids[1:]`을 선택한다. 요청 장부에 ordinal 2, 3이 이미 있어 기존 응답 중복 방지 검사에 걸릴 수 있으므로 수정 전 실행하지 않는다.
- 실행·평가 관련 코드는 다수 미추적 상태이고, 현재 작업 트리에는 이 작업과 별개인 수정 사항도 있다. 공유 준비 목록은 §10을 확인하고, 커밋·푸시는 수행하지 않았다.

세부 장애 절차는 [Troubleshooting](CONDITION_EXTRACTION_TROUBLESHOOTING.md), 우선순위별 작업은 [Next TODO](CONDITION_EXTRACTION_NEXT_TODO.md)를 참조한다.

## 2. 작업 이력과 산출물 위치

| 단계 | 목적·구현 및 결과 | 주요 경로 / 상태 |
|---|---|---|
| K-Startup 수집·정제 | K-Startup 원천 수집과 정제 파이프라인의 기반. 원본 첨부·수집 원천 일부는 로컬 전용이며 Git에서 제외된다. | `data/kstartup/`, `tools/`, `.gitignore`; 현재 조건 파일럿은 정제된 입력 스냅샷을 사용 |
| 다중 출처 정규화 | 기업마당·K-Startup·G2B 자료를 공통 추출 입력 형태로 정리하고 입력 이력을 보존했다. | `docs/SUPPORT_DATA_NORMALIZATION_V1.md`, `data/condition_inputs/v1/20261125/`, `data/condition_inputs/v2/20261126/`; 입력 JSONL은 Git 추적됨 |
| 조건 스키마 v1.0/v1.1 | 공통 조건, 논리 그룹, 공고별 조건 집합과 검수·평가 스키마를 분리했다. v1.1은 temporal 및 평가/충족 시점 등을 포함한다. | `schemas/conditions/condition-v1.schema.json`, `condition-v1.1.schema.json`, `condition-common-v1*.schema.json`, `notice-condition-set-v1*.schema.json`; 상세는 `docs/condition/CONDITION_SCHEMA_V1.md` 및 `docs/CONDITION_EVALUATION_V11_POLICY.md` |
| 조건 입력·골든셋 | 추출 입력 및 검토 가능한 개발 정답셋을 만들었다. 파일럿 10건과 개발용 30건은 다른 범위다. | 입력: `data/condition_inputs/v2/20261126/extraction_inputs.jsonl`; 정답: `data/goldsets/conditions/v1.1/20261126/final30/development/`; 파일럿 ID: `data/evaluations/conditions/v1.1/20261126/llm_pilot_preparation/development/pilot_notice_ids.json` |
| 규칙 추출·개선 실험 | 기존 규칙 v1과 개선 규칙 E를 비교했다. 개발 10건 평가를 30건 전체 평가와 혼동하지 않는다. | `data/evaluations/conditions/v1.1/20261126/development/baseline_v1/`, `rule_improved_2_5c/`; 규칙 추출 결과·상세 보고 참조 |
| LLM 추출기·P12 | OpenAI 호환 provider, 중간/최종 검증, 요청 장부, 응답 보존, 실패 산출물 및 실행 계보를 구현했다. P12는 10건 응답을 확보했고 178507의 `UNKNOWN` operator는 스키마 위반 실패로 보존해 평가 입력에서 빈 예측으로 처리했다. | `tools/extract_condition_candidates_llm.py`, `tools/run_condition_llm_p12.py`; P12: `.../llm_pilot_2_5c3_r2_p12/`; 기존 추출기 안내 `docs/CONDITION_LLM_EXTRACTOR_PILOT_20261126.md` |
| P12 오류 진단 | 속성·근거·스키마·실행 상태 문제를 공고 단위로 추적했다. | `tools/diagnose_condition_llm_p12.py`; `.../llm_pilot_2_5c3d1_diagnosis/` |
| 표준 표현 draft 및 N0–N5 | draft-v1 계약에서 안전한 실험 subset을 사용해 단위·값·범위·alias 정규화를 비교했다. 운영 기본값이나 골든셋은 바꾸지 않았다. N1/N5가 단위 표현을 정규화해 F1 6.38%였고 나머지는 기준 P12 2.13%와 같았다. | `schemas/conditions/contracts/draft-v1/`, `tools/condition_safe_normalization_experiment.py`, `tools/run_condition_normalization_experiments.py`; 결과 `.../condition_normalization_2_5c3d2c_v1/`; draft는 미승격 |
| 논리 평가 adapter | 원본 논리 산출물 구조 전달을 개선한 별도 평가 adapter를 구현했다. 다만 LLM strict 그룹/관계 F1은 여전히 0%였다. | `tools/condition_logic_evaluation_adapter.py`, `tools/run_logic_adapter_experiments.py`; `.../logic_adapter_2_5c3d3_v1/`; 미지원 예외 효과·미해결 관계는 미측정으로 남김 |
| P4 정책 및 실행 준비 | 공통 표현 계약, 제한 enum, 구조화 출력, 원자 조건, 근거·논리 연결 및 N1을 통합한 `condition-next-extraction-policy-v1`을 별도 계보로 준비했다. | `tools/condition_llm_next_policy.py`, `tools/run_condition_llm_p4_pilot.py`; `.../llm_next_policy_2_5c3d4_v1/` |
| P4 실제 실행·진단 | 첫 3건에 실제 요청이 수행됨. 2건 technical pass, 119490은 중복 인용 근거 오류로 차단. 117168/118182는 source_field mismatch로 유효 후보 0개. P4 전체 평가는 10건 자격 요건 부족으로 정상 차단 상태다. | `.../llm_pilot_2_5c3d5a_p4/`; 자세한 장애 분석은 [Troubleshooting](CONDITION_EXTRACTION_TROUBLESHOOTING.md) |

## 3. 고정 성능 기준선

아래 수치는 **같은 개발용 파일럿 10건 및 정답 조건 62개**를 대상으로 하는 strict 조건 평가다. Precision/Recall/F1은 exact match 기준이다. 부분 일치는 TP에 포함하지 않는다.

| 방식 | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|
| 규칙 v1 | 6 | 20 | 56 | 23.08% | 9.68% | 13.64% |
| 개선 규칙 E | 6 | 17 | 56 | 26.09% | 9.68% | 14.12% |
| LLM P12 | 1 | 31 | 61 | 3.13% | 1.61% | 2.13% |
| LLM P12 + N1 | 3 | 29 | 59 | 9.38% | 4.84% | 6.38% |
| P4 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 |

P12 검증 후 부분 일치는 16개, Macro F1은 2.50%, 예측 0개 공고는 3건이다. P4는 현 시점에서 2개 공고의 후보 처리 장애와 1개 공고의 근거 모호성으로 전체 10건이 완료되지 않아 점수를 만들 수 없다. P4의 현재 2건 후보 0개 현상은 전반적인 LLM 성능으로 해석하지 말고 source_field bridge 장애로 분리한다.

논리 gold 기준은 24개 그룹·71개 관계다. 논리 adapter 개선 뒤에도 그룹 및 관계 strict F1 0%이며, P12 논리 기준선 보고서에서는 그룹 exact 0/24, AST exact 0/10이다. 예외 적용 효과와 미해결 관계 의미는 기존 평가기에서 `UNSUPPORTED_V1_0`로 미측정이다. 조건 F1과 논리 F1을 혼합하지 않는다.

평가 정책의 필드, 매칭과 미지원 값 처리는 [조건 의미 평가 v1.1 정책](CONDITION_EVALUATION_V11_POLICY.md)을 참조한다. P12 기준선 및 매칭 상세는 `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3_r2_p12/`의 manifest와 평가 산출물, 규칙 기준선은 `baseline_v1/` 및 `rule_improved_2_5c/` 아래 manifest/report를 참조한다.

## 4. P4 계보 및 현재 상태

실행 ID `llm_pilot_2_5c3d5a_p4`, 실행기 `tools/run_condition_llm_p4_pilot.py`. 결과 폴더는 `data/evaluations/conditions/v1.1/20261126/development/llm_pilot_2_5c3d5a_p4/`이다.

| 구분 | 현재 확인값 |
|---|---|
| 계획 입력 | 10건, 5개 BIZINFO + 5개 K-Startup; 고정 입력 순서는 manifest 및 `pilot_notice_ids.json` 기준 |
| 요청 장부 | 승인된 별도 예산 10회; used 3, remaining 7, reserved 0, succeeded 2, failed 1, api_call_count 3 |
| 응답 | HTTP 200 3건; 원본 응답은 `responses.jsonl`에 보존 |
| 기술 Gate | 2 pass / 1 blocked; 전체 `IN_PROGRESS`, 전체 평가 준비 false |
| 상세 상태 | 117168 pass, 118182 pass, 119490 blocked; 미실행 7건은 `126490`, `128028`, `KSTARTUP:176001`, `176813`, `177447`, `178507`, `179386` |
| 부모 P12 | 13/13 사용, 잔여 0; 장부 원본을 보존. P4와 별도 장부·실행 계보 |
| 요청 설정 | 기존 모델 `gpt-5.6-luna`, reasoning low, max completion 8192, timeout 180초, JSON Schema 구조화 출력, SDK 자동 재시도 0회 |

부모 P12와 P4 결과를 섞어 하나의 실행 점수로 보고하지 않는다. P4의 `without N1`/`with N1`는 동일 P4 원본 응답으로 별도 파생 산출물을 생성하는 비교다. 새 API 응답이 확보되기 전까지 P4 성능은 미측정이다.

## 5. 후속 담당자가 먼저 알아야 할 세 가지 문제

1. **source_field 계약 불일치:** P4 모델 값은 자연어 속성값/카탈로그명(`소상공인`, `주소지`, `BUSINESS_LOCATION` 등)인데 legacy converter는 고정 source path `condition_texts.eligibility.text`만 허용한다. converter는 변환 검증 전에 `SOURCE_FIELD_MISMATCH`를 반환한다. 허용 조건을 느슨하게 하기보다 trusted input evidence에서 source path를 붙이고 provenance와 모델 추출값을 분리해야 한다.
2. **근거 위치 중복:** `condition_llm_next_policy.py`는 unresolved evidence quote가 원문에 정확히 한 번 나타나지 않으면 `ValueError`를 발생시켜 전체 공고 처리를 멈춘다. 모든 span 후보와 모호성 보류 상태를 보존하는 것이 안전한 수정 방향이다. 첫 출현 선택은 금지한다.
3. **재개 선택 오류:** runner의 remaining 경로는 현재 입력 목록 `ids[1:]`을 매번 선택한다. 이미 호출된 ordinal 2, 3과 겹칠 수 있으므로 남은 예산 7회가 있다고 바로 이어 실행하면 안 된다. 원본 응답·장부를 대조해 실제 미실행 ID만 고르는 재개 계획을 새 fingerprint에서 검증해야 한다.

검수 대기나 유효 후보 0개는 기술 오류와 분리한다. 자동 판정 가능 상태는 계속 false다. 현재 제안서의 안전 규칙과 구현 판단은 [Troubleshooting](CONDITION_EXTRACTION_TROUBLESHOOTING.md)에 상세히 있다.

## 6. 개발 환경 및 사용 경로

현재 확인 환경은 Python 3.12.13, OpenAI SDK 2.54.0, httpx 0.28.1, jsonschema 4.26.0이다. 저장소는 `requirements.lock.txt`를 잠금 의존성 입력으로 안내한다. `.venv`는 Git 제외 대상이다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
```

Linux/macOS에서는 `.venv/bin/python`을 사용한다. Windows 명령을 그대로 복사하지 않는다. 네트워크 없는 오프라인 재현 환경이면 사전에 wheelhouse나 의존성 캐시를 준비해야 한다. 이 문서 작성 중 설치는 실행하지 않았다.

P4에서 환경 변수로 확인된 credential 이름은 `OPENAI_API_KEY`다. `.env`의 값은 문서화하거나 Git에 포함하지 않는다. 실행기는 `--env-file`을 제공한다. P4 preflight는 읽기 전용이다. 오프라인 self-test는 테스트 전용 transport/임시 경로로 확인한다.

```powershell
# 도움말 / 읽기 전용 사전 점검
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --help
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --preflight

# 실제 API 없이 실행 경로 점검
.\.venv\Scripts\python.exe tools/run_condition_llm_p4_pilot.py --offline-self-test
```

위 세 명령 중 `--preflight`와 `--offline-self-test`만 API 비호출이다. 실제 요청을 보내는 `--run-first` 및 `--run-remaining`은 **현재 source_field·근거 처리·재개 선택 문제가 해결되고 새 파생 fingerprint와 장부 안전성이 확인될 때까지 실행 금지**다. P4 전체 평가는 기존 10건의 eligibility가 완료된 뒤 명시적으로 실행한다. 현재 `--evaluate`는 10건 조건을 충족하지 못해 차단되는 것이 정상이다. 정확한 CLI 인자는 `python tools/run_condition_llm_p4_pilot.py --help`가 기준이다.

P4 변경 시 관련 offline 회귀 테스트는 다음과 같이 실행한다(테스트는 실제 API 키를 사용하지 않아야 한다).

```powershell
.\.venv\Scripts\python.exe -m unittest `
  tests.test_condition_llm_p4_pilot `
  tests.test_condition_llm_next_policy `
  tests.test_condition_llm_client_lifecycle `
  tests.test_condition_logic_evaluation_adapter -v

# 전체 저장소 회귀
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`docs/CONDITION_LLM_EXTRACTOR_PILOT_20261126.md`에 기록된 217개 전체 테스트 결과는 이전 상태의 기록이며, 이번 handover 작성 중 테스트를 재실행한 결과가 아니다. P4 관련 테스트도 새 source 변경 후 다시 실행해야 한다.

조건 strict evaluator 정책/사전검사는 `tools/evaluate_condition_pipeline_v11.py`이며, 정책 설명과 실행 예시는 [CONDITION_EVALUATION_V11_POLICY.md](CONDITION_EVALUATION_V11_POLICY.md)에 있다. Goldset·입력 고정 해시 검사가 실패하면 점수 생성 전에 원인을 조사한다.

## 7. 주요 파일 목록

| 경로 | 역할·입력·출력 | 상태 / 후속 확인 |
|---|---|---|
| `tools/extract_condition_candidates_llm.py` | LLM 응답 변환 및 조건 검증; raw/intermediate JSON을 검증된 후보, 거절, review queue로 변환 | 현재 변경됨. legacy `SOURCE_FIELD`가 고정되어 있어 P4 bridge mismatch 원인 확인 필요 |
| `tools/condition_llm_next_policy.py` | P4 정책 prompt/schema, P4 응답 projection·근거 처리 | 현재 미추적. evidence unique-count 차단 지점. v1 정책 및 fingerprint 재검토 필요 |
| `tools/run_condition_llm_p4_pilot.py` | P4 사전 점검, 장부, budget 승인, 순차 실행, Gate 및 평가 CLI | 미추적. current `--run-remaining` 선택 결함 수정·offline CLI 검증 필요 |
| `tools/run_condition_llm_p12.py` | P12 실행 계보 | 미추적 여부를 `git status`에서 확인. P12 장부는 13/13 보존 |
| `tools/evaluate_condition_pipeline_v11.py` | strict v1.1 evaluator 및 고정 입력 검증 | tracked path; P12/P4 공통 결과 기준 변경 금지 |
| `tools/condition_safe_normalization_experiment.py` | 실험용 안전 정규화, N1 등의 결과 비교 | 미추적; 운영 기본 정책으로 자동 적용 금지 |
| `tools/condition_logic_evaluation_adapter.py` | 논리 산출물 평가 입력 adapter | 미추적; unsupported 구조는 미측정 유지 |
| `schemas/conditions/condition-v1.1.schema.json` | 최종 v1.1 조건 schema | tracked; 임의 enum 완화 금지 |
| `schemas/conditions/contracts/draft-v1/` | 공통 조건 표현 draft contract | 미추적; 운영 승격 전 검토·버전 고정 필요 |
| `data/condition_inputs/v2/20261126/extraction_inputs.jsonl` | 공고 입력/evidence, source provenance 경로의 기준 | Git 추적됨; 고정 입력 변경 금지 |
| `data/condition_inputs/v2/20261126/representative_samples.jsonl` | 대표 샘플/입력 검증 보조 | Git 추적됨 |
| `data/goldsets/conditions/v1.1/20261126/final30/development/` | 개발용 조건·논리 골든셋과 manifest | 일부 확인 파일은 Git 추적됨; 절대 수정 금지. 파일럿 10건과 개발 30건 분리 |
| `.../llm_pilot_2_5c3_r2_p12/` | 부모 P12 원본 응답, 요청 장부, 검증/평가 | 작업 트리에서 미추적 subtree 있음. 원본 보존, 13/13 사용 |
| `.../llm_pilot_2_5c3d5a_p4/` | 신규 P4 manifest, 장부, `responses.jsonl`, preflight, runbook, notice별 하위 결과 | 미추적 subtree; 응답 공유 전 데이터/저장소 정책 검토, 수정 금지 |
| `tests/test_condition_llm_p4_pilot.py` | P4 오프라인 통합 및 예산/실행 흐름 테스트 | 미추적; 다음 수정은 임시 장부/경로에서 검증 |
| `docs/CONDITION_LLM_EXTRACTOR_PILOT_20261126.md` | 이전 LLM 파일럿 사용·회귀 기록 | 기존 문서. 이 handover는 P4 후속 내용을 보충 |
| `docs/CONDITION_EVALUATION_V11_POLICY.md` | exact/partial, logic 및 v1.1 평가 정책 | 기존 문서. 평가 해석 전 필독 |

`...`는 `data/evaluations/conditions/v1.1/20261126/development/`를 뜻한다.

## 8. 안전 정책

- 골든셋, 독립 평가 20건 및 고정 입력을 변경하지 않는다. 개발용 30건, 파일럿 10건, 독립 20건은 명칭과 평가 단계가 다르다.
- raw 응답, 기존 실패, 장부 및 manifest를 덮어쓰거나 초기화하지 않는다. 재처리는 파생 output dir와 명시적인 source lineage/fingerprint를 사용한다.
- 이전 응답을 재호출하지 않는다. 실패 요청을 예산 사용량에서 제외하거나 자동 재시도하지 않는다.
- 속성 허용 검사를 제거하거나 실제 미지원 속성을 자동 통과시키지 않는다. 의미 모호성은 보류한다.
- 근거 중복일 때 임의 첫 span을 선택하지 않는다. 모든 후보 위치와 미확정 상태를 기록한다.
- 미해결 조건이나 예외를 유효 조건으로 승격하거나 AND/OR를 추정하지 않는다. `decision_eligible=false` 유지.
- P12·P4처럼 추출 정책이 다른 응답을 같은 모델/정책 결과로 합치지 않는다.
- strict evaluator와 골든셋이 고정되어 있어도 개발 파일럿 성능은 독립 성능이 아니다.

## 9. 기존 문서와 중복 범위

- 데이터 정규화 전체 설계: `docs/SUPPORT_DATA_NORMALIZATION_V1.md`
- 조건 스키마/입력/골든셋/추출 작업 일지: `docs/condition/CONDITION_SCHEMA_V1.md`, `CONDITION_INPUTS_STAGE_2_1_FINAL.md`, `CONDITION_GOLDSET_STAGE_2_4_REPORT.md`, `WORKLOG_20261125_CONDITION_PIPELINE.md`
- LLM P12 실행 가이드 및 평가 규칙: `docs/CONDITION_LLM_EXTRACTOR_PILOT_20261126.md`, `docs/CONDITION_EVALUATION_V11_POLICY.md`
- P12 실행 준비 및 차단 이력: `docs/CONDITION_LLM_PILOT_R2_READINESS_20261126.md`, `docs/CONDITION_LLM_PILOT_R2_RETRY_READY_20261126.md`
- 이 문서들은 기존 설계/결과를 복제하지 않고 현재 P4 handover 상태, 장애, 인계 순서를 덧붙인다.

## 10. Git 공유 준비 스냅샷

브랜치 생성 전 상태는 `main` @ `11634d17225010719becd2f4dd85d4077d8420e7`이었고, 현재 인수인계 브랜치는 `handover/condition-extraction`이다. 이 확인 시점의 `git status --short`에는 tracked 변경과 다수 untracked artifact가 있었다. 예를 들면 tracked 변경 `tools/extract_condition_candidates_llm.py`, `tools/evaluate_condition_pipeline_v11.py`, P12 manifest/ledger, goldset pilot profiles 및 기존 라벨링 문서/UI가 있고, P4/정규화/논리 도구와 테스트, contracts, 실험 출력, `data/normalized/v1/20261125_g2b/`가 untracked다. 자세한 전체 목록은 현재 상태가 바뀔 수 있으므로 `git status --short`로 다시 확인한다. 여기서 기존 변경의 소유자를 추정하거나 덮어쓰지 않는다.

**공유 후보(검토 후):** 신규 범용 Python 소스와 테스트, schemas/contracts의 승인된 계약 파일, 이 handover 문서. P4 실행 재현에 필요한 prompt/schema fingerprint와 결과 report/manifest는 민감 내용 및 데이터 라이선스 확인 후 필요한 최소 산출물을 선택한다.

**별도 전달 또는 제한된 artifact 보관 후보:** raw LLM responses, source notice text/evidence, 대용량 normalized snapshot, 원문/첨부, 로컬 추출물, P4/P12 request ledger 및 untracked eval subtree. 실험 재현에 필요하더라도 개인정보·원문 제공 정책·저장소 크기를 검토하고, Git에 무조건 추가하지 않는다. `data/goldset/pilot/packets/`, Bizinfo 첨부, K-Startup 원본, `.env`, `.venv`는 `.gitignore` 대상이다.

**절대 Git에 넣지 않음:** API key, 비밀번호, `.env` 값; 로컬 전용 credential; 무단 원문/첨부; 실행 장부를 새로 초기화한 대체 파일. `.env`·`.venv`·일부 raw data 및 packet 경로는 `.gitignore`에서 제외됨을 `git check-ignore -v`로 확인했다.

이번 후속 정리에서는 현재 변경·미추적 파일 2,700개를 임시 ZIP으로 백업했다: `%TEMP%\condition-extraction-handover-20261127-before-cleanup.zip` (압축 11,553,879 bytes, SHA-256 manifest 포함). ZIP은 로컬 백업이며 공유 artifact가 아니다.

중복을 SHA-256으로 확인한 루트 콘솔 출력 3개만 제거했다. `logic_adapter_run_output_final.json` 및 `logic_adapter_run_output_final_v1.json`은 남긴 `logic_adapter_run_output.json`과 바이트 단위 동일했고, `normalization_run_output_final.json`은 남긴 `normalization_run_output.json`과 동일했다. 이후 변경 파일 스냅샷은 2,697개다. 삭제본은 위 ZIP에 보관돼 있다. 고유한 `diagnosis_run_output.json`, `logic_adapter_run_output.json`, `normalization_run_output.json`, `p10_prepare_output.json`, `p12_prepare_output.json`은 진단 이력으로 보존했다.

실행기·검증기 통합은 수행하지 않았다. 정적 import/reference 확인 결과 P12 → P10 → P8 → norm_v2/base, P10/P8/recovery → norm_v2/base, P4 → P4 policy + logic adapter + safe normalization + 기존 LLM validator 체인이 확인됐다. P4 fingerprint는 관련 모듈, schema, prompt 및 입력 해시를 고정한다. 파일을 합치거나 제거하면 부모 계보와 fingerprint의 재현성이 바뀌므로 기능 통합 없이 보존하는 편이 안전하다. 현재 폴더 구조는 다음과 같으며 이동은 하지 않았다.

```text
tools/                         공통 validator, 정책, runner, 실험·평가 adapter
tests/                         기존 단계별 회귀 및 오프라인 통합 테스트
schemas/conditions/            v1/v1.1 schema 및 contracts/draft-v1
data/condition_inputs/         고정 normalized extraction input
data/goldsets/conditions/      개발용 gold 및 manifest
data/evaluations/conditions/   P12/P4/정규화/논리 실험별 독립 lineage
docs/                          기존 설계 문서 + handover 3종
```

정리 후 확인 결과:

- P4 `--preflight`: PASS, 고정 10 IDs와 62/24/71 개수 확인, API 호출 0.
- P4 `--offline-self-test`: PASS, 임시 폴더에서 mock 요청 10회, 기존 P12 파일 보존, API 실제 호출 0.
- 안정된 LLM/정규화/논리 모듈 subset: 154 tests PASS.
- G2B `notices.jsonl`을 포함한 전체 `unittest discover -s tests`: 369 tests, 11 failures, 2 errors, 37 skipped. 파일 누락 오류는 해소됐지만 고정 입력 hash/원문과 snapshot 내용 차이로 `test_condition_inputs` 3개가 실패한다. 나머지는 P10 fingerprint/CLI 2개, P12 budget·claim·10응답 집계·CLI 4개, P4 preflight의 기존 output 경로 가정 1개, P8 blocked fixture 1개 등이다. P10/P12 CLI 2개는 오류다. 테스트를 삭제하거나 건너뛰고 데이터를 임의 수정하지 않았다.
- 관련 안정 모듈 subset: 154 tests PASS. P4 전체 모의 CLI self-test PASS; 실제 API 호출 0.
- 기존 P12와 N1 저장 응답/예측에서 평가 helper를 in-memory로 재실행하여 10개 notice·62개 gold 기준을 재현했다: 규칙 v1 6/20/56 F1 13.636%; 규칙 E 6/17/56 F1 14.118%; P12 검증 전 1/57/61 F1 1.667%; P12 검증 후 1/31/61 F1 2.128%; P12+N1 3/29/59 F1 6.383%. 어떤 평가 파일도 덮어쓰지 않았다.
- 테스트 전 백업 archive와 비교해 P12/P4 manifest 및 요청 장부 바이트 hash가 동일함을 확인했다. P4 3/10 사용·7회 잔여, 부모 P12 13/13 상태는 그대로다.

현재 브랜치는 `handover/condition-extraction`이다. 문서와 normalized G2B snapshot/LFS 및 Linux 경로 수정은 이미 branch history에 있다. 후속 공유 범위에는 P4/P12 실행 코드와 import 의존성, 관련 테스트, draft contract, P12/P4 manifest가 직접 hash로 참조하는 246개 파일, P12/N1/logic adapter 최종 평가 산출물, P4 실제 응답 3건이 포함된다. 파일 본문 스캔에서 API key/Bearer 패턴은 발견되지 않았다. `.env`, `.venv`, 첨부파일과 로컬 raw attachment 디렉터리는 제외한다.

`.gitattributes`는 기존 평가 JSONL/JSON의 `-text` 규칙을 유지하고, 이 실행 계보에서 fingerprint를 고정한 Python source 및 draft contract에도 범위를 좁혀 `-text`를 적용했다. 이는 현재 바이트를 바꾸지 않고 다른 OS의 checkout이 해시를 바꾸지 않도록 한다. `data/normalized/v1/20261125_g2b/notices.jsonl`은 LFS 대상으로 branch에 포함됐다. 기존 G2B `chunks.jsonl`/정규화 보고서와 중복 initial-run 디렉터리는 이번 공유 묶음에서 제외하고 로컬 보존한다. 사용자/팀의 goldset pilot profile, labeler, 기존 R2 manifest/ledger 수정은 별도 검토 전 커밋하지 않는다.

이번 후속 공유는 문서만이 아니라 실행 가능한 P4/P12 계보와 재현 산출물을 명시적 파일 목록으로 추가한다. 코드 정리로 fingerprint를 다시 쓰지 않고 현재 계보 해시를 보존한다. raw responses와 ledger는 고정 실험 산출물이며 P4 3/10, P12 13/13 상태를 그대로 공유한다. 저장소 전체 `git add .`는 사용하지 않는다. 추가 커밋에는 코드/테스트/계약/필수 산출물만 포함하고 별도 사용자 변경은 그대로 unstaged로 남긴다.
