#!/usr/bin/env python3
"""Weekly: download every attachment in the supplier inbox to cache/, and index it.

This script does I/O only. It never parses an invoice — extraction is the agent's
job, because supplier layouts vary and regex dies on the first one that changes.
The agent reads each cached PDF/photo (Claude renders both natively) and calls
the liangzai_append_invoice_log gateway tool with structured rows.

The Gmail MCP connector cannot download attachment bytes; that is why this exists.
Scope is gmail.readonly, so we never label, move, or delete the owner's mail — which
also means we cannot use labels to track what we've processed. Idempotency comes
from the deterministic source_ref instead.

Usage:
    python3 scripts/capture/download_invoices.py --days 7
    python3 scripts/capture/download_invoices.py --since 2026-06-01 --until 2026-07-01
"""
import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from env import read_env  # noqa: E402
import gmail  # noqa: E402

CACHE = os.path.join(HERE, "..", "..", "cache")
SGT = dt.timezone(dt.timedelta(hours=8))

# Attachments we can actually read. Anything else is indexed but marked, never
# silently dropped — a supplier who sends a .xlsx must still surface to a human.
READABLE = (".pdf", ".jpg", ".jpeg", ".png", ".webp", ".heic", ".gif")


def safe_name(s):
    return "".join(c if c.isalnum() or c in "._-" else "_" for c in s)[:120]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--since", help="YYYY-MM-DD (overrides --days)")
    ap.add_argument("--until", help="YYYY-MM-DD")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mailbox = read_env("SUPPLIER_MAILBOX", required=True)

    if args.since:
        since, until = args.since, args.until
    else:
        today = dt.datetime.now(SGT).date()
        since = (today - dt.timedelta(days=args.days)).isoformat()
        until = None

    # Gmail's after:/before: take YYYY/MM/DD.
    q = f"has:attachment after:{since.replace('-', '/')}"
    if until:
        q += f" before:{until.replace('-', '/')}"

    print(f"mailbox {mailbox}\nquery   {q}\n")
    msg_ids = gmail.search(q)
    print(f"{len(msg_ids)} message(s) with attachments\n")

    manifest = []
    for mid in msg_ids:
        msg = gmail.get_message(mid)
        h = gmail.headers(msg)
        sender = h.get("from", "")
        subject = h.get("subject", "")
        date = h.get("date", "")

        for att in gmail.attachments(msg):
            ext = os.path.splitext(att["filename"])[1].lower()
            entry = {
                "gmail_msg_id": mid,
                "attachment_id": att["attachment_id"],
                "filename": att["filename"],
                "mime_type": att["mime_type"],
                "size": att["size"],
                "from": sender,
                "subject": subject,
                "date_header": date,
                "readable": ext in READABLE,
                "cache_path": None,
            }
            if not entry["readable"]:
                # Indexed, not dropped. The agent logs it as needs_review.
                entry["note"] = f"unreadable attachment type {ext!r} — needs a human"
            elif not args.dry_run:
                d = os.path.join(CACHE, mid)
                os.makedirs(d, exist_ok=True)
                p = os.path.join(d, safe_name(att["filename"]))
                if not os.path.exists(p):
                    with open(p, "wb") as f:
                        f.write(gmail.download(mid, att["attachment_id"]))
                entry["cache_path"] = os.path.relpath(p, os.path.join(HERE, "..", ".."))
            manifest.append(entry)

    if args.dry_run:
        for e in manifest:
            flag = "" if e["readable"] else "  [UNREADABLE]"
            print(f"  {e['filename']}  <- {e['from'][:40]}{flag}")
        print(f"\nDRY RUN — {len(manifest)} attachment(s) would be downloaded.")
        return

    os.makedirs(CACHE, exist_ok=True)
    mp = os.path.join(CACHE, "manifest.json")
    with open(mp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": dt.datetime.now(SGT).isoformat(timespec="seconds"),
                   "query": q, "attachments": manifest}, f, ensure_ascii=False, indent=2)

    ok = sum(1 for e in manifest if e["readable"])
    print(f"{ok} readable attachment(s) cached, {len(manifest) - ok} unreadable.")
    print(f"manifest -> {os.path.relpath(mp, os.path.join(HERE, '..', '..'))}")
    print("\nNext: the agent reads each cache_path and calls the liangzai_append_invoice_log gateway tool.")


if __name__ == "__main__":
    main()
