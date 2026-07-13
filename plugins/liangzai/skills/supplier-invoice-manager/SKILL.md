---
name: supplier-invoice-manager
description: >-
  Log Liang Zai's supplier invoices and reconcile them against each month's
  Statements of Account. Run weekly to capture that week's invoices from the shared
  supplier inbox into the tracking Sheet, split by outlet; run monthly (after the 4th,
  when SOAs land) to match each supplier's statement line-by-line against what was
  logged and flag any variance. Use whenever the user says capture invoices, log
  invoices, reconcile, check the statement, month-end close, or asks why a supplier
  total does not match.
area: Invoicing
use_for: "Weekly: read supplier inbox, extract invoice line items, log to Sheet by outlet. Monthly: reconcile SOAs, flag any variance, email the owner."
---

# Supplier Invoice Manager

Two modes on two clocks: **capture** weekly, **reconcile** monthly.

**The contract, which nothing may relax:** the agent logs, reconciles, and flags. It
never approves and it never pays. There is no `Approved` and no `Paid` status anywhere
in this system. Every flagged item and every payment goes through the owner.

Pass the plugin's `gateway_api_key`, plus the Google credentials from
`.claude/settings.local.json`, on every `liangzai_*` call — see `agents/liangzai.md` for
the exact argument names.

---

## Mode: capture (weekly, Sunday morning)

