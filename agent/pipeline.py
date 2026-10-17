"""Glue: create drafts, handle Telegram approvals, publish to the platforms."""
import os
import traceback
from datetime import date

from . import store, telegram
from .config import env, load_config, now

PLATFORM_ICONS = {"linkedin": "💼 LinkedIn", "facebook": "📘 Facebook", "instagram": "📸 Instagram"}
TERMINAL = {"published", "skipped", "replaced", "expired"}


def _pending_buttons(draft_id: str):
    return [[("✅ Approve & post", f"a:{draft_id}")], [("🔁 Regenerate", f"r:{draft_id}"), ("❌ Skip", f"s:{draft_id}")]]


def _instagram_caption(post: dict) -> str:
    tags = " ".join(f"#{t}" for t in post["hashtags"])
    return f"{post['instagram_caption']}\n.\n.\n{tags}" if tags else post["instagram_caption"]


# ── generate ──────────────────────────────────────────────────
def create_draft(pillar: str | None = None, replace: str | None = None, send_to_telegram: bool = True) -> dict:
    from .content import generate_post
    from .render import render_slides

    old = store.load_draft(replace) if replace else None
    if old:
        pillar = pillar or old["pillar"]

    post = generate_post(pillar_override=pillar, avoid_topic=old["topic"] if old else None)
    draft = {
        "id": store.new_draft_id(),
        "created": now().isoformat(timespec="seconds"),
        "status": "pending",
        "pillar": post["pillar"],
        "topic": post["topic"],
        "post": post,
        "images": [],
        "results": {},
    }
    draft["images"] = render_slides(post, store.draft_dir(draft["id"]))
    store.save_draft(draft)

    if old:
        _finish(old, "replaced")

    if send_to_telegram:
        send_preview(draft)
        _linkedin_token_reminder()
    return draft


def send_preview(draft: dict) -> None:
    post = draft["post"]
    telegram.send_album(store.slide_paths(draft), f"🗓 {now():%a %d %b} · #{draft['pillar']}\n{draft['topic']}")
    telegram.send(f"💼 LINKEDIN\n\n{post['linkedin_text']}")
    telegram.send(f"📘 FACEBOOK\n\n{post['facebook_text']}")
    telegram.send(f"📸 INSTAGRAM\n\n{_instagram_caption(post)}")
    draft["control_message_id"] = telegram.send(
        f"👆 Today's draft ({draft['id']}) — what should I do?", _pending_buttons(draft["id"])
    )
    store.save_draft(draft)


def _linkedin_token_reminder() -> None:
    expires = env("LINKEDIN_TOKEN_EXPIRES", required=False)
    if not expires:
        return
    days = (date.fromisoformat(expires) - now().date()).days
    if days <= 7:
        telegram.send(
            f"⚠️ Your LinkedIn token expires in {days} day(s) ({expires}). "
            "Run tools/linkedin_auth.py again and update the LINKEDIN_ACCESS_TOKEN and "
            "LINKEDIN_TOKEN_EXPIRES secrets on GitHub."
        )


# ── publish ───────────────────────────────────────────────────
def publish(draft: dict) -> dict:
    """Publishes to every enabled platform not already done. Safe to call again to retry failures."""
    from .publishers import linkedin, meta

    cfg = load_config()["platforms"]
    post, images = draft["post"], store.slide_paths(draft)
    results = draft.setdefault("results", {})

    def attempt(platform: str, fn):
        if not cfg.get(platform) or results.get(platform, {}).get("ok"):
            return
        try:
            results[platform] = {"ok": True, "url": fn()}
        except Exception as e:
            traceback.print_exc()
            results[platform] = {"ok": False, "error": str(e)[:500]}

    attempt("linkedin", lambda: linkedin.publish(post["linkedin_text"], images, post["alt_text"]))

    needs_meta = any(cfg.get(p) and not results.get(p, {}).get("ok") for p in ("facebook", "instagram"))
    if needs_meta and not draft.get("photo_ids"):
        try:
            draft["photo_ids"] = meta.upload_unpublished_photos(images)
        except Exception as e:
            traceback.print_exc()
            for p in ("facebook", "instagram"):
                if cfg.get(p):
                    results[p] = {"ok": False, "error": f"photo upload: {str(e)[:450]}"}
    if draft.get("photo_ids"):
        attempt("facebook", lambda: meta.publish_facebook(post["facebook_text"], draft["photo_ids"]))
        attempt("instagram", lambda: meta.publish_instagram(_instagram_caption(post), meta.photo_urls(draft["photo_ids"])))

    enabled = [p for p in ("linkedin", "facebook", "instagram") if cfg.get(p)]
    all_ok = all(results.get(p, {}).get("ok") for p in enabled)
    draft["status"] = "published" if all_ok else "partial"
    store.save_draft(draft)
    if all_ok:
        _finish(draft, "published")
    return results


