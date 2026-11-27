#!/usr/bin/env python3
"""도메인 온톨로지 설계서용 그림 2개를 만든다 (양식의 개념 그래프·인스턴스 그래프 예시에 대응).

- ontology_concept.png : 클래스와 관계(개념 모델, v0.2)
- ontology_instance.png: 실제 공고(`BIZINFO:PBLN_000000000121231`)와 코드표 위의 인스턴스 예시. 사용자 값과 평가는 가상(손계산).

출력: docs/diagrams/, docs/submission/ontology/
사용: python tools/make_ontology_diagrams.py
"""
from __future__ import annotations

import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
font_manager.fontManager.addfont("C:/Windows/Fonts/malgun.ttf")
font_manager.fontManager.addfont("C:/Windows/Fonts/malgunbd.ttf")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False})
EDGE, FILL, ARROW = "#1f4e79", "#e8f0f9", "#2a7f98"
W, H = 17, 6


def box(ax, x, y, text, sub=None, w=W, h=H, fill=FILL, edge=EDGE, ls="-", fs=10.5, color="#14365c"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.25,rounding_size=1.2", fc=fill, ec=edge, lw=1.8, ls=ls))
    ax.text(x + w / 2, y + h / 2 + (0.9 if sub else 0), text, ha="center", va="center", fontsize=fs, weight="bold", color=color)
    if sub:
        ax.text(x + w / 2, y + h / 2 - 1.3, sub, ha="center", va="center", fontsize=7.5, color="#556")


def arrow(ax, p, q, label="", dx=0, dy=0, ls="-", color=ARROW, fs=8):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color=color, lw=1.7, ls=ls, shrinkA=0, shrinkB=0))
    if label:
        ax.text((p[0] + q[0]) / 2 + dx, (p[1] + q[1]) / 2 + dy, label, ha="center", va="center", fontsize=fs, color="#222",
                bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9))


def mid(x, y, side, w=W, h=H):
    return {"r": (x + w, y + h / 2), "l": (x, y + h / 2), "t": (x + w / 2, y + h), "b": (x + w / 2, y)}[side]


