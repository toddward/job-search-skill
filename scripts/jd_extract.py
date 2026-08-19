#!/usr/bin/env python3
"""Extract structured requirements from a job description (JSON-LD, Greenhouse/Ashby/Lever JSON, or HTML headings)."""
from __future__ import annotations
import hashlib, html, json, re, sys, unicodedata

REQ_HEAD = re.compile(r"(minimum|basic|required|must[- ]have|what you.{0,4}ll need|qualifications|requirements|you have|about you|"
                      r"we.{0,4}re looking for|good fit if|great fit if|candidates? must|you (?:should|will) (?:have|bring)|"
                      r"what we.{0,4}re looking for|skills? (?:and|&) experience|who you are)", re.I)
NICE_HEAD = re.compile(r"(preferred|nice[- ]to[- ]have|bonus|plus|desired|strong(ly)? preferred|additionally|may also have|"
                       r"particularly great fit|stand out|icing on the cake)", re.I)
SKIP_HEAD = re.compile(r"(responsibilit|what you.{0,4}ll do|about (us|the team|the role|the company)|benefits|compensation|"
                       r"equal opportunity|eeo|how to apply|perks|culture)", re.I)
CLEAR = re.compile(r"\b(TS/SCI|Top Secret|Secret clearance|\bSCI\b|CI poly(graph)?|full[- ]scope poly|active .{0,20}clearance|public trust|security clearance)\b", re.I)
CLEAR_OK = re.compile(r"(eligible to obtain|ability to obtain|able to obtain|clearance sponsorship|will sponsor .{0,20}clearance)", re.I)
CITIZ = re.compile(r"\b(U\.?S\.? citizen(ship)?|must be a citizen|green card|permanent resident)\b", re.I)
NOSPONSOR = re.compile(r"(no sponsorship|not able to sponsor|unable to sponsor|without sponsorship|cannot sponsor)", re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?years?", re.I)
MONEY = re.compile(r"\$\s?(\d{2,3})(?:,(\d{3}))?(?:\s?[kK])?")
REMOTE = re.compile(r"\b(remote|work from home|wfh)\b", re.I); HYBRID = re.compile(r"\bhybrid\b", re.I)
INJECT = re.compile(r"(ignore (all )?(previous|prior|above) instructions|[Yy]ou are an (?:ai|AI)|(?:ai|AI) agents?|language model|include the (word|phrase|token)|"
                    r"\b[A-Z]{8,}\b(?![a-z]))")
DOMAINS = {"ai": r"\b(ai|artificial intelligence|llm|generative|genai|machine learning|ml)\b", "platform": r"\bplatform\b",
           "cloud": r"\b(aws|azure|gcp|cloud)\b", "devops": r"\b(devops|sre|site reliability|kubernetes)\b",
           "data": r"\b(data engineering|analytics|etl|warehouse)\b", "security": r"\b(security|appsec|zero trust)\b",
           "fintech": r"\b(bank|fintech|payments|trading)\b", "defense": r"\b(clearance|dod|federal|defense|intelligence community)\b",
           "healthcare": r"\b(health|clinical|hipaa)\b"}

def strip_html(s: str) -> str:
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s or "")
    s = re.sub(r"(?i)</(li|p|div|h[1-6]|tr)>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)<h([1-6])[^>]*>", r"\n## ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unicodedata.normalize("NFKC", html.unescape(s))
    return re.sub(r"[ \t]+", " ", s)

def jsonld_postings(raw: str) -> list[dict]:
    out = []
    for b in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw or ""):
        for cand in (b.strip(), html.unescape(b.strip())):
            try:
                d = json.loads(cand); break
            except ValueError:
                d = None
        if d is None:
            continue
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                t = o.get("@type")
                if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t):
                    out.append(o)
                stack += list(o.values())
            elif isinstance(o, list):
                stack += o
    return out

def sectioned_bullets(text: str):
    must, nice, cur = [], [], None
    for line in text.splitlines():
        ln = line.strip()
        if not ln:
            continue
        is_head = ln.startswith("##") or (len(ln) < 90 and ln.endswith(":")) or (len(ln) < 70 and ln == ln.title() and not ln.startswith("-"))
        if is_head:
            h = ln.lstrip("#").strip()
            if SKIP_HEAD.search(h): cur = None
            elif NICE_HEAD.search(h): cur = "nice"
            elif REQ_HEAD.search(h): cur = "must"
            else: cur = cur if not ln.startswith("##") else None
            continue
        if ln.startswith(("- ", "* ", "•")) and cur:
            item = ln.lstrip("-*• ").strip()
            if 1 <= len(item) <= 400:
                (must if cur == "must" else nice).append(item)
    return must, nice

def facts(text: str) -> dict:
    yrs = [int(m.group(1)) for m in YEARS.finditer(text)]
    money = []
    for m in MONEY.finditer(text):
        val = int(m.group(1)) * (1000 if not m.group(2) else 1) + (int(m.group(2)) if m.group(2) else 0)
        if m.group(2):
            val = int(m.group(1) + m.group(2))
        money.append(val)
    money = [v for v in money if 20000 <= v <= 2000000]
    return {"clearance_required": bool(CLEAR.search(text)) and not CLEAR_OK.search(text),
            "clearance_eligible_ok": bool(CLEAR_OK.search(text)),
            "citizenship_required": bool(CITIZ.search(text)), "sponsorship_unavailable": bool(NOSPONSOR.search(text)),
            "years_min": min(yrs) if yrs else None,
            "comp_min": min(money) if len(money) >= 2 else (money[0] if money else None),
            "comp_max": max(money) if money else None}

