"""Facebook Page + Instagram publishing through the Meta Graph API (one Page token covers both)."""
import json
import time
from pathlib import Path

import requests

from ..config import env, load_config


class MetaError(RuntimeError):
    pass


def _graph(method: str, path: str, **kwargs) -> dict:
    version = load_config()["api_versions"]["meta_graph"]
    params = kwargs.pop("params", {})
    params["access_token"] = env("FB_PAGE_ACCESS_TOKEN")
    r = requests.request(method, f"https://graph.facebook.com/{version}/{path}", params=params, timeout=120, **kwargs)
    data = r.json() if r.content else {}
    if not r.ok or "error" in data:
        err = data.get("error", {})
        raise MetaError(f"{method} {path} → {r.status_code}: {err.get('message', r.text[:300])}")
    return data


def upload_unpublished_photos(images: list[Path]) -> list[str]:
    """Uploads images to the Page without publishing them. Returns photo ids.

    These ids are reused for the Facebook multi-photo post, and their CDN URLs
    give Instagram the public image URLs it requires.
    """
    page = env("FB_PAGE_ID")
    ids = []
    for img in images:
        with open(img, "rb") as f:
            data = _graph("POST", f"{page}/photos", data={"published": "false"}, files={"source": (img.name, f, "image/jpeg")})
        ids.append(data["id"])
    return ids


def photo_urls(photo_ids: list[str]) -> list[str]:
    urls = []
    for pid in photo_ids:
        images = _graph("GET", pid, params={"fields": "images"})["images"]
        urls.append(max(images, key=lambda i: i["width"])["source"])
    return urls


def publish_facebook(text: str, photo_ids: list[str]) -> str:
    page = env("FB_PAGE_ID")
    data = {"message": text}
    for i, pid in enumerate(photo_ids):
        data[f"attached_media[{i}]"] = json.dumps({"media_fbid": pid})
    post_id = _graph("POST", f"{page}/feed", data=data)["id"]
    return f"https://www.facebook.com/{post_id}"


def _wait_ready(container_id: str, timeout: int = 120) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = _graph("GET", container_id, params={"fields": "status_code,status"})
        code = status.get("status_code")
        if code == "FINISHED":
            return
        if code in ("ERROR", "EXPIRED"):
            raise MetaError(f"Instagram media {container_id} failed: {status.get('status')}")
        time.sleep(4)
    raise MetaError(f"Instagram media {container_id} not ready after {timeout}s")


def publish_instagram(caption: str, image_urls: list[str]) -> str:
    ig = env("IG_USER_ID")
    if len(image_urls) == 1:
        creation = _graph("POST", f"{ig}/media", data={"image_url": image_urls[0], "caption": caption})["id"]
    else:
        children = []
        for url in image_urls[:20]:
            cid = _graph("POST", f"{ig}/media", data={"image_url": url, "is_carousel_item": "true"})["id"]
            children.append(cid)
        for cid in children:
            _wait_ready(cid)
        creation = _graph(
            "POST", f"{ig}/media",
            data={"media_type": "CAROUSEL", "children": ",".join(children), "caption": caption},
        )["id"]
    _wait_ready(creation)
    media_id = _graph("POST", f"{ig}/media_publish", data={"creation_id": creation})["id"]
    return _graph("GET", media_id, params={"fields": "permalink"}).get("permalink", f"instagram media {media_id}")
