"""판정 일치율(KPI N-02) 사전 측정: 서비스 판정 대 사람 판정(파일럿 라벨 B).

- 정답: `data/goldset/labels/<라벨러>/B/*.json`(사람 독립 판정, adjudication.csv 수정 반영본). 라벨 파일은 로컬 전용이라
  저장소에는 집계만 남긴다. 파일이 없으면 아무것도 쓰지 않고 끝낸다.
- 예측: 서비스와 같은 엔진(`Engine`, 검수 정답·검수 큐 반영)의 `evaluate_notice`.
- 프로필 변환(임시 기본값 2026-11-28, 팀 검토 전):
  - 지역 글자 → 지역 개념(label_eval.resolve_region), business_status "예비창업자" → pre_founder=True, "사업자" → False
  - company_size가 소기업·중기업·소상공인이면 sme_status="expected"(규모는 알지만 확인서 보유는 모른다). 그 밖은 비움
  - 업종·직원 수·매출·인증·특수 집단은 서비스 입력에 없어 넘기지 않는다
- 엔진 데이터에 없는 공고는 비교에서 빼고 그 수를 남긴다.

사용: python tools/graphrag/pilot_verdict_eval.py [--labeler baek] -> data/eval/pilot_verdict_agreement_<라벨러>_<날짜>.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag.engine import TODAY, Engine  # noqa: E402
from graphrag.evaluator import (  # noqa: E402
    ELIGIBLE,
    NEEDS_CHECK,
    NOT_ELIGIBLE,
    Profile,
    evaluate_notice,
)
from graphrag.label_eval import resolve_region  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PILOT = ROOT / "data" / "goldset" / "pilot"
LABELS = ROOT / "data" / "goldset" / "labels"
VERDICTS = [ELIGIBLE, NOT_ELIGIBLE, NEEDS_CHECK]
SME_SIZES = {"소기업", "중기업", "소상공인"}


def profiles() -> dict[str, dict]:
    out = {}
    for name in ("profiles.json", "profiles_extra.json"):
        path = PILOT / name
        if path.exists():
            out.update({p["profile_id"]: p for p in json.loads(path.read_text(encoding="utf-8"))["profiles"]})
    return out


def to_profile(p: dict) -> Profile:
    region = resolve_region(p["region"])[0] if p.get("region") else None
    status = p.get("business_status")
    return Profile(region=region, business_age_years=p.get("business_age_years"), founder_age=p.get("founder_age"),
                   pre_founder=True if status == "예비창업자" else False if status == "사업자" else None,
                   sme_status="expected" if p.get("company_size") in SME_SIZES else None)


def kappa(pairs: list[tuple[str, str]]) -> float | None:
    n = len(pairs)
    if not n:
        return None
    po = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in VERDICTS) / (n * n)
    return None if pe == 1 else (po - pe) / (1 - pe)


def evaluate(labeler: str, engine: Engine | None = None) -> dict | None:
    files = sorted((LABELS / labeler / "B").glob("*.json"))
    if not files:
        return None
    engine = engine or Engine()
    by_id, profs, today = {n["notice_id"]: n for n in engine.notices}, profiles(), date.fromisoformat(TODAY)
    pairs: list[tuple[str, str]] = []
    missing: list[str] = []
    per_notice: dict[str, dict] = {}
    for f in files:
        label = json.loads(f.read_text(encoding="utf-8"))
        n = by_id.get(label["notice_id"])
        if n is None:
            missing.append(label["notice_id"])
            continue
        rows = []
        for j in label["judgments"]:
            if j["profile_id"] not in profs or j.get("overall") not in VERDICTS:
                continue
            got = evaluate_notice(n, to_profile(profs[j["profile_id"]]), engine.rg, today=today)["verdict"]
            pairs.append((j["overall"], got))
            rows.append((j["overall"], got))
        # 라벨은 로컬 전용이라 판정 하나하나가 아니라 공고별 개수만 남긴다
        per_notice[label["notice_id"]] = {"text_requirements": n.get("text_requirements"), "judgments": len(rows),
                                          "agree": sum(a == b for a, b in rows), "service": dict(Counter(b for _, b in rows))}
    confusion = {h: {s: sum(1 for a, b in pairs if a == h and b == s) for s in VERDICTS} for h in VERDICTS}
    decided = [(a, b) for a, b in pairs if a != NEEDS_CHECK]
    return {
        "measured_at": date.today().isoformat(), "status": "팀 검토 전", "labeler": labeler, "rule_today": TODAY,
        "notices_labeled": len(files), "notices_compared": len(per_notice), "notices_missing_in_engine": missing,
        "judgments": len(pairs),
        "agreement": sum(a == b for a, b in pairs) / len(pairs) if pairs else None,
        "kappa": kappa(pairs),
        "confusion_human_to_service": confusion,
        # 위험 지표: 사람이 불가라 했는데 서비스가 가능이라 함(잘못된 신청 유도) / 사람이 가능인데 서비스가 불가(기회 놓침)
        "unsafe_eligible": confusion[NOT_ELIGIBLE][ELIGIBLE] + confusion[NEEDS_CHECK][ELIGIBLE],
        "missed_opportunity": confusion[ELIGIBLE][NOT_ELIGIBLE],
        "human_decided_service_needs_check": sum(1 for a, b in decided if b == NEEDS_CHECK),
        "human_decided": len(decided),
        "per_notice": per_notice,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="파일럿 라벨 B 대 서비스 판정")
    ap.add_argument("--labeler", default="baek")
    a = ap.parse_args(argv)
    res = evaluate(a.labeler)
    if res is None:
        print(f"라벨 없음: {LABELS / a.labeler / 'B'} (로컬 전용 파일)")
        return 0
    out = ROOT / "data" / "eval" / f"pilot_verdict_agreement_{a.labeler}_{date.today():%Y%m%d}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{out.relative_to(ROOT)}  판정 {res['judgments']}건, 일치율 {res['agreement']:.3f}, kappa {res['kappa']}, "
          f"위험(가능 오판) {res['unsafe_eligible']}, 놓침 {res['missed_opportunity']}, 엔진에 없는 공고 {len(res['notices_missing_in_engine'])}")
    print(json.dumps(res["confusion_human_to_service"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
