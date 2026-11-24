#!/usr/bin/env python3
"""정답셋 파일럿 10건의 **빈** 라벨 A 템플릿과 배정표를 만든다.

주의: 자동 추출 후보(data/graph/requirement_candidates*)는 템플릿에 넣지 않는다. 라벨러가 기계 결과에 끌리지 않게 하기 위해서다.
사용: python tools/make_pilot_templates.py
"""
import csv
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "data" / "goldset" / "pilot"
BACKSLASH = chr(92)


def norm(p: str) -> str:
    return p.replace(BACKSLASH, "/")


def materials(r: dict) -> list[str]:
    if r["source"] == "BIZINFO":
        return [norm(r["local_text"]), "원본 첨부(로컬 전용): " + norm(r["local_original"]),
                "API 필드: bsnsSumryCn(사업개요), reqstMthPapersCn(신청 방법)", r["url"]]
    aid = r["notice_id"].split(":")[1]
    return ["API 필드: aply_trgt_ctnt, aply_excl_trgt_ctnt, pbanc_ctnt, support_ctnt, eval_method, biz_enyy, biz_trgt_age, supt_regin, aply_trgt",
            f"data/kstartup/processed/kstartup_cleaned.jsonl (announcement_id={aid})",
            r["url"] + " (상세 페이지는 사람이 직접 열어 확인, 자동 수집 금지)"]


def main() -> None:
    rows = [r for r in csv.DictReader(open(REPO / "data/goldset/candidates_v0.1.csv", encoding="utf-8-sig")) if r["role"] == "PILOT"]
    (OUT / "templates").mkdir(parents=True, exist_ok=True)
    with open(OUT / "pilot_assignment.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["번호", "notice_id", "출처", "제목", "읽을 자료(요약)", "라벨러 A", "라벨러 B", "A 완료", "B 완료", "메모"])
        for i, r in enumerate(rows, 1):
            mats = materials(r)
            t = {"notice_id": r["notice_id"], "reviewer": None, "time_minutes": None, "read": [], "materials": mats, "tracks": [],
                 "requirements": [], "source_conflicts": [], "ambiguities": [],
                 "_instructions": "docs/GOLDSET_라벨링_가이드_v0.1.md의 라벨 A 스키마를 따른다. 자동 추출 후보는 보지 않는다. 비워 둔 값은 원문에 없다는 뜻이며 '제한 없음'이 아니다."}
            name = r["notice_id"].replace(":", "_") + ".label_A.json"
            (OUT / "templates" / name).write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
            w.writerow([i, r["notice_id"], r["source"], r["title"], "; ".join(mats)[:200], "", "", "", "", ""])
    print(f"{len(rows)}건 템플릿 생성: {OUT}")


if __name__ == "__main__":
    main()
