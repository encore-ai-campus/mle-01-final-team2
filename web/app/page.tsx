"use client";
// SCR-01 공고 찾기(/): 내 기업 조건 → 버튼 판정(POST /api/eligibility, 모델·Router 없이 규칙 평가기만) → 3값 공고 카드.
// 카드의 행동은 공고 상세(SCR-02)의 원문·조건별 검증·추론 과정 탭으로 이어진다. 화면설계서 v3.5 §5 SCR-01.
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import ProfileFields from "@/components/ProfileFields";
import StatusScreen from "@/components/StatusScreen";
import { apiFetch } from "@/lib/auth";
import { ATTR, REASON, SOURCE, VERDICT_MARK, day, errorMessage } from "@/lib/labels";
import { EMPTY_PROFILE, hasPII, loadProfile, saveProfile, toApiProfile, type ProfileForm } from "@/lib/profile";

type Cond = { cond_id: string; attribute: string; status: string; strength: string; reason: string };
type Result = {
  notice_id: string;
  verdict: string;
  reasons: string[];
  conditions: Cond[];
  score: number | null;
  title: string | null;
  source: string | null;
  detail_url: string | null;
  deadline: string | null;
  fetched_at: string | null;
};
type Resp = { evaluated: number; candidates: number; counts: Record<string, number>; results: Result[]; meta?: { stale?: boolean } };
type Tab = "ALL" | "ELIGIBLE" | "NEEDS_CHECK" | "NOT_ELIGIBLE";

const TABS: { key: Tab; label: string }[] = [
  { key: "ALL", label: "전체" },
  { key: "ELIGIBLE", label: "✓ 조건 충족" },
  { key: "NEEDS_CHECK", label: "? 확인 필요" },
  { key: "NOT_ELIGIBLE", label: "✕ 조건 미충족" },
];
const TOP = 50;

/** 판정을 가른 사유: 미충족 조건 → 모르는 조건 → 공고 단위 사유 순 */
function decisive(r: Result): string[] {
  const bad = r.conditions.filter((c) => c.status === "UNSATISFIED").map((c) => `${ATTR[c.attribute] ?? c.attribute}: ${c.reason}`);
  const unknown = r.conditions.filter((c) => c.status === "UNKNOWN" && c.strength === "hard").map((c) => `${ATTR[c.attribute] ?? c.attribute}: ${c.reason}`);
  const why = r.reasons.map((x) => REASON[x] ?? x);
  return [...bad, ...unknown, ...why].slice(0, 3);
}

