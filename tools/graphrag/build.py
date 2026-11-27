"""그래프 내보내기와 SQL 베이스라인 비교.

사용:
    python tools/graphrag/build.py export     # data/graph/nodes.jsonl, edges.jsonl, manifest.json (Neo4j 적재 전 파일)
    python tools/graphrag/build.py compare    # 같은 구조 조건을 SQL로 평가해 그래프 평가기와 결과·시간 비교
    python tools/graphrag/build.py stats      # 적재 대상 건수·조건 현황

Neo4j(Aura)에는 쓰지 않는다. 팀 공용 인스턴스라 적재는 별도 승인 후 한다.
"""
from __future__ import annotations

import hashlib
import json
import random
import sqlite3
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag import concepts_laws  # noqa: E402
from graphrag.condition_schema import requirement_groups, unify  # noqa: E402
from graphrag.engine import Engine  # noqa: E402
from graphrag.evaluator import BOUNDARY_YEARS, DEFAULT_OPTIONS, NOT_ELIGIBLE, Profile, evaluate_notice  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "graph"


def export(e: Engine) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    nodes, edges = [], []
    orgs: dict[str, str] = {}
    cats: dict[str, str] = {}

    def org_id(name: str) -> str:
        key = name.strip()
        return orgs.setdefault(key, f"ORG:{hashlib.sha1(key.encode()).hexdigest()[:12]}")

    c_nodes, c_edges, by_label = concepts_laws.concepts()
    for rid, n in e.rg.nodes.items():
        nodes.append({"label": "Concept", "concept_id": rid, "scheme": "REGION", **{k: v for k, v in n.items() if k != "region_id"}})
        for p, rel in e.rg.parents.get(rid, []):
            edges.append({"type": rel, "from": rid, "to": p, "basis": e.rg.edge_basis[(rid, p, rel)]})
    for rid, n in e.rg.retired.items():  # 폐지 지역(행정 분할·통합 전 명칭). 후계 관계는 코드표의 후보 대응이라 미검수
        nodes.append({"label": "Concept", "concept_id": rid, "scheme": "REGION", **{k: v for k, v in n.items() if k not in ("region_id", "successor_ids")}})
        for succ in e.rg.successors.get(rid, []):
            edges.append({"type": "SUCCEEDED_BY", "from": rid, "to": succ, "partial": True, "reviewed": False})
    for n in e.notices:
        nid = n["notice_id"]
        node = {"label": "Notice", "notice_id": nid, "source_system": n["source"], "title": n["title"], "detail_url": n["detail_url"],
                "deadline": n.get("deadline"), "apply_status_kind": n["apply_status_kind"], "is_open": n["is_open"], "fetched_at": n["fetched_at"],
                "text_requirements": n["text_requirements"]}
        conditions = n["conditions"]
        if n["source"] == "BIZINFO" and DEFAULT_OPTIONS.c6_bizinfo_org_region == "drop":
            # C-6 ②: 기업마당 소관 기관 시도는 자격 조건이 아니다. 조건을 만들지 않고 검색 필터 속성으로만 둔다
            org_region = [c for c in conditions if c["attribute"] == "region"]
            conditions = [c for c in conditions if c["attribute"] != "region"]
            if org_region:
                node["search_region_id"] = org_region[0]["value"]["concept_id"]
        nodes.append(node)
        if n.get("org"):
            edges.append({"type": "ANNOUNCED_BY", "from": nid, "to": org_id(n["org"]), "source_field": "jrsdInsttNm" if n["source"] == "BIZINFO" else "pbanc_ntrp_nm"})
        if n.get("executor"):
            edges.append({"type": "EXECUTED_BY", "from": nid, "to": org_id(n["executor"]), "source_field": "excInsttNm"})
        if n.get("category"):
            cid = cats.setdefault(f"{n['source']}|{n['category']}", f"CAT:{n['source']}:{hashlib.sha1(n['category'].encode()).hexdigest()[:10]}")
            edges.append({"type": "IN_SUPPORT_CATEGORY", "from": nid, "to": cid})
        if conditions:
            # 예비창업자 허용 업력은 OR 요건으로 따로 둔다(설계서 4.3). 평가기도 같은 묶음을 쓴다
            for rq, logic, basis, conds in requirement_groups(nid, conditions):
                nodes.append({"label": "Requirement", "req_id": rq, "kind": "ELIGIBILITY", "logic": logic, "logic_basis": basis,
                              "status": "structured_only", "extraction_method": "rule"})
                edges.append({"type": "HAS_REQUIREMENT", "from": nid, "to": rq, "evidence": "구조화 API 필드", "source": "api_structured"})
                for c in conds:
                    attr, op, val = c.get("unified") or unify(c["attribute"], c["value"])
                    node = {"label": "Condition", "cond_id": c["cond_id"], "cond_type": "ATOM", "attribute": attr, "operator": op,
                            "strength": c["strength"], "value": json.dumps(val, ensure_ascii=False), "evidence_source": "API", "reviewed": False}
                    if c.get("value") is not None and c.get("legacy", 1) is not None:
                        node["legacy_value"] = json.dumps(c["value"], ensure_ascii=False)
                    if attr in ("business_age", "founder_age"):  # 구조화 필드에는 기준일이 없다(설계서 4.3 기준일)
                        node.update({"ref_date_kind": "UNSPECIFIED", "ref_start_kind": "UNSPECIFIED"})
                    if op is None:
                        node["unknown_reason"] = "all_options"
                    if attr in ("applicant_type", "certification", "industry", "company_size"):
                        node["about_pending"] = True  # 개념(APPLICANT_TYPE 등)이 아직 없어 ABOUT 간선을 만들 수 없다
                    nodes.append(node)
                    edges.append({"type": "HAS_CONDITION", "from": rq, "to": c["cond_id"], "evidence": c["evidence"], "source": c["source_field"]})
                    if attr == "region":
                        edges.append({"type": "ABOUT", "from": c["cond_id"], "to": val["concept_id"]})
                    if attr == "applicant_type":  # K-Startup 신청 대상 옵션 -> 신청자 유형 개념. 개념이 없는 값은 about_unmapped에 남긴다
                        mapped = [(lab, by_label[lab]) for lab in val["labels"] if lab in by_label]
                        for lab, cid in mapped:
                            edges.append({"type": "ABOUT", "from": c["cond_id"], "to": cid, "option": lab})
                        missing = [lab for lab in val["labels"] if lab not in by_label]
                        node["about_pending"] = bool(missing)
                        if missing:
                            node["about_unmapped"] = missing
        gold_seen: set[str] = set()  # 같은 조건이 공고의 다른 요건에도 걸리면 노드는 하나, HAS_CONDITION은 요건마다(요건 안 중복은 gold_bridge가 없앤다)
        for g in n.get("gold_requirements", []):  # 사람이 검수한 본문 요건(gold_bridge). 발췌 검수라 공고 전체 요건은 아니다
            rv = n["gold_review"]
            nodes.append({"label": "Requirement", "req_id": g["req_id"], "kind": "ELIGIBILITY", "logic": g["logic_tree"].get("operator", "ATOM"),
                          "logic_basis": g["logic_basis"], "logic_tree": json.dumps(g["logic_tree"], ensure_ascii=False), "status": "reviewed_excerpt",
                          "extraction_method": "human_review", "review_split": rv["split"], "reviewed_at": rv["reviewed_at"]})
            edges.append({"type": "HAS_REQUIREMENT", "from": nid, "to": g["req_id"], "evidence": "검수 정답(발췌)", "source": rv["source_field"]})
            for c in g["conditions"]:
                edges.append({"type": "HAS_CONDITION", "from": g["req_id"], "to": c["cond_id"], "evidence": c["evidence"], "source": c["source_field"]})
                if c["cond_id"] in gold_seen:
                    continue
                gold_seen.add(c["cond_id"])
                v = c["value"]
                node = {"label": "Condition", "cond_id": c["cond_id"], "cond_type": "ATOM", "attribute": c["attribute"],
                        "operator": None if v.get("unsupported") else c["operator"], "strength": c["strength"], "negate": c["negate"],
                        "value": json.dumps(v if not v.get("unsupported") else c["raw_value"], ensure_ascii=False), "evidence_source": "NOTICE_TEXT",
                        "reviewed": True, "ref_date_kind": c.get("reference_date_type") or "UNKNOWN"}
                if v.get("unsupported"):
                    node["unknown_reason"] = "no_evaluation_rule"
                nodes.append(node)
                for cid in v.get("concept_ids", []):
                    edges.append({"type": "ABOUT", "from": c["cond_id"], "to": cid})
    l_nodes, l_edges, article_index, pending = concepts_laws.laws()
    d_nodes, d_edges, def_notes = concepts_laws.definitions(by_label, article_index)
    nodes += c_nodes + l_nodes + d_nodes
    edges += c_edges + l_edges + d_edges
    # 공고가 법령·조문을 인용한 연결. 요건 노드가 본문에서 만들어진 뒤에 Requirement-[:CITES]->조문으로 잇는다(지금은 보류 목록만 남긴다)
    (OUT / "law_citations_pending.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in pending) + "\n", encoding="utf-8")
    for k, v in orgs.items():
        nodes.append({"label": "Organization", "org_id": v, "name": k})
    for k, v in cats.items():
        s, name = k.split("|", 1)
        nodes.append({"label": "SupportCategory", "category_id": v, "name": name, "source_system": s})
    for fn, rows in (("nodes.jsonl", nodes), ("edges.jsonl", edges)):
        (OUT / fn).write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")
    gold = sum(1 for n in nodes if n["label"] == "Requirement" and n.get("status") == "reviewed_excerpt")
    man = {"built": date.today().isoformat(), "nodes": Counter(n["label"] for n in nodes), "edges": Counter(x["type"] for x in edges),
           "skipped": e.skipped, "gold_requirements": gold,
           "note": "구조화 필드 조건과 사람이 검수한 본문 요건(발췌)만 담는다. Aura 적재 여부는 docs/LOAD_Neo4j_적재기록_v0.1.md를 본다."}
    (OUT / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1, default=dict), encoding="utf-8")
    return man


