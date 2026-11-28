"""자격 판정 에이전트(LangGraph StateGraph). 기초 설계서 §7.1의 고정 순서를 그대로 따른다.

  input_guard → classify_query → search_candidates(정형 조건·검색 → 계층 확장 → 규칙 평가)
              → trace_path(Neo4j 경로) → fetch_definition(Neo4j 정의→법령) → explain_gap
              → verify_evidence → answer(모델, 문장 단위 출력 가드) → finalize
  차단·후보 없음은 reply_template, 정보 부족은 되묻기(ask) 뒤 종료.

- 판정은 규칙 평가기(judge 함수)가 한다. 모델은 answer에서 설명만 쓰고, 판정을 바꾸지 못한다.
- 이벤트(verdict·requirement·path·definition·token·banner·ask·usage·done)는 노드 안에서 get_stream_writer()로 내보낸다.
  판정·요건 이벤트가 설명 토큰보다 먼저 나가므로 모델이 느리거나 죽어도 판정은 화면에 뜬다(§8 스트리밍).
- 사용자 조건 값은 상태에만 두고 로그·체크포인터에 남기지 않는다(체크포인터는 쓰지 않는다, NFR-N03).
- 아직 없는 것: what-if(P1), 질문 순서 최적화(P1), 운영자 권한(ROLE_DENIED), 후보 검색의 벡터·RRF(지금은 BM25).
"""
from __future__ import annotations

import asyncio
import inspect
import json
import operator
import re
from collections.abc import AsyncIterator, Callable
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from . import templates
from .guards import input_guard, sentence_guard, split_sentences
from .llm import AllProvidersFailed, LLMError, LLMRouter

PROMPT_VERSION = "answer-v0.1"
RECURSION_LIMIT = 20          # 노드 수(8)보다 넉넉히, 그래도 명시한다(GraphRecursionError 방지)
MAX_ASK = 2                   # 되묻기 최대 2회
MAX_NOTICES_IN_PROMPT = 3
STALE_DAYS = 7                # 수집 지연 경고 기준(제안, 팀 결정 전)
PROFILE_FIELDS = {"region": "사업장 소재지(시군구)", "business_age_years": "업력", "pre_founder": "예비창업자 여부",
                  "founder_age": "대표자 만 나이", "applicant_type": "신청자 유형"}

# judge(profile, question, top, notice_id, include_closed) -> {"evaluated", "candidates", "counts", "results": [...]}
Judge = Callable[..., Any]


class AgentState(TypedDict, total=False):
    question: str
    profile: dict                      # ApplicantProfile 값. None = 모름
    notice_id: str | None
    top: int
    include_closed: bool
    ask_count: int
    intent: str
    reason_code: str | None
    outcome: str
    evaluated: int
    results: list[dict]
    gaps: list[dict]
    definitions: list[dict]
    evidence_defs: list[dict] | None   # trace_path가 근거 카드(evidence)로 미리 받은 정의 행. None이면 fetch_definition이 따로 묻는다
    banners: list[str]
    provider: str | None
    fallback_depth: int | None
    tools_used: Annotated[list[str], operator.add]
    failures: dict


SYSTEM_PROMPT = """너는 정부지원사업 공고의 자격 판정 결과를 설명하는 도우미다.
규칙:
1. 판정은 이미 규칙 평가기가 내렸다. <context>의 verdict를 바꾸거나 새로 판단하지 않는다.
2. <context>에 있는 조건만 설명한다. 조건을 말할 때는 해당 조건 id를 [조건id] 형태로 붙인다. 없는 id를 만들지 않는다.
3. "선정", "받을 수 있습니다", "확실히" 같은 확정·수혜 표현을 쓰지 않는다. 최종 판단은 주관 기관이 한다고 안내한다.
4. 확인이 필요한 조건(UNKNOWN)은 무엇을 확인하면 되는지 알려 준다. 모르는 것을 추측하지 않는다.
5. 한국어로, 공고당 2~3문장으로 짧게 쓴다.
6. 질문 중 신청 방법·제출 서류·지원 내용처럼 공고 내용을 묻는 부분은 다음 단계가 공고 원문으로 답하므로 다루지 않는다."""


def _emit(kind: str, **data) -> None:
    get_stream_writer()({"type": kind, **data})


