"""신청자 유형·인증 개념 사전, 법령(법령·조문·별표), 정의 노드를 그래프 내보내기용 노드·간선으로 만든다(설계서 4.1·4.2·5.2).

- 개념: `data/ref/term_standard_v0.1.json`의 신청자 유형 24개. 인증·확인서를 발급받아야 성립하는 지위(벤처기업·사회적기업·여성기업·장애인기업)는
  `CERTIFICATION` scheme으로 옮기고(O-07) 이노비즈·메인비즈·소상공인확인을 더한다. `IS_A`는 법령 원문이 근거인 소기업·중기업 -> 중소기업만 만든다.
- 법령: `data/지원사업_법령/`의 44문서(법률 22·시행령 22)·조문 2,325개·별표 59개(2026-11-26 추가 수집 반영). 조문·별표는 `PART_OF`로 법령에 속한다.
- 정의: 용어 사전이 법령 원문을 그대로 인용한 6개와 수집 조문에서 잘라 온 17개(`LAW_DEFS`). 중소기업은 사전 문장 대신 조문 원문을 쓴다. 개념이 있는 것만 `DEFINED_BY`로 잇고 `CITES_LAW`로 조문에 잇는다. `rule_json`은 만들지 않는다.
  검수 결과(`data/ref/definition_review_v0.1.json`)가 '확인'인 정의만 `needs_review=false`이고, 검수 때 본 시행령 조항을 `delegated_basis`로 남긴다.
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
REVIEW = REPO / "data" / "ref" / "definition_review_v0.1.json"  # 법령 정의 검수 결과(2026-11-27). '확인'만 needs_review=false

CERT_FROM_TERMS = {"벤처기업", "사회적기업", "여성기업", "장애인기업"}
CERT_EXTRA = [("이노비즈", "기술 혁신형 중소기업 확인"), ("메인비즈", "경영 혁신형 중소기업 확인"), ("소상공인확인", "소상공인 확인서")]
# 데이터명세서 v0.3 추가 법령으로 정의가 생긴 신청자 유형(2026-11-26). (scheme, 이름, group, 메모)
# 지정·인정·등록을 받아야 성립하는 지위는 O-07에 따라 CERTIFICATION, 정의 기준만으로 성립하는 것은 APPLICANT_TYPE에 둔다.
LAW_CONCEPTS_V03 = [
    ("CERTIFICATION", "마을기업", "CERTIFICATION", "마을기업법 제11조에 따른 지정이 있어야 성립"),
    ("CERTIFICATION", "자활기업", "CERTIFICATION", "국민기초생활 보장법 제18조제2항에 따른 보장기관의 인정이 있어야 성립"),
    ("CERTIFICATION", "연구소기업", "CERTIFICATION", "연구개발특구법 제9조의3제2항에 따른 등록이 있어야 성립"),
    ("APPLICANT_TYPE", "어업인", "PERSON", "수산업ㆍ어촌 발전 기본법 제3조 제3호. 세부 기준은 시행령 제3조"),
    ("APPLICANT_TYPE", "농업인", "PERSON", "농업ㆍ농촌 및 식품산업 기본법 제3조 제2호. 세부 기준은 시행령 제3조"),
    ("APPLICANT_TYPE", "중소기업협동조합", "ORGANIZATION", "중소기업협동조합법 제3조의 조합·사업조합·연합회·중앙회. 협동조합 기본법의 `협동조합`과 다른 개념"),
]


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
    for scheme, name, group, note in LAW_CONCEPTS_V03:
        cid = f"{scheme}:{name}"
        nodes.append({"label": "Concept", "concept_id": cid, "scheme": scheme, "name": name, "group": group, "reviewed": False,
                      "source": "지원사업 법령 데이터명세서 v0.3", "note": note})
        by_label[name] = cid
    from .concept_aliases import new_concepts  # 업종(데이터에 나온 값만)·기업부설연구소. 사용자 결정 2026-11-28, 팀 검토 전
    for node in new_concepts():
        nodes.append(node)
        by_label[node["name"]] = node["concept_id"]
    return nodes, edges, by_label


def law_url(doc_id: str) -> str:
    """국가법령정보센터에서 수집한 버전(법령일련번호)의 본문 주소. 수집 데이터의 `source`(`law.go.kr/law/{번호}`)는 식별자라 그대로 열리지 않는다."""
    return f"https://www.law.go.kr/lsInfoP.do?lsiSeq={doc_id}"


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
                          "effective_date": r["effective"], "org": r["org"], "source_url": law_url(r["doc_id"]), "priority": r["priority"]})
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
        if seen[base] == 1 and str(r.get("table_branch")) in ("00", "0"):
            index[(r["doc_name"], f"별표{int(r['table_no'])}")] = pid  # 정의가 위임한 별표 찾기(`definitions`)
    return nodes, edges, index, pending


# 데이터명세서 v0.3 추가 법령의 정의 조항. (개념 이름, 법령 용어, 법령, 조, 시작 표지, 조항 표기)
# 시작 표지가 "N." 꼴이면 그 호(딸린 목 포함)만, "①②"처럼 항 묶음이면 그 항들만 `조문.jsonl` 원문에서 그대로 잘라 온다.
LAW_DEFS_V03 = [
    ("장애인기업", "장애인기업", "장애인기업활동 촉진법", "2", "2.", "제2조 제2호"),
    ("이노비즈", "기술혁신형 중소기업", "중소기업 기술혁신 촉진법", "2", "3의2.", "제2조 제3호의2"),
    ("메인비즈", "경영혁신형 중소기업", "중소기업 기술혁신 촉진법", "2", "4의2.", "제2조 제4호의2"),
    ("청년", "청년", "청년기본법", "3", "1.", "제3조 제1호"),
    ("마을기업", "마을기업", "마을기업 육성 및 지원에 관한 법률", "2", "1.", "제2조 제1호"),
    ("어업인", "어업인", "수산업ㆍ어촌 발전 기본법", "3", "3.", "제3조 제3호"),
    ("농업인", "농업인", "농업ㆍ농촌 및 식품산업 기본법", "3", "2.", "제3조 제2호"),
    ("자활기업", "자활기업", "국민기초생활 보장법", "18", "①②", "제18조 제1항·제2항"),
    ("연구소기업", "연구소기업", "연구개발특구의 육성에 관한 특별법", "2", "6.", "제2조 제6호"),
    ("중소기업협동조합", "중소기업협동조합", "중소기업협동조합법", "3", "①", "제3조 제1항"),
]
# 데이터명세서 v0.2 법령(2026-11-26 보강). 용어 사전에 개념은 있었지만 정의 노드가 없던 7개.
# 벤처기업은 제2조제1항이 제2조의2를 가리키기만 하므로 요건 조항(제2조의2제1항)을 정의로 쓴다.
# 소상공인은 규모가 커진 뒤 3년간 소상공인으로 보는 제2항까지 판정에 필요해서 두 항을 함께 둔다.
LAW_DEFS_V02 = [
    # 중소기업은 v0.1 용어 사전 문장이 제1항 각 호를 `[중략]`으로 줄이고 제3항(5년 유예)을 뺐다. 조문에서 제1항~제3항을 다시 잘라 사전 문장을 대신한다.
    ("중소기업", "중소기업", "중소기업기본법", "2", "①②③", "제2조 제1항~제3항"),
    ("소상공인", "소상공인", "소상공인기본법", "2", "①②", "제2조 제1항·제2항"),
    ("중견기업", "중견기업", "중견기업 성장촉진 및 경쟁력 강화에 관한 특별법", "2", "1.", "제2조 제1호"),
    ("벤처기업", "벤처기업", "벤처기업육성에 관한 특별법", "2의2", "①", "제2조의2 제1항"),
    ("여성기업", "여성기업", "여성기업지원에 관한 법률", "2", "1.", "제2조 제1호"),
    ("사회적기업", "사회적기업", "사회적기업 육성법", "2", "1.", "제2조 제1호"),
    ("협동조합", "협동조합", "협동조합 기본법", "2", "1.", "제2조 제1호"),
    ("1인 창조기업", "1인 창조기업", "1인 창조기업 육성에 관한 법률", "2", "1.", "제2조 제1호"),
]
LAW_DEFS = LAW_DEFS_V02 + LAW_DEFS_V03
_ITEM = re.compile(r"^\d+(?:의\d+)?\.(?!\d)")  # 번호 뒤에 공백이 없는 원문도 있다(`1."중견기업"이란`)
_PARA = "①②③④⑤⑥⑦⑧⑨⑩"


def clause_text(article_text: str, marker: str) -> str | None:
    """조문 원문에서 정의 조항만 그대로 잘라 온다(글자를 바꾸지 않는다). 찾지 못하면 None."""
    lines = article_text.split("\n")
    if marker[0] in _PARA:  # 항 묶음: 첫 항부터 묶음 밖의 항이 나오기 전까지
        # v0.2 수집분은 첫 항이 조 제목과 같은 줄에 붙어 있다(`제18조(자활기업) ① …`)
        start = next((i for i, l in enumerate(lines) if l.startswith(marker[0]) or (i == 0 and f") {marker[0]}" in l)), None)
        if start is None:
            return None
        out = [lines[start]]
        for l in lines[start + 1:]:
            if (l[:1] in _PARA and l[:1] not in marker) or l.startswith("["):
                break
            out.append(l)
        return "\n".join(out).strip()
    start = next((i for i, l in enumerate(lines) if l.startswith(marker) and _ITEM.match(l) and _ITEM.match(l).group() == marker), None)
    if start is None:
        return None
    out = [lines[start]]
    for l in lines[start + 1:]:  # 다음 호, 다음 항, [개정 표시]가 나오면 멈춘다(딸린 목 "가."는 포함)
        if _ITEM.match(l) or l[:1] in _PARA or l.startswith("["):
            break
        out.append(l)
    return "\n".join(out).strip()


def law_definitions() -> dict[str, dict]:
    """`LAW_DEFS`의 개념 이름 -> {law, article, text, legal_term, source}. 원문을 찾지 못한 정의는 넣지 않는다."""
    arts = {(r["doc_name"], str(r["article_no"])): r["text"] for r in _jsonl(LAW_DIR / "조문.jsonl") if r.get("level") == "article"}
    out = {}
    v02 = {d[0] for d in LAW_DEFS_V02}
    for name, legal, law, art_no, marker, ref in LAW_DEFS:
        text = clause_text(arts.get((law, art_no), ""), marker)
        if text:
            out[name] = {"law": law, "article": ref, "text": text, "legal_term": legal,
                         "source": "data/지원사업_법령 v0.2" if name in v02 else "data/지원사업_법령 v0.3"}
    return out


APPENDIX_REF = re.compile(r"(?:^|;\s*)([^;\[]+?)\s*\[별표\s*(\d+)\]")


def definitions(by_label: dict[str, str], article_index: dict[tuple[str, str], str]) -> tuple[list[dict], list[dict], list[str]]:
    """(노드, 간선, 연결하지 못한 정의 설명). 법령 원문을 그대로 인용한 정의만 만든다.

    v0.1 용어 사전의 정의 6개에 수집 법령 조문에서 잘라 온 정의 17개(`LAW_DEFS`: v0.2 법령 7개, v0.3 추가 법령 10개)를 더한다.
    `LAW_DEFS`에 사전과 같은 용어가 있으면 사전 문장 대신 조문 원문을 쓴다(중소기업).
    """
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    review = json.loads(REVIEW.read_text(encoding="utf-8"))
    nodes, edges, notes = [], [], []
    all_defs = {**terms["law_definitions_verbatim"], **law_definitions()}
    for term, d in all_defs.items():
        m = re.search(r"제\s*(\d+)\s*조(?:의\s*(\d+))?", d["article"])
        art_no = f"{m.group(1)}의{m.group(2)}" if m and m.group(2) else (m.group(1) if m else None)
        aid = article_index.get((d["law"], art_no or ""))
        did = f"DEF:{term}"
        r = review["definitions"].get(term) or {"status": "미검수"}
        checked = r["status"] == "확인"
        nodes.append({"label": "Definition", "def_id": did, "term": term, "basis_note": f"{d['law']} {d['article']} 원문 인용",
                      "article_text_hash": sha(d["text"]), "needs_review": not checked, "review_status": r["status"],
                      **({"reviewed_at": review["reviewed_at"]} if checked else {}),
                      **({"delegated_basis": r["delegated_basis"]} if r.get("delegated_basis") else {}),
                      **({"review_note": r["note"]} if r.get("note") else {}),
                      **{k: d[k] for k in ("legal_term", "source") if d.get(k)}})
        if term not in review["definitions"]:
            notes.append(f"{term}: 검수 결과가 없어 needs_review=true")
        if aid:
            edges.append({"type": "CITES_LAW", "from": did, "to": aid, "article_ref": d["article"]})
        else:
            notes.append(f"{term}: 조문 `{d['law']} {d['article']}`을 수집 법령에서 찾지 못함")
        # 검수에서 판정에 필요하다고 확인한 별표(업종 제외, 규모 기준)를 CITES_LAW로 잇는다(설계서 §13.4)
        for law, no in APPENDIX_REF.findall("; ".join(r.get("delegated_basis") or [])) if checked else []:
            pid = article_index.get((law.strip(), f"별표{int(no)}"))
            if pid:
                edges.append({"type": "CITES_LAW", "from": did, "to": pid, "article_ref": f"{law.strip()} [별표 {int(no)}]", "role": "delegated_appendix"})
            else:
                notes.append(f"{term}: 위임 별표 `{law.strip()} [별표 {no}]`을 수집 법령에서 찾지 못함")
        cid = by_label.get(term)
        if cid:
            edges.append({"type": "DEFINED_BY", "from": cid, "to": did})
        else:
            notes.append(f"{term}: 이름이 같은 개념이 없어 DEFINED_BY를 만들지 않음")
    return nodes, edges, notes
