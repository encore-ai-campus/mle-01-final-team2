"""Neo4j Aura 읽기 전용 저장소(기초 설계서 §4.5 Multi-hop 질의, §7 계층 확장·경로·정의).

적재된 그래프(docs/LOAD_Neo4j_적재기록_v0.1.md)를 요청 시점에 읽는다. 쓰기 질의는 두지 않는다(세션을 READ_ACCESS로 연다).
- region_paths: 사용자 지역에서 조건 지역까지 WITHIN·MEMBER_OF 경로(최대 3 hop). 판정 근거 경로로 보낸다
- region_candidates: 사용자 지역으로 지역 조건을 충족(SAT)·미확인(UNK)하는 모집 중 공고(후보 검색의 정형 조건)
- notice_subgraph: 공고 → 요건 → 조건 → 개념(→ 지역 경로) → 정의 → 조문 → 법령. 그래프 화면(GET /api/graph/path)용
- definitions: 개념에 연결된 정의·법령 조문(fetch_definition). 모델이 법령을 외워 답하지 않게 원문 위치를 준다

판정은 여기서 하지 않는다. 판정은 규칙 평가기(ADR-12)가 하고, 이 저장소는 경로·정의를 근거로 붙인다.
"""
from __future__ import annotations

import json
import logging
from typing import Any

log = logging.getLogger("jiwongak.graph")
MAX_HOPS = 3

Q_REGIONS = """MATCH (r:Region) RETURN r.concept_id AS id, r.name AS name, r.full_name AS full_name, r.level AS level,
               r.parent_region_id AS parent ORDER BY r.region_code"""
Q_PATHS = f"""MATCH p=(u:Concept {{concept_id: $u}})-[:WITHIN|MEMBER_OF*0..{MAX_HOPS}]->(t:Concept)
              WHERE t.concept_id IN $targets
              RETURN t.concept_id AS target, [n IN nodes(p) | {{id: n.concept_id, name: n.name}}] AS nodes,
                     [r IN relationships(p) | type(r)] AS rels ORDER BY length(p)"""
Q_SAT = f"""MATCH (u:Concept {{concept_id: $u}})-[:WITHIN|MEMBER_OF*0..{MAX_HOPS}]->(:Concept)<-[:ABOUT]-(:Condition {{attribute: 'region'}})
            <-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice {{is_open: true}}) RETURN DISTINCT n.notice_id AS id"""
Q_UNK = f"""MATCH (t:Concept)-[:WITHIN|MEMBER_OF*1..{MAX_HOPS}]->(:Concept {{concept_id: $u}}) MATCH (t)<-[:ABOUT]-(:Condition {{attribute: 'region'}})
            <-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice {{is_open: true}}) RETURN DISTINCT n.notice_id AS id"""
Q_NATIONWIDE = """MATCH (:Concept {concept_id: 'REGION:NATIONWIDE'})<-[:ABOUT]-(:Condition {attribute: 'region'})
                  <-[:HAS_CONDITION]-(:Requirement)<-[:HAS_REQUIREMENT]-(n:Notice {is_open: true}) RETURN DISTINCT n.notice_id AS id"""
Q_NOTICE = """MATCH (n:Notice {notice_id: $nid})
              OPTIONAL MATCH (n)-[:HAS_REQUIREMENT]->(q:Requirement)-[:HAS_CONDITION]->(c:Condition)
              OPTIONAL MATCH (c)-[:ABOUT]->(k:Concept)
              RETURN n {.notice_id, .title, .detail_url, .fetched_at, .source_system} AS notice,
                     q {.req_id, .logic, .logic_basis, .kind, .status} AS req,
                     c {.cond_id, .attribute, .operator, .value, .strength, .reviewed} AS cond,
                     k {.concept_id, .name, .scheme} AS concept"""
Q_DEFS = """MATCH (k:Concept)-[:IS_A*0..2]->(k2:Concept)-[:DEFINED_BY]->(d:Definition)
            WHERE k.concept_id IN $ids
            OPTIONAL MATCH (d)-[:CITES_LAW]->(a:LawArticle)-[:PART_OF]->(l:ExternalLaw)
            RETURN k.concept_id AS concept, k2.concept_id AS defined_concept, k2.name AS defined_name, d.def_id AS def_id, d.term AS term,
                   d.needs_review AS needs_review, a.article_id AS article_id, a.article_no AS article_no, a.article_title AS article_title,
                   l.law_id AS law_id, l.name AS law_name, l.source_url AS law_url"""


