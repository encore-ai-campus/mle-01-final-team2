# Neo4j 적재 기록 (v0.1)

> 지원각 · 근거 it(2팀) · 2026-11-25 · 대상 인스턴스: 우리 전용 Aura(`4fcaaade`)
> 이 문서는 **무엇을 어떤 순서로 올렸고, 어떻게 다시 올리고, 올린 뒤 무엇을 확인했는지**를 남긴다. 수치는 2026-11-25에 DB를 읽기 전용으로 조회해 센 값이다. 적재 코드는 PR #14·#15에 있다.

## 1. 요약

| 항목 | 내용 |
|---|---|
| 적재 상태 | **구조화 필드로 만든 요건까지 적재 완료.** 노드 31,506개, 관계 55,903개, 유일 제약 10개. 2026-11-26 추가 법령·정의·개념 적재 후 노드 32,605개, 관계 56,995개(§추가 적재) |
| 적재 전 상태 | 노드 0, 관계 0, 제약 0(신규 인스턴스). Supabase도 비어 있음(공개 테이블·계정·버킷 0) |
| 적재 방법 | `tools/load_graph_neo4j.py`. `MERGE` 기반이라 여러 번 실행해도 같은 결과이고 `DELETE`가 없다. 기본은 dry-run |
| 적재하지 않은 것 | 본문에서 읽은 조건 17,253건(검수 전), 공고의 법령 인용 `CITES` 543건, 정의의 판정 기준(`rule_json`) |
| 소요 | 단계별 약 8초 안팎. 전체를 다시 올려도 1분 미만 |

## 2. 입력과 생성

| 입력 | 만드는 법 | 비고 |
|---|---|---|
| `data/graph/nodes.jsonl`, `edges.jsonl` | `python tools/graphrag/build.py export`(약 6초) | `.gitignore` 대상. 정리층(`data/cleaned/20261124`)과 개념·법령 사전에서 만든다 |
| 개념·법령·정의 | `tools/graphrag/concepts_laws.py`가 export에 포함 | 신청자 유형 24개·인증 7개, 법령 26종·조문 1,286·별표 40(`data/지원사업_법령/`), 법령 원문을 인용한 정의 6개 |
| 보류 목록 | `data/graph/law_citations_pending.jsonl` | 공고가 법령·조문을 인용한 543건. 요건 노드가 본문에서 만들어진 뒤에 `Requirement-[:CITES]->조문`으로 잇는다 |
| 제약 | `docs/submission/ontology/schema.cypher`의 `CREATE CONSTRAINT` | 적재 단계가 해당 레이블의 제약만 먼저 건다 |

## 3. 단계와 순서

순서는 `meta` → `laws` → `requirements`다. 뒤 단계가 앞 단계의 노드를 가리키기 때문이다.

| 단계 | 레이블 | 관계 | 선행 조건 |
|---|---|---|---|
| `meta` | Notice, Organization, SupportCategory, Concept(지역·신청자 유형·인증·특수 집단) | ANNOUNCED_BY, EXECUTED_BY, IN_SUPPORT_CATEGORY, WITHIN, MEMBER_OF, SUCCEEDED_BY, IS_A | 없음 |
| `laws` | ExternalLaw, LawArticle, LawAppendix, Definition | PART_OF, DEFINED_BY, CITES_LAW | `meta`(DEFINED_BY가 개념을 찾는다) |
| `requirements` | Requirement, Condition | HAS_REQUIREMENT, HAS_CONDITION, ABOUT | `meta`(ABOUT이 개념을 찾는다) |

2026-11-25 적재 순서: ① `meta` 중 지역 개념·공고·기관·분야(노드 6,855, 관계 11,533) → ② `meta`와 `laws` 다시(개념 27개 추가, 법령·정의 추가) → ③ `requirements`. 같은 단계를 한 번 더 실행해도 건수가 늘지 않는 것을 확인했다(멱등).

## 4. 실행 방법

