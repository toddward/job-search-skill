# Search strategy

How the skill turns a free-text query into per-board search targets, crawls them, and
dedupes results. Condensed from `docs/research/job-boards.md` ("Search strategy" and
"Freshness & dedup"). `scripts/boards.py` does the parsing/rendering; this document
governs how the agent uses the rendered targets.

## Tools (exact names)

| Layer | Tool | Use for |
|---|---|---|
| 1 | `WebFetch` | Known JSON/RSS/HTML URL that already works without a browser (USAJOBS API, ATS JSON, RemoteOK API, WWR RSS, HN Algolia, guest SERPs). Cheapest, most ToS-aligned. |
| 2 | `mcp__firecrawl__firecrawl_search` | No working URL yet, or cross-ATS discovery (`site:job-boards.greenhouse.io {keywords} {location}`, etc.). Also how to use Google Jobs without scraping google.com. |
| 3 | `mcp__firecrawl__firecrawl_scrape` | Known listing URL, public HTML. One listing page, then scrape up to `search.detail_pages_per_board` detail URLs per board for JD text + apply URL + posted date. |
| 4 | `mcp__firecrawl__firecrawl_extract` | SPA filters `scrape` missed (Eightfold, Phenom, keyword boxes). Schema-extract `{title, company, location, posted, apply_url, req_id, salary}`, don't dump markdown. |
| 5 | `WebSearch` / `WebFetch` (built-in) | One-off lookups (current HN thread id, "does this board still exist"). Not a ranked-list source. |
| 6 | `mcp__playwright__browser_navigate` + `mcp__playwright__browser_snapshot` | Boards behind Cloudflare/Akamai walls or requiring a login (Indeed, Glassdoor, ZipRecruiter, Eightfold, Phenom-if-challenged, apply flows, Easy Apply). Discovery should not start here; apply almost always ends here. Persistent profile at `$JOB_SEARCH_HOME/config/browser-profile`. |

**Bash fallback:** if the Firecrawl MCP server is not connected, use the `firecrawl` skill's
CLI (`firecrawl search "..."`, `firecrawl scrape <url>`) via Bash instead of the MCP tools above.
Same caps and failure-recording rules apply.

Use layers in order 1 → 6 per board; stop as soon as a layer returns usable results. Do not
retry a board with a heavier tool just because a lighter one returned zero — record it as a
failure (see Caps below) and move on.

## Per-board construction

`scripts/boards.py parse_query` turns free text into `{keywords, location, radius_miles,
remote, raw}`. `scripts/boards.py render` fills each enabled board's template, URL-encoding
substitutions (`urllib.parse.quote`, never shell `sed`) and applying `location_alias` (e.g.
Capital One → McLean VA, Amazon → Herndon VA, Anthropic/OpenAI/Built In/Wellfound →
Washington DC, Google Careers → "…, USA", USAJOBS → full state name). Rows whose template has
no `http` (the ATS discovery row) are Firecrawl-search queries, not URLs — method becomes
`firecrawl-search`.

Example plan for "AI based jobs in the Reston, VA area" (one run):

1. LinkedIn guest SERP, 25mi, past week.
2. Dice, 25mi.
3. ClearanceJobs.
4. USAJOBS API: `Keyword=machine learning` + `LocationName=Reston, Virginia`, then again with
   `LocationName=Washington DC, District of Columbia`; also try series `2210`.
5. Built In DC listing + keyword filter if available.
6. Google Careers, Reston office query.
7. Capital One, `location=McLean, VA`.
8. Amazon AWS Herndon geo search (full lat/long params required).
9. Firecrawl search across Greenhouse/Lever/Ashby (`site:job-boards.greenhouse.io …`).
10. Anthropic + OpenAI ATS JSON, filter to DC.
11. If remote is not excluded: RemoteOK API, WWR RSS, current HN "Who is hiring" thread.
12. If still <10 results after fit filter: Booz Allen, MITRE, Leidos, Microsoft, CACI
    (Playwright).
13. Indeed / ZipRecruiter only if coverage is still thin — one SERP each, Playwright.

Always run a second **remote-US** pass in addition to the local-radius pass; many hybrid NoVA
"AI" roles never set a Virginia city, and vice versa.

