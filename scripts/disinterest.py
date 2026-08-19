#!/usr/bin/env python3
"""Disinterest rules: evaluate, learn from dismissals (soft -> hard ladder), unhide, retro hits."""
from __future__ import annotations
import json, re, sys
from pathlib import Path
import common

FAMILIES_PATH = common.SKILL_DIR / "references" / "title-families.md"
SOFT_PENALTY = 20
PROMOTE_WINDOW_DAYS = 90
HIGH_FIT_EXEMPT = 90

def load_families(path: Path = FAMILIES_PATH) -> list[dict]:
    fams = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---") or "Family" in line and "Regex" in line:
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 3:
            continue
        regex = cells[2].strip("`").replace("\\|", "|")
        fams.append({"family": cells[1], "regex": regex, "stems": cells[0]})
    return fams

def family_for(title: str, families: list[dict]) -> str | None:
    t = (title or "").lower()
    for f in families:
        if re.search(f["regex"], t, re.I):
            return f["family"]
    return None

def load_rules(path: Path) -> list[dict]:
    data = common.read_json(path, {"rules": []}) or {"rules": []}
    return list(data.get("rules", []))

def save_rules(path: Path, rules: list[dict]) -> None:
    common.write_json(path, {"rules": rules})

def _next_id(rules: list[dict]) -> str:
    nums = [int(r["id"].split("-")[1]) for r in rules if re.match(r"^dis-\d+$", r.get("id", ""))]
    return f"dis-{(max(nums) + 1) if nums else 1:03d}"

def _matches(rule: dict, job: dict) -> bool:
    scope = rule.get("scope", "title")
    if scope == "title":
        return bool(re.search(rule["pattern"], job.get("title_key") or job.get("title", ""), re.I))
    if scope == "company":
        return bool(re.fullmatch(rule["pattern"], job.get("company_key", ""), re.I))
    if scope == "location":
        return bool(re.search(rule["pattern"], job.get("location_key", ""), re.I))
    if scope == "keyword":
        hay = " ".join(str(job.get(k, "")) for k in ("title", "description_text", "notes"))
        return bool(re.search(rule["pattern"], hay, re.I))
    if scope == "comp":
        cm = job.get("comp_max")
        return cm is not None and rule.get("min_base") and cm < rule["min_base"]
    return False

def evaluate(job: dict, rules: list[dict]) -> dict:
    hidden, penalty, rule_id, hits, exempt = False, 0, None, [], False
    for r in rules:
        if not _matches(r, job):
            continue
        r["hits"] = int(r.get("hits", 0)) + 1
        hits.append(r["id"])
        if r.get("strength") == "hard":
            if r.get("created_by") == "generalized" and (job.get("fit_score") or 0) >= HIGH_FIT_EXEMPT:
                exempt, rule_id = True, rule_id or r["id"]
                continue
            hidden, rule_id = True, r["id"]
            break
        penalty += int(r.get("penalty", SOFT_PENALTY))
        rule_id = rule_id or r["id"]
    return {"hidden": hidden, "penalty": penalty, "rule_id": rule_id, "hits": hits, "exempt": exempt}

