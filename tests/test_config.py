import json, config

def test_defaults_load_without_files(home):
    cfg = config.load(home)
    assert cfg["apply"]["auto_submit"] is False
    assert cfg["apply"]["submit_threshold"] == 80
    assert cfg["memory"]["cooldown_days"] == 14
    assert cfg["scoring"]["weights"]["must_have"] == 35
    assert cfg["_home"] == str(home)

def test_toml_and_local_override(home):
    (home / "config" / "settings.toml").write_text('[apply]\nauto_submit = true\n[search]\nradius_miles = 50\n')
    (home / "config" / "settings.local.json").write_text(json.dumps({"notion": {"data_source_id": "abc"}}))
    cfg = config.load(home)
    assert cfg["apply"]["auto_submit"] is True
    assert cfg["search"]["radius_miles"] == 50
    assert config.get(cfg, "notion.data_source_id") == "abc"
    assert config.get(cfg, "nope.nothing", 7) == 7

def test_set_local_and_resolve_path(home):
    config.set_local(home, "notion.database_id", "db1")
    cfg = config.load(home)
    assert cfg["notion"]["database_id"] == "db1"
    assert config.resolve_path(cfg, "output.report_dir") == home / "reports"

def test_platform_override_applied(home, monkeypatch):
    import common
    monkeypatch.setattr(common, "host_os", lambda: "linux")
    (home / "config" / "settings.toml").write_text('[platform_overrides.linux.apply]\nbrowser_channel = "chromium"\n')
    cfg = config.load(home)
    assert cfg["apply"]["browser_channel"] == "chromium"

def test_set_local_refuses_apply_keys(home):
    import pytest, subprocess, sys, common
    for key in ("apply.auto_submit", "apply.submit_threshold", "apply"):
        with pytest.raises(ValueError):
            config.set_local(home, key, True)
    assert not (home / "config" / "settings.local.json").exists()
    assert config.load(home)["apply"]["auto_submit"] is False
    r = subprocess.run([sys.executable, str(common.SKILL_DIR / "scripts" / "config.py"), "--home", str(home),
                        "set-local", "apply.auto_submit", "true"], capture_output=True, text=True)
    assert r.returncode == 2 and "refused: apply.* is hand-edited in settings.toml only" in r.stderr
    assert config.load(home)["apply"]["auto_submit"] is False
    config.set_local(home, "notion.database_id", "ok")  # non-apply keys still work
    assert config.load(home)["notion"]["database_id"] == "ok"

def test_browser_mode_env_override(home, monkeypatch):
    assert config.load(home)["apply"]["browser_mode"] == "auto"
    monkeypatch.setenv("JOBSEARCH_BROWSER_MODE", "headless")
    assert config.load(home)["apply"]["browser_mode"] == "headless"
    (home / "config" / "settings.toml").write_text('[apply]\nbrowser_mode = "headed"\n')
    assert config.load(home)["apply"]["browser_mode"] == "headless"  # env wins over TOML
    monkeypatch.setenv("JOBSEARCH_BROWSER_MODE", "headed")
    assert config.load(home)["apply"]["browser_mode"] == "headed"    # any other value is inert

def test_example_toml_matches_defaults_exactly():
    """Every shipped key must be one the code actually reads, and every default must be
    documented in the example — an unconsumed setting is a lie to the user."""
    import tomllib, common
    with open(common.SKILL_DIR / "assets" / "settings.example.toml", "rb") as f:
        example = tomllib.load(f)

    def keys(d, prefix=""):
        out = set()
        for k, v in d.items():
            out.add(prefix + k)
            if isinstance(v, dict):
                out |= keys(v, prefix + k + ".")
        return out

    skip = {"platform_overrides"}
    ex = {k for k in keys(example) if k.split(".")[0] not in skip}
    de = {k for k in keys(config.DEFAULTS) if k.split(".")[0] not in skip}
    assert ex == de, f"only in example: {sorted(ex - de)} | only in DEFAULTS: {sorted(de - ex)}"
    for gone in ("remote_preference", "include_hybrid", "max_applications_per_run", "pdf_font_family"):
        assert not any(k.endswith(gone) for k in de | ex), gone