## Dedup

**Fingerprint** (durable memory key, Python stdlib only — never shell `shasum`/`sha256sum`):

```python
import hashlib
fingerprint = hashlib.sha256(
    f"{company_norm}|{title_norm}|{loc_norm}|{req_id_or_empty}".encode("utf-8")
).hexdigest()
```

- `company_norm`: lowercase; strip `inc|llc|ltd|corp|corporation|the|group|co.`; map aliases
  (`booz allen hamilton`→`booz allen`, `amazon web services`→`amazon`, `google llc`→`google`).
- `title_norm`: lowercase, collapse whitespace, strip requisition suffixes like `(R0…)`; keep
  seniority words (`senior` ≠ `staff` — different jobs).
- `loc_norm`: `city, ST` or `remote-us`. Normalize DC variants to `washington, dc`. Keep
  Tysons distinct from McLean in the fingerprint even though they're the same commute radius.
- `req_id`: Greenhouse id, Ashby uuid, Workday req, USAJOBS `MatchedObjectId`, Dice uuid,
  LinkedIn numeric id. `req_id + company` alone is sufficient even if the title changed.

**Secondary match:** same `company_norm` + `title_norm` + `loc_norm`, Jaccard(title tokens)
≥ 0.8, first seen within 90 days, even without a `req_id`.

**Canonical apply URL** (keep this one; store the rest in `source_urls[]`):

1. Company ATS host (`job-boards.greenhouse.io`, `jobs.ashbyhq.com`, `jobs.lever.co`,
   `*.myworkdayjobs.com`, `amazon.jobs/.../jobs/`, `careers.microsoft.com`,
   `google.com/about/careers/…`, `capitalonecareers.com/job/`,
   `usajobs.gov/GetJob/ViewDetails/`).
2. Else first-party careers path on the employer domain.
3. Else LinkedIn `/jobs/view/{id}` (strip `refId`, `trackingId`, `position`, `pageNum`).
4. Else Dice `/job-detail/{uuid}`.
5. Else Indeed/Glassdoor/ZipRecruiter (last resort).

Strip tracking params on every URL: `utm_*`, `gh_src`, `lever-source`, duplicate `ashby_jid`,
LinkedIn `refId`/`trackingId`, Indeed `from`/`alid` (keep `vjk`, it's the job key).

Do **not** merge across seniority (`AI Engineer` vs `Lead AI Engineer`) or across offices
(Reston vs NYC). Staffing-firm clones (Dice/ClearanceJobs listing the same end-client req
through different vendors) keep separate fingerprints — the vendor is who you apply to.

## Freshness

Trust order for posted date: USAJOBS/Greenhouse/Ashby/Lever/RemoteOK JSON fields (high) >
site card text with an explicit date (high, e.g. Capital One `08/18/2026`) > relative text
("4 hours ago", "13d ago" — medium, parse to an estimate and store `date_precision=relative`)
> no date at all (low — set `posted_at=null`, `first_seen=now`, rank below dated postings).

**Expire** a posting (`status=expired`) when: HTTP 404/410 on the canonical URL; page text
matches `/no longer (accepting|available)|this job has expired|position (has been )?filled|
requisition closed/i`; USAJOBS `ApplicationCloseDate` < now; or an ATS JSON board drops the id
for 7 consecutive days (`missing` first, then expire). Do not expire solely because LinkedIn
shows a stale relative date — recheck the canonical URL first.

**Repost:** same fingerprint, new `posted_at` after a gap, or an explicit "Reposted" label.
Keep one memory row, bump `repost_count`, update `last_posted_at`/`last_seen`. A repost of a
job the user marked `not_interested` stays suppressed. A genuine new `req_id` with a similar
title after a cooldown *is* a new job.

## Caps (per run)

- ≤ `search.detail_pages_per_board` (default 30) detail-page fetches per board.
- Per-board wall-clock budget: `search.board_timeout_seconds` (default 90s). Abort the board
  and move on if exceeded.
- **Record every board failure with a reason** (timeout, bot-wall, HTTP error, empty result,
  parse error) as an entry in `memory/logs/runs.jsonl` — never fail the whole run silently
  because one board errored.
