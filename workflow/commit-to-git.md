Please commit to git by following these steps (do not use DEV for versioning as this is PRODUCTION):

Check git status to ensure clean working directory
Check today's date
Create/Update version in versions/version.ts and ensure to update:
DEFAULT_VERSION
DEFAULT_DATE (current date)
VERSION_HISTORY
Bump the SAME version in all THREE places — they drifted once (version.ts said v0.4.2
while both manifests still said 0.4.0) and the skills read the manifest, not version.ts:
  versions/version.ts                        DEFAULT_VERSION (vX.Y.Z, with the leading v)
  plugins/liangzai/.claude-plugin/plugin.json  "version" (X.Y.Z) — the ONLY one that ships
                                               with the installed plugin; plugin-update
                                               Step 0 and setup Step 9a both read it
  .claude-plugin/marketplace.json              "version" in BOTH metadata and plugins[0]
Confirm nothing sensitive is staged — this repository is PUBLIC:
  git ls-files | grep -E '^\.claude/|^cache/|^fixtures/|^\.venv|_audit|bowl_checklist\.(json|md)'
  must return nothing. `.claude/settings.local.json` holds the Loyverse token and the
  Google refresh tokens; `cache/` and `fixtures/` hold supplier invoices; the bowl
  checklist holds the owner's real per-dish sales volumes. None of it may be published.
Use git add . to stage all changes
Commit with descriptive message that starts with the version number
Git push origin
Add tag (after commit is pushed)
Git push the tag to git