export default function FindPage() {
  const [form, setForm] = useState<ProfileForm>(EMPTY_PROFILE);
  const [query, setQuery] = useState("");
  const [source, setSource] = useState("");
  const [includeClosed, setIncludeClosed] = useState(false);
  const [resp, setResp] = useState<Resp | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<{ code: "PII_BLOCKED" | "SERVICE_DEGRADED" | null; message: string }>({ code: null, message: "" });
  const [tab, setTab] = useState<Tab>("ALL");
  const [sort, setSort] = useState<"relevance" | "deadline">("relevance");

  useEffect(() => {
    const p = loadProfile();
    if (p) setForm(p);
  }, []);

  async function find(ev?: React.FormEvent) {
    ev?.preventDefault();
    if (hasPII(query)) {
      setError({ code: "PII_BLOCKED", message: "" });
      return;
    }
    setRunning(true);
    setError({ code: null, message: "" });
    saveProfile(form);
    try {
      const r = await apiFetch("/api/eligibility", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ profile: toApiProfile(form), question: query, top: TOP, include_closed: includeClosed, source: source || null }),
      });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setResp(null);
        setError({ code: r.status === 502 ? "SERVICE_DEGRADED" : null, message: errorMessage(d, r.status) });
        return;
      }
      setResp(d as Resp);
      setTab("ALL");
    } catch {
      setError({ code: "SERVICE_DEGRADED", message: "" });
    } finally {
      setRunning(false);
    }
  }

  const shown = useMemo(() => {
    const rows = (resp?.results ?? []).filter((r) => tab === "ALL" || r.verdict === tab);
    if (sort === "deadline") return [...rows].sort((a, b) => (a.deadline ?? "9999").localeCompare(b.deadline ?? "9999"));
    return rows;
  }, [resp, tab, sort]);
  const listed = (v: Tab) => (resp?.results ?? []).filter((r) => v === "ALL" || r.verdict === v).length;

  return (
    <main>
      <h1>공고 찾기</h1>
      <div className="muted">
        조건을 넣고 찾기를 누르면 규칙 평가기가 모집 중 공고를 판정합니다(모델을 쓰지 않습니다). 결과는 참고용이며 신청 가능을 보장하지 않습니다.{" "}
        <Link href="/chat">챗봇으로 묻기</Link>
      </div>

      <div className="row tabs" role="tablist" aria-label="공고 유형">
        <button type="button" role="tab" aria-selected="true" className="tab on">
          지원사업
        </button>
        <button type="button" role="tab" aria-selected="false" className="tab" disabled title="나라장터 입찰공고 판정은 P1(SCR-01-1)입니다">
          입찰공고(준비 중)
        </button>
      </div>

      <form className="panel" onSubmit={find}>
        <div className="card-head">
          <h2>내 기업 조건</h2>
          <span className="row" style={{ marginTop: 0 }}>
            <button type="button" className="link" disabled title="조건 저장은 저장 동의·저장소(P-01)가 정해진 뒤 붙습니다">
              저장 조건 불러오기
            </button>
            <button type="button" className="link" disabled title="조건 저장은 저장 동의·저장소(P-01)가 정해진 뒤 붙습니다">
              이 조건 저장
            </button>
            <button type="button" className="link" onClick={() => setForm(EMPTY_PROFILE)}>
              비우기
            </button>
          </span>
        </div>
        <div className="muted">비워 둔 칸은 &lsquo;모름&rsquo;입니다. 조건은 이 브라우저 탭에만 남고 서버에 저장하지 않습니다.</div>
        <ProfileFields form={form} onChange={setForm} />
        <div className="grid">
          <label>
            검색어(공고명·내용)
            <input value={query} onChange={(e) => setQuery(e.target.value)} maxLength={500} placeholder="비우면 판정만" />
          </label>
          <label>
            출처
            <select value={source} onChange={(e) => setSource(e.target.value)}>
              <option value="">전체</option>
              <option value="BIZINFO">기업마당</option>
              <option value="KSTARTUP">K-Startup</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={includeClosed} onChange={(e) => setIncludeClosed(e.target.checked)} /> 마감 공고 포함
          </label>
        </div>
        <div className="row">
          <button className="primary" disabled={running}>
            {running ? "판정 중…" : "맞는 공고 찾기"}
          </button>
          <span className="muted">사업자번호·주민번호·연락처 같은 식별 정보는 입력하지 마세요.</span>
        </div>
      </form>

      {error.code && <StatusScreen code={error.code} />}
      {!error.code && error.message && <div className="banner">{error.message}</div>}
      {resp?.meta?.stale && <StatusScreen code="STALE_DATA" />}

      {resp && (
        <section className="panel">
          <div>
            판정한 공고 {resp.evaluated.toLocaleString()}건 ·{" "}
            {Object.entries(resp.counts)
              .map(([k, v]) => `${VERDICT_MARK[k] ?? k} ${v.toLocaleString()}`)
              .join(" · ")}
          </div>
          <div className="muted">아래에는 관련도가 높은 {resp.results.length}건을 보입니다(최대 {TOP}건). 신청 불가 공고는 판정 사유만 보입니다.</div>
          <div className="row" role="tablist" aria-label="판정 결과">
            {TABS.map((t) => (
              <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} className={`tab ${tab === t.key ? "on" : ""}`} onClick={() => setTab(t.key)}>
                {t.label} {listed(t.key)}
              </button>
            ))}
            <label className="check" style={{ marginLeft: "auto" }}>
              정렬
              <select value={sort} onChange={(e) => setSort(e.target.value as "relevance" | "deadline")}>
                <option value="relevance">관련순</option>
                <option value="deadline">마감순</option>
              </select>
            </label>
          </div>
        </section>
      )}

      {resp && resp.results.length === 0 && <StatusScreen code="NO_MATCH" />}

      <div className="notice-list">
        {shown.map((r) => {
          const c = r.conditions;
          const sat = c.filter((x) => x.status === "SATISFIED").length;
          const bad = c.filter((x) => x.status === "UNSATISFIED").length;
          const unk = c.filter((x) => x.status === "UNKNOWN").length;
          const href = (t: string) => `/notices/${encodeURIComponent(r.notice_id)}?tab=${t}`;
          return (
            <section className="panel notice-card" key={r.notice_id}>
              <div className="card-head">
                <h2>
                  <Link href={href("source")}>{r.title || r.notice_id}</Link>
                </h2>
                <span className={`badge ${r.verdict}`}>{VERDICT_MARK[r.verdict] ?? r.verdict}</span>
              </div>
              <div className="meta">
                출처 {SOURCE[r.source ?? ""] ?? r.source ?? "미상"} · 수집 {r.fetched_at ? day(r.fetched_at) : "미상"} · 마감 {r.deadline ?? "기간 확인"}
                {r.detail_url && (
                  <>
                    {" · "}
                    <a href={r.detail_url} target="_blank" rel="noreferrer">
                      원본 사이트
                    </a>
                  </>
                )}
              </div>
              <div className="muted">
                조건 {c.length}개: ✓ 충족 {sat} · ✕ 미충족 {bad} · ? 모름 {unk}
              </div>
              {decisive(r).length > 0 && (
                <ul className="why">
                  {decisive(r).map((x, i) => (
                    <li key={i}>{x}</li>
                  ))}
                </ul>
              )}
              <div className="row">
                <Link href={href("source")}>원문 보기</Link>
                <Link href={href("verify")}>조건별 검증</Link>
                <Link href={href("reasoning")}>추론 과정</Link>
                <button type="button" className="link" disabled title={r.verdict === "NOT_ELIGIBLE" ? "조건 미충족 공고는 신청 문서를 만들 수 없습니다" : "신청 문서 초안(SCR-03)은 P1입니다"}>
                  신청 문서 작성
                </button>
              </div>
            </section>
          );
        })}
      </div>
    </main>
  );
}
