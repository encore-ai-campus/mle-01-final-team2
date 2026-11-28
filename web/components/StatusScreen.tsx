// 예외 상태 화면 EX-01~06(화면설계서 §5). 고정 문구만 쓰고 모델이 문구를 쓰지 않는다.
// 상태 배지는 공고 판정 배지(조건 충족·미충족·확인 필요)와 다른 모양이다(v3.5 수정: 예외 배지가 판정처럼 보이지 않게).
import Link from "next/link";

type Code =
  | "NO_MATCH"
  | "INSUFFICIENT_PROFILE"
  | "REQ_UNPARSED"
  | "CHAIN_BROKEN"
  | "PII_BLOCKED"
  | "INJECTION_BLOCKED"
  | "OUT_OF_SCOPE"
  | "ROLE_DENIED"
  | "STALE_DATA"
  | "SERVICE_DEGRADED"
  | "OUTPUT_BLOCKED";

const T: Record<Code, { ex: string; badge: string; reason: string; next: string }> = {
  NO_MATCH: { ex: "EX-01", badge: "맞는 공고 없음", reason: "입력한 조건과 모집 중 공고를 지역 계층까지 넓혀 비교했지만 남은 공고가 없습니다.", next: "조건을 비우거나 바꿔 다시 찾거나, 마감 공고 포함을 켜 보세요." },
  INSUFFICIENT_PROFILE: { ex: "EX-02", badge: "정보 부족", reason: "판정에 필요한 값이 비어 있어 결론을 내지 않았습니다.", next: "조건별 검증 탭에서 '미입력' 항목을 채우고 다시 판정하세요." },
  REQ_UNPARSED: { ex: "EX-03", badge: "요건 해석 전", reason: "이 공고의 본문·첨부 자격 요건은 아직 사람이 검수하지 않아 자동 판정에 쓰지 않습니다.", next: "원문 탭이나 공고 원문에서 자격 요건을 직접 확인하세요." },
  CHAIN_BROKEN: { ex: "EX-03", badge: "근거 끊김", reason: "조건의 정의에서 법령까지 이어지는 연결이 없어 결론을 내지 않았습니다.", next: "공고 원문과 관련 법령을 직접 확인하세요." },
  PII_BLOCKED: { ex: "EX-04", badge: "입력 처리 불가", reason: "식별 정보(주민·사업자등록번호, 연락처, 이메일)로 보이는 값이 있어 보내지 않았습니다.", next: "그 값을 지우고 다시 보내세요. 판정에는 식별 정보가 필요 없습니다." },
  INJECTION_BLOCKED: { ex: "EX-04", badge: "입력 처리 불가", reason: "처리할 수 없는 지시가 들어 있습니다.", next: "공고·자격에 관한 질문으로 다시 써 주세요." },
  OUT_OF_SCOPE: { ex: "EX-04", badge: "입력 처리 불가", reason: "이 서비스가 다루지 않는 요청입니다(대리 신청, 선정 가능성 등).", next: "공고 찾기, 자격 확인, 공고 내용 질문을 이용하세요." },
  ROLE_DENIED: { ex: "EX-05", badge: "접근 권한 없음", reason: "운영자만 볼 수 있는 화면입니다.", next: "공고 찾기로 돌아가세요. 운영자라면 관리자 계정으로 로그인하세요." },
  STALE_DATA: { ex: "EX-06", badge: "일부 기능 제한", reason: "공고 수집이 늦어져 최신 공고가 빠졌을 수 있습니다.", next: "공고 원문에서 마감일과 변경 사항을 꼭 확인하세요." },
  SERVICE_DEGRADED: { ex: "EX-06", badge: "일부 기능 제한", reason: "서버나 모델에 닿지 않아 결과를 가져오지 못했습니다.", next: "잠시 뒤 다시 시도하세요. 규칙 판정은 모델 없이도 동작합니다." },
  OUTPUT_BLOCKED: { ex: "EX-06", badge: "일부 기능 제한", reason: "설명 문장에 확정 표현이 있어 내보내지 않았습니다.", next: "판정 결과와 조건별 검증표를 확인하세요." },
};

export const STATUS_CODES = Object.keys(T) as Code[];

export default function StatusScreen({ code, detail, action }: { code: Code; detail?: string; action?: React.ReactNode }) {
  const t = T[code];
  return (
    <section className="panel status-screen" role="status" aria-live="polite">
      <div className="card-head">
        <h2>
          <span className="ex-badge">{t.badge}</span>
        </h2>
        <span className="muted">
          {t.ex} · {code}
        </span>
      </div>
      <p>{t.reason}</p>
      {detail && <p className="muted">{detail}</p>}
      <p>
        <strong>다음 행동:</strong> {t.next}
      </p>
      {action ?? (code === "ROLE_DENIED" ? <Link href="/">공고 찾기로</Link> : null)}
    </section>
  );
}
