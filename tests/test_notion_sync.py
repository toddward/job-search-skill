import json, notion_sync as ns

JOB = {"fingerprint": "b7f3c1a9d2e40185", "title": "Staff AI Architect", "company": "Anthropic", "status": "needs_manual_apply", "fit_score": 91,
       "location": "Reston, VA", "remote": "hybrid", "comp_min": 215000, "comp_max": 270000, "canonical_url": "https://job-boards.greenhouse.io/a/jobs/1",
       "source": "greenhouse", "posted_at": "2026-08-17", "first_seen": "2026-08-19T10:31:04Z", "last_seen": "2026-08-19T10:31:44Z",
       "last_shown": "2026-08-19T10:33:12Z", "applied_at": None, "submitted": False, "fit_reasons": ["a", "b", "c", "d"], "notes": "n",
       "description_text": "x" * 5000, "application_dir": "applications/2026-08-19-b7f3c1a9d2e40185"}

def test_properties_shape():
    p = ns.page_properties(JOB, "run-1")
    assert p["Role"] == "Staff AI Architect" and p["Fingerprint"] == "b7f3c1a9d2e40185" and p["Status"] == "needs manual apply"
    assert p["Posting URL"].startswith("https://") and p["First Seen"] == "2026-08-19" and p["Last Shown"] == "2026-08-19"
    assert p["Submitted"] is False and p["Comp Max"] == 270000 and p["Why It Fits"].count("\n") == 2 and p["Run ID"] == "run-1"
    assert "phone" not in json.dumps(p).lower()

def test_content_and_policy_and_hash():
    body = ns.page_content(JOB)
    assert len(body) < 2000 and "applications/2026-08-19" in body
    assert ns.should_mirror(dict(JOB, status="new"), "shown") is False and ns.should_mirror(JOB, "shown") is True
    assert ns.should_mirror(dict(JOB, status="shown"), "selected") is False and ns.should_mirror(dict(JOB, status="applied"), "selected") is True
    assert len(ns.schema_hash()) == 16 and "Posting URL" in ns.DDL and "userDefined" not in ns.DDL

def test_outbox_roundtrip(home):
    ns.outbox_add(home, {"fp": "x", "props": {"Role": "r"}})
    ns.outbox_add(home, {"fp": "y", "props": {"Role": "s"}})
    items = ns.outbox_drain(home)
    assert [i["fp"] for i in items] == ["x", "y"] and ns.outbox_drain(home) == []

def test_page_content_falls_back_to_description_path(home):
    (home / "memory" / "jd").mkdir(parents=True, exist_ok=True)
    (home / "memory" / "jd" / "abc.html").write_text("<h2>About</h2><p>We serve LLMs with vLLM.</p>" + "<p>x</p>" * 500)
    job = dict(JOB); job.pop("description_text"); job["description_path"] = "memory/jd/abc.html"
    assert "vLLM" not in ns.page_content(job)                     # no home -> no disk read
    body = ns.page_content(job, home)
    assert "We serve LLMs with vLLM." in body and "<p>" not in body
    assert len(body.rsplit("## Description (excerpt)\n", 1)[1]) <= 1200
    missing = dict(job, description_path="memory/jd/nope.html")
    assert ns.page_content(missing, home).endswith("## Description (excerpt)\n")
    escape = dict(job, description_path="../../etc/passwd")
    assert ns.page_content(escape, home).endswith("## Description (excerpt)\n")

def test_page_content_reads_stored_ats_json_as_prose(home, fixtures):
    (home / "memory" / "jd").mkdir(parents=True, exist_ok=True)
    (home / "memory" / "jd" / "gh.json").write_text((fixtures / "jd_greenhouse.json").read_text())
    job = dict(JOB); job.pop("description_text"); job["description_path"] = "memory/jd/gh.json"
    body = ns.page_content(job, home)
    assert "Hybrid, 3 days in Reston." in body and "absolute_url" not in body
