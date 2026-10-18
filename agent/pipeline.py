"""Glue: create drafts, handle Telegram approvals, publish to the platforms."""
import json
import os
import subprocess
import time
import traceback
from datetime import date, timedelta

import requests

from . import store, telegram
from .config import env, load_config, now

PLATFORMS = ("linkedin", "facebook", "instagram", "threads")
PLATFORM_ICONS = {"linkedin": "💼 LinkedIn", "facebook": "📘 Facebook", "instagram": "📸 Instagram", "threads": "🧵 Threads"}
TERMINAL = {"published", "skipped", "replaced", "expired"}


def _languages() -> dict:
    """Facebook languages offered as buttons: {"en": {...}, "fa": {"label": "فارسی", "name": "..."}, ...}."""
    return {"en": {"label": "English", "name": "English"}, **(load_config().get("facebook_languages") or {})}


def _controls(draft: dict) -> list[list[tuple[str, str]]]:
    """Approve buttons — one per ready Facebook language, so approving also picks the language."""
    did = draft["id"]
    if not load_config()["platforms"].get("facebook"):
        rows = [[("✅ Approve & post", f"a:{did}")]]
    else:
        texts, langs = _facebook_texts(draft), _languages()
        ready = [(f"✅ Post · FB {lang['label']}", f"a:{did}:{code}") for code, lang in langs.items() if code in texts]
        rows = [ready[:1], ready[1:]] if len(ready) > 1 else [ready]
        missing = [(f"🌐 Write FB in {lang['label']}", f"l:{did}:{code}") for code, lang in langs.items() if code not in texts]
        if missing:
            rows.append(missing)
    rows.append([("🔁 Regenerate", f"r:{did}"), ("❌ Skip", f"s:{did}")])
    return rows


def _send_controls(draft: dict) -> None:
    """(Re)sends the button message at the bottom of the chat and disables the previous one."""
    if draft.get("control_message_id"):
        telegram.set_buttons(draft["control_message_id"], None)
    question = ("pick the Facebook language to post with" if load_config()["platforms"].get("facebook")
                else "what should I do?")
    draft["control_message_id"] = telegram.send(f"👆 Draft {draft['id']} — {question}", _controls(draft))
    store.save_draft(draft)


def _facebook_texts(draft: dict) -> dict:
    return draft.get("facebook_texts") or {"en": draft["post"]["facebook_text"]}


def _translate_facebook(post: dict) -> dict:
    """Writes the Facebook post in every extra language up front, so the preview has them all."""
    texts = {"en": post["facebook_text"]}
    if not load_config()["platforms"].get("facebook"):
        return texts
    from .content import translate

    for code, lang in _languages().items():
        if code == "en":
            continue
        try:
            texts[code], used = translate(post["facebook_text"], lang["name"])
            print(f"[translate] Facebook {code} written by {used}")
        except Exception as e:  # the preview offers a "Write FB in …" button instead
            print(f"[translate] Facebook {code} failed: {e}")
    return texts


def _instagram_caption(post: dict) -> str:
    tags = " ".join(f"#{t}" for t in post["hashtags"])
    return f"{post['instagram_caption']}\n.\n.\n{tags}" if tags else post["instagram_caption"]


def _facebook_text(draft: dict) -> str:
    return _facebook_texts(draft).get(draft.get("facebook_lang", "en")) or draft["post"]["facebook_text"]


# ── generate ──────────────────────────────────────────────────
def create_draft(pillar: str | None = None, replace: str | None = None, idea: str | None = None,
                 send_to_telegram: bool = True) -> dict:
    from .content import generate_post
    from .render import render_slides

    old = store.load_draft(replace) if replace else None
    if old:
        pillar = pillar or old["pillar"]
        idea = idea or old.get("idea")

    post = generate_post(pillar_override=pillar, avoid_topic=old["topic"] if old else None, idea=idea)
    draft = {
        "id": store.new_draft_id(),
        "created": now().isoformat(timespec="seconds"),
        "status": "pending",
        "pillar": post["pillar"],
        "topic": post["topic"],
        "idea": idea or "",
        "post": post,
        "images": [],
        "results": {},
        "facebook_texts": _translate_facebook(post),
    }
    draft["images"] = render_slides(post, store.draft_dir(draft["id"]))
    store.save_draft(draft)

    if old:
        _finish(old, "replaced")

    if send_to_telegram:
        send_preview(draft)
        _token_upkeep()
    return draft


