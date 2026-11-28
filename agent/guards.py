"""입력·출력 가드레일(기초 설계서 §7.1, §7.3). 규칙·정규식만 쓴다(NeMo 연동은 검증 전).

처리 순서: PII_BLOCKED → INJECTION_BLOCKED → OUT_OF_SCOPE·LEGAL_ADVICE. 여러 개가 겹치면 앞선 것이 우선한다.
입력 원문·검출된 값은 반환하지 않는다(사유 코드만). 사전은 config/로 옮길 예정이다(§13).
"""
from __future__ import annotations

import re

PII = [
    re.compile(r"(?<!\d)\d{6}\s?-\s?[1-8]\d{6}(?!\d)"),                 # 주민등록번호·외국인등록번호
    re.compile(r"(?<!\d)\d{3}\s?-\s?\d{2}\s?-\s?\d{5}(?!\d)"),           # 사업자등록번호
    re.compile(r"(?<!\d)01[016789]\s?-?\s?\d{3,4}\s?-?\s?\d{4}(?!\d)"),   # 휴대전화
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),                             # 이메일
]
INJECTION = re.compile(
    r"(이전|위의?|앞의?)\s*(지시|명령|규칙|프롬프트)[을를은는]?\s*(모두\s*)?(무시|잊어)|시스템\s*프롬프트|개발자\s*모드|탈옥|"
    r"ignore\s+(all\s+|any\s+)?(previous|prior|above)\s+instructions|system\s+prompt|jailbreak|\bDAN\b|you\s+are\s+now",
    re.I)
LEGAL = re.compile(r"(법률|법적|세무|회계)\s*(자문|상담|조언)|소송|절세|탈세|세금\s*(신고|줄이)|변호사\s*대신")
OUT_OF_SCOPE = re.compile(r"대신\s*(신청|접수|제출)|대리\s*(신청|접수|제출)|선정\s*(확률|가능성)|합격\s*(확률|가능성)|"
                          r"(붙을|뽑힐|선정될)\s*(수|확률)")

# 출력: 선정·수혜를 시사하는 확정 표현(MR-N1). '선정 절차' 같은 일반 명사는 막지 않는다
FORBIDDEN = re.compile(r"선정(될\s*(것|수)|됩니다|되실)|받(을|으실)\s*수\s*있(습니다|어요|다)|지원받(을|으실)\s*수\s*있|"
                       r"확실(히|합니다)|무조건|틀림없|100\s*%|보장(합니다|됩니다)")
AFFIRM = re.compile(r"신청(하실|할)\s*수\s*있(습니다|어요)|신청\s*가능합니다|자격(이|을)\s*(됩니다|갖추셨|충족하셨)")
CITATION = re.compile(r"\[([^\[\]\s]+#[^\[\]\s]+)\]")


def input_guard(text: str) -> str | None:
    """막아야 하면 사유 코드, 통과면 None."""
    if any(p.search(text) for p in PII):
        return "PII_BLOCKED"
    if INJECTION.search(text):
        return "INJECTION_BLOCKED"
    if LEGAL.search(text):
        return "LEGAL_ADVICE"
    if OUT_OF_SCOPE.search(text):
        return "OUT_OF_SCOPE"
    return None


def sentence_guard(sentence: str, known_ids: set[str], any_eligible: bool) -> str | None:
    """설명 문장 하나를 검사한다. 위반 유형(로그용) 또는 None.

    - forbidden: 확정·수혜 시사 표현
    - contradiction: ELIGIBLE이 하나도 없는데 신청할 수 있다고 단정
    - citation: 평가 결과에 없는 조건 id 인용(지어낸 근거)
    """
    if FORBIDDEN.search(sentence):
        return "forbidden"
    if not any_eligible and AFFIRM.search(sentence):
        return "contradiction"
    if any(cid not in known_ids for cid in CITATION.findall(sentence)):
        return "citation"
    return None


# 문장 끝 뒤에 오는 인용 표시([id#…])는 앞 문장에 붙이고, 인용 표시 뒤에서 끊는다
_END = re.compile(r"(?<=[.!?。])\s+(?!\s|\[[^\[\]\s]+#)|(?<=\])\s+(?!\s)")


def split_sentences(buffer: str) -> tuple[list[str], str]:
    """완성된 문장 목록과 아직 끝나지 않은 나머지를 돌려준다."""
    parts = _END.split(buffer)
    return [p for p in parts[:-1] if p.strip()], parts[-1]
