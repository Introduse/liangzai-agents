#!/usr/bin/env python3
"""One-time OAuth consent for the supplier mailbox.

Mints a refresh token for two scopes:

  gmail.readonly  — the Gmail MCP connector cannot download attachment bytes,
                    and supplier invoices arrive as PDF/photo attachments.
                    Read-only means we never label, move, or delete mail.
  gmail.send      — sends the Reconciliation Summary from the mailbox itself,
                    which is the From: line the proposal promised. Send-only:
                    it grants no read access and cannot touch drafts.

There used to be a third, `spreadsheets`, for the tracking Sheet. The Sheet is
gone — the gateway keeps its data in Postgres — so the scope is no longer
requested and SHEETS_REFRESH_TOKEN is no longer written. A token minted before
this change still works: the extra scope is unused, not harmful.

The token lands in two places, for two different consumers: `.claude/settings.
local.json` for `download_invoices.py`, which runs here, and the gateway's Vault
for the summary mailer, which does not. `/liangzai-setup` Step 3j does the
second half — this script only does the first.

Scope classification, since it decides everything below: gmail.readonly is
RESTRICTED (external apps need an annual third-party security assessment);
gmail.send is merely SENSITIVE. An Internal client is exempt from both.

TWO COMMANDS, NO LOCAL SERVER.

    python3 scripts/oauth/google_oauth.py --auth-url
        Prints the Google sign-in link. The owner opens it, signs in, approves.

    python3 scripts/oauth/google_oauth.py --exchange "<the URL he lands on>"
        Takes the redirect URL out of his address bar, pulls the ?code= out of
        it, swaps it for a refresh token, and saves.

The redirect still points at http://localhost:5179 — the URI registered on the
OAuth client — but nothing is listening there, so the browser will show
"This site can't be reached". THAT IS THE SUCCESS CASE. The code we need is
sitting in the address bar of that error page. Google never sends the code
anywhere except that address bar, so pasting the URL back is not a workaround;
it is the whole handoff.

Why no loopback server any more: it needed a free port, a browser that could
reach it, and a terminal held open for five minutes. Copying one URL is
something the owner can do without any of that.

THE OAUTH CLIENT MUST BE "INTERNAL". This is not a preference.

`gmail.readonly` is a Google *restricted* scope. An EXTERNAL OAuth client using it
needs brand verification, scope verification, and an annual third-party CASA
security assessment. Leaving the app in "Testing" to avoid that caps refresh-token
lifetime at 7 DAYS — so the weekly job would run once and then die silently,
forever, while appearing to be configured correctly.

An OAuth client created inside a Google Workspace org with user type **Internal**
is exempt from verification, from the test-user cap, and from the 7-day expiry.
`/liangzai-setup` Step 3 walks through this one click at a time.
"""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "common"))
# pyrefly: ignore [missing-import]
from env import read_env  # noqa: E402

PORT = 5179
REDIRECT_URI = f"http://localhost:{PORT}"
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]
SETTINGS = Path(__file__).resolve().parents[2] / ".claude" / "settings.local.json"


def save(**kv):
    data = json.loads(SETTINGS.read_text()) if SETTINGS.exists() else {}
    data.setdefault("env", {}).update(kv)
    SETTINGS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def build_auth_url(cid, expected):
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urllib.parse.urlencode({
        "client_id": cid,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",   # without this there is no refresh_token at all
        "prompt": "consent",        # force a fresh one even if he consented before
        "login_hint": expected,
    })


def extract_code(pasted):
    """Accept the whole redirect URL, or a bare code if that is all he sent."""
    pasted = pasted.strip().strip('"').strip("'")
    if pasted.startswith("http://") or pasted.startswith("https://"):
        q = urllib.parse.parse_qs(urllib.parse.urlparse(pasted).query)
        if "error" in q:
            raise SystemExit(
                f"Google returned an error instead of a code: {q['error'][0]}.\n"
                "If it says 'access_denied' he clicked Cancel — re-run --auth-url.\n"
                "If it says 'redirect_uri_mismatch', add http://localhost:5179 to the "
                "OAuth client's Authorized redirect URIs (setup Step 3e)."
            )
        if "code" not in q:
            raise SystemExit(
                "That URL has no ?code= in it. Copy the FULL address from the browser's "
                "address bar on the page that failed to load — the code is in the URL, "
                "not on the page."
            )
        return q["code"][0]
    if pasted.startswith("4/"):   # Google auth codes look like 4/0A...
        return pasted
    raise SystemExit(
        "That does not look like the redirect URL. Paste the whole thing from the "
        "address bar, starting with http://localhost:5179/?code="
    )


def exchange(pasted):
    cid = read_env("GOOGLE_CLIENT_ID", required=True)
    csecret = read_env("GOOGLE_CLIENT_SECRET", required=True)
    expected = (read_env("OAUTH_ACCOUNT", required=True) or "").strip().lower()
    code = extract_code(pasted)

    req = urllib.request.Request(
        "https://oauth2.googleapis.com/token",
        data=urllib.parse.urlencode({
            "code": code, "client_id": cid, "client_secret": csecret,
            "redirect_uri": REDIRECT_URI, "grant_type": "authorization_code",
        }).encode(), method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            tok = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if "invalid_grant" in body:
            raise SystemExit(
                "Google rejected the code (invalid_grant). These codes are single-use "
                "and expire within minutes — most likely it was already exchanged, or "
                "it sat too long. Just run --auth-url again and redo the sign-in."
            )
        raise SystemExit(f"Token exchange failed ({e.code}): {body}")

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

    save(GMAIL_REFRESH_TOKEN=refresh)
    print(f"OK — consented as {email}. Refresh token saved to .claude/settings.local.json\n"
          "NEXT: this is the LOCAL copy, used by download_invoices.py. The gateway needs "
          "its own — store it with liangzai_store_credential (setup Step 3j) or the "
          "summary email cannot send.")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--auth-url", action="store_true", help="Print the Google sign-in link")
    g.add_argument("--exchange", metavar="URL", help="The redirect URL he landed on")
    args = ap.parse_args()

    if args.auth_url:
        cid = read_env("GOOGLE_CLIENT_ID", required=True)
        expected = (read_env("OAUTH_ACCOUNT", required=True) or "").strip().lower()
        print(
            f"Sign in as {expected} and click Allow:\n\n{build_auth_url(cid, expected)}\n\n"
            f"You will land on a page that says the site can't be reached. THAT IS CORRECT.\n"
            f"Copy the whole address from the address bar (it starts with {REDIRECT_URI}/?code=)\n"
            f"and give it back to Claude.\n\n"
            f"NOTE: the OAuth client must list this exact Authorized redirect URI:\n"
            f"  {REDIRECT_URI}\n"
            f"Without it Google rejects the sign-in with 'redirect_uri_mismatch'.\n",
            flush=True,
        )
        return

    exchange(args.exchange)


if __name__ == "__main__":
    main()
