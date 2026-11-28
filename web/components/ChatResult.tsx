"use client";
// 어시스턴트 한 턴: 오케스트레이션 타임라인 → 안내 배너 → 되묻기 → 판정 카드 → 정의 → 설명(인용) → 검색 근거.
import { Fragment, useState } from "react";

import type { AgentEvent } from "@/lib/sse";
import { buildTurn, CITE_RE, type Chunk, type NoticeView, type TurnView } from "@/lib/chat";
import { AGENT, ATTR, day, ROUTE_METHOD, s, SOURCE, STATUS, VERDICT } from "@/lib/labels";

type Props = {
  events: AgentEvent[];
  turnKey: string;
  running?: boolean;
  onAskContinue?: () => void;
  showNoticeLink?: boolean;
};

export default function ChatResult({ events, turnKey, running, onAskContinue, showNoticeLink = true }: Props) {
  const v = buildTurn(events);
  const [hit, setHit] = useState<string | null>(null);

  function jump(chunkId: string) {
    setHit(chunkId);
    document.getElementById(chunkDom(turnKey, chunkId))?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <div className="turn">
      <Timeline v={v} running={running} />
      {v.banners.map((b, i) => (
        <div className="banner" key={i}>
          {s(b.text ?? b.message)}
          {b.code ? <span className="muted"> ({s(b.code)})</span> : null}
        </div>
      ))}
      {v.ask && (
        <div className="panel ask">
          <div>
            <strong>되묻기 {s(v.ask.ask_count)}/2</strong> · {s(v.ask.text)}
          </div>
          {onAskContinue && (
            <div className="row">
              <span className="muted">위 &lsquo;내 조건&rsquo;을 채워 다시 보내거나,</span>
              <button type="button" onClick={onAskContinue} disabled={running}>
                입력 없이 계속
              </button>
            </div>
          )}
        </div>
      )}
      {v.notices.map((n) => (
        <VerdictCard key={n.id} n={n} showLink={showNoticeLink} />
      ))}
      {v.definitions.map((d, i) => (
        <DefinitionCard key={i} d={d} />
      ))}
      {(v.segments.length > 0 || v.done) && (
        <div className="panel">
          <h2>설명</h2>
          {v.segments.map((seg, i) => (
            <div className={`answer${seg.template ? " template" : ""}`} key={i}>
              {seg.agent && (v.segments.length > 1 || v.steps.length > 1) ? <span className="agent-tag">{AGENT[seg.agent] ?? seg.agent}</span> : null}
              <Cited text={seg.text} chunks={v.chunks} onJump={jump} />
            </div>
          ))}
          {v.done && (
            <div className="meta">
              {s(v.done.disclaimer)}
              {v.done.disclaimer ? <br /> : null}
              결과: {s(v.done.outcome)}
              {v.done.reason_code ? ` (${s(v.done.reason_code)})` : ""} · 설명 모델: {s(v.done.provider) || "없음"}
              {v.usage ? ` · 토큰 ${s(v.usage.completion_tokens)}` : ""}
            </div>
          )}
        </div>
      )}
      {v.chunks.length > 0 && <Retrieval v={v} turnKey={turnKey} hit={hit} />}
    </div>
  );
}

const chunkDom = (turnKey: string, chunkId: string) => `chunk-${turnKey}-${chunkId.replace(/[^A-Za-z0-9_-]/g, "_")}`;

