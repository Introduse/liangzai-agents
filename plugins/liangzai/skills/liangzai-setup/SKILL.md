---
name: liangzai-setup
description: >-
  Run once, inside the owner's Claude Cowork project, to wire up the Liang Zai agents:
  connect the liangzai gateway, register the Google refresh token locally for invoice
  downloads, create the Sheet, confirm the Loyverse mapping, record what counts as a
  bowl, and embed the agent into the workspace CLAUDE.md. Use when the user says "set
  up", "get started", "onboard", "first run", or when any Liang Zai skill reports a
  missing connector, key, or bowl definition.
area: Setup
use_for: "First-run onboarding: gateway connector + API key, local Google OAuth, Sheet tabs, outlet map, bowl definition, workspace CLAUDE.md, scheduled tasks."
---

# Liang Zai — First-Run Setup

The owner is a hawker-chain operator, not an engineer. **Explain what each step is for
before asking, do one step at a time, and confirm before moving on. Never show a stack
trace** — say plainly what broke and what you need.

Almost everything runs through the **gateway** (a remote MCP server Five Bucks deploys).
It holds only the **Loyverse** token and the spreadsheet id; the **Google credentials are
this machine's**, kept in `.claude/settings.local.json` and sent with every call. Setup
connects the gateway, mints those Google credentials, and embeds the agent so every future
session loads it. It is safe to re-run — every step checks whether it is already done.

## Arguments

| Argument | Meaning |
|---|---|
| `-- project created` | The user is already inside the project session. **Skip Step 1** and begin at Step 2. |

## Flow

Run the steps in order. At the end of each, ask the user to confirm before continuing —
so they can pause and resume anytime. The only exception is an explicit "skip".

---

## Step 1 — Work in a Project

All local files (the invoice cache, `.claude/settings.local.json`) live inside a Cowork
project. Setup cannot run without one.

> In Cowork, look below the chat input for **Projects** → **Create a new Project** →
> **Use an existing folder**, pick the `liangzai-agents` folder, name it "Liang Zai".
> Set Claude Permission to **Act without asking** — the weekly and monthly jobs stall
> without it. ⚠️ *Review Claude's autonomy warnings before confirming.*

Then have the user **open the project session** and re-run:

```
/liangzai-setup -- project created
```

**Do not continue in this session** — resume inside the project.

## Step 2 — Connect the gateway

The gateway is where the Sheet writes, reconciliation, and the summary email happen. It
must be connected first — every `liangzai_*` tool depends on it.

> 1. **Settings → Connectors → "Add custom connector".**
> 2. Name: `gateway`
> 3. URL: `https://liangzai-gateway.vercel.app/api/mcp`
> 4. Click **Connect**.

The gateway API key (`liangzai_live_…`) is a plugin setting, not entered in the connector
dialog — paste it when the plugin prompts for **`gateway_api_key`** (stored in your OS
keychain). Confirm by asking the model to call **`liangzai_ping`** — it returns `pong`
when the key is valid. If not, the key or URL is wrong; stop and fix.

## Step 3 — Google access

This machine is where the Google credentials live. They do two jobs. Locally, they let
`download_invoices.py` fetch invoice attachments — the Gmail connector can't fetch
attachment bytes, so that part has to run here. Remotely, they are what every `liangzai_*`
call sends to the gateway, which holds no Google credentials of its own (see
`agents/liangzai.md`). One consent, minted here, covers both.

The OAuth client must be **Internal** to the Google Workspace — `gmail.readonly` is a
restricted scope, and an External client left in Testing gets refresh tokens that
**expire after 7 days**, so the weekly job would run once and die silently.

This is the fiddliest step in the whole setup. **Walk the user through it one click at a
time and confirm each sub-step before moving on.** Do not paraphrase — the console has
several near-identical menus and the wrong one is a dead end.

### 3a. Sign in and create the project

