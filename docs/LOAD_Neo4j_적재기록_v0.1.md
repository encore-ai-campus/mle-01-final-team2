# Neo4j 적재 기록 (v0.1)

> 지원각 · 근거 it(2팀) · 2026-11-25 · 대상 인스턴스: 우리 전용 Aura(`4fcaaade`)
> 이 문서는 **무엇을 어떤 순서로 올렸고, 어떻게 다시 올리고, 올린 뒤 무엇을 확인했는지**를 남긴다. 수치는 2026-11-25에 DB를 읽기 전용으로 조회해 센 값이다. 적재 코드는 PR #14·#15에 있다.

## 1. 요약

| 항목 | 내용 |
|---|---|
| 적재 상태 | **구조화 필드로 만든 요건까지 적재 완료.** 노드 31,506개, 관계 55,903개, 유일 제약 10개 |
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
