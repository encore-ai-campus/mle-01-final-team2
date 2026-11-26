# 원문 인코딩 손상 진단 (2026-11-26)

## 결론

`BIZINFO:PBLN_000000000117546`은 파일 손상이 아니다. API 원본부터 UTF-8로 정상이며, 터미널에서 한글이 깨져 보인 현상을 저장 데이터 손상으로 오인했다. 앞서 작성한 `CONDITION_GOLDSET_PRECHECK_20261126_BLOCKER.md`의 “원문 훼손” 결론은 본 보고서로 대체한다.

## 바이트 단위 표본 추적

아래 모든 파일은 엄격한 UTF-8 디코딩에 성공했다. 각 값에 U+FFFD가 없고, 이 공고에서 비교한 한글 필드는 정상 Unicode 문자열이다. 원본 API JSON은 JSON escape로 직렬화되어 있었고, 파싱 이후 JSONL은 UTF-8로 직렬화되어 있다.

| 단계 | 파일 / 필드 | 결과 |
|---|---|---|
| 최초 수집 API 응답 | `data/bizinfo/raw/20261124_091601/page_012.json`, `jsonArray[].bsnsSumryCn` | 정상. 원본 바이트 UTF-8 유효, JSON 안에 `미국 수출 또는 예정 기업`이 포함 |
| 원본 저장 | 동일 page JSON | 정상. JSON escape된 한글이 손실 없이 저장 |
| 파싱 | `data/bizinfo/parsed/20261124_091601/notices.jsonl`, `eligibility_criteria_text` | 정상 |
| 정제 | `data/cleaned/20261124/notices.jsonl`, `eligibility_text` | 정상 |
| 20261124 정규화 | `data/normalized/v1/20261124/notices.jsonl`, `condition_texts.eligibility.text` | 정상 |
| 20261125_g2b 통합 | `data/normalized/v1/20261125_g2b/notices.jsonl`, 동일 조건 필드 | 정상 |
| 조건 입력 | `data/condition_inputs/v1/20261125/extraction_inputs.jsonl`, `raw_text` | 정상 |
| 추출 후보 | `data/condition_inputs/v1/20261125/extracted/development_conditions.jsonl` | 엄격 UTF-8 유효; 후보 원문 참조도 정상 |
| 논리 구조 | `data/condition_inputs/v1/20261125/logic/notice_condition_sets.jsonl` | 엄격 UTF-8 유효; 원문 참조 정상 |
| 검수 패킷 | `data/goldsets/conditions/v1/20261125/development/condition_review.jsonl`, `source_text` | 정상; 30개 `source_text`에서 U+FFFD 0 |

최초 손상 단계는 발견되지 않았다. 기존 파일의 저장 문자와 원문이 일치하므로 재수집이나 데이터 복구가 필요하지 않다. 원시 HTTP 헤더는 저장돼 있지 않아 실제 응답 `Content-Type`/charset을 사후 확정할 수 없다. 수집 코드는 `response.read().decode("utf-8")`를 사용한다.

## 저장 파일 무결성 범위

진단은 현재 보유한 기업마당 원시 페이지/파싱 결과, K-Startup 원시·처리 파일, 공통 정제·정규화 산출물, 조건 입력·후보·논리·검수 파일을 스트리밍 검사했다. JSON/JSONL/CSV 전체 텍스트를 strict UTF-8 디코딩하고 U+FFFD 포함 여부를 확인했다. 한글 필드에 대한 이상한 라틴 문자 시퀀스 탐색은 휴리스틱이므로 확정 손상 판단에 쓰지 않았다.

