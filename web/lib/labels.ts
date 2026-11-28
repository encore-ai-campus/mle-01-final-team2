// 화면 공통 문구. 판정은 "신청 가능"이라고 단정하지 않는다(ELIGIBLE = 조건 충족(참고)).
export const VERDICT: Record<string, string> = { ELIGIBLE: "조건 충족(참고)", NOT_ELIGIBLE: "조건 미충족", NEEDS_CHECK: "확인 필요" };
export const STATUS: Record<string, string> = { SATISFIED: "충족", UNSATISFIED: "미충족", UNKNOWN: "모름" };
export const ATTR: Record<string, string> = {
  region: "지역",
  business_age: "업력",
  founder_age: "대표자 나이",
  pre_founder: "예비창업자",
  applicant_type: "신청 대상",
  business_type: "기업 유형",
};
export const SOURCE: Record<string, string> = { BIZINFO: "기업마당", KSTARTUP: "K-Startup" };
export const AGENT: Record<string, string> = {
  auto: "자동",
  eligibility: "자격 판정",
  notice_qa: "공고 질의",
  definition: "용어 정의",
};
export const ROUTE_METHOD: Record<string, string> = { rule: "규칙 분류", llm: "모델 분류", forced: "직접 지정" };
export const DISCLAIMER = "참고용입니다. 최종 확인은 공고 원문과 주관기관이 합니다.";
export const PII_WARNING = "사업자번호·주민번호·연락처 같은 식별 정보는 입력하지 마세요.";

export const s = (v: unknown) => (v == null ? "" : String(v));
export const day = (v: unknown) => s(v).slice(0, 16).replace("T", " ");
export const num = (v: string) => (v.trim() === "" ? null : Number(v));

/** API 오류 본문에서 사람이 읽을 문구를 꺼낸다. */
export function errorMessage(d: unknown, status: number): string {
  const x = d as { error?: { message?: string }; detail?: { error?: { message?: string }; msg?: string }[] | { error?: { message?: string } } } | null;
  if (x?.error?.message) return x.error.message;
  const det = x?.detail;
  if (Array.isArray(det)) return det[0]?.msg ?? `요청 실패(${status})`;
  if (det?.error?.message) return det.error.message;
  if (status === 401) return "로그인이 필요합니다.";
  return `요청 실패(${status})`;
}
