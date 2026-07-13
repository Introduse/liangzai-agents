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

All six checks are read-only. Run them, then tag each item **present / missing / stale**.

| # | Item | How to check | Reads as missing when |
|---|---|---|---|
| 1 | Gateway connector + key | **`liangzai_ping`** | Anything other than `pong` — the connector isn't installed, or the key is wrong |
| 2 | Local Google token | Look for `GMAIL_REFRESH_TOKEN` in the workspace `.claude/settings.local.json` (the local invoice download needs it; the gateway has its own copy) | Key absent or empty |
| 3 | Sheet tabs | **`liangzai_init_sheet`** with `dry_run: true` — it inspects the live Sheet and returns `present` and `missing` | `missing` is non-empty. `agent_config` in `missing` means this setup predates the gateway |
| 4 | Outlet map | **`liangzai_get_config`** — `outlets_configured` / `outlets_count` | `outlets_configured: false`, or `outlets_count` is not 6 |
| 5 | Bowl definition | **`liangzai_get_config`** — same call as #4 — `bowl_confirmed` | `bowl_confirmed: false` (unset, or set but never confirmed by the owner) |
| 6 | Schedule | **`liangzai_get_config`** — same call again — `schedule_confirmed` | `schedule_confirmed: false`. Any setup done before plugin v0.5.0 has no schedule recorded, so this will fire on every older install — that is correct, not a false alarm |
| 7 | CLAUDE.md embed | Does the workspace `CLAUDE.md` contain the `BEGIN/END agents/liangzai.md` block, and is its stamped version the one from Step 0? | Block absent, or stamped version is older |

Notes:
- **#4, #5 and #6 are one `liangzai_get_config` call**, not three. It writes nothing.
- If `liangzai_get_config` errors with an unknown-tool error, the user is on an old
  gateway deployment — the fix is redeploying the gateway, not anything in this repo.
- Don't use `liangzai_compute_cost_per_bowl` as a probe. It's expensive and its refusal
  only tells you about the bowl definition, which #5 already answers directly.
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
| Local Google token | **liangzai-setup Step 3** (`google_oauth.py`) |
| Sheet tabs | **`liangzai_init_sheet`** (no `dry_run`) — creates only the missing tabs and styles only those; it never restyles a tab the user has already edited |
| Outlet map | **`liangzai_loyverse_stores`** with `write_config: true` |
| Bowl definition | **liangzai-setup Step 6** — `liangzai_bowl_checklist`, review the item list **with the owner**, then `liangzai_set_bowl_definition` with `confirmed_by_owner: true`. Never confirm it on the owner's behalf |
| Schedule | **liangzai-setup Step 10** — ask him for the weekday/time and day-of-month/time, `liangzai_set_schedule`, then walk him through creating the two Cowork tasks. Recording the schedule is not the same as creating the tasks; do both, and don't pick the cadence for him |

## Step 4 — Refresh the CLAUDE.md embed (if stale or missing)

If Step 0 found the embed missing or on an older version, re-run **liangzai-setup Step 9**:
locate `agents/liangzai.md`, strip its frontmatter, and replace the block between the
`BEGIN/END agents/liangzai.md` markers in the workspace `CLAUDE.md`. Stamp the Step 0
version into the marker so the next `plugin-update` can compare. This refreshes the agent
identity without disturbing anything the user added manually.

## Step 5 — Re-validate & record

Re-run only the Step 1 checks whose gaps you filled — `liangzai_ping` after a reconnect,
`liangzai_init_sheet` with `dry_run: true` after creating tabs (expect `missing: []`),
`liangzai_get_config` after writing the outlet map, bowl definition, or schedule. Then
confirm in one short message what was filled and what was already current. A clean run
reports "everything is up to date".
