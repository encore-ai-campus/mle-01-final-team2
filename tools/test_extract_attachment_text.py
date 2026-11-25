"""extract_attachment_text.py 단위 시험(합성 데이터 사용). 실행: python tools/test_extract_attachment_text.py"""
import struct
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_attachment_text as E  # noqa: E402


def rec(tag: int, payload: bytes) -> bytes:
    size = len(payload)
    if size >= 0xFFF:
        return struct.pack("<I", tag | (0xFFF << 20)) + struct.pack("<I", size) + payload
    return struct.pack("<I", tag | (size << 20)) + payload


def utf16(s: str) -> bytes:
    return s.encode("utf-16-le")


class TestHwpRecords(unittest.TestCase):
    def test_para_text_and_controls(self):
        ctrl = struct.pack("<H", 11) + b"\x00" * 14  # 확장 컨트롤: 8 WCHAR 차지
        data = rec(66, b"\x00" * 8) + rec(E.HWPTAG_PARA_TEXT, utf16("신청자격 ") + ctrl + utf16("중소기업") + struct.pack("<H", 13))
        data += rec(E.HWPTAG_PARA_TEXT, utf16("둘째 문단"))
        self.assertEqual([p.strip() for p in E.parse_hwp_section(data)], ["신청자격 중소기업", "둘째 문단"])

    def test_large_record_size_field(self):
        text = "가" * 3000  # 6,000바이트 -> 확장 길이 필드 사용
        self.assertEqual(E.parse_hwp_section(rec(E.HWPTAG_PARA_TEXT, utf16(text))), [text])

    def test_surrogate_pair_is_joined(self):
        text = "𠮷野家 신청"  # U+20BB7은 UTF-16 서로게이트 쌍
        out = E.parse_hwp_section(rec(E.HWPTAG_PARA_TEXT, utf16(text)))
        self.assertEqual(out, [text])
        out[0].encode("utf-8")  # 저장 가능해야 한다

    def test_truncated_data_does_not_crash(self):
        data = rec(E.HWPTAG_PARA_TEXT, utf16("가나다"))[:-3]
        E.parse_hwp_section(data)  # 예외 없이 끝나면 통과
        E.parse_hwp_section(b"\x01\x02")


class TestHwpx(unittest.TestCase):
    NS = 'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"'

    def _make(self, xml: str) -> Path:
        f = tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False)
        f.close()
        with zipfile.ZipFile(f.name, "w") as z:
            z.writestr("Contents/section0.xml", xml)
        return Path(f.name)

    def test_paragraphs_and_table(self):
        xml = (f'<hp:sec {self.NS}>'
               '<hp:p><hp:run><hp:t>1. 신청자격</hp:t></hp:run></hp:p>'
               '<hp:p><hp:run><hp:tbl><hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t>업력</hp:t></hp:run></hp:p></hp:subList></hp:tc>'
               '<hp:tc><hp:subList><hp:p><hp:run><hp:t>7년 이내</hp:t></hp:run></hp:p></hp:subList></hp:tc></hp:tr></hp:tbl></hp:run></hp:p>'
               '<hp:p><hp:run><hp:t>끝</hp:t></hp:run></hp:p></hp:sec>')
        p = self._make(xml)
        text, status, _, n = E.extract_hwpx(p)
        self.assertEqual(status, "OK")
        self.assertEqual(text.split("\n"), ["1. 신청자격", "업력", "7년 이내", "끝"])  # 표 셀이 중복 없이 한 번씩
        self.assertEqual(n, 1)

    def test_not_zip(self):
        f = tempfile.NamedTemporaryFile(suffix=".hwpx", delete=False); f.write(b"not a zip"); f.close()
        self.assertEqual(E.extract_hwpx(Path(f.name))[1], "NOT_HWPX_OR_CORRUPT")


