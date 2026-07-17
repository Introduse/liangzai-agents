---
name: plugin-update
description: >-
  Bring an existing Liang Zai setup up to date after the plugin is upgraded — detects
  what changed since the last setup and fills only the gaps, idempotently. Use after
  a plugin update, or when a skill reports a missing connector or tool, key, token,
  Sheet tab, outlet map, bowl definition, scheduled task, recipient allowlist, or
  CLAUDE.md embed. Says "update", "upgrade", "catch up", "what's missing",
  "plugin-update".
area: Setup
use_for: "Idempotent catch-up after a plugin upgrade: re-check the gateway connector (including a STALE cached tool list), Google credentials, Sheet tabs, outlet map, bowl definition, Cowork scheduled tasks, recipient allowlist, and the workspace CLAUDE.md embed; fill only what's missing."
---

# Plugin Update — catch an existing setup up to the latest version

The user already ran `/liangzai-setup` at some earlier version, and the plugin has since
changed. Your job is to **detect what's missing or stale** and fill **only those gaps** —
never re-run a step that's already complete. This skill is **idempotent**: a second run
in a row should report "nothing to do".

If nothing has ever been set up (no gateway connector, no `.claude/settings.local.json`),
stop and tell the user to run **`/liangzai-setup`** first.

## How this differs from liangzai-setup

| | liangzai-setup | plugin-update |
|---|---|---|
| When | First run | After an upgrade / when something's missing |
| Writes | Everything | Only the gaps |
| Re-asks known data | Yes | No — reuses what's already stored |

## Step 0 — Version gap

- Read the installed plugin version from **`${CLAUDE_PLUGIN_ROOT}/.claude-plugin/plugin.json`**
  (the `version` field). That file ships with the plugin; the repo's `versions/version.ts`
  does **not** — don't reach for it, it won't be there on a real install.
- Read the version stamped in the workspace `CLAUDE.md` embed marker
  (`<!-- liangzai plugin: vX.Y.Z … -->`). If the marker is missing, treat the CLAUDE.md
  embed as a gap.
- If the two differ, the agent definition may have changed → Step 4 refreshes the embed.

## Step 1 — Detect current state (read-only, no prompts)

All the checks below are read-only. Run them, then tag each item **present / missing / stale**.

| # | Item | How to check | Reads as missing when |
|---|---|---|---|
| 1 | Gateway connector + key | **`liangzai_ping`** | Anything other than `pong` — the connector isn't installed, or the key is wrong |
| 2 | Connector is not **stale** | Compare the `liangzai_*` tools you can actually see against the tool table in `agents/liangzai.md`. The gateway advertises every tool in that table | A tool from the table is missing from your tool list. That means the connector cached an old tool list — **the fix is to reconnect it** (Settings → Connectors → remove `gateway`, add it again), NOT a change to the gateway. Never report a missing tool as a gateway gap without checking this first. After a plugin upgrade this is the FIRST thing to check: `liangzai_daily_sales` (newest), `liangzai_logged_attachments`, `liangzai_list_suppliers` and `liangzai_merge_suppliers` are all recent, and an old connector will simply not show them |
| 3 | Google credentials | Look for `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` and `SHEETS_REFRESH_TOKEN` in the workspace `.claude/settings.local.json`. The local invoice download needs them, and every `liangzai_*` call sends them to the gateway — see `agents/liangzai.md` | Any of the four is absent or empty |
| 4 | Sheet tabs | **`liangzai_init_sheet`** with `dry_run: true` — it inspects the live Sheet and returns `present` and `missing` | `missing` is non-empty. `agent_config` in `missing` means this setup predates the gateway |
| 5 | Tabs are well-formed | **You cannot probe this read-only** — no tool reads an arbitrary tab. It surfaces on the next real write: gateway v0.11.0 REFUSES to write when row 1 of a tab is not the header, and names the tab | A `liangzai_append_*` call errors with `REFUSING to write`. That tab was written by the pre-v0.11.0 gateway, which could push the header below the data. Note it here so the owner isn't surprised by it later |
| 6 | Outlet map | **`liangzai_get_config`** — `outlets_configured` / `outlets_count` | `outlets_configured: false`, or `outlets_count` is not 6 |
| 7 | Bowl definition | **`liangzai_get_config`** — the same call as #6 — `bowl_confirmed` | `bowl_confirmed: false` (unset, or set but never confirmed by the owner) |
| 8 | Scheduled tasks | Open Cowork's **Scheduled** page (or ask him to) and look for `Liang Zai · Weekly capture` and `Liang Zai · Monthly close`. **No gateway tool can answer this** — Cowork owns the schedule, so this is the only place it can be seen | Either task is absent. An install predating plugin v0.8.0 may have neither |
| 9 | CLAUDE.md embed | Does the workspace `CLAUDE.md` contain the `BEGIN/END agents/liangzai.md` block, and is its stamped version the one from Step 0? | Block absent, or stamped version is older |
| 10 | Recipient allowlist | Look for `SUMMARY_RECIPIENTS` in `.claude/settings.local.json` (sent on every `liangzai_send_summary` / `liangzai_send_run_report` call) | Key absent or empty |
| 11 | Sheet id recorded | Look for `SPREADSHEET_ID` in `.claude/settings.local.json` — it is sent on every Sheet call and points the gateway at this owner's Sheet | Key absent or empty. Not always fatal — see the note below — but recording it is the normal path now |