> Go to <https://console.cloud.google.com> and sign in **as the supplier mailbox account**
> (the same Workspace account the agents will read mail from).
>
> Top bar → the project dropdown → **New Project**. Name it `liangzai-agents` → **Create**.
> When it finishes, make sure that new project is **selected in the top bar** — everything
> below applies to the selected project.

### 3b. Turn on the two APIs

Both are required: Gmail (to read invoice attachments and send the summary) and Sheets (to
write the tracking sheet). If either is off, the token mints fine but every call fails
later with `API has not been used in project … before or it is disabled`.

> Left menu → **APIs & Services → Library**.
> 1. Search **Gmail API** → click it → **Enable**.
> 2. Go back to Library. Search **Google Sheets API** → click it → **Enable**.

Confirm both now show **API Enabled** before continuing.

### 3c. Configure the consent screen (Google Auth Platform)

Google reorganised this: it is no longer one "OAuth consent screen" page but a section
called **Google Auth Platform** with sub-pages (Branding, Audience, Clients, Data Access).

> Left menu → **APIs & Services → OAuth consent screen** (this opens **Google Auth
> Platform**). If it shows a **Get started** button, click it.
>
> **Branding** — App name `Liang Zai Agents`; User support email = the mailbox account;
> Developer contact email = the same. **Save**.
>
> **Audience** — set **User type: Internal**. **Save**.

**"Internal" must be selectable.** If it is greyed out, the account signed in is not a
Google Workspace account — stop and fix that first. Do not fall back to **External**: an
External app in Testing hands out refresh tokens that expire in 7 days, and the weekly job
would run once and then fail silently forever. This is the single worst outcome available
and it is the default one.

### 3d. Add the scopes (Data Access)

> **Google Auth Platform → Data Access → Add or remove scopes.** Add these three, then
> **Update** and **Save**:
>
> ```
> https://www.googleapis.com/auth/gmail.readonly
> https://www.googleapis.com/auth/gmail.send
> https://www.googleapis.com/auth/spreadsheets
> ```

### 3e. Create the OAuth client — and add the redirect URI

> **Google Auth Platform → Clients → Create client.**
> - **Application type: Web application** (not Desktop — we need to register a redirect URI).
> - Name: `liangzai-cowork`.
> - Under **Authorized redirect URIs**, click **+ ADD URI** and enter exactly:
>
>   ```
>   http://localhost:5179
>   ```
>
> - Click **Create**, then copy the **Client ID** and **Client secret**.

**The redirect URI is mandatory and must match exactly** — `http` (not `https`), no
trailing slash, port `5179`. Without it Google rejects the sign-in with
`redirect_uri_mismatch` before he ever reaches the Allow button.

**Nothing is listening on that port**, and nothing needs to be. Google puts the code in
the browser's address bar when it redirects there; the page fails to load, and he pastes
that URL back (3g–3h). The failed page *is* the handoff.

### 3f. Save the credentials

Write `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_ACCOUNT`, `SUPPLIER_MAILBOX` into
`.claude/settings.local.json` under `env`. `OAUTH_ACCOUNT` is the supplier mailbox address —
the consent below is refused under any other login, so a stray personal account can never
quietly become the inbox the agent reads.

This file is the only copy of these values anywhere. The agent reads them straight out of
it and passes them to the gateway on every `liangzai_*` call, so if they are wrong or
missing here, nothing works — not the local download, not the Sheet.

### 3g. Get the sign-in link and give it to him

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/oauth/google_oauth.py --auth-url
```

Show him the link it prints and tell him exactly this:

> 1. Open this link.
> 2. Sign in **as the supplier mailbox** (not your personal Gmail).
> 3. Click **Allow**.
> 4. Your browser will then land on a page saying **"This site can't be reached"**.
>    **That is what success looks like — nothing has gone wrong.**
> 5. Copy the **whole address** out of the address bar (it starts with
>    `http://localhost:5179/?code=`) and paste it back to me.

