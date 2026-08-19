import fingerprint as fp

def test_company_key_strips_legal_suffixes():
    assert fp.company_key("Anthropic, PBC") == "anthropic"
    assert fp.company_key("Capital One Financial Corp.") == "capital one financial"
    assert fp.company_key("Booz Allen Hamilton Inc") == "booz allen"
    assert fp.company_key("Amazon Web Services LLC") == "amazon"

def test_title_key_normalizes_abbreviations_and_noise():
    assert fp.title_key("Sr. ML Eng (Remote) - R0246909") == "senior ml engineer"
    assert fp.title_key("Staff AI Solutions Architect") == "staff ai solutions architect"

def test_location_key():
    assert fp.location_key("Reston, Virginia") == "reston-va"
    assert fp.location_key("Washington, D.C.") == "washington-dc"
    assert fp.location_key("Remote - US", "remote") == "remote-us"
    assert fp.location_key("") == "unknown"

def test_canonical_url_strips_tracking_and_sorts():
    u = "https://www.linkedin.com/jobs/view/4198877612/?refId=abc&trackingId=xyz&position=1"
    assert fp.canonical_url(u) == "https://linkedin.com/jobs/view/4198877612"
    g = "https://job-boards.greenhouse.io/anthropic/jobs/4512345?gh_src=linkedin&b=2&a=1"
    assert fp.canonical_url(g) == "https://job-boards.greenhouse.io/anthropic/jobs/4512345?a=1&b=2"

def test_fingerprint_stable_across_sources():
    a = fp.fingerprint("Anthropic", "Staff AI Solutions Architect", "Reston, VA")
    b = fp.fingerprint("Anthropic PBC", "Staff AI Solutions Architect (Hybrid)", "Reston, Virginia")
    assert a == b and len(a) == 16
    assert fp.fingerprint("Anthropic", "Senior AI Solutions Architect", "Reston, VA") != a

def test_detect_source_and_priority():
    assert fp.detect_source("https://job-boards.greenhouse.io/x/jobs/1") == "greenhouse"
    assert fp.detect_source("https://jobs.lever.co/x/1") == "lever"
    assert fp.detect_source("https://jobs.ashbyhq.com/x/1") == "ashby"
    assert fp.detect_source("https://redhat.wd5.myworkdayjobs.com/en-US/jobs/job/x") == "workday"
    assert fp.detect_source("https://www.indeed.com/viewjob?jk=1") == "indeed"
    assert fp.canonical_priority("https://job-boards.greenhouse.io/x/jobs/1") < fp.canonical_priority("https://www.linkedin.com/jobs/view/1")
    assert fp.canonical_priority("https://www.linkedin.com/jobs/view/1") < fp.canonical_priority("https://www.indeed.com/viewjob?jk=1")

def test_titles_similar():
    assert fp.titles_similar("Senior ML Engineer", "Sr ML Eng")
    assert not fp.titles_similar("Senior ML Engineer", "Director of Engineering")
