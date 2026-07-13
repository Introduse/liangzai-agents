#!/usr/bin/env python3
"""One-time OAuth loopback consent for the supplier mailbox + tracker Sheet.

Mints refresh tokens for three scopes:

  gmail.readonly  — the Gmail MCP connector cannot download attachment bytes,
                    and supplier invoices arrive as PDF/photo attachments.
                    Read-only means we never label, move, or delete mail.
  gmail.send      — sends the Reconciliation Summary from the mailbox itself,
                    which is the From: line the proposal promised. Send-only:
                    it grants no read access and cannot touch drafts.
  spreadsheets    — the Drive MCP connector cannot append rows to a Sheet.

Scope classification, since it decides everything below: gmail.readonly is
RESTRICTED (external apps need an annual third-party security assessment);
gmail.send is merely SENSITIVE. An Internal client is exempt from both.

Two accounts, two phases:

  DEV       We do not have access to ai@example.com. Consent as our own
            Google account, which receives mocked-up supplier invoices and has
            edit access to the owner's tracker Sheet. Set OAUTH_ACCOUNT to it.

  PRODUCTION the owner consents as ai@example.com inside his own Cowork
            project, and OAUTH_ACCOUNT is set to that address. The guard below
            then refuses any other account, so a stray personal login can never
            silently become the mailbox the agent reads.

    python3 scripts/oauth/google_oauth.py

THE OAUTH CLIENT MUST BE "INTERNAL". This is not a preference.

`gmail.readonly` is a Google *restricted* scope. An EXTERNAL OAuth client using it
needs brand verification, scope verification, and an annual third-party CASA
security assessment. Leaving the app in "Testing" to avoid that caps refresh-token
lifetime at 7 DAYS — so the weekly job would run once and then die silently,
forever, while appearing to be configured correctly.

your-workspace.example is a Google Workspace domain (MX -> aspmx.l.google.com). An
OAuth client created inside that Workspace org with user type **Internal** is
exempt from verification, from the test-user cap, and from the 7-day expiry.

So: create the client in a Google Cloud project owned by the your-workspace.example
Workspace, set the consent screen's user type to Internal, and consent as
ai@example.com. `/liangzai-setup` walks through this step by step.
"""
import http.server
import json
import os
import sys
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
# pyrefly: ignore [missing-import]
from env import read_env  # noqa: E402

PORT = 5179
REDIRECT_URI = f"http://localhost:{PORT}"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
]
SETTINGS = Path(__file__).resolve().parents[2] / ".claude" / "settings.local.json"


def save(**kv):
    data = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
    data.setdefault("env", {}).update(kv)
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    cid = read_env("GOOGLE_CLIENT_ID", required=True)
    csecret = read_env("GOOGLE_CLIENT_SECRET", required=True)
    expected = (read_env("OAUTH_ACCOUNT", required=True) or "").strip().lower()

    auth_url = "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "login_hint": expected,
    })

    print(
        f"Sign in as {expected} and grant access:\n\n{auth_url}\n\n"
        f"NOTE: your Google OAuth client must list this exact Authorized redirect URI:\n"
        f"  {REDIRECT_URI}\n"
        f"(Google Cloud console -> Credentials -> your OAuth client -> Authorized redirect URIs)\n"
        f"Without it Google rejects the sign-in with 'redirect_uri_mismatch'.\n",
        flush=True,
    )
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    holder = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            if "code" in q:
                holder["code"] = q["code"][0]
                self.wfile.write(b"<h2>Done. Close this tab and return to the terminal.</h2>")
            else:
                self.wfile.write(b"<h2>No code returned. Check the terminal.</h2>")

        def log_message(self, *a):
            pass

    httpd = http.server.HTTPServer(("localhost", PORT), Handler)
    httpd.timeout = 300
    httpd.handle_request()

    code = holder.get("code")
    if not code:
        raise SystemExit("No auth code received (timed out after 5 minutes).")

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "code": code, "client_id": cid, "client_secret": csecret,
            "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code",
        }).encode(), method="POST")
    with urllib.request.urlopen(req) as r:
        tok = json.load(r)

    refresh = tok.get("refresh_token")
    if not refresh:
        raise SystemExit(f"No refresh_token in response: {list(tok)}. "
                         "Revoke prior consent and retry with prompt=consent.")

    # Confirm we consented as the intended mailbox, not somebody's personal account.
    # Without this guard a stray Google login silently becomes the inbox the agent reads.
    prof = urllib.request.Request(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers={"Authorization": f"Bearer {tok['access_token']}"})
    with urllib.request.urlopen(prof) as r:
        email = json.load(r).get("emailAddress", "")
    if email.lower() != expected:
        raise SystemExit(f"Consented as {email!r}, but OAUTH_ACCOUNT is {expected!r}. "
                         "Nothing saved — re-run and pick the right account, or fix "
                         "OAUTH_ACCOUNT in .claude/settings.local.json.")

    # One consent covers both scopes, so both tokens are the same value.
    save(GMAIL_REFRESH_TOKEN=refresh, SHEETS_REFRESH_TOKEN=refresh)
    print(f"OK — consented as {email}. Refresh tokens saved to .claude/settings.local.json")


if __name__ == "__main__":
    main()
