"""Prints your Telegram chat id. First send any message (e.g. "hi") to your bot, then run:

    python tools/telegram_chat_id.py <BOT_TOKEN>
"""
import sys

import requests

token = sys.argv[1] if len(sys.argv) > 1 else input("Bot token: ").strip()
data = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=20).json()
if not data.get("ok"):
    sys.exit(f"Error: {data.get('description')}")
chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "") for u in data["result"] if "message" in u}
if not chats:
    sys.exit("No messages found. Send 'hi' to your bot in Telegram, then run this again.")
for cid, name in chats.items():
    print(f"TELEGRAM_CHAT_ID = {cid}   ({name})")
