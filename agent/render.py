"""Renders carousel slides to 1080x1350 JPEGs (Instagram's 4:5 portrait format) with headless Chromium."""
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .config import load_config

TEMPLATES = Path(__file__).parent / "templates"


def _highlight(title: str) -> Markup:
    """Turn *word* markers from Claude into gradient-highlighted spans (HTML-escaped first)."""
    return Markup(re.sub(r"\*(.+?)\*", r'<span class="hl">\1</span>', str(escape(title))))


def build_html(post: dict) -> str:
    cfg = load_config()
    author = cfg["author"]
    slides, n = [], 0
    for s in post["slides"]:
        s = dict(s)
        if s["kind"] == "point":
            n += 1
            s["n"] = n
        s["title_html"] = _highlight(s["title"])
        s["title"] = s["title"].replace("*", "")
        slides.append(s)
    slides.append({"kind": "cta", "title": post.get("cta") or "Follow for daily dev tips"})

    env = Environment(loader=FileSystemLoader(TEMPLATES), autoescape=select_autoescape(["html"]))
    return env.get_template("carousel.html").render(
        slides=slides,
        name=author["name"],
        handle=author["instagram_handle"],
        initials=author.get("initials") or author["name"][:2].upper(),
        pillar=post["pillar"],
    )


def render_slides(post: dict, out_dir: Path) -> list[str]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    html = build_html(post)
    (out_dir / "carousel.html").write_text(html, encoding="utf-8")

    names: list[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=1)
        page.set_content(html, wait_until="networkidle")
        page.evaluate("window.fitText()")
        for i, el in enumerate(page.query_selector_all("section.slide"), start=1):
            name = f"slide_{i:02d}.jpg"
            el.screenshot(path=str(out_dir / name), type="jpeg", quality=92)
            names.append(name)
        browser.close()
    return names
