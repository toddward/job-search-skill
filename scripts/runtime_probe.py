#!/usr/bin/env python3
"""Print the runtime mode for SKILL.md injection. No shell expansion in output."""
from __future__ import annotations
import os, sys
import common

INTERACTIVE = {"cli", "vscode", "jetbrains", "desktop"}
UNSAFE_CHARS = ("$", "`", "\\", "\n")

def _safe(s: str) -> str:
    """Neutralize a value before it goes into the printed line: a `$` or backtick surviving
    into a `!`-injected result silently aborts the whole skill invocation (see references/headless.md)."""
    return "<unsafe-path>" if any(c in s for c in UNSAFE_CHARS) else s

def probe() -> dict:
    entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "unset")
    mode = "interactive" if entry in INTERACTIVE else "headless"
    forced = os.environ.get("JOBSEARCH_FORCE_MODE")
    if forced in ("interactive", "headless"):
        mode = forced
    home, source = common.data_home_info()
    return {"mode": mode, "entrypoint": entry, "os": common.host_os(), "tty": sys.stdin.isatty() and sys.stdout.isatty(),
            "home": str(home), "home_source": source, "python": sys.version.split()[0]}

if __name__ == "__main__":
    p = probe()
    print(f"mode={p['mode']} entrypoint={_safe(p['entrypoint'])} os={p['os']} home={_safe(p['home'])} "
          f"home_source={p['home_source']} python={_safe(p['python'])}")
