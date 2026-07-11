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

Almost everything runs through the **gateway** (a remote MCP server Five Bucks deploys,
holding the Google and Loyverse credentials). The owner's setup connects to it, mints
the one local token invoice downloads need, and embeds the agent so every future session
loads it. Setup is safe to re-run — every step checks whether it is already done.

## Arguments

| Argument | Meaning |
|---|---|
| `-- project created` | The user is already inside the project session. **Skip Step 1a** and begin at Step 1b. |

## Flow

Run the steps in order. At the end of each, ask the user to confirm before continuing —
so they can pause and resume anytime. The only exception is an explicit "skip".

---

## Step 1 — Cowork setup

### 1a. Work in a Project

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

### 1b. Configure settings

> Go to **Settings** and enable:
> 1. **Claude Code → Allow bypass permissions mode** — ON (so scheduled jobs run
>    without interruption).
> 2. **Capabilities → Domain Allowlist → All Domains** — ON (so the local download
>    script can reach Gmail and the gateway connector works).

Do not proceed until both 1a and 1b are confirmed.

## Step 2 — Connect the gateway

The gateway is where the Sheet writes, reconciliation, and the summary email happen. It
must be connected first — every `liangzai_*` tool depends on it.

> 1. **Settings → Connectors → "Add custom connector".**
> 2. Name: `gateway`
> 3. URL: the liangzai gateway address (ends in `/api/mcp`).
> 4. Click **Connect**.

The gateway API key (`liangzai_live_…`) is a plugin setting, not entered in the connector
dialog — paste it when the plugin prompts for **`gateway_api_key`** (stored in your OS
keychain). Confirm by asking the model to call **`liangzai_ping`** — it returns `pong`
when the key is valid. If not, the key or URL is wrong; stop and fix.

## Step 3 — Google access for downloads

The gateway holds the Google credentials, but **downloading invoice attachments runs
locally** (the Gmail connector can't fetch attachment bytes), so this machine needs a
`gmail.readonly` refresh token. Minting it also produces the token Five Bucks sets on the
gateway.

The OAuth client must be **Internal** to the Google Workspace — `gmail.readonly` is a
restricted scope, and an External client left in Testing gets refresh tokens that
**expire after 7 days**, so the weekly job would run once and die silently. Walk the user
through creating a Desktop OAuth client under a Workspace account (Gmail API + Sheets API
enabled, consent screen **Internal**), write `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`OAUTH_ACCOUNT`, `SUPPLIER_MAILBOX` into `.claude/settings.local.json` under `env`, then:

```
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/oauth/google_oauth.py
```

Sign in as the supplier mailbox and click Allow — the script refuses any other login. It
writes `GMAIL_REFRESH_TOKEN` + `SHEETS_REFRESH_TOKEN` locally. Give the same refresh token
to Five Bucks for the gateway (plus `SUMMARY_RECIPIENTS`, the comma-separated allowlist of
who receives the monthly summary — a hard guard so no bug can email a supplier).

## Step 4 — Create the Sheet

Confirm the gateway's `SPREADSHEET_ID` points at the *Invoice log and Cost tracker* and
that the mailbox account can edit it. Then:

> Call **`liangzai_init_sheet`**.

It creates `invoice_log`, `soa_entries`, `reconciliation`, `reconciliation_detail`,
`sales_daily`, `cost_tracking`, and `agent_config` with bilingual headers and the
payment-status dropdown. Idempotent. **This must run before Step 5** — `loyverse_stores
write_config` writes the outlet map into `agent_config`, which only exists once this runs.

## Step 5 — Loyverse & outlet map

> Call **`liangzai_loyverse_stores`** with `write_config: true`.

It must report **6 stores** matching the outlets. Fewer means the token is scoped wrong;
`HTTP 402` is the plan limit, expected for old receipts (Step 7).

## Step 6 — What counts as a bowl

**This decides the number the owner actually cares about, and he must answer it himself.**
Loyverse has no "bowls sold" field.

> Call **`liangzai_bowl_checklist`** with `last_days: 30`.

It returns the distinct item names by net quantity (markdown). Show it and explain: the
same dish is named differently per outlet, so we count by Loyverse **item ID** not name;
and the highest-volume line item is a `$0.30` packaging charge, assumed **not** a bowl.
Ask the judgement calls (is fried Hokkien mee a bowl? rice dishes? staff meals?), then:

> Call **`liangzai_set_bowl_definition`** with the confirmed item IDs in `bowl_items`,
> `confirmed_by_owner: true`, and a `version`.

Until that flag is true, `liangzai_compute_cost_per_bowl` refuses to publish a
cost-per-bowl — by design.

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
import glob, os, re, datetime

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
vt = [f for p in ([os.path.join(config_dir, "**/versions/version.ts")] if config_dir else [])
      + [os.path.expanduser("~/.claude/**/liangzai/**/versions/version.ts")]
      for f in glob.glob(p, recursive=True)]
plugin_version = "unknown"
if vt:
    m = re.search(r"DEFAULT_VERSION\s*=\s*['\"](v[\S]+)['\"]", open(vt[0], encoding="utf-8").read())
    plugin_version = m.group(1) if m else "unknown"
```

### 9b. Patch CLAUDE.md idempotently

Read `CLAUDE.md` at the workspace root (create if absent). Replace everything between the
markers, or append the block if the markers aren't present:

```
<!-- BEGIN agents/liangzai.md (embedded by liangzai-setup) -->
<!-- liangzai plugin: {plugin_version} | embedded: {embed_date} -->

{body}

<!-- END agents/liangzai.md -->
```

Embed the **content**, not a path reference, so the workspace is self-contained for
scheduled runs and fresh clones. Re-running setup or upgrading the agent just refreshes
the block. Surface any write failure now, before Step 10.

## Step 10 — Schedule & hand over

Create two Cowork Scheduled Tasks:

| Task | When | Runs |
|---|---|---|
| Weekly capture | Sunday, 08:00 SGT | `/supplier-invoice-manager capture` then `/cost-optimizer capture-sales` |
| Monthly close | 6th, 09:00 SGT | `/supplier-invoice-manager reconcile` then `/cost-optimizer monthly` |

The monthly job runs on the **6th** because SOAs land by the 4th. Then tell the owner in
one short message: what runs, when, what lands in the Sheet, and that **nothing is ever
paid automatically** — every flagged item and every payment goes through him.
