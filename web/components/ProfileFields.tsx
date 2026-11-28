"use client";
// 내 기업 조건 입력칸(SCR-01-02). 공고 찾기와 공고 상세가 같이 쓴다. 비워 둔 칸은 '모름'이고 '제한 없음'으로 보지 않는다.
import RegionSelect from "@/components/RegionSelect";
import { APPLICANT_TYPES, type ProfileForm } from "@/lib/profile";

export default function ProfileFields({ form, onChange, compact = false }: { form: ProfileForm; onChange: (f: ProfileForm) => void; compact?: boolean }) {
  const set = (k: keyof ProfileForm) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => onChange({ ...form, [k]: e.target.value });
  const toggle = (t: string) =>
    onChange({ ...form, applicant_type: form.applicant_type.includes(t) ? form.applicant_type.filter((x) => x !== t) : [...form.applicant_type, t] });
  return (
    <>
      <div className="grid">
        <RegionSelect value={form.region} onChange={set("region")} />
        {!compact && (
          <label>
            사업 개시일
            <input type="date" value={form.business_start_date} onChange={set("business_start_date")} />
          </label>
        )}
        <label>
          {compact ? "업력(년)" : "또는 업력(년)"}
          <input type="number" min={0} step="0.5" value={form.business_age_years} onChange={set("business_age_years")} placeholder="모름" />
        </label>
        {!compact && (
          <label>
            대표자 생년월일
            <input type="date" value={form.birth_date} onChange={set("birth_date")} />
          </label>
        )}
        <label>
          {compact ? "대표자 만 나이" : "또는 대표자 만 나이"}
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
        <label>
          중소기업 여부
          <select value={form.sme_status} onChange={set("sme_status")}>
            <option value="">모름</option>
            <option value="certified">중소기업확인서 보유</option>
            <option value="expected">중소기업 예정(확인서 없음)</option>
          </select>
        </label>
      </div>
      <fieldset className="plain">
        <legend className="muted">신청 대상(여러 개 선택, 하나라도 맞으면 충족)</legend>
        <div className="row">
          {APPLICANT_TYPES.map((t) => (
            <label className="check" key={t}>
              <input type="checkbox" checked={form.applicant_type.includes(t)} onChange={() => toggle(t)} /> {t}
            </label>
          ))}
        </div>
      </fieldset>
    </>
  );
}
