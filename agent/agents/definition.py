"""용어 정의 에이전트. "중소기업이 뭐야?", "소상공인 기준은?" 같은 질문에 **법령 원문 정의**로 답한다.

  lookup(용어 사전에서 질문 속 용어 찾기) ─ 없음 → finalize(held, NO_DEFINITION: 오케스트레이터가 공고 질의로 넘긴다)
                                        └ 있음 → explain(모델, 정의 원문만 근거, 출력 가드) → finalize

- 정의 원문은 수집 법령(data/지원사업_법령)에서 잘라 온 조문 그대로다(tools/graphrag/concepts_laws.py). 모델이 법령을 외워 답하지 않는다.
- 검수 전 정의(needs_review)는 화면에 '검수 전'을 표시하게 이벤트에 싣는다. 법적 자문은 하지 않는다.
"""
from __future__ import annotations

import json
import operator
import re
from collections.abc import Callable
from typing import Annotated, Any, TypedDict

from langgraph.config import get_stream_writer
from langgraph.graph import END, START, StateGraph

from .. import templates
from ..guards import sentence_guard, split_sentences
from ..llm import AllProvidersFailed, LLMError, LLMRouter

PROMPT_VERSION = "definition-v0.1"
DEF_SYSTEM = """너는 정부지원사업에 나오는 법령 용어를 쉽게 풀어 주는 도우미다.
규칙:
1. <definition>의 법령 원문만 근거로 설명한다. 원문에 없는 기준·숫자를 만들지 않는다.
2. 설명 문장 끝에 [def#용어] 형태로 근거를 붙인다.
3. 법적 자문이 아니라 원문 안내임을 밝히고, 특정 기업이 해당하는지는 판단하지 않는다. 확정 표현을 쓰지 않는다.
4. 위임 규정(시행령·별표)이 있으면 "세부 기준은 ○○에 있다"고만 안내한다.
5. 한국어로 3~5문장."""


class DefState(TypedDict, total=False):
    question: str
    term: str | None
    entry: dict | None
    outcome: str
    reason_code: str | None
    provider: str | None
    fallback_depth: int | None
    tools_used: Annotated[list[str], operator.add]
    failures: dict


def _emit(kind: str, **data) -> None:
    get_stream_writer()({"type": kind, **data})


def load_terms() -> dict[str, dict]:
    """용어 → {law, article, text, needs_review, review_status, delegated_basis, law_url, concept}. 로컬 파일에서 읽는다."""
    from tools.graphrag import concepts_laws as C

    terms = json.loads(C.TERMS.read_text(encoding="utf-8"))
    review = json.loads(C.REVIEW.read_text(encoding="utf-8"))
    raw = {**terms["law_definitions_verbatim"], **C.law_definitions()}
    laws, _, _, _ = C.laws()
    url = {n["name"]: n.get("source_url") for n in laws if n.get("label") == "ExternalLaw" and n.get("name")}
    nodes, _, by_label = C.concepts()
    out = {}
    for term, d in raw.items():
        r = review["definitions"].get(term) or {"status": "미검수"}
        out[term] = {"term": term, "law": d["law"], "article": d["article"], "text": d["text"], "law_url": url.get(d["law"]),
                     "needs_review": r["status"] != "확인", "review_status": r["status"],
                     "delegated_basis": r.get("delegated_basis") or [], "concept": by_label.get(term)}
    return out


def find_term(question: str, terms: dict[str, dict]) -> str | None:
    """질문에 들어 있는 가장 긴 용어. 공백은 무시한다."""
    q = re.sub(r"\s+", "", question)
    best = None
    for t in terms:
        if re.sub(r"\s+", "", t) in q and (best is None or len(t) > len(best)):
            best = t
    return best


