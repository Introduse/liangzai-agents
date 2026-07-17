---
name: cost-optimizer
description: >-
  Work out Liang Zai's real cost per bowl, per outlet, per month. Run weekly to record
  that week's Loyverse sales into the tracking Sheet; run monthly to tally those sales
  into bowls, pair each outlet's bowls with its reconciled supplier cost, and write
  cost-per-bowl. Use whenever the user asks about cost per bowl, margin, bowls sold,
  Loyverse sales, how much an outlet sold today or this week, or which outlet is getting
  more expensive.
area: Cost
use_for: "Weekly: record Loyverse sales per item per outlet per day. Monthly: tally bowls, pair with reconciled cost, write cost/bowl. Ad hoc: live per-outlet sales in SGD for today or a trailing window."
---

# Cost Optimizer

Cost per bowl is the number the owner does not have today and the one he will actually
look at. Everything here exists to make sure it is *right*, or absent.

Pass the plugin's `gateway_api_key`, plus the Google credentials from
`.claude/settings.local.json`, on every `liangzai_*` call — see `agents/liangzai.md` for
the exact argument names.

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
the owner immediately — that data is gone.

## What counts as a bowl

Loyverse has **no bowls-sold field**, so the definition is a rule we apply, not a question
we put to the owner. **A meal counts; anything that rides along with a meal does not** —
so noodle and rice dishes are bowls, while packaging charges, drinks, à la carte extras,
sides, staff meals and fee/discount lines are not. The `$0.30` packaging line is the
highest-volume item in the catalogue and counting it would roughly double the bowl count.
The full rule and the exact call live in **`/liangzai-setup` Step 6** — follow it there,
and don't re-litigate the classification with him.

This choice silently sets the headline number, which is why
`liangzai_compute_cost_per_bowl` refuses to run until `confirmed_by_owner` is true. Don't
work around that. Because `sales_daily` is item-level, changing the definition later
re-derives history correctly instead of corrupting it.

## Mode: monthly

Run after reconciliation, so the cost basis is settled.

**This mode is step 2 of the monthly close — it is never scheduled on its own.**
`liangzai_compute_cost_per_bowl` reads the `reconciliation` tab, so a separate schedule
could fire it before reconciliation had run and publish a cost per bowl against a stale or
empty basis. It looks entirely plausible when that happens, which is what makes it
dangerous. One task, in order: reconcile, then this. See `/liangzai-setup` Step 10.

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

### When `capture-sales` ran on a schedule

The weekly scheduled task runs `/supplier-invoice-manager capture` and then this. **That
task sends one `liangzai_send_run_report` covering both** — fold your sales-capture counts
into its `summary_lines`, and put any unreachable days into `needs_owner`, because those
days are gone for good and he needs to know today, not at month end. Don't send a second
email.

`monthly` needs no report of its own: the monthly close ends with `liangzai_send_summary`.

## Mode: daily sales (live snapshot, ad hoc)

Separate from everything above. When the owner asks *"how much did we sell today?"* — or this
week, or per outlet — that is a **revenue** question, not a cost-per-bowl one, and it has its
own tool. Nothing here writes to the Sheet or sends an email; it is just an answer to a
question he asked.

> Call **`liangzai_daily_sales`** (`days: 1` = today only, the default; `days: 7` = the
> trailing week; max 30, the Loyverse wall).

It reads Loyverse **live and writes nothing** — it does not touch `sales_daily`, and it is
not the weekly capture. Three things to hold onto when you report it:

- **It is money, not bowls.** `sales` is net revenue in SGD (refunds subtracted), summed per
  receipt — the figure the owner cross-checks against each till. It says nothing about cost or
  margin; don't blur it with cost-per-bowl. None of the cost-per-bowl reporting above applies.
- **Today is partial.** The current day runs to *now*, not to close, so today's total keeps
  climbing. Say so, and don't compare a half-day against yesterday's full day as if it were a
  drop.
- **`gst_charged` is false**, because the owner's Loyverse charges no GST — so the sales
  figure carries no tax to strip out. If it ever flips true, the numbers change meaning and
  you should flag it, not silently report a tax-inclusive total as revenue.

An outlet that shows **no receipts at all** for a day it should be trading is worth a line to
the owner — it usually means that till didn't sync, not that it sold nothing.

Report per outlet plus a total; lead with nothing in particular — he is reading the tills,
not hunting a problem.
