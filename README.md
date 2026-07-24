# Liang Zai — agents

A **Claude plugin** for Liang Zai Kitchen's back-office: capture supplier invoices and
Loyverse sales, reconcile each month's Statements of Account line-by-line, and track supplier
cost per bowl. The skills run inside the owner's own Claude Cowork project and drive the
private [liangzai-gateway](https://github.com/Introduse/liangzai-gateway) MCP server, which
owns the database and does all the Loyverse/Gmail work.

**The gateway holds every credential.** Google, the mailbox settings and the Loyverse token
all live server-side in Supabase Vault. This plugin sends exactly one thing: the gateway API
key. It used to send seven credentials on every call, because the gateway had nowhere to put
them; it does now — and `/liangzai-setup` is what puts them there.

The OAuth client id, secret and mailbox address are also kept locally, in
`.claude/settings.local.json` — not because anything here uses them at run time, but
because minting a Google refresh token needs a browser and a human clicking Allow, and
that cannot happen server-side. The token itself is never written to disk: the script
prints it and setup puts it in the Vault.

Built by [Five Bucks Ventures](https://fivebucksventures.com).

> **Status (v0.15.0):** Plugin marketplace with four skills and the agent. Client-neutral.
> Requires the gateway deployed and registered as a Cowork custom connector (set the URL in
> `plugins/liangzai/.mcp.json`), and `/liangzai-setup` run through to the end — the gateway
> can neither read the supplier mailbox nor send an email until Step 3j has put the
> credentials in its Vault.

**Nothing is ever paid automatically.** The agents log, reconcile, and calculate — there is
no `Approved` and no `Paid` status the agent can set. Every flagged item and every payment
goes through the owner.

---

## Architecture

```
liangzai-agents (THIS REPO — the plugin)         liangzai-gateway (remote MCP, Vercel)
  skills drive the workflow; Claude       ──MCP──▶  poll_mailbox · pending_documents ·
  drains the ingestion queue, reads                 document_content · mark_document ·
  each invoice PDF and calls the                    append_invoice_log · reconcile ·
  gateway                                           capture_sales · compute_cost · …
                                                      │
  google_oauth.py runs LOCALLY, once                  ├──▶ Supabase Postgres + a private
  (Google will only hand a refresh                    │    Storage bucket (source of truth)
   token to a browser)                                └──▶ the supplier mailbox, polled
                                                           daily on cron and on demand
```

**The gateway fetches the mail.** It polls the supplier mailbox server-side, stores each
attachment in a private bucket, and hands the skill a 15-minute signed URL per document.
The PDF still lands on the owner's machine — Claude has to read it to extract line items —
but nothing here talks to Gmail. One script runs locally, once: `google_oauth.py`, the
one-time consent that mints the refresh token the gateway then owns. Everything else —
reconciliation, cost math, every database write, all Loyverse and Gmail calls — is the
gateway's.

Those calls carry no credentials. If a `liangzai_*` call comes back `unknown tool`, or a
tool's schema still shows `spreadsheet_id` or `sheets_refresh_token`, the connector has
cached an old tool list — reconnect it rather than filling fields in or filing a gateway bug.

## The skills

| Skill | Does |
|---|---|
| `liangzai-setup` | First-run onboarding: connect the gateway, mint the Google token and store it in the gateway's Vault, confirm the Loyverse mapping and the bowl definition, and embed the agent into the workspace `CLAUDE.md` |
| `supplier-invoice-manager` | **Weekly** — `liangzai_poll_mailbox` → drain `liangzai_pending_documents` → extract invoices → `liangzai_append_invoice_log`; anything that is not a money document is closed with `liangzai_mark_document`. **Monthly** — extract statements, `liangzai_run_reconciliation`, `liangzai_send_summary` |
| `cost-optimizer` | **Weekly** — `liangzai_capture_sales`. **Monthly** — `liangzai_compute_cost_per_bowl`. **Ad hoc** — `liangzai_daily_sales` for live per-outlet sales in SGD |
| `plugin-update` | Idempotent catch-up after an upgrade — detects gaps (connector, Vault credentials, whether the mailbox poller is running, bowl definition, scheduled tasks, CLAUDE.md embed) and fills only what's missing |

`agents/liangzai.md` defines the agent identity; `liangzai-setup` embeds it into the
workspace `CLAUDE.md` so every session — including scheduled runs — auto-loads it.

## What the guarantees are

- **Any variance flags.** `Matched` requires the variance to be exactly zero (compared as
  integer cents, so float noise never manufactures a phantom variance). A missing statement
  is `SOA_MISSING`, never agreement.
- **Never guess.** An unresolved supplier or an ambiguous outlet becomes `needs_review` — a
  mis-attributed outlet corrupts that outlet's cost-per-bowl while the totals still reconcile.
- **The owner owns approval.** The agent sets a default payment status once and preserves his
  choice on every re-run; it can never set `Paid`.
- **Cost per bowl is honest.** It covers only the tracked (automated) suppliers, names them
  in `tracked_suppliers`, exposes partial-month coverage in `days_covered`, and is withheld
  entirely until the bowl definition is confirmed.

## Structure

```
.claude-plugin/marketplace.json     # the marketplace manifest
plugins/liangzai/
  ├── .claude-plugin/plugin.json    # userConfig.gateway_api_key (sensitive)
  ├── .mcp.json                     # the gateway connector URL
  ├── agents/liangzai.md            # agent identity (embedded into CLAUDE.md by setup)
  ├── skills/{liangzai-setup, supplier-invoice-manager, cost-optimizer, plugin-update}/
  └── scripts/
      ├── oauth/google_oauth.py     # the only local entry point: one-time Google consent
      └── common/env.py             # reads .claude/settings.local.json, for the above
```

## Install

1. Add this repo as a plugin marketplace in Claude, then install the **liangzai** plugin.
2. Paste the gateway API key (`liangzai_live_…`) when prompted for `gateway_api_key`.
3. Run **`/liangzai-setup`** and follow it end to end — it walks through the gateway
   connector, Google access, storing the credentials in the gateway's Vault, the bowl
   definition, and the workspace `CLAUDE.md`.

The 30-day Loyverse note, in one line: the free plan refuses receipts older than 31 days, so
sales accumulate forward — the weekly run records what it can see, the monthly run tallies it,
and every read stays inside the window.

## The gateway

All the reconciliation and cost logic lives in the private
[liangzai-gateway](https://github.com/Introduse/liangzai-gateway) — a Next.js + `mcp-handler`
MCP server on Vercel. Deploy it, register `https://<app>.vercel.app/api/mcp` as a Cowork
custom connector, and put that URL in `plugins/liangzai/.mcp.json`.

It holds its own credentials — Supabase Vault first, its Vercel env vars as the bootstrap
fallback. `/liangzai-setup` Step 3j writes the Google and mailer ones into the Vault via
`liangzai_store_credential`; `LOYVERSE_ACCESS_TOKEN` is seeded at deploy time and is not
the owner's to supply. No credential travels on a tool call. See the gateway's README for
the full list.
