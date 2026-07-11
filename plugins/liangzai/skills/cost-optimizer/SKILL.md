---
name: cost-optimizer
description: >-
  Work out Liang Zai's real cost per bowl, per outlet, per month. Run weekly to record
  that week's Loyverse sales into the tracking Sheet; run monthly to tally those sales
  into bowls, pair each outlet's bowls with its reconciled supplier cost, and write
  cost-per-bowl. Use whenever the user asks about cost per bowl, margin, bowls sold,
  Loyverse sales, or which outlet is getting more expensive.
area: Cost
use_for: "Weekly: record Loyverse sales per item per outlet per day. Monthly: tally bowls, pair with reconciled cost, write cost/bowl."
---

# Cost Optimizer

Cost per bowl is the number the owner does not have today and the one he will actually
look at. Everything here exists to make sure it is *right*, or absent. Pass the
plugin's `gateway_api_key` on every `liangzai_*` call.

## It is not "cost per bowl", and must never be labelled as one

The figure covers **only the ~70% of suppliers in the automated flow.** The small
suppliers the owner keeps manual are excluded — by his own choice. It contains no rent, no
labour, no utilities. So it is **supplier cost per bowl, for tracked suppliers** —
`每碗供应商成本(已记录)`. The Sheet, the email, and every report say so.

**Never gross it up.** The 30% is a share of *suppliers*, not of *spend*, and they are
the small ones. Dividing by 0.7 would invent an authoritative-looking number that is
probably wrong by more than the error it tried to fix.

The `tracked_suppliers` column names exactly which suppliers are in the total. If that
set changes between months, the month-on-month move is **not** a cost trend — the
gateway sets the delta to `—` and says why.

## The 30-day wall — read this before changing anything

The owner's Loyverse plan returns **`HTTP 402` for any receipt older than 31 days.** So
this agent **never looks back**: the weekly run records sales as they happen; the
monthly run only tallies what is already stored. Three consequences, all load-bearing:

1. **`sales_daily` stores net quantity per item — not a bowl count.** Loyverse can never
   be re-read past 30 days, so a stored bowl count would permanently freeze today's bowl
   definition. Item quantities keep the definition a revisable *view* over durable data.
2. **A weekly run missed for over 30 days loses that period permanently.** Each run
   backfills from the last recorded day and says so loudly when it can't reach back far
   enough.
3. **June 2026 cost-per-bowl does not exist** and never will. Do not fabricate it.

## Mode: capture-sales (weekly, alongside the invoice capture)

> Call **`liangzai_capture_sales`** (omit `days` to resume from the last recorded day;
> add `dry_run: true` to preview).

The gateway buckets by **Singapore date**, not UTC, and is idempotent on
`{outlet}|{date}|{item_id}|{variant}`. If it warns that days are unreachable, tell
The owner immediately — that data is gone.

## What counts as a bowl

Loyverse has **no bowls-sold field.** The synthesis silently sets the headline number,
so `liangzai_compute_cost_per_bowl` refuses to run until the bowl definition is
confirmed. Do not work around that. To (re)generate the checklist and record his answer,
use `liangzai_bowl_checklist` and `liangzai_set_bowl_definition` — see
`/liangzai-setup` Step 6. Because `sales_daily` is item-level, changing the definition
later re-derives history correctly instead of corrupting it.

## Mode: monthly

Run after reconciliation, so the cost basis is settled.

> Call **`liangzai_compute_cost_per_bowl`** with `{ month: "2026-07" }` (add `dry_run:
> true` to preview).

This reads `sales_daily` and `reconciliation`. **It does not call Loyverse.** Two honesty
rules it enforces:

- **`days_covered`** is written on every row. Eighteen days of sales divided into a full
  month of costs understates cost-per-bowl by a third and looks entirely plausible. If
  coverage is partial, the row says so and the email repeats it.
- **A flagged reconciliation means the cost basis is not final.** The row is still
  written, but `cost_basis_note` names the unresolved suppliers.

If it returns a `bowl_definition_unconfirmed` error, the definition has not been
confirmed yet — run `/liangzai-setup` Step 6, don't work around it.

## Reporting back

Per outlet: bowls, reconciled cost, cost per bowl, and the move against last month. Lead
with any outlet whose cost per bowl rose. Say plainly when a number is withheld and why
— unconfirmed definition, partial coverage, or unresolved variance. Never print a number
you would have to caveat away in the next sentence.
