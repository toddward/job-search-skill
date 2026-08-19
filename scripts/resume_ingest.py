#!/usr/bin/env python3
"""Turn the user's resume (md/txt/pdf/docx in resume/, or a hosted URL) into resume/master.md."""
from __future__ import annotations
import hashlib, shutil, subprocess, sys
from pathlib import Path
import common, config

EXT_ORDER = [".md", ".txt", ".pdf", ".docx"]

def find_resume(home: Path, cfg_scoring: dict) -> Path | None:
    rp = Path(cfg_scoring.get("resume_path") or "resume").expanduser()
    rp = rp if rp.is_absolute() else Path(home) / rp
    if rp.is_file():
        return rp
    if rp.is_dir():
        for ext in EXT_ORDER:
            hits = sorted(p for p in rp.glob(f"*{ext}") if p.name != "master.md")
            if hits: return hits[0]
    return None

def needs_resume(home: Path, cfg: dict) -> bool:
    return find_resume(home, cfg["scoring"]) is None and not cfg["scoring"].get("resume_url")

def _pdf_text(p: Path) -> str:
    if shutil.which("pdftotext"):
        return subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
    raise RuntimeError("pdftotext not found (install poppler: brew install poppler | apt-get install poppler-utils | dnf install poppler-utils)")

def _docx_text(p: Path) -> str:
    if common.host_os() == "macos" and shutil.which("textutil"):
        return subprocess.run(["textutil", "-convert", "txt", "-stdout", str(p)], capture_output=True, text=True).stdout
    if shutil.which("pandoc"):
        return subprocess.run(["pandoc", str(p), "-t", "plain"], capture_output=True, text=True).stdout
    raise RuntimeError("no DOCX converter (install pandoc)")

def _url_text(url: str) -> str:
    if shutil.which("firecrawl"):
        r = subprocess.run(["firecrawl", "scrape", url, "--format", "markdown"], capture_output=True, text=True, timeout=120)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout
    import urllib.request, re, html
    with urllib.request.urlopen(url, timeout=30) as resp:
        raw = resp.read().decode("utf-8", "ignore")
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return html.unescape(re.sub(r"<[^>]+>", "\n", raw))

def ingest(home: Path, cfg: dict) -> Path:
    home = Path(home); rdir = home / "resume"; rdir.mkdir(parents=True, exist_ok=True)
    master, shafile = rdir / "master.md", rdir / ".master.sha"
    src = find_resume(home, cfg["scoring"])
    if src:
        data = src.read_bytes(); key = hashlib.sha256(data).hexdigest()
        if master.exists() and shafile.exists() and shafile.read_text().strip() == key:
            return master
        if src.suffix == ".pdf": text = _pdf_text(src)
        elif src.suffix == ".docx": text = _docx_text(src)
        else: text = data.decode("utf-8", "ignore")
        header = f"<!-- generated from {src.name} sha256:{key[:16]} on {common.utcnow()} — edit resume/{src.name} not this file -->\n"
    else:
        url = cfg["scoring"].get("resume_url")
        if not url:
            raise FileNotFoundError("no resume found in resume/ and scoring.resume_url is empty")
        text = _url_text(url); key = hashlib.sha256(text.encode()).hexdigest()
        if master.exists() and shafile.exists() and shafile.read_text().strip() == key:
            return master
        header = f"<!-- generated from {url} on {common.utcnow()} -->\n"
    common.atomic_write(master, header + text.strip() + "\n")
    common.atomic_write(shafile, key)
    return master

def main(argv=None):
    import argparse, json
    ap = argparse.ArgumentParser(description="resume ingest"); ap.add_argument("--home"); ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    home = common.data_home(a.home); cfg = config.load(home)
    if a.check:
        print(json.dumps({"needs_resume": needs_resume(home, cfg), "source": str(find_resume(home, cfg["scoring"]) or cfg["scoring"].get("resume_url") or "")})); return
    print(ingest(home, cfg))

if __name__ == "__main__":
    main()
