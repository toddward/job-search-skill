import json
from pathlib import Path
import disinterest as di

import hashlib
def job(title, company="Acme", fit=70, loc="reston-va", comp_max=None):
    return {"fingerprint": hashlib.sha256((title + company).encode()).hexdigest()[:16], "title": title, "title_key": title.lower(), "company_key": company.lower(),
            "location_key": loc, "fit_score": fit, "comp_max": comp_max}

def test_families_load_and_match():
    fams = di.load_families()
    assert di.family_for("Senior Sales Engineer, AI Platform", fams) == "sales-engineering"
    assert di.family_for("Director of Engineering", fams) == "management"
    assert di.family_for("Staff AI Solutions Architect", fams) == "architecture"
    assert di.family_for("Underwater Basket Weaver", fams) is None

def test_ladder_soft_then_hard(home):
    fams = di.load_families(); rules = []
    rules, msg, r1 = di.learn_dismissal(job("Senior Sales Engineer"), rules, "quota", "2026-08-05T00:00:00Z", fams)
    assert r1["strength"] == "soft" and r1["penalty"] == 20 and r1["family"] == "sales-engineering" and "dis-001" == r1["id"]
    ev = di.evaluate(job("Solutions Engineer"), rules)
    assert ev["hidden"] is False and ev["penalty"] == 20 and ev["rule_id"] == "dis-001"
    rules, msg, r2 = di.learn_dismissal(job("Field Engineer", company="Other"), rules, "also sales", "2026-08-14T00:00:00Z", fams)
    assert r2["id"] == "dis-001" and r2["strength"] == "hard" and r2["promoted_from"] == "soft" and len(r2["evidence"]) == 2
    assert di.evaluate(job("Solutions Engineer"), rules)["hidden"] is True
    assert "HARD" in msg and "unhide dis-001" in msg

def test_company_dismissal_is_hard_and_literal():
    fams = di.load_families()
    rules, msg, r = di.learn_dismissal(job("ML Engineer", company="TekSystems"), [], "staffing firm", "2026-08-05T00:00:00Z", fams, scope="company")
    assert r["scope"] == "company" and r["strength"] == "hard"
    assert di.evaluate(job("ML Engineer", company="TekSystems"), rules)["hidden"] is True
    assert di.evaluate(job("ML Engineer", company="Anthropic"), rules)["hidden"] is False

def test_generalized_rule_never_hides_high_fit():
    fams = di.load_families()
    rules, _, _ = di.learn_dismissal(job("Sales Engineer"), [], "x", "2026-08-01T00:00:00Z", fams)
    rules, _, _ = di.learn_dismissal(job("Account Executive"), rules, "x", "2026-08-02T00:00:00Z", fams)
    ev = di.evaluate(job("Solutions Engineer", fit=93), rules)
    assert ev["hidden"] is False and ev.get("exempt") is True and ev["rule_id"] == "dis-001"
    user_rule = {"id": "dis-009", "scope": "title", "pattern": r"\bsolutions? engineer\b", "strength": "hard",
                 "created_by": "user", "hits": 0, "penalty": 0, "reason": "", "created": "2026-08-01", "evidence": []}
    assert di.evaluate(job("Solutions Engineer", fit=95), [user_rule])["hidden"] is True

def test_unhide_and_retro_hits(home):
    fams = di.load_families()
    rules, _, _ = di.learn_dismissal(job("Sales Engineer"), [], "x", "2026-08-01T00:00:00Z", fams)
    rules, _, _ = di.learn_dismissal(job("Account Executive"), rules, "x", "2026-08-02T00:00:00Z", fams)
    assert di.retro_hits(rules[0], [job("Solutions Engineer"), job("ML Engineer"), job("Field Engineer")]) == 2
    rules, msg = di.unhide(rules, "dis-001", to="soft")
    assert rules[0]["strength"] == "soft"
    rules, msg = di.unhide(rules, "dis-001", to=None)
    assert rules == []
    p = home / "memory" / "disinterest.json"
    di.save_rules(p, [{"id": "dis-001", "scope": "title", "pattern": "x", "strength": "soft", "penalty": 20, "hits": 0}])
    assert di.load_rules(p)[0]["id"] == "dis-001"

def test_architect_titles_prefer_architecture_family():
    fams = di.load_families()
    assert di.family_for("AI Platform Architect", fams) == "architecture"
    assert di.family_for("Cloud Architect", fams) == "architecture"
    assert di.family_for("Platform Engineer", fams) == "infrastructure"
    assert di.family_for("SRE", fams) == "infrastructure"

def test_repeat_dismissal_message_has_undo():
    fams = di.load_families(); rules = []
    rules, _, _ = di.learn_dismissal(job("Sales Engineer"), rules, "x", "2026-08-01T00:00:00Z", fams)
    rules, _, _ = di.learn_dismissal(job("Account Executive"), rules, "x", "2026-08-02T00:00:00Z", fams)
    rules, msg, _ = di.learn_dismissal(job("Field Engineer"), rules, "x", "2026-08-03T00:00:00Z", fams)
    assert "unhide dis-001" in msg and "HARD" in msg
