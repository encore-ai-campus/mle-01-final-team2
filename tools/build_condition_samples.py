"""Build review-only condition examples from the frozen 2026-11-24 snapshot.

This emits examples only; it never edits normalized inputs or performs extraction.
"""
from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Iterator, Iterable
from typing import Any
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/normalized/v1/20261124"
G2B_SNAPSHOT = ROOT / "data/normalized/v1/20261125_g2b"
OUT = ROOT / "sample_data/conditions"


def read_jsonl(path: Path) -> Iterator[dict[str, Any]]:
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON") from exc
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{number}: expected object")
            yield row


def source(system, kind, field, path, *, evidence_id=None, chunks=(), status="AVAILABLE", text=None):
    return {"source_system": system, "source_kind": kind, "source_field": field,
            "normalized_path": path, "evidence_id": evidence_id, "chunk_ids": list(chunks),
            "location": None, "observed_value_status": status, "evidence_text": text}


def refdate():
    return {"value": None, "date_type": "UNKNOWN", "precision": "UNKNOWN", "basis": None, "source_field": None}


def condition(cid, nid, typ, category, field, op, value, value_type, unit, text, src, *,
              review="UNREVIEWED", availability="AVAILABLE", completeness="UNKNOWN",
              decision=False, logic="UNRESOLVED", confidence=None, search=False,
              search_reason="UNKNOWN", qualifiers=None, benefit=None):
    return {"schema_version": "1.0", "condition_id": cid, "notice_id": nid,
            "condition_type": typ, "category_id": category, "field": field,
            "operator": op, "value": value, "value_type": value_type, "unit": unit,
            "reference_date": refdate(), "raw_text": text, "source": src,
            "availability_status": availability, "completeness_status": completeness,
            "review_status": review, "confidence": confidence, "search_eligible": search,
            "search_reason": search_reason, "decision_eligible": decision,
            "logic_relation_status": logic, "qualifiers": qualifiers or [], "benefit": benefit}


def collection(typ, status, completeness="UNKNOWN", review="UNREVIEWED", structure="UNSTRUCTURED",
               logic="UNRESOLVED", conditions=None, roots=None, evidence=None, decision=False, reasons=None):
    return {"condition_type": typ, "availability_status": status,
            "completeness_status": completeness, "review_status": review,
            "structure_status": structure, "logic_status": logic,
            "conditions": conditions or [], "logical_roots": roots or [],
            "source_evidence": evidence or [], "decision_eligible": decision,
            "insufficient_reasons": reasons if reasons is not None else ([] if decision else ["SOURCE_NOT_FULLY_VERIFIED"])}


def notice_set(nid, system, eligibility, exclusion, preference, *, label, contexts=None,
               eligibility_ready=False, preference_ready=False, limits=None):
    return {"schema_version": "1.0", "record_type": "notice_condition_set", "notice_id": nid,
            "source_system": system, "source_snapshot": "20261124" if system != "G2B" else "20261125_g2b",
            "condition_sets": {"eligibility": eligibility, "exclusion": exclusion, "preference": preference},
            "decision_readiness": {"eligibility_decision_eligible": eligibility_ready,
                                   "preference_assessment_eligible": preference_ready,
                                   "limiting_reasons": limits if limits is not None else ["EXCLUSION_OR_PREFERENCE_NOT_CONFIRMED"]},
            "context_references": contexts or [], "sample_metadata": {"kind": "ACTUAL_SOURCE", "label": label}}


