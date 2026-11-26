"""Convert only the five unreviewed development precheck notices to v1.1."""
from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/goldsets/conditions/v1/20261126_balanced/precheck5/development"
TARGET = ROOT / "data/goldsets/conditions/v1.1/20261126/precheck5/development"
IDS = {
    "KSTARTUP:177469", "KSTARTUP:176813", "BIZINFO:PBLN_000000000118927",
    "KSTARTUP:178507", "BIZINFO:PBLN_000000000118182",
}


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (SOURCE / name).read_text(encoding="utf-8").splitlines() if line]


def ref(condition: dict) -> dict:
    r = condition["evidence_reference"]
    return {"role": "PRIMARY", "source_field": condition["source_field"],
            "start_char": r["start_char"], "end_char": r["end_char"],
            "evidence_text": condition["raw_text"], "document_id": None,
            "evidence_id": None}


def node(condition: dict) -> dict:
    return {"node_type": "CONDITION_REF", "condition_id": condition["gold_condition_id"]}


def group(label: str, op: str, children: list[dict]) -> dict:
    return {"node_type": "LOGICAL_GROUP", "group_id": label, "operator": op,
            "children": children, "review_status": "UNREVIEWED", "evidence": None}


def section(kind: str, phase: str, root: dict, label: str, fulfillment: str | None = None) -> dict:
    return {"section_id": label, "condition_type": kind, "evaluation_phase": phase,
            "fulfillment_phase": fulfillment or phase,
            "root": root, "review_status": "UNREVIEWED"}


