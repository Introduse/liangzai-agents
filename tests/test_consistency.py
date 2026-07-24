#!/usr/bin/env python3
"""Consistency tests for the plugin's prose.

This repository ships almost no code. What it ships is instructions a model
follows, and its characteristic bug is DRIFT: the gateway changes, some of the
skills are updated to match, and one is not. v0.13.0 renamed a tool and moved
the credentials server-side, but left two skills still telling the agent to send
credentials that no longer exist as arguments — nothing failed, because nothing
here can fail. It just quietly instructed the agent to do the wrong thing.

So these tests assert the things a reader would otherwise have to hold in their
head across nine files:

  * every liangzai_* tool named anywhere is one the gateway actually has
  * the tool table in the agent identity IS the gateway's tool list, exactly —
    plugin-update uses it as the stale-connector oracle, so a table that drifts
    makes that check lie in both directions
  * retired vocabulary (the Sheet, spreadsheet_id, sales_daily, …) stays gone
  * the three version fields move together
  * cross-references between skills point at steps that exist

Run: python3 -m unittest discover -s tests -v      (no dependencies)

WHEN THE GATEWAY CHANGES, EDIT GATEWAY_TOOLS FIRST. It is the local mirror of
liangzai-gateway's lib/tools/liangzai.ts, and everything else is checked against
it. Verified against gateway Phase 1 (24 Jul 2026).
"""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "liangzai"
AGENT = PLUGIN / "agents" / "liangzai.md"
SKILLS = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
PROSE = [AGENT, ROOT / "README.md", *SKILLS]

# The gateway's registered tools, as of Phase 1. Mirror of lib/tools/liangzai.ts.
GATEWAY_TOOLS = {
    "liangzai_append_invoice_log",
    "liangzai_append_soa_entries",
    "liangzai_bowl_checklist",
    "liangzai_capture_sales",
    "liangzai_compute_cost_per_bowl",
    "liangzai_daily_sales",
    "liangzai_get_config",
    "liangzai_list_credentials",
    "liangzai_list_suppliers",
    "liangzai_loyverse_stores",
    "liangzai_merge_suppliers",
    "liangzai_pending_documents",
    "liangzai_ping",
    "liangzai_run_reconciliation",
    "liangzai_send_run_report",
    "liangzai_send_summary",
    "liangzai_set_bowl_definition",
    "liangzai_store_credential",
}

# Tools the gateway used to have. Naming one as if it were live is the bug this
# catches; each may still appear in prose that explicitly marks it as retired.
RETIRED_TOOLS = {
    "liangzai_init_sheet",
    "liangzai_logged_attachments",
    "liangzai_set_schedule",
}

# `liangzai_live_…` is the API key prefix, not a tool. It is the only other thing
# in this repo that looks like one.
TOOL_RE = re.compile(r"liangzai_(?!live_)[a-z_]+")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


class ToolSurface(unittest.TestCase):
    """Every tool named in prose exists; the identity table is the full list."""

    def agent_table_tools(self):
        """Tools listed in the agent identity's `| tool | does |` table."""
        rows = re.findall(r"^\|\s*`(liangzai_[a-z_]+)`\s*\|", read(AGENT), re.M)
        return set(rows)

    def test_agent_table_matches_gateway_exactly(self):
        table = self.agent_table_tools()
        self.assertEqual(
            table,
            GATEWAY_TOOLS,
            "\nThe tool table in agents/liangzai.md must list the gateway's tools "
            "EXACTLY — plugin-update check #2 compares a live tool list against it "
            "to detect a stale connector, so a missing row makes a healthy "
            "connector look stale and an extra row hides a real gap."
            f"\n  missing from the table: {sorted(GATEWAY_TOOLS - table)}"
            f"\n  in the table but not the gateway: {sorted(table - GATEWAY_TOOLS)}",
        )

    def test_no_prose_names_a_tool_that_does_not_exist(self):
        for path in PROSE:
            for tool in set(TOOL_RE.findall(read(path))):
                if tool in RETIRED_TOOLS:
                    continue  # covered by test_retired_tools_only_appear_as_history
                self.assertIn(
                    tool,
                    GATEWAY_TOOLS,
                    f"\n{rel(path)} names `{tool}`, which the gateway does not "
                    "have. The agent will call it and get 'unknown tool'.",
                )

    def test_retired_tools_only_appear_as_history(self):
        """A retired name may be explained, never instructed."""
        for path in PROSE:
            for line in read(path).splitlines():
                for tool in RETIRED_TOOLS:
                    if tool not in line:
                        continue
                    marks_it_dead = re.search(
                        r"REPLACED|replaced|deleted|DELETED|retired|used to|"
                        r"no longer|old name|OLD tool|deliberately no",
                        line,
                    )
                    self.assertTrue(
                        marks_it_dead,
                        f"\n{rel(path)} mentions the retired tool `{tool}` without "
                        "marking it retired:\n  " + line.strip(),
                    )

    def test_every_gateway_tool_is_documented_somewhere(self):
        """A tool nobody mentions is a tool the agent will never use."""
        mentioned = set()
        for path in PROSE:
            mentioned |= set(TOOL_RE.findall(read(path)))
        self.assertEqual(
            set(),
            GATEWAY_TOOLS - mentioned,
            f"\nundocumented: {sorted(GATEWAY_TOOLS - mentioned)}",
        )


