"""Local preview: generate (or use a sample) and render slides into preview/ without touching Telegram."""
import json

from .config import ROOT, now
from .render import render_slides

SAMPLE = {
    "pillar": "Code",
    "topic": "Python one-liners that replace whole loops",
    "linkedin_text": "(sample LinkedIn text)",
    "facebook_text": "(sample Facebook text)",
    "instagram_caption": "(sample Instagram caption)",
    "hashtags": ["python", "coding"],
    "cta": "Follow for daily dev tips",
    "alt_text": "Carousel with Python tips",
    "slides": [
        {"kind": "cover", "title": "5 Python tricks that *replace loops*", "body": "Write less code. Ship cleaner logic.", "code": "", "language": ""},
        {"kind": "point", "title": "Think in transformations", "body": "Most loops just map, filter or reduce a list. Name the transformation and Python usually has a one-liner for it.", "code": "", "language": ""},
        {"kind": "code", "title": "Filter + map in one line", "body": "Comprehensions are faster and easier to read than append loops.", "code": "# before\nresult = []\nfor u in users:\n    if u.active:\n        result.append(u.email)\n\n# after\nresult = [u.email for u in users if u.active]", "language": "python"},
        {"kind": "point", "title": "Count without a dict dance", "body": "collections.Counter turns a 6-line counting loop into one readable call: Counter(words).most_common(3).", "code": "", "language": ""},
    ],
}


def preview(pillar: str | None, sample: bool = False) -> None:
    if sample:
        post = SAMPLE
    else:
        from .content import generate_post

        post = generate_post(pillar_override=pillar)
    out = ROOT / "preview" / f"{now():%Y%m%d-%H%M%S}"
    names = render_slides(post, out)
    (out / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n=== {post['pillar']}: {post['topic']} ===\n")
    print("--- LinkedIn ---\n" + post["linkedin_text"] + "\n")
    print("--- Facebook ---\n" + post["facebook_text"] + "\n")
    print("--- Instagram ---\n" + post["instagram_caption"] + "\n" + " ".join("#" + t for t in post["hashtags"]))
    print(f"\nSlides ({len(names)}) saved in: {out}")
