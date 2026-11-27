"""정답셋 파일럿: 사람이 비운 쪽(라벨 A 또는 B)을 판사 모델로 채운다. 모델 라벨은 사람 정답이 아니다.

쓰임
- 사람 두 명이 같은 공고를 서로 다른 쪽(A만, B만)만 했을 때, 모델 라벨을 세 번째 라벨러로 두고
  사람-모델 일치율을 본다(`python tools/goldset_check.py agree <사람> <모델>`).
- 결과는 data/goldset/labels/<reviewer>/{A,B}/ 에 쓴다. reviewer 기본값은 model_luna이며 파일의 reviewer 필드는 "model:<모델명>"이다.
- 사람 라벨은 읽지 않는다(독립 판정). 라벨 B는 자기 라벨 A도 보지 않고 원문과 프로필만으로 판정한다.

환경 변수(.env 또는 셸): OPENAI_API_KEY 또는 OPEN_API(필수), GOLDSET_JUDGE_MODEL(기본 gpt-6-luna), OPENAI_BASE_URL(선택)
실행
  python tools/goldset_judge_llm.py --dry-run           # 호출 없이 대상과 프롬프트 길이만 본다
  python tools/goldset_judge_llm.py --kind A B          # 라벨 A·B를 모두 만든다(이미 있는 파일은 건너뜀, --force로 덮어씀)
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import goldset_check as G  # noqa: E402

GUIDE = G.REPO / "docs" / "GOLDSET_라벨링_가이드_v0.1.md"
DEFAULT_MODEL = "gpt-6-luna"

SYSTEM = """너는 한국 정부 지원사업 공고의 정답셋 라벨러다. 아래 가이드를 그대로 따른다.
- 원문에 없는 값을 지어내지 않는다. 비어 있으면 비워 둔다.
- source_sentence는 원문 패킷에 있는 문장을 그대로(공백만 달라도 됨) 옮긴다.
- 허용 값만 쓴다. attribute: {attrs}. operator: {ops}. kind: {kinds}. logic: {logics}. ref_date_kind: {refs}. reason_codes: {reasons}.
- 그룹은 {{"cond_id","logic","children":[...]}}로 쓰고 중첩은 3단까지.
- 업력·연령·매출·직원 수 조건에는 ref_date_kind를 꼭 쓴다. company_size·applicant_type의 IS_A는 needs_definition=true.
- 연령이 출생연도로 정해지면(예: '1975년 12월 31일 이전 출생') value에 "basis":"YEAR_AGE"를 넣는다.
- JSON 객체 하나만 출력한다.

