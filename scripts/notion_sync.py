#!/usr/bin/env python3
"""Build Notion payloads for the jobs mirror (the skill performs the MCP calls); manage the failure outbox."""
from __future__ import annotations
import json, sys
from pathlib import Path
import common

DDL = """CREATE TABLE (
  "Role"        TITLE COMMENT 'Job title as posted',
  "Company"     RICH_TEXT,
  "Fingerprint" RICH_TEXT COMMENT 'upsert key; do not edit',
  "Status"      SELECT('new':gray, 'shown':blue, 'selected':purple, 'applied':green, 'not interested':red, 'expired':brown, 'needs manual apply':orange),
  "Fit"         NUMBER,
  "Location"    RICH_TEXT,
  "Work Model"  SELECT('remote':green, 'hybrid':blue, 'onsite':gray, 'unknown':default),
  "Comp Min"    NUMBER FORMAT 'dollar',
  "Comp Max"    NUMBER FORMAT 'dollar',
  "Posting URL" URL,
  "Source"      SELECT('greenhouse':blue, 'lever':purple, 'ashby':pink, 'workday':orange, 'linkedin':blue, 'indeed':yellow, 'phenom':gray, 'usajobs':green, 'dice':gray, 'other':default),
  "Posted"      DATE,
  "First Seen"  DATE,
  "Last Seen"   DATE,
  "Last Shown"  DATE,
  "Applied On"  DATE,
  "Submitted"   CHECKBOX,
  "Why It Fits" RICH_TEXT,
  "Notes"       RICH_TEXT,
  "Run ID"      RICH_TEXT
)"""
STATUS_LABEL = {"not_interested": "not interested", "needs_manual_apply": "needs manual apply"}
ICON = {"new": "🆕", "shown": "👀", "selected": "📝", "applied": "✅", "not_interested": "🚫", "expired": "🗄️", "needs_manual_apply": "⚠️"}
KNOWN_SOURCES = {"greenhouse", "lever", "ashby", "workday", "linkedin", "indeed", "phenom", "usajobs", "dice"}

def schema_hash() -> str:
    return common.sha16(DDL)

def status_icon(status: str) -> str:
    return ICON.get(status, "📄")

def _d(ts):
    return (ts or "")[:10] or None

def page_properties(job: dict, run_id: str = "") -> dict:
    return {"Role": job.get("title", ""), "Company": job.get("company", ""), "Fingerprint": job["fingerprint"],
            "Status": STATUS_LABEL.get(job.get("status"), job.get("status", "new")), "Fit": job.get("fit_score"),
            "Location": job.get("location", ""), "Work Model": job.get("remote") or "unknown",
            "Comp Min": job.get("comp_min"), "Comp Max": job.get("comp_max"), "Posting URL": job.get("canonical_url"),
            "Source": job.get("source") if job.get("source") in KNOWN_SOURCES else "other",
            "Posted": job.get("posted_at"), "First Seen": _d(job.get("first_seen")), "Last Seen": _d(job.get("last_seen")),
            "Last Shown": _d(job.get("last_shown")), "Applied On": _d(job.get("applied_at")), "Submitted": bool(job.get("submitted")),
            "Why It Fits": "\n".join((job.get("fit_reasons") or [])[:3]), "Notes": job.get("notes", "") or "", "Run ID": run_id}

def _description(job: dict, home: Path | None) -> str:
    """The stored row keeps the JD body on disk (`description_path`), not in the row, so a
    mirror built from a jobs.jsonl record would otherwise have an empty excerpt."""
    text = job.get("description_text") or ""
    rel = job.get("description_path")
    if not text and rel and home:
        home = Path(home).resolve()
        p = (home / rel).resolve()
        if p.is_file() and p.is_relative_to(home):   # never read outside the data home
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return ""
            if p.suffix.lower() in (".html", ".htm") or text.lstrip().startswith("<"):
                import jd_extract
                text = jd_extract.strip_html(text)
            text = "\n".join(ln.strip() for ln in text.splitlines() if ln.strip())
    return text[:1200]

def page_content(job: dict, home: Path | None = None) -> str:
    desc = _description(job, home)
    lines = [f"# {job.get('title')} @ {job.get('company')}", "", f"Posting: {job.get('canonical_url')}", "",
             "## Why it fits", *[f"- {r}" for r in (job.get("fit_reasons") or [])[:5]], ""]
    if job.get("application_dir"):
        lines += ["## Artifacts", f"- {job['application_dir']}/resume.pdf", f"- {job['application_dir']}/cover-letter.pdf", ""]
    lines += ["## Description (excerpt)", desc]
    return "\n".join(lines)

def should_mirror(job: dict, policy: str) -> bool:
    st = job.get("status")
    if policy == "all": return True
    if policy == "shown": return st != "new"
    if policy == "selected": return st in ("selected", "applied", "needs_manual_apply")
    return False

def outbox_add(home: Path, payload: dict) -> None:
    common.append_jsonl(Path(home) / "memory" / "notion-outbox.jsonl", payload)

def outbox_drain(home: Path) -> list[dict]:
    p = Path(home) / "memory" / "notion-outbox.jsonl"
    items = common.read_jsonl(p)
    if p.exists(): p.unlink()
    return items

def main(argv=None):
    import argparse, jobs_db
    ap = argparse.ArgumentParser(description="notion payloads"); ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("payload"); pl.add_argument("fp"); pl.add_argument("--run", default="")
    sub.add_parser("ddl"); sub.add_parser("outbox")
    a = ap.parse_args(argv)
    home = common.data_home(a.home)
    if a.cmd == "ddl": print(DDL); return
    if a.cmd == "outbox": print(json.dumps(common.read_jsonl(home / "memory" / "notion-outbox.jsonl"))); return
    job = jobs_db.JobsDB(home / "memory" / "jobs.jsonl").find(a.fp)
    if not job: sys.exit("unknown fingerprint")
    print(json.dumps({"properties": page_properties(job, a.run), "content": page_content(job, home), "icon": status_icon(job.get("status"))}, ensure_ascii=False))

if __name__ == "__main__":
    main()
