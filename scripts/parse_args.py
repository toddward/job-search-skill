#!/usr/bin/env python3
"""Parse the /job-search $ARGUMENTS string into a normalized JSON intent."""
from __future__ import annotations
import json, re, shlex, sys

COMMANDS = {"scan", "pick", "select", "no", "snooze", "show", "status", "unhide", "submit", "setup", "apply", "help"}
BOOL_FLAGS = {"headless", "no-tailor", "apply", "no-apply", "i-mean-it", "dry-run", "json"}
VALUE_FLAGS = {"from", "run", "max", "query", "note", "reason", "home", "to", "duration"}
NUM_RE = re.compile(r"^(\d+|[0-9a-f]{6,16}(-\d+)?|M\d+|S\d+)$", re.I)
URL_RE = re.compile(r"^https?://", re.I)

def _split(argstr: str) -> list[str]:
    try:
        return shlex.split(argstr)
    except ValueError:
        return argstr.split()

def parse(argstr: str) -> dict:
    raw = (argstr or "").strip()
    out = {"command": "help", "numbers": [], "reason": None, "flags": {}, "query": None, "url": None, "raw": raw}
    toks = _split(raw)
    if not toks:
        return out
    head = toks[0].lower()
    if head not in COMMANDS:
        out["command"] = "scan"
        # strip trailing flags from a free-text query
        q, flags = [], {}
        i = 0
        while i < len(toks):
            t = toks[i]
            if t.startswith("--"):
                name = t[2:]
                if name in VALUE_FLAGS and i + 1 < len(toks):
                    flags[name] = toks[i + 1]; i += 2; continue
                flags[name] = True
            else:
                q.append(t)
            i += 1
        out["query"] = " ".join(q) or None
        out["flags"] = flags
        return out
    out["command"] = "pick" if head == "select" else head
    i = 1
    positionals = []
    while i < len(toks):
        t = toks[i]
        if t.startswith("--"):
            name = t[2:]
            if name in VALUE_FLAGS and i + 1 < len(toks) and not toks[i + 1].startswith("--"):
                out["flags"][name] = toks[i + 1]; i += 2; continue
            out["flags"][name] = True
        else:
            positionals.append(t)
        i += 1
    for p in positionals:
        if URL_RE.match(p):
            out["url"] = p
        elif "," in p and all(NUM_RE.match(x) for x in p.split(",") if x):
            out["numbers"].extend([x for x in p.split(",") if x])
        elif NUM_RE.match(p) and out["command"] != "unhide":
            out["numbers"].append(p)
        elif out["command"] == "snooze" and re.match(r"^\d+[dwm]$", p):
            out["flags"]["duration"] = p
        elif out["command"] == "unhide":
            out["numbers"].append(p)
        elif out["command"] == "scan":
            out["query"] = (out["query"] + " " + p) if out["query"] else p
        else:
            out["reason"] = (out["reason"] + " " + p) if out["reason"] else p
    if out["flags"].get("reason"):
        out["reason"] = out["flags"]["reason"]
    if out["flags"].get("query"):
        out["query"] = out["flags"]["query"]
    return out

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    print(json.dumps(parse(" ".join(argv)), ensure_ascii=False))

if __name__ == "__main__":
    main()
