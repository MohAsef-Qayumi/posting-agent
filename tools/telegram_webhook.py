"""Connects your Telegram bot to the Cloudflare worker (instant mode). Reads TELEGRAM_BOT_TOKEN from .env.

    python tools/telegram_webhook.py secret          make a random WORKER_SECRET
    python tools/telegram_webhook.py on <WORKER_URL> turn instant mode on   (needs WORKER_SECRET in .env)
    python tools/telegram_webhook.py off             back to polling every hour
    python tools/telegram_webhook.py info            show the current setting
"""
import os
import secrets
import sys
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass


def call(method: str, **params) -> dict:
    token = os.environ.get("TELEGRAM_BOT_TOKEN") or sys.exit("TELEGRAM_BOT_TOKEN is missing from .env")
    for attempt in range(5):  # some networks drop connections to Telegram now and then
        try:
            data = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=params, timeout=60).json()
            break
        except requests.ConnectionError:
            if attempt == 4:
                sys.exit("Couldn't reach Telegram after 5 tries — check your connection (or a VPN) and run this again.")
            time.sleep(3)
    if not data.get("ok"):
        sys.exit(f"Telegram {method} failed: {data.get('description')}")
    return data["result"]


command = sys.argv[1] if len(sys.argv) > 1 else "info"

if command == "secret":
    print(f"WORKER_SECRET={secrets.token_urlsafe(32)}")
    print("\nSave it in .env, as a GitHub secret and as a Cloudflare worker secret (all three the same).")

elif command == "on":
    url = (sys.argv[2] if len(sys.argv) > 2 else input("Worker URL: ")).strip().rstrip("/")
    secret = os.environ.get("WORKER_SECRET") or sys.exit("WORKER_SECRET is missing from .env — run: python tools/telegram_webhook.py secret")
    check = requests.get(url, timeout=30)
    if "posting-agent worker" not in check.text:
        sys.exit(f"{url} doesn't look like the posting-agent worker (got: {check.text[:100]!r})")
    call("setWebhook", url=f"{url}/telegram", secret_token=secret,
         allowed_updates=["message", "callback_query"], drop_pending_updates=False)
    print("✅ Instant mode is on. Send /help to your bot to try it.")

elif command == "off":
    call("deleteWebhook")
    print("✅ Instant mode is off — taps are handled by the hourly run. Remove the WORKER_URL secret on GitHub too.")

else:
    info = call("getWebhookInfo")
    print(f"Webhook: {info.get('url') or '(none — polling mode)'}")
    if info.get("pending_update_count"):
        print(f"Pending updates: {info['pending_update_count']}")
    if info.get("last_error_message"):
        print(f"Last error: {info['last_error_message']}")
