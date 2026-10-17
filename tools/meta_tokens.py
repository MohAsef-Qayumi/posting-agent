"""Turns a short-lived Graph API Explorer token into a never-expiring Facebook Page token,
and finds the Instagram account linked to the Page.

    python tools/meta_tokens.py <APP_ID> <APP_SECRET> <SHORT_LIVED_USER_TOKEN>
"""
import sys
from datetime import datetime

import requests

GRAPH = "https://graph.facebook.com/v23.0"


def get(path: str, **params) -> dict:
    data = requests.get(f"{GRAPH}/{path}", params=params, timeout=30).json()
    if "error" in data:
        sys.exit(f"Error from Meta ({path}): {data['error'].get('message')}")
    return data


app_id = sys.argv[1] if len(sys.argv) > 1 else input("App ID: ").strip()
app_secret = sys.argv[2] if len(sys.argv) > 2 else input("App Secret: ").strip()
short_token = sys.argv[3] if len(sys.argv) > 3 else input("Short-lived user token: ").strip()

long_user = get("oauth/access_token", grant_type="fb_exchange_token", client_id=app_id,
                client_secret=app_secret, fb_exchange_token=short_token)["access_token"]
pages = get("me/accounts", access_token=long_user, fields="id,name,access_token")["data"]
if not pages:
    sys.exit("No Pages found. Make sure you selected your Page when granting permissions in Graph API Explorer.")

for i, p in enumerate(pages):
    print(f"[{i}] {p['name']} ({p['id']})")
choice = pages[int(input("Which Page? number: ") or 0)] if len(pages) > 1 else pages[0]

page_token = choice["access_token"]
info = get("debug_token", input_token=page_token, access_token=f"{app_id}|{app_secret}")["data"]
expires = info.get("expires_at", 0)
ig = get(choice["id"], fields="instagram_business_account{id,username}", access_token=page_token).get("instagram_business_account")

print(f"\n✅ Page: {choice['name']}")
print("   Token expires: " + ("never ✨" if not expires else datetime.fromtimestamp(expires).isoformat()))
print("\nAdd these as GitHub secrets (and to .env for local testing):\n")
print(f"FB_PAGE_ID           = {choice['id']}")
print(f"FB_PAGE_ACCESS_TOKEN = {page_token}")
if ig:
    print(f"IG_USER_ID           = {ig['id']}   (@{ig.get('username')})")
else:
    print("\n⚠️  No Instagram account linked to this Page yet. Switch Instagram to a Professional account,")
    print("    link it in the Page settings (Linked accounts → Instagram), then run this again.")