- BIZINFO 원시 13개 page JSON: UTF-8 오류 파일 0, U+FFFD 파일 0
- BIZINFO parsed `notices.jsonl` 및 `attachments.jsonl`: UTF-8 오류 0, U+FFFD 0
- K-Startup raw 및 `processed` 내 JSONL: 검사한 파일 모두 UTF-8 오류 0, U+FFFD 0
- `data/cleaned/20261124` 및 20261124 normalized 산출물: UTF-8 오류 0, U+FFFD 0
- condition inputs, extracted baseline/improved, logic, development/evaluation review 패킷: UTF-8 오류 0, U+FFFD 0
- `20261125_g2b/notices.jsonl`: 197,180 레코드 중 U+FFFD 1 레코드, U+FFFD 2개. 위치는 `source_metadata.source_specific.G2B.documents[].name`, ID `G2B:R26BK01463797:000`, 파일명 `...(통합예약결제시스템 고도��).hwpx`. G2B 문서 파일명 필드 국소 이상으로 보이며, 입찰/지원 조건 원문 손상 근거는 아니다. 원본 바이트가 남아있는지 별도 소스 대조가 필요하다.

| 범위 | 파일/레코드 수 | U+FFFD 레코드 / 코드포인트 | 잘못된 UTF-8 파일/행 |
|---|---:|---:|---:|
| BIZINFO raw | 14 files / 14 file units | 0 / 0 | 0 / 0 |
| BIZINFO parsed | 3 files / 3,949 JSONL records | 0 / 0 | 0 / 0 |
| K-Startup raw + processed | 22 files / 103,812 JSONL records or file units | 0 / 0 | 0 / 0 |
| common cleaned 20261124 | 5 files / 38,066 JSONL records or file units | 0 / 0 | 0 / 0 |
| normalized 20261124 | 5 files / 45,064 JSONL records or file units | 0 / 0 | 0 / 0 |
| normalized 20261125_g2b | 4 files / 230,128 records or file units | 1 / 2 | 0 / 0 |
| condition input + candidate/logic diagnostics | 32 files / 224,446 records or file units | 0 / 0 | 0 / 0 |
| goldset review packages | 16 files / 108 records or file units | 0 / 0 | 0 / 0 |
| **합계** | **101 files / 645,587 records or file units** | **1 / 2** | **0 / 0** |

이 수치는 파일이 포함한 모든 자유 텍스트와 식별 필드에 대해 U+FFFD를 검사한 결과다. 완전히 유효한 UTF-8로 잘못 디코딩된 텍스트는 U+FFFD가 없을 수 있으므로 표본 계보를 별도로 비교했다. 117546 표본에서는 raw→parsed→cleaned→input→review 텍스트가 일치한다. 전체 원천 데이터의 의미 정확성을 전수 보증하는 검사는 아니며, 확정 손상으로 식별된 조건 원문 공고는 0건이다.

기존 개발용 80개 / 검수 패킷 30개 / 평가용 20개에 대해서도 저장 바이트 기준 확인 결과 조건 원문 손상은 0건이다. 평가용 20건은 무결성 확인만 수행했고 의미 분석, 추출 생성 및 조건 검토는 하지 않았다.

## 표본과 기존 파이프라인 영향

- `representative_samples.jsonl`: DEVELOPMENT 80건(기업마당 40, K-Startup 40), EVALUATION 20건(기업마당 10, K-Startup 10). 이 20건은 아래 의미·후보 분석에서 제외했다.
- 20261125 gold review 패킷의 DEVELOPMENT는 별도 기존 검수 대상 목록 30건으로, BIZINFO 28건 / KSTARTUP 2건이다. `build_condition_gold_review.py`는 80건 중 `dev_existing`에 미리 저장된 30개 ID를 선택해 검수 패킷을 만들며, 출처별 재균형을 하지 않는다. 따라서 28/2 편중은 이 선행 30개 선택 목록에서 이미 형성된 편중이며, UTF-8 손상에 의한 표본 선정으로 볼 증거가 없다. 표본은 변경하지 않았다.
- 개발용 표본 30개 중 추출 후보 행이 없는 공고 10개(기준선), 개선 결과 기준 9개다. 표본의 원문은 유효하므로 파일 인코딩으로 이 누락을 설명할 수 없다. 원인 연관성은 여기서 결론 내리지 않는다.
- 검수 패킷의 논리 입력은 30건 모두 `logic_status=UNRESOLVED`로 표시된다. 이는 논리 검토 상태이지 원문 손상의 증거가 아니다.
- 조건 후보 84행(기준선), 98행(개선본)은 모두 `UNREVIEWED`다. 이 진단은 파이프라인 데이터 및 기준선을 수정하지 않았고, gold를 승인하거나 성능 점수를 내지 않았다.
- 앞서 언급된 “미추출 26건 / 논리 미확정 18건”의 모집단 정의가 이 진단의 검수 30건과 다르다. 정확한 ID 집합 정의가 없는 상태에서 그 수치를 전체 30/80과 교차 집계하지 않았다.

