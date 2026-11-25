"""수기 정규화 도우미(tools/labeler/labeler.html)의 점검 규칙이 tools/goldset_check.py와 같은 결과를 내는지 시험한다.

Node가 있어야 한다(없으면 건너뛴다). 같은 입력을 파이썬 검사기와 HTML 안의 자바스크립트 검사기에 넣어 오류 목록이 똑같은지 비교한다.
실행: python -m unittest tools.test_labeler_core -v
"""
import copy
import json
import shutil
import subprocess
import sys
import unittest
import zipfile
import io
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import goldset_check as G  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "tools" / "labeler" / "labeler.html"
PACKET = "## 지원대상\n구미 소재 창업기업 중 업력 7년 이내 창업기업 (신청일 기준) / 구미(본사)로 이전 계획 기업\n선정 후 60일 이내 이전 必"
S1 = "구미 소재 창업기업 중 업력 7년 이내 창업기업 (신청일 기준)"

BASE_A = {
    "notice_id": "N", "reviewer": "A", "time_minutes": 10, "read": [], "tracks": [], "source_conflicts": [], "ambiguities": ["x"],
    "requirements": [{
        "req_id": "R1", "kind": "ELIGIBILITY", "logic": "OR", "logic_basis": "assumed", "min_count": None, "status": "parsed", "open_ended": False,
        "source_sentence": S1, "source": "s",
        "conditions": [
            {"cond_id": "G1", "logic": "AND", "children": [
                {"cond_id": "C1", "attribute": "region", "operator": "WITHIN", "value": {"label": "구미"}, "ref_date_kind": "NONE", "needs_definition": False},
                {"cond_id": "C2", "attribute": "business_age", "operator": "LTE", "value": {"value": 7, "unit": "YEAR"}, "ref_date_kind": "OTHER", "needs_definition": False}]},
            {"cond_id": "C3", "attribute": "applicant_type", "operator": "IS_A", "value": {"label": "창업기업"}, "ref_date_kind": "NONE", "needs_definition": True}]}],
}
BASE_B = {"notice_id": "N", "reviewer": "A", "judgments": [{"profile_id": "P1", "overall": "NEEDS_CHECK", "reason_codes": ["ASSUMED_LOGIC"],
          "conditions": [{"cond_ref": "C1", "result": "SATISFIED"}, {"cond_ref": "C2", "result": "UNKNOWN"}, {"cond_ref": "G1", "result": "UNKNOWN"}]}]}
PROFS = {"P1": {}, "P2": {}}


def mutate(base, fn):
    x = copy.deepcopy(base)
    fn(x)
    return x


def a_cases():
    req = lambda x: x["requirements"][0]
    cond = lambda x: x["requirements"][0]["conditions"][1]
    leaf = lambda x: x["requirements"][0]["conditions"][0]["children"][1]
    deep = lambda x: x["requirements"][0]["conditions"]
    cs = {
        "ok": lambda x: None,
        "kind_bad": lambda x: req(x).update(kind="WRONG"),
        "kind_missing": lambda x: req(x).pop("kind"),
        "logic_bad": lambda x: req(x).update(logic="XOR"),
        "at_least_no_min": lambda x: req(x).update(logic="AT_LEAST"),
        "at_least_min": lambda x: req(x).update(logic="AT_LEAST", min_count=2),
        "no_sentence": lambda x: req(x).update(source_sentence=""),
        "sentence_not_in_packet": lambda x: req(x).update(source_sentence="원문에 없는 문장"),
        "sentence_spacing_differs": lambda x: req(x).update(source_sentence=S1.replace(" ", "")),
        "attr_bad": lambda x: leaf(x).update(attribute="nope"),
        "op_bad": lambda x: leaf(x).update(operator="LIKE"),
        "ref_none": lambda x: leaf(x).update(ref_date_kind="NONE"),
        "ref_missing": lambda x: leaf(x).pop("ref_date_kind"),
        "ref_bad": lambda x: leaf(x).update(ref_date_kind="WHENEVER"),
        "ref_none_but_limit_kind": lambda x: (leaf(x).update(ref_date_kind="NONE"), req(x).update(kind="LIMIT")),
        "is_a_no_def": lambda x: cond(x).update(needs_definition=False),
        "dup_id": lambda x: cond(x).update(cond_id="C1"),
        "group_logic_bad": lambda x: x["requirements"][0]["conditions"][0].update(logic="MAYBE"),
        "group_at_least_no_min": lambda x: x["requirements"][0]["conditions"][0].update(logic="AT_LEAST"),
        "group_empty_children": lambda x: x["requirements"][0]["conditions"][0].update(children=[]),
        "no_requirements_no_ambiguity": lambda x: x.update(requirements=[], ambiguities=[]),
        "no_requirements_with_ambiguity": lambda x: x.update(requirements=[]),
        "missing_keys": lambda x: (x.pop("reviewer"), x.pop("ambiguities")),
        "depth_3_ok": lambda x: deep(x).__setitem__(0, {"cond_id": "G1", "logic": "AND", "children": [{"cond_id": "G2", "logic": "AND", "children": [{"cond_id": "G3", "logic": "AND", "children": [
            {"cond_id": "C1", "attribute": "region", "operator": "WITHIN", "value": {"label": "x"}, "ref_date_kind": "NONE"}]}]}]}),
        "depth_4_bad": lambda x: deep(x).__setitem__(0, {"cond_id": "G1", "logic": "AND", "children": [{"cond_id": "G2", "logic": "AND", "children": [{"cond_id": "G3", "logic": "AND", "children": [
            {"cond_id": "G4", "logic": "AND", "children": [{"cond_id": "C1", "attribute": "region", "operator": "WITHIN", "value": {"label": "x"}, "ref_date_kind": "NONE"}]}]}]}]}),
    }
    return {k: mutate(BASE_A, f) for k, f in cs.items()}


