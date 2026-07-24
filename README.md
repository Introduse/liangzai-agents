# Liang Zai — agents

A **Claude plugin** for Liang Zai Prawn Noodle's back-office: capture supplier invoices and
Loyverse sales, reconcile each month's Statements of Account line-by-line, and track supplier
cost per bowl. The skills run inside the owner's own Claude Cowork project and drive the
private [liangzai-gateway](https://github.com/Introduse/liangzai-gateway) MCP server, which
owns the database and does all the Loyverse/Gmail work.

**The gateway holds every credential.** Google, the mailbox settings and the Loyverse token
all live server-side in Supabase Vault. This plugin sends exactly one thing: the gateway API
key. It used to send seven credentials on every call, because the gateway had nowhere to put
them; it does now.

Built by [Five Bucks Ventures](https://fivebucksventures.com).

> **Status (v0.4.0):** Plugin marketplace with four skills and the agent. Client-neutral.
> Requires the gateway deployed and registered as a Cowork custom connector (set the URL in
> `plugins/liangzai/.mcp.json`).

**Nothing is ever paid automatically.** The agents log, reconcile, and calculate — there is
no `Approved` and no `Paid` status the agent can set. Every flagged item and every payment
goes through the owner.

---

## Architecture

```
liangzai-agents (THIS REPO — the plugin)         liangzai-gateway (remote MCP, Vercel)
  skills drive the workflow; Claude       ──MCP──▶  liangzai_* tools:
  extracts invoice PDFs and calls                     reconcile · capture_sales ·
  the gateway                                         append_invoice_log · compute_cost ·
  download_invoices.py runs LOCALLY                   send_summary · pending_documents · …
  (the Gmail connector can't fetch                    → Supabase Postgres (source of truth)
   attachment bytes)
```

Only two scripts run locally, on the owner's machine: `download_invoices.py` (Claude reads
the downloaded PDFs to extract line items) and `google_oauth.py` (one-time consent to mint
the Google refresh token). Everything else — reconciliation, cost math, every database
write, all Loyverse and Gmail calls — happens in the gateway.

Those calls carry no credentials. If a tool's schema still shows `spreadsheet_id` or
`sheets_refresh_token`, the connector has cached an old tool list: reconnect it rather than
filling the fields in.

## The skills

| Skill | Does |
|---|---|
| `liangzai-setup` | First-run onboarding: connect the gateway, mint the Google token, confirm the Loyverse mapping and the bowl definition, and embed the agent into the workspace `CLAUDE.md` |
| `supplier-invoice-manager` | **Weekly** — download + extract invoices → `liangzai_append_invoice_log`. **Monthly** — extract statements, `liangzai_run_reconciliation`, `liangzai_send_summary` |
| `cost-optimizer` | **Weekly** — `liangzai_capture_sales`. **Monthly** — `liangzai_compute_cost_per_bowl`. **Ad hoc** — `liangzai_daily_sales` for live per-outlet sales in SGD |
| `plugin-update` | Idempotent catch-up after an upgrade — detects gaps (connector, token, tabs, outlet map, bowl definition, CLAUDE.md embed) and fills only what's missing |

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
  └── scripts/                      # local-only: download_invoices.py, google_oauth.py
```

## Install

1. Add this repo as a plugin marketplace in Claude, then install the **liangzai** plugin.
2. Paste the gateway API key (`liangzai_live_…`) when prompted for `gateway_api_key`.
3. Run **`/liangzai-setup`** and follow it end to end — it walks through the gateway
   connector, Google access, the bowl definition, and the workspace `CLAUDE.md`.

The 30-day Loyverse note, in one line: the free plan refuses receipts older than 31 days, so
sales accumulate forward — the weekly run records what it can see, the monthly run tallies it,
and every read stays inside the window.

## The gateway

All the reconciliation and cost logic lives in the private
[liangzai-gateway](https://github.com/Introduse/liangzai-gateway) — a Next.js + `mcp-handler`
MCP server on Vercel. Deploy it, register `https://<app>.vercel.app/api/mcp` as a Cowork
custom connector, and put that URL in `plugins/liangzai/.mcp.json`.

It holds its own credentials — Supabase Vault first, its Vercel env vars as the bootstrap
fallback. Nothing this plugin does supplies them. See the gateway's README for the list.
