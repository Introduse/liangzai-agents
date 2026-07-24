---
name: supplier-invoice-manager
description: >-
  Log Liang Zai's supplier invoices and reconcile them against each month's
  Statements of Account. Run weekly to drain the gateway's ingestion queue, classify each
  queued document, and log the INVOICES, split by outlet — statements are left for month end.
  Run monthly (after the 4th, when SOAs land) to log the statements, catch any
  straggler invoice, and match each supplier's statement line-by-line against what was
  logged. Use whenever the user says capture invoices, log invoices, reconcile, check the
  statement, month-end close, or asks why a supplier total does not match.
area: Invoicing
use_for: "Weekly: poll the mailbox, drain the pending queue, record INVOICES by outlet, defer statements, dismiss non-invoices with a reason. Monthly: log the statements + any straggler invoice, reconcile, flag variance, email the owner. Re-sending a document replaces it, so a re-run is safe."
---

# Supplier Invoice Manager

Two modes on two clocks. **Capture** weekly: drain the queue, log the invoices, leave the
statements on it. **Reconcile** monthly: log the statements *and* any invoice the weekly run
missed, then match them line by line.

Both modes write, and both are safe to re-run: re-sending a document replaces what was
recorded for it. That is not a reason to re-read one — see **The dedupe**, and do not skip
it.

**The contract, which nothing may relax:** the agent logs, reconciles, and flags. It
never approves and it never pays. There is no `Approved` and no `Paid` status anywhere
in this system. Every flagged item and every payment goes through the owner.

Pass the plugin's `gateway_api_key` on every `liangzai_*` call. **That is the only
argument you supply** — the gateway holds its own Google, mailbox and Loyverse credentials
server-side. If a `liangzai_*` call comes back `unknown tool`, or a tool's schema still
shows `spreadsheet_id` or `sheets_refresh_token`, the connector has cached an old tool
list — **reconnect it**, and never report it as a missing gateway feature.
`liangzai_poll_mailbox`, `liangzai_document_content` and `liangzai_mark_document` are the
newest three, so on a stale connector this run fails at step 1 rather than anywhere
subtle. `/plugin-update` checks exactly this.

---

## Classify before you write — this is where the last run went wrong

The gateway's poller queues **every attachment** in the mailbox. It does not know an invoice
from a statement, and neither does the database. **You** must, before a single row is written.

The first live run misfiled a supplier's Statement of Account as an invoice, and the
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

**Never guess.** A non-money document must never enter a money table, where reconciliation
would pick it up and invent a variance. But writing nothing is only half the job:

> **Neither an invoice nor a statement → call `liangzai_mark_document`
> with `status: "not_an_invoice"` and a reason.** A price list, a marketing PDF, a delivery
> note with no figures, a HeyGen receipt, a screenshot — the mailbox is shared with the
> owner's ordinary mail, so this is routine and not an edge case.
>
> **A money document you genuinely cannot read → `status: "failed"`, with the reason.** A
> scan too dark to read is still an invoice; it is not `not_an_invoice`. The other common
> case is a format you cannot render — an `.xlsx` or `.docx` invoice. The poller queues
> those deliberately rather than filtering them out, precisely so a supplier who changes
> how they bill reaches a human instead of vanishing. Say which supplier and what format,
> so the owner can ask them for a PDF.

**Reporting it in prose is not enough, and this is the part that bites.** A document you
leave `pending` stays on the worklist for ever, and from the month close onward *any*
pending document blocks the close for **all six stalls** — an unextracted PDF has no known
stall yet, so the gate cannot scope the block to one. Say it in your report *and* close it
with the tool.

**The one thing you must NOT close: a statement during the weekly run.** Statements are
deliberately left `pending` so the monthly close finds them. That is the queue working, not
a backlog to tidy. Never use `mark_document` to clear a readable money document off the list.

---

## Mode: capture (weekly, Sunday morning)

**The weekly run captures. It never reconciles, and it never appends a statement.**

