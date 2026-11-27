// 도메인 온톨로지 설계서 v0.4 · 그래프 스키마 정의서 v0.2 Neo4j 스키마 (2026-11-27 갱신)
// 출처: 설계서 §8(스키마·예시), §5.4(점검 쿼리), §7(경로 쿼리), 그래프 스키마 정의서 부록 A.
// 제약은 tools/sync_graph_neo4j.py가 이 파일의 CREATE CONSTRAINT 줄을 읽어 적재 전에 건다(Aura에 적용됨, 2026-11-25).
// 적재 입력: data/graph/nodes.jsonl, edges.jsonl (tools/graphrag/build.py export로 다시 만든다)
// 아래 MERGE 예시는 구조 설명용이다. 실제 적재는 적재 스크립트가 한다.

// 제약: 적재 전에 먼저 건다
CREATE CONSTRAINT notice_id   IF NOT EXISTS FOR (n:Notice)       REQUIRE n.notice_id IS UNIQUE;
CREATE CONSTRAINT org_id      IF NOT EXISTS FOR (o:Organization) REQUIRE o.org_id IS UNIQUE;
CREATE CONSTRAINT concept_id  IF NOT EXISTS FOR (k:Concept)      REQUIRE k.concept_id IS UNIQUE;
CREATE CONSTRAINT req_id      IF NOT EXISTS FOR (r:Requirement)  REQUIRE r.req_id IS UNIQUE;
CREATE CONSTRAINT cond_id     IF NOT EXISTS FOR (c:Condition)    REQUIRE c.cond_id IS UNIQUE;
CREATE CONSTRAINT def_id      IF NOT EXISTS FOR (d:Definition)   REQUIRE d.def_id IS UNIQUE;
CREATE CONSTRAINT law_id      IF NOT EXISTS FOR (l:ExternalLaw)  REQUIRE l.law_id IS UNIQUE;
CREATE CONSTRAINT track_id    IF NOT EXISTS FOR (t:Track)        REQUIRE t.track_id IS UNIQUE;
CREATE CONSTRAINT attach_id   IF NOT EXISTS FOR (a:Attachment)   REQUIRE a.attachment_id IS UNIQUE;
CREATE CONSTRAINT program_id  IF NOT EXISTS FOR (p:Program)      REQUIRE p.program_id IS UNIQUE;
CREATE CONSTRAINT category_id IF NOT EXISTS FOR (s:SupportCategory) REQUIRE s.category_id IS UNIQUE;
CREATE CONSTRAINT article_id  IF NOT EXISTS FOR (a:LawArticle)   REQUIRE a.article_id IS UNIQUE;
CREATE CONSTRAINT appendix_id IF NOT EXISTS FOR (a:LawAppendix)  REQUIRE a.appendix_id IS UNIQUE;
// 속성 존재·값 목록 제약(예: Requirement.kind IN [...])은 인스턴스 종류에 따라 걸 수 없을 수 있어 §5.4 점검 쿼리로 대신한다

// 개념 층: 시군구 → 시도 (하위→상위)
MERGE (sido:Concept:Region {concept_id:'REGION:1100000000'})
  SET sido.scheme='REGION', sido.label='서울특별시', sido.code_version='20260701';
MERGE (gu:Concept:Region {concept_id:'REGION:1120000000'})
  SET gu.scheme='REGION', gu.label='성동구', gu.code_version='20260701';
MERGE (gu)-[:WITHIN {source_system:'MOIS_KIKcd_B'}]->(sido);

// 권역 묶음(H12): 공고가 정의한 경상권, 근거 공고와 구성 시도를 기록
MERGE (grp:Concept {concept_id:'REGION_GROUP:GYEONGSANG'})
  SET grp.scheme='REGION', grp.label='경상권', grp.kind='GROUP', grp.defined_in='KSTARTUP:179834', grp.reviewed=false;
// 구성 시도: 부산·대구·울산·경남·경북 (코드표에서 코드 확인 후 연결)
MERGE (dg:Concept:Region {concept_id:'REGION:2700000000'});
MERGE (dg)-[:MEMBER_OF {basis:'공고 본문 정의'}]->(grp);

// 메타 층 예시
MERGE (n:Notice {notice_id:'KSTARTUP:179839'})
  SET n.source_system='KSTARTUP', n.is_latest=true, n.version=1;

// 요건 층 예시(T-01, 검수 전 가설)
MERGE (nb:Notice {notice_id:'BIZINFO:PBLN_000000000119999'})
  SET nb.source_system='BIZINFO', nb.is_latest=true, nb.version=1;
