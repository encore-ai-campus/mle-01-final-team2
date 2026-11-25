#!/usr/bin/env python3
"""기업마당 첨부 파일(PDF·hwp·hwpx·이미지)에서 텍스트를 추출한다. 로컬 전용.

입력 : data/bizinfo/files/<run>/  (download_bizinfo_attachments.py 산출물, manifest.json 포함)
출력 : data/bizinfo/extracted/<run>/<원본파일명>.txt, extraction_report.json

- PDF  : PyMuPDF. 페이지 구분선(=== p.N ===)을 넣고, 글자가 거의 없는 PDF는 NEEDS_OCR로 표시한다.
- hwp  : HWP 5.x(OLE) 본문 스트림을 직접 읽는다(압축 해제 후 PARA_TEXT 레코드). 암호·배포용 문서는 지원하지 않고 상태만 표시한다.
- hwpx : zip 안의 Contents/section*.xml에서 문단과 표 셀 텍스트를 읽는다.
- 이미지·스캔 PDF: 기본은 IMAGE_NEEDS_OCR / NEEDS_OCR로 표시만 한다. --ocr를 주면 Tesseract(kor+eng)로 읽는다.
  OCR 결과는 항상 낮은 신뢰로 표시(OCR_LOW_TRUST)하며 검토 전에는 요건의 근거로 쓰지 않는다.
  Tesseract 한국어는 음절 사이에 공백을 끼우므로 공백을 줄인 검색용 사본(*.search.txt)을 함께 만들고,
  요건 후보 구간 위치는 그 사본 기준으로 기록한다.
- 요건 후보 구간(신청자격·제외·제출서류·평가 등)은 '확정이 아닌 후보'로 위치(문자 오프셋·페이지)만 기록한다.
  요건 정규화(Condition 추출)는 이 도구의 범위가 아니다.

사용 예:
    python tools/extract_attachment_text.py
    python tools/extract_attachment_text.py --files data/bizinfo/files/20261124_094715
    python tools/extract_attachment_text.py --ocr            # 이미지·스캔 PDF까지 OCR
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    import pymupdf  # type: ignore
except ImportError:  # 구버전 이름
    import fitz as pymupdf  # type: ignore
import olefile

KST = timezone(timedelta(hours=9))
REPO = Path(__file__).resolve().parent.parent
MIN_CHARS_PER_PAGE = 30  # 이보다 적으면 스캔본(이미지 PDF)으로 본다

SECTION_RULES = [
    ("ELIGIBILITY", re.compile(r"신청\s*자격|지원\s*자격|지원\s*대상|신청\s*대상|참여\s*대상|참가\s*대상|참가\s*자격|참여\s*자격|모집\s*대상|입점\s*자격|신청\s*요건|지원\s*요건")),
    ("EXCLUSION", re.compile(r"제외\s*대상|신청\s*제외|지원\s*제외|선정\s*제외|결격|참여\s*제한|지원\s*불가|제한\s*대상")),
    ("DOCUMENT", re.compile(r"제출\s*서류|구비\s*서류|신청\s*서류|첨부\s*서류")),
    ("CRITERION", re.compile(r"평가\s*(기준|항목|방법)|선정\s*(기준|방법|절차)|심사\s*(기준|방법)")),
    ("BENEFIT", re.compile(r"지원\s*(내용|규모|한도|금액)|지원\s*조건|융자\s*(한도|조건)")),
    ("PERIOD", re.compile(r"신청\s*기간|접수\s*기간|모집\s*기간|공고\s*기간")),
    ("METHOD", re.compile(r"신청\s*방법|접수\s*방법|제출\s*방법|신청\s*절차")),
    ("CONTACT", re.compile(r"문\s*의\s*처|문의\s*사항|담당\s*(부서|자)")),
]
_SYM = r"[^0-9A-Za-z가-힣]*"  # 글머리 기호·괄호·사설 영역 문자(hwp 글머리) 등 글자가 아닌 접두를 모두 허용한다
_HEAD_PREFIX = re.compile(rf"^{_SYM}(?:(?:\d{{1,2}}[.)]|[가-하][.)])\s*)?{_SYM}(?:[mO]\s+(?=[가-힣]))?")  # PDF 글머리가 'm'으로 읽히는 경우 포함
_LABEL_END = re.compile(r"\s*[)\]】:：]")


# ---------------------------------------------------------------- 공통
def clean_text(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace(" ", " ").replace("​", "").replace("﻿", "")
    out = []
    for ln in s.replace("\r", "\n").split("\n"):
        ln = re.sub(r"[ \t　]+", " ", ln).strip()
        if ln:
            out.append(ln)
    return "\n".join(out)


def quality_warnings(text: str) -> list[str]:
    w = []
    n = max(len(text), 1)
    pua = sum(1 for c in text if "" <= c <= "")
    if pua / n > 0.02:
        w.append(f"PUA_CHARS_{pua}")
    if "�" in text:
        w.append("REPLACEMENT_CHARS")
    hangul = sum(1 for c in text if "가" <= c <= "힣")
    if len(text) > 300 and hangul / n < 0.15:
        w.append("LOW_HANGUL_RATIO")
    return w


# ---------------------------------------------------------------- HWP (5.x)
HWPTAG_PARA_TEXT = 67


def parse_hwp_section(data: bytes) -> list[str]:
    """압축 해제된 BodyText/SectionN 스트림에서 문단 텍스트 목록을 만든다."""
    paras: list[str] = []
    i, n = 0, len(data)
    while i + 4 <= n:
        h = struct.unpack("<I", data[i:i + 4])[0]
        i += 4
        tag, size = h & 0x3FF, (h >> 20) & 0xFFF
        if size == 0xFFF:
            if i + 4 > n:
                break
            size = struct.unpack("<I", data[i:i + 4])[0]
            i += 4
        if tag == HWPTAG_PARA_TEXT:
            b = data[i:i + size]
            chars, j = [], 0
            while j + 2 <= len(b):
                c = struct.unpack("<H", b[j:j + 2])[0]
                j += 2
                if c >= 32:
                    chars.append(chr(c))
                elif c in (10, 13):
                    chars.append("\n")
                elif c == 9:
                    chars.append(" ")
                elif c in (0, 24, 25, 26, 27, 28, 29, 30, 31):
                    continue
                else:  # 확장·인라인 컨트롤은 총 8 WCHAR(첫 글자 포함)를 차지한다
                    j += 14
            # WCHAR를 하나씩 chr()로 바꾸면 서로게이트 쌍이 깨지므로 UTF-16으로 다시 해석한다
            paras.append("".join(chars).encode("utf-16-le", "surrogatepass").decode("utf-16-le", "replace"))
        i += size
    return paras


def extract_hwp(path: Path) -> tuple[str, str, list[str], int | None]:
    warns: list[str] = []
    try:
        o = olefile.OleFileIO(str(path))
    except Exception:
        return "", "NOT_HWP5_OR_CORRUPT", warns, None
    try:
        if not o.exists("FileHeader"):
            return "", "NOT_HWP5_OR_CORRUPT", warns, None
        hdr = o.openstream("FileHeader").read()
        if not hdr.startswith(b"HWP Document File"):
            return "", "NOT_HWP5_OR_CORRUPT", warns, None
        flags = struct.unpack("<I", hdr[36:40])[0]
        if flags & 0x2:
            return "", "ENCRYPTED", warns, None
        if flags & 0x4 or (o.exists("ViewText") and not o.exists("BodyText")):
            return "", "DISTRIBUTION_DOC_UNSUPPORTED", warns, None
        compressed = bool(flags & 0x1)
        secs = [s for s in o.listdir() if len(s) == 2 and s[0] == "BodyText" and re.fullmatch(r"Section\d+", s[1])]
        secs.sort(key=lambda s: int(s[1][7:]))
        paras: list[str] = []
        for s in secs:
            data = o.openstream(s).read()
            if compressed:
                data = zlib.decompress(data, -15)
            paras += parse_hwp_section(data)
        return clean_text("\n".join(paras)), "OK", warns, len(secs)
    except zlib.error:
        return "", "CORRUPT_STREAM", warns, None
    finally:
        o.close()


# ---------------------------------------------------------------- HWPX
def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _hwpx_para(p: ET.Element) -> list[str]:
    own: list[str] = []
    nested: list[str] = []

    def walk(el: ET.Element) -> None:
        for ch in el:
            ln = _local(ch.tag)
            if ln == "t":
                own.append("".join(ch.itertext()))
            elif ln in ("lineBreak", "br"):
                own.append("\n")
            elif ln == "tab":
                own.append(" ")
            elif ln == "p":
                nested.extend(_hwpx_para(ch))
            else:
                walk(ch)

    walk(p)
    return ["".join(own)] + nested


def extract_hwpx(path: Path) -> tuple[str, str, list[str], int | None]:
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        return "", "NOT_HWPX_OR_CORRUPT", [], None
    names = [n for n in z.namelist() if re.fullmatch(r"Contents/section\d+\.xml", n)]
    names.sort(key=lambda n: int(re.search(r"(\d+)\.xml", n).group(1)))
    if not names:
        enc = any("encrypt" in n.lower() for n in z.namelist())
        return "", "ENCRYPTED" if enc else "NO_SECTIONS", [], None
    lines: list[str] = []
    for n in names:
        for p in _top_paragraphs(ET.fromstring(z.read(n))):
            lines += _hwpx_para(p)
    return clean_text("\n".join(lines)), "OK", [], len(names)


def _top_paragraphs(el: ET.Element):
    """다른 문단 안에 들어 있지 않은 최상위 문단만 돌려준다(표 셀 안의 문단은 바깥 문단이 처리한다)."""
    for ch in el:
        if _local(ch.tag) == "p":
            yield ch
        else:
            yield from _top_paragraphs(ch)


# ---------------------------------------------------------------- PDF
def extract_pdf(path: Path) -> tuple[str, str, list[str], int | None, list[int]]:
    try:
        doc = pymupdf.open(str(path))
    except Exception:
        return "", "NOT_PDF_OR_CORRUPT", [], None, []
    parts, offsets, pos = [], [], 0
    for i, page in enumerate(doc, 1):
        t = clean_text(page.get_text("text", sort=True))
        block = f"=== p.{i} ===\n{t}\n" if t else f"=== p.{i} ===\n"
        offsets.append(pos)
        parts.append(block)
        pos += len(block)
    text = "".join(parts)
    body = sum(len(re.sub(r"\s", "", clean_text(p.get_text("text")))) for p in doc)
    pages = len(doc)
    status = "OK" if pages and body / pages >= MIN_CHARS_PER_PAGE else "NEEDS_OCR"
    return text, status, [], pages, offsets


# ---------------------------------------------------------------- 요건 후보 구간
def find_sections(text: str, page_offsets: list[int] | None = None) -> list[dict]:
    """제목처럼 보이는 줄(짧고 키워드로 시작)을 찾아 후보 구간의 위치를 기록한다. 확정이 아니다."""
    heads = []
    pos = 0
    for ln in text.split("\n"):
        start = pos
        pos += len(ln) + 1
        if ln.startswith("=== p."):
            continue
        body = _HEAD_PREFIX.sub("", ln, count=1)
        if not body:
            continue
        for label, rx in SECTION_RULES:
            m = rx.match(body[:25])
            # 짧은 줄이거나, 키워드 바로 뒤에 ')' ':' 가 붙은 '제목: 값' 형태만 제목으로 본다
            if m and (len(ln) <= 45 or _LABEL_END.match(body, m.end())):
                heads.append((start, label, ln))
                break
    out = []
    for k, (start, label, ln) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(text)
        sec = {"label": label, "heading": ln, "start": start, "end": end, "chars": end - start}
        if page_offsets:
            sec["page"] = max(i for i, o in enumerate(page_offsets, 1) if o <= start)
        out.append(sec)
    return out


# ---------------------------------------------------------------- OCR (Tesseract, 선택)
TESSERACT_CANDIDATES = [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
OCR_LANG = "kor+eng"
OCR_MAX_SIDE_UP = 2200    # 작은 이미지는 긴 변이 이 값이 되도록 확대
OCR_MAX_SIDE_DOWN = 5000  # 너무 큰 이미지는 속도를 위해 축소
LOW_CONF = 60.0


def find_tesseract() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    for c in TESSERACT_CANDIDATES:
        if Path(c).exists():
            return c
    return None


def despace_hangul(s: str) -> str:
    """Tesseract가 음절 사이에 끼우는 공백을 줄인 검색용 텍스트. 실제 띄어쓰기도 함께 사라지므로 읽기용이 아니다."""
    return "\n".join(re.sub(r"(?<=[가-힣]) (?=[가-힣])", "", ln) for ln in s.split("\n"))


def tsv_to_lines(tsv: str) -> tuple[list[str], list[float]]:
    """Tesseract TSV 출력을 줄 목록과 단어 신뢰도 목록으로 바꾼다."""
    lines: dict[tuple, list[str]] = {}
    confs: list[float] = []
    for row in tsv.split("\n")[1:]:
        cols = row.split("\t", 11)
        if len(cols) < 12:
            continue
        try:
            conf = float(cols[10])
        except ValueError:
            continue
        word = cols[11].strip()
        if conf < 0 or not word:
            continue
        lines.setdefault(tuple(cols[1:5]), []).append(word)
        confs.append(conf)
    return [" ".join(ws) for ws in lines.values()], confs


def ocr_image(png: Path, tess: str, psm: int, timeout: int = 180) -> tuple[list[str], list[float]]:
    p = subprocess.run([tess, str(png), "stdout", "-l", OCR_LANG, "--psm", str(psm), "tsv"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return tsv_to_lines(p.stdout)


def _prep_image(src: Path, dst: Path) -> None:
    from PIL import Image, ImageOps
    im = ImageOps.exif_transpose(Image.open(src)).convert("L")
    side = max(im.size)
    if side < OCR_MAX_SIDE_UP or side > OCR_MAX_SIDE_DOWN:
        s = (OCR_MAX_SIDE_UP if side < OCR_MAX_SIDE_UP else OCR_MAX_SIDE_DOWN) / side
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))), Image.LANCZOS)
    im.save(dst)


OCR_DPI = 300
OCR_MAX_PIXELS = 6000  # 렌더링 결과의 긴 변 상한(MuPDF 한도·속도). 쪽 크기가 매우 큰 스캔본 대응


def choose_dpi(page) -> int:
    """쪽에 들어 있는 이미지의 원래 해상도를 넘지 않게 하고, 긴 변이 OCR_MAX_PIXELS를 넘지 않게 dpi를 고른다."""
    w_in, h_in = page.rect.width / 72, page.rect.height / 72
    dpi = OCR_DPI
    try:
        imgs = page.get_images()
        if imgs:  # (xref, smask, width, height, ...) 중 가장 큰 이미지의 가로 픽셀을 쪽 가로 길이로 나눈 값이 원래 해상도
            native = max(i[2] for i in imgs) / max(w_in, 1e-6)
            if native >= 72:
                dpi = min(dpi, int(native))
    except Exception:
        pass
    return max(30, min(dpi, int(OCR_MAX_PIXELS / max(w_in, h_in, 1e-6))))


def run_ocr(path: Path, kind: str, tess: str, psm: int = 3, max_pages: int = 30) -> dict:
    """이미지 또는 PDF를 OCR한다. 반환: raw(읽기용), search(공백 축소), page_offsets(search 기준), pages, conf 통계."""
    tmp = Path(tempfile.mkdtemp(prefix="ocr_"))
    raw_parts, search_parts, offsets, confs, pos, truncated = [], [], [], [], 0, False
    try:
        if kind == "pdf":
            doc = pymupdf.open(str(path))
            n_pages = len(doc)
            work = [(i + 1, None) for i in range(min(n_pages, max_pages))]
            truncated = n_pages > max_pages
        else:
            n_pages, work = 1, [(1, path)]
            doc = None
        for pno, img in work:
            png = tmp / f"p{pno}.png"
            if doc is not None:
                doc[pno - 1].get_pixmap(dpi=choose_dpi(doc[pno - 1])).save(str(png))
            else:
                _prep_image(img, png)
            lines, c = ocr_image(png, tess, psm)
            confs += c
            raw = "\n".join(lines)
            sea = despace_hangul(raw)
            head = f"=== p.{pno} ===\n" if kind == "pdf" else ""
            raw_parts.append(head + raw + "\n")
            sea_block = head + sea + "\n"
            offsets.append(pos)
            search_parts.append(sea_block)
            pos += len(sea_block)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    mean = sum(confs) / len(confs) if confs else 0.0
    return {"raw": "".join(raw_parts), "search": "".join(search_parts), "page_offsets": offsets if kind == "pdf" else None,
            "pages": n_pages, "pages_ocr": len(work), "truncated": truncated,
            "engine": "tesseract", "lang": OCR_LANG, "psm": psm, "words": len(confs), "mean_conf": round(mean, 1),
            "low_conf_ratio": round(sum(1 for c in confs if c < LOW_CONF) / len(confs), 3) if confs else None}


# ---------------------------------------------------------------- 실행
def sniff(head: bytes) -> str:
    if head.startswith(b"%PDF"): return "pdf"
    if head.startswith(b"\xd0\xcf\x11\xe0"): return "hwp"
    if head.startswith(b"PK\x03\x04"): return "zip"
    if head.startswith(b"\x89PNG"): return "png"
    if head.startswith(b"\xff\xd8\xff"): return "jpg"
    return "unknown"


def extract_file(path: Path, ocr: bool = False, tess: str | None = None, ocr_psm: int = 3,
                 ocr_max_pages: int = 30) -> tuple[dict, str, str | None]:
    """반환: (보고 레코드, 본문 텍스트, OCR 검색용 텍스트 또는 None). OCR 파일의 sections 오프셋은 검색용 텍스트 기준이다."""
    with open(path, "rb") as f:
        kind = sniff(f.read(8))
    if kind == "zip":  # hwpx / xlsx / 일반 zip
        kind = "hwpx" if zipfile.is_zipfile(path) and any(n.startswith("Contents/") for n in zipfile.ZipFile(path).namelist()) else "zip_other"
    rec = {"file": path.name, "format": kind, "status": None, "pages": None, "chars": 0, "warnings": [], "sections": []}
    text, offsets, search = "", None, None
    if kind == "pdf":
        text, rec["status"], w, rec["pages"], offsets = extract_pdf(path)
    elif kind == "hwp":
        text, rec["status"], w, _ = extract_hwp(path)
    elif kind == "hwpx":
        text, rec["status"], w, _ = extract_hwpx(path)
    elif kind in ("png", "jpg"):
        rec["status"], w = "IMAGE_NEEDS_OCR", []
    else:
        rec["status"], w = "UNSUPPORTED_FORMAT", []

    if rec["status"] in ("IMAGE_NEEDS_OCR", "NEEDS_OCR") and ocr:
        if not tess:
            w = w + ["TESSERACT_NOT_FOUND"]
        else:
            r = run_ocr(path, kind, tess, ocr_psm, ocr_max_pages)
            text, search, offsets = r["raw"], r["search"], r["page_offsets"]
            rec["status"] = "OK_OCR"
            rec["pages"] = r["pages"] if kind == "pdf" else rec["pages"]
            rec["ocr"] = {k: r[k] for k in ("engine", "lang", "psm", "words", "mean_conf", "low_conf_ratio", "pages_ocr", "truncated")}
            w = w + ["OCR_LOW_TRUST"] + (["OCR_LOW_CONFIDENCE"] if r["mean_conf"] < LOW_CONF else []) + (["OCR_PAGES_TRUNCATED"] if r["truncated"] else [])
    base = search if search is not None else text
    rec["warnings"] = w + (quality_warnings(text) if text and search is None else [])
    rec["chars"] = len(text)
    rec["sections"] = find_sections(base, offsets) if base else []
    if search is not None:
        rec["sections_text"] = "search"  # 오프셋이 *.search.txt 기준임을 표시
    return rec, text, search


def _process(job: tuple) -> tuple[dict, str, str | None]:
    """프로세스 풀에서 한 파일을 처리한다. 한 파일의 실패가 전체를 멈추지 않게 예외를 기록으로 바꾼다."""
    p, ocr, tess, psm, max_pages = job
    try:
        return extract_file(Path(p), ocr=ocr, tess=tess, ocr_psm=psm, ocr_max_pages=max_pages)
    except Exception as e:
        return {"file": Path(p).name, "format": "?", "status": "ERROR", "error": f"{type(e).__name__}: {str(e)[:100]}",
                "chars": 0, "pages": None, "warnings": [], "sections": []}, "", None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--files", help="내려받은 파일 폴더(기본: data/bizinfo/files의 가장 최근 폴더)")
    ap.add_argument("--out", default=str(REPO / "data" / "bizinfo" / "extracted"))
    ap.add_argument("--ocr", action="store_true", help="이미지·스캔 PDF를 Tesseract(kor+eng)로 읽는다")
    ap.add_argument("--ocr-psm", type=int, default=3, help="Tesseract 페이지 분할 모드(기본 3)")
    ap.add_argument("--ocr-max-pages", type=int, default=30, help="PDF 한 파일에서 OCR할 최대 쪽수")
    ap.add_argument("--workers", type=int, default=1, help="병렬 프로세스 수(많은 파일·OCR일 때)")
    args = ap.parse_args()
    if args.workers > 1:
        os.environ["OMP_THREAD_LIMIT"] = "1"  # 프로세스마다 Tesseract가 스레드를 또 만들지 않게 한다(자식 프로세스가 상속)
    tess = find_tesseract() if args.ocr else None
    if args.ocr and not tess:
        print("경고: Tesseract를 찾지 못해 OCR을 건너뜁니다.")

    root = REPO / "data" / "bizinfo" / "files"
    src = Path(args.files) if args.files else sorted(p for p in root.iterdir() if p.is_dir())[-1]
    out = Path(args.out) / src.name
    out.mkdir(parents=True, exist_ok=True)

    notice_of: dict[str, str] = {}
    man = src / "manifest.json"
    if man.exists():
        for r in json.loads(man.read_text(encoding="utf-8")).get("results", []):
            if r.get("saved_as"):
                notice_of[r["saved_as"]] = r["notice_id"]

    items = []
    files = [p for p in sorted(src.iterdir()) if p.is_file() and p.name != "manifest.json"]
    jobs = [(str(p), args.ocr, tess, args.ocr_psm, args.ocr_max_pages) for p in files]
    if args.workers > 1:
        from concurrent.futures import ProcessPoolExecutor
        pool = ProcessPoolExecutor(max_workers=args.workers)
        results_iter = pool.map(_process, jobs, chunksize=1)
    else:
        pool, results_iter = None, map(_process, jobs)
    for n, (p, (rec, text, search)) in enumerate(zip(files, results_iter), 1):
        if n % 50 == 0 or n == len(files):
            print(f"[{n}/{len(files)}] 처리 중", flush=True)
        rec["notice_id"] = notice_of.get(p.name)
        if text:
            (out / (p.name + ".txt")).write_text(text, encoding="utf-8")
            rec["text_file"] = p.name + ".txt"
        if search is not None:
            (out / (p.name + ".search.txt")).write_text(search, encoding="utf-8")
            rec["search_text_file"] = p.name + ".search.txt"
        items.append(rec)
    if pool:
        pool.shutdown()

    st = collections.Counter(r["status"] for r in items)
    labels = collections.Counter(s["label"] for r in items for s in r["sections"])
    report = {"extracted_at": datetime.now(KST).isoformat(timespec="seconds"), "source_dir": str(src.name), "files": len(items),
              "status": dict(st),
              "by_format": {f"{k[0]}:{k[1]}": v for k, v in collections.Counter((r["format"], r["status"]) for r in items).items()},
              "ocr_enabled": bool(args.ocr), "ocr_files": sum(1 for r in items if r["status"] == "OK_OCR"),
              "section_candidates": dict(labels),
              "files_with_eligibility_candidate": sum(1 for r in items if any(s["label"] == "ELIGIBILITY" for s in r["sections"])),
              "files_with_exclusion_candidate": sum(1 for r in items if any(s["label"] == "EXCLUSION" for s in r["sections"])),
              "note": "섹션은 후보 위치일 뿐 확정이 아님. 원본·추출 텍스트는 로컬 전용(git 제외).", "items": items}
    (out / "extraction_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "items"}, ensure_ascii=False, indent=2))
    print("출력:", out)


if __name__ == "__main__":
    main()