def actual_samples(snapshot: Path = SNAPSHOT, g2b_snapshot: Path | None = G2B_SNAPSHOT) -> list[dict[str, Any]]:
    chosen = [
        ("BIZINFO:PBLN_000000000128037", "short source field; no matching chunk"),
        ("BIZINFO:PBLN_000000000128081", "short compound-marker example"),
        ("BIZINFO:PBLN_000000000128064", "long exception-marker example"),
        ("KSTARTUP:179799", "short source field; no matching chunk"),
        ("KSTARTUP:179837", "compound-marker example"),
        ("KSTARTUP:179834", "exception-marker example"),
        ("KSTARTUP:179839", "region and age context kept separate"),
    ]
    selected = {nid for nid, _ in chosen}
    notices = {}
    for row in read_jsonl(snapshot / "notices.jsonl"):
        nid = row.get("notice_id")
        if nid in selected:
            if nid in notices:
                raise ValueError(f"Duplicate selected notice: {nid}")
            notices[nid] = row
    missing = selected - notices.keys()
    if missing:
        raise ValueError(f"Missing selected notices: {sorted(missing)}")
    chunks = {}
    for row in read_jsonl(snapshot / "chunks.jsonl"):
        nid = row.get("notice_id")
        if nid not in selected:
            continue
        if (row.get("search_eligible") is True
                and row.get("privacy_status") == "CLEARED"
                and row.get("origin") not in {None, "UNKNOWN"}
                and not str(row.get("origin")).startswith("ATTACHMENT")
                and row.get("source_system") == notices[nid]["source"]["source_system"]):
            chunks.setdefault(nid, []).append(row)
    output = []
    for nid, label in chosen:
        row = notices[nid]
        system = row["source"]["source_system"]
        source_field = "bsnsSumryCn" if system == "BIZINFO" else "aply_trgt_ctnt"
        eligibility = row["condition_texts"]["eligibility"]
        text = eligibility["text"]
        if eligibility["availability"] != "PRESENT" or not isinstance(text, str) or not text.strip():
            raise ValueError(f"Selected eligibility sample unavailable: {nid}")
        needle = " ".join(text.split())
        chunk_ids = list(dict.fromkeys(
            c["chunk_id"] for c in chunks.get(nid, [])
            if isinstance(c.get("text"), str)
            and needle in " ".join(c["text"].split())
            and isinstance(c.get("chunk_id"), str) and c["chunk_id"].strip()
        ))
        kind = "CHUNK" if chunk_ids else "NOTICE_FIELD"
        src = source(system, kind, source_field, "condition_texts.eligibility.text",
                     evidence_id=f"{nid}:eligibility-source", chunks=chunk_ids, text=text)
        c = condition(f"{nid}:ELIGIBILITY:RAW", nid, "UNCLASSIFIED", "UNCLASSIFIED", None,
                      None, None, "UNKNOWN", None, text, src, completeness="PARTIAL" if system == "BIZINFO" else "UNKNOWN",
                      search=bool(chunk_ids), search_reason="SOURCE_CHUNK_AVAILABLE" if chunk_ids else "SOURCE_FIELD_ONLY")
        ev = [src]
        elig = collection("ELIGIBILITY", "AVAILABLE", "PARTIAL" if system == "BIZINFO" else "UNKNOWN",
                          structure="UNSTRUCTURED", conditions=[c], evidence=ev,
                          reasons=["RAW_TEXT_NOT_REVIEWED", "LOGIC_AND_SCOPE_UNRESOLVED"])
        absent = row["condition_texts"]["exclusion"]
        pref = row["condition_texts"]["preference"]
        def empty_set(typ, value):
            status = value["availability"]
            field = {"EXCLUSION": "aply_excl_trgt_ctnt", "PREFERENCE": "prfn_matr"}[typ] if system == "KSTARTUP" else f"condition_texts.{typ.lower()}.text"
            path = f"condition_texts.{typ.lower()}.text"
            if status == "PRESENT":
                text = value.get("text")
                if not isinstance(text, str) or not text.strip():
                    raise ValueError(f"Inconsistent {typ} text: {nid}")
                src = source(system, "NOTICE_FIELD", field, path, evidence_id=f"{nid}:{typ.lower()}-source", text=text)
                candidate = condition(f"{nid}:{typ}:RAW", nid, "UNCLASSIFIED", "UNCLASSIFIED", None, None, None, "UNKNOWN", None, text, src, search=False)
                return collection(typ, "AVAILABLE", conditions=[candidate], evidence=[src], reasons=["RAW_TEXT_NOT_REVIEWED", "LOGIC_AND_SCOPE_UNRESOLVED"])
            if status not in {"EMPTY", "NOT_COLLECTED"}:
                raise ValueError(f"Unexpected availability {status}: {nid}")
            evidence = []
            if status == "EMPTY":
                evidence = [source(system, "NOTICE_FIELD", field, path, status="EMPTY")]
            return collection(typ, status, evidence=evidence,
                              reasons=["EMPTY_OR_NOT_COLLECTED_IS_NOT_CONFIRMED_ABSENCE"])
        exclusion = empty_set("EXCLUSION", absent)
        preference = empty_set("PREFERENCE", pref)
        contexts = []
        if system == "KSTARTUP":
            for role, field, path, value in [
                ("REGION_CONTEXT_ONLY", "supt_regin", "region.raw", row["region"].get("raw")),
                ("BUSINESS_AGE_CONTEXT_ONLY", "biz_enyy", "structured.business_age_raw", row["structured"].get("business_age_raw")),
                ("REPRESENTATIVE_AGE_CONTEXT_ONLY", "biz_trgt_age", "structured.founder_age_raw", row["structured"].get("founder_age_raw")),
            ]:
                contexts.append({"role": role, "source": source(system, "NOTICE_FIELD", field, path,
                                  status="AVAILABLE" if value not in (None, "") else "UNKNOWN"),
                                 "raw_value": value, "used_as_condition": False})
        output.append(notice_set(nid, system, elig, exclusion, preference, label=label, contexts=contexts,
                                 limits=["EXCLUSION_DATA_NOT_VERIFIED", "PREFERENCE_DATA_NOT_VERIFIED",
                                         "ELIGIBILITY_TEXT_NOT_STRUCTURED_OR_REVIEWED"]))
    for item in output:
        item["source_snapshot"] = snapshot.name
    if g2b_snapshot is not None:
        output.extend(g2b_samples(g2b_snapshot))
    return output