**Do not skip step 4's warning.** The page genuinely fails to load, and an owner who
isn't expecting that will assume he broke something and stop. Google hands the code back
only in that address bar — there is nowhere else for it to go, and nothing is listening
on that port to catch it. The failed page *is* the handoff.

### 3h. Exchange it

When he pastes the URL back:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/oauth/google_oauth.py --exchange "<the URL he pasted>"
```

Quote the URL — it contains `&` and an unquoted shell will cut it in half. The script
pulls the code out, swaps it for a refresh token, checks the account he actually signed in
as matches `OAUTH_ACCOUNT`, and only then writes `GMAIL_REFRESH_TOKEN` +
`SHEETS_REFRESH_TOKEN`. If the account doesn't match, it saves nothing and says so.

**The code is single-use and expires in minutes.** If he took a coffee break, or you run
the exchange twice, Google answers `invalid_grant` — that isn't a misconfiguration, just
redo 3g.

### 3i. Save the recipient allowlist

Ask the owner who should receive the summary and run-report emails — almost always just
himself. Write the answer as a comma-separated list under `SUMMARY_RECIPIENTS` in
`.claude/settings.local.json`, next to the values from 3f and the refresh tokens 3h just
wrote.

This is a hard guard, not a formality. Every send is checked against this list and refuses
any address off it, and the mailbox it sends *from* is the one suppliers write *to* — so
the list is what stands between a bug and an email landing at a supplier. Keep it to the
owner.

### If something fails

| What you see | Fix |
|---|---|
| `redirect_uri_mismatch` | The redirect URI is missing or wrong. Go to **Clients → your client → Authorized redirect URIs** and add `http://localhost:5179` exactly (3e). |
| `Access blocked: … has not completed the Google verification process` | The app is **External**. Switch **Audience** to **Internal** (3c). |
| `API has not been used in project … or it is disabled` | Gmail API or Sheets API is off. Enable both (3b). |
| `Internal` is greyed out | Not signed in with a Google Workspace account. Sign in with one. |
| Token stops working after ~7 days | The app was left **External / Testing**. Recreate it as **Internal** (3c). |

## Step 4 — Create the Sheet

Confirm the gateway's `SPREADSHEET_ID` points at the *Invoice log and Cost tracker* and
that the mailbox account can edit it. Then:

> Call **`liangzai_init_sheet`**.

It creates `invoice_log`, `soa_entries`, `reconciliation`, `reconciliation_detail`,
`sales_daily`, `cost_tracking`, and `agent_config` with bilingual headers, the
payment-status dropdown on `reconciliation`, and the 状态 Status dropdown on `invoice_log`
and `soa_entries`. Idempotent, and safe to re-run on a Sheet that already has tabs — it
fully styles only the tabs it creates (so it never stomps formatting the owner has changed),
but it ensures the dropdowns on tabs that already exist, because those are a data contract
rather than decoration.

**This must run before Step 5** — `loyverse_stores write_config` writes the outlet map into
`agent_config`, which only exists once this runs.

## Step 5 — Loyverse & outlet map

> Call **`liangzai_loyverse_stores`** with `write_config: true`.

It must report **6 stores** matching the outlets. Fewer means the token is scoped wrong;
`HTTP 402` is the plan limit, expected for old receipts (Step 7).

## Step 6 — What counts as a bowl

Loyverse has no "bowls sold" field, so we have to decide which items are a bowl. **Do not
put that question to the owner.** He sells noodles; he does not think in taxonomies, and
asking him to rule on whether a side dish is "a bowl" invents a decision he never had.

**Apply this rule. It is the definition — not a starting point for a discussion.**

