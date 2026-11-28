"""오케스트레이터·공고 질의(RAG)·하이브리드 검색·LLM 게이트웨이 시험. 네트워크·데이터·모델 없이 돈다.

실행: python -m unittest tests.test_orchestration -v
"""
import asyncio
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

HAS_DEPS = all(importlib.util.find_spec(m) for m in ("openai", "langgraph", "fastapi", "httpx", "yaml", "numpy"))

CHUNKS = [
    {"chunk_id": "N1#apply_method:0", "notice_id": "N1", "source": "KSTARTUP", "section": "apply_method",
     "origin": "API", "text": "신청 방법: K-Startup 누리집에서 온라인으로 접수한다. 사업계획서를 제출한다."},
    {"chunk_id": "N1#support_details:0", "notice_id": "N1", "source": "KSTARTUP", "section": "support_details",
     "origin": "API", "text": "지원 내용: 사업화 자금 최대 1억 원을 지원한다."},
    {"chunk_id": "N2#apply_method:0", "notice_id": "N2", "source": "BIZINFO", "section": "apply_method",
     "origin": "API", "text": "우편 또는 방문 접수. 제출 서류는 신청서와 사업자등록증 사본."},
]
META = {"N1": {"title": "청년 창업 지원", "source": "KSTARTUP", "detail_url": "https://example.org/1", "fetched_at": "2026-11-24"},
        "N2": {"title": "소상공인 지원", "source": "BIZINFO", "detail_url": "https://example.org/2", "fetched_at": "2026-11-24"}}


class FakeEmbedder:
    """주제어 개수 벡터. 같은 주제어가 있으면 가깝고, 하나도 없으면 영벡터(유사도 0)다."""

    TOPICS = ("신청", "접수", "방법", "지원", "자금", "서류", "제출")

    def __init__(self, dim=len(TOPICS), fail=False):
        from agent.rag.embedder import EmbedConfig

        self.cfg = EmbedConfig(base_url="x", model="fake", api_key=None, dim=dim, index_dir=Path("."))
        self.fail = fail

    def embed(self, texts):
        from agent.rag.embedder import EmbeddingError

        if self.fail:
            raise EmbeddingError("down")
        return [[float(t.count(k)) for k in self.TOPICS] for t in texts]


def retriever(fail=False):
    from agent.rag import HybridRetriever
    from agent.rag.dense import DenseIndex, build
    from tools.graphrag.search import BM25

    with tempfile.TemporaryDirectory() as d:
        build(CHUNKS, FakeEmbedder(), Path(d), log=lambda m: None)
        dense = DenseIndex.load(Path(d))
    return HybridRetriever(CHUNKS, BM25(CHUNKS), dense, FakeEmbedder(fail=fail))


def collect(agen):
    async def go():
        return [e async for e in agen]

    return asyncio.run(go())


@unittest.skipUnless(HAS_DEPS, "openai·langgraph·fastapi·httpx·pyyaml·numpy가 필요하다")
class TestHybridRetriever(unittest.TestCase):
    def test_rrf_fuses_bm25_and_dense(self):
        res = retriever().search_detailed("신청 방법 온라인 접수", None, top=3)
        self.assertEqual(res["mode"], "hybrid")
        self.assertEqual(res["hits"][0]["chunk"]["chunk_id"], "N1#apply_method:0")
        self.assertIsNotNone(res["hits"][0]["rank_dense"])

    def test_allowed_notices_filter_applies_to_both(self):
        res = retriever().search_detailed("신청 방법 접수", {"N2"}, top=5)
        self.assertTrue(res["hits"])
        self.assertEqual({h["chunk"]["notice_id"] for h in res["hits"]}, {"N2"})

    def test_embedding_failure_falls_back_to_bm25(self):
        r = retriever(fail=True)
        res = r.search_detailed("신청 방법", None, top=3)
        self.assertEqual(res["mode"], "bm25")
        self.assertEqual(r.status()["last_error"], "down")
        self.assertEqual(len(r.search("신청 방법", None, 2)), 2)  # 엔진용 모양 [(점수, 청크)]

    def test_rebuild_reuses_unchanged_vectors(self):
        from agent.rag.dense import build

        with tempfile.TemporaryDirectory() as d:
            build(CHUNKS, FakeEmbedder(), Path(d), log=lambda m: None)
            meta = build(CHUNKS, FakeEmbedder(), Path(d), log=lambda m: None)
        self.assertEqual(meta["embedded_now"], 0)
        self.assertEqual(meta["chunks"], 3)


