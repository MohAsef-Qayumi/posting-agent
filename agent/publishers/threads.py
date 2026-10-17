"""Threads publishing through the Threads API (graph.threads.net)."""
import time

import requests

from ..config import env, load_config

BASE = "https://graph.threads.net"


class ThreadsError(RuntimeError):
    pass


def _api(method: str, path: str, **params) -> dict:
    version = load_config()["api_versions"].get("threads", "v1.0")
    params["access_token"] = env("THREADS_ACCESS_TOKEN")
    r = requests.request(method, f"{BASE}/{version}/{path}", params=params, timeout=120)
    data = r.json() if r.content else {}
    if not r.ok or "error" in data:
        err = data.get("error", {})
        raise ThreadsError(f"{method} {path} → {r.status_code}: {err.get('message', r.text[:300])}")
    return data


def _user() -> str:
    return env("THREADS_USER_ID", required=False) or "me"


def _wait_ready(container_id: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _api("GET", container_id, fields="status,error_message")
        if status.get("status") == "FINISHED":
            return
        if status.get("status") in ("ERROR", "EXPIRED"):
            raise ThreadsError(f"Threads media {container_id} failed: {status.get('error_message')}")
        time.sleep(4)
    raise ThreadsError(f"Threads media {container_id} not ready after {timeout}s")


def publish(text: str, image_urls: list[str]) -> str:
    """Text-only, single image or carousel (2–20 images). Returns the post's permalink."""
    user = _user()
    if not image_urls:
        creation = _api("POST", f"{user}/threads", media_type="TEXT", text=text)["id"]
    elif len(image_urls) == 1:
        creation = _api("POST", f"{user}/threads", media_type="IMAGE", image_url=image_urls[0], text=text)["id"]
    else:
        children = [
            _api("POST", f"{user}/threads", media_type="IMAGE", image_url=url, is_carousel_item="true")["id"]
            for url in image_urls[:20]
        ]
        for cid in children:
            _wait_ready(cid)
        creation = _api("POST", f"{user}/threads", media_type="CAROUSEL", children=",".join(children), text=text)["id"]
    _wait_ready(creation)
    media_id = _api("POST", f"{user}/threads_publish", creation_id=creation)["id"]
    return _api("GET", media_id, fields="permalink").get("permalink", f"threads media {media_id}")


def refresh_token() -> tuple[str, int]:
    """Extends the long-lived token by another 60 days. Returns (token, expires_in_seconds)."""
    r = requests.get(f"{BASE}/refresh_access_token", params={
        "grant_type": "th_refresh_token", "access_token": env("THREADS_ACCESS_TOKEN"),
    }, timeout=60)
    data = r.json()
    if "access_token" not in data:
        raise ThreadsError(f"token refresh failed: {data.get('error', data)}")
    return data["access_token"], int(data.get("expires_in", 5184000))
