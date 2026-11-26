# 후보 입력 변경 이력 및 기준선 복구 검증 (2026-11-26)

## 결론

**A. 기존 입력 원본 확보 및 기준선 재현 가능.** 이전 진단서 `CONDITION_CANDIDATE_REGEN_DETERMINISM_20261126.md`의 “당시 입력 원본 미확보” 결론은 이번 조사로 정정한다. Git 커밋 `afc464e`의 `data/normalized/20261124/notices_normalized.jsonl`을 Windows CRLF로 보존하면 당시 `analysis_report.json`의 입력 SHA-256과 정확히 일치한다. 임시 파일을 통해 기존 생성 코드를 실행한 `candidate_refs.jsonl`은 기존 기준선과 **바이트 단위로 일치**한다. 기준선과 현재 입력은 서로 다른 데이터 버전이다. 기존 파일은 수정하지 않았고 신규 기준선도 확정하지 않았다.

## 탐색 및 복구 근거

| 위치/검사 | 결과 |
|---|---|
| Git 커밋·브랜치 | `afc464e`(2026-11-25 11:33 +09:00)에 변경 전 값 정규화 후보가 포함됨. 현재 로컬 `main` 및 `feature/logical-structure`의 정리 전 이력도 이 객체를 참조함. |
| 후속 커밋 | `9672433`(2026-11-25 15:38 +09:00)이 지역 코드표와 인증 상태 분류 규칙을 수정하고 정규화 산출물을 재생성함. 현재 HEAD/`origin/main`은 해당 내용. |
| Git stash | 목록 비어 있음. |
| Git reflog | 정리 전·후 커밋으로 이동한 기록 확인. 복구는 도달 가능한 커밋에서 완료되어 미도달 객체 사용 불필요. |
| 기존 스냅샷·정제 이전 데이터·백업·임시 파일·manifest | `data/cleaned/20261124/`와 정규화 보고서·`analysis_report.json`의 계보 확인. 기록 해시와 맞는 별도 중복 파일은 검색 결과에 없었고, Git 커밋 객체로 원본 확보. |
| Git 포함 여부 | 변경 전 원본은 Git 추적 파일. `candidate_refs.jsonl`은 현재 작업트리에서 Git 미추적 상태이므로 기존 해시로 보존 여부를 직접 확인. |

`afc464e` Git blob(LF) SHA-256은 `6dfbae160a8a0e78053a6ca4e0b87fe871f713f2238a280cefd20487fb2d78ea`다. 이 바이트의 LF를 CRLF로 변환한 임시 파일은 13,740,940바이트이고 SHA-256이 **`c47bccc38ee373f756481a93e68e1a123a24d31f04ed1b4f198d3647930ac2e8`**로 과거 입력 기록과 같다. 현재 디스크 파일은 13,771,546바이트, SHA-256 **`31452b47a592744245b2953ed4cf544567f771dc3f0868e54ae4215da59886e2`**다. 현재 파일의 CRLF를 LF로 바꾸면 현 Git blob의 SHA-256 `32540993bc9fcfb8406782c916da480b6472a153ae2f1d461d94052baa2cfa73`과 같다. 따라서 줄바꿈 차이는 Windows 작업트리와 Git blob 사이에만 존재하며, 과거·현재 데이터의 의미 차이와는 별개다.

임시 파일은 `TemporaryDirectory`에 만들고 삭제했다. `prepare_condition_inputs.run()`의 입력 읽기와 해시 계산을 그 임시 파일로 연결하되, 출력의 `source_file` 경로 문자열은 기존 `FACTS` 경로 그대로 유지했다. 생성기 본문·설정·ID 함수는 바꾸지 않았다. 임시 출력의 `candidate_refs.jsonl`은 17,211건, 11,795,783바이트, SHA-256 **`5765dad05de72b8a44875353495e12224704da3f5b0067b955e1fb5e4b5c06e3`**로 기존 기준선과 정확히 같다. `extraction_inputs.jsonl`, `dispositions.jsonl`, `representative_samples.jsonl`, `g2b_deferred_samples.jsonl`, `kstartup_candidate_audit.jsonl`도 각각 기존 바이트 해시와 일치한다. 세부 검증은 `data/diagnostics/condition_candidate_refs_20261126/recovery_verification.json`에 있다.

## 변경 원인과 의미 검토

`9672433`의 커밋 메시지와 `docs/SUPPORT_DATA_NORMALIZATION_V1.md`는 두 변경을 의도된 정리로 기록한다. `tools/graphrag/extract_req.py`의 `CERTIFIED_STATUS` 분기가 사회적기업·여성기업·장애인기업을 `company_size IS_A`에서 `certification EXISTS`로 옮겼다. 지역 코드표 확대로 빠졌던 시군구 명칭이 `region_loc WITHIN` 후보로 들어왔다. 보고서의 전체 값 후보는 17,211건에서 17,253건으로 증가했다. **v1.1 공통 스키마 확장 코드는 이 입력 생성 경로를 수정하지 않았다.** 커밋 작성자 메타데이터는 있으나 실제 로컬 데이터 재생성 수행자는 독립적으로 확인하지 못했다.

