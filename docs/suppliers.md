# How suppliers are identified

Reconciliation compares what we logged from invoices against what the supplier billed on
their statement. To compare them, both sides have to agree on **who the supplier is**.

That sounds trivial. It is where this system is most easily broken, and the failure is
silent.

---

## The supplier name is a join key, not a label

Invoices and statements are matched on `(supplier, outlet)`. So the supplier name is not
decoration — it is the thing that makes the two halves meet.

The same company writes its name three different ways:

| Where | What it says |
|---|---|
| Invoice letterhead | `Acme Packaging Pte. Ltd. (中文名)` |
| Statement header | `ACME PACKAGING` |
| Email address | `accounts@acme.example` |

If those resolve to three different suppliers, the invoices land under one key and the
statement under another. Each is then compared against **nothing**. Every row comes out
"statement missing", the totals all look wrong, and *nothing explains why* — the numbers are
individually plausible and collectively meaningless.

This is why the system will not simply accept whatever name is printed on the page.

---

## Suppliers register themselves

**A supplier the system has never seen is recorded automatically**, the first time an
invoice arrives, keyed on the **sender's email domain**. There is no list to maintain and
nothing to set up.

The domain is the key because it is the stable part. A supplier can typo their letterhead,
change their trading name, or send a scan with the header cut off. They cannot typo their
mail server.

Once registered, every later invoice **and statement** from that domain resolves to the same
supplier — which is exactly what the join needs.

The owner is **told**, not asked:

> *12 invoices logged. 3 new suppliers registered: Acme Packaging, … — nothing needed from
> you.*

---

## The one thing the machine will not decide

**Creating a supplier is safe. Merging two is not.**

The worst case of creating one wrongly is a duplicate, which is visible and fixable. The
worst case of *merging* two wrongly is that two different companies' money is added together
— and the total still looks completely reasonable. There is no way to see that from the
number. It is the precise failure this system exists to prevent, so the machine never does
it on a hunch.

So it stops and asks in exactly one situation:

> **A known name arrives from an unknown address.**

That is either the supplier's outsourced billing agent, or a *different company with a
similar name*. Those two cases look identical to a machine and are obvious to the owner. He
decides; the system does not.

---

## The split supplier

The residual case, and the reason this is documented at all.

A company invoices from one address and sends **statements from another** — a billing agent,
a separate accounts department, an outsourced bookkeeper. Both addresses are legitimate, and
both are new, so both register. The company becomes **two suppliers**.

Then:

- Supplier A has invoices, and **no statement**.
- Supplier B has a statement, and **no invoices**.
- Both read as unmatched.

That looks like a supplier problem. It is ours. So reconciliation detects it and says so
outright, in the Sheet and in the summary email:

> *Acme Packaging* has invoices but no statement, and *Acme Pkg Services* has a statement but
> no invoices. **Are these the same company?**

One answer fixes it. The rows correct **in place** on the next reconciliation — invoice and
statement rows upsert on a deterministic key, so nothing is re-entered by hand.

The detector deliberately errs toward suggesting. A false suggestion costs a glance. A
missed one costs a month of reconciliation that quietly does not add up.

---

## What this replaced

Supplier names used to come from a hand-maintained file inside the server, baked in when the
service was deployed. Registering a supplier meant an engineer editing that file and
redeploying. Suppliers change all the time, so in practice the file was never right — and
every invoice from anyone not in it was flagged for review.

The flag was correct. The registration was the problem.

---

## Summary

| Situation | What happens |
|---|---|
| Invoice from a known email domain | Resolves. Silent. |
| Invoice from a **new** domain | **Registers automatically.** The owner is told, not asked. |
| A **known name** from a **new** domain | **Flagged.** Billing agent, or a different company? Only the owner knows. |
| Invoices under one name, statement under another | **Detected**, and a merge is suggested. |
| Two suppliers confirmed to be one company | The owner merges. The next reconciliation repairs the rows in place. |

The rule underneath all of it: **register freely, merge never.**