### 1. Make the queue current

> Call **`liangzai_poll_mailbox`** with `{ days: 7 }`.

The gateway checks the mailbox itself — read-only; it never labels, moves or deletes mail.
A cron does this daily too, but daily is not good enough for a weekly run: **call it here
rather than trusting the queue to be current.** Re-running is free — a document already
queued or already extracted is left exactly as it is, so the overlapping window costs
nothing.

Two things in the response are worth reading rather than skimming:

- **`capped: true`** means it stopped early and there is more mail behind it. Call it again.
- **`duplicate_content`** counts attachments it recognised by their bytes and did not queue
  twice. Mail threads re-attach everything on every reply, so one statement can arrive as
  five Gmail attachments; the gateway collapses them. That number is normal, not a fault.

### 2. Take the worklist

> Call **`liangzai_pending_documents`**.

**`pending` is the work**, oldest first, each entry carrying `gmail_msg_id`,
`attachment_id`, `filename`, `sender`, `mime_type`, `size_bytes` and `age_days`.

**Skip every attachment named in `processed`.** Do not re-read the PDF, do not re-extract,
do not re-append. See *The dedupe* below — this is what makes a re-run cheap, and it is not
optional. (`processed` also covers documents dismissed with `liangzai_mark_document`, so a
price list you closed last week never comes back.)

**`failed` is documents a previous run gave up on.** Retry one only if you have reason to
think it will read differently this time; otherwise leave it and name it in the report.

If `pending` is empty, check `last_poll` before saying it was a quiet week — a poller that
stopped on Tuesday looks identical to a mailbox with no invoices in it.

### 3. Fetch each pending document

> For each entry, call **`liangzai_document_content`** with its `gmail_msg_id` and
> `attachment_id` (omit `attachment_id` for an invoice in the mail body itself).

It returns a **signed download URL valid for 15 minutes** — never the bytes, which would
blow the response limit on exactly the biggest, most complex invoices. Download it and read
the file:

```
mkdir -p cache && curl -sL "<download_url>" -o "cache/<gmail_msg_id>_<safe_filename>"
```

**Build `safe_filename` yourself — do not paste the supplier's.** `filename` is whatever
they typed, and suppliers put spaces, slashes and Chinese characters in it. A `/` makes
`curl` write into a directory that does not exist and fail; a space unquoted splits the
argument. Keep the extension, replace anything that is not a letter, digit, dot, dash or
underscore with `_`. Prefixing the `gmail_msg_id` also keeps two suppliers' `invoice.pdf`
apart.

Fetch and read one document at a time. If a URL has expired by the time you get to it, call
`liangzai_document_content` again — it costs nothing.

### 4. Classify, then route

Apply the rule above to each downloaded document:

- **Invoice** → extract it (step 5) and record it (step 6).
- **Statement** → **do not append it, and do not mark it.** The weekly run does not record
  statements; leaving it `pending` is how the monthly close finds it. Count it and say so:
  *"2 statements arrived — they'll be reconciled at month end."*
- **Neither** → **`liangzai_mark_document`** with `not_an_invoice` and a reason, then report
  the filename and sender. Write nothing to a money table.
- **A money document you cannot read** → **`liangzai_mark_document`** with `failed` and the
  reason.

### 5. Extract — this is your job, not a tool's

Read each downloaded file. You render PDFs and photos natively. Extract
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
  empty fields instead. What you send **replaces** everything previously recorded for that
  document (see *The dedupe*), so a lazier second reading does not sit alongside the good
  first one — it overwrites it.
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

### 6. Append

> Call **`liangzai_append_invoice_log`** with `{ invoices: [...] }` (add `dry_run:
> true` first to preview).

The gateway checks each invoice's line sum against its stated total; a mismatch writes
the lines anyway with `needs_review` and the arithmetic in the reason. Outlets are
canonicalised — an unresolved one is stored with no outlet, marked `needs_review`, with the
printed delivery text kept as evidence, **never a guess**.

