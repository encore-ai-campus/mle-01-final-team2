# K-Startup 최근 1년 수집 요약

- 기준 기간: 2025-11-24 ~ 2026-11-24 (양 끝 포함)
- API reported totalCount: 30632
- 페이지 응답 행 합계: 30632
- ID 중복 제거 후 보관 레코드: 30632
- 등록일 확인 및 기간 내: 0
- 기간 외: 0
- 등록일 미확인/충돌: 30632
- 상세 페이지 성공: 0 / 0
- 첨부 다운로드 성공: 0
- API 페이지 오류: 0

## 제한 및 주의

- 공식 API 문서는 등록일 필터와 등록일 응답 필드를 명시하지 않습니다.
- 등록일 확인 불가 레코드는 접수 시작일로 대체하지 않았으며 별도 JSONL로 분리했습니다.
- PDF/HWP 텍스트 추출 및 수동 검증은 수행하지 않았습니다.

## 산출물

- `raw/kstartup_raw.jsonl`: API 원본 레코드(공개 토큰 및 연락처 패턴 제거)
- `processed/kstartup_cleaned.jsonl`: 등록일로 기간 확인된 공고만 포함
- `processed/kstartup_publication_date_unavailable.jsonl`: 등록일이 없거나 충돌하는 공고
- `processed/kstartup_conditions.jsonl`: 출처 연결 조건 필드
- `processed/kstartup_chunks.jsonl`: 검증 가능한 문서가 없어 현재 비어 있음
