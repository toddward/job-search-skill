#!/usr/bin/env python3
"""Dependency checks with per-OS install hints; bootstrap of the data home; Firecrawl MCP registration."""
from __future__ import annotations
import json, os, shutil, subprocess, sys
from pathlib import Path
import common, config, html2pdf, resume_ingest

ASSETS = common.SKILL_DIR / "assets"
HINTS = {"macos": {"pdftotext": "brew install poppler", "fonts": "(built in)", "chrome": "install Google Chrome or: npx playwright install chromium"},
         "linux": {"pdftotext": "sudo apt-get install -y poppler-utils  # or: sudo dnf install -y poppler-utils",
                   "fonts": "sudo apt-get install -y fonts-liberation fonts-dejavu-core  # or: sudo dnf install -y liberation-fonts dejavu-sans-fonts",
                   "chrome": "sudo apt-get install -y chromium  # or: npx playwright install --with-deps chromium"},
         "other": {"pdftotext": "install poppler-utils", "fonts": "install Liberation fonts", "chrome": "install Chromium"}}

def _run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout); return r.returncode, (r.stdout + r.stderr)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, str(e)

def check(home: Path, cfg: dict, quick: bool = False, source: str | None = None) -> dict:
    hints = HINTS.get(common.host_os(), HINTS["other"]); C = []
    def add(name, ok, detail, fix=""): C.append({"name": name, "ok": bool(ok), "detail": detail, "fix": fix})
    add("python", sys.version_info >= (3, 11), sys.version.split()[0], "install Python 3.11+")
    add("data_home", os.access(home, os.W_OK), str(home) + (f" (via {source})" if source else ""),
        "set JOBSEARCH_HOME or run: doctor.py bootstrap")
    add("resume", not resume_ingest.needs_resume(home, cfg), str(resume_ingest.find_resume(home, cfg["scoring"]) or cfg["scoring"].get("resume_url") or "missing"),
        f"put resume.pdf/.md/.txt in {home/'resume'} or set scoring.resume_url")
    add("settings", (home / "config" / "settings.toml").exists(), "config/settings.toml", "doctor.py bootstrap")
    add("profile", (home / "config" / "profile.md").exists(), "config/profile.md", "doctor.py bootstrap, then edit")
    add("boards", (home / "config" / "job-board-links.md").exists(), "config/job-board-links.md", "doctor.py bootstrap")
    b = html2pdf.find_browser(cfg["output"].get("chrome_path", "auto")); add("pdf_browser", bool(b), b or "none", hints["chrome"])
    add("pdftotext", bool(shutil.which("pdftotext")), shutil.which("pdftotext") or "missing", hints["pdftotext"])
    add("git", bool(shutil.which("git")), shutil.which("git") or "missing", "install git")
    if common.host_os() == "linux":
        rc, out = _run(["fc-list"]); add("fonts", "Liberation" in out or "DejaVu" in out, "fontconfig list", hints["fonts"])
    if not quick:
        rc, out = _run(["firecrawl", "--status"]); add("firecrawl_cli", rc == 0 and "Authenticated" in out, "firecrawl --status", "npm i -g firecrawl-cli && firecrawl login")
        if shutil.which("claude"):
            rc, out = _run(["claude", "mcp", "get", "firecrawl"]); add("firecrawl_mcp", rc == 0, "claude mcp get firecrawl", "doctor.py register-firecrawl-mcp")
            rc, out = _run(["claude", "mcp", "list"], timeout=60); add("playwright_mcp", "playwright" in out.lower(), "claude mcp list", "enable the playwright plugin or: claude mcp add playwright -- npx @playwright/mcp@latest")
        if cfg["notion"].get("enabled"):
            add("notion_ids", bool(cfg["notion"].get("data_source_id")), cfg["notion"].get("data_source_id") or "not bootstrapped", "first interactive scan bootstraps the Notion database")
    return {"ok": all(c["ok"] for c in C if c["name"] not in ("playwright_mcp", "notion_ids", "firecrawl_mcp")), "checks": C}

def _copy_if_absent(src: Path, dst: Path, force: bool, subs: dict | None = None) -> bool:
    if dst.exists() and not force: return False
    txt = src.read_text(encoding="utf-8")
    for k, v in (subs or {}).items(): txt = txt.replace(k, v)
    common.atomic_write(dst, txt); return True