# 가이드
{guide}"""


def system_prompt() -> str:
    j = lambda s: ", ".join(sorted(s))  # noqa: E731
    return SYSTEM.format(attrs=j(G.ATTRS), ops=j(G.OPS), kinds=j(G.KINDS), logics=j(G.LOGICS), refs=j(G.REF_KINDS),
                         reasons=j(G.REASONS), guide=GUIDE.read_text(encoding="utf-8"))


def notices() -> list[str]:
    with (G.PILOT / "pilot_assignment.csv").open(encoding="utf-8-sig") as f:
        return [r["notice_id"] for r in csv.DictReader(f) if r.get("notice_id")]


def assigned_profiles() -> dict[str, list[str]]:
    out = {}
    with (G.PILOT / "profiles_assignment.csv").open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            out[r["notice_id"]] = [r[k] for k in ("프로필1", "프로필2", "프로필3", "프로필4", "프로필5") if r.get(k)]
    return out


def template(nid: str, kind: str) -> dict:
    sub = "templates" if kind == "A" else "templates_B"
    p = G.PILOT / sub / f"{nid.replace(':', '_')}.label_{kind}.json"
    return G.load_json(p) if p.exists() else {"notice_id": nid}


def user_prompt(nid: str, kind: str, profs: dict, pids: list[str]) -> str:
    packet = G.packet_text(nid)
    if kind == "A":
        task = "라벨 A(요건 정규화)를 만든다. 템플릿의 키를 채워라(requirements, tracks, source_conflicts, ambiguities)."
        extra = ""
    else:
        task = ("라벨 B(프로필별 판정)를 만든다. 아래 프로필마다 overall(ELIGIBLE/NOT_ELIGIBLE/NEEDS_CHECK), reason_codes, note를 쓴다. "
                "conditions는 빈 목록으로 둔다. NOT_ELIGIBLE과 ELIGIBLE에는 reason_codes를 쓰지 않고, NEEDS_CHECK에는 꼭 쓴다. "
                "프로필에 없는 값은 모르는 값이다(충족으로 치지 않는다).")
        extra = "\n# 프로필\n" + json.dumps([profs[p] for p in pids if p in profs], ensure_ascii=False, indent=1)
    tpl = {k: v for k, v in template(nid, kind).items() if not k.startswith("_")}
    return f"# 과제\n{task}\n\n# 템플릿\n{json.dumps(tpl, ensure_ascii=False, indent=1)}{extra}\n\n# 공고 원문 패킷\n{packet}"


def call(client, model: str, system: str, user: str) -> dict:
    r = client.chat.completions.create(model=model, messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                                       response_format={"type": "json_object"})
    return json.loads(r.choices[0].message.content)


def finish(d: dict, nid: str, kind: str, model: str, pids: list[str]) -> dict:
    d["notice_id"], d["reviewer"], d["time_minutes"] = nid, f"model:{model}", None
    d["generated_by"] = {"tool": "tools/goldset_judge_llm.py", "model": model, "independent_of_human_labels": True}
    if kind == "B":
        d["judgments"] = [j for j in d.get("judgments", []) if j.get("profile_id") in pids]
        for j in d["judgments"]:
            j.setdefault("conditions", [])
            if j.get("overall") != "NEEDS_CHECK":
                j["reason_codes"] = []
    return d


def errors(d: dict, nid: str, kind: str, profs: dict) -> list[str]:
    return G.validate_a(d, G.packet_text(nid)) if kind == "A" else G.validate_b(d, None, profs)


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", nargs="+", default=["A", "B"], choices=["A", "B"])
    ap.add_argument("--reviewer", default="model_luna")
    ap.add_argument("--notice", nargs="*", help="공고 ID(기본: 파일럿 10건)")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    try:
        from dotenv import load_dotenv
        load_dotenv(G.REPO / ".env")
    except ImportError:
        pass
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPEN_API"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPEN_API"]  # 팀 .env에서 쓰는 이름
    model = os.environ.get("GOLDSET_JUDGE_MODEL", DEFAULT_MODEL)
    profs, assign = G.profiles(), assigned_profiles()
    system = system_prompt()
    todo = [(nid, k) for nid in (args.notice or notices()) for k in args.kind]
    if args.dry_run:
        print("model:", model, "| OPENAI_API_KEY:", "있음" if os.environ.get("OPENAI_API_KEY") else "없음")
        for nid, k in todo:
            print(nid, k, "프롬프트 글자 수", len(system) + len(user_prompt(nid, k, profs, assign.get(nid, []))))
        return 0
    if not os.environ.get("OPENAI_API_KEY"):
        print("OPENAI_API_KEY가 없다. .env에 넣고 다시 실행한다.")
        return 2
    from openai import OpenAI
    client = OpenAI(base_url=os.environ.get("OPENAI_BASE_URL") or None)
    failed = 0
    for nid, k in todo:
        out = G.LABELS / args.reviewer / k / f"{nid.replace(':', '_')}.json"
        if out.exists() and not args.force:
            print("건너뜀(있음):", out.name, k)
            continue
        pids = assign.get(nid, [])
        user = user_prompt(nid, k, profs, pids)
        d = finish(call(client, model, system, user), nid, k, model, pids)
        errs = errors(d, nid, k, profs)
        if errs:  # 한 번만 오류를 알려 주고 다시 받는다
            fix = user + "\n\n# 앞 답의 검사 오류(고쳐서 JSON 전체를 다시 낸다)\n" + "\n".join(errs) + "\n\n# 앞 답\n" + json.dumps(d, ensure_ascii=False)
            d = finish(call(client, model, system, fix), nid, k, model, pids)
            errs = errors(d, nid, k, profs)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(d, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        failed += bool(errs)
        print(("오류 " + str(len(errs)) if errs else "OK"), nid, k, *errs[:3], sep=" | ")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