def concept(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 6.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(-11, 64)
    ax.axis("off")
    for y0, y1, label, col in ((38, 62, "메타 층 (규칙으로 생성)", "#dbe8f7"), (17, 36, "요건 층 (추출 + 검수)", "#fdebd0"), (-2, 15, "개념 계층 (코드표·사전) + 법령 근거", "#dff0df")):
        ax.add_patch(FancyBboxPatch((1, y0), 98, y1 - y0, boxstyle="round,pad=0.2,rounding_size=1.5", fc=col, ec="none", alpha=0.55))
        ax.text(2.2, y1 - 2.2, label, fontsize=9, weight="bold", color="#334")
    P = {"Organization": (3, 47), "Notice": (33, 47), "SupportCategory": (64, 54), "Attachment": (64, 41),
         "Program": (2, 22), "Track": (22, 22), "Requirement": (50, 22), "Condition": (78, 22),
         "Concept": (78, 1), "Definition": (52, 1), "LawArticle": (27, 1), "ExternalLaw": (3, 1)}
    for k, (x, y) in P.items():
        box(ax, x, y, k, sub="+ LawAppendix(별표)" if k == "LawArticle" else None, fill="#ffffff" if k in ("Program", "Track") else FILL, ls="--" if k in ("Program", "Track") else "-")
    arrow(ax, mid(*P["Notice"], "l"), mid(*P["Organization"], "r"), "ANNOUNCED_BY\nEXECUTED_BY", dy=2.6)
    arrow(ax, mid(*P["Notice"], "r"), mid(*P["SupportCategory"], "l"), "IN_SUPPORT_CATEGORY", dy=3.2, dx=-1)
    arrow(ax, mid(*P["Notice"], "r"), mid(*P["Attachment"], "l"), "HAS_ATTACHMENT", dy=-3.0, dx=-1)
    arrow(ax, (P["Notice"][0] + 4, P["Notice"][1]), mid(*P["Program"], "t"), "OF_PROGRAM", dx=-2, dy=1)
    arrow(ax, (P["Notice"][0] + 8, P["Notice"][1]), mid(*P["Track"], "t"), "HAS_TRACK", dx=-2, dy=0.5)
    arrow(ax, (P["Notice"][0] + 12, P["Notice"][1]), mid(*P["Requirement"], "t"), "HAS_REQUIREMENT", dx=3, dy=1.5)
    arrow(ax, mid(*P["Track"], "r"), mid(*P["Requirement"], "l"), "HAS_REQUIREMENT", dy=2.2)
    arrow(ax, mid(*P["Requirement"], "r"), mid(*P["Condition"], "l"), "HAS_CONDITION", dy=2.2)
    arrow(ax, mid(*P["Condition"], "b"), mid(*P["Concept"], "t"), "ABOUT", dx=3.5)
    arrow(ax, mid(*P["Concept"], "l"), mid(*P["Definition"], "r"), "DEFINED_BY", dy=2.2)
    arrow(ax, mid(*P["Definition"], "l"), mid(*P["LawArticle"], "r"), "CITES_LAW", dy=2.2)
    arrow(ax, mid(*P["LawArticle"], "l"), mid(*P["ExternalLaw"], "r"), "PART_OF", dy=2.2)
    arrow(ax, (P["Requirement"][0] + 3, P["Requirement"][1]), mid(*P["LawArticle"], "t"), "CITES", dx=-5, dy=2)
    ax.text(3, -4.5, "Concept(scheme) 내부: IS_A(종류) · WITHIN(행정 포함) · MEMBER_OF(권역 묶음) · SUCCEEDED_BY(개편), 하위→상위", fontsize=8.5, color="#254")
    ax.text(3, -6.8, "공고 간: SUPERSEDES(새→이전) · SAME_AS(포털 간 중복)  |  공고→지역: TARGETS_REGION", fontsize=8.5, color="#254")
    ax.text(3, -9.1, "점선 상자(Program, Track)는 설계만, Attachment·CITES는 데이터만 있고 적재 전. 나머지 상자·관계는 Aura에 적재했다(2026-11-27, 요건·조건은 구조화 필드분).", fontsize=7.5, color="#555")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def instance(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(12.5, 8.2))
    ax.set_xlim(0, 100)
    ax.set_ylim(-24, 66)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((1, 59), 12, 5, boxstyle="round,pad=0.2,rounding_size=1.2", fc="#4a7fd6", ec="none"))
    ax.text(7, 61.5, "인스턴스 예시", ha="center", va="center", color="white", fontsize=11, weight="bold")
    ax.text(15, 61.5, "코드표와 실제 공고(BIZINFO:PBLN_000000000121231) 위의 그래프 (사용자 값·평가는 가상, 손계산)", va="center", fontsize=11, weight="bold", color="#1b3b73")
    bw, bh = 19, 7
    # 지역 사슬
    n = {"namgu": (1, 51), "gj": (31, 51), "merged": (61, 51), "notice": (1, 29), "r1": (31, 29), "c1": (56, 40), "c2": (56, 29), "c3": (56, 18),
         "sme": (80, 29), "defn": (80, 18), "law": (80, 7)}
    box(ax, *n["namgu"], "남구", "Concept · REGION:1227000000", w=bw, h=bh)
    box(ax, *n["gj"], "광주(구)", "묶음 개념 · 미검수(H11)", w=bw, h=bh, fill="#fff4d6", edge="#c07a00", ls="--")
    box(ax, *n["merged"], "전남광주통합특별시", "Concept · REGION:1200000000", w=bw, h=bh, fs=9.5)
    box(ax, *n["notice"], "공고 121231", "[광주] 소상공인 SNS·블로그 홍보지원", w=bw, h=bh, fill="#fdebd0", edge="#c0600a", color="#7a3a00")
    box(ax, *n["r1"], "R1 자격요건", "Requirement · logic=AND(추정)", w=bw, h=bh)
    box(ax, *n["c1"], "C1 지역", "region WITHIN 광주(구)", w=bw, h=6)
    box(ax, *n["c2"], "C2 소상공인", "company_size IS_A 소상공인", w=bw, h=6)
    box(ax, *n["c3"], "C3 확인서", "certification: 중소기업확인서", w=bw, h=6)
    box(ax, *n["sme"], "소상공인", "Concept · APPLICANT_TYPE", w=bw, h=6)
    box(ax, *n["defn"], "Definition", "원문 없음(rule_json 비어 있음)", w=bw, h=6, fill="#f1f1f1", edge="#888", ls="--", color="#555")
    box(ax, *n["law"], "소상공인기본법", "ExternalLaw 후보 · 미수집", w=bw, h=6, fill="#f1f1f1", edge="#888", ls="--", color="#555")
    arrow(ax, mid(*n["namgu"], "r", bw, bh), mid(*n["gj"], "l", bw, bh), "MEMBER_OF", dy=2.0)
    arrow(ax, mid(*n["gj"], "r", bw, bh), mid(*n["merged"], "l", bw, bh), "MEMBER_OF", dy=2.0)
    arrow(ax, mid(*n["notice"], "r", bw, bh), mid(*n["r1"], "l", bw, bh), "HAS_REQUIREMENT", dy=2.2)
    arrow(ax, (n["r1"][0] + bw, n["r1"][1] + 5), (n["c1"][0], n["c1"][1] + 3), "HAS_CONDITION", dx=-2, dy=3.6)
    arrow(ax, (n["r1"][0] + bw, n["r1"][1] + 3), (n["c2"][0], n["c2"][1] + 3), "", dy=0)
    arrow(ax, (n["r1"][0] + bw, n["r1"][1] + 1), (n["c3"][0], n["c3"][1] + 3), "", dy=0)
    arrow(ax, (n["c1"][0] + 3, n["c1"][1] + 6), (n["gj"][0] + 12, n["gj"][1]), "ABOUT", dx=5, dy=0.5)
    arrow(ax, (n["c2"][0] + bw, n["c2"][1] + 3), mid(*n["sme"], "l", bw, 6), "ABOUT", dy=2.0)
    arrow(ax, mid(*n["sme"], "b", bw, 6), mid(*n["defn"], "t", bw, 6), "DEFINED_BY", dx=5, color="#888", ls="--")
    arrow(ax, mid(*n["defn"], "b", bw, 6), mid(*n["law"], "t", bw, 6), "CITES_LAW", dx=5, color="#888", ls="--")
    ax.text(2, 3.5, "실선: 정리 파일·코드표에서 만든 관계  /  점선: 근거 데이터가 없는 관계(법령 원문 미수집, 묶음 사전 검수 전)", fontsize=8.5, color="#445")
    ax.text(2, 0.5, "• 남구 → 광주(구) → 전남광주통합특별시: 코드표에 광주광역시가 없어 묶음 개념이 있어야 \"광주광역시 관내\"에 닿는다.", fontsize=8.5, color="#445")
    ax.text(2, -2.5, "• 소상공인 정의의 법령 원문이 없어 사슬이 끊긴다(CHAIN_BROKEN) → 결과는 NEEDS_CHECK.", fontsize=8.5, color="#445")
    for y, (tag, col, text) in ((-8.5, ("Q", "#1fb28a", "광주 남구에 사업장이 있는 소상공인이 [광주] 소상공인 SNS·블로그 홍보지원 공고에 신청할 수 있나? (가상 입력)")),
                                (-15.5, ("A", "#f08c00", "지역 조건은 충족(남구→광주(구), 1 hop). 소상공인 기준은 법령 원문이 없고 중소기업확인서 보유도 미입력이라 '확인 필요'입니다."))):
        ax.add_patch(FancyBboxPatch((2, y - 1.8), 4, 4.2, boxstyle="round,pad=0.15,rounding_size=1", fc=col, ec="none"))
        ax.text(4, y + 0.3, tag, ha="center", va="center", color="white", weight="bold", fontsize=11)
        ax.text(8, y + 0.3, text, va="center", fontsize=9.5, weight="bold" if tag == "Q" else "normal", color="#222")
    ax.text(2, -21.5, "근거 경로: 공고 원문 문장(\"광주광역시 관내 소상공인\") → 조건 C1·C2 → 개념 → (정의 → 법령). 수집 시각 2026-11-24, 참고용.", fontsize=8, color="#666")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _node(ax, cx, cy, w, h, title, sub=None, fill="#e1f5ee", edge="#0f6e56", color="#085041", fs=10):
    ax.add_patch(FancyBboxPatch((cx - w / 2, cy - h / 2), w, h, boxstyle="round,pad=0.2,rounding_size=1.0", fc=fill, ec=edge, lw=1.4))
    ax.text(cx, cy + (1.1 if sub else 0), title, ha="center", va="center", fontsize=fs, weight="bold", color=color)
    if sub:
        ax.text(cx, cy - 1.6, sub, ha="center", va="center", fontsize=7.5, color=color)


