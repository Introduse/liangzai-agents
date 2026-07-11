#!/usr/bin/env python3
"""Exchange a stored refresh token for a short-lived Google access token.

Stdlib only. Mirrors the pattern proven in the Five Agents youtube_today.py.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
from env import read_env  # noqa: E402

TOKEN_URL = "https://oauth2.googleapis.com/token"
_cache = {}  # refresh_token -> (access_token, expires_at)


def access_token(refresh_key="GMAIL_REFRESH_TOKEN"):
    """Return a valid access token for the given refresh-token env var."""
    rt = read_env(refresh_key, required=True)
    tok, exp = _cache.get(rt, (None, 0))
    if tok and time.time() < exp - 60:
        return tok

    req = urllib.request.Request(TOKEN_URL, method="POST", data=urllib.parse.urlencode({
        "client_id": read_env("GOOGLE_CLIENT_ID", required=True),
        "client_secret": read_env("GOOGLE_CLIENT_SECRET", required=True),
        "refresh_token": rt,
        "grant_type": "refresh_token",
    }).encode())
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    _cache[rt] = (d["access_token"], time.time() + d.get("expires_in", 3600))
    return d["access_token"]


def api(url, refresh_key, method="GET", body=None, raw=False):
    """Call a Google API with a Bearer token. Returns parsed JSON, or bytes if raw."""
    headers = {"Authorization": f"Bearer {access_token(refresh_key)}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, headers=headers, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read() if raw else json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"{method} {url.split('?')[0]} -> HTTP {e.code}\n{detail}")