### 1. Download — locally

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture/download_invoices.py --days 7
```

This runs on the owner's machine (the Gmail connector cannot fetch attachment bytes). It
does I/O only: writes attachments to `cache/<msg_id>/` and an index at
`cache/manifest.json`. It never parses.

### 2. Extract — this is your job, not a tool's

Read each `cache_path` from the manifest. You render PDFs and photos natively. Extract
to exactly this shape, one object per invoice:

```json
{"invoices": [{
  "gmail_msg_id": "...", "attachment_id": "...",
  "invoice_date": "2026-06-17",
  "supplier_raw": "<exactly as printed on the invoice>",
  "sender_email": "<the From: address>",
  "delivery_text": "<the delivery/deliver-to line, verbatim>",
  "invoice_no": "KI-2606007",
  "stated_total": 741.00,
  "gst_inclusive": true,
  "lines": [{"item": "Pork Bones (kg)", "qty": 58, "unit": "kg",
             "unit_price": 4.20, "amount": 243.60}]
}]}
```

Rules that matter more than speed:

- **Copy `supplier_raw` and `delivery_text` verbatim.** Do not tidy them — the
  canonicaliser needs the raw string, and a "helpful" correction destroys the only
  evidence of what the supplier wrote.
- **Never invent a line.** If a column is unreadable, leave the field empty.
- **`stated_total` is the invoice's own printed total** — the control figure. If the
  invoice prints none, leave it null; the gateway marks it `needs_review` because
  completeness can't be verified.
- Some suppliers print no per-line amount. Give `qty` and `unit_price`, leave `amount`
  empty; do not multiply it out.
- An attachment that is not an invoice gets an entry with an empty `lines` array. It
  becomes `needs_review`, not silence.

### 3. Append

> Call **`liangzai_append_invoice_log`** with `{ invoices: [...] }` (add `dry_run:
> true` first to preview).

The gateway checks each invoice's line sum against its stated total; a mismatch writes
the lines anyway with `needs_review` and the arithmetic in the reason. Outlets are
canonicalised — an unresolved one becomes `needs_review` with `UNASSIGNED`, **never a
guess**. Re-running the same week is safe: `source_ref` makes it idempotent.

**Suppliers register themselves.** A supplier you have never seen is recorded automatically,
keyed on the sender's email domain — no list to maintain, nothing to ask him. The response
carries two fields:

- **`suppliers_registered`** — new suppliers, now known. **Tell him, don't ask him:**
  *"12 invoices logged. 3 new suppliers registered: EcoGreen Packaging, … — nothing needed
  from you."* This is information, not a decision.
- **`suppliers_ambiguous`** — the one case the gateway refuses to decide. A name it already
  knows has arrived from an address it doesn't. That is either the supplier's billing agent
  or a *different company with a similar name*, and guessing wrong corrupts reconciliation
  while every total still looks reasonable. Put the question to him plainly — *"is this the
  same company?"* — and if he says yes, call **`liangzai_merge_suppliers`**.

Why the machine registers but never merges: **creating** a supplier is safe (the worst case
is a duplicate you merge later), while **merging** two is not. That asymmetry is the whole
design.

### 4. Capture sales too

The weekly run must also record the week's Loyverse sales — see `/cost-optimizer`.
Loyverse refuses receipts older than 31 days, so a skipped run over a month loses that
period permanently.

---

## Mode: reconcile (monthly, from the 6th)

### 1. Download and extract the statements

Same local download step, then extract each SOA:

```json
{"soas": [{
  "gmail_msg_id": "...", "attachment_id": "...",
  "supplier_raw": "ACME MEAT SUPPLY", "sender_email": "acct@acme-supplier.example",
  "period": "2026-06", "stated_total": 4103.60,
  "rows": [{"invoice_no": "KI-2606007", "date": "2026-06-17",
            "delivery_text": "靓仔大虾面 (Outlet A)", "amount": 741.00}]
}]}
```

> Call **`liangzai_append_soa_entries`** with `{ soas: [...] }`.

### 2. Reconcile

> Call **`liangzai_run_reconciliation`** with `{ month: "2026-06" }`.

What the arithmetic guarantees:

- **No tolerance.** `Matched` requires the variance to be exactly zero. One cent is a
  flag. Totals are compared as integer cents, so float noise never manufactures a
  phantom variance.
- **A missing SOA is never agreement** — it is `SOA_MISSING`. Re-run when it lands;
  the row upserts.
- **Equal totals are not enough.** Differing invoice numbers on the two sides flag the
  row even when the money agrees.

**Check `merge_suggestions` before you explain anything.** If it is non-empty, one company
is billing from two addresses — it invoices as one supplier and sends statements as another
— so it registered as two, and **both halves read as unmatched**. That looks like a supplier
problem and is actually ours. Say so first, because it explains rows that otherwise look
inexplicable:

> *EcoGreen Packaging* has invoices but no statement, and *Ecogreen Pkg Services* has a
> statement but no invoices. Are these the same company?

If he says yes → **`liangzai_merge_suppliers`** → re-run reconciliation. The rows upsert, so
they correct in place; nothing is re-entered. If he says no, leave them apart — they really
are two suppliers, and the `SOA_MISSING` is real.

Month one will be noisy — rounding, GST inclusivity, partial deliveries. That is the
system working. The owner is the filter.

### 3. Send the summary

> Call **`liangzai_send_summary`** with `{ month: "2026-06", preview: true }` and show
> the owner the result first. Then call it again with `preview: false` to send.

Flagged and needs-review rows lead; matched follow. The footer states, in both
languages, that nothing has been approved or paid. The gateway refuses any recipient
outside `SUMMARY_RECIPIENTS` — the agent must never write to a supplier.

### The button does not approve anything

It deep-links to the `reconciliation` tab. The owner changes the status himself, from a
dropdown: `审核中 Under Review` → `待付款 Ready for Payment`. Do not replace this with a
one-click approval link — mail scanners fetch URLs before a human clicks, and a scanner
would silently mark rows ready that the owner never opened.

### The owner owns the payment-status column

The gateway writes a default only when a row is created (`Ready for Payment` for a
clean match, `Under Review` otherwise) and **preserves his choice** on every later run.
The one exception: if a late SOA changes the figures under a row he already approved,
it resets to `Under Review` and says so. The agent can never set `已付款 Paid` — only
the owner can, after paying his bank.

---

## Reporting back

Counts, not row dumps: how many invoices logged, how many need review and why, how many
suppliers matched, the net variance, anything still awaiting an SOA. Name the flagged
supplier and outlet. If nothing needs him, say so plainly.

### When this ran on a schedule, email him — always

If the run was started by a Cowork scheduled task rather than by the owner sitting there:

> **capture** → call **`liangzai_send_run_report`** with `job: "weekly_capture"`, the same
> counts you'd have said out loud in `summary_lines`, and anything needing a human in
> `needs_owner` (unreadable attachments, unmatched outlets). Set `status: "attention"` if
> `needs_owner` is non-empty, `"ok"` if not, `"failed"` if the run broke.
>
> **reconcile** → `liangzai_send_summary` already emails him. Do **not** also send a run
> report; that would be two emails for one job.

**Send it even when there is nothing to report.** A week with no invoices and a week where
the job never ran look identical to him — the email is the only thing that tells them
apart, and with Loyverse's 30-day limit a silently-dead capture costs real money. A quiet
success is a signal, not noise.