class RetiredVocabulary(unittest.TestCase):
    """The Sheet era left vocabulary behind. It must not read as current."""

    # term -> what makes a mention legitimate on that line
    RETIRED = {
        r"\bSPREADSHEET_ID\b": r"retired|no longer|used to|deleted|gone",
        r"\bSHEETS_REFRESH_TOKEN\b": r"retired|no longer|used to|deleted|gone",
        r"\bsales_daily\b": r"retired|no longer|used to|deleted|gone",
        r"\bagent_config\b": r"retired|no longer|used to|deleted|gone",
        r"\bUNASSIGNED\b": r"retired|no longer|used to|deleted|gone",
        r"\bsource_ref\b": r"retired|no longer|used to|deleted|gone",
        r"\bthe Sheet\b": r"retired|no longer|used to|deleted|gone|Sheet is gone",
        r"\bthe tracking Sheet\b": r"retired|no longer|used to|deleted|gone",
        r"\bGoogle Sheets? API\b": r"retired|no longer|used to|deleted|gone|Earlier versions",
    }

    def test_retired_terms_are_absent_or_marked(self):
        for path in PROSE:
            for lineno, line in enumerate(read(path).splitlines(), 1):
                for term, escape in self.RETIRED.items():
                    if not re.search(term, line):
                        continue
                    self.assertTrue(
                        re.search(escape, line),
                        f"\n{rel(path)}:{lineno} uses retired term {term!r} as if "
                        f"current:\n  {line.strip()}",
                    )

    def test_no_skill_tells_the_agent_to_send_credentials(self):
        """The single defect v0.13.0 shipped: two skills still said to send them."""
        # The gap between the two halves must allow '.', because the sentence this
        # exists to catch reads "...credentials from `.claude/settings.local.json`,
        # on every call" — an earlier version of this pattern excluded '.' and
        # therefore missed the exact line it was written for.
        bad = re.compile(
            r"(credentials|GOOGLE_CLIENT|refresh token)[^\n]{0,80}?"
            r"(on every|with every|and pass|passes them|send them|sent with)",
            re.I,
        )
        for path in PROSE:
            for lineno, line in enumerate(read(path).splitlines(), 1):
                m = bad.search(line)
                if m and not re.search(r"no longer|used to|never|stop|not what", line, re.I):
                    self.fail(
                        f"\n{rel(path)}:{lineno} instructs the agent to send "
                        f"credentials on a gateway call. Only gateway_api_key "
                        f"travels now.\n  {line.strip()}"
                    )


