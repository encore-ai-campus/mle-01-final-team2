"""정의의 판정 기준(`Definition.rule_json`) 초안. 지금은 중소기업 하나다.

원칙(기초 설계서 §474, 온톨로지 설계서 §660): 법령 기준 숫자는 기억으로 쓰지 않는다. 업종별 규모 기준은 수집한 별표 원문
(`data/지원사업_법령/별표.jsonl`, 중소기업기본법 시행령 별표 1·3)의 표를 행으로 풀어 만들고, 근거 조문은 원문 해시와 함께 남긴다.

초안이다(`status=draft`, `needs_review=true`). 판정 해석은 팀이 정한다(`docs/RULES_판정_정규화_검토목록_v0.1.md` §5 E-1~E-5).
평가기(`evaluator.py`)의 공고 판정에는 아직 쓰지 않는다. 중소기업을 가리키는 공고 조건이 0개이고 프로필에 업종·매출·자산 입력이 없다.

사용: python tools/graphrag/definition_rules.py   -> data/graph/definition_rules.json (기준 초안과 별표 행 점검 결과)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag.concepts_laws import LAW_DIR, _jsonl, sha  # noqa: E402

SAT, UNSAT, UNK = "SATISFIED", "UNSATISFIED", "UNKNOWN"
DECREE = "중소기업기본법 시행령"
ASSET_LIMIT_EOK = 5000  # 시행령 제3조제1항제1호나목 "자산총액이 5천억원 미만". 아래 rule에서 조문 원문에 이 문구가 있는지 검사한다
ASSET_PHRASE = "자산총액이 5천억원 미만일 것"
_ITEM = re.compile(r"^\s*(\d+)\.\s*(.*)$")
_LIMIT = re.compile(r"([\d,]+)억원\s*이하")
_CODE = re.compile(r"^([A-Z]\d*)(?:\(([A-Z]\d+)\s*제외\))?$")


def appendix(table_no: str) -> dict:
    rows = [r for r in _jsonl(LAW_DIR / "별표.jsonl") if r.get("doc_name") == DECREE and r.get("table_no") == table_no]
    if len(rows) != 1:
        raise ValueError(f"{DECREE} 별표 {table_no}가 {len(rows)}개")
    return rows[0]


def parse_size_table(text: str) -> list[dict]:
    """별표 1·3의 상자 표를 행으로 푼다. 규모 기준 칸은 묶음(가로줄 ┼ 두 개로 끊긴 구간)의 첫 행에만 있으므로 묶음 단위로 나눠 준다."""
    groups: list[dict] = [{"items": [], "limit": None}]
    for line in text.splitlines():
        if line.startswith("├") and line.count("┼") == 2:  # 세 칸을 모두 끊는 줄 = 새 묶음
            groups.append({"items": [], "limit": None})
            continue
        m = _LIMIT.search(line)
        if m and line.startswith(("├", "│")):
            groups[-1]["limit"] = int(m.group(1).replace(",", ""))
        if not line.startswith("│"):
            continue
        cells = [c.strip() for c in line.strip("│").split("│")]
        if len(cells) != 3 or cells[0].startswith("해당 기업"):
            continue
        it = _ITEM.match(cells[0])
        if it:
            groups[-1]["items"].append({"no": int(it.group(1)), "industry": it.group(2), "code": cells[1]})
        elif groups[-1]["items"]:  # 업종 이름·분류기호가 두 줄에 걸친 경우
            last = groups[-1]["items"][-1]
            last["industry"] += cells[0]
            last["code"] += cells[1]
    rows = []
    for g in groups:
        for it in g["items"]:
            m = _CODE.match(it["code"].replace(" ", ""))
            if not m or g["limit"] is None:
                raise ValueError(f"별표 행을 풀지 못함: {it} limit={g['limit']}")
            rows.append({"no": it["no"], "industry": it["industry"], "ksic": m.group(1), "ksic_excluded": m.group(2),
                         "max_avg_sales_eok": g["limit"]})
    return sorted(rows, key=lambda r: r["no"])


def match_industry(rows: list[dict], ksic: str) -> list[dict]:
    """한국표준산업분류 코드(예: C2811, J58, F) -> 맞는 별표 행. 가장 긴 접두 코드가 이긴다(E36이 E보다 먼저)."""
    k = ksic.strip().upper()
    hits = [r for r in rows if k.startswith(r["ksic"]) and not (r["ksic_excluded"] and k.startswith(r["ksic_excluded"]))]
    if not hits:
        return []
    best = max(len(r["ksic"]) for r in hits)
    return [r for r in hits if len(r["ksic"]) == best]


def _notes(text: str) -> str:
    return text[text.index("비고"):] if "비고" in text else ""


def sme_rule() -> dict:
    """중소기업 판정 기준 초안. 숫자는 별표·조문 원문에서 읽고, 읽은 원문의 해시를 남긴다."""
    t1, t3 = appendix("0001"), appendix("0003")
    arts = {r["article_no"]: r for r in _jsonl(LAW_DIR / "조문.jsonl") if r.get("doc_name") == DECREE and r.get("level") == "article"}
    a3 = arts["3"]["text"]
    if ASSET_PHRASE not in a3:
        raise ValueError("시행령 제3조 원문에서 자산총액 기준 문구를 찾지 못함")
    n1, n3 = _notes(t1["text"]), _notes(t3["text"])
    return {
        "rule_id": "RULE:중소기업:v0.1", "term": "중소기업", "status": "draft", "needs_review": True, "checked_at": "2026-11-26",
        "basis": [
            {"law": "중소기업기본법", "article": "제2조 제1항~제3항"},
            {"law": DECREE, "article": "제3조", "text_hash": sha(a3), "effective": arts["3"]["effective"]},
            {"law": DECREE, "article": "제8조", "text_hash": sha(arts["8"]["text"])},
            {"law": DECREE, "appendix": "별표 1", "title": t1["title"], "text_hash": sha(t1["text"]), "effective": t1["effective"]},
            {"law": DECREE, "appendix": "별표 3", "title": t3["title"], "text_hash": sha(t3["text"]), "effective": t3["effective"]},
        ],
        # 법 제2조제1항제1호(영리기업) 경로만 숫자로 판정한다. 제2호~제5호(사회적기업·협동조합 등)와 독립성·공시대상기업집단은 입력이 있어야 본다
        "logic": {"op": "AND", "children": [
            {"id": "S1", "fact": "avg_sales_eok", "by": "main_industry_ksic", "op": "LTE", "table": "size_table", "basis": "시행령 제3조제1항제1호가목, 별표 1"},
            {"id": "S2", "fact": "total_assets_eok", "op": "LT", "value": ASSET_LIMIT_EOK, "basis": "시행령 제3조제1항제1호나목"},
            {"id": "S3", "fact": "independence_ok", "op": "EQ", "value": True, "basis": "법 제2조제1항제1호나목, 시행령 제3조제1항제2호"},
            {"id": "S4", "fact": "disclosure_group_member", "op": "EQ", "value": False, "basis": "법 제2조제1항 단서(공시대상기업집단)"},
        ]},
        # 사회적기업·협동조합 등도 규모·자산 기준(시행령 제3조제1항제1호)은 같다(제3조제2항제1호, 제3항~제5항이 제2항 준용). 다른 것은 독립성 기준(S3)이다
        "alternatives": [{"id": "ALT1", "text": "사회적기업·협동조합 등(법 제2조제1항제2호~제5호, 시행령 제3조제2항~제5항). S1·S2는 같고 S3 대신 제3조제1항제2호나목만 본다",
                          "evaluable": "input_only"}],
        "grace": {"text": "규모가 커져 중소기업이 아니게 된 다음 연도부터 5년간 중소기업으로 본다(법 제2조제3항, 제외 사유 시행령 제9조)",
                  "fact": "in_grace_period", "evaluable": "input_only"},
        "size_table": parse_size_table(t1["text"]),
        "size_table_notes": n1,
        "small_table": parse_size_table(t3["text"]),
        "small_table_notes": n3,
        "special_cases": [  # 별표 비고 2: 분류기호 안의 일부 품목만 기준이 달라 코드만으로는 정할 수 없다
            {"ksic": "C30393", "max_avg_sales_eok": 1500, "partial": False, "source": "별표 1 비고 2"},
            {"ksic": "C31202", "max_avg_sales_eok": 1500, "partial": True, "item": "철도 차량용 의자 제조업", "source": "별표 1 비고 2"},
            {"ksic": "C31322", "max_avg_sales_eok": 1500, "partial": True, "item": "항공기용 의자 제조업", "source": "별표 1 비고 2"},
        ],
        "small_special_cases": [  # 별표 3 비고 2
            {"ksic": "C31202", "max_avg_sales_eok": 120, "partial": True, "item": "철도 차량용 의자 제조업", "source": "별표 3 비고 2"},
            {"ksic": "C31322", "max_avg_sales_eok": 120, "partial": True, "item": "항공기용 의자 제조업", "source": "별표 3 비고 2"},
        ],
        "units": {"avg_sales_eok": "억원(평균매출액등, 시행령 제7조 산정)", "total_assets_eok": "억원(직전 사업연도 말 자산총계, 시행령 제7조의2)"},
    }


def _special(rule: dict, ksic: str) -> dict | None:
    k = ksic.strip().upper()
    return next((s for s in rule["special_cases"] if k.startswith(s["ksic"])), None)


def evaluate_sme(rule: dict, facts: dict) -> dict:
    """사업자 사실(facts) -> 중소기업 여부 3값. 모르는 값은 UNKNOWN이고, '제한 없음'으로 바꾸지 않는다.

    facts: main_industry_ksic(str), avg_sales_eok(float), total_assets_eok(float), independence_ok(bool),
           disclosure_group_member(bool), in_grace_period(bool). 없으면 입력하지 않은 것이다.
    """
    steps = []
    k, sales = facts.get("main_industry_ksic"), facts.get("avg_sales_eok")
    if k is None or sales is None:
        steps.append(("S1", UNK, "주된 업종 또는 평균매출액등 미입력"))
    else:
        sp = _special(rule, k)
        rows = match_industry(rule["size_table"], k)
        if sp and sp["partial"]:
            steps.append(("S1", UNK, f"{k}는 별표 1 비고 2에 따라 {sp['item']}만 기준이 다름. 코드만으로 정할 수 없음"))
        elif sp:
            ok = sales <= sp["max_avg_sales_eok"]
            steps.append(("S1", SAT if ok else UNSAT, f"{k} 비고 2 기준 {sp['max_avg_sales_eok']:,}억원 이하, 입력 {sales:g}억원"))
        elif len({r["max_avg_sales_eok"] for r in rows}) != 1:
            steps.append(("S1", UNK, f"업종 코드 {k}를 별표 1 행에 대응시키지 못함"))
        else:
            r = rows[0]
            ok = sales <= r["max_avg_sales_eok"]
            steps.append(("S1", SAT if ok else UNSAT, f"{r['industry']}({r['ksic']}) {r['max_avg_sales_eok']:,}억원 이하, 입력 {sales:g}억원"))
    a = facts.get("total_assets_eok")
    steps.append(("S2", UNK, "자산총액 미입력") if a is None else
                 ("S2", SAT if a < ASSET_LIMIT_EOK else UNSAT, f"자산총액 {a:g}억원, 기준 {ASSET_LIMIT_EOK:,}억원 미만"))
    ind = facts.get("independence_ok")
    steps.append(("S3", UNK if ind is None else (SAT if ind else UNSAT), "독립성 기준(관계기업·대기업 출자) " + ("미입력" if ind is None else "입력값")))
    grp = facts.get("disclosure_group_member")
    steps.append(("S4", UNK if grp is None else (UNSAT if grp else SAT), "공시대상기업집단 소속 " + ("미입력" if grp is None else ("예" if grp else "아니오"))))
    st = [s for _, s, _ in steps]
    status = UNSAT if UNSAT in st else (SAT if all(s == SAT for s in st) else UNK)
    if status == UNSAT and facts.get("in_grace_period") is True and not facts.get("disclosure_group_member"):
        status, steps = UNK, steps + [("GRACE", UNK, "유예기간(법 제2조제3항) 입력. 시행령 제9조 제외 사유 확인 필요")]
    return {"status": status, "steps": [{"id": i, "status": s, "reason": r} for i, s, r in steps], "rule_id": rule["rule_id"]}


def run() -> dict:
    rule = sme_rule()
    out = Path(__file__).resolve().parents[2] / "data" / "graph" / "definition_rules.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"DEF:중소기업": rule}, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"size_rows": len(rule["size_table"]), "small_rows": len(rule["small_table"]),
            "size_limits": sorted({r["max_avg_sales_eok"] for r in rule["size_table"]}, reverse=True),
            "small_limits": sorted({r["max_avg_sales_eok"] for r in rule["small_table"]}, reverse=True), "out": str(out)}


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))
