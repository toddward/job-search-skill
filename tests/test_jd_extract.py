import json, jd_extract as jx

def test_greenhouse_json(fixtures):
    j = jx.extract((fixtures / "jd_greenhouse.json").read_text(), url="https://boards-api.greenhouse.io/v1/boards/anthropic/jobs/4512345")
    assert j["source_layer"] == "greenhouse" and j["title"] == "Staff AI Solutions Architect" and j["company"] == "Anthropic"
    assert "Kubernetes" in " ".join(j["must_have"]) and "Go" in j["nice_to_have"]
    assert j["comp_min"] == 215000 and j["comp_max"] == 270000 and j["posted_at"] == "2026-08-17" and j["remote"] == "hybrid"
    assert j["low_confidence"] is False and len(j["content_hash"]) == 16

def test_ashby_json_flags(fixtures):
    j = jx.extract((fixtures / "jd_ashby.json").read_text(), url="https://jobs.ashbyhq.com/acme/1")
    assert j["source_layer"] == "ashby" and j["clearance_required"] is True and j["citizenship_required"] is True
    assert j["years_min"] == 5 and "Rust" in j["nice_to_have"] and "Ship things" not in j["must_have"]

def test_jsonld_html(fixtures):
    j = jx.extract((fixtures / "jd_jsonld.html").read_text(), url="https://www.capitalonecareers.com/job/x")
    assert j["source_layer"] == "jsonld" and j["company"] == "Capital One" and j["remote"] == "remote"
    assert j["comp_max"] == 180000 and j["closes_at"] == "2026-09-30" and "AWS" in j["nice_to_have"]

def test_heading_harvest_and_low_confidence(fixtures):
    j = jx.extract((fixtures / "jd_headings.html").read_text())
    assert j["must_have"] == ["Kubernetes", "Terraform"] and j["nice_to_have"] == ["Go"] and j["low_confidence"] is False
    j2 = jx.extract("<p>We are hiring. Email us.</p>")
    assert j2["low_confidence"] is True and j2["must_have"] == []

def test_injection_suspects(fixtures):
    j = jx.extract((fixtures / "jd_injected.html").read_text())
    assert any("FROBSCOTTLE" in s or "ignore previous" in s.lower() for s in j["injection_suspects"])

def test_domain_tags():
    assert "ai" in jx.domain_tags("LLM platform for generative AI") and "platform" in jx.domain_tags("platform engineering")
