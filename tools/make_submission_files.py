#!/usr/bin/env python3
"""온톨로지 설계서 제출 파일 5종을 설계서 표와 데이터에서 만든다 (표준 라이브러리만 사용).

- entities.csv          설계서 §4.1 클래스 표
- relationships.csv     설계서 §5.2 관계 표(+유효기간 필드)
- cq_tests.xlsx         설계서 §2 CQ 표 + 시험 입력·기대 결과·현재 상태(정직하게: 시험하지 않은 것은 '미실행')
- schema.cypher         설계서 §8 Cypher(실행하지 않음) + 인덱스
- evidence_manifest.csv 설계서 §6 S-P-O와 근거 문장, 근거가 현재 데이터에 그대로 있는지 검사한 결과

사용: python tools/make_submission_files.py   -> docs/submission/ontology/
"""
from __future__ import annotations

import csv
import glob
import json
import re
import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "docs" / "submission" / "ontology"
NL = chr(10)
MD = Path(glob.glob(str(REPO / "docs" / "[[]도메인온톨로지[]]*.md"))[0]).read_text(encoding="utf-8")


def table_after(heading: str) -> list[list[str]]:
    """heading 줄 뒤에 나오는 첫 번째 마크다운 표를 행 목록으로 반환한다(머리글 포함)."""
    i = MD.index(heading)
    lines = MD[i:].split(NL)
    rows, started = [], False
    for l in lines[1:]:
        if l.startswith("|"):
            started = True
            cells = [c.strip().replace("\x00", "|") for c in l.strip().replace("\\|", "\x00").strip("|").split("|")]
            if not re.match(r"^[\s\-:|]+$", l):
                rows.append(cells)
        elif started:
            break
    return rows


def clean(s: str) -> str:
    return re.sub(r"\*\*|`", "", s)


