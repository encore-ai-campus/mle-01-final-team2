"use client";
// SCR-02 공고 상세(화면설계서 v3.5). 위: 기본 정보 + 판정 요약 막대. 탭: 원문(SCR-02) · 조건별 검증(SCR-02-1) · 추론 과정(SCR-02-2).
// 판정은 POST /api/eligibility/{id}(규칙 평가기만, 모델 없음). 모델 설명(자격 판정 에이전트)은 추론 과정 탭에서 따로 부르고 판정과 섞지 않는다.
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";

import ChatResult from "@/components/ChatResult";
import PathGraph from "@/components/PathGraph";
import ProfileFields from "@/components/ProfileFields";
import StatusScreen from "@/components/StatusScreen";
import { apiFetch } from "@/lib/auth";
import { streamChat, type AgentMode, type ChatProfile } from "@/lib/chat";
import { ATTR, DISCLAIMER, PII_WARNING, REASON, SOURCE, STATUS_MARK, VALUE_SOURCE, VERDICT_MARK, day, errorMessage, s } from "@/lib/labels";
import { EMPTY_PROFILE, loadProfile, saveProfile, toApiProfile, toChatProfile, type ProfileForm } from "@/lib/profile";
import type { AgentEvent } from "@/lib/sse";

export type DetailTab = "source" | "verify" | "reasoning";
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
type Check = {
  cond_id: string;
  attribute: string;
  strength: string | null;
  required: { label: string };
  my_value: { value: unknown; source: "INPUT" | "DERIVED" | "MISSING"; field: string | null };
  result: string;
  reason: string;
  evidence: { text: string };
  path: string[] | null;
  flags: string[];
};
type Checks = {
  notice_id: string;
  result: { verdict: string; reasons: string[]; structured: string; unparsed_text?: { chunk_id: string; label: string; text: string }[] };
  checks: Check[];
  by_result: Record<string, number>;
  by_source: Record<string, number>;
  meta?: { stale?: boolean; disclaimer?: string };
};
type Run = { events: AgentEvent[]; running: boolean; error: string; key: number };

const REQ_STATUS: Record<string, string> = { parsed: "요건 정규화 완료", partial: "요건 일부만 정규화", unparsed: "요건 미정규화(원문 확인 필요)" };
const TAB_LABEL: Record<DetailTab, string> = { source: "원문", verify: "조건별 검증", reasoning: "추론 과정" };
const SME: Record<string, string> = { certified: "중소기업확인서 보유", expected: "중소기업 예정" };
const FIELD_LABEL: Record<string, string> = { region: "지역", business_start_date: "사업 개시일", business_age_years: "업력", birth_date: "대표자 생년월일", founder_age: "대표자 나이", pre_founder: "예비창업자", sme_status: "중소기업 여부", applicant_type: "신청 대상" };
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

/** 내 값 표시. 지역은 개념 ID를 그대로 두되 접두어를 뗀다 */
function shown(v: unknown, field: string | null): string {
  if (v == null) return "—";
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "boolean") return v ? "예" : "아니오";
  if (field === "sme_status") return SME[String(v)] ?? String(v);
  if (field === "business_age_years") return `${v}년`;
  if (field === "founder_age") return `만 ${v}세`;
  return String(v).replace(/^REGION:/, "지역 코드 ");
}

