# K-Startup 전체 데이터 품질 보고서

| 지표 | 결과 |
|---|---:|
| 입력 공고 | 3819 |
| 처리 성공 | 3819 (100.00%) |
| 처리 실패 | 0 |
| 고유 ID 입력/출력 | 3819/3819 |
| API 원문 필드 키 누락 | 0 |
| 중복 ID/누락 ID | 0/0 |
| 최근 1년 범위 밖 | 0 |
| 시작일 오류/결측 | 0 |
| 종료일 오류/결측 | 0 |
| 시작일>종료일 | 0 |
| published_date 비null/date_unverified | 0/3819 |

- 조건 원문 후보 건수: {"region":3819,"business_age":3819,"eligibility_target":3819,"company_type":195,"industry":15,"representative_age":3819,"revenue":81,"employment":18,"exclusion":82,"support_amount":555,"evaluation_criteria":3819,"participation_restriction":0}. 후보량은 정확도가 아닙니다.
- 조건 상태: needs_review 27945, verified 0, not_found 18231, extraction_failed 0.
- 청크 26733; 중복 ID 0; 고아 청크 0; 원문 근거 연결 26733/26733; 정규화 혼입 0.
- 개인정보 마스킹: 이메일 0, 전화 41, 명시적 담당자 이름 49; 마스킹 후 잔존 이메일/전화 0/0.
- 문의/담당자 라벨 포함 공고 123건은 이름 자동 탐지 한계로 수동 확인 대상입니다.
- 조건 출처 및 근거 연결 24208/46176; not_found는 근거 텍스트가 비어 있을 수 있습니다.

## 제한

자동 추출 조건은 검색 청크에 넣지 않았으며 verified 조건은 없습니다. 담당자명 자동 탐지는 불완전할 수 있습니다. 원본 후보 JSONL은 변경하지 않았습니다.