Two more things it now refuses to accept quietly: the same `invoice_no` from the same
supplier twice, and — where an invoice carries no number — a near-match on the same
supplier, date and total. Both go to `needs_review` rather than being silently accepted or
silently dropped. If you see one, the invoice probably arrived twice; say so.

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

  **It will be raised again next week.** The refusal deliberately does not register the
  supplier, so the same invoice re-raises it on every run until he rules. The gateway
  queues it once rather than once per run; do the same in your report — raise it the first
  time, then say it is still waiting on him, and don't re-present it as news.

Why the machine registers but never merges: **creating** a supplier is safe (the worst case
is a duplicate you merge later), while **merging** two is not. That asymmetry is the whole
design.

### 7. Capture sales too

The weekly run must also record the week's Loyverse sales — see `/cost-optimizer`.
Loyverse refuses receipts older than 31 days, so a skipped run over a month loses that
period permanently.

---

## The dedupe — read this before you re-run anything

**A document's identity is the document.** `{gmail_msg_id}:{attachment_id}` — both come
from Gmail and neither ever moves. Re-sending an invoice or a statement **replaces**
everything previously recorded for it, inside one transaction: the lines are rewritten, not
appended to.

This changed, and it changed in your favour. A line used to be identified by its *position*
in whatever array you happened to extract, so a second pass that reordered or merged lines
produced different keys, the dedupe missed, and the same money was logged twice with no
error anywhere. That failure is now structurally impossible — a re-read lands on the same
document row and overwrites it, however differently you read it.

So the rule survives, but for a different reason:

1. **Never re-extract a document that is already recorded.** Call
   **`liangzai_pending_documents`** first, work only `pending`, and skip everything in
   `processed`. Not because a re-read would double the money — it can't — but because it
   costs tokens and minutes to arrive back where you already were, and a hurried second
   reading **overwrites a careful first one**. Replacement cuts both ways.

   The queue now guards one thing your own care cannot. A single statement, forwarded and
   replied to, arrives as several Gmail attachments with several different
   `attachment_id`s — genuinely different attachments, and not five documents. The poller
   recognises them by their bytes and queues one. Without that, five queue rows would mean
   five sets of statement rows and a reconciliation run against five times the supplier's
   figures — and a doubled statement total does not look like a bug, it looks like a
   supplier dispute.
2. **Extract deterministically anyway** — one row per printed line, in document order. It
   is what makes two readings of the same invoice agree, and what makes the owner's
   line-by-line reconciliation legible when he opens it.

A genuine correction is now a supported operation rather than a hazard: re-send the
document and the record is replaced. That is the safety net. It is not permission to skip
rule 1 above.

---

## Mode: reconcile (monthly, from the 6th)

**The close captures too — both kinds — and then reconciles.** An invoice that arrived after
the last weekly run must be logged here, or the statement bills something we never logged
and the variance it produces is not real.

### 1. Make the queue current

> Call **`liangzai_poll_mailbox`** with `{ days: 14 }`.

Fourteen days, not seven: wide enough to catch statements sent on the 1st–6th **and** any
invoice that landed after the last weekly run. Read the same two fields as the weekly run —
`capped` (run it again) and `duplicate_content` (normal).

### 2. Take the worklist, fetch, then classify

> Call **`liangzai_pending_documents`**, then **`liangzai_document_content`** per pending
> entry and `curl` each signed URL to a file, exactly as the weekly capture does (capture
> steps 2–3).

Skip every attachment named in `processed` — it covers invoices and statements alike, so
one call answers for both. Then classify what you downloaded with the rule at the top:

- **Statements** → extract and record them (below). Most of `pending` will be these: the
  weekly runs deliberately left them here.
- **Invoices** → extract and append with **`liangzai_append_invoice_log`**, exactly as the
  weekly capture does. These are the stragglers that would otherwise reconcile against
  nothing.
