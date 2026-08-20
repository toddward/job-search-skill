import shutil, pytest, html2pdf, common

MD = "# Jane Example\nReston, VA • you@example.com\n## Summary\nPlatform architect.\n## Experience\n### Staff Architect — Example Corp\n- Built **LLM** platform\n- Cut latency 38%\n"

def test_md_to_html_structure():
    h = html2pdf.md_to_html(MD, common.SKILL_DIR / "assets" / "resume-template.html", "Jane Example - Resume")
    assert "<h1>Jane Example</h1>" in h and "<h2>Summary</h2>" in h and "<li>Built <strong>LLM</strong> platform</li>" in h
    assert "<title>Jane Example - Resume</title>" in h and "text-align: justify" not in h

def test_find_browser_returns_path_or_none(monkeypatch):
    b = html2pdf.find_browser("auto")
    assert b is None or shutil.which(b) or __import__("os").path.exists(b)
    monkeypatch.setenv("CHROME_BIN", "/nonexistent/chrome")
    # a CHROME_BIN pointing at nothing must be ignored, never handed back as the engine
    b2 = html2pdf.find_browser("auto")
    assert b2 != "/nonexistent/chrome"
    assert b2 is None or shutil.which(b2) or __import__("os").path.exists(b2)
    assert html2pdf.find_browser("/also/nonexistent/chrome") != "/also/nonexistent/chrome"

@pytest.mark.skipif(html2pdf.find_browser("auto") is None, reason="no Chrome/Chromium on this host")
def test_render_pdf_with_chrome(tmp_path):
    out = tmp_path / "r.pdf"
    res = html2pdf.md_to_pdf(MD, out, common.SKILL_DIR / "assets" / "resume-template.html", "Resume")
    assert out.exists() and res["pages"] == 1 and res["engine"] == "chrome" and res["bytes"] < 2_500_000
    if shutil.which("pdftotext"):
        import subprocess
        txt = subprocess.run(["pdftotext", str(out), "-"], capture_output=True, text=True).stdout
        assert "Jane Example" in txt and "Cut latency 38%" in txt

@pytest.mark.skipif(html2pdf.find_browser("auto") is None, reason="no Chrome/Chromium on this host")
def test_render_pdf_with_chrome_relative_out_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = html2pdf.md_to_pdf(MD, "rel.pdf", common.SKILL_DIR / "assets" / "resume-template.html", "Resume")
    assert (tmp_path / "rel.pdf").exists() and res["engine"] == "chrome"

def test_reportlab_fallback(tmp_path, monkeypatch):
    pytest.importorskip("reportlab")
    out = tmp_path / "f.pdf"
    res = html2pdf.md_to_pdf(MD, out, common.SKILL_DIR / "assets" / "resume-template.html", "Resume", engine="reportlab")
    assert out.exists() and res["engine"] == "reportlab" and res["pages"] >= 1
