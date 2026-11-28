"""요건 검수 큐 API(B-3 ②, 설계 docs/DESIGN_요건검수큐_v0.1.md). 관리자만 쓴다(`require_admin`).

  GET  /api/admin/reviews                 큐 목록(상태·출처·모집 중·검색어 필터, 우선순위 순)
  GET  /api/admin/reviews/{notice_id}     한 공고: 원문·구역·사전 채움·작성한 조건과 입력 목록
  PUT  /api/admin/reviews/{notice_id}     저장(action=save: 작업 중, verify: 검수 완료, reopen: 다시 작업)
  POST /api/admin/reviews/ingest          VERIFIED 공고를 판정 입력(gold_bridge)으로 반영. 판정에 쓰려면 API를 다시 띄운다

- 조건의 근거 문장은 서버가 원문[시작:끝]에서 잘라 쓰고, id도 서버가 만든다(검수자가 적은 근거·id는 믿지 않는다).
- 검수 완료는 ingest와 같은 검사(check_row)를 통과해야 저장된다. 통과하지 못하면 422와 문제 목록을 돌려주고 작업 중으로 남긴다.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..core.errors import api_error
from ..dependencies import get_review_store
from ..dependencies.auth import CurrentUser, require_admin
from ..repositories.review_queue import ReviewQueueStore

router = APIRouter(prefix="/api/admin/reviews", tags=["admin"])

# 검수자가 고를 수 있는 속성. 판정 규칙이 있는 것은 업력·대표자 나이·소재지·기업 유형뿐이고, 나머지는 평가기에서 UNKNOWN(확인 필요)이다
FIELDS = [
    {"field": "BUSINESS_AGE", "label": "업력", "kind": "number", "unit": "YEAR", "evaluated": True},
    {"field": "REPRESENTATIVE_AGE", "label": "대표자 나이", "kind": "number", "unit": "YEAR", "evaluated": True},
    {"field": "BUSINESS_LOCATION", "label": "사업장 소재지", "kind": "labels", "unit": None, "evaluated": True},
    {"field": "BUSINESS_TYPE", "label": "기업 유형(중소기업 등)", "kind": "labels", "unit": None, "evaluated": True},
    {"field": "CERTIFICATION", "label": "인증·확인서", "kind": "labels", "unit": None, "evaluated": False},
    {"field": "INDUSTRY", "label": "업종", "kind": "labels", "unit": None, "evaluated": False},
    {"field": "APPLICANT_TYPE", "label": "신청자 유형(사회적기업 등)", "kind": "labels", "unit": None, "evaluated": False},
    {"field": "EMPLOYEE_COUNT", "label": "상시 근로자 수", "kind": "number", "unit": "PERSON", "evaluated": False},
    {"field": "REVENUE_FINANCIAL", "label": "매출·재무", "kind": "number", "unit": None, "evaluated": False},
    {"field": "QUALITATIVE_QUALIFICATION", "label": "정성 자격(초격차 기업 등)", "kind": "text", "unit": None, "evaluated": False},
    {"field": "OTHER", "label": "기타(평가 규칙 없음)", "kind": "text", "unit": None, "evaluated": False},
]
FIELD = {f["field"]: f for f in FIELDS}
OPERATORS = {"number": ["LT", "LTE", "GT", "GTE", "EQ"], "labels": ["IN", "EQ"], "text": ["EQ", "EXISTS"]}


class ConditionIn(BaseModel):
    condition_type: Literal["ELIGIBILITY", "EXCLUSION", "PREFERENCE"]
    field: str
    operator: str
    value: float | list[str] | str | None = None
    start_char: int = Field(ge=0)
    end_char: int = Field(gt=0)
    review_comment: str | None = None


class ReviewIn(BaseModel):
    action: Literal["save", "verify", "reopen"]
    conditions: list[ConditionIn] = []
    logic: Literal["AND", "OR"] = Field("AND", description="자격(ELIGIBILITY) 조건 사이 논리. 제외 조건은 따로 AND")
    whole_notice_conditions_complete: bool = False
    none_in_text: bool = Field(False, description="원문에 판정할 자격 조건이 없음(CONFIRMED_NONE_IN_PROVIDED_TEXT)")
    review_comment: str = ""


def _summary(r: dict) -> dict:
    return {k: r.get(k) for k in ("notice_id", "title", "source_system", "is_open", "deadline", "priority_rank", "priority_reasons",
                                  "review_status", "adjudication_status", "reviewer", "reviewed_at", "stale_source")} | {
        "n_prefill": len(r.get("prefill_candidates", [])), "n_conditions": len(r.get("gold_conditions", []))}


def _store(store: ReviewQueueStore) -> ReviewQueueStore:
    if not store.available():
        raise api_error(503, "QUEUE_NOT_BUILT", "검수 큐가 없습니다. python tools/requirement_review_queue.py build로 먼저 만드세요.")
    return store


@router.get("")
def list_reviews(status: str | None = Query(None, description="UNREVIEWED·NEEDS_REVIEW·VERIFIED"), source: str | None = None,
                 open_only: bool = False, q: str | None = None, offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=200),
                 user: CurrentUser = Depends(require_admin), store: ReviewQueueStore = Depends(get_review_store)) -> dict:
    rows = _store(store).rows()
    counts: dict[str, int] = {}
    for r in rows:
        counts[r.get("review_status", "UNREVIEWED")] = counts.get(r.get("review_status", "UNREVIEWED"), 0) + 1
    sel = [r for r in rows if (not status or r.get("review_status") == status) and (not source or r.get("source_system") == source)
           and (not open_only or r.get("is_open")) and (not q or q in (r.get("title") or "") or q in r["notice_id"])]
    return {"total": len(sel), "counts": counts, "stale": sum(1 for r in rows if r.get("stale_source")),
            "items": [_summary(r) for r in sel[offset:offset + limit]]}


@router.get("/{notice_id}")
def get_review(notice_id: str, user: CurrentUser = Depends(require_admin), store: ReviewQueueStore = Depends(get_review_store)) -> dict:
    r = _store(store).get(notice_id)
    if r is None:
        raise api_error(404, "NOT_FOUND", "검수 큐에 없는 공고입니다.")
    r.pop("_sort", None)
    return {"review": r, "fields": FIELDS, "operators": OPERATORS}


def _value(c: ConditionIn) -> tuple[object, str | None]:
    f = FIELD.get(c.field)
    if f is None:
        raise ValueError(f"알 수 없는 속성 {c.field}")
    if c.operator not in OPERATORS[f["kind"]]:
        raise ValueError(f"{f['label']}에 쓸 수 없는 연산자 {c.operator}")
    if f["kind"] == "number":
        if not isinstance(c.value, (int, float)):
            raise ValueError(f"{f['label']} 값은 숫자여야 합니다")
        return (int(c.value) if float(c.value).is_integer() else float(c.value)), f["unit"]
    if f["kind"] == "labels":
        vals = c.value if isinstance(c.value, list) else [x.strip() for x in str(c.value or "").split(",")]
        vals = [str(x).strip() for x in vals if str(x).strip()]
        if not vals:
            raise ValueError(f"{f['label']} 값을 하나 이상 적어 주세요")
        return (vals if c.operator == "IN" else vals[0]), None
    return (str(c.value or "").strip() or None), None


def build_conditions(row: dict, items: list[ConditionIn], verified: bool) -> list[dict]:
    from tools.requirement_review_queue import make_id

    text = row["source_text"]
    out, errs = [], []
    for i, c in enumerate(items, 1):
        if not c.start_char < c.end_char <= len(text):
            errs.append(f"{i}번 조건: 근거 위치가 원문 밖입니다")
            continue
        try:
            value, unit = _value(c)
        except ValueError as e:
            errs.append(f"{i}번 조건: {e}")
            continue
        raw = text[c.start_char:c.end_char]
        out.append({"gold_condition_id": make_id(row["notice_id"], c.condition_type, c.start_char, c.end_char, raw),
                    "condition_type": c.condition_type, "field": c.field, "category": c.field, "operator": c.operator,
                    "value": value, "unit": unit, "raw_text": raw, "source_field": row["source_field"],
                    "evidence_reference": {"start_char": c.start_char, "end_char": c.end_char}, "reference_date_type": "UNKNOWN",
                    "review_status": "VERIFIED" if verified else "UNREVIEWED", "review_comment": c.review_comment})
    if errs:
        raise api_error(422, "INVALID_CONDITIONS", "조건을 확인해 주세요.", errors=errs)
    ids = [c["gold_condition_id"] for c in out]
    if len(ids) != len(set(ids)):
        raise api_error(422, "INVALID_CONDITIONS", "같은 근거·종류의 조건이 두 번 있습니다.", errors=["중복 조건"])
    return out


def logic_roots(notice_id: str, conds: list[dict], op: str) -> list[dict]:
    """자격 조건이 2개 이상이고 OR면 OR 묶음 하나. AND는 gold_bridge가 AND로 묶으므로 따로 적지 않는다(logic_basis=assumed 아님을 남기려 적는다)."""
    elig = [c["gold_condition_id"] for c in conds if c["condition_type"] == "ELIGIBILITY"]
    if len(elig) < 2:
        return []
    return [{"node_type": "LOGICAL_GROUP", "group_id": f"{notice_id}#R1", "operator": op, "review_status": "VERIFIED",
             "children": [{"node_type": "CONDITION_REF", "condition_id": x} for x in elig]}]


@router.put("/{notice_id}")
def save_review(notice_id: str, body: ReviewIn, user: CurrentUser = Depends(require_admin),
                store: ReviewQueueStore = Depends(get_review_store)) -> dict:
    from tools.requirement_review_queue import check_row

    row = _store(store).get(notice_id)
    if row is None:
        raise api_error(404, "NOT_FOUND", "검수 큐에 없는 공고입니다.")
    if body.action == "reopen":
        def reopen(r: dict) -> dict:
            return {**r, "review_status": "NEEDS_REVIEW", "adjudication_status": "PENDING", "reviewed_at": None,
                    "gold_conditions": [{**c, "review_status": "UNREVIEWED"} for c in r.get("gold_conditions", [])]}
        saved = store.update(notice_id, reopen)
        saved.pop("_sort", None)
        return {"review": saved, "errors": []}

    verified = body.action == "verify"
    if body.none_in_text and body.conditions:
        raise api_error(422, "INVALID_CONDITIONS", "'원문에 자격 조건 없음'과 조건을 함께 둘 수 없습니다.", errors=["조건 없음 표시와 조건이 함께 있음"])
    conds = build_conditions(row, body.conditions, verified)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    new = {**row, "gold_conditions": conds, "missed_condition_candidates": [],
           "gold_logic_roots": logic_roots(notice_id, conds, body.logic) if body.logic == "OR" else [],
           "logic_operator": body.logic, "whole_notice_conditions_complete": body.whole_notice_conditions_complete,
           "review_comment": body.review_comment, "reviewer": user.user_id,
           "review_status": "VERIFIED" if verified else "NEEDS_REVIEW",
           "adjudication_status": ("CONFIRMED_NONE_IN_PROVIDED_TEXT" if body.none_in_text else "REVIEWED_COMPLETE") if verified else "PENDING",
           "reviewed_at": now if verified else None, "updated_at": now}
    if verified:
        if not conds and not body.none_in_text:
            raise api_error(422, "INVALID_CONDITIONS", "조건이 없으면 '원문에 자격 조건 없음'을 표시해 주세요.", errors=["조건 없음"])
        errs = check_row(new)
        if errs:  # 검사에 걸리면 작업 중으로만 저장한다
            draft = {**new, "review_status": "NEEDS_REVIEW", "adjudication_status": "PENDING", "reviewed_at": None,
                     "gold_conditions": [{**c, "review_status": "UNREVIEWED"} for c in conds]}
            store.update(notice_id, lambda r: {**draft, "_sort": r.get("_sort")})
            raise api_error(422, "REVIEW_CHECK_FAILED", "검수 완료 검사를 통과하지 못해 작업 중으로 저장했습니다.", errors=errs)
    saved = store.update(notice_id, lambda r: {**new, "_sort": r.get("_sort")})
    saved.pop("_sort", None)
    return {"review": saved, "errors": []}


@router.post("/ingest")
def ingest_reviews(user: CurrentUser = Depends(require_admin), store: ReviewQueueStore = Depends(get_review_store)) -> dict:
    from tools.requirement_review_queue import ingest

    rep = ingest(_store(store).path)
    return {**rep, "note": "판정 엔진은 시작할 때 검수 결과를 읽습니다. API를 다시 띄우면 반영됩니다."}