def build_definition(router: LLMRouter | None, terms: Callable[[], dict[str, dict]]):
    async def n_lookup(s: DefState) -> dict:
        table = terms()
        term = find_term(s.get("question", ""), table)
        if term is None:
            return {"term": None, "entry": None, "outcome": "held", "reason_code": "NO_DEFINITION", "tools_used": ["lookup_definition"]}
        e = table[term]
        _emit("definition", agent="definition", notice_id=None, cond_id=None, term=term, concept=e.get("concept"), law=e["law"],
              article_no=e["article"], article_title=None, law_url=e.get("law_url"), needs_review=e["needs_review"],
              review_status=e["review_status"], delegated_basis=e["delegated_basis"], text=e["text"][:1500], broken=False)
        return {"term": term, "entry": e, "tools_used": ["lookup_definition"]}

    async def n_explain(s: DefState) -> dict:
        e = s["entry"]
        known = {f"def#{s['term']}"}
        if router is None:
            _emit("token", agent="definition", source="template",
                  text=f"「{e['law']}」 {e['article']}의 정의 원문을 위에 보여 드립니다. 해당 여부는 원문과 주관 기관에 확인해 주세요.")
            return {"outcome": "degraded", "reason_code": "SERVICE_DEGRADED", "tools_used": ["explain_definition"]}
        ctx = {"용어": s["term"], "법령": e["law"], "조문": e["article"], "원문": e["text"][:3000], "위임": e["delegated_basis"]}
        messages = [{"role": "system", "content": DEF_SYSTEM},
                    {"role": "user", "content": f"<definition>{json.dumps(ctx, ensure_ascii=False)}</definition>\n질문: {s.get('question', '')}"}]
        try:
            h = await router.open_stream("answer", messages)
        except (AllProvidersFailed, LLMError):
            h = None
        if h is None or h.degraded:
            _emit("banner", code="SERVICE_DEGRADED", text=templates.render("SERVICE_DEGRADED"))
            _emit("token", agent="definition", source="template", text=f"「{e['law']}」 {e['article']}의 정의 원문을 위에 보여 드립니다.")
            return {"outcome": "degraded", "reason_code": "SERVICE_DEGRADED", "tools_used": ["explain_definition"]}
        buf, blocked = "", None
        try:
            async for piece in h.tokens():
                buf += piece
                done, buf = split_sentences(buf)
                for sent in done:
                    if (blocked := sentence_guard(sent, known, False)):
                        break
                    _emit("token", agent="definition", text=sent + " ")
                if blocked:
                    break
            if not blocked and buf.strip() and (blocked := sentence_guard(buf, known, False)) is None:
                _emit("token", agent="definition", text=buf)
        except LLMError:
            blocked = "stream_cut"
        if h.usage:
            _emit("usage", **h.usage)
        update: dict = {"outcome": "answered", "provider": h.provider, "fallback_depth": h.fallback_depth, "tools_used": ["explain_definition"]}
        if blocked:
            _emit("banner", code="OUTPUT_BLOCKED", text="설명 일부를 안전 문구로 바꿨습니다.")
            _emit("token", agent="definition", source="template", text="정의 원문을 직접 확인해 주세요. 해당 여부는 주관 기관이 판단합니다.")
            update.update(reason_code="OUTPUT_BLOCKED", failures={**s.get("failures", {}), "output_guard": blocked})
        return update

    async def n_finalize(s: DefState) -> dict:
        outcome = s.get("outcome") or "held"
        _emit("done", outcome=outcome, reason_code=s.get("reason_code"), tools_used=s.get("tools_used", []),
              provider=s.get("provider"), fallback_depth=s.get("fallback_depth"), prompt_version=PROMPT_VERSION,
              disclaimer=templates.DISCLAIMER, term=s.get("term"))
        return {"outcome": outcome}

    g = StateGraph(DefState)
    g.add_node("lookup_definition", n_lookup)
    g.add_node("explain_definition", n_explain)
    g.add_node("finalize", n_finalize)
    g.add_edge(START, "lookup_definition")
    g.add_conditional_edges("lookup_definition", lambda s: "explain_definition" if s.get("entry") else "finalize")
    g.add_edge("explain_definition", "finalize")
    g.add_edge("finalize", END)
    return g.compile()


async def run_definition(graph, request: dict[str, Any]):
    state: DefState = {"question": request.get("question", ""), "tools_used": [], "failures": {}}
    async for ev in graph.astream(state, stream_mode="custom", config={"recursion_limit": 10}):
        yield ev