function Timeline({ v, running }: { v: TurnView; running?: boolean }) {
  if (!v.route && v.steps.length === 0) return running ? <div className="muted">확인 중…</div> : null;
  const plan = (v.route?.plan as string[] | undefined) ?? (v.done?.plan as string[] | undefined) ?? [];
  return (
    <div className="timeline" aria-label="오케스트레이션">
      <div className="tl-head">
        <strong>오케스트레이션</strong>
        {plan.length > 0 && <span> · 계획: {plan.map((p) => AGENT[p] ?? p).join(" → ")}</span>}
        {v.route?.method ? <span className="muted"> ({ROUTE_METHOD[s(v.route.method)] ?? s(v.route.method)})</span> : null}
      </div>
      {v.route && (v.route.intent || v.route.reason) ? (
        <div className="muted">
          {v.route.intent ? `의도: ${s(v.route.intent)}` : ""}
          {v.route.intent && v.route.reason ? " · " : ""}
          {v.route.reason ? `이유: ${s(v.route.reason)}` : ""}
        </div>
      ) : null}
      <ol>
        {v.steps.map((st) => {
          const r = v.retrievals.filter((x) => s(x.agent) === st.name);
          return (
            <li key={`${st.step}-${st.name}`}>
              <span className={`tl-status ${st.ended ? "end" : "run"}`}>{st.ended ? "완료" : running ? "진행 중" : "중단"}</span> {AGENT[st.name] ?? st.name}
              {st.outcome ? <span className="muted"> · {st.outcome}</span> : null}
              {r.map((x, i) => (
                <div className="muted" key={i}>
                  검색: &ldquo;{s(x.query)}&rdquo;{x.rewritten ? " (질문 다시 씀)" : ""} · {x.mode === "bm25" ? "키워드(BM25)" : "하이브리드"} ·{" "}
                  {((x.chunks as unknown[]) ?? []).length}건
                </div>
              ))}
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function Cited({ text, chunks, onJump }: { text: string; chunks: Chunk[]; onJump: (id: string) => void }) {
  const byId = new Map(chunks.map((c) => [c.chunk_id, c]));
  const parts: React.ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(CITE_RE)) {
    const idx = m.index ?? 0;
    parts.push(text.slice(last, idx));
    const c = byId.get(m[1]);
    parts.push(
      c ? (
        <button type="button" className="cite" key={idx} onClick={() => onJump(c.chunk_id)} title={`${s(c.title)} · ${s(c.section)}`}>
          {c.n}
        </button>
      ) : (
        <span className="cite missing" key={idx} title={`검색 결과에 없는 근거: ${m[1]}`}>
          ?
        </span>
      ),
    );
    last = idx + m[0].length;
  }
  parts.push(text.slice(last));
  return <>{parts.map((p, i) => (typeof p === "string" ? <Fragment key={`t${i}`}>{p}</Fragment> : p))}</>;
}

function Retrieval({ v, turnKey, hit }: { v: TurnView; turnKey: string; hit: string | null }) {
  return (
    <div className="panel">
      <h2>검색 근거 ({v.chunks.length}건)</h2>
      <div className="muted">답변의 번호를 누르면 해당 원문 구역으로 이동합니다. &lsquo;인용됨&rsquo;은 답변이 실제로 쓴 구역입니다.</div>
      <ol className="chunks">
        {v.chunks.map((c) => (
          <li key={c.chunk_id} id={chunkDom(turnKey, c.chunk_id)} className={`chunk${hit === c.chunk_id ? " hit" : ""}`}>
            <div className="card-head">
              <span>
                <span className="cite static">{c.n}</span> {s(c.title) || s(c.notice_id)}
              </span>
              {v.cited.has(c.chunk_id) && <span className="badge SATISFIED">인용됨</span>}
            </div>
            <div className="meta">
              구역 {s(c.section)} · 출처 {SOURCE[s(c.source)] ?? (s(c.source) || "미상")}
              {c.score != null ? ` · 점수 ${Number(c.score).toFixed(3)}` : ""}
              {c.notice_id ? (
                <>
                  {" · "}
                  <a href={`/notices/${encodeURIComponent(c.notice_id)}`}>공고 상세</a>
                </>
              ) : null}
              {c.detail_url ? (
                <>
                  {" · "}
                  <a href={c.detail_url} target="_blank" rel="noreferrer">
                    공고 원문
                  </a>
                </>
              ) : null}
            </div>
            {c.text && <div className="chunk-text">{c.text}</div>}
          </li>
        ))}
      </ol>
    </div>
  );
}

export function VerdictCard({ n, showLink = true }: { n: NoticeView; showLink?: boolean }) {
  return (
    <section className="panel">
      <div className="card-head">
        <h2>{s(n.verdict?.title) || n.id}</h2>
        {n.verdict && <span className={`badge ${s(n.verdict.verdict)}`}>{VERDICT[s(n.verdict.verdict)] ?? s(n.verdict.verdict)}</span>}
      </div>
      <div className="meta">
        {n.id}
        {n.verdict?.source ? ` · 출처 ${SOURCE[s(n.verdict.source)] ?? s(n.verdict.source)}` : ""}
        {n.verdict?.deadline ? ` · 마감 ${s(n.verdict.deadline)}` : ""}
        {` · 수집 ${n.verdict?.fetched_at ? day(n.verdict.fetched_at) : "미상"}`}
        {n.verdict?.detail_url ? (
          <>
            {" · "}
            <a href={s(n.verdict.detail_url)} target="_blank" rel="noreferrer">
              공고 원문
            </a>
          </>
        ) : null}
        {showLink && (
          <>
            {" · "}
            <a href={`/notices/${encodeURIComponent(n.id)}`}>상세·경로 보기</a>
          </>
        )}
      </div>
      {((n.verdict?.reasons as string[] | undefined) ?? []).length > 0 && (
        <ul>
          {(n.verdict!.reasons as string[]).map((r, i) => (
            <li key={i}>{r}</li>
          ))}
        </ul>
      )}
      {n.requirements.length > 0 && <RequirementTable rows={n.requirements} />}
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
        <DefinitionLine key={i} d={d} />
      ))}
    </section>
  );
}

export function RequirementTable({ rows }: { rows: AgentEvent[] }) {
  return (
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
        {rows.map((r, i) => (
          <tr key={`${s(r.cond_id)}-${i}`}>
            <td>
              {ATTR[s(r.attribute)] ?? s(r.attribute)}
              <span className="muted"> ({r.strength === "soft" ? "참고" : "필수"})</span>
            </td>
            <td>
              <span className={`badge ${s(r.status)}`}>{STATUS[s(r.status)] ?? s(r.status)}</span>
            </td>
            <td>{s(r.reason)}</td>
            <td className="muted">{s(r.evidence) || "원문 근거 없음"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function lawLabel(d: AgentEvent) {
  return `${s(d.law)} 제${s(d.article_no).replace(/^제|조$/g, "")}조${d.article_title ? `(${s(d.article_title)})` : ""}`;
}

function DefinitionLine({ d }: { d: AgentEvent }) {
  return (
    <div className="chain">
      정의: <code>{s(d.term)}</code> →{" "}
      {d.broken || !d.law ? (
        <span className="muted">법령 원문 확인 필요(미보유)</span>
      ) : (
        <a href={s(d.law_url)} target="_blank" rel="noreferrer">
          {lawLabel(d)}
        </a>
      )}
      {d.needs_review ? <span className="muted"> · 검수 전</span> : null}
    </div>
  );
}

function DefinitionCard({ d }: { d: AgentEvent }) {
  return (
    <section className="panel">
      <div className="card-head">
        <h2>용어 정의: {s(d.term)}</h2>
        {d.needs_review ? <span className="badge UNKNOWN">검수 전</span> : null}
      </div>
      {d.text ? <div className="answer">{s(d.text)}</div> : null}
      <div className="meta">
        근거:{" "}
        {d.broken || !d.law ? (
          "법령 원문 확인 필요(미보유)"
        ) : d.law_url ? (
          <a href={s(d.law_url)} target="_blank" rel="noreferrer">
            {lawLabel(d)}
          </a>
        ) : (
          lawLabel(d)
        )}
      </div>
    </section>
  );
}
