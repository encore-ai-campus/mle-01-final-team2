#!/usr/bin/env python3
"""마크다운 설계서를 **양식 docx**(머리글·바닥글·스타일·표 서식)에 얹어 docx로 만든다.

- 양식 파일을 열어 본문만 비우고 머리글·바닥글·페이지 설정·`Title`/`Heading` 스타일·표 스타일(`Table1`: 파란 위·아래 선, 줄무늬, 첫 열 굵게)을 그대로 쓴다.
- 양식의 바닥글 안내 문구("실제 팀 자료로 교체하여 제출")는 --footer 문구로 바꾼다.
- 마크다운의 이미지(`![설명](경로)`)와 ```mermaid 블록(대체 그림 --mermaid-image)을 넣는다.

사용:
  python tools/md_to_docx_template.py --template <양식.docx> --md <설계서.md> --out <결과.docx> \\
      --footer "2팀 | 도메인 온톨로지 설계서 v0.2" --mermaid-image docs/diagrams/ontology_concept.png
"""
from __future__ import annotations

import argparse
import copy
import os
import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

CODE_FONT = "Consolas"
NAVY = RGBColor(0x14, 0x40, 0x69)


def link_strip(t: str) -> str:
    return re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)


def set_run_font(run, size=None, bold=None, mono=False, color=None, italic=None):
    if mono:
        run.font.name = CODE_FONT
        run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "Malgun Gothic")
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color is not None:
        run.font.color.rgb = color


def inline(p, text: str, size=None, base_bold=False):
    text = link_strip(text).replace("\\|", "|")
    for tok in re.split(r"(\*\*[^*]+\*\*|`[^`]+`)", text):
        if not tok:
            continue
        if tok.startswith("**"):
            set_run_font(p.add_run(tok[2:-2].replace("`", "")), size, True)
        elif tok.startswith("`"):
            set_run_font(p.add_run(tok[1:-1]), (size or 9) - 0.5, base_bold or None, mono=True)
        else:
            set_run_font(p.add_run(tok), size, True if base_bold else None)


def cellsplit(line: str) -> list[str]:
    s = line.strip().replace("\\|", "\x00")
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip().replace("\x00", "|") for c in s.split("|")]


def style_table(tbl, widths_dxa: list[int]) -> None:
    """양식 표와 같은 속성: 스타일 Table1, 위·아래 파란 선, 고정 레이아웃, 폭 8640(dxa), tblLook 04A0."""
    tblPr = tbl._tbl.tblPr
    for tag in ("w:tblStyle", "w:tblW", "w:jc", "w:tblBorders", "w:tblLayout", "w:tblLook"):
        for el in tblPr.findall(qn(tag)):
            tblPr.remove(el)
    st = OxmlElement("w:tblStyle")
    st.set(qn("w:val"), "Table1")
    tblPr.insert(0, st)
    w = OxmlElement("w:tblW")
    w.set(qn("w:w"), str(sum(widths_dxa)))
    w.set(qn("w:type"), "dxa")
    tblPr.append(w)
    jc = OxmlElement("w:jc")
    jc.set(qn("w:val"), "center")
    tblPr.append(jc)
    b = OxmlElement("w:tblBorders")
    for side in ("top", "bottom"):
        e = OxmlElement(f"w:{side}")
        for k, v in (("val", "single"), ("sz", "8"), ("space", "0"), ("color", "4f81bd")):
            e.set(qn(f"w:{k}"), v)
        b.append(e)
    tblPr.append(b)
    lay = OxmlElement("w:tblLayout")
    lay.set(qn("w:type"), "fixed")
    tblPr.append(lay)
    look = OxmlElement("w:tblLook")
    look.set(qn("w:val"), "04A0")
    tblPr.append(look)
    grid = tbl._tbl.tblGrid
    for i, gc in enumerate(grid.findall(qn("w:gridCol"))):
        gc.set(qn("w:w"), str(widths_dxa[i]))


def shade_cell(cell, fill: str) -> None:
    tcPr = cell._element.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def border_cell(cell, color: str) -> None:
    tcPr = cell._element.get_or_add_tcPr()
    b = OxmlElement("w:tcBorders")
    for side in ("top", "bottom"):
        e = OxmlElement(f"w:{side}")
        for k, v in (("val", "single"), ("sz", "8"), ("space", "0"), ("color", color)):
            e.set(qn(f"w:{k}"), v)
        b.append(e)
    tcPr.append(b)


def disp_w(word: str, per_wide: int = 150, per_narrow: int = 82) -> int:
    return sum(per_wide if ord(ch) > 0x2E80 else per_narrow for ch in word)


def col_widths(rows: list[list[str]], total: int = 8640) -> list[int]:
    """열 폭(dxa): 가장 긴 단어가 줄바꿈되지 않을 만큼을 최소로 하고, 나머지는 내용 길이에 비례해 나눈다."""
    n = len(rows[0])
    mins, score = [], []
    for j in range(n):
        cells = [re.sub(r"[`*]", "", r[j] if j < len(r) else "") for r in rows]
        longest = max((disp_w(w) for c in cells for w in c.split()), default=300)
        mins.append(min(longest + 230, 2300))
        score.append(max(min(max(len(c) for c in cells), 70), 6))
    if sum(mins) >= total:
        scale = total / sum(mins)
        w = [int(m * scale) for m in mins]
    else:
        extra = total - sum(mins)
        w = [int(m + extra * sc / sum(score)) for m, sc in zip(mins, score)]
    w[-1] += total - sum(w)
    return w


