#!/usr/bin/env python3
"""Markdown -> HTML (template) -> PDF via headless Chrome/Chromium, with reportlab fallback. macOS + Linux."""
from __future__ import annotations
import glob, html as _html, os, re, shutil, subprocess, sys
from pathlib import Path
import common

MAC_PATHS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
             "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"]
LINUX_NAMES = ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser", "microsoft-edge-stable", "brave-browser"]
LINUX_PATHS = ["/usr/bin/google-chrome-stable", "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
               "/snap/bin/chromium", "/usr/lib/chromium-browser/chromium-browser"]

def _playwright_chromium() -> str | None:
    roots = [os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), str(Path.home() / "Library/Caches/ms-playwright"), str(Path.home() / ".cache/ms-playwright")]
    pats = ["chromium-*/chrome-mac*/Chromium.app/Contents/MacOS/Chromium", "chromium-*/chrome-linux*/chrome", "chromium_headless_shell-*/chrome-linux*/headless_shell"]
    for r in roots:
        if not r: continue
        for p in pats:
            hits = sorted(glob.glob(os.path.join(r, p)))
            if hits: return hits[-1]
    return None

def find_browser(cfg_chrome_path: str = "auto") -> str | None:
    if cfg_chrome_path and cfg_chrome_path != "auto" and Path(cfg_chrome_path).expanduser().exists():
        return str(Path(cfg_chrome_path).expanduser())
    env = os.environ.get("CHROME_BIN")
    if env and Path(env).exists():
        return env
    if common.host_os() == "macos":
        for p in MAC_PATHS:
            if Path(p).expanduser().exists(): return str(Path(p).expanduser())
    for n in LINUX_NAMES:
        w = shutil.which(n)
        if w: return w
    for p in LINUX_PATHS:
        if Path(p).exists(): return p
    return _playwright_chromium()

def _inline(s: str) -> str:
    s = _html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"\[(.+?)\]\((https?://[^\s)]+)\)", r'<a href="\2">\1</a>', s)
    return s

def md_to_html(md: str, template_path: Path, title: str) -> str:
    out, in_list, para = [], False, []
    def flush_para():
        nonlocal para
        if para:
            txt = " ".join(para)
            cls = ' class="contact"' if ("@" in txt or "•" in txt) and len(out) <= 2 else ""
            out.append(f"<p{cls}>{_inline(txt)}</p>"); para = []
    for raw in (md or "").splitlines():
        line = raw.rstrip()
        if line.startswith("- ") or line.startswith("* "):
            flush_para()
            if not in_list: out.append("<ul>"); in_list = True
            out.append(f"<li>{_inline(line[2:].strip())}</li>"); continue
        if in_list: out.append("</ul>"); in_list = False
        if not line.strip(): flush_para(); continue
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m: flush_para(); out.append(f"<h{len(m.group(1))}>{_inline(m.group(2).strip())}</h{len(m.group(1))}>"); continue
        if line.strip() == "---": flush_para(); out.append("<hr>"); continue
        para.append(line.strip())
    flush_para()
    if in_list: out.append("</ul>")
    tpl = Path(template_path).read_text(encoding="utf-8")
    return tpl.replace("{{title}}", _html.escape(title)).replace("{{body}}", "\n".join(out))

def _count_pages(pdf: Path) -> int:
    if shutil.which("pdfinfo"):
        r = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
        m = re.search(r"Pages:\s+(\d+)", r.stdout)
        if m: return int(m.group(1))
    data = pdf.read_bytes()
    return max(1, len(re.findall(rb"/Type\s*/Page[^s]", data)))

def _chrome(html_path: Path, out_pdf: Path, browser: str, timeout_s: int) -> list[str]:
    args = [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer", "--virtual-time-budget=5000",
            "--timeout=20000", "--hide-scrollbars", f"--print-to-pdf={out_pdf}"]
    if os.path.exists("/.dockerenv") or os.environ.get("CI") == "true" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        args += ["--no-sandbox", "--disable-dev-shm-usage"]
    args.append(html_path.resolve().as_uri())
    subprocess.run(args, capture_output=True, text=True, timeout=timeout_s)
    return args

