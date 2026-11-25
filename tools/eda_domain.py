#!/usr/bin/env python3
"""도메인 분석(EDA): 결측·중복·분포·요건 유형을 정리 층에서 집계하고 그림을 만든다.

입력: data/cleaned/<날짜>/notices.jsonl, chunks.jsonl, related_groups.csv (tools/preprocess_notices.py 결과)
      data/normalized/<날짜>/notices_normalized.jsonl, normalization_report.json (tools/normalize_values.py 결과, 9절)
출력: data/eda/eda_results.json, docs/figures/eda_*.png

주의: 요건 유형 비율은 정규식으로 센 근사치다(공고별로 한 번이라도 나오면 1건). 정확도 지표가 아니다.
사용: python tools/eda_domain.py
"""
from __future__ import annotations

import csv
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib import font_manager  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from preprocess_notices import norm_title_key  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CLEAN = REPO / "data" / "cleaned" / (REPO / "data" / "cleaned" / "LATEST").read_text().strip()
FIG = REPO / "docs" / "figures"
OUTJ = REPO / "data" / "eda"
FIG.mkdir(parents=True, exist_ok=True)
OUTJ.mkdir(parents=True, exist_ok=True)
font_manager.fontManager.addfont("C:/Windows/Fonts/malgun.ttf")
plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})
C_B, C_K, C_A = "#3b6ea5", "#d9822b", "#5b9a6b"

PATTERNS = {
    "업력·창업 연수": r"업력|창업\s*(후|한지)?\s*\d+\s*년|설립\s*(후)?\s*\d+\s*년|\d+\s*년\s*(이내|미만|이하)",
    "소재·관내·거주·본사": r"소재|관내|거주|본사|주소",
    "제외·제한·불가": r"제외|신청\s*불가|지원\s*불가|참여\s*제한|결격|제한\s*대상",
    "인증·확인서·등록": r"인증|확인서|등록증|등록\s*업체|벤처기업|이노비즈|메인비즈",
    "법령 인용(「」)": r"「[^」]{2,30}」",
    "연령(만 N세·청년)": r"만\s*\d+\s*세|\d+\s*세\s*(이하|이상|미만)|청년",
    "매출·고용": r"매출|상시\s*근로자|고용보험|피보험자|종업원|상시근로",
}


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").split("\n") if l.strip()]


def load_att_sections(CH: list[dict]) -> tuple[dict[str, str], Counter]:
    """정리층 청크 중 첨부 자격·제외 구간을 공고 단위로 합친다. 별도 파일을 읽지 않으므로 정리층(보충 첨부·OCR 포함)과 항상 같다."""
    out: dict[str, list[str]] = defaultdict(list)
    origin: Counter = Counter()
    for c in CH:
        if c["section"].split("@")[0] in ("att_eligibility", "att_exclusion"):
            out[c["notice_id"]].append(c["text"])
            origin[c["origin"]] += 1
    return {k: chr(10).join(v) for k, v in out.items()}, origin


def chi2_2x2(a: int, b: int, c: int, d: int) -> dict:
    """2x2 카이제곱(연속성 보정 없음), p값은 df=1 닫힌 식, 효과크기 phi(=Cramér's V)."""
    n = a + b + c + d
    r1, r2, c1, c2 = a + b, c + d, a + c, b + d
    if min(r1, r2, c1, c2) == 0:
        return {"chi2": None, "p": None, "phi": None}
    chi = n * (a * d - b * c) ** 2 / (r1 * r2 * c1 * c2)
    return {"chi2": round(chi, 2), "p": math.erfc(math.sqrt(chi / 2)), "phi": round(math.sqrt(chi / n), 3)}


def save(fig, name: str) -> str:
    fig.tight_layout()
    fig.savefig(FIG / name, bbox_inches="tight")
    plt.close(fig)
    return f"figures/{name}"


def pct(x: int, n: int) -> float:
    return round(100 * x / n, 1) if n else 0.0