def send_preview(draft: dict) -> None:
    post, enabled = draft["post"], load_config()["platforms"]
    telegram.send_album(store.slide_paths(draft), f"🗓 {now():%a %d %b} · #{draft['pillar']}\n{draft['topic']}")
    if enabled.get("linkedin"):
        telegram.send(f"💼 LINKEDIN\n\n{post['linkedin_text']}")
    if enabled.get("facebook"):
        langs = _languages()
        for code, text in _facebook_texts(draft).items():
            telegram.send(f"📘 FACEBOOK · {langs.get(code, {}).get('label', code)}\n\n{text}")
    if enabled.get("instagram"):
        telegram.send(f"📸 INSTAGRAM\n\n{_instagram_caption(post)}")
    if enabled.get("threads"):
        telegram.send(f"🧵 THREADS\n\n{post.get('threads_text', '')}")
    _send_controls(draft)


def _token_upkeep() -> None:
    """LinkedIn: remind before expiry. Threads: renew automatically every week (needs GH_PAT), else remind."""
    if expires := env("LINKEDIN_TOKEN_EXPIRES", required=False):
        days = (date.fromisoformat(expires) - now().date()).days
        if days <= 7:
            telegram.send(
                f"⚠️ Your LinkedIn token expires in {days} day(s) ({expires}). "
                "Run tools/linkedin_auth.py again and update the LINKEDIN_ACCESS_TOKEN and "
                "LINKEDIN_TOKEN_EXPIRES secrets on GitHub."
            )

    if not load_config()["platforms"].get("threads") or not env("THREADS_ACCESS_TOKEN", required=False):
        return
    state = store.get_state("threads", {})
    if state.get("refreshed") and (now().date() - date.fromisoformat(state["refreshed"])).days < 7:
        return
    repo = os.environ.get("GITHUB_REPOSITORY")
    if env("GH_PAT", required=False) and repo:
        try:
            from .publishers import threads

            token, seconds = threads.refresh_token()
            print(f"::add-mask::{token}")
            done = subprocess.run(
                ["gh", "secret", "set", "THREADS_ACCESS_TOKEN", "--repo", repo],
                input=token, text=True, capture_output=True, env={**os.environ, "GH_TOKEN": env("GH_PAT")},
            )
            if done.returncode:
                raise RuntimeError(f"saving the new token failed: {done.stderr.strip()[:300]}")
            expires = (now().date() + timedelta(seconds=seconds)).isoformat()
            store.set_state("threads", {"refreshed": now().date().isoformat(), "expires": expires})
            print(f"[threads] token renewed, valid until {expires}")
            return
        except Exception as e:
            traceback.print_exc()
            telegram.send(f"⚠️ Couldn't renew the Threads token automatically: {str(e)[:300]}")
    expires = state.get("expires") or env("THREADS_TOKEN_EXPIRES", required=False)
    if expires and (date.fromisoformat(expires) - now().date()).days <= 7:
        telegram.send(
            f"⚠️ Your Threads token expires on {expires}. Run tools/threads_auth.py again and update the "
            "THREADS_ACCESS_TOKEN and THREADS_TOKEN_EXPIRES secrets (or add GH_PAT so it renews itself)."
        )


