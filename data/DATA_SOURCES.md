# 2팀 데이터 출처 정리 — 기업 규정 준수 검증 (온톨로지 + Multi-hop 추론)

> 작성일: 2026-11-17 · 근거: 웹 검색 결과(스니펫 수준 확인). **라이선스·필드 구성은 사용 전 각 페이지에서 직접 확인할 것.**

## 1. 법령·규정 원문 (온톨로지의 뼈대)

| 출처 | 쓸모 | 비고 |
|---|---|---|
| [국가법령정보센터 공동활용 Open API](https://law.go.kr/LSW/information.do) | 법령, 조문 단위 조회, 신구법 대비 | 공식 출처 |
| [공공데이터포털 법제처 API](https://www.data.go.kr/data/15057041/openapi.do) | 같은 API를 키 발급과 함께 사용 | 호출 예시 블로그: [velog](https://velog.io/@ryuj7338/법률-API-연동) (개인 기록, 공식 가이드로 재확인) |
| [법망 (비공식)](https://news.hada.io/topic?id=28050) | 법령 전체를 JSON으로 제공하는 에이전트용 API | HWP·PDF·표 사전 파싱. 비공식이므로 신뢰성 검증 필요 |

- "참조조문" 필드 제공 여부는 **미확인**. 없으면 조문 본문의 "제○조", "준용", "대통령령으로 정하는" 표현을 정규식+LLM으로 추출해 REFERS_TO / DELEGATES_TO 엣지를 만든다.

## 2. Hugging Face 한국어 법률 데이터

- [Yeeachan/korleg](https://huggingface.co/datasets/Yeeachan/korleg/blob/refs%2Fpr%2F2/README.md) — 법제처 수집 법령, Apache-2.0
- [woalsdnd/law.go.kr](https://huggingface.co/datasets/woalsdnd/law.go.kr) — 판례 검색용 파일, MIT
- [GyuHyeonWkdWkdMan/lawdata](https://huggingface.co/datasets/GyuHyeonWkdWkdMan/lawdata/tree/refs%2Fpr%2F2) — 법령 CSV (파일당 약 260MB)
- [scvcoder/korean-privacy-law-corpus](https://huggingface.co/datasets/scvcoder/korean-privacy-law-corpus/discussions) — 개인정보 관련 법령 말뭉치
- [lbox/kcl](https://huggingface.co/datasets/lbox/kcl/blob/main/README.md) — 법률 추론 벤치마크(283문항), **CC BY-NC 4.0(비상업)**
- [wellsa-ai/treaty-kr](https://huggingface.co/datasets/wellsa-ai/treaty-kr/discussions) — 조약 데이터(RAG 태그)

주의: 수집 시점이 달라 최신 개정이 빠졌을 수 있음 → API로 갱신.

## 3. 판결·AI Hub

- [AI Hub](https://wikidocs.net/316114) — 2026-08 독자 AI 파운데이션 모델용 데이터에 법률 추론 데이터가 포함됐다는 보도. 세부 구성 미확인 → aihub.or.kr에서 "법률/판결문/약관" 직접 검색.
- 판결문은 비실명화·이용 규제 이슈([대한변협 세미나](https://www.lawtimes.co.kr/news/articleView.html?idxno=170853)). 규정 준수 검증에는 법령·행정 지침이 우선.

## 4. 미확인 / 직접 확인 필요

- 개인정보보호위원회(pipc.go.kr) 결정례·가이드라인
- 공정위 약관 심사 결과, 금융법령정보포털(금융 약관·표준약관)
- 사내 규정 샘플은 공개 데이터가 마땅치 않음 → 공공기관 공개 규정 수집 또는 LLM 합성

## 5. 추천 도메인 구성

개인정보 보호법 → 시행령 → 고시/가이드라인 → 사내 규정 4단 계층으로 시작하면 위임·준용·예외 관계와 Multi-hop 질의("이 행위/사내 규정이 위반인가?")를 자연스럽게 설계할 수 있다.

## 6. 샘플 데이터 (합성)

`sample_data/` 폴더. **가상 법령이며 실제 조문과 무관**하다.

| 파일 | 내용 |
|---|---|
| `compliance_graph.json` | 문서 3(법·시행령·사내규정), 조문 14, 관계 13, 의무(Obligation) 7, 충돌 링크 3 |
| `qa_cases.jsonl` | Multi-hop 질의응답 6건 (위반 3, 준수 3), 추론 경로·판정 포함 |
| `load_sample.cypher` | Neo4j 제약조건, APOC 적재, Multi-hop·위반 탐지 질의 예시 |

### 온톨로지 요약
- 노드: `Document(level, level_rank)`, `Article`, `Obligation(modality, attribute, operator, value)`
- 관계: `HAS_ARTICLE`, `REFERS_TO`, `EXCEPTION_REFERS_TO`(단서), `DELEGATES_TO`(위임), `IMPLEMENTS`(하위→상위), `STATES`, `CHECKED_AGAINST`
- 내장된 위반 시나리오: 접속기록 6개월 vs 1년, 신고 96시간 vs 72시간, 제3자 제공 부서장 승인 vs 동의 필요