def _finish(draft: dict, status: str) -> None:
    draft["status"] = status
    store.save_draft(draft)
    store.add_history({
        "date": draft["id"][:10],
        "draft_id": draft["id"],
        "pillar": draft["pillar"],
        "topic": draft["topic"],
        "status": status,
        "links": {p: r.get("url") for p, r in draft.get("results", {}).items() if r.get("ok")},
    })


def _report(draft: dict) -> str:
    lines = []
    for p, r in draft["results"].items():
        lines.append(f"{PLATFORM_ICONS[p]}: " + (f"✅ {r['url']}" if r["ok"] else f"❌ {r['error']}"))
    return "\n".join(lines)


# ── process Telegram updates ──────────────────────────────────
HELP = (
    "🤖 Posting agent commands\n\n"
    "/new — create an extra draft now (today's pillar)\n"
    "/new AI | Career | Tech | Startup | Code | Engagement | Mindset — draft on a pillar\n"
    "/status — show recent drafts\n"
    "/help — this message\n\n"
    "Drafts arrive daily at 08:00. Taps are processed within ~30 minutes."
)


def process_updates() -> list[dict]:
    """Handles button taps and commands. Returns generate requests to dispatch (regenerate / new)."""
    owner = str(telegram.chat_id())
    dispatch: list[dict] = []
    offset = store.telegram_offset()

    for update in telegram.get_updates(offset + 1 if offset else 0):
        offset = max(offset, update["update_id"])
        store.set_telegram_offset(offset)  # never process the same tap twice, even after a crash
        try:
            if (cb := update.get("callback_query")) and str(cb["message"]["chat"]["id"]) == owner:
                _handle_button(cb, dispatch)
            elif (msg := update.get("message")) and str(msg["chat"]["id"]) == owner:
                _handle_command(msg.get("text", "").strip(), dispatch)
        except Exception as e:
            traceback.print_exc()
            telegram.send(f"💥 Something went wrong: {str(e)[:500]}\nCheck the GitHub Actions log for details.")

    _expire_old_drafts()
    store.prune_drafts()
    return dispatch


def _handle_button(cb: dict, dispatch: list[dict]) -> None:
    action, _, draft_id = cb.get("data", "").partition(":")
    draft = store.load_draft(draft_id)
    if not draft or draft["status"] in TERMINAL:
        telegram.answer_callback(cb["id"], "This draft is no longer active.")
        return
    msg_id = draft.get("control_message_id")

    if action == "a":
        telegram.answer_callback(cb["id"], "Publishing…")
        telegram.set_buttons(msg_id, None)
        draft["status"] = "approved"
        store.save_draft(draft)
        publish(draft)
        if draft["status"] == "published":
            telegram.send(f"🚀 Published {draft['id']}\n\n{_report(draft)}")
        else:
            telegram.send(f"⚠️ Partly published {draft['id']}\n\n{_report(draft)}", [[("🔁 Retry failed", f"a:{draft_id}")]])
    elif action == "r":
        telegram.answer_callback(cb["id"], "Regenerating…")
        telegram.set_buttons(msg_id, None)
        telegram.send(f"🔁 Writing a new version of {draft['id']} — it'll arrive in a few minutes.")
        dispatch.append({"replace": draft_id})
    elif action == "s":
        telegram.answer_callback(cb["id"], "Skipped")
        telegram.set_buttons(msg_id, None)
        _finish(draft, "skipped")
        telegram.send(f"❌ Skipped {draft['id']}. See you tomorrow!")


def _handle_command(text: str, dispatch: list[dict]) -> None:
    cmd, _, arg = text.partition(" ")
    cmd = cmd.lower().split("@")[0]
    if cmd == "/new":
        dispatch.append({"pillar": arg.strip()} if arg.strip() else {})
        telegram.send("✍️ Writing a new draft — it'll arrive in a few minutes.")
    elif cmd == "/status":
        drafts = store.all_drafts()[-7:]
        lines = [f"{d['id']} · {d['pillar']} · {d['status']}\n  {d['topic']}" for d in drafts]
        telegram.send("📋 Recent drafts\n\n" + ("\n".join(lines) or "No drafts yet."))
    elif cmd in ("/help", "/start"):
        telegram.send(HELP)


def _expire_old_drafts(max_age_days: int = 2) -> None:
    for d in store.all_drafts():
        if d["status"] == "pending" and (now().date() - date.fromisoformat(d["id"][:10])).days >= max_age_days:
            telegram.set_buttons(d.get("control_message_id"), None)
            _finish(d, "expired")


def run_dispatch(requests_: list[dict], dispatch_file: str | None) -> None:
    """In GitHub Actions, hand generate requests to the heavier generate workflow; locally, run them inline."""
    if not requests_:
        return
    if os.environ.get("GITHUB_ACTIONS") and dispatch_file:
        with open(dispatch_file, "w", encoding="utf-8") as f:
            for r in requests_:
                f.write(f"{r.get('pillar', '')}|{r.get('replace', '')}\n")
        return
    for r in requests_:
        create_draft(pillar=r.get("pillar") or None, replace=r.get("replace") or None)
