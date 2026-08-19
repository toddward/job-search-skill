#!/usr/bin/env python3
"""Scheduler entrypoint: run `/job-search <sub> --headless` via `claude -p` with a lock and a run log. macOS + Linux."""
from __future__ import annotations
import json, os, shutil, subprocess, sys, uuid
from pathlib import Path
import common, config

def acquire(lock: Path) -> bool:
    try:
        lock.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        pidf = lock / "pid"
        try:
            pid = int(pidf.read_text().strip()); os.kill(pid, 0)
            return False
        except (OSError, ValueError):
            shutil.rmtree(lock, ignore_errors=True); lock.mkdir(parents=True, exist_ok=True)
    (lock / "pid").write_text(str(os.getpid())); return True

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    sub = argv[0] if argv else "scan"; extra = argv[1:]
    home = common.data_home(); cfg = config.load(home); common.ensure_dirs(home)
    lock = home / "memory" / ".run.lock"
    if not acquire(lock):
        print("job-search already running; exiting 0"); return 0
    try:
        run_id = str(uuid.uuid4())
        claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local/bin/claude")
        if not Path(claude).exists():
            print("claude CLI not found; set CLAUDE_BIN", file=sys.stderr); return 2
        try:
            mcp_out = subprocess.run([claude, "mcp", "list"], capture_output=True, text=True, timeout=30).stdout.lower()
            missing = [n for n in ("firecrawl", "playwright") if n not in mcp_out]
            if missing:
                print(f"warning: MCP servers not registered: {missing}", file=sys.stderr)
        except (OSError, subprocess.TimeoutExpired):
            pass
        rt = cfg["runtime"]
        prompt = f"/job-search {sub} --headless --run {run_id} " + " ".join(extra)
        cmd = [claude, "-p", prompt.strip(), "--model", rt["model"], "--fallback-model", rt["fallback_model"],
               "--permission-mode", "dontAsk", "--settings", str(home / "config" / "headless.settings.json"),
               "--mcp-config", str(home / "config" / "mcp.headless.json"), "--strict-mcp-config",
               "--disallowedTools", "AskUserQuestion", "--max-turns", str(rt["max_turns"]), "--max-budget-usd", str(rt["max_budget_usd"]),
               "--session-id", run_id, "--output-format", "json"]
        env = dict(os.environ, JOBSEARCH_HOME=str(home))
        if not env.get("FIRECRAWL_API_KEY"):
            import doctor
            k = doctor._firecrawl_key()
            if k: env["FIRECRAWL_API_KEY"] = k
        out_path = home / "memory" / "runs" / f"{run_id}.json"
        started = common.utcnow()
        with open(os.devnull) as devnull, open(out_path, "w") as out:
            rc = subprocess.call(cmd, cwd=str(home), stdin=devnull, stdout=out, stderr=subprocess.STDOUT, env=env)
        try:
            res = json.loads(out_path.read_text())
        except ValueError:
            res = {}
        line = {"run_id": run_id, "started_at": started, "ended_at": common.utcnow(), "mode": "headless", "subcommand": sub,
                "exit_code": rc, "is_error": res.get("is_error"), "num_turns": res.get("num_turns"), "cost_usd": res.get("total_cost_usd")}
        common.append_jsonl(home / "memory" / "logs" / "headless.jsonl", line)
        print(json.dumps(line))
        if rc != 0 or res.get("is_error") or not res.get("num_turns"):
            print("headless run failed or did nothing (zero turns) — see " + str(out_path), file=sys.stderr)
            return rc or 3
        return 0
    finally:
        shutil.rmtree(lock, ignore_errors=True)

if __name__ == "__main__":
    sys.exit(main())
