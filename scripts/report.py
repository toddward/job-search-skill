#!/usr/bin/env python3
"""Render/write the daily report with a machine-readable index; resolve user-typed numbers back to fingerprints."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import common

INDEX_RE = re.compile(r"```json job-index\n(.*?)\n```", re.S)

def _comp(j):
    lo, hi = j.get("comp_min"), j.get("comp_max")
    if lo and hi: return f"${lo//1000}–{hi//1000}k"
    if hi: return f"up to ${hi//1000}k"
    return "not listed"

def render(run: dict, result: dict, learned=(), decisions=()) -> str:
    c = result.get("counts", {})
    date = (run.get("started_at") or common.utcnow())[:10]
    L = [f"# Job search — {date} · run {run.get('run_id','')[:8]} · {c.get('seen',0)} seen, {c.get('new',0)} new, "
         f"{c.get('suppressed',0)} suppressed, {c.get('in_cooldown',0)} in cooldown, {c.get('listed',0)} listed", ""]
    if run.get("query"): L.append(f"Query: {run['query']}  ")
    if run.get("boards_failed"): L.append("Boards failed: " + "; ".join(f"{b['board']} ({b['reason']})" for b in run["boards_failed"]) + "  ")
    L += ["", "## Top matches", "", "| # | fit | role | company | location | comp | posted | source | link |", "|---|---|---|---|---|---|---|---|---|"]
    items = []
    for n, j in enumerate(result.get("ranked", []), 1):
        L.append(f"| {n} | {j.get('adjusted_fit', j.get('fit_score'))} | {j.get('title')} | {j.get('company')} | {j.get('location','')} | {_comp(j)} | "
                 f"{j.get('posted_at') or '—'} | {j.get('source','')} | {j.get('canonical_url','')} |")
        items.append({"n": n, "fp": j["fingerprint"], "title": j.get("title"), "company": j.get("company"), "fit": j.get("adjusted_fit", j.get("fit_score")), "url": j.get("canonical_url")})
    L.append("")
    for n, j in enumerate(result.get("ranked", []), 1):
        why = "; ".join((j.get("fit_reasons") or [])[:3]) or "—"
        miss = ", ".join(((j.get("fit_breakdown") or {}).get("missing_must_haves") or [])[:4]) or "none"
        extra = f" · penalty −{j['penalty']} ({j.get('suppressed_by')})" if j.get("penalty") else ""
        L.append(f"- **#{n} {j.get('title')} @ {j.get('company')}** — why: {why} · missing must-haves: {miss}{extra}")
    manual = []
    if result.get("manual"):
        L += ["", "## Needs your decision", ""]
        for i, j in enumerate(result["manual"], 1):
            L.append(f"- M{i} {j.get('title')} @ {j.get('company')} — {j.get('status_reason') or 'needs manual apply'} — {j.get('canonical_url','')}")
            manual.append({"n": f"M{i}", "fp": j["fingerprint"]})
    supp = []
    if result.get("suppressed_high_fit"):
        L += ["", "## Suppressed but high-fit", ""]
        for i, j in enumerate(result["suppressed_high_fit"], 1):
            L.append(f"- S{i} {j.get('adjusted_fit')} {j.get('title')} @ {j.get('company')} — rule {j.get('rule_id')} (undo: /job-search unhide {j.get('rule_id')})")
            supp.append({"n": f"S{i}", "fp": j["fingerprint"], "rule": j.get("rule_id")})
    if learned:
        L += ["", "## Learned today", ""] + [f"- {x}" for x in learned]
    if decisions:
        L += ["", "## Tell me why so I can learn", ""] + [f"- {x}" for x in decisions]
    L += ["", "## Reply with", "", "```", "apply 1,3        tailor + fill applications (stops before submit)",
          'no 5 "reason"    not interested, and learn from it', "snooze 7 30d     hide #7 for 30 days", "show 1           full JD, fit breakdown, tailored-resume diff", "```", ""]
    idx = {"run_id": run.get("run_id"), "date": date, "generated_at": common.utcnow(), "items": items, "manual": manual, "suppressed": supp}
    L += ["## Index (machine-readable — do not edit)", "", "```json job-index", json.dumps(idx, ensure_ascii=False), "```", ""]
    return "\n".join(L)

def load_index_text(md: str) -> dict:
    m = INDEX_RE.search(md)
    if not m:
        raise ValueError("report has no job-index block")
    return json.loads(m.group(1))

def load_index(path: Path) -> dict:
    return load_index_text(Path(path).read_text(encoding="utf-8"))

def append_run(home: Path, run: dict) -> None:
    common.append_jsonl(Path(home) / "memory" / "runs.jsonl", run)

def write(home: Path, date: str, run: dict, result: dict, learned=(), decisions=(), db=None) -> Path:
    home = Path(home)
    rdir = home / "reports"; rdir.mkdir(parents=True, exist_ok=True)
    path = rdir / f"{date}.md"
    n = 1
    while path.exists():
        try:
            if load_index(path).get("run_id") == run.get("run_id"):
                break
        except ValueError:
            pass
        n += 1
        path = rdir / f"{date}.r{n}.md"
    md = render(run, result, learned, decisions)
    common.atomic_write(path, md)
    if db is not None:
        db.mark_shown([j["fingerprint"] for j in result.get("ranked", [])], now=common.utcnow())
        db.save()
    run = dict(run, report=str(path.relative_to(home)), counts=result.get("counts", {}), ended_at=common.utcnow())
    append_run(home, run)
    return path

def latest_report(home: Path, date: str | None = None, run_id: str | None = None):
    home = Path(home)
    runs = common.read_jsonl(home / "memory" / "runs.jsonl")
    if run_id:
        for r in reversed(runs):
            if r.get("run_id", "").startswith(run_id) and r.get("report") and (home / r["report"]).exists():
                return home / r["report"]
        return None
    if date:
        cands = sorted((home / "reports").glob(f"{date}*.md"), key=lambda p: (len(p.name), p.name))
        return cands[-1] if cands else None
    for r in reversed(runs):
        if r.get("report") and (home / r["report"]).exists():
            return home / r["report"]
    return None

def resolve_numbers(tokens: list[str], index: dict, db, now: str | None = None) -> list[dict]:
    now = now or common.utcnow()
    if index.get("generated_at") and common.days_between(index["generated_at"], now) > 14:
        raise ValueError(f"report index from {index.get('date')} is older than 14 days; run a new scan before using numbers")
    table = {str(i["n"]): i for i in index.get("items", [])}
    table.update({m["n"]: m for m in index.get("manual", [])})
    table.update({s["n"]: s for s in index.get("suppressed", [])})
    out = []
    for t in tokens:
        if t in table:
            e = table[t]; job = db.get(e["fp"]) if db else None
            out.append({"n": t, "fp": e["fp"], "title": (job or e).get("title"), "company": (job or e).get("company")})
            continue
        job = db.find(t) if db else None
        if job:
            out.append({"n": t, "fp": job["fingerprint"], "title": job.get("title"), "company": job.get("company")}); continue
        raise ValueError(f"'{t}' is not a number in report {index.get('date')} nor a known fingerprint")
    return out

def main(argv=None):
    import argparse, jobs_db
    ap = argparse.ArgumentParser(description="report tools")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write"); w.add_argument("--run-json", required=True); w.add_argument("--result-json", required=True); w.add_argument("--date")
    r = sub.add_parser("resolve"); r.add_argument("tokens"); r.add_argument("--from"); r.add_argument("--run")
    sub.add_parser("latest")
    a = ap.parse_args(argv)
    home = common.data_home(a.home); db = jobs_db.JobsDB(home / "memory" / "jobs.jsonl")
    if a.cmd == "write":
        run = json.loads(Path(a.run_json).read_text()); result = json.loads(Path(a.result_json).read_text())
        print(write(home, a.date or common.utcnow()[:10], run, result, db=db))
    elif a.cmd == "resolve":
        p = latest_report(home, getattr(a, "from"), a.run)
        if not p:
            sys.exit("no report found")
        print(json.dumps(resolve_numbers(a.tokens.split(","), load_index(p), db)))
    elif a.cmd == "latest":
        p = latest_report(home); print(p or "")

if __name__ == "__main__":
    main()
