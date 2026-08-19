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
