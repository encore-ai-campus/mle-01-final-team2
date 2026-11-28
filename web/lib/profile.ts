// 내 기업 조건(SCR-01-02). 공고 찾기·공고 상세가 같은 조건을 쓴다.
// 조건 저장(P-01, 선택 동의)은 Supabase 표가 정해진 뒤 붙인다. 지금은 브라우저 탭(sessionStorage)에만 둔다: 탭을 닫으면 사라진다.

export type ProfileForm = {
  region: string;
  business_start_date: string;
  business_age_years: string;
  birth_date: string;
  founder_age: string;
  pre_founder: string;
  sme_status: string;
  applicant_type: string[];
};

export const EMPTY_PROFILE: ProfileForm = {
  region: "",
  business_start_date: "",
  business_age_years: "",
  birth_date: "",
  founder_age: "",
  pre_founder: "",
  sme_status: "",
  applicant_type: [],
};

// K-Startup 신청 대상 값(구조화 필드)
export const APPLICANT_TYPES = ["일반기업", "1인 창조기업", "일반인", "대학생", "대학", "연구기관", "청소년"];

const KEY = "jiwongak.profile.v1";
const n = (v: string) => (v.trim() === "" ? null : Number(v));

/** 폼 → API 프로필(E-01·E-02 profile). 빈 칸은 null(= 모름, 제한 없음이 아님) */
export function toApiProfile(f: ProfileForm) {
  return {
    region: f.region || null,
    business_start_date: f.business_start_date || null,
    business_age_years: n(f.business_age_years),
    birth_date: f.birth_date || null,
    founder_age: n(f.founder_age),
    pre_founder: f.pre_founder === "" ? null : f.pre_founder === "yes",
    sme_status: f.sme_status || null,
    applicant_type: f.applicant_type.length ? f.applicant_type : null,
  };
}

/** 챗봇(/api/chat) 프로필. 챗봇 입력은 지역·업력·나이·예비창업자만 받는다 */
export function toChatProfile(f: ProfileForm) {
  return { region: f.region || null, business_age_years: n(f.business_age_years), founder_age: n(f.founder_age),
           pre_founder: f.pre_founder === "" ? null : f.pre_founder === "yes" };
}

export function isEmptyProfile(f: ProfileForm): boolean {
  return Object.values(toApiProfile(f)).every((v) => v == null);
}

export function loadProfile(): ProfileForm | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    return raw ? { ...EMPTY_PROFILE, ...(JSON.parse(raw) as Partial<ProfileForm>) } : null;
  } catch {
    return null;
  }
}

export function saveProfile(f: ProfileForm): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(f));
  } catch {
    /* 저장소를 못 쓰면 이번 화면에서만 쓴다 */
  }
}

/** 입력 가드(EX-04). 서버 가드(agent/guards.py)와 같은 식별 정보 규칙을 전송 전에 먼저 본다 */
const PII = [
  /(?<!\d)\d{6}\s?-\s?[1-8]\d{6}(?!\d)/, // 주민·외국인등록번호
  /(?<!\d)\d{3}\s?-\s?\d{2}\s?-\s?\d{5}(?!\d)/, // 사업자등록번호
  /(?<!\d)01[016789]\s?-?\s?\d{3,4}\s?-?\s?\d{4}(?!\d)/, // 휴대전화
  /[\w.+-]+@[\w-]+\.[\w.-]+/, // 이메일
];
export const hasPII = (text: string) => PII.some((p) => p.test(text));