@unittest.skipUnless(HAS_DEPS, "openai·langgraph·fastapi·httpx·pyyaml·numpy가 필요하다")
class TestRulePlan(unittest.TestCase):
    def test_routes(self):
        from agent.orchestrator import rule_plan

        def term(q):
            return "중소기업" in q

        self.assertEqual(rule_plan("중소기업이 뭐야?", {}, None, term)[0], ["definition"])
        self.assertEqual(rule_plan("이 공고 신청 방법 알려줘", {}, "N1", term)[0], ["notice_qa"])
        self.assertEqual(rule_plan("서울 창업 2년차인데 신청할 수 있는 사업과 제출 서류 알려줘", {}, None, term)[0],
                         ["eligibility", "notice_qa"])
        self.assertEqual(rule_plan("맞는 공고 추천해줘", {}, None, term)[0], ["eligibility"])
        self.assertIsNone(rule_plan("안녕", {}, None, term)[0])
        self.assertEqual(rule_plan("안녕", {"region": "REGION:11"}, None, term)[0], ["eligibility"])


@unittest.skipUnless(HAS_DEPS, "openai·langgraph·fastapi·httpx·pyyaml·numpy가 필요하다")
class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        from agent.agents import build_definition, build_notice_qa
        from agent.graph import build_graph
        from agent.orchestrator import build_orchestrator, make_runners
        from tests.test_agent import fake_judge, notice, provider, router

        r = router(provider())
        elig = build_graph(fake_judge([{**notice(), "notice_id": "N1"}]), r, None)
        qa = build_notice_qa(retriever(), r, META.get, lambda: {"N1", "N2"})
        terms = {"중소기업": {"term": "중소기업", "law": "중소기업기본법", "article": "제2조", "text": "중소기업은 …",
                           "law_url": None, "needs_review": False, "review_status": "확인", "delegated_basis": [], "concept": None}}
        dg = build_definition(r, lambda: terms)
        runners = make_runners(elig, qa, dg)
        self.elig_reqs = []
        inner = runners["eligibility"]

        def capture(req):
            self.elig_reqs.append(req)
            return inner(req)

        runners["eligibility"] = capture
        self.g = build_orchestrator(runners, r, is_term=lambda q: "중소기업" in q)

    def run_req(self, **req):
        from agent.orchestrator import run_orchestrated

        return collect(run_orchestrated(self.g, req))

    def test_chain_eligibility_then_qa_scoped_to_candidates(self):
        ev = self.run_req(question="창업 3년차인데 신청할 수 있는 공고와 신청 방법 알려줘", profile={"business_age_years": 3})
        kinds = [e["type"] for e in ev]
        self.assertEqual(ev[0]["plan"], ["eligibility", "notice_qa"])
        self.assertEqual([e["name"] for e in ev if e["type"] == "agent" and e["status"] == "start"], ["eligibility", "notice_qa"])
        self.assertLess(kinds.index("verdict"), kinds.index("retrieval"))
        ret = next(e for e in ev if e["type"] == "retrieval")
        self.assertEqual({c["notice_id"] for c in ret["chunks"]}, {"N1"})  # 판정 후보로 범위를 좁힘
        cit = next(e for e in ev if e["type"] == "citation")
        self.assertTrue(cit["chunk_ids"])
        self.assertEqual(kinds.count("done"), 1)
        self.assertEqual(ev[-1]["agents"], ["eligibility", "notice_qa"])
        self.assertEqual(ev[-1]["outcome"], "answered")

    def test_eligibility_explanation_defers_content_question(self):
        from agent.graph import DEFER_QUESTION, answer_messages

        self.run_req(question="창업 3년차인데 신청할 수 있는 공고와 신청 방법 알려줘", profile={"business_age_years": 3})
        self.assertTrue(self.elig_reqs[-1]["defer_content"])  # 뒤에 공고 질의가 있으면 판정 설명은 판정만
        self.run_req(question="맞는 공고 추천해줘", profile={"business_age_years": 3})
        self.assertFalse(self.elig_reqs[-1]["defer_content"])
        q = "창업 3년차 신청 방법 알려줘"
        deferred = answer_messages("{}", q, True)
        self.assertNotIn(q, deferred[1]["content"])  # 내용 질문을 모델에 보이지 않는다
        self.assertIn(DEFER_QUESTION, deferred[1]["content"])
        self.assertIn(q, answer_messages("{}", q, False)[1]["content"])

    def test_definition_and_replan_when_term_unknown(self):
        ev = self.run_req(question="중소기업이 뭐야?")
        self.assertEqual(ev[0]["plan"], ["definition"])
        self.assertTrue(any(e["type"] == "definition" and e["term"] == "중소기업" for e in ev))
        ev = self.run_req(question="벤처기업 뜻이 뭐야?", agent="definition")
        routes = [e for e in ev if e["type"] == "route"]
        self.assertEqual(routes[-1]["method"], "replan")
        self.assertEqual(ev[-1]["agents"], ["definition", "notice_qa"])

    def test_guard_blocks_before_planning(self):
        ev = self.run_req(question="제 사업자번호는 123-45-67890 입니다")
        self.assertNotIn("route", [e["type"] for e in ev])
        self.assertEqual(ev[-1]["outcome"], "refused")
        self.assertEqual(ev[-1]["reason_code"], "PII_BLOCKED")

    def test_qa_abstains_without_evidence(self):
        ev = self.run_req(question="zzzz qqqq xxxx?", agent="notice_qa")
        self.assertEqual(ev[-1]["reason_code"], "NO_EVIDENCE")
        self.assertEqual(ev[-1]["outcome"], "held")


