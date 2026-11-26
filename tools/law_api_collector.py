"""공공데이터포털 법제처 국가법령정보 공유서비스(OPEN API)로 추가 법령 18문서를 검증하고 별표·서식을 수집한다.

- 인증: 저장소 루트 .env의 `open_law_key`, `open_law_endpoint` (값은 읽기만 하고 출력·저장하지 않는다).
- 이 게이트웨이는 목록 조회(`lawSearchList.do`)만 제공한다. 본문(조문) 조회 오퍼레이션은 없다.
  그래서 다음처럼 나눠 쓴다.
  1. target=law 목록 조회로 법령일련번호·시행일·소관부처·법령구분을 공식 값으로 확인한다.
  2. 본문은 그 일련번호로 국가법령정보센터 본문 페이지를 읽는다(`law_web_collector.collect_by_seq`).
  3. 본문 페이지의 별표·서식 목록(별표일련번호, 제목, PDF 링크)을 읽고, target=licbyl 목록 조회(별표명 검색)로
     별표번호·종류를 공식 값으로 확인한 뒤, PDF에서 텍스트를 뽑는다.
- 결과: `data/지원사업_법령/조문.jsonl`(해당 법령 행 교체), `별표.jsonl`(해당 법령 행 교체), `수집기록_api.json`.
- 별표 PDF 원본은 `data/지원사업_법령/_별표원본/`(git 제외)에만 둔다.

사용:
  python tools/law_api_collector.py            # 검증 + 수집 + 저장
  python tools/law_api_collector.py --dry-run  # 검증·수집만 하고 저장하지 않음
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import law_web_collector as web  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "data" / "지원사업_법령"
RAW_DIR = OUT_DIR / "_별표원본"
UA = {"User-Agent": "Mozilla/5.0 (jiwongak law collector; educational project)"}


def load_env() -> tuple[str, str]:
    env = {}
    path = REPO / ".env"
    if path.exists():
        for line in path.open(encoding="utf-8"):
            m = re.match(r"\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
            if m:
                env[m.group(1)] = m.group(2).strip().strip("\"'")
    key, ep = env.get("open_law_key"), env.get("open_law_endpoint")
    if not key or not ep:
        sys.exit(".env에 open_law_key, open_law_endpoint가 필요합니다.")
    return key, ep.rstrip("/")


KEY, EP = load_env()


def api(target: str, query: str, rows: int = 100) -> list[dict]:
    """목록 조회. 각 항목을 {태그: 텍스트} 사전으로 돌려준다."""
    out, page = [], 1
    while True:
        q = urllib.parse.urlencode({"target": target, "query": query, "pageNo": page, "numOfRows": rows})
        req = urllib.request.Request(f"{EP}/lawSearchList.do?serviceKey={KEY}&{q}", headers=UA)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    body = r.read().decode("utf-8", "replace")
                break
            except (urllib.error.URLError, TimeoutError) as e:
                if attempt == 3:
                    raise RuntimeError(f"API 연결 실패 target={target}: {type(e).__name__}") from None
                time.sleep(3 * (attempt + 1))
        if "<resultCode>00</resultCode>" not in body:
            code = re.search(r"<(?:returnReasonCode|resultCode)>(\w+)<", body)
            raise RuntimeError(f"API 오류 target={target} code={code.group(1) if code else '?'}")
        item_tag = {"law": "law", "licbyl": "licbyl"}[target]
        items = re.findall(rf'<{item_tag} id="\d+">(.*?)</{item_tag}>', body, re.S)
        for it in items:
            d = {}
            for k, v in re.findall(r"<([^/>\s]+)>(.*?)</\1>", it, re.S):
                v = re.sub(r"^<!\[CDATA\[(.*)\]\]>$", r"\1", v.strip(), flags=re.S)
                d[k] = html.unescape(re.sub(r"<[^>]+>", "", v)).strip()
            out.append(d)
        total = int(re.search(r"<totalCnt>(\d+)</totalCnt>", body).group(1))
        if page * rows >= total or not items:
            return out
        page += 1
        time.sleep(0.5)


def official_law(name: str) -> dict:
    hits = [d for d in api("law", name) if d.get("법령명한글") == name and d.get("현행연혁코드") == "현행"]
    if len(hits) != 1:
        raise RuntimeError(f"현행 법령을 하나로 정하지 못함: {name} ({len(hits)}건)")
    return hits[0]


BYL_ITEM = re.compile(r'<li[^>]*>\s*<span class="pcf_cover[^"]*">(.*?)</li>', re.S)


def appendix_list(body: str) -> list[dict]:
    """본문 페이지의 별표·서식 목록: 별표일련번호, 제목, PDF flSeq."""
    out = []
    sec = body[body.find('<a name="byl">'):] if '<a name="byl">' in body else ""
    for li in BYL_ITEM.finditer(sec):
        s = li.group(1)
        seq = re.search(r"bylInfoDiv\('(\d+)'\)", s)
        title = re.findall(r'bylInfoDiv\(\'\d+\'\);" href="#AJAX">\s*([^<]+?)\s*</a>', s)
        pdf = re.search(r'flDownload\.do\?gubun=&amp;flSeq=(\d+)&amp;bylClsCd=\d+">\s*<img alt="PDF', s)
        if seq and title:
            out.append({"byl_seq": seq.group(1), "label": html.unescape(title[0]).strip(), "pdf_flseq": pdf.group(1) if pdf else None})
    return out


def official_appendix(label: str, byl_seq: str, law_seq: str) -> dict | None:
    """별표명으로 licbyl 목록을 찾아 별표일련번호가 같은 항목을 고른다."""
    name = re.sub(r"^\[[^\]]+\]\s*", "", label)  # "[별표 1] 제목" → "제목"
    name = re.sub(r"\s*\([^)]*관련\)\s*$", "", name)  # 끝의 "(제N조 관련)"은 검색에서 뺀다
    for q in (name, name[:30]):
        try:
            for d in api("licbyl", q):
                if d.get("별표일련번호") == byl_seq or (d.get("관련법령일련번호") == law_seq and d.get("별표명", "").startswith(name[:15])):
                    return d
        except RuntimeError:
            pass
        time.sleep(0.5)
    return None


def pdf_text(path: Path) -> str:
    """PDF 텍스트. 일부 별표 PDF는 글자 사이 공백이 빠져 나오므로 글자 위치 간격으로 띄어쓰기를 되살린다."""
    import fitz  # PyMuPDF

    out = []
    with fitz.open(path) as d:
        for page in d:
            for b in page.get_text("rawdict")["blocks"]:
                for line in b.get("lines", []):
                    s, prev = "", None
                    for sp in line["spans"]:
                        for c in sp["chars"]:
                            if prev is not None and c["bbox"][0] - prev > sp["size"] * 0.18 and not s.endswith(" "):
                                s += " "
                            s += c["c"]
                            prev = c["bbox"][2]
                    s = re.sub(r"[ \t\u00a0]+", " ", s).strip()
                    if s:
                        out.append(s)
    return "\n".join(out)


def download(flseq: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        req = urllib.request.Request(f"https://www.law.go.kr/LSW/flDownload.do?flSeq={flseq}", headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        if not data.startswith(b"%PDF"):
            raise RuntimeError(f"PDF가 아님: flSeq={flseq}")
        dest.write_bytes(data)
        time.sleep(1)
    return dest


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    texts = web.notice_texts()
    law_rows, app_rows, log = [], [], []
    for name, prio, why, aliases in web.TARGETS:
        off = official_law(name)
        seq, ef = off["법령일련번호"], off["시행일자"]
        time.sleep(0.5)
        doc, body = web.collect_by_seq(seq, ef, name)
        assert doc["doc_id"] == seq
        doc.update(doc_kind=off["법령구분명"], effective=ef, org=off["소관부처명"])
        law_cited, art_cited = web.citations(doc["doc_name"], aliases, texts)
        base = {k: doc[k] for k in ("doc_name", "doc_kind", "doc_id", "effective", "org", "source")}
        base.update(priority=prio, why=why)
        law_rows.append({**base, "chapter": None, "article_no": None, "article_title": "(법령 전체)", "text": "", "deleted": False,
                         "level": "law", "cited_by": law_cited})
        for a in doc["articles"]:
            law_rows.append({**base, **a, "level": "article", "cited_by": art_cited.get(a["article_no"], [])})

        apps = appendix_list(body)
        app_log = []
        for a in apps:
            o = official_appendix(a["label"], a["byl_seq"], seq)
            kind = (o or {}).get("별표종류") or ("서식" if "서식" in a["label"] else "별표")
            no = (o or {}).get("별표번호") or ""
            if not no:  # API에서 못 찾으면 표기("[별지 제2호서식]", "[별표 3]")에서 번호를 딴다
                m = re.search(r"제?\s*(\d+)\s*호?\s*(?:의\s*(\d+))?", a["label"].split("]")[0])
                no = f"{int(m.group(1)):04d}{int(m.group(2) or 0):02d}" if m else ""
            text, err = "", None
            if a["pdf_flseq"]:
                try:
                    text = pdf_text(download(a["pdf_flseq"], RAW_DIR / seq / f"{a['byl_seq']}.pdf"))
                except Exception as e:  # noqa: BLE001
                    err = str(e)[:120]
            title = (o or {}).get("별표명") or re.sub(r"^\[[^\]]+\]\s*", "", a["label"])
            app_rows.append({**{k: base[k] for k in ("doc_name", "doc_kind", "doc_id", "effective", "org", "source", "priority", "why")},
                             "table_no": no[:4] if no else None, "table_branch": no[4:6] if no else None, "table_kind": kind,
                             "title": title, "label": a["label"], "byl_seq": a["byl_seq"], "api_verified": o is not None,
                             "text": text})
            app_log.append({"label": a["label"], "api_verified": o is not None, "text_chars": len(text), "error": err})
        log.append({"doc_name": doc["doc_name"], "doc_id": seq, "law_id": off.get("법령ID"), "doc_kind": off["법령구분명"],
                    "effective": ef, "org": off["소관부처명"], "promulgated": off.get("공포일자"),
                    "articles": len(doc["articles"]), "deleted": sum(a["deleted"] for a in doc["articles"]),
                    "appendices": app_log})
        print(f"{doc['doc_name']} | {seq} | {ef} | {off['소관부처명']} | 조문 {len(doc['articles'])} | "
              f"별표·서식 {len(apps)} (API 확인 {sum(x['api_verified'] for x in app_log)}, 본문 {sum(1 for x in app_log if x['text_chars'])})")
        time.sleep(1)

    if args.dry_run:
        return 0
    names = {r["doc_name"] for r in law_rows}
    for fname, new in (("조문.jsonl", law_rows), ("별표.jsonl", app_rows)):
        path = OUT_DIR / fname
        keep = [json.loads(l) for l in path.open(encoding="utf-8") if json.loads(l)["doc_name"] not in names]
        with path.open("w", encoding="utf-8") as f:
            for r in keep + new:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{fname}: 기존 {len(keep)}행 + 새 {len(new)}행")
    (OUT_DIR / "수집기록_api.json").write_text(json.dumps(
        {"collected_on": date.today().isoformat(),
         "method": "공공데이터포털 법제처 국가법령정보 공유서비스(lawSearchList.do: target=law, licbyl) + 국가법령정보센터 본문·별표 PDF",
         "docs": log}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