# ── publish ───────────────────────────────────────────────────
def publish(draft: dict) -> dict:
    """Publishes to every enabled platform not already done. Safe to call again to retry failures."""
    from .publishers import linkedin, meta

    cfg = load_config()["platforms"]
    post, images = draft["post"], store.slide_paths(draft)
    results = draft.setdefault("results", {})
    todo = [p for p in PLATFORMS if cfg.get(p) and not results.get(p, {}).get("ok")]

    def attempt(platform: str, fn):
        if platform not in todo:
            return
        try:
            results[platform] = {"ok": True, "url": fn()}
        except Exception as e:
            traceback.print_exc()
            results[platform] = {"ok": False, "error": str(e)[:500]}

    attempt("linkedin", lambda: linkedin.publish(post["linkedin_text"], images, post["alt_text"]))

    # Facebook posts the Page photos; Instagram and Threads need public image URLs, which those photos provide.
    image_users = [p for p in ("facebook", "instagram", "threads") if p in todo]
    if image_users and not draft.get("photo_ids"):
        try:
            draft["photo_ids"] = meta.upload_unpublished_photos(images)
        except Exception as e:
            traceback.print_exc()
            for p in image_users:
                results[p] = {"ok": False, "error": f"photo upload: {str(e)[:450]}"}
    if draft.get("photo_ids"):
        urls: list[str] = []

        def image_urls() -> list[str]:
            if not urls:
                urls.extend(meta.photo_urls(draft["photo_ids"]))
            return urls

        attempt("facebook", lambda: meta.publish_facebook(_facebook_text(draft), draft["photo_ids"]))
        attempt("instagram", lambda: meta.publish_instagram(_instagram_caption(post), image_urls()))
        if "threads" in todo:
            from .publishers import threads

            attempt("threads", lambda: threads.publish(post.get("threads_text") or post["facebook_text"][:500], image_urls()))

    enabled = [p for p in PLATFORMS if cfg.get(p)]
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
    "🤖 Posting agent\n\n"
    "💡 Send me any idea (a sentence or more) and I'll turn it into a draft.\n"
    "   Start with a pillar to set the theme, e.g. \"Career why freelancers need contracts\".\n\n"
    "/new — create an extra draft now (today's pillar)\n"
    "/new AI | Career | Tech | Startup | Code | Engagement | Mindset — draft on a pillar\n"
    "/status — show recent drafts\n"
    "/help — this message\n\n"
    "Each draft shows the Facebook post in English, فارسی and پښتو —\n"
    "tap ✅ Post · FB <language> to publish everywhere with that Facebook version."
)


def _incoming_updates() -> list[dict]:
    """Instant mode: updates queued by the Cloudflare worker (plus the one that triggered this run).
    Otherwise: poll Telegram with getUpdates."""
    if not telegram.queue_enabled():
        offset = store.telegram_offset()
        return telegram.get_updates(offset + 1 if offset else 0)

    updates = {}
    if trigger := os.environ.get("TELEGRAM_UPDATE", "").strip():
        u = json.loads(trigger)
        updates[u["update_id"]] = u
    for attempt in range(3):  # the worker's queue can take a few seconds to show new entries
        for u in telegram.queued_updates():
            updates[u["update_id"]] = u
        if updates or attempt == 2:
            break
        time.sleep(8)
    return [updates[k] for k in sorted(updates)]


def process_updates() -> list[dict]:
    """Handles button taps, ideas and commands. Returns generate requests to dispatch."""
    owner = str(telegram.chat_id())
    queue_mode = telegram.queue_enabled()
    dispatch: list[dict] = []
    seen = store.seen_updates()

    for update in _incoming_updates():
        uid = update["update_id"]
        # mark as handled first: never process the same tap twice, even after a crash
        if queue_mode:
            telegram.ack(uid)
            if uid in seen:
                continue
            store.mark_seen(uid)
        else:
            store.set_telegram_offset(uid)
        try:
            if (cb := update.get("callback_query")) and str(cb["message"]["chat"]["id"]) == owner:
                _handle_button(cb, dispatch)
            elif (msg := update.get("message")) and str(msg["chat"]["id"]) == owner:
                _handle_message(msg.get("text", "").strip(), dispatch)
        except Exception as e:
            traceback.print_exc()
            telegram.send(f"💥 Something went wrong: {str(e)[:500]}\nCheck the GitHub Actions log for details.")

    _expire_old_drafts()
    store.prune_drafts()
    _ensure_daily_draft(dispatch)
    return dispatch


def _ensure_daily_draft(dispatch: list[dict], by_hour: int = 22) -> None:
    """Safety net: GitHub sometimes delays or skips scheduled runs. No draft by 22:00 → start one (once a day)."""
    today = f"{now():%Y-%m-%d}"
    if now().hour < by_hour or any(d["id"].startswith(today) for d in store.all_drafts()):
        return
    if store.get_state("daily", {}).get("backup_requested") == today:
        return
    store.set_state("daily", {"backup_requested": today})
    dispatch.append({})
    telegram.send("⏰ Today's evening draft didn't arrive (GitHub skipped or delayed it) — writing it now.")


