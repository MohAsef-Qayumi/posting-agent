"""One-time Threads sign-in. Prints the secrets to save.

    python tools/threads_auth.py <THREADS_APP_ID> <THREADS_APP_SECRET>

Your Meta app's Threads settings must list this redirect URL: https://localhost:8765/callback
After you click "Allow", the browser shows a "can't reach this page" error — that's expected.
Copy the full address from the address bar and paste it here.
"""
import secrets
import sys
import webbrowser
from datetime import date, timedelta
from urllib.parse import parse_qs, urlencode, urlparse

import requests

REDIRECT = "https://localhost:8765/callback"
SCOPES = "threads_basic,threads_content_publish"


def check(data: dict, step: str) -> dict:
    if "error" in data or "error_message" in data:
        err = data.get("error", {})
        sys.exit(f"Error from Threads ({step}): {err.get('message') if isinstance(err, dict) else data}")
    return data


app_id = (sys.argv[1] if len(sys.argv) > 1 else input("Threads app ID: ")).strip().strip("<>")
if not app_id.isdigit():
    sys.exit(f"The Threads app ID should be only digits, got: {app_id!r}")
app_secret = (sys.argv[2] if len(sys.argv) > 2 else input("Threads app secret: ")).strip().strip("<>")
state = secrets.token_urlsafe(16)

url = "https://www.threads.com/oauth/authorize?" + urlencode({
    "client_id": app_id, "redirect_uri": REDIRECT, "scope": SCOPES, "response_type": "code", "state": state,
})
print("Opening Threads in your browser… if it doesn't open, visit:\n" + url)
webbrowser.open(url)
print("\nAfter clicking Allow, the page won't load — that's fine.")
pasted = input("Paste the full address from the browser's address bar: ").strip()

q = parse_qs(urlparse(pasted).query)
if "error" in q:
    sys.exit(f"Threads returned an error: {q.get('error_description', q['error'])[0]}")
if q.get("state", [""])[0] != state or "code" not in q:
    sys.exit("That address doesn't contain a valid sign-in code — try again and paste the whole address.")
code = q["code"][0].removesuffix("#_")

short = check(requests.post("https://graph.threads.net/oauth/access_token", data={
    "client_id": app_id, "client_secret": app_secret, "grant_type": "authorization_code",
    "redirect_uri": REDIRECT, "code": code,
}, timeout=30).json(), "code exchange")
long = check(requests.get("https://graph.threads.net/access_token", params={
    "grant_type": "th_exchange_token", "client_secret": app_secret, "access_token": short["access_token"],
}, timeout=30).json(), "long-lived token")
me = check(requests.get("https://graph.threads.net/v1.0/me", params={
    "fields": "id,username", "access_token": long["access_token"],
}, timeout=30).json(), "profile")
expires = date.today() + timedelta(seconds=long.get("expires_in", 5184000))

print(f"\n✅ Signed in as @{me.get('username')}\n\nAdd these as GitHub secrets (and to .env for local testing):\n")
print(f"THREADS_USER_ID       = {me['id']}")
print(f"THREADS_ACCESS_TOKEN  = {long['access_token']}")
print(f"THREADS_TOKEN_EXPIRES = {expires.isoformat()}")
