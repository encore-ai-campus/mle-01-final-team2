"use client";
// 최소 화면: 조건 입력 → /api/chat(SSE) → 판정 카드·요건·경로·정의·설명. 상세 화면은 팀에서 이어서 만든다.
import { useEffect, useMemo, useRef, useState } from "react";

import { readSse, type AgentEvent } from "@/lib/sse";

type Region = { id: string; name: string; full_name: string | null; level: string | null };
type Notice = {
  id: string;
  verdict?: AgentEvent;
  requirements: AgentEvent[];
  paths: AgentEvent[];
  definitions: AgentEvent[];
};
type Subgraph = { nodes: { id: string; kind: string; label: string }[]; edges: { from: string; to: string; type: string }[] };

const VERDICT: Record<string, string> = { ELIGIBLE: "조건 충족(참고)", NOT_ELIGIBLE: "조건 미충족", NEEDS_CHECK: "확인 필요" };
const STATUS: Record<string, string> = { SATISFIED: "충족", UNSATISFIED: "미충족", UNKNOWN: "모름" };
const ATTR: Record<string, string> = {
  region: "지역",
  business_age: "업력",
  founder_age: "대표자 나이",
  pre_founder: "예비창업자",
  applicant_type: "신청자 유형",
};

const s = (v: unknown) => (v == null ? "" : String(v));