# ---------- 조건 추출(규칙 먼저, §6.4) ----------
_AGE = re.compile(r"만\s?(\d{1,3})\s?세|(\d{1,3})\s?살")
_BIZ_AGE = re.compile(r"업력\s?(\d+(?:\.\d+)?)\s?년|창업\s?(\d+(?:\.\d+)?)\s?년\s?(?:차|째|됐|되었)")
_PRE = re.compile(r"예비\s?창업")
_DEFINE = re.compile(r"(뜻|정의|의미)(가|는|이)?\s*(뭐|무엇)|(이|가)?란\s*(무엇|뭐)")
_GAP = re.compile(r"왜|부족|안\s?되|안\s?돼|빠진|못\s?하")


def profile_from_text(text: str) -> dict:
    """질문 문장에서 범주형 값만 뽑는다. 지역은 개념 코드 사전이 필요해 폼 입력으로만 받는다(지금은 뽑지 않음)."""
    out: dict = {}
    if m := _AGE.search(text):
        out["founder_age"] = int(m.group(1) or m.group(2))
    if m := _BIZ_AGE.search(text):
        out["business_age_years"] = float(m.group(1) or m.group(2))
    if _PRE.search(text):
        out["pre_founder"] = True
    return out


def classify_intent(question: str, notice_id: str | None) -> str:
    if notice_id:
        return "JUDGE_NOTICE"
    if _DEFINE.search(question):
        return "DEFINITION"
    if _GAP.search(question):
        return "EXPLAIN_GAP"
    return "FIND_CANDIDATES"


def _context(results: list[dict], definitions: list[dict] | None = None) -> dict:
    """모델에 넘기는 구조화 컨텍스트. 사용자 조건 원값은 넣지 않고 조건별 평가 결과와 정의·법령 위치만 넣는다."""
    notices = []
    defs_by = {}
    for d in definitions or []:
        defs_by.setdefault(d["notice_id"], []).append({"term": d["term"], "law": d.get("law_name"), "article_no": d.get("article_no")})
    for r in results[:MAX_NOTICES_IN_PROMPT]:
        notices.append({"notice_id": r["notice_id"], "title": r.get("title"), "verdict": r["verdict"],
                        "conditions": [{"cond_id": c["cond_id"], "attribute": c["attribute"], "status": c["status"],
                                        "reason": c.get("reason")} for c in r.get("conditions", [])],
                        "definitions": defs_by.get(r["notice_id"], [])})
    return {"notices": notices}


def _as_of(results: list[dict]) -> str | None:
    ts = [r["fetched_at"] for r in results if r.get("fetched_at")]
    return min(ts) if ts else None


