#!/usr/bin/env python3
"""용어 표준화 사전 v0.1: 실데이터의 표현 변이를 세고, 표준 용어·별칭·개념 ID로 매핑한다.

- 표현 변이 빈도는 정규식으로 센 근사치이며 '공고 수'(공고별로 한 번이라도 나오면 1건)다.
- 법령이 정의한 용어는 **로컬 법령 원문의 조문을 그대로** 인용한다(기억으로 쓰지 않는다). 원문이 없는 법령의 용어는 정의를 비워 두고 `definition_source: missing`으로 표시한다.
- 계층(IS_A)은 법령 원문이 직접 근거인 것만 `status: grounded_in_local_law_text`로 둔다. 나머지는 가설(`proposed`)이다.

사용: python tools/term_standard.py -> data/ref/term_standard_v0.1.json, data/eda/term_variants.json
"""
from __future__ import annotations

import glob
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CLEAN = REPO / "data" / "cleaned" / (REPO / "data" / "cleaned" / "LATEST").read_text().strip()
LAW = REPO / "data" / "old" / "상위법령_변환" / "텍스트"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from eda_domain import load_att_sections  # noqa: E402


def jl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").split("\n") if l.strip()]


def law_article(file: str, marker: str, length: int = 400) -> str | None:
    """로컬 법령 원문에서 marker가 시작하는 **한 줄(호·항)**을 그대로 가져온다. 이어지는 다른 호는 포함하지 않는다."""
    p = LAW / f"{file}.txt"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    i = t.find(marker)
    return t[i:].split("\n")[0].strip() if i >= 0 else None


def sme_definition() -> str | None:
    """중소기업기본법 제2조: 제1항 본문 줄과 제2항 줄(소기업·중기업 구분)을 원문 그대로 이어 붙인다(사이는 [중략])."""
    p = LAW / "중소기업기본법.txt"
    if not p.exists():
        return None
    t = p.read_text(encoding="utf-8")
    i = t.find("제2조(중소기업자의 범위)")
    block = t[i:i + 4000].split("\n제3조")[0].split("\n")
    first = block[1].strip() if len(block) > 1 else block[0].strip()
    second = next((l.strip() for l in block if l.startswith("②")), None)
    return "제2조(중소기업자의 범위)" + "\n" + first + "\n[중략]\n" + second if second else None