def build(template: Path, md: Path, out: Path, footer: str, mermaid_image: Path | None) -> dict:
    d = Document(str(template))
    body = d.element.body
    for ch in list(body):
        if ch.tag != qn("w:sectPr"):
            body.remove(ch)
    # 바닥글: 양식 안내 문구를 팀 문구로 교체
    for p in d.sections[0].footer.paragraphs:
        if p.runs:
            p.runs[0].text = footer
            for r in p.runs[1:]:
                r.text = ""
    base = md.parent
    lines = md.read_text(encoding="utf-8").split("\n")
    stats = {"tables": 0, "images": 0, "headings": 0}

    def spacer(pt=3):
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(pt)
        p.paragraph_format.space_before = Pt(0)
        return p

    def table(rows: list[list[str]]):
        n = len(rows[0])
        wide = n >= 5
        t = d.add_table(rows=len(rows), cols=n)
        style_table(t, col_widths(rows))
        for i, row in enumerate(rows):
            for j in range(n):
                c = t.cell(i, j)
                p = c.paragraphs[0]
                p.paragraph_format.space_after = Pt(1)
                p.paragraph_format.space_before = Pt(1)
                # 양식 표 스타일(Table1)의 조건부 서식(머리 행·첫 열 굵게, 줄무늬, 머리 행 파란 선)을 직접 서식으로도 적용한다.
                # LibreOffice 같은 뷰어는 스타일의 조건부 서식을 그리지 않기 때문이다. Word에서는 같은 모양이다.
                inline(p, row[j] if j < len(row) else "", 7.5 if wide else 8, base_bold=(i == 0 or j == 0))
                if i > 0 and i % 2 == 1:
                    shade_cell(c, "D3DFEE")
                if i == 0:
                    border_cell(c, "4F81BD")
        if rows:
            trPr = t.rows[0]._tr.get_or_add_trPr()
            h = OxmlElement("w:tblHeader")
            h.set(qn("w:val"), "1")
            trPr.append(h)
        stats["tables"] += 1
        spacer(4)

    def picture(path: Path, caption: str):
        if not path.exists():
            return
        d.add_picture(str(path), width=Cm(15.0))
        d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap = d.add_paragraph()
        cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        set_run_font(cap.add_run("그림. " + caption), 7.5, color=RGBColor(0x55, 0x55, 0x55))
        stats["images"] += 1

    def codeblock(buf: list[str]):
        for ln in buf:
            p = d.add_paragraph()
            p.paragraph_format.space_after = Pt(0)
            p.paragraph_format.left_indent = Cm(0.2)
            pPr = p._p.get_or_add_pPr()
            shd = OxmlElement("w:shd")
            shd.set(qn("w:val"), "clear")
            shd.set(qn("w:color"), "auto")
            shd.set(qn("w:fill"), "F2F5F9")
            pPr.append(shd)
            set_run_font(p.add_run(ln if ln else " "), 7.2, mono=True)
        spacer(4)

    i, first = 0, True
    while i < len(lines):
        l = lines[i]
        if l.startswith("```"):
            lang = l[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            if lang == "mermaid":
                if mermaid_image:
                    picture(mermaid_image, "개념 모델(클래스와 관계)")
            else:
                codeblock(buf)
            continue
        if l.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s\-|:]+\|$", lines[i + 1]):
            rows = [cellsplit(l)]
            i += 2
            while i < len(lines) and lines[i].startswith("|"):
                rows.append(cellsplit(lines[i]))
                i += 1
            table(rows)
            continue
        m = re.match(r"^(#{1,4}) (.*)", l)
        if m:
            lvl, txt = len(m.group(1)), link_strip(m.group(2))
            if first and lvl == 1:
                d.add_paragraph(txt, style="Title")
                first = False
            else:
                # 마크다운 '##'(절)은 양식의 Heading 1, '###'은 Heading 2, '####'는 Heading 3
                d.add_paragraph(txt, style=f"Heading {min(max(lvl - 1, 1), 4)}")
                stats["headings"] += 1
            i += 1
            continue
        mi = re.match(r"^!\[(.*?)\]\((.+?)\)\s*$", l)
        if mi:
            picture(base / mi.group(2), mi.group(1))
            i += 1
            continue
        if l.strip() in ("", "---"):
            i += 1
            continue
        if l.startswith("> "):
            p = d.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.7)
            p.paragraph_format.space_after = Pt(2)
            inline(p, l[2:], 8.5)
            i += 1
            continue
        if re.match(r"^\s*- ", l):
            p = d.add_paragraph()
            p.paragraph_format.left_indent = Cm(0.6)
            p.paragraph_format.first_line_indent = Cm(-0.4)
            p.paragraph_format.space_after = Pt(1)
            item = re.sub(r"^\s*- ", "", l)
            # 체크리스트(■/□)는 양식처럼 글머리 기호 없이 표시한다
            inline(p, item if item[:1] in ("■", "□") else "• " + item)
            i += 1
            continue
        p = d.add_paragraph()
        p.paragraph_format.space_after = Pt(4)
        inline(p, l)
        i += 1
    d.save(str(out))
    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--template", required=True)
    ap.add_argument("--md", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--footer", default="2팀")
    ap.add_argument("--mermaid-image", default=None)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    st = build(Path(a.template), Path(a.md), Path(a.out), a.footer, Path(a.mermaid_image) if a.mermaid_image else None)
    print("saved", a.out, st)


if __name__ == "__main__":
    main()