def _reportlab(md: str, out_pdf: Path) -> None:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem
    styles = getSampleStyleSheet(); story = []
    doc = SimpleDocTemplate(str(out_pdf), pagesize=letter, leftMargin=0.7*inch, rightMargin=0.7*inch, topMargin=0.65*inch, bottomMargin=0.65*inch)
    bullets = []
    def flush():
        nonlocal bullets
        if bullets:
            story.append(ListFlowable([ListItem(Paragraph(_inline(b), styles["Normal"])) for b in bullets], bulletType="bullet")); bullets = []
    for line in (md or "").splitlines():
        if line.startswith(("- ", "* ")): bullets.append(line[2:]); continue
        flush()
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m: story.append(Paragraph(_inline(m.group(2)), styles[{1: "Title", 2: "Heading2", 3: "Heading3"}[len(m.group(1))]]))
        elif line.strip(): story.append(Paragraph(_inline(line), styles["Normal"]))
        else: story.append(Spacer(1, 4))
    flush(); doc.build(story)

def render_pdf(html: str, out_pdf: Path, engine: str = "auto", chrome_path: str = "auto", timeout_s: int = 30, md_for_fallback: str = "") -> dict:
    out_pdf = Path(out_pdf); out_pdf.parent.mkdir(parents=True, exist_ok=True)
    warnings = []
    html_path = out_pdf.with_suffix(".html"); html_path.write_text(html, encoding="utf-8")
    browser = find_browser(chrome_path) if engine in ("auto", "chrome") else None
    if browser:
        try:
            _chrome(html_path, out_pdf, browser, timeout_s)
            if out_pdf.exists() and out_pdf.stat().st_size > 0:
                pages = _count_pages(out_pdf); size = out_pdf.stat().st_size
                if size > 2_500_000: warnings.append("PDF larger than 2.5MB; some ATS will not parse it")
                return {"engine": "chrome", "pages": pages, "bytes": size, "warnings": warnings, "browser": browser}
            warnings.append("chrome produced no output")
        except subprocess.TimeoutExpired:
            warnings.append("chrome timed out (watchdog)")
    if engine == "chrome":
        raise RuntimeError("chrome engine requested but failed: " + "; ".join(warnings))
    try:
        _reportlab(md_for_fallback or re.sub(r"<[^>]+>", "", html), out_pdf)
    except ImportError:
        raise RuntimeError("no browser found and reportlab is not installed; run doctor for install hints")
    return {"engine": "reportlab", "pages": _count_pages(out_pdf), "bytes": out_pdf.stat().st_size, "warnings": warnings}

def md_to_pdf(md: str, out_pdf: Path, template_path: Path, title: str, engine: str = "auto", chrome_path: str = "auto") -> dict:
    html = md_to_html(md, template_path, title)
    Path(out_pdf).with_suffix(".md").write_text(md, encoding="utf-8") if not Path(out_pdf).with_suffix(".md").exists() else None
    return render_pdf(html, out_pdf, engine=engine, chrome_path=chrome_path, md_for_fallback=md)

def main(argv=None):
    import argparse, json
    ap = argparse.ArgumentParser(description="markdown -> pdf")
    ap.add_argument("input"); ap.add_argument("--out", required=True); ap.add_argument("--template", default="resume", choices=["resume", "cover"])
    ap.add_argument("--title", default="Document"); ap.add_argument("--engine", default="auto"); ap.add_argument("--chrome", default="auto")
    a = ap.parse_args(argv)
    tpl = common.SKILL_DIR / "assets" / ("resume-template.html" if a.template == "resume" else "cover-letter-template.html")
    print(json.dumps(md_to_pdf(Path(a.input).read_text(encoding="utf-8"), Path(a.out), tpl, a.title, a.engine, a.chrome)))

if __name__ == "__main__":
    main()
