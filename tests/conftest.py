import os, sys, pathlib, pytest
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

@pytest.fixture(autouse=True)
def _isolated_pointer(tmp_path, monkeypatch):
    import common
    monkeypatch.setattr(common, "POINTER", tmp_path / "_pointer" / "home")

@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    monkeypatch.setenv("JOBSEARCH_HOME", str(h))
    import common
    common.ensure_dirs(h)
    return h

@pytest.fixture
def fixtures():
    return ROOT / "tests" / "fixtures"
