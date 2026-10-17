"""`python main.py check` — verifies each credential with a harmless read-only call."""
from datetime import date

import requests

from .config import env, load_config, now
from .llm import pick_provider


def _line(ok: bool, name: str, detail: str) -> bool:
    print(f"{'✅' if ok else '❌'} {name}: {detail}")
    return ok


def check() -> bool:
    cfg = load_config()
    results = []

    # AI writer — a tiny real request to whichever provider is active
    try:
        from .llm import complete_json

        schema = {"type": "object", "properties": {"ok": {"type": "string"}}, "required": ["ok"], "additionalProperties": False}
        provider = pick_provider(cfg)
        if provider == "claude":
            _, used = complete_json(cfg, "Reply in JSON.", 'Return {"ok": "yes"}.', schema)
        else:
            from . import llm

            from .llm import candidates

            model = candidates(cfg)[0][1]
            sys_prompt = 'Respond with only the JSON object {"ok": "yes"}.'
            raw = llm._gemini(model, sys_prompt, "ping") if provider == "gemini" else llm._openai_compatible(provider, model, sys_prompt, "ping")
            used = f"{provider}/{model}" if raw.strip() else ""
        results.append(_line(bool(used), "AI writer", f"{used} works"))
    except Exception as e:
        results.append(_line(False, "AI writer", str(e)[:200]))

    # Telegram
    try:
        r = requests.get(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getMe", timeout=60).json()
        if not r.get("ok"):
            raise RuntimeError(r.get("description"))
        env("TELEGRAM_CHAT_ID")
        results.append(_line(True, "Telegram", f"bot @{r['result']['username']}"))
        hook = requests.get(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getWebhookInfo", timeout=60).json()["result"]
        if hook.get("url"):
            from . import telegram

            if not telegram.queue_enabled():
                raise RuntimeError("instant mode is on but WORKER_URL / WORKER_SECRET are missing")
            telegram.queued_updates()  # proves the worker URL and secret are right
            note = f" (last error: {hook['last_error_message']})" if hook.get("last_error_message") else ""
            results.append(_line(not note, "Instant mode", f"worker connected{note}"))
        else:
            print("ℹ️  Instant mode: off — taps are handled by the hourly run (see SETUP.md step 9)")
    except Exception as e:
        results.append(_line(False, "Telegram", str(e)[:200]))

    # LinkedIn
    if cfg["platforms"].get("linkedin"):
        try:
            r = requests.get("https://api.linkedin.com/v2/userinfo",
                             headers={"Authorization": f"Bearer {env('LINKEDIN_ACCESS_TOKEN')}"}, timeout=20)
            r.raise_for_status()
            detail = f"signed in as {r.json().get('name')}"
            if exp := env("LINKEDIN_TOKEN_EXPIRES", required=False):
                detail += f", token expires in {(date.fromisoformat(exp) - now().date()).days} days"
            results.append(_line(True, "LinkedIn", detail))
        except Exception as e:
            results.append(_line(False, "LinkedIn", str(e)[:200]))

    # Facebook + Instagram
    graph = f"https://graph.facebook.com/{cfg['api_versions']['meta_graph']}"
    if cfg["platforms"].get("facebook") or cfg["platforms"].get("instagram"):
        try:
            token = env("FB_PAGE_ACCESS_TOKEN")
            r = requests.get(f"{graph}/{env('FB_PAGE_ID')}", params={"fields": "name,instagram_business_account", "access_token": token}, timeout=20).json()
            if "error" in r:
                raise RuntimeError(r["error"]["message"])
            results.append(_line(True, "Facebook Page", r["name"]))
            if cfg["platforms"].get("instagram"):
                ig = env("IG_USER_ID")
                linked = r.get("instagram_business_account", {}).get("id")
                u = requests.get(f"{graph}/{ig}", params={"fields": "username", "access_token": token}, timeout=20).json()
                if "error" in u:
                    raise RuntimeError(u["error"]["message"])
                note = "" if linked == ig else " (warning: not the account linked to this Page)"
                results.append(_line(True, "Instagram", f"@{u['username']}{note}"))
        except Exception as e:
            results.append(_line(False, "Facebook/Instagram", str(e)[:200]))

    # Threads
    if cfg["platforms"].get("threads"):
        try:
            r = requests.get(f"https://graph.threads.net/{cfg['api_versions'].get('threads', 'v1.0')}/me",
                             params={"fields": "username", "access_token": env("THREADS_ACCESS_TOKEN")}, timeout=20).json()
            if "error" in r:
                raise RuntimeError(r["error"]["message"])
            detail = f"@{r['username']}"
            if exp := env("THREADS_TOKEN_EXPIRES", required=False):
                detail += f", token expires in {(date.fromisoformat(exp) - now().date()).days} days"
            results.append(_line(True, "Threads", detail))
        except Exception as e:
            results.append(_line(False, "Threads", str(e)[:200]))

    print("\nAll good! 🎉" if all(results) else "\nFix the ❌ items above (see SETUP.md).")
    return all(results)
