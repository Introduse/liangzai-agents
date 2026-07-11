#!/usr/bin/env python3
"""Credential loading for Claude Cowork.

Cowork stores credentials in `.claude/settings.local.json` under the `env`
object. Scheduled and automated runs do NOT inject them into the environment
automatically, so every entry point must call `load_credentials()` before
reading any env var.

Stdlib only.
"""
import json
import os
from pathlib import Path


def load_credentials():
    """Walk up from cwd (then from this file) looking for .claude/settings.local.json
    and copy its `env` block into os.environ. Existing env vars always win.

    Returns True if a settings file was found.
    """
    roots = [Path.cwd(), Path(__file__).resolve().parent]
    for root in roots:
        for p in [root] + list(root.parents):
            settings_file = p / ".claude" / "settings.local.json"
            if settings_file.exists():
                data = json.loads(settings_file.read_text())
                for k, v in data.get("env", {}).items():
                    if not os.environ.get(k):
                        os.environ[k] = str(v)
                return True
    return False


def read_env(key, required=False):
    """Read an env var, loading Cowork credentials first."""
    if not os.environ.get(key):
        load_credentials()
    val = os.environ.get(key)
    if required and not val:
        raise SystemExit(
            f"{key} is not set. Add it to .claude/settings.local.json under \"env\"."
        )
    return val
