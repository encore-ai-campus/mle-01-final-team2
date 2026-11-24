"""3단계: 법령 노드·인용 해소 측정과 권역 묶음 후보 스캔.

- 법령 원문은 새로 수집하지 못했다(법제처 API 시험 호출 실패). 대신 동료가 이미 수집한 로컬 법령 275건(data/old/상위법령_변환, 금융 중심)을
  `ExternalLaw`로 쓰고, 공고가 인용한 법령이 그 안에 있는지 **측정**한다.
- 법령 내용을 기억으로 쓰지 않는다. Definition에는 조문 원문(verbatim)만 담고 rule_json은 비워 둔다(status=text_only).
- 권역 묶음은 후보만 만든다(data/ref/region_group_candidates.json). 검수 전에는 활성 사전에 넣지 않는다.

사용: python tools/graphrag/laws.py
"""
from __future__ import annotations

import csv
import glob
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag.data import BIZ, KST, _jsonl  # noqa: E402
from graphrag.regions import REPO  # noqa: E402

LAWDIR = REPO / "data" / "old" / "상위법령_변환"
OUT = REPO / "data" / "graph"
REF = REPO / "data" / "ref"


def norm(name: str) -> str:
    return re.sub(r"[\s·ㆍ,]", "", name)


def load_laws() -> dict[str, dict]:
    laws = {}
    rows = list(csv.DictReader(open(LAWDIR / "목록.csv", encoding="utf-8-sig")))
    for r in rows:
        txt = LAWDIR / "텍스트" / f"{r['id']}.txt"
        if not txt.exists():
            continue
        t = txt.read_bytes()
        laws[norm(r["title"])] = {"law_id": f"LAW:{r['id']}", "name": r["title"], "doc_type": r["doc_type"], "date": r["date"],
                                  "ministry": r["ministry"], "file": r["id"], "chars": int(r["chars"] or 0),
                                  "text_hash": hashlib.sha256(t).hexdigest(), "source": "data/old/상위법령_변환(동료 수집분, 로컬 전용)"}
    return laws


def cite_kind(key: str) -> str:
    """인용 표기를 종류로 나눈다. 법령 원문(국가법령)으로 해소할 수 있는 것은 law·decree뿐이다."""
    if key.endswith("조례"):
        return "ordinance"
    if key.endswith(("고시", "지침", "세칙", "가이드라인", "기준")) or "고시" in key:
        return "notice_or_guideline"
    if key.endswith(("법", "법률")):
        return "law"
    if key.endswith(("시행령", "령", "시행규칙", "규칙")):
        return "decree"
    return "other"


def article_text(file_id: str, article: str | None) -> str | None:
    if not article:
        return None
    p = LAWDIR / "구조화" / f"{file_id}.json"
    if not p.exists():
        return None
    for a in json.loads(p.read_text(encoding="utf-8"))["articles"]:
        if a["no"] == article and not a.get("deleted"):
            return a["text"]
    return None