def domain_tags(text: str) -> list[str]:
    return [k for k, p in DOMAINS.items() if re.search(p, text or "", re.I)]

def _remote_kind(text: str, hint: str = "") -> str:
    h = (hint or "").lower()
    if "remote" in h or "telecommute" in h: return "remote"
    if "hybrid" in h: return "hybrid"
    if "onsite" in h or "on-site" in h: return "onsite"
    if HYBRID.search(text): return "hybrid"
    if REMOTE.search(text): return "remote"
    return "unknown"

def _date(s):
    return (s or "")[:10] or None

def _base(title="", company="", location="", desc_html="", url="", layer="headings", **kw) -> dict:
    text = strip_html(desc_html)
    must, nice = sectioned_bullets(text)
    f = facts(text)
    out = {"title": title.strip(), "company": company.strip(), "location": location.strip(), "remote": kw.get("remote") or _remote_kind(text, kw.get("remote_hint", "")),
           "description_text": text.strip(), "must_have": must, "nice_to_have": nice, **f,
           "posted_at": kw.get("posted_at"), "closes_at": kw.get("closes_at"), "apply_url": kw.get("apply_url") or url,
           "source_layer": layer, "low_confidence": not must, "domain_tags": domain_tags(title + " " + text),
           "content_hash": hashlib.sha256(text.strip().encode()).hexdigest()[:16],
           "injection_suspects": sorted({m.group(0) for m in INJECT.finditer(strip_html(desc_html))})[:10]}
    for k in ("comp_min", "comp_max"):
        if kw.get(k) is not None:
            out[k] = kw[k]
    return out

def extract(raw: str, url: str = "", source_hint: str = "") -> dict:
    raw = raw or ""
    data = None
    if raw.lstrip().startswith("{"):
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
    if isinstance(data, dict) and "absolute_url" in data and "content" in data:  # Greenhouse
        content = html.unescape(data.get("content", ""))
        return _base(data.get("title", ""), data.get("company_name", ""), (data.get("location") or {}).get("name", ""), content,
                     url, "greenhouse", posted_at=_date(data.get("first_published") or data.get("updated_at")), apply_url=data.get("absolute_url"))
    if isinstance(data, dict) and "descriptionPlain" in data:  # Ashby
        hint = "remote" if data.get("isRemote") else (data.get("workplaceType") or "")
        return _base(data.get("title", ""), data.get("company", data.get("organizationName", "")), data.get("location", ""),
                     data.get("descriptionHtml") or data.get("descriptionPlain", ""), url, "ashby", posted_at=_date(data.get("publishedAt")),
                     apply_url=data.get("applyUrl") or data.get("jobUrl"), remote_hint=hint)
    if isinstance(data, dict) and "hostedUrl" in data:  # Lever
        cats = data.get("categories") or {}
        desc = (data.get("description") or "") + "".join(f"<h2>{l.get('text','')}</h2>{l.get('content','')}" for l in data.get("lists", []))
        ts = data.get("createdAt")
        posted = None
        if isinstance(ts, (int, float)):
            import datetime as _dt
            posted = _dt.datetime.utcfromtimestamp(ts / 1000).strftime("%Y-%m-%d")
        return _base(data.get("text", ""), data.get("company", ""), cats.get("location", ""), desc, url, "lever", posted_at=posted,
                     apply_url=data.get("applyUrl") or data.get("hostedUrl"), remote_hint=data.get("workplaceType", ""))
    posts = jsonld_postings(raw)
    if posts:
        p = posts[0]
        org = p.get("hiringOrganization") or {}
        locs = p.get("jobLocation") or {}
        if isinstance(locs, list):
            locs = locs[0] if locs else {}
        addr = (locs.get("address") or {}) if isinstance(locs, dict) else {}
        location = ", ".join(x for x in [addr.get("addressLocality"), addr.get("addressRegion")] if x)
        sal = (p.get("baseSalary") or {}).get("value") or {}
        return _base(p.get("title", ""), org.get("name", "") if isinstance(org, dict) else str(org), location, p.get("description", ""), url, "jsonld",
                     posted_at=_date(p.get("datePosted")), closes_at=_date(p.get("validThrough")), apply_url=p.get("url"),
                     remote_hint="remote" if p.get("jobLocationType") == "TELECOMMUTE" else "",
                     comp_min=sal.get("minValue") if isinstance(sal, dict) else None, comp_max=sal.get("maxValue") if isinstance(sal, dict) else None)
    m = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", raw)
    title = strip_html(m.group(1)).strip() if m else ""
    return _base(title, "", "", raw, url, "headings")

def main(argv=None):
    import argparse, pathlib
    ap = argparse.ArgumentParser(description="extract job requirements")
    ap.add_argument("file"); ap.add_argument("--url", default="")
    a = ap.parse_args(argv)
    print(json.dumps(extract(pathlib.Path(a.file).read_text(encoding="utf-8"), a.url), ensure_ascii=False))

if __name__ == "__main__":
    main()
