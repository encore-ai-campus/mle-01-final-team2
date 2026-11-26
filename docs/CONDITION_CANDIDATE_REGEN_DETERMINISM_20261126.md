# `candidate_refs.jsonl` 재생성 결정성 회귀 진단 (2026-11-26)

## 결론

실패 테스트는 `tests/test_condition_inputs.py::ConditionInputTests.test_deterministic_recreation`이다. 단독 실행에서도 실패했다. 현재 입력으로 독립 임시 경로 3곳에 생성한 결과는 모두 같은 SHA-256이므로 생성기는 **현재 입력에 대해 결정적**이다. 기존 산출물은 과거 입력으로 생성되었고, 그 입력의 기록된 SHA-256이 현재 파일과 다르다. 기존 입력 자체의 의미가 달라진 사례이므로 기준선이나 생성기를 임의로 수정하지 않았다. 회귀 테스트는 여전히 실패하며 이 건은 **BLOCKER**다.

## 입력과 생성 시점

| 항목 | 기존 `analysis_report.json` 기록 | 현재 디스크 SHA-256 |
|---|---|---|
| 통합 정규화 `notices.jsonl` | `2cbcf09df66f8ba2c2c906451b228dad18ef0b562ed4ac9ad7e2d4042cc5a901` | 동일 |
| 통합 정규화 `chunks.jsonl` | `cdce6d9c01b4ad686adef0bbca0b7fcc9f2e27a8d552a70d6ba2ee36fda5abe7` | 동일 |
| 기존 값 정규화 후보 `data/normalized/20261124/notices_normalized.jsonl` | `c47bccc38ee373f756481a93e68e1a123a24d31f04ed1b4f198d3647930ac2e8` | `31452b47a592744245b2953ed4cf544567f771dc3f0868e54ae4215da59886e2` |
| K-Startup 후보 `kstartup_conditions.jsonl` | `9651c99316cdde2b818a63edad016d281895e13583dd9d24ac950dce4e614a09` | 동일 |

기준선 `candidate_refs.jsonl`과 `analysis_report.json`은 11월 25일 작성되었다. 현재 기존 값 정규화 후보 파일은 11월 26일 갱신되었다. 현재 파일의 CRLF를 LF로 바꾸면 SHA-256이 `32540993bc9fcfb8406782c916da480b6472a153ae2f1d461d94052baa2cfa73`으로, 현재 Git HEAD의 내용과 일치한다. 이 역시 기준선에 기록된 `c47b...`와 다르다. Git의 확인 가능한 이전 두 버전의 SHA-256(`325409...`, `6dfbae...`)에도 기록된 `c47b...`와 같은 바이트 원본은 없다. 따라서 당시 입력의 정확한 원본은 현재 확보된 Git 이력에서 찾지 못했다.

## 기존 파일과 재생성 파일 비교

| 검사 | 기존 기준선 | 임시 재생성 1·2·3회 |
|---|---:|---:|
| 바이트 | 11,795,783 | 11,823,288 (세 번 동일) |
| SHA-256 | `5765dad05de72b8a44875353495e12224704da3f5b0067b955e1fb5e4b5c06e3` | `f20acf5599785e4d3e9c7224359ba41e11a5ae01f867108470798064f4d1b51c` (세 번 동일) |
| 레코드 / 고유 후보 ID | 17,211 / 17,211 | 17,253 / 17,253 |
| 중복 후보 ID | 0 | 0 |
| UTF-8 BOM / CRLF | 없음 / 0 | 없음 / 0 |
| LF 개수 / 마지막 개행 | 17,211 / 있음 | 17,253 / 있음 |
| JSON 키 구성 | 15개 키의 동일한 구성 | 동일 |

기존 ID 232개가 현재 재생성 파일에 없고, 신규 ID 274개가 있다. 공통 ID의 레코드 내용 변경은 0건이다. ID 순서는 같지 않지만 이는 목록의 추가·교체에 따른 결과다. 최초 바이트 차이 위치는 176,869이다. 다른 생성 산출물 중 `dispositions.jsonl`, `g2b_deferred_samples.jsonl`, `kstartup_candidate_audit.jsonl`, `representative_samples.jsonl`은 기존과 재생성 해시가 같다. `extraction_inputs.jsonl`은 후보 참조 목록 변화로 해시가 다르다.

원본 근거 위치·문자열·정규화 값과 현재 후보를 묶어 비교하면 기존 17,211건 모두 현재 입력에 대응한다. 이 중 232건은 속성만 `company_size`에서 `certification`으로 바뀌어, 속성을 ID에 포함하는 `candidate_ref()` 규칙상 ID가 달라졌다. 지역 `ELIGIBILITY` 후보 42건이 28개 공고에 추가되었다. 후보 ID 누락 또는 내용 손상으로 단정할 증거는 없다. 기존 232건의 원문 근거 문자열과 위치는 현재 대응 사실과 같다. 신규 42건은 과거 기준선에 대응 후보가 없으므로 과거 원문 참조와의 일치 여부를 확정할 수 없다.

## 원인 분류와 조치

주원인은 **INPUT_DATA_CHANGE**다. 그 결과 **RECORD_CONTENT_DIFFERENCE**(속성 재분류 및 42건 추가), **CANDIDATE_ID_DIFFERENCE**, **RECORD_ORDER_DIFFERENCE**가 발생했다. 현재 입력 파일의 CRLF는 Git 저장 내용과의 바이트 차이를 설명하지만, 레코드 의미 차이와 후보 기준선 불일치의 원인은 아니다. 후보 출력 자체의 BOM·개행·JSON 키 구성 차이는 없다. 단독 테스트와 전체 테스트에서 같은 실패가 발생하므로 **TEST_ISOLATION_FAILURE** 증거는 없다. v1.1 변경 파일은 이 생성기의 입력·ID 함수·정렬·직렬화 경로를 수정하지 않았으며, 기준선보다 뒤에 갱신된 기존 값 정규화 후보가 직접 원인이다.

기존 후보 ID 생성 규칙, 기존 후보 레코드, 기대 해시, 입력 스냅샷, 테스트를 변경하지 않았다. 현재 입력으로 기존 기준선의 SHA-256을 재현할 수 없으며, 기준선 생성 당시의 정확한 입력 원본이 없으므로 요청 조건에 따라 임의 복원이나 테스트 완화도 하지 않았다. **기존 해시와의 일치 및 전체 회귀 테스트 통과는 미달성**이다. 후속으로 당시 입력 원본을 찾아 SHA-256을 확인하거나, 입력 변경과 기준선 갱신을 별도 승인 범위에서 함께 검토해야 한다.

단독 테스트: 1개 실행, 같은 해시 불일치로 실패. 전체 테스트: **93개 실행, 92개 통과, 동일한 1개 실패**. 기존 92개에 앞선 v1.1 작업에서 추가된 새 테스트 1개가 포함되어 총 93개다. 실패가 단독·전체에서 일치하므로 테스트 순서나 공유 상태가 주원인이라는 근거는 없다.

기계 비교 세부값: `data/diagnostics/condition_candidate_refs_20261126/comparison.json`, `semantic_diff.json`, `field_diff.json`. 임시 재생성 파일은 기준선 디렉터리에 쓰지 않고 테스트 종료 후 제거했다.