def build_sqlite(e: Engine) -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.executescript("""
    CREATE TABLE closure(region TEXT, ancestor TEXT, hops INT);
    CREATE INDEX ix_cl ON closure(region, ancestor);
    CREATE TABLE notice(notice_id TEXT PRIMARY KEY, source TEXT);
    CREATE TABLE cond_region(notice_id TEXT, target TEXT);
    CREATE TABLE cond_bage(notice_id TEXT, pre_ok INT, max_years REAL, all_opts INT);
    """)
    rows = [(r, a, h) for r in e.rg.nodes for a, h in e.rg.ancestors(r).items()]
    db.executemany("INSERT INTO closure VALUES (?,?,?)", rows)
    for n in e.notices:
        if not e.is_open(n):
            continue
        db.execute("INSERT INTO notice VALUES (?,?)", (n["notice_id"], n["source"]))
        for c in n["conditions"]:
            if c["attribute"] == "region":
                db.execute("INSERT INTO cond_region VALUES (?,?)", (n["notice_id"], c["value"]["concept_id"]))
            elif c["attribute"] == "business_age":
                v = c["value"]
                db.execute("INSERT INTO cond_bage VALUES (?,?,?,?)", (n["notice_id"], int(v["pre_founder_allowed"]), v["max_years"], int(v["all_options"])))
    return db


