import json, jobs_db
from jobs_db import JobsDB

def rec(**kw):
    base = {"fingerprint": "b7f3c1a9d2e40185", "title": "Staff AI Solutions Architect", "company": "Anthropic",
            "location": "Reston, VA", "remote": "hybrid", "url": "https://job-boards.greenhouse.io/anthropic/jobs/1?gh_src=li",
            "source": "greenhouse", "posted_at": "2026-08-17", "content_hash": "55ab90c3e7d14f02"}
    base.update(kw); return base

def test_upsert_creates_then_merges_sources(home):
    db = JobsDB(home / "memory" / "jobs.jsonl")
    r = db.upsert(rec(), now="2026-08-19T10:00:00Z")
    assert r["status"] == "new" and r["first_seen"] == "2026-08-19T10:00:00Z" and len(r["sources"]) == 1
    r2 = db.upsert(rec(url="https://www.linkedin.com/jobs/view/42?trackingId=x", source="linkedin"), now="2026-08-19T11:00:00Z")
    assert r2["first_seen"] == "2026-08-19T10:00:00Z" and r2["last_seen"] == "2026-08-19T11:00:00Z"
    assert len(r2["sources"]) == 2 and r2["canonical_url"].startswith("https://job-boards.greenhouse.io")
    db.save(); assert len(JobsDB(home / "memory" / "jobs.jsonl").all()) == 1

def test_status_and_mark_shown_preserved_on_upsert(home):
    db = JobsDB(home / "memory" / "jobs.jsonl")
    db.upsert(rec(), now="2026-08-19T10:00:00Z")
    db.mark_shown(["b7f3c1a9d2e40185"], now="2026-08-19T10:33:12Z")
    db.set_status("b7f3c1a9d2e40185", "not_interested", reason="sales", now="2026-08-19T10:40:00Z")
    r = db.upsert(rec(), now="2026-08-20T10:00:00Z")
    assert r["status"] == "not_interested" and r["last_shown"] == "2026-08-19T10:33:12Z" and r["shown_count"] == 1

def test_repost_bumps_version_and_resets(home):
    db = JobsDB(home / "memory" / "jobs.jsonl")
    db.upsert(rec(), now="2026-08-01T10:00:00Z"); db.mark_shown(["b7f3c1a9d2e40185"], now="2026-08-01T10:05:00Z")
    r = db.upsert(rec(content_hash="ffffffffffffffff", posted_at="2026-08-18"), now="2026-08-19T10:00:00Z")
    assert r["version"] == 2 and r["status"] == "new" and r["last_shown"] is None

def test_validate_and_quarantine(home):
    p = home / "memory" / "jobs.jsonl"
    p.write_text('{"fingerprint":"b7f3c1a9d2e40185","title":"x","company":"y","canonical_url":"https://a/b","source":"other","first_seen":"2026-08-19T10:00:00Z","last_seen":"2026-08-19T10:00:00Z","status":"new"}\nnot json\n')
    db = JobsDB(p)
    assert len(db.all()) == 1 and (home / "memory" / "jobs.badlines.jsonl").read_text().strip() == "not json"
    assert db.validate() == []
    db.all()[0]["status"] = "bogus"
    assert any("status" in e for e in db.validate())

def test_find_prefix(home):
    db = JobsDB(home / "memory" / "jobs.jsonl"); db.upsert(rec(), now="2026-08-19T10:00:00Z")
    assert db.find("b7f3c1")["fingerprint"] == "b7f3c1a9d2e40185" and db.find("zzzzzz") is None
