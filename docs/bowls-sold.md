# How "bowls sold per outlet" is determined

Cost per bowl is a fraction. The numerator — reconciled supplier cost — comes from
invoices and statements. This document is about the **denominator**, which is harder than
it looks and is where the number quietly goes wrong.

Everything below is the logic. It is deliberately written without any figures from a live
catalogue.

---

## The problem

**The POS has no "bowls sold" field.** It records line items on receipts: a name, a
quantity, an item ID, sometimes a variant. Nothing in it says "this was one bowl of
noodles". So the bowl count is *synthesised* — and that synthesis silently sets the
headline number the owner will actually look at and price against.

Two properties of real POS data make the naive approach wrong.

### Trap 1 — the same dish is a different item ID at every outlet

Each stall has its own menu entries. The same bowl of noodles appears as separate items
with separate IDs at each location, and the names differ too — usually by the menu
numbering prefix, and often by nothing more than a space or an apostrophe:

```
001. Prawn Noodle (soup/dry)
001.Prawn Noodle (soup/dry)     <- no space after the dot
01. Prawn Noodle (soup/dry)
```

Those are one dish to a human and three strings to a computer. **Count by name and one
dish splits into several rows; classify per-ID and it is easy to tick five outlets and
miss the sixth.** Either way an outlet's bowls vanish from the denominator, and its cost
per bowl comes out too high while looking perfectly reasonable.

### Trap 2 — the highest-volume line item is not food

A takeaway/packaging charge — a few cents, added to most orders — is typically the single
highest-quantity line item in the entire catalogue, out-selling every actual dish.
Counting every line item as a bowl overstates the bowl count enormously and drags cost per
bowl down by a wide margin. It is the most expensive mistake available here and the
easiest one to make.

---

## The rule

**A meal counts as a bowl. Anything that rides along with a meal does not.**

| Counts | Does not count |
|---|---|
| Noodle dishes sold as a meal, in every per-outlet spelling | Packaging / takeaway / bag charges |
| Rice dishes sold as a meal | Drinks |
| | À la carte add-ons and extras (extra noodles, extra protein, extra soup) |
| | Sides and snacks sold alone |
| | Staff meals |
| | Discounts, service and delivery fee lines, and zero/negative-priced lines |

The one-line test: **would a customer call this "a bowl of noodles I bought for lunch"?**

Two consequences that matter:

- **A name-only rule is not enough.** An "add noodles" side contains the word *noodles*
  and would pass any keyword rule that looks for it. Exclusions are checked **before**
  inclusions for exactly this reason.
- **The owner is not asked to adjudicate item by item.** He sells noodles; he does not
  think in taxonomies. The rule is applied for him, and he is shown the finished
  classification once. See *The confirmation gate* below.

---

## The pipeline

### 1. Classify — by dish, submit by ref

`liangzai_bowl_checklist` pulls the last 30 days of receipts across **all outlets** and
returns them grouped into **dishes**, each with a short **ref** (`d001`) and the three
things the rule actually reads: the name, the variants, and the net quantity.

Grouping strips what differs between stalls — the menu-number prefix, case, punctuation,
spacing — and keys on what's left. The agent classifies the **dish** and submits its
**ref** to `liangzai_set_bowl_definition`; the gateway expands each ref into *every* POS
item ID behind that dish.

**Nobody handles item IDs — not the owner, not the agent.** They are an internal join key,
they are different at every outlet, and there is no version of this where a human or a
model transcribing a list of UUIDs makes the count more correct. Keeping them server-side
also keeps them out of the agent's context, where ~200 of them cost tens of thousands of
tokens to carry around and do nothing.

**The ref map is a snapshot, taken when the checklist is generated, and it is never
recomputed at confirm time.** The 30-day window is a rolling one: receipts arrive between
the moment the checklist is produced and the moment it is confirmed. If the grouping were
re-derived on confirm, a ref could resolve to a different set of IDs than the one that was
agreed to — and the definition would quietly stop meaning what it said. A ref that isn't in
the saved snapshot is a hard error, never a silent omission: dropping one would remove that
dish's bowls from the denominator, permanently and invisibly.

