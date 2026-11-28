"use client";
// SCR-06 운영 현황 패널(M-01 GET /api/admin/status): 운영 지표 · 출처별 수집 상태 · 재처리·검수 큐 · 기간 상태 · 관측.
// 값이 없는 칸(null)은 '연결 전'으로 적는다: 수집 실행 기록(ingest_runs)·Langfuse가 아직 붙지 않았다.
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import StatusScreen from "@/components/StatusScreen";
import { apiFetch } from "@/lib/auth";
import { SOURCE, day, errorMessage } from "@/lib/labels";

type Src = {
  source: string;
  in_service: number;
  last_success_at: string | null;
  last_run: { run_id: string | null; status: string | null; fetched: number | null; new: number | null; changed: number | null; failed: number | null } | null;
  stale: boolean;
};
type Status = {
  checked_at: string;
  notices: number;
  sources: Src[];
  queues: { review_pending: number; review_done: number; review_total: number; reprocess_pending: number; reprocess_by_status: Record<string, number>; unparsed: number };
  period_status: Record<string, number>;
  observability: { langfuse_url: string | null; gpu_running: boolean | null };
  notes: string[];
};

const PERIOD: Record<string, string> = { open_with_deadline: "모집 중(마감일 있음)", open_no_date: "모집 중(상시·미정)", closed: "마감", other: "기타" };
const v = (x: number | null | undefined) => (x == null ? "연결 전" : x.toLocaleString());

export default function OpsStatus() {
  const [st, setSt] = useState<Status | null>(null);
  const [code, setCode] = useState(0);
  const [err, setErr] = useState("");

  const load = useCallback(() => {
    setErr("");
    apiFetch("/api/admin/status")
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        setCode(r.status);
        if (r.ok) setSt(d as Status);
        else setErr(errorMessage(d, r.status));
      })
      .catch(() => setErr("Next 서버에 닿지 않습니다."));
  }, []);
  useEffect(() => load(), [load]);

  if (code === 401 || code === 403) return <StatusScreen code="ROLE_DENIED" />;
  if (err) return <div className="banner">운영 현황을 불러오지 못했습니다: {err}</div>;
  if (!st) return <div className="muted">운영 현황을 불러오는 중…</div>;
  const stale = st.sources.some((x) => x.stale);

  return (
    <>
      {stale && <StatusScreen code="STALE_DATA" detail="수집이 기준 시간보다 늦은 출처가 있습니다. 아래 출처별 수집 상태를 보세요." />}
      <section className="panel">
        <div className="card-head">
          <h2>운영 지표</h2>
          <span className="muted">
            확인 {day(st.checked_at)}{" "}
            <button type="button" className="link" onClick={load}>
              다시 확인
            </button>
          </span>
        </div>
        <div className="kpis">
          <div className="kpi">
            <div className="muted">서비스 중 공고</div>
            <strong>{st.notices.toLocaleString()}</strong>
          </div>
          <div className="kpi">
            <div className="muted">검수 대기</div>
            <strong>{st.queues.review_pending.toLocaleString()}</strong>
            <div className="muted">완료 {st.queues.review_done.toLocaleString()} / {st.queues.review_total.toLocaleString()}</div>
          </div>
          <div className="kpi">
            <div className="muted">재처리 대기(첨부 추출 실패)</div>
            <strong>{st.queues.reprocess_pending.toLocaleString()}</strong>
          </div>
          <div className="kpi">
            <div className="muted">요건 해석 전</div>
            <strong>{st.queues.unparsed.toLocaleString()}</strong>
          </div>
        </div>
        <div className="row">
          <button type="button" disabled title="공고 업데이트 실행(M-02)은 수집 실행 기록 표가 정해진 뒤 붙습니다">
            공고 업데이트 실행
          </button>
          <Link href="/admin/reviews">요건 검수 큐로</Link>
        </div>
      </section>

      <section className="panel">
        <h2>출처별 수집 상태</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>출처</th>
                <th>서비스 중</th>
                <th>마지막 성공</th>
                <th>마지막 실행</th>
                <th>가져옴</th>
                <th>신규</th>
                <th>변경</th>
                <th>실패</th>
                <th>상태</th>
              </tr>
            </thead>
            <tbody>
              {st.sources.map((x) => (
                <tr key={x.source}>
                  <td>{SOURCE[x.source] ?? x.source}</td>
                  <td>{x.in_service.toLocaleString()}</td>
                  <td>{x.last_success_at ? day(x.last_success_at) : "기록 없음"}</td>
                  <td>{x.last_run?.run_id ?? "—"}</td>
                  <td>{v(x.last_run?.fetched)}</td>
                  <td>{v(x.last_run?.new)}</td>
                  <td>{v(x.last_run?.changed)}</td>
                  <td>{v(x.last_run?.failed)}</td>
                  <td>{x.stale ? <span className="st-bad">○ 늦음</span> : <span className="st-ok">● 정상</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <div className="status-grid">
        <section className="panel">
          <h2>재처리 큐</h2>
          <table>
            <tbody>
              {Object.entries(st.queues.reprocess_by_status).map(([k, n]) => (
                <tr key={k}>
                  <th>{k}</th>
                  <td>{n.toLocaleString()}</td>
                </tr>
              ))}
              {!Object.keys(st.queues.reprocess_by_status).length && (
                <tr>
                  <td className="muted">추출 실패 첨부가 없습니다.</td>
                </tr>
              )}
            </tbody>
          </table>
        </section>
        <section className="panel">
          <h2>기간 상태</h2>
          <table>
            <tbody>
              {Object.entries(st.period_status).map(([k, n]) => (
                <tr key={k}>
                  <th>{PERIOD[k] ?? k}</th>
                  <td>{n.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
        <section className="panel">
          <h2>관측</h2>
          <table>
            <tbody>
              <tr>
                <th>Langfuse</th>
                <td>{st.observability.langfuse_url ? <a href={st.observability.langfuse_url}>열기</a> : "연결 전"}</td>
              </tr>
              <tr>
                <th>GPU(vLLM)</th>
                <td>{st.observability.gpu_running == null ? "연결 전" : st.observability.gpu_running ? "● 켜짐" : "○ 꺼짐"}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
      {st.notes.length > 0 && (
        <ul className="muted">
          {st.notes.map((n, i) => (
            <li key={i}>{n}</li>
          ))}
        </ul>
      )}
    </>
  );
}
