import fit_score as fs, config

CFG = dict(config.DEFAULTS["scoring"], resume_seniority="staff", home_metro=["reston-va"], ok_metros=["remote-us"],
           target_domains=["ai", "ml", "platform"], target_base=200000, holds_clearance=False)

def job(**kw):
    j = {"title": "Staff ML Platform Engineer", "location_key": "reston-va", "remote": "hybrid",
         "must_have": ["Kubernetes", "Python", "LLM inference", "Terraform"], "nice_to_have": ["Go", "Rust", "vLLM"],
         "domain_tags": ["ai", "platform"], "comp_max": 250000, "clearance_required": False,
         "citizenship_required": False, "sponsorship_unavailable": False}
    j.update(kw); return j

def test_perfect_match_scores_high(fixtures):
    master = (fixtures / "master.md").read_text()
    r = fs.score(master, job(), CFG, age_days=3)
    assert r["total"] >= 88 and r["caps"] == [] and r["must_have_coverage"] == 1.0
    assert set(r["components"]) == {"must_have", "skills", "seniority", "location", "domain", "recency", "comp"}

def test_synonym_groups_are_symmetric(fixtures):
    master = (fixtures / "master.md").read_text()
    a = fs.score(master, job(must_have=["k8s", "python"]), CFG, 3)["total"]
    b = fs.score(master, job(must_have=["Kubernetes", "Python"]), CFG, 3)["total"]
    assert a == b

def test_clearance_cap(fixtures):
    master = (fixtures / "master.md").read_text()
    r = fs.score(master, job(clearance_required=True), CFG, 3)
    assert r["total"] <= 25 and "clearance_not_held" in r["caps"]
    r2 = fs.score(master, job(clearance_required=False, clearance_eligible_ok=True), CFG, 3)
    assert r2["total"] > 25

def test_hard_requirement_floor_and_missing_list(fixtures):
    master = (fixtures / "master.md").read_text()
    r = fs.score(master, job(must_have=["Salesforce", "SAP", "COBOL", "Java"]), CFG, 3)
    assert r["total"] <= 45 and "must_have_floor" in r["caps"] and "Salesforce" in r["missing_must_haves"]

def test_no_comp_is_neutral_and_recency_decays(fixtures):
    master = (fixtures / "master.md").read_text()
    r1 = fs.score(master, job(comp_max=None), CFG, 3)
    assert abs(r1["components"]["comp"]["ratio"] - 0.6) < 1e-9
    assert fs.score(master, job(), CFG, 60)["components"]["recency"]["ratio"] == 0.2

def test_seniority_ladder():
    assert fs.seniority_level("Staff Engineer") == fs.seniority_level("Staff ML Platform Engineer")
    assert fs.seniority_level("Director of Engineering") > fs.seniority_level("Senior Engineer") > fs.seniority_level("Software Engineer II")

def test_deterministic(fixtures):
    master = (fixtures / "master.md").read_text()
    import json
    assert json.dumps(fs.score(master, job(), CFG, 3), sort_keys=True) == json.dumps(fs.score(master, job(), CFG, 3), sort_keys=True)

def test_realistic_jd_scores_on_harvested_terms(fixtures):
    """C1: jd_extract emits bullet sentences; fit_score must score the harvested TERMS."""
    import jd_extract as jx
    master = (fixtures / "master.md").read_text()
    j = jx.extract((fixtures / "jd_greenhouse.json").read_text())
    r = fs.score(master, j, CFG, 3)
    assert r["must_have_coverage"] >= 0.9 and r["total"] >= 80
    assert "must_have_floor" not in r["caps"] and r["missing_must_haves"] == []
    # the ashby posting is still capped by the clearance red flag
    a = fs.score(master, jx.extract((fixtures / "jd_ashby.json").read_text()), CFG, 3)
    assert a["total"] <= 25 and "clearance_not_held" in a["caps"]

def test_prose_lists_still_scored_when_no_terms_present(fixtures):
    master = (fixtures / "master.md").read_text()
    r = fs.score(master, job(must_have_terms=["Kubernetes"], must_have=["Salesforce"]), CFG, 3)
    assert r["must_have_coverage"] == 1.0 and r["missing_must_haves"] == []

def test_row_merge_supplies_location_key(fixtures, tmp_path, capsys):
    import json, jd_extract as jx
    master = (fixtures / "master.md").read_text()
    j = jx.extract((fixtures / "jd_greenhouse.json").read_text())
    assert "location_key" not in j
    merged = fs.merge_row(j, {"location_key": "reston-va", "remote": "hybrid", "fit_score": 3, "title": "nope"})
    assert fs.score(master, j, CFG, 3)["components"]["location"]["ratio"] == 0.5
    assert fs.score(master, merged, CFG, 3)["components"]["location"]["ratio"] == 1.0
    assert merged["title"] == j["title"] and "fit_score" not in merged  # only location_key/remote cross over
    (tmp_path / "job.json").write_text(json.dumps(j))
    (tmp_path / "row.json").write_text(json.dumps({"location_key": "reston-va"}))
    (tmp_path / "master.md").write_text(master)
    (tmp_path / "cfg.json").write_text(json.dumps(CFG))
    fs.main(["--master", str(tmp_path / "master.md"), "--job", str(tmp_path / "job.json"),
             "--config-json", str(tmp_path / "cfg.json"), "--age-days", "3", "--row", str(tmp_path / "row.json")])
    out = json.loads(capsys.readouterr().out)
    assert out["components"]["location"]["ratio"] == 1.0 and out["total"] == 100
