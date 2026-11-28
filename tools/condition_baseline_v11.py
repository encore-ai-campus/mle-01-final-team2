"""개발용 정답 30건(조건 116개)에 대한 조건 추출 기준선 측정. 보고서용 요약을 `data/eval/`에 쓴다.

- 채점은 팀 평가기 `tools/evaluate_condition_pipeline_v11.py`의 `evaluate_records`(정책 1.1.0)를 그대로 쓴다. 평가기는 고치지 않는다.
- 평가기 CLI는 사전 점검(preflight)이 하나라도 실패하면 점수를 내지 않는다. 이 도구는 사전 점검 결과를 함께 기록하고,
  정답·예측 해시가 맞을 때만 점수를 낸다(원문 스냅샷 해시만 다르면 점수 입력에 영향이 없으므로 계산하고 그 사실을 남긴다).
- 판정 정확도(가상 프로필 판정 대 사람 판정)는 아니다. 개발용 30건에는 판정 정답이 없다.

- `--source queue`: 검수 큐(data/reviews/requirements/queue.jsonl)의 자동 후보(규칙·LLM)를 같은 평가기로 잰다.
  큐 후보를 평가기 예측 모양으로 바꾸는 규칙(임시 기본값 2026-11-28, 팀 검토 전):
  - 규칙 속성 → 정답 필드: business_age→BUSINESS_AGE, founder_age→APPLICANT_AGE, region→BUSINESS_LOCATION(EQ, 지역 이름),
    company_size→BUSINESS_TYPE(EQ), certification→CERTIFICATION(EQ). 법령 인용(law_reference)과 제외 문장 표시(exclusion)는
    조건이 아니라 검수자용 표시라 뺀다. LLM 후보는 필드·연산자·값·단위를 그대로 쓴다.
  - 근거 위치: 큐 원문이 정답 원문과 같으면 위치를 그대로, 다르면 후보 문구를 정답 원문에서 찾아 옮긴다(못 찾으면 위치 없음).
  - 큐에는 AND/OR 논리 예측이 없어 논리 지표는 내지 않는다.

사용: python tools/condition_baseline_v11.py [--source queue] [--methods rule,llm]
      -> data/eval/gold30_extraction_baseline_<날짜>.json, gold30_queue_candidates_<방법>_<날짜>.json
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import evaluate_condition_pipeline_v11 as ev  # noqa: E402

SCORE_INPUTS_OK = {"INPUT_HASH_MISMATCH:normalized_snapshot"}  # 점수 입력(정답·예측)이 아닌 출처 확인용 해시
QUEUE = ROOT / "data" / "reviews" / "requirements" / "queue.jsonl"
RULE_FIELD = {"business_age": "BUSINESS_AGE", "founder_age": "APPLICANT_AGE", "region": "BUSINESS_LOCATION",
              "company_size": "BUSINESS_TYPE", "certification": "CERTIFICATION"}
RULE_OP = {"WITHIN": "EQ", "IS_A": "EQ", "EXISTS": "EQ"}


def _value(p: dict) -> tuple[object, str | None]:
    """후보 값 → (값, 단위). 규칙 후보는 {"value", "unit"} 또는 {"label"} 모양이다."""
    v = p.get("value")
    if isinstance(v, dict):
        if "value" in v:
            return v["value"], v.get("unit")
        return v.get("label"), None
    return v, p.get("unit")


def queue_predictions(gold_rows: list[dict], methods: set[str], queue: Path = QUEUE) -> list[dict]:
    gold = {r["notice_id"]: r for r in gold_rows}
    out: list[dict] = []
    for line in queue.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        g = gold.get(row["notice_id"])
        if g is None:
            continue
        same_text = row["source_text"] == g["source_text"]
        for p in row["prefill_candidates"]:
            if p["extraction_method"] not in methods or not p.get("attribute"):
                continue
            rule = p["extraction_method"] == "rule"
            field = RULE_FIELD.get(p["attribute"]) if rule else p["attribute"]
            if field is None:
                continue
            value, unit = _value(p)
            ref, text = p.get("evidence_reference"), p.get("raw_text") or ""
            if ref and not same_text:  # 큐 원문 위치 → 정답 원문 위치
                quote = row["source_text"][ref["start_char"]:ref["end_char"]]
                at = g["source_text"].find(quote) if quote else -1
                ref = {"start_char": at, "end_char": at + len(quote)} if at >= 0 else None
            if ref:
                text = g["source_text"][ref["start_char"]:ref["end_char"]]
            op = RULE_OP.get(p["operator"], p["operator"]) if rule else p["operator"]
            out.append({"condition_id": p["candidate_id"], "notice_id": row["notice_id"], "condition_type": p["condition_type"],
                        "category_id": field, "field": field, "operator": op, "value": value, "unit": unit, "raw_text": text,
                        "source": {"source_field": g["source_field"] if ref else None, "location": ref, "evidence_text": text}})
    return out


def summarize(result: dict, pre: dict, predictions: str | None = None, with_logic: bool = True) -> dict:
    c, logic = result["common"], [n["logic"] for n in result["notices"]]
    evidence_only = sum(p["status"] == "PARTIAL_MATCH" and p["differences"] == ["evidence"] for n in result["notices"] for p in n["pairs"])
    tp, pred, gold = c["micro"]["tp"], c["micro"]["tp"] + c["micro"]["fp"], c["micro"]["tp"] + c["micro"]["fn"]
    s = lambda key, sub: sum(x[key][sub] for x in logic)  # noqa: E731
    return {
        "measured_at": date.today().isoformat(), "status": "팀 검토 전",
        "goldset": pre["goldset_version"], "policy_version": result["policy_version"],
        "predictions": predictions or "규칙 추출기 v1 고정 기준선(configs/condition_evaluation_v11_development.json의 condition_predictions)",
        "preflight_errors": pre["errors"],
        "common": {k: c[k] for k in ("micro", "macro_by_notice", "by_source", "by_condition_type", "partial_count", "notice_count",
                                     "notices_with_misses", "notices_with_false_positives")},
        "by_field": {k: v for k, v in c["by_field"].items() if v["tp"] or v["fp"] or v["fn"] >= 2},
        "diagnostic_meaning_match_ignoring_evidence": {
            "matches": tp + evidence_only, "precision": (tp + evidence_only) / pred if pred else None,
            "recall": (tp + evidence_only) / gold if gold else None, "note": "근거 위치만 다른 부분 일치를 일치로 본 참고값. 공식 점수 아님"},
        "logic": None if not with_logic else {"relations": {k: s("logical_relation", k) for k in ("tp", "fp", "fn")},
                  "operator_correct_groups": s("operator_accuracy", "correct_groups"), "gold_groups": s("operator_accuracy", "gold_groups"),
                  "notice_structure_exact": sum(bool(x["notice_structure_exact"]) for x in logic),
                  "overcautious_unresolved": sum(x["unresolved_handling"].get("overcautious_unresolved", 0) for x in logic)},
        "safety_errors": result["safety"],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="개발용 정답 30건 조건 추출 기준선")
    ap.add_argument("--source", choices=["v1", "queue"], default="v1")
    ap.add_argument("--methods", default="rule,llm", help="--source queue일 때 쓸 후보(rule, llm)")
    a = ap.parse_args(argv)
    cfg = json.loads(ev.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    gold, cond, logic = ROOT / cfg["gold_dir"], ROOT / cfg["condition_predictions"], ROOT / cfg["logic_predictions"]
    pre = ev.preflight(gold, cond, logic)
    blocking = set(pre["errors"]) - SCORE_INPUTS_OK
    if blocking:
        print(json.dumps(pre, ensure_ascii=False, indent=2))
        return 2
    gold_rows, logic_rows = ev.read_jsonl(gold / "reviewed_condition_gold.jsonl"), ev.read_jsonl(gold / "reviewed_logic_gold.jsonl")
    if a.source == "queue":
        methods = {m.strip() for m in a.methods.split(",") if m.strip()}
        preds = queue_predictions(gold_rows, methods)
        result = ev.evaluate_records(gold_rows, logic_rows, preds, [])
        out = ROOT / "data" / "eval" / f"gold30_queue_candidates_{'_'.join(sorted(methods))}_{date.today():%Y%m%d}.json"
        summary = summarize(result, pre, f"검수 큐 자동 후보({', '.join(sorted(methods))}), {len(preds)}개", with_logic=False)
    else:
        result = ev.evaluate_records(gold_rows, logic_rows, ev.read_jsonl(cond), ev.read_jsonl(logic))
        out = ROOT / "data" / "eval" / f"gold30_extraction_baseline_{date.today():%Y%m%d}.json"
        summary = summarize(result, pre)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    m = summary["common"]["micro"]
    print(f"{out.relative_to(ROOT)}  TP {m['tp']} FP {m['fp']} FN {m['fn']}  P {m['precision']:.3f} R {m['recall']:.3f} F1 {m['f1']:.3f}"
          f"  사전 점검 오류: {pre['errors'] or '없음'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
