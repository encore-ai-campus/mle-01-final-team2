"""국가법령정보센터 공개 본문 페이지에서 현행 법령을 조문 단위로 받아 `data/지원사업_법령/`에 추가한다.

법제처 OPEN API 인증값(LAW_OC)이 없을 때 쓰는 보조 수집기다. 결과 형식은 `조문.jsonl`(데이터명세서 §5.1)과 같다.
- 출처: https://www.law.go.kr/법령/<법령명> → 법령일련번호(lsiSeq)·시행일 확인 → /LSW/lsInfoR.do 본문
- 법령은 저작권 보호 대상이 아니다(저작권법 제7조). 요청 사이에 1초 쉰다.
- 소관부처는 부서명까지만 남기고 전화번호는 저장하지 않는다.
- 별표·서식 원문은 받지 않는다(별도 파일 형식). 별표가 필요한 법령은 OPEN API로 다시 받는다.
- 공고 인용(`cited_by`)은 공고 정리층 텍스트에서 법령명·약칭과 뒤따르는 `제N조`로 찾는다(명세서 §5.4 규칙의 축약판).

사용:
  python tools/law_web_collector.py            # 아래 TARGETS를 받아 조문.jsonl에 추가(같은 법령은 교체)
  python tools/law_web_collector.py --dry-run  # 받기만 하고 쓰지 않음
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "지원사업_법령"
NOTICES = REPO / "data" / "cleaned" / "20261124"
UA = {"User-Agent": "Mozilla/5.0 (jiwongak law collector; educational project)"}

# (법령명, 우선순위, 선택 이유, 공고에서 쓰는 약칭)
TARGETS: list[tuple[str, str, str, list[str]]] = [
    ("장애인기업활동 촉진법", "P1", "장애인기업 정의(제2조), 공고 언급 76건", ["장애인기업법"]),
    ("장애인기업활동 촉진법 시행령", "P1", "장애인기업 판정 기준(소유·경영·고용비율)", []),
    ("중소기업 기술혁신 촉진법", "P1", "기술혁신형(이노비즈)·경영혁신형(메인비즈) 중소기업, 공고 언급 67·47건", ["중소기업기술혁신 촉진법", "중소기업기술혁신촉진법", "기술혁신촉진법"]),
    ("중소기업 기술혁신 촉진법 시행령", "P1", "이노비즈·메인비즈 선정 기준", []),
    ("청년기본법", "P1", "청년 정의(제3조, 19~34세), 공고 언급 725건. 공고별 나이 기준이 우선", []),
    ("청년기본법 시행령", "P1", "청년 정책 대상 범위", []),
    ("마을기업 육성 및 지원에 관한 법률", "P1", "마을기업 정의, 공고 언급 47건·법령 인용 9건", ["마을기업법"]),
    ("마을기업 육성 및 지원에 관한 법률 시행령", "P1", "마을기업 지정 요건", []),
    ("수산업ㆍ어촌 발전 기본법", "P2", "어업인 정의, 공고 언급 56건", ["수산업·어촌 발전 기본법", "수산업어촌발전기본법"]),
    ("수산업ㆍ어촌 발전 기본법 시행령", "P2", "어업인 범위", []),
    ("농업ㆍ농촌 및 식품산업 기본법", "P2", "농업인 정의, 공고 언급 47건", ["농업·농촌 및 식품산업 기본법", "농업식품기본법"]),
    ("농업ㆍ농촌 및 식품산업 기본법 시행령", "P2", "농업인 기준(제3조)", []),
    ("국민기초생활 보장법", "P2", "자활기업(제18조), 공고 언급 31건", ["기초생활보장법"]),
    ("국민기초생활 보장법 시행령", "P2", "자활기업 인정 요건", []),
    ("연구개발특구의 육성에 관한 특별법", "P2", "연구소기업(제9조의3), 공고 언급 37건", ["연구개발특구법"]),
    ("연구개발특구의 육성에 관한 특별법 시행령", "P2", "연구소기업 등록 요건", []),
    ("중소기업협동조합법", "P2", "중소기업협동조합, 공고 언급 24건·법령 인용 20건", []),
    ("중소기업협동조합법 시행령", "P2", "조합 설립·조합원 자격", []),
]

# 본문 순서대로 장·절 제목(gtit)과 조문 앵커(J{조}:{가지})를 읽는다. 긴 숫자 J 앵커부터는 부칙이다.
TOKEN = re.compile(r'<p class="gtit"[^>]*>(?P<gtit>.*?)</p>|<a name="J(?P<no>\d+):(?P<br>\d+)"[^>]*>|<a name="(?P<other>[^"]+)"', re.S)


def fetch(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def text_of(fragment: str) -> str:
    fragment = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S)
    fragment = re.sub(r"</p>|</div>|</li>|<br\s*/?>", "\n", fragment)
    s = html.unescape(re.sub(r"<[^>]+>", "", fragment))
    lines = [re.sub(r"[ \t ]+", " ", ln).strip() for ln in s.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def collect(name: str) -> dict:
    page = fetch("https://www.law.go.kr/" + urllib.parse.quote("법령/" + name.replace(" ", "")))
    seq = re.search(r'id="frm_lsiSeq" name="lsiSeq" value="(\d+)"', page).group(1)
    ef = re.search(r'id="frm_efYd" name="efYd" value="(\d*)"', page).group(1)
    time.sleep(1)
    return collect_by_seq(seq, ef, name)[0]


def collect_by_seq(seq: str, ef: str, name: str) -> tuple[dict, str]:
    """법령일련번호·시행일로 본문 페이지를 읽어 (문서, 본문 HTML)을 돌려준다."""
    body = fetch(f"https://www.law.go.kr/LSW/lsInfoR.do?lsiSeq={seq}&efYd={ef}&chrClsCd=010202&urlMode=lsInfoP&ancYnChk=0")
    top = text_of(body[body.find('class="cont_top'):body.find('class="cont_top') + 3000]).replace("\n", " ")
    doc_name = html.unescape(re.search(r'<h2[^>]*>(.*?)</h2>', body, re.S).group(1)) if "<h2" in body else name
    doc_name = re.sub(r"\s*\(\s*약칭.*", "", text_of(doc_name)).strip() or name
    kind = re.search(r"\[(법률|대통령령|총리령|[가-힣]+부령) 제", top)
    org = re.search(r"\]\s*([가-힣]+(?:부|처|청|실|위원회))\s*\(", top)
    articles, chapter = [], None
    tokens = list(TOKEN.finditer(body))
    for i, m in enumerate(tokens):
        if m.group("gtit") is not None:
            chapter = text_of(m.group("gtit")).replace("\n", " ").strip() or chapter
            continue
        if m.group("no") is None:
            if m.group("other").startswith("J"):
                break  # 부칙
            continue
        seg = body[m.end(): tokens[i + 1].start() if i + 1 < len(tokens) else len(body)]
        no = m.group("no") + (f"의{m.group('br')}" if m.group("br") != "0" else "")
        con = seg.find('<div class="lawcon"')
        txt = text_of(seg[con:] if con >= 0 else seg)
        if not re.match(rf"제{m.group('no')}조", txt):
            continue
        title = re.match(r"제\d+조(?:의\d+)?\s*\(([^)]*)\)", txt)
        deleted = bool(re.match(r"제\d+조(?:의\d+)?\s*삭제", txt))
        articles.append({"article_no": no, "article_title": title.group(1) if title else None, "text": txt,
                         "deleted": deleted, "chapter": chapter})
    return {"doc_name": doc_name, "doc_id": seq, "effective": ef, "doc_kind": kind.group(1) if kind else None,
            "org": org.group(1) if org else None, "source": f"law.go.kr/law/{seq}", "articles": articles}, body


def notice_texts() -> dict[str, str]:
    texts: dict[str, str] = defaultdict(str)
    for line in (NOTICES / "chunks.jsonl").open(encoding="utf-8"):
        c = json.loads(line)
        texts[c["notice_id"]] += "\n" + c["text"]
    for line in (NOTICES / "notices.jsonl").open(encoding="utf-8"):
        n = json.loads(line)
        for k in ("eligibility_text", "body_text", "support_text", "evaluation_text"):
            if n.get(k):
                texts[n["notice_id"]] += "\n" + str(n[k])
    return texts


def citations(name: str, aliases: list[str], texts: dict[str, str]) -> tuple[list[str], dict[str, list[str]]]:
    """(법령 단위 인용 공고, {조 번호: 공고}) 시행령은 '<법령명> 시행령'으로만 찾는다."""
    def pat(n: str) -> str:
        return r"[\s·ㆍ]*".join(re.escape(ch) for ch in re.sub(r"[\s·ㆍ]", "", n))
    names = [name] + aliases
    is_decree = name.endswith("시행령")
    rx = re.compile(r"[「｢『]?\s*(?:" + "|".join(pat(n) for n in names) + r")\s*[」｣』]?" + ("" if is_decree else r"(?!\s*시행)"))
    law_level, by_article = [], defaultdict(list)
    for nid, t in texts.items():
        arts, hit = set(), False
        for m in rx.finditer(t):
            hit = True
            a = re.match(r"\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?", t[m.end(): m.end() + 40])
            if a:
                arts.add(a.group(1) + (f"의{a.group(2)}" if a.group(2) else ""))
        if arts:
            for a in arts:
                by_article[a].append(nid)
        elif hit:
            law_level.append(nid)
    return sorted(law_level), {k: sorted(v) for k, v in by_article.items()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    texts = notice_texts()
    new_rows, summary = [], []
    for name, prio, why, aliases in TARGETS:
        doc = collect(name)
        time.sleep(1)
        law_cited, art_cited = citations(doc["doc_name"], aliases, texts)
        base = {k: doc[k] for k in ("doc_name", "doc_kind", "doc_id", "effective", "org", "source")}
        base.update(priority=prio, why=why)
        new_rows.append({**base, "chapter": None, "article_no": None, "article_title": "(법령 전체)", "text": "", "deleted": False,
                         "level": "law", "cited_by": law_cited})
        found = {a["article_no"] for a in doc["articles"]}
        for a in doc["articles"]:
            new_rows.append({**base, **a, "level": "article", "cited_by": art_cited.get(a["article_no"], [])})
        missing_cited = sorted(set(art_cited) - found)
        summary.append((doc["doc_name"], doc["doc_kind"], doc["effective"], doc["org"], len(doc["articles"]),
                        sum(a["deleted"] for a in doc["articles"]), len(law_cited), sum(len(v) for v in art_cited.values()), missing_cited))
    for s in summary:
        print(" | ".join(str(x) for x in s))
    if args.dry_run:
        return 0
    path = OUT_DIR / "조문.jsonl"
    names = {r["doc_name"] for r in new_rows}
    keep = [json.loads(l) for l in path.open(encoding="utf-8") if json.loads(l)["doc_name"] not in names]
    with path.open("w", encoding="utf-8") as f:
        for r in keep + new_rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT_DIR / "수집기록_web.json").write_text(json.dumps(
        {"collected_on": date.today().isoformat(), "method": "law.go.kr 공개 본문 페이지(lsInfoR.do)",
         "docs": [{"doc_name": s[0], "doc_kind": s[1], "effective": s[2], "org": s[3], "articles": s[4], "deleted": s[5],
                   "law_level_citing_notices": s[6], "article_level_citations": s[7], "cited_articles_not_found": s[8]} for s in summary]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"조문.jsonl: 기존 {len(keep)}행 + 새 {len(new_rows)}행")
    return 0


if __name__ == "__main__":
    sys.exit(main())
