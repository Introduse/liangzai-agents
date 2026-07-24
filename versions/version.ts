// Version information (production)
// Keep in lockstep with plugins/liangzai/.claude-plugin/plugin.json and
// .claude-plugin/marketplace.json — the skills read the manifest, not this file.
const DEFAULT_VERSION = 'v0.14.1';
const DEFAULT_DATE = 'Jul 24, 2026';

// Export constants initially with default values
export const APP_VERSION = DEFAULT_VERSION;
export const RELEASE_DATE = DEFAULT_DATE;

// NOTE: Keep only last 15 versions to prevent git overload (following Next.js pattern)
// Full history available in GitHub releases and git commits
export const VERSION_HISTORY: Array<{ version: string; date: string; changes: string[] }> = [
  {
    version: 'v0.14.1',
    date: 'Jul 24, 2026',
    changes: [
      'Found by reading all eleven changed files top to bottom after v0.14.0 was tagged, rather than trusting that ~30 individual edits had left each file coherent. The consistency tests check across files; they cannot tell you a paragraph stopped making sense once three edits landed in it.',
      'supplier-invoice-manager opened with "Both modes write. Neither may write the same thing twice — see The dedupe" — the exact claim the same release had rewritten that section to retract. Writing twice is now structurally impossible; the reason not to re-read is cost, and that a hurried second reading overwrites a careful first one. The forward reference now says what the section it points at says. Its use_for said "Every append is deduped" for the same stale reason.',
      'agents/liangzai.md gave the capture flow as "skip what is already logged → download → classify", but the skill downloads first and calls liangzai_pending_documents second — and must, because the queue is filled from the append side and cannot know about an attachment nobody has downloaded. The identity is what gets embedded into CLAUDE.md, so it was the copy more likely to be followed.',
      'google_oauth.py\'s new docstring paragraph broke a path across a line inside backticks, rendering as `.claude/settings.` / `local.json`. Reworded so it does not need to.',
      'README said "one credential is also kept locally" when five values are; and its status line still read v0.4.0, from before any of this. It now names the version and the one thing that actually gates a working install: the gateway cannot send an email until Step 3j has put the credentials in its Vault.',
      'plugin-update\'s fill table numbered some gaps (#N) and not others — half a convention introduced in v0.14.0. All eight now carry their checklist number, and the test that validates those references no longer skips table lines, which is why nothing caught it the first time.',
    ],
  },
  {
    version: 'v0.14.0',
    date: 'Jul 24, 2026',
    changes: [
      'FINISHES v0.13.0. That release moved the credentials server-side in the agent identity and the setup skill, but left supplier-invoice-manager and cost-optimizer — the two skills that actually run every week — still instructing the agent to read the Google credentials out of .claude/settings.local.json and send them on every call, pointing at a credential table the same release had deleted. Both now say what the identity says: gateway_api_key is the only argument, and a tool still advertising spreadsheet_id means a stale connector.',
      'NEW liangzai-setup Step 3j — hand the credentials to the gateway. Nothing ever wrote to Vault. Setup minted the Google token locally and stopped, while Step 8 validated with liangzai_list_credentials and plugin-update flagged the same five names as gaps whose fill instructions only wrote locally: detect, "fill", re-check, still missing, forever. 3j stores google_client_id, google_client_secret, gmail_refresh_token, supplier_mailbox and summary_recipients with liangzai_store_credential, and names loyverse_access_token as the one nobody here can supply. The local copy stays, because download_invoices.py still runs on the owner\'s machine — two copies of one credential, for two jobs, said in those words.',
      'liangzai_store_credential and liangzai_list_credentials added to the tool table in agents/liangzai.md. They shipped with the gateway\'s Phase 0a and were never listed, so the table that plugin-update check #2 uses as its stale-connector oracle was two tools short — and both skills were calling tools the identity said did not exist.',
      'The dedupe doctrine is rewritten around the reason that is now true. It argued from a source_ref ending in the line INDEX, so a reordered second pass logged the same money twice with no error anywhere. Gateway Phase 1 replaced that with (invoice_id, line_no): a re-sent document REPLACES what was recorded for it, and the double-count is structurally impossible. The rule survives — skip what is already recorded — but because re-reading costs tokens and a hurried second reading OVERWRITES a careful first one. Statements got the same fix, and it matters more there: a doubled statement total does not look like a bug, it looks like a supplier dispute.',
      'capture-sales now says it records revenue as well as quantities. Gateway Phase 1 started writing per-stall daily revenue, which nothing had ever recorded; cost-optimizer still described item quantities only, and still called the table sales_daily. Since liangzai_daily_sales also deals in revenue now, the skill spells out the difference: one answers a question he asked, the other writes the day down before Loyverse\'s 30-day window closes it.',
      'Corrections carried in from the gateway spec: the summary email links to /reconcile?period=…, not a Sheet tab, and that screen is still being built — say so rather than talking him through a page that is not there. An unresolved outlet is a null with the printed text kept as evidence, not the UNASSIGNED sentinel. An ambiguous supplier is queued and deliberately NOT registered, so the same invoice re-raises it every run — report it once, then say it is still waiting on him. A merge now moves the invoices themselves, so re-running reconciliation after one is not optional. Duplicate invoice numbers and near-duplicate untitled invoices go to needs-review.',
      'The Google Sheets API and the auth/spreadsheets scope are no longer requested, and google_oauth.py no longer writes SHEETS_REFRESH_TOKEN — it was always the same physical token as GMAIL_REFRESH_TOKEN, and there is no Sheet left to address. The script now ends by pointing at Step 3j, because minting the token locally is only half of what setup needs.',
      'plugin-update separates the two credential questions that an upgraded install answers differently: #3 is what the gateway holds in Vault, #9 is what download_invoices.py needs locally. Finding a value in settings.local.json says nothing about whether the gateway has it — which is precisely the state every pre-v0.14.0 install is in. Also fixed: a note pointing at check #7 for the bowl definition, left over from the v0.13.0 renumber (it is #5), and a misfiled-statements cleanup that told the agent to delete rows it has no tool to delete.',
      'NEW tests/test_consistency.py — 14 unit tests, no dependencies. This repo ships instructions rather than code, so its characteristic bug is drift that nothing can fail on: the gateway changes, some skills are updated, one is not. The tests assert that the agent\'s tool table IS the gateway\'s tool list exactly, that no prose names a tool that does not exist or a retired one without marking it retired, that retired vocabulary stays retired, that no skill tells the agent to send credentials, that the three version fields move together, and that cross-references between skills point at steps that exist. Each was mutation-checked against the v0.13.0 defects it is meant to catch — one of them failed that check first time (the credential pattern excluded "." and so missed "settings.local.json", the exact line it was written for) and was fixed.',
    ],
  },
  {
    version: 'v0.13.0',
    date: 'Jul 24, 2026',
    changes: [
      'The gateway moved to Postgres and deleted its Google Sheet layer (gateway Phase 1), so this release stops the plugin telling the owner to set up things that no longer exist. liangzai-setup Step 4 recorded a spreadsheet_id and called liangzai_init_sheet to create seven tabs; both are gone — the schema is migrations, applied once at install. The step is kept as a numbered placeholder so every cross-reference to Steps 5-10 still lines up.',
      'agents/liangzai.md no longer sends credentials. The gateway holds its own in Supabase Vault, so gateway_api_key is now the ONLY argument the agent supplies. The identity says so explicitly, and adds the tell: a tool still advertising spreadsheet_id or sheets_refresh_token means a STALE connector, and the fix is to reconnect rather than to fill the field in.',
      'liangzai_logged_attachments is replaced by liangzai_pending_documents in supplier-invoice-manager. The dedupe rule is unchanged and the wire format is identical (gmail_msg_id:attachment_id in `processed`), so the skill reads the same way — but it now also reports what is QUEUED and what FAILED, which is what Phase 2 fills. Recorded alongside it: the gateway now REPLACES a re-sent document rather than appending a copy, so a genuine correction is safe. That is a safety net, not a licence to skip the skip.',
      'liangzai_loyverse_stores loses write_config. The six stalls are seeded server-side, and letting Loyverse overwrite our outlet names would be dangerous — that name is the key every historical row is filed under. The tool now checks by STORE ID (a renamed stall is cosmetic; a stall the token cannot see is a silent hole in the sales data) and reports renames without acting on them.',
      'plugin-update rewritten around what can now actually be checked: liangzai_list_credentials replaces hunting for Google keys in settings.local.json, the Sheet-tabs and Sheet-id checks are deleted, and the stale-connector check names liangzai_pending_documents — seeing the OLD tool name is itself proof the connector is stale.',
    ],
  },
  {
    version: 'v0.12.0',
    date: 'Jul 18, 2026',
    changes: [
      'Surfaced the gateway\'s new liangzai_daily_sales tool to the agent: added it to the tool table in agents/liangzai.md (which plugin-update reads as the complete list), gave cost-optimizer a "daily sales (live snapshot, ad hoc)" mode so "how much did we sell today?" routes there, and named it as the newest tool in plugin-update\'s stale-connector check. It answers a revenue question (per-outlet SGD, today included), distinct from cost-per-bowl, and is read-only.',
      'The target Sheet id is now recorded client-side. liangzai-setup Step 4 records SPREADSHEET_ID into .claude/settings.local.json (4a) before creating the tabs (4b), and agents/liangzai.md sends spreadsheet_id on every Sheet call alongside the Google credentials. The gateway falls back to its own Vercel SPREADSHEET_ID only when no argument is sent, so the setup no longer depends on a value the owner can\'t see. plugin-update gained detection (#11) and a fill step for it, with the note that a missing local id is only fatal when the gateway env lacks it too.',
    ],
  },
  {
    version: 'v0.11.1',
    date: 'Jul 17, 2026',
    changes: [
      'liangzai-setup Step 9b\'s CLAUDE.md embed now PREPENDS instead of appending when the BEGIN/END markers are absent, matching the fix adana-skills-library made to adana-setup (v0.2.4): the agent identity must lead the file, not trail whatever else is there. Replaced the prose-only instruction with actual code, including the same `lambda m: new_block` re.sub guard that avoids backslash-interpretation corruption when replacing between existing markers.',
      'New Step 9c explicitly verifies the embed after writing — confirms the version stamp and a body-unique string actually landed — instead of trusting the write silently succeeded.',
      'plugin-update Step 4 updated to match: prepend-not-append is now explicit, and it verifies the refreshed embed via the new liangzai-setup Step 9c rather than assuming the write worked.',
    ],
  },
  {
    version: 'v0.11.0',
    date: 'Jul 13, 2026',
    changes: [
      'Weekly capture and monthly close now split cleanly: weekly classifies each mailbox attachment and logs only invoices, leaving statements for month end; monthly logs the statements plus any straggler invoice, then reconciles.',
      'New gateway tool liangzai_logged_attachments — call it before extracting anything, skip every attachment it names. This is the document-level dedupe that guards against the row-level source_ref key drifting when a re-extraction reorders or merges lines.',
      'supplier-invoice-manager and agents/liangzai.md now spell out the invoice-vs-statement classification rule after a real run misfiled a Statement of Account into invoice_log — reconciliation does not filter on status, so a misfiled statement invents a variance that is not real.',
      'plugin-update gained a check for tabs the pre-v0.11.0 gateway could have corrupted (header not in row 1) and renumbered its checklist accordingly.',
    ],
  },
  {
    version: 'v0.10.0',
    date: 'Jul 13, 2026',
    changes: [
      'Suppliers now register themselves, so the first real invoice run stops flagging EVERY row. The gateway\'s supplier list held three fixture names and none of the owner\'s real ones, with no way to add one short of an engineer editing JSON and redeploying. Gateway v0.11.0 learns a supplier on first sight, keyed on the sender\'s email domain — a supplier can typo their letterhead, not their mail server.',
      'supplier-invoice-manager: capture now REPORTS newly registered suppliers rather than asking about them ("12 invoices logged. 3 new suppliers registered: … — nothing needed from you"). That is information, not a decision.',
      'The one case the agent must NOT decide, and the skill says why: a known supplier NAME arriving from an UNKNOWN email address. That is either their outsourced billing agent or a different company with a similar name — identical to a machine, obvious to the owner. Creating a supplier is safe (worst case, a visible duplicate); MERGING two is not (it adds two companies\' money together and the total still looks plausible). Register freely, merge never.',
      'reconcile: check merge_suggestions BEFORE explaining anything. A company that invoices from one address and sends statements from another becomes two suppliers, and BOTH halves read as unmatched — which looks like a supplier problem and is actually ours. The skill now surfaces it first, because it explains rows that otherwise look inexplicable.',
      'agents/liangzai.md: added liangzai_list_suppliers and liangzai_merge_suppliers. Amended the "never guess a supplier or outlet" rule, which was no longer true: the gateway now REGISTERS an unknown supplier automatically, and still never MERGES one without the owner saying so.',
      'docs/suppliers.md (new): why the supplier name is a join key and not a label, why a split silently breaks reconciliation, what registers automatically, and what genuinely needs a human. Generic — no client names or figures; the repo is public.',
      'Requires gateway v0.11.0, which also fixes the Sheet-corruption bug from the owner\'s first live run (data written above the header, retries behaving differently, rows inheriting the header\'s dark fill — all one bug: Google\'s values.append was guessing where the rows went). The connector must be reconnected: two new tools.',
    ],
  },
  {
    version: 'v0.9.0',
    date: 'Jul 13, 2026',
    changes: [
      'Setup Step 6 now classifies dishes and submits REFS (d001…), not Loyverse item_ids. The checklist was costing ~32,500 tokens a call — by far the most expensive thing in the onboarding — because it shipped ~200 UUIDs the model never reads and only hands back, plus the same 132 dishes rendered three separate ways. Gateway v0.10.0 returns short refs and expands them itself. Now ~4,700 tokens: -85.6%, measured on the live catalogue.',
      'The rule for what counts as a bowl is UNCHANGED, and that is the point. A differential test (gateway `npm run bowl:diff`) runs both the old and new paths over one live receipt snapshot and asserts they produce the identical bowl definition — 42 item_ids across 22 bowl dishes, exactly equal. The token cut buys nothing if it changes the answer.',
      'Step 6 tells the agent to classify against the list it was JUST given: a ref is a handle into that checklist, not a permanent name. Re-run the checklist and you must re-classify against the fresh one. Passing an unknown ref is a hard error rather than a silent skip — a dropped ref would remove that dish\'s bowls from the denominator, permanently and invisibly, and push its cost per bowl up while looking perfectly reasonable.',
      'Step 6 also tells the agent to read two fields it now gets: `names` (present only when one dish sold under several spellings — if those spellings are clearly different dishes, the grouping is wrong and it should say so rather than classify it) and the `ids`/`outlets` counts (a bowl dish showing one outlet where you would expect six is worth a second look).',
      'agents/liangzai.md: liangzai_bowl_checklist now WRITES (it saves the ref→id map to agent_config) and returns refs; liangzai_set_bowl_definition takes bowl_refs. The doc has always said "the owner never sees an id" — this is what finally makes it true of the model as well.',
      'docs/bowls-sold.md: the pipeline section rewritten for refs, including WHY the ref map is a snapshot and never recomputed on confirm — the 30-day window rolls, receipts land between the checklist and the confirmation, and a re-derived ref could resolve to a different set of ids than the one that was agreed to. Still free of live figures; the repo is public.',
      'Requires gateway v0.10.0. The tool schemas changed, so the connector must be reconnected — exactly the stale-connector case plugin-update check #2 catches.',
    ],
  },
  {
    version: 'v0.8.0',
    date: 'Jul 13, 2026',
    changes: [
      'Scheduling now uses Cowork\'s OWN scheduled-task system. Setup Step 10 invokes /schedule rather than reading UI instructions aloud, and nothing records the cadence anywhere else. Gateway v0.9.0 dropped liangzai_set_schedule to match: Cowork owns the schedule, fires the jobs and lists them, so a copy in the Sheet was a second source of truth that went stale the first time he edited a task — and a stale copy that is written down looks authoritative.',
      'plugin-update gained a STALE-CONNECTOR check (#2), which is what prompted all of this. A connected client reported liangzai_set_schedule as "missing from the gateway" and concluded it was a gateway gap — but the gateway was advertising it fine; the connector had cached an old tool list. The check now compares the tools you can actually see against the table in agents/liangzai.md, and says plainly: a missing tool means RECONNECT THE CONNECTOR, not change the gateway. Without it, a cached tool list sends someone to fix code that is already correct.',
      'plugin-update check #7 (scheduled tasks) is answered by looking at Cowork\'s Scheduled page — no gateway tool can answer it, and the skill says so rather than inviting the agent to hunt for one.',
      'FIXED in agents/liangzai.md: the credential table said liangzai_bowl_checklist needs no credentials because it "reads Loyverse rather than the Sheet". It does read the Sheet — agent_config, to label each item with the outlet that sold it — so omitting them made the gateway fall back to the SERVER\'s Sheet. liangzai_ping is now correctly the only tool needing none. (Gateway v0.9.0 carries the matching fix.)',
      'FIXED in setup Step 3e: it still described the OAuth loopback server ("hands the code back to a tiny local server on that port") after v0.6.0 replaced it with the paste-back flow. It now says nothing is listening on 5179, and that the page failing to load IS the handoff — the one thing an owner will otherwise read as failure.',
      'FIXED in the setup preamble: it still claimed the gateway holds the Google credentials. Since v0.6.0 they are this machine\'s, in .claude/settings.local.json, and travel with every call; the gateway holds only the Loyverse token and the spreadsheet id.',
      'plugin-update stale cross-references cleaned up: its notes still said "#4, #5 and #6 are one get_config call" after #6 became the Cowork check, and its bowl-definition fill row still told the agent to re-open the classification with the owner, which v0.7.0 had deliberately removed.',
      'Requires gateway v0.9.0.',
    ],
  },
  {
    version: 'v0.7.0',
    date: 'Jul 13, 2026',
    changes: [
      'Setup Step 6 no longer interrogates the owner about what a bowl is. He sells noodles; he does not think in taxonomies, and asking him to rule on whether a side dish counts as "a bowl" invents a decision he never had. The rule is now HARDCODED in the skill — a meal is a bowl; packaging, drinks, à la carte add-ons, sides, staff meals and fee lines are not — and the agent applies it and shows him the finished classification once. He can correct it in a sentence; that is the only input he gives.',
      'Step 6 now classifies DISHES and submits every item_id behind each one (needs gateway v0.8.0, which groups the checklist by dish). The same bowl of noodles is a different Loyverse item_id at each of the six stalls and is spelled differently too, so ticking a dish but submitting one stall\'s id makes that outlet\'s bowls vanish from the denominator forever — and its cost per bowl then reads too high while looking perfectly reasonable. The skill says this in those words.',
      'Exclusions are checked BEFORE inclusions, and Step 6 says why: an "add noodles" side contains the word noodles and defeats any rule that only looks for noodle names. The packaging charge is the highest-volume line in the catalogue and would roughly double the bowl count if it slipped through.',
      'cost-optimizer: "What counts as a bowl" rewritten to point at the rule rather than re-open the classification with the owner, and to note that `monthly` is step 2 of the monthly close, never its own scheduled task — compute_cost_per_bowl reads the reconciliation tab, so firing it independently could publish a plausible-looking cost against a stale or empty basis.',
      'docs/bowls-sold.md (new): how bowls sold per outlet is determined — the two traps in real POS data (one dish, many item_ids; the packaging charge outselling every dish), the rule, the pipeline, the confirmation gate, and what the number is NOT (not "cost per bowl", never grossed up, and not a per-dish cost — the denominator splits by dish but the numerator does not). Written generically, with no figures or names from the live catalogue, since this repo is public.',
    ],
  },
  {
    version: 'v0.6.0',
    date: 'Jul 13, 2026',
    changes: [
      'The plugin now OWNS the Google and mailer credentials rather than borrowing the gateway\'s. Gateway v0.7.0 accepts them as per-call arguments, so agents/liangzai.md now tells the agent to read GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET and SHEETS_REFRESH_TOKEN out of .claude/settings.local.json and send them on every Sheet-touching call — plus GMAIL_REFRESH_TOKEN, SUPPLIER_MAILBOX and SUMMARY_RECIPIENTS on liangzai_send_summary and liangzai_send_run_report. liangzai_ping needs none; liangzai_bowl_checklist reads Loyverse rather than the Sheet, so it needs none either.',
      'Never omit a credential argument to "let the gateway handle it". The gateway falls back to its own env when an argument is missing, which means a silently-omitted token does not fail loudly — it quietly reads or writes whatever Sheet and mailbox the SERVER is configured for, which may not be the owner\'s. agents/liangzai.md says this in those words.',
      'setup Step 3i (new): collect SUMMARY_RECIPIENTS from the owner and save it locally. It was previously handed to Five Bucks to set in Vercel and never stored here. It is the allowlist that stands between a bug and an email landing at a supplier — from the mailbox those suppliers write to — so the setup now asks for it explicitly and keeps it to the owner.',
      'setup Step 3 retitled from "Google access for downloads": downloads are now the minor use of those credentials, since every gateway call carries them.',
      'plugin-update gained an 8th check (recipient allowlist) and its check #2 widened from "local Google token" to all four Google credentials, since every one of them now travels to the gateway. Its "All six checks" line was also miscounting a seven-row table before this.',
      'OAuth rewrite (was uncommitted from an earlier session, shipped here): google_oauth.py drops the loopback HTTP server for two commands — --auth-url prints the sign-in link, --exchange "<url>" takes the redirect URL out of the owner\'s address bar. The old flow needed a free port, a browser that could reach it, and a terminal held open for five minutes. The "This site can\'t be reached" page IS the handoff — Google puts the code nowhere but that address bar — and setup Step 3g now warns him of that in advance, because an owner who is not expecting it assumes he broke something and stops.',
    ],
  },
  {
    version: 'v0.5.1',
    date: 'Jul 13, 2026',
    changes: [
      'Setup Step 2 now gives the gateway URL literally (https://liangzai-gateway.vercel.app/api/mcp) instead of "the liangzai gateway address (ends in /api/mcp)". The address is fixed and already committed in .mcp.json, so the vague wording was a blank the owner — a hawker operator, not an engineer — had no way to fill in, and Step 2 blocks every later step.',
    ],
  },
  {
    version: 'v0.5.0',
    date: 'Jul 13, 2026',
    changes: [
      'Setup Step 10 is now an interview, not a hard-coded table. It asks the owner which weekday/time he wants the weekly capture and which day-of-month/time he wants the monthly close, records the answer with liangzai_set_schedule, and only then walks him through creating the two Cowork tasks. It refuses a monthly day below 5 (SOAs land by the 4th — reconciling earlier checks invoices against statements that have not arrived) and above 28 (no such day in February).',
      'The monthly close is scheduled DAILY with a date guard on the first line of the prompt, because Cowork\'s frequency picker has no monthly option — only hourly, daily, weekly, weekdays, manual. The guard exits immediately on the other ~29 days. Removing it would run the close every single day.',
      'Every scheduled run now emails the owner via liangzai_send_run_report, including the runs with nothing to report. Cowork tasks only fire while his machine is on, and Loyverse serves only 30 days of receipts, so a weekly capture that silently stops destroys that month\'s sales data — and a clean run looks exactly like a dead one from the outside. Step 10 tells him, in his words, that a missing email means something is wrong.',
      'Cost-per-bowl is documented as step 2 of the monthly close and never its own scheduled task: it reads the reconciliation tab, so firing it independently could publish a plausible-looking cost against a stale or empty basis.',
      'plugin-update gained a 6th check — Schedule — off the same single liangzai_get_config call. Any install predating this version has no schedule recorded and will now say so.',
      'FIXED: setup Step 9a read the plugin version from versions/version.ts, which sits OUTSIDE plugins/liangzai/ and therefore never ships with the installed plugin — so the CLAUDE.md marker was always stamped "unknown" and plugin-update could never detect a stale embed. It now reads .claude-plugin/plugin.json, the only version file that installs.',
      'FIXED version drift: plugin.json and marketplace.json were still on 0.4.0 while version.ts said v0.4.2, because the commit process only ever bumped version.ts. All three now move together, and workflow/commit-to-git.md says so.',
      'agents/liangzai.md tool table was missing liangzai_get_config entirely; added it plus liangzai_set_schedule and liangzai_send_run_report.',
      'Requires gateway v0.6.0 for liangzai_set_schedule, liangzai_send_run_report, and schedule in liangzai_get_config.',
    ],
  },
  {
    version: 'v0.4.2',
    date: 'Jul 13, 2026',
    changes: [
      'Setup fix (found during a real run): Step 3 never told you to register the OAuth redirect URI, so Google rejected the sign-in with redirect_uri_mismatch. Step 3 now walks the Google Cloud console end to end and calls out adding http://localhost:5179 under Authorized redirect URIs as mandatory, with a troubleshooting note.',
      'google_oauth.py now prints the required redirect URI alongside the consent link, so the fix is visible at the exact moment you would hit the error.',
    ],
  },
  {
    version: 'v0.4.1',
    date: 'Jul 11, 2026',
    changes: [
      'Rewrote the README in the gateway house pattern (status line, architecture, skills table, guarantees, install, gateway link). Fixed a few over-capitalised "the owner" mid-sentence artifacts from the client-scrub pass.',
    ],
  },
];
