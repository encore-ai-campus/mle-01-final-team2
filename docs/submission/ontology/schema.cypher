// 도메인 온톨로지 설계서 v0.2 Neo4j 스키마 초안 (이 파일은 실행하지 않았다)
// 출처: 설계서 §8(스키마·예시), §5.4(점검 쿼리), §7(경로 쿼리). 적재 대상 인스턴스(공용 Aura)가 정해지기 전에는 실행하지 않는다.
// 적재 입력: data/graph/nodes.jsonl, edges.jsonl (tools/graphrag/build.py export, 로컬 전용)

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

// 질의 예시: 사용자 개념에서 조건 개념까지 최대 3 hop
MATCH p = (u:Concept {concept_id:$user_concept})-[:IS_A|WITHIN*0..3]->(t:Concept {concept_id:$target})
RETURN [x IN nodes(p) | x.label] AS route, length(p) AS hops ORDER BY hops LIMIT 1;

// 점검 쿼리: 모두 0이어야 한다 (적재 후 실행)
// V1 scheme 사이 간선
MATCH (a:Concept)-[r:IS_A|WITHIN]->(b:Concept)
WHERE a.scheme <> b.scheme AND NOT (a.scheme = 'ZONE' AND b.scheme = 'REGION')
RETURN count(r) AS cross_scheme;
// V2 순환
MATCH p = (a:Concept)-[:IS_A|WITHIN*1..6]->(a) RETURN count(p) AS cycles;
// V3 금지된 방향
MATCH ()-[r:HAS_SUBREGION]->() RETURN count(r) AS banned_direction;
// V4 고아 조건
MATCH (c:Condition) WHERE NOT ( ()-[:HAS_CONDITION]->(c) OR ()-[:HAS_CHILD]->(c) ) RETURN count(c) AS orphan_conditions;
// V5 근거 없는 간선
MATCH ()-[r:HAS_REQUIREMENT|HAS_CONDITION|HAS_CHILD]->() WHERE r.evidence IS NULL RETURN count(r) AS no_evidence;
// V6 그룹 중첩 3단 초과 (요건 아래 HAS_CHILD 사슬이 4 이상)
MATCH p = (:Requirement)-[:HAS_CONDITION]->(:Condition)-[:HAS_CHILD*4..]->(:Condition) RETURN count(p) AS too_deep;
// V7 SUPERSEDES 방향(새 버전이 이전 버전을 대체: 새.version > 이전.version)
MATCH (n:Notice)-[:SUPERSEDES]->(o:Notice) WHERE n = o OR n.version <= o.version RETURN count(*) AS bad_supersedes;

// P-4 요건 트리 한 번에 읽기: 공고 → (트랙) → 요건 → 조건 → 하위 조건
MATCH (n:Notice {notice_id: $id})-[:HAS_TRACK*0..1]->(x)-[:HAS_REQUIREMENT]->(r:Requirement)-[:HAS_CONDITION]->(c:Condition)
OPTIONAL MATCH (c)-[:HAS_CHILD*1..3]->(d:Condition)
RETURN x, r, c, collect(d) AS children;

// 추가 인덱스(검색·필터용)
CREATE INDEX notice_source IF NOT EXISTS FOR (n:Notice) ON (n.source_system);
CREATE INDEX notice_open   IF NOT EXISTS FOR (n:Notice) ON (n.is_open);
CREATE INDEX concept_scheme IF NOT EXISTS FOR (k:Concept) ON (k.scheme);
// 점검 쿼리는 위 5.4 블록(V1~V7)에 있다
