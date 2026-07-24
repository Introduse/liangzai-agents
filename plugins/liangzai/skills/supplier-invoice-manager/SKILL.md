---
name: supplier-invoice-manager
description: >-
  Log Liang Zai's supplier invoices and reconcile them against each month's
  Statements of Account. Run weekly to classify that week's mailbox attachments and log
  the INVOICES, split by outlet — statements are left for month
  end. Run monthly (after the 4th, when SOAs land) to log the statements, catch any
  straggler invoice, and match each supplier's statement line-by-line against what was
  logged. Use whenever the user says capture invoices, log invoices, reconcile, check the
  statement, month-end close, or asks why a supplier total does not match.
area: Invoicing
use_for: "Weekly: classify mailbox attachments, record INVOICES by outlet, defer statements. Monthly: log the statements + any straggler invoice, reconcile, flag variance, email the owner. Every append is deduped."
---

# Supplier Invoice Manager

Two modes on two clocks. **Capture** weekly: classify the mailbox, log the invoices, leave
the statements. **Reconcile** monthly: log the statements *and* any invoice the weekly run
missed, then match them line by line.

Both modes write. Neither may write the same thing twice — see **The dedupe**, and do not
skip it.

**The contract, which nothing may relax:** the agent logs, reconciles, and flags. It
never approves and it never pays. There is no `Approved` and no `Paid` status anywhere
in this system. Every flagged item and every payment goes through the owner.

Pass the plugin's `gateway_api_key`, plus the Google credentials from
`.claude/settings.local.json`, on every `liangzai_*` call — see `agents/liangzai.md` for
the exact argument names.

---

## Classify before you write — this is where the last run went wrong

The download fetches **every attachment** in the mailbox. It does not know an invoice from
a statement, and neither tab can tell. **You** must, before a single row is written.

The first live run misfiled a supplier's Statement of Account into `invoice_log`, and the
owner had to unpick it by hand. It is not merely untidy: **reconciliation does not filter on
status**, so a junk row is reconciled anyway — grouped under a supplier and outlet no
statement line can ever match — and manufactures a variance that is not real.

| It is a **STATEMENT** when | It is an **INVOICE** when |
|---|---|
| It lists **several invoice references**, each with its own number, date and amount | It has **item-level lines** — qty, unit, unit price — under **one** invoice number |
| Titled *Statement of Account*, *Statement*, *对账单*; often *"as at <date>"* | Titled *Invoice*, *Tax Invoice*, *发票*; or a delivery order with items |
| Has a period, a running balance, or ageing columns | Has a delivery/deliver-to line and one printed invoice total |

**The tell is the shape, not the title.** Per-item lines under one invoice number is an
invoice even if someone typed "Statement" on it. A list of invoice numbers with no item
detail is a statement even if it says "Invoice".

**Never guess.** If it is genuinely ambiguous, or it is neither — a price list, a marketing
PDF, a scan you cannot read — **write nothing** and report it by filename and sender. The
owner is told, so nothing is silently dropped; but a non-money document never enters a money
tab, where reconciliation would pick it up and invent a variance.

---

## Mode: capture (weekly, Sunday morning)

**The weekly run captures. It never reconciles, and it never appends a statement.**

