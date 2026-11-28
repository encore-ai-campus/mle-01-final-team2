"""사람이 검수한 조건 정답(2-4 정답셋)을 그래프 요건·조건과 평가기 입력으로 옮긴다.

입력은 `tools/ingest_condition_gold_reviews.py`가 만든 `reviewed_condition_gold.jsonl`·`reviewed_logic_gold.jsonl`이다.
검수 도구가 VERIFIED로 반영한 행만 들어 있으므로 이 모듈은 검수 상태를 다시 판단하지 않는다. 조건 하나하나도 `review_status=VERIFIED`인 것만 쓴다.

2026-11-27 팀 결정(`docs/RULES_판정_정규화_검토목록_v0.1.md` D-1~D-5)대로 옮긴다:
- D-1 ②: 검수 범위가 발췌 문장이면(`whole_notice_conditions_complete=false`) 공고의 `text_requirements`는 `partially_reviewed`이고
  ELIGIBLE을 만들지 않는다(REQ_UNPARSED). 검수 양식의 "자격 조건 전체 확인"이 참인 공고만 `reviewed`로 올린다.
- D-2 ③: 조건 강도는 구조화 필드와 같은 속성 규칙이다(`evaluator.gold_strength`, 업력만 hard). 그래프에도 같은 강도를 적는다.
- 우대(PREFERENCE)는 자격 요건이 아니라 옮기지 않는다. 의미를 정하지 못한 조건(UNCLASSIFIED)도 옮기지 않는다.
- 제외(EXCLUSION) 조건은 `negate=True`다. 해당하면(SATISFIED) 요건 불충족이다.
- 기본은 개발용(development) 정답만 쓴다. 평가용(evaluation) 정답을 서비스 그래프에 넣을지는 팀이 정한다.
"""
from __future__ import annotations

import json
from pathlib import Path

# 개발용 정답 v1.1 최종 30건(조건 116개, 2026-11-26 확정). 예전 v1/20261125는 검수 반영 0건이었다
GOLD_ROOT = Path(__file__).resolve().parents[2] / "data" / "goldsets" / "conditions" / "v1.1" / "20261126" / "final30"
# 서비스 검수 큐(tools/requirement_review_queue.py ingest) 결과. 골든셋과 따로 두고 평가 정답으로 쓰지 않는다
SERVICE_ROOT = Path(__file__).resolve().parents[2] / "data" / "reviews" / "requirements"
NUMERIC = {"LT", "LTE", "GT", "GTE", "EQ"}
FIELD_ATTR = {"BUSINESS_AGE": "business_age", "REPRESENTATIVE_AGE": "founder_age", "BUSINESS_LOCATION": "region"}


