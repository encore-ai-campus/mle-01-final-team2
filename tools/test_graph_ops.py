"""Aura 점검 도구 단위 시험(DB 접속 없음). 적재 도구 시험은 test_sync_graph.py. 실행: python -m unittest tools.test_graph_ops -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_graph_neo4j as CHK  # noqa: E402


def snap(**checks):
    base = {cid: (exp if isinstance(exp, int) else 0) for cid, _, _, exp in CHK.CHECKS}
    return {"nodes": 10, "relationships": 5, "labels": {"Notice": 1}, "relationship_types": {"ABOUT": 2}, "keys": {"Notice": {"missing": 0, "dup": 0}},
            "checks": {**base, **checks}, "paths": {"p": 21}}


class CheckTests(unittest.TestCase):
    def test_judge_zero_checks_fail_and_known_values_warn(self):
        self.assertEqual(CHK.judge(snap()), ([], []))
        fails, warns = CHK.judge(snap(V4=3, V17=5))
        self.assertEqual(len(fails), 1)
        self.assertIn("V4", fails[0])
        self.assertIn("V17", warns[0])
        bad = snap()
        bad["keys"]["Notice"] = {"missing": 0, "dup": 2}
        self.assertIn("V0", CHK.judge(bad)[0][0])

    def test_diff_lists_only_changes(self):
        a, b = snap(), snap(V17=1)
        b["labels"] = {"Notice": 1, "Definition": 2}
        b["nodes"] = 12
        out = CHK.diff(a, b)
        self.assertEqual(len(out), 3)
        self.assertTrue(any(x.startswith("nodes: 10 → 12 (+2)") for x in out))
        self.assertTrue(any("labels.Definition: None → 2" in x for x in out))
        self.assertEqual(CHK.diff(a, snap()), [])

    def test_schema_cypher_has_every_check_query(self):
        # 제출용 schema.cypher의 점검 쿼리가 점검 스크립트와 어긋나지 않게 한다
        text = (Path(__file__).resolve().parents[1] / "docs" / "submission" / "ontology" / "schema.cypher").read_text(encoding="utf-8")
        missing = [cid for cid, _, cy, _ in CHK.CHECKS if cy + ";" not in text]
        self.assertEqual(missing, [])
        self.assertTrue(all(cy + ";" in text for cy in CHK.PATHS.values()))

    def test_key_query_rejects_bad_identifiers(self):
        self.assertIn("count(n.notice_id)", CHK.key_check_cypher("Notice", "notice_id"))
        with self.assertRaises(AssertionError):
            CHK.key_check_cypher("Notice) DETACH DELETE n //", "x")


if __name__ == "__main__":
    unittest.main()
