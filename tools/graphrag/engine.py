"""그래프 RAG 최소 구현: 구조 조건 평가 + 지역 계층 확장 + 청크 검색 + 근거 출력.

흐름: 프로필 -> (1) 모집 중 공고의 구조화 조건 평가(규칙) -> (2) 불가 공고 제외 -> (3) 질문으로 BM25 검색 -> (4) 판정·조건 표·근거 청크 출력.
LLM은 쓰지 않는다. 설명 생성은 이 출력(근거 문장·경로)을 입력으로 받는 별도 단계다.
"""
from __future__ import annotations

from collections import Counter
from datetime import date

from . import cleaned, gold_bridge
from .data import load_all
from .evaluator import DEFAULT_OPTIONS, NOT_ELIGIBLE, Profile, RuleOptions, evaluate_notice
from .search import BM25

TODAY = "2026-11-24"


class Engine:
    def __init__(self, use_cleaned: bool | None = None):
        # 정리 층(data/cleaned)이 있으면 그것을 쓰고, 없으면 원본 파서 결과를 직접 읽는다
        use = cleaned.available() if use_cleaned is None else use_cleaned
        d = cleaned.load_cleaned() if use else load_all()
        self.input_layer = "cleaned" if use else "parsed"

        self.rg, self.notices, self.chunks, self.skipped = d["rg"], d["notices"], d["chunks"], d["skipped"]
        # 사람이 검수한 본문 요건(2-4 정답셋)을 붙인다. 검수 반영 0건이면 아무것도 바뀌지 않는다
        # 서비스 검수 큐(B-3 ②)에서 VERIFIED로 반영된 공고도 붙인다. 공고 전체 확인이면 text_requirements=reviewed가 된다
        self.gold_notices = gold_bridge.attach(self.notices, gold_bridge.load_all())
        self.by_id = {n["notice_id"]: n for n in self.notices}
        self.bm25 = BM25(self.chunks)

    def is_open(self, n: dict) -> bool:
        if not n["is_open"]:
            return False
        return not (n.get("deadline") and n["apply_status_kind"] == "DATE_RANGE" and n["deadline"] < TODAY)

    def evaluate_all(self, prof: Profile, include_closed: bool = False, opts: RuleOptions = DEFAULT_OPTIONS) -> list[dict]:
        out = []
        for n in self.notices:
            if not include_closed and not self.is_open(n):
                continue
            out.append(evaluate_notice(n, prof, self.rg, opts, today=date.fromisoformat(TODAY)))
        return out

    def query(self, prof: Profile, question: str = "", top: int = 10, include_closed: bool = False, source: str | None = None,
              search=None) -> dict:
        """search: (질문, 허용 공고 id 집합, top) -> [(점수, 청크)]. 비우면 BM25. 하이브리드(BM25+벡터 RRF)는 agent.rag가 준다."""
        ev = self.evaluate_all(prof, include_closed)
        if source:
            ev = [e for e in ev if self.by_id[e["notice_id"]]["source"] == source]
        counts = Counter(e["verdict"] for e in ev)
        cand = {e["notice_id"]: e for e in ev if e["verdict"] != NOT_ELIGIBLE}
        ranked: list[dict] = []
        if question.strip():
            hits = (search or self.bm25.search)(question, set(cand), top=top * 20)
            best: dict[str, tuple[float, list]] = {}
            for s, c in hits:
                b = best.setdefault(c["notice_id"], (s, []))
                if len(b[1]) < 3:
                    b[1].append(c)
            # 구조 조건을 통과(PASS)한 공고를 먼저, 그다음 UNKNOWN. 같은 그룹 안에서는 검색 점수 순
            order = {"PASS": 0, "UNKNOWN": 1}
            ordered = sorted(best.items(), key=lambda x: (order.get(cand[x[0]]["structured"], 2), -x[1][0]))[:top]
            for nid, (s, cs) in ordered:
                ranked.append({"score": round(s, 2), "chunks": cs, **cand[nid]})
        else:
            for e in list(cand.values())[:top]:
                ranked.append({"score": None, "chunks": [], **e})
        return {"counts": dict(counts), "evaluated": len(ev), "candidates": len(cand), "results": ranked}

    def show(self, res: dict) -> str:
        lines = [f"평가 {res['evaluated']}건 → " + ", ".join(f"{k} {v}" for k, v in res["counts"].items()) + f" | 후보 {res['candidates']}건"]
        for i, r in enumerate(res["results"], 1):
            n = self.by_id[r["notice_id"]]
            lines.append(f"\n{i}. [{n['source']}] {n['title'][:60]}  ({r['verdict']}, 구조조건 {r['structured']}, 사유 {','.join(r['reasons']) or '-'})")
            lines.append(f"   {n['detail_url']}  | 수집 {n['fetched_at'][:10]}  | 마감 {n.get('deadline') or n['apply_status_kind']}")
            for c in r["conditions"]:
                p = " → ".join(c.path) if c.path else ""
                fl = f" ⚠{','.join(c.flags)}" if c.flags else ""
                lines.append(f"   - {c.attribute}({c.strength}) {c.status}: {c.reason} {p}{fl}  [{c.evidence}]")
            for c in r["chunks"][:1]:
                lines.append(f"   근거 청크[{c['section']}/{c['origin']}]: {c['text'][:140].replace(chr(10), ' ')}…")
        return "\n".join(lines)
