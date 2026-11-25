
## 1. K-Startup
- 지원사업 공고 엔드포인트: `https://apis.data.go.kr/B552735/kisedKstartupService01/getAnnouncementInformation01`
- 호출: GET / `serviceKey`, `page=1`, `perPage=3`, `returnType=json`
- 응답 구조(공개 구현 참조): `currentCount`, `totalCount`, `data` (공고 객체 배열). 실제 값과 타입은 수집 결과로 재검증.
- 핵심 필드:

| 필드명 | 의미 | 전처리 / 활용 |
|---|---|---|
| `pbanc_sn` | 공고 일련번호 | K-Startup 내 PK 후보, 문자열 변환 |
| `biz_pbanc_nm` | 공고명 | 제목 검색, 임베딩 |
| `pbanc_ntrp_nm` | 지원 기관 | 기관 엔티티 |
| `supt_biz_clsfc` | 지원 분야 | 범주 표준화 |
| `supt_regin` | 지원 지역 | 지역 엔티티 |
| `aply_trgt`, `aply_trgt_ctnt` | 대상, 구체적 대상 | 자격 판단 근거 |
| `biz_enyy`, `biz_trgt_age` | 업력, 연령 | 정형 조건; 자연어 파싱 필요 |
| `pbanc_rcpt_bgng_dt`, `pbanc_rcpt_end_dt` | 접수 시작·종료일 | YYYYMMDD -> 날짜 |
| `rcrt_prgs_yn` | 모집 여부 | Y/N + 접수일과 교차 검증 |
| `pbanc_ctnt` | 공고 본문 | RAG 검색용 텍스트 |
| `detl_pg_url` | 상세 페이지 | 근거 출처 링크 |

## 2. 기업마당
- API 설명: `https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi`
- 호출: GET `https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do`
- 인증: `crtfcKey` (별도 발급 필요)
- 조회 파라미터: `dataType=json` 또는 `rss`, `searchCnt`, `searchLclasId`, `hashtags`, `pageUnit`, `pageIndex`
- 응답: 최상위 `jsonArray` 객체 아래 채널 메타정보와 `item` 배열 (공식 문서 예시 기준). XML은 RSS 2.0 `rss/channel/item`.
- 대표 필드:

| 필드명 | 의미 | 전처리 / 활용 |
|---|---|---|
| `seq`, `pblancId` | 공고 ID | 기업마당 내 PK 후보 |
| `title`, `pblancNm` | 공고명 | 중복 명칭 통합 |
| `author`, `jrsdInsttNm` | 소관 기관 | 기관 엔티티 |
| `excInsttNm` | 수행 기관 | 기관 간 역할 구분 |
| `description`, `bsnsSumryCn` | 공고 개요 | HTML 제거, RAG |
| `lcategory`, `pldirSportRealmLclasCodeNm` | 분야 | 표준 분류 매핑 |
| `trgetNm` | 지원 대상 | 자격 판단 |
| `reqstDt`, `reqstBeginEndDe` | 신청 기간 | `YYYYMMDD ~ YYYYMMDD` 분리 |
| `reqstMthPapersCn` | 신청 방법 | 조건 / 절차 추출 |
| `flpthNm`, `printFlpthNm` | 첨부 문서 URL | 원문 수집·출처 보존 |
| `link`, `pblancUrl` | 공고 URL | 인용 및 링크 |
| `hashTags` | 태그 | 분류·보조 검색 |

공식 예시의 원문 제목: **착한임대인 장관 표창 신청 연장 공고** (`PBLN_000000000080236`). 해당 예시는 2022년 게시된 과거 샘플로, 현재 진행 중인 공고라는 뜻이 아님.