def build() -> tuple[list[dict], list[dict]]:
    conditions, logics = rows("condition_review.jsonl"), rows("logic_review.jsonl")
    assert {r["notice_id"] for r in conditions} == IDS == {r["notice_id"] for r in logics}
    by_logic = {r["notice_id"]: r for r in logics}
    for record in conditions:
        nid = record["notice_id"]
        logic = by_logic[nid]
        record["schema_version"] = logic["schema_version"] = "1.1"
        record["evaluation_version"] = logic["evaluation_version"] = "1.1"
        record["review_status"] = logic["review_status"] = "UNREVIEWED"
        record["adjudication_status"] = logic["adjudication_status"] = "PENDING"
        cs = record["gold_conditions"] + record["missed_condition_candidates"]
        for c in cs:
            c["evidence_references"] = [ref(c)]
            c["structure_capable"] = c["operator"] is not None and c["value"] is not None
            c["facts_sufficient"] = False
            c["evaluation_phase"] = "APPLICATION"
            c["fulfillment_phase"] = "APPLICATION"
            c["requirement_kind"] = "CURRENT_STATE"
            c["temporal_constraint"] = None
            c["external_reference"] = None
            if c["condition_type"] == "PREFERENCE":
                c["evaluation_phase"] = "SELECTION"
                c["fulfillment_phase"] = "SELECTION"
            if c["condition_type"] == "EXCLUSION":
                c["evaluation_phase"] = "UNKNOWN"
                c["fulfillment_phase"] = "UNKNOWN"
                c["requirement_kind"] = "UNKNOWN"
            c["decision_possible"] = False
        for ex in logic["gold_exceptions"]:
            ex.update(effect="UNKNOWN", effect_target=None, replacement=None,
                      precondition=None, effect_confirmed=False, application_mode="UNKNOWN",
                      evidence_references=[{"role": "PRIMARY", "source_field": record["source_field"],
                         "start_char": ex["evidence_reference"]["start_char"],
                         "end_char": ex["evidence_reference"]["end_char"],
                         "evidence_text": ex["raw_text"], "document_id": None, "evidence_id": None}])
        d = {c["field"]: c for c in cs if c["field"]}
        sections = []
        if nid.endswith("177469"):
            sections = [section("ELIGIBILITY", "APPLICATION", logic["gold_logic_roots"][0], "eligibility")]
        elif nid.endswith("176813"):
            sections = [section("ELIGIBILITY", "APPLICATION", logic["gold_logic_roots"][0], "eligibility")]
            ps = [c for c in cs if c["condition_type"] == "PREFERENCE"]
            sections += [section("PREFERENCE", "SELECTION", node(c), f"preference_{i}") for i, c in enumerate(ps, 1)]
            d["BUSINESS_AGE"]["temporal_constraint"] = {
                "anchor_event": "MOVE_IN_APPLICATION", "fixed_reference_date": None,
                "offset_value": 7, "offset_unit": "YEAR", "operator": "LT", "inclusive": False,
                "applies_to": "BUSINESS_AGE", "anchor_date_known": False}
            d["BUSINESS_TECHNOLOGY_SCOPE"]["external_reference"] = {
                "reference_type": "DETAIL_NOTICE", "reference_text": "advanced technology scope",
                "collection_status": "NOT_COLLECTED", "details_confirmed": False}
            ex = logic["gold_exceptions"][0]
            ex.update(effect="EXCLUDE_FROM_SCOPE", effect_target="RESTRICTED_GOV_INCUBATOR_EXPERIENCE_COUNT",
                      precondition="EXPERIENCE_RECORD_IS_LOCAL_INCUBATOR", effect_confirmed=True,
                      application_mode="EFFECT_ONLY")
        elif nid.endswith("118927"):
            sections = [section("ELIGIBILITY", "APPLICATION", logic["gold_logic_roots"][0], "eligibility")]
            for c in cs:
                if c["field"] in {"FAMILY_FRIENDLY_PRACTICE", "WORK_LIFE_BALANCE_PRACTICE"}:
                    c["structure_capable"] = False
            for c in cs:
                if c["field"] == "BUSINESS_LOCATION":
                    c["evidence_references"].append({"role": "SUPPORTING", "source_field": "title",
                        "start_char": 1, "end_char": 3, "evidence_text": "강원",
                        "document_id": "data/normalized/v1/20261125_g2b/notices.jsonl", "evidence_id": None})
            for c in cs:
                c["external_reference"] = {"reference_type": "DETAIL_NOTICE", "reference_text": "공고문",
                    "collection_status": "NOT_COLLECTED", "details_confirmed": False}
        elif nid.endswith("178507"):
            founder = next(c for c in cs if c["field"] == "BUSINESS_REGISTRATION")
            founder.update(evaluation_phase="APPLICATION", fulfillment_phase="POST_MOVE_IN",
                           requirement_kind="FUTURE_FEASIBILITY", structure_capable=True,
                           temporal_constraint={"anchor_event": "MOVE_IN_START", "fixed_reference_date": None,
                               "offset_value": 3, "offset_unit": "MONTH", "operator": "LTE",
                               "inclusive": True, "applies_to": "BUSINESS_REGISTRATION", "anchor_date_known": False})
            age = next(c for c in cs if c["field"] == "BUSINESS_AGE")
            age["temporal_constraint"] = {"anchor_event": "FIXED_DATE", "fixed_reference_date": "2026-07-07",
                "offset_value": None, "offset_unit": None, "operator": "LT", "inclusive": False,
                "applies_to": "BUSINESS_AGE", "anchor_date_known": True}
            # Keep the publication-date-like age reference visible without
            # asserting that it is an applicant-age cutoff.
            applicant_age = next(c for c in cs if c["field"] == "APPLICANT_AGE")
            applicant_age["temporal_constraint"] = {"anchor_event": "UNKNOWN", "fixed_reference_date": None,
                "offset_value": None, "offset_unit": None, "operator": None, "inclusive": None,
                "applies_to": "APPLICANT_AGE_CUTOFF", "anchor_date_known": False}
            age_marker = "2026. 7. 7."
            age_pos = record["source_text"].find(age_marker)
            assert age_pos >= 0
            applicant_age["evidence_references"].append({"role": "CONTEXT", "source_field": record["source_field"],
                "start_char": age_pos, "end_char": age_pos + len(age_marker), "evidence_text": age_marker,
                "document_id": None, "evidence_id": None})
            marker = "2019. 7. 8."
            pos = record["source_text"].find(marker)
            assert pos >= 0
            age["evidence_references"].append({"role": "SUPPORTING", "source_field": record["source_field"],
                "start_char": pos, "end_char": pos + len(marker), "evidence_text": marker,
                "document_id": None, "evidence_id": None})
            address = next(c for c in cs if c["field"] == "BUSINESS_LOCATION")
            address.update(evaluation_phase="POST_SELECTION", fulfillment_phase="POST_SELECTION",
                           requirement_kind="FULFILLMENT_OBLIGATION",
                           temporal_constraint={"anchor_event": "MOVE_IN_START", "fixed_reference_date": None,
                               "offset_value": 30, "offset_unit": "DAY", "operator": "LTE", "inclusive": True,
                               "applies_to": "HEAD_OR_BRANCH_ADDRESS_TRANSFER", "anchor_date_known": False})
            for c in cs:
                if c["field"] == "DUPLICATE_OCCUPANCY":
                    c["evaluation_phase"] = "UNKNOWN"
                    c["fulfillment_phase"] = "UNKNOWN"
                    if "FINAL" in (c.get("applicability_scope") or "").upper() or c["gold_condition_id"].endswith("XNGYEKKQZZIRCEYLRC7XBPHS"):
                        c["evaluation_phase"] = "POST_SELECTION"
                        c["fulfillment_phase"] = "POST_SELECTION"
            exclusion = next(c for c in cs if c["field"] is None)
            exclusion["external_reference"] = {"reference_type": "LAW", "reference_text": exclusion["raw_text"],
                "collection_status": "NOT_COLLECTED", "details_confirmed": False}
            root = copy.deepcopy(logic["gold_logic_roots"][0])
            founder_branch = root["children"][1]["children"][0]
            root["children"][1]["children"][0] = group(f"DRAFT:{nid}:FOUNDER_FEASIBILITY", "AND",
                [founder_branch, node(founder)])
            sections = [section("ELIGIBILITY", "APPLICATION", root, "eligibility", "UNKNOWN")]
            sections += [section("EXCLUSION", c["evaluation_phase"], node(c), f"exclusion_{i}", c["fulfillment_phase"])
                         for i, c in enumerate((x for x in cs if x["condition_type"] == "EXCLUSION"), 1)]
            sections += [section("POST_SELECTION_OBLIGATION", "POST_SELECTION", node(address), "address_transfer")]
            for ex in logic["gold_exceptions"]:
                ex.update(effect="REPLACE_DEADLINE", effect_target="BUSINESS_LOCATION.temporal_constraint",
                          replacement={"anchor_event": "CONTRACT_SIGNING", "offset_value": 3,
                                       "offset_unit": "MONTH", "operator": "LTE", "inclusive": True},
                          precondition="FOREIGN_COMPANY_OR_CORPORATE_RESEARCH_INSTITUTE",
                          effect_confirmed=True, application_mode="EFFECT_ONLY")
        else:
            sections = [section("ELIGIBILITY", "APPLICATION", logic["gold_logic_roots"][0], "eligibility")]
            for c in cs:
                if c["field"] == "BUSINESS_TYPE" and "「" in c["raw_text"]:
                    c["external_reference"] = {"reference_type": "LAW", "reference_text": c["raw_text"],
                        "collection_status": "NOT_COLLECTED", "details_confirmed": False}
                if c["field"] == "BUSINESS_LOCATION":
                    c["evidence_references"].append({"role": "SUPPORTING", "source_field": "title",
                        "start_char": 1, "end_char": 3, "evidence_text": "경기",
                        "document_id": "data/normalized/v1/20261125_g2b/notices.jsonl", "evidence_id": None})
            for ex in logic["gold_exceptions"]:
                ex.update(effect="WAIVE_REQUIREMENT", effect_target="PROFIT_STATUS",
                          precondition="NONPROFIT_AND_ALLOWED_THREE_ORGANIZATION_TYPES",
                          effect_confirmed=True, application_mode="AST_ONLY")
        logic["gold_logic_sections"] = sections
        logic["gold_logic_roots"] = [s["root"] for s in sections]
    return conditions, logics


