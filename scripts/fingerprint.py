#!/usr/bin/env python3
"""Job identity: normalized keys, canonical URLs, fingerprints, source detection."""
from __future__ import annotations
import hashlib, json, re, unicodedata
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, parse_qs

LEGAL = re.compile(r"\b(inc|llc|l l c|ltd|limited|corp|corporation|co|company|pbc|gmbh|plc|sa|nv|ag|ab|oy|pty|the|group)\b")
ALIASES = {"booz allen hamilton": "booz allen", "amazon web services": "amazon", "aws": "amazon",
           "google llc": "google", "alphabet": "google", "meta platforms": "meta", "microsoft corporation": "microsoft"}
NOISE = re.compile(r"\((remote|hybrid|onsite|on-site|us|usa|united states)\)|\b(req|requisition|job)\s*#?\s*[a-z0-9\-]{3,}\b|\b[a-z]{1,3}-?\d{4,}\b", re.I)
STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar", "california": "ca",
    "colorado": "co", "connecticut": "ct", "delaware": "de", "district of columbia": "dc", "d c": "dc", "florida": "fl",
    "georgia": "ga", "hawaii": "hi", "idaho": "id", "illinois": "il", "indiana": "in",
    "iowa": "ia", "kansas": "ks", "kentucky": "ky", "louisiana": "la", "maine": "me",
    "maryland": "md", "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv", "new hampshire": "nh",
    "new jersey": "nj", "new mexico": "nm", "new york": "ny", "north carolina": "nc", "north dakota": "nd",
    "ohio": "oh", "oklahoma": "ok", "oregon": "or", "pennsylvania": "pa", "rhode island": "ri",
    "south carolina": "sc", "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut",
    "vermont": "vt", "virginia": "va", "washington": "wa", "washington state": "wa", "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy"
}
TRACKING = re.compile(r"^(utm_|gh_|lever-|ashby_|ref$|refid$|source$|src$|trk$|trackingid$|position$|pagenum$|from$|alid$|fbclid$|gclid$|mc_)", re.I)
SOURCES = [
    ("greenhouse", r"greenhouse\.io"), ("lever", r"jobs\.lever\.co|lever\.co"), ("ashby", r"ashbyhq\.com"),
    ("workday", r"myworkdayjobs\.com|workday\.com"), ("smartrecruiters", r"smartrecruiters\.com"),
    ("workable", r"workable\.com"), ("icims", r"icims\.com"), ("taleo", r"taleo\.net"),
    ("bamboohr", r"bamboohr\.com"), ("jazzhr", r"applytojob\.com|jazz\.co"), ("rippling", r"rippling\.com"),
    ("usajobs", r"usajobs\.gov"), ("clearancejobs", r"clearancejobs\.com"), ("dice", r"dice\.com"),
    ("builtin", r"builtin\.com"), ("linkedin", r"linkedin\.com"), ("indeed", r"indeed\.com"),
    ("glassdoor", r"glassdoor\.com"), ("ziprecruiter", r"ziprecruiter\.com"), ("wellfound", r"wellfound\.com"),
    ("remoteok", r"remoteok\.com"), ("weworkremotely", r"weworkremotely\.com"), ("hn", r"news\.ycombinator\.com"),
    ("phenom", r"careers\.[a-z0-9-]+\.(com|org)/us/en|phenom"), ("eightfold", r"eightfold\.ai|apply\.careers\.microsoft\.com|searchcareers\.caci\.com"),
]
PRIORITY = {"greenhouse": 0, "lever": 0, "ashby": 0, "workday": 0, "smartrecruiters": 0, "workable": 0, "icims": 0,
            "taleo": 0, "bamboohr": 0, "jazzhr": 0, "rippling": 0, "usajobs": 0, "phenom": 1, "eightfold": 1,
            "other": 2, "linkedin": 3, "dice": 4, "builtin": 4, "clearancejobs": 4, "wellfound": 4,
            "indeed": 5, "glassdoor": 5, "ziprecruiter": 5, "remoteok": 4, "weworkremotely": 4, "hn": 4}

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def company_key(company: str) -> str:
    k = _norm(company)
    k = re.sub(r"\s+", " ", LEGAL.sub(" ", k)).strip()
    return ALIASES.get(k, k)