| Counts as a bowl | Does not count |
|---|---|
| Any noodle dish sold as a meal — prawn noodle (dry or soup), 大虾面, mee, kway teow, bee hoon, Hokkien mee, and every per-outlet spelling of them | Packaging and bag charges (the `$0.30` line — it is the highest-volume item in the catalogue and would roughly double the bowl count if counted) |
| A rice dish sold as a meal, if he sells one | Drinks |
| | À la carte add-ons and extras — extra prawns, extra egg, extra noodles, extra soup |
| | Sides and snacks — toast, kaya, eggs sold alone |
| | Staff meals, discounts, delivery/service fees, and anything with a zero or negative price |

The test in one line: **would a customer call this "a bowl of noodles I bought for lunch"?**
If it is a meal, it counts. If it rides along with a meal, it does not.

> Call **`liangzai_bowl_checklist`** with `last_days: 30`. It returns **`dishes`** — one row
> per real dish, already collapsed across all six stalls, each with a short **`ref`** like
> `d001`. Classify each `dish` with the rule above, then call
> **`liangzai_set_bowl_definition`** with the **`bowl_refs`** of the bowl dishes, the rest in
> `excluded_refs`, `confirmed_by_owner: true`, and a `version` like `v1-2026-07`.

**You classify dishes and submit refs. You never touch a Loyverse ID.** The same bowl of
noodles is a *different* ID at each stall, spelled differently too (`001. Big Prawn Noodle`,
`01. Big Prawn Noodle`, `001.Big Prawn Noodle`). The gateway knows every ID behind each
dish and expands the ref itself — which is the whole point: it cannot be got wrong, and the
IDs never enter the conversation (they were costing ~28,000 tokens a run for nothing).

**Classify against the list you were just given.** A ref is a handle into *that* checklist,
not a permanent name. If you re-run `liangzai_bowl_checklist`, classify against the fresh
list — refs from an older run may point somewhere else. Passing an unknown ref is an error,
not a silent skip, and it will tell you to re-run.

Two things worth reading on the returned rows:

- **`names`** appears only when one dish was sold under more than one spelling. Glance at
  it: if the spellings in a single row are clearly *different dishes*, the grouping is
  wrong — say so rather than classifying it.
- **`ids`** and **`outlets`** are counts, not lists. A bowl dish showing `outlets: 1` when
  you'd expect all six is worth a second look.

The owner never sees any of this. He confirms dish names.

**Then show him the result as a finished thing, not a quiz.** One short message: *"I'm
counting these N items as a bowl, and not counting these M (packaging, drinks, add-ons,
staff meals). Tell me if any of those look wrong."* He can correct it in a sentence, and
that is the only input he should ever have to give. Re-run
`liangzai_set_bowl_definition` with a new `version` if he does.

Showing it is not optional, and it is why `confirmed_by_owner` exists: this single
classification silently sets the headline number he will actually look at, and
`liangzai_compute_cost_per_bowl` refuses to publish anything until the flag is true.
Because `sales_daily` stores item-level quantities, changing the definition later
re-derives history correctly instead of corrupting it — so a correction six months from
now is cheap, and getting it wrong today is not permanent.

## Step 7 — The 30-day rule, explained once

> Your Loyverse plan only lets us read the last 30 days of sales. Rather than pay for
> more, the agent records each week's sales as they happen and tallies them at month end.
> Cost-per-bowl starts from now — earlier months can't be recovered — and if the weekly
> job is off for over a month, that gap is lost for good, so we'll flag any missed run
> loudly.

## Step 8 — Validate

Confirm each connection with a low-cost call before handing over:

- **`liangzai_ping`** → `pong` (gateway + key).
- **`liangzai_loyverse_stores`** (no write) → 6 stores.
- **`liangzai_capture_sales`** with `dry_run: true` → a receipt count, no write.
- Locally: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/capture/download_invoices.py --days 7 --dry-run`.
  If it finds nothing, suppliers haven't started sending to the mailbox yet — a business
  step, not a bug.

## Step 9 — Initialize the workspace CLAUDE.md

The agent only activates for this workspace if `CLAUDE.md` embeds `agents/liangzai.md`.
This writes it idempotently between markers, so every future session — including scheduled
runs — auto-loads the agent. **Mandatory; do not skip.**

### 9a. Locate and read agents/liangzai.md

The skill runs inside the Cowork sandbox (Ubuntu VM), so search `$CLAUDE_CONFIG_DIR` first;
the host-OS paths are fallbacks for local Claude Code.

```python
import glob, json, os, re, datetime

