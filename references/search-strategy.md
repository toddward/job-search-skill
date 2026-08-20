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
| 6 | `mcp__playwright__browser_navigate` + `mcp__playwright__browser_snapshot` | Boards behind Cloudflare/Akamai walls or requiring a login (Indeed, Glassdoor, ZipRecruiter, Eightfold, Phenom-if-challenged, apply flows, Easy Apply). Discovery should not start here; apply almost always ends here. Persistent profile at `$JOBSEARCH_HOME/config/browser-profile`. |

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

**Fingerprint** (durable memory key): never compute it here — call
`scripts/fingerprint.py`, which is the single authority. `fingerprint(company, title,
location, remote)` returns the **first 16 hex characters** of a SHA-256 over the three
normalized keys joined by `\x1f`; no requisition id takes part, so the same posting keeps one
identity across boards that expose different ids.

- `company_key`: lowercase, accent-folded; strips legal suffixes (`inc|llc|ltd|corp|co|the|
  group|…`); maps aliases (`booz allen hamilton`→`booz allen`, `amazon web services`→`amazon`,
  `google llc`→`google`).
- `title_key`: lowercase, collapse whitespace, strip `(remote)`/req-number noise, expand
  `sr`→`senior`, `eng`→`engineer`, `swe`→`software engineer`; seniority words are kept
  (`senior` ≠ `staff` — different jobs).
- `location_key`: `city-st` or `remote-us`/`remote-<qualifier>`; DC variants normalize to
  `washington-dc`. Tysons stays distinct from McLean even though it is the same commute.
- The per-board posting identity is separate: `posting_id(url)` = sha256 of the canonical URL,
  stored per entry in `sources[]`.

**Secondary match:** same `company_key` + `location_key` and
`fingerprint.titles_similar(a, b)` (`SequenceMatcher` ratio ≥ 0.90 over the title keys),
first seen within 90 days — for near-identical titles that hash to different fingerprints.

**Canonical apply URL** (keep this one; store every board's URL in `sources[]`):

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
("4 hours ago", "13d ago" — medium, parse to an estimate) > no date at all (low — set
`posted_at=null`, `first_seen=now`, rank below dated postings). `posted_at`/`closes_at` are
stored as bare `YYYY-MM-DD` (`jobs_db.upsert` truncates anything longer).

**Expire** a posting (`status=expired`) when: HTTP 404/410 on the canonical URL; page text
matches `/no longer (accepting|available)|this job has expired|position (has been )?filled|
requisition closed/i`; USAJOBS `ApplicationCloseDate` < now; or an ATS JSON board drops the id
for 7 consecutive days (`missing` first, then expire). Do not expire solely because LinkedIn
shows a stale relative date — recheck the canonical URL first.

**Repost:** same fingerprint, a changed `content_hash`, and a newer `posted_at`. Keep one
memory row; `jobs_db.upsert` bumps `version`, resets the row to `new`, clears `last_shown`,
and updates `last_seen`. A repost of a job the user marked `not_interested` stays suppressed
(status is preserved across upserts). A materially different title after a cooldown hashes to a
different fingerprint and *is* a new job.

## Caps (per run)

- ≤ `search.detail_pages_per_board` (default 30) detail-page fetches per board.
- Per-board wall-clock budget: `search.board_timeout_seconds` (default 90s). Abort the board
  and move on if exceeded.
- **Record every board failure with a reason** (timeout, bot-wall, HTTP error, empty result,
  parse error) in the run's `boards_failed[]`, which `report.py write` appends to
  `memory/runs.jsonl` (and prints in the report header) — never fail the whole run silently
  because one board errored.
