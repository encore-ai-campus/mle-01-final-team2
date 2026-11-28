"""요건 검수 큐(B-3 ②) 시험. 합성 공고·청크만 쓴다(실제 검수 결과 아님). 네트워크·모델 없이 돈다.

실행: python -m unittest tests.test_requirement_review_queue -v
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools import requirement_review_queue as Q  # noqa: E402
from tools.ingest_condition_gold_reviews import make_id  # noqa: E402

NID = "BIZINFO:TEST1"
ELIG = "대구광역시 소재 창업 3년 이내 기업. 업력 계산은 사업자등록일 기준."
EXCL = "국세·지방세 체납 기업은 신청할 수 없습니다(제외 대상)."
CHUNKS = [
    {"chunk_id": f"{NID}#apply_method:0", "notice_id": NID, "section": "apply_method", "text": "온라인으로 접수합니다. 사업계획서를 제출합니다."},
    {"chunk_id": f"{NID}#att_exclusion@f0-1:0", "notice_id": NID, "section": "att_exclusion@f0-1", "text": EXCL},
    {"chunk_id": f"{NID}#eligibility_api:0", "notice_id": NID, "section": "eligibility_api", "text": ELIG},
    {"chunk_id": f"{NID}#att_eligibility@f0-2:0", "notice_id": NID, "section": "att_eligibility@f0-2", "text": ELIG},  # 같은 글 → 한 번만
    {"chunk_id": f"{NID}#att_eligibility@f0-3:0", "notice_id": NID, "section": "att_eligibility@f0-3", "text": "짧음"},
]
NOTICE = {"notice_id": NID, "title": "합성 공고", "source": "BIZINFO", "deadline": "2026-12-01", "detail_url": "https://example.org/1",
          "conditions": [], "text_requirements": "unparsed"}


def fake_extract(text, notice_id, source, origin, section, kind):
    """규칙 추출기 대역: '3년 이내'와 '체납'을 후보로 낸다. char_start는 구역 글 기준."""
    out = []
    for quote, attr, op, val in (("창업 3년 이내", "business_age", "LTE", {"value": 3, "unit": "YEAR"}),
                                 ("체납 기업은 신청할 수 없습니다", "exclusion", "TEXT_ONLY", {"text_only": True})):
        i = text.find(quote)
        if i >= 0:
            out.append({"rule_id": attr, "attribute": attr, "operator": op, "value": val, "concept": None, "ambiguous": False,
                        "evidence_text": quote, "char_start": 0})
    return out


def row():
    return Q.queue_row(NOTICE, CHUNKS, True, "2026-11-24", extract=fake_extract)


def verify(r, conds, whole=True, logic=None):
    """검수자가 하는 일: 조건을 적고 VERIFIED로 바꾼다."""
    r = json.loads(json.dumps(r))
    r.update(gold_conditions=conds, review_status="VERIFIED", adjudication_status="REVIEWED_COMPLETE", reviewer="검수자A",
             reviewed_at="2026-11-28T10:00:00+09:00", whole_notice_conditions_complete=whole, gold_logic_roots=logic or [])
    return r


def cond(r, quote, ctype, field, op, value, unit=None):
    s = r["source_text"].index(quote)
    e = s + len(quote)
    return {"gold_condition_id": make_id(NID, ctype, s, e, quote), "condition_type": ctype, "field": field, "category": field,
            "operator": op, "value": value, "unit": unit, "raw_text": quote, "source_field": Q.SOURCE_FIELD,
            "evidence_reference": {"start_char": s, "end_char": e}, "reference_date_type": "UNKNOWN", "review_status": "VERIFIED",
            "review_comment": None}


class TestBuild(unittest.TestCase):
    def test_source_text_keeps_chunk_text_and_offsets(self):
        text, segs = Q.compose_source(CHUNKS)
        self.assertEqual([s["section"] for s in segs], ["eligibility_api", "att_exclusion@f0-1"])  # 순서·중복·짧은 글·신청 방법 제외
        for s, src in zip(segs, (ELIG, EXCL)):
            self.assertEqual(text[s["start"]:s["end"]], src)
        self.assertEqual(segs[1]["condition_type"], "EXCLUSION")

    def test_rule_prefill_anchors_in_source_and_is_not_decision(self):
        r = row()
        self.assertEqual(len(r["prefill_candidates"]), 2)
        for c in r["prefill_candidates"]:
            ref = c["evidence_reference"]
            self.assertEqual(r["source_text"][ref["start_char"]:ref["end_char"]], c["raw_text"])
            self.assertFalse(c["decision_possible"])
        self.assertEqual({c["condition_type"] for c in r["prefill_candidates"]}, {"ELIGIBILITY", "EXCLUSION"})
        self.assertEqual(r["review_status"], "UNREVIEWED")

    def test_llm_proposal_anchored_only_when_unique(self):
        text = "대구 소재 기업. 대구 소재 기업. 업력 5년 미만."
        out, unanchored = Q.proposal_prefill(NID, text, [{"condition_id": "C1", "field": "BUSINESS_LOCATION", "raw_text": "대구 소재 기업"},
                                                         {"condition_id": "C2", "field": "BUSINESS_AGE", "raw_text": "업력 5년 미만"}])
        self.assertEqual(unanchored, 1)  # 두 번 나오는 근거는 첫 위치를 고르지 않는다
        self.assertIsNone(out[0]["evidence_reference"])
        self.assertTrue(out[1]["anchored"])

    def test_priority_open_soon_first(self):
        k_soon, _ = Q.priority({**NOTICE, "deadline": "2026-11-30"}, True, "2026-11-24")
        k_open, _ = Q.priority({**NOTICE, "deadline": "2027-03-01"}, True, "2026-11-24")
        k_closed, reasons = Q.priority(NOTICE, False, "2026-11-24")
        self.assertLess(k_soon, k_open)
        self.assertLess(k_open, k_closed)
        self.assertIn("마감·상태 미상", reasons)

    def test_rebuild_keeps_reviewer_work_and_marks_stale(self):
        r = row()
        worked = {**r, "gold_conditions": [cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3, "YEAR")]}
        other = {**r, "notice_id": "BIZINFO:OTHER"}
        changed = {**r, "source_text": r["source_text"] + " 추가", "source_hash": "x"}
        merged, stats = Q.merge([changed], [worked, other])
        self.assertEqual(stats["kept_reviewed"], 1)
        self.assertTrue(merged[0]["stale_source"])
        self.assertEqual(merged[0]["gold_conditions"], worked["gold_conditions"])  # 덮어쓰지 않는다
        self.assertEqual(stats["dropped"], 1)  # 손대지 않은 대상 밖 행은 뺀다


class TestIngest(unittest.TestCase):
    def ingest(self, rows):
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / "queue.jsonl"
            Q.write_jsonl(q, rows)
            rep = Q.ingest(q)
            applied = Q.read_jsonl(Path(d) / "service" / "reviewed_condition_gold.jsonl")
        return rep, applied

    def test_only_valid_verified_rows_are_applied(self):
        r = row()
        good = verify(r, [cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3, "YEAR")])
        bad_span = verify({**r, "notice_id": "BIZINFO:B"}, [{**cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3), "raw_text": "다른 글"}])
        bad_id = verify({**r, "notice_id": "BIZINFO:C"}, [cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3)])  # id가 다른 공고 기준
        unverified = verify({**r, "notice_id": "BIZINFO:D"}, [{**cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3), "review_status": "UNREVIEWED"}])
        stale = {**verify({**r, "notice_id": "BIZINFO:E"}, []), "adjudication_status": "CONFIRMED_NONE_IN_PROVIDED_TEXT", "stale_source": True}
        no_reviewer = {**verify({**r, "notice_id": "BIZINFO:F"}, []), "reviewer": None}
        rep, applied = self.ingest([good, bad_span, bad_id, unverified, stale, no_reviewer, r])
        self.assertEqual([a["notice_id"] for a in applied], [NID])
        self.assertEqual(rep["applied"], 1)
        self.assertEqual(rep["verified"], 6)  # UNREVIEWED 행은 세지 않는다
        self.assertEqual({x["notice_id"] for x in rep["rejected"]}, {"BIZINFO:B", "BIZINFO:C", "BIZINFO:D", "BIZINFO:E", "BIZINFO:F"})

    def test_logic_must_reference_known_conditions(self):
        r = row()
        c = cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3, "YEAR")
        bad = verify(r, [c], logic=[{"node_type": "LOGICAL_GROUP", "group_id": "g", "operator": "AND",
                                    "children": [{"node_type": "CONDITION_REF", "condition_id": "GOLD:NOPE"}]}])
        self.assertIn("논리가 없는 조건을 가리킴(GOLD:NOPE)", Q.check_row(bad))


class TestToVerdict(unittest.TestCase):
    """검수 → ingest → gold_bridge → 평가기. 공고 전체 확인이면 REQ_UNPARSED가 풀린다."""

    def run_eval(self, whole, age):
        from tools.graphrag import gold_bridge
        from tools.graphrag.evaluator import Profile, evaluate_notice
        from tools.graphrag.regions import RegionGraph

        r = row()
        reviewed = verify(r, [cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3, "YEAR")], whole=whole)
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / "queue.jsonl"
            Q.write_jsonl(q, [reviewed])
            Q.ingest(q)
            g = gold_bridge.load_all(resolve_region=lambda x: (None,), service_root=Path(d))
        n = {**NOTICE, "conditions": []}
        gold_bridge.attach([n], {NID: g[NID]})
        self.assertEqual(g[NID]["review"]["split"], "SERVICE")
        return n, evaluate_notice(n, Profile(business_age_years=age), RegionGraph())

    def test_whole_notice_review_lifts_req_unparsed(self):
        n, r = self.run_eval(True, 2)
        self.assertEqual(n["text_requirements"], "reviewed")
        self.assertNotIn("REQ_UNPARSED", r["reasons"])
        self.assertEqual(r["verdict"], "ELIGIBLE")
        _, r = self.run_eval(True, 10)
        self.assertEqual(r["verdict"], "NOT_ELIGIBLE")  # 업력은 hard 조건

    def test_partial_review_keeps_needs_check(self):
        n, r = self.run_eval(False, 2)
        self.assertEqual(n["text_requirements"], "partially_reviewed")
        self.assertIn("REQ_UNPARSED", r["reasons"])
        self.assertEqual(r["verdict"], "NEEDS_CHECK")


class TestReload(unittest.TestCase):
    """API 재시작 없이 검수 결과 다시 읽기(Engine.reload_reviews). 검수를 되돌리면 원래 상태로 돌아가야 한다."""

    def test_reload_attaches_and_reverts(self):
        from types import SimpleNamespace
        from unittest import mock

        from tools.graphrag import gold_bridge
        from tools.graphrag.engine import Engine

        r = row()
        reviewed = verify(r, [cond(r, "창업 3년 이내", "ELIGIBILITY", "BUSINESS_AGE", "LTE", 3, "YEAR")])
        with tempfile.TemporaryDirectory() as d:
            q = Path(d) / "queue.jsonl"
            Q.write_jsonl(q, [reviewed])
            Q.ingest(q)
            gold = gold_bridge.load_all(resolve_region=lambda x: (None,), service_root=Path(d))
        notice = {**NOTICE, "conditions": []}
        eng = SimpleNamespace(notices=[notice, {**NOTICE, "notice_id": "BIZINFO:OTHER", "text_requirements": "unparsed"}])
        with mock.patch.object(gold_bridge, "load_all", return_value=gold):
            rep = Engine.reload_reviews(eng)
        self.assertEqual((rep["before"], rep["after"], rep["reviewed"]), (0, 1, 1))
        self.assertEqual(notice["text_requirements"], "reviewed")
        with mock.patch.object(gold_bridge, "load_all", return_value={}):  # 검수를 되돌림(다시 작업)
            rep = Engine.reload_reviews(eng)
        self.assertEqual((rep["before"], rep["after"]), (1, 0))
        self.assertEqual(notice["text_requirements"], "unparsed")
        self.assertNotIn("gold_requirements", notice)
        self.assertNotIn("_text_requirements_base", notice)


if __name__ == "__main__":
    unittest.main()
