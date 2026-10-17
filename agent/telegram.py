"""Minimal Telegram Bot API client for the approval flow."""
import json
from pathlib import Path

import requests

from .config import env

LIMIT = 4000  # Telegram's hard limit is 4096 characters per message


def _call(method: str, files=None, **params) -> dict:
    url = f"https://api.telegram.org/bot{env('TELEGRAM_BOT_TOKEN')}/{method}"
    r = requests.post(url, data=params, files=files, timeout=60)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram {method} failed: {data.get('description')}")
    return data["result"]


def chat_id() -> str:
    return env("TELEGRAM_CHAT_ID")


def send(text: str, buttons: list[list[tuple[str, str]]] | None = None) -> int:
    params = {"chat_id": chat_id(), "text": text[:LIMIT], "disable_web_page_preview": "true"}
    if buttons:
        params["reply_markup"] = json.dumps(
            {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in buttons]}
        )
    return _call("sendMessage", **params)["message_id"]


def send_album(images: list[Path], caption: str = "") -> None:
    for start in range(0, len(images), 10):  # albums hold at most 10 items
        chunk = images[start:start + 10]
        media, files = [], {}
        for i, path in enumerate(chunk):
            key = f"img{i}"
            files[key] = (path.name, open(path, "rb"), "image/jpeg")
            item = {"type": "photo", "media": f"attach://{key}"}
            if i == 0 and start == 0 and caption:
                item["caption"] = caption[:1000]
            media.append(item)
        try:
            _call("sendMediaGroup", files=files, chat_id=chat_id(), media=json.dumps(media))
        finally:
            for f in files.values():
                f[1].close()


def set_buttons(message_id: int, buttons: list[list[tuple[str, str]]] | None) -> None:
    markup = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in row] for row in (buttons or [])]}
    try:
        _call("editMessageReplyMarkup", chat_id=chat_id(), message_id=message_id, reply_markup=json.dumps(markup))
    except RuntimeError as e:  # e.g. "message is not modified" — harmless
        print(f"[telegram] {e}")


def answer_callback(callback_id: str, text: str) -> None:
    try:
        _call("answerCallbackQuery", callback_query_id=callback_id, text=text)
    except RuntimeError:
        pass  # callback queries expire after a while; the bot may only see them on the next poll


def get_updates(offset: int) -> list[dict]:
    try:
        return _call("getUpdates", offset=offset, timeout=0,
                     allowed_updates=json.dumps(["message", "callback_query"]))
    except RuntimeError as e:
        if "webhook" in str(e).lower():
            raise RuntimeError("Instant mode (webhook) is on, so taps are queued in the Cloudflare worker — "
                               "set the WORKER_URL and WORKER_SECRET secrets.") from e
        raise


# ── instant mode: the Cloudflare worker receives taps instantly and queues them for us ──
def queue_enabled() -> bool:
    return bool(env("WORKER_URL", required=False))


def _queue(method: str, path: str, **kwargs):
    r = requests.request(method, env("WORKER_URL").rstrip("/") + path,
                         headers={"Authorization": f"Bearer {env('WORKER_SECRET')}"}, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def queued_updates() -> list[dict]:
    return _queue("GET", "/queue")


def ack(update_id: int) -> None:
    _queue("POST", "/queue/ack", json={"ids": [update_id]})
