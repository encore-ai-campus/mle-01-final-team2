"use client";
// 판정 경로 서브그래프(GET /api/graph/path)를 SVG로 그린다. 종류별 열 배치: 공고 → 요건 → 조건 → 개념 → 정의 → 조문 → 법령.
// 끊긴 구간(사용자 지역에서 닿지 않음·법령 미보유)은 점선과 글자로 표시한다(색에만 의존하지 않음).
import { useEffect, useState } from "react";

import { errorMessage, s } from "@/lib/labels";
import { apiFetch } from "@/lib/auth";

type GNode = { id: string; kind: string; label: string; broken?: boolean; user?: boolean; needs_review?: boolean; [k: string]: unknown };
type GEdge = { from: string; to: string; type: string; highlight?: boolean; broken?: boolean };
type Subgraph = { nodes: GNode[]; edges: GEdge[] };

const COLUMN: Record<string, number> = { Notice: 0, Requirement: 1, Condition: 2, Concept: 3, Definition: 4, ExternalLaw: 6 };
const KIND: Record<string, string> = {
  Notice: "공고",
  Requirement: "요건",
  Condition: "조건",
  Concept: "개념",
  Definition: "정의",
  LawArticle: "조문",
  ExternalLaw: "법령",
  Missing: "미보유",
};
const REL: Record<string, string> = {
  HAS_REQUIREMENT: "요건",
  HAS_CONDITION: "조건",
  ABOUT: "대상",
  WITHIN: "포함됨",
  MEMBER_OF: "소속",
  IS_A: "종류",
  DEFINED_BY: "정의",
  CITES_LAW: "근거 법령",
  PART_OF: "소속 법령",
  MISSING: "미보유",
};

const W = 168;
const H = 44;
const GAP_X = 56;
const GAP_Y = 14;
const PAD = 16;

const cut = (t: string, n = 13) => (t.length > n ? `${t.slice(0, n - 1)}…` : t);

export default function PathGraph({ noticeId, region, reloadKey = 0 }: { noticeId: string; region?: string; reloadKey?: number }) {
  const [state, setState] = useState<{ loading: boolean; error: string; g: Subgraph | null }>({ loading: true, error: "", g: null });

  useEffect(() => {
    const ctl = new AbortController();
    setState({ loading: true, error: "", g: null });
    const qs = new URLSearchParams({ notice_id: noticeId, ...(region ? { region } : {}) });
    apiFetch(`/api/graph/path?${qs}`, { signal: ctl.signal })
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (r.status === 503) setState({ loading: false, error: "그래프 DB가 꺼져 있거나 닿지 않습니다. 판정과 요건 카드는 그래프 없이도 그대로 볼 수 있습니다.", g: null });
        else if (!r.ok) setState({ loading: false, error: errorMessage(d, r.status), g: null });
        else setState({ loading: false, error: "", g: d as Subgraph });
      })
      .catch((e) => {
        if ((e as Error).name !== "AbortError") setState({ loading: false, error: "그래프를 불러오지 못했습니다.", g: null });
      });
    return () => ctl.abort();
  }, [noticeId, region, reloadKey]);

  if (state.loading) return <div className="muted">경로 그래프를 불러오는 중…</div>;
  if (state.error) return <div className="banner">{state.error}</div>;
  if (!state.g || state.g.nodes.length === 0) return <div className="muted">그릴 경로가 없습니다.</div>;
  return <GraphSvg g={state.g} />;
}

