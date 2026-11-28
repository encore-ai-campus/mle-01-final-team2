"use client";
// 요건 검수 큐 목록(B-3 ②, docs/DESIGN_요건검수큐_v0.1.md). 우선순위 순(모집 중 → 마감 임박 → 마감일). 관리자만 쓴다.
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { errorMessage } from "@/lib/labels";
import { apiFetch } from "@/lib/auth";

type Item = {
  notice_id: string;
  title: string;
  source_system: string;
  is_open: boolean;
  deadline: string | null;
  priority_rank: number;
  priority_reasons: string[];
  review_status: string;
  adjudication_status: string;
  reviewer: string | null;
  stale_source: boolean;
  n_prefill: number;
  n_conditions: number;
};
type ListRes = { total: number; counts: Record<string, number>; stale: number; items: Item[] };

const STATUS: Record<string, string> = { UNREVIEWED: "검수 전", NEEDS_REVIEW: "작업 중", VERIFIED: "검수 완료" };
const STATUS_CLASS: Record<string, string> = { UNREVIEWED: "", NEEDS_REVIEW: "NEEDS_CHECK", VERIFIED: "ELIGIBLE" };
const PAGE = 30;

export default function ReviewListPage() {
  const [status, setStatus] = useState("");
  const [source, setSource] = useState("");
  const [openOnly, setOpenOnly] = useState(true);
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<ListRes | null>(null);
  const [error, setError] = useState("");
  const [ingest, setIngest] = useState("");

  const load = useCallback(() => {
    const p = new URLSearchParams({ offset: String(offset), limit: String(PAGE) });
    if (status) p.set("status", status);
    if (source) p.set("source", source);
    if (openOnly) p.set("open_only", "true");
    if (q.trim()) p.set("q", q.trim());
    setError("");
    apiFetch(`/api/admin/reviews?${p}`)
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(errorMessage(d, r.status));
        setData(d);
      })
      .catch((e: Error) => {
        setData(null);
        setError(e.message);
      });
  }, [status, source, openOnly, q, offset]);

  useEffect(() => load(), [load]);

  const runIngest = async () => {
    setIngest("반영 중…");
    const r = await apiFetch("/api/admin/reviews/ingest", { method: "POST" });
    const d = await r.json().catch(() => null);
    if (!r.ok) return setIngest(errorMessage(d, r.status));
    setIngest(`검수 완료 ${d.verified}건 중 ${d.applied}건 반영, ${d.rejected?.length ?? 0}건 거절. ${d.note}`);
  };

  const counts = data?.counts ?? {};
  return (
    <main>
      <h1>운영 · 요건 검수 큐</h1>
      <div className="muted">
        자동으로 해석하지 못한 자격 요건(REQ_UNPARSED)을 사람이 조건으로 옮깁니다. 사전 채움 후보는 규칙이 찾은 것이라 판정에 쓰지 않습니다.{" "}
        <Link href="/admin">시스템 상태로</Link>
      </div>
      <section className="panel">
        <div className="row" style={{ marginTop: 0 }}>
          {["", "UNREVIEWED", "NEEDS_REVIEW", "VERIFIED"].map((k) => (
            <button key={k} type="button" className={status === k ? "primary" : ""} onClick={() => (setStatus(k), setOffset(0))}>
              {k ? STATUS[k] : "전체"} {k ? (counts[k] ?? 0).toLocaleString() : ""}
            </button>
          ))}
          {data && data.stale > 0 && <span className="badge NEEDS_CHECK">원문 바뀜 {data.stale}건</span>}
        </div>
        <div className="row">
          <select value={source} onChange={(e) => (setSource(e.target.value), setOffset(0))} aria-label="출처">
            <option value="">출처 전체</option>
            <option value="BIZINFO">기업마당</option>
            <option value="KSTARTUP">K-Startup</option>
          </select>
          <label style={{ flexDirection: "row", alignItems: "center" }}>
            <input type="checkbox" checked={openOnly} onChange={(e) => (setOpenOnly(e.target.checked), setOffset(0))} /> 모집 중만
          </label>
          <input placeholder="공고명·ID 검색" value={q} onChange={(e) => (setQ(e.target.value), setOffset(0))} aria-label="검색" />
          <span style={{ flex: 1 }} />
          <button type="button" onClick={runIngest} title="검수 완료(VERIFIED) 공고를 판정 입력으로 내보냅니다">
            판정에 반영(ingest)
          </button>
        </div>
        {ingest && <div className="banner">{ingest}</div>}
        {error && (
          <div className="banner">
            {error} <Link href="/login">로그인</Link>
          </div>
        )}
        {data && (
          <>
            <div className="muted" style={{ marginTop: 8 }}>
              {data.total.toLocaleString()}건 중 {data.total ? offset + 1 : 0}–{Math.min(offset + PAGE, data.total)}
            </div>
            <table className="review-list">
              <thead>
                <tr>
                  <th>순위</th>
                  <th>공고</th>
                  <th>마감</th>
                  <th>후보</th>
                  <th>조건</th>
                  <th>상태</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((it) => (
                  <tr key={it.notice_id}>
                    <td>{it.priority_rank}</td>
                    <td>
                      <Link href={`/admin/reviews/${encodeURIComponent(it.notice_id)}`}>{it.title || it.notice_id}</Link>
                      <div className="muted">
                        {it.source_system} · {it.priority_reasons.join(", ")}
                      </div>
                    </td>
                    <td>{it.deadline ?? "-"}</td>
                    <td>{it.n_prefill}</td>
                    <td>{it.n_conditions}</td>
                    <td>
                      <span className={`badge ${STATUS_CLASS[it.review_status] ?? ""}`}>{STATUS[it.review_status] ?? it.review_status}</span>
                      {it.stale_source && <div className="badge NEEDS_CHECK">원문 바뀜</div>}
                      {it.reviewer && <div className="muted">{it.reviewer}</div>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="row">
              <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                이전
              </button>
              <button type="button" disabled={offset + PAGE >= data.total} onClick={() => setOffset(offset + PAGE)}>
                다음
              </button>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
