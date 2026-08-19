#!/usr/bin/env python3
"""Eligibility (cooldown/snooze/status), expiry, and ranking of jobs for a report."""
from __future__ import annotations
import json, sys
import common, disinterest as di

def eligible(job: dict, now: str, mem: dict):
    st = job.get("status")
    if st == "needs_manual_apply":
        return True, "needs_manual_apply"
    if st in ("not_interested", "applied", "expired"):
        return False, st
    su = job.get("snooze_until")
    if su and common.parse_ts(su) > common.parse_ts(now):
        return False, "snoozed"
    if st in ("shown", "selected"):
        ls = job.get("last_shown")
        if not ls:
            return True, "listed"
        days = common.days_between(ls, now)
        if int(job.get("shown_count", 0)) >= 3:
            return (True, "listed") if days >= mem.get("extended_cooldown_days", 45) else (False, "extended_cooldown")
        return (True, "listed") if days >= mem.get("cooldown_days", 14) else (False, "cooldown")
    return True, "listed"

def apply_expiry(job: dict, now: str, mem: dict) -> dict:
    today = now[:10]
    if job.get("status") in ("applied", "not_interested", "expired"):
        return job
    if job.get("closes_at") and job["closes_at"] < today:
        job["status"], job["status_reason"], job["status_changed_at"] = "expired", "closes_at passed", now
    elif job.get("last_seen") and common.days_between(job["last_seen"], now) > mem.get("expire_after_days", 45):
        job["status"], job["status_reason"], job["status_changed_at"] = "expired", "not seen on any board", now
    elif job.get("status") == "selected" and not job.get("application_dir") and \
            common.days_between(job.get("status_changed_at") or job.get("first_seen"), now) > mem.get("selection_expiry_days", 7):
        job["status"], job["status_reason"], job["status_changed_at"] = "shown", "selection expired", now
    return job

def rank(jobs: list[dict], rules: list[dict], now: str, cfg: dict) -> dict:
    mem, search = cfg["memory"], cfg["search"]
    min_fit = (cfg.get("scoring") or {}).get("min_fit_to_show", 0)
    ranked, manual, supp_hi = [], [], []
    counts = {"seen": len(jobs), "new": 0, "suppressed": 0, "in_cooldown": 0, "listed": 0}
    for job in jobs:
        apply_expiry(job, now, mem)
        if job.get("status") == "new":
            counts["new"] += 1
        ok, why = eligible(job, now, mem)
        if why == "needs_manual_apply":
            manual.append(job); continue
        if not ok:
            if why in ("cooldown", "extended_cooldown", "snoozed"):
                counts["in_cooldown"] += 1
            continue
        ev = di.evaluate(job, rules)
        job["suppressed_by"] = ev["rule_id"] if (ev["hidden"] or ev["penalty"]) else None
        if ev["hidden"]:
            counts["suppressed"] += 1; continue
        if ev.get("exempt"):
            supp_hi.append(dict(job, adjusted_fit=job.get("fit_score") or 0, rule_id=ev["rule_id"])); counts["suppressed"] += 1; continue
        adj = (job.get("fit_score") or 0) - ev["penalty"]
        if adj < min_fit:
            counts["suppressed"] += 1; continue
        ranked.append(dict(job, adjusted_fit=adj, penalty=ev["penalty"]))
    ranked.sort(key=lambda r: (-r["adjusted_fit"], -int((r.get("posted_at") or "0000-01-01").replace("-", "")), r.get("first_seen") or ""))
    ranked = ranked[: int(search.get("max_results", 12))]
    counts["listed"] = len(ranked)
    return {"ranked": ranked, "manual": manual, "suppressed_high_fit": supp_hi, "counts": counts,
            "widen": len(ranked) < int(search.get("min_results", 10))}

def main(argv=None):
    import argparse, config, jobs_db
    ap = argparse.ArgumentParser(description="rank jobs")
    ap.add_argument("--home"); ap.add_argument("--now", default=common.utcnow())
    a = ap.parse_args(argv)
    home = common.data_home(a.home); cfg = config.load(home)
    db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    rules = di.load_rules(home / "memory" / "disinterest.json")
    out = rank(db.all(), rules, a.now, cfg)
    db.save(); di.save_rules(home / "memory" / "disinterest.json", rules)
    print(json.dumps(out, ensure_ascii=False))

if __name__ == "__main__":
    main()
