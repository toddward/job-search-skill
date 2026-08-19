#!/usr/bin/env python3
"""Parse config/job-board-links.md and render per-board search URLs for a free-text query."""
from __future__ import annotations
import json, re
from urllib.parse import quote
import common

STATE_NAMES = {"va": "Virginia", "md": "Maryland", "dc": "District of Columbia", "ca": "California", "ny": "New York",
               "tx": "Texas", "wa": "Washington", "ma": "Massachusetts", "nc": "North Carolina", "co": "Colorado",
               "il": "Illinois", "ga": "Georgia", "fl": "Florida", "pa": "Pennsylvania", "nj": "New Jersey"}
# Word-boundary DC-metro match (not a bare substring) so e.g. "Savannah, GA" or "Austin, TX" never
# false-positive on "va"/"md" appearing inside another word.
DC_METRO_RE = re.compile(r"\b(va|dc|md|virginia|maryland|district of columbia)\b", re.I)
ALIASES = [  # (board substring, location map)
    ("capital one", lambda loc: "McLean, VA" if DC_METRO_RE.search(loc) else loc),
    ("amazon", lambda loc: "Herndon, VA" if DC_METRO_RE.search(loc) else loc),
    ("built in", lambda loc: "Washington, DC" if DC_METRO_RE.search(loc) else loc),
    ("anthropic", lambda loc: "Washington, DC" if DC_METRO_RE.search(loc) else loc),
    ("openai", lambda loc: "Washington, DC" if DC_METRO_RE.search(loc) else loc),
    ("wellfound", lambda loc: "Washington, DC" if DC_METRO_RE.search(loc) else loc),
    ("google careers", lambda loc: loc + ", USA" if loc and "usa" not in loc.lower() else loc),
    ("usajobs", lambda loc: _expand_state(loc)),
]
STOP = {"i'm", "im", "i", "am", "searching", "looking", "for", "jobs", "job", "roles", "role", "positions", "position", "based", "in", "the",
        "area", "near", "around", "a", "an", "of", "and", "or", "openings", "opportunities", "want", "find", "me", "please", "that", "are",
        "with", "within"}
# Tech acronyms that must survive the two-letter-uppercase (state-abbreviation) filter below.
ACRONYMS = {"ai", "ml", "llm", "nlp"}
# "within 50 miles" / "50 mi" — matched and stripped from the free-text body before tokenizing
# into keywords, so the radius phrase never leaks into the keyword list.
RADIUS_RE = re.compile(r"(?:within\s+)?(\d{1,3})\s*(?:mi\b|miles?\b)", re.I)

def _expand_state(loc: str) -> str:
    m = re.match(r"^(.*?),\s*([A-Za-z]{2})$", loc.strip())
    if m and m.group(2).lower() in STATE_NAMES:
        return f"{m.group(1)}, {STATE_NAMES[m.group(2).lower()]}"
    return loc

def location_alias(board: str, location: str) -> str:
    b = (board or "").lower()
    for key, fn in ALIASES:
        if key in b:
            return fn(location or "")
    return location or ""

def parse_table(md: str) -> list[dict]:
    rows = []
    for line in (md or "").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 5 or cells[0].lower() == "board" or set(cells[0]) <= {"-", ":"}:
            continue
        rows.append({"board": cells[0], "template": cells[1], "method": cells[2].lower(), "login": cells[3],
                     "enabled": cells[4].strip().lower() in ("true", "yes", "on", "1"), "notes": cells[5] if len(cells) > 5 else ""})
    return rows

def parse_query(text: str, cfg_search: dict) -> dict:
    raw = (text or "").strip()
    location, remote = "", None
    m = re.search(r"\b(?:in|near|around)\s+(?:the\s+)?([A-Z][A-Za-z .]+?,\s*[A-Z]{2})\b", raw)
    if m:
        location = m.group(1).strip()
    elif re.search(r"\bremote\b", raw, re.I):
        remote = True
    if not location and not remote:
        location = cfg_search.get("default_location", "")
    if re.search(r"\bremote\b", raw, re.I):
        remote = True
    body = raw
    if m:
        body = raw.replace(m.group(0), " ")
    body = re.sub(r"\b(remote|hybrid|onsite)\b", " ", body, flags=re.I)
    radius_m = RADIUS_RE.search(raw)
    radius = int(radius_m.group(1)) if radius_m else int(cfg_search.get("radius_miles", 25))
    body = RADIUS_RE.sub(" ", body)
    words = [w.strip(",.;:!?()\"'") for w in body.split()]
    # Drop stopwords and bare two-letter uppercase tokens (state abbreviations like VA/DC),
    # but keep known tech acronyms (AI/ML/LLM/NLP) even though they are also all-caps.
    kws = [w for w in words if w and w.lower() not in STOP and (w.lower() in ACRONYMS or not re.fullmatch(r"[A-Z]{2}", w))]
    kws = [w.upper() if w.lower() in ACRONYMS else w for w in kws]
    return {"keywords": kws or [cfg_search.get("query") or "engineer"], "location": location, "radius_miles": radius, "remote": remote, "raw": raw}

def render(rows: list[dict], query: dict, only_enabled: bool = True) -> list[dict]:
    out = []
    kw = " ".join(query.get("keywords") or [])
    for r in rows:
        if only_enabled and not r["enabled"]:
            continue
        loc = location_alias(r["board"], query.get("location") or "")
        is_url = r["template"].lower().startswith("http")
        enc = (lambda s: quote(s, safe="")) if is_url else (lambda s: s)
        url = (r["template"].replace("{keywords}", enc(kw)).replace("{location}", enc(loc))
               .replace("{radius}", str(query.get("radius_miles", 25)))
               .replace("{remote}", "true" if query.get("remote") else ""))
        url = re.sub(r"\{[a-z_]+\}", "", url)
        out.append({"board": r["board"], "url": url, "method": r["method"] if is_url else "firecrawl-search",
                    "login": r["login"], "notes": r["notes"]})
    return out

def main(argv=None):
    import argparse, config
    ap = argparse.ArgumentParser(description="boards")
    ap.add_argument("--home")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    rd = sub.add_parser("render"); rd.add_argument("--query", required=True); rd.add_argument("--all", action="store_true")
    a = ap.parse_args(argv)
    home = common.data_home(a.home); cfg = config.load(home)
    path = config.resolve_path(cfg, "search.boards_file")
    if not path.exists():
        path = common.SKILL_DIR / "assets" / "job-board-links.default.md"
    rows = parse_table(path.read_text(encoding="utf-8"))
    if a.cmd == "list":
        print(json.dumps(rows, indent=2))
    else:
        q = parse_query(a.query, cfg["search"])
        print(json.dumps({"query": q, "targets": render(rows, q, only_enabled=not a.all)}, indent=2))

if __name__ == "__main__":
    main()