@unittest.skipUnless(HAS_DEPS, "openai·langgraph·fastapi·httpx·pyyaml·numpy가 필요하다")
class TestUnparsedRequirements(unittest.TestCase):
    """REQ_UNPARSED 공고: 판정은 그대로(NEEDS_CHECK) 두고, 읽지 못한 자격 요건 원문을 보이고 설명에서 인용하게 한다."""

    def test_excerpts_pick_eligibility_sections_in_order(self):
        from api.services.eligibility import MAX_UNPARSED, unparsed_excerpts

        chunks = [{"chunk_id": "N#apply_method:0", "section": "apply_method", "text": "온라인 접수합니다. 사업계획서를 제출합니다."},
                  {"chunk_id": "N#att_exclusion@f0-1:0", "section": "att_exclusion@f0-1", "text": "국세 체납 기업은 신청할 수 없습니다(제외 대상)."},
                  {"chunk_id": "N#eligibility_api:0", "section": "eligibility_api", "text": "서울 소재 창업 3년 이내 중소기업 ※ 자세한 지원대상 공고문 참조"},
                  {"chunk_id": "N#att_eligibility@f0-2:0", "section": "att_eligibility@f0-2", "text": "짧음"}]
        out = unparsed_excerpts(chunks)
        self.assertEqual([u["chunk_id"] for u in out], ["N#eligibility_api:0", "N#att_exclusion@f0-1:0"])  # 신청 방법·너무 짧은 글 제외
        self.assertTrue(all(u["label"] for u in out))
        many = [{"chunk_id": f"N#att_eligibility@f0-{i}:0", "section": f"att_eligibility@f0-{i}", "text": f"참여 대상 {i}번 문단입니다. " * 5}
                for i in range(6)]
        self.assertEqual(len(unparsed_excerpts(many)), MAX_UNPARSED)

    def test_explanation_context_and_citation_allow_unparsed_text(self):
        from agent.graph import _context, cite_ids
        from agent.guards import sentence_guard

        r = {"notice_id": "N1", "title": "t", "verdict": "NEEDS_CHECK", "reasons": ["REQ_UNPARSED"], "conditions": [],
             "unparsed_text": [{"chunk_id": "N1#eligibility_api:0", "section": "eligibility_api", "label": "신청 자격", "text": "서울 소재 기업"}]}
        ctx = _context([r])["notices"][0]
        self.assertEqual(ctx["reasons"], ["REQ_UNPARSED"])
        self.assertEqual(ctx["unparsed_requirements"][0]["id"], "N1#eligibility_api:0")
        known = cite_ids([r])
        self.assertIsNone(sentence_guard("소재지 요건을 원문에서 확인해 주세요 [N1#eligibility_api:0]", known, False))
        self.assertEqual(sentence_guard("업력 요건을 확인해 주세요 [N1#att_eligibility@f0-9:0]", known, False), "citation")

    def test_verdict_event_carries_unparsed_text(self):
        from agent.graph import build_graph, run_events
        from tests.test_agent import fake_judge, notice

        n = {**notice(), "notice_id": "N1", "reasons": ["REQ_UNPARSED"],
             "unparsed_text": [{"chunk_id": "N1#eligibility_api:0", "section": "eligibility_api", "label": "신청 자격", "text": "서울 소재 기업"}]}
        ev = collect(run_events(build_graph(fake_judge([n]), None, None), {"question": "신청할 수 있는 공고", "profile": {"business_age_years": 1}}))
        v = next(e for e in ev if e["type"] == "verdict")
        self.assertEqual(v["unparsed_text"][0]["chunk_id"], "N1#eligibility_api:0")
        self.assertEqual(v["verdict"], n["verdict"])  # 판정은 바꾸지 않는다