Q_COND_PATHS = f"""MATCH (u:Concept {{concept_id: $u}})
                   MATCH (c:Condition)-[:ABOUT]->(t:Concept) WHERE c.cond_id IN $cids AND c.attribute = 'region'
                   OPTIONAL MATCH p=(u)-[:WITHIN|MEMBER_OF*0..{MAX_HOPS}]->(t)
                   WITH c, t, p ORDER BY length(p)
                   WITH c, t, head(collect(p)) AS p
                   RETURN c.cond_id AS cond_id, t.concept_id AS target, t.name AS target_name,
                          CASE WHEN p IS NULL THEN null ELSE [n IN nodes(p) | {{id: n.concept_id, name: n.name}}] END AS nodes,
                          CASE WHEN p IS NULL THEN null ELSE [r IN relationships(p) | type(r)] END AS rels"""
Q_NOTICE_DEFS = """MATCH (n:Notice)-[:HAS_REQUIREMENT]->(:Requirement)-[:HAS_CONDITION]->(c:Condition)-[:ABOUT]->(k:Concept)
                   -[:IS_A*0..2]->(k2:Concept)-[:DEFINED_BY]->(d:Definition)
                   WHERE n.notice_id IN $ids
                   OPTIONAL MATCH (d)-[:CITES_LAW]->(a:LawArticle)-[:PART_OF]->(l:ExternalLaw)
                   RETURN n.notice_id AS notice_id, c.cond_id AS cond_id, k.name AS concept, k2.name AS defined_concept,
                          d.def_id AS def_id, d.term AS term, d.needs_review AS needs_review, a.article_no AS article_no,
                          a.article_title AS article_title, l.name AS law_name, l.source_url AS law_url"""


class GraphUnavailable(RuntimeError):
    pass