def _read(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def to_condition(g: dict, notice_id: str, resolve_region) -> dict | None:
    """정답 조건 하나 -> 평가기 조건. 옮기지 않는 조건은 None."""
    if g.get("review_status") != "VERIFIED" or g["condition_type"] not in ("ELIGIBILITY", "EXCLUSION"):
        return None
    field = g.get("field") or g.get("category")
    attr = FIELD_ATTR.get(field, (field or "unclassified").lower())
    op, val = g.get("operator"), g.get("value")
    from .evaluator import gold_strength
    cond = {"cond_id": g["gold_condition_id"], "notice_id": notice_id, "attribute": attr, "strength": gold_strength(attr), "gold": True,
            "negate": g["condition_type"] == "EXCLUSION", "operator": op, "unit": g.get("unit"), "raw_value": val,
            "source_field": g["source_field"], "evidence": g["raw_text"], "reference_date_type": g.get("reference_date_type"),
            "review_comment": g.get("review_comment")}
    if attr in ("business_age", "founder_age") and op in NUMERIC and isinstance(val, (int, float)) and not isinstance(val, bool):
        cond["value"] = {"op": op, "value": float(val), "unit": g.get("unit") or "YEAR"}
    elif attr == "business_type" and op in ("EQ", "IN") and val:
        labels = val if isinstance(val, list) else [val]
        cond["value"] = {"labels": [str(x).strip() for x in labels]}  # 판정 기준이 있는 유형(중소기업)만 평가기가 본다
    elif attr == "region" and op in ("EQ", "IN") and val:
        labels = val if isinstance(val, list) else [val]
        ids = [resolve_region(str(x))[0] for x in labels]
        cond["value"] = {"concept_ids": [i for i in ids if i], "labels": [str(x) for x in labels], "unresolved": [str(x) for x, i in zip(labels, ids, strict=True) if not i]}
    else:
        cond["value"] = {"unsupported": True}  # 평가 규칙이 없거나 값 모양이 다르다 → 평가기에서 UNKNOWN
    return cond


def _prune(node: dict, known: set[str]) -> dict | None:
    """옮기지 않은 조건을 가리키는 가지를 뺀다. AND/OR에 자식이 하나 남으면 그 자식으로 줄인다."""
    if node["node_type"] == "CONDITION_REF":
        return node if node["condition_id"] in known else None
    kids = [k for k in (_prune(c, known) for c in node["children"]) if k]
    if not kids:
        return None
    if node["operator"] in ("AND", "OR") and len(kids) == 1:
        return kids[0]
    return {**node, "children": kids}


def load(root: Path = GOLD_ROOT, splits: tuple[str, ...] = ("development",), resolve_region=None) -> dict[str, dict]:
    """공고별 {"requirements": [{req_id, logic_tree, logic_basis, conditions}], "review": {...}}."""
    if resolve_region is None:
        from .label_eval import resolve_region
    out: dict[str, dict] = {}
    for split in splits:
        logic = {r["notice_id"]: r for r in _read(root / split / "reviewed_logic_gold.jsonl")}
        for row in _read(root / split / "reviewed_condition_gold.jsonl"):
            nid = row["notice_id"]
            conds = [c for c in (to_condition(g, nid, resolve_region) for g in row["gold_conditions"] + row["missed_condition_candidates"]) if c]
            by_id = {c["cond_id"]: c for c in conds}
            reqs = []
            lg = logic.get(nid)
            if lg:
                roots = [r for r in (_prune(x, set(by_id)) for x in lg["gold_logic_roots"]) if r]
                for i, tree in enumerate(roots, 1):
                    ids = list(dict.fromkeys(_refs(tree)))  # 트리 안 여러 가지가 같은 조건을 가리킬 수 있다(v1.1 118182). 조건 목록은 한 번씩
                    reqs.append({"req_id": f"{nid}#G{i}", "logic_tree": tree, "logic_basis": "explicit", "conditions": [by_id[x] for x in ids]})
                rest = [c for c in conds if c["cond_id"] not in {x for r in reqs for x in _refs(r["logic_tree"])}]
            else:
                rest = conds
            if rest:  # 논리 검수가 없거나 논리에 안 들어간 조건은 AND로 묶는다(가정)
                tree = {"node_type": "LOGICAL_GROUP", "group_id": f"{nid}#G-and", "operator": "AND",
                                 "children": [{"node_type": "CONDITION_REF", "condition_id": c["cond_id"]} for c in rest]}
                reqs.append({"req_id": f"{nid}#G{len(reqs) + 1}", "logic_tree": tree, "logic_basis": "assumed", "conditions": rest})
            out[nid] = {"requirements": reqs, "review": {"split": split.upper(), "reviewer": row["reviewer"], "reviewed_at": row["reviewed_at"],
                                                         "adjudication_status": row["adjudication_status"], "source_field": row["source_field"],
                                                         "logic_reviewed": bool(lg), "whole_notice_complete": bool(row["whole_notice_conditions_complete"])}}
    return out


def load_all(resolve_region=None, service_root: Path = SERVICE_ROOT) -> dict[str, dict]:
    """개발용 정답 + 서비스 검수 결과. 같은 공고가 둘 다 있으면 정답(합의 검수)을 쓴다. 임시 기본값(2026-11-28, 팀 검토 전, docs/DESIGN_요건검수큐_v0.1.md Q-4)."""
    service = load(service_root, ("service",), resolve_region)
    return {**service, **load(resolve_region=resolve_region)}


def _refs(node: dict) -> list[str]:
    if node["node_type"] == "CONDITION_REF":
        return [node["condition_id"]]
    return [x for c in node["children"] for x in _refs(c)]


def attach(notices: list[dict], gold: dict[str, dict]) -> int:
    """정답이 있는 공고에 `gold_requirements`를 붙인다. 공고 전체 검수가 아니므로 text_requirements는 partially_reviewed다."""
    n = 0
    for notice in notices:
        g = gold.get(notice["notice_id"])
        if not g:
            continue
        notice["gold_requirements"] = g["requirements"]
        notice["gold_review"] = g["review"]
        if notice.get("text_requirements") != "reviewed":
            notice["text_requirements"] = "reviewed" if g["review"]["whole_notice_complete"] else "partially_reviewed"
        n += 1
    return n