def main() -> None:
    N = jl(CLEAN / "notices.jsonl")
    CH = jl(CLEAN / "chunks.jsonl")
    B = [n for n in N if n["source_system"] == "BIZINFO"]
    K = [n for n in N if n["source_system"] == "KSTARTUP"]
    R: dict = {"source_dir": CLEAN.name, "counts": {"BIZINFO": len(B), "KSTARTUP": len(K), "total": len(N)}}
    figs: dict[str, str] = {}

    # 1. 구성
    R["open"] = {"BIZINFO": sum(n["is_open"] for n in B), "KSTARTUP": sum(n["is_open"] for n in K)}
    fig, ax = plt.subplots(figsize=(6, 3.2))
    ax.barh(["기업마당", "K-Startup"], [len(B), len(K)], color=[C_B, C_K], label="전체")
    ax.barh(["기업마당", "K-Startup"], [R["open"]["BIZINFO"], R["open"]["KSTARTUP"]], color="#222", height=0.35, label="모집 중")
    for i, (a, b) in enumerate([(len(B), R["open"]["BIZINFO"]), (len(K), R["open"]["KSTARTUP"])]):
        ax.text(a + 40, i, f"{a:,}건 (모집 중 {b:,})", va="center")
    ax.set_xlim(0, max(len(B), len(K)) * 1.5)
    ax.set_title("공고 수와 모집 중 공고")
    figs["overview"] = save(fig, "eda_overview.png")

    # 2. 결측(필드 채움률)
    def fill(rows, f) -> float:
        return pct(sum(1 for r in rows if (r.get(f) if not isinstance(r.get(f), (list, dict)) else r.get(f))), len(rows))

    bf = {"자격 문구": "eligibility_text", "본문(요약)": "body_text", "접수 방법": "apply_method_text", "온라인 접수 URL": "apply_url", "문의처": "contact_text",
          "마감일(날짜)": "application_end", "수행 기관": "executor_org_name", "지역 코드(소관 기관)": "region_concept_ids", "지원분야 중분류": "category_medium"}
    kf = {"자격 문구": "eligibility_text", "제외 대상 문구": "exclusion_text", "우대 사항": "preferred_text", "본문": "body_text", "지원 내용": "support_text",
          "평가 방법": "evaluation_text", "접수 방법": "apply_method_text", "온라인 접수 URL": "apply_url", "안내 URL": "guide_url", "지역 코드": "region_concept_ids"}
    R["fill_rate"] = {"BIZINFO": {k: fill(B, v) for k, v in bf.items()}, "KSTARTUP": {k: fill(K, v) for k, v in kf.items()}}
    R["fill_rate"]["BIZINFO"]["일반 첨부 있음"] = pct(sum(1 for n in B if (n["attachments"]["count"] or 0) > 1), len(B))
    R["fill_rate"]["BIZINFO"]["첨부 본문 텍스트 추출"] = pct(sum(1 for n in B if n["attachments"]["text_extracted"]), len(B))
    R["fill_rate"]["KSTARTUP"]["업력 옵션"] = fill([{"v": (n["structured"] or {}).get("business_age_raw")} for n in K], "v")
    R["fill_rate"]["KSTARTUP"]["연령 옵션"] = fill([{"v": (n["structured"] or {}).get("founder_age_raw")} for n in K], "v")
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, key, col, title in ((axs[0], "BIZINFO", C_B, "기업마당(1,294건)"), (axs[1], "KSTARTUP", C_K, f"K-Startup({len(K):,}건)")):
        items = sorted(R["fill_rate"][key].items(), key=lambda x: x[1])
        ax.barh([i[0] for i in items], [i[1] for i in items], color=col)
        for y, (_, v) in enumerate(items):
            ax.text(min(v + 1, 88), y, f"{v}%", va="center", fontsize=8)
        ax.set_xlim(0, 105)
        ax.set_title(f"필드 채움률 — {title}")
    figs["missing"] = save(fig, "eda_missing.png")

    # 3. 중복
    def dup_titles(rows) -> dict:
        c = Counter(r["title"] for r in rows)
        d = {t: n for t, n in c.items() if n > 1}
        return {"duplicate_titles": len(d), "notices_in_duplicate_titles": sum(d.values())}

    rel = list(csv.DictReader(open(CLEAN / "related_groups.csv", encoding="utf-8-sig")))
    rb = [r for r in rel if r["notice_id"].startswith("BIZINFO")]
    rk = [r for r in rel if r["notice_id"].startswith("KSTARTUP")]
    keyb = {norm_title_key(n["title"]) for n in B if len(norm_title_key(n["title"])) >= 8}
    cross = sum(1 for n in K if norm_title_key(n["title"]) in keyb and len(norm_title_key(n["title"])) >= 8)
    R["duplicates"] = {"notice_id_duplicates": len(N) - len({n["notice_id"] for n in N}), "BIZINFO": dup_titles(B), "KSTARTUP": dup_titles(K),
                       "related_group_notices": {"BIZINFO": len(rb), "KSTARTUP": len(rk)},
                       "related_group_with_extension_signal": sum(1 for r in rel if r["signals"]),
                       "cross_source_same_title_key_candidates": cross}

    # 4. 신청 기간·시기
    kind = Counter(n["apply_status_kind"] for n in B)
    R["bizinfo_apply_status_kind"] = dict(kind.most_common())
    months = Counter(n["application_start"][:7] for n in K if n["application_start"])
    R["kstartup_start_month"] = dict(sorted(months.items()))
    label = {"UNTIL_BUDGET_EXHAUSTED": "예산 소진 시까지", "DATE_RANGE": "날짜 범위", "ALWAYS_OPEN": "상시", "UNTIL_FILLED": "인원 충족 시까지",
             "FIRST_COME": "선착순", "VARIES_OR_TBD": "별도 공지·미정", "UNPARSED": "해석 불가"}
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
    items = kind.most_common()[::-1]
    axs[0].barh([label.get(k, k) for k, _ in items], [v for _, v in items], color=C_B)
    for y, (_, v) in enumerate(items):
        axs[0].text(v + 8, y, f"{v:,} ({pct(v, len(B))}%)", va="center", fontsize=8)
    axs[0].set_xlim(0, max(kind.values()) * 1.45)
    axs[0].set_title("기업마당: 신청 기간 유형")
    ms = sorted(months)
    axs[1].bar(range(len(ms)), [months[m] for m in ms], color=C_K)
    axs[1].set_xticks(range(0, len(ms), 2))
    axs[1].set_xticklabels([ms[i][2:] for i in range(0, len(ms), 2)], rotation=60, fontsize=8)
    axs[1].set_title("K-Startup: 접수 시작 월별 공고 수")
    figs["period"] = save(fig, "eda_period.png")

    # 5. 지원 분야·기관·지역
    bcat, kcat = Counter(n["category_major"] for n in B), Counter(n["category_major"] for n in K)
    R["category"] = {"BIZINFO_major": dict(bcat.most_common()), "BIZINFO_medium": dict(Counter(n["category_medium"] for n in B).most_common()),
                     "KSTARTUP": dict(kcat.most_common())}
    R["kstartup_org_kind"] = dict(Counter(n["org_kind"] for n in K).most_common())
    kreg = Counter(n["region_raw"] for n in K)
    R["kstartup_region"] = dict(kreg.most_common())
    R["bizinfo_region_scope_hint"] = dict(Counter(n["region_scope_hint"] for n in B))
    R["bizinfo_jurisdiction"] = dict(Counter(n["org_raw"] for n in B).most_common(12))
    R["bizinfo_executor_kind"] = dict(Counter(n["executor_kind"] for n in B))
    fig, axs = plt.subplots(1, 3, figsize=(13, 4))
    for ax, cnt, col, t in ((axs[0], bcat, C_B, "기업마당 지원분야(대분류)"), (axs[1], kcat, C_K, "K-Startup 지원분야")):
        it = cnt.most_common()[::-1]
        ax.barh([i[0] for i in it], [i[1] for i in it], color=col)
        ax.set_title(t)
        for y, (_, v) in enumerate(it):
            ax.text(v, y, f" {v:,}", va="center", fontsize=8)
    it = kreg.most_common(12)[::-1]
    axs[2].barh([i[0] for i in it], [i[1] for i in it], color=C_K)
    axs[2].set_title(f"K-Startup 지역(상위 12/{len(kreg)}종)")
    for y, (_, v) in enumerate(it):
        axs[2].text(v, y, f" {v:,}", va="center", fontsize=8)
    figs["category_region"] = save(fig, "eda_category_region.png")

    # 6. K-Startup 구조화 옵션
    ba = Counter(len((n["structured"]["business_age_raw"] or "").split(",")) for n in K)
    ag = Counter(n["structured"]["founder_age_raw"] for n in K)
    tg = Counter(n["structured"]["applicant_target_raw"] for n in K)
    R["kstartup_business_age_option_count"] = dict(sorted(ba.items()))
    R["kstartup_founder_age_options"] = dict(ag.most_common(8))
    R["kstartup_applicant_target_top"] = dict(tg.most_common(8))
    R["bizinfo_target_group"] = dict(Counter(n["structured"]["target_group_text"] for n in B).most_common())
    fig, axs = plt.subplots(1, 2, figsize=(11, 3.6))
    ks = sorted(ba)
    axs[0].bar([str(k) for k in ks], [ba[k] for k in ks], color=C_K)
    for i, k in enumerate(ks):
        axs[0].text(i, ba[k], f"{pct(ba[k], len(K))}%", ha="center", va="bottom", fontsize=8)
    axs[0].set_xlabel("나열된 업력 옵션 개수 (7 = 전부 나열)")
    axs[0].set_title("K-Startup 업력 옵션 개수")
    it = Counter(n["structured"]["business_age_raw"] for n in K).most_common(6)[::-1]
    axs[1].barh([i[0][:28] + ("…" if len(i[0]) > 28 else "") for i in it], [i[1] for i in it], color=C_K)
    axs[1].set_title("업력 옵션 조합 상위 6")
    figs["age_options"] = save(fig, "eda_age_options.png")

    # 7. 텍스트 길이
    api_len_b = [len(n["eligibility_text"] or "") for n in B]
    api_len_k = [len(n["eligibility_text"] or "") for n in K if n["application_start"] and n["application_start"] >= "2025-11-24"]  # 최근 1년 3,819건
    att_text, att_origin = load_att_sections(CH)
    R["attachment_chunk_origin"] = dict(att_origin)
    att_len = [len(t) for t in att_text.values()]
    R["text_len"] = {k: {"n": len(v), "mean": round(float(np.mean(v))), "median": float(np.median(v)), "p95": float(np.percentile(v, 95)), "lt20": int(sum(1 for x in v if x < 20))}
                     for k, v in (("BIZINFO_api_eligibility", api_len_b), ("KSTARTUP_api_eligibility", api_len_k), ("BIZINFO_attachment_eligibility_exclusion", att_len))}
    fig, ax = plt.subplots(figsize=(8, 3.8))
    bins = np.logspace(0.7, 4.2, 30)
    for v, col, lab in ((api_len_b, C_B, "기업마당 API 자격 문구"), (api_len_k, C_K, "K-Startup 자격 문구"), (att_len, C_A, "기업마당 첨부 자격·제외 구간")):
        ax.hist([max(x, 5) for x in v], bins=bins, alpha=0.55, color=col, label=f"{lab} (중앙값 {int(np.median(v))}자)")
    ax.set_xscale("log")
    ax.set_xlabel("글자 수 (로그 축)")
    ax.set_ylabel("공고 수")
    ax.legend(fontsize=8)
    ax.set_title("요건 텍스트 길이 분포")
    figs["textlen"] = save(fig, "eda_textlen.png")

    # 8. 요건 유형(정규식 근사)
    K1 = [n for n in K if n["application_start"] and n["application_start"] >= "2025-11-24"]  # 접수 시작일 기준 최근 1년(3,819건)
    flags = {}
    for name, pat in PATTERNS.items():
        rx = re.compile(pat)
        fb = sum(1 for n in B if rx.search(n["eligibility_text"] or ""))
        fk = sum(1 for n in K1 if rx.search(n["eligibility_text"] or ""))
        fa = sum(1 for t in att_text.values() if rx.search(t))
        flags[name] = {"BIZINFO_api": fb, "BIZINFO_att": fa, "KSTARTUP_api": fk}
    R["requirement_flags"] = {"denominators": {"BIZINFO_api": len(B), "BIZINFO_att": len(att_text), "KSTARTUP_api": len(K1)}, "counts": flags,
                              "chi2_bizinfo_api_vs_kstartup_api": {}}
    for name, f in flags.items():
        R["requirement_flags"]["chi2_bizinfo_api_vs_kstartup_api"][name] = chi2_2x2(f["BIZINFO_api"], len(B) - f["BIZINFO_api"], f["KSTARTUP_api"], len(K1) - f["KSTARTUP_api"])
    fig, ax = plt.subplots(figsize=(10, 4.2))
    names = list(PATTERNS)
    w = 0.27
    x = np.arange(len(names))
    for i, (key, col, lab, den) in enumerate((("BIZINFO_api", C_B, "기업마당 API 자격 문구", len(B)), ("BIZINFO_att", C_A, "기업마당 첨부 자격·제외 구간", len(att_text)),
                                              ("KSTARTUP_api", C_K, "K-Startup 자격 문구(최근 1년)", len(K1)))):
        vals = [pct(flags[n][key], den) for n in names]
        ax.bar(x + (i - 1) * w, vals, w, color=col, label=f"{lab} (n={den:,})")
    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=20, fontsize=8)
    ax.set_ylabel("해당 표현이 나온 공고 비율(%)")
    ax.legend(fontsize=8)
    ax.set_title("요건 표현 유형별 비율 (정규식 근사)")
    figs["reqtypes"] = save(fig, "eda_reqtypes.png")

    # 9. 정규화 층(값 후보) 현황
    NZ = REPO / "data" / "normalized" / CLEAN.name
    if (NZ / "notices_normalized.jsonl").exists():
        rows = jl(NZ / "notices_normalized.jsonl")
        rep = json.loads((NZ / "normalization_report.json").read_text(encoding="utf-8"))
        by = {"BIZINFO": [r for r in rows if r["source_system"] == "BIZINFO"], "KSTARTUP": [r for r in rows if r["source_system"] == "KSTARTUP"]}
        attrs = ["business_age", "founder_age", "region", "company_size", "certification", "law_reference", "exclusion"]
        cov = {src: {a: pct(sum(1 for r in rs if any(f["attribute"] == a for f in r["facts"])), len(rs)) for a in attrs} for src, rs in by.items()}
        cov_any = {src: pct(sum(1 for r in rs if r["facts"]), len(rs)) for src, rs in by.items()}
        term_any = {src: pct(sum(1 for r in rs if r["applicant_term_mentions"]), len(rs)) for src, rs in by.items()}
        top_terms = Counter(m["concept_id"] for r in rows for m in r["applicant_term_mentions"])
        allopt = {k: rep["counters"].get(f"structured.{k}.all_options", 0) for k in ("business_age", "founder_age", "applicant_target")}
        R["normalized"] = {"facts": rep["facts"], "facts_by_source_kind": rep["facts_by_source_kind"], "notice_coverage_any_fact": cov_any, "notice_coverage_by_attribute": cov,
                           "notice_with_applicant_term": term_any, "top_applicant_terms": dict(top_terms.most_common(10)), "kstartup_filter_all_options": allopt,
                           "kstartup_filter_all_options_pct": {k: pct(v, len(K)) for k, v in allopt.items()},
                           "business_age_text_vs_structured": {k.split(".")[-1]: v for k, v in rep["counters"].items() if k.startswith("business_age_text_vs_structured")},
                           "bizinfo_region_missing": rep["counters"].get("region_missing.BIZINFO", 0), "ocr_review": rep.get("ocr_review")}
        fig, axs = plt.subplots(1, 2, figsize=(11, 3.8))
        x = np.arange(len(attrs))
        axs[0].bar(x - 0.2, [cov["BIZINFO"][a] for a in attrs], 0.4, color=C_B, label="기업마당")
        axs[0].bar(x + 0.2, [cov["KSTARTUP"][a] for a in attrs], 0.4, color=C_K, label="K-Startup")
        axs[0].set_xticks(x)
        axs[0].set_xticklabels(attrs, rotation=25, fontsize=8)
        axs[0].set_ylabel("규칙 값이 나온 공고 비율(%)")
        axs[0].legend(fontsize=8)
        axs[0].set_title("정규화 값 후보 커버리지")
        names = {"business_age": "업력 옵션", "founder_age": "대표자 연령 옵션", "applicant_target": "신청 대상 옵션"}
        ks = list(allopt)
        axs[1].barh([names[k] for k in ks], [pct(allopt[k], len(K)) for k in ks], color=C_K)
        for y, k in enumerate(ks):
            axs[1].text(pct(allopt[k], len(K)) + 1, y, f"{pct(allopt[k], len(K))}% ({allopt[k]:,}건)", va="center", fontsize=8)
        axs[1].set_xlim(0, 100)
        axs[1].set_title("K-Startup 선택형 필드를 전부 고른 공고(필터 무정보)")
        figs["normalized"] = save(fig, "eda_normalized.png")

    R["figures"] = figs
    (OUTJ / "eda_results.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: R[k] for k in ("counts", "open", "duplicates", "text_len")}, ensure_ascii=False, indent=1))
    print(json.dumps(R["requirement_flags"], ensure_ascii=False, indent=1)[:2400])
    print("figures:", list(figs.values()))


if __name__ == "__main__":
    main()
