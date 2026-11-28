"use client";
// 공고 상세: 기본 정보·원문 구역 → 내 조건으로 판정(자격 판정 에이전트) → 경로 그래프 → 이 공고에 질문하기(공고 질의 에이전트).
import { useEffect, useRef, useState } from "react";

import ChatResult from "@/components/ChatResult";
import PathGraph from "@/components/PathGraph";
import RegionSelect from "@/components/RegionSelect";
import { streamChat, type AgentMode, type ChatProfile } from "@/lib/chat";
import { day, errorMessage, num, PII_WARNING, s, SOURCE } from "@/lib/labels";
import type { AgentEvent } from "@/lib/sse";
import { apiFetch } from "@/lib/auth";

type Section = { chunk_id: string; section: string; origin: string; text: string };
type Detail = {
  notice_id: string;
  source_system: string;
  title: string;
  organization: string | null;
  category: string | null;
  deadline: string | null;
  is_open: boolean;
  detail_url: string | null;
  fetched_at: string | null;
  application_start: string | null;
  period_status: string | null;
  apply_url: string | null;
  contact_text: string | null;
  attachments: { count?: number; text_extracted?: number | boolean; preview_only?: number | boolean; note?: string } | null;
  requirements_status: string;
  sections: Section[];
};
type Run = { events: AgentEvent[]; running: boolean; error: string; key: number };

const REQ_STATUS: Record<string, string> = { parsed: "요건 정규화 완료", partial: "요건 일부만 정규화", unparsed: "요건 미정규화(원문 확인 필요)" };
const EMPTY_RUN: Run = { events: [], running: false, error: "", key: 0 };

/** 자격 판정·공고 질의 한 묶음을 돌리는 훅. 새로 보내면 앞 결과를 지운다. */
function useChatRun(noticeId: string, agent: AgentMode) {
  const [run, setRun] = useState<Run>(EMPTY_RUN);
  const abort = useRef<AbortController | null>(null);
  useEffect(() => () => abort.current?.abort(), []);
  async function start(question: string, profile: ChatProfile, askCount = 0) {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setRun((r) => ({ events: [], running: true, error: "", key: r.key + 1 }));
    const err = await streamChat(
      { question, profile, notice_id: noticeId, agent, ask_count: askCount },
      (e) => setRun((r) => ({ ...r, events: [...r.events, e] })),
      ctl.signal,
    );
    setRun((r) => ({ ...r, running: false, error: err }));
  }
  return { run, start, stop: () => abort.current?.abort() };
}

