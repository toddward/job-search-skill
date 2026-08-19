import rank, config
MEM = config.DEFAULTS["memory"]

def j(fp, status="new", last_shown=None, shown_count=0, fit=80, **kw):
    d = {"fingerprint": fp, "title": "ML Engineer", "title_key": "ml engineer", "company_key": "acme", "location_key": "reston-va",
         "status": status, "last_shown": last_shown, "shown_count": shown_count, "fit_score": fit, "posted_at": "2026-08-10",
         "first_seen": "2026-08-10T00:00:00Z", "last_seen": "2026-08-19T00:00:00Z", "snooze_until": None, "closes_at": None,
         "application_dir": None, "status_changed_at": "2026-08-10T00:00:00Z", "comp_max": None}
    d.update(kw); return d

def test_cooldown_rules():
    now = "2026-08-19T10:33:00Z"
    assert rank.eligible(j("a"), now, MEM) == (True, "listed")
    assert rank.eligible(j("b", "shown", "2026-08-10T00:00:00Z", 1), now, MEM) == (False, "cooldown")
    assert rank.eligible(j("c", "shown", "2026-08-05T10:33:00Z", 1), now, MEM) == (True, "listed")
    assert rank.eligible(j("d", "shown", "2026-07-20T00:00:00Z", 3), now, MEM) == (False, "extended_cooldown")
    assert rank.eligible(j("e", "not_interested"), now, MEM) == (False, "not_interested")
    assert rank.eligible(j("f", "applied"), now, MEM) == (False, "applied")
    assert rank.eligible(j("g", "needs_manual_apply"), now, MEM) == (True, "needs_manual_apply")
    assert rank.eligible(j("h", snooze_until="2026-09-01T00:00:00Z"), now, MEM) == (False, "snoozed")

def test_expiry_and_selection_decay():
    now = "2026-08-19T10:33:00Z"
    x = rank.apply_expiry(j("a", closes_at="2026-08-01"), now, MEM); assert x["status"] == "expired"
    y = rank.apply_expiry(j("b", last_seen="2026-06-01T00:00:00Z"), now, MEM); assert y["status"] == "expired"
    z = rank.apply_expiry(j("c", "selected", status_changed_at="2026-08-01T00:00:00Z"), now, MEM); assert z["status"] == "shown"
    k = rank.apply_expiry(j("d", "selected", status_changed_at="2026-08-18T00:00:00Z"), now, MEM); assert k["status"] == "selected"

def test_rank_orders_penalizes_and_counts():
    now = "2026-08-19T10:33:00Z"
    cfg = {"memory": MEM, "search": dict(config.DEFAULTS["search"], min_results=2, max_results=3), "scoring": config.DEFAULTS["scoring"]}
    rules = [{"id": "dis-001", "scope": "title", "pattern": r"\bsales\b", "strength": "soft", "penalty": 20, "created_by": "generalized", "hits": 0},
             {"id": "dis-002", "scope": "company", "pattern": "badco", "strength": "hard", "created_by": "user", "hits": 0}]
    jobs = [j("a", fit=70), j("b", fit=85, title="Sales Engineer", title_key="sales engineer"), j("c", fit=60, company_key="badco"),
            j("d", fit=95, status="needs_manual_apply"), j("e", fit=50, status="shown", last_shown="2026-08-18T00:00:00Z", shown_count=1),
            j("f", fit=93, title="Sales Lead", title_key="sales lead", status="new")]
    rules[0]["strength"] = "hard"
    r = rank.rank(jobs, rules, now, cfg)
    ids = [x["fingerprint"] for x in r["ranked"]]
    assert ids[0] == "a" and "c" not in ids and "d" not in ids
    assert [x["fingerprint"] for x in r["manual"]] == ["d"]
    assert [x["fingerprint"] for x in r["suppressed_high_fit"]] == ["f"]
    assert r["counts"]["in_cooldown"] == 1 and r["counts"]["suppressed"] >= 2 and r["widen"] is True
