"use client";
// 규칙 판정 PoC: 프로필 입력 → /api/eligibility(모델 없음) → 공고별 판정과 조건별 사유.
// 2026-11-27 회의 결정을 화면에 반영했다: 신청 대상 여러 개(A-5), 사업 개시일·생년월일(A-2·A-4),
// 중소기업확인서·중소기업 예정(E-5), 상세 입력은 선택. 예비창업자(신규창업)는 확장 기능이라 입력만 받는다.
import { useEffect, useState } from "react";

type Region = { id: string; name: string; full_name: string | null; level: string | null };
type Cond = { cond_id: string; attribute: string; status: string; strength: string; reason: string; evidence: string; flags: string[] };
type Result = {
  notice_id: string;
  verdict: string;
  structured: string;
  reasons: string[];
  conditions: Cond[];
  score: number | null;
  title: string | null;
  source: string | null;
  detail_url: string | null;
  deadline: string | null;
  fetched_at: string | null;
};
type Resp = { evaluated: number; candidates: number; counts: Record<string, number>; results: Result[]; input_layer: string };

const VERDICT: Record<string, string> = { ELIGIBLE: "조건 충족(참고)", NOT_ELIGIBLE: "조건 미충족", NEEDS_CHECK: "확인 필요" };
const STATUS: Record<string, string> = { SATISFIED: "충족", UNSATISFIED: "미충족", UNKNOWN: "모름" };
const ATTR: Record<string, string> = {
  region: "지역",
  business_age: "업력",
  founder_age: "대표자 나이",
  pre_founder: "예비창업자",
  applicant_type: "신청 대상",
  business_type: "기업 유형",
};
// K-Startup 신청 대상 값(구조화 필드). 일반기업은 B-1로 개념을 만들었다
const APPLICANT_TYPES = ["일반기업", "1인 창조기업", "일반인", "대학생", "대학", "연구기관", "청소년"];

const EMPTY = {
  region: "",
  business_age_years: "",
  business_start_date: "",
  founder_age: "",
  birth_date: "",
  pre_founder: "",
  sme_status: "",
  ksic: "",
  avg_sales_eok: "",
  total_assets_eok: "",
  independence_ok: "",
  disclosure_group_member: "",
  question: "",
  source: "",
  include_closed: false,
  top: "10",
};

const SAMPLES: { label: string; form: Partial<typeof EMPTY>; types: string[] }[] = [
  { label: "서울 2년 차 일반기업, 확인서 보유", form: { region: "REGION:1100000000", business_start_date: "2024-09-01", birth_date: "1990-03-15", sme_status: "certified" }, types: ["일반기업"] },
  { label: "대구 대학생 예비창업자", form: { region: "REGION:2700000000", pre_founder: "yes", founder_age: "22" }, types: ["대학생", "일반인"] },
  { label: "중소기업 예정, 상세 입력", form: { business_age_years: "4", sme_status: "expected", ksic: "C", avg_sales_eok: "120", total_assets_eok: "300", independence_ok: "yes", disclosure_group_member: "no" }, types: ["일반기업"] },
];

const s = (v: unknown) => (v == null ? "" : String(v));
const num = (v: string) => (v.trim() === "" ? null : Number(v));
const bool = (v: string) => (v === "" ? null : v === "yes");