MERGE (r:Requirement {req_id:'BIZINFO:PBLN_000000000119999@v1#R1'})
  SET r.kind='ELIGIBILITY', r.logic='AND', r.logic_basis='assumed', r.status='parsed',
      r.source_sentence='초격차 분야 업력 7년 이내 창업기업(공고일 기준)';
MERGE (nb)-[:HAS_REQUIREMENT {evidence:r.source_sentence, source:'bsnsSumryCn'}]->(r);
MERGE (c:Condition {cond_id:r.req_id + '#C1'})
  SET c.attribute='business_age', c.operator='LTE', c.value='{"value":7,"unit":"YEAR"}',
      c.ref_date_kind='NOTICE_DATE', c.evidence_source='API', c.reviewed=false;
MERGE (r)-[:HAS_CONDITION {evidence:r.source_sentence, source:'bsnsSumryCn'}]->(c);

// 그룹 조건 예시(§4.6 예시 1, 검수 전 가설): R1 = OR{ G1 = AND{지역, 업력}, 본사 이전 계획 }
MERGE (nk:Notice {notice_id:'BIZINFO:PBLN_000000000120707'})
  SET nk.source_system='BIZINFO', nk.is_latest=true, nk.version=1;
MERGE (rk:Requirement {req_id:'BIZINFO:PBLN_000000000120707@v1#R1'})
  SET rk.kind='ELIGIBILITY', rk.logic='OR', rk.logic_basis='explicit', rk.status='parsed';
MERGE (nk)-[:HAS_REQUIREMENT {evidence:'구미 소재 창업기업 중 업력 7년 이내 창업기업 (신청일 기준) / 구미(본사)로 이전 계획 기업', source:'bsnsSumryCn'}]->(rk);
MERGE (g1:Condition {cond_id:rk.req_id + '#G1'}) SET g1.cond_type='GROUP', g1.logic='AND';
MERGE (rk)-[:HAS_CONDITION {evidence:'구미 소재 창업기업 중 업력 7년 이내 창업기업 (신청일 기준)', source:'bsnsSumryCn'}]->(g1);
MERGE (c1:Condition {cond_id:rk.req_id + '#C1'}) SET c1.cond_type='ATOM', c1.attribute='region', c1.operator='WITHIN', c1.value='{"label":"구미"}';
MERGE (g1)-[:HAS_CHILD {evidence:'구미 소재', source:'bsnsSumryCn'}]->(c1);
MERGE (c2:Condition {cond_id:rk.req_id + '#C2'}) SET c2.cond_type='ATOM', c2.attribute='business_age', c2.operator='LTE', c2.value='{"value":7,"unit":"YEAR"}', c2.ref_date_kind='OTHER';
MERGE (g1)-[:HAS_CHILD {evidence:'업력 7년 이내 창업기업 (신청일 기준)', source:'bsnsSumryCn'}]->(c2);

// P-1 지역 포함: 사용자 지역에서 조건 지역까지 최대 3 hop (SUCCEEDED_BY는 따라가지 않는다)
MATCH p = (u:Concept {concept_id:$user_region})-[:WITHIN|MEMBER_OF*0..3]->(t:Concept {concept_id:$target})
RETURN [x IN nodes(p) | x.label] AS route, length(p) AS hops ORDER BY hops LIMIT 1;
// P-2 종류 포함: 사용자 유형에서 조건 유형까지 최대 2 hop
MATCH p = (u:Concept {concept_id:$user_type})-[:IS_A*0..2]->(t:Concept {concept_id:$target})
RETURN [x IN nodes(p) | x.label] AS route, length(p) AS hops ORDER BY hops LIMIT 1;
// P-3 정의 → 법령: 조건 → 개념 → (상위 개념) → 정의 → 조문·별표 → 법령 (최대 6 hop)
MATCH p = (c:Condition {cond_id:$cond_id})-[:ABOUT]->(:Concept)-[:IS_A*0..2]->(:Concept)-[:DEFINED_BY]->(:Definition)
          -[:CITES_LAW]->(a)-[:PART_OF]->(:ExternalLaw)
RETURN [x IN nodes(p) | coalesce(x.label, x.term, x.title, x.name)] AS route, length(p) AS hops;

