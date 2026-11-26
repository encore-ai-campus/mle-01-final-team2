"""판정 규칙 선택지별 영향: 선택지 하나만 바꿨을 때 모집 중 공고의 판정이 얼마나 바뀌는지 잰다.

회의 결정 시트(`docs/MEETING_판정규칙_결정시트_2026-11-27.md`)의 "바뀌는 것"을 숫자로 채우는 데 쓴다. DB·모델은 쓰지 않는다.

- 프로필: (1) 대표 프로필 6개(이름 붙임) (2) 무작위 프로필 300개(`build.compare`와 같은 분포·시드)
- 비교: 기본값(`DEFAULT_OPTIONS`) 대비 선택지 하나만 바꾼 판정. 판정 전환(예: NOT_ELIGIBLE → NEEDS_CHECK) 건수와 바뀐 공고 수
- 지금은 본문 요건이 없어 ELIGIBLE이 나오지 않는다(REQ_UNPARSED). 그래서 전환은 NOT_ELIGIBLE ↔ NEEDS_CHECK뿐이다.
  조건 단위 변화(충족 → UNKNOWN 등)는 `condition_changes`로 따로 센다.

사용: python tools/graphrag/rule_options_impact.py   -> data/eval/rule_options_impact.json, 표 출력
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from dataclasses import asdict, replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graphrag.engine import Engine  # noqa: E402
from graphrag.evaluator import DEFAULT_OPTIONS, OPTION_CHOICES, Profile, evaluate_notice  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "data" / "eval" / "rule_options_impact.json"
LABEL = {"c1_pre_founder_not_in_options": "C-1", "c2_business_age_all_options": "C-2", "c3_age_all_options": "C-3",
         "c4_applicant_all_options": "C-4", "c6_bizinfo_org_region": "C-6", "a1_kstartup_region": "A-1",
         "a3_pre_founder_missing_with_age": "A-3", "a6_unreviewed_group": "A-6"}


def named_profiles(e: Engine) -> dict[str, Profile]:
    sd = e.rg.find_by_name("성동구")[0]
    return {
        "예비창업자·서울 성동구·28세": Profile(region=sd, pre_founder=True, founder_age=28, applicant_type="일반인"),
        "업력 2년·대구·35세·일반기업": Profile(region="REGION:2700000000", business_age_years=2, pre_founder=False, founder_age=35, applicant_type="일반기업"),
        "업력 12년·경기·45세·일반기업": Profile(region="REGION:4100000000", business_age_years=12, pre_founder=False, founder_age=45, applicant_type="일반기업"),
        "업력 4년·광주 남구·예비창업 여부 미입력": Profile(region="REGION:1227000000", business_age_years=4, founder_age=31, applicant_type="일반기업"),
        "대학생·부산·22세·예비창업자": Profile(region="REGION:2600000000", pre_founder=True, founder_age=22, applicant_type="대학생"),
        "지역만 입력(세종)": Profile(region="REGION:3600000000"),
    }


def random_profiles(e: Engine, n: int = 300, seed: int = 20261124) -> list[Profile]:
    rng = random.Random(seed)
    regions = [r for r, x in e.rg.nodes.items() if x.get("level") in ("SIDO", "SIGUNGU")]
    return [Profile(region=rng.choice(regions + [None]), business_age_years=rng.choice([None, 0.5, 1, 2.8, 3, 5, 8, 12, 20]),
                    pre_founder=rng.choice([None, True, False]), founder_age=rng.choice([None, 18, 30, 45]),
                    applicant_type=rng.choice([None, "일반인", "일반기업"])) for _ in range(n)]


def compare(e: Engine, notices: list[dict], profiles: list[Profile], opts) -> dict:
    trans, cond_changes = Counter(), Counter()
    notices_hit, profiles_hit = set(), 0
    for prof in profiles:
        hit = False
        for n in notices:
            a, b = evaluate_notice(n, prof, e.rg), evaluate_notice(n, prof, e.rg, opts)
            for x, y in zip(a["conditions"], b["conditions"], strict=False):
                if x.cond_id == y.cond_id and x.status != y.status:
                    cond_changes[f"{x.attribute}: {x.status} → {y.status}"] += 1
            if len(a["conditions"]) != len(b["conditions"]):
                cond_changes["조건 수 변화(drop)"] += 1
            if a["verdict"] != b["verdict"]:
                trans[f"{a['verdict']} → {b['verdict']}"] += 1
                notices_hit.add(n["notice_id"])
                hit = True
        profiles_hit += hit
    return {"verdict_transitions": dict(trans), "verdict_changed": sum(trans.values()), "notices_changed": len(notices_hit),
            "profiles_changed": profiles_hit, "condition_changes": dict(cond_changes.most_common())}


def run() -> dict:
    e = Engine()
    notices = [n for n in e.notices if e.is_open(n)]
    named = named_profiles(e)
    rand = random_profiles(e)
    out = {"open_notices": len(notices), "random_profiles": len(rand), "pairs_random": len(notices) * len(rand),
           "default": asdict(DEFAULT_OPTIONS), "options": []}
    for field, choices in OPTION_CHOICES.items():
        for choice in choices:
            if choice == getattr(DEFAULT_OPTIONS, field):
                continue
            opts = replace(DEFAULT_OPTIONS, **{field: choice})
            row = {"id": LABEL[field], "field": field, "choice": choice, "random": compare(e, notices, rand, opts),
                   "named": {k: compare(e, notices, [p], opts)["verdict_transitions"] for k, p in named.items()}}
            out["options"].append(row)
            print(f"{row['id']} {field}={choice}: 판정 변화 {row['random']['verdict_changed']:,}쌍, 공고 {row['random']['notices_changed']:,}건", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    run()