def run() -> dict:
    laws = load_laws()
    cands = _jsonl(OUT / "requirement_candidates.jsonl")
    cites = [c for c in cands if c["attribute"] == "law_reference"]
    res, miss = Counter(), Counter()
    cited_laws: Counter = Counter()
    for c in cites:
        key = norm(c["value"]["law"])
        kind = cite_kind(key)
        res[f"type_{kind}"] += 1
        if kind not in ("law", "decree"):  # 조례·고시·지침·사업명 등은 법령 원문 해소 대상이 아니다
            continue
        cited_laws[c["value"]["law"]] += 1
        if key in laws:
            art = article_text(laws[key]["file"], c["value"]["article"])
            res["resolved_law"] += 1
            if c["value"]["article"]:
                res["article_given"] += 1
                res["article_found" if art else "article_not_found"] += 1
        else:
            res["law_missing"] += 1
            miss[c["value"]["law"]] += 1
    # 정의 사슬 측정: 같은 문장에 규모 용어(중소기업 등)와 법령 인용이 함께 있는 경우
    by_line: dict[tuple, dict] = defaultdict(lambda: {"terms": set(), "laws": []})
    for c in cands:
        k = (c["notice_id"], c["evidence_text"])
        if c["attribute"] == "company_size":
            by_line[k]["terms"].add(c["value"]["label"])
        elif c["attribute"] == "law_reference":
            by_line[k]["laws"].append(c["value"])
    chain, pair_counts, defs = Counter(), Counter(), {}
    for (nid, ev), v in by_line.items():
        for term in v["terms"]:
            if not v["laws"]:
                chain["no_citation_in_sentence"] += 1
                continue
            for law in v["laws"]:
                key = norm(law["law"])
                pair_counts[(term, law["law"])] += 1
                if key in laws:
                    art = article_text(laws[key]["file"], law["article"])
                    chain["resolved_text" if art else ("law_found_article_unknown" if law["article"] else "law_found_no_article")] += 1
                    if art and (term, laws[key]["law_id"], law["article"]) not in defs:
                        defs[(term, laws[key]["law_id"], law["article"])] = {
                            "def_id": f"DEF:{term}:{laws[key]['law_id']}:{law['article']}", "term": term, "law_id": laws[key]["law_id"],
                            "article_no": law["article"], "article_text_verbatim": art, "rule_json": None, "status": "text_only", "link_basis": "same_sentence_cocitation(정의로 확인하지 않음)",
                            "term_in_law_name": norm(term) in key,
                            "note": "조문 원문만 담았다. 판정 기준(rule_json)은 원문을 확인한 사람이 채운다.", "first_seen": nid}
                else:
                    chain["law_missing"] += 1
    laws_out = [dict(v) for v in laws.values()]
    (OUT / "external_laws.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in laws_out) + "\n", encoding="utf-8")
    (OUT / "definitions_text_only.jsonl").write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in defs.values()) + "\n", encoding="utf-8")
    groups = scan_region_groups()
    rep = {"external_laws_local": len(laws), "citations": len(cites), "citation_resolution": dict(res),
           "top_missing_laws": miss.most_common(15), "top_cited_laws": cited_laws.most_common(10),
           "chain_company_size_sentences": dict(chain), "term_law_pairs_top": [[f"{t} ← {l}", n] for (t, l), n in pair_counts.most_common(12)],
           "definitions_text_only": len(defs), "definitions_with_term_in_law_name": sum(1 for d in defs.values() if d["term_in_law_name"]), "region_group_candidates": groups["summary"]}
    (OUT / "law_chain_report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    return rep


R_DEF = re.compile(r"([가-힣]{2,5}권)\s*\*?\s*[:：=]\s*([가-힣0-9/,·ㆍ\s\(\)]{3,60})")
R_MENT = re.compile(r"[가-힣]{2,4}권(?![가-힣])")
STOP = {"수도권", "비수도권"}  # 흔히 쓰이는 권역도 후보로 세되 정의가 있는지 따로 본다


def scan_region_groups() -> dict:
    texts = []
    run_id = (BIZ / "raw" / "LATEST").read_text().strip()
    for r in _jsonl(BIZ / "parsed" / run_id / "notices.jsonl"):
        texts.append((r["notice_id"], r.get("eligibility_criteria_text") or ""))
        texts.append((r["notice_id"], r.get("summary") or ""))
    ed = sorted(glob.glob(str(BIZ / "extracted" / "*")))
    if ed:
        ed = Path(ed[-1])
        for it in json.loads((ed / "extraction_report.json").read_text(encoding="utf-8"))["items"]:
            if it["status"] in ("OK", "OK_OCR"):
                try:
                    t = (ed / it["text_file"]).read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                for s in it["sections"]:
                    if s["label"] in ("ELIGIBILITY", "EXCLUSION"):
                        texts.append((it["notice_id"], t[s["start"]:s["end"]]))
    for r in _jsonl(KST):
        texts.append((f"KSTARTUP:{r['announcement_id']}", r.get("eligibility_text") or ""))
    mentions: dict[str, set] = defaultdict(set)
    defs: dict[str, list] = defaultdict(list)
    for nid, t in texts:
        for m in R_MENT.finditer(t):
            if m.group(0) not in ("교육권", "복지권", "인권", "소유권", "사용권", "저작권", "특허권", "채권", "청구권", "권리권"):
                mentions[m.group(0)].add(nid)
        for m in R_DEF.finditer(t):
            defs[m.group(1)].append({"notice_id": nid, "text": (m.group(1) + ": " + m.group(2)).strip()[:80]})
    REGION_LIKE = ("수도권", "동남권", "충청권", "호남권", "영남권", "경상권", "대경권", "강원권", "제주권", "중부권", "남부권", "북부권", "동부권", "서부권", "전북권", "전남권", "경북권", "경남권", "충북권", "충남권", "동북권", "서북권", "서남권")
    excluded = sorted(k for k, v in mentions.items() if len(v) >= 3 and k not in REGION_LIKE)
    cand = [{"label": k, "notices": len(v), "has_definition_sentence": k in defs,
             "definitions": defs.get(k, [])[:2]} for k, v in sorted(mentions.items(), key=lambda x: -len(x[1])) if len(v) >= 3 and k in REGION_LIKE]
    out = {"note": "공고 텍스트에서 '○○권'이 3개 이상 공고에 나온 후보. 구성 시도는 공고 본문이 정의한 것만 근거가 되며 사람이 검수하기 전에는 활성 사전에 넣지 않는다.",
           "summary": {"distinct_labels_ge3_notices": len(cand), "with_definition_sentence": sum(1 for c in cand if c["has_definition_sentence"]),
                       "top": [[c["label"], c["notices"], c["has_definition_sentence"]] for c in cand[:12]]},
           "excluded_non_region_labels": excluded, "candidates": cand}
    (REF / "region_group_candidates.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))