export default function EligibilityPoc() {
  const [regions, setRegions] = useState<Region[]>([]);
  const [form, setForm] = useState(EMPTY);
  const [types, setTypes] = useState<string[]>([]);
  const [resp, setResp] = useState<Resp | null>(null);
  const [sent, setSent] = useState<unknown>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [open, setOpen] = useState<Record<string, boolean>>({});

  useEffect(() => {
    fetch("/api/concepts?scheme=region")
      .then((r) => r.json())
      .then((d) => setRegions((d.items ?? []).filter((r: Region) => r.level !== "GROUP")))
      .catch(() => setRegions([]));
  }, []);

  const set = (k: keyof typeof EMPTY) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.type === "checkbox" ? (e.target as HTMLInputElement).checked : e.target.value }));
  const toggle = (t: string) => setTypes((ts) => (ts.includes(t) ? ts.filter((x) => x !== t) : [...ts, t]));

  function buildBody() {
    const facts = {
      main_industry_ksic: form.ksic.trim() || undefined,
      avg_sales_eok: num(form.avg_sales_eok) ?? undefined,
      total_assets_eok: num(form.total_assets_eok) ?? undefined,
      independence_ok: bool(form.independence_ok) ?? undefined,
      disclosure_group_member: bool(form.disclosure_group_member) ?? undefined,
    };
    const hasFacts = Object.values(facts).some((v) => v !== undefined);
    return {
      question: form.question,
      top: Number(form.top) || 10,
      include_closed: form.include_closed,
      source: form.source || null,
      profile: {
        region: form.region || null,
        business_age_years: num(form.business_age_years),
        business_start_date: form.business_start_date || null,
        founder_age: num(form.founder_age),
        birth_date: form.birth_date || null,
        pre_founder: bool(form.pre_founder),
        applicant_type: types.length ? types : null,
        sme_status: form.sme_status || null,
        sme_facts: hasFacts ? facts : null,
      },
    };
  }

  async function submit(ev?: React.FormEvent) {
    ev?.preventDefault();
    setRunning(true);
    setError("");
    const body = buildBody();
    setSent(body);
    try {
      const r = await fetch("/api/eligibility", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
      const d = await r.json().catch(() => null);
      if (!r.ok) {
        setResp(null);
        setError(d?.error?.message ?? d?.detail?.[0]?.msg ?? `요청 실패(${r.status})`);
        return;
      }
      setResp(d as Resp);
      setOpen({});
    } catch {
      setError("API 서버에 닿지 않습니다.");
    } finally {
      setRunning(false);
    }
  }

  function loadSample(i: number) {
    setForm({ ...EMPTY, ...SAMPLES[i].form });
    setTypes(SAMPLES[i].types);
    setResp(null);
  }

  return (
    <main>
      <h1>지원각 · 규칙 판정 PoC</h1>
      <div className="muted">
        모델 없이 규칙 평가기만 씁니다. 비워 둔 칸은 &lsquo;모름&rsquo;이며 &lsquo;제한 없음&rsquo;으로 보지 않습니다. 결과는 참고용입니다. <a href="/">채팅 화면</a>
      </div>

      <div className="row">
        <span className="muted">예시:</span>
        {SAMPLES.map((x, i) => (
          <button type="button" className="link" key={i} onClick={() => loadSample(i)}>
            {x.label}
          </button>
        ))}
      </div>

      <form className="panel" onSubmit={submit}>
        <h2>기본</h2>
        <div className="grid">
          <label>
            사업장 소재지
            <select value={form.region} onChange={set("region")}>
              <option value="">모름</option>
              {regions.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.full_name ?? r.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            사업 개시일(정확)
            <input type="date" value={form.business_start_date} onChange={set("business_start_date")} />
          </label>
          <label>
            또는 업력(년)
            <input type="number" min={0} step="0.5" value={form.business_age_years} onChange={set("business_age_years")} placeholder="모름" />
          </label>
          <label>
            대표자 생년월일(정확)
            <input type="date" value={form.birth_date} onChange={set("birth_date")} />
          </label>
          <label>
            또는 대표자 만 나이
            <input type="number" min={0} max={120} value={form.founder_age} onChange={set("founder_age")} placeholder="모름" />
          </label>
          <label>
            예비창업자 <span>(신규창업은 확장 기능)</span>
            <select value={form.pre_founder} onChange={set("pre_founder")}>
              <option value="">모름</option>
              <option value="yes">예</option>
              <option value="no">아니오</option>
            </select>
          </label>
        </div>

        <h2>신청 대상 (여러 개 선택, 하나라도 맞으면 충족)</h2>
        <div className="row">
          {APPLICANT_TYPES.map((t) => (
            <label className="check" key={t}>
              <input type="checkbox" checked={types.includes(t)} onChange={() => toggle(t)} /> {t}
            </label>
          ))}
        </div>

        <h2>중소기업</h2>
        <div className="grid">
          <label>
            중소기업 여부
            <select value={form.sme_status} onChange={set("sme_status")}>
              <option value="">모름</option>
              <option value="certified">중소기업확인서 보유</option>
              <option value="expected">중소기업 예정(확인서 없음)</option>
            </select>
          </label>
        </div>
        {form.sme_status !== "certified" && (
          <details>
            <summary className="muted">상세 입력(선택) — 확인서가 없을 때만 씁니다. 매출 기준 ±5%는 &lsquo;모름&rsquo;</summary>
            <div className="grid">
              <label>
                주된 업종(KSIC 대분류·코드)
                <input value={form.ksic} onChange={set("ksic")} placeholder="예: C, 26" />
              </label>
              <label>
                3년 평균매출액(억 원)
                <input type="number" min={0} value={form.avg_sales_eok} onChange={set("avg_sales_eok")} />
              </label>
              <label>
                자산총액(억 원)
                <input type="number" min={0} value={form.total_assets_eok} onChange={set("total_assets_eok")} />
              </label>
              <label>
                독립성 기준 충족
                <select value={form.independence_ok} onChange={set("independence_ok")}>
                  <option value="">모름</option>
                  <option value="yes">예</option>
                  <option value="no">아니오</option>
                </select>
              </label>
              <label>
                공시대상기업집단 소속
                <select value={form.disclosure_group_member} onChange={set("disclosure_group_member")}>
                  <option value="">모름</option>
                  <option value="yes">예</option>
                  <option value="no">아니오</option>
                </select>
              </label>
            </div>
          </details>
        )}

        <h2>검색(선택)</h2>
        <div className="grid">
          <label>
            검색어
            <input value={form.question} onChange={set("question")} maxLength={500} placeholder="비우면 판정만" />
          </label>
          <label>
            출처
            <select value={form.source} onChange={set("source")}>
              <option value="">전체</option>
              <option value="BIZINFO">기업마당</option>
              <option value="KSTARTUP">K-Startup</option>
            </select>
          </label>
          <label>
            보여 줄 공고 수
            <input type="number" min={1} max={50} value={form.top} onChange={set("top")} />
          </label>
          <label className="check">
            <input type="checkbox" checked={form.include_closed} onChange={set("include_closed")} /> 마감 공고 포함
          </label>
        </div>

        <div className="row">
          <button className="primary" disabled={running}>
            {running ? "판정 중…" : "판정"}
          </button>
          <span className="muted">개인정보(주민·사업자번호 등)는 입력하지 마세요.</span>
        </div>
      </form>

      {error && <div className="banner">{error}</div>}

      {resp && (
        <div className="panel">
          <div>
            판정한 공고 {resp.evaluated.toLocaleString()}건 · 후보 {resp.candidates.toLocaleString()}건 ·{" "}
            {Object.entries(resp.counts)
              .map(([k, v]) => `${VERDICT[k] ?? k} ${v.toLocaleString()}`)
              .join(" · ")}
          </div>
          <div className="meta">데이터 층: {resp.input_layer}</div>
          <details>
            <summary className="muted">보낸 프로필(JSON)</summary>
            <pre>{JSON.stringify(sent, null, 2)}</pre>
          </details>
        </div>
      )}

      {resp?.results.map((n) => (
        <section className="panel" key={n.notice_id}>
          <div className="card-head">
            <h2>{n.title || n.notice_id}</h2>
            <span className={`badge ${n.verdict}`}>{VERDICT[n.verdict] ?? n.verdict}</span>
          </div>
          <div className="meta">
            {n.notice_id}
            {n.deadline ? ` · 마감 ${n.deadline}` : ""}
            {n.fetched_at ? ` · 수집 ${s(n.fetched_at).slice(0, 10)}` : ""}
            {n.detail_url ? (
              <>
                {" · "}
                <a href={n.detail_url} target="_blank" rel="noreferrer">
                  공고 원문
                </a>
              </>
            ) : null}
          </div>
          {n.reasons.length > 0 && (
            <ul>
              {n.reasons.map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          )}
          <button type="button" className="link" onClick={() => setOpen((o) => ({ ...o, [n.notice_id]: !o[n.notice_id] }))}>
            {open[n.notice_id] ? "조건 접기" : `조건 ${n.conditions.length}개 보기`}
          </button>
          {open[n.notice_id] && (
            <table>
              <thead>
                <tr>
                  <th>조건</th>
                  <th>상태</th>
                  <th>사유</th>
                  <th>공고 근거</th>
                </tr>
              </thead>
              <tbody>
                {n.conditions.map((c) => (
                  <tr key={c.cond_id}>
                    <td>
                      {ATTR[c.attribute] ?? c.attribute}
                      <span className="muted"> ({c.strength === "hard" ? "필수" : "참고"})</span>
                      {c.flags.length > 0 && <div className="muted">{c.flags.join(", ")}</div>}
                    </td>
                    <td>
                      <span className={`badge ${c.status}`}>{STATUS[c.status] ?? c.status}</span>
                    </td>
                    <td>{c.reason}</td>
                    <td className="muted">{c.evidence}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      ))}
    </main>
  );
}
