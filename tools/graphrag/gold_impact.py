"""검수 정답(gold_bridge)을 붙이기 전과 뒤의 판정 비교. 정답 판을 바꿀 때 서비스 판정이 얼마나 바뀌는지 잰다.

`Engine`은 정답을 판정에 쓰므로(`engine.py`) 정답 판을 바꾸면 그래프 내보내기뿐 아니라 서비스 판정도 바뀐다.
- 비교: 정답이 붙은 공고마다, 정답 없음(본문 요건 unparsed) 대 지금 정답(`gold_bridge.GOLD_ROOT`)
- 프로필: rule_options_impact와 같은 대표 6개 + 무작위 300개(같은 시드)
- DB·모델은 쓰지 않는다

사용: python tools/graphrag/gold_impact.py  -> data/eval/gold_v11_impact.json
"""
from __future__ import annotations

import copy
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag import gold_bridge  # noqa: E402
from graphrag.engine import TODAY, Engine  # noqa: E402
from graphrag.evaluator import DEFAULT_OPTIONS, evaluate_notice  # noqa: E402
from graphrag.rule_options_impact import named_profiles, random_profiles  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "eval" / "gold_v11_impact.json"


def without_gold(n: dict) -> dict:
    """정답을 붙이기 전 공고(본문 요건 unparsed)."""
    m = copy.deepcopy(n)
    m.pop("gold_requirements", None)
    m.pop("gold_review", None)
    m["text_requirements"] = "unparsed"
    return m


def compare(e: Engine, notices: list[dict], profiles) -> dict:
    trans, per_notice = Counter(), Counter()
    today = date.fromisoformat(TODAY)
    before = {n["notice_id"]: without_gold(n) for n in notices}
    for prof in profiles:
        for n in notices:
            a = evaluate_notice(before[n["notice_id"]], prof, e.rg, DEFAULT_OPTIONS, today=today)["verdict"]
            b = evaluate_notice(n, prof, e.rg, DEFAULT_OPTIONS, today=today)["verdict"]
            if a != b:
                trans[f"{a} → {b}"] += 1
                per_notice[n["notice_id"]] += 1
    return {"verdict_transitions": dict(trans), "verdict_changed": sum(trans.values()), "notices_changed": len(per_notice),
            "by_notice": dict(per_notice.most_common())}


def run() -> dict:
    e = Engine()
    gold = [n for n in e.notices if n.get("gold_requirements")]
    open_gold = [n for n in gold if e.is_open(n)]
    rand = random_profiles(e)
    after = Counter(evaluate_notice(n, p, e.rg, DEFAULT_OPTIONS, today=date.fromisoformat(TODAY))["verdict"] for n in gold for p in rand)
    out = {"gold_root": str(gold_bridge.GOLD_ROOT.relative_to(Path(__file__).resolve().parents[2])).replace("\\", "/"),
           "gold_notices": len(gold), "gold_notices_open": len(open_gold),
           "requirements": sum(len(n["gold_requirements"]) for n in gold),
           "text_requirements": dict(Counter(n["text_requirements"] for n in gold)),
           "random_profiles": len(rand), "pairs": len(gold) * len(rand),
           "random": compare(e, gold, rand), "random_open_only": compare(e, open_gold, rand),
           "verdicts_after": dict(after),
           "named": {k: compare(e, gold, [p])["verdict_transitions"] for k, p in named_profiles(e).items()}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    r = run()
    print({k: r[k] for k in ("gold_notices", "gold_notices_open", "requirements", "text_requirements", "pairs", "verdicts_after")})
    print("전체:", {k: r["random"][k] for k in ("verdict_transitions", "notices_changed")})
    print("모집 중만:", {k: r["random_open_only"][k] for k in ("verdict_transitions", "notices_changed")})
    print("대표 프로필:", r["named"])