def sql_hard_fail(db: sqlite3.Connection, prof: Profile) -> set[str]:
    """business_age(hard) 불충족 공고. 그래프 평가기와 같은 경계 규칙(±0.5년, 옵션 전체 나열은 UNKNOWN)을 SQL로 쓴 것."""
    if prof.pre_founder:
        q = "SELECT notice_id FROM cond_bage WHERE pre_ok=0"
        return {r[0] for r in db.execute(q)}
    if prof.business_age_years is None:
        return set()
    q = "SELECT notice_id FROM cond_bage WHERE max_years IS NULL OR (? >= max_years + ? AND all_opts=0)"
    # 옵션을 전부 나열한 공고(all_opts=1)는 해석이 모호해 UNKNOWN이므로 제외 집합에 넣지 않는다(그래프 평가기와 같은 규칙).
    return {r[0] for r in db.execute(q, (prof.business_age_years, BOUNDARY_YEARS))}


def sql_region_status(db: sqlite3.Connection, prof: Profile) -> dict[str, str]:
    if prof.region is None:
        return {r[0]: ("SATISFIED" if r[1] == "REGION:NATIONWIDE" else "UNKNOWN") for r in db.execute("SELECT notice_id, target FROM cond_region")}
    q = """
    SELECT c.notice_id,
      CASE WHEN c.target='REGION:NATIONWIDE' THEN 'SATISFIED'
           WHEN EXISTS (SELECT 1 FROM closure k WHERE k.region=? AND k.ancestor=c.target) THEN 'SATISFIED'
           WHEN EXISTS (SELECT 1 FROM closure k WHERE k.region=c.target AND k.ancestor=?) THEN 'UNKNOWN'
           ELSE 'UNSATISFIED' END
    FROM cond_region c"""
    return {r[0]: r[1] for r in db.execute(q, (prof.region, prof.region))}


