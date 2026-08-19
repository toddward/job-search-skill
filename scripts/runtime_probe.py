#!/usr/bin/env python3
"""Print the runtime mode for SKILL.md injection. No shell expansion in output."""
from __future__ import annotations
import os, sys
import common

INTERACTIVE = {"cli", "vscode", "jetbrains", "desktop"}

def probe() -> dict:
    entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "unset")
    mode = "interactive" if entry in INTERACTIVE else "headless"
    forced = os.environ.get("JOBSEARCH_FORCE_MODE")
    if forced in ("interactive", "headless"):
        mode = forced
    return {"mode": mode, "entrypoint": entry, "os": common.host_os(), "tty": sys.stdin.isatty() and sys.stdout.isatty(),
            "home": str(common.data_home()), "python": sys.version.split()[0]}

if __name__ == "__main__":
    p = probe()
    print(f"mode={p['mode']} entrypoint={p['entrypoint']} os={p['os']} home={p['home']} python={p['python']}")