class Versions(unittest.TestCase):
    """Three files carry the version and they drifted once already."""

    def test_all_three_agree(self):
        marketplace = json.loads(read(ROOT / ".claude-plugin" / "marketplace.json"))
        plugin = json.loads(read(PLUGIN / ".claude-plugin" / "plugin.json"))
        version_ts = read(ROOT / "versions" / "version.ts")

        default = re.search(r"DEFAULT_VERSION = 'v([\d.]+)'", version_ts).group(1)
        self.assertEqual(default, plugin["version"], "version.ts vs plugin.json")
        self.assertEqual(
            default, marketplace["metadata"]["version"], "version.ts vs marketplace metadata"
        )
        self.assertEqual(
            default,
            marketplace["plugins"][0]["version"],
            "version.ts vs marketplace plugins[0] — this is the one that drifted",
        )

    def test_history_leads_with_the_current_version(self):
        version_ts = read(ROOT / "versions" / "version.ts")
        default = re.search(r"DEFAULT_VERSION = 'v([\d.]+)'", version_ts).group(1)
        first = re.search(r"version: 'v([\d.]+)'", version_ts).group(1)
        self.assertEqual(default, first, "VERSION_HISTORY[0] is not the current version")

    def test_dates_agree(self):
        version_ts = read(ROOT / "versions" / "version.ts")
        default_date = re.search(r"DEFAULT_DATE = '([^']+)'", version_ts).group(1)
        first_date = re.search(r"date: '([^']+)'", version_ts).group(1)
        self.assertEqual(default_date, first_date)


class CrossReferences(unittest.TestCase):
    """Skills delegate to each other by step number. The numbers must exist."""

    def setup_steps(self):
        text = read(PLUGIN / "skills" / "liangzai-setup" / "SKILL.md")
        top = {m.group(1) for m in re.finditer(r"^## Step (\d+)", text, re.M)}
        sub = {m.group(1) for m in re.finditer(r"^### (\d+[a-z])\.", text, re.M)}
        return top | sub

    def test_referenced_setup_steps_exist(self):
        steps = self.setup_steps()
        ref = re.compile(r"(?:liangzai-)?[Ss]etup Steps? (\d+[a-z]?)(?:[–-](\d+[a-z]?))?")
        for path in PROSE:
            for lineno, line in enumerate(read(path).splitlines(), 1):
                for m in ref.finditer(line):
                    for step in filter(None, m.groups()):
                        self.assertIn(
                            step,
                            steps,
                            f"\n{rel(path)}:{lineno} points at liangzai-setup Step "
                            f"{step}, which does not exist.\n  {line.strip()}",
                        )

    def test_plugin_update_checklist_references_resolve(self):
        """`#N` in the notes must name a row that exists in the table above."""
        text = read(PLUGIN / "skills" / "plugin-update" / "SKILL.md")
        rows = {m.group(1) for m in re.finditer(r"^\| (\d+) \|", text, re.M)}
        self.assertTrue(rows, "no checklist rows found — did the table format change?")
        for lineno, line in enumerate(text.splitlines(), 1):
            if line.startswith("|"):
                continue  # the table itself
            for ref in re.findall(r"#(\d+)", line):
                self.assertIn(
                    ref,
                    rows,
                    f"\nplugin-update:{lineno} refers to check #{ref}, which is not "
                    f"a row in the table (rows: {sorted(rows, key=int)}).\n  {line.strip()}",
                )


class Manifests(unittest.TestCase):
    def test_json_is_valid(self):
        for p in [
            ROOT / ".claude-plugin" / "marketplace.json",
            PLUGIN / ".claude-plugin" / "plugin.json",
            PLUGIN / ".mcp.json",
            PLUGIN / "settings.json",
        ]:
            with self.subTest(file=rel(p)):
                json.loads(read(p))

    def test_skills_have_required_frontmatter(self):
        for skill in SKILLS:
            with self.subTest(skill=rel(skill)):
                text = read(skill)
                self.assertTrue(text.startswith("---\n"), "missing frontmatter")
                fm = text.split("---", 2)[1]
                for key in ("name:", "description:", "use_for:"):
                    self.assertIn(key, fm, f"frontmatter missing {key}")
                name = re.search(r"^name: (.+)$", fm, re.M).group(1).strip()
                self.assertEqual(
                    name,
                    skill.parent.name,
                    "frontmatter name must match the skill's directory",
                )

    def test_business_name_is_consistent(self):
        """Six stalls trade as 靓仔大虾面; the business is Liang Zai Kitchen."""
        for path in PROSE:
            self.assertNotIn(
                "Liang Zai Prawn Noodle",
                read(path),
                f"\n{rel(path)} says 'Liang Zai Prawn Noodle'. The business is "
                "Liang Zai Kitchen (靓仔私房菜).",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