def compare(e: Engine, n_profiles: int = 300, seed: int = 20261124) -> dict:
    db = build_sqlite(e)
    rng = random.Random(seed)
    regions = [r for r, n in e.rg.nodes.items() if n.get("level") in ("SIDO", "SIGUNGU")]
    open_notices = [n for n in e.notices if e.is_open(n)]
    t_graph = t_sql = 0.0
    diff_hard = diff_region = 0
    checked_region = 0
    examples = []
    for _ in range(n_profiles):
        prof = Profile(region=rng.choice(regions + [None]), business_age_years=rng.choice([None, 0.5, 1, 2.8, 3, 5, 8, 12, 20]),
                       pre_founder=rng.choice([None, True, False]), founder_age=rng.choice([None, 18, 30, 45]),
                       applicant_type=rng.choice([None, "일반인", "일반기업"]))
        t = time.perf_counter()
        ev = {n["notice_id"]: evaluate_notice(n, prof, e.rg) for n in open_notices}
        t_graph += time.perf_counter() - t
        t = time.perf_counter()
        sh = sql_hard_fail(db, prof)
        sr = sql_region_status(db, prof)
        t_sql += time.perf_counter() - t
        gh = {k for k, v in ev.items() if v["verdict"] == NOT_ELIGIBLE}
        if gh != sh:
            diff_hard += 1
            if len(examples) < 3:
                examples.append({"profile": prof.__dict__, "only_graph": sorted(gh - sh)[:3], "only_sql": sorted(sh - gh)[:3]})
        for k, v in ev.items():
            for c in v["conditions"]:
                if c.attribute == "region" and "gold" not in c.flags and k in sr:  # SQL 기준선은 구조화 지역만 안다
                    checked_region += 1
                    if sr[k] != c.status:
                        diff_region += 1
    return {"profiles": n_profiles, "open_notices": len(open_notices), "hard_fail_set_mismatch_profiles": diff_hard,
            "region_condition_checked": checked_region, "region_status_mismatch": diff_region,
            "graph_evaluator_sec_total": round(t_graph, 2), "sql_sec_total": round(t_sql, 2), "mismatch_examples": examples}


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    eng = Engine()
    if cmd == "export":
        print(json.dumps(export(eng), ensure_ascii=False, indent=1, default=dict))
    elif cmd == "compare":
        print(json.dumps(compare(eng), ensure_ascii=False, indent=1))
    else:
        cnt = Counter(c["attribute"] for n in eng.notices for c in n["conditions"])
        print(json.dumps({"notices": len(eng.notices), "chunks": len(eng.chunks), "conditions": cnt, "skipped": eng.skipped}, ensure_ascii=False, indent=1, default=dict))