/** 원문에서 근거 문구를 <mark>로 표시한다. 4자 미만 문구는 너무 흔해서 표시하지 않는다 */
function highlight(text: string, phrases: string[]): React.ReactNode {
  const ps = [...new Set(phrases.map((p) => p.trim()).filter((p) => p.length >= 4))];
  if (!ps.length) return text;
  const re = new RegExp(`(${ps.map((p) => p.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return text.split(re).map((part, i) => (ps.includes(part) ? <mark key={i}>{part}</mark> : part));
}

export default function NoticeDetail({ id, initialTab = "source" }: { id: string; initialTab?: DetailTab }) {
  const [detail, setDetail] = useState<Detail | null>(null);
  const [loadError, setLoadError] = useState("");
  const [tab, setTabState] = useState<DetailTab>(initialTab);
  const [form, setForm] = useState<ProfileForm>(EMPTY_PROFILE);
  const [check, setCheck] = useState<Checks | null>(null);
  const [checking, setChecking] = useState(false);
  const [checkError, setCheckError] = useState("");
  const [judgedRegion, setJudgedRegion] = useState("");
  const [question, setQuestion] = useState("");
  const explain = useChatRun(id, "eligibility");
  const qa = useChatRun(id, "notice_qa");

  const setTab = (t: DetailTab) => {
    setTabState(t);
    try {
      const u = new URL(window.location.href);
      u.searchParams.set("tab", t);
      window.history.replaceState(null, "", u);
    } catch {
      /* 주소만 못 바꾼다 */
    }
  };

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

  const judge = useCallback(
    async (f: ProfileForm) => {
      setChecking(true);
      setCheckError("");
      saveProfile(f);
      try {
        const r = await apiFetch(`/api/eligibility/${encodeURIComponent(id)}`, {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({ profile: toApiProfile(f) }),
        });
        const d = await r.json().catch(() => null);
        if (r.ok) {
          setCheck(d as Checks);
          setJudgedRegion(f.region);
        } else setCheckError(r.status === 502 ? "SERVICE_DEGRADED" : errorMessage(d, r.status));
      } catch {
        setCheckError("SERVICE_DEGRADED");
      } finally {
        setChecking(false);
      }
    },
    [id],
  );

  // 탭 사이에서 같은 조건을 쓴다: 공고 찾기에서 넣은 조건으로 바로 판정한다(규칙 평가기만이라 모델 비용이 없다)
  useEffect(() => {
    const p = loadProfile() ?? EMPTY_PROFILE;
    setForm(p);
    void judge(p);
  }, [judge]);

  function rejudge(ev: React.FormEvent) {
    ev.preventDefault();
    void judge(form);
  }
  function ask(ev: React.FormEvent) {
    ev.preventDefault();
    if (question.trim()) qa.start(question.trim(), toChatProfile(form));
  }

  const rows = check?.checks ?? [];
  const allMissing = rows.length > 0 && rows.every((c) => c.my_value.source === "MISSING");
  const evidence = rows.map((c) => c.evidence.text);
  const unparsed = detail?.requirements_status === "unparsed" || check?.result.reasons.includes("REQ_UNPARSED");
  const verdict = check?.result.verdict;

  return (
    <main>
      <div className="muted">
        <Link href="/">← 공고 찾기</Link> · <Link href="/notices">공고 목록</Link>
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
            <span className="row" style={{ marginTop: 0 }}>
              <span className="ex-badge">{detail.is_open ? "모집 중" : "마감"}</span>
              <span className="ex-badge">{REQ_STATUS[detail.requirements_status] ?? detail.requirements_status}</span>
            </span>
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
        </section>
      )}

      {/* 판정 요약 막대: 판정 배지와 조건 개수. 예외 배지(.ex-badge)와 모양이 다르다 */}
      <section className="panel verdict-bar" aria-live="polite">
        {checking && <span className="muted">판정 중…</span>}
        {!checking && check && verdict && (
          <>
            <span className={`badge ${verdict}`}>{VERDICT_MARK[verdict] ?? verdict}</span>{" "}
            <span>
              조건 {rows.length}개: ✓ 충족 {check.by_result.SATISFIED ?? 0} · ✕ 미충족 {check.by_result.UNSATISFIED ?? 0} · ? 모름 {check.by_result.UNKNOWN ?? 0}
            </span>{" "}
            <span className="muted">
              · 내 값 입력 {check.by_source.INPUT ?? 0} · 도출 {check.by_source.DERIVED ?? 0} · 미입력 {check.by_source.MISSING ?? 0}
            </span>
            <div className="muted">{check.meta?.disclaimer ?? DISCLAIMER}</div>
          </>
        )}
        {!checking && checkError && checkError !== "SERVICE_DEGRADED" && <div className="banner">{checkError}</div>}
      </section>
      {checkError === "SERVICE_DEGRADED" && <StatusScreen code="SERVICE_DEGRADED" />}
      {check?.meta?.stale && <StatusScreen code="STALE_DATA" />}

      <div className="row tabs" role="tablist" aria-label="공고 상세">
        {(Object.keys(TAB_LABEL) as DetailTab[]).map((t) => (
          <button key={t} type="button" role="tab" aria-selected={tab === t} className={`tab ${tab === t ? "on" : ""}`} onClick={() => setTab(t)}>
            {TAB_LABEL[t]}
          </button>
        ))}
      </div>

      {tab === "source" && (
        <section className="panel" role="tabpanel">
          <h2>원문</h2>
          <div className="muted">
            정리된 원문 구역입니다. 판정 근거로 쓴 문구는 <mark>표시</mark>합니다. 출처 {SOURCE[detail?.source_system ?? ""] ?? "미상"} · 수집{" "}
            {detail?.fetched_at ? day(detail.fetched_at) : "미상"}
          </div>
          {unparsed && <StatusScreen code="REQ_UNPARSED" />}
          {detail?.attachments && (
            <div className="muted">
              첨부 {s(detail.attachments.count ?? 0)}개
              {detail.attachments.text_extracted != null ? ` · 텍스트 추출 ${s(detail.attachments.text_extracted)}` : ""}
              {detail.attachments.preview_only ? ` · 미리보기만 ${s(detail.attachments.preview_only)}` : ""}
              {detail.attachments.note ? ` · ${detail.attachments.note}` : ""}
            </div>
          )}
          {detail?.contact_text && <div className="meta">문의: {detail.contact_text}</div>}
          {detail && detail.sections.length === 0 && <div className="muted">정리된 원문 구역이 없습니다. 공고 원문 링크에서 확인하세요.</div>}
          {detail?.sections.map((sec, i) => (
            <details key={sec.chunk_id} open={i < 2}>
              <summary>
                {sec.section} <span className="muted">({sec.origin === "ATTACHMENT" ? "첨부" : "API"})</span>
              </summary>
              <div className="chunk-text">{highlight(sec.text, evidence)}</div>
            </details>
          ))}
        </section>
      )}

      {tab === "verify" && (
        <>
          <form className="panel" onSubmit={rejudge}>
            <h2>내 기업 조건</h2>
            <div className="muted">값을 바꾸고 다시 판정하면 아래 표가 바뀝니다. 비워 둔 칸은 &lsquo;모름&rsquo;입니다. {PII_WARNING}</div>
            <ProfileFields form={form} onChange={setForm} />
            <div className="row">
              <button className="primary" disabled={checking}>
                {checking ? "판정 중…" : "다시 판정"}
              </button>
            </div>
          </form>
          {allMissing && <StatusScreen code="INSUFFICIENT_PROFILE" />}
          {unparsed && <StatusScreen code="REQ_UNPARSED" />}
          <section className="panel" role="tabpanel">
            <h2>조건별 검증</h2>
            {rows.length === 0 && !checking && <div className="muted">이 공고에서 자동 판정에 쓰는 조건이 없습니다. 원문 탭에서 자격 요건을 확인하세요.</div>}
            {rows.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>조건</th>
                      <th>공고 요구(근거)</th>
                      <th>내 값</th>
                      <th>값 출처</th>
                      <th>결과</th>
                      <th>판정 이유</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((c) => (
                      <tr key={c.cond_id}>
                        <td>
                          {ATTR[c.attribute] ?? c.attribute}
                          {c.strength === "soft" && <span className="muted"> (참고)</span>}
                        </td>
                        <td>{c.required.label || "—"}</td>
                        <td>{shown(c.my_value.value, c.my_value.field)}</td>
                        <td>
                          <span className={`src ${c.my_value.source}`}>{VALUE_SOURCE[c.my_value.source]}</span>
                        </td>
                        <td>
                          <span className={`badge ${c.result}`}>{STATUS_MARK[c.result] ?? c.result}</span>
                        </td>
                        <td className="ev">{c.reason || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="muted">값 출처: 입력 = 직접 넣은 값, 도출 = 다른 입력에서 계산한 값(개시일 → 업력, 생년월일 → 나이), 미입력 = 값 없음(모름).</div>
          </section>
        </>
      )}

      {tab === "reasoning" && (
        <section className="panel" role="tabpanel">
          <h2>추론 과정</h2>
          <div className="muted">규칙 평가기가 판정한 순서입니다. 모델 설명은 맨 아래에 따로 있고 판정을 바꾸지 않습니다.</div>
          <ol className="steps">
            <li>
              <strong>입력 사실</strong>
              <div className="muted">
                {Object.entries(toApiProfile(form))
                  .filter(([, v]) => v != null)
                  .map(([k, v]) => `${FIELD_LABEL[k] ?? k} ${shown(v, k)}`)
                  .join(" · ") || "입력한 값이 없습니다(모두 모름)."}
              </div>
            </li>
            <li>
              <strong>개념 추론</strong>
              <div className="muted">조건 값과 내 값을 같은 개념(지역 계층·기업 유형)으로 맞춥니다.</div>
              <ul className="why">
                {rows.filter((c) => c.path?.length).map((c) => (
                  <li key={c.cond_id}>
                    {ATTR[c.attribute] ?? c.attribute}: {c.path!.join(" → ")}
                  </li>
                ))}
                {!rows.some((c) => c.path?.length) && <li className="muted">개념 경로가 필요한 조건이 없습니다.</li>}
              </ul>
            </li>
            <li>
              <strong>정의·법령</strong>
              <div className="muted">
                공고 → 요건 → 조건 → 개념 → 정의 → 법령. {judgedRegion ? "내 지역에서 조건 지역으로 가는 경로를 굵게 표시합니다." : "지역을 넣고 판정하면 내 지역 경로가 함께 표시됩니다."}
              </div>
              <PathGraph noticeId={id} region={judgedRegion || undefined} />
            </li>
            <li>
              <strong>조건 평가</strong>
              <ul className="why">
                {rows.map((c) => (
                  <li key={c.cond_id}>
                    {STATUS_MARK[c.result] ?? c.result} {ATTR[c.attribute] ?? c.attribute}: {c.required.label} — {c.reason}
                  </li>
                ))}
              </ul>
            </li>
            <li>
              <strong>판정 합성</strong>
              <div>
                {verdict ? <span className={`badge ${verdict}`}>{VERDICT_MARK[verdict] ?? verdict}</span> : "—"}{" "}
                <span className="muted">
                  필수 조건이 하나라도 미충족이면 조건 미충족, 모르는 필수 조건이 있거나 요건 해석 전이면 확인 필요입니다.
                  {check?.result.reasons.length ? ` 사유: ${check.result.reasons.map((x) => REASON[x] ?? x).join(", ")}` : ""}
                </span>
              </div>
            </li>
          </ol>

          <h2 className="sub">모델 설명(선택)</h2>
          <div className="muted">자격 판정 에이전트가 위 판정을 문장으로 풀어 줍니다. 모델을 부르므로 버튼을 눌렀을 때만 돕니다.</div>
          <div className="row">
            <button type="button" disabled={explain.run.running} onClick={() => explain.start("이 공고에 내 조건으로 신청 자격이 되는지 확인해 줘", toChatProfile(form))}>
              {explain.run.running ? "설명 만드는 중…" : "모델 설명 보기"}
            </button>
            {explain.run.running && (
              <button type="button" onClick={explain.stop}>
                중지
              </button>
            )}
          </div>
          {(explain.run.events.length > 0 || explain.run.running) && (
            <ChatResult events={explain.run.events} turnKey={`elig${explain.run.key}`} running={explain.run.running} showNoticeLink={false} />
          )}
          {explain.run.error && <div className="banner">{explain.run.error}</div>}
        </section>
      )}

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
