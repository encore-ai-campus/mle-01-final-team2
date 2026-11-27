"""서비스 지연 측정 도구 단위 시험(DB 접속 없음). 실행: python -m unittest tools.test_measure_service_latency -v"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import measure_service_latency as M  # noqa: E402

PATH = [{"id": "REGION:GANGNAM", "name": "강남구"}, {"id": "REGION:SEOUL", "name": "서울"}]
OLD_PATHS = [{"cond_id": "N1#C-region", "nodes": PATH}]
OLD_DEFS = [{"notice_id": "N1", "cond_id": "N1#C-type", "def_id": "D1", "article_id": "A2"},
            {"notice_id": "N1", "cond_id": "N1#C-type", "def_id": "D1", "article_id": "T1"}]
CARDS = [
    {"notice_id": "N1", "cond_id": "N1#C-region", "nodes": PATH, "basis": []},
    {"notice_id": "N1", "cond_id": "N1#C-type", "nodes": None,
     "basis": [{"def_id": "D1", "article_id": "A2"}, {"def_id": "D1", "article_id": "T1"}]},
]


class Stats(unittest.TestCase):
    def test_percentiles(self):
        xs = [float(i) for i in range(1, 101)]
        self.assertEqual(M.pct(xs, 0.5), 51.0)
        self.assertEqual(M.pct(xs, 0.95), 95.0)
        s = M.summarize(xs)
        self.assertEqual((s["n"], s["p50_ms"], s["mean_ms"]), (100, 50.5, 50.5))


class Comparable(unittest.TestCase):
    def test_same_rows_compare_equal(self):
        old, new = M.comparable(OLD_PATHS, OLD_DEFS, CARDS, "REGION:GANGNAM")
        self.assertEqual(old, new)

    def test_missing_appendix_basis_is_a_mismatch(self):
        cards = [dict(c) for c in CARDS]
        cards[1]["basis"] = cards[1]["basis"][:1]  # 별표 근거가 빠지면
        old, new = M.comparable(OLD_PATHS, OLD_DEFS, cards, "REGION:GANGNAM")
        self.assertEqual(old[0], new[0])
        self.assertNotEqual(old[1], new[1])

    def test_unreached_region_compares_as_none(self):
        old, new = M.comparable([{"cond_id": "N1#C-region", "nodes": None}], [],
                                [{"notice_id": "N1", "cond_id": "N1#C-region", "nodes": None, "basis": []}], "REGION:BUSAN")
        self.assertEqual(old, new)
        self.assertEqual(old[0], {"N1#C-region": None})

    def test_no_region_has_no_paths(self):
        old, new = M.comparable([], OLD_DEFS, CARDS, None)
        self.assertEqual(old, new)


if __name__ == "__main__":
    unittest.main()