232건의 전체 비교 목록은 `data/diagnostics/condition_candidate_refs_20261126/reclassified_232.csv`에 있다. 과거 후보 ID, 현재 후보 ID, 두 `legacy_candidate_ref`, 원문 근거와 위치, 값, 과거·현재 규칙/연산자, 자동 검토 플래그를 포함한다. 비평가용 231건은 사회적기업 131, 여성기업 79, 장애인기업 21건이며 나머지 1건은 평가용이어서 ID·참조만 기록했다. 기업 규모와 발급형 지위의 분리는 분류 축상 타당한 방향이다. 다만 원문에 우대 표현이 있는 20건, 법령 표현이 있는 58건, 제외 표현이 있는 1건은 각각 **조건 유형·법령 정의 범위·제외 범위의 사람 검수**가 필요하다. `EXISTS`가 실제 지위 충족을 뜻하는지도 별도 의미 검수 사항이다. 이 자동 검토를 사람 승인으로 보지 않는다.

신규 지역 후보 42건은 `data/diagnostics/condition_candidate_refs_20261126/new_region_42.csv`에 있다. 평가용 2건은 ID만 확인하고 근거·의미를 비공개로 두었다. 나머지 40건의 발췌문과 규칙을 잠정 분류하면 신청자 거주지/사업장 지역 후보 20, 우대 지역 문구 9, 선정 후 의무와 섞인 조건부 문맥 10, 의미 미확정 1건이다. 지원기관 소재지·사업 수행 지역·전국/지역 제한 없음으로 분류된 사례는 이번 40건에서는 0건이다. **이 수치는 자동·문맥 검토이며 실제 사람 검수 결과가 아니다.** 특히 우대 9건을 신청 필수 지역 조건으로 처리하면 안 되고, 조건부 10건은 OR 분기 및 선정 시점 의무와 분리해야 한다. 해당 원문 271건(232건 중 비평가용 231건 + 지역 40건)은 정제 원문의 해당 구간 시작 위치와 문자열이 모두 일치했다. 평가용 3건의 의미는 검사하지 않았다.

## 기존 산출물·표본 영향

| 범위 | 확인 결과 |
|---|---|
| 기존 `candidate_refs.jsonl` | 과거 버전 17,211건 및 SHA-256 그대로 보존. 현재 입력으로 새로 만들면 17,253건, SHA-256 `f20acf5599785e4d3e9c7224359ba41e11a5ae01f867108470798064f4d1b51c`. 독립 임시 생성 3회 모두 일치. |
| `extraction_inputs.jsonl` | 80건 중 변경 속성 17건(7개 공고), 신규 지역 1건(1개 공고). 변경된 후보 ID의 직접 참조 17개는 기존 입력에만 있음. 재생성 시 후보 참조 목록이 달라지므로 기존 파일을 덮어쓰지 않아야 함. |
| 개발용 검수 표본 30건 | 속성 변경 10건(2개 공고), 신규 지역 0건. |
| 사전 검수 5건 | `BIZINFO:PBLN_000000000118182`의 후보 참조 4건 해당. 정답 초안의 GOLD ID나 원문 근거를 이번 조사에서 수정하지 않음. 나머지 4건 교집합 없음. |
| 기존 추출 provenance | baseline·현재 추출 파일의 기존 참조 2개씩, improved 258개가 모두 보존된 과거 `candidate_refs.jsonl`에 존재함. 변경 대상 17개 ID는 기존 추출 provenance에 직접 나타나지 않음. |
| 기존 논리 구조·검수 JSONL | 변경된 후보 ID의 직접 참조 0개. 기존 CND/GOLD ID 구조와 논리 기준선은 변경하지 않음. 향후 새 후보 버전으로 파이프라인을 실행하면 provenance 재검토 필요. |
| 독립 평가용 20건 | ID 집합과 분할 일치. 변경 속성 후보 1개, 신규 지역 후보 2개의 ID/참조 영향만 확인. 원문 의미·정답은 분석하지 않음. |

## 권장 해결 방향과 테스트 정책

과거 입력은 재현되므로 **A 경로**를 택한다. 과거 Git blob의 CRLF 작업트리 형식을 별도 불변 `legacy` 입력 버전으로 명시하고, 기존 17,211건 기준선과 연결한다. 현재 `9672433` 입력은 17,253건의 **별도 버전 후보**로 보존한다. 현재 버전의 후보·ID·근거·우대/선정 시점 문맥은 사람 검수 전까지 확정 정답이나 기존 기준선의 대체물로 삼지 않는다. 이번 단계에서 신규 버전이나 기준선을 실제 생성·확정하지 않았다.

테스트는 (1) 과거 버전: 고정된 입력 SHA-256과 기존 후보 출력 SHA-256의 바이트 재현, (2) 현재 버전: 현재 입력 SHA-256과 독립 재생성 3회 해시 일치 및 참조·중복 검사, (3) 버전 간 차이: 232건 재분류와 42건 추가를 **별도 기대 변경 목록**으로 확인하도록 분리할 것을 제안한다. 현재 입력으로 과거 산출물과 직접 비교하는 기존 `test_deterministic_recreation`은 그대로 두었으며, 버전 경로가 명시되기 전에는 계속 실패한다. 테스트 삭제·완화·해시 갱신은 이 조사에서 수행하지 않았다.

실제 조사 자료: `data/diagnostics/condition_candidate_refs_20261126/`의 `comparison.json`, `recovery_verification.json`, `reclassified_232.csv`, `new_region_42.csv`, `impact_summary.json`, `evidence_validation.json`, `downstream_references.json`.