def g2b_samples(snapshot: Path) -> list[dict[str, Any]]:
    """Add source-field candidates without interpreting G2B flags as verified conditions."""
    wanted = {
        "licenses": ("licenses", "LICENSE_CANDIDATE"),
        "regions": ("regions", "REGION_CANDIDATE"),
        "industry_limit_yn": ("industry_limit_yn", "INDUSTRY_LIMIT_FLAG"),
        "participation_limit_yn": ("participation_limit_yn", "PARTICIPATION_LIMIT_FLAG"),
    }
    chosen: dict[str, tuple[dict[str, Any], str, Any]] = {}
    used_notice_ids: set[str] = set()
    for row in read_jsonl(snapshot / "notices.jsonl"):
        if row.get("source", {}).get("source_system") != "G2B":
            continue
        native = row.get("source_metadata", {}).get("source_specific", {}).get("G2B", {})
        for key, (path, label) in wanted.items():
            if label in chosen or row.get("notice_id") in used_notice_ids:
                continue
            value = native.get(key)
            if key == "licenses":
                indexed = next(((index, item) for index, item in enumerate(value or [])
                                if isinstance(item, dict) and item.get("name")), None)
                if indexed is not None:
                    index, value = indexed
                    value = value["name"]
                    path = f"licenses[{index}].name"
            elif key == "regions":
                indexed = next(((index, item) for index, item in enumerate(value or [])
                                if isinstance(item, str) and item.strip()), None)
                if indexed is not None:
                    index, value = indexed
                    path = f"regions[{index}]"
            elif value != "Y":
                continue
            if value not in (None, "", []):
                chosen[label] = (row, path, value)
                used_notice_ids.add(row["notice_id"])
        if len(chosen) == len(wanted):
            break
    missing = {label for _, label in wanted.values()} - set(chosen)
    if missing:
        raise ValueError(f"Could not find G2B examples for: {sorted(label for _, label in missing)}")

    output = []
    for label, (row, path, value) in chosen.items():
        nid = row["notice_id"]
        src = source("G2B", "NOTICE_FIELD", path.rsplit("[", 1)[0] if "[" in path else path,
                     f"source_metadata.source_specific.G2B.{path}",
                     evidence_id=f"{nid}:G2B:{label}", text=str(value))
        candidate = condition(f"{nid}:G2B:{label}", nid, "UNCLASSIFIED", "UNCLASSIFIED", None,
                              None, None, "UNKNOWN", None, str(value), src,
                              availability="AVAILABLE", completeness="UNKNOWN", review="UNREVIEWED",
                              decision=False, search=False, search_reason="SOURCE_FIELD_ONLY")
        elig = collection("ELIGIBILITY", "AVAILABLE", "UNKNOWN", "UNREVIEWED", "PARTIALLY_STRUCTURED",
                          "UNRESOLVED", [candidate], [], [src], False,
                          ["SOURCE_FIELD_SEMANTICS_UNREVIEWED", "FULL_CONDITION_TEXT_NOT_COLLECTED"])
        excl = collection("EXCLUSION", "NOT_COLLECTED", reasons=["FULL_CONDITION_TEXT_NOT_COLLECTED"])
        pref = collection("PREFERENCE", "NOT_COLLECTED", reasons=["FULL_CONDITION_TEXT_NOT_COLLECTED"])
        output.append(notice_set(nid, "G2B", elig, excl, pref,
                                  label=f"G2B {label}; raw source field only, not interpreted",
                                  limits=["G2B_CONDITION_TEXT_NOT_COLLECTED", "SOURCE_FIELD_SEMANTICS_UNREVIEWED"]))
        output[-1]["source_snapshot"] = snapshot.name
    return output


