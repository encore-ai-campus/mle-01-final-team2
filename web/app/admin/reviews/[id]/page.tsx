"use client";
// 요건 검수 화면 한 건(B-3 ②). 원문에서 근거를 드래그해 조건을 만들거나 규칙·모델 후보를 채택한다.
// 근거 위치는 원문(source_text) 글자 위치다. 구역마다 <pre data-start>로 그려서 선택 위치 = 구역 시작 + 구역 안 글자 수로 계산한다.
// 근거 문장·조건 id는 서버가 원문에서 잘라 만든다. 화면은 위치·속성·연산자·값만 보낸다.
import Link from "next/link";
import { use, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { errorMessage } from "@/lib/labels";
import { apiFetch } from "@/lib/auth";

type Segment = { chunk_id: string; section: string; label: string; condition_type: string; start: number; end: number };
type Candidate = {
  candidate_id: string;
  extraction_method: string;
  condition_type: string;
  attribute: string | null;
  operator: string | null;
  value: unknown;
  raw_text: string;
  evidence_reference: { start_char: number; end_char: number } | null;
  /** 규칙 후보의 조건 문구 위치(문장 안의 좁은 위치). 채택하면 이 위치를 근거로 쓴다 */
  condition_reference?: { start_char: number; end_char: number } | null;
  condition_text?: string | null;
  unit?: string | null;
  anchored?: boolean;
};
type Gold = {
  gold_condition_id: string;
  condition_type: string;
  field: string;
  operator: string;
  value: unknown;
  raw_text: string;
  evidence_reference: { start_char: number; end_char: number };
  review_comment: string | null;
};
type Review = {
  notice_id: string;
  title: string;
  source_system: string;
  detail_url: string | null;
  is_open: boolean;
  deadline: string | null;
  priority_reasons: string[];
  source_text: string;
  segments: Segment[];
  prefill_candidates: Candidate[];
  prefill_unanchored: number;
  gold_conditions: Gold[];
  gold_logic_roots: { operator: string }[];
  logic_operator?: string;
  whole_notice_conditions_complete: boolean;
  review_status: string;
  adjudication_status: string;
  reviewer: string | null;
  reviewed_at: string | null;
  review_comment: string | null;
  stale_source: boolean;
};
type Field = { field: string; label: string; kind: "number" | "labels" | "text"; unit: string | null; evaluated: boolean };
type Draft = { key: string; condition_type: string; field: string; operator: string; value: string; start_char: number; end_char: number; review_comment: string };

const TYPE: Record<string, string> = { ELIGIBILITY: "자격", EXCLUSION: "제외", PREFERENCE: "우대" };
const OP: Record<string, string> = { LT: "미만(<)", LTE: "이하(≤)", GT: "초과(>)", GTE: "이상(≥)", EQ: "같음", IN: "중 하나", EXISTS: "있음" };
const STATUS: Record<string, string> = { UNREVIEWED: "검수 전", NEEDS_REVIEW: "작업 중", VERIFIED: "검수 완료" };
const ATTR_FIELD: Record<string, string> = {
  business_age: "BUSINESS_AGE",
  founder_age: "REPRESENTATIVE_AGE",
  region: "BUSINESS_LOCATION",
  company_size: "BUSINESS_TYPE",
  certification: "CERTIFICATION",
};
let seq = 0;
const key = () => `d${++seq}`;

function toDraft(g: Gold): Draft {
  const v = Array.isArray(g.value) ? g.value.join(", ") : g.value == null ? "" : String(g.value);
  return {
    key: key(),
    condition_type: g.condition_type,
    field: g.field,
    operator: g.operator,
    value: v,
    start_char: g.evidence_reference.start_char,
    end_char: g.evidence_reference.end_char,
    review_comment: g.review_comment ?? "",
  };
}

/** 후보 → 작성 중 조건. 규칙 속성은 검수 양식 속성으로 옮기고, 모르는 속성은 '기타'(평가 규칙 없음)로 둔다. */
function fromCandidate(c: Candidate, fields: Record<string, Field>): Draft | null {
  const ref = c.condition_reference ?? c.evidence_reference;
  if (!ref) return null;
  const v = (c.value ?? {}) as Record<string, unknown>;
  const base = { key: key(), condition_type: c.condition_type === "EXCLUSION" ? "EXCLUSION" : "ELIGIBILITY", start_char: ref.start_char, end_char: ref.end_char, review_comment: "" };
  const attr = c.attribute ?? "";
  const field = ATTR_FIELD[attr] ?? (fields[attr] ? attr : "OTHER");
  const f = fields[field];
  if (f?.kind === "number") {
    const n = typeof c.value === "number" ? c.value : Number(v.value);
    const op = ["LT", "LTE", "GT", "GTE", "EQ"].includes(c.operator ?? "") ? c.operator! : "LTE";
    return { ...base, field, operator: op, value: Number.isFinite(n) ? String(n) : "" };
  }
  if (f?.kind === "labels") {
    const labels = Array.isArray(c.value) ? c.value.map(String) : typeof c.value === "string" ? [c.value] : v.label ? [String(v.label)] : [];
    return { ...base, field, operator: "IN", value: labels.join(", ") };
  }
  if (attr === "law_reference") return { ...base, field: "OTHER", operator: "EQ", value: `${v.law ?? ""} ${v.article ?? ""}`.trim() };
  if (attr === "exclusion") return { ...base, field: "OTHER", operator: "EXISTS", value: "" };
  return { ...base, field, operator: "EQ", value: typeof c.value === "string" ? c.value : "" };
}

function offsetIn(pre: HTMLElement, node: Node, off: number): number {
  const r = document.createRange();
  r.setStart(pre, 0);
  r.setEnd(node, off);
  return Number(pre.dataset.start) + r.toString().length;
}

/** 구역 글을 표시 구간(조건=mark, 후보=밑줄)으로 나눠 그린다. */
function SegmentText({ seg, text, spans }: { seg: Segment; text: string; spans: { s: number; e: number; cls: string }[] }) {
  const inSeg = spans.filter((x) => x.e > seg.start && x.s < seg.end);
  const cuts = new Set([seg.start, seg.end]);
  for (const x of inSeg) {
    cuts.add(Math.max(seg.start, x.s));
    cuts.add(Math.min(seg.end, x.e));
  }
  const pts = [...cuts].sort((a, b) => a - b);
  const parts = [];
  for (let i = 0; i < pts.length - 1; i++) {
    const [a, b] = [pts[i], pts[i + 1]];
    const cls = inSeg.filter((x) => x.s <= a && x.e >= b).map((x) => x.cls);
    const t = text.slice(a, b);
    parts.push(cls.length ? <mark key={a} className={[...new Set(cls)].join(" ")}>{t}</mark> : <span key={a}>{t}</span>);
  }
  return (
    <pre className="review-src" data-start={seg.start}>
      {parts}
    </pre>
  );
}

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const nid = decodeURIComponent(id);
  const [review, setReview] = useState<Review | null>(null);
  const [fields, setFields] = useState<Field[]>([]);
  const [ops, setOps] = useState<Record<string, string[]>>({});
  const [drafts, setDrafts] = useState<Draft[]>([]);
  const [logic, setLogic] = useState("AND");
  const [whole, setWhole] = useState(false);
  const [noneInText, setNoneInText] = useState(false);
  const [comment, setComment] = useState("");
  const [sel, setSel] = useState<{ s: number; e: number } | null>(null);
  const [msg, setMsg] = useState("");
  const [errs, setErrs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const srcRef = useRef<HTMLDivElement>(null);

  const apply = useCallback((r: Review) => {
    setReview(r);
    setDrafts(r.gold_conditions.map(toDraft));
    setLogic(r.logic_operator ?? r.gold_logic_roots[0]?.operator ?? "AND");
    setWhole(r.whole_notice_conditions_complete);
    setNoneInText(r.adjudication_status === "CONFIRMED_NONE_IN_PROVIDED_TEXT");
    setComment(r.review_comment ?? "");
  }, []);

  useEffect(() => {
    apiFetch(`/api/admin/reviews/${encodeURIComponent(nid)}`)
      .then(async (r) => {
        const d = await r.json().catch(() => null);
        if (!r.ok) throw new Error(errorMessage(d, r.status));
        setFields(d.fields);
        setOps(d.operators);
        apply(d.review);
      })
      .catch((e: Error) => setMsg(e.message));
  }, [nid, apply]);

  const fieldMap = useMemo(() => Object.fromEntries(fields.map((f) => [f.field, f])), [fields]);
  const locked = review?.review_status === "VERIFIED";

  const onMouseUp = () => {
    const s = window.getSelection();
    if (!s || s.isCollapsed || !srcRef.current) return setSel(null);
    const pa = (s.anchorNode?.parentElement?.closest("pre[data-start]") ?? null) as HTMLElement | null;
    const pf = (s.focusNode?.parentElement?.closest("pre[data-start]") ?? null) as HTMLElement | null;
    if (!pa || !pf || !srcRef.current.contains(pa) || !srcRef.current.contains(pf)) return setSel(null);
    let a = offsetIn(pa, s.anchorNode!, s.anchorOffset);
    let b = offsetIn(pf, s.focusNode!, s.focusOffset);
    if (a > b) [a, b] = [b, a];
    // 앞뒤 공백은 근거에서 뺀다
    const t = review!.source_text;
    while (a < b && /\s/.test(t[a])) a++;
    while (b > a && /\s/.test(t[b - 1])) b--;
    setSel(a < b ? { s: a, e: b } : null);
  };

  const addFromSel = (ctype: string) => {
    if (!sel) return;
    setDrafts((d) => [...d, { key: key(), condition_type: ctype, field: "BUSINESS_AGE", operator: "LTE", value: "", start_char: sel.s, end_char: sel.e, review_comment: "" }]);
    setSel(null);
    window.getSelection()?.removeAllRanges();
  };

  const adopt = (c: Candidate) => {
    const d = fromCandidate(c, fieldMap);
    if (d) setDrafts((x) => [...x, d]);
  };

  const patch = (k: string, p: Partial<Draft>) => setDrafts((d) => d.map((x) => (x.key === k ? { ...x, ...p } : x)));

  const save = async (action: "save" | "verify" | "reopen") => {
    if (!review) return;
    setBusy(true);
    setMsg("");
    setErrs([]);
    const conditions = drafts.map((d) => {
      const f = fieldMap[d.field];
      const value = f?.kind === "number" ? (d.value.trim() === "" ? null : Number(d.value)) : f?.kind === "labels" ? d.value.split(",").map((x) => x.trim()).filter(Boolean) : d.value;
      return { condition_type: d.condition_type, field: d.field, operator: d.operator, value, start_char: d.start_char, end_char: d.end_char, review_comment: d.review_comment || null };
    });
    const body = { action, conditions, logic, whole_notice_conditions_complete: whole, none_in_text: noneInText, review_comment: comment };
    try {
      const r = await apiFetch(`/api/admin/reviews/${encodeURIComponent(nid)}`, { method: "PUT", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setMsg(errorMessage(d, r.status));
        setErrs(d?.detail?.error?.errors ?? []);
        if (d?.detail?.error?.code === "REVIEW_CHECK_FAILED") {
          const again = await apiFetch(`/api/admin/reviews/${encodeURIComponent(nid)}`).then((x) => x.json());
          apply(again.review);
        }
        return;
      }
      apply(d.review);
      setMsg(action === "verify" ? "검수 완료로 저장했습니다. 목록의 '판정에 반영'을 눌러야 판정에 쓰입니다." : action === "reopen" ? "다시 작업 중으로 바꿨습니다." : "작업 중으로 저장했습니다.");
    } catch {
      setMsg("Next 서버에 닿지 않습니다.");
    } finally {
      setBusy(false);
    }
  };

  if (!review) {
    return (
      <main>
        <h1>요건 검수</h1>
        <div className="banner">{msg || "불러오는 중…"}</div>
        <Link href="/admin/reviews">목록으로</Link>
      </main>
    );
  }

  const text = review.source_text;
  const spans = [
    ...review.prefill_candidates.filter((c) => c.evidence_reference).map((c) => ({ s: c.evidence_reference!.start_char, e: c.evidence_reference!.end_char, cls: "cand" })),
    ...drafts.map((d) => ({ s: d.start_char, e: d.end_char, cls: d.condition_type === "EXCLUSION" ? "gold excl" : "gold" })),
    ...(sel ? [{ s: sel.s, e: sel.e, cls: "sel" }] : []),
  ];
  const nElig = drafts.filter((d) => d.condition_type === "ELIGIBILITY").length;

  return (
    <main className="review-page">
      <div className="muted">
        <Link href="/admin/reviews">← 검수 큐</Link>
      </div>
      <h1>{review.title || review.notice_id}</h1>
      <div className="muted">
        {review.notice_id} · {review.source_system} · 마감 {review.deadline ?? "-"} · {review.priority_reasons.join(", ")} ·{" "}
        <span className={`badge ${locked ? "ELIGIBLE" : review.review_status === "NEEDS_REVIEW" ? "NEEDS_CHECK" : ""}`}>{STATUS[review.review_status] ?? review.review_status}</span>
        {review.reviewer && ` ${review.reviewer} ${review.reviewed_at ?? ""}`}
        {review.detail_url && (
          <>
            {" · "}
            <a href={review.detail_url} target="_blank" rel="noreferrer">
              공고 원문 열기
            </a>
          </>
        )}
      </div>
      {review.stale_source && <div className="banner">검수한 뒤 원문이 바뀌었습니다. 근거를 다시 확인하고 검수 완료를 다시 눌러야 반영됩니다.</div>}

      <div className="review-grid">
        <section className="panel">
          <div className="card-head">
            <h2>원문(자격·제외 구역)</h2>
            <span className="muted">드래그해서 근거를 고르세요</span>
          </div>
          <div ref={srcRef} onMouseUp={locked ? undefined : onMouseUp}>
            {review.segments.map((g) => (
              <div key={g.chunk_id} className="review-seg">
                <div className="meta">
                  {g.label} · {TYPE[g.condition_type] ?? g.condition_type}
                </div>
                <SegmentText seg={g} text={text} spans={spans} />
              </div>
            ))}
          </div>
          {sel && (
            <div className="row sel-bar">
              <span className="muted">선택: “{text.slice(sel.s, sel.e).slice(0, 60)}{sel.e - sel.s > 60 ? "…" : ""}”</span>
              <button type="button" className="primary" onClick={() => addFromSel("ELIGIBILITY")}>
                자격 조건으로 추가
              </button>
              <button type="button" onClick={() => addFromSel("EXCLUSION")}>
                제외 조건으로 추가
              </button>
            </div>
          )}
        </section>

        <div>
          <section className="panel">
            <h2>사전 채움 후보 {review.prefill_candidates.length}개</h2>
            <div className="muted">규칙·모델이 찾은 후보입니다. 맞는지 확인하고 채택하세요. 위치를 찾지 못한 후보({review.prefill_unanchored}개 포함)는 채택할 수 없습니다.</div>
            <ul className="cand-list">
              {review.prefill_candidates.map((c) => (
                <li key={c.candidate_id}>
                  <span className="badge">{c.extraction_method === "llm" ? "모델" : "규칙"}</span> {TYPE[c.condition_type] ?? c.condition_type} · {c.attribute} {c.operator}{" "}
                  <code>{JSON.stringify(c.value)}</code>
                  {c.unit && <span className="muted"> {c.unit}</span>}
                  {c.condition_text && <div>조건 문구: <mark>{c.condition_text}</mark></div>}
                  <div className="muted">“{c.raw_text.slice(0, 80)}”</div>
                  {!locked && (
                    <button type="button" className="link" disabled={!c.evidence_reference} onClick={() => adopt(c)}>
                      {c.evidence_reference ? "채택" : "위치 없음"}
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="panel">
            <h2>조건 {drafts.length}개</h2>
            {drafts.length === 0 && <div className="muted">원문을 드래그하거나 후보를 채택해 조건을 만드세요.</div>}
            {drafts.map((d, i) => {
              const f = fieldMap[d.field];
              return (
                <fieldset key={d.key} className="cond" disabled={locked}>
                  <div className="card-head">
                    <strong>
                      {i + 1}. {TYPE[d.condition_type]}
                    </strong>
                    <button type="button" className="link" onClick={() => setDrafts((x) => x.filter((y) => y.key !== d.key))}>
                      삭제
                    </button>
                  </div>
                  <div className="muted">근거: “{text.slice(d.start_char, d.end_char)}”</div>
                  <div className="row">
                    <select value={d.condition_type} onChange={(e) => patch(d.key, { condition_type: e.target.value })} aria-label="종류">
                      {Object.entries(TYPE).map(([k, v]) => (
                        <option key={k} value={k}>
                          {v}
                        </option>
                      ))}
                    </select>
                    <select
                      value={d.field}
                      onChange={(e) => {
                        const nf = fieldMap[e.target.value];
                        patch(d.key, { field: e.target.value, operator: ops[nf?.kind ?? "text"]?.[0] ?? "EQ" });
                      }}
                      aria-label="속성"
                    >
                      {fields.map((x) => (
                        <option key={x.field} value={x.field}>
                          {x.label}
                          {x.evaluated ? "" : " (판정 안 함)"}
                        </option>
                      ))}
                    </select>
                    <select value={d.operator} onChange={(e) => patch(d.key, { operator: e.target.value })} aria-label="연산자">
                      {(ops[f?.kind ?? "text"] ?? []).map((o) => (
                        <option key={o} value={o}>
                          {OP[o] ?? o}
                        </option>
                      ))}
                    </select>
                    {d.operator !== "EXISTS" && (
                      <input
                        value={d.value}
                        onChange={(e) => patch(d.key, { value: e.target.value })}
                        placeholder={f?.kind === "number" ? `숫자${f.unit === "YEAR" ? "(년·세)" : ""}` : f?.kind === "labels" ? "쉼표로 구분(예: 서울특별시, 경기도)" : "값"}
                        inputMode={f?.kind === "number" ? "decimal" : undefined}
                        aria-label="값"
                      />
                    )}
                  </div>
                  <input className="cond-note" value={d.review_comment} onChange={(e) => patch(d.key, { review_comment: e.target.value })} placeholder="조건 메모(선택)" aria-label="조건 메모" />
                </fieldset>
              );
            })}
          </section>

          <section className="panel">
            <h2>검수 결과</h2>
            <fieldset disabled={locked} className="plain">
              <div className="row">
                <span className="muted">자격 조건 사이</span>
                {["AND", "OR"].map((x) => (
                  <label key={x} style={{ flexDirection: "row", alignItems: "center" }}>
                    <input type="radio" name="logic" checked={logic === x} onChange={() => setLogic(x)} /> {x === "AND" ? "모두(AND)" : "하나라도(OR)"}
                  </label>
                ))}
                {logic === "OR" && nElig < 2 && <span className="muted">자격 조건이 2개 이상일 때만 OR가 쓰입니다.</span>}
              </div>
              <div className="muted">제외 조건은 따로, 하나라도 해당하면 불충족입니다.</div>
              <label className="review-check">
                <span>
                  <input type="checkbox" checked={noneInText} onChange={(e) => setNoneInText(e.target.checked)} /> 원문에 판정할 자격 조건이 없음
                </span>
              </label>
              <label className="review-check">
                <span>
                  <input type="checkbox" checked={whole} onChange={(e) => setWhole(e.target.checked)} /> 공고 전체의 자격 조건을 확인했음
                </span>
                <span className="muted">
                  체크하면 이 공고의 &lsquo;자동 해석 못 함&rsquo;이 풀려 적합 판정이 날 수 있습니다. 위 원문은 공고 일부일 수 있으니(K-Startup은 첨부 본문이 없음) 공고 원문을 열어 확인한 뒤에만 체크하세요.
                  체크하지 않으면 조건은 쓰이지만 판정은 계속 &lsquo;확인 필요&rsquo;로 남습니다.
                </span>
              </label>
              <textarea value={comment} onChange={(e) => setComment(e.target.value)} placeholder="검수 메모(선택)" aria-label="검수 메모" />
            </fieldset>
            <div className="row">
              {locked ? (
                <button type="button" disabled={busy} onClick={() => save("reopen")}>
                  다시 작업
                </button>
              ) : (
                <>
                  <button type="button" disabled={busy} onClick={() => save("save")}>
                    작업 중 저장
                  </button>
                  <button type="button" className="primary" disabled={busy} onClick={() => save("verify")}>
                    검수 완료
                  </button>
                </>
              )}
            </div>
            {msg && <div className="banner">{msg}</div>}
            {errs.length > 0 && (
              <ul className="errs">
                {errs.map((e, i) => (
                  <li key={i}>{e}</li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </main>
  );
}