Notes:
- **#11 (`SPREADSHEET_ID`) is only *fatal* when the gateway's own env lacks it too.** The
  gateway falls back to a Vercel `SPREADSHEET_ID` when the client sends none, so an older
  install with nothing in `settings.local.json` may still be working off that fallback. Record
  it locally anyway: it makes the setup self-contained and stops it depending on gateway-side
  config the owner can't see. If Sheet calls currently succeed, treat a missing #11 as a
  recommended fill, not a broken setup.
- **#6 and #7 are one `liangzai_get_config` call**, not two. It writes nothing. #8 is NOT
  one of them — the schedule lives in Cowork and the gateway cannot see it.
- If a `liangzai_*` tool comes back as unknown, **check #2 before blaming the gateway.**
  A cached connector tool-list is the common cause and is fixed by reconnecting; an
  actually-old deployment is rare. Reporting a stale connector as a "gateway gap" sends
  someone to change code that is already correct.
- Don't use `liangzai_compute_cost_per_bowl` as a probe. It's expensive and its refusal
  only tells you about the bowl definition, which #7 already answers directly.
- Don't fix anything yet — just look.

## Step 2 — Gap report

Show a compact summary: present, missing, stale. Then ask once: "Want me to fill these
now?" Nothing is written until the user says yes.

## Step 3 — Fill only the gaps

For each gap, delegate to the matching `/liangzai-setup` step — never touch what's already
complete:

| Gap | Fill with |
|---|---|
| Gateway connector / key | **liangzai-setup Step 2** |
| Google credentials | **liangzai-setup Steps 3g–3h** — `google_oauth.py --auth-url`, he signs in and pastes back the URL he lands on, then `google_oauth.py --exchange "<url>"`. There is no bare invocation any more; running the script with no flag just errors. The whole Google Cloud console walk (3a–3f) is only needed if the OAuth **client** is gone too — if `GOOGLE_CLIENT_ID` is already in `settings.local.json`, the client exists and you only need to re-mint the token |
| Sheet id (`SPREADSHEET_ID`) | **liangzai-setup Step 4a** — ask the owner for the *Invoice log and Cost tracker* Sheet link, take the id from the `/d/<id>/edit` segment, and write `SPREADSHEET_ID` into `.claude/settings.local.json`. Do this **before** the Sheet-tabs fill below, so `liangzai_init_sheet` targets the right Sheet |
| Sheet tabs | **`liangzai_init_sheet`** (no `dry_run`) — creates only the missing tabs and fully styles only those, so it never stomps formatting the owner has changed. It DOES ensure the 状态 Status dropdown on the tabs that already exist: that is a data contract, not decoration |
| Outlet map | **`liangzai_loyverse_stores`** with `write_config: true` |
| Bowl definition | **liangzai-setup Step 6** — `liangzai_bowl_checklist`, classify each **dish** with the rule there (a meal is a bowl; packaging, drinks, add-ons, sides, staff meals are not), submit the **`bowl_refs`** of the bowl dishes (the gateway expands each ref into every Loyverse id behind that dish), and show him the finished classification. Don't put the taxonomy question to him, and don't confirm it without showing him |
| Scheduled tasks | **liangzai-setup Step 10** — ask him for the weekday/time and day-of-month/time, then create the two tasks with Cowork's **`/schedule`**. There is no gateway tool for this and there must not be: Cowork owns the schedule. Don't pick the cadence for him |
| Recipient allowlist | **liangzai-setup Step 3i** — ask who should receive the emails and write `SUMMARY_RECIPIENTS` into `.claude/settings.local.json` |
| Statements misfiled into `invoice_log` | Installs before plugin v0.11.0 wrote Statements of Account into `invoice_log` as junk `needs_review` rows — and reconciliation does NOT filter on status, so they are reconciled anyway and invent a variance. If `invoice_log` holds rows whose supplier is really a statement header, or rows with no line items, delete them: the next capture re-logs the real invoices, deduped, and files the statements where they belong |

## Step 4 — Refresh the CLAUDE.md embed (if stale or missing)

If Step 0 found the embed missing or on an older version, re-run **liangzai-setup Steps
9a–9b**: locate `agents/liangzai.md` and strip its frontmatter (9a), then replace the
block between the `BEGIN/END agents/liangzai.md` markers in the workspace `CLAUDE.md` —
**prepending** it if the markers are absent entirely, never appending, so the agent
identity leads the file rather than trailing whatever else is there (9b). Stamp the Step
0 version into the marker so the next `plugin-update` can compare. This refreshes the
agent identity without disturbing anything the user added manually.

**Verify:** read `CLAUDE.md` back and confirm the stamp matches the Step 0 version, and
that a string unique to the current `agents/liangzai.md` body appears inside the markers
(liangzai-setup Step 9c). If it doesn't, the body wasn't actually replaced — retry before
reporting this gap as filled.

## Step 5 — Re-validate & record

Re-run only the Step 1 checks whose gaps you filled — `liangzai_ping` after a reconnect
(and re-check #2: the reconnected connector should now show every tool in the table),
`liangzai_init_sheet` with `dry_run: true` after creating tabs (expect `missing: []`),
`liangzai_get_config` after writing the outlet map or bowl definition. Then confirm in one
short message what was filled and what was already current. A clean run reports
"everything is up to date".
