---
name: plugin-update
description: >-
  Bring an existing Liang Zai setup up to date after the plugin is upgraded — detects
  what changed since the last setup and fills only the gaps, idempotently. Use after
  a plugin update, or when a skill reports a missing connector or tool, key, token,
  credential, bowl definition, scheduled task, recipient allowlist, or
  CLAUDE.md embed. Says "update", "upgrade", "catch up", "what's missing",
  "plugin-update".
area: Setup
use_for: "Idempotent catch-up after a plugin upgrade: re-check the gateway connector (including a STALE cached tool list), the gateway's Vault credentials, whether the mailbox poller is actually running, the six stalls, bowl definition, Cowork scheduled tasks, recipient allowlist, and the workspace CLAUDE.md embed; fill only what's missing."
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
| 2 | Connector is not **stale** | Compare the `liangzai_*` tools you can actually see against the tool table in `agents/liangzai.md`. The gateway advertises every tool in that table | A tool from the table is missing from your tool list. That means the connector cached an old tool list — **the fix is to reconnect it** (Settings → Connectors → remove `gateway`, add it again), NOT a change to the gateway. Never report a missing tool as a gateway gap without checking this first. After a plugin upgrade this is the FIRST thing to check: `liangzai_poll_mailbox`, `liangzai_document_content` and `liangzai_mark_document` (the newest three — without them the whole capture flow has nowhere to go), `liangzai_store_credential` and `liangzai_list_credentials` (without which #3 cannot be checked OR filled), and `liangzai_pending_documents` (which REPLACED `liangzai_logged_attachments` — seeing the old name is itself proof of a stale connector). Seeing `liangzai_init_sheet` at all is the same proof: it was deleted |
| 3 | Gateway credentials | **`liangzai_list_credentials`** — names only, never values. The gateway holds its own credentials in Vault now; nothing is sent on a call | `google_client_id`, `google_client_secret`, `gmail_refresh_token`, `supplier_mailbox`, `summary_recipients` or `loyverse_access_token` is missing from the list. **An install from before v0.14.0 will show most of these missing** — it wrote them only to `.claude/settings.local.json`, and nothing ever copied them across. That is the single most likely gap on an upgraded setup |
| 4 | The six stalls | **`liangzai_get_config`** — `outlets_configured` / `outlets_count` | `outlets_count` is not 6. They are seeded at install, so this failing means the database was never seeded |
| 5 | Bowl definition | **`liangzai_get_config`** — the same call as #4 — `bowl_confirmed` | `bowl_confirmed: false` (unset, or set but never confirmed by the owner) |
| 6 | Scheduled tasks | Open Cowork's **Scheduled** page (or ask him to) and look for `Liang Zai · Weekly capture` and `Liang Zai · Monthly close`. **No gateway tool can answer this** — Cowork owns the schedule, so this is the only place it can be seen | Either task is absent. An install predating plugin v0.8.0 may have neither |
| 7 | CLAUDE.md embed | Does the workspace `CLAUDE.md` contain the `BEGIN/END agents/liangzai.md` block, and is its stamped version the one from Step 0? | Block absent, or stamped version is older |
| 8 | Recipient allowlist | Covered by #3 — `summary_recipients` in `liangzai_list_credentials`. It is the allowlist that stops the agent ever emailing a supplier, and it is gateway-side now rather than something a caller supplies | Absent from the list |
| 9 | The mailbox queue is being filled | **`liangzai_pending_documents`** — read `last_poll`, not `pending`. The gateway polls the mailbox server-side now | `last_poll` is null (it has never polled), its `status` is `failed`, or it is more than a couple of days old. An install from before v0.15.0 was fetching mail locally and will show null. Confirm with **`liangzai_poll_mailbox`** `{dry_run: true}`, which writes nothing |

Notes:
- **#4 and #5 are one `liangzai_get_config` call**, not two. It writes nothing. #6 is NOT
  one of them — the schedule lives in Cowork and the gateway cannot see it.
- **`.claude/settings.local.json` is no longer a gap check.** Since v0.15.0 the gateway
  fetches the mail itself, so the only local values anything reads are `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET` and `OAUTH_ACCOUNT` — and only `google_oauth.py` reads them, only
  while re-minting a token. If #3 is complete, nothing on this machine is needed at all and
  their absence is not a gap. Look at the file for one reason only: it is the cheapest place
  to fill #3 from on an upgraded install (Step 3). A `GMAIL_REFRESH_TOKEN` or
  `SUPPLIER_MAILBOX` still sitting there from an older setup has no reader — leave it or
  delete it, but never report it as a gap and never send the owner off to refill it.
- **#3 and #9 are different questions.** #3 is whether the gateway *has* the Google
  credentials; #9 is whether it is *using* them against the mailbox. An install can pass #3
  and fail #9 — that is exactly the state a pre-v0.15.0 setup is in the moment it upgrades.
- If a `liangzai_*` tool comes back as unknown, **check #2 before blaming the gateway.**
  A cached connector tool-list is the common cause and is fixed by reconnecting; an
  actually-old deployment is rare. Reporting a stale connector as a "gateway gap" sends
  someone to change code that is already correct.
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
| Gateway connector / key (#1, #2) | **liangzai-setup Step 2** |
| Gateway credentials (#3) | **liangzai-setup Step 3j** — `liangzai_store_credential`, once per service. If the values are already in `.claude/settings.local.json` (the usual case on an upgrade), this is a copy, not a re-consent: read each one and store it. Only if a value is missing locally too do you need Steps 3g–3h to re-mint the token first — `google_oauth.py --auth-url`, he signs in and pastes back the URL he lands on, then `google_oauth.py --exchange "<url>"`, which **prints** the token for you to store. That needs `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` and `OAUTH_ACCOUNT` present locally; the full Google Cloud console walk (3a–3f) is only needed if the OAuth **client** itself is gone. **`loyverse_access_token` is not fillable from here** — Five Bucks seeds it gateway-side; report it and stop |
| The mailbox queue (#9) | Nothing to install — the poller is gateway-side. If `last_poll` is null on an upgraded setup, it simply has never been called: run **`liangzai_poll_mailbox`** `{days: 14}` once to prime the queue and say how many documents it found. If it fails on a credential, the real gap is #3 — fix that first, then come back. If it keeps failing after #3 is complete, report it to Five Bucks: the daily cron is gateway-side too and neither you nor the owner can configure it from here |
| The six stalls (#4) | Nothing to fill from here — they are seeded server-side. `liangzai_loyverse_stores` only CHECKS that the Loyverse token can see all six |
| Bowl definition (#5) | **liangzai-setup Step 6** — `liangzai_bowl_checklist`, classify each **dish** with the rule there (a meal is a bowl; packaging, drinks, add-ons, sides, staff meals are not), submit the **`bowl_refs`** of the bowl dishes (the gateway expands each ref into every Loyverse id behind that dish), and show him the finished classification. Don't put the taxonomy question to him, and don't confirm it without showing him |
| Scheduled tasks (#6) | **liangzai-setup Step 10** — ask him for the weekday/time and day-of-month/time, then create the two tasks with Cowork's **`/schedule`**. There is no gateway tool for this and there must not be: Cowork owns the schedule. Don't pick the cadence for him |
| Recipient allowlist (#8) | **liangzai-setup Steps 3i–3j** — ask who should receive the emails, then store it with **`liangzai_store_credential`** (`service: summary_recipients`). Write-only: it never reads a value back |
| Statements misfiled as invoices | Installs before plugin v0.11.0 logged Statements of Account as junk `needs_review` invoices — and reconciliation does NOT filter on status, so they are reconciled anyway and invent a variance. **You cannot clean this up from here**: there is no tool that deletes an invoice, and the screen that will is still being built. Report it — name the month and the supplier — and leave it. Re-running reconciliation will keep producing that phantom variance until it is removed, so say that too, rather than letting him read it as a supplier problem |

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
`liangzai_list_credentials` after storing one, `liangzai_get_config` after confirming the
bowl definition, `liangzai_pending_documents` after priming the queue (`last_poll` should
now be recent). Then confirm in one short message what was filled and what was already
current. A clean run reports "everything is up to date".

**Report what you could not fill, separately and plainly** — a missing
`loyverse_access_token`, misfiled statements, a reconciliation screen that isn't built
yet. Those are not gaps he can close and not gaps you can close; folding them into
"everything is up to date" is how they stay invisible.