config_dir = os.environ.get("CLAUDE_CONFIG_DIR")
patterns = []
if config_dir:
    patterns.append(os.path.join(config_dir, "**/agents/liangzai.md"))
patterns += [
    os.path.expanduser("~/.claude/**/agents/liangzai.md"),
    os.path.expandvars(r"%APPDATA%\Claude\**\agents\liangzai.md"),
    os.path.expanduser("~/Library/Application Support/Claude/**/agents/liangzai.md"),
]
found = [f for p in patterns for f in glob.glob(p, recursive=True)]
if not found:
    raise SystemExit("Could not auto-detect agents/liangzai.md — ask the user for the "
                     "full absolute path (in Cowork: echo $CLAUDE_CONFIG_DIR).")

agent_md = open(os.path.realpath(found[0]), encoding="utf-8").read()
# Strip the YAML frontmatter — it is a plugin-loader directive, meaningless in CLAUDE.md.
body = re.sub(r'^---\s*\n.*?\n---\s*\n', '', agent_md, count=1, flags=re.DOTALL).lstrip()
embed_date = datetime.date.today().isoformat()

# Read the installed plugin version to stamp into the marker (plugin-update compares it).
# It comes from .claude-plugin/plugin.json — the only version file that SHIPS with the
# plugin. The repo's versions/version.ts sits outside plugins/liangzai/ and is not
# installed, so reading it here would always yield "unknown".
plugin_version = "unknown"
pj = os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(found[0]))),
                  ".claude-plugin", "plugin.json")   # …/liangzai/.claude-plugin/plugin.json
if os.path.exists(pj):
    plugin_version = "v" + json.load(open(pj, encoding="utf-8"))["version"]
```

### 9b. Patch CLAUDE.md idempotently

Read `CLAUDE.md` at the workspace root (create it fresh with the block below if absent).

```python
import os, re

new_block = (
    "<!-- BEGIN agents/liangzai.md (embedded by liangzai-setup) -->\n"
    f"<!-- liangzai plugin: {plugin_version} | embedded: {embed_date} -->\n"
    "\n"
    f"{body}\n"
    "\n"
    "<!-- END agents/liangzai.md -->"
)

claude_md = open("CLAUDE.md", encoding="utf-8").read() if os.path.exists("CLAUDE.md") else ""

if "<!-- BEGIN agents/liangzai.md (embedded by liangzai-setup) -->" in claude_md:
    # Case 1 — markers present: replace everything between (and including) them.
    claude_md_new = re.sub(
        r'<!-- BEGIN agents/liangzai\.md \(embedded by liangzai-setup\) -->.*?<!-- END agents/liangzai\.md -->',
        lambda m: new_block,   # lambda avoids re.sub's backslash interpretation in `body`
        claude_md, count=1, flags=re.DOTALL,
    )
else:
    # Case 2 — markers absent, including a brand-new file: PREPEND above all existing
    # content. The agent identity must lead the file, not trail whatever else is there.
    claude_md_new = new_block + ("\n\n" + claude_md if claude_md else "\n")

