"""LinkedIn personal-profile publishing via the Posts + Images APIs (scope: w_member_social)."""
import re
import time
from pathlib import Path
from urllib.parse import quote

import requests

from ..config import env, load_config

API = "https://api.linkedin.com/rest"
# Characters LinkedIn's "little text" format reserves; unescaped they silently truncate posts.
RESERVED = re.compile(r"([\\|{}@\[\]()<>#*_~])")


class LinkedInError(RuntimeError):
    pass


def _headers(json_body: bool = True) -> dict:
    h = {
        "Authorization": f"Bearer {env('LINKEDIN_ACCESS_TOKEN')}",
        "LinkedIn-Version": str(load_config()["api_versions"]["linkedin"]),
        "X-Restli-Protocol-Version": "2.0.0",
    }
    if json_body:
        h["Content-Type"] = "application/json"
    return h


def _check(r: requests.Response, what: str) -> requests.Response:
    if not r.ok:
        raise LinkedInError(f"{what} → {r.status_code}: {r.text[:400]}")
    return r


def person_urn() -> str:
    urn = env("LINKEDIN_PERSON_URN", required=False)
    if urn:
        return urn
    r = _check(
        requests.get("https://api.linkedin.com/v2/userinfo",
                     headers={"Authorization": f"Bearer {env('LINKEDIN_ACCESS_TOKEN')}"}, timeout=30),
        "userinfo",
    )
    return f"urn:li:person:{r.json()['sub']}"


def format_commentary(text: str) -> str:
    """Escape reserved characters, keeping #hashtags as real clickable hashtags."""
    out = []
    for token in re.split(r"(#\w+)", text):
        if re.fullmatch(r"#\w+", token):
            out.append("{hashtag|\\#|" + token[1:] + "}")
        else:
            out.append(RESERVED.sub(r"\\\1", token))
    return "".join(out)


def upload_image(path: Path, owner: str) -> str:
    r = _check(
        requests.post(f"{API}/images?action=initializeUpload", headers=_headers(),
                      json={"initializeUploadRequest": {"owner": owner}}, timeout=30),
        "image init",
    )
    value = r.json()["value"]
    with open(path, "rb") as f:
        _check(requests.put(value["uploadUrl"], headers={"Authorization": _headers()["Authorization"]},
                            data=f, timeout=120), "image upload")
    urn = value["image"]
    for _ in range(15):  # wait until LinkedIn finishes processing the image
        status = requests.get(f"{API}/images/{quote(urn)}", headers=_headers(False), timeout=30)
        if status.ok and status.json().get("status") == "AVAILABLE":
            break
        time.sleep(2)
    return urn


def publish(text: str, images: list[Path], alt_text: str) -> str:
    owner = person_urn()
    urns = [upload_image(p, owner) for p in images[:20]]
    body = {
        "author": owner,
        "commentary": format_commentary(text),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    if len(urns) > 1:
        body["content"] = {"multiImage": {"images": [{"id": u, "altText": alt_text[:4000]} for u in urns]}}
    elif urns:
        body["content"] = {"media": {"id": urns[0], "altText": alt_text[:4000]}}

    r = requests.post(f"{API}/posts", headers=_headers(), json=body, timeout=60)
    if not r.ok and len(urns) > 1:  # fall back to a single cover image if multi-image is rejected
        body["content"] = {"media": {"id": urns[0], "altText": alt_text[:4000]}}
        r = requests.post(f"{API}/posts", headers=_headers(), json=body, timeout=60)
    _check(r, "create post")
    post_urn = r.headers.get("x-restli-id", "")
    return f"https://www.linkedin.com/feed/update/{post_urn}/" if post_urn else "posted"
