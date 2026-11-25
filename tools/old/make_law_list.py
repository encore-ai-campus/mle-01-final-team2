#!/usr/bin/env python
"""사규(parsed JSON)에서 인용된 '코퍼스 밖' 문서 목록을 집계해 동료(국가 법령 수집 담당)에게 전달할 목록을 만든다.

출력:
    docs/LAW_COLLECTION_LIST.md      사람이 읽는 목록(우선순위별)
    data/law_collection_list.csv     같은 내용(엑셀용, UTF-8 BOM)

우선순위:
    1순위 = 핵심 문서 16개(docs/MLE_2팀_기초 설계.md 부록 A)가 인용한 법령·감독규정
    2순위 = 그 외 사규가 인용한 법령·감독규정
    별도  = 국가 법령이 아닌 IBK 내규(ALIO에서 추가 확보 후보)

실행: python tools/make_law_list.py
"""
from __future__ import annotations

import collections
import csv
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CORE = ["내부통제규정", "금융소비자보호에관한내부통제규정", "금융소비자보호규정", "금융소비자보호에관한민원예방및사후구제규정",
        "자금세탁방지업무취급규정", "자금세탁방지업무취급지침", "준법지원규정", "준법제보제도운영규정",
        "기업은행이해충돌방지지침", "기업은행임직원행동강령", "개인·신용정보관리및보호규정", "정보보호규정",
        "AI위험관리규정", "광고및상품공시에관한업무지침", "리스크관리규정", "내부통제위원회규정"]

# 같은 법령의 표기 차이·약칭을 하나로 합친다. (키: 공백 제거한 표기 → 대표 표기)
ALIAS = {
    "금융소비자보호에관한법률": "금융소비자 보호에 관한 법률",
    "금융소비자보호법": "금융소비자 보호에 관한 법률",
    "금소법": "금융소비자 보호에 관한 법률",
    "개인정보보호법": "개인정보 보호법",
    "특정금융정보법": "특정 금융거래정보의 보고 및 이용 등에 관한 법률",
    "특정금융거래정보의보고및이용등에관한법률": "특정 금융거래정보의 보고 및 이용 등에 관한 법률",
    "금융실명법": "금융실명거래 및 비밀보장에 관한 법률",
    "금융실명거래및비밀보장에관한법률": "금융실명거래 및 비밀보장에 관한 법률",
    "이해충돌방지법": "공직자의 이해충돌 방지법",
    "공직자의이해충돌방지법": "공직자의 이해충돌 방지법",
    "대부업등의등록및금융이용자보호에관한법률": "대부업 등의 등록 및 금융이용자 보호에 관한 법률",
    "공중협박자금조달금지법": "공중 등 협박목적 및 대량살상무기 확산을 위한 자금조달행위의 금지에 관한 법률",
    "청탁금지법": "부정청탁 및 금품등 수수의 금지에 관한 법률",
    "부패방지권익위법": "부패방지 및 국민권익위원회의 설치와 운영에 관한 법률",
    "표시광고법": "표시·광고의 공정화에 관한 법률",
    "신용정보법": "신용정보의 이용 및 보호에 관한 법률",
    "범죄수익규제법": "범죄수익은닉의 규제 및 처벌 등에 관한 법률",
    "공공재정환수법": "공공재정 부정청구 금지 및 부정이익 환수 등에 관한 법률",
    "공공재정부정청구금지및부정이익환수등에관란법률": "공공재정 부정청구 금지 및 부정이익 환수 등에 관한 법률",  # 원문 오탈자('관란')
    "특정금융정보법시행령": "특정 금융거래정보의 보고 및 이용 등에 관한 법률 시행령",
}
# 약칭 → 정식명칭 힌트(법제처에서 최종 확인할 것)
FORMAL_HINT: dict[str, str] = {}

RE_LAW = re.compile(r"(법|법률|시행령|시행규칙)$")
RE_SUP = re.compile(r"(감독규정|감독업무시행세칙|고시|가이드라인|프레임워크)$")
RE_INTERNAL = re.compile(r"(규정|지침|세칙|기준|매뉴얼|업무방법서|내규|강령|원칙|규범|지침서)$")


def norm(s: str) -> str:
    return re.sub(r"[\s「」]", "", s)


def clean(name: str) -> str:
    name = re.sub(r"\(이하[^)]*\)", "", name)  # "(이하 “금소법”이라 한다)" 제거
    return name.strip()


def classify(name: str) -> str:
    if RE_SUP.search(name):
        return "감독규정·고시·가이드라인"
    if RE_LAW.search(name):
        return "법령"
    if RE_INTERNAL.search(name):
        return "내규(국가 법령 아님)"
    return "분류 불명(확인 필요)"


