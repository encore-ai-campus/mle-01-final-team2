#!/usr/bin/env python
"""IBK 사규(HWP/PDF) 일괄 변환기.

data/ibk기업/*.hwp|HWP|pdf  →  data/ibk_converted/
    text/<파일명>.txt      추출 원문(UTF-8)
    parsed/<파일명>.json   조문 단위 구조화 + 참조/단서/위임 후보
    manifest.csv           파일별 결과(성공/실패, 글자 수, 조문 수 등)
    manifest.json          같은 내용(JSON)

사용법:
    pip install -r tools/requirements.txt
    python tools/convert_ibk.py
    python tools/convert_ibk.py --src data/ibk기업 --out data/ibk_converted --force

HWP(5.x)는 olefile로 BodyText 스트림을 직접 읽는다(한컴 오피스 불필요).
암호화·배포용(ViewText) 문서와 스캔 PDF는 실패로 기록하고 건너뛴다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import struct
import sys
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- HWP 추출

# HWP 5.x 문단 텍스트(WCHAR)의 제어 문자: 아래는 문자 뒤에 14바이트가 더 붙는다.
_EXT_CTRL = {1, 2, 3, 4, 5, 6, 7, 8, 9, 11, 12, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23}
_TAG_PARA_TEXT = 67  # HWPTAG_BEGIN(16) + 51


class ConvertError(Exception):
    pass


def extract_hwp(path: Path) -> str:
    import olefile

    if not olefile.isOleFile(str(path)):
        raise ConvertError("OLE 형식이 아님(HWPX/손상 파일 가능)")
    ole = olefile.OleFileIO(str(path))
    try:
        header = ole.openstream("FileHeader").read()
        flags = struct.unpack("<I", header[36:40])[0]
        compressed, encrypted, distributed = flags & 1, flags & 2, flags & 4
        if encrypted:
            raise ConvertError("암호화된 문서")
        if distributed:
            raise ConvertError("배포용 문서(ViewText 암호화)")
        sections = sorted(
            (s for s in ole.listdir() if s[0] == "BodyText"),
            key=lambda s: int(re.sub(r"\D", "", s[1]) or 0),
        )
        if not sections:
            raise ConvertError("BodyText 없음")
        paragraphs: list[str] = []
        for sec in sections:
            data = ole.openstream(sec).read()
            if compressed:
                data = zlib.decompress(data, -15)
            paragraphs.extend(_paragraphs(data))
        return "\n".join(paragraphs)
    finally:
        ole.close()


def _paragraphs(data: bytes):
    i, n = 0, len(data)
    while i + 4 <= n:
        head = struct.unpack("<I", data[i : i + 4])[0]
        i += 4
        tag, size = head & 0x3FF, head >> 20
        if size == 0xFFF:
            size = struct.unpack("<I", data[i : i + 4])[0]
            i += 4
        body = data[i : i + size]
        i += size
        if tag == _TAG_PARA_TEXT:
            yield _decode_para(body)


def _decode_para(body: bytes) -> str:
    out: list[str] = []
    j, m = 0, len(body)
    while j + 2 <= m:
        c = struct.unpack("<H", body[j : j + 2])[0]
        j += 2
        if c in _EXT_CTRL:
            if c == 9:
                out.append("\t")
            j += 14
        elif c == 10:
            out.append("\n")
        elif c == 13:
            continue
        elif c == 24:
            out.append("-")
        elif c in (30, 31):
            out.append(" ")
        elif c < 32:
            continue
        else:
            out.append(chr(c))
    # 서로게이트 쌍(드문 한자·이모지 등)을 하나의 문자로 합친다. 짝이 없는 조각은 대체 문자로 바꾼다.
    s = "".join(out)
    return s.encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace")


# ---------------------------------------------------------------- PDF 추출

def extract_pdf(path: Path) -> str:
    try:
        import pymupdf as fitz  # PyMuPDF >= 1.24
    except ImportError:
        try:
            import fitz  # 구버전 이름
        except ImportError as e:  # pragma: no cover
            raise ConvertError("PyMuPDF 미설치(pip install pymupdf)") from e
    doc = fitz.open(str(path))
    try:
        if doc.needs_pass:
            raise ConvertError("암호가 걸린 PDF")
        text = "\n".join(page.get_text("text") for page in doc)
    finally:
        doc.close()
    if len(text.strip()) < 50:
        raise ConvertError("추출된 텍스트 없음(스캔 이미지/DRM 가능)")
    return text


# ---------------------------------------------------------------- 파일명 메타

_RE_DATE_KO = re.compile(r"\((\d{4})년도\s*(\d{1,2})월(?:\s*(\d{1,2})일)?\s*(제정|개정)\)")
_RE_DATE_8 = re.compile(r"\((\d{8})\)")
_RE_PREFIX6 = re.compile(r"^\((\d{6})\)")
_DOC_TYPES = ("시행세칙", "운영규정", "운영기준", "운용기준", "업무규정", "규정", "지침", "세칙",
              "기준", "준칙", "원칙", "강령", "규칙", "제도")


def parse_filename(name: str) -> dict:
    stem = Path(name).stem
    title, date, action = stem, None, None
    m = _RE_DATE_KO.search(stem)
    if m:
        y, mo, d, action = m.group(1), int(m.group(2)), m.group(3), m.group(4)
        date = f"{y}-{mo:02d}" + (f"-{int(d):02d}" if d else "")
        title = stem[: m.start()] + stem[m.end():]
    else:
        m = _RE_DATE_8.search(stem)
        if m:
            s = m.group(1)
            date = f"{s[:4]}-{s[4:6]}-{s[6:]}"
            title = stem[: m.start()] + stem[m.end():]
        else:
            m = _RE_PREFIX6.match(stem)
            if m:
                s = m.group(1)
                date = f"20{s[:2]}-{s[2:4]}-{s[4:]}"
                title = stem[m.end():]
    title = title.strip()
    doc_type = next((t for t in _DOC_TYPES if title.endswith(t)), None)
    return {"title": title, "date": date, "action": action, "doc_type": doc_type}


# ---------------------------------------------------------------- 조문 파싱

_RE_ARTICLE = re.compile(r"^\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*[\(（]([^)）]*)[\)）]\s*(.*)$")
_RE_DELETED = re.compile(r"^\s*제\s*(\d+)\s*조(?:\s*의\s*(\d+))?\s*[\[\(<]?\s*삭제\s*[\]\)>]?\s*(.*)$")
_RE_PART = re.compile(r"^\s*제\s*\d+\s*편\s")
_RE_CHAPTER = re.compile(r"^\s*제\s*(\d+)\s*([장절관편])(?:\s*의\s*\d+)?\s+(.+?)\s*$")
_RE_ADDENDA = re.compile(r"^\s*부\s*칙")
_RE_PARA_NO = re.compile(r"^\s*([①-⑳])\s*(.*)$")
_RE_ITEM = re.compile(r"^\s*(\d{1,2})\s*[.)]\s+(.*)$")
_RE_SUBITEM = re.compile(r"^\s*([가-하])\s*[.)]\s+(.*)$")
_RE_EXT_NAME = re.compile(r"「([^」]+)」")
_RE_ART_REF = re.compile(
    r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?(?:\s*제\s*(\d+)\s*항)?(?:\s*제\s*(\d+)\s*호)?"
)
_RE_DELEGATION = re.compile(r"정한다|정하는\s*바|정하는\s*기준|정하는\s*사항|따로\s*정|별도로\s*정")


def _sentences(text: str):
    return [s.strip() for s in re.split(r"(?<=다\.)\s+", text) if s.strip()]


def _article_id(no: str, branch: str | None) -> str:
    return f"제{no}조" + (f"의{branch}" if branch else "")


def _split_paragraphs(lines: list[str]) -> list[dict]:
    """조문 본문 줄들을 항(①)/호(1.)/목(가.) 구조로 나눈다."""
    paras: list[dict] = []
    cur_para = cur_item = cur_sub = None
    last = None  # 이어 붙일 대상 dict

    def new_para(no, text):
        nonlocal cur_para, cur_item, cur_sub, last
        cur_para = {"no": no, "text": text, "items": []}
        cur_item = cur_sub = None
        paras.append(cur_para)
        last = cur_para

    for line in lines:
        if not line.strip():
            continue
        m = _RE_PARA_NO.match(line)
        if m:
            new_para(m.group(1), m.group(2).strip())
            continue
        if cur_para is None:
            new_para(None, line.strip())
            continue
        m = _RE_SUBITEM.match(line)
        if m and cur_item is not None:
            cur_sub = {"no": m.group(1), "text": m.group(2).strip()}
            cur_item.setdefault("subitems", []).append(cur_sub)
            last = cur_sub
            continue
        m = _RE_ITEM.match(line)
        if m:
            cur_item = {"no": m.group(1), "text": m.group(2).strip()}
            cur_para["items"].append(cur_item)
            cur_sub = None
            last = cur_item
            continue
        last["text"] = (last["text"] + " " + line.strip()).strip()
    return paras


def parse_regulation(text: str, doc_id: str) -> dict:
    lines = text.splitlines()
    chapters: list[dict] = []
    articles: list[dict] = []
    addenda: list[str] = []
    preamble: list[str] = []
    cur_chapter = None
    cur_part = None
    cur = None
    in_addenda = False
    # 편(編)이 있는 문서는 편마다 제1조가 반복되므로 ID에 편 번호를 붙여 유일하게 만든다.
    has_parts = any(_RE_PART.match(ln) for ln in lines)

    def prefix(part):
        return f"{part}-" if has_parts and part else ""

    def start_article(no, branch, title, head_text, deleted=False):
        aid = _article_id(no, branch)
        return {
            "id": f"{doc_id}#{prefix(cur_part)}{aid}",
            "no": aid,
            "title": title,
            "part": cur_part,
            "chapter": cur_chapter["no"] if cur_chapter else None,
            "deleted": deleted,
            "head_text": head_text,
            "_lines": [head_text] if head_text else [],
        }

    def flush():
        nonlocal cur
        if cur is not None:
            cur["paragraphs"] = _split_paragraphs(cur.pop("_lines"))
            cur["text"] = "\n".join(cur_lines_text(cur))
            articles.append(cur)
            cur = None

    def cur_lines_text(a):
        out = []
        for p in a["paragraphs"]:
            out.append(((p["no"] or "") + " " + p["text"]).strip())
            for it in p["items"]:
                out.append(f"  {it['no']}. {it['text']}")
                for sb in it.get("subitems", []):
                    out.append(f"    {sb['no']}. {sb['text']}")
        return out

    for line in lines:
        if _RE_ADDENDA.match(line):
            flush()
            in_addenda = True
            addenda.append(line.strip())
            continue
        if in_addenda:
            addenda.append(line.strip())
            continue
        m = _RE_CHAPTER.match(line)
        if m and not _RE_ARTICLE.match(line):
            flush()
            no = f"제{m.group(1)}{m.group(2)}"
            if m.group(2) == "편":
                cur_part, cur_chapter = no, None
            cur_chapter_new = {"no": no, "title": m.group(3), "kind": m.group(2), "part": cur_part}
            chapters.append(cur_chapter_new)
            if m.group(2) != "편":
                cur_chapter = cur_chapter_new
            continue
        m = _RE_DELETED.match(line)
        if m:  # "제25조 삭제<2012.12.4.>" 같은 삭제 조문
            flush()
            cur = start_article(m.group(1), m.group(2), None, m.group(3).strip(), deleted=True)
            flush()
            continue
        m = _RE_ARTICLE.match(line)
        if m:
            flush()
            cur = start_article(m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip())
            continue
        if cur is not None:
            cur["_lines"].append(line)
        else:
            if line.strip():
                preamble.append(line.strip())
    flush()

    # 참조·단서·위임 후보 추출
    refs_ext, refs_int, exceptions, delegations = [], [], [], []
    for a in articles:
        body = a["text"]
        for name in dict.fromkeys(_RE_EXT_NAME.findall(body)):
            refs_ext.append({"from": a["id"], "target_name": name.strip()})
        for m in _RE_ART_REF.finditer(body):
            before = body[max(0, m.start() - 4) : m.start()].rstrip()
            ref = {
                "article": _article_id(m.group(1), m.group(2)),
                "paragraph": m.group(3),
                "item": m.group(4),
            }
            if before.endswith("」"):
                prev = body[: m.start()].rstrip()
                nm = _RE_EXT_NAME.findall(prev)
                refs_ext.append({"from": a["id"], "target_name": nm[-1].strip() if nm else None,
                                 "target_article": ref["article"], "paragraph": ref["paragraph"]})
            else:
                if ref["article"] != a["no"]:
                    refs_int.append({"from": a["id"], "to": f"{doc_id}#{prefix(a['part'])}{ref['article']}",
                                     "paragraph": ref["paragraph"], "item": ref["item"],
                                     "context": body[max(0, m.start() - 14) : m.end()].replace("\n", " "),
                                     "_before": body[max(0, m.start() - 8) : m.start()]})
        for s in _sentences(body.replace("\n", " ")):
            if "다만" in s:
                exceptions.append({"article": a["id"], "text": s})
            if _RE_DELEGATION.search(s):
                delegations.append({"article": a["id"], "text": s})

    # 대상 조문이 이 문서에 없거나 "법/령/규칙 제N조"처럼 다른 법령을 가리키는 표현은 분리한다.
    # (예: "법 제88조", "같은 법 시행령 제5조", "시행령 제3조") — 어느 법령인지 자동 판단이 불가능하다.
    existing = {a["id"] for a in articles}
    other_law = re.compile(r"(?:법|령|시행령|시행규칙|규칙|동법|같은\s*법)\s*$")
    resolved, unresolved = [], []
    for r in refs_int:
        before = r.pop("_before").rstrip()
        if r["to"] not in existing or other_law.search(before):
            unresolved.append(r)
        else:
            r.pop("context", None)
            resolved.append(r)
    refs_int = resolved

    return {
        "preamble": preamble,
        "chapters": chapters,
        "articles": articles,
        "addenda": [x for x in addenda if x],
        "external_refs": refs_ext,
        "internal_refs": refs_int,
        "unresolved_refs": unresolved,
        "exception_sentences": exceptions,
        "delegation_candidates": delegations,
    }


# ---------------------------------------------------------------- 실행

def convert_one(path: Path, out_dir: Path, force: bool) -> dict:
    meta = parse_filename(path.name)
    ext = path.suffix.lower()
    row = {"file": path.name, "format": ext.lstrip("."), "title": meta["title"], "date": meta["date"],
           "action": meta["action"], "status": "ok", "error": "", "chars": 0, "articles": 0,
           "external_refs": 0, "internal_refs": 0, "exceptions": 0}
    txt_path = out_dir / "text" / (path.stem + ".txt")
    json_path = out_dir / "parsed" / (path.stem + ".json")
    if not force and txt_path.exists() and json_path.exists():
        data = json.loads(json_path.read_text(encoding="utf-8"))
        row.update(status="skipped", chars=data["stats"]["chars"], articles=len(data["articles"]),
                   external_refs=len(data["external_refs"]), internal_refs=len(data["internal_refs"]),
                   exceptions=len(data["exception_sentences"]))
        return row
    try:
        if ext == ".hwp":
            text = extract_hwp(path)
        elif ext == ".pdf":
            text = extract_pdf(path)
        else:
            raise ConvertError(f"지원하지 않는 형식: {ext}")
        text = re.sub(r"[ \t]+\n", "\n", text).strip()
        if len(text) < 20:
            raise ConvertError("추출된 텍스트가 너무 짧음")
        doc_id = re.sub(r"\s+", "", meta["title"])
        parsed = parse_regulation(text, doc_id)
        doc = {
            "doc": {"id": doc_id, "title": meta["title"], "doc_type": meta["doc_type"],
                    "date": meta["date"], "action": meta["action"], "source": "ALIO(IBK기업은행)",
                    "file": path.name, "format": ext.lstrip(".")},
            **parsed,
            "stats": {"chars": len(text), "has_articles": bool(parsed["articles"])},
        }
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(text, encoding="utf-8")
        json_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        row.update(chars=len(text), articles=len(parsed["articles"]),
                   external_refs=len(parsed["external_refs"]), internal_refs=len(parsed["internal_refs"]),
                   exceptions=len(parsed["exception_sentences"]))
        if not parsed["articles"]:
            row["status"] = "ok_no_articles"  # 조문(제N조) 형식이 아닌 문서
    except ConvertError as e:
        row.update(status="failed", error=str(e))
    except Exception as e:  # 한 파일 오류로 전체가 멈추지 않게 한다
        row.update(status="failed", error=f"{type(e).__name__}: {e}")
    return row


def main() -> int:
    ap = argparse.ArgumentParser(description="IBK 사규 HWP/PDF 일괄 변환")
    ap.add_argument("--src", default=str(ROOT / "data" / "ibk기업"))
    ap.add_argument("--out", default=str(ROOT / "data" / "ibk_converted"))
    ap.add_argument("--force", action="store_true", help="이미 변환된 파일도 다시 변환")
    args = ap.parse_args()

    src, out = Path(args.src), Path(args.out)
    if not src.is_dir():
        print(f"입력 폴더가 없습니다: {src}", file=sys.stderr)
        return 1
    files = sorted(p for p in src.iterdir() if p.is_file() and p.suffix.lower() in (".hwp", ".pdf", ".hwpx"))
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    for i, p in enumerate(files, 1):
        r = convert_one(p, out, args.force)
        rows.append(r)
        print(f"[{i:3d}/{len(files)}] {r['status']:<14} {r['articles']:>3}조 {r['chars']:>7}자  {p.name}"
              + (f"  ← {r['error']}" if r["error"] else ""))

    fields = list(rows[0].keys()) if rows else []
    with open(out / "manifest.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    (out / "manifest.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")

    total = len(rows)
    ok = sum(r["status"] in ("ok", "skipped") for r in rows)
    noart = [r["file"] for r in rows if r["status"] == "ok_no_articles"]
    failed = [r for r in rows if r["status"] == "failed"]
    print(f"\n총 {total}개 | 성공 {ok} | 조문 형식 아님 {len(noart)} | 실패 {len(failed)}")
    print(f"조문 합계 {sum(r['articles'] for r in rows)} | 외부 참조 {sum(r['external_refs'] for r in rows)}"
          f" | 내부 참조 {sum(r['internal_refs'] for r in rows)}")
    for r in failed:
        print(f"  실패: {r['file']} ← {r['error']}")
    print(f"결과: {out}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