def _line(ax, p, q):
    ax.annotate("", xy=q, xytext=p, arrowprops=dict(arrowstyle="-|>", color="#5f5e5a", lw=1.3, shrinkA=0, shrinkB=0))


def condition_tree(path: Path) -> None:
    """공고 한 건의 조건 트리(요건 → GROUP 게이트 → ATOM). 조건 이름은 구조를 보이기 위한 예시."""
    fig, ax = plt.subplots(figsize=(11, 6.4))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")
    gray = dict(fill="#f1efe8", edge="#5f5e5a", color="#2c2c2a")
    purple = dict(fill="#eeedfe", edge="#534ab7", color="#26215c")
    teal = dict(fill="#e1f5ee", edge="#0f6e56", color="#04342c")
    _node(ax, 50, 56, 22, 5.5, "공고 Notice", **gray)
    for x in (27, 66, 90):
        _line(ax, (50, 53.2), (x, 47.5))
    _node(ax, 27, 44, 44, 7, "ELIGIBILITY 자격", "모두 통과해야 함", **gray)
    _node(ax, 66, 44, 22, 7, "EXCLUSION 제외", "걸리면 탈락", **gray)
    _node(ax, 90, 44, 16, 7, "PREFERENCE 우대", "점수·가점", **gray)
    for x in (27, 66, 90):
        _line(ax, (x, 40.3), (x, 36.5))
    _node(ax, 27, 33, 44, 7, "GROUP: AND", "모두 충족해야 충족", **purple)
    _node(ax, 66, 33, 22, 7, "GROUP: NONE_OF", "하나라도 해당=탈락", **purple)
    _node(ax, 90, 33, 16, 7, "수출 기업", "판정 불변, 가점만", **teal)
    for x in (11, 27, 44):
        _line(ax, (27, 29.3), (x, 24.5))
    for x in (62, 76):
        _line(ax, (66, 29.3), (x, 24.5))
    _node(ax, 11, 21, 12, 6, "지역", **teal)
    _node(ax, 27, 21, 12, 6, "업력", **teal)
    _node(ax, 44, 21, 20, 7, "GROUP: OR", "하나만 충족해도 충족", **purple)
    _node(ax, 62, 21, 12, 6, "휴폐업", **teal)
    _node(ax, 76, 21, 12, 6, "세금체납", **teal)
    for x in (38, 50):
        _line(ax, (44, 17.5), (x, 12.5))
    _node(ax, 38, 9, 11, 6, "중소기업", **teal)
    _node(ax, 51, 9, 11, 6, "소상공인", **teal)
    ax.add_patch(FancyBboxPatch((3, 1.2), 2.2, 2.2, boxstyle="round,pad=0.1", fc=purple["fill"], ec=purple["edge"], lw=1.2))
    ax.text(6.5, 2.3, "GROUP: 논리 게이트 (AND, OR, NONE_OF, AT_LEAST), 3단까지 중첩", va="center", fontsize=8.5, color="#333")
    ax.add_patch(FancyBboxPatch((57, 1.2), 2.2, 2.2, boxstyle="round,pad=0.1", fc=teal["fill"], ec=teal["edge"], lw=1.2))
    ax.text(60.5, 2.3, "ATOM: 값 하나를 비교하는 조건", va="center", fontsize=8.5, color="#333")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def gate_rules(path: Path) -> None:
    """게이트별 3값 합성 규칙표(tools/graphrag/label_eval.py의 combine과 같다)."""
    rows = [("AND", "하위가 전부 충족", "하나라도 불충족", "그 외"),
            ("OR", "하나라도 충족", "전부 불충족", "그 외"),
            ("NONE_OF", "전부 해당 안 함(불충족)", "하나라도 해당(충족)", "그 외"),
            ("AT_LEAST n", "충족 개수 ≥ n", "충족 + 모름 < n", "그 외")]
    heads = ("게이트", "충족 SATISFIED", "불충족 UNSATISFIED", "모름 UNKNOWN")
    cols = [("#f1efe8", "#2c2c2a"), ("#eaf3de", "#27500a"), ("#fcebeb", "#791f1f"), ("#faeeda", "#633806")]
    xs, ws = (0, 14, 42, 71), (13, 27, 28, 27)
    fig, ax = plt.subplots(figsize=(10.5, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(-4, 40)
    ax.axis("off")
    for x, w, h, (fc, tc) in zip(xs, ws, heads, cols):
        ax.text(x + w / 2, 36, h, ha="center", va="center", fontsize=10, weight="bold", color="#444")
    for i, r in enumerate(rows):
        y = 28 - i * 7.5
        for j, (x, w, t) in enumerate(zip(xs, ws, r)):
            fc, tc = cols[j]
            ax.add_patch(FancyBboxPatch((x, y - 2.6), w, 5.2, boxstyle="round,pad=0.1,rounding_size=0.8", fc=fc, ec="none"))
            ax.text(x + w / 2, y, t, ha="center", va="center", fontsize=10, weight="bold" if j == 0 else "normal", color=tc)
    ax.text(0, -2.5, "공고 판정: 자격 요건 중 하나라도 불충족이거나 제외에 걸리면 NOT_ELIGIBLE, 모두 충족이면 ELIGIBLE, 모르는 값이 남으면 NEEDS_CHECK", fontsize=8.5, color="#555")
    fig.savefig(path, dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def main() -> None:
    d1 = REPO / "docs" / "diagrams"
    d2 = REPO / "docs" / "submission" / "ontology"
    d1.mkdir(parents=True, exist_ok=True)
    d2.mkdir(parents=True, exist_ok=True)
    concept(d1 / "ontology_concept.png")
    instance(d1 / "ontology_instance.png")
    condition_tree(d1 / "ontology_condition_tree.png")
    gate_rules(d1 / "ontology_gate_rules.png")
    shutil.copy(d1 / "ontology_concept.png", d2 / "ontology_diagram.png")
    shutil.copy(d1 / "ontology_instance.png", d2 / "ontology_instance.png")
    print("saved:", d1, d2)


if __name__ == "__main__":
    main()
