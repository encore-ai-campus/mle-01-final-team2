#!/usr/bin/env python3
"""정답셋 파일럿 10건의 작업 자료를 만든다: 빈 라벨 A·B 템플릿, 자료 패킷, 공통 프로필 8종, 프로필 배정표.

주의: 자동 추출 후보(data/graph/requirement_candidates*)와 요건 절 위치 힌트는 넣지 않는다. 라벨러가 기계 결과에 끌리지 않게 하기 위해서다.
패킷(data/goldset/pilot/packets/)은 공고 원문이므로 git에 올리지 않는다(.gitignore).
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


PROFILES = [
    {"profile_id": "P1", "summary": "서울 성동구, 법인 제조업, 업력 2년, 대표 만 35세, 소기업, 직원 8명", "region": "서울 성동구", "business_status": "사업자", "business_age_years": 2, "founder_age": 35, "company_size": "소기업", "industry": "제조업", "employees": 8, "revenue_krw": None, "certifications": [], "gender": None, "special_group": []},
    {"profile_id": "P2", "summary": "경북 구미시, 개인사업자 도소매업, 업력 8년, 대표 만 45세, 소상공인, 직원 3명", "region": "경북 구미시", "business_status": "사업자", "business_age_years": 8, "founder_age": 45, "company_size": "소상공인", "industry": "도소매업", "employees": 3, "revenue_krw": None, "certifications": [], "gender": None, "special_group": []},
    {"profile_id": "P3", "summary": "사업자 없음(예비창업자), 경남 창원시 거주, 만 24세", "region": "경남 창원시", "business_status": "예비창업자", "business_age_years": None, "founder_age": 24, "company_size": None, "industry": None, "employees": None, "revenue_krw": None, "certifications": [], "gender": None, "special_group": []},
    {"profile_id": "P4", "summary": "광주 남구, 법인 서비스업, 업력 5년, 만 39세, 중기업(구 광주광역시 지역)", "region": "광주 남구", "business_status": "사업자", "business_age_years": 5, "founder_age": 39, "company_size": "중기업", "industry": "서비스업", "employees": None, "revenue_krw": None, "certifications": [], "gender": None, "special_group": []},
    {"profile_id": "P5", "summary": "충북 청주시, 법인 IT업, 업력 0.5년, 만 29세, 벤처기업 확인서 보유", "region": "충북 청주시", "business_status": "사업자", "business_age_years": 0.5, "founder_age": 29, "company_size": None, "industry": "IT업", "employees": None, "revenue_krw": None, "certifications": ["벤처기업 확인서"], "gender": None, "special_group": []},
    {"profile_id": "P6", "summary": "경기 성남시, 여성 대표 법인, 업력 정확히 3년, 만 40세 정각(경계값)", "region": "경기 성남시", "business_status": "사업자", "business_age_years": 3.0, "founder_age": 40, "company_size": None, "industry": None, "employees": None, "revenue_krw": None, "certifications": None, "gender": "여성", "special_group": []},
    {"profile_id": "P7", "summary": "대전, 사회적기업 인증, 업력 10년, 직원 12명, 연 매출 30억 원", "region": "대전", "business_status": "사업자", "business_age_years": 10, "founder_age": None, "company_size": None, "industry": None, "employees": 12, "revenue_krw": 3000000000, "certifications": ["사회적기업 인증"], "gender": None, "special_group": []},
    {"profile_id": "P8", "summary": "제주시, 양식업 예정자(사업자 미등록), 만 36세", "region": "제주시", "business_status": "예비창업자", "business_age_years": None, "founder_age": 36, "company_size": None, "industry": "양식업", "employees": None, "revenue_krw": None, "certifications": [], "gender": None, "special_group": []},
]
PROFILE_NOTE = "null은 '미입력'(알 수 없음)이다. 빈 배열 []은 '해당 없음'이다. 미입력이 필요한 조건은 UNKNOWN이다. 공고별 경계값·미입력 프로필은 profiles_extra.json에 PX-<공고번호끝6자리>-<번호>로 추가한다."


def packet(r: dict) -> str:
    """공고 원문 자료. 기계 후보·절 위치 힌트는 넣지 않는다."""
    nid = r["notice_id"]
    out = [f"# {nid}", f"제목: {r['title']}", f"URL: {r['url']}", ""]
    if r["source"] == "BIZINFO":
        rec = next((json.loads(l) for l in open(REPO / "data/cleaned/20261124/notices.jsonl", encoding="utf-8") if json.loads(l)["notice_id"] == nid), {})
        for k, label in (("org_raw", "소관기관"), ("executor_org_name", "수행기관"), ("application_start", "신청 시작"), ("application_end", "신청 종료"), ("region_tags_hint", "지역 태그(API 해시태그, 본문과 다를 수 있음)"), ("structured", "구조화 필드"),
                         ("eligibility_text", "지원대상(API)"), ("body_text", "사업개요(API)"), ("support_text", "지원내용(API)"), ("evaluation_text", "평가(API)"), ("apply_method_text", "신청방법(API)")):
            if rec.get(k):
                out += [f"## {label}", json.dumps(rec[k], ensure_ascii=False) if not isinstance(rec[k], str) else rec[k], ""]
        lt = REPO / norm(r["local_text"])
        if r["local_text"] and lt.exists() and lt.suffix == ".txt":
            out += ["## 첨부 추출 텍스트(원문 그대로, 표·서식이 깨졌으면 원본 파일을 연다)", f"파일: {norm(r['local_text'])}", lt.read_text(encoding="utf-8", errors="replace")[:200000], ""]
        elif r["local_text"]:
            out += [f"## 첨부 원본: {norm(r['local_text'])} (텍스트 추출본 없음, 원본을 직접 연다)", ""]
    else:
        aid = nid.split(":")[1]
        rec = next((json.loads(l) for l in open(REPO / "data/kstartup/raw/20261124_full/announcements_all.jsonl", encoding="utf-8") if str(json.loads(l).get("pbanc_sn")) == aid), {})
        for k, label in (("pbanc_ntrp_nm", "공고기관"), ("pbanc_rcpt_bgng_dt", "접수 시작"), ("pbanc_rcpt_end_dt", "접수 종료"), ("supt_regin", "지원 지역(API)"), ("aply_trgt", "신청 대상 구분(API)"), ("biz_enyy", "업력(API)"), ("biz_trgt_age", "대상 연령(API)"),
                         ("aply_trgt_ctnt", "신청 대상 내용"), ("aply_excl_trgt_ctnt", "신청 제외 대상"), ("pbanc_ctnt", "공고 내용"), ("support_ctnt", "지원 내용"), ("eval_method", "평가 방법")):
            if rec.get(k):
                out += [f"## {label}", str(rec[k]), ""]
        out += ["상세 페이지는 사람이 직접 열어 확인한다(자동 수집 금지).", ""]
    return chr(10).join(out)


def main() -> None:
    rows = [r for r in csv.DictReader(open(REPO / "data/goldset/candidates_v0.1.csv", encoding="utf-8-sig")) if r["role"] == "PILOT"]
    (OUT / "templates").mkdir(parents=True, exist_ok=True)
    (OUT / "packets").mkdir(exist_ok=True)
    (OUT / "templates_B").mkdir(exist_ok=True)
    (OUT / "profiles.json").write_text(json.dumps({"note": PROFILE_NOTE, "profiles": PROFILES}, ensure_ascii=False, indent=1), encoding="utf-8")
    ex = OUT / "profiles_extra.json"
    if not ex.exists():
        ex.write_text(json.dumps({"note": PROFILE_NOTE, "profiles": []}, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT / "profiles_assignment.csv", "w", encoding="utf-8-sig", newline="") as f:
        w2 = csv.writer(f)
        w2.writerow(["notice_id", "프로필1", "프로필2", "프로필3", "프로필4", "프로필5", "배정자", "메모(조건에 맞을 것 같음/아님/경계/미입력 구분)"])
        for r in rows:
            w2.writerow([r["notice_id"], "", "", "", "", "", "", ""])
    with open(OUT / "pilot_assignment.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["번호", "notice_id", "출처", "제목", "읽을 자료(요약)", "라벨러 A", "라벨러 B", "A 완료", "B 완료", "메모"])
        for i, r in enumerate(rows, 1):
            mats = materials(r)
            t = {"notice_id": r["notice_id"], "reviewer": None, "time_minutes": None, "read": [], "materials": mats, "tracks": [],
                 "requirements": [], "source_conflicts": [], "ambiguities": [],
                 "_instructions": "docs/GOLDSET_라벨링_가이드_v0.1.md의 라벨 A 스키마를 따른다. 자동 추출 후보는 보지 않는다. 비워 둔 값은 원문에 없다는 뜻이며 '제한 없음'이 아니다."}
            stem = r["notice_id"].replace(":", "_")
            (OUT / "packets" / (stem + ".txt")).write_text(packet(r), encoding="utf-8")
            b = {"notice_id": r["notice_id"], "reviewer": None, "time_minutes": None,
                 "judgments": [{"profile_id": None, "overall": None, "conditions": [{"cond_ref": None, "result": None, "why": ""}], "reason_codes": []}],
                 "_instructions": "라벨 A를 열지 않고 공고 원문으로 판정한다. judgments에 배정된 프로필 5개를 쓴다. cond_ref는 자신이 쓴 라벨 A의 cond_id다(라벨 A 작성 뒤 채운다)."}
            (OUT / "templates_B" / (stem + ".label_B.json")).write_text(json.dumps(b, ensure_ascii=False, indent=2), encoding="utf-8")
            name = stem + ".label_A.json"
            (OUT / "templates" / name).write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")
            w.writerow([i, r["notice_id"], r["source"], r["title"], "; ".join(mats)[:200], "", "", "", "", ""])
    print(f"{len(rows)}건 템플릿 생성: {OUT}")


if __name__ == "__main__":
    main()