사전 준비
- `.env`에 `NEO4J_URI`(`neo4j+s://<id>.databases.neo4j.io`, **`://`가 있어야 한다**), `NEO4J_USERNAME`, `NEO4J_PASSWORD`, `NEO4J_DATABASE`
- 사내망에서 인증서 오류(`self-signed certificate in certificate chain`)가 나면 `pip install truststore`(스크립트가 있으면 자동으로 쓴다)

```powershell
python tools/graphrag/build.py export                          # 적재 파일 생성(로컬, 약 6초)
python tools/load_graph_neo4j.py --stage all                   # dry-run: 파일 검증과 계획 출력, DB 접속 없음
python tools/load_graph_neo4j.py --stage meta --check-db       # dry-run + DB를 읽기 전용으로 조회(비어 있는지)
python tools/load_graph_neo4j.py --stage meta --apply --confirm-host <NEO4J_URI의 호스트>
python tools/load_graph_neo4j.py --stage laws --apply --allow-existing --confirm-host <호스트>
python tools/load_graph_neo4j.py --stage requirements --apply --allow-existing --confirm-host <호스트>
```

안전 장치
- `--apply`에는 접속 대상 호스트를 `--confirm-host`로 다시 입력해야 한다(다른 인스턴스에 잘못 올리는 것을 막는다).
- DB에 노드가 하나라도 있으면 중단한다. 이미 올린 단계를 이어서 올릴 때만 `--allow-existing`을 쓴다.
- 적재 후 건수 일치와 점검 쿼리 V2(순환)·V4(고아 조건)·V8(행정 상위 중복)을 자동으로 확인하고, 문제가 있으면 종료 코드 5로 끝난다.
- 노드를 모두 올린 뒤 관계를 올린다. 노드는 `MERGE (n:레이블 {키: ...})`로, 지역 개념에는 보조 레이블 `Region`을 붙인다.

### 이미 적재된 DB를 점검하거나 일부만 고칠 때 (2026-11-26 추가)

```powershell
python tools/check_graph_neo4j.py --save before.json --check-definitions   # 읽기 전용 점검 + 스냅숏 저장
python tools/load_graph_partial.py --select gold --show-changes            # dry-run: DB와 비교한 변경 내역(새로·바뀜·같음)
python tools/load_graph_partial.py --select gold --apply --confirm-host <호스트>
python tools/check_graph_neo4j.py --compare before.json                     # 적재 전후 차이
```

- `check_graph_neo4j.py`는 쓰지 않는다. 레이블·관계 건수, V0~V17, 정의·법령 점검(D1 조문 없는 정의, D2 옛 형식 링크), 개념 → 정의 → 조문 → 법령 경로 수를 본다. 0이어야 하는 점검이 실패하면 종료 코드 1이고, 알려진 값(V9 546, V15 330, V16a 34, V17 2)이 바뀌면 경고만 한다.
- `load_graph_partial.py`의 선택은 `laws`(법령·조문·별표·정의), `gold`(검수 요건 `reviewed_excerpt`와 그 조건), `sme-rule`(중소기업 `rule_json`을 기존 정의 노드에 속성으로만 붙인다. 노드가 없으면 만들지 않고 멈춘다), `ids`(정규식)다. 같은 ID를 다른 레이블이 쓰거나 관계 끝점이 선택에도 DB에도 없으면 쓰지 않는다. 지우기는 없다.
- 2026-11-26 dry-run에서 찾은 차이: 처음 적재한 정의 5개(창업기업·예비창업자·초기창업기업·청년창업기업·중장년창업기업)에 `source` 속성이 없다(파일은 `local_law_text`). `--select laws`로 맞출 수 있다(승인 전).

## 5. 적재 결과

노드 31,506개

| 종류 | 건수 | 종류 | 건수 |
|---|---:|---|---:|
| Condition | 17,366 | LawAppendix | 40 |
| Requirement | 5,900 | Concept(신청자 유형 18·인증 7·특수 집단 2) | 27 |
| Notice | 5,116 | ExternalLaw | 26 |
| Organization | 1,399 | SupportCategory | 19 |
| LawArticle | 1,286 | Definition | 6 |
| Concept:Region(지역) | 321 | | |