class Neo4jGraphRepository:
    """동기 드라이버. FastAPI·에이전트에서는 asyncio.to_thread로 부른다."""

    def __init__(self, uri: str, user: str, password: str, database: str | None = None, timeout_s: float = 10.0):
        try:
            import truststore  # Windows·사내망 인증서 저장소(없으면 기본 번들)

            truststore.inject_into_ssl()
        except ImportError:
            pass
        from neo4j import GraphDatabase

        self._driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=timeout_s,
                                            max_transaction_retry_time=timeout_s)
        self._db = database or None

    def __repr__(self) -> str:  # 주소·계정을 남기지 않는다
        return "Neo4jGraphRepository()"

    def close(self) -> None:
        self._driver.close()

    def _read(self, query: str, **params) -> list[dict]:
        from neo4j import READ_ACCESS
        from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired

        try:
            with self._driver.session(database=self._db, default_access_mode=READ_ACCESS) as s:
                return s.run(query, **params).data()
        except (ServiceUnavailable, SessionExpired, Neo4jError, OSError) as e:
            raise GraphUnavailable(type(e).__name__) from e

    # ---------- 조회 ----------
    def ping(self) -> bool:
        try:
            return self._read("RETURN 1 AS ok")[0]["ok"] == 1
        except GraphUnavailable:
            return False

    def regions(self) -> list[dict]:
        return self._read(Q_REGIONS)

    def region_paths(self, user_region: str, targets: list[str]) -> dict[str, dict]:
        """조건 지역별 가장 짧은 경로. 없으면 그 지역은 빠진다(→ 평가기 판정이 UNSATISFIED·UNKNOWN)."""
        if not user_region or not targets:
            return {}
        out: dict[str, dict] = {}
        for r in self._read(Q_PATHS, u=user_region, targets=list(set(targets))):
            out.setdefault(r["target"], {"nodes": r["nodes"], "rels": r["rels"], "hops": len(r["rels"])})
        return out

    def region_candidates(self, user_region: str | None) -> dict[str, set[str]]:
        """지역 조건만 본 후보. sat=경로로 충족, unk=사용자가 상위 지역만 입력, nationwide=전국 대상."""
        nation = {r["id"] for r in self._read(Q_NATIONWIDE)}
        if not user_region:
            return {"sat": set(), "unk": set(), "nationwide": nation}
        sat = {r["id"] for r in self._read(Q_SAT, u=user_region)}
        unk = {r["id"] for r in self._read(Q_UNK, u=user_region)} - sat
        return {"sat": sat, "unk": unk, "nationwide": nation}

    def condition_paths(self, user_region: str | None, cond_ids: list[str]) -> list[dict]:
        """지역 조건별 경로(trace_path). nodes가 None이면 사용자 지역에서 닿지 않는다(CHAIN_BROKEN 아님, 지역 불일치·미확인)."""
        if not user_region or not cond_ids:
            return []
        return self._read(Q_COND_PATHS, u=user_region, cids=list(set(cond_ids)))

    def definitions_for_notices(self, notice_ids: list[str]) -> list[dict]:
        """후보 공고의 조건이 가리키는 개념 → 정의 → 조문 → 법령(fetch_definition)."""
        if not notice_ids:
            return []
        return self._read(Q_NOTICE_DEFS, ids=list(set(notice_ids)))

    def definitions(self, concept_ids: list[str]) -> list[dict]:
        if not concept_ids:
            return []
        return self._read(Q_DEFS, ids=list(set(concept_ids)))

    def notice_subgraph(self, notice_id: str, user_region: str | None = None) -> dict:
        """그래프 화면용 노드·간선. 공고가 없으면 nodes가 빈 목록이다."""
        rows = self._read(Q_NOTICE, nid=notice_id)
        nodes: dict[str, dict] = {}
        edges: list[dict] = []

        def node(nid: str, kind: str, label: str, **extra) -> None:
            nodes.setdefault(nid, {"id": nid, "kind": kind, "label": label, **extra})

        def edge(a: str, b: str, kind: str, **extra) -> None:
            e = {"from": a, "to": b, "type": kind, **extra}
            if e not in edges:
                edges.append(e)

        if not rows or rows[0]["notice"] is None:
            return {"notice_id": notice_id, "nodes": [], "edges": []}
        n = rows[0]["notice"]
        node(n["notice_id"], "Notice", n.get("title") or n["notice_id"], detail_url=n.get("detail_url"), fetched_at=n.get("fetched_at"))
        region_targets, concept_ids = [], []
        for r in rows:
            q, c, k = r["req"], r["cond"], r["concept"]
            if not q or not c:
                continue
            node(q["req_id"], "Requirement", f"요건 {q['req_id'].split('#')[-1]} ({q.get('logic')})", logic=q.get("logic"),
                 logic_basis=q.get("logic_basis"))
            edge(n["notice_id"], q["req_id"], "HAS_REQUIREMENT")
            node(c["cond_id"], "Condition", f"{c['attribute']} {c.get('operator') or ''}".strip(), attribute=c["attribute"],
                 operator=c.get("operator"), value=_json(c.get("value")), reviewed=c.get("reviewed"))
            edge(q["req_id"], c["cond_id"], "HAS_CONDITION")
            if k:
                node(k["concept_id"], "Concept", k.get("name") or k["concept_id"], scheme=k.get("scheme"))
                edge(c["cond_id"], k["concept_id"], "ABOUT")
                concept_ids.append(k["concept_id"])
                if c["attribute"] == "region":
                    region_targets.append(k["concept_id"])
        if user_region:
            for target, p in self.region_paths(user_region, region_targets).items():
                for a, b, rel in zip(p["nodes"], p["nodes"][1:], p["rels"]):
                    node(a["id"], "Concept", a["name"], scheme="region")
                    node(b["id"], "Concept", b["name"], scheme="region")
                    edge(a["id"], b["id"], rel, highlight=True)
                if p["nodes"]:
                    nodes[p["nodes"][0]["id"]]["user"] = True
            for t in region_targets:
                if t not in self.region_paths(user_region, [t]):
                    nodes[t]["broken"] = True  # 사용자 지역에서 닿지 않음(점선)
        for d in self.definitions(concept_ids):
            node(d["def_id"], "Definition", d.get("term") or d["def_id"], needs_review=d.get("needs_review"))
            if d["defined_concept"] != d["concept"]:
                node(d["defined_concept"], "Concept", d.get("defined_name") or d["defined_concept"])
                edge(d["concept"], d["defined_concept"], "IS_A")
            edge(d["defined_concept"], d["def_id"], "DEFINED_BY")
            if d.get("article_id"):
                node(d["article_id"], "LawArticle", f"{d.get('article_no')} {d.get('article_title') or ''}".strip())
                node(d["law_id"], "ExternalLaw", d.get("law_name") or d["law_id"], source_url=d.get("law_url"))
                edge(d["def_id"], d["article_id"], "CITES_LAW")
                edge(d["article_id"], d["law_id"], "PART_OF")
        return {"notice_id": notice_id, "nodes": list(nodes.values()), "edges": edges}


def _json(v: Any) -> Any:
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


def from_settings(settings) -> Neo4jGraphRepository | None:
    """Neo4j 설정이 없으면 None(그래프 근거 없이 규칙 판정만)."""
    if not (settings.neo4j_uri and settings.neo4j_user and settings.neo4j_password):
        return None
    if "://" not in settings.neo4j_uri:
        log.warning("NEO4J_URI에 '://'가 없어 그래프 저장소를 쓰지 않는다")
        return None
    return Neo4jGraphRepository(settings.neo4j_uri, settings.neo4j_user, settings.neo4j_password.get_secret_value(),
                                settings.neo4j_database)