@unittest.skipUnless(HAS_DEPS, "openai·langgraph·fastapi·httpx·pyyaml·numpy가 필요하다")
class TestGateway(unittest.TestCase):
    def test_translate_and_unsupported_param(self):
        from deploy.llm_gateway import app as gw

        out = gw.translate_chat({"model": gw.SERVED_MODEL, "max_tokens": 100, "temperature": 0.2, "guided_json": {}, "messages": []})
        self.assertEqual(out["model"], gw.UPSTREAM_MODEL)
        self.assertEqual(out["max_completion_tokens"], 100 + gw.REASONING_BUDGET)
        self.assertNotIn("max_tokens", out)
        self.assertNotIn("guided_json", out)
        err = {"error": {"message": "Unsupported value: 'temperature' does not support 0.2", "param": "temperature"}}
        self.assertEqual(gw.unsupported_param(err), "temperature")
        self.assertIsNone(gw.unsupported_param({"error": {"message": "bad messages"}}))

    def test_rejects_unknown_model_and_missing_key(self):
        from fastapi.testclient import TestClient

        from deploy.llm_gateway import app as gw

        c = TestClient(gw.app)
        self.assertEqual(c.post("/v1/chat/completions", json={"model": "nope", "messages": []}).status_code, 404)
        saved = {k: os.environ.pop(k, None) for k in ("UPSTREAM_API_KEY", "OPENAI_API_KEY", "OPEN_API")}
        try:
            self.assertEqual(c.post("/v1/chat/completions", json={"model": gw.SERVED_MODEL, "messages": []}).status_code, 503)
        finally:
            os.environ.update({k: v for k, v in saved.items() if v is not None})


if __name__ == "__main__":
    unittest.main()
