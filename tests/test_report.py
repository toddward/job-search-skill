import json, report, jobs_db

def mk(fp, n, fit=90):
    return {"fingerprint": fp, "title": f"Role {n}", "company": "Acme", "location": "Reston, VA", "comp_min": 100000, "comp_max": 150000,
            "posted_at": "2026-08-17", "source": "greenhouse", "canonical_url": f"https://x/{fp}", "fit_score": fit, "adjusted_fit": fit,
            "fit_reasons": ["good"], "fit_breakdown": {"missing_must_haves": ["Rust"]}, "status": "new"}

def result():
    return {"ranked": [mk("a" * 16, 1), mk("b" * 16, 2, 80)], "manual": [dict(mk("c" * 16, 3), status="needs_manual_apply", status_reason="captcha")],
            "suppressed_high_fit": [dict(mk("d" * 16, 4, 93), rule_id="dis-002")], "counts": {"seen": 10, "new": 4, "suppressed": 2, "in_cooldown": 1, "listed": 2}}

def run(rid="9f1c2d3e-0000-0000-0000-000000000000"):
    return {"run_id": rid, "started_at": "2026-08-19T10:30:00Z", "mode": "interactive", "subcommand": "scan", "query": "AI Reston",
            "boards_attempted": 3, "boards_ok": 2, "boards_failed": [{"board": "Indeed", "reason": "captcha"}]}

def test_render_has_sections_and_index():
    md = report.render(run(), result(), learned=["dis-001 soft"], decisions=[])
    assert "| 1 |" in md and "Needs your decision" in md and "Suppressed but high-fit" in md and "```json job-index" in md
    idx = report.load_index_text(md)
    assert idx["items"][0]["fp"] == "a" * 16 and idx["manual"][0]["n"] == "M1" and idx["suppressed"][0]["rule"] == "dis-002"

def test_write_sets_last_shown_and_versions(home):
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    for fp in ("a" * 16, "b" * 16):
        db.upsert({"fingerprint": fp, "title": "t", "company": "c", "url": f"https://x/{fp}"}, now="2026-08-19T10:00:00Z")
    db.save()
    p1 = report.write(home, "2026-08-19", run(), result(), db=db)
    assert p1.name == "2026-08-19.md" and db.get("a" * 16)["last_shown"] is not None and db.get("a" * 16)["status"] == "shown"
    p2 = report.write(home, "2026-08-19", run("other-run"), result(), db=db)
    assert p2.name == "2026-08-19.r2.md"
    assert report.latest_report(home).name == "2026-08-19.r2.md"
    assert report.latest_report(home, run_id="9f1c2d3e").name == "2026-08-19.md"

def test_resolve_numbers(home):
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    db.upsert({"fingerprint": "a" * 16, "title": "t", "company": "c", "url": "https://x/a"}, now="2026-08-19T10:00:00Z")
    p = report.write(home, "2026-08-19", run(), result(), db=db)
    idx = report.load_index(p)
    got = report.resolve_numbers(["1", "M1", "aaaaaa"], idx, db)
    assert [g["fp"] for g in got] == ["a" * 16, "c" * 16, "a" * 16]
    import pytest
    with pytest.raises(ValueError):
        report.resolve_numbers(["9"], idx, db)
    idx["generated_at"] = "2026-07-01T00:00:00Z"
    with pytest.raises(ValueError):
        report.resolve_numbers(["1"], idx, db, now="2026-08-19T00:00:00Z")

def test_latest_report_ignores_stray_date_prefixed_files(home):
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    (home / "reports").mkdir(parents=True, exist_ok=True)
    (home / "reports" / "2026-08-19-scratchpad-notes.md").write_text("not a report", encoding="utf-8")
    report.write(home, "2026-08-19", run(), result(), db=db)
    report.write(home, "2026-08-19", run("other-run"), result(), db=db)
    p = report.latest_report(home, date="2026-08-19")
    assert p.name == "2026-08-19.r2.md"

def test_write_skips_slot_of_deleted_but_recorded_report(home):
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    report.write(home, "2026-08-19", run("run-1"), result(), db=db)
    report.write(home, "2026-08-19", run("run-2"), result(), db=db)
    p3 = report.write(home, "2026-08-19", run("run-3"), result(), db=db)
    assert p3.name == "2026-08-19.r3.md"
    p3.unlink()
    p4 = report.write(home, "2026-08-19", run("run-4"), result(), db=db)
    assert p4.name != "2026-08-19.r3.md"
    got = report.latest_report(home, run_id="run-3")
    assert got is None or report.load_index(got).get("run_id") == "run-3"

def test_render_escapes_pipe_in_table_cells():
    r = result()
    r["ranked"][0]["title"] = "Engineer | Full Stack"
    md = report.render(run(), r)
    rows = [l for l in md.splitlines() if l.startswith("| 1 |")]
    assert rows and "Engineer \\| Full Stack" in rows[0]
    idx = report.load_index_text(md)
    assert idx["items"][0]["title"] == "Engineer | Full Stack"

def test_comp_cell_tolerates_strings_and_floats():
    """I7: _comp did lo//1000 on whatever it was handed."""
    assert report._comp({"comp_min": "215000", "comp_max": 270000.0}) == "$215–270k"
    assert report._comp({"comp_min": "$215,000", "comp_max": "$270,000"}) == "$215–270k"
    assert report._comp({"comp_max": "180000"}) == "up to $180k"
    assert report._comp({"comp_min": "competitive", "comp_max": None}) == "not listed"

def test_write_with_string_comp_does_not_raise(home):
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    r = result()
    r["ranked"][0].update(comp_min="215,000", comp_max="270000")
    r["ranked"][1].update(comp_min="tbd", comp_max="tbd")
    p = report.write(home, "2026-08-19", run(), r, db=db)
    assert "$215–270k" in p.read_text() and "not listed" in p.read_text()
