# Resume tailoring, fit scoring and document generation

Research for the `job-search` Claude Code skill. Written 2026-08-19.
Everything marked **[tested]** was executed on the target machine during this research
(macOS 26 / Darwin 25.6.0, arm64, Google Chrome 151.0.7922.169, poppler 26.08.0,
pandoc 3.10.1, reportlab 4.4.10, Python 3, Firecrawl CLI authenticated). Linux behaviour
is marked **[untested-linux]** where I could not run it here — see `## Cross-platform notes`.

Working scripts produced and verified during this research live in the session scratchpad
at `.../scratchpad/pdftest/` (`html2pdf.py`, `md2html.sh`, `truth_gate.py`, `fit_score.py`,
`jd_extract.py`, `md2pdf_reportlab.py`, `jsonld.py`). They are reproduced inline below so
the skill can be built from this document alone.

---

## Resume ingestion

### 1. Tool selection

| Input | Primary | Fallback | Why |
|---|---|---|---|
| Text PDF | `pdftotext -layout` | Firecrawl `/parse` | Local, offline, deterministic, zero cost, best line structure **[tested]** |
| Structure probe on any PDF | `pdftotext -tsv` | `pdftotext -bbox-layout` | Gives per-word x/y/height → heading + column detection **[tested]** |
| Scanned / image-only PDF | Firecrawl `parse --json` with `parsers:{type:"pdf",mode:"ocr"}` | `ocrmypdf` (needs install) | No OCR binary is present on this machine |
| `.docx/.doc/.rtf/.odt` | macOS: `textutil -convert txt` · Linux: `pandoc` or `libreoffice --headless --convert-to txt` | Firecrawl `/parse` | `textutil` is macOS-only; Firecrawl is the portable path |
| Hosted HTML resume | `firecrawl scrape <url> -f markdown` | built-in `WebFetch` | Handles JS-rendered pages |
| LinkedIn profile | LinkedIn's own **Save to PDF** → then treat as a text PDF | "Get a copy of your data" archive | Scraping violates the User Agreement — see below |

`pdftotext -v` on this box reports **version 26.08.0** (poppler). Useful flags, from the
installed man page **[tested]**:

- `-layout` — preserve physical layout (columns line up side by side).
- *(default, no flag)* — "undo" physical layout and emit **reading order**. This is the
  closest local approximation of what an ATS sees; use it for the ATS self-check.
- `-tsv` — `level page_num par_num block_num line_num word_num left top width height conf text`.
  `height` ≈ rendered font size, so headings pop out (16 pt heading vs 10.5 pt body in my
  test); `left` clusters into columns.
- `-bbox-layout` — same data as XHTML `<flow>/<block>/<line>/<word>`.
- `-nopgbrk` — suppress the `\f` between pages (do use it; page breaks pollute section parsing).
- `-enc UTF-8` (default), `-eol unix`, `-colspacing <frac>` (default 0.7; lower it to ~0.4 if a
  wide-tracking resume is being split into phantom columns).
- `-nodiag` — drop diagonal text, i.e. "DRAFT"/"CONFIDENTIAL" watermarks.

Canonical ingest command:

```bash
pdftotext -layout -nopgbrk -enc UTF-8 -eol unix resume/master.pdf resume/.raw/master.layout.txt
pdftotext        -nopgbrk -enc UTF-8 -eol unix resume/master.pdf resume/.raw/master.reading.txt
pdftotext -tsv   -nopgbrk                      resume/master.pdf resume/.raw/master.tsv
```

Keep all three. `.layout.txt` is for a human to eyeball, `.reading.txt` is the ATS-eye view,
`.tsv` drives heading/column detection.

### 2. Image-only / scanned detection (must run before anything else)

```bash
WORDS=$(pdftotext -layout resume/master.pdf - | wc -w)
# < ~80 words on a one-page resume ⇒ the PDF is an image; go to OCR.
```

This same gate is baked into `html2pdf.py` below so the skill never ships an unparseable PDF.

### 3. Firecrawl `/parse` — what it is actually good for

