"""S-01 메타 정보: 출처별 수집 시각, 버전, 면책 문구, 출처 이용 조건, 입력 구간 코드표(명세 §2.1, §3.1, S-01).

- 수집 시각은 엔진이 읽은 공고의 `fetched_at` 중 출처별 가장 늦은 값이다. 수집 기록(`ingest_runs`)이 생기면 그 값으로 바꾼다.
- `stale`은 `APP_STALE_HOURS`(기본 0 = 끔)를 넘으면 true다. 수집 주기가 정해지지 않아(KPI N-06) 기본은 끈다.
- 구간 코드표는 명세 §3.1 제안 그대로다. **임시 기본값(2026-11-28, 팀 검토 전)**: API-9(구간 경계)가 확정되면 바꾼다.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
DISCLAIMER = "이 결과는 참고용입니다. 신청 가능 여부와 선정은 공고 원문과 주관 기관의 판단에 따릅니다."
SCHEMA = "support-notice-v1"
RULE = "0.1"

# 출처 이용 조건 안내 주소. 임시 기본값(2026-11-28, 팀 검토 전): 공공데이터포털 출처는 데이터셋 페이지가 정해지면 그 주소로 바꾼다.
SOURCES = [
    {"source": "BIZINFO", "name": "기업마당", "terms_url": "https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi"},
    {"source": "KSTARTUP", "name": "K-Startup(공공데이터포털)", "terms_url": "https://www.data.go.kr"},
    {"source": "G2B", "name": "나라장터(공공데이터포털)", "terms_url": "https://www.data.go.kr"},
]

INF = None  # 위쪽 끝 없음


def _band(code: str, label: str, lo, hi) -> dict:
    """[lo, hi] 닫힌 범위(hi=None이면 끝 없음). 매출처럼 반열린 구간은 max를 "미만" 값으로 두고 max_exclusive=True를 붙인다."""
    return {"code": code, "label": label, "min": lo, "max": hi}


BANDS = {
    "EMP": [
        _band("EMP_0", "0명", 0, 0), _band("EMP_1_4", "1~4명", 1, 4), _band("EMP_5_9", "5~9명", 5, 9),
        _band("EMP_10_49", "10~49명", 10, 49), _band("EMP_50_99", "50~99명", 50, 99),
        _band("EMP_100_299", "100~299명", 100, 299), _band("EMP_300_PLUS", "300명 이상", 300, INF),
    ],
    # 매출(원)은 [min, max) 반열린 구간. max는 '미만' 값
    "REV": [
        {**_band("REV_LT_100M", "1억 원 미만", 0, 100_000_000), "max_exclusive": True},
        {**_band("REV_100M_1B", "1억~10억 원", 100_000_000, 1_000_000_000), "max_exclusive": True},
        {**_band("REV_1B_5B", "10억~50억 원", 1_000_000_000, 5_000_000_000), "max_exclusive": True},
        {**_band("REV_5B_10B", "50억~100억 원", 5_000_000_000, 10_000_000_000), "max_exclusive": True},
        {**_band("REV_10B_PLUS", "100억 원 이상", 10_000_000_000, INF), "max_exclusive": True},
    ],
    # 대표자 연령(만 나이, 닫힌 구간)
    "AGE": [
        _band("AGE_LT_20", "20세 미만", 0, 19), _band("AGE_20_29", "20~29세", 20, 29), _band("AGE_30_39", "30~39세", 30, 39),
        _band("AGE_40_49", "40~49세", 40, 49), _band("AGE_50_PLUS", "50세 이상", 50, INF),
    ],
    # 업력(년)은 [min, max) 반열린 구간. 예: BAGE_1_2 = 1년 이상 2년 미만
    "BAGE": [
        {**_band("BAGE_LT_1", "1년 미만", 0, 1), "max_exclusive": True},
        {**_band("BAGE_1_2", "1년 이상 2년 미만", 1, 2), "max_exclusive": True},
        {**_band("BAGE_2_3", "2년 이상 3년 미만", 2, 3), "max_exclusive": True},
        {**_band("BAGE_3_5", "3년 이상 5년 미만", 3, 5), "max_exclusive": True},
        {**_band("BAGE_5_7", "5년 이상 7년 미만", 5, 7), "max_exclusive": True},
        {**_band("BAGE_7_10", "7년 이상 10년 미만", 7, 10), "max_exclusive": True},
        {**_band("BAGE_10_PLUS", "10년 이상", 10, INF), "max_exclusive": True},
    ],
}


def _parse(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def data_as_of(notices) -> dict[str, str]:
    """출처별 가장 늦은 수집 시각(ISO, KST)."""
    latest: dict[str, datetime] = {}
    for n in notices:
        dt = _parse(n.get("fetched_at"))
        if dt and (n["source"] not in latest or dt > latest[n["source"]]):
            latest[n["source"]] = dt
    return {s: dt.astimezone(KST).isoformat() for s, dt in sorted(latest.items())}


def build_meta(notices, *, stale_hours: float = 0, model: str | None = None, data_snapshot: str | None = None,
               now: datetime | None = None) -> dict:
    as_of = data_as_of(notices)
    now = now or datetime.now(KST)
    stale = bool(stale_hours) and any(now - datetime.fromisoformat(v) > timedelta(hours=stale_hours) for v in as_of.values())
    return {
        "data_as_of": as_of,
        "stale": stale,
        "versions": {"rule": RULE, "data": data_snapshot, "schema": SCHEMA, "model": model},
        "disclaimer": DISCLAIMER,
        "sources": SOURCES,
        "bands": BANDS,
        "bands_status": "임시 기본값(2026-11-28, 팀 검토 전, API-9)",
    }