class TestSections(unittest.TestCase):
    def test_find_sections(self):
        text = "=== p.1 ===\n□ 지원대상\n중소기업\n=== p.2 ===\n2. 신청제외 대상\n휴폐업 업체\n나. 제출서류\n사업자등록증\n"
        offs = [0, text.index("=== p.2")]
        s = E.find_sections(text, offs)
        self.assertEqual([x["label"] for x in s], ["ELIGIBILITY", "EXCLUSION", "DOCUMENT"])
        self.assertEqual([x.get("page") for x in s], [1, 2, 2])
        self.assertIn("중소기업", text[s[0]["start"]:s[0]["end"]])
        self.assertNotIn("휴폐업", text[s[0]["start"]:s[0]["end"]])

    def test_bullet_and_inline_value_headings(self):
        text = ("❍ 지원제외 대상 업종\n\U000f02b2 지원 제외\nm 지원대상 : 참가신청일 현재 관내 소재 중소기업 및 중장년 취업자로서 요건을 갖춘 자\n"
                "가. (신청기간) 2026. 4. 1. ~ 2026. 4. 30. 까지 접수하며 기간 내에 제출한 경우에 한한다\n1. 모집대상(참여자격)\n")
        labels = [s["label"] for s in E.find_sections(text)]
        self.assertEqual(labels, ["EXCLUSION", "EXCLUSION", "ELIGIBILITY", "PERIOD", "ELIGIBILITY"])

    def test_long_sentence_is_not_heading(self):
        text = "본 사업은 지원대상 기업을 선정하기 위하여 다음과 같이 공고하며 신청자격 요건을 충족하는 경우에 한하여 접수한다."
        self.assertEqual(E.find_sections(text), [])


