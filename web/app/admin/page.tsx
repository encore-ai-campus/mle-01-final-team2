"use client";
// 운영 화면(시스템 상태). /health·/health/llm·/health/graph·/health/index를 카드로 보인다. 상태는 글자로도 적는다(색에만 의존하지 않음).
// 요건 검수 큐는 /admin/reviews. 수집 현황(/admin/runs)은 관리자 로그인(A-01) 뒤에 붙인다.
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { errorMessage, s } from "@/lib/labels";

type Kind = "app" | "llm" | "graph" | "index";
type Result = { loading: boolean; httpOk: boolean; status: number; data: Record<string, unknown> | null; error: string };
type Fact = { label: string; value: string; ok?: boolean };

const KINDS: { kind: Kind; title: string; desc: string }[] = [
  { kind: "app", title: "API 서버", desc: "GET /health · 외부 접속 없이 설정 여부만" },
  { kind: "llm", title: "설명 모델(LLM)", desc: "GET /health/llm · provider 연결과 차단기 상태" },
  { kind: "graph", title: "그래프 DB(Neo4j)", desc: "GET /health/graph · 연결 확인" },
  { kind: "index", title: "검색 색인", desc: "GET /health/index · 밀집 벡터·청크 수" },
];

const yes = (v: unknown) => v === true || v === "ok" || v === "up" || v === "healthy" || v === "closed";

function judge(kind: Kind, r: Result): { ok: boolean; facts: Fact[] } {
  const d = r.data ?? {};
  if (!r.httpOk) return { ok: false, facts: [{ label: "응답", value: r.error || `HTTP ${r.status}`, ok: false }] };
  if (kind === "app") {
    const conf = (d.configured as Record<string, boolean>) ?? {};
    return {
      ok: d.status === "ok",
      facts: [
        { label: "상태", value: s(d.status), ok: d.status === "ok" },
        { label: "환경", value: s(d.environment) },
        ...Object.entries(conf).map(([k, v]) => ({ label: `${k} 설정`, value: v ? "있음" : "없음", ok: !!v })),
      ],
    };
  }
  if (kind === "graph") {
    return {
      ok: !!d.reachable,
      facts: [
        { label: "설정", value: d.configured ? "있음" : "없음", ok: !!d.configured },
        { label: "연결", value: d.reachable ? "닿음" : "닿지 않음", ok: !!d.reachable },
      ],
    };
  }
  if (kind === "index") {
    const chunks = Number(d.chunks ?? 0);
    return {
      ok: chunks > 0,
      facts: [
        { label: "밀집 벡터", value: d.dense ? "켜짐(하이브리드)" : "꺼짐(BM25만)", ok: !!d.dense },
        { label: "청크 수", value: chunks.toLocaleString(), ok: chunks > 0 },
        { label: "임베딩 모델", value: s(d.model) || "없음" },
      ],
    };
  }
  // llm: providers 모양이 provider별 객체 또는 목록일 수 있어 너그럽게 읽는다
  const providers = d.providers;
  const facts: Fact[] = [];
  const list: [string, unknown][] = Array.isArray(providers)
    ? providers.map((p, i) => [s((p as Record<string, unknown>)?.name ?? i), p])
    : Object.entries((providers as Record<string, unknown>) ?? {});
  for (const [name, p] of list) {
    const o = typeof p === "object" && p !== null ? (p as Record<string, unknown>) : { ok: p };
    const ok = yes(o.ok ?? o.reachable ?? o.status ?? o.healthy);
    facts.push({ label: name, value: ok ? "연결됨" : `연결 안 됨${o.error ? ` (${s(o.error)})` : ""}`, ok });
  }
  const roles = d.roles as Record<string, unknown> | undefined;
  if (roles) facts.push({ label: "역할 배정", value: Object.entries(roles).map(([k, v]) => `${k}=${Array.isArray(v) ? v.join("/") : s(v)}`).join(", ") });
  return { ok: facts.some((f) => f.ok), facts: facts.length ? facts : [{ label: "provider", value: "설정 없음", ok: false }] };
}

export default function AdminPage() {
  const [res, setRes] = useState<Record<Kind, Result>>(() => {
    const init = { loading: true, httpOk: false, status: 0, data: null, error: "" };
    return { app: init, llm: init, graph: init, index: init };
  });
  const [checkedAt, setCheckedAt] = useState("");

  const refresh = useCallback(() => {
    setCheckedAt(new Date().toLocaleString("ko-KR"));
    for (const { kind } of KINDS) {
      setRes((r) => ({ ...r, [kind]: { ...r[kind], loading: true } }));
      fetch(`/api/health/${kind}`)
        .then(async (r) => {
          const d = await r.json().catch(() => null);
          setRes((x) => ({ ...x, [kind]: { loading: false, httpOk: r.ok, status: r.status, data: d, error: r.ok ? "" : errorMessage(d, r.status) } }));
        })
        .catch(() => setRes((x) => ({ ...x, [kind]: { loading: false, httpOk: false, status: 0, data: null, error: "Next 서버에 닿지 않습니다." } })));
    }
  }, []);

  useEffect(() => refresh(), [refresh]);

  return (
    <main>
      <h1>운영 · 시스템 상태</h1>
      <div className="muted">
        주소·키는 보이지 않고 이름과 상태만 보입니다. 확인 시각 {checkedAt || "-"}{" "}
        <button type="button" className="link" onClick={refresh}>
          다시 확인
        </button>
        {" · "}
        <Link href="/admin/reviews">요건 검수 큐</Link>
      </div>
      <div className="status-grid">
        {KINDS.map(({ kind, title, desc }) => {
          const r = res[kind];
          const j = r.loading ? null : judge(kind, r);
          return (
            <section className="panel" key={kind}>
              <div className="card-head">
                <h2>{title}</h2>
                {r.loading ? (
                  <span className="badge">확인 중</span>
                ) : (
                  <span className={`badge ${j!.ok ? "SATISFIED" : "UNSATISFIED"}`}>{j!.ok ? "정상" : "이상"}</span>
                )}
              </div>
              <div className="meta">{desc}</div>
              {j && (
                <table>
                  <tbody>
                    {j.facts.map((f, i) => (
                      <tr key={i}>
                        <th>{f.label}</th>
                        <td>
                          {f.ok === undefined ? null : <span className={f.ok ? "st-ok" : "st-bad"}>{f.ok ? "● 정상" : "○ 이상"} </span>}
                          {f.value}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              {r.data && (
                <details>
                  <summary className="muted">응답 원문(JSON)</summary>
                  <pre>{JSON.stringify(r.data, null, 2)}</pre>
                </details>
              )}
            </section>
          );
        })}
      </div>
      <div className="muted">수집 현황·검수 큐·감사 로그는 관리자 로그인(A-01)이 붙은 뒤 이 화면에 더합니다.</div>
    </main>
  );
}