function GraphSvg({ g }: { g: Subgraph }) {
  // 조문이 없는 정의에는 '법령 미보유' 점선 노드를 붙인다(CHAIN_BROKEN)
  const nodes: GNode[] = [...g.nodes];
  const edges: GEdge[] = [...g.edges];
  for (const n of g.nodes) {
    if (n.kind === "Definition" && !g.edges.some((e) => e.from === n.id && e.type === "CITES_LAW")) {
      const id = `missing:${n.id}`;
      nodes.push({ id, kind: "Missing", label: "법령 미보유", broken: true });
      edges.push({ from: n.id, to: id, type: "MISSING", broken: true });
    }
  }
  const col = (n: GNode) => (n.kind === "Missing" ? 5 : COLUMN[n.kind] ?? 5);
  const columns = new Map<number, GNode[]>();
  for (const n of nodes) columns.set(col(n), [...(columns.get(col(n)) ?? []), n]);
  const used = [...columns.keys()].sort((a, b) => a - b);
  const pos = new Map<string, { x: number; y: number }>();
  let maxRows = 0;
  used.forEach((c, ci) => {
    const list = columns.get(c)!;
    maxRows = Math.max(maxRows, list.length);
    list.forEach((n, ri) => pos.set(n.id, { x: PAD + ci * (W + GAP_X), y: PAD + 22 + ri * (H + GAP_Y) }));
  });
  const width = PAD * 2 + used.length * W + (used.length - 1) * GAP_X;
  const height = PAD * 2 + 22 + maxRows * (H + GAP_Y);
  const byId = new Map(nodes.map((n) => [n.id, n]));

  return (
    <div className="graph">
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} role="img" aria-label="판정 경로 그래프">
        <defs>
          <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M0,0 L10,5 L0,10 z" fill="var(--muted)" />
          </marker>
        </defs>
        {used.map((c, ci) => (
          <text key={c} x={PAD + ci * (W + GAP_X)} y={PAD + 8} className="g-col">
            {KIND[columns.get(c)![0].kind] ?? columns.get(c)![0].kind}
          </text>
        ))}
        {edges.map((e, i) => {
          const a = pos.get(e.from);
          const b = pos.get(e.to);
          if (!a || !b) return null;
          const broken = e.broken || byId.get(e.to)?.broken;
          let d: string;
          let lx: number, ly: number;
          if (a.x === b.x) {
            // 같은 열(지역 계층 WITHIN 등): 오른쪽으로 휘는 곡선
            const x = a.x + W;
            d = `M${x},${a.y + H / 2} C${x + 40},${a.y + H / 2} ${x + 40},${b.y + H / 2} ${x},${b.y + H / 2}`;
            lx = x + 30;
            ly = (a.y + b.y) / 2 + H / 2;
          } else {
            const x1 = a.x + W, y1 = a.y + H / 2, x2 = b.x, y2 = b.y + H / 2;
            const mx = (x1 + x2) / 2;
            d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
            lx = mx;
            ly = (y1 + y2) / 2 - 3;
          }
          return (
            <g key={i} className={`g-edge${e.highlight ? " hl" : ""}${broken ? " broken" : ""}`}>
              <path d={d} markerEnd="url(#arrow)" />
              {(e.highlight || broken) && (
                <text x={lx} y={ly} textAnchor="middle">
                  {REL[e.type] ?? e.type}
                </text>
              )}
              <title>{`${byId.get(e.from)?.label ?? e.from} —${REL[e.type] ?? e.type}→ ${byId.get(e.to)?.label ?? e.to}`}</title>
            </g>
          );
        })}
        {nodes.map((n) => {
          const p = pos.get(n.id)!;
          const tag = n.broken ? (n.kind === "Missing" ? "" : " · 닿지 않음") : n.user ? " · 내 지역" : n.needs_review ? " · 검수 전" : "";
          return (
            <g key={n.id} className={`g-node k-${n.kind}${n.broken ? " broken" : ""}${n.user ? " user" : ""}`} transform={`translate(${p.x},${p.y})`}>
              <rect width={W} height={H} rx={8} />
              <text x={8} y={17} className="g-kind">
                {(KIND[n.kind] ?? n.kind) + tag}
              </text>
              <text x={8} y={34}>
                {cut(s(n.label))}
              </text>
              <title>{`${KIND[n.kind] ?? n.kind}: ${s(n.label)}`}</title>
            </g>
          );
        })}
      </svg>
      <div className="meta">
        굵은 선: 내 지역에서 조건 지역으로 가는 경로 · 점선: 끊긴 구간(닿지 않음·법령 미보유). 노드 위에 마우스를 올리면 전체 이름이 보입니다.
      </div>
      <details>
        <summary className="muted">간선 목록(글로 보기)</summary>
        <table>
          <thead>
            <tr>
              <th>출발</th>
              <th>관계</th>
              <th>도착</th>
            </tr>
          </thead>
          <tbody>
            {edges.map((e, i) => (
              <tr key={i}>
                <td>{byId.get(e.from)?.label ?? e.from}</td>
                <td>
                  <code>{REL[e.type] ?? e.type}</code>
                  {e.broken || byId.get(e.to)?.broken ? " (끊김)" : ""}
                </td>
                <td>{byId.get(e.to)?.label ?? e.to}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </div>
  );
}
