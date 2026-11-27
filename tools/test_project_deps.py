"""pyproject.toml(uv)과 requirements*.txt(Docker·CI)의 의존성 범위가 같은지 본다. 한쪽만 고치면 실패한다.

실행: python -m unittest tools.test_project_deps
"""
from __future__ import annotations

import re
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _norm(spec: str) -> str:
    return re.sub(r"\s+", "", spec.split("#")[0]).lower()


def req_file(name: str) -> set[str]:
    out = set()
    for line in (ROOT / name).read_text(encoding="utf-8").splitlines():
        s = _norm(line)
        if s and not s.startswith("-r"):
            out.add(s)
    return out


class ProjectDepsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.py = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    def group(self, name: str) -> set[str]:
        return {_norm(x) for x in self.py["dependency-groups"][name] if isinstance(x, str)}

    def test_server_deps_match_requirements(self):
        self.assertEqual({_norm(x) for x in self.py["project"]["dependencies"]}, req_file("requirements.txt"))

    def test_tools_group_matches_requirements_tools(self):
        self.assertEqual(self.group("tools"), req_file("requirements-tools.txt"))

    def test_dev_group_matches_requirements_dev(self):
        self.assertEqual(self.group("dev") - {"ruff==0.17.6"}, req_file("requirements-dev.txt"))

    def test_lock_exists_and_python_pinned(self):
        self.assertTrue((ROOT / "uv.lock").exists())
        self.assertEqual((ROOT / ".python-version").read_text(encoding="utf-8").strip(), "3.12")


if __name__ == "__main__":
    unittest.main()
