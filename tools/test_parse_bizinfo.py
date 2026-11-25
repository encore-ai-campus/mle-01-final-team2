"""parse_bizinfo.py 단위 시험. 실행: python tools/test_parse_bizinfo.py"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import parse_bizinfo as P  # noqa: E402


class TestHtml(unittest.TestCase):
    def test_blocks_and_entities(self):
        t = P.html_to_text('<p>개요&nbsp;문장</p><p><br></p><p style="x">☞&nbsp;대상 A</p><p>-&nbsp;세부 &amp; 조건</p>')
        self.assertEqual(t, "개요 문장\n\n☞ 대상 A\n- 세부 & 조건")

    def test_split_blocks(self):
        b = P.split_blocks("개요\n☞ 대상\n- 세부\n☞ 지원\n※ 참고")
        self.assertEqual(b["intro"], ["개요"])
        self.assertEqual([x["head"] for x in b["blocks"]], ["대상", "지원"])
        self.assertEqual(b["notes"], ["※ 참고"])
        self.assertEqual(P.block_text(b["blocks"][0]), "대상\n- 세부")


class TestPeriod(unittest.TestCase):
    def test_range(self):
        p = P.parse_period("2026-11-23 ~ 2026-11-30")
        self.assertEqual(p["application_end_date"], "2026-11-30")
        self.assertEqual(p["deadline_at"], "2026-11-30T23:59:59+09:00")
        self.assertEqual(p["apply_status_kind"], "DATE_RANGE")

    def test_compact_range(self):
        self.assertEqual(P.parse_period("20220727 ~ 20220930")["application_start_date"], "2022-07-27")

    def test_non_date_keeps_raw_without_deadline(self):
        for raw, kind in [("예산 소진시까지", "UNTIL_BUDGET_EXHAUSTED"), ("상시 접수", "ALWAYS_OPEN"),
                          ("선착순 접수", "FIRST_COME"), ("모집 완료시", "UNTIL_FILLED"), ("세부사업별 상이", "VARIES_OR_TBD"),
                          ("매월 10일 18:00까지", "UNPARSED")]:
            p = P.parse_period(raw)
            self.assertEqual(p["apply_status_kind"], kind, raw)
            self.assertIsNone(p["deadline_at"], raw)
            self.assertEqual(p["deadline_raw"], raw)

    def test_invalid_date(self):
        self.assertIsNone(P.parse_period("2026-13-40 ~ 2026-13-41")["deadline_at"])


class TestAttachments(unittest.TestCase):
    def test_split_names(self):
        self.assertEqual(P.split_file_names("a.pdf@b 서식.hwpx"), ["a.pdf", "b 서식.hwpx"])
        self.assertEqual(P.split_file_names("문의 a@b.com 안내.pdf"), ["문의 a@b.com 안내.pdf"])
        self.assertEqual(P.split_file_names(None), [])

    def test_pairing_and_no_token(self):
        item = {"fileNm": "a.pdf@b.zip",
                "flpthNm": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_1&fileSn=1&downloadToken=[REDACTED]&fileSn=2&downloadToken=[REDACTED]",
                "printFileNm": "본문.hwp",
                "printFlpthNm": "https://www.bizinfo.go.kr/cmm/fms/getImageFile.do?atchFileId=FILE_2&fileSn=0&downloadToken=[REDACTED]"}
        atts, warns = P.parse_attachments("BIZINFO:PBLN_1", item)
        self.assertEqual(warns, [])
        self.assertEqual([(a["role"], a["file_name"], a["file_sn"]) for a in atts],
                         [("ATTACHMENT", "a.pdf", "1"), ("ATTACHMENT", "b.zip", "2"), ("PRINT_BODY", "본문.hwp", "0")])
        self.assertTrue(all("downloadToken" not in (a["source_url"] or "") for a in atts))

    def test_count_mismatch_warns(self):
        _, w = P.parse_attachments("X", {"fileNm": "a.pdf@b.pdf", "flpthNm": "https://x/getImageFile.do?atchFileId=F&fileSn=1"})
        self.assertTrue(any(x.startswith("ATTACHMENT_COUNT_MISMATCH") for x in w))


class TestTagsAndOrgs(unittest.TestCase):
    def test_all_sido_is_hint_only(self):
        tags = ["기술"] + [t for t in P.SIDO_BY_TAG] + ["키워드", "2026", "중소벤처기업부"]
        c = P.classify_tags(tags, {"중소벤처기업부"})
        self.assertEqual(c["region_scope_hint"], "ALL_SIDO_TAGGED")
        self.assertEqual(c["keyword"], ["키워드"])
        self.assertEqual(c["agency"], ["중소벤처기업부"])
        self.assertEqual(c["year"], ["2026"])

    def test_legacy_gwangju_jeonnam_counts_as_cover(self):
        tags = [t for t in P.SIDO_BY_TAG if t != "전남광주"] + ["광주", "전남"]
        self.assertEqual(P.classify_tags(tags, set())["region_scope_hint"], "ALL_SIDO_TAGGED")

    def test_specific_and_none(self):
        self.assertEqual(P.classify_tags(["경북", "창업"], set())["region_scope_hint"], "SPECIFIC_SIDO_TAGGED")
        self.assertEqual(P.classify_tags(["창업"], set())["region_scope_hint"], "NO_REGION_TAG")

    def test_executor(self):
        self.assertEqual(P.parse_executor("기초자치단체")["executor_kind"], "LOCAL_GOVERNMENT_UNSPECIFIED")
        self.assertEqual(P.parse_executor("직접수행")["executor_kind"], "SELF_OPERATED")
        e = P.parse_executor("경기도일자리재단 남부사업본부장")
        self.assertEqual((e["executor_org_name"], e["executor_role_title"]), ("경기도일자리재단", "남부사업본부장"))
        self.assertEqual(P.parse_executor("경상북도경제진흥원")["executor_org_name"], "경상북도경제진흥원")


class TestItem(unittest.TestCase):
    def test_parse_item(self):
        item = {"pblancId": "PBLN_000000000000001", "pblancNm": "시험 공고", "pblancUrl": "https://x/view?pblancId=PBLN_1",
                "bsnsSumryCn": "<p>개요</p><p>☞&nbsp;창업 7년 이내 기업</p><p>☞ 컨설팅 지원</p>",
                "reqstBeginEndDe": "예산 소진시까지", "trgetNm": "중소기업", "hashtags": "창업,서울,2026",
                "jrsdInsttNm": "서울특별시", "excInsttNm": "기초자치단체", "creatPnttm": "2026-11-23 15:05:41",
                "updtPnttm": "2026-11-23 15:29:54", "inqireCo": "12", "pldirSportRealmLclasCodeNm": "창업"}
        rec, atts, _ = P.parse_item(item, "2026-11-24T09:16:01+09:00")
        self.assertEqual(rec["notice_id"], "BIZINFO:PBLN_000000000000001")
        self.assertEqual(rec["eligibility_criteria_text"], "창업 7년 이내 기업")
        self.assertIsNone(rec["deadline_at"])
        self.assertEqual(rec["published_at"], "2026-11-23T15:05:41+09:00")
        self.assertEqual(rec["region_scope_hint"], "SPECIFIC_SIDO_TAGGED")
        self.assertEqual(rec["jurisdiction_sido_code"], "1100000000")
        self.assertEqual(atts, [])
        # 결정적: 같은 입력이면 해시가 같다
        rec2, _, _ = P.parse_item(item, "2099-01-01T00:00:00+09:00")
        self.assertEqual((rec["content_hash"], rec["raw_hash"]), (rec2["content_hash"], rec2["raw_hash"]))


if __name__ == "__main__":
    unittest.main(verbosity=1)