export default function NoticeDetail({ id }: { id: string }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loadError, setLoadError] = useState("");
  const [form, setForm] = useState({ region: "", business_age_years: "", founder_age: "", pre_founder: "" });
  const [graphRegion, setGraphRegion] = useState("");
  const [question, setQuestion] = useState("");
  const elig = useChatRun(id, "eligibility");
  const qa = useChatRun(id, "notice_qa");

  useEffect(() => {
    const ctl = new AbortController();
    apiFetch(`/api/notices/${encodeURIComponent(id)}`, { signal: ctl.signal })
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (r.ok) setDetail(d as Detail);
        else setLoadError(r.status === 404 ? "공고를 찾을 수 없습니다." : errorMessage(d, r.status));
      })
      .catch((e) => {
        if ((e as Error).name !== "AbortError") setLoadError("API 서버에 닿지 않습니다.");
      });
    return () => ctl.abort();
  }, [id]);

  const profile = (): ChatProfile => ({
    region: form.region || null,
    business_age_years: num(form.business_age_years),
    founder_age: num(form.founder_age),
    pre_founder: form.pre_founder === "" ? null : form.pre_founder === "yes",
  });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  function judge(ev: React.FormEvent) {
    ev.preventDefault();
    setGraphRegion(form.region);
    elig.start("이 공고에 내 조건으로 신청 자격이 되는지 확인해 줘", profile());
  }
  function ask(ev: React.FormEvent) {
    ev.preventDefault();
    if (question.trim()) qa.start(question.trim(), profile());
  }

  return (
    <main>
      <div className="muted">
        <a href="/notices">← 공고 목록</a>
      </div>
      {loadError && (
        <>
          <h1>{id}</h1>
          <div className="banner">공고 정보를 불러오지 못했습니다: {loadError} 판정과 질문은 아래에서 그대로 쓸 수 있습니다.</div>
        </>
      )}
      {!detail && !loadError && <div className="muted">공고를 불러오는 중…</div>}
      {detail && (
        <section className="panel">
          <div className="card-head">
            <h1>{detail.title}</h1>
            <span className={`badge ${detail.is_open ? "SATISFIED" : "UNSATISFIED"}`}>{detail.is_open ? "모집 중" : "마감"}</span>
          </div>
          <div className="meta">
            {detail.organization ?? "기관 미상"}
            {detail.category ? ` · ${detail.category}` : ""} · 접수 {detail.application_start ?? "미상"} ~ {detail.deadline ?? "상시·미정"}
            <br />
            출처 {SOURCE[detail.source_system] ?? detail.source_system} · 수집 {detail.fetched_at ? day(detail.fetched_at) : "미상"} · {detail.notice_id}
            {detail.detail_url && (
              <>
                {" · "}
                <a href={detail.detail_url} target="_blank" rel="noreferrer">
                  공고 원문
                </a>
              </>
            )}
            {detail.apply_url && detail.apply_url !== detail.detail_url && (
              <>
                {" · "}
                <a href={detail.apply_url} target="_blank" rel="noreferrer">
                  신청 페이지
                </a>
              </>
            )}
          </div>
          <div className="row">
            <span className={`badge ${detail.requirements_status === "parsed" ? "SATISFIED" : "UNKNOWN"}`}>
              {REQ_STATUS[detail.requirements_status] ?? detail.requirements_status}
            </span>
            {detail.attachments && (
              <span className="muted">
                첨부 {s(detail.attachments.count ?? 0)}개
                {detail.attachments.text_extracted != null ? ` · 텍스트 추출 ${s(detail.attachments.text_extracted)}` : ""}
                {detail.attachments.preview_only ? ` · 미리보기만 ${s(detail.attachments.preview_only)}` : ""}
                {detail.attachments.note ? ` · ${detail.attachments.note}` : ""}
              </span>
            )}
          </div>
          {detail.contact_text && <div className="meta">문의: {detail.contact_text}</div>}

          <h2 className="sub">원문 구역 ({detail.sections.length})</h2>
          {detail.sections.length === 0 && <div className="muted">정리된 원문 구역이 없습니다. 공고 원문 링크에서 확인하세요.</div>}
          {detail.sections.map((sec, i) => (
            <details key={sec.chunk_id} open={i < 2}>
              <summary>
                {sec.section} <span className="muted">({sec.origin === "ATTACHMENT" ? "첨부" : "API"})</span>
              </summary>
              <div className="chunk-text">{sec.text}</div>
            </details>
          ))}
        </section>
      )}

      <form className="panel" onSubmit={judge}>
        <h2>내 조건으로 판정</h2>
        <div className="muted">규칙 평가기가 이 공고의 조건만 판정합니다. 비워 둔 칸은 &lsquo;모름&rsquo;입니다.</div>
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
        </div>
        <div className="row">
          <button className="primary" disabled={elig.run.running}>
            {elig.run.running ? "판정 중…" : "판정"}
          </button>
          {elig.run.running && (
            <button type="button" onClick={elig.stop}>
              중지
            </button>
          )}
          <span className="muted">{PII_WARNING}</span>
        </div>
      </form>
      {(elig.run.events.length > 0 || elig.run.running) && (
        <ChatResult events={elig.run.events} turnKey={`elig${elig.run.key}`} running={elig.run.running} showNoticeLink={false} />
      )}
      {elig.run.error && <div className="banner">{elig.run.error}</div>}

      <section className="panel">
        <h2>판정 경로 그래프</h2>
        <div className="muted">
          공고 → 요건 → 조건 → 개념 → 정의 → 법령. {graphRegion ? "판정에 쓴 내 지역에서 조건 지역으로 가는 경로를 굵게 표시합니다." : "판정하면 내 지역 경로가 함께 표시됩니다."}
        </div>
        <PathGraph noticeId={id} region={graphRegion || undefined} />
      </section>

      <form className="panel" onSubmit={ask}>
        <h2>이 공고에 질문하기</h2>
        <div className="muted">공고 원문 구역을 찾아 답하고, 답의 번호는 근거 구역을 가리킵니다.</div>
        <textarea value={question} onChange={(e) => setQuestion(e.target.value)} maxLength={1000} placeholder="예: 신청 방법과 제출 서류가 뭐야?" aria-label="공고 질문" />
        <div className="row">
          <button className="primary" disabled={qa.run.running || !question.trim()}>
            {qa.run.running ? "찾는 중…" : "질문"}
          </button>
          {qa.run.running && (
            <button type="button" onClick={qa.stop}>
              중지
            </button>
          )}
          <span className="muted">{PII_WARNING}</span>
        </div>
      </form>
      {(qa.run.events.length > 0 || qa.run.running) && (
        <ChatResult events={qa.run.events} turnKey={`qa${qa.run.key}`} running={qa.run.running} showNoticeLink={false} />
      )}
      {qa.run.error && <div className="banner">{qa.run.error}</div>}
    </main>
  );
}
