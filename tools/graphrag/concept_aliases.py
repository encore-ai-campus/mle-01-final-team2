"""표기 -> 개념 ID 별칭 사전(`data/ref/concept_aliases_v0.1.json`)과 업종·추가 인증 개념.

- 개념 이름, `term_standard_v0.1.json`의 aliases, 이 사전의 aliases를 한 색인으로 묶는다.
- 표기 비교는 NFKC, 공백·가운뎃점(·ㆍ・‧) 제거 후 한다. 그 밖의 추측(부분 일치, 접미사 떼기)은 하지 않는다.
- 판정 규칙은 바꾸지 않는다. 그래프의 ABOUT 연결과 근거 경로, 본문 후보의 개념 연결 비율 측정에만 쓴다.

사용: python tools/graphrag/concept_aliases.py  -> data/eval/concept_alias_coverage.json (본문 후보 연결 비율)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ALIASES = REPO / "data" / "ref" / "concept_aliases_v0.1.json"
TERMS = REPO / "data" / "ref" / "term_standard_v0.1.json"
_SEP = re.compile("[\\s·ㆍ・‧ᆞ]+")  # 공백과 가운뎃점 변이. ㆍ(U+318D)는 NFKC 뒤 U+119E가 된다


def key(text: str) -> str:
    return _SEP.sub("", unicodedata.normalize("NFKC", str(text))).lower()


def spec() -> dict:
    return json.loads(ALIASES.read_text(encoding="utf-8"))


def new_concepts() -> list[dict]:
    """concepts_laws.concepts()에 더할 개념 노드(업종, 기업부설연구소)."""
    out = []
    for c in spec()["new_concepts"]:
        node = {"label": "Concept", "reviewed": False, **c}
        out.append(node)
    return out


@lru_cache(maxsize=1)
def index() -> dict[str, str]:
    from .concepts_laws import concepts
    nodes, _, _ = concepts()
    idx: dict[str, str] = {}
    for n in nodes:
        idx.setdefault(key(n["name"]), n["concept_id"])
    by_name = {n["name"]: n["concept_id"] for n in nodes}
    terms = json.loads(TERMS.read_text(encoding="utf-8"))
    for t in terms["applicant_types"]:
        cid = by_name.get(t["label"])
        for a in t.get("aliases", []):
            if cid:
                idx.setdefault(key(a), cid)
    for a, cid in spec()["aliases"].items():
        idx[key(a)] = cid
    return idx


def resolve(label) -> str | None:
    """표기 하나 -> 개념 ID. 일반 단어·열린 목록·모르는 값은 None."""
    if label is None:
        return None
    return index().get(key(label))


def resolve_all(labels) -> tuple[list[str], list[str]]:
    """여러 표기 -> (개념 ID 목록, 못 이은 표기 목록). 순서 유지, 중복 제거."""
    if labels is None:
        return [], []
    items = labels if isinstance(labels, list) else [labels]
    ids, missing = [], []
    for x in items:
        if x is None or isinstance(x, (bool, int, float)):
            continue
        cid = resolve(x)
        if cid:
            ids.append(cid)
        else:
            missing.append(str(x))
    return list(dict.fromkeys(ids)), list(dict.fromkeys(missing))


def coverage(normalized: Path) -> dict:
    """정규화 층 본문 후보(인증·기업 규모)가 별칭 사전으로 개념에 몇 건 이어지는지."""
    generic = {key(x) for x in spec()["not_concepts"]["generic"]}
    tally: dict[str, Counter] = {}
    unmapped: dict[str, Counter] = {}
    for line in normalized.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        for f in json.loads(line).get("facts", []):
            cat = f.get("category") or f.get("attribute")
            if cat not in ("certification", "company_size"):
                continue
            label = (f.get("value") or {}).get("label")
            t = tally.setdefault(cat, Counter())
            if resolve(label):
                t["mapped"] += 1
            elif label is not None and key(label) in generic:
                t["generic_not_concept"] += 1
            else:
                t["unmapped"] += 1
                unmapped.setdefault(cat, Counter())[str(label)] += 1
    return {"source": str(normalized.relative_to(REPO)).replace("\\", "/"), "by_category": {k: dict(v) for k, v in tally.items()},
            "unmapped_top": {k: v.most_common(20) for k, v in unmapped.items()}}


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.path.insert(0, str(REPO / "tools"))
    from graphrag import concept_aliases as M  # 패키지 상대 import를 쓰려고 다시 불러온다
    src = sorted((REPO / "data" / "normalized").glob("2*/notices_normalized.jsonl"))[-1]
    out = M.coverage(src)
    p = REPO / "data" / "eval" / "concept_alias_coverage.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out["by_category"], ensure_ascii=False), "->", p.relative_to(REPO))