def synthetic_samples():
    rows = []
    def synsrc(nid, ev):
        return source("SYNTHETIC", "SYNTHETIC_TEST", "example", "synthetic.example",
                      evidence_id=ev, text="합성 테스트 근거 문장")
    nid = "SYNTHETIC:AND-ELIGIBILITY"
    s1, s2, sx = synsrc(nid, "SYNTH:EV-1"), synsrc(nid, "SYNTH:EV-2"), synsrc(nid, "SYNTH:EV-X")
    a = condition("SYNTH:C-REGION", nid, "ELIGIBILITY", "BUSINESS_LOCATION", "applicant.region", "IN", ["서울특별시", "부산광역시"], "ARRAY", None, "신청 사업장이 서울 또는 부산에 소재할 것", s1, review="VERIFIED", completeness="COMPLETE", decision=True, logic="RESOLVED")
    b = condition("SYNTH:C-AGE", nid, "ELIGIBILITY", "BUSINESS_AGE", "business.age_years", "LTE", 7, "NUMBER", "YEAR", "창업 7년 이내", s2, review="VERIFIED", completeness="COMPLETE", decision=True, logic="RESOLVED")
    root = {"node_type": "LOGICAL_GROUP", "group_id": "SYNTH:G-AND", "operator": "AND", "children":[{"node_type":"CONDITION_REF","condition_id":a["condition_id"]},{"node_type":"CONDITION_REF","condition_id":b["condition_id"]}], "review_status":"VERIFIED", "evidence":sx}
    elig = collection("ELIGIBILITY", "AVAILABLE", "COMPLETE", "VERIFIED", "STRUCTURED", "RESOLVED", [a,b], [root], [s1,s2,sx], True, [])
    excl = collection("EXCLUSION", "NO_CONDITION_CONFIRMED", "COMPLETE", "VERIFIED", "NOT_APPLICABLE", "NOT_APPLICABLE", evidence=[sx], decision=True, reasons=[])
    pref = collection("PREFERENCE", "NOT_COLLECTED")
    rows.append(notice_set(nid,"SYNTHETIC",elig,excl,pref,label="AND eligibility; confirmed no exclusion; preference not collected",eligibility_ready=True,limits=["PREFERENCE_NOT_COLLECTED"]))

    nid = "SYNTHETIC:OR-EXCEPTION-PREFERENCE"
    ev = synsrc(nid,"SYNTH:EV-OR")
    c1 = condition("SYNTH:C-STARTUP",nid,"ELIGIBILITY","BUSINESS_TYPE","applicant.type","EQ","STARTUP","STRING",None,"창업기업일 것",ev,review="VERIFIED",completeness="COMPLETE",decision=True,logic="RESOLVED")
    c2 = condition("SYNTH:C-UNIV","SYNTHETIC:OR-EXCEPTION-PREFERENCE","ELIGIBILITY","APPLICANT_TYPE","applicant.type","EQ","UNIVERSITY_SPINOFF","STRING",None,"대학 창업기업일 것",ev,review="VERIFIED",completeness="COMPLETE",decision=True,logic="RESOLVED")
    c5 = condition("SYNTH:C-UNIV-AGE",nid,"ELIGIBILITY","BUSINESS_AGE","business.age_years","LTE",7,"NUMBER","YEAR","창업 7년 이내",ev,review="VERIFIED",completeness="COMPLETE",decision=True,logic="RESOLVED")
    c3 = condition("SYNTH:C-EXCLUSION",nid,"EXCLUSION","LEGAL_SANCTION","applicant.sanction_status","EQ",True,"BOOLEAN",None,"법적 제재 중인 경우 제외",ev,review="VERIFIED",completeness="COMPLETE",decision=True,logic="RESOLVED")
    c4 = condition("SYNTH:C-PREF",nid,"PREFERENCE","CERTIFICATION","applicant.certification","EQ","여성기업 확인","STRING",None,"여성기업 확인 보유 시 가점",ev,review="VERIFIED",completeness="COMPLETE",decision=True,logic="RESOLVED")
    c4["benefit"]={"benefit_type":"BONUS_POINTS","value":5,"unit":"POINT","applies_when_condition_ids":[c4["condition_id"]],"stackable":None,"maximum_value":None,"raw_text":"여성기업 확인 보유 시 5점 가점","review_status":"VERIFIED","source":ev}
    c3["decision_eligible"] = False
    c3["logic_relation_status"] = "UNRESOLVED"
    c3["qualifiers"]=[{"qualifier_type":"EXCEPTION","raw_text":"단, 협약 전 제재가 해소된 경우는 신청 가능","applies_to_condition_ids":[c3["condition_id"]],"linkage_status":"LINKED","review_status":"VERIFIED","source":ev}]
    orroot={"node_type":"LOGICAL_GROUP","group_id":"SYNTH:G-OR","operator":"OR","children":[{"node_type":"CONDITION_REF","condition_id":c1["condition_id"]},{"node_type":"LOGICAL_GROUP","group_id":"SYNTH:G-OR-AND","operator":"AND","children":[{"node_type":"CONDITION_REF","condition_id":c2["condition_id"]},{"node_type":"CONDITION_REF","condition_id":c5["condition_id"]}],"review_status":"VERIFIED","evidence":ev}],"review_status":"VERIFIED","evidence":ev}
    elig=collection("ELIGIBILITY","AVAILABLE","COMPLETE","VERIFIED","STRUCTURED","RESOLVED",[c1,c2,c5],[orroot],[ev],True,[])
    excl=collection("EXCLUSION","AVAILABLE","COMPLETE","VERIFIED","PARTIALLY_STRUCTURED","UNRESOLVED",[c3],[{"node_type":"CONDITION_REF","condition_id":c3["condition_id"]}],[ev],False,["EXCEPTION_NOT_MACHINE_EVALUABLE"])
    pref=collection("PREFERENCE","AVAILABLE","COMPLETE","VERIFIED","STRUCTURED","RESOLVED",[c4],[{"node_type":"CONDITION_REF","condition_id":c4["condition_id"]}],[ev],True,[])
    rows.append(notice_set(nid,"SYNTHETIC",elig,excl,pref,label="nested OR/AND; linked exception; conditional points",eligibility_ready=False,preference_ready=True,limits=["EXCEPTION_NOT_MACHINE_EVALUABLE"]))

    nid="SYNTHETIC:UNRESOLVED-ATTACHMENT"
    ev=synsrc(nid,"SYNTH:EV-ATT")
    u1=condition("SYNTH:C-ATT-1",nid,"UNCLASSIFIED","UNCLASSIFIED",None,None,None,"UNKNOWN",None,"첨부 원문 후보 A",source("SYNTHETIC","ATTACHMENT","attachment","attachments[0]",evidence_id="SYNTH:ATT-1",text="첨부 원문 후보 A"),availability="AVAILABLE",completeness="UNKNOWN",search=False,search_reason="UNREVIEWED_ATTACHMENT")
    u2=condition("SYNTH:C-ATT-2",nid,"UNCLASSIFIED","UNCLASSIFIED",None,None,None,"UNKNOWN",None,"첨부 원문 후보 B",source("SYNTHETIC","ATTACHMENT_OCR","attachment_ocr","attachments[1]",evidence_id="SYNTH:ATT-2",text="첨부 원문 후보 B"),availability="AVAILABLE",completeness="UNKNOWN",search=False,search_reason="UNREVIEWED_ATTACHMENT")
    unresolved={"node_type":"LOGICAL_GROUP","group_id":"SYNTH:G-UNRESOLVED","operator":"UNRESOLVED","children":[{"node_type":"CONDITION_REF","condition_id":u1["condition_id"]},{"node_type":"CONDITION_REF","condition_id":u2["condition_id"]}],"review_status":"NEEDS_REVIEW","evidence":ev}
    elig=collection("ELIGIBILITY","AVAILABLE","UNKNOWN","NEEDS_REVIEW","PARTIALLY_STRUCTURED","UNRESOLVED",[u1,u2],[unresolved],[ev],False,["ATTACHMENT_NOT_REVIEWED","LOGIC_UNRESOLVED"])
    excl=collection("EXCLUSION","NOT_EXTRACTED","UNKNOWN","NEEDS_REVIEW",evidence=[ev],reasons=["SOURCE_PRESENT_BUT_NOT_EXTRACTED"])
    pref=collection("PREFERENCE","EMPTY",reasons=["EMPTY_DOES_NOT_CONFIRM_ABSENCE"])
    rows.append(notice_set(nid,"SYNTHETIC",elig,excl,pref,label="unreviewed attachment candidates and not-extracted exclusion",limits=["ATTACHMENT_NOT_REVIEWED","EXCLUSION_NOT_EXTRACTED"]))
    for row in rows:
        row["source_snapshot"]="SYNTHETIC"
        row["sample_metadata"]["kind"]="SYNTHETIC_TEST"
    return rows


def write(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False) as stream:
            temp = Path(stream.name)
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n")
        temp.replace(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, default=SNAPSHOT)
    parser.add_argument("--g2b-snapshot-dir", type=Path, default=G2B_SNAPSHOT)
    parser.add_argument("--output-dir", type=Path, default=OUT)
    args = parser.parse_args()
    if args.output_dir.resolve().is_relative_to(args.snapshot_dir.resolve()):
        parser.error("Output must not be inside normalized inputs")
    actual = actual_samples(args.snapshot_dir, args.g2b_snapshot_dir if args.g2b_snapshot_dir.exists() else None)
    synthetic = synthetic_samples()
    write(args.output_dir / "actual-condition-samples.jsonl", actual)
    write(args.output_dir / "synthetic-condition-samples.jsonl", synthetic)
    print(f"Wrote {len(actual)} actual-source and {len(synthetic)} synthetic review examples.")


if __name__ == "__main__":
    main()