def main() -> None:
    N = jl(CLEAN / "notices.jsonl")
    att = load_att_sections()
    corpus: dict[str, str] = {}
    for n in N:
        if n["source_system"] == "KSTARTUP" and not (n["application_start"] and n["application_start"] >= "2025-11-24"):
            continue  # K-Startup은 접수 시작일 기준 최근 1년만
        corpus[n["notice_id"]] = (n["eligibility_text"] or "") + "\n" + att.get(n["notice_id"], "")
    src = {nid: ("BIZINFO" if nid.startswith("BIZ") else "KSTARTUP") for nid in corpus}
    tot = Counter(src.values())

    def count(patterns: dict[str, str]) -> dict[str, dict]:
        out = {}
        for k, p in patterns.items():
            rx = re.compile(p)
            c = Counter(src[nid] for nid, t in corpus.items() if rx.search(t))
            out[k] = {"BIZINFO": c["BIZINFO"], "KSTARTUP": c["KSTARTUP"], "total": c["BIZINFO"] + c["KSTARTUP"]}
        return out

    V = {
        "업력 표현(접두)": count({"업력": r"업력", "창업 N년·창업 후·창업한지": r"창업\s*(후|한지|일로부터)?\s*\d+\s*년|창업\s*후|창업한\s*지", "설립 N년·설립 후": r"설립\s*(후|일로부터)?\s*\d+\s*년|설립\s*후",
                          "사업개시(일)": r"사업\s*개시", "사업자등록(일) 기준": r"사업자\s*등록(일|증)?\s*(기준|일로부터|후)"}),
        "연산 표현(N년)": count({"N년 이내": r"\d+\s*년\s*이내", "N년 이하": r"\d+\s*년\s*이하", "N년 미만": r"\d+\s*년\s*미만", "N년 초과": r"\d+\s*년\s*초과", "N년 이상": r"\d+\s*년\s*이상"}),
        "기준일 표현": count({"공고일 기준·현재": r"공고일\s*(기준|현재)", "접수(신청) 마감일 기준": r"(접수|신청)?\s*마감일\s*(기준|현재)", "신청일·접수일 기준": r"(신청일|접수일|신청\s*시점)\s*(기준|현재)?",
                         "전년도·직전 연도": r"전년도|직전\s*(연도|년도)|전년\s", "협약(선정)일 기준": r"(협약|선정)(일|시)\s*(기준|현재)"}),
        "지역 기준 표현": count({"소재(지)": r"소재", "관내": r"관내", "거주": r"거주", "본사": r"본사", "주소(지)": r"주소", "사업장": r"사업장", "사업자등록 상 소재": r"사업자\s*등록[^\n]{0,12}(소재|주소)"}),
        "우대·제외 표현": count({"우대·가점·우선": r"우대|가점|우선\s*(선정|지원|선발)", "제외": r"제외", "불가·제한": r"신청\s*불가|지원\s*불가|참여\s*제한|제한\s*대상|결격"}),
    }
    T = count({"중소기업": r"중소기업", "소기업": r"(?<!중)소기업", "중기업": r"중기업", "소상공인": r"소상공인", "중견기업": r"중견기업", "창업기업": r"창업기업", "초기창업기업·초기창업자": r"초기\s*창업",
               "예비창업자": r"예비\s*창업", "재창업": r"재창업", "스타트업": r"스타트업", "벤처기업": r"벤처기업", "이노비즈·메인비즈": r"이노비즈|메인비즈", "사회적기업": r"사회적\s*기업",
               "협동조합": r"협동조합", "여성기업": r"여성\s*기업", "장애인기업": r"장애인\s*기업", "1인 창조기업": r"1인\s*(창조|창업)\s*기업", "개인사업자": r"개인\s*사업자", "법인": r"법인",
               "청년": r"청년", "중장년": r"중장년", "대학생": r"대학생", "청소년": r"청소년", "농업인·어업인": r"농업인|어업인|농어업인|귀어인|귀농"})
    V["신청자 유형 표현"] = T

    # 법령 원문(로컬)에서 그대로 인용하는 정의
    defs = {
        "중소기업": {"law": "중소기업기본법", "article": "제2조 제1항·제2항", "text": sme_definition()},
        "창업기업": {"law": "중소기업창업 지원법", "article": "제2조 제3호", "text": law_article("중소기업창업지원법", '3. "창업기업"이란', 200)},
        "예비창업자": {"law": "중소기업창업 지원법", "article": "제2조 제4호", "text": law_article("중소기업창업지원법", '4. "예비창업자"란', 80)},
        "초기창업기업": {"law": "중소기업창업 지원법", "article": "제2조 제10호", "text": law_article("중소기업창업지원법", '10. "초기창업기업"이란', 160)},
        "청년창업기업": {"law": "중소기업창업 지원법", "article": "제2조 제11호", "text": law_article("중소기업창업지원법", '11. "청년창업기업"이란', 100)},
        "중장년창업기업": {"law": "중소기업창업 지원법", "article": "제2조 제13호", "text": law_article("중소기업창업지원법", '13. "중장년창업기업"이란', 100)},
    }

    def ty(name, scheme="APPLICANT_TYPE", aliases=(), group="ORGANIZATION", dsrc="missing", parents=(), note="", variants_key=None):
        c = T.get(variants_key or name, {"BIZINFO": None, "KSTARTUP": None, "total": None})
        d = defs.get(name)
        return {"concept_id": f"{scheme}:{name}", "label": name, "group": group, "aliases": list(aliases), "mentions_in_notices": c,
                "definition_source": f"local_law_text:{d['law']} {d['article']}" if d and d["text"] else dsrc,
                "definition_text_verbatim": d["text"] if d and d["text"] else None, "parents": list(parents), "note": note}

    parent_sme = [{"to": "APPLICANT_TYPE:중소기업", "relation": "IS_A", "status": "grounded_in_local_law_text",
                   "basis": "중소기업기본법 제2조 제2항: \"중소기업은 대통령령으로 정하는 구분기준에 따라 소기업(小企業)과 중기업(中企業)으로 구분한다.\""}]
    types = [
        ty("중소기업", aliases=["중소기업자", "중소 기업"], note="판정 기준(업종별 매출액·자산총액, 독립성)은 대통령령에 있어 시행령 원문 확인 필요"),
        ty("소기업", parents=parent_sme, aliases=["小企業"], note="구분 기준은 대통령령(시행령)"),
        ty("중기업", parents=parent_sme, aliases=["中企業"], note="구분 기준은 대통령령(시행령)"),
        ty("소상공인", aliases=["소공인"], note="소상공인기본법·소상공인 보호 및 지원에 관한 법률 원문이 로컬에 없다. 소기업과의 포함 관계는 가설이며 확인 전", dsrc="missing"),
        ty("중견기업", note="중견기업 성장촉진 및 경쟁력 강화에 관한 특별법 원문 없음"),
        ty("창업기업", aliases=["창업 기업", "창업기업(법인·개인사업자)"], note="'사업을 개시한 날부터 7년이 지나지 아니한 기업'. 기산점은 설립일이 아니라 사업 개시일"),
        ty("초기창업기업", aliases=["초기창업자", "초기 창업"], variants_key="초기창업기업·초기창업자", note="사업 개시일부터 3년이 지나지 아니한 창업기업(대통령령 기준에 따름)"),
        ty("예비창업자", group="PERSON", aliases=["예비 창업자", "(예비)창업자", "예비창업팀"], note="'창업을 하려는 개인 등'. K-Startup 업력 옵션에서는 사업자 옵션과 별개 항목"),
        ty("재창업기업", aliases=["재창업자"], variants_key="재창업", note="'재창업하여 사업을 개시한 날부터 7년이 지나지 아니한 기업'(제2조 제6호, 원문 미인용)"),
        ty("벤처기업", group="CERTIFICATION", aliases=["벤처 기업"], note="신청자 유형이 아니라 확인 제도(`certification`)로 다룬다. 벤처기업육성에 관한 특별법 제2조의2의 요건"),
        ty("사회적기업", aliases=["사회적 기업"], note="사회적기업 육성법 원문 없음. 중소기업기본법 제2조 제1항 제2호에 따라 대통령령이 정하는 사회적기업은 중소기업에 포함될 수 있음(조건부)"),
        ty("협동조합", aliases=["사회적협동조합"], note="중소기업기본법 제2조 제1항 제3호~제5호에 따라 대통령령이 정하는 조합은 중소기업에 포함될 수 있음(조건부)"),
        ty("여성기업", note="여성기업지원에 관한 법률 원문 없음"),
        ty("장애인기업", note="장애인기업활동 촉진법 원문 없음"),
        ty("1인 창조기업", aliases=["1인 창업기업"], note="K-Startup 신청 대상 값. 근거 법령 원문 없음"),
        ty("개인사업자", note="법인과 구분되는 사업자 형태(조건 `business_form`). 창업기업 정의가 법인과 개인사업자를 모두 포함함(제2조 제3호)"),
        ty("법인", aliases=["법인사업자"], note="조건 `business_form`"),
        ty("청년", scheme="SPECIAL_GROUP", group="PERSON", note="연령 기준은 사업마다 다르다. 개념에 나이를 넣지 않고 `founder_age` 조건으로 둔다. 창업지원법의 청년창업기업은 대표자 39세 이하"),
        ty("중장년", scheme="SPECIAL_GROUP", group="PERSON", note="창업지원법의 중장년창업기업은 대표자 40세 이상"),
        ty("일반인", group="PERSON", note="K-Startup 신청 대상 값", variants_key="일반인" if "일반인" in T else "청년"),
        ty("대학생", group="PERSON", note="K-Startup 신청 대상 값. 학생 신분은 학교별 발급 서류 기준이라 시스템이 확인할 수 없는 경우가 많음"),
        ty("청소년", group="PERSON", note="K-Startup 신청 대상 값"),
        ty("대학", group="INSTITUTION", note="K-Startup 신청 대상 값", variants_key="대학생"),
        ty("연구기관", group="INSTITUTION", note="K-Startup 신청 대상 값", variants_key="대학생"),
        ty("일반기업", group="ORGANIZATION", note="K-Startup 신청 대상 값. 예비창업자·대학생 등 개인과 구분하려고 쓰는 말이며 법령 정의가 없다. "
           "중소기업과 동일시하지 않는다(B-1, 2026-11-27 결정). 기업마당 본문의 '일반기업'(우대기업과 구분한 지원 금액 차등)과는 다른 뜻이다",
           variants_key="대학생"),
    ]
    for t in types:  # 값이 없는 유형(법령용어가 아닌 K-Startup 값)의 집계는 의미가 없으므로 비운다
        if t["label"] in ("일반인", "대학", "연구기관", "일반기업"):
            t["mentions_in_notices"] = {"BIZINFO": None, "KSTARTUP": None, "total": None}
    spec = {
        "version": "v0.1", "date": "2026-11-24", "status": "proposed(검수 전)",
        "note": "표준명·별칭·개념 ID는 제안이다. 법령 정의는 로컬 법령 원문 그대로이며, 원문이 없는 법령은 비워 두었다.",
        "law_definitions_verbatim": {k: {"law": v["law"], "article": v["article"], "text": v["text"], "source": "local_law_text" if v["text"] else "missing"} for k, v in defs.items()},
        "applicant_types": types,
        "source_value_mapping": {
            "kstartup_aply_trgt": {"청소년": "APPLICANT_TYPE:청소년", "대학생": "APPLICANT_TYPE:대학생", "일반인": "APPLICANT_TYPE:일반인", "대학": "APPLICANT_TYPE:대학", "연구기관": "APPLICANT_TYPE:연구기관",
                                   "일반기업": "APPLICANT_TYPE:일반기업", "1인 창조기업": "APPLICANT_TYPE:1인 창조기업"},
            "bizinfo_trgetNm": {"중소기업": "APPLICANT_TYPE:중소기업", "소상공인": "APPLICANT_TYPE:소상공인", "창업벤처": "(복합 값: 창업기업 + 벤처기업. 판정에 쓰지 않음)", "사회적기업": "APPLICANT_TYPE:사회적기업",
                                "장애인기업": "APPLICANT_TYPE:장애인기업", "여성기업": "APPLICANT_TYPE:여성기업", "제조업": "INDUSTRY:제조업 (업종이므로 신청자 유형이 아님)"},
        },
        "business_age": {
            "standard_name": "business_age(업력)", "unit": "YEAR", "ref_start_kind_standard": "BUSINESS_START_DATE(사업 개시일)",
            "note": "창업지원법은 창업기업을 '사업을 개시한 날부터 7년이 지나지 아니한 기업'으로 정의한다. 공고는 설립일·창업일·사업자등록일을 섞어 쓰므로 `ref_start_kind`로 구분한다.",
            "operators": {"이내": "LTE", "이하": "LTE", "미만": "LT", "초과": "GT", "이상": "GTE", "지나지 아니한": "LT"},
            "ref_date_kind": {"공고일 기준·현재": "NOTICE_DATE", "접수(신청) 마감일 기준": "DEADLINE", "신청일·접수일 기준": "APPLICATION_DATE", "전년도·직전 연도": "PREV_YEAR", "협약(선정)일 기준": "AGREEMENT_DATE"},
            "kstartup_options": {"예비창업자": {"pre_founder": True}, "1년미만": {"op": "LT", "years": 1}, "2년미만": {"op": "LT", "years": 2}, "3년미만": {"op": "LT", "years": 3},
                                 "5년미만": {"op": "LT", "years": 5}, "7년미만": {"op": "LT", "years": 7}, "10년미만": {"op": "LT", "years": 10}},
            "option_rule": "허용 구간의 합집합. 전부 나열하면 제한 없음(미검증 규칙, 판정에서는 UNKNOWN 처리)",
        },
        "founder_age": {
            "standard_name": "founder_age(대표자 연령)", "unit": "YEAR_OF_AGE", "note": "'만 N세' 기준. 연령과 출생연도를 함께 적은 공고는 한 조건으로 정규화한다. 창업지원법의 청년창업기업은 대표자 39세 이하",
            "kstartup_options": {"만 20세 미만": [0, 20], "만 20세 이상 ~ 만 39세 이하": [20, 40], "만 40세 이상": [40, 200]},
        },
        "region_basis": {
            "standard": {"BUSINESS_LOCATION": ["소재", "소재지", "사업장 소재"], "JURISDICTION": ["관내"], "RESIDENCE": ["거주", "전입"], "HEADQUARTERS": ["본사", "본점"],
                         "REGISTERED_ADDRESS": ["사업자등록 상 주소", "사업자등록증 상 소재", "주소"]},
            "note": "같은 '지역' 요건이라도 기준이 소재지·거주지·본사로 달라서 `Condition.value`에 `region_basis`를 기록한다. 코드표·묶음 사전은 data/ref/ 참고",
        },
        "support_field_mapping(proposed)": {
            "standard": ["금융", "기술", "인력", "수출", "내수", "창업", "경영", "기타"],
            "kstartup_to_standard": {"사업화": ["창업"], "시설ㆍ공간ㆍ보육": ["창업"], "멘토링ㆍ컨설팅ㆍ교육": ["경영"], "행사ㆍ네트워크": ["기타"], "창업교육": ["창업"], "판로ㆍ해외진출": ["내수", "수출"],
                                     "글로벌": ["수출"], "기술개발(R&D)": ["기술"], "인력": ["인력"], "정책자금": ["금융"], "융자ㆍ보증": ["금융"]},
            "per_notice_split": {"판로ㆍ해외진출": {"수출": "해외|수출|글로벌|국제|현지|바이어", "내수": "입점|판로|쇼핑몰|라이브커머스|홈쇼핑|유통|구매상담|기획전|팝업",
                                                  "rule": "해외 키워드가 있으면 수출, 국내 판로 키워드만 있으면 내수, 둘 다 없으면 내수·수출(제목·지원 내용 기준)"}},
            "confidence": {"high": ["기술개발(R&D)", "인력", "정책자금", "융자ㆍ보증", "글로벌", "사업화", "시설ㆍ공간ㆍ보육", "멘토링ㆍ컨설팅ㆍ교육", "행사ㆍ네트워크", "창업교육", "판로ㆍ해외진출"], "low": []},
            "note": "기업마당 대분류 8개를 표준 기준으로 삼고 K-Startup 11개를 대응시켰다. 낮은 신뢰 6개는 2026-11-27 회의에서 실제 공고를 보고 확정했다(B-5). 검색 필터 전용이다.",
        },
        "corpus": {"notices": dict(tot), "note": "표현 변이는 기업마당(API 자격 문구 + 첨부 자격·제외 구간)과 K-Startup 최근 1년 자격 문구에서 센 공고 수"},
    }
    (REPO / "data" / "ref").mkdir(exist_ok=True)
    (REPO / "data" / "ref" / "term_standard_v0.1.json").write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
    (REPO / "data" / "eda" / "term_variants.json").write_text(json.dumps({"corpus": dict(tot), "variants": V}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"corpus": dict(tot), **{k: {a: b["total"] for a, b in v.items()} for k, v in V.items()}}, ensure_ascii=False, indent=1))
    print("정의 원문 확보:", {k: bool(v["text"]) for k, v in defs.items()})


if __name__ == "__main__":
    main()