### 1. Download — locally

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture/download_invoices.py --days 7
```

This runs on the owner's machine (the Gmail connector cannot fetch attachment bytes). It
does I/O only: writes **every** attachment to `cache/<msg_id>/` and an index at
`cache/manifest.json`. It never parses, and it makes no distinction between an invoice and
a statement — that is your job, above.

### 2. Skip what is already recorded

> Call **`liangzai_pending_documents`**.

**Skip every attachment named in `processed`.** Do not re-read the PDF, do not re-extract, do not
re-append. See *The dedupe* below — this is the guard that makes a re-run safe, and it is
not optional.

### 3. Classify, then route

Apply the rule above to each remaining attachment:

- **Invoice** → extract it (step 4) and record it (step 5).
- **Statement** → **do not append it.** The weekly run does not record statements. Count
  it and say so: *"2 statements arrived — they'll be reconciled at month end."*
- **Neither** → write nothing. Report the filename and sender.

### 4. Extract — this is your job, not a tool's

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

- **ONE ROW PER PRINTED LINE, IN THE DOCUMENT'S OWN ORDER, TOP TO BOTTOM.** Never reorder.
  Never merge two printed lines into one. Never drop a line you cannot read — emit it with
  empty fields instead. **The line's position is part of its identity** (see *The dedupe*):
  change the order and the same line becomes a different row, the dedupe misses it, and the
  money is logged twice with no error anywhere.
- **Copy `supplier_raw` and `delivery_text` verbatim.** Do not tidy them — the
  canonicaliser needs the raw string, and a "helpful" correction destroys the only
  evidence of what the supplier wrote.
- **Never invent a line.** If a column is unreadable, leave the field empty.
- **`stated_total` is the invoice's own printed total** — the control figure. If the
  invoice prints none, leave it null; the gateway marks it `needs_review` because
  completeness can't be verified.
- Some suppliers print no per-line amount. Give `qty` and `unit_price`, leave `amount`
  empty; do not multiply it out.
- **Do not send a statement here, and do not send an entry with an empty `lines` array to
  stand in for one.** That was the old rule and it is what misfiled the statements. If it
  is not an invoice, it does not belong in this payload.

### 5. Append

> Call **`liangzai_append_invoice_log`** with `{ invoices: [...] }` (add `dry_run:
> true` first to preview).

The gateway checks each invoice's line sum against its stated total; a mismatch writes
the lines anyway with `needs_review` and the arithmetic in the reason. Outlets are
canonicalised — an unresolved one becomes `needs_review` with `UNASSIGNED`, **never a
guess**.

Re-running is safe **only because you skipped the already-logged attachments in step 2**.
Do not lean on `source_ref` alone to save you — read *The dedupe* below and understand why
it can fail silently.

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

### 6. Capture sales too

The weekly run must also record the week's Loyverse sales — see `/cost-optimizer`.
Loyverse refuses receipts older than 31 days, so a skipped run over a month loses that
period permanently.

---

## The dedupe — read this before you re-run anything

Both tabs skip rows whose `source_ref` is already present. The key is:

```
source_ref = {gmail_msg_id}:{attachment_id}:{line_index}
```

`gmail_msg_id` and `attachment_id` come from Gmail and never move. **`line_index` does
not** — it is the position of the line in the array *you* extracted, not a property of the
document.

So if a second pass over the same PDF reorders the lines, merges two printed lines into
one, or skips a line it read last time, **every following index shifts, every `source_ref`
changes, and the dedupe silently fails.** The same invoice is logged twice. There is no
error, no flag, and the total in a tab the owner trusts is simply wrong.

Two defences, and you need both:

1. **Extract deterministically** — one row per printed line, in document order. That is what
   keeps the index stable.
2. **Never re-extract a document that is already logged.** Call
   **`liangzai_pending_documents`** first and skip everything in `processed`. This is the
   stronger guard, because it means a second pass never happens at all — nothing can drift
   if nothing is re-read.

   The gateway now backs this up: a re-sent document REPLACES what was recorded for it
   rather than adding a second copy, so a genuine correction is safe. That is a safety net,
   not a licence to skip step 2 — re-reading a PDF costs tokens and time for no gain, and
   the skip is still the rule.

---

## Mode: reconcile (monthly, from the 6th)

**The close captures too — both kinds — and then reconciles.** An invoice that arrived after
the last weekly run must be logged here, or the statement bills something we never logged
and the variance it produces is not real.

### 1. Download

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture/download_invoices.py --days 14
```

Fourteen days, not seven: wide enough to catch statements sent on the 1st–6th **and** any
invoice that landed after the last weekly run.

### 2. Skip what is already recorded, then classify

> Call **`liangzai_pending_documents`**.

Skip every attachment named in `processed` — it covers invoices and statements alike, so
one call answers for both. Then classify what remains with the rule at the top:

- **Statements** → extract and record them (below).
- **Invoices** → extract and append with **`liangzai_append_invoice_log`**, exactly as the
  weekly capture does. Most will already be logged and skipped; the ones that aren't are the
  stragglers that would otherwise reconcile against nothing.
- **Neither** → write nothing, report it.

### 3. Extract the statements

```json
{"soas": [{
  "gmail_msg_id": "...", "attachment_id": "...",
  "supplier_raw": "ACME MEAT SUPPLY", "sender_email": "acct@acme-supplier.example",
  "period": "2026-06", "stated_total": 4103.60,
  "rows": [{"invoice_no": "KI-2606007", "date": "2026-06-17",
            "delivery_text": "靓仔大虾面 (Outlet A)", "amount": 741.00}]
}]}
```

**The same extraction rules apply here, and for the same reason.** A statement row is
identified by its position within that statement:

- **ONE ROW PER PRINTED LINE OF THE STATEMENT, IN ITS OWN ORDER, TOP TO BOTTOM.** Never
  reorder, never merge, never drop a line you cannot read — emit it with empty fields. The
  row's position is part of its identity.
- **Copy `supplier_raw` and `delivery_text` verbatim.**
- **`stated_total` is the statement's own printed total.** If it prints none, leave it null.

> Call **`liangzai_append_soa_entries`** with `{ soas: [...] }`.

### 4. Reconcile

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

### 5. Send the summary

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

Counts, not row dumps: how many invoices logged, how many **statements deferred to month
end**, how many attachments you **could not classify** (by filename and sender — they were
written nowhere), how many need review and why, how many suppliers matched, the net
variance, anything still awaiting an SOA. Name the flagged supplier and outlet. If nothing
needs him, say so plainly.

### When this ran on a schedule, email him — always

If the run was started by a Cowork scheduled task rather than by the owner sitting there:

> **capture** → call **`liangzai_send_run_report`** with `job: "weekly_capture"`.
>
> `summary_lines` carries the counts you'd have said out loud, **including the statements
> you deferred** — *"2 statements arrived; they'll be reconciled at month end"* — so he
> knows they were seen and not lost.
>
> `needs_owner` carries anything needing a human: unmatched outlets, and **every attachment
> you could not classify**, by filename and sender. Those were written nowhere, so this
> report is their only trace — if you omit them, they are lost.
>
> Set `status: "attention"` if `needs_owner` is non-empty, `"ok"` if not, `"failed"` if the
> run broke.
>
> **reconcile** → `liangzai_send_summary` already emails him. Do **not** also send a run
> report; that would be two emails for one job.

**Send it even when there is nothing to report.** A week with no invoices and a week where
the job never ran look identical to him — the email is the only thing that tells them
apart, and with Loyverse's 30-day limit a silently-dead capture costs real money. A quiet
success is a signal, not noise.