def main() -> int:
    docs = [json.loads(Path(f).read_text(encoding="utf-8")) for f in glob.glob(str(ROOT / "data/ibk_converted/parsed/*.json"))]
    if not docs:
        print("data/ibk_converted/parsed 가 비어 있습니다. 먼저 tools/convert_ibk.py 를 실행하세요.", file=sys.stderr)
        return 1
    corpus = {norm(d["doc"]["title"]) for d in docs}
    core_ids = {d["doc"]["id"] for d in docs if norm(d["doc"]["title"]) in CORE}

    agg: dict[str, dict] = {}
    for d in docs:
        is_core = d["doc"]["id"] in core_ids
        for r in d["external_refs"]:
            raw = r.get("target_name")
            if not raw:
                continue
            name = clean(raw)
            key = norm(name)
            if key in corpus or not key:
                continue
            rep = ALIAS.get(key, name)
            a = agg.setdefault(norm(rep), {"name": rep, "variants": set(), "count": 0, "core_count": 0,
                                           "docs": collections.Counter(), "articles": set()})
            a["variants"].add(raw.strip())
            a["count"] += 1
            a["core_count"] += is_core
            a["docs"][d["doc"]["title"]] += 1
            if r.get("target_article"):
                a["articles"].add(r["target_article"])

    rows = []
    for a in agg.values():
        a["kind"] = classify(a["name"])
        a["hint"] = FORMAL_HINT.get(a["name"], "")
        rows.append(a)
    rows.sort(key=lambda a: (-a["core_count"], -a["count"], a["name"]))

    def tier(a):
        if a["kind"] == "내규(국가 법령 아님)":
            return "별도"
        if a["kind"].startswith("분류 불명"):
            return "확인"
        return "1순위" if a["core_count"] else "2순위"

    for a in rows:
        a["tier"] = tier(a)

    # CSV
    out_csv = ROOT / "data" / "law_collection_list.csv"
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["우선순위", "구분", "법령명(대표 표기)", "(예비)", "총 인용 수", "핵심문서 인용 수",
                    "인용 조문 번호", "인용한 사규(상위 3)", "문서 내 표기 변형"])
        for a in rows:
            w.writerow([a["tier"], a["kind"], a["name"], a["hint"], a["count"], a["core_count"],
                        ", ".join(sorted(a["articles"]))[:80], " / ".join(t for t, _ in a["docs"].most_common(3)),
                        " | ".join(sorted(a["variants"])) if len(a["variants"]) > 1 else ""])

    # Markdown
    def table(items, cols):
        lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
        for i, a in enumerate(items, 1):
            var = " / ".join(sorted(v for v in a["variants"] if norm(v) != norm(a["name"])))
            lines.append(f"| {i} | {a['name']} | {a['core_count']} | {a['count']} | "
                         f"{', '.join(t for t, _ in a['docs'].most_common(2))} | {var} |")
        return "\n".join(lines)

    cols = ["#", "법령명", "핵심문서 인용", "전체 인용", "주로 인용한 사규", "사규 내 다른 표기(약칭 등)"]
    t1 = [a for a in rows if a["tier"] == "1순위"]
    t2 = [a for a in rows if a["tier"] == "2순위"]
    sep = [a for a in rows if a["tier"] == "별도"]
    unk = [a for a in rows if a["tier"] == "확인"]
    md = f"""# 국가 법령 수집 요청 목록

> 생성: `python tools/make_law_list.py` (사규 148종의 `「…」` 인용에서 자동 집계)
> 전체 목록(CSV): [data/law_collection_list.csv](../data/law_collection_list.csv)

## 사용 방법
- **1순위**: 우리 팀 핵심 문서 16개(설계서 [부록 A](MLE_2팀_기초%20설계.md))가 인용한 법령·감독규정. 먼저 수집해 주세요.
- **2순위**: 그 외 사규가 인용한 법령·감독규정. 시간이 되면 빈도순으로.
- 법령은 **법률·시행령·시행규칙을 함께** 수집하면 위임 관계(법 → 시행령)를 그래프로 이을 수 있습니다.
- 사규에는 약칭·표기 차이가 섞여 있어서 같은 법령의 변형은 합치고 **법제처 정식명칭 기준으로 적었습니다**(약칭은 마지막 열). 최종 확인은 법제처에서 해 주세요.
- 수집 후 전달 형식(조문 단위 JSON 권장)은 팀에서 정한 뒤 맞춥니다.

## 요약
| 구분 | 개수 |
|---|---|
| 1순위 (핵심 문서가 인용) | {len(t1)} |
| 2순위 | {len(t2)} |
| 별도: 국가 법령이 아닌 IBK 내규 | {len(sep)} |
| 분류 불명(확인 필요) | {len(unk)} |

## 1순위 — 핵심 문서가 인용한 법령·감독규정

{table(t1, cols)}

## 2순위 — 그 외 사규가 인용 (인용 많은 상위 40)

{table(t2[:40], cols)}

→ 나머지 {max(0, len(t2) - 40)}건은 CSV 참고.

## 별도 — 국가 법령이 아닌 IBK 내규 (상위 15)
ALIO에서 추가로 구할 수 있는지 확인이 필요합니다. 법령 수집 대상은 아닙니다.

{table(sep[:15], cols)}

## 분류 불명 (상위 15)
이름만으로 법령인지 내규인지 구분하지 못한 항목입니다. CSV에서 검토해 주세요.

{table(unk[:15], cols)}

---
*분류(법령/감독규정/내규)는 이름 끝말로 판단한 휴리스틱이라 오분류가 있을 수 있습니다.*
"""
    (ROOT / "docs" / "LAW_COLLECTION_LIST.md").write_text(md, encoding="utf-8")
    print(f"1순위 {len(t1)} | 2순위 {len(t2)} | 내규 {len(sep)} | 불명 {len(unk)} | 합계 {len(rows)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
