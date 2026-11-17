#!/usr/bin/env python
"""docs/DESIGN.md 의 ```mermaid 블록을 읽어 확대·축소·이동이 되는 docs/architecture.html 을 만든다.

다이어그램 원본은 DESIGN.md 한 곳에만 둔다(이 스크립트는 복사본을 만들 뿐이다).
설계서의 다이어그램을 고치면 이 스크립트를 다시 실행한다.

    python tools/build_architecture_html.py

생성된 HTML은 CDN(jsdelivr)에서 mermaid / svg-pan-zoom 을 불러오므로 인터넷 연결이 필요하다.
조작: 마우스 휠 확대·축소, 드래그 이동, 더블클릭 확대, 버튼(＋ − 맞춤 100%), 키보드(+ − 0).
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs" / "DESIGN.md"
OUT = ROOT / "docs" / "architecture.html"

MERMAID_VER = "10.9.1"
PANZOOM_VER = "3.6.1"

PAGE = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>시스템 아키텍처 다이어그램</title>
<style>
  :root { --bg:#ffffff; --fg:#1f2328; --muted:#656d76; --line:#d0d7de; --panel:#f6f8fa; --btn:#ffffff; --accent:#0969da; }
  @media (prefers-color-scheme: dark) {
    :root:not([data-theme="light"]) { --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --line:#30363d; --panel:#161b22; --btn:#21262d; --accent:#4493f8; }
  }
  :root[data-theme="dark"] { --bg:#0d1117; --fg:#e6edf3; --muted:#8d96a0; --line:#30363d; --panel:#161b22; --btn:#21262d; --accent:#4493f8; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family:-apple-system,"Segoe UI","Noto Sans KR","Malgun Gothic",sans-serif; }
  header { padding:14px 16px 8px; }
  h1 { font-size:18px; margin:0 0 4px; }
  p.hint { margin:0; color:var(--muted); font-size:13px; }
  .block { margin:12px 16px 24px; }
  .block h2 { font-size:15px; margin:0 0 8px; }
  .bar { display:flex; gap:6px; align-items:center; margin-bottom:6px; flex-wrap:wrap; }
  .bar button { background:var(--btn); color:var(--fg); border:1px solid var(--line); border-radius:6px;
                min-width:36px; height:32px; padding:0 10px; font-size:15px; cursor:pointer; }
  .bar button:hover { border-color:var(--accent); }
  .bar .zoom { margin-left:6px; font-size:13px; color:var(--muted); min-width:52px; }
  .view { height:78vh; min-height:320px; border:1px solid var(--line); border-radius:8px;
          background:var(--panel); overflow:hidden; position:relative; cursor:grab; touch-action:none; }
  .view:active { cursor:grabbing; }
  .view svg { width:100%; height:100%; max-width:none !important; display:block; }
  .err { color:#cf222e; white-space:pre-wrap; padding:12px; font-size:13px; }
  pre.src { display:none; }
  .loading { padding:16px; color:var(--muted); font-size:14px; }
</style>
</head>
<body>
<header>
  <h1>시스템 아키텍처 다이어그램</h1>
  <p class="hint">마우스 휠: 확대·축소 · 드래그: 이동 · 더블클릭: 확대 · 키보드 + − 0 · 원본: docs/DESIGN.md</p>
</header>
<main id="root">__BLOCKS__</main>

<script src="https://cdn.jsdelivr.net/npm/mermaid@__MERMAID__/dist/mermaid.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/svg-pan-zoom@__PANZOOM__/dist/svg-pan-zoom.min.js"></script>
<script>
(async function () {
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({ startOnLoad: false, theme: dark ? "dark" : "default",
                       securityLevel: "strict", flowchart: { useMaxWidth: false, htmlLabels: true } });

  const blocks = document.querySelectorAll(".block");
  for (let i = 0; i < blocks.length; i++) {
    const blk = blocks[i];
    const code = blk.querySelector("pre.src").textContent;
    const view = blk.querySelector(".view");
    const label = blk.querySelector(".zoom");
    try {
      const { svg } = await mermaid.render("mmd" + i, code);
      view.innerHTML = svg;
    } catch (e) {
      view.innerHTML = '<div class="err">다이어그램을 그리지 못했습니다.\\n' + (e && e.message ? e.message : e) + "</div>";
      continue;
    }
    const el = view.querySelector("svg");
    el.removeAttribute("height"); el.removeAttribute("width");
    el.style.maxWidth = "none";
    const pz = svgPanZoom(el, { zoomEnabled: true, panEnabled: true, controlIconsEnabled: false,
      fit: true, center: true, minZoom: 0.2, maxZoom: 12, zoomScaleSensitivity: 0.3,
      dblClickZoomEnabled: true, mouseWheelZoomEnabled: true });
    const show = () => { label.textContent = Math.round(pz.getZoom() / (view.__base || 1) * 100) + "%"; };
    view.__base = pz.getZoom();            // '맞춤' 상태를 100%로 표시한다
    pz.setOnZoom(show); show();
    const fit = () => { pz.resize(); pz.fit(); pz.center(); view.__base = pz.getZoom(); show(); };
    blk.querySelector('[data-act="in"]').onclick = () => pz.zoomBy(1.3);
    blk.querySelector('[data-act="out"]').onclick = () => pz.zoomBy(1 / 1.3);
    blk.querySelector('[data-act="fit"]').onclick = fit;
    blk.querySelector('[data-act="one"]').onclick = () => { pz.zoom(view.__base); pz.center(); show(); };
    view.tabIndex = 0;
    view.addEventListener("keydown", (e) => {
      if (e.key === "+" || e.key === "=") pz.zoomBy(1.3);
      else if (e.key === "-" || e.key === "_") pz.zoomBy(1 / 1.3);
      else if (e.key === "0") fit();
    });
    addEventListener("resize", () => { pz.resize(); });
    window["pz" + i] = pz;                 // 콘솔 점검용
  }
})();
</script>
</body>
</html>
"""

BLOCK = """<section class="block">
  <h2>{title}</h2>
  <div class="bar">
    <button data-act="in" title="확대 (+)">＋</button>
    <button data-act="out" title="축소 (-)">－</button>
    <button data-act="fit" title="화면에 맞춤 (0)">맞춤</button>
    <button data-act="one" title="맞춤 크기로">100%</button>
    <span class="zoom">100%</span>
  </div>
  <div class="view"><div class="loading">다이어그램을 불러오는 중…</div></div>
  <pre class="src">{code}</pre>
</section>"""


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    found = list(re.finditer(r"```mermaid\s*\n(.*?)```", text, re.S))
    if not found:
        print(f"{SRC} 에서 mermaid 블록을 찾지 못했습니다.", file=sys.stderr)
        return 1
    codes, items = [], []
    for m in found:  # 각 다이어그램 직전의 가장 가까운 제목을 화면 제목으로 쓴다
        heads = re.findall(r"^#{2,4}\s+(.+)$", text[: m.start()], re.M)
        title = heads[-1].strip() if heads else "다이어그램"
        codes.append(m.group(1))
        items.append(BLOCK.format(title=html.escape(title), code=html.escape(m.group(1).strip())))
    blocks = "\n".join(items)
    page = (PAGE.replace("__BLOCKS__", blocks)
                .replace("__MERMAID__", MERMAID_VER).replace("__PANZOOM__", PANZOOM_VER))
    OUT.write_text(page, encoding="utf-8")
    print(f"다이어그램 {len(codes)}개 → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
