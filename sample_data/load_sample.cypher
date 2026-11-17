// 샘플 데이터(compliance_graph.json)를 Neo4j에 적재하기 위한 Cypher 예시.
// 사용: Neo4j Browser에서 아래 스키마를 먼저 실행하고, compliance_graph.json을 Neo4j import 폴더에 복사한 뒤
// apoc.load.json 파트를 실행한다(APOC 필요). Python Driver로 적재할 경우 같은 MERGE 패턴을 사용한다.

// 1) 제약조건/인덱스
CREATE CONSTRAINT doc_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE;
CREATE CONSTRAINT article_id IF NOT EXISTS FOR (a:Article) REQUIRE a.id IS UNIQUE;
CREATE CONSTRAINT obligation_id IF NOT EXISTS FOR (o:Obligation) REQUIRE o.id IS UNIQUE;
CREATE FULLTEXT INDEX article_text IF NOT EXISTS FOR (a:Article) ON EACH [a.title, a.text];

// 2) 적재
CALL apoc.load.json('file:///compliance_graph.json') YIELD value
UNWIND value.documents AS d
MERGE (doc:Document {id: d.id})
SET doc.title = d.title, doc.level = d.level, doc.level_rank = d.level_rank,
    doc.effective_date = date(d.effective_date), doc.issuer = d.issuer;

CALL apoc.load.json('file:///compliance_graph.json') YIELD value
UNWIND value.articles AS a
MATCH (doc:Document {id: a.doc_id})
MERGE (art:Article {id: a.id})
SET art.no = a.no, art.title = a.title, art.text = a.text
MERGE (doc)-[:HAS_ARTICLE]->(art);

CALL apoc.load.json('file:///compliance_graph.json') YIELD value
UNWIND value.relations AS r
MATCH (s:Article {id: r.source}), (t:Article {id: r.target})
CALL apoc.merge.relationship(s, r.type, {}, {note: r.note}, t) YIELD rel
RETURN count(rel);

CALL apoc.load.json('file:///compliance_graph.json') YIELD value
UNWIND value.obligations AS o
MATCH (a:Article {id: o.article_id})
MERGE (ob:Obligation {id: o.id})
SET ob.subject = o.subject, ob.modality = o.modality, ob.attribute = o.attribute,
    ob.operator = o.operator, ob.value = toString(o.value)
MERGE (a)-[:STATES]->(ob);

CALL apoc.load.json('file:///compliance_graph.json') YIELD value
UNWIND value.obligation_links AS l
MATCH (i:Obligation {id: l.internal}), (u:Obligation {id: l.upper})
MERGE (i)-[:CHECKED_AGAINST {expected: l.expected}]->(u);

// 3) Multi-hop 질의 예시: 사내 규정이 (직접·간접) 근거하는 상위 조문 전체 추적
MATCH p = (i:Article {id: 'I-4'})-[:IMPLEMENTS*1..3]->(up:Article)
RETURN [n IN nodes(p) | n.id] AS chain;

// 4) 위반 후보: 사내 의무가 상위 의무와 충돌하는 쌍
MATCH (ia:Article)-[:STATES]->(io:Obligation)-[c:CHECKED_AGAINST]->(uo:Obligation)<-[:STATES]-(ua:Article)
WHERE c.expected = 'VIOLATES'
RETURN ia.id AS internal_article, io.attribute, io.value AS internal_value,
       ua.id AS upper_article, uo.value AS upper_value;

// 5) 단서·준용 관계 추적: 제2조 → 예외 조문 → 이를 준용하는 조문
MATCH (a:Article {id: 'L-2'})-[:EXCEPTION_REFERS_TO]->(e:Article)<-[:REFERS_TO]-(other:Article)
RETURN a.id, e.id AS exception, other.id AS also_refers;