def write_csv(name: str, header: list[str], rows: list[list]) -> None:
    with open(OUT / name, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


# ---------------------------------------------------------------- entities.csv
LAYER = {"Notice": "메타", "Organization": "메타", "SupportCategory": "메타", "Attachment": "메타", "Tag": "메타", "Region": "개념",
         "Program": "요건", "Track": "요건", "Requirement": "요건", "Condition": "요건", "Concept": "개념", "Definition": "개념", "ExternalLaw": "개념"}


def entities() -> int:
    rows = table_after("### 4.1 클래스")[1:]
    out = []
    for r in rows:
        name = clean(r[0])
        key = re.split(r"[ →(]", name)[0]
        out.append([name, LAYER.get(key, ""), clean(r[1]), clean(r[2]), clean(r[3])])
    write_csv("entities.csv", ["클래스", "층", "식별자(예)", "핵심 속성", "현재 데이터·예시(2026-11-24)"], out)
    return len(out)


# ---------------------------------------------------------------- relationships.csv
VALID = {"SUPERSEDES": "새 버전 fetched_at부터(version, is_latest)", "WITHIN": "code_version(코드표 기준일), 묶음은 reviewed", "TARGETS_REGION": "code_version",
         "HAS_REQUIREMENT": "공고 버전(content_hash)과 접수기간", "HAS_CONDITION": "공고 버전", "ABOUT": "code_version", "DEFINED_BY": "법령 시행일·text_hash",
         "CITES_LAW": "법령 시행일·text_hash", "ANNOUNCED_BY": "fetched_at", "EXECUTED_BY": "fetched_at", "IN_SUPPORT_CATEGORY": "fetched_at", "HAS_ATTACHMENT": "fetched_at",
         "HAS_TAG": "fetched_at", "IS_A": "code_version", "SAME_AS": "fetched_at", "HAS_TRACK": "공고 버전", "OF_PROGRAM": "공고 버전"}


def relationships() -> int:
    rows = table_after("### 5.2 관계 정의")[1:]
    out = [[clean(r[0]), clean(r[1]), clean(r[2]), clean(r[3]), clean(r[4]), VALID.get(clean(r[0]), "-")] for r in rows]
    write_csv("relationships.csv", ["관계 타입", "시작→끝", "의미", "카디널리티/제약", "층·상태", "유효기간 기준"], out)
    return len(out)


# ---------------------------------------------------------------- schema.cypher
def schema() -> int:
    blocks = re.findall(r"```cypher" + NL + r"(.*?)" + NL + r"```", MD, re.S)
    blocks.sort(key=lambda b: 0 if "CREATE CONSTRAINT" in b else 1)  # 제약·스키마를 먼저, 점검·경로 쿼리는 뒤
    body = (NL + NL).join(blocks)  # 8절 스키마·예시 + 5.4 점검 쿼리 + 7절 경로 쿼리
    head = ("// 도메인 온톨로지 설계서 v0.2 Neo4j 스키마 초안 (이 파일은 실행하지 않았다)" + NL +
            "// 출처: 설계서 §8(스키마·예시), §5.4(점검 쿼리), §7(경로 쿼리). 적재 대상 인스턴스(공용 Aura)가 정해지기 전에는 실행하지 않는다." + NL +
            "// 적재 입력: data/graph/nodes.jsonl, edges.jsonl (tools/graphrag/build.py export, 로컬 전용)" + NL + NL)
    extra = (NL + NL + "// 추가 인덱스(검색·필터용)" + NL +
             "CREATE INDEX notice_source IF NOT EXISTS FOR (n:Notice) ON (n.source_system);" + NL +
             "CREATE INDEX notice_open   IF NOT EXISTS FOR (n:Notice) ON (n.is_open);" + NL +
             "CREATE INDEX concept_scheme IF NOT EXISTS FOR (k:Concept) ON (k.scheme);" + NL +
             "// 점검 쿼리는 위 5.4 블록(V1~V7)에 있다" + NL)
    (OUT / "schema.cypher").write_text(head + body + extra, encoding="utf-8")
    return len((head + body + extra).split(NL))


# ---------------------------------------------------------------- evidence_manifest.csv
def load_text_sources() -> dict[str, list[tuple[str, str]]]:
    """notice_id -> [(위치, 텍스트)]. 정리 층의 공고 텍스트와 기업마당 첨부 자격·제외 구간."""
    clean_dir = REPO / "data" / "cleaned" / (REPO / "data" / "cleaned" / "LATEST").read_text().strip()
    src: dict[str, list[tuple[str, str]]] = {}
    for l in (clean_dir / "notices.jsonl").read_text(encoding="utf-8").split(NL):
        if not l.strip():
            continue
        n = json.loads(l)
        items = [("eligibility_text", n.get("eligibility_text") or ""), ("body_text", n.get("body_text") or "")]
        items += [(f"structured.{k}", f"{k}={v}") for k, v in (n.get("structured") or {}).items() if v]
        if n.get("region_raw"):
            items.append(("region_raw", f"region_raw={n['region_raw']}"))
        src[n["notice_id"]] = items
    ed = sorted(glob.glob(str(REPO / "data" / "bizinfo" / "extracted" / "*")))
    if ed:
        d = Path(ed[-1])
        for it in json.loads((d / "extraction_report.json").read_text(encoding="utf-8"))["items"]:
            if it["status"] not in ("OK", "OK_OCR"):
                continue
            try:
                t = (d / it["text_file"]).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for s in it["sections"]:
                if s["label"] in ("ELIGIBILITY", "EXCLUSION"):
                    src.setdefault(it["notice_id"], []).append((f"attachment:{it['file']}[{s['label']}]", t[s["start"]:s["end"]]))
    return src


def norm(s: str) -> str:
    return re.sub(r"\s+", "", s.replace("｢", "「").replace("｣", "」").replace("“", '"').replace("”", '"').replace("'", '"'))


def evidence() -> tuple[int, int]:
    rows = table_after("## 6. S-P-O 트리플과 출처 문장 매핑")[1:]
    src = load_text_sources()
    out, ok = [], 0
    for r in rows:
        tid, triple, ev, origin = r[0], clean(r[1]), clean(r[2]), clean(r[3])
        nid = (re.search(r"(BIZINFO:PBLN_\d+|KSTARTUP:\d+)", triple) or [None])[0]
        preds = ",".join(dict.fromkeys(re.findall(r"\b[A-Z][A-Z_]{3,}\b", triple)))
        origin_type = "ATTACHMENT" if "첨부" in origin else ("STRUCTURED" if "구조화" in origin else "API")
        if origin_type == "STRUCTURED":
            # 구조화 필드 값(biz_enyy, supt_regin)은 필드 일치로, 따옴표 안의 본문 문장은 자격 문구에서 찾는다
            fmap = {"biz_enyy": "business_age_raw", "supt_regin": "region_raw"}
            pairs = [f"{fmap[k]}={v}" for k, v in re.findall(r'(biz_enyy|supt_regin)="([^"]+)"', ev)]
            quoted = [q.lstrip("…") for q in re.findall(r'"([^"]{8,})"', ev) if "=" not in q and not re.fullmatch(r"[^\s]+", q)]
            parts = pairs + quoted
        else:
            parts = [p.strip().strip('"').strip("“”") for p in ev.split(" / ") if p.strip()]
        found_parts, loc = 0, []
        for p in parts:
            hit = next((w for w, t in src.get(nid, []) if norm(p) in norm(t)), None)
            if hit:
                found_parts += 1
                loc.append(hit)
        allfound = bool(parts) and found_parts == len(parts)
        ok += allfound
        method = "rule" if origin_type == "STRUCTURED" else "manual_reading"
        out.append([tid, nid, preds, triple, ev, origin_type, ";".join(dict.fromkeys(loc)) or "-", method, "staged", "true" if allfound else "false", f"{found_parts}/{len(parts)}", "2026-11-24"])
    write_csv("evidence_manifest.csv", ["triple_id", "source_id(notice_id)", "predicates", "triple", "source_span(근거 문장)", "source_type", "근거를 찾은 위치", "extraction_method",
                                          "review_status", "근거 문장이 현재 데이터에 그대로 있음", "찾은 문장 수/전체", "검사일"], out)
    return len(out), ok


# ---------------------------------------------------------------- cq_tests.xlsx
CQ_STATUS = {
    "CQ-01": ("가상 프로필: 서울 성동구 사업장", "성동구 →(WITHIN) 서울특별시 →(WITHIN) 전국. 서울 지역 조건 공고가 후보", "tools/test_graphrag.py RegionTests.test_sido_chain, ConditionTests.test_region_satisfied_with_path", "지역 계층 시험 통과(공고 후보 조회는 `build.py compare`로 SQL과 일치 확인)"),
    "CQ-02": ("공고 1건의 요건 조회", "자격·제외·우대 요건과 원문 문장", "data/graph/requirement_candidates*.jsonl(후보)", "후보 생성(18,021개), 검수 전이라 정답 아님"),
    "CQ-03": ("가상 프로필: 업력 2년, 대표 만 35세, 구미시 소재", "구조 조건은 규칙으로 3값 평가, 본문 요건이 없으면 NEEDS_CHECK(REQ_UNPARSED)", "tools/test_graphrag.py ConditionTests, NoticeTests", "평가기 단위 시험 통과. 본문 요건은 평가에 연결하지 않음"),
    "CQ-04": ("가상 프로필: 광주 남구 사업장, 조건 '광주광역시 관내'", "남구 → 광주(구) → 전남광주통합특별시. 묶음 사전이 있으면 SATISFIED(1 hop)", "RegionTests.test_gwangju_group_between_gu_and_merged_city, test_legacy_gwangju_matches_namgu_but_flags_unreviewed", "시험 통과(묶음 사전은 검수 전, 판정에 unreviewed_group 표시)"),
    "CQ-05": ("공고 116943의 '중소기업' 기준", "중소기업 → Definition → 중소기업기본법 제2조(원문). 기준 숫자는 시행령 원문 확인 필요", "data/graph/definitions_text_only.jsonl, 설계서 §7 시나리오 3", "손계산. Definition은 조문 원문만 있고 rule_json은 비어 있음"),
    "CQ-06": ("정의→법령 연결이 끊긴 요건", "법령 원문이 없으면 CHAIN_BROKEN, NEEDS_CHECK", "data/graph/law_chain_report.json", "측정만 함(규모 용어 문장 4,069개 중 조문 원문까지 확보 318개). 평가기 연결은 미구현"),
    "CQ-07": ("신청 불가·확인 필요 사유 추적", "조건별 UNSATISFIED/UNKNOWN과 사유 목록", "tools/graphrag/engine.py show(), evaluator.evaluate_notice", "구현됨(구조 조건 한정)"),
    "CQ-08": ("정정·재공고·연장 공고", "SUPERSEDES 경로와 content_hash 비교", "data/cleaned/<날짜>/related_groups.csv(후보 412묶음)", "후보만 있음. 스냅샷 1회라 확정 불가, 미실행"),
    "CQ-09": ("두 포털 중복 게재", "SAME_AS 후보", "EDA: 제목 키가 같은 후보 15건", "후보만 있음. 미실행"),
    "CQ-10": ("트랙별 조건이 다른 공고", "HAS_TRACK → Track", "설계서 §7 시나리오 4(KSTARTUP:179834)", "손계산만. Track 노드 미구축"),
    "CQ-11": ("요건·첨부를 읽지 못한 공고", "Requirement.status, Attachment.text_status", "data/bizinfo/extracted/ 추출 리포트", "데이터로 확인 가능(첨부 텍스트 1,292/1,294, 배포용 HWP 2건 제외)"),
    "CQ-12": ("N개 중 k개 충족·열린 목록 요건", "logic=AT_LEAST, open_ended", "설계서 §7 시나리오 2(BIZINFO:117985)", "손계산만. open_ended 평가는 미구현"),
    "CQ-13": ("구조화 필드와 본문이 충돌하는 공고", "source_conflict 후보 목록", "data/graph/conflicts_kstartup_business_age.csv", "후보 167건(비교 가능 1,400건 중), 검수 전"),
    "CQ-14": ("기준일이 다른 조건", "ref_date_kind 집계", "data/eda/term_variants.json(기준일 표현 빈도)", "표현 빈도만 측정. 조건 단위 집계는 미실행"),
    "CQ-15": ("법령 개정 시 영향받는 공고", "text_hash → Definition → Concept → Condition → Notice", "-", "미실행(법령·Definition 데이터 부족)"),
    "CQ-16": ("가장 후보를 줄이는 질문", "Condition.attribute 집계, 평가 결과", "-", "미실행"),
    "CQ-17": ("가상 프로필: 대구 달서구 사업장, 조건 '경상권 소재'", "달서구 → 대구 → 경상권(2 hop)", "RegionTests.test_three_hop_limit", "시험 통과(권역 묶음은 검수 전)"),
    "CQ-18": ("K-Startup 업력 옵션 7개 전부 나열 공고", "옵션 해석: 합집합, 전부 나열은 상한 초과 시 UNKNOWN", "ConditionTests.test_all_options_does_not_become_unconditional_pass", "시험 통과(전체 나열 규칙은 미검증)"),
}


def col_letter(i: int) -> str:
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def write_xlsx(path: Path, sheet: str, rows: list[list[str]], widths: list[int]) -> None:
    sheet_rows = []
    for ri, row in enumerate(rows):
        cells = []
        for ci, v in enumerate(row):
            ref = f"{col_letter(ci)}{ri + 1}"
            style = ' s="1"' if ri == 0 else ' s="2"'
            cells.append(f'<c r="{ref}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(str(v))}</t></is></c>')
        sheet_rows.append(f'<row r="{ri + 1}">{"".join(cells)}</row>')
    cols = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>' for i, w in enumerate(widths))
    sheet_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                 f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols>{cols}</cols>'
                 f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    styles = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
              '<fonts count="2"><font><sz val="10"/><name val="Malgun Gothic"/></font><font><b/><sz val="10"/><color rgb="FFFFFFFF"/><name val="Malgun Gothic"/></font></fonts>'
              '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>'
              '<fill><patternFill patternType="solid"><fgColor rgb="FF144069"/><bgColor indexed="64"/></patternFill></fill></fills>'
              '<borders count="2"><border><left/><right/><top/><bottom/><diagonal/></border>'
              '<border><left style="thin"><color rgb="FFBBBBBB"/></left><right style="thin"><color rgb="FFBBBBBB"/></right><top style="thin"><color rgb="FFBBBBBB"/></top><bottom style="thin"><color rgb="FFBBBBBB"/></bottom><diagonal/></border></borders>'
              '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
              '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
              '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1"><alignment vertical="center" wrapText="1"/></xf>'
              '<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1"><alignment vertical="top" wrapText="1"/></xf></cellXfs></styleSheet>')
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          '<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
          '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
    wb = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
          'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
          f'<sheet name="{escape(sheet)}" sheetId="1" r:id="rId1"/></sheets></workbook>')
    wbrels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
              '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>'
              '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("xl/workbook.xml", wb)
        z.writestr("xl/_rels/workbook.xml.rels", wbrels)
        z.writestr("xl/styles.xml", styles)
        z.writestr("xl/worksheets/sheet1.xml", sheet_xml)