def b_cases():
    j = lambda x: x["judgments"][0]
    cs = {
        "ok": lambda x: None,
        "unknown_profile": lambda x: j(x).update(profile_id="P9"),
        "overall_bad": lambda x: j(x).update(overall="MAYBE"),
        "overall_none": lambda x: j(x).update(overall=None),
        "result_bad": lambda x: j(x)["conditions"][0].update(result="SORT_OF"),
        "cond_ref_missing_in_a": lambda x: j(x)["conditions"].append({"cond_ref": "C9", "result": "SATISFIED"}),
        "cond_ref_nested_leaf": lambda x: j(x)["conditions"].append({"cond_ref": "C2", "result": "SATISFIED"}),
        "reason_bad": lambda x: j(x).update(reason_codes=["BECAUSE"]),
        "no_judgments": lambda x: x.update(judgments=[]),
        "single_judgment_form": lambda x: (x.pop("judgments"), x.update(profile_id="P1", overall="ELIGIBLE", conditions=[], reason_codes=[])),
        "single_judgment_unknown": lambda x: (x.pop("judgments"), x.update(profile_id="P7", overall="X", conditions=[], reason_codes=[])),
    }
    return {k: mutate(BASE_B, f) for k, f in cs.items()}


NODE_SCRIPT = r"""
const fs = require('fs');
const html = fs.readFileSync(process.argv[process.argv.length - 1], 'utf8');
const core = html.match(/<script id="core">([\s\S]*?)<\/script>/)[1];
const m = { exports: {} }; new Function('module', 'globalThis', core + ';')(m, globalThis);
const C = m.exports;
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = { A: {}, B: {}, phrase: {}, zip: null };
for (const [k, v] of Object.entries(cases.A)) out.A[k] = C.validateA(v, cases.packet);
for (const [k, v] of Object.entries(cases.B)) out.B[k] = C.validateB(v, cases.a, cases.profs);
for (const t of cases.phrases) out.phrase[t] = C.parsePhrase(t);
const files = [{ name: 'labels/kwan/A/N_1.json', data: new TextEncoder().encode('{"가":1}') }, { name: 'labels/kwan/B/N_1.json', data: new TextEncoder().encode('{}') }];
out.zip = Buffer.from(C.makeZip(files)).toString('base64');
process.stdout.write(JSON.stringify(out));
"""


@unittest.skipUnless(shutil.which("node") and HTML.exists(), "node 또는 labeler.html이 없다")
class TestLabelerCore(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cases = {"A": a_cases(), "B": b_cases(), "packet": PACKET, "a": BASE_A, "profs": PROFS, "phrases": ["7년 이내", "만 39세 이하", "10인 미만", "3억원 이상", "매출 12억 5천만원 이하", "제한 없음"]}
        r = subprocess.run(["node", "-e", NODE_SCRIPT, str(HTML)], input=json.dumps(cases), capture_output=True, text=True, encoding="utf-8", check=True)
        cls.js = json.loads(r.stdout)
        cls.cases = cases

    def test_label_a_errors_match_the_python_checker(self):
        for name, label in self.cases["A"].items():
            self.assertEqual(self.js["A"][name], G.validate_a(label, PACKET), name)

    def test_label_b_errors_match_the_python_checker(self):
        for name, label in self.cases["B"].items():
            self.assertEqual(self.js["B"][name], G.validate_b(label, BASE_A, PROFS), name)

    def test_cases_cover_both_clean_and_failing_labels(self):
        self.assertEqual(self.js["A"]["ok"], [])
        self.assertTrue(any(self.js["A"][k] for k in self.js["A"] if k != "ok"))
        self.assertEqual(self.js["B"]["ok"], [])
        self.assertEqual(self.js["B"]["cond_ref_nested_leaf"], [])  # 그룹 안의 조건도 가리킬 수 있다

    def test_number_phrase_helper(self):
        p = self.js["phrase"]
        self.assertEqual((p["7년 이내"]["op"], p["7년 이내"]["num"]), ("LTE", 7))
        self.assertEqual((p["만 39세 이하"]["op"], p["만 39세 이하"]["num"]), ("LTE", 39))
        self.assertEqual((p["10인 미만"]["op"], p["10인 미만"]["num"]), ("LT", 10))
        self.assertEqual((p["3억원 이상"]["op"], p["3억원 이상"]["krw"]), ("GTE", 300000000))
        self.assertIsNone(p["제한 없음"])

    def test_zip_is_a_valid_archive_with_utf8_names(self):
        import base64
        z = zipfile.ZipFile(io.BytesIO(base64.b64decode(self.js["zip"])))
        self.assertIsNone(z.testzip())
        self.assertEqual(z.namelist(), ["labels/kwan/A/N_1.json", "labels/kwan/B/N_1.json"])
        self.assertEqual(json.loads(z.read("labels/kwan/A/N_1.json").decode("utf-8")), {"가": 1})


if __name__ == "__main__":
    unittest.main()
