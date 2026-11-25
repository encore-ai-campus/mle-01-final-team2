// 도메인 온톨로지 설계서 v0.2 Neo4j 스키마 초안 (이 파일은 실행하지 않았다)
// 출처: 설계서 §8. 적재 대상 인스턴스(공용 Aura)가 정해지기 전에는 실행하지 않는다.
// 적재 입력: data/graph/nodes.jsonl, edges.jsonl (tools/graphrag/build.py export, 로컬 전용)

// 제약: 적재 전에 먼저 건다
CREATE CONSTRAINT notice_id   IF NOT EXISTS FOR (n:Notice)       REQUIRE n.notice_id IS UNIQUE;
CREATE CONSTRAINT org_id      IF NOT EXISTS FOR (o:Organization) REQUIRE o.org_id IS UNIQUE;
CREATE CONSTRAINT concept_id  IF NOT EXISTS FOR (k:Concept)      REQUIRE k.concept_id IS UNIQUE;
CREATE CONSTRAINT req_id      IF NOT EXISTS FOR (r:Requirement)  REQUIRE r.req_id IS UNIQUE;
CREATE CONSTRAINT cond_id     IF NOT EXISTS FOR (c:Condition)    REQUIRE c.cond_id IS UNIQUE;

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
MERGE (dg)-[:WITHIN {basis:'공고 본문 정의'}]->(grp);

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

// 질의 예시: 사용자 개념에서 조건 개념까지 최대 3 hop
MATCH p = (u:Concept {concept_id:$user_concept})-[:IS_A|WITHIN*0..3]->(t:Concept {concept_id:$target})
RETURN [x IN nodes(p) | x.label] AS route, length(p) AS hops ORDER BY hops LIMIT 1;

// 추가 인덱스(검색·필터용)
CREATE INDEX notice_source IF NOT EXISTS FOR (n:Notice) ON (n.source_system);
CREATE INDEX notice_open   IF NOT EXISTS FOR (n:Notice) ON (n.is_open);
CREATE INDEX concept_scheme IF NOT EXISTS FOR (k:Concept) ON (k.scheme);
CREATE CONSTRAINT def_id   IF NOT EXISTS FOR (d:Definition)  REQUIRE d.def_id IS UNIQUE;
CREATE CONSTRAINT law_id   IF NOT EXISTS FOR (l:ExternalLaw) REQUIRE l.law_id IS UNIQUE;

// 점검 쿼리 예: WITHIN은 하위→상위이며 순환이 없어야 한다
// MATCH p=(a:Concept)-[:WITHIN*1..6]->(a) RETURN count(p) AS cycles;
