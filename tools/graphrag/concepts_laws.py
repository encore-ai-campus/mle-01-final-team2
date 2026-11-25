"""신청자 유형·인증 개념 사전, 법령(법령·조문·별표), 정의 노드를 그래프 내보내기용 노드·간선으로 만든다(설계서 4.1·4.2·5.2).

- 개념: `data/ref/term_standard_v0.1.json`의 신청자 유형 24개. 인증·확인서를 발급받아야 성립하는 지위(벤처기업·사회적기업·여성기업·장애인기업)는
  `CERTIFICATION` scheme으로 옮기고(O-07) 이노비즈·메인비즈·소상공인확인을 더한다. `IS_A`는 법령 원문이 근거인 소기업·중기업 -> 중소기업만 만든다.
- 법령: `data/지원사업_법령/`의 법령 26종·조문 1,286개·별표 40개. 조문·별표는 `PART_OF`로 법령에 속한다.
- 정의: 용어 사전이 법령 원문을 그대로 인용한 6개. 개념이 있는 것만 `DEFINED_BY`로 잇고 `CITES_LAW`로 조문에 잇는다. `rule_json`은 만들지 않는다(원문 확인 전).
- 공고가 조문을 인용한 543건은 요건 노드가 본문에서 만들어진 뒤에 `CITES`로 이어야 하므로 지금은 보류 목록(`law_citations_pending.jsonl`)으로만 남긴다.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TERMS = REPO / "data" / "ref" / "term_standard_v0.1.json"
LAW_DIR = REPO / "data" / "지원사업_법령"

CERT_FROM_TERMS = {"벤처기업", "사회적기업", "여성기업", "장애인기업"}
CERT_EXTRA = [("이노비즈", "기술 혁신형 중소기업 확인"), ("메인비즈", "경영 혁신형 중소기업 확인"), ("소상공인확인", "소상공인 확인서")]


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").split("\n") if l.strip()]


def sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def concepts() -> tuple[list[dict], list[dict], dict[str, str]]:
    """(노드, 간선, 신청자 유형 이름 -> concept_id). 이름은 ABOUT 연결에 쓴다."""
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    nodes, edges, by_label = [], [], {}
    for t in terms["applicant_types"]:
        name = t["label"]
        scheme, _, _ = t["concept_id"].partition(":")
        if scheme == "APPLICANT_TYPE" and name in CERT_FROM_TERMS:
            scheme = "CERTIFICATION"  # 발급형 지위는 인증 개념으로만 둔다
        cid = f"{scheme}:{name}"
        nodes.append({"label": "Concept", "concept_id": cid, "scheme": scheme, "name": name, "group": t["group"], "reviewed": False,
                      "source": "term_standard_v0.1"})
        by_label[name] = cid
        for p in t.get("parents", []):
            if p.get("relation") == "IS_A" and p.get("status") == "grounded_in_local_law_text":
                edges.append({"type": "IS_A", "from": cid, "to": p["to"], "basis": "법령 원문", "note": p["basis"][:200]})
    for name, note in CERT_EXTRA:
        cid = f"CERTIFICATION:{name}"
        nodes.append({"label": "Concept", "concept_id": cid, "scheme": "CERTIFICATION", "name": name, "group": "CERTIFICATION", "reviewed": False,
                      "source": "설계서 4.3", "note": note})
        by_label[name] = cid
    return nodes, edges, by_label


def laws() -> tuple[list[dict], list[dict], dict[tuple[str, str], str], list[dict]]:
    """(노드, 간선, (법령 이름, 조 번호) -> article_id, 공고 인용 보류 목록)."""
    articles = _jsonl(LAW_DIR / "조문.jsonl")
    appendices = _jsonl(LAW_DIR / "별표.jsonl")
    nodes, edges, index, pending = [], [], {}, []
    law_id = {}
    for r in articles:
        if r.get("level") == "law":
            law_id[r["doc_id"]] = f"LAW:{r['doc_id']}"
            nodes.append({"label": "ExternalLaw", "law_id": law_id[r["doc_id"]], "name": r["doc_name"], "doc_kind": r["doc_kind"],
                          "effective_date": r["effective"], "org": r["org"], "source_url": "https://www." + r["source"], "priority": r["priority"]})
            for nid in r.get("cited_by") or []:  # 조문 번호 없이 법령만 인용한 공고
                pending.append({"notice_id": nid, "law_id": law_id[r["doc_id"]]})
    for r in articles:
        if r.get("level") != "article":
            continue
        aid = f"{law_id[r['doc_id']]}:A{r['article_no']}"
        nodes.append({"label": "LawArticle", "article_id": aid, "law_id": law_id[r["doc_id"]], "article_no": str(r["article_no"]),
                      "article_title": r.get("article_title"), "text": r["text"], "text_hash": sha(r["text"]), "deleted": bool(r.get("deleted") in (True, "True"))})
        edges.append({"type": "PART_OF", "from": aid, "to": law_id[r["doc_id"]]})
        index[(r["doc_name"], str(r["article_no"]))] = aid
        for nid in r.get("cited_by") or []:
            pending.append({"notice_id": nid, "article_id": aid})
    seen: dict[str, int] = {}
    for r in appendices:
        base = f"{law_id[r['doc_id']]}:T{r['table_no']}-{r['table_branch']}"
        seen[base] = seen.get(base, 0) + 1
        pid = base if seen[base] == 1 else f"{base}#{seen[base]}"  # 같은 번호의 별표가 둘 있는 법령이 있다
        nodes.append({"label": "LawAppendix", "appendix_id": pid, "law_id": law_id[r["doc_id"]], "table_no": r["table_no"],
                      "table_kind": r["table_kind"], "title": r["title"], "text": r["text"], "text_hash": sha(r["text"])})
        edges.append({"type": "PART_OF", "from": pid, "to": law_id[r["doc_id"]]})
    return nodes, edges, index, pending


def definitions(by_label: dict[str, str], article_index: dict[tuple[str, str], str]) -> tuple[list[dict], list[dict], list[str]]:
    """(노드, 간선, 연결하지 못한 정의 설명). 법령 원문을 그대로 인용한 정의만 만든다."""
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    nodes, edges, notes = [], [], []
    for term, d in terms["law_definitions_verbatim"].items():
        m = re.search(r"제\s*(\d+)\s*조(?:의\s*(\d+))?", d["article"])
        art_no = f"{m.group(1)}의{m.group(2)}" if m and m.group(2) else (m.group(1) if m else None)
        aid = article_index.get((d["law"], art_no or ""))
        did = f"DEF:{term}"
        nodes.append({"label": "Definition", "def_id": did, "term": term, "basis_note": f"{d['law']} {d['article']} 원문 인용",
                      "article_text_hash": sha(d["text"]), "needs_review": True})  # rule_json은 원문 확인 후에만 채운다
        if aid:
            edges.append({"type": "CITES_LAW", "from": did, "to": aid, "article_ref": d["article"]})
        else:
            notes.append(f"{term}: 조문 `{d['law']} {d['article']}`을 수집 법령에서 찾지 못함")
        cid = by_label.get(term)
        if cid:
            edges.append({"type": "DEFINED_BY", "from": cid, "to": did})
        else:
            notes.append(f"{term}: 이름이 같은 개념이 없어 DEFINED_BY를 만들지 않음")
    return nodes, edges, notes
