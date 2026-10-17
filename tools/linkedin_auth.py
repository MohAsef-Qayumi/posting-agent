"""One-time LinkedIn sign-in. Opens your browser, you click "Allow", and it prints the secrets to save.

    python tools/linkedin_auth.py <CLIENT_ID> <CLIENT_SECRET>

Your LinkedIn app must list this redirect URL: http://localhost:8765/callback
Tokens last 60 days — run this again when the Telegram bot reminds you.
"""
import secrets
import sys
import webbrowser
from datetime import date, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

REDIRECT = "http://localhost:8765/callback"
SCOPES = "openid profile w_member_social"

client_id = sys.argv[1] if len(sys.argv) > 1 else input("LinkedIn Client ID: ").strip()
client_secret = sys.argv[2] if len(sys.argv) > 2 else input("LinkedIn Client Secret: ").strip()
state = secrets.token_urlsafe(16)
result: dict = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        q = parse_qs(urlparse(self.path).query)
        if q.get("state", [""])[0] != state:
            self.send_response(400)
            self.end_headers()
            return
        result.update({k: v[0] for k, v in q.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("<h2>Done — you can close this tab and return to the terminal.</h2>".encode())

    def log_message(self, *args):
        pass


url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
    "response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "state": state, "scope": SCOPES,
})
print("Opening LinkedIn in your browser… if it doesn't open, visit:\n" + url)
webbrowser.open(url)
server = HTTPServer(("localhost", 8765), Handler)
while not result:
    server.handle_request()

if "error" in result:
    sys.exit(f"LinkedIn returned an error: {result.get('error_description', result['error'])}")

token = requests.post("https://www.linkedin.com/oauth/v2/accessToken", data={
    "grant_type": "authorization_code", "code": result["code"], "redirect_uri": REDIRECT,
    "client_id": client_id, "client_secret": client_secret,
}, timeout=30).json()
if "access_token" not in token:
    sys.exit(f"Token exchange failed: {token}")

me = requests.get("https://api.linkedin.com/v2/userinfo",
                  headers={"Authorization": f"Bearer {token['access_token']}"}, timeout=30).json()
expires = date.today() + timedelta(seconds=token.get("expires_in", 5184000))

print(f"\n✅ Signed in as {me.get('name')}\n\nAdd these as GitHub secrets (and to .env for local testing):\n")
print(f"LINKEDIN_ACCESS_TOKEN = {token['access_token']}")
print(f"LINKEDIN_PERSON_URN   = urn:li:person:{me['sub']}")
print(f"LINKEDIN_TOKEN_EXPIRES = {expires.isoformat()}")
