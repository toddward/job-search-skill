import pathlib
import common

def test_data_home_resolution(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBSEARCH_HOME", raising=False)
    monkeypatch.setattr(common, "POINTER", tmp_path / "pointer")
    monkeypatch.setattr(common, "DEFAULT_HOME", tmp_path / "default")
    assert common.data_home() == tmp_path / "default"
    (tmp_path / "pointer").write_text(str(tmp_path / "ptr") + "\n")
    assert common.data_home() == tmp_path / "ptr"
    monkeypatch.setenv("JOBSEARCH_HOME", str(tmp_path / "env"))
    assert common.data_home() == tmp_path / "env"
    assert common.data_home(str(tmp_path / "arg")) == tmp_path / "arg"

def test_pointer_path_honors_xdg_config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    assert common.pointer_path() == tmp_path / "xdg" / "job-search" / "home"
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative/ignored")  # XDG spec: non-absolute values are ignored
    assert common.pointer_path() == pathlib.Path.home() / ".config" / "job-search" / "home"
    monkeypatch.delenv("XDG_CONFIG_HOME")
    assert common.pointer_path() == pathlib.Path.home() / ".config" / "job-search" / "home"

def test_data_home_info_reports_source(tmp_path, monkeypatch):
    monkeypatch.delenv("JOBSEARCH_HOME", raising=False)
    monkeypatch.setattr(common, "POINTER", tmp_path / "pointer")
    monkeypatch.setattr(common, "DEFAULT_HOME", tmp_path / "default")
    assert common.data_home_info() == (tmp_path / "default", "default")
    (tmp_path / "pointer").write_text(str(tmp_path / "ptr") + "\n")
    assert common.data_home_info() == (tmp_path / "ptr", "pointer")
    monkeypatch.setenv("JOBSEARCH_HOME", str(tmp_path / "env"))
    assert common.data_home_info() == (tmp_path / "env", "env")
    assert common.data_home_info(str(tmp_path / "arg")) == (tmp_path / "arg", "cli")

def test_time_helpers():
    assert common.utcnow().endswith("Z") and len(common.utcnow()) == 20
    assert abs(common.days_between("2026-08-05T10:33:00Z", "2026-08-19T10:33:00Z") - 14.0) < 1e-9

def test_sha16_and_slug():
    assert len(common.sha16("abc")) == 16
    assert common.slugify("Staff AI Solutions Architect (Remote)!") == "staff-ai-solutions-architect-remote"

def test_atomic_and_jsonl(tmp_path):
    p = tmp_path / "a" / "x.jsonl"
    common.append_jsonl(p, {"a": 1})
    common.append_jsonl(p, {"b": 2})
    assert common.read_jsonl(p) == [{"a": 1}, {"b": 2}]
    common.atomic_write(tmp_path / "t.txt", "hi")
    assert (tmp_path / "t.txt").read_text() == "hi"
    assert not list(tmp_path.glob("*.tmp"))

def test_ensure_dirs(tmp_path):
    common.ensure_dirs(tmp_path)
    for d in ["resume", "config", "memory/logs", "memory/runs", "memory/ats-learned", "reports", "applications"]:
        assert (tmp_path / d).is_dir()

def test_host_os():
    assert common.host_os() in {"macos", "linux", "other"}

def test_data_subdirs_include_jd_and_runs(tmp_path):
    import common
    common.ensure_dirs(tmp_path)
    for d in ("memory/jd", "memory/runs", "memory/logs", "memory/ats-learned"):
        assert (tmp_path / d).is_dir(), d
