# Liang Zai — agents (Claude plugin marketplace)

Back-office agents for [Liang Zai Prawn Noodle](https://liangzai.example), built by
[Five Bucks Ventures](https://fivebucksventures.com). They run inside the owner's own Claude
Cowork project and keep his supplier costs honest.

**Nothing is ever paid automatically.** The agents log, reconcile, and calculate. Every
flagged item and every payment goes through the owner — there is no `Approved` and no `Paid`
status the agent can set.

## What this repo is

This is the **plugin marketplace**. The agents' logic — the reconciliation engine, the
GST-aware capture guards, the cost-per-bowl math, and every Google/Loyverse/Sheets call —
lives server-side in the private **liangzai-gateway** (a remote MCP server), where the
credentials are held and never leave. The skills here call its `liangzai_*` tools.

```
liangzai-agents (this repo — the plugin)        liangzai-gateway (remote MCP, Vercel)
  skills drive the workflow, extract invoice ──▶  liangzai_* tools:
  PDFs, and call the gateway                        reconcile · capture_sales ·
  download_invoices.py runs LOCALLY                 append_invoice_log · compute_cost ·
  (the Gmail connector can't fetch                  send_summary · init_sheet · …
   attachment bytes)                                → Google Sheets (source of truth)
```

Only two scripts run locally, on the owner's machine: `download_invoices.py` (the Gmail
connector cannot fetch attachment bytes, and Claude reads the PDFs to extract line items)
and `google_oauth.py` (one-time consent to mint the Google refresh token).

## Structure

```
.claude-plugin/marketplace.json     # the marketplace manifest
plugins/liangzai/
  ├── .claude-plugin/plugin.json    # userConfig.gateway_api_key
  ├── .mcp.json                     # the gateway connector URL
  ├── agents/liangzai.md
  ├── skills/{liangzai-setup, supplier-invoice-manager, cost-optimizer}/
  └── scripts/                      # local-only: download_invoices.py, google_oauth.py
```

## The two agents

**Supplier Invoice Manager** — weekly, captures the shared supplier inbox into the tracking
Sheet by outlet; monthly, reconciles each Statement of Account line-by-line. No tolerance: a
row is `Matched` only when the variance is exactly zero.

**Cost Optimizer** — weekly, records Loyverse sales per item per outlet per day; monthly,
tallies bowls and pairs each outlet's bowls with its reconciled supplier cost. Loyverse's
free plan refuses receipts older than 31 days, so sales accumulate forward — every read stays
inside the 30-day window, permanently, on the free plan.

## History

The full Python implementation this system grew from is preserved at git tag
`python-source-final`. The TypeScript gateway was proven bit-exact against it by a
differential harness (340k+ cases) before the Python was retired.