export default function Home() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [regionSource, setRegionSource] = useState("");
  const [form, setForm] = useState({ region: "", business_age_years: "", founder_age: "", pre_founder: "", notice_id: "" });
  const [question, setQuestion] = useState("서울에서 창업 2년 차인데 신청할 만한 지원사업 알려줘");
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [askCount, setAskCount] = useState(0);
  const [graphs, setGraphs] = useState<Record<string, Subgraph | string>>({});
  const abort = useRef<AbortController | null>(null);

  useEffect(() => {
    fetch("/api/concepts?scheme=region")
      .then((r) => r.json())
      .then((d) => {
        setRegions((d.items ?? []).filter((r: Region) => r.level !== "GROUP"));
        setRegionSource(d.source ?? "");
      })
      .catch(() => setRegionSource("unavailable"));
  }, []);

  const view = useMemo(() => {
    const notices = new Map<string, Notice>();
    const get = (id: string) => {
      if (!notices.has(id)) notices.set(id, { id, requirements: [], paths: [], definitions: [] });
      return notices.get(id)!;
    };
    let answer = "";
    const banners: AgentEvent[] = [];
    let ask: AgentEvent | undefined, done: AgentEvent | undefined, usage: AgentEvent | undefined;
    for (const e of events) {
      const nid = s(e.notice_id);
      if (e.type === "verdict") get(nid).verdict = e;
      else if (e.type === "requirement") get(nid).requirements.push(e);
      else if (e.type === "path") get(nid).paths.push(e);
      else if (e.type === "definition") get(nid).definitions.push(e);
      else if (e.type === "token") answer += s(e.text);
      else if (e.type === "banner" || e.type === "error") banners.push(e);
      else if (e.type === "ask") ask = e;
      else if (e.type === "usage") usage = e;
      else if (e.type === "done") done = e;
    }
    return { notices: [...notices.values()], answer, banners, ask, done, usage };
  }, [events]);

  async function submit(ev?: React.FormEvent, nextAsk = 0) {
    ev?.preventDefault();
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setEvents([]);
    setGraphs({});
    setError("");
    setRunning(true);
    setAskCount(nextAsk);
    const num = (v: string) => (v.trim() === "" ? null : Number(v));
    const body = {
      question,
      notice_id: form.notice_id.trim() || null,
      ask_count: nextAsk,
      profile: {
        region: form.region || null,
        business_age_years: num(form.business_age_years),
        founder_age: num(form.founder_age),
        pre_founder: form.pre_founder === "" ? null : form.pre_founder === "yes",
      },
    };
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(body),
        signal: ctl.signal,
      });
      if (!res.ok) {
        const d = await res.json().catch(() => null);
        setError(d?.error?.message ?? d?.detail?.[0]?.msg ?? `요청 실패(${res.status})`);
        return;
      }
      for await (const e of readSse(res)) setEvents((prev) => [...prev, e]);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError("연결이 끊겼습니다. 잠시 뒤 다시 시도해 주세요.");
    } finally {
      setRunning(false);
    }
  }

  async function loadGraph(nid: string) {
    setGraphs((g) => ({ ...g, [nid]: "불러오는 중…" }));
    const qs = new URLSearchParams({ notice_id: nid, ...(form.region ? { region: form.region } : {}) });
    const r = await fetch(`/api/graph/path?${qs}`);
    const d = await r.json().catch(() => null);
    setGraphs((g) => ({ ...g, [nid]: r.ok ? (d as Subgraph) : d?.detail?.error?.message ?? "그래프를 불러오지 못했습니다." }));
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <main>
      <h1>지원각</h1>
      <div className="muted">조건을 넣으면 규칙 평가기가 판정하고, 모델은 그 근거를 설명만 합니다. 결과는 참고용입니다.</div>

      <form className="panel" onSubmit={(e) => submit(e, 0)}>
        <div className="grid">
          <label>
            사업장 소재지 {regionSource && <span>({regionSource === "neo4j" ? "그래프" : regionSource === "local" ? "내장 사전" : "불러오기 실패"})</span>}
            <select value={form.region} onChange={set("region")}>
              <option value="">모름</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.full_name ?? r.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            업력(년)
            <input type="number" min={0} step="0.5" value={form.business_age_years} onChange={set("business_age_years")} placeholder="모름" />
          </label>
          <label>
            대표자 만 나이
            <input type="number" min={0} max={120} value={form.founder_age} onChange={set("founder_age")} placeholder="모름" />
          </label>
          <label>
            예비창업자
            <select value={form.pre_founder} onChange={set("pre_founder")}>
              <option value="">모름</option>
              <option value="yes">예</option>
              <option value="no">아니오</option>
            </select>
          </label>
          <label>
            공고 ID(선택)
            <input value={form.notice_id} onChange={set("notice_id")} placeholder="예: KSTARTUP:179814" />
          </label>
        </div>
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000} aria-label="질문" />
        <div className="row">
          <button className="primary" disabled={running || !question.trim()}>
            {running ? "확인 중…" : "자격 확인"}
          </button>
          {running && (
            <button type="button" onClick={() => abort.current?.abort()}>
              중지
            </button>
          )}
          <span className="muted">개인정보(주민·사업자번호 등)는 입력하지 마세요.</span>
        </div>
      </form>

      {error && <div className="banner">{error}</div>}
      {view.banners.map((b, i) => (
        <div className="banner" key={i}>
          {s(b.text ?? b.message)}
        </div>
      ))}

      {view.ask && (
        <div className="panel">
          <div>{s(view.ask.text)}</div>
          <div className="row">
            <button type="button" onClick={() => submit(undefined, askCount + 1)} disabled={running}>
              입력 없이 계속
            </button>
          </div>
        </div>
      )}

      {view.notices.map((n) => (
        <section className="panel" key={n.id}>
          <div className="card-head">
            <h2>{s(n.verdict?.title) || n.id}</h2>
            {n.verdict && <span className={`badge ${s(n.verdict.verdict)}`}>{VERDICT[s(n.verdict.verdict)] ?? s(n.verdict.verdict)}</span>}
          </div>
          <div className="meta">
            {n.id}
            {n.verdict?.deadline ? ` · 마감 ${s(n.verdict.deadline)}` : ""}
            {n.verdict?.fetched_at ? ` · 수집 ${s(n.verdict.fetched_at).slice(0, 10)}` : ""}
            {n.verdict?.detail_url ? (
              <>
                {" · "}
                <a href={s(n.verdict.detail_url)} target="_blank" rel="noreferrer">
                  공고 원문
                </a>
              </>
            ) : null}
          </div>

          {n.requirements.length > 0 && (
            <table>
              <thead>
                <tr>
                  <th>요건</th>
                  <th>상태</th>
                  <th>사유</th>
                  <th>공고 근거</th>
                </tr>
              </thead>
              <tbody>
                {n.requirements.map((r) => (
                  <tr key={s(r.cond_id)}>
                    <td>
                      {ATTR[s(r.attribute)] ?? s(r.attribute)}
                      {r.strength === "soft" ? <span className="muted"> (참고)</span> : null}
                    </td>
                    <td>
                      <span className={`badge ${s(r.status)}`}>{STATUS[s(r.status)] ?? s(r.status)}</span>
                    </td>
                    <td>{s(r.reason)}</td>
                    <td className="muted">{s(r.evidence)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          {n.paths.map((p) => (
            <div className="chain" key={`p-${s(p.cond_id)}`}>
              지역 경로({p.source === "neo4j" ? "그래프" : "평가기"}):{" "}
              {p.reached ? (
                ((p.nodes as { name: string }[]) ?? []).map((x, i) => (
                  <span key={i}>
                    {i > 0 && " → "}
                    <code>{x.name}</code>
                  </span>
                ))
              ) : (
                <span className="muted">사용자 지역에서 조건 지역({s(p.target)})으로 가는 경로 없음</span>
              )}
            </div>
          ))}

          {n.definitions.map((d, i) => (
            <div className="chain" key={`d-${i}`}>
              정의: <code>{s(d.term)}</code> →{" "}
              {d.broken ? (
                <span className="muted">법령 원문 확인 필요</span>
              ) : (
                <a href={s(d.law_url)} target="_blank" rel="noreferrer">
                  {s(d.law)} 제{s(d.article_no).replace(/^제|조$/g, "")}조{d.article_title ? `(${s(d.article_title)})` : ""}
                </a>
              )}
              {d.needs_review ? <span className="muted"> · 검수 전</span> : null}
            </div>
          ))}

          <div className="row">
            <button type="button" className="link" onClick={() => loadGraph(n.id)}>
              판정 경로 그래프 보기
            </button>
          </div>
          {typeof graphs[n.id] === "string" && <div className="muted">{graphs[n.id] as string}</div>}
          {graphs[n.id] && typeof graphs[n.id] === "object" && <GraphList g={graphs[n.id] as Subgraph} />}
        </section>
      ))}

      {(view.answer || view.done) && (
        <div className="panel">
          <h2>설명</h2>
          <div className="answer">{view.answer}</div>
          {view.done && (
            <div className="meta">
              {s(view.done.disclaimer)}
              <br />
              결과: {s(view.done.outcome)}
              {view.done.reason_code ? ` (${s(view.done.reason_code)})` : ""} · 설명 모델: {s(view.done.provider) || "없음"}
              {view.usage ? ` · 토큰 ${s(view.usage.completion_tokens)}` : ""}
            </div>
          )}
        </div>
      )}
    </main>
  );
}

function GraphList({ g }: { g: Subgraph }) {
  const label = new Map(g.nodes.map((n) => [n.id, `${n.kind}: ${n.label}`]));
  return (
    <table>
      <thead>
        <tr>
          <th>출발</th>
          <th>관계</th>
          <th>도착</th>
        </tr>
      </thead>
      <tbody>
        {g.edges.map((e, i) => (
          <tr key={i}>
            <td>{label.get(e.from) ?? e.from}</td>
            <td>
              <code>{e.type}</code>
            </td>
            <td>{label.get(e.to) ?? e.to}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
