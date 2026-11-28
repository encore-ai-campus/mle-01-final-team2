"use client";
// SCR-01 공고 목록: 검색어·출처·마감 포함 필터와 페이지. 판정은 하지 않는다(판정은 상세 화면이나 홈에서).
import { useCallback, useEffect, useState } from "react";

import { day, errorMessage, s, SOURCE } from "@/lib/labels";
import { apiFetch } from "@/lib/auth";

type NoticeSummary = {
  notice_id: string;
  source_system: string;
  title: string;
  organization: string | null;
  category: string | null;
  deadline: string | null;
  is_open: boolean;
  detail_url: string | null;
  fetched_at: string | null;
};
type ListResp = { items: NoticeSummary[]; page: number; size: number; total: number };
type Filter = { q: string; source: string; include_closed: boolean; page: number };

const SIZE = 20;

export default function NoticesPage() {
  const [draft, setDraft] = useState({ q: "", source: "", include_closed: false });
  const [filter, setFilter] = useState<Filter>({ q: "", source: "", include_closed: false, page: 1 });
  const [resp, setResp] = useState<ListResp | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async (f: Filter, signal: AbortSignal) => {
    setLoading(true);
    setError("");
    const qs = new URLSearchParams({ page: String(f.page), size: String(SIZE) });
    if (f.q.trim()) qs.set("q", f.q.trim());
    if (f.source) qs.set("source", f.source);
    if (f.include_closed) qs.set("include_closed", "true");
    try {
      const r = await apiFetch(`/api/notices?${qs}`, { signal });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setResp(null);
        setError(errorMessage(d, r.status));
      } else setResp(d as ListResp);
    } catch (e) {
      if ((e as Error).name !== "AbortError") setError("API 서버에 닿지 않습니다.");
    } finally {
      if (!signal.aborted) setLoading(false);
    }
  }, []);

  useEffect(() => {
    const ctl = new AbortController();
    load(filter, ctl.signal);
    return () => ctl.abort();
  }, [filter, load]);

  const pages = resp ? Math.max(1, Math.ceil(resp.total / (resp.size || SIZE))) : 1;
  const go = (page: number) => {
    setFilter((f) => ({ ...f, page }));
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  return (
    <main>
      <h1>공고 목록</h1>
      <div className="muted">K-Startup·기업마당에서 수집한 공고입니다. 카드를 누르면 원문 구역·내 조건 판정·경로 그래프를 볼 수 있습니다.</div>

      <form
        className="panel"
        onSubmit={(e) => {
          e.preventDefault();
          setFilter({ ...draft, page: 1 });
        }}
      >
        <div className="grid">
          <label>
            검색어
            <input value={draft.q} onChange={(e) => setDraft((d) => ({ ...d, q: e.target.value }))} maxLength={100} placeholder="예: 창업, 수출, 서울" />
          </label>
          <label>
            출처
            <select value={draft.source} onChange={(e) => setDraft((d) => ({ ...d, source: e.target.value }))}>
              <option value="">전체</option>
              <option value="KSTARTUP">K-Startup</option>
              <option value="BIZINFO">기업마당</option>
            </select>
          </label>
          <label className="check">
            <input type="checkbox" checked={draft.include_closed} onChange={(e) => setDraft((d) => ({ ...d, include_closed: e.target.checked }))} /> 마감 공고 포함
          </label>
        </div>
        <div className="row">
          <button className="primary" disabled={loading}>
            {loading ? "찾는 중…" : "검색"}
          </button>
          {resp && (
            <span className="muted">
              {resp.total.toLocaleString()}건 · {resp.page}/{pages}쪽
            </span>
          )}
        </div>
      </form>

      {error && <div className="banner">{error}</div>}
      {resp && resp.items.length === 0 && <div className="panel muted">조건에 맞는 공고가 없습니다. 검색어를 줄이거나 마감 공고 포함을 켜 보세요.</div>}

      <div className="notice-list">
        {resp?.items.map((n) => (
          <section className="panel notice-card" key={n.notice_id}>
            <div className="card-head">
              <h2>
                <a href={`/notices/${encodeURIComponent(n.notice_id)}`}>{n.title}</a>
              </h2>
              <span className={`badge ${n.is_open ? "SATISFIED" : "UNSATISFIED"}`}>{n.is_open ? "모집 중" : "마감"}</span>
            </div>
            <div className="meta">
              {n.organization ?? "기관 미상"}
              {n.category ? ` · ${n.category}` : ""} · 마감 {n.deadline ?? "상시·미정"}
              <br />
              출처 {SOURCE[n.source_system] ?? n.source_system} · 수집 {n.fetched_at ? day(n.fetched_at) : "미상"} · {s(n.notice_id)}
              {n.detail_url ? (
                <>
                  {" · "}
                  <a href={n.detail_url} target="_blank" rel="noreferrer">
                    공고 원문
                  </a>
                </>
              ) : null}
            </div>
          </section>
        ))}
      </div>

      {resp && pages > 1 && (
        <div className="row pager">
          <button type="button" onClick={() => go(1)} disabled={loading || filter.page <= 1}>
            처음
          </button>
          <button type="button" onClick={() => go(filter.page - 1)} disabled={loading || filter.page <= 1}>
            이전
          </button>
          <span className="muted">
            {filter.page} / {pages}
          </span>
          <button type="button" onClick={() => go(filter.page + 1)} disabled={loading || filter.page >= pages}>
            다음
          </button>
          <button type="button" onClick={() => go(pages)} disabled={loading || filter.page >= pages}>
            끝
          </button>
        </div>
      )}
    </main>
  );
}