관계 55,903개

| 종류 | 시작 → 끝 | 건수 |
|---|---|---:|
| HAS_CONDITION | Requirement → Condition | 17,366 |
| ABOUT | Condition → Concept(신청자 유형·인증) | 14,980 |
| HAS_REQUIREMENT | Notice → Requirement | 5,900 |
| ANNOUNCED_BY | Notice → Organization | 5,116 |
| IN_SUPPORT_CATEGORY | Notice → SupportCategory | 5,116 |
| ABOUT | Condition → Region | 4,786 |
| PART_OF | LawArticle → ExternalLaw | 1,286 |
| EXECUTED_BY | Notice → Organization | 947 |
| WITHIN | Region → Region(행정 상위) | 284 |
| PART_OF | LawAppendix → ExternalLaw | 40 |
| MEMBER_OF | Region → Region(권역·묶음) | 35 |
| SUCCEEDED_BY | Region → Region(행정 분할 후계, 미검수) | 35 |
| CITES_LAW | Definition → LawArticle | 6 |
| DEFINED_BY | Concept → Definition | 4 |
| IS_A | Concept → Concept(소기업·중기업 → 중소기업) | 2 |

유일 제약 10개: `notice_id`, `org_id`, `category_id`, `concept_id`, `req_id`, `cond_id`, `law_id`, `article_id`, `appendix_id`, `def_id`.

요건 5,900개는 모두 K-Startup·기업마당 구조화 필드로 만든 `structured_only`다(`AND/assumed` 4,786, 예비창업자 허용 업력 `OR/explicit` 1,114). 조건 17,366개의 속성은 `applicant_type IN` 5,074, `region WITHIN` 4,786, `founder_age BETWEEN` 3,822, `business_age LT` 2,330, `business_age`(operator 없음) 1,354다.

## 6. 적재 후 점검 (설계서 5.4의 점검 쿼리)

| 점검 | 결과 |
|---|---|
| V1 scheme이 다른 개념 사이의 `IS_A`·`WITHIN`·`MEMBER_OF` | 0 |
| V2 `IS_A`·`WITHIN`·`MEMBER_OF` 순환 | 0 |
| V4 고아 조건 | 0 (고아 요건도 0) |
| V5 근거(`evidence`) 없는 `HAS_REQUIREMENT`·`HAS_CONDITION` | 0 |
| V8 행정 `WITHIN` 상위가 둘 이상인 지역 | 0 (`MEMBER_OF` 분리 전 32) |
| V9 `ABOUT` 없는 개념형 조건 | 546. 전부 신청 대상이 `일반기업` 하나뿐인 K-Startup 조건이다(개념이 없어 `about_pending=true`). `about_pending=false`인데 `ABOUT`이 없는 조건은 0 |
| 지역 조건이 지역이 아닌 개념을 가리킴 | 0 |
| 끝점이 없는 간선 | 0 (적재 전 파일 검증에서도 0) |
| 기관이 없는 공고 | 0 |
| 멱등성(VAL-09) | 같은 단계를 한 번 더 실행해도 노드·관계 건수 동일 |

경로 질의 확인
- 장안구 → 수원시 → 경기도 → 전국 (3 hop, `WITHIN`)
- 광주 남구 → 광주(구) (`MEMBER_OF`)
- 중소기업 → 정의 → 중소기업기본법 제2조 → 중소기업기본법 (3 hop, `DEFINED_BY`·`CITES_LAW`·`PART_OF`)
- 금천구(코드표 누락 보완 지역) 존재, 인천 중구 → 제물포구·영종구(`SUCCEEDED_BY`, `partial`)
- 성동구 사업장이 지역 조건을 충족하는 모집 중 공고 후보를 `[:WITHIN|MEMBER_OF*0..3]`로 조회

## 7. 알아 둘 점