## 인코딩 구현 검토

- BIZINFO collector는 `urlopen(...).read().decode("utf-8")` 후 UTF-8 JSON 저장. 이 실행의 원시 페이지는 strict UTF-8 유효하다. 응답 헤더/charset은 보존하지 않는다.
- K-Startup collector도 `read().decode("utf-8")` 후 UTF-8 JSONL 저장한다. 이번 저장 파일 검사에서 오류는 확인되지 않았다.
- parser, normalizer, condition-input, extractor, logic, review builder는 UTF-8 읽기/쓰기를 명시하며 JSON 직렬화는 `ensure_ascii=False` 사용.
- `preprocess_notices.py`의 첨부 텍스트 읽기 한 곳에 `errors="ignore"`, OLE `PrvText` 디코딩에 `errors="replace"`가 있다. 이 경로는 첨부에서 발췌한 텍스트에만 적용될 수 있고, 확인한 117546의 API 조건 원문에는 적용되지 않았다. 이 파일만으로 실제 데이터 손상 범위가 있다고 볼 수 없다.
- 주요 JSON 원문 처리 경로에서 `errors="ignore"/"replace"` 사용은 확인하지 못했다. 조건 데이터 경로에 중복 인코딩/디코딩 징후도 발견하지 못했다.

## 복구 분류

| 유형 | 현재 판단 |
|---|---|
| DISPLAY_ONLY | `BIZINFO:PBLN_000000000117546`은 이 유형. 셸 표시를 피하려면 UTF-8 terminal 또는 Python `ascii(text)`/JSON escaping으로 확인 |
| DECODING_RECOVERABLE | 조건 원문 사례는 식별되지 않음 |
| RAW_SOURCE_AVAILABLE | 117546을 포함한 BIZINFO API raw pages는 존재하고 정상 |
| RECOLLECTION_REQUIRED | 조건 원문에 대해서는 해당 없음. G2B 파일명 필드는 원본 검토 후 결정 |
| UNRECOVERABLE | 조건 원문에서 식별되지 않음 |
| NEEDS_REVIEW | G2B 문서명 U+FFFD 2개는 원본 소스 대조 필요 |

## 최소 후속 계획

1. 파일 손상 수정이나 재수집 없이 저장 데이터를 재사용한다. 117546 검수 작업은 현재 정상 조건 원문을 기준으로 재개할 수 있다.
2. 콘솔에서 한국어를 확인할 때 UTF-8 출력으로 설정하고, 원문 비교는 원본 JSON에서 동일 notice ID/필드의 값을 비교한다.
3. 첨부 추출의 `ignore`/`replace` 경로는 향후 별도 부록 텍스트 품질 점검에서 교체 여부를 결정한다. 이번 진단에서는 코드나 데이터를 수정하지 않는다.
4. G2B 문서 파일명은 사용 가능한 원본 데이터와 대조한다. 해당 필드 수정은 별도 승인된 복구 작업으로 수행한다.
5. 추후 원문 검수 패킷의 대상 5건을 만들 때 현재 스키마와 기존 도구를 재사용한다. 정답 생성 전 원문 완전성과 출처를 사람이 확인한다.

## 재현 범위 및 한계

진단 중 데이터 파일은 읽기만 했다. 신규 API 호출, 평가 데이터 의미 분석, 추출기 실행, DB 변경, 정답 작성 및 커밋은 하지 않았다. 집계 파일 수준 인코딩 검사는 JSONL은 행별, JSON/CSV는 파일 단위 strict UTF-8로 수행했다. 파일별 상세 검사 통계 CSV는 `data/diagnostics/condition_encoding_file_stats_20261126.csv`에 둔다.
