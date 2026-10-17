"""Renders the Page profile picture and cover photo (dark tech theme) into preview/brand/.

    python tools/brand_assets.py
"""
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent.parent / "preview" / "brand"

HEAD = """<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;600&display=block" rel="stylesheet">
<style>
:root { --bg:#070b12; --cyan:#22d3ee; --violet:#a78bfa; --green:#34d399; --muted:#8b98ad; --text:#e6edf7;
        --grad:linear-gradient(100deg,var(--cyan),var(--violet)); }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--bg); }
.canvas { position:relative; overflow:hidden; color:var(--text); font-family:Inter,sans-serif;
  background:
    radial-gradient(closest-side, rgba(34,211,238,.18), transparent) var(--g1),
    radial-gradient(closest-side, rgba(167,139,250,.22), transparent) var(--g2),
    linear-gradient(rgba(120,160,220,.07) 1px, transparent 1px) 0 0/48px 48px,
    linear-gradient(90deg, rgba(120,160,220,.07) 1px, transparent 1px) 0 0/48px 48px,
    var(--bg); }
.hl { background:var(--grad); -webkit-background-clip:text; background-clip:text; color:transparent; }
svg.net { position:absolute; inset:0; width:100%; height:100%; }
</style></head><body>"""


def network(width: int, height: int, seed: int, count: int, avoid=None) -> str:
    """Decorative 'neural network' of glowing nodes and links, kept away from the text area."""
    import random

    rnd = random.Random(seed)
    pts = []
    while len(pts) < count:
        x, y = rnd.uniform(0, width), rnd.uniform(0, height)
        if avoid and avoid[0] < x < avoid[2] and avoid[1] < y < avoid[3]:
            continue
        pts.append((x, y))
    lines, dots = [], []
    for i, (x, y) in enumerate(pts):
        near = sorted(pts, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)[1:3]
        for nx, ny in near:
            lines.append(f'<line x1="{x:.0f}" y1="{y:.0f}" x2="{nx:.0f}" y2="{ny:.0f}"/>')
        r = rnd.choice([3, 4, 5, 7])
        color = rnd.choice(["#22d3ee", "#a78bfa", "#34d399"])
        dots.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r}" fill="{color}" opacity="{rnd.uniform(.5, 1):.2f}" filter="url(#glow)"/>')
    return (f'<svg class="net" viewBox="0 0 {width} {height}"><defs><filter id="glow"><feGaussianBlur stdDeviation="3" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'<g stroke="rgba(139,152,173,.22)" stroke-width="1.5">{"".join(lines)}</g>{"".join(dots)}</svg>')


PROFILE = HEAD + """
<style>
.canvas { width:1080px; height:1080px; --g1:-200px -200px/900px 900px no-repeat; --g2:380px 380px/1000px 1000px no-repeat;
  display:grid; place-items:center; }
.ring { width:820px; height:820px; border-radius:50%; padding:10px; background:conic-gradient(from 200deg, var(--cyan), var(--violet), var(--green), var(--cyan));
  box-shadow:0 0 120px rgba(34,211,238,.35), 0 0 220px rgba(167,139,250,.25); position:relative; z-index:2; }
.inner { width:100%; height:100%; border-radius:50%; background:radial-gradient(circle at 35% 30%, #142033, #070b12 70%);
  display:flex; flex-direction:column; align-items:center; justify-content:center; }
.mono { font:700 290px/1 "Space Grotesk"; letter-spacing:-12px; }
.br { font:600 150px/1 "JetBrains Mono"; color:var(--muted); opacity:.8; }
.row { display:flex; align-items:center; gap:18px; }
.tag { font:500 46px "JetBrains Mono"; color:var(--green); margin-top:34px; letter-spacing:2px; }
.tag::after { content:"▍"; color:var(--cyan); }
</style>
<div class="canvas">__NET__
  <div class="ring"><div class="inner">
    <div class="row"><span class="br">{</span><span class="mono hl">MAQ</span><span class="br">}</span></div>
    <div class="tag">build.solve()</div>
  </div></div>
</div></body></html>"""

COVER = HEAD + """
<style>
.canvas { width:1640px; height:856px; --g1:-300px -400px/1300px 1300px no-repeat; --g2:900px 100px/1200px 1200px no-repeat;
  display:flex; flex-direction:column; align-items:center; justify-content:center; text-align:center; }
.content { position:relative; z-index:2; }
.prompt { font:500 30px "JetBrains Mono"; color:var(--green); margin-bottom:30px; }
.prompt::after { content:"▍"; color:var(--cyan); margin-left:6px; }
h1 { font:700 92px/1.05 "Space Grotesk"; letter-spacing:-2px; }
.sub { font:400 34px Inter; color:var(--muted); margin-top:30px; }
.pills { display:flex; gap:18px; justify-content:center; margin-top:44px; }
.pills span { font:600 24px "JetBrains Mono"; color:var(--cyan); padding:12px 26px; border-radius:999px;
  border:2px solid rgba(34,211,238,.35); background:rgba(7,11,18,.7); }
.pills span:nth-child(even) { color:var(--violet); border-color:rgba(167,139,250,.4); }
</style>
<div class="canvas">__NET__
  <div class="content">
    <div class="prompt">$ while (problems) { solve(); }</div>
    <h1>Turning <span class="hl">problems</span> into<br><span class="hl">solutions</span> — one line at a time</h1>
    <div class="sub">Full-stack developer · Building remote</div>
    <div class="pills"><span>#AI</span><span>#Tech</span><span>#Career</span><span>#Startup</span><span>#Code</span></div>
  </div>
</div></body></html>"""


def render(page, html: str, size: tuple[int, int], path: Path) -> None:
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.set_content(html, wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    page.locator(".canvas").screenshot(path=str(path), type="png")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    profile = PROFILE.replace("__NET__", network(1080, 1080, seed=7, count=34, avoid=(110, 110, 970, 970)))
    cover = COVER.replace("__NET__", network(1640, 856, seed=3, count=46, avoid=(260, 150, 1380, 720)))
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        render(page, profile, (1080, 1080), OUT / "page_profile.png")
        render(page, cover, (1640, 856), OUT / "page_cover.png")
        browser.close()
    print(f"Saved to {OUT}")


if __name__ == "__main__":
    main()
