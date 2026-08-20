#!/usr/bin/env python3
"""Load and merge job-search configuration (TOML + local JSON + platform overrides)."""
from __future__ import annotations
import copy, json, os, sys
from pathlib import Path
try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore
import common

DEFAULTS = {
    "schema_version": 1,
    "search": {"query": "", "default_location": "", "radius_miles": 25, "remote_preference": "prefer",
               "include_hybrid": True, "min_results": 10, "max_results": 12, "max_age_days": 30,
               "boards_file": "config/job-board-links.md", "board_timeout_seconds": 90,
               "strategy_order": ["webfetch", "firecrawl", "playwright"], "detail_pages_per_board": 30},
    "scoring": {"resume_path": "resume", "resume_url": "", "rubric_version": 1, "min_fit_to_show": 40,
                "weights": {"must_have": 35, "skills": 20, "seniority": 12, "location": 12,
                            "domain": 8, "recency": 5, "comp": 8},
                "resume_seniority": "senior", "home_metro": [], "ok_metros": [], "target_domains": [],
                "target_base": 0, "holds_clearance": False, "work_authorized_us": True, "needs_sponsorship": False},
    "memory": {"cooldown_days": 14, "extended_cooldown_days": 45, "expire_after_days": 45,
               "selection_expiry_days": 7, "git_autocommit": True},
    "apply": {"auto_submit": False, "submit_threshold": 80, "max_submits_per_run": 5,
              "max_applications_per_run": 5, "browser_profile_path": "config/browser-profile",
              "browser_mode": "auto", "browser_channel": "auto", "browser_no_sandbox": False,
              "cdp_endpoint": "", "tailor_by_default": True, "profile": "config/profile.md",
              "cover_letter_style": "config/cover-letter-style.md", "screenshot_every_step": True},
    "output": {"report_dir": "reports", "applications_dir": "applications", "pdf_engine": "auto",
               "chrome_path": "auto", "pdf_font_family": 'Arial, "Liberation Sans", Helvetica, "Nimbus Sans", sans-serif'},
    "notion": {"enabled": True, "database_id": "", "data_source_id": "", "parent_page_id": "",
               "database_title": "Job Search", "mirror": "shown"},
    "runtime": {"model": "opus", "fallback_model": "sonnet", "max_turns": 120, "max_budget_usd": 4.0},
    "platform_overrides": {"macos": {}, "linux": {}},
}

def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out

def load(home: Path | None = None) -> dict:
    home = Path(home) if home else common.data_home()
    cfg = copy.deepcopy(DEFAULTS)
    toml_path = home / "config" / "settings.toml"
    if toml_path.exists():
        with open(toml_path, "rb") as f:
            cfg = _merge(cfg, tomllib.load(f))
    local = common.read_json(home / "config" / "settings.local.json", {}) or {}
    cfg = _merge(cfg, local)
    po = (cfg.get("platform_overrides") or {}).get(common.host_os()) or {}
    cfg = _merge(cfg, po)
    # Env override for headless hosts (systemd unit / cron): the scheduler cannot edit TOML.
    if os.environ.get("JOBSEARCH_BROWSER_MODE") == "headless":
        cfg.setdefault("apply", {})["browser_mode"] = "headless"
    cfg["_home"] = str(home)
    return cfg

def get(cfg: dict, dotted: str, default=None):
    cur = cfg
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur

APPLY_REFUSAL = "refused: apply.* is hand-edited in settings.toml only"

def set_local(home: Path, dotted: str, value) -> None:
    # settings.local.json is machine-written, so nothing the model can call may reach the
    # submit gate: auto_submit/submit_threshold/caps stay a human edit in settings.toml.
    if dotted == "apply" or dotted.startswith("apply."):
        raise ValueError(APPLY_REFUSAL)
    path = Path(home) / "config" / "settings.local.json"
    data = common.read_json(path, {}) or {}
    cur = data
    parts = dotted.split(".")
    for p in parts[:-1]:
        cur = cur.setdefault(p, {})
    cur[parts[-1]] = value
    common.write_json(path, data)

def resolve_path(cfg: dict, dotted: str) -> Path:
    raw = str(get(cfg, dotted, ""))
    p = Path(raw).expanduser()
    return p if p.is_absolute() else Path(cfg["_home"]) / p

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="job-search config")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("dump")
    g = sub.add_parser("get"); g.add_argument("key")
    s = sub.add_parser("set-local"); s.add_argument("key"); s.add_argument("value")
    a = ap.parse_args(argv)
    home = common.data_home(a.home)
    if a.cmd == "dump":
        print(json.dumps(load(home), indent=2))
    elif a.cmd == "get":
        v = get(load(home), a.key)
        print(json.dumps(v) if not isinstance(v, str) else v)
    elif a.cmd == "set-local":
        val = a.value
        try:
            val = json.loads(a.value)
        except ValueError:
            pass
        try:
            set_local(home, a.key, val)
        except ValueError as e:
            print(str(e), file=sys.stderr); sys.exit(2)
        print("ok")

if __name__ == "__main__":
    main()
