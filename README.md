# Liang Zai — agents

A **Claude plugin** for Liang Zai Prawn Noodle's back-office: capture supplier invoices and
Loyverse sales, reconcile each month's Statements of Account line-by-line, and track supplier
cost per bowl. The skills run inside the owner's own Claude Cowork project and drive the
private [liangzai-gateway](https://github.com/Introduse/liangzai-gateway) MCP server, which
does all the Sheet/Loyverse/Gmail work.

The credentials are split between the two. The gateway holds the Loyverse token. The Google
and mailer credentials live *here*, in the project's `.claude/settings.local.json`, and
travel to the gateway as arguments on every call.

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
  download_invoices.py runs LOCALLY                   send_summary · init_sheet · …
  (the Gmail connector can't fetch                    → Google Sheets (source of truth)
   attachment bytes)
```

Only two scripts run locally, on the owner's machine: `download_invoices.py` (Claude reads
the downloaded PDFs to extract line items) and `google_oauth.py` (one-time consent to mint
the Google refresh token). Everything else — reconciliation, cost math, all Sheet/Loyverse/
Gmail calls — happens in the gateway.

Those gateway calls carry the Google and mailer credentials with them, read out of
`.claude/settings.local.json` on each request. `agents/liangzai.md` lists which argument
maps to which key, and which tools need them.

## The skills

| Skill | Does |
|---|---|
| `liangzai-setup` | First-run onboarding: connect the gateway, mint the local Google token, create the Sheet, confirm the bowl definition, and embed the agent into the workspace `CLAUDE.md` |
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
   connector, Google access, the Sheet, the bowl definition, and the workspace `CLAUDE.md`.

The 30-day Loyverse note, in one line: the free plan refuses receipts older than 31 days, so
sales accumulate forward — the weekly run records what it can see, the monthly run tallies it,
and every read stays inside the window.

## The gateway

All the reconciliation and cost logic lives in the private
[liangzai-gateway](https://github.com/Introduse/liangzai-gateway) — a Next.js + `mcp-handler`
MCP server on Vercel. Deploy it, register `https://<app>.vercel.app/api/mcp` as a Cowork
custom connector, and put that URL in `plugins/liangzai/.mcp.json`.

It needs two env vars of its own: `GATEWAY_API_KEY_SHA256` and `LOYVERSE_ACCESS_TOKEN`. The
Google, mailer, and `SPREADSHEET_ID` vars can also be set there, but only as a fallback for
calls that omit them — this plugin sends its own (including `spreadsheet_id`, recorded in
`.claude/settings.local.json` at setup) on every call.