def build_graph(judge: Judge, router: LLMRouter | None, graph: Any = None,
                now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
    """judge: 규칙 판정 함수. router: 모델 라우터(None이면 설명 없음). graph: Neo4j 저장소(condition_paths·
    definitions_for_notices를 가진 객체, None이면 경로는 평가기 결과로·정의는 생략). graph에 evidence가 있으면
    경로와 정의를 질의 한 번으로 받는다(Aura 왕복 2번 → 1번)."""
    async def call_judge(**kw) -> dict:
        if inspect.iscoroutinefunction(judge):
            return await judge(**kw)
        return await asyncio.to_thread(judge, **kw)

    # ---------- 노드 ----------
    async def n_input_guard(s: AgentState) -> dict:
        code = input_guard(s.get("question", ""))
        return {"reason_code": code, "outcome": "refused" if code else "answered", "tools_used": ["input_guard"]}

    async def n_classify(s: AgentState) -> dict:
        intent = classify_intent(s.get("question", ""), s.get("notice_id"))
        form = {k: v for k, v in (s.get("profile") or {}).items() if v is not None}
        profile = {**{k: None for k in PROFILE_FIELDS}, **profile_from_text(s.get("question", "")), **form}  # 폼 값이 우선
        update: dict = {"intent": intent, "profile": profile, "tools_used": ["classify_query"]}
        if all(v is None for v in profile.values()) and not s.get("notice_id") and s.get("ask_count", 0) < MAX_ASK:
            fields = [PROFILE_FIELDS[k] for k in ("region", "business_age_years", "founder_age")]
            _emit("ask", fields=fields, ask_count=s.get("ask_count", 0) + 1,
                  text=templates.render("INSUFFICIENT_PROFILE", fields=", ".join(fields)))
            update.update(reason_code="INSUFFICIENT_PROFILE", outcome="held")
        return update

    async def n_search(s: AgentState) -> dict:
        try:
            res = await call_judge(profile=s["profile"], question=s.get("question", ""), top=s.get("top", 5),
                                   notice_id=s.get("notice_id"), include_closed=s.get("include_closed", False))
        except Exception as e:  # 그래프·데이터 장애면 판정도 불가(§7.3 #12 ③)
            _emit("banner", code="SERVICE_DEGRADED", text=templates.render("FAILED"))
            return {"reason_code": "SERVICE_DEGRADED", "outcome": "failed", "results": [],
                    "failures": {**s.get("failures", {}), "search_candidates": type(e).__name__},
                    "tools_used": ["search_candidates"]}
        results = res.get("results", [])
        for r in results:
            _emit("verdict", notice_id=r["notice_id"], title=r.get("title"), verdict=r["verdict"], reasons=r.get("reasons", []),
                  unknown=[c["cond_id"] for c in r.get("conditions", []) if c["status"] == "UNKNOWN"],
                  source=r.get("source"), detail_url=r.get("detail_url"), fetched_at=r.get("fetched_at"),
                  deadline=r.get("deadline"))
            for c in r.get("conditions", []):
                _emit("requirement", notice_id=r["notice_id"], **{k: c.get(k) for k in
                      ("cond_id", "attribute", "status", "strength", "reason", "evidence", "flags")})
        update: dict = {"results": results, "evaluated": res.get("evaluated", 0),
                        "tools_used": ["search_candidates", "expand_concepts", "evaluate_requirements"]}
        if not results:
            update.update(reason_code="NO_MATCH", outcome="held")
        return update

    async def n_trace_path(s: AgentState) -> dict:
        """판정 근거 경로: 사용자 지역 → (WITHIN·MEMBER_OF, ≤3 hop) → 조건 지역. Neo4j가 있으면 적재 그래프에서 읽는다."""
        results, region = s.get("results", []), (s.get("profile") or {}).get("region")
        region_conds = [c for r in results for c in r.get("conditions", []) if c["attribute"] == "region"]
        owner = {c["cond_id"]: r["notice_id"] for r in results for c in r.get("conditions", [])}
        failures = dict(s.get("failures", {}))
        rows, evidence_defs = None, None
        if graph is not None and hasattr(graph, "evidence") and results:
            # 근거 카드 한 번으로 경로와 정의를 같이 받는다. 정의 행은 fetch_definition이 그대로 쓴다
            try:
                cards = await asyncio.to_thread(graph.evidence, [r["notice_id"] for r in results], region)
                wanted = {c["cond_id"] for c in region_conds}
                rows = [c for c in cards if c["cond_id"] in wanted] if region else None
                evidence_defs = [{"notice_id": c["notice_id"], "cond_id": c["cond_id"], "concept": c["concept"], **b}
                                 for c in cards for b in c.get("basis") or []]
            except Exception as e:
                failures["trace_path"] = type(e).__name__
                _emit("banner", code="GRAPH_UNAVAILABLE", text="그래프 DB에 닿지 않아 경로는 내장 지역 사전으로 표시합니다.")
        elif graph is not None and region and region_conds:
            try:
                rows = await asyncio.to_thread(graph.condition_paths, region, [c["cond_id"] for c in region_conds])
            except Exception as e:
                failures["trace_path"] = type(e).__name__
                _emit("banner", code="GRAPH_UNAVAILABLE", text="그래프 DB에 닿지 않아 경로는 내장 지역 사전으로 표시합니다.")
        if rows is not None:
            for p in rows:
                _emit("path", notice_id=owner.get(p["cond_id"]), cond_id=p["cond_id"], source="neo4j", target=p["target"],
                      reached=p["nodes"] is not None, nodes=p["nodes"] or [], rels=p["rels"] or [])
        else:  # 그래프 없음: 평가기가 계산한 경로(이름 목록)를 그대로 쓴다
            for c in region_conds:
                if c.get("path"):
                    _emit("path", notice_id=owner.get(c["cond_id"]), cond_id=c["cond_id"], source="evaluator", reached=True,
                          nodes=[{"id": None, "name": n} for n in c["path"]], rels=[])
        return {"failures": failures, "evidence_defs": evidence_defs, "tools_used": ["trace_path"]}

    async def n_fetch_definition(s: AgentState) -> dict:
        """조건 개념의 정의 → 법령 조문(P1). 모델이 법령을 외워 답하지 않게 원문 위치만 준다."""
        if graph is None or not s.get("results"):
            return {"definitions": [], "tools_used": ["fetch_definition"]}
        rows = s.get("evidence_defs")
        if rows is None:  # 근거 카드를 못 받았으면(메서드 없음·장애) 예전처럼 따로 묻는다
            try:
                rows = await asyncio.to_thread(graph.definitions_for_notices, [r["notice_id"] for r in s["results"]])
            except Exception as e:
                return {"definitions": [], "failures": {**s.get("failures", {}), "fetch_definition": type(e).__name__},
                        "tools_used": ["fetch_definition"]}
        seen, defs = set(), []
        for d in rows:
            key = (d["notice_id"], d["def_id"], d.get("article_id"))  # 한 정의가 조문·별표를 함께 인용하면 둘 다 보인다
            if key in seen:
                continue
            seen.add(key)
            defs.append(d)
            _emit("definition", notice_id=d["notice_id"], cond_id=d["cond_id"], term=d["term"], concept=d["concept"],
                  law=d.get("law_name"), article_no=d.get("article_no"), article_title=d.get("article_title"),
                  law_url=d.get("law_url"), needs_review=d.get("needs_review"),
                  broken=d.get("law_name") is None)  # 정의는 있는데 법령이 끊김 → 화면에 '법령 원문 확인 필요'
        return {"definitions": defs, "tools_used": ["fetch_definition"]}

    async def n_explain_gap(s: AgentState) -> dict:
        gaps = [{"notice_id": r["notice_id"], "verdict": r["verdict"],
                 "unsatisfied": [c["cond_id"] for c in r.get("conditions", []) if c["status"] == "UNSATISFIED"],
                 "unknown": [c["cond_id"] for c in r.get("conditions", []) if c["status"] == "UNKNOWN"]}
                for r in s.get("results", []) if r["verdict"] != "ELIGIBLE"]
        return {"gaps": gaps, "tools_used": ["explain_gap"]}

    async def n_verify(s: AgentState) -> dict:
        banners = list(s.get("banners", []))
        missing = [r["notice_id"] for r in s.get("results", []) if not (r.get("detail_url") and r.get("fetched_at"))]
        if missing:
            _emit("banner", code="EVIDENCE_MISSING", notice_ids=missing, text="일부 공고는 출처 주소나 수집 시각이 없습니다. 원문을 확인해 주세요.")
            banners.append("EVIDENCE_MISSING")
        as_of = _as_of(s.get("results", []))
        if as_of:
            try:
                age = now() - datetime.fromisoformat(as_of.replace("Z", "+00:00")).astimezone(timezone.utc)
                if age.days >= STALE_DAYS:
                    _emit("banner", code="STALE_DATA", text=templates.render("STALE_DATA", as_of=as_of[:16]))
                    banners.append("STALE_DATA")
            except ValueError:
                pass
        return {"banners": banners, "tools_used": ["verify_evidence"]}

    async def n_answer(s: AgentState) -> dict:
        results = s.get("results", [])
        if router is None:
            return _degraded(s, None, "no_router")
        known = {c["cond_id"] for r in results for c in r.get("conditions", [])}
        any_eligible = any(r["verdict"] == "ELIGIBLE" for r in results)
        ctx = json.dumps(_context(results, s.get("definitions", [])), ensure_ascii=False)
        messages = [{"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"<context>{ctx}</context>\n질문: {s.get('question', '')}"}]  # 가변 값은 뒤에
        try:
            h = await router.open_stream("answer", messages)
        except (AllProvidersFailed, LLMError) as e:
            return _degraded(s, None, type(e).__name__)
        if h.degraded:
            return _degraded(s, h, "template")

        buf, shown, blocked = "", 0, None
        try:
            async for piece in h.tokens():
                buf += piece
                done, buf = split_sentences(buf)
                for sent in done:
                    if (blocked := sentence_guard(sent, known, any_eligible)):
                        break
                    _emit("token", text=sent + " ")
                    shown += 1
                if blocked:
                    break
            if not blocked and buf.strip():
                if (blocked := sentence_guard(buf, known, any_eligible)) is None:
                    _emit("token", text=buf)
                    shown += 1
        except LLMError as e:
            out = _degraded(s, h, type(e).__name__)
            out["banners"] = out["banners"] + ["STREAM_CUT"]
            return out
        if h.usage:
            _emit("usage", **h.usage)
        update: dict = {"provider": h.provider, "fallback_depth": h.fallback_depth, "tools_used": ["answer"]}
        if blocked:
            # 위반 문장과 그 뒤는 내보내지 않고 안전 템플릿으로 마무리한다. 재생성(1회)은 다음 단계에서 붙인다
            _emit("banner", code="OUTPUT_BLOCKED", text="설명 일부를 안전 문구로 바꿨습니다.")
            _emit("token", text=templates.render("OUTPUT_BLOCKED"), source="template")
            update.update(reason_code="OUTPUT_BLOCKED", failures={**s.get("failures", {}), "output_guard": blocked})
        return update

    def _degraded(s: AgentState, h, why: str) -> dict:
        _emit("banner", code="SERVICE_DEGRADED", text=templates.render("SERVICE_DEGRADED"))
        return {"reason_code": "SERVICE_DEGRADED", "outcome": "degraded", "banners": [*s.get("banners", []), "SERVICE_DEGRADED"],
                "provider": h.provider if h else None, "fallback_depth": h.fallback_depth if h else None,
                "failures": {**s.get("failures", {}), "answer": why}, "tools_used": ["answer"]}

    async def n_reply_template(s: AgentState) -> dict:
        code = s.get("reason_code") or "FAILED"
        text_code = "NO_MATCH_NOTICE" if code == "NO_MATCH" and s.get("notice_id") else code
        _emit("token", text=templates.render(text_code, evaluated=s.get("evaluated", 0), notice_id=s.get("notice_id"),
                                             as_of=_as_of(s.get("results", [])) or "-"), source="template")
        return {"outcome": templates.OUTCOME.get(code, "failed"), "tools_used": ["reply_template"]}

    async def n_finalize(s: AgentState) -> dict:
        outcome = s.get("outcome") or ("answered" if s.get("results") else "held")
        _emit("done", outcome=outcome, reason_code=s.get("reason_code"), tools_used=s.get("tools_used", []),
              provider=s.get("provider"), fallback_depth=s.get("fallback_depth"), prompt_version=PROMPT_VERSION,
              disclaimer=templates.DISCLAIMER)
        return {"outcome": outcome}

    # ---------- 연결 ----------
    g = StateGraph(AgentState)
    for name, fn in [("input_guard", n_input_guard), ("classify_query", n_classify), ("search_candidates", n_search),
                     ("trace_path", n_trace_path), ("fetch_definition", n_fetch_definition),
                     ("explain_gap", n_explain_gap), ("verify_evidence", n_verify), ("answer", n_answer),
                     ("reply_template", n_reply_template), ("finalize", n_finalize)]:
        g.add_node(name, fn)
    g.add_edge(START, "input_guard")
    g.add_conditional_edges("input_guard", lambda s: "reply_template" if s.get("reason_code") else "classify_query")
    g.add_conditional_edges("classify_query", lambda s: "finalize" if s.get("reason_code") == "INSUFFICIENT_PROFILE" else "search_candidates")
    g.add_conditional_edges("search_candidates", lambda s: {"NO_MATCH": "reply_template", "SERVICE_DEGRADED": "finalize"}
                            .get(s.get("reason_code") or "", "trace_path"))
    g.add_edge("trace_path", "fetch_definition")
    g.add_edge("fetch_definition", "explain_gap")
    g.add_edge("explain_gap", "verify_evidence")
    g.add_edge("verify_evidence", "answer")
    g.add_edge("answer", "finalize")
    g.add_edge("reply_template", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


async def run_events(graph, request: dict) -> AsyncIterator[dict]:
    """그래프를 돌리며 이벤트를 차례로 낸다. SSE 라우터와 평가 스크립트가 같이 쓴다."""
    state: AgentState = {"question": request.get("question", ""), "profile": request.get("profile") or {},
                         "notice_id": request.get("notice_id"), "top": request.get("top", 5),
                         "include_closed": request.get("include_closed", False), "ask_count": request.get("ask_count", 0),
                         "tools_used": [], "failures": {}, "banners": []}
    async for ev in graph.astream(state, stream_mode="custom", config={"recursion_limit": RECURSION_LIMIT}):
        yield ev