open("CLAUDE.md", "w", encoding="utf-8").write(claude_md_new)   # show the diff first
```

Embed the **content**, not a path reference, so the workspace is self-contained for
scheduled runs and fresh clones. Re-running setup or upgrading the agent just refreshes
the block. Surface any write failure now, before Step 10.

### 9c. Verify

Read `CLAUDE.md` back and confirm the version stamp matches `plugin_version` and that a
string unique to the current `agents/liangzai.md` body (e.g. its latest Maintenance
version) appears inside the markers. If it doesn't, the body wasn't actually replaced —
re-read the file and retry rather than reporting this step as done.

## Step 10 — Schedule & hand over

Two jobs run on their own from here. **Ask the owner when he wants them** — do not assume
the defaults — then create the tasks with Cowork's own scheduler.

### 10a. Ask for the two cadences

**Weekly capture** — which weekday, what time? (default **Sunday 08:00**)

**Monthly close** — which day of the month, what time? (default **the 6th, 09:00**)

Explain the monthly one before he picks, in his language:

> Your suppliers send their statements by the 4th. If we reconcile before they arrive,
> we'd be checking your invoices against statements that aren't there yet and everything
> would look wrong. So pick the 5th or later.

**Refuse any day below 5, and any day above 28** (the 29th doesn't exist in February).

### 10b. Create the two tasks with Cowork's `/schedule`

**Use Cowork's own scheduling — do not read UI instructions aloud and do not ask him to
click through Settings.** Invoke **`/schedule`** and give it the task name, frequency and
prompt. Cowork asks him to confirm, and the task appears on its **Scheduled** page.

**The schedule is Cowork's, and only Cowork's.** There is no gateway tool that records it,
and there must not be: Cowork owns the cadence, fires the jobs, and lists them. A second
copy in the Sheet would go stale the first time he edits a task, and a stale copy that is
written down looks authoritative. To see or change when the jobs run, look in Cowork.

Create these two:

**Task 1 — `Liang Zai · Weekly capture`** · frequency **Weekly**, his weekday + time:

```
Run /supplier-invoice-manager capture, then /cost-optimizer capture-sales.
Then call liangzai_send_run_report with job: "weekly_capture", a summary of what was
logged, and anything that needs the owner in needs_owner. Send the report even if
there was nothing to log — a silent run is indistinguishable from a broken one.
```

**The weekly job captures only — it never reconciles, and it never logs a statement.** It
classifies each attachment: invoices are logged, statements are counted and left for the
monthly close, and anything that is neither is reported and written nowhere.

**Task 2 — `Liang Zai · Monthly close`** · frequency **Daily**, his time:

```
Today is {{today}}. The monthly close runs on day <N> of the month.
If today is not day <N>, STOP NOW — do nothing, write nothing, send nothing.

Otherwise: run /supplier-invoice-manager reconcile, then /cost-optimizer monthly,
then send the reconciliation summary with liangzai_send_summary.
```

**Why Task 2 is Daily and not Monthly:** Cowork's frequency picker only offers hourly,
daily, weekly, weekdays, or manual — **there is no monthly option**. So the task wakes
daily and the date check on its first line exits immediately on the other ~29 days. Do
not remove that guard; without it the close would run every single day.

**Cost-per-bowl is step 2 of the monthly close, never its own task.**
`liangzai_compute_cost_per_bowl` reads the `reconciliation` tab, so scheduling it
separately risks it firing before reconciliation and publishing a cost against a stale or
empty basis. One task, in order, is what makes that impossible.

### 10c. Tell him the thing that will actually bite him

Say this plainly — it is the one failure that cannot be undone:

> These jobs only run while this computer is on. If it's off on the day, the job is
> missed. Missing one week is survivable — the next run catches up the sales it missed.
> **But Loyverse only keeps 30 days of sales.** If the computer is off for more than a
> month, that month's sales are gone for good and we can never work out your cost per
> bowl for it.
>
> So: **you get an email every time a job finishes, even when there's nothing to report.**
> That's on purpose. If a Sunday goes by and no email arrives, something is wrong — open
> Cowork and tell Claude.

### 10d. Hand over

One short message: what runs, when, what lands in the Sheet, and that **nothing is ever
paid automatically** — every flagged item and every payment goes through him.
