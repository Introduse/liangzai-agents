---
name: plugin-update
description: >-
  Bring an existing Liang Zai setup up to date after the plugin is upgraded — detects
  what changed since the last setup and fills only the gaps, idempotently. Use after
  a plugin update, or when a skill reports a missing connector, key, token, Sheet tab,
  bowl definition, or CLAUDE.md embed. Says "update", "upgrade", "catch up", "what's
  missing", "plugin-update".
area: Setup
use_for: "Idempotent catch-up after a plugin upgrade: re-check the gateway connector, local Google token, Sheet tabs, outlet map, bowl definition, and the workspace CLAUDE.md embed; fill only what's missing."
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
| Re-asks known data | Yes | No — reuses what's on disk |

## Step 0 — Version gap

- Read the installed plugin version from `versions/version.ts` (`DEFAULT_VERSION`).
- Read the version stamped in the workspace `CLAUDE.md` embed marker
  (`<!-- liangzai plugin: vX.Y.Z … -->`). If missing, treat the CLAUDE.md embed as a gap.
- If the two differ, the agent definition changed → Step 4 will refresh the embed.

## Step 1 — Detect current state (read-only, no prompts)

Inspect each item and tag it **present / missing / stale**:

| # | Item | How to check |
|---|---|---|
| 1 | Gateway connector + key | Call **`liangzai_ping`**. `pong` = present; error = missing/invalid |
| 2 | Local Google token | `GMAIL_REFRESH_TOKEN` present in `.claude/settings.local.json` (needed by the local download) |
| 3 | Sheet tabs | Call **`liangzai_init_sheet`** with `dry_run: true` — it lists which tabs exist vs would be created |
| 4 | Outlet map | Call **`liangzai_loyverse_stores`** (no write) — confirms the token and that 6 stores resolve |
| 5 | Bowl definition | Call **`liangzai_compute_cost_per_bowl`** with `dry_run: true` — a `bowl_definition_unconfirmed` error means it's missing |
| 6 | CLAUDE.md embed | Does the workspace `CLAUDE.md` contain the `agents/liangzai.md` block, and is its version current (Step 0)? |

Do not fix anything yet — just look.

## Step 2 — Gap report

Show a compact summary: what's present, what's missing, what's stale. Then ask once:
"Want me to fill these now?" Nothing is written until the user says yes.

## Step 3 — Fill only the gaps

For each gap, delegate to the matching `/liangzai-setup` step — never touch what's already
complete:

- Gateway connector / key missing → **liangzai-setup Step 2**.
- Local Google token missing → **liangzai-setup Step 3** (`google_oauth.py`).
- Sheet tabs missing → call **`liangzai_init_sheet`** (idempotent — creates only what's absent).
- Outlet map missing → **`liangzai_loyverse_stores`** with `write_config: true`.
- Bowl definition unconfirmed → **liangzai-setup Step 6** (`bowl_checklist` → `set_bowl_definition`).

## Step 4 — Refresh the CLAUDE.md embed (if stale or missing)

If Step 0 found the embed missing or on an older version, re-run **liangzai-setup Step 9**:
locate `agents/liangzai.md`, strip its frontmatter, and replace the block between the
`BEGIN/END agents/liangzai.md` markers in the workspace `CLAUDE.md`. Stamp the current
plugin version into the marker so the next `plugin-update` can compare. This refreshes the
agent identity every session without disturbing anything the user added manually.

## Step 5 — Re-validate & record

Re-test only what Step 3 touched (e.g. `liangzai_ping` after a reconnect, `init_sheet
dry_run` after creating tabs). Then confirm to the user, in one short message, what was
filled and what was already current. A clean run reports "everything is up to date".
