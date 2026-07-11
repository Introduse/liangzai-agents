#!/usr/bin/env python3
"""Gmail read + attachment download for the shared supplier mailbox.

The Gmail MCP connector cannot download attachment bytes — that is the entire
reason this module exists. Scope is gmail.readonly: we never label, move, or
delete the owner's mail.

Stdlib only.
"""
import base64
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(__file__))
from google_auth import api  # noqa: E402

BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
RK = "GMAIL_REFRESH_TOKEN"


def search(query, max_results=500):
    """Return message ids matching a Gmail query, following pagination."""
    ids, token = [], None
    while len(ids) < max_results:
        p = {"q": query, "maxResults": min(500, max_results - len(ids))}
        if token:
            p["pageToken"] = token
        d = api(f"{BASE}/messages?" + urllib.parse.urlencode(p), RK)
        ids.extend(m["id"] for m in d.get("messages", []))
        token = d.get("nextPageToken")
        if not token:
            break
    return ids


def get_message(msg_id):
    return api(f"{BASE}/messages/{msg_id}?format=full", RK)


def headers(msg):
    return {h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])}


def _walk(part):
    yield part
    for p in part.get("parts", []) or []:
        yield from _walk(p)


def attachments(msg):
    """[{filename, mime_type, attachment_id, size}] for every attachment part."""
    out = []
    for p in _walk(msg.get("payload", {})):
        body = p.get("body", {})
        if p.get("filename") and body.get("attachmentId"):
            out.append({
                "filename": p["filename"],
                "mime_type": p.get("mimeType", ""),
                "attachment_id": body["attachmentId"],
                "size": body.get("size", 0),
            })
    return out


def download(msg_id, attachment_id):
    """Return the attachment's raw bytes."""
    d = api(f"{BASE}/messages/{msg_id}/attachments/{attachment_id}", RK)
    return base64.urlsafe_b64decode(d["data"])
