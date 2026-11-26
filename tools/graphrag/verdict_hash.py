"""평가기 회귀 확인: 고정 시드 프로필 × 전체 공고(+ 합성 검수 조건)의 판정 결과를 해시 하나로 줄인다.

평가기를 리팩터링하기 전후에 돌려 해시가 같으면 판정·이유·조건 상태가 하나도 바뀌지 않은 것이다.
규칙을 일부러 바꿨다면 해시는 달라지고, 바뀐 건수는 `rule_options_impact.py`나 `build.py compare`로 본다. DB·모델은 쓰지 않는다.

사용
  python tools/graphrag/verdict_hash.py before.json            # 바꾸기 전
  python tools/graphrag/verdict_hash.py after.json             # 바꾼 뒤, 두 파일의 sha256을 비교
  python tools/graphrag/verdict_hash.py out.json --profiles 50 # 빠르게(기본 150)
  python tools/graphrag/verdict_hash.py out.json --gold <dir>  # 검수 정답 폴더를 고정 복사본으로(검수가 진행 중일 때)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag import gold_bridge  # noqa: E402
from graphrag.engine import Engine  # noqa: E402
from graphrag.evaluator import Profile, evaluate_notice  # noqa: E402


def _cond(i: int, attr: str, value: dict, negate: bool = False) -> dict:
    return {"cond_id": f"SYN#{i}", "attribute": attr, "strength": "soft", "negate": negate, "operator": "EQ",
            "value": value, "evidence": "x", "raw_value": None}


def synthetic_notices(picks: list[str]) -> list[dict]:
    """검수 조건 경로(지역 전국·상위·하위·미확정·제외, 업력·연령 비교, 미지원 속성)를 지금 데이터가 없어도 거치게 한다."""
    conds = [_cond(1, "region", {"concept_ids": ["REGION:NATIONWIDE"], "labels": ["전국"], "unresolved": []}),
             _cond(2, "region", {"concept_ids": picks[:2], "labels": ["a", "b"], "unresolved": []}),
             _cond(3, "region", {"concept_ids": picks[2:3], "labels": ["c"], "unresolved": []}, negate=True),
             _cond(4, "region", {"concept_ids": [], "labels": ["모름"], "unresolved": ["모름"]}),
             _cond(5, "business_age", {"op": "LT", "value": 3.0, "unit": "YEAR"}),
             _cond(6, "founder_age", {"op": "GTE", "value": 40.0, "unit": "YEAR"}, negate=True),
             _cond(7, "industry", {"unsupported": True})]
    out = []
    for i, c in enumerate(conds):
        tree = {"node_type": "LOGICAL_GROUP", "operator": "OR" if i % 2 else "AND",
                "children": [{"node_type": "CONDITION_REF", "condition_id": c["cond_id"]}]}
        out.append({"notice_id": f"SYN:{i}", "conditions": [],
                    "gold_requirements": [{"req_id": f"SYN:{i}#G1", "logic_tree": tree, "logic_basis": "explicit", "conditions": [c]}]})
    return out


def run(n_profiles: int = 150, gold_root: Path = gold_bridge.GOLD_ROOT) -> dict:
    e = Engine()
    gold_bridge.attach(e.notices, gold_bridge.load(gold_root))
    rng = random.Random(7)
    regions = [r for r, n in e.rg.nodes.items() if n.get("level") in ("SIDO", "SIGUNGU", "GU")]
    picks = rng.sample(regions, 6)
    notices = e.notices + synthetic_notices(picks)
    h, n = hashlib.sha256(), 0
    for _ in range(n_profiles):
        prof = Profile(region=rng.choice(regions + picks + [None, "REGION:NATIONWIDE"]),
                       business_age_years=rng.choice([None, 0.5, 2.6, 3, 3.4, 5, 12]), pre_founder=rng.choice([None, True, False]),
                       founder_age=rng.choice([None, 18, 39, 40, 45]), applicant_type=rng.choice([None, "일반인", "일반기업"]))
        for nt in notices:
            r = evaluate_notice(nt, prof, e.rg)
            h.update(json.dumps([r["verdict"], r["structured"], r["reasons"], r["requirements"],
                                 [(c.cond_id, c.status, c.reason, c.path, c.flags, c.strength, c.attribute) for c in r["conditions"]]],
                                ensure_ascii=False).encode())
            n += 1
    return {"evaluations": n, "profiles": n_profiles, "gold_root": str(gold_root), "sha256": h.hexdigest()}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("out", type=Path)
    ap.add_argument("--profiles", type=int, default=150)
    ap.add_argument("--gold", type=Path, default=gold_bridge.GOLD_ROOT)
    a = ap.parse_args()
    res = run(a.profiles, a.gold)
    a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(res["evaluations"], res["sha256"])
