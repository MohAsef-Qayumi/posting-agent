"""`python main.py check` — verifies each credential with a harmless read-only call."""
from datetime import date

import requests

from .config import env, load_config, now


def _line(ok: bool, name: str, detail: str) -> bool:
    print(f"{'✅' if ok else '❌'} {name}: {detail}")
    return ok


def check() -> bool:
    cfg = load_config()
    results = []

    # Anthropic
    try:
        import anthropic

        anthropic.Anthropic().models.retrieve(cfg["claude"]["model"])
        results.append(_line(True, "Claude API", f"key works, model {cfg['claude']['model']} available"))
    except Exception as e:
        results.append(_line(False, "Claude API", str(e)[:200]))

    # Telegram
    try:
        r = requests.get(f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/getMe", timeout=20).json()
        if not r.get("ok"):
            raise RuntimeError(r.get("description"))
        env("TELEGRAM_CHAT_ID")
        results.append(_line(True, "Telegram", f"bot @{r['result']['username']}"))
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

    print("\nAll good! 🎉" if all(results) else "\nFix the ❌ items above (see SETUP.md).")
    return all(results)
