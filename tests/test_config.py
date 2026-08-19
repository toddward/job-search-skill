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