- **공고 330건에는 요건이 없다.** 지역 조건이 없는 기업마당 공고이고 본문 요건은 아직 추출하지 않았다(`bizinfo_no_region_condition`).
- **`ABOUT` 546개가 비어 있다**(위 V9). "일반기업"은 중소기업과 같다고 볼 수 없어 개념을 만들지 않았다.
- 청년창업기업·중장년창업기업 정의는 같은 이름의 개념이 없어 `DEFINED_BY`가 없다(정의 6개 중 4개만 연결).
- 지역 후계 관계(`SUCCEEDED_BY` 35개)는 코드표의 후보 대응이며 검수 전이다.
- 적재 중 `IS_A` 관계 타입이 아직 없다는 DB 경고가 한 번 나올 수 있다. 점검 쿼리가 참조하는 이름일 뿐 문제가 아니다.
- Aura Free 한도(노드 20만, 관계 40만) 대비 노드 15.8%, 관계 14.0%다. 인스턴스 등급이 다르면 한도도 다르다.
- 삭제·초기화 스크립트는 일부러 두지 않았다. 처음부터 다시 올려야 하면 팀 합의 후 Aura 콘솔에서 인스턴스를 초기화한 뒤 위 순서로 다시 적재한다.
- `.env` 값에서 `://`가 빠지면(`neo4j+s4fcaaade...`) 모든 도구가 접속하지 못한다. 2026-11-25에 이 문제가 있어 고쳤다.

## 8. 아직 올리지 않은 것과 다음 단계

| 항목 | 이유 | 조건 |
|---|---|---|
| 본문에서 읽은 조건 17,253건 | 전부 `unreviewed`(검수 전) | 정답 라벨 파일럿 후 검수된 것만 |
| `CITES`(요건 → 조문) 543건 | 본문 요건 노드가 아직 없다 | 본문 요건 적재 후 `law_citations_pending.jsonl`로 연결 |
| 정의의 `rule_json` | 법령 원문 확인 전 | 중소기업·창업기업 정의부터 |
| 청년·중장년창업기업 개념 | 이름이 같은 개념이 없다 | 팀 결정(개념 신설 또는 근사 연결) |
| `Program`·`Track`·`Attachment` | 요건 추출 전 | 통합공고 854건이 트랙 후보 |

## 9. 변경 이력