def cq_tests() -> tuple[int, dict]:
    rows = table_after("## 2. 핵심 업무 질문")[1:]
    hdr = ["CQ ID", "업무 질문 예시", "유형", "필요 경로/검증", "SQL 대비(가설)", "시험 입력(가상)", "기대 결과(손계산·규칙)", "시험·증빙", "현재 상태(2026-11-24)"]
    out = [hdr]
    status_count: dict[str, int] = {}
    for r in rows:
        cid = clean(r[0])
        t = CQ_STATUS.get(cid, ("", "", "", "미실행"))
        out.append([cid, clean(r[1]), clean(r[2]), clean(r[3]), clean(r[4]), *t])
        k = "시험 통과" if "시험 통과" in t[3] else ("미실행" if t[3].startswith("미실행") else "부분(손계산·후보·측정)")
        status_count[k] = status_count.get(k, 0) + 1
    write_xlsx(OUT / "cq_tests.xlsx", "CQ 시험", out, [8, 34, 6, 34, 18, 28, 36, 36, 36])
    return len(out) - 1, status_count


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    n_ent, n_rel, n_cql = entities(), relationships(), schema()
    n_cq, st = cq_tests()
    n_ev, n_ok = evidence()
    print(f"entities.csv {n_ent}행, relationships.csv {n_rel}행, schema.cypher {n_cql}줄, cq_tests.xlsx {n_cq}행 {st}, evidence_manifest.csv {n_ev}행(근거 일치 {n_ok})")


if __name__ == "__main__":
    main()