// 점검 쿼리 (적재 후 실행). tools/check_graph_neo4j.py의 CHECKS와 같은 쿼리다(tools/test_graph_ops.py가 일치를 확인).
// 기대값 0이 아닌 것은 알려진 값이다(바뀌면 경고). 실행 결과: docs/ontology/evidence/check_graph_neo4j_20261127.txt
// V0 키 결측·중복은 레이블마다 만든다: MATCH (n:<레이블>) RETURN count(n) - count(n.<키>) AS missing, count(n.<키>) - count(DISTINCT n.<키>) AS dup;
// V1 서로 다른 scheme 사이 WITHIN·IS_A (기대: 0)
MATCH (a:Concept)-[r:IS_A|WITHIN]->(b:Concept) WHERE a.scheme <> b.scheme AND NOT (a.scheme = 'ZONE' AND b.scheme = 'REGION') RETURN count(r) AS c;
// V2 계층 순환(IS_A·WITHIN·MEMBER_OF, 6 hop) (기대: 0)
MATCH p = (a:Concept)-[:IS_A|WITHIN|MEMBER_OF*1..6]->(a) RETURN count(p) AS c;
// V3 금지된 방향 관계(HAS_SUBREGION) (기대: 0)
MATCH ()-[r:HAS_SUBREGION]->() RETURN count(r) AS c;
// V4 고아 조건 (기대: 0)
MATCH (c:Condition) WHERE NOT ( ()-[:HAS_CONDITION]->(c) OR ()-[:HAS_CHILD]->(c) ) RETURN count(c) AS c;
// V5 근거(evidence) 없는 요건·조건 관계 (기대: 0)
MATCH ()-[r:HAS_REQUIREMENT|HAS_CONDITION|HAS_CHILD]->() WHERE r.evidence IS NULL RETURN count(r) AS c;
// V6 그룹 중첩 3단 초과 (기대: 0)
MATCH p = (:Requirement)-[:HAS_CONDITION]->(:Condition)-[:HAS_CHILD*4..]->(:Condition) RETURN count(p) AS c;
// V7 SUPERSEDES 방향 오류 (기대: 0)
MATCH (n:Notice)-[:SUPERSEDES]->(o:Notice) WHERE n = o OR n.version <= o.version RETURN count(*) AS c;
// V8 행정 WITHIN 상위가 둘 이상인 지역 (기대: 0)
MATCH (a:Concept {scheme:'REGION'})-[r:WITHIN]->(:Concept) WITH a, count(r) AS p WHERE p > 1 RETURN count(a) AS c;
// V9 ABOUT 없는 개념형 조건 (기대: 0)
MATCH (c:Condition) WHERE c.attribute IN ['region','applicant_type','company_size','industry','certification','business_type'] AND NOT (c)-[:ABOUT]->(:Concept) AND coalesce(c.about_pending, false) = false RETURN count(c) AS c;
// V9b 개념 연결 보류로 표시한 조건(about_pending, ABOUT 없음) (기대: 10, 검수 정답 v1.1의 기업 유형 8·신청자 유형 1·지역 1)
MATCH (c:Condition) WHERE c.attribute IN ['region','applicant_type','company_size','industry','certification','business_type'] AND NOT (c)-[:ABOUT]->(:Concept) AND c.about_pending = true RETURN count(c) AS c;
// V10 대칭 관계 양방향 (기대: 0)
MATCH (a:Notice)-[:SAME_AS]->(b:Notice), (b)-[:SAME_AS]->(a) RETURN count(*) AS c;
// V11 같은 쌍의 중복 HAS_CONDITION·ABOUT (기대: 0)
MATCH (a)-[r:HAS_CONDITION|ABOUT]->(b) WITH a, b, type(r) AS t, count(*) AS n WHERE n > 1 RETURN count(*) AS c;
// V12 조건 없는 요건 (기대: 0)
MATCH (r:Requirement) WHERE NOT (r)-[:HAS_CONDITION]->() RETURN count(r) AS c;
// V13 지역 조건이 지역 아닌 개념을 가리킴 (기대: 0)
MATCH (c:Condition {attribute: 'region'})-[:ABOUT]->(k) WHERE NOT k:Region RETURN count(c) AS c;
// V14 법령에 안 붙은 조문·별표 (기대: 0)
MATCH (a) WHERE (a:LawArticle OR a:LawAppendix) AND NOT (a)-[:PART_OF]->(:ExternalLaw) RETURN count(a) AS c;
// V15 요건이 하나도 없는 공고 (기대: 알려진 값 1279)
MATCH (n:Notice) WHERE NOT (n)-[:HAS_REQUIREMENT]->() RETURN count(n) AS c;
// V16 상위(WITHIN)가 없는 현행 시군구·구 (기대: 0)
MATCH (a:Region) WHERE a.level IN ['SIGUNGU', 'GU'] AND coalesce(a.status, '') <> '폐지' AND NOT (a)-[:WITHIN]->() RETURN count(a) AS c;
// V16a 상위(WITHIN)가 없는 비시도 지역(폐지 시군구 31·권역 3 포함) (기대: 알려진 값 34)
MATCH (a:Region) WHERE NOT a.level IN ['SIDO', 'NATIONWIDE'] AND NOT (a)-[:WITHIN]->() RETURN count(a) AS c;
// V17 개념에 안 붙은 정의 (기대: 알려진 값 2)
MATCH (d:Definition) WHERE NOT ()-[:DEFINED_BY]->(d) RETURN count(d) AS c;
// V20 계층 관계 끝점 위반(WITHIN: 지역·구역→지역, MEMBER_OF·SUCCEEDED_BY: 지역→지역, IS_A: 지역 아닌 개념끼리) (기대: 0)
MATCH (a)-[r:WITHIN|MEMBER_OF|SUCCEEDED_BY|IS_A]->(b) WHERE (type(r) = 'WITHIN' AND NOT (a.scheme IN ['REGION','ZONE'] AND b.scheme = 'REGION')) OR (type(r) IN ['MEMBER_OF','SUCCEEDED_BY'] AND NOT (a.scheme = 'REGION' AND b.scheme = 'REGION')) OR (type(r) = 'IS_A' AND (a:Region OR b:Region OR NOT a:Concept OR NOT b:Concept)) RETURN count(r) AS c;
// V21 자기 자신을 가리키는 계층 관계 (기대: 0)
MATCH (a)-[r:WITHIN|MEMBER_OF|SUCCEEDED_BY|IS_A]->(a) RETURN count(r) AS c;
// V22 MEMBER_OF 양쪽 모두 묶음(GROUP)이 아님(지역→묶음, 묶음→상위 지역만 허용) (기대: 0)
MATCH (a)-[r:MEMBER_OF]->(g) WHERE coalesce(a.level, '') <> 'GROUP' AND coalesce(g.level, '') <> 'GROUP' RETURN count(r) AS c;
// V23 SUCCEEDED_BY 순환(승계가 되돌아옴, 6 hop) (기대: 0)
MATCH p = (a)-[:SUCCEEDED_BY*1..6]->(a) RETURN count(p) AS c;
// V24 SUCCEEDED_BY 출발이 폐지 지역이 아님 (기대: 0)
MATCH (a)-[r:SUCCEEDED_BY]->() WHERE coalesce(a.status, '') <> '폐지' RETURN count(r) AS c;
// V25 위임 별표를 가리키는 정의 관계(Definition-CITES_LAW->LawAppendix, 검수 확인분) (기대: 알려진 값 4)
MATCH (:Definition)-[r:CITES_LAW]->(:LawAppendix) RETURN count(r) AS c;
// D1 조문·별표를 인용하지 않은 정의 (기대: 0)
MATCH (d:Definition) WHERE NOT (d)-[:CITES_LAW]->() RETURN count(d) AS c;
// D2 옛 형식 법령 링크(lsInfoP.do?lsiSeq= 아님) (기대: 0)
MATCH (l:ExternalLaw) WHERE l.source_url IS NULL OR NOT l.source_url STARTS WITH 'https://www.law.go.kr/lsInfoP.do?lsiSeq=' RETURN count(l) AS c;
// 경로 수: 개념→정의→조문→법령 경로
MATCH p = (:Concept)-[:DEFINED_BY]->(:Definition)-[:CITES_LAW]->()-[:PART_OF]->(:ExternalLaw) RETURN count(p) AS c;

// P-4 요건 트리 한 번에 읽기: 공고 → (트랙) → 요건 → 조건 → 하위 조건
MATCH (n:Notice {notice_id: $id})-[:HAS_TRACK*0..1]->(x)-[:HAS_REQUIREMENT]->(r:Requirement)-[:HAS_CONDITION]->(c:Condition)
OPTIONAL MATCH (c)-[:HAS_CHILD*1..3]->(d:Condition)
RETURN x, r, c, collect(d) AS children;

// 추가 인덱스(검색·필터용)
CREATE INDEX notice_source IF NOT EXISTS FOR (n:Notice) ON (n.source_system);
CREATE INDEX notice_open   IF NOT EXISTS FOR (n:Notice) ON (n.is_open);
CREATE INDEX concept_scheme IF NOT EXISTS FOR (k:Concept) ON (k.scheme);
// 점검 쿼리는 위 블록(V1~V25, D1·D2)에 있다
