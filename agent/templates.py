"""고정 응답 문구(기초 설계서 §7.3). 거절·안전 응답은 모델이 쓰지 않는다."""
from __future__ import annotations

OUTCOME = {
    "NO_MATCH": "held", "INSUFFICIENT_PROFILE": "held", "REQ_UNPARSED": "held", "CHAIN_BROKEN": "held",
    "OUT_OF_SCOPE": "refused", "PII_BLOCKED": "refused", "INJECTION_BLOCKED": "refused", "LEGAL_ADVICE": "refused",
    "ROLE_DENIED": "refused", "OUTPUT_BLOCKED": "answered", "STALE_DATA": "answered", "SERVICE_DEGRADED": "degraded",
}

TEXT = {
    "NO_MATCH": "수집한 공고({evaluated}건, 기준 시각 {as_of}) 중 입력하신 조건에 맞는 공고를 찾지 못했습니다. "
                "지역·업종·업력 조건을 넓히면 후보가 생길 수 있습니다. 공고 원문은 각 포털에서 확인해 주세요.",
    "NO_MATCH_NOTICE": "지목하신 공고({notice_id})를 수집한 공고에서 찾지 못했습니다. 공고 번호를 확인하시거나, 이미 내려간 공고라면 포털 원문을 확인해 주세요.",
    "INSUFFICIENT_PROFILE": "판정에 필요한 정보가 부족합니다. 아래 항목을 알려 주시면 다시 확인합니다: {fields}. "
                            "모르는 항목은 비워 두셔도 되며, 그 조건은 '확인 필요'로 표시됩니다.",
    "OUT_OF_SCOPE": "이 서비스는 공고의 신청 자격 요건을 확인하고 부족한 조건을 설명하는 데까지 돕습니다. "
                    "신청 대행이나 선정 가능성 예측은 하지 않습니다.",
    "PII_BLOCKED": "입력에 사업자등록번호나 연락처로 보이는 내용이 있어 처리하지 않았습니다. "
                   "번호를 빼고 지역·업종·업력처럼 범주로 다시 입력해 주세요.",
    "INJECTION_BLOCKED": "이 요청은 처리할 수 없습니다. 지원사업 공고의 신청 자격에 관한 질문으로 다시 입력해 주세요.",
    "LEGAL_ADVICE": "이 서비스는 법적·세무 자문을 제공하지 않습니다. 공고에 적힌 요건과 관련 정의·법령 원문까지만 보여 드릴 수 있으며, "
                    "최종 판단은 공고 주관 기관과 전문가에게 확인해 주세요.",
    "OUTPUT_BLOCKED": "요건별 확인 결과는 위와 같습니다. 이 결과는 참고용이며 신청 가능 여부와 선정은 공고 원문과 주관 기관의 판단에 따릅니다.",
    "SERVICE_DEGRADED": "지금은 설명을 만들 수 없어 판정과 요건 목록만 보여 드립니다. 판정은 규칙으로 계산한 결과입니다.",
    "STALE_DATA": "이 정보는 {as_of}에 수집한 것입니다. 이후 공고가 정정되거나 마감됐을 수 있으니 공고 원문에서 최신 내용을 확인해 주세요.",
    "FAILED": "일시적으로 답할 수 없습니다. 잠시 뒤 다시 시도해 주세요.",
}

DISCLAIMER = "이 결과는 신청 가능 여부의 참고 정보이며, 최종 판단은 공고 주관 기관이 합니다."


def render(code: str, **kw) -> str:
    try:
        return TEXT[code].format(**kw)
    except (KeyError, IndexError):
        return TEXT.get(code, TEXT["FAILED"]).replace("{", "").replace("}", "")
