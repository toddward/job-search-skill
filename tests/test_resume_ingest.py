import resume_ingest as ri, config

def test_find_and_ingest_markdown(home, fixtures):
    (home / "resume" / "resume.md").write_text((fixtures / "master.md").read_text())
    cfg = config.load(home)
    assert ri.needs_resume(home, cfg) is False
    p = ri.ingest(home, cfg)
    assert p == home / "resume" / "master.md" and "Jane Example" in p.read_text()
    sha1 = (home / "resume" / ".master.sha").read_text()
    ri.ingest(home, cfg); assert (home / "resume" / ".master.sha").read_text() == sha1

def test_needs_resume_when_empty(home):
    cfg = config.load(home)
    assert ri.needs_resume(home, cfg) is True
    (home / "config" / "settings.toml").write_text('[scoring]\nresume_url = "https://example.com/resume"\n')
    assert ri.needs_resume(home, config.load(home)) is False

def test_txt_and_pdf_paths(home, monkeypatch, tmp_path):
    (home / "resume" / "resume.txt").write_text("Plain Resume\nSkills: Python")
    p = ri.ingest(home, config.load(home)); assert "Plain Resume" in p.read_text()