`firecrawl parse <file>` posts the file to `/v2/parse`
(<https://docs.firecrawl.dev/features/parse>). Supported: `.html .htm .xhtml .pdf .docx .doc
.docm .odt .ods .odp .rtf .xlsx .xls .xlsm .xlsb .pptx .ppt .pptm .epub .csv`, 50 MB max.
Options that matter here: `parsers: {"type":"pdf","mode":"fast"|"auto"|"ocr","maxPages":N}`
and `timeout` (default 30 000 ms, max 300 000 ms).

**[tested]** I ran `firecrawl parse ./out-resume.pdf -f markdown` on a Chrome-generated
resume PDF. It recovered the name as an `# H1` and preserved `**bold**`, but **collapsed
every section onto a single line** — worse structural fidelity than `pdftotext -layout` for
this document class. Conclusion: `pdftotext` first, Firecrawl for formats poppler cannot read
(DOCX/DOC/RTF/ODT) and for OCR.

Do **not** pass `redactPII` when parsing a resume — it strips exactly the contact block you
need.

### 4. Hosted HTML resume (example.com-style)

```bash
firecrawl scrape "https://example.com/resume" -f markdown --only-main-content -o resume/.raw/hosted.md
```

`--only-main-content` drops nav/footer chrome. If Firecrawl is unavailable, `WebFetch` with a
prompt like *"return the resume verbatim as Markdown; do not summarise"* is the fallback.
Either way, write the raw capture to `resume/.raw/` and never edit it — `master.md` is the
only hand-edited file.

### 5. LinkedIn

LinkedIn's User Agreement forbids automated collection: members agree not to "*develop, support
or use software, devices, scripts, robots or any other means or processes … to scrape the
Services or otherwise copy profiles and other data*"
(<https://www.linkedin.com/legal/user-agreement>). Playwright-driving a logged-in session to
harvest a profile — including your own — is exactly what that prohibits, and LinkedIn
enforces with CAPTCHAs and account restriction.

Use the sanctioned exports instead. Both are one-time manual steps the skill prompts for:

1. **Save to PDF** — profile → *More*/*Resources* → *Save to PDF*
   (<https://www.linkedin.com/help/linkedin/answer/a541960>). Desktop only, English profiles
   only. Drop the file in `resume/` and it flows through the normal PDF path.
2. **Get a copy of your data** — Settings → Data privacy → *Get a copy of your data*
   (<https://www.linkedin.com/help/linkedin/answer/a510363> covers the related resume-upload
   flow). Yields CSVs (`Positions.csv`, `Education.csv`, `Skills.csv`) that map straight onto
   the `master.md` sections.

The skill should refuse to scrape linkedin.com and say why, offering these two paths.

### 6. Canonical `resume/master.md`

One file, one authority. Everything downstream (tailoring, truth gate, scoring) reads only this.

```markdown
---
name: Jane Example
email: you@example.com
phone: "+1-555-555-5555"
location: Reston, VA
links:
  site: https://example.com
  linkedin: https://www.linkedin.com/in/example
  github: https://github.com/example
seniority: staff          # intern|junior|mid|senior|staff|principal|director  → scorer input
target_titles: [Staff Platform Engineer, Principal Engineer, ML Platform Engineer]
target_base: 200000
holds_clearance: false
clearance_level: null
us_citizen: true
open_to_remote: true
home_metro: [Reston VA, Herndon VA, Tysons VA, Arlington VA, Washington DC]
ok_metros: [Baltimore MD, Richmond VA]
target_domains: [AI/ML, Platform, Data Infrastructure]
schema_version: 1
---

# Jane Example
Reston, VA | you@example.com | (555) 555-5555 | example.com

## Summary
<2-3 sentences. No adjectives that cannot be evidenced below.>

## Skills
**Languages:** Python, Go, TypeScript
**Platform:** Kubernetes, Terraform, AWS (EKS, S3, IAM), Kafka, PostgreSQL

## Experience
### Staff Platform Engineer — Acme Corp, Inc.
Reston, VA | Jan 2020 – Present
- Cut p99 API latency 42% by replacing a synchronous fan-out with a Kafka pipeline serving 3.1M req/day.
- Led migration of 180 services to Kubernetes, reducing median deploy time from 45 minutes to 6 minutes.

## Education
B.S. Computer Science — Virginia Tech, Blacksburg, VA

## Certifications
Certified Kubernetes Administrator (CKA), 2023
```

Rules that make the rest of the system work:

- **Section names are fixed**: `Summary`, `Skills`, `Experience`, `Education`, `Certifications`,
  optionally `Projects`, `Publications`, `Clearance`. The tailor may reorder and drop sections
  but may never invent one.
- **Every bullet is one line** starting `- `. No nested lists. The truth gate and the diff both
  operate line-wise.
- **Every bullet should carry a number** where one exists (%, count, $, duration). Metrics are
  what the tailor is allowed to reorder around; prose without them is dead weight.
- `master.md` should be a **superset**: keep bullets you would not use for every job. Tailoring
  is *selection*, and selection needs stock to select from.
- The YAML front matter is the scorer's config. One source of truth means the score is a pure
  function of `(master.md, job.json, rubric_version)`.

### 7. Normalization contract

`scripts/ingest_resume.py` (Python 3 stdlib) should be **idempotent**: re-running it over an
unchanged `resume/` must not touch `master.md`. Concretely:

1. Discover inputs: `resume/*.pdf|*.docx|*.md|*.txt` plus any `resume_url` in config.
2. Convert each to text into `resume/.raw/<name>.<ext>.txt`, recording `sha256` in
   `resume/.raw/manifest.json`.
3. If `master.md` exists and every input hash is unchanged → exit 0, no writes.
4. If `master.md` does not exist → emit a **draft** `master.md.draft` from the best text source
   with sections mapped by heading regex, and stop with a message asking the user to review and
   `mv` it into place. Never auto-overwrite a hand-curated `master.md`.
5. Validate: front matter parses, required keys present, ≥1 Experience bullet, no bullet >400
   chars, no `TODO`/`TBD`. Exit non-zero with the specific failure.

Heading detection from `-tsv`: cluster words by `height`; the modal height is body text, and any
line whose modal height is ≥1.15× body **or** whose text is fully uppercase and <60 chars is a
heading candidate. Column detection: histogram `left`; two dense clusters separated by >80 pt
across most of the page ⇒ the source PDF is two-column and reading-order text will be
interleaved — warn the user that their *current* resume is likely mis-parsed by ATSes today.

---

## Fit scoring rubric

### A. Getting requirements out of a JD reliably

Four layers, cheapest and most deterministic first. Record which layer produced the data in
`source_layer` so scores stay auditable.

**Layer 1 — schema.org `JobPosting` JSON-LD.** Google's job-posting spec
(<https://developers.google.com/search/docs/appearance/structured-data/job-posting>) requires
`title`, `description`, `datePosted`, `hiringOrganization`, `jobLocation` and recommends
`validThrough`, `employmentType`, `baseSalary`, `jobLocationType` (`TELECOMMUTE` = remote),
`applicantLocationRequirements`, `directApply`, `identifier`, plus beta `educationRequirements`
/ `experienceRequirements`. schema.org itself (<https://schema.org/JobPosting>) additionally
defines `skills`, `qualifications`, `responsibilities`, **`securityClearanceRequirement`** and
**`eligibilityToWorkRequirement`** — the last two map directly onto the red flags below when
present.

**[tested] Reality check:** Greenhouse's hosted board pages ship **no** JSON-LD. I fetched
`https://job-boards.greenhouse.io/anthropic/jobs/5023394008` (HTTP 200, 83 351 bytes) and found
`0` `application/ld+json` blocks. So Layer 1 covers company career sites and aggregators, not
the big ATS-hosted boards.

**Layer 2 — public ATS JSON APIs.** Far better than scraping where they exist. **[tested]**:

| ATS | Endpoint | Result |
|---|---|---|
| Greenhouse | `https://boards-api.greenhouse.io/v1/boards/<token>/jobs/<id>?questions=false` | **200.** Keys incl. `title`, `location.name`, `absolute_url`, `first_published`, `updated_at`, `requisition_id`, `metadata[]`, `company_name`, and `content` (26 344 chars of HTML-escaped JD). |
| Ashby | `https://api.ashbyhq.com/posting-api/job-board/<org>` | **200**, 136 jobs. Per job: `title`, `location`, `secondaryLocations[]`, `employmentType`, `isRemote`, `workplaceType`, `publishedAt`, `department`, `team`, `descriptionHtml`, `descriptionPlain`, `jobUrl`, `applyUrl`. |
| Lever | `https://api.lever.co/v0/postings/<org>?mode=json` | **404** for the org I probed — the endpoint exists but only for orgs that expose a public board. Treat a 404 as "fall through to Layer 3", not as an error. |

Ashby's payload is the richest: `isRemote` and `secondaryLocations` remove all guessing from
the location component.

**Layer 3 — heading-scoped bullet harvest.** Convert the description HTML to text (`<li>` → `- `,
`<h*>` → `## `), then walk the lines carrying a "current section" state: requirement headings
open a `must` bucket, preference headings open a `nice` bucket, and responsibilities/benefits/EEO
headings close both. This is where the real accuracy problem lives.

**[tested]** My first heading regex extracted **0** requirements from the real Anthropic JD,
because that posting uses headings like *"Across the workstreams, you may be a good fit if
you:"*, *"Strong candidates may also have:"* and *"Candidates must be:"*. After widening the
patterns to include `good fit if|great fit if|candidates? must|who you are|what we're looking
for|skills? (and|&) experience` (must) and `may also have|particularly great fit|stand out`
(nice), the same JD yielded **7 must-haves and 31 nice-to-haves**, byte-identical across runs.
Take the lesson, not the regex: heading matching gets you most of the way and then silently
returns nothing. Always set `low_confidence: true` when `must_have` is empty.

**Layer 4 — model extraction, only for `low_confidence` JDs.** Prompt the model with the
description text and a strict JSON schema, temperature 0, and cache the result keyed by the
JD's sha256 so re-scoring the same job never re-invokes the model and never changes the score.

Regex facts harvested in every layer: clearance (`TS/SCI|Top Secret|Secret clearance|SCI|CI
poly|full-scope poly|active .* clearance|public trust`), citizenship/sponsorship (`U.S.
citizen|no sponsorship|not able to sponsor|green card|permanent resident|work authorization`),
`N+ years`, and `$NNN,NNN`/`$NNNk` salary pairs.

Working extractor (`scripts/jd_extract.py`), **[tested]** against `gh.json` — deterministic,
same md5 on repeat runs:

```python
#!/usr/bin/env python3
"""jd_extract.py <jd.html|jd.md|jd.txt|ats.json>  ->  normalized job.json on stdout."""
import html, json, re, sys, unicodedata

REQ_HEAD = re.compile(r"(minimum|basic|required|must[- ]have|what you.{0,4}ll need|"
                      r"qualifications|requirements|you have|about you|we.{0,4}re looking for|"
                      r"good fit if|great fit if|candidates? must|you (?:should|will) (?:have|bring)|"
                      r"what we.{0,4}re looking for|skills? (?:and|&) experience|who you are)", re.I)
NICE_HEAD = re.compile(r"(preferred|nice[- ]to[- ]have|bonus|plus|desired|"
                       r"strong(ly)? preferred|additionally|may also have|"
                       r"particularly great fit|stand out|icing on the cake)", re.I)
SKIP_HEAD = re.compile(r"(responsibilit|what you.{0,4}ll do|about (us|the team|the role)|"
                       r"benefits|compensation|equal opportunity|eeo|how to apply)", re.I)
CLEAR = re.compile(r"\b(TS/SCI|Top Secret|Secret clearance|SCI\b|CI poly(graph)?|"
                   r"full[- ]scope poly|active .{0,20}clearance|public trust)\b", re.I)
CITIZ = re.compile(r"\b(U\.?S\.? citizen(ship)?|must be a citizen|green card|"
                   r"permanent resident|no sponsorship|not able to sponsor|"
                   r"work authorization)\b", re.I)
YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?years?", re.I)
MONEY = re.compile(r"\$\s?(\d{2,3})(?:,(\d{3}))?(?:\s?[kK])?")

def strip_html(s):
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?i)</(li|p|div|h[1-6]|tr)>", "\n", s)
    s = re.sub(r"(?i)<li[^>]*>", "\n- ", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)<h([1-6])[^>]*>", r"\n## ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unicodedata.normalize("NFKC", html.unescape(s))
    return re.sub(r"[ \t]+", " ", s)

def jsonld(raw):
    out = []
    for b in re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', raw):
        try:                d = json.loads(html.unescape(b.strip()))
        except Exception:
            try:            d = json.loads(b.strip())
            except Exception: continue
        stack = [d]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                t = o.get("@type")
                if t == "JobPosting" or (isinstance(t, list) and "JobPosting" in t): out.append(o)
                stack += list(o.values())
            elif isinstance(o, list): stack += o
    return out

def sectioned_bullets(text):
    must, nice, cur = [], [], None
    for line in text.splitlines():
        ln = line.strip()
        if not ln: continue
        is_head = ln.startswith("##") or (len(ln) < 90 and ln.endswith(":")) or \
                  (len(ln) < 70 and ln == ln.title() and not ln.startswith("-"))
        if is_head:
            h = ln.lstrip("#").strip()
            if   SKIP_HEAD.search(h): cur = None
            elif NICE_HEAD.search(h): cur = "nice"
            elif REQ_HEAD.search(h):  cur = "must"
            else:                     cur = cur if not ln.startswith("##") else None
            continue
        if ln.startswith(("- ", "* ", "•")) and cur:
            item = ln.lstrip("-*• ").strip()
            if 3 <= len(item) <= 400:
                (must if cur == "must" else nice).append(item)
    return must, nice
```

*(The `parse()` driver that dispatches Layer 1 vs Layer 2 vs Layer 3 and applies the regex
facts is ~70 more lines of the same shape; it lives in the scratchpad copy.)*

### B. The rubric

Seven additive components summing to 100, then hard-flag caps applied afterwards. Weights are
config, not code — record them in every score so an old score stays interpretable when the
weights change.

| # | Component | Weight | How it is computed |
|---|---|---|---|
| 1 | **Hard requirements** | **35** | Fraction of `must_have` items covered by the resume. 1.0 per exact/synonym hit, 0.6 if every word of a multi-word requirement appears somewhere, 0 otherwise. If the JD lists none, use a neutral 0.75. |
| 2 | **Skills overlap** | **20** | Same coverage function over `nice_to_have`. Neutral 0.5 if absent. |
| 3 | **Seniority / title** | **12** | Map both titles onto an ordinal ladder (intern 0 … VP 7). Δ=0 → 1.0; Δ=+1 → 0.75 (a stretch is fine); Δ=−1 → 0.85 (slight down-level); \|Δ\|=2 → 0.45; else 0.15. |
| 4 | **Location / remote** | **12** | Remote or in `home_metro` → 1.0; in `ok_metros` → 0.7; location unknown → 0.5; anything else → 0.0. |
| 5 | **Domain / industry** | **8** | In `target_domains` → 1.0; unknown → 0.5; explicitly other → 0.25. |
| 6 | **Recency** | **5** | ≤7 d → 1.0; ≤21 d → 0.8; ≤45 d → 0.5; older → 0.2. Stale reqs are frequently already filled. |
| 7 | **Compensation signal** | **8** | Top of range ≥ `target_base` → 1.0; ≥90% → 0.7; ≥80% → 0.35; below → 0.0. **No range posted → 0.6, not 0.** |

Why the weights land where they do:

- **35 on hard requirements** because that is the only component that maps to a screening
  decision. Everything else is preference.
- **20 on skills** keeps a strong keyword overlap from ever outvoting a missing hard
  requirement (35 > 20, and the <50% floor caps the total anyway).
- **12/12 on seniority and location** — each one alone routinely kills an application, so they
  need to be able to move the score by more than a rounding error, but neither should sink an
  otherwise perfect match on its own.
- **8 on domain, 5 on recency** — real but weak signals.
- **8 on compensation, defaulting to 0.6 when absent.** As of 2026, 18 states plus DC have pay
  transparency laws, and CA/CO/NY/WA/IL/MD/MA/MN/NJ/VT/ME/HI require a range in the posting
  itself (<https://www.jacksonlewis.com/insights/navigating-2026-pay-transparency-laws-and-employer-obligations>).
  **Virginia is not among them**, so a Reston-local posting with no range is completely normal
  and must not be punished. A remote posting with no range is more suspicious — but not enough
  to justify a different weight, so keep it simple and let the human see the `notes` line.

### C. Red flags — caps applied *after* the additive score

Caps, not subtractions, so a red-flagged job can never out-rank a clean one on component
strength.

| Flag | Condition | Effect |
|---|---|---|
| Clearance not held | JD requires an **active** clearance and `holds_clearance: false` | `total = min(total, 25)` |
| Citizenship / sponsorship | JD states a requirement `master.md` does not satisfy | `total = min(total, 20)` |
| Hard-requirement floor | `must_have` coverage < 0.50 | `total = min(total, 45)` |

The clearance flag needs one distinction the regex must respect: **"active TS/SCI required"** is
a blocker, **"must be eligible to obtain"** or **"clearance sponsorship available"** is not.
Individuals cannot self-apply for a clearance; it has to be sponsored by an employer or agency
(<https://www.dcsa.mil/Personnel-Vetting/Background-Investigations-for-Applicants/Investigations-Clearance-Process/>),
so an "eligible to obtain" posting is a normal open door and should score normally. How long a
lapsed clearance stays reinstatable is **unknown** to me at the level of a citable rule — I would
check 32 CFR Part 117 (NISPOM) and DCSA's reciprocity guidance before encoding any window.

Other flags worth surfacing in `notes` without capping: unpaid/equity-only, "rockstar/ninja"
language, >5 years required for a stated junior title, an apply flow that is email-only, and a
`validThrough` date already in the past.

### D. Reference implementation and worked examples

`scripts/fit_score.py` — **[tested]**, pure function, no clock, no RNG, no network.

```python
W = {"must_have": 35, "skills": 20, "seniority": 12, "location": 12,
     "domain": 8, "recency": 5, "comp": 8}          # sums to 100
HARD_FLOOR = 0.5                                    # <50% of must-haves => cap total at 45

def canon(s):
    s = unicodedata.normalize("NFKD", s).lower()
    s = s.replace("+", "p").replace("#", "sharp")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())

# Equivalence GROUPS, not one-way aliases: a requirement matches if ANY member is in the resume.
SYN_GROUPS = [
 {"kubernetes","k8s","eks","gke","aks","openshift"}, {"terraform","tf","opentofu"},
 {"infrastructure as code","iac"}, {"amazon web services","aws"},
 {"google cloud platform","gcp","google cloud"}, {"microsoft azure","azure"},
 {"postgresql","postgres","psql"}, {"javascript","js"}, {"typescript","ts"},
 {"python","py"}, {"go","golang"}, {"machine learning","ml"},
 {"large language model","large language models","llm","llms"},
 {"generative ai","genai","gen ai"}, {"retrieval augmented generation","rag"},
 {"natural language processing","nlp"},
 {"continuous integration","ci cd","cicd","ci/cd"},
]
SYN = {}
for _g in SYN_GROUPS:
    _c = {canon(x) for x in _g}
    for _m in _c: SYN.setdefault(_m, set()).update(_c)

def variants(s):  return SYN.get(canon(s), {canon(s)})

def resume_terms(master_md):
    words, grams = canon(master_md).split(), set()
    for n in (1, 2, 3):
        for i in range(len(words) - n + 1): grams.add(" ".join(words[i:i+n]))
    return grams

def covered(term, grams):
    vs = variants(term)
    if vs & grams: return 1.0
    for t in vs:
        parts = t.split()
        if len(parts) > 1 and all(p in grams for p in parts): return 0.6
    return 0.0
```

**One-way aliases are a bug, and I hit it.** My first pass mapped `"aws" -> "amazon web
services"`; a JD requiring "AWS" then scored as *missing* against a resume that literally says
"AWS", costing 8.75 points (score 83.2 instead of 92.0). Equivalence *groups* fixed it. **[tested]**

Worked examples against the sample `master.md` (config: `resume_seniority=staff`, home metro
Reston VA, `target_base=200000`, `holds_clearance=false`):

| Job | must | skills | sen | loc | dom | rec | comp | **Total** | Flags |
|---|---|---|---|---|---|---|---|---|---|
| Staff ML Platform Eng, Reston VA, $210–250k, 3 d old | 35.0 | 12.0 | 12.0 | 12.0 | 8.0 | 5.0 | 8.0 | **92.0** | — |
| Senior AI Eng, Chantilly VA, active TS/SCI | 35.0 | 20.0 | 10.2 | 0.0 | 8.0 | 2.5 | 8.0 | ~~83.7~~ **25.0** | clearance not held |
| Director of Eng, Austin TX, Salesforce/SAP/Java | 0.0 | 0.0 | 5.4 | 0.0 | 2.0 | 1.0 | 2.8 | **11.2** | 0% hard reqs |

The `k8s`-spelled variant of the first job also scores **92.0**, confirming synonym symmetry.
Re-running any of these produces a byte-identical md5 **[tested]**.

### E. Keeping scores reproducible

1. **Version the rubric.** `rubric_version: 3` in config; store it with every score. Never
   silently re-weight history.
2. **Freeze inputs.** Score is `f(master.md sha256, job.json sha256, rubric_version, config
   sha256)`. Cache on that tuple; a cache hit means the model is never re-invoked and the number
   cannot drift.
3. **No clock inside the function.** Pass `age_days` in from the caller; otherwise the same job
   scores differently tomorrow for no reason the user can see.
4. **Always emit the breakdown**, not just the total — components, weights, `must_have_coverage`,
   `notes`, `red_flags`. The report renders "83 — missing must-have: Rust; comp 12% under
   target", which is what actually helps someone decide.
5. **Calibrate before trusting the `auto_submit` threshold.** Score 30–40 known jobs, have the
   user label each *would apply / would not*, and check that the 80 cut-off sits between the
   populations. Adjust `target_base`, metro lists and `target_domains` — not the weights —
   first. The default threshold of 80 is a starting guess, not a validated boundary.

---

## Tailoring method

### A. What the tailor may and may not do

**Allowed (all are selection or presentation):**

1. **Select** — drop bullets and whole roles that do not serve this JD. Roles older than ~12
   years compress to a one-line "Earlier: Title, Company (2008–2013)".
2. **Reorder** — put the most JD-relevant bullet first inside each role; reorder the `Skills`
   lines so the JD's stack leads. Roles themselves stay reverse-chronological, always.
3. **Retitle within truth** — if `master.md` says "Staff Platform Engineer" and the JD says
   "Staff Infrastructure Engineer", you keep the real title. You may add a parenthetical only if
   it was a real internal alias.
4. **Mirror vocabulary onto experience that already exists** — master says "container
   orchestration", JD says "Kubernetes", and the bullet's underlying work *was* Kubernetes →
   rewrite to "Kubernetes". Master says "container orchestration" because it was Nomad → leave it.
5. **Rewrite the Summary** — 2–3 sentences, drawn only from facts elsewhere in the document.
6. **Tighten** — shorten a bullet to fit the page.

**Forbidden:**

- Any skill, tool, employer, title, certification, degree, or number not in `master.md`.
- Inflating a metric, or attaching a real metric to a different bullet.
- Changing dates, or removing a role in a way that manufactures continuity across a gap.
- Keyword stuffing, white text, or a hidden keyword block. MIT's career office is explicit that
  keywords must be *"meaningfully incorporated"* rather than spammed
  (<https://capd.mit.edu/resources/make-your-resume-ats-friendly/>) — and a hidden block is
  simply a lie to a human reader who opens the PDF.
- Any claim the tailor could not point at a specific master line to justify.

### B. Truth gate (enforced, not advisory)

`scripts/truth_gate.py` runs after every tailoring pass and blocks PDF generation on failure.
Three deterministic rules, no model in the loop — **[tested]**:

- **R1 NUMBER** — every number/percent/currency/date in the tailored file must appear in
  `master.md`.
- **R2 UNSOURCED** — every capitalized token or acronym (≥2 chars) must appear in `master.md`
  case-insensitively, or in `config/allowlist.txt` (for things like the target company's name,
  which legitimately appears only in the cover letter).
- **R3 INFLATED** — no tailored bullet may exceed its nearest master bullet (best
  `difflib.SequenceMatcher` ratio ≥ 0.5) by more than 25% of its character length. This is what
  catches quiet embellishment — "led a migration" becoming "led a company-wide migration
  spanning four business units".

A stop-word list covers connectives, months, and JD-neutral verbs so R2 does not fire on
"Led"/"Built"/"January".

**[tested] Result:** on a tailored file that introduced "FedRAMP" (not in master), the gate
printed `R2-UNSOURCED FedRAMP` and exited 1. On a version that only reordered the Skills line
and dropped one bullet, it printed `TRUTH GATE: PASS` and exited 0.

```python
# R2, the load-bearing rule
for w in WORD.findall(tailored):
    if len(w) < 2 or not (w[0].isupper() or w.isupper()): continue
    nw = norm(w)
    if nw in STOP or nw in allow or nw in m_tokens: continue
    if nw and nw in m_norm: continue          # substring rescue: "Kubernetes-based"
    fails.append(("R2-UNSOURCED", w))
```

The gate is a floor, not a ceiling — it cannot detect a *reworded* exaggeration that reuses only
master vocabulary. That is what the diff review below is for.

### C. Keyword mirroring, concretely

For each `must_have` the scorer marked as covered at 1.0, ensure the JD's exact surface form
appears at least once in the tailored resume — in `Skills` if it is a tool, in an Experience
bullet if it is a practice. For items covered at 0.6 (partial), mirror only if a specific bullet
genuinely supports it; otherwise leave it and let the score reflect the gap honestly. For items
covered at 0.0, do nothing — that is the gap the cover letter may address, or the reason not to
apply.

Do not abbreviate a keyword the JD spells out, and do not let a keyword break across a line
hyphenated — both are called out by MIT CAPD as parse hazards.

### D. Page-count rules

- **One page** if total professional experience <10 years, or if changing fields.
- **Two pages** are fine at 10+ years — but the second page must be at least ~60% full. A
  two-page resume with four lines on page 2 reads as a formatting accident.
- **Never three** for industry roles (academic CVs are a different document and out of scope here).
- The generator measures, it does not guess: render, run `pdfinfo | grep Pages`, and if the count
  is wrong apply fixes in this fixed order — (1) drop the lowest-scoring bullets, (2) compress
  pre-12-year roles to one line, (3) `font-size: 10.5pt → 10pt`, (4) `line-height: 1.34 → 1.25`,
  (5) `@page margin: 0.65in → 0.55in`. Stop below 10 pt or 0.5 in; MIT CAPD sets the floor at
  **10 pt or larger**.

### E. ATS-safe formatting — the rules and the evidence for them

The vendors are unusually explicit. Greenhouse's own "Unsuccessful resume parse" article
(<https://support.greenhouse.io/hc/en-us/articles/200989175-Unsuccessful-resume-parse>) names
the causes: **files that are images rather than .docx/.pdf; graphics, photos or word art;
complex resumes with tables, headers and footers; name/contact information in headers, footers
or text boxes; column-based layouts; sections with no clear structure; spaces between letters;
company names missing Inc./Co./Ltd./LLC; abbreviated job titles.** It also states Greenhouse
**cannot parse resumes larger than 2.5 MB**, even though uploads are accepted up to 100 MB in
`.doc/.docx/.pdf/.rtf/.txt`
(<https://support.greenhouse.io/hc/en-us/articles/360052218132-Supported-formats-for-resumes-cover-letters-and-other-candidate-uploads>).

Lever parses Word, PDF, RTF, WordPerfect, HTML, MS Office HTML and ODF, cannot parse image
files, and offers the same self-test — *"if you cannot highlight text, the document is likely
not parseable"* (<https://help.lever.co/s/article/Understanding-Resume-Parsing>, last published
2026-03-01). MIT CAPD adds: avoid graphics, icons, images, tables and text boxes; 10 pt
minimum; Arial, Calibri, Cambria, Georgia, Helvetica or Times New Roman; and **convert to plain
text and check nothing is missing and the order is right**.

I ran exactly that plain-text check against Chrome-generated PDFs. The results are specific
enough to design against — every row **[tested]** with `pdftotext` (poppler 26.08.0), which is
the same class of extractor an ATS uses:

| Construct | Rendered | Extracted (default reading order) | Verdict |
|---|---|---|---|
| `<ul>` with CSS `list-style: disc` | `• CSSMARKER alpha` | `CSSMARKER alpha` — **the bullet glyph is gone** | Use a real glyph, not a CSS marker |
| `li::before { content: "\2022\00a0\00a0" }` or literal `&#8226;` | `• MANUAL alpha` | `• MANUAL alpha` | ✅ survives |
| `<table>` 2×2 | rows | `TCELL-A1, TCELL-A2, TCELL-B1, TCELL-B2` — **column-major; row association destroyed** | Never |
| Right-aligned date via `display:flex; justify-content:space-between` | one visual line | date split onto its own block — and in one test **the date landed at the very end of the document**, after two later sections | Avoid |
| Same via `float:right`, CSS table cells, or `margin-left:auto` | one visual line | date split onto its own block | Avoid |
| `text-align-last: justify` for a tab-stop effect | one visual line | **every word became its own extracted block**, interleaved with later content | Never |
| Title and date on one inline line, `Title, Company \| Jan 2020 – Present` | one line | identical, in order | ✅ best |
| Title line + separate meta line beneath | two lines | two lines, in order | ✅ also fine |
| Two-column `display:flex` body | two columns | two separate blocks | Avoid (matches Greenhouse's "column-based layouts") |

Two further findings: Chrome's `Skia/PDF m151` output is **`Tagged: yes` by default**
**[tested]** (do *not* pass `--disable-pdf-tagging` — tagging is structure, and structure helps),
and fonts embed as subsetted CID TrueType with ToUnicode maps, so extraction is lossless.

Resulting hard rules for the template: single column; no tables; no headers/footers; no images
or icons; contact block as real body text on line 2; standard section headings; real `•`
glyphs; dates inline or on their own line, never right-aligned on a shared line; `text-align:
left` everywhere, never `justify`; company names carry their legal suffix (Greenhouse checks
for Inc./Co./Ltd./LLC); full job titles, never abbreviated; ≤2.5 MB.

### F. File naming

```
Todd-Wardzinski-Resume.pdf                       # generic / master export
Todd-Wardzinski-Resume-Anthropic-MLPlatformEng.pdf
Todd-Wardzinski-Cover-Letter-Anthropic-MLPlatformEng.pdf
```

Rules: given-family name first so a recruiter's Downloads folder sorts usefully; ASCII only;
hyphens, never spaces or underscores (some upload widgets mangle both); no dates or version
numbers in the filename (an ATS shows it to a human, and `v3-final` is not a good look);
company and a CamelCase role slug capped at ~24 chars. Keep the on-disk copies at the plain
names `resume.pdf` / `cover-letter.pdf` inside the application directory and generate the
"pretty" filename only as a symlink or at upload time.

### G. Cover letter

Structure — 3–4 paragraphs, **≤300 words**, one page. Yale OCS and MIT CAPD both land on three
to four paragraphs and 250–400 words as the norm
(<https://ocs.yale.edu/channels/cover-letters-correspondence/>,
<https://capd.mit.edu/resources/how-to-write-an-effective-cover-letter/>), so ≤300 sits inside
the accepted band on the tighter side, which is the right bias for a cold application.

1. **Hook (2–3 sentences).** Name the role and one *specific* thing about this company or team —
   drawn from the JD text or the company's own site, never invented. If the skill cannot find a
   specific hook, it must say so and let the human supply one rather than writing "I have long
   admired your commitment to innovation".
2. **Proof (3–5 sentences).** The single strongest bullet, expanded with the context the resume
   had no room for: the problem, what you did, the number. Must trace to a `master.md` bullet.
3. **Fit (2–4 sentences).** Map two or three of the JD's `must_have` items to specific
   experience. If there is a known gap the score flagged, this is where a one-clause honest
   framing goes ("my Kafka work is production but pre-dates Flink").
4. **Close (1–2 sentences).** Availability, location/remote posture, thanks. No "I look forward
   to hearing from you at your earliest convenience".

Same truth gate applies, with the company name and role title in the allowlist. The cover letter
renders through the identical HTML→PDF path, minus the `Skills`/`Experience` CSS.

### H. Diff review — how the user actually checks the tailoring

`git diff --no-index` works outside a repository, which is exactly the situation here **[tested]**:

```bash
git diff --no-index --word-diff=plain \
         --word-diff-regex='[^[:space:]]+' \
         -- resume/master.md applications/2026-08-19-acme-ml-platform/resume.md
```

Produces, verbatim from my test run:

```
## Summary
Platform engineer with 12 years building [-**Kubernetes**-based-]{+**Kubernetes** and **Terraform**+} data [-platforms.-]{+platforms for **FedRAMP**-regulated environments.+}

## Skills
[-Python, Go,-]Kubernetes, Terraform, AWS, {+Python, Go,+} PostgreSQL, Kafka

### Senior Engineer, Globex | Jun 2016 - Dec 2019
[-- Built a Terraform module library adopted by 9 teams.-]
```

`[-removed-]` / `{+added+}` at word granularity is the right resolution: a pure reorder shows as
a small paired change, while an invented phrase shows up as a `{+...+}` with no matching `[-...-]`
— visually obvious, and the same signal the truth gate catches mechanically.

The skill writes this to `applications/<dir>/tailoring-diff.txt` and shows a summary line —
`3 bullets dropped, 1 reordered, 0 additions, TRUTH GATE: PASS` — before asking the user to
approve. Counting: additions are `{+...+}` groups, drops are whole `[-- ...-]` lines, reorders
are lines with both markers where the multiset of words is unchanged.

---

## PDF generation

### A. The Chrome invocation, verified

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu \
  --no-pdf-header-footer \
  --virtual-time-budget=5000 \
  --run-all-compositor-stages-before-draw \
  --timeout=20000 \
  --print-to-pdf="/abs/path/resume.pdf" \
  "file:///abs/path/resume.html"
```

**[tested]** on Chrome 151.0.7922.169: writes a 1-page, `Tagged: yes`, 612×792 pt (Letter) PDF
with subsetted embedded CID TrueType fonts in **1.77 s**, and `pdftotext` recovers every line in
correct reading order.

The switches are defined in Chromium's headless command handler
(<https://chromium.googlesource.com/chromium/src/+/refs/heads/main/components/headless/command_handler/headless_command_switches.cc>),
which declares exactly: `default-background-color`, `dump-dom`, **`print-to-pdf`**,
**`no-pdf-header-footer`**, `disable-pdf-tagging`, `generate-pdf-document-outline`, `screenshot`,
**`timeout`**, **`virtual-time-budget`**.

- `--no-pdf-header-footer` **works and is required.** Without it Chrome stamps `8/19/26, 2:48 PM`
  and the document title across the top and the full `file:///...` URL plus `1/2` across the
  bottom of every page — I extracted exactly that from the control run. File size difference in
  my test: 22 636 bytes with the flag vs 39 335 without. (Older write-ups claiming there is no
  CLI way to suppress headers pre-date this switch; on Chrome 151 it is real.)
- `--headless` and `--headless=new` produced **byte-identical output** (22 636 bytes each)
  **[tested]** — old headless is gone, `--headless` *is* the new mode. Use the short form.
- `--timeout=<ms>` bounds page load. `--virtual-time-budget=<ms>` advances virtual time only as
  network fetches settle, which is the correct guard for web fonts.
- **Do not pass `--disable-pdf-tagging`.** It flips `Tagged: yes` → `Tagged: no` **[tested]**;
  tagging is free structure.

### B. Pitfalls — every one of these I hit while testing

1. **`--user-data-dir` makes headless Chrome hang forever.** **[tested, reproducible]** With a
   fresh `--user-data-dir`, Chrome writes a correct PDF (byte-identical to the normal run) and
   then **never exits**. It survived every mitigation I tried: `--use-mock-keychain`,
   `--no-first-run`, `--no-default-browser-check`, `--password-store=basic`, `--disable-sync`,
   `--disable-component-update`, `--disable-background-networking`, `--disable-default-apps`,
   and even `--timeout=5000`. Control run without the flag: **1.77 s**. With it: still alive at
   25 s, every time. **Omit `--user-data-dir` for PDF generation**, and wrap the call in a
   watchdog anyway.
2. **A relative path silently hangs.** Passing `t4.html` instead of `file:///abs/t4.html` makes
   Chrome treat it as a search query; no PDF is produced and the process blocks. Always
   `pathlib.Path(x).resolve().as_uri()`.
3. **`--no-sandbox` on macOS is a hang risk and is not needed.** It belongs to Linux containers
   only (see `## Cross-platform notes`).
4. **CSS list markers vanish from the text layer.** `list-style: disc` renders a bullet that
   `pdftotext` does not extract. Use `li::before { content: "\2022\00a0\00a0" }`.
5. **Never `text-align: justify`** (or `text-align-last: justify`). It spaces words
   individually; extraction shattered into one block per word and interleaved later content.
6. **Right-aligned dates on a shared line break reading order** in every CSS technique I tried.
   Put the date inline after a separator, or on its own line.
7. **External CSS via a relative `href` from a `file://` page loads fine** — Georgia embedded
   correctly from `<link rel="stylesheet" href="ext.css">` **[tested]**. No
   `--allow-file-access-from-files` needed for same-directory assets. Inlining the CSS into a
   `<style>` block is still preferable: one file to archive per application.
8. **`@page { size: Letter; margin: ... }` is honoured** and produced exactly 612×792 pt
   **[tested]**. Do **not** use `--no-margins`; it zeroes the print margin and your `@page`
   margin becomes the only thing between text and the paper edge — a 0-margin resume looks broken
   and can be clipped on print.
9. **pandoc `--standalone` duplicates your name.** With `--metadata title="Jane Example -
   Resume"`, pandoc emits a visible `<h1 class="title">` *and* your `# Name` heading, so the PDF
   opens with the name twice **[tested]**. Generate a fragment and wrap it yourself (§D).
10. **Size ceiling is 2.5 MB, not 100 MB.** Greenhouse accepts 100 MB but *parses* nothing over
    2.5 MB. A text resume lands around 50–100 KB; if you are anywhere near the limit, something
    (an embedded image) is wrong.
11. **Font choice changes the page count across machines** — see `## Cross-platform notes`.

### C. The ATS-safe HTML/CSS template

Single column, system fonts, Letter, 0.65 in × 0.7 in margins. **[tested]** end to end: renders
to 1 page, 139 extractable words, 56.5 KB, perfect reading order.

```html
<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Jane Example - Resume</title>
<style>
  @page { size: Letter; margin: 0.65in 0.7in; }
  html, body { margin:0; padding:0; }
  body {
    /* Arial first: real Arial on macOS/Windows, metric-identical Liberation Sans on Linux */
    font-family: Arial, "Liberation Sans", Helvetica, "Nimbus Sans", sans-serif;
    font-size: 10.5pt; line-height: 1.34; color: #000;
    text-align: left;                     /* never justify */
    -webkit-print-color-adjust: exact;
  }
  h1 { font-size: 17pt; font-weight: 700; margin: 0 0 2pt; letter-spacing: .01em; }
  .contact { font-size: 9.5pt; margin: 0 0 10pt; }   /* real body text, NOT a header */
  h2 { font-size: 10.5pt; font-weight: 700; text-transform: uppercase;
       letter-spacing: .07em; margin: 12pt 0 4pt; padding-bottom: 2pt;
       border-bottom: .75pt solid #000;
       break-after: avoid; page-break-after: avoid; }
  h3 { font-size: 10.5pt; font-weight: 700; margin: 7pt 0 0;
       break-after: avoid; page-break-after: avoid; }
  .meta { font-size: 10pt; margin: 0 0 3pt; }        /* "Reston, VA • Jan 2020 – Present" */
  p  { margin: 0 0 5pt; }
  ul { list-style: none; margin: 0 0 6pt; padding: 0; }   /* CSS markers don't extract */
  li { margin: 0 0 3pt; padding-left: 11pt; text-indent: -11pt;
       break-inside: avoid; page-break-inside: avoid; }
  li::before { content: "\2022\00a0\00a0"; }              /* real glyph in the text stream */
  a  { color: #000; text-decoration: none; }
</style></head><body>
<h1>Jane Example</h1>
<p class="contact">Reston, VA &#8226; you@example.com &#8226; (555) 555-5555
   &#8226; example.com &#8226; linkedin.com/in/example</p>

<section><h2>Summary</h2>
<p>Platform engineer with 12 years building Kubernetes-based data platforms for regulated environments.</p></section>

<section><h2>Skills</h2>
<p><b>Languages:</b> Python, Go, TypeScript</p>
<p><b>Platform:</b> Kubernetes, Terraform, AWS (EKS, S3, IAM), Kafka, PostgreSQL</p></section>

<section><h2>Experience</h2>
<h3>Staff Platform Engineer &#8212; Acme Corp, Inc.</h3>
<p class="meta">Reston, VA &#8226; Jan 2020 &#8211; Present</p>
<ul>
  <li>Cut p99 API latency 42% by replacing a synchronous fan-out with a Kafka pipeline serving 3.1M req/day.</li>
  <li>Led migration of 180 services to Kubernetes, reducing median deploy time from 45 minutes to 6 minutes.</li>
</ul>
</section>

<section><h2>Education</h2>
<p>B.S. Computer Science &#8212; Virginia Tech, Blacksburg, VA</p></section>

<section><h2>Certifications</h2>
<p>Certified Kubernetes Administrator (CKA), 2023</p></section>
</body></html>
```

Extraction from the generated PDF, verbatim **[tested]**:

```
Jane Example
Reston, VA • you@example.com • (555) 555-5555 • example.com • linkedin.com/in/example
SUMMARY
Platform engineer with 12 years building Kubernetes-based data platforms for regulated environments.
SKILLS
Languages: Python, Go, TypeScript
Platform: Kubernetes, Terraform, AWS (EKS, S3, IAM), Kafka, PostgreSQL
EXPERIENCE
Staff Platform Engineer — Acme Corp, Inc.
Reston, VA • Jan 2020 – Present
• Cut p99 API latency 42% by replacing a synchronous fan-out with a Kafka pipeline serving 3.1M req/day.
• Led migration of 180 services to Kubernetes, reducing median deploy time from 45 minutes to 6 minutes.
EDUCATION
B.S. Computer Science — Virginia Tech, Blacksburg, VA
CERTIFICATIONS
Certified Kubernetes Administrator (CKA), 2023
```

### D. Markdown → HTML (pandoc, fragment mode)

**[tested]** — avoids the duplicate-title bug in pitfall 9.

```bash
#!/usr/bin/env bash
# md2html.sh <resume.md> <out.html> <ats.css> "<Doc Title>"
set -euo pipefail
MD="$1"; OUT="$2"; CSS="$3"; TITLE="${4:-Resume}"
# -smart (note the minus) keeps ASCII hyphens and straight quotes: maximum parser safety.
BODY="$(pandoc "$MD" -f markdown-smart -t html5 --wrap=none)"
{
  printf '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
  printf '<title>%s</title>\n<style>\n' "$TITLE"
  cat "$CSS"
  printf '\n</style></head><body>\n%s\n</body></html>\n' "$BODY"
} > "$OUT"
```

pandoc 3.10.1 is installed and has **no PDF engine**, which is fine — it never touches PDF here.
(A Python equivalent for portability is trivial: `subprocess.run(["pandoc", ...],
capture_output=True)` plus an f-string.)

### E. `html2pdf.py` — the portable wrapper with a verification gate

**[tested]** on macOS: `ok: .../out2.pdf pages=1 words=139 bytes=56548`, exit 0, 2.06 s wall.

```python
#!/usr/bin/env python3
"""html2pdf.py IN.html OUT.pdf -- ATS-safe HTML -> PDF via headless Chrome/Chromium.
Exit 0 ok | 1 no browser | 2 no output | 3 not text-extractable | 4 too large."""
import glob, os, pathlib, platform, shutil, subprocess, sys

MAX_PARSE_BYTES = 2_500_000     # Greenhouse refuses to PARSE above this
MIN_WORDS = 80                  # below this the PDF is probably image-only

def find_browser():
    if os.environ.get("CHROME_BIN"): return os.environ["CHROME_BIN"]
    if platform.system() == "Darwin":
        cands = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                 "/Applications/Chromium.app/Contents/MacOS/Chromium",
                 "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
                 os.path.expanduser("~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")]
    else:
        cands = ["google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
                 "microsoft-edge-stable", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
                 "/snap/bin/chromium", "/usr/lib/chromium-browser/chromium-browser"]
    for c in cands:
        p = shutil.which(c) if not c.startswith("/") else (c if os.path.exists(c) else None)
        if p: return p
    root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or (
        os.path.expanduser("~/Library/Caches/ms-playwright") if platform.system() == "Darwin"
        else os.path.expanduser("~/.cache/ms-playwright"))
    for pat in ("chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium",
                "chromium-*/chrome-linux/chrome",
                "chromium_headless_shell-*/chrome-linux/headless_shell"):
        hits = sorted(glob.glob(os.path.join(root, pat)))
        if hits: return hits[-1]
    return None

def in_container():
    return (os.path.exists("/.dockerenv") or os.environ.get("CI") == "true"
            or (platform.system() == "Linux" and os.geteuid() == 0))

def main():
    src = pathlib.Path(sys.argv[1]).resolve()
    out = pathlib.Path(sys.argv[2]).resolve()
    browser = find_browser()
    if not browser:
        print("no Chrome/Chromium; set CHROME_BIN or run: npx playwright install chromium",
              file=sys.stderr); return 1
    if out.exists(): out.unlink()
    argv = [browser, "--headless", "--disable-gpu", "--no-pdf-header-footer",
            "--virtual-time-budget=5000", "--run-all-compositor-stages-before-draw",
            "--timeout=20000", f"--print-to-pdf={out}", src.as_uri()]   # as_uri() => absolute file://
    if platform.system() == "Linux" and in_container():
        argv[1:1] = ["--no-sandbox", "--disable-dev-shm-usage"]
    try:
        subprocess.run(argv, timeout=60, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        pass    # watchdog: Chrome can linger after writing; the file is already on disk
    if not out.exists() or out.stat().st_size == 0:
        print(f"no PDF produced: {out}", file=sys.stderr); return 2

    size, words, pages = out.stat().st_size, None, None
    if shutil.which("pdftotext"):
        words = len(subprocess.run(["pdftotext", "-layout", str(out), "-"],
                                   capture_output=True, text=True).stdout.split())
    if shutil.which("pdfinfo"):
        for line in subprocess.run(["pdfinfo", str(out)], capture_output=True,
                                   text=True).stdout.splitlines():
            if line.startswith("Pages:"): pages = int(line.split()[1])
    print(f"ok: {out} pages={pages} words={words} bytes={size}")
    if words is not None and words < MIN_WORDS:
        print(f"FAIL: only {words} extractable words - image-only PDF?", file=sys.stderr); return 3
    if size > MAX_PARSE_BYTES:
        print(f"FAIL: {size} > {MAX_PARSE_BYTES}; Greenhouse will not parse it",
              file=sys.stderr); return 4
    return 0

sys.exit(main())
```

The `subprocess.run(timeout=60)` is the watchdog that neutralises pitfall 1 even if a future
Chrome build starts hanging without `--user-data-dir`.

### F. reportlab fallback

Use when no Chrome/Chromium exists at all (a truly minimal Linux cron host). reportlab 4.4.10 is
installed. **[tested]**: 1 page, Letter, correct reading order, real `•` glyphs.

```python
#!/usr/bin/env python3
"""md2pdf_reportlab.py <resume.md> <out.pdf> — minimal Markdown -> ATS-safe PDF.
Handles '# Name', '## SECTION', '### Role', '- bullet', paragraphs, **bold**, *italic*."""
import re, sys
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, HRFlowable

BODY    = ParagraphStyle('body', fontName='Helvetica', fontSize=10.5, leading=13.2,
                         spaceAfter=3, alignment=TA_LEFT)
NAME    = ParagraphStyle('name', parent=BODY, fontName='Helvetica-Bold', fontSize=18,
                         leading=21, spaceAfter=2)
CONTACT = ParagraphStyle('contact', parent=BODY, fontSize=9.5, leading=12, spaceAfter=8)
SECTION = ParagraphStyle('section', parent=BODY, fontName='Helvetica-Bold', fontSize=11,
                         leading=13, spaceBefore=10, spaceAfter=2)
BULLET  = ParagraphStyle('bullet', parent=BODY, leftIndent=12, bulletIndent=0, spaceAfter=2)

def inline(s):
    s = s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
    s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    s = re.sub(r'(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)', r'<i>\1</i>', s)
    return re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1', s)      # keep link text, drop the URL

def build(md_path, pdf_path):
    flow, seen_name = [], False
    for raw in open(md_path, encoding='utf-8').read().splitlines():
        line = raw.rstrip()
        if not line.strip(): continue
        if line.startswith('# '):
            flow.append(Paragraph(inline(line[2:].strip()), NAME)); seen_name = True
        elif line.startswith('## '):
            flow.append(Paragraph(inline(line[3:].strip()).upper(), SECTION))
            flow.append(HRFlowable(width='100%', thickness=0.6, color='#000000',
                                   spaceBefore=1, spaceAfter=5))
        elif line.startswith('### '):
            flow.append(Paragraph('<b>%s</b>' % inline(line[4:].strip()), BODY))
        elif line.lstrip().startswith(('- ', '* ')):
            # bulletText renders a REAL glyph, so it survives text extraction
            flow.append(Paragraph(inline(line.lstrip()[2:]), BULLET, bulletText='•'))
        else:
            flow.append(Paragraph(inline(line),
                                  CONTACT if seen_name and len(flow) == 1 else BODY))
    SimpleDocTemplate(pdf_path, pagesize=LETTER,
                      leftMargin=0.7*inch, rightMargin=0.7*inch,
                      topMargin=0.65*inch, bottomMargin=0.65*inch,
                      title='Resume', creator='job-search skill').build(flow)

if __name__ == '__main__':
    build(sys.argv[1], sys.argv[2])
```

Trade-offs versus Chrome, all **[tested]**: reportlab emits `Tagged: no` and uses the
**non-embedded base-14** `Helvetica`/`Helvetica-Bold` (WinAnsi, no ToUnicode). Text still
extracts correctly because WinAnsi maps directly — but non-embedded fonts render with whatever
the viewer substitutes, so line breaks can differ on the recruiter's screen. It is a genuine
fallback, not a co-equal path. Its one advantage: it needs no browser and no fonts installed,
which makes it the reliable choice on a bare Linux container.

---

## Output layout

### A. Directory

```
~/development/random/job-search/
├── resume/
│   ├── master.md                  # the one hand-curated authority
│   ├── master.pdf                 # optional source PDF
│   ├── .raw/                      # machine-written captures, never hand-edited
│   │   ├── manifest.json          # {path: sha256} — drives idempotent re-ingest
│   │   ├── master.layout.txt      # pdftotext -layout
│   │   ├── master.reading.txt     # pdftotext (reading order == the ATS view)
│   │   └── master.tsv             # pdftotext -tsv
│   └── templates/
│       ├── ats.css                # the single stylesheet, inlined at render time
│       ├── resume.html.j2
│       └── cover-letter.html.j2
├── config/
│   ├── job-board-links.md
│   ├── settings.yaml              # auto_submit, threshold, per_run_cap, rubric_version
│   └── allowlist.txt              # proper nouns the truth gate may accept
├── memory/
├── reports/2026-08-19.md
└── applications/
    └── 2026-08-19-anthropic-ml-platform-engineer/
        ├── job.md
        ├── job.json
        ├── resume.md
        ├── resume.html
        ├── resume.pdf
        ├── cover-letter.md
        ├── cover-letter.html
        ├── cover-letter.pdf
        ├── answers.md
        ├── tailoring-diff.txt
        ├── score.json
        ├── status.json
        └── evidence/
            ├── 01-jd-page.png
            ├── 02-form-filled.png
            ├── 03-review-page.png
            └── 04-confirmation.png
```

### B. Directory naming

`<YYYY-MM-DD>-<company-slug>-<role-slug>`

- Date is the day the application directory was **created**, local time, `date +%F` /
  `datetime.date.today().isoformat()`.
- Slugs: NFKD-normalize → lowercase → strip everything but `[a-z0-9]` → collapse runs to a
  single `-` → trim. Company capped at 24 chars, role at 40. Drop corporate suffixes
  (`inc`, `llc`, `ltd`, `corp`, `co`) from the *directory* slug only — keep them in the resume
  text, where Greenhouse's parser wants them.
- Collision (same company + role + day): append `-2`, `-3`. Never overwrite; a second attempt at
  the same job is a distinct artifact worth keeping.
- Lowercase everywhere, so the tree behaves identically on case-sensitive Linux filesystems and
  case-insensitive macOS ones.

### C. File contents

**`job.md`** — the human-readable JD snapshot, so the posting survives being taken down:

```markdown
---
fingerprint: sha256:8f3c…            # matches memory/jobs.json
url: https://job-boards.greenhouse.io/anthropic/jobs/5023394008
apply_url: https://…/application
company: Anthropic
title: ML Platform Engineer
location: San Francisco, CA / Remote-Friendly, United States
remote: true
posted: 2025-12-11
captured: 2026-08-19T15:04:11-04:00
source_layer: ats-api                 # json-ld | ats-api | text | model
salary_min: null
salary_max: null
fit_score: 92.0
rubric_version: 3
---

## Requirements (extracted)
- …
## Preferred (extracted)
- …
## Full description
<verbatim JD text — never summarised; this is the evidence the tailoring was based on>
```

**`job.json`** — the normalized machine record `jd_extract.py` emits, and the exact input
`fit_score.py` consumed. Keeping it lets a score be reproduced months later.

**`resume.md` / `cover-letter.md`** — the tailored sources. These are the review surface; the
HTML and PDF are derived and disposable.

**`resume.html` / `cover-letter.html`** — rendered with `ats.css` **inlined**, so an archived
application still renders correctly after the template changes.

**`resume.pdf` / `cover-letter.pdf`** — the uploaded artifacts, byte-for-byte.

**`answers.md`** — one block per screening question:

```markdown
## Q3. Describe your experience operating Kafka at scale.
- **type:** textarea (max 2000 chars)
- **required:** true
- **confidence:** high        # high = grounded in a master.md bullet
- **source:** master.md:L42 "Cut p99 API latency 42% … Kafka pipeline serving 3.1M req/day"
- **needs_review:** false

**Draft answer**
I ran the Kafka pipeline behind Acme's public API for four years…

## Q4. Are you willing to relocate to San Francisco?
- **type:** radio [Yes / No]
- **required:** true
- **confidence:** none        # NOT derivable from the resume
- **needs_review:** true
- **draft:** (blank — needs a human decision)
```

The `needs_review` flag is what the auto-apply flow gates on: **any** question with
`confidence: none` blocks submission regardless of `auto_submit` or fit score. Personal-fact
questions (relocation, salary expectation, start date, sponsorship, veteran/disability
self-identification) should be hard-coded to `needs_review: true` unless the answer is
explicitly present in `config/settings.yaml`.

**`tailoring-diff.txt`** — the `git diff --no-index --word-diff` output from §H above, plus the
truth-gate verdict on the first line.

**`score.json`** — `fit_score.py` output verbatim: total, components, weights,
`must_have_coverage`, `notes`, `red_flags`, plus the input hashes and `rubric_version`.

**`evidence/`** — numbered PNGs from the Playwright run. Numbering matters: they are the record
of what was actually submitted. Capture at minimum the JD page, the filled form before submit,
and the confirmation screen. If a run stops at "needs review", the last screenshot is the
review page — that alone justifies keeping the directory.

### D. `status.json`

Single source of truth for lifecycle state. Written on every state change; every write is a full
rewrite of the file (small enough that atomicity via `os.replace` on a temp file is trivial).

```json
{
  "schema_version": 1,
  "fingerprint": "sha256:8f3c…",
  "company": "Anthropic",
  "title": "ML Platform Engineer",
  "url": "https://job-boards.greenhouse.io/anthropic/jobs/5023394008",
  "apply_url": "https://job-boards.greenhouse.io/anthropic/jobs/5023394008/application",
  "ats": "greenhouse",
  "fit_score": 92.0,
  "rubric_version": 3,
  "status": "ready_for_review",
  "auto_submit_eligible": true,
  "blocked_by": ["answers.Q4 needs_review"],
  "created": "2026-08-19T15:04:11-04:00",
  "updated": "2026-08-19T15:22:03-04:00",
  "history": [
    {"at": "2026-08-19T15:04:11-04:00", "status": "generated",         "note": "tailored resume + cover letter"},
    {"at": "2026-08-19T15:09:47-04:00", "status": "truth_gate_passed", "note": "0 findings"},
    {"at": "2026-08-19T15:22:03-04:00", "status": "ready_for_review",  "note": "1 screening question needs a human"}
  ],
  "artifacts": {
    "resume_pdf":       {"path": "resume.pdf",       "bytes": 56548, "pages": 1, "sha256": "…"},
    "cover_letter_pdf": {"path": "cover-letter.pdf", "bytes": 41120, "pages": 1, "sha256": "…"}
  },
  "submission": null,
  "notion_page_id": null
}
```

`status` values, in order: `generated` → `truth_gate_passed` → `ready_for_review` →
`submitted` | `abandoned` | `rejected` | `interviewing` | `offer`. On submission, `submission`
becomes `{"at": …, "confirmation_text": …, "confirmation_screenshot": "evidence/04-confirmation.png"}`.

`blocked_by` is the machine-readable reason a `ready_for_review` application did not
auto-submit, so a headless cron run can report *why* without a human reading the logs.

### E. Retention and idempotency

- Application directories are **never** deleted by the skill. They are the audit trail, and
  disk cost is a few hundred KB each.
- Re-running the tailor for an existing directory rewrites `resume.md`/`cover-letter.md`/PDFs but
  **appends** to `history` and never touches `evidence/` or a non-null `submission`.
- If `submission` is non-null, the tailor refuses to regenerate and says so. What was sent is
  what is on disk.
- `reports/YYYY-MM-DD.md` links to application directories by relative path so the report stays
  valid if the data home moves.

---

## Cross-platform notes

Everything above was executed on macOS. This section covers what changes on
Debian/Ubuntu/Fedora-class Linux, including headless servers and containers.
All Linux specifics here are **[untested-linux]** — I had no Linux host in this session — and are
drawn from vendor documentation, cited inline. The single highest-value thing to do before
trusting this on Linux is to run §E's smoke test there.

### A. Browser discovery

`find_browser()` in `html2pdf.py` already implements this order:

1. `$CHROME_BIN` — always wins; the documented escape hatch.
2. **macOS:** `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, then Chromium,
   then Edge, then `~/Applications/…`.
3. **Linux (`$PATH`):** `google-chrome-stable`, `google-chrome`, `chromium`,
   `chromium-browser`, `microsoft-edge-stable`, then absolute fallbacks `/usr/bin/…`,
   `/snap/bin/chromium`, `/usr/lib/chromium-browser/chromium-browser`.
   Debian/Ubuntu name the binary `chromium` (recent) or `chromium-browser` (older / Snap);
   Fedora uses `chromium`. Google's own `.deb`/`.rpm` installs `google-chrome-stable`.
4. **Playwright's bundled Chromium** — the same cache layout on both OSes, per
   <https://playwright.dev/docs/browsers>: macOS `~/Library/Caches/ms-playwright`,
   Linux `~/.cache/ms-playwright`, overridable with `PLAYWRIGHT_BROWSERS_PATH`. Globs:
   `chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium`,
   `chromium-*/chrome-linux/chrome`, `chromium_headless_shell-*/chrome-linux/headless_shell`.

**Snap caveat:** a Snap-packaged Chromium on Ubuntu is confined and generally cannot read
`file://` paths outside `$HOME` — including `/tmp`. If the skill's scratch HTML lives outside
`$HOME`, either write it under `$HOME` or prefer a non-Snap browser. Detect with
`readlink -f $(command -v chromium) | grep -q '^/snap/'`.

### B. Sandbox and shared memory (Linux only)

- **`--no-sandbox`** is required when Chrome runs as **root** in a container (its normal
  refusal), and is *not* required for an unprivileged user with user namespaces available.
  The script adds it only when `/.dockerenv` exists, `CI=true`, or `os.geteuid() == 0`.
- **`--disable-dev-shm-usage`** avoids crashes from Docker's default 64 MB `/dev/shm`.
  Alternative: run the container with `--shm-size=1g`.
- Do **not** add either flag on macOS — see PDF-generation pitfall 3.
- New headless needs no X server or `xvfb`.

### C. Fonts — the one that silently breaks page counts

Stock Linux has neither Arial nor Helvetica. Without a metric-compatible substitute installed,
Chrome falls back to whatever fontconfig offers, glyph widths change, and **the same HTML that
is one page on macOS becomes two on Linux** — or renders tofu boxes on a truly bare container.

The fix is two-part:

1. **Font stack.** Use `font-family: Arial, "Liberation Sans", Helvetica, "Nimbus Sans",
   sans-serif;` as in §C's template. Liberation Sans is explicitly metric-compatible with Arial
   (<https://github.com/liberationfonts/liberation-fonts>), and fontconfig's
   `30-metric-aliases.conf` already maps Arial→Liberation Sans and Helvetica→Nimbus Sans
   (<https://wiki.archlinux.org/title/Metric-compatible_fonts>), so glyph widths match on all
   three platforms. **[tested on macOS]** switching from a Helvetica-first to this Arial-first
   stack produced byte-identical extracted text and the same 1-page count (Arial subsets embed
   larger — 102 KB vs 56 KB — still far under the 2.5 MB parse limit).
2. **Install the fonts.** Debian/Ubuntu: `apt-get install -y fonts-liberation fonts-dejavu-core`.
   Fedora: `dnf install -y liberation-fonts dejavu-sans-fonts`. Then `fc-cache -f`.
   `npx playwright install --with-deps chromium` also pulls font packages on supported distros.

**Verify, do not assume:** `html2pdf.py` already prints `pages=`. Make the caller assert the
expected page count on every platform; a page-count change is the cheap canary for a font
substitution problem.

### D. Package installation per OS

| Need | macOS | Debian/Ubuntu | Fedora |
|---|---|---|---|
| `pdftotext`, `pdfinfo`, `pdffonts` | `brew install poppler` | `apt-get install -y poppler-utils` | `dnf install -y poppler-utils` |
| pandoc | `brew install pandoc` | `apt-get install -y pandoc` | `dnf install -y pandoc` |
| reportlab | `python3 -m pip install reportlab` | same (add `python3-pip`) | same |
| Fonts | built in | `fonts-liberation fonts-dejavu-core` | `liberation-fonts dejavu-sans-fonts` |
| Chrome/Chromium | Chrome app bundle | `chromium` / Google's `.deb` | `chromium` / Google's `.rpm` |
| Playwright browser | `npx playwright install chromium` | `npx playwright install --with-deps chromium` | `npx playwright install chromium` + manual deps |
| DOCX→text | `textutil` (built in) | `pandoc` or `libreoffice --headless --convert-to txt` | same |

`poppler-utils` is the package name on **both** Debian and Fedora
(<https://packages.debian.org/sid/poppler-utils>,
<https://packages.fedoraproject.org/pkgs/poppler/poppler-utils/>). `--with-deps` is officially
supported on Debian 12/13 and Ubuntu 22.04/24.04/26.04, x86-64 or arm64
(<https://playwright.dev/docs/browsers>); on Fedora it will not resolve packages, so install
Chromium from the distro and point `CHROME_BIN` at it.

A startup `doctor` check should probe each of these and print the exact install command for the
detected platform rather than failing with a bare `command not found`.

### E. Smoke test to run on every new host

```bash
python3 - <<'PY'
import platform, shutil, subprocess, sys
print("platform:", platform.system(), platform.machine())
for tool in ("pdftotext", "pdfinfo", "pandoc", "git"):
    print(f"  {tool:10} {shutil.which(tool) or 'MISSING'}")
try:
    import reportlab; print("  reportlab ", reportlab.Version)
except ImportError: print("  reportlab  MISSING")
PY
python3 scripts/html2pdf.py resume/templates/smoke.html /tmp/smoke.pdf
# expect: ok: /tmp/smoke.pdf pages=1 words=<N> bytes=<B>   and exit 0
pdftotext /tmp/smoke.pdf -   # eyeball reading order and the • glyphs
```

If `pages` differs from the macOS baseline, fonts are the cause: check `fc-list | grep -i liberation`.

### F. Schedulers

**cron (both platforms).** Cron gives a minimal environment — no `~/.zshrc`, often
`PATH=/usr/bin:/bin`. Set everything explicitly:

```cron
# m h dom mon dow
SHELL=/bin/bash
PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
CHROME_BIN=/Applications/Google Chrome.app/Contents/MacOS/Google Chrome
30 7 * * 1-5 cd "$HOME/development/random/job-search" && claude -p "/job-search daily" >> logs/cron.log 2>&1
```

On macOS, cron additionally needs **Full Disk Access** granted to `/usr/sbin/cron` in System
Settings → Privacy & Security, or it cannot read files under `~/Documents`, `~/Desktop`, etc.
This is the single most common reason a macOS cron job works by hand and fails on schedule.

**launchd (macOS, preferred over cron).** `~/Library/LaunchAgents/info.jobsearch.daily.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>info.jobsearch.daily</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string><string>-lc</string>
    <string>cd "$HOME/development/random/job-search" &amp;&amp; claude -p "/job-search daily"</string>
  </array>
  <key>StartCalendarInterval</key><dict>
    <key>Hour</key><integer>7</integer><key>Minute</key><integer>30</integer>
  </dict>
  <key>StandardOutPath</key><string>/tmp/jobsearch.out</string>
  <key>StandardErrorPath</key><string>/tmp/jobsearch.err</string>
  <key>EnvironmentVariables</key><dict>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
</dict></plist>
```

```bash
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/info.jobsearch.daily.plist
launchctl kickstart -k gui/$UID/info.jobsearch.daily      # run now, to test
launchctl bootout   gui/$UID/info.jobsearch.daily         # remove
```

The key advantage over cron, per `man 5 launchd.plist` **[read locally]**: *"Unlike cron which
skips job invocations when the computer is asleep, launchd will start the job the next time the
computer wakes up."* On a laptop that is asleep at 07:30, cron simply never runs. `launchctl
load/unload` still work but the man page recommends `bootstrap`/`bootout`.

**systemd user timer (Linux, preferred over cron).**
`~/.config/systemd/user/jobsearch.service`:

```ini
[Unit]
Description=Daily job search

[Service]
Type=oneshot
WorkingDirectory=%h/development/random/job-search
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/local/bin/claude -p "/job-search daily"
```

`~/.config/systemd/user/jobsearch.timer`:

```ini
[Unit]
Description=Daily job search timer

[Timer]
OnCalendar=Mon..Fri 07:30
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now jobsearch.timer
systemctl --user list-timers jobsearch.timer
loginctl enable-linger "$USER"      # required for user timers to fire without an active login
journalctl --user -u jobsearch.service -n 50
```

`Persistent=true` is the systemd analogue of launchd's wake behaviour: a missed run fires on next
boot. `loginctl enable-linger` is easy to forget and is why "the timer is enabled but never runs"
on a headless box.

### G. Shell and coreutils differences — and why the helpers are Python

These all bit me or would have **[tested locally where noted]**:

| Thing | macOS (BSD) | Linux (GNU) | Portable answer |
|---|---|---|---|
| `timeout` | **absent** — `command not found` **[tested]**; `gtimeout` only with coreutils | present | `subprocess.run(..., timeout=N)` |
| Date arithmetic | `date -v-14d +%F` works; `date -d` fails **[tested]** | `date -d '14 days ago'` works; `-v` fails | `datetime.date.today() - timedelta(days=14)` **[tested]** |
| In-place sed | `sed -i '' -e …` | `sed -i -e …` | read/modify/write in Python |
| File size | `stat -f%z` | `stat -c%s` | `os.path.getsize()` |
| Default shell | `zsh` **[tested: SHELL=/bin/zsh]** | usually `bash` | `#!/usr/bin/env bash` on scripts; never rely on interactive rc files |
| Glob with no match | zsh **errors**: `no matches found` **[tested]** | bash yields the literal | `glob.glob()` |
| `readlink -f` | absent on older macOS | present | `pathlib.Path(p).resolve()` |
| `md5` vs `md5sum` | `md5` | `md5sum` | `hashlib.sha256` |

Policy: **every helper under `scripts/` is Python 3 stdlib.** `md2html.sh` is the only shell
script above and has a two-line Python equivalent; prefer that. Any shell that does survive gets
`#!/usr/bin/env bash` and `set -euo pipefail`, never `#!/bin/sh` (dash lacks `pipefail`).

### H. Persistent browser profile for the Playwright apply flow

The apply flow needs a *persistent* profile so the user logs into each ATS once. Keep it inside
the data home, not in an OS-specific cache, so backup and inspection are obvious:

```
~/development/random/job-search/.browser-profile/    # chmod 700 — holds session cookies
```

Pass it as Playwright's `userDataDir` (`launchPersistentContext`). Notes:

- This is a **separate concern** from PDF generation. `html2pdf.py` deliberately never touches
  `--user-data-dir` — see PDF-generation pitfall 1.
- `chmod 700`, and add `.browser-profile/` to any ignore file. Live session cookies for job
  boards are credentials.
- Playwright's own browser binaries live in the OS cache paths in §A; only the *profile* lives
  in the data home.
- Use the **full** Chromium, not `chromium_headless_shell` (`--only-shell`), for the apply flow —
  the headless shell is a stripped build and headed/persistent-profile work expects the full one.
- Chrome/Chromium refuses to run two instances against the same `userDataDir`. Guard the apply
  flow with a lockfile in the data home so a cron run and an interactive run cannot collide.

---

## Confidence

| Claim group | Rating | Reason |
|---|---|---|
| **Chrome headless PDF recipe on macOS** — `--headless`, `--no-pdf-header-footer`, `--print-to-pdf`, `--timeout`, `--virtual-time-budget`, tagged output, Letter sizing, 1.77 s runtime | **high** | Executed on the target machine against Chrome 151.0.7922.169; outputs inspected with `pdfinfo`/`pdffonts`/`pdftotext`. Switch names confirmed against Chromium source (`headless_command_switches.cc`). |
| **`--user-data-dir` hangs headless print-to-pdf** | **high** | Reproduced 5×, including with `--use-mock-keychain`, `--no-first-run`, `--password-store=basic`, `--disable-sync` and `--timeout=5000`. Control (no flag) exits in 1.77 s every time. PDF bytes are identical either way — it is purely a process-exit defect. Scoped to Chrome 151 / macOS 26; I did not test other versions. |
| **ATS text-extraction behaviour** — CSS list markers lost, tables extracted column-major, `text-align-last:justify` shattering, flex/float right-aligned dates reordering, inline and two-line date formats safe | **high** | Each row generated as its own PDF and extracted with poppler 26.08.0 in both reading-order and `-layout` modes. Note the one caveat: poppler is *representative of*, not identical to, any specific vendor's parser. |
| **Vendor ATS formatting rules** — no tables/columns/headers/footers/graphics, 2.5 MB parse ceiling, accepted file types, "highlight the text" self-test | **high** | Primary-source vendor docs read directly: Greenhouse "Unsuccessful resume parse" and "Supported formats"; Lever "Understanding Resume Parsing" (last published 2026-03-01, retrieved via Firecrawl); MIT CAPD ATS guidance. |
| **`pdftotext` flags and `-tsv`/`-bbox-layout` structure signals** | **high** | Read from the installed man page (poppler 26.08.0) and exercised; the `height`-as-font-size and `left`-as-column heuristics were observed directly in the TSV output. |
| **pandoc fragment pipeline and the `--standalone` duplicate-title bug** | **high** | Both variants rendered and extracted; the duplicate name is visible in the `--standalone` output and absent from the fragment output. |
| **reportlab fallback** | **high** | Script written and run; 1 page, correct reading order, real `•` glyphs. The `Tagged: no` / non-embedded base-14 Helvetica limitation was confirmed with `pdfinfo` and `pdffonts`. |
| **Truth gate (R1/R2/R3) catches fabrication** | **medium-high** | Implemented and verified on both a fabricated ("FedRAMP") and a legitimately tailored file. Medium-high rather than high because R2 is a lexical check: it will not catch a reworded exaggeration built entirely from master vocabulary, and it will produce false positives on unusual proper nouns until the allowlist is seeded. The diff review is the intended backstop. |
| **`git diff --no-index --word-diff` review artifact** | **high** | Run outside a git repository; output reproduced verbatim in the document. |
| **Fit-scoring rubric is deterministic and implementable** | **high** *(mechanics)* / **low** *(calibration)* | The implementation is tested — identical md5 across runs, three worked examples with full breakdowns, and the one-way-alias bug found and fixed. But the specific weights (35/20/12/12/8/5/8), the 0.6-when-no-salary default and the 80 auto-submit threshold are **my judgement, not empirical**. They have not been validated against any labelled outcome data. Calibrate per §E before trusting the threshold. |
| **JD extraction: Greenhouse and Ashby public JSON APIs work; Greenhouse pages carry no JSON-LD** | **high** | All three endpoints called live; status codes, key lists and payload sizes recorded. The Lever 404 was for one org and means "no public board there", not "the endpoint is dead" — I did not probe an org known to have one. |
| **Heading-regex requirement harvesting is fragile** | **high** | Demonstrated: 0 requirements on a real JD, then 7 must / 31 nice on the same JD after widening the patterns. This is the evidence for mandating the `low_confidence` flag and a model fallback. |
| **schema.org / Google JobPosting property names** | **high** | Read from Google Search Central and schema.org directly, including `securityClearanceRequirement` and `eligibilityToWorkRequirement`. |
| **LinkedIn scraping prohibition and the sanctioned export paths** | **high** *(policy)* / **medium** *(UI steps)* | The User Agreement language is unambiguous and the Save-to-PDF help article is current. Medium on the exact click path only because LinkedIn moves UI affordances (*More* vs *Resources*) without notice — the skill should describe the goal, not hard-code the menu. |
| **Cover letter norms (3–4 paragraphs, 250–400 words, one page)** | **medium-high** | Consistent across Yale OCS, MIT CAPD, Columbia and Princeton career-services guidance. Medium-high because it is convention, not measured outcome; the ≤300-word target is my tightening within that band. |
| **Pay-transparency context (18 states + DC; VA not among the posting-mandate states)** | **medium** | From 2026 employment-law roundups (Jackson Lewis and others), not from statute text. The rubric only uses this to justify not penalising a missing range, so an error here is low-impact — but verify VA's status before making any stronger claim. |
| **Security clearance red-flag logic (active vs. eligible; must be employer-sponsored)** | **medium** | DCSA/State Department sourcing supports "cannot self-apply, must be sponsored", but state.gov returned an error page on fetch. How long a lapsed clearance stays reinstatable is **unknown** — I would read 32 CFR Part 117 (NISPOM) and DCSA reciprocity guidance before encoding any window. |
| **Cross-platform Linux specifics** — binary names, sandbox flags, font packages, package names, systemd timers, Snap `file://` confinement | **medium** | **No Linux host was available in this session; none of it was executed.** Each claim is sourced (Playwright docs for cache paths and `--with-deps` distro support; Debian/Fedora package pages for `poppler-utils`; liberation-fonts and ArchWiki for metric compatibility; systemd/launchd docs for schedulers), and the font-stack change was verified to be a no-op on macOS. Treat §E's smoke test as a required gate on first Linux run, not a formality. |
| **macOS shell/coreutils differences** (`timeout` absent, BSD vs GNU `date`, zsh glob failure, `SHELL=/bin/zsh`) | **high** | Probed directly on this machine. |
| **Output layout, `status.json` schema, naming conventions** | **medium** | Design proposals, internally consistent and grounded in the constraints above (2.5 MB ceiling, evidence capture, idempotent re-ingest), but not validated by running a full apply cycle. The one part I would flag for review is the `status` state machine — it should be reconciled with whatever the memory/reporting brief defines, since both touch the same lifecycle. |
