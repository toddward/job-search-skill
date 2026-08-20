import json, os, subprocess, sys, doctor, runtime_probe, common
from pathlib import Path

def test_probe_modes(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli"); assert runtime_probe.probe()["mode"] == "interactive"
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "sdk-cli"); assert runtime_probe.probe()["mode"] == "headless"
    monkeypatch.delenv("CLAUDE_CODE_ENTRYPOINT"); assert runtime_probe.probe()["mode"] == "headless"
    monkeypatch.setenv("JOBSEARCH_FORCE_MODE", "interactive"); assert runtime_probe.probe()["mode"] == "interactive"
    out = subprocess.run([sys.executable, str(common.SKILL_DIR / "scripts" / "runtime_probe.py")], capture_output=True, text=True).stdout
    assert out.startswith("mode=") and " os=" in out and "$" not in out

def test_probe_sanitizes_dollar_in_home(monkeypatch):
    import subprocess, sys, common
    env = dict(__import__("os").environ, JOBSEARCH_HOME="/tmp/x/$USER/home", CLAUDE_CODE_ENTRYPOINT="cli")
    out = subprocess.run([sys.executable, str(common.SKILL_DIR / "scripts" / "runtime_probe.py")], capture_output=True, text=True, env=env).stdout
    assert "$" not in out and "`" not in out and "mode=interactive" in out and "<unsafe-path>" in out

def test_bootstrap_creates_config(home):
    msgs = doctor.bootstrap(home)
    for f in ["settings.toml", "profile.md", "cover-letter-style.md", "job-board-links.md", "headless.settings.json", "mcp.headless.json"]:
        assert (home / "config" / f).exists(), f
    assert (home / ".git").exists() and (home / ".gitignore").read_text().count("browser-profile")
    hs = json.loads((home / "config" / "headless.settings.json").read_text())
    assert str(home) in json.dumps(hs) and "{{" not in json.dumps(hs)
    assert common.POINTER.read_text().strip() == str(home)
    (home / "config" / "settings.toml").write_text("# edited\n")
    doctor.bootstrap(home); assert (home / "config" / "settings.toml").read_text() == "# edited\n"

def test_firecrawl_key_reads_credentials_json(tmp_path, monkeypatch):
    monkeypatch.delenv("FIRECRAWL_API_KEY", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert doctor._firecrawl_key() is None  # no files, no env -> None
    cred_dir = tmp_path / "Library" / "Application Support" / "firecrawl-cli"
    cred_dir.mkdir(parents=True)
    (cred_dir / "credentials.json").write_text(json.dumps({"apiKey": "fc-test"}))
    assert doctor._firecrawl_key() == "fc-test"

def test_check_reports_structure(home):
    import config
    doctor.bootstrap(home)
    r = doctor.check(home, config.load(home), quick=True)
    names = {c["name"] for c in r["checks"]}
    assert {"python", "data_home", "resume", "settings", "boards", "pdf_browser", "pdftotext"} <= names
    assert all({"name", "ok", "detail", "fix"} <= set(c) for c in r["checks"])

def test_headless_settings_allowlist_is_narrow():
    """I4: a bare `python3 *` is arbitrary code execution — it makes the allowlist decorative."""
    import json, common
    s = json.loads((common.SKILL_DIR / "assets" / "headless.settings.example.json").read_text())
    allow = s["permissions"]["allow"]
    for banned in ("Bash(python3 *)", "Bash(cp *)", "Bash(mv *)"):
        assert banned not in allow, banned
    for kept in ("Bash(python3 {{SKILL}}/scripts/*)", "Bash(mkdir *)", "Bash(cat *)",
                 "Bash(firecrawl *)", "Bash(pdftotext *)", "Bash(git -C {{HOME}} *)"):
        assert kept in allow, kept
    assert "AskUserQuestion" in s["permissions"]["deny"]

def test_bootstrap_gitignores_application_evidence(home):
    import doctor
    doctor.bootstrap(home)
    gi = (home / ".gitignore").read_text()
    for pat in ("config/settings.local.json", "config/browser-profile/", "memory/.submits-*",
                "applications/*/evidence/", "applications/*/screenshots/"):
        assert pat in gi, pat