def learn_dismissal(job: dict, rules: list[dict], reason: str, now: str, families: list[dict],
                    scope: str = "title", created_by: str = "generalized"):
    rules = list(rules)
    fp = job.get("fingerprint")
    today = now[:10]
    if scope == "company":
        rule = {"id": _next_id(rules), "scope": "company", "pattern": re.escape(job.get("company_key", "")),
                "family": None, "strength": "hard", "penalty": 0, "reason": reason, "created": today,
                "created_by": "user", "evidence": [fp], "hits": 0}
        rules.append(rule)
        return rules, f"Learned: {rule['id']} never show company '{job.get('company_key')}' (HARD). Undo: /job-search unhide {rule['id']}", rule
    if scope == "comp":
        min_base = job.get("comp_max") or 0
        if not min_base:
            return rules, f"Recorded not_interested for {fp} ({reason}); job has no comp_max, no comp rule created.", None
        rule = {"id": _next_id(rules), "scope": "comp", "min_base": min_base, "pattern": "", "family": None,
                "strength": "hard", "penalty": 0, "reason": reason, "created": today, "created_by": "user",
                "evidence": [fp], "hits": 0}
        rules.append(rule)
        return rules, (f"Learned: {rule['id']} never show comp below ${min_base:,.0f} (HARD). "
                        f"Undo: /job-search unhide {rule['id']}"), rule
    fam = family_for(job.get("title", ""), families)
    if not fam:
        return rules, f"Recorded not_interested for {fp} ({reason}); no title family matched, no rule created.", None
    regex = next(f["regex"] for f in families if f["family"] == fam)
    existing = next((r for r in rules if r.get("family") == fam and r.get("scope") == "title"), None)
    if existing is None:
        rule = {"id": _next_id(rules), "scope": "title", "family": fam, "pattern": regex, "strength": "soft",
                "penalty": SOFT_PENALTY, "reason": reason, "created": today, "created_by": created_by,
                "evidence": [fp], "hits": 0}
        rules.append(rule)
        msg = (f"Learned: {rule['id']} {fam} is now SOFT (-{SOFT_PENALTY} fit). Second dismissal within {PROMOTE_WINDOW_DAYS} days makes it HARD.\n"
               f"  Undo: /job-search unhide {rule['id']}")
        return rules, msg, rule
    if fp and fp not in existing.get("evidence", []):
        existing.setdefault("evidence", []).append(fp)
    if existing["strength"] == "soft" and common.days_between(existing["created"] + "T00:00:00Z", now) <= PROMOTE_WINDOW_DAYS:
        existing.update({"strength": "hard", "promoted_from": "soft", "promoted_on": today})
        msg = (f"Learned: {existing['id']} {fam} is now HARD (2nd dismissal in this family since {existing['created']}).\n"
               f"  pattern: {existing['pattern']}\n  Undo: /job-search unhide {existing['id']}   Soften: /job-search unhide {existing['id']} --to soft")
        return rules, msg, existing
    return rules, f"Recorded dismissal under {existing['id']} ({fam}, {existing['strength'].upper()}). Undo: /job-search unhide {existing['id']}", existing

def unhide(rules: list[dict], rule_id: str, to: str | None):
    rules = list(rules)
    r = next((x for x in rules if x["id"] == rule_id), None)
    if r is None:
        return rules, f"No rule {rule_id}."
    if to in ("soft", "hard"):
        r["strength"] = to
        if to == "soft":
            r.setdefault("penalty", SOFT_PENALTY)
        return rules, f"{rule_id} is now {to.upper()}."
    rules.remove(r)
    return rules, f"Deleted {rule_id}."

def retro_hits(rule: dict, jobs: list[dict]) -> int:
    return sum(1 for j in jobs if _matches(rule, j))

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="disinterest rules")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    e = sub.add_parser("evaluate"); e.add_argument("job_json")
    l = sub.add_parser("learn"); l.add_argument("job_json"); l.add_argument("--reason", default=""); l.add_argument("--scope", default="title")
    u = sub.add_parser("unhide"); u.add_argument("rule_id"); u.add_argument("--to")
    a = ap.parse_args(argv)
    home = common.data_home(a.home); path = home / "memory" / "disinterest.json"
    rules = load_rules(path)
    if a.cmd == "list":
        print(json.dumps(rules, indent=2))
    elif a.cmd == "evaluate":
        job = json.loads(Path(a.job_json).read_text()) if Path(a.job_json).exists() else json.loads(a.job_json)
        print(json.dumps(evaluate(job, rules))); save_rules(path, rules)
    elif a.cmd == "learn":
        job = json.loads(Path(a.job_json).read_text()) if Path(a.job_json).exists() else json.loads(a.job_json)
        rules, msg, _ = learn_dismissal(job, rules, a.reason, common.utcnow(), load_families(), scope=a.scope)
        save_rules(path, rules); print(msg)
    elif a.cmd == "unhide":
        rules, msg = unhide(rules, a.rule_id, a.to); save_rules(path, rules); print(msg)

if __name__ == "__main__":
    main()