The grouper is deliberately **conservative**. When it can't tell that two names are the
same dish (an apostrophe, a genuinely different menu wording at one outlet), it leaves
them as separate rows rather than merging them. That fails in the safe direction: an
unmerged dish is still a visible row, and the agent classifies by meaning, not by string,
so it still gets classified. The dangerous failure is the opposite — merging a bowl with a
non-bowl — and the grouping never does that. When a row *did* merge more than one spelling,
it carries them all, so an over-merge is visible rather than silent.

### 2. Record the weekly sales

The POS plan only serves roughly **30 days** of receipts; older ones are refused outright.
So the agent never looks back — `liangzai_capture_sales` runs weekly and records sales *as
they happen*, resuming from the last recorded day.

Three consequences, all load-bearing:

- **`daily_item_sales` stores net quantity per item, not a bowl count.** Receipts can never
  be re-read past the window, so a stored bowl count would permanently freeze whatever bowl
  definition was current on the day. Storing item quantities keeps the definition a
  **revisable view over durable data** — change it later and history re-derives correctly
  instead of being corrupted.
- **A missed run beyond the window loses that period permanently.** Runs backfill and say
  so loudly when they cannot reach far enough back. It is not only bowls that go: the same
  run records **`daily_sales`**, the per-stall daily revenue, and nothing else in the system
  can reconstruct that day once the window closes.
- Months before the agent started **do not have a cost per bowl** and never will. They are
  not estimated.

Rows are keyed by outlet, date, item and variant, and are idempotent — a re-run corrects
rather than duplicates. Dates are bucketed by **local (SGT, UTC+8) calendar day**, not UTC,
so a late-evening sale lands on the day it was actually sold.

### 3. Count the bowls

For a given month and outlet:

> **bowls sold** = the sum of net quantity, over every `daily_item_sales` row whose
> `item_id` is in the confirmed `bowl_items`, for that outlet, within that month.

**Net** quantity: refunds subtract. A refunded bowl was not a bowl sold.

### 4. Divide

> **supplier cost per bowl** = reconciled supplier cost for that outlet ÷ bowls sold for
> that outlet

Per outlet, per month. Both halves of the fraction must describe the same outlet and the
same period, or the number is meaningless.

---

## The confirmation gate

`liangzai_compute_cost_per_bowl` **refuses to publish anything** until the bowl definition
is recorded with `confirmed_by_owner: true`. This is not ceremony. The classification
silently sets the number the owner trusts, and an unconfirmed guess printed as fact is
worse than no number at all. The agent classifies, then shows him the finished list once —
*"I'm counting these as a bowl, and not these"* — and he can correct it in a sentence.

The definition is **versioned**. Because the sales are stored item by item, a correction six
months from now re-derives history correctly. Getting it wrong today is recoverable;
publishing it unconfirmed is not.

---

## What this number is not

**It is not "cost per bowl", and must never be labelled as one.**

- It covers **only the suppliers in the automated flow**. Suppliers the owner keeps manual
  are excluded, by his own choice.
- It contains **no rent, no labour, no utilities**.
- It is therefore *supplier cost per bowl, for tracked suppliers* — and the stored row, the
  email and every report say so.

**It is never grossed up.** The untracked suppliers are a share of *suppliers*, not of
*spend*, and they are the small ones. Dividing by a coverage ratio would invent an
authoritative-looking number that is probably wrong by more than the error it tried to
correct.

**It is not a per-dish cost.** The denominator splits by dish; the numerator does not. An
invoice says *"this supplier, this outlet, this amount"* — nothing in it says which dollar
went into which dish. Dividing an outlet's total cost by its bowls and printing it against
each dish would produce the same figure for a plain noodle and a loaded one, which is the
outlet average wearing a disguise. Per-dish costing needs a recipe, and a recipe has to
come from the owner. Until then it is not reported.

## Honesty rules carried into the report

Each of these exists because the failure it prevents looks entirely plausible:

| Rule | Why |
|---|---|
| `days_covered` is written on every row, and shown in the email | A partial month of sales divided into a full month of costs understates cost per bowl badly |
| A flagged reconciliation writes the row but names the unresolved suppliers | The cost basis is not final; withholding the row would hide that, printing it silently would misrepresent it |
| Month-on-month change is `—` when the tracked-supplier set changed | That is not a cost trend, and must not be drawn as one |
| A cost that cannot be honestly stated renders as `—` | Never `0.00`, which reads as "this outlet costs nothing" |
| `tracked_suppliers` names exactly which suppliers are in the total | So the scope of the number is never in doubt |

Never print a number you would have to caveat away in the next sentence.