def _handle_button(cb: dict, dispatch: list[dict]) -> None:
    action, _, rest = cb.get("data", "").partition(":")
    draft_id, _, arg = rest.partition(":")
    draft = store.load_draft(draft_id)
    if not draft or draft["status"] in TERMINAL or (action == "l" and draft["status"] != "pending"):
        telegram.answer_callback(cb["id"], "This draft is no longer active.")
        return
    msg_id = draft.get("control_message_id")

    if action == "a":
        telegram.answer_callback(cb["id"], "Publishing…")
        telegram.set_buttons(msg_id, None)
        if arg in _facebook_texts(draft):  # "Retry failed" has no language and keeps the chosen one
            draft["facebook_lang"] = arg
        draft["status"] = "approved"
        store.save_draft(draft)
        publish(draft)
        lang = _languages().get(draft.get("facebook_lang", "en"), {}).get("label", "English")
        if draft["status"] == "published":
            telegram.send(f"🚀 Published {draft['id']} · Facebook in {lang}\n\n{_report(draft)}")
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
    elif action == "l" and arg in _languages():
        from .content import translate

        lang = _languages()[arg]
        telegram.answer_callback(cb["id"], f"Writing Facebook in {lang['label']}…")
        texts = draft.setdefault("facebook_texts", _facebook_texts(draft))
        if arg not in texts:
            try:
                texts[arg], _ = translate(texts["en"], lang["name"])
            except Exception as e:
                traceback.print_exc()
                telegram.send(
                    f"⚠️ Couldn't write the {lang['label']} version right now — the AI writers are busy.\n"
                    "Tap the button again in a minute, or post with one of the ready languages."
                    f"\n\n({str(e)[:200]})"
                )
                return
        store.save_draft(draft)
        telegram.send(f"📘 FACEBOOK · {lang['label']}\n\n{texts[arg]}")
        _send_controls(draft)


def _handle_message(text: str, dispatch: list[dict]) -> None:
    if not text.startswith("/"):
        if len(text.split()) >= 3:
            _queue_draft(text, dispatch)
        else:
            telegram.send("💡 Send me an idea of at least a few words and I'll draft a post about it.\n\n" + HELP)
        return
    cmd, _, arg = text.partition(" ")
    cmd = cmd.lower().split("@")[0]
    if cmd == "/new":
        _queue_draft(arg.strip(), dispatch)
    elif cmd == "/status":
        drafts = store.all_drafts()[-7:]
        lines = [f"{d['id']} · {d['pillar']} · {d['status']}\n  {d['topic']}" for d in drafts]
        telegram.send("📋 Recent drafts\n\n" + ("\n".join(lines) or "No drafts yet."))
    elif cmd in ("/help", "/start"):
        telegram.send(HELP)


def _queue_draft(text: str, dispatch: list[dict]) -> None:
    """`text` is empty (today's pillar), a pillar name, or an idea that may start with a pillar name."""
    pillars = {s["pillar"].lower(): s["pillar"] for s in load_config()["rotation"].values()}
    first, _, rest = text.partition(" ")
    request = {}
    if first.lower() in pillars:
        request["pillar"] = pillars[first.lower()]
        text = text if rest.strip() else ""  # "AI agents are overhyped" keeps its first word
    if text:
        request["idea"] = text[:1500]
    dispatch.append(request)
    telegram.send(("✍️ Writing a draft from your idea" if text else "✍️ Writing a new draft")
                  + " — it'll arrive in about 3 minutes.")


def _expire_old_drafts(max_age_days: int = 2) -> None:
    for d in store.all_drafts():
        if d["status"] == "pending" and (now().date() - date.fromisoformat(d["id"][:10])).days >= max_age_days:
            telegram.set_buttons(d.get("control_message_id"), None)
            _finish(d, "expired")


def run_dispatch(requests_: list[dict]) -> None:
    """In GitHub Actions, start the (heavier) generate workflow for each request; locally, run them inline."""
    if not requests_:
        return
    if not os.environ.get("GITHUB_ACTIONS"):
        for r in requests_:
            create_draft(pillar=r.get("pillar"), replace=r.get("replace"), idea=r.get("idea"))
        return
    repo = os.environ["GITHUB_REPOSITORY"]
    for r in requests_:
        resp = requests.post(
            f"https://api.github.com/repos/{repo}/actions/workflows/generate.yml/dispatches",
            headers={"Authorization": f"Bearer {env('GITHUB_TOKEN')}", "Accept": "application/vnd.github+json"},
            json={"ref": os.environ.get("GITHUB_REF_NAME", "main"),
                  "inputs": {k: r.get(k, "") for k in ("pillar", "replace", "idea")}},
            timeout=30,
        )
        if not resp.ok:
            telegram.send(f"💥 Couldn't start the draft workflow: {resp.status_code} {resp.text[:300]}")
