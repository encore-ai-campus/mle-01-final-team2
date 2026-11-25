#!/usr/bin/env python3
"""수기 정규화 도우미(HTML)를 만든다. 서식(tools/labeler/labeler.template.html)에 공통 프로필 8종을 넣어 tools/labeler/labeler.html로 저장한다.

사용: python tools/make_labeler.py
만든 HTML은 서버나 인터넷 없이 브라우저에서 파일로 연다. 공고 원문(자료 패킷)은 넣지 않는다(로컬 전용 자료).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "tools" / "labeler" / "labeler.template.html"
OUT = ROOT / "tools" / "labeler" / "labeler.html"
PROFILES = ROOT / "data" / "goldset" / "pilot" / "profiles.json"
MARK = "/*__PROFILES__*/[]"


def main() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")
    assert MARK in html, "서식에 프로필 자리표시자가 없다"
    profiles = json.loads(PROFILES.read_text(encoding="utf-8"))["profiles"]
    html = html.replace(MARK, json.dumps(profiles, ensure_ascii=False))
    OUT.write_text(html, encoding="utf-8", newline="\n")
    print(f"저장: {OUT} ({len(html):,}자, 프로필 {len(profiles)}개)")


if __name__ == "__main__":
    main()
