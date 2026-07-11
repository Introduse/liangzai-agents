// Version information (production)
const DEFAULT_VERSION = 'v0.4.0';
const DEFAULT_DATE = 'Jul 11, 2026';

// Export constants initially with default values
export const APP_VERSION = DEFAULT_VERSION;
export const RELEASE_DATE = DEFAULT_DATE;

// NOTE: Keep only last 15 versions to prevent git overload (following Next.js pattern)
// Full history available in GitHub releases and git commits
export const VERSION_HISTORY: Array<{ version: string; date: string; changes: string[] }> = [
  {
    version: 'v0.4.0',
    date: 'Jul 11, 2026',
    changes: [
      'Public-ready: scrubbed all client identifiers (mailbox, supplier names/domains, outlet addresses, owner name) to generic placeholders; renamed the tool arg confirmed_by_adrian -> confirmed_by_owner in step with the gateway',
      'Aligned onboarding with the fiveagents brand-setup approach: a `-- project created` re-run argument, a settings step (bypass-permissions + domain allowlist), a validate step, and — most importantly — Step 9 embeds agents/liangzai.md into the workspace CLAUDE.md between markers so every session (incl. scheduled runs) auto-loads the agent',
      'Added a plugin-update skill: an idempotent catch-up runner that detects gaps (gateway connector, local token, Sheet tabs, outlet map, bowl definition, CLAUDE.md embed) since the last setup and fills only what is missing',
      'Integration audit fixes: setup now runs init_sheet before loyverse_stores write_config (agent_config must exist first); invoice example documents the optional subtotal; local scripts invoked via ${CLAUDE_PLUGIN_ROOT} so the path resolves regardless of cwd; download_invoices reference updated to the gateway tool',
    ],
  },
  {
    version: 'v0.3.0',
    date: 'Jul 11, 2026',
    changes: [
      'Restructured into a Claude plugin marketplace (.claude-plugin/marketplace.json + plugins/liangzai/). The reconciliation engine, capture guards, cost math, and all Google/Loyverse/Sheets I/O moved to the private liangzai-gateway remote MCP server; the three skills now call its liangzai_* tools',
      'Only two scripts stay local: download_invoices.py (the Gmail connector cannot fetch attachment bytes) and google_oauth.py (one-time token consent)',
      'Retired the server-side Python. It is preserved at tag python-source-final, and the gateway was proven bit-exact against it by a differential harness (340k+ cases) before removal',
    ],
  },
  {
    version: 'v0.2.0',
    date: 'Jul 10, 2026',
    changes: [
      'Three skills: liangzai-setup (first-run onboarding), supplier-invoice-manager (capture + reconcile), cost-optimizer (sales capture + cost/bowl)',
      'OAuth client must be INTERNAL. gmail.readonly is a Google *restricted* scope — an external client needs a paid annual third-party security assessment, and staying in "Testing" to avoid that caps refresh tokens at 7 days, so the weekly job would run once and die silently. your-workspace.example is Workspace, so an Internal client is exempt from verification, the test-user cap, and the expiry.',
      'Added gmail.send (merely "sensitive", not restricted) so the summary sends from ai@example.com — the From: line the proposal promised',
      'mailer.py enforces a hard SUMMARY_RECIPIENTS allowlist and fails closed: the agent holds send access on the mailbox suppliers write to, and must never email one',
      'reconcile_core.py: money compared as integer cents, so float noise cannot manufacture a phantom variance. Matched requires exactly zero. A missing SOA is SOA_MISSING, never Matched. Equal totals with mismatched invoice numbers still flag. No Approved or Paid status exists.',
      'canon.py never guesses: an unresolved supplier or an ambiguous delivery line becomes needs_review, because a mis-attributed outlet corrupts that outlet\'s cost/bowl while the totals still reconcile',
      'append_invoice_log.py checks each invoice\'s line sum against its own printed total — an invoice can lose a line and still look well-formed. Unreadable invoices still write a needs_review row carrying the gmail_msg_id.',
      'compute_cost_per_bowl.py refuses to publish while bowl_definition.confirmed_by_owner is false, writes days_covered so partial months cannot masquerade as full ones, and names unresolved suppliers in cost_basis_note',
      'send_summary.py: bilingual branded email, flagged rows lead, "nothing approved or paid" footer in both languages, cost/bowl withheld rather than guessed',
      'init_sheet.py creates the five tabs with bilingual headers in Liang Zai\'s palette, and doubles as proof the consented account can actually write',
      'test_contract.py — 24 executable assertions covering every promise that would otherwise break quietly',
    ],
  },
  {
    version: 'v0.1.0',
    date: 'Jul 10, 2026',
    changes: [
      'Initial liangzai-agents — Supplier Invoice Manager + Cost Optimizer for Liang Zai Prawn Noodle (Free Build of the Week)',
      'Loyverse token verified: 6 stores, names match the owner\'s list exactly; mapped in config/outlets.json',
      'Found Loyverse free-plan wall — receipts older than 31 days return HTTP 402. The proposal\'s monthly-lookback job would have failed on its first real run. Replaced with accumulate-forward: the weekly run records sales to sales_daily, the monthly run tallies it. Every read stays inside 30 days, on the free plan.',
      'sales_daily stores net quantity PER ITEM, not a bowl count — Loyverse can never be re-read beyond 30 days, so a stored bowl count would permanently bake in today\'s bowl definition',
      'Bowl definition keyed on item_id, not item_name: the same dish is named differently at every outlet, and the highest-volume line item (打包 Takeaway) is a $0.30 packaging charge. 42 items, 22,118 bowls/30d, 1.19 per receipt — pending the owner\'s confirmation',
      'Bilingual Sheet + summary email ("中文 English"), in Liang Zai\'s palette extracted from the Chinese proposal PDF',
      'Google helpers on gmail.readonly + spreadsheets — the MCP connectors can neither download attachment bytes nor append rows',
      'Dev fixtures: 36 mock invoices across 3 supplier layouts + 3 matching SOAs, with a S$12.60 injected variance Reconcile must flag',
    ],
  },
];