def bootstrap(home: Path, force: bool = False) -> list[str]:
    home = Path(home); common.ensure_dirs(home); msgs = []
    cfg_dir = home / "config"
    browser = "chrome" if common.host_os() == "macos" else "chromium"
    subs = {"{{HOME}}": str(home), "{{SKILL}}": str(common.SKILL_DIR), "{{HOME_DIR}}": str(Path.home()), "{{BROWSER}}": browser}
    pairs = [("settings.example.toml", "settings.toml"), ("profile.example.md", "profile.md"), ("cover-letter-style.example.md", "cover-letter-style.md"),
             ("job-board-links.default.md", "job-board-links.md"), ("headless.settings.example.json", "headless.settings.json"), ("mcp.headless.example.json", "mcp.headless.json")]
    for src, dst in pairs:
        if _copy_if_absent(ASSETS / src, cfg_dir / dst, force, subs): msgs.append(f"created config/{dst}")
    gi = home / ".gitignore"
    if not gi.exists():
        gi.write_text("config/browser-profile/\nconfig/settings.local.json\nmemory/.run.lock/\nmemory/.submits-*\n*.lock\n"
                      "applications/_artifacts/\napplications/*/evidence/\napplications/*/screenshots/\n"); msgs.append("created .gitignore")
    if shutil.which("git") and not (home / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=str(home)); msgs.append("git init (data home)")
    if not common.POINTER.exists():
        common.POINTER.parent.mkdir(parents=True, exist_ok=True); common.POINTER.write_text(str(home) + "\n"); msgs.append(f"wrote pointer {common.POINTER}")
    return msgs

def _firecrawl_key() -> str | None:
    k = os.environ.get("FIRECRAWL_API_KEY")
    if k: return k
    cands = [Path.home() / "Library/Application Support/firecrawl-cli/credentials.json",
             Path.home() / "Library/Application Support/firecrawl-cli/config.json",
             Path.home() / ".config/firecrawl-cli/credentials.json",
             Path.home() / ".config/firecrawl-cli/config.json"]
    for c in cands:
        d = common.read_json(c, {}) or {}
        for key in ("apiKey", "api_key", "FIRECRAWL_API_KEY"):
            if d.get(key): return d[key]
    return None

def register_firecrawl_mcp() -> str:
    if not shutil.which("claude"): return "claude CLI not found; cannot register MCP server"
    rc, _ = _run(["claude", "mcp", "get", "firecrawl"])
    if rc == 0: return "firecrawl MCP already registered"
    key = _firecrawl_key()
    if not key: return "no Firecrawl API key found (set FIRECRAWL_API_KEY or run `firecrawl login`)"
    rc, out = _run(["claude", "mcp", "add", "--scope", "user", "firecrawl", "-e", f"FIRECRAWL_API_KEY={key}", "--", "npx", "-y", "firecrawl-mcp"], timeout=60)
    return "registered firecrawl MCP (user scope)" if rc == 0 else "failed to register firecrawl MCP: " + out.replace(key, "***")[:300]

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="doctor"); ap.add_argument("--home"); ap.add_argument("--quick", action="store_true"); ap.add_argument("--json", action="store_true")
    sub = ap.add_subparsers(dest="cmd")
    b = sub.add_parser("bootstrap"); b.add_argument("--force", action="store_true")
    sub.add_parser("register-firecrawl-mcp")
    a = ap.parse_args(argv)
    home, source = common.data_home_info(a.home)
    if a.cmd == "bootstrap":
        print("\n".join(bootstrap(home, a.force) or ["nothing to do"])); return
    if a.cmd == "register-firecrawl-mcp":
        print(register_firecrawl_mcp()); return
    r = check(home, config.load(home), quick=a.quick, source=source)
    if a.json: print(json.dumps(r, indent=2)); return
    for c in r["checks"]:
        print(f"[{'ok' if c['ok'] else '!!'}] {c['name']:<15} {c['detail']}" + ("" if c["ok"] else f"   → {c['fix']}"))
    sys.exit(0 if r["ok"] else 1)

if __name__ == "__main__":
    main()
