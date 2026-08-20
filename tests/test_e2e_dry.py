"""Offline end-to-end regression test for the whole deterministic pipeline.

bootstrap -> resume ingest -> JD extract (greenhouse/ashby/jsonld/headings) -> JobsDB upsert ->
fit_score -> write-back upsert (Task 15 C2 regression guard) -> rank -> report.write -> index
resolution -> cooldown -> disinterest.learn_dismissal -> penalized re-rank.

No network, no Chrome, no sleeping: all "later" timestamps are derived from common.utcnow() via
common.parse_ts()/timedelta.
"""
from __future__ import annotations
import datetime as dt

import common, config, disinterest, doctor, fingerprint, fit_score, jd_extract, jobs_db, rank, report, resume_ingest

JD_SPECS = {
    "greenhouse": ("jd_greenhouse.json", "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs/4512345"),
    "ashby": ("jd_ashby.json", "https://jobs.ashbyhq.com/acme/1"),
    "jsonld": ("jd_jsonld.html", "https://www.capitalonecareers.com/job/x"),
    "headings": ("jd_headings.html", "https://careers.acme-corp.example/platform-engineer"),
}


def _fmt(d: dt.datetime) -> str:
    return d.strftime("%Y-%m-%dT%H:%M:%SZ")


def _extract_all(fixtures) -> dict:
    out = {}
    for name, (fname, url) in JD_SPECS.items():
        raw = (fixtures / fname).read_text(encoding="utf-8")
        out[name] = jd_extract.extract(raw, url=url)
    return out


def _build_record(name: str, e: dict) -> dict:
    """Map jd_extract output onto JobsDB.upsert's input fields."""
    company = e["company"]
    if not company:
        # The headings layer never parses a company; this Ashby fixture happens to omit one too.
        # Both mention "Acme" in the fixture body/URL, so set it explicitly rather than upsert "".
        company = "Acme Corp" if name == "headings" else "Acme"
    return {"title": e["title"], "company": company, "location": e["location"], "remote": e["remote"],
            "url": e["apply_url"], "posted_at": e["posted_at"], "comp_min": e["comp_min"],
            "comp_max": e["comp_max"], "content_hash": e["content_hash"]}


def test_e2e_dry_run(home, fixtures):
    # --- bootstrap the data home, ingest the resume ---
    doctor.bootstrap(home)
    cfg = config.load(home)
    (home / "resume" / "resume.md").write_text((fixtures / "master.md").read_text(encoding="utf-8"), encoding="utf-8")
    master_md = resume_ingest.ingest(home, cfg).read_text(encoding="utf-8")

    # --- extract the four JD fixtures across all four source layers ---
    extracted = _extract_all(fixtures)
    assert {e["source_layer"] for e in extracted.values()} == {"greenhouse", "ashby", "jsonld", "headings"}

    # --- build records, upsert, score, and write the score back (Task 15 C2 regression guard) ---
    now0 = common.utcnow()
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    fps, scores = {}, {}
    for name, e in extracted.items():
        cur = db.upsert(_build_record(name, e), now=now0)
        fps[name] = cur["fingerprint"]
        score_job = dict(e, location_key=fingerprint.location_key(e["location"], e["remote"]))
        s = fit_score.score(master_md, score_job, cfg["scoring"], age_days=2)
        scores[name] = s
        fit_reasons = (s.get("notes") or [])[:3] or [f"must-have coverage {s['must_have_coverage']:.0%}"]
        first_seen_before = cur["first_seen"]
        cur = db.upsert({"fingerprint": cur["fingerprint"], "fit_score": s["total"], "fit_breakdown": s,
                          "fit_reasons": fit_reasons}, now=now0)
        # write-back must not disturb identity/status fields
        assert cur["first_seen"] == first_seen_before and cur["status"] == "new"
    db.save()

    # regression guard: fit_score/fit_breakdown/fit_reasons persist across save()+reload (Task 15 C2 fix)
    reloaded = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    for name in extracted:
        row = reloaded.get(fps[name])
        assert row["fit_score"] == scores[name]["total"]
        assert row["fit_breakdown"] == scores[name]
        assert row["fit_reasons"]
    db = reloaded

    # Ashby fixture requires a clearance we don't hold -> fit_score caps it at <= 25.
    assert scores["ashby"]["total"] <= 25 and "clearance_not_held" in scores["ashby"]["caps"]

    # --- rank + write the report ---
    rules = disinterest.load_rules(home / "memory" / "disinterest.json")
    result1 = rank.rank(db.all(), rules, now0, cfg)
    assert len(result1["ranked"]) >= 1

    run = {"run_id": "11111111-1111-1111-1111-111111111111", "started_at": now0, "mode": "headless",
           "subcommand": "scan", "query": "AI jobs in Reston, VA"}
    report_path = report.write(home, now0[:10], run, result1, db=db)
    assert report_path.exists()

    idx = report.load_index(report_path)
    resolved = report.resolve_numbers(["1"], idx, db)
    top_fp = result1["ranked"][0]["fingerprint"]
    assert resolved[0]["fp"] == top_fp
    assert db.get(top_fp)["last_shown"] is not None
    assert db.get(top_fp)["status"] == "shown"

    # --- a day later, the just-shown jobs are in cooldown ---
    now1 = _fmt(common.parse_ts(now0) + dt.timedelta(days=1))
    result2 = rank.rank(db.all(), rules, now1, cfg)
    assert result2["counts"]["in_cooldown"] >= len(result1["ranked"])
    db.save()

    # --- learn a dismissal from the Ashby job (title "Senior AI Engineer" -> ml-engineering family) ---
    families = disinterest.load_families()
    ashby_job = db.get(fps["ashby"])
    assert disinterest.family_for(ashby_job["title"], families) == "ml-engineering"
    rules, msg, learned_rule = disinterest.learn_dismissal(ashby_job, rules, "not the roles I want", now1, families)
    assert learned_rule["family"] == "ml-engineering" and learned_rule["strength"] == "soft"
    disinterest.save_rules(home / "memory" / "disinterest.json", rules)

    # a fresh job matching the same family must be penalized (soft rule) on the next rank
    synth = db.upsert({"title": "AI Engineer II", "company": "NewCo", "location": "Reston, VA", "remote": "hybrid",
                        "url": "https://newco.example/jobs/ai-eng-2", "posted_at": now1[:10],
                        "content_hash": "abc123def4567890", "fit_score": 70, "fit_breakdown": {"total": 70},
                        "fit_reasons": ["strong match"]}, now=now1)
    db.save()

    result3 = rank.rank(db.all(), rules, now1, cfg)
    hit = next((r for r in result3["ranked"] if r["fingerprint"] == synth["fingerprint"]), None)
    if hit is not None:
        # soft rule penalizes but doesn't hide outright
        assert hit["suppressed_by"] == learned_rule["id"]
        assert hit["penalty"] == learned_rule["penalty"]
        assert hit["adjusted_fit"] == 70 - learned_rule["penalty"]
    else:
        # or the penalty pushed it below min_fit_to_show -> suppressed entirely
        assert result3["counts"]["suppressed"] >= 1
