"use client";
// 홈: 조건 폼 + 대화 패널. 질문마다 /api/chat(SSE)로 멀티 에이전트를 부르고, 턴마다 오케스트레이션·판정 카드·검색 근거·정의·설명을 보인다.
// 판정은 규칙 평가기가 하고, 모델은 설명만 한다.
import { useEffect, useRef, useState } from "react";

import ChatResult from "@/components/ChatResult";
import RegionSelect from "@/components/RegionSelect";
import { streamChat, type AgentMode, type ChatBody } from "@/lib/chat";
import { AGENT, num, PII_WARNING } from "@/lib/labels";
import type { AgentEvent } from "@/lib/sse";

type Turn = { id: string; question: string; mode: AgentMode; noticeId: string; askCount: number; events: AgentEvent[]; running: boolean; error: string };

const MODES: AgentMode[] = ["auto", "eligibility", "notice_qa", "definition"];
const EXAMPLES: Record<AgentMode, string> = {
  auto: "서울에서 창업 2년 차인데 신청할 만한 지원사업 알려줘",
  eligibility: "내 조건으로 신청 자격이 되는 공고를 찾아줘",
  notice_qa: "신청 방법과 제출 서류가 뭐야?",
  definition: "중소기업의 정의가 뭐야?",
};

let seq = 0;

export default function Home() {
  const [form, setForm] = useState({ region: "", business_age_years: "", founder_age: "", pre_founder: "", notice_id: "" });
  const [question, setQuestion] = useState(EXAMPLES.auto);
  const [mode, setMode] = useState<AgentMode>("auto");
  const [turns, setTurns] = useState<Turn[]>([]);
  const abort = useRef<AbortController | null>(null);
  const bottom = useRef<HTMLDivElement | null>(null);
  const running = turns.some((t) => t.running);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns.length]);

  const patch = (id: string, f: (t: Turn) => Partial<Turn>) => setTurns((ts) => ts.map((t) => (t.id === id ? { ...t, ...f(t) } : t)));

  async function send(q: string, m: AgentMode, askCount: number, noticeId: string) {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    const id = `t${++seq}`;
    setTurns((ts) => [...ts, { id, question: q, mode: m, noticeId, askCount, events: [], running: true, error: "" }]);
    const body: ChatBody = {
      question: q,
      agent: m,
      notice_id: noticeId || null,
      ask_count: askCount,
      profile: {
        region: form.region || null,
        business_age_years: num(form.business_age_years),
        founder_age: num(form.founder_age),
        pre_founder: form.pre_founder === "" ? null : form.pre_founder === "yes",
      },
    };
    const err = await streamChat(body, (e) => patch(id, (t) => ({ events: [...t.events, e] })), ctl.signal);
    patch(id, () => ({ running: false, error: err }));
  }

  function submit(ev: React.FormEvent) {
    ev.preventDefault();
    if (!question.trim() || running) return;
    send(question.trim(), mode, 0, form.notice_id.trim());
    setQuestion("");
  }

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <main>
      <h1>지원각</h1>
      <div className="muted">
        조건과 질문을 넣으면 규칙 평가기가 판정하고, 모델은 그 근거를 설명만 합니다. 판정 결과는 신청 가능 여부를 보장하지 않습니다.{" "}
        <a href="/eligibility">규칙 판정만 보기</a>
      </div>

      <details className="panel" open>
        <summary>
          <strong>내 조건</strong> <span className="muted">(비워 둔 칸은 &lsquo;모름&rsquo;이며 &lsquo;제한 없음&rsquo;으로 보지 않습니다)</span>
        </summary>
        <form className="grid-form" onSubmit={(e) => e.preventDefault()}>
          <div className="grid">
            <RegionSelect value={form.region} onChange={set("region")} />
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
        </form>
      </details>

      <div className="chat">
        {turns.length === 0 && <div className="muted empty">아래에 질문을 입력하세요. 에이전트를 고르지 않으면 질문을 보고 자동으로 나눕니다.</div>}
        {turns.map((t, i) => (
          <div key={t.id}>
            <div className="msg user">
              <div className="msg-meta">
                나 · {AGENT[t.mode]}
                {t.noticeId ? ` · 공고 ${t.noticeId}` : ""}
                {t.askCount ? ` · 되묻기 ${t.askCount}회 뒤` : ""}
              </div>
              {t.question}
            </div>
            <div className="msg assistant">
              <div className="msg-meta">지원각{t.running ? " · 확인 중…" : ""}</div>
              <ChatResult
                events={t.events}
                turnKey={t.id}
                running={t.running}
                onAskContinue={i === turns.length - 1 ? () => send(t.question, t.mode, t.askCount + 1, t.noticeId) : undefined}
              />
              {t.error && (
                <div className="banner">
                  {t.error}{" "}
                  <button type="button" className="link" onClick={() => send(t.question, t.mode, t.askCount, t.noticeId)} disabled={running}>
                    다시 시도
                  </button>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={bottom} />
      </div>

      <form className="panel composer" onSubmit={submit}>
        <div className="row modes" role="radiogroup" aria-label="에이전트 선택">
          {MODES.map((m) => (
            <label className="check" key={m}>
              <input
                type="radio"
                name="mode"
                checked={mode === m}
                onChange={() => {
                  setMode(m);
                  if (!question.trim() || Object.values(EXAMPLES).includes(question)) setQuestion(EXAMPLES[m]);
                }}
              />{" "}
              {AGENT[m]}
            </label>
          ))}
        </div>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault();
              (e.currentTarget.form as HTMLFormElement).requestSubmit();
            }
          }}
          maxLength={1000}
          aria-label="질문"
          placeholder="질문을 입력하세요 (Enter 보내기, Shift+Enter 줄바꿈)"
        />
        <div className="row">
          <button className="primary" disabled={running || !question.trim()}>
            {running ? "확인 중…" : "보내기"}
          </button>
          {running && (
            <button type="button" onClick={() => abort.current?.abort()}>
              중지
            </button>
          )}
          {turns.length > 0 && !running && (
            <button type="button" className="link" onClick={() => setTurns([])}>
              대화 지우기
            </button>
          )}
          <span className="muted">{PII_WARNING}</span>
        </div>
      </form>
    </main>
  );
}