def title_key(title: str) -> str:
    t = NOISE.sub(" ", (title or "").lower())
    t = _norm(t)
    t = re.sub(r"\b(sr|snr)\b", "senior", t)
    t = re.sub(r"\bjr\b", "junior", t)
    t = re.sub(r"\bmgr\b", "manager", t)
    t = re.sub(r"\beng\b", "engineer", t)
    t = re.sub(r"\bswe\b", "software engineer", t)
    return re.sub(r"\s+", " ", t).strip()

def location_key(location: str, remote: str = "") -> str:
    loc = _norm(location)
    if remote == "remote" or "remote" in loc.split():
        rest = [p for p in loc.split() if p not in ("remote", "us", "usa", "united", "states", "only")]
        return "remote-us" if not rest else "remote-" + "-".join(rest)

    # Handle comma-separated format: split on ALL commas
    if "," in location:
        segments = [_norm(s) for s in location.split(",")]

        # Drop trailing country tokens
        country_tokens = {"united states", "united states of america", "usa", "us", "u s", "america"}
        while segments and segments[-1] in country_tokens:
            segments.pop()

        # If only one segment remains, apply no-comma logic
        if len(segments) == 1:
            loc = segments[0]
        else:
            # Region = last remaining segment (mapped via STATES table)
            region_str = segments[-1]
            region_abbr = STATES.get(region_str, region_str.replace(" ", "-"))

            # City = leading segments with spaces replaced by dashes, then joined
            city_parts = [s.replace(" ", "-") for s in segments[:-1]]
            city = "-".join(city_parts)

            # Combine city and region
            if city and region_abbr:
                return f"{city}-{region_abbr}"
            elif region_abbr:
                return region_abbr
            elif city:
                return city
            else:
                return "unknown"

    # No comma: check if last 1-3 words form a state name/abbr
    words = loc.split()
    region = None
    city_words = words
    for i in range(1, 4):
        if i <= len(words):
            candidate = " ".join(words[-i:])
            if candidate in STATES or candidate.replace("-", " ") in STATES:
                region = candidate
                city_words = words[:-i]
                break
    city = "-".join(city_words) if city_words else ""
    region_str = region or ""

    # Map region via STATES table
    if region_str:
        region_abbr = STATES.get(region_str, region_str.replace(" ", "-"))
    else:
        region_abbr = ""

    # Combine city and region
    if city and region_abbr:
        return f"{city}-{region_abbr}"
    elif region_abbr:
        return region_abbr
    elif city:
        return city
    else:
        return "unknown"

def canonical_url(url: str) -> str:
    p = urlsplit((url or "").strip())
    host = p.netloc.lower()
    host = host[4:] if host.startswith("www.") else host
    path = p.path.rstrip("/") or "/"
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False) if not TRACKING.match(k)]
    q.sort()
    return urlunsplit(("https", host, path, urlencode(q), ""))

def fingerprint(company: str, title: str, location: str, remote: str = "") -> str:
    raw = "\x1f".join([company_key(company), title_key(title), location_key(location, remote)])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def posting_id(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:16]

def detect_source(url: str) -> str:
    u = (url or "").lower()
    p = urlsplit(u)
    host = p.netloc.lower()
    host_path = host + p.path.lower()

    # Check host patterns first
    for name, pat in SOURCES:
        if name == "phenom":
            # Phenom: match host+path pattern only (careers.example.com/us/en)
            if re.search(pat, host_path):
                return name
        else:
            # All others: match host only
            if re.search(pat, host):
                return name

    # Check gh_jid query parameter (Greenhouse board embedded on company domain)
    # Use parse_qs for exact key matching (not substring)
    query_params = parse_qs(p.query)
    if "gh_jid" in query_params:
        return "greenhouse"

    return "other"

def canonical_priority(url: str) -> int:
    return PRIORITY.get(detect_source(url), 2)

def titles_similar(a: str, b: str) -> bool:
    return SequenceMatcher(a=title_key(a), b=title_key(b)).ratio() >= 0.90

def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="compute job fingerprint")
    ap.add_argument("--company", required=True); ap.add_argument("--title", required=True)
    ap.add_argument("--location", default=""); ap.add_argument("--remote", default=""); ap.add_argument("--url", default="")
    a = ap.parse_args(argv)
    print(json.dumps({"fingerprint": fingerprint(a.company, a.title, a.location, a.remote),
                      "company_key": company_key(a.company), "title_key": title_key(a.title),
                      "location_key": location_key(a.location, a.remote),
                      "canonical_url": canonical_url(a.url) if a.url else None,
                      "posting_id": posting_id(a.url) if a.url else None,
                      "source": detect_source(a.url) if a.url else None}))

if __name__ == "__main__":
    main()
