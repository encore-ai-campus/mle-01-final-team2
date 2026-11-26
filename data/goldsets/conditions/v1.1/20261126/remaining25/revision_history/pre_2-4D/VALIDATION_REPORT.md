# 개발용 추가 검수 25건 초안 검증 보고서

- 대상: 고정 개발용 30건에서 사전 검수 5건을 제외한 기존 ID 25건. 표본 ID 변경은 없습니다.
- 출처 분포: 기업마당 13건, K-Startup 12건
- 사람 검수 자료: 5개 묶음, 묶음마다 5건이며 두 출처를 모두 포함합니다.
- 조건 초안: 72건
- JSONL 상태: 모두 UNREVIEWED / PENDING. VERIFIED 처리 0건
- 조건·논리 JSON Schema 오류: 0건
- 원문 근거 위치·논리 참조 오류: 0건
- 독립 평가 ID 중복: 0건. 평가 데이터 의미 분석, 정답 작성 및 추출은 수행하지 않았습니다.
- 기존 후보 자동 정렬 상태: PARTIAL_MATCH 29건, MATCH 4건, UNRESOLVED 1건. 정답 초안 72건 중 41건은 v1 후보 대응이 없어 누락 의심으로 표시했습니다. 자동 정렬은 사람 검수 대상이며 오류나 성능 점수로 확정하지 않았습니다.

## 원문 범위와 데이터 버전

조건 원문과 비교 후보·논리는 data/goldsets/conditions/v1/20261126_balanced/development/의 고정 v1 자료에서 가져왔습니다. 신규 v2 후보는 사용하지 않았습니다. 제공된 source_text는 조건 발췌문이므로 발췌 완전성과 공고 전체 조건 완전성을 UNKNOWN으로 유지했습니다. 공고 제목은 v1 정규화 title_summary/title_body 메타데이터에서 보완했습니다.

- 기존 v1 condition review SHA-256: 77e4c42d826781c26f5ed16699008063b9f897e50080e190308afca4ac6876ff
- 기존 v1 logic review SHA-256: 4368fb95cc5db5918641bdb4c969ccb7266ff3a15a3aba6f2538f3606090207f
- 기존 v1 candidate_refs SHA-256: 5765dad05de72b8a44875353495e12224704da3f5b0067b955e1fb5e4b5c06e3
- 신규 초안 condition_review.jsonl SHA-256: a721dbee6ecd459d17371500987a21a35e29242cc9b97d7e1d1d0a47b2c1f304
- 신규 초안 logic_review.jsonl SHA-256: 1d6f648d9c43089f2ebd616595e842ca1b189a245c72e63bf37e454206ca85f5

## 의미 미확정으로 남긴 항목

- BIZINFO:PBLN_000000000119490: 채용 후 조건의 적용·평가 시점
- BIZINFO:PBLN_000000000125345: 70%/30%의 의미와 대상 조직 유형의 연결
- BIZINFO:PBLN_000000000126715: 국내기업에 한정된 업력·연구소 요건의 적용 범위
- KSTARTUP:177506: 민간기업만 적용되는 신용등급 조건의 논리 범위
- KSTARTUP:176387: 2년 업력의 분기 적용 및 대상 산업과 자격 분기의 연결
- KSTARTUP:179386: 중점분야의 필수 자격 여부
- KSTARTUP:177447: 병역 기간별 연령 예외의 효과는 UNKNOWN으로 두고 기본 연령 자격과 분리했습니다.
- KSTARTUP:177051: 설립일 각주 범위는 업력 조건의 보조 근거로 연결해 별도 중복 조건으로 세지 않았습니다.
- 법령·상세 공고문에만 있는 세부 자격은 추론하지 않았습니다. 정성 문구의 존재를 충족으로 판단하지 않았습니다.

FALSE_POSITIVE는 자동 확정하지 않았으며 대응이 불명확한 기존 후보는 UNRESOLVED로 남겼습니다. 원문 근거는 유니코드 코드포인트 위치와 문자열을 대조했습니다.

## 검증 결과

- v1.1 조건·논리 스키마, 참조, 근거 범위, 기존 30건 표본 유지, 평가 표본과의 비중복, CSV·Markdown 동기화를 확인했습니다.
- 	ests.test_condition_gold_v11: 8개 통과. 기존 v1.1 스키마·의미 계약 테스트이며, 25건의 사람 승인이나 성능 평가를 의미하지 않습니다.
- Precision/Recall/F1 및 전체 신청 가능 판정 점수는 계산하지 않았습니다. v1.1 의미 평가기는 아직 미구현입니다.

## 산출물

- condition_review.jsonl, logic_review.jsonl
- 기존 검수 열을 보존하고 v1.1 의미 필드를 추가한 condition_review.csv, logic_review.csv
- emaining25_selection.csv, difference_report.csv
- HUMAN_REVIEW_REMAINING25_BUNDLE1.md–HUMAN_REVIEW_REMAINING25_BUNDLE5.md

모든 파일은 사람 검수용 초안입니다. 승인·수정 의견을 기다립니다.