class TestFiles(unittest.TestCase):
    def test_sniff_and_image(self):
        d = Path(tempfile.mkdtemp())
        (d / "a.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        rec_, text, search = E.extract_file(d / "a.png")
        self.assertEqual((rec_["format"], rec_["status"], text, search), ("png", "IMAGE_NEEDS_OCR", "", None))
        (d / "b.bin").write_bytes(b"hello world")
        self.assertEqual(E.extract_file(d / "b.bin")[0]["status"], "UNSUPPORTED_FORMAT")

    def test_corrupt_hwp_and_pdf(self):
        d = Path(tempfile.mkdtemp())
        (d / "x.hwp").write_bytes(b"\xd0\xcf\x11\xe0" + b"0" * 50)
        self.assertEqual(E.extract_file(d / "x.hwp")[0]["status"], "NOT_HWP5_OR_CORRUPT")
        (d / "y.pdf").write_bytes(b"%PDF-1.4 broken")
        self.assertIn(E.extract_file(d / "y.pdf")[0]["status"], ("NOT_PDF_OR_CORRUPT", "NEEDS_OCR"))

    def test_pdf_text_and_scanned(self):
        d = Path(tempfile.mkdtemp())
        doc = E.pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Eligibility: SME founded within 7 years. " * 3, fontsize=11)
        doc.save(str(d / "t.pdf")); doc.close()
        blank = E.pymupdf.open(); blank.new_page(); blank.save(str(d / "s.pdf")); blank.close()
        r1, t1, _ = E.extract_file(d / "t.pdf")
        self.assertEqual((r1["status"], r1["pages"]), ("OK", 1))
        self.assertIn("=== p.1 ===", t1)
        self.assertIn("Eligibility", t1)
        self.assertEqual(E.extract_file(d / "s.pdf")[0]["status"], "NEEDS_OCR")


class TestChooseDpi(unittest.TestCase):
    def test_normal_page_keeps_300(self):
        doc = E.pymupdf.open(); page = doc.new_page(width=595, height=842)
        self.assertEqual(E.choose_dpi(page), 300)

    def test_huge_page_is_capped(self):
        doc = E.pymupdf.open(); page = doc.new_page(width=4958, height=7008)  # 실제 실패 파일(127340)과 같은 쪽 크기
        dpi = E.choose_dpi(page)
        self.assertLess(dpi, 300)
        pix = page.get_pixmap(dpi=dpi)  # 예전에는 300dpi에서 FzErrorLimit이 났다
        self.assertLessEqual(max(pix.width, pix.height), E.OCR_MAX_PIXELS + 2)

    def test_dpi_follows_embedded_image_resolution(self):
        from PIL import Image
        p = Path(tempfile.mkdtemp()) / "i.png"; Image.new("RGB", (800, 1100), "white").save(p)
        doc = E.pymupdf.open(); page = doc.new_page(width=595, height=842); page.insert_image(page.rect, filename=str(p))
        self.assertLess(E.choose_dpi(page), 130)  # 800px / 8.26in ≈ 97dpi


class TestOcrHelpers(unittest.TestCase):
    def test_despace_hangul(self):
        self.assertEqual(E.despace_hangul("신 청 자 격 : 중 소 기업 TIPS 2026"), "신청자격 : 중소기업 TIPS 2026")
        self.assertEqual(E.despace_hangul("a b\n가 나"), "a b\n가나")

    def test_tsv_to_lines(self):
        hdr = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext"
        rows = [hdr,
                "5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t90.5\t신청",
                "5\t1\t1\t1\t1\t2\t0\t0\t1\t1\t80.0\t자격",
                "5\t1\t1\t1\t2\t1\t0\t0\t1\t1\t-1\t ",      # 신뢰도 -1·빈 단어는 버린다
                "5\t1\t1\t1\t2\t2\t0\t0\t1\t1\t40\t제외"]
        lines, confs = E.tsv_to_lines("\n".join(rows))
        self.assertEqual(lines, ["신청 자격", "제외"])
        self.assertEqual(confs, [90.5, 80.0, 40.0])
        self.assertEqual(E.tsv_to_lines("")[0], [])


@unittest.skipUnless(E.find_tesseract() and Path(r"C:\Windows\Fonts\malgun.ttf").exists(), "Tesseract 또는 맑은 고딕 글꼴 없음")
class TestOcrEndToEnd(unittest.TestCase):
    def _image(self, text: str) -> Path:
        from PIL import Image, ImageDraw, ImageFont
        im = Image.new("RGB", (1400, 260), "white")
        ImageDraw.Draw(im).text((40, 60), text, fill="black", font=ImageFont.truetype(r"C:\Windows\Fonts\malgun.ttf", 64))
        p = Path(tempfile.mkdtemp()) / "t.png"
        im.save(p)
        return p

    def test_image_ocr_and_sections(self):
        p = self._image("지원대상 : 중소기업")
        rec_, raw, search = E.extract_file(p, ocr=True, tess=E.find_tesseract())
        self.assertEqual(rec_["status"], "OK_OCR")
        self.assertIn("OCR_LOW_TRUST", rec_["warnings"])
        self.assertEqual(rec_["sections_text"], "search")
        self.assertIn("지원대상", search.replace(" ", ""))
        self.assertTrue(rec_["ocr"]["words"] > 0)

    def test_scanned_pdf_ocr_has_page_markers(self):
        png = self._image("신청자격 : 창업 7년 이내")
        doc = E.pymupdf.open()
        page = doc.new_page(width=842, height=300)
        page.insert_image(page.rect, filename=str(png))
        pdf = png.with_suffix(".pdf"); doc.save(str(pdf)); doc.close()
        rec_, raw, search = E.extract_file(pdf, ocr=True, tess=E.find_tesseract())
        self.assertEqual(rec_["status"], "OK_OCR")
        self.assertIn("=== p.1 ===", search)
        self.assertEqual(rec_["pages"], 1)

    def test_without_flag_or_tesseract(self):
        p = self._image("지원대상")
        self.assertEqual(E.extract_file(p)[0]["status"], "IMAGE_NEEDS_OCR")
        r = E.extract_file(p, ocr=True, tess=None)[0]
        self.assertEqual(r["status"], "IMAGE_NEEDS_OCR")
        self.assertIn("TESSERACT_NOT_FOUND", r["warnings"])


class TestClean(unittest.TestCase):
    def test_clean_text(self):
        self.assertEqual(E.clean_text("가 나 \r\n\n  다\t라  "), "가 나\n다 라")

    def test_quality_warnings(self):
        self.assertIn("REPLACEMENT_CHARS", E.quality_warnings("가�" * 10))
        self.assertTrue(any(w.startswith("PUA_CHARS") for w in E.quality_warnings("" * 50 + "가" * 10)))


if __name__ == "__main__":
    unittest.main(verbosity=1)