- **Neither** → **`liangzai_mark_document`** (`not_an_invoice`, with a reason), and report it.
- **Unreadable money document** → **`liangzai_mark_document`** (`failed`, with the reason).

**Nothing may be left `pending` at the end of the close.** Unlike the weekly run, this is
the run where the queue must come out empty — the month close gates on it, and it gates
across all six stalls at once.

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

**The same extraction rules apply here, and for the same reason.** Re-sending a statement
replaces its rows rather than adding a second set — the statement side got that fix
alongside the invoice side, and it matters more here, because a doubled statement total does
not look like a bug. It looks like a supplier dispute.

- **ONE ROW PER PRINTED LINE OF THE STATEMENT, IN ITS OWN ORDER, TOP TO BOTTOM.** Never
  reorder, never merge, never drop a line you cannot read — emit it with empty fields. The
  owner reconciles this line by line against his own records; the order is how he reads it.
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

If he says yes → **`liangzai_merge_suppliers`** → re-run reconciliation. The merge moves the
invoices and statements themselves, not just the supplier's aliases, and clears the
reconciliation it invalidated so the re-run rebuilds it; nothing is re-entered. **Re-running
reconciliation after a merge is not optional** — until you do, the month still shows the
split. If he says no, leave them apart — they really are two suppliers, and the
`SOA_MISSING` is real.

Month one will be noisy — rounding, GST inclusivity, partial deliveries. That is the
system working. The owner is the filter.

### 5. Send the summary

> Call **`liangzai_send_summary`** with `{ month: "2026-06", preview: true }` and show
> the owner the result first. Then call it again with `preview: false` to send.

Flagged and needs-review rows lead; matched follow. The footer states, in both
languages, that nothing has been approved or paid. The gateway refuses any recipient
outside the `summary_recipients` allowlist it holds — the agent must never write to a
supplier.

### The button does not approve anything

It deep-links to the gateway's own reconciliation view (`/reconcile?period=…`), where the
owner changes the status himself: `审核中 Under Review` → `待付款 Ready for Payment`. Do not
replace this with a one-click approval link — mail scanners fetch URLs before a human
clicks, and a scanner would silently mark rows ready that the owner never opened.

**That screen is still being built.** Until it lands, the link may not resolve to anything
he can act on. Say so if he asks, rather than talking him through a page that isn't there
— and never offer to set the status for him instead. You cannot: the database refuses it
for anyone who is not the owner, which is the point.

### The owner owns the payment-status column

The gateway writes a default only when a row is created (`Ready for Payment` for a
clean match, `Under Review` otherwise) and **preserves his choice** on every later run.
The one exception: if a late SOA changes the figures under a row he already approved,
it resets to `Under Review` and says so. The agent can never set `已付款 Paid` — only
the owner can, after paying his bank.

---

## Reporting back

Counts, not row dumps: how many invoices logged, how many **statements deferred to month
end**, how many documents you **dismissed as not-an-invoice** (by filename and sender — they
were written to no money table), how many need review and why, how many suppliers matched,
the net variance, anything still awaiting an SOA. Name the flagged supplier and outlet. If
nothing needs him, say so plainly.

Say what the queue looks like when you finish: how many `pending` are left and why (weekly:
statements, deliberately; monthly: nothing should be). A number left behind with no
explanation is the one that turns into a blocked month close.

### When this ran on a schedule, email him — always

If the run was started by a Cowork scheduled task rather than by the owner sitting there:

> **capture** → call **`liangzai_send_run_report`** with `job: "weekly_capture"`.
>
> `summary_lines` carries the counts you'd have said out loud, **including the statements
> you deferred** — *"2 statements arrived; they'll be reconciled at month end"* — so he
> knows they were seen and not lost.
>
> `needs_owner` carries anything needing a human: unmatched outlets, and **every document
> you dismissed or could not read**, by filename and sender. The dismissal reason is on the
> row, but he does not have a screen to read it on yet — this report is the only place he
> sees it.
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