if __name__ == "__main__":
    conditions, logics = build()
    TARGET.mkdir(parents=True, exist_ok=True)
    for name, items in (("condition_review.jsonl", conditions), ("logic_review.jsonl", logics)):
        (TARGET / name).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in items), encoding="utf-8")
    by_logic = {r["notice_id"]: r for r in logics}
    lines = ["# 사전 검수 5건 v1.1 초안", "", "모든 항목은 UNREVIEWED/PENDING이며 실제 판정 및 성능 점수에 사용하지 않는다.",
             "v1.0 원본: `data/goldsets/conditions/v1/20261126_balanced/precheck5/development/`", ""]
    for record in conditions:
        nid = record["notice_id"]
        logic = by_logic[nid]
        lines += [f"## {nid}", "", "### 실제 발췌 원문", "", "```text", record["source_text"], "```", "",
                  "### 조건 초안", "", "| ID | 유형 | 속성·연산자·값 | 평가 → 이행 / 성격 | 판정 정보 | 근거 |",
                  "|---|---|---|---|---|---|"]
        for c in record["gold_conditions"] + record["missed_condition_candidates"]:
            e = c["evidence_references"]
            citations = "; ".join(f"{x['role']} {x['source_field']}[{x['start_char']}:{x['end_char']}] `{x['evidence_text']}`" for x in e)
            val = json.dumps(c["value"], ensure_ascii=False)
            lines.append(f"| `{c['gold_condition_id']}` | {c['condition_type']} | {c['field']} / {c['operator']} / {val} | {c['evaluation_phase']} → {c['fulfillment_phase']} / {c['requirement_kind']} | structure={c['structure_capable']}, facts={c['facts_sufficient']}, decision={c['decision_possible']} | {citations} |")
        lines += ["", "### 논리 구역·예외 초안", "", "```json",
                  json.dumps({"gold_logic_sections": logic["gold_logic_sections"],
                              "gold_exceptions": logic["gold_exceptions"]}, ensure_ascii=False, indent=2), "```", ""]
        notes = {
            "KSTARTUP:177469": "v1.0의 AND 세 조건을 유지. 연령 기준일과 창업 관심의 객관적 충족 기준은 미확인.",
            "KSTARTUP:176813": "v1.0 공통 자격 AND, 예비창업자/기창업자 OR, 우대 2개 유지. 입주신청일 기준 업력과 지방 보육센터 이력만 제외하는 효과를 구조화. 첨단기술 상세 범위·우대 점수는 미확인.",
            "BIZINFO:PBLN_000000000118927": "v1.0 지역·가족친화·일생활균형 세 조건 유지. 제목 강원과 본문 도내를 복수 근거로 연결. 정확한 소재지 요건과 정성 기준, 상세 공고문은 미확인.",
            "KSTARTUP:178507": "주소 이전 기한은 입주개시일 기준 30일 이내로 기록(POST_SELECTION). 최종 선정기업 중복입주 제한은 POST_SELECTION, 공공시설 중복입주 시점은 UNKNOWN. 2026. 7. 7.은 연령 기준일로 확정하지 않고 근거 후보로만 보존. 업력 기준일과 2019. 7. 8. 각주 근거를 유지. 해외기업·기업부설연구소 계약일 기준 3개월 예외 유지.",
            "BIZINFO:PBLN_000000000118182": "v1.0의 경기 AND (영리·8유형 OR 비영리·3유형) 유지. 제목과 본문 근거 연결. 비영리 예외는 AST_ONLY로 표시해 중복 완화 차단. 법령 세부 요건은 미수집.",
        }
        lines += ["### v1.0 대비 변경 및 사람 확인 사항", "", notes[nid], "",
                  "승인 / 수정 / 판단 불가: __________", ""]
    (TARGET / "HUMAN_REVIEW_PRECHECK5_V11.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    import csv
    condition_fields = ["notice_id", "gold_condition_id", "condition_type", "field", "operator", "value",
                        "evaluation_phase", "fulfillment_phase", "requirement_kind", "temporal_constraint",
                        "review_status", "raw_text", "evidence_references"]
    with (TARGET / "condition_review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=condition_fields)
        writer.writeheader()
        for record in conditions:
            for c in record["gold_conditions"] + record["missed_condition_candidates"]:
                writer.writerow({"notice_id": record["notice_id"], **{k: json.dumps(c.get(k), ensure_ascii=False) if isinstance(c.get(k), (dict, list)) else c.get(k) for k in condition_fields if k != "notice_id"}})
    logic_fields = ["notice_id", "section_id", "condition_type", "evaluation_phase", "fulfillment_phase",
                    "review_status", "root", "exceptions"]
    with (TARGET / "logic_review.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=logic_fields)
        writer.writeheader()
        for record in logics:
            for s in record["gold_logic_sections"]:
                writer.writerow({"notice_id": record["notice_id"], **{k: json.dumps(s.get(k), ensure_ascii=False) if isinstance(s.get(k), (dict, list)) else s.get(k) for k in logic_fields if k not in {"notice_id", "exceptions"}},
                                 "exceptions": json.dumps(record["gold_exceptions"], ensure_ascii=False)})
