import boards, config

def test_parse_table(fixtures):
    rows = boards.parse_table((fixtures / "boards.md").read_text())
    assert [r["board"] for r in rows] == ["LinkedIn", "USAJOBS", "Indeed", "ATS public boards"]
    assert rows[2]["enabled"] is False and rows[0]["method"] == "firecrawl"

def test_parse_query_free_text():
    q = boards.parse_query("I'm searching for AI based jobs in the Reston, VA area", config.DEFAULTS["search"])
    assert q["location"] == "Reston, VA" and "ai" in [k.lower() for k in q["keywords"]] and q["radius_miles"] == 25
    q2 = boards.parse_query("remote machine learning engineer roles", config.DEFAULTS["search"])
    assert q2["remote"] is True and q2["location"] == ""

def test_render_substitutes_and_encodes(fixtures):
    rows = boards.parse_table((fixtures / "boards.md").read_text())
    q = {"keywords": ["AI engineer"], "location": "Reston, VA", "radius_miles": 25, "remote": None}
    out = boards.render(rows, q)
    assert len(out) == 3  # Indeed disabled
    li = next(o for o in out if o["board"] == "LinkedIn")
    assert "keywords=AI%20engineer" in li["url"] and "location=Reston%2C%20VA" in li["url"] and "distance=25" in li["url"]
    usa = next(o for o in out if o["board"] == "USAJOBS")
    assert "LocationName=Reston%2C%20Virginia" in usa["url"]
    ats = next(o for o in out if o["board"] == "ATS public boards")
    assert ats["method"] == "firecrawl-search" and "AI engineer" in ats["url"] and "{" not in ats["url"]

def test_location_alias():
    assert boards.location_alias("Capital One", "Reston, VA") == "McLean, VA"
    assert boards.location_alias("Dice", "Reston, VA") == "Reston, VA"

def test_parse_query_strips_radius_phrase():
    q = boards.parse_query("senior ML engineer jobs near Arlington, VA within 50 miles", config.DEFAULTS["search"])
    assert q["radius_miles"] == 50 and q["location"] == "Arlington, VA"
    kws = [k.lower() for k in q["keywords"]]
    assert "within" not in kws and "50" not in kws and "miles" not in kws

def test_location_alias_word_boundary_and_non_dc_passthrough():
    assert boards.location_alias("Capital One", "Savannah, GA") == "Savannah, GA"
    assert boards.location_alias("Capital One", "Austin, TX") == "Austin, TX"
    assert boards.location_alias("Capital One", "Reston, VA") == "McLean, VA"
    assert boards.location_alias("Amazon AWS Herndon", "Arlington, Virginia") == "Herndon, VA"
    assert boards.location_alias("Built In DC", "") == ""

def test_default_asset_parses():
    import common
    rows = boards.parse_table((common.SKILL_DIR / "assets" / "job-board-links.default.md").read_text())
    assert len(rows) >= 20 and sum(1 for r in rows if r["enabled"]) >= 8
    assert all(r["method"] in {"firecrawl", "webfetch", "playwright"} for r in rows)
