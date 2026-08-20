"""chrome_keep.py: headed apply Chrome must outlive the fill process."""
import socket
from pathlib import Path
import pytest, common

def test_module_importable():
    import chrome_keep
    assert chrome_keep.DEFAULT_PORT == 9223
    assert chrome_keep.endpoint_url(9223) == "http://127.0.0.1:9223"
    assert chrome_keep.port_from_endpoint("http://localhost:9223") == 9223
    assert chrome_keep.port_from_endpoint("http://127.0.0.1:9333/") == 9333
    assert chrome_keep.port_from_endpoint("") is None


def test_launch_args_use_profile_and_debug_port(tmp_path):
    import chrome_keep
    args = chrome_keep.chrome_launch_args("/usr/bin/google-chrome", tmp_path / "prof", 9223)
    joined = " ".join(args)
    assert args[0] == "/usr/bin/google-chrome"
    assert "--remote-debugging-port=9223" in args
    assert "--remote-debugging-address=127.0.0.1" in args
    assert f"--user-data-dir={tmp_path / 'prof'}" in joined
    assert "--no-first-run" in args
    assert "about:blank" in args
    # never the user's default profile
    assert ".config/google-chrome" not in joined and "Library/Application Support/Google/Chrome" not in joined


def test_popen_kwargs_detach_from_fill_process_group():
    import chrome_keep
    kw = chrome_keep.popen_kwargs()
    assert kw.get("start_new_session") is True


def test_ensure_attaches_when_already_listening(tmp_path, monkeypatch):
    import chrome_keep
    monkeypatch.setattr(chrome_keep, "is_listening", lambda host, port: True)
    launched = []
    monkeypatch.setattr(chrome_keep.subprocess, "Popen", lambda *a, **k: launched.append((a, k)) or type("P", (), {"pid": 1})())
    out = chrome_keep.ensure_debug_chrome(tmp_path / "prof", chrome_bin="/usr/bin/google-chrome")
    assert out["endpoint"] == "http://127.0.0.1:9223"
    assert out["launched"] is False
    assert launched == []


def test_ensure_launches_detached_chrome_when_port_free(tmp_path, monkeypatch):
    import chrome_keep
    calls = []
    class FakeProc:
        pid = 4242
    def fake_popen(args, **kw):
        calls.append((list(args), dict(kw)))
        return FakeProc()
    monkeypatch.setattr(chrome_keep.subprocess, "Popen", fake_popen)
    # pre-check: port free; wait-loop: port is up
    seq = iter([False, True])
    monkeypatch.setattr(chrome_keep, "is_listening", lambda host, port: next(seq, True))
    out = chrome_keep.ensure_debug_chrome(tmp_path / "prof", chrome_bin="/usr/bin/google-chrome", port=9223)
    assert out["launched"] is True
    assert out["pid"] == 4242
    assert out["endpoint"] == "http://127.0.0.1:9223"
    assert len(calls) == 1
    args, kw = calls[0]
    assert "--remote-debugging-port=9223" in args
    assert kw.get("start_new_session") is True


def test_ensure_respects_explicit_cdp_endpoint(tmp_path, monkeypatch):
    import chrome_keep
    monkeypatch.setattr(chrome_keep, "is_listening", lambda host, port: True)
    launched = []
    monkeypatch.setattr(chrome_keep.subprocess, "Popen", lambda *a, **k: launched.append(1))
    out = chrome_keep.ensure_debug_chrome(tmp_path / "p", endpoint="http://127.0.0.1:9333")
    assert out["endpoint"] == "http://127.0.0.1:9333"
    assert out["launched"] is False
    assert launched == []


def test_ensure_refuses_headless(tmp_path):
    import chrome_keep
    with pytest.raises(RuntimeError, match="headed-only"):
        chrome_keep.ensure_debug_chrome(tmp_path / "p", headed=False)


def test_cli_ensure_json(home, monkeypatch, capsys):
    import json, chrome_keep
    monkeypatch.setattr(chrome_keep, "is_listening", lambda host, port: True)
    chrome_keep.main(["--home", str(home), "ensure"])
    data = json.loads(capsys.readouterr().out)
    assert data["endpoint"].startswith("http://")
    assert data["launched"] is False


def test_apply_flow_forbids_closing_headed_browser():
    md = (common.SKILL_DIR / "references" / "apply-flow.md").read_text()
    low = md.lower()
    assert "chrome_keep.py" in md
    assert "never close" in low or "do not close" in low
    assert "browser.close" in low or "browser_close" in low
    assert "outlive" in low or "leave" in low
    # the fill process must not own the chrome child
    assert "start_new_session" in md or "connect_over_cdp" in md or "cdp" in low