| 일자 | 내용 |
|---|---|
| 2026-11-25 | 적재 전 정규화 정리(PR #14): 지역 코드표 318행, `MEMBER_OF` 분리, `region_source`, `TEXT_ONLY`, Condition `operator` |
| 2026-11-25 | 적재 스크립트와 1단계 적재(PR #15). 이어서 개념·법령·정의·`ABOUT`을 추가하고 `laws`·`requirements` 단계를 적재 |

## 추가 적재: 법령 18문서 (2026-11-26)

| 항목 | 값 |
|---|---|
| 대상 | 데이터명세서 v0.3의 추가 법령 9종 + 시행령 9종 = 18문서, 조문 1,039개, 별표·서식 19개 |
| 방법 | `concepts_laws.laws()`에서 18문서만 골라 `tools/load_graph_neo4j.py --stage laws --graph-dir <추가분> --apply --allow-existing`. 전체 export는 다시 하지 않았다 |
| 사전 점검 | 같은 `law_id`·`article_id`·`appendix_id`를 가진 기존 노드 0개(읽기 전용 조회). 파일 검증: 중복 0, 끝점 없는 간선 0, 시그니처 위반 0 |
| 적재 | 노드 1,076(`ExternalLaw` 18, `LawArticle` 1,039, `LawAppendix` 19), 관계 `PART_OF` 1,058. 쓰기 트랜잭션 7회, MERGE만 사용 |
| 적재 후 합계 | 노드 32,582, 관계 56,961, 유일 제약 10. `ExternalLaw` 44, `LawArticle` 2,325, `LawAppendix` 59, `PART_OF` 2,384 |
| 점검 | 법령에 안 붙은 조문·별표(V14) 0, `PART_OF` 둘 이상 0, 조문 `law_id`와 법령 불일치 0, 조문 없는 법령 0, `article_id` 중복 0 |
| 남은 것 | 정의 노드는 아래 "추가 적재: 정의 10개"에서 연결했다 |

적재 스크립트의 자체 점검은 "기대 18, 실제 44"처럼 표시한다. 기대값을 이번 묶음 건수로, 실제값을 DB 전체 건수로 비교하기 때문이며, 실제값은 기존 + 추가와 정확히 같다.

## 추가 적재: 추가 법령 정의 10개 (2026-11-26)

| 항목 | 값 |
|---|---|
| 원천 | `조문.jsonl`의 정의 조항을 글자 그대로 잘라 온 것(`concepts_laws.LAW_DEFS_V03`, `clause_text`). 호 단위는 딸린 목까지, 항 단위는 지정한 항까지 |
| 정의 | 장애인기업(장애인기업활동 촉진법 제2조 제2호), 이노비즈(중소기업 기술혁신 촉진법 제2조 제3호의2), 메인비즈(같은 법 제2조 제4호의2), 청년(청년기본법 제3조 제1호), 마을기업(마을기업법 제2조 제1호), 어업인(수산업ㆍ어촌 발전 기본법 제3조 제3호), 농업인(농업ㆍ농촌 및 식품산업 기본법 제3조 제2호), 자활기업(국민기초생활 보장법 제18조 제1항·제2항), 연구소기업(연구개발특구법 제2조 제6호), 중소기업협동조합(중소기업협동조합법 제3조 제1항) |
| 사전 점검 | 같은 `def_id` 기존 노드 0, 대상 조문 9개·개념 4개 모두 존재, 파일 검증 문제 0 |
| 적재 | `Definition` 10, `CITES_LAW` 10, `DEFINED_BY` 4 (MERGE) |
| 적재 후 합계 | 노드 32,592, 관계 56,975. `Definition` 16, `CITES_LAW` 16, `DEFINED_BY` 8 |
| 점검 | 조문에 안 붙은 정의 0, 조문을 둘 이상 인용한 정의 0, V14 = 0. 개념 → 정의 → 조문 → 법령 경로 8개 |
| 남은 것 | 마을기업·어업인·농업인·자활기업·연구소기업·중소기업협동조합은 대응 개념이 없어 `DEFINED_BY`가 없다(V17 = 8, 기존 2 포함). 공고 조건이 가리키는 개념은 아직 `예비창업자`뿐이라 새 정의는 본문 요건 적재 후 공고와 이어진다 |

## 추가 적재: 추가 법령 개념 6개 (2026-11-26)

| 항목 | 값 |
|---|---|
| 원천 | `concepts_laws.LAW_CONCEPTS_V03`. 지정·인정·등록이 있어야 성립하는 지위는 O-07에 따라 `CERTIFICATION`, 정의 기준만으로 성립하는 것은 `APPLICANT_TYPE` |
| 개념 | `CERTIFICATION:마을기업`(제11조 지정), `CERTIFICATION:자활기업`(제18조제2항 인정), `CERTIFICATION:연구소기업`(제9조의3제2항 등록), `APPLICANT_TYPE:어업인`, `APPLICANT_TYPE:농업인`, `APPLICANT_TYPE:중소기업협동조합`(협동조합 기본법의 `협동조합`과 별개) |
| 사전 점검 | 같은 `concept_id`·같은 이름의 기존 개념 0, 대상 정의 6개 존재, 파일 검증 문제 0. 공고 조건의 미매핑 선택지는 `일반기업`뿐이라 기존 `ABOUT`에는 영향 없음 |
| 적재 | `Concept` 6, `DEFINED_BY` 6 (MERGE) |
| 적재 후 합계 | 노드 32,598, 관계 56,981. `Concept` 354(신청자 유형 21·인증 10·특수 집단 2·지역 321), `DEFINED_BY` 14 |
| 점검 | V17(개념에 안 붙은 정의) 8 → 2(청년창업기업·중장년창업기업), 개념 ID 중복 0, IS_A·WITHIN 순환 0, 개념 → 정의 → 조문 → 법령 경로 14개, 고립 개념 15 → 11 |
| 남은 것 | 새 개념을 가리키는 공고 조건(`ABOUT`)은 없다. 본문·첨부 요건 적재 때 연결한다 |

## 추가 적재: 기존 법령 정의 7개 (2026-11-26)

| 항목 | 값 |
|---|---|
| 원천 | `concepts_laws.LAW_DEFS_V02`. 용어 사전에 개념은 있었지만 정의 노드가 없던 신청자 유형. 조문 원문을 글자 그대로 잘라 온다 |
| 정의 | 소상공인(소상공인기본법 제2조 제1항·제2항, 3년 유예 포함), 중견기업(중견기업법 제2조 제1호), 벤처기업(벤처기업법 제2조의2 제1항, 제2조제1항이 요건 조항을 가리킴), 여성기업·사회적기업·협동조합·1인 창조기업(각 법 제2조 제1호) |
| 사전 점검 | 같은 `def_id` 기존 0, 대상 조문 7·개념 7 존재, 대상 개념의 기존 `DEFINED_BY` 0, 기존 정의 16개 원문 해시 DB와 일치, 파일 검증 문제 0 |
| 적재 | `Definition` 7, `CITES_LAW` 7, `DEFINED_BY` 7 (MERGE) |
| 적재 후 합계 | 노드 32,605, 관계 56,995. `Definition` 23, `CITES_LAW` 23, `DEFINED_BY` 21 |
| 점검 | V17 = 2(청년창업기업·중장년창업기업), 조문 없는 정의 0, `def_id` 중복 0, 개념 → 정의 → 조문 → 법령 경로 21개, 고립 개념 11 → 5 |
| 효과 | K-Startup 신청 대상 `1인 창조기업` 조건 2,903개가 1인 창조기업법 제2조까지 이어졌다. 정의에 닿는 공고 1,252 → 3,143건(예비창업자와 겹침 1,012) |

## 수정 적재: 중소기업 정의 원문·법령 링크 (2026-11-26)

| 항목 | 값 |
|---|---|
| 원인 | 정의 검수 시트(`docs/REVIEW_법령정의_검수시트_v0.1.md`)를 만들며 찾은 두 문제. ① 중소기업 정의가 v0.1 용어 사전 문장이라 제2조 제1항 각 호(1~5호)가 `[중략]`이고 제3항(5년 유예)이 없었다. ② `ExternalLaw.source_url`이 `https://www.law.go.kr/law/{번호}` 형식이라 44개 모두 404였다 |
| 수정 | ① `concepts_laws.LAW_DEFS_V02`에 중소기업(제2조 제1항~제3항)을 넣어 조문에서 글자 그대로 자른다. ② `concepts_laws.law_url()`이 `https://www.law.go.kr/lsInfoP.do?lsiSeq={법령일련번호}`를 만든다(44개 모두 열림 확인) |
| 사전 점검 | 새 ID 0(같은 `def_id`·`law_id`만 MERGE), 파일 검증 문제 0, ExternalLaw DB 44 = 파일 44 |
| 적재 | `Definition` 1(원문 해시 `d5159658…` → `62c13e88…`, `basis_note`·`legal_term`·`source` 갱신), `CITES_LAW` 1(`article_ref` 제2조 제1항·제2항 → 제1항~제3항), `ExternalLaw` 44(`source_url`) (MERGE) |
| 적재 후 합계 | 노드 32,605, 관계 56,995(변화 없음). `Definition` 23, `CITES_LAW` 23, `DEFINED_BY` 21 |
| 점검 | 정의 23개 원문 해시 파일과 일치, 옛 형식 링크 0, 새 형식 링크 44, 조문 없는 정의 0, V17 = 2, 개념 → 정의 → 조문 → 법령 경로 21개 |
