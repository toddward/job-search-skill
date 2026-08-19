# Job-board inventory for a Reston / Northern Virginia AI job-search skill (August 2026)

Checked live on **2026-08-19**. Templates below were hit in a browser/fetch pass unless a board explicitly notes a bot wall. URL-encode `{keywords}` and `{location}` (`AI engineer` → `AI%20engineer`; `Reston, VA` → `Reston%2C%20VA`) in **Python 3** (`urllib.parse.quote`), not shell-specific `sed`. `{radius}` is miles unless a vendor uses km. `{remote}` is `true` / `false` / empty; empty means “local + remote mixed.”

The skill runs on **macOS and Linux** (Debian/Ubuntu/Fedora-class, including headless cron hosts). Board URLs are OS-agnostic. Browser, PDF, scheduler, and profile paths are not — see **Cross-platform notes**. Default-on boards in the seed table are `firecrawl` / `webfetch` so a Linux container with no GUI can still crawl; Playwright boards stay opt-in.

For Reston-area AI / ML / platform-engineering searches, treat **Reston + Herndon + McLean + Tysons + Dulles** as one labor market (about 25 miles). **40–50 miles** also covers Arlington, Washington DC, and Bristow / Victory Lakes (Prince William County) if that is the home location. Always run a **second remote-US pass** — many NoVA “AI” listings are hybrid-in-office with a Reston or DC badge, and many genuine remote roles never set a Virginia city.

**Otta is Welcome to the Jungle.** The US product is `us.welcometothejungle.com` / `app.welcometothejungle.com`; Apple still ships the app as “Welcome to the Jungle (Otta).”

**Anthropic and OpenAI both hire in Washington, DC** as of this week (policy, public-sector, applied-AI, and some engineering). They are not Reston campus employers; they are DC-metro AI employers. Filter their boards on `Washington, DC` rather than Reston.

---

## Board inventory

### 1. LinkedIn (guest job search)

- **Base URL:** https://www.linkedin.com/jobs
- **Search URL template (verified guest HTML, 2026-08-19):**  
  `https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&distance={radius}&f_TPR=r604800&sortBy=DD`  
  Remote-only: append `&f_WT=2`. Hybrid: `&f_WT=3`. On-site: `&f_WT=1`. Easy Apply: `&f_AL=true`. Past 24h: `f_TPR=r86400`. Past month: `f_TPR=r2592000`.  
  Example that returned 1,000+ AI Engineer cards in Reston: https://www.linkedin.com/jobs/search?keywords=AI%20engineer&location=Reston%2C%20VA&distance=25
- **Guest pagination API (HTML fragments, no login):**  
  `https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={keywords}&location={location}&distance={radius}&start={offset}`  
  `start` steps of 25. Documented in current scrapers (e.g. https://dev.to/agenthustler/how-to-scrape-linkedin-job-listings-in-2026-public-data-without-login-5094). Guest HTML still caps; a sign-in modal appears after the first public page.
- **Access:** public HTML for the guest SERP; heavily JS after login; Easy Apply and “under 10 applicants” need an account.
- **Firecrawl:** `search` is useful to discover a job’s company career URL. `scrape` of the guest SERP returns titles, companies, locations, relative dates, and `/jobs/view/{id}` links (verified). Do not paginate aggressively. Skip `agent` unless you need logged-in filters.
- **Playwright:** required for Easy Apply, full pagination, and any apply flow. Persistent profile after the user logs in once (store under `$JOB_SEARCH_HOME/config/browser-profile` on both macOS and Linux; see Cross-platform notes). On headless Linux use Playwright’s bundled Chromium, not a missing `/Applications/Google Chrome.app`.
- **Rate-limit / ToS:** LinkedIn User Agreement (https://www.linkedin.com/legal/user-agreement) forbids scraping, crawlers, and copying job/profile data. Guest search is the least-toxic read path; still treat as fragile and low-volume (one search + one detail page per job, backoff). Logged-in automation can lock the account.
- **NoVA note:** guest Reston+25mi SERP currently surfaces Booz Allen, MITRE, Capital One, Accenture Federal, Peraton, Steampunk, ID.me, and many staffing firms.

### 2. Indeed

- **Base URL:** https://www.indeed.com/
- **Search URL template:**  
  `https://www.indeed.com/jobs?q={keywords}&l={location}&radius={radius}&fromage=7&sort=date`  
  Remote-only: `l=Remote` (or `l=United+States` plus the remote filter). Age: `fromage=1|3|7|14`. Pagination: `&start={0,10,20,…}`.  
  Documented parameter set: https://decodo.com/blog/scrape-indeed-guide
- **Access:** public HTML in a real browser; **Akamai/Cloudflare “Security Check”** for datacenter fetches (verified 2026-08-19 on `https://www.indeed.com/jobs?q=AI+engineer&l=Reston%2C+VA&radius=25`). Heavily JS-rendered cards.
- **Firecrawl:** `scrape` of SERPs often fails or returns a challenge page. `search` can still find Indeed URLs via Google. Prefer Playwright.
- **Playwright:** required. Persistent profile helps; Indeed still rate-limits headless Chromium (Playwright bundle or system Chrome/Chromium — same on macOS and Linux). On Linux CI/containers install with `npx playwright install --with-deps chromium`.
- **Rate-limit / ToS:** Indeed’s terms and robots restrict automated collection. Highest bot-wall of the general aggregators. Use as a **dedup/coverage backfill**, not the primary crawl. Cap to 1–2 SERPs per run.
- **NoVA note:** huge volume, lots of staffing duplicates of Dice/ClearanceJobs/company ATS posts.

### 3. Glassdoor (Indeed-owned)

- **Base URL:** https://www.glassdoor.com/Job/index.htm
- **Search URL template:**  
  `https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keywords}&locKeyword={location}&radius={radius}`  
  Reston city id used on Glassdoor listings is **IC1130404** (e.g. https://www.glassdoor.com/Jobs/Google-google-software-engineering-Reston-Jobs-EI_IE9079.0,6_KO7,34_IL.35,41_IC1130404.htm). Slug form: `https://www.glassdoor.com/Job/reston-va-{slug}-jobs-SRCH_IL.0,9_IC1130404_KO10,{end}.htm` — brittle because KO offsets depend on keyword length. Prefer the `jobs.htm?sc.keyword=` form. Remote: UI `remoteWorkType` query (values drift; if a scrape returns unfiltered results, fall back to keyword `remote`).
- **Access:** public HTML with a login/community wall; heavily JS. Reviews/salaries often require an account.
- **Firecrawl:** mixed. Job cards sometimes render; full JD often does not. `search` can find Glassdoor job-listing URLs.
- **Playwright:** needed for a logged-in profile if you want JDs + Easy Apply. Not worth it as a default board — Indeed already aggregates much of the same inventory.
- **Rate-limit / ToS:** same family as Indeed; aggressive bot detection. Disabled by default.

### 4. ZipRecruiter

- **Base URL:** https://www.ziprecruiter.com/
- **Search URL template (slug form, used live in Aug 2026 indexes):**  
  `https://www.ziprecruiter.com/Jobs/{keywords-as-hyphen-slug}/-in-{City},{ST}`  
  Example indexed today: https://www.ziprecruiter.com/Jobs/It/-in-Reston,VA  
  Query form (Cloudflare-challenged from this environment):  
  `https://www.ziprecruiter.com/jobs-search?search={keywords}&location={location}`  
  `{radius}` is not a first-class query param on the slug URLs; location is city-level. `{remote}`: use location `Remote` or add `remote` to keywords.
- **Access:** public HTML behind Cloudflare (“Just a moment…”) for automated clients (verified 2026-08-19). 1-click apply needs an account.
- **Firecrawl:** `scrape` likely hits the challenge; `search` can recover indexed ZipRecruiter URLs.
- **Playwright:** required for a usable SERP. Persistent profile for 1-click apply.
- **Rate-limit / ToS:** commercial aggregator; no public API. High duplicate rate vs Indeed/LinkedIn. Disabled by default.

### 5. Dice

- **Base URL:** https://www.dice.com/
- **Search URL template (verified 2026-08-19, 1,694 AI-engineer hits near Reston):**  
  `https://www.dice.com/jobs?q={keywords}&location={location}&radius={radius}&radiusUnit=mi`  
  Example: https://www.dice.com/jobs?q=AI+engineer&location=Reston%2C+VA&radius=25&radiusUnit=mi  
  Slug alternate: `https://www.dice.com/jobs/q-{keywords}-l-{location}-jobs`  
  Remote: `location=Remote` or keep Reston and read the “Remote or …” workplace badge. Pagination is JS infinite-scroll on `/job-detail/{uuid}`.
- **Access:** public HTML + JS. Search results and JD body rendered enough for scrape (verified). Apply/Easy Apply needs login.
- **Firecrawl:** **good.** `scrape` of the search URL returned titles, companies, locations, salaries, ages, and `/job-detail/` links. Use `scrape` on each detail URL for the full JD. `agent` only if you must drive filters in the UI.
- **Playwright:** only for Easy Apply / account features.
- **Rate-limit / ToS:** tech-specialist board; still a commercial site. Moderate politeness (detail pages 1–2s apart). Strong NoVA signal (Capital One, Booz Allen, MITRE, Leidos, Navy Federal, contractors).
- **NoVA note:** default radius in the UI was 30 miles when unset; always pass `{radius}`.

### 6. ClearanceJobs

- **Base URL:** https://www.clearancejobs.com/
- **Search URL template (verified 2026-08-19):**  
  `https://www.clearancejobs.com/jobs?keywords={keywords}&location={location}`  
  Example: https://www.clearancejobs.com/jobs?keywords=AI+engineer&location=Reston%2C+VA  
  `{radius}` is not a documented query param; location is city/metro. `{remote}`: omit location or use `Remote`. About page stats as of 2026-08-01: https://about.clearancejobs.com/
- **Access:** public HTML search. Applying and contacting hiring managers requires a cleared-candidate account.
- **Firecrawl:** **good** for search cards (title, company, clearance, polygraph, on-site vs remote, relative date, `/jobs/{id}/…` links). Scrape the job URL for the full JD.
- **Playwright:** needed to apply. Persistent profile after the user registers (clearance self-attestation).
- **Rate-limit / ToS:** DHI / CareerBuilder family. Do not scrape resumes (employer product). Job search is the intended public surface. Essential for NoVA/IC/DoD AI work.
- **NoVA note:** Reston hits include TS/SCI + polygraph roles that never appear on Built In or Wellfound.

### 7. USAJOBS (official API)

- **Base HTML:** https://www.usajobs.gov/
- **Developer:** https://developer.usajobs.gov/ — Search API reference: https://developer.usajobs.gov/api-reference/get-api-search  
  Auth: https://developer.usajobs.gov/Guides/Authentication  
  Rate limits: https://developer.usajobs.gov/guides/rate-limiting (max **10,000 rows/query**, **500 rows/page**; default page size 250, default hiring path Public).
- **Search URL template (API — preferred):**  
  `https://data.usajobs.gov/api/search?Keyword={keywords}&LocationName={location}&Radius={radius}&ResultsPerPage=50&Page=1&DatePosted=7&HiringPath=public`  
  Remote-only: `&RemoteIndicator=true`. Reston example location: `Reston,%20Virginia`. Also search `Washington%20DC,%20District%20of%20Columbia` and occupational series `2210` (IT) / keyword `machine learning`.  
  Headers: `Host: data.usajobs.gov`, `User-Agent: {your-registration-email}`, `Authorization-Key: {key}`. Free key via https://developer.usajobs.gov/apirequest/
- **HTML template (JS-heavy, weaker than the API):**  
  `https://www.usajobs.gov/Search/Results?k={keywords}&l={location}`  
  A Reston + “artificial intelligence” HTML search returned **zero** hits on 2026-08-19; federal titles rarely contain “AI engineer.” Prefer `Keyword=computer%20scientist` / `data%20scientist` / `2210` via the API.
- **Access:** official **JSON API**. HTML is a JS app.
- **Firecrawl:** skip. Use `webfetch`/HTTP to the API. `scrape` of HTML search is a waste.
- **Playwright:** only to submit an application on usajobs.gov (login.gov). Persistent profile.
- **Rate-limit / ToS:** this is the **allowed** integration path. Do not scrape the website if you have a key. Slice by agency or series if a query would exceed 10k rows.
- **Canonical URL:** `PositionURI` / `ApplyURI` from the payload (https://www.usajobs.gov/GetJob/ViewDetails/{id}). Dates: `PublicationStartDate`, `ApplicationCloseDate` — closed ≠ 404; drop when `ApplicationCloseDate` < now.

### 8. Wellfound (formerly AngelList Talent)

- **Base URL:** https://wellfound.com/jobs
- **Search URL templates (verified):**  
  Location hub: `https://wellfound.com/location/{location-slug}`  
  DC (230 results today): https://wellfound.com/location/district-of-columbia  
  Role+location: `https://wellfound.com/role/l/{role-slug}/{location-slug}`  
  Remote: https://wellfound.com/remote  
  Querystring `?q=` on `/jobs` did **not** filter (SPA landing page). `{radius}` is not supported. `{remote}`: use `/remote` or `/role/r/{role}`.
- **Access:** public HTML for location/role hubs; apply/save needs an account. Heavily JS.
- **Firecrawl:** `scrape` of `/location/district-of-columbia` returned real cards (company, title, salary, workplace, relative date, `/jobs/{id}-slug`). `scrape` of `/jobs?q=…` did not. Use location/role URLs, not the homepage search box.
- **Playwright:** needed to apply (one-click profile). Optional for scraping if Firecrawl’s JS wait is enough.
- **Rate-limit / ToS:** no public list API. Don’t hammer. Startup-biased; weak on Booz/Leidos, useful for DC AI startups (Vannevar, Scale public-sector, Statecraft, etc.).

### 9. Built In (Washington DC hub)

- **Base URL:** https://builtin.com/
- **DC jobs (verified 2026-08-19, live cards with salaries and “Reposted”):**  
  `https://builtin.com/jobs/washington-dc`  
  Remote-in-DC: `https://builtin.com/jobs/remote/washington-dc`  
  Keyword: the page has a “Job Title, Company or Keyword” box (JS). If a query param is needed, try `https://builtin.com/jobs/washington-dc?search={keywords}` and fall back to Firecrawl `search` `site:builtin.com/job {keywords} Washington`. `{radius}` is metro-level, not miles.
- **Access:** public HTML listings (verified). Easy Apply / alerts need an account.
- **Firecrawl:** **good** on the DC listing page (title, company, salary band, workplace, seniority, skills, relative date including **Reposted**, `/job/{slug}/{id}`).
- **Playwright:** only for Easy Apply and the keyword box if query params fail.
- **Rate-limit / ToS:** commercial; polite scrape of public listing pages is the practical path. Excellent for non-cleared tech/AI in DC/NoVA (Palantir, Shield AI, Cloudflare, Datadog public-sector, etc.).

### 10. Welcome to the Jungle (formerly Otta)

- **Base URL (US):** https://us.welcometothejungle.com/  
  App: https://app.welcometothejungle.com/  
  Global jobs: https://www.welcometothejungle.com/en/jobs  
  Status: Otta was absorbed; the iOS app is still branded “(Otta)” (https://apps.apple.com/us/app/welcome-to-the-jungle-otta/id1640509194). US marketing claims ~3,500 companies / 70k jobs.
- **Search URL template:**  
  `https://www.welcometothejungle.com/en/jobs?query={keywords}`  
  US-only: add country refinements when the UI exposes them. The US site funnels first-time users through https://app.welcometothejungle.com/initial-preferences (login + matching quiz). `{location}` / `{radius}` / `{remote}` are preference-service fields, not stable public query params.
- **Access:** **requires login / preference onboarding** for the product people actually use. Public `/en/jobs` exists but is secondary.
- **Firecrawl:** `scrape` of the marketing site is not a job feed. `agent` might complete onboarding once; not worth it.
- **Playwright:** required, persistent profile after the user finishes Otta/WTTJ preferences.
- **Rate-limit / ToS:** candidate marketplace; scraping logged-in recs likely violates terms. **Disabled by default.** Revisit only if the user already lives in the WTTJ app.

### 11. RemoteOK

- **Base URL:** https://remoteok.com/
- **Search URL template:**  
  `https://remoteok.com/remote-{keywords-as-hyphen-slug}-jobs`  
  Example (218 AI jobs today): https://remoteok.com/remote-ai-jobs  
  `{location}` / `{radius}` N/A (remote-only). `{remote}` is implicit `true`. Region chips exist in the UI (US, Worldwide).
- **JSON API (preferred):** `https://remoteok.com/api` and `https://remoteok.com/json` (linked from the site footer as “Remote Jobs API” / “JSON feed”). Filter client-side on tags, position, and `location` constraints. Legal note on the API: attribution + don’t republish the whole dump as a competing board.
- **Access:** public HTML + **public JSON**. HTML scrape of tag pages returned a mostly empty table shell; **API is the real interface**.
- **Firecrawl:** skip HTML. `webfetch` the API.
- **Playwright:** not needed for discovery.
- **Rate-limit / ToS:** public API with community norms (User-Agent, modest frequency). Enable when the user query includes remote.

### 12. We Work Remotely

- **Base URL:** https://weworkremotely.com/
- **Search URL template (verified, returned AI/ML engineering cards):**  
  `https://weworkremotely.com/remote-jobs/search?term={keywords}`  
  RSS (official, attribution required): https://weworkremotely.com/remote-jobs.rss  
  Docs: https://weworkremotely.com/remote-job-rss-feed  
  Category RSS: `https://weworkremotely.com/categories/remote-full-stack-programming-jobs.rss` (and design, back-end, devops, product). `{location}` is “Anywhere” / country flags on each post. `{radius}` N/A. `{remote}` implicit.
- **Access:** public HTML + RSS.
- **Firecrawl:** `scrape` of the search URL worked. Prefer **RSS + webfetch** to avoid HTML churn.
- **Playwright:** not needed for discovery.
- **Rate-limit / ToS:** RSS is the blessed bulk path; attribute links back to WWR. Smaller volume, higher quality than RemoteOK.

### 13. Hacker News “Who is hiring?”

- **Current thread (August 2026, verified):** https://news.ycombinator.com/item?id=49156683  
  Algolia discovery: `https://hn.algolia.com/api/v1/search_by_date?query=Ask%20HN%3A%20Who%20is%20hiring&tags=story,author_whoishiring`  
  Mirrors linked from the official post: https://nthesis.ai/public/hn-who-is-hiring , https://hnjobs.emilburzo.com , https://dheerajck.github.io/hnwhoishiring/
- **Search URL template:** Algolia first → official `item?id={id}` for the current month. `{keywords}` filtered client-side (comment text). `{location}` / `{remote}`: comments are required to say `REMOTE` / `ONSITE` / city. `{radius}` N/A.
- **Access:** public HTML + Algolia JSON. No login.
- **Firecrawl:** `scrape` the thread (large). Better: Algolia `search_by_date` with `tags=comment,story_{id}` then keyword filter.
- **Playwright:** not needed.
- **Rate-limit / ToS:** HN guidelines; Algolia public API. One fetch per monthly thread. Unique, high-signal, low volume. Stellar Science (Tysons VA / DC) appeared in the August 2026 thread.

### 14. Greenhouse public boards (how to search across them)

- **HTML:** `https://job-boards.greenhouse.io/{company}` (current host; older `boards.greenhouse.io/{company}` still redirects for many tenants). Anthropic uses this: https://job-boards.greenhouse.io/anthropic
- **JSON API (no auth, per company):**  
  `https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true`  
  Docs: https://developers.greenhouse.io/job-board.html and overview https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview  
  2026 roundup: https://cavuno.com/blog/ats-platforms-public-job-posting-apis
- **Cross-company search template (Google/Firecrawl search):**  
  `site:job-boards.greenhouse.io ({keywords}) ("Reston" OR "Herndon" OR "McLean" OR "Arlington" OR "Washington, DC")`  
  There is **no official global Greenhouse search**. You maintain a `{company}` token list (Anthropic, Stripe, Cloudflare, …) and/or discover tokens via `search`.
- **Access:** public JSON + public HTML. Apply forms are public POST (Harvest key only for submitting via API — do not do that from the skill; send the user to the apply URL).
- **Firecrawl:** `search` for discovery; `webfetch` JSON per token (best). `scrape` HTML boards if JSON is disabled for that tenant.
- **Playwright:** only to fill Greenhouse embed forms on company sites.
- **Rate-limit / ToS:** Job Board API is meant for career sites. Keep a token allowlist; 1 req/board/run is enough. `{location}` / `{remote}` filtered client-side on `offices` / `location`. `{radius}` N/A.

### 15. Lever public boards

- **HTML:** `https://jobs.lever.co/{company}`
- **JSON API (no auth):** `https://api.lever.co/v0/postings/{company}?mode=json`  
  (same 2026 ATS-API roundup as Greenhouse).
- **Cross-company search:**  
  `site:jobs.lever.co ({keywords}) ("Reston" OR "Washington, DC" OR "Remote")`
- **Access:** public JSON + HTML.
- **Firecrawl / Playwright / ToS:** same pattern as Greenhouse. Client-side filter on `categories.location` / `workplaceType`. HN August 2026 still points at live Lever boards (e.g. Eleos).

### 16. Ashby public boards

- **HTML:** `https://jobs.ashbyhq.com/{company}` — OpenAI: https://jobs.ashbyhq.com/openai (Washington, DC roles live today).
- **JSON API (no auth):**  
  `https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true`  
  Docs: https://developers.ashbyhq.com/docs/public-job-posting-api
- **Cross-company search:**  
  `site:jobs.ashbyhq.com ({keywords}) ("Washington, DC" OR "Reston" OR "Remote")`
- **Access:** public JSON + HTML. Compensation bands often included (`includeCompensation=true`).
- **Firecrawl:** `webfetch` JSON. HTML scrape also works (OpenAI board listed DC hybrid roles with salary).
- **Playwright:** apply forms.
- **Rate-limit / ToS:** public posting API is the intended read path. Token allowlist: `openai`, plus other AI labs/startups the user cares about.

### 17. Google Jobs (search vertical)

- **Templates in use in 2026:**  
  `https://www.google.com/search?q={keywords}+jobs+{location}&udm=8`  
  Legacy: `https://www.google.com/search?q={keywords}+jobs+in+{location}&ibp=htl;jobs`  
  Employer docs: https://jobs.google.com/about/  
  Scrapers still target `udm=8` (https://apify.com/memo23/google-jobs-scraper). A raw fetch of `udm=8` from this environment returned a Google interstitial, not cards.
- **Access:** heavily JS, bot-gated. Aggregates LinkedIn, Indeed, Glassdoor, company pages.
- **Firecrawl:** `search` (not `scrape` of google.com) is the right tool — it is a search API, not a Google HTML scrape. Use it to **discover canonical apply URLs**, then scrape those.
- **Playwright:** possible but against Google ToS; don’t. Use Firecrawl `search` / WebSearch.
- **Rate-limit / ToS:** do not scrape google.com/search HTML. Huntr’s 2026 board study still ranks Google Jobs as a high-conversion aggregator (https://questromfeld.bu.edu/blog/2026/03/10/announcing-the-9-best-job-search-sites-job-boards-of-2026-backed-by-600k-applications/). Treat hits as pointers, then canonicalize off-Google.

### 18. Amazon / AWS (Herndon, VA)

- **Base:** https://www.amazon.jobs/  
  Location hub: https://www.amazon.jobs/location/herndon-area-va  
  Search (geo params from a live Herndon AWS SERP indexed 2026-08-19, posting dates including Aug 14, 2026):  
  `https://www.amazon.jobs/en/search?base_query={keywords}&loc_query=Herndon%2C%20VA%2C%20United%20States&latitude=38.96969&longitude=-77.38555&radius=40km&distanceType=Mi&city=Herndon&country=USA&region=Virginia&county=Fairfax`  
  AWS-only: add `business_category[]=amazon-web-services`. `{remote}`: Amazon encodes workplace in the JD, not a clean flag — keyword `remote` or filter after scrape. `{radius}` here is **km in the `radius` param** (their UI mixes Mi + km; 40km ≈ 25mi).
- **Access:** public HTML, JS search. A stripped `base_query`+`loc_query` without lat/long returned an empty chrome page; **send the full geo query**.
- **Firecrawl:** `scrape` with wait on the full geo URL. `agent` if category chips must be clicked.
- **Playwright:** apply on amazon.jobs (account). Persistent profile.
- **Rate-limit / ToS:** personal job search is fine; don’t bulk-harvest. Herndon is one of the largest AWS hubs; 500+ Herndon listings on the location facet.

### 19. Microsoft (Reston, VA / DC Metro)

- **Marketing:** https://careers.microsoft.com/  
  DC Metro (Elkridge, MD **and Reston, VA**, verified): https://careers.microsoft.com/professionals/us/en/l-dcmetro  
  **Live search (Eightfold PCS):** `https://apply.careers.microsoft.com/careers?query={keywords}&location=United+States%2C+Virginia&hl=en`  
  `{radius}`: Eightfold `locationRadiusDistanceDefault` is **160 km** on this instance. `{remote}`: `include_remote` is default-true in their config. Reston also appears on LinkedIn as Microsoft jobs.
- **Access:** **heavily JS** (Eightfold). Fetching the search URL returns config JSON, not job cards.
- **Firecrawl:** `scrape` with JS wait may still miss the job list. `agent` or Playwright to extract cards. WebSearch `site:jobs.careers.microsoft.com Reston` as backup.
- **Playwright:** required for a reliable listing + apply. Persistent Microsoft account.
- **Rate-limit / ToS:** careers ToS; personal search OK. Enable if Playwright is already in the run; otherwise keep off default HTML crawl.

### 20. Google Careers (Reston, VA office)

- **Office page (Reston is a first-class Google location):** https://www.google.com/about/careers/applications/locations/reston/  
  Locations index: https://www.google.com/about/careers/applications/locations/
- **Search URL template (verified 2026-08-19, 59 jobs for `AI engineer` + Reston):**  
  `https://www.google.com/about/careers/applications/jobs/results/?q={keywords}&location=Reston,%20VA,%20USA`  
  Example: https://www.google.com/about/careers/applications/jobs/results/?q=AI%20engineer&location=Reston,%20VA,%20USA  
  `{radius}` N/A (office filter). `{remote}`: “Remote eligible” chip on the page. Public Sector / Cloud Security / SRE roles in Reston often require Secret or TS/SCI.
- **Access:** public HTML, JS, but **scrape returned full JDs** (min quals, clearance, apply links).
- **Firecrawl:** **good.** Prefer `scrape` of this URL over Google Jobs.
- **Playwright:** apply on Google’s application site (account).
- **Rate-limit / ToS:** personal use of the careers site is expected. Do not hit it as a general-purpose scraper.

### 21. Booz Allen Hamilton

- **Base:** https://www.boozallen.com/careers.html  
  Search UI: https://careers.boozallen.com/jobs/search  
  Template: `https://careers.boozallen.com/jobs/search?q={keywords}`  
  Workday mirror: `https://bah.wd1.myworkdayjobs.com/BAH_Jobs?q={keywords}`  
  `{location}`: the HTML search has Country / State fields (use `Virginia` / `District of Columbia`) rather than a radius. `{remote}`: Remote Work facet (Yes/Hybrid/No). A `q=AI` fetch returned a real table of jobs but did **not** clearly apply the keyword in the first 20 rows — treat as JS and confirm with Playwright or Workday.
- **Access:** public HTML table + Workday. Apply needs an account.
- **Firecrawl:** `scrape` gets *some* rows; keyword/location filters are unreliable without JS. Prefer Playwright or Workday `webfetch` if the JSON endpoint is reachable.
- **Playwright:** recommended. Persistent profile for apply.
- **Rate-limit / ToS:** personal search OK. Booz Allen is a primary NoVA AI employer (Arlington, McLean, DC). Recruiter-scam warning is on the search page — ignore outbound “Booz” emails that don’t match careers.boozallen.com.

### 22. Leidos (HQ Reston, VA)

- **Base:** https://careers.leidos.com/  
  Company site notes HQ Reston and FY revenue ~$17.2B for the year ended 2026-01-02 (https://careers.leidos.com/). Search is Phenom-class / JS. Template to try:  
  `https://careers.leidos.com/search/jobs?q={keywords}&location={location}`  
  `{radius}` unknown; `{remote}` via location `Remote`. Homepage fetch from this environment hit Cloudflare.
- **Access:** public, JS, bot-walled from datacenters.
- **Firecrawl:** `scrape` with JS; if challenged, Playwright. Firecrawl `search` `site:careers.leidos.com AI Reston`.
- **Playwright:** likely required.
- **Rate-limit / ToS:** personal search OK. HQ is Reston — high priority for this user even if the HTML is annoying.

### 23. CACI (Eightfold)

- **Base:** https://careers.caci.com/  
  **Live search (verified title “Ai jobs in Reston, Va”):**  
  `https://searchcareers.caci.com/careers?query={keywords}&location={location}`  
  `{radius}`: Eightfold default **80 km**. `{remote}`: `include_remote` default true; facet `remotetype` / `work_location_option`. Clearance facet: `minimum_clearance_requiredto_start`.
- **Access:** Eightfold SPA (same family as Microsoft). Fetch returns config, not cards.
- **Firecrawl:** `agent` or Playwright. `search` `site:searchcareers.caci.com AI Reston` as backup.
- **Playwright:** required for listings + apply. Persistent profile.
- **Rate-limit / ToS:** personal search OK. Strong cleared-AI inventory.

### 24. SAIC (HQ Reston, VA)

- **Base:** https://jobs.saic.com/  
  Reston slice: https://jobs.saic.com/search/jobs/in/reston  
  HQ address on the site: 12010 Sunset Hills Road, Reston, VA.  
  Template: `https://jobs.saic.com/search/jobs?q={keywords}&location={location}`  
  Remote: https://jobs.saic.com/search/jobs/in/remote-work  
  `{radius}` not first-class. Homepage search fetch hit Cloudflare from this environment.
- **Access:** public JS, bot-walled.
- **Firecrawl / Playwright:** same as Leidos. Enable for NoVA completeness; expect Playwright.
- **Rate-limit / ToS:** personal search OK.

### 25. Capital One (McLean, VA)

- **Base:** https://www.capitalonecareers.com/  
  Workday: https://capitalone.wd12.myworkdayjobs.com/Capital_One  
  **Search template (verified 2026-08-19, “796 AI engineer jobs in McLean, VA”, including an AI Engineer posted 2026-08-18):**  
  `https://www.capitalonecareers.com/search-jobs?k={keywords}&l={location}`  
  Example: https://www.capitalonecareers.com/search-jobs?k=AI%20engineer&l=McLean,%20VA  
  `{radius}` is SmashFly/Phenom internal (not a documented mile param). `{remote}`: Remote / Remote Eligible facets. McLean is the right city, not Reston.
- **Access:** public HTML (TalentBrew). Scrape returned real job links with **posted dates as YYYY-MM-DD**.
- **Firecrawl:** **good.** `scrape` the search URL; follow `/job/mclean/…` for JDs.
- **Playwright:** apply (Workday). Persistent profile.
- **Rate-limit / ToS:** personal search OK. Best commercial-bank AI platform-engineering source in NoVA.

### 26. MITRE (McLean, VA)

- **Base:** https://careers.mitre.org/  
  Phenom search: `https://careers.mitre.org/us/en/search-results?keywords={keywords}`  
  A keywords=AI fetch returned the Phenom shell (“No results for ${pageStateData.searchKeyword}”) — **JS required**. AI/ML is listed as a hiring area on the homepage.
- **Access:** Phenom SPA.
- **Firecrawl:** `agent` with wait, or Playwright. Firecrawl `search` `site:careers.mitre.org "machine learning" McLean`.
- **Playwright:** recommended.
- **Rate-limit / ToS:** FFRDC careers site; personal search OK. McLean HQ + Springfield/Bedford. Many roles need US citizenship; some need clearance.

### 27. Anthropic (Washington, DC office / public sector)

- **Base:** https://www.anthropic.com/careers  
  Jobs: https://www.anthropic.com/careers/jobs (verified 2026-08-19)  
  Apply host: `https://job-boards.greenhouse.io/anthropic/jobs/{id}`  
  JSON: `https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true`  
  `{keywords}` / `{location}`: client-side filter of the JSON (`Washington, DC`, `Remote-Friendly`). `{radius}` N/A. `{remote}`: many “Remote-Friendly, United States” + DC.
- **DC roles live today include:** Applied AI Architect, Public Sector (National Security) — Washington, DC; Staff+ Software Engineer, Public Sector (includes DC); Product Manager, Public Sector — DC; External Affairs, US Federal — DC; multiple Safeguards Enforcement Analyst roles listing DC; Enterprise Account Executive federal/civilian — DC. This is a **policy + public-sector office**, not a Reston lab. FAQ on the careers page still says most staff are Bay Area office-centric (https://www.anthropic.com/careers).
- **Access:** public HTML + Greenhouse JSON.
- **Firecrawl:** `webfetch` JSON, or `scrape` `/careers/jobs`.
- **Playwright:** Greenhouse apply.
- **Rate-limit / ToS:** public board. One JSON pull per run.

### 28. OpenAI (Washington, DC office)

- **Base:** https://openai.com/careers/  
  Board: https://jobs.ashbyhq.com/openai  
  JSON: `https://api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=true`  
  `{keywords}` / `{location}`: filter JSON on `Washington, DC`. `{remote}`: many hybrid DC gov roles. `{radius}` N/A.
- **DC roles live today include:** Senior Staff Software Engineer, Gov (DC; SF; Seattle, hybrid); Government Partnerships Communications Lead (DC, hybrid); AI Support Engineer, Government — Washington, D.C.; GRC Program Manager, US Government Compliance (DC); Forward Deployed Security Engineer (DC). Confirmed on the Ashby board HTML.
- **Access:** public Ashby HTML + JSON.
- **Firecrawl:** `webfetch` JSON (best) or scrape the Ashby board.
- **Playwright:** Ashby apply.
- **Rate-limit / ToS:** public posting API.

### 29. Y Combinator Work at a Startup

- **Base:** https://www.workatastartup.com/jobs  
  Companies: https://www.workatastartup.com/companies  
  `{keywords}`: UI search (JS). `{location}` / `{remote}`: filters in the UI. `{radius}` N/A. No stable public query template was verified beyond `/jobs`.
- **Access:** public listing, account to apply. Complements Wellfound for early-stage.
- **Firecrawl:** `scrape` `/jobs` with wait; `search` `site:workatastartup.com {keywords}`.
- **Playwright:** apply.
- **Rate-limit / ToS:** YC ToS; personal search OK. Disabled by default unless the user wants startups.

### 30. SimplyHired (Indeed network)

- **Base:** https://www.simplyhired.com/  
  Template: `https://www.simplyhired.com/search?q={keywords}&l={location}`  
  Example in indexes: https://www.simplyhired.com/search?q=microsoft&l=reston%2C+va  
  Fetch from this environment hit Cloudflare. `{radius}` / `{remote}` similar to Indeed.
- **Access:** public HTML, bot-walled. Inventory overlaps Indeed.
- **Firecrawl / Playwright / ToS:** treat as Indeed-lite. **Disabled.** Do not waste crawl budget.

### Local extra (not a default board): Nextdoor

The attached neighborhood map is **Victory Lakes, Bristow, VA** (Victory Lakes Loop / Roaring Spring Loop / Devlin Rd), not Reston. Nextdoor is a neighborhood social graph with occasional gigs, not a job board with a stable search URL. Skip unless the user wants local classifieds; if so, Playwright with their Nextdoor login, no template.

---

## Search strategy

### Tool layers (use in this order)

1. **Official JSON / RSS / HTML that already works without a browser**  
   USAJOBS Search API, Greenhouse / Lever / Ashby job-board JSON, RemoteOK `/api`, WWR RSS, HN Algolia, Capital One TalentBrew HTML, Google Careers results HTML, LinkedIn **guest** SERP, Dice SERP, ClearanceJobs SERP, Built In DC listing, Wellfound location hub, Anthropic + OpenAI boards.  
   **Tool:** WebFetch / HTTP (`webfetch` in the seed table). Cheapest, most ToS-aligned, most parseable.

2. **Firecrawl `search`**  
   When you do **not** have a working URL, or you need cross-ATS discovery:  
   `{keywords} {location} (job OR careers)`  
   `site:job-boards.greenhouse.io {keywords} Reston OR "Washington, DC"`  
   `site:jobs.lever.co …` / `site:jobs.ashbyhq.com …` / `site:careers.leidos.com …`  
   Also the right way to use **Google Jobs** without scraping google.com.  
   **Do not** use `search` as a substitute for USAJOBS or ATS JSON.

3. **Firecrawl `scrape`**  
   Known listing URL, public HTML. Set `--wait-for` on Dice, Built In, LinkedIn guest, Amazon geo search, Google Careers. One listing page, then scrape **detail URLs** (cap e.g. 30/run). Good for JD text + apply URL + posted date.

4. **Firecrawl `agent` / extract**  
   SPA filters that `scrape` missed: Booz Allen keyword+state, Phenom (MITRE, Leidos), Eightfold (Microsoft, CACI), Built In keyword box, Wellfound role slugs if location hub is too broad. Schema-extract `{title, company, location, posted, apply_url, req_id, salary}` rather than dumping markdown.

5. **WebSearch / WebFetch (built-in)**  
   Enough for: this month’s HN thread id, “did Otta rebrand,” “does Google still have Reston,” a single company careers URL. Not enough for a 10-job ranked list.

6. **Playwright (logged-in persistent Chromium)**  
   Required for: Indeed, Glassdoor, ZipRecruiter, Microsoft/CACI Eightfold lists, Leidos/SAIC if Cloudflare, WTTJ/Otta, Easy Apply, Workday apply, USAJOBS login.gov apply.  
   Use the **same** user-data-dir on macOS and Linux (`$JOB_SEARCH_HOME/config/browser-profile`). Prefer Playwright’s bundled Chromium so Linux servers without Google Chrome still apply. First login needs a display (macOS GUI, Linux desktop, or one-time X11/VNC); later cron runs can be headless against that profile.  
   **Discovery** should not start here. **Apply** almost always ends here.

### Per-board construction from “AI based jobs in the Reston, VA area”

Parse the free text into:

| Field | Value for this example |
|---|---|
| `{keywords}` | Primary: `AI engineer`. Alternate queries (run 2–3, not 10): `"machine learning" OR LLM OR "platform engineer"`, `MLOps`, `"applied AI"` |
| `{location}` | `Reston, VA` on aggregators; `McLean, VA` on Capital One; `Herndon, VA` on Amazon; `Reston, VA, USA` on Google Careers; `Washington, DC` on Anthropic/OpenAI/Wellfound/Built In; `Reston, Virginia` on USAJOBS |
| `{radius}` | `25` miles first; `50` if yield < 10 after dedup |
| `{remote}` | Always run **local 25mi** and **remote-US** as two passes |

**Query plan (one run):**

1. LinkedIn guest Reston 25mi + `f_TPR=r604800` (past week).
2. Dice Reston 25mi.
3. ClearanceJobs Reston.
4. USAJOBS API `Keyword=machine learning` + `LocationName=Reston, Virginia` + `Radius=25`, and a second call `LocationName=Washington DC, District of Columbia`. Also `JobCategoryCode=2210`.
5. Built In `https://builtin.com/jobs/washington-dc` + keyword filter if possible.
6. Google Careers Reston `q=AI engineer`.
7. Capital One `k=AI engineer&l=McLean, VA`.
8. Amazon AWS Herndon geo search `base_query=AI`.
9. Firecrawl `search` across Greenhouse/Lever/Ashby as above.
10. Anthropic + OpenAI JSON, filter DC.
11. If `{remote}` not false: RemoteOK API + WWR RSS + HN current thread.
12. Company extras if still < 10 after fit filter: Booz Allen, MITRE, Leidos, Microsoft, CACI (Playwright).
13. Indeed/ZipRecruiter **only** if coverage is still thin — Playwright, 1 SERP each.

Skip WTTJ, Glassdoor, SimplyHired, Nextdoor unless the user asks.

### Dedup strategy

**Fingerprint (durable memory key):**

```python
import hashlib
fingerprint = hashlib.sha256(
    f"{company_norm}|{title_norm}|{loc_norm}|{req_id_or_empty}".encode("utf-8")
).hexdigest()
```

Do not call `shasum` (macOS) or `sha256sum` (Linux) from the shell; Python 3 stdlib is the portable hasher.

- `company_norm`: lowercase, strip `inc|llc|ltd|corp|corporation|the|group|co.`, map aliases (`booz allen hamilton` → `booz allen`, `amazon web services` → `amazon`, `google llc` → `google`, `capital one financial` → `capital one`).
- `title_norm`: lowercase, collapse whitespace, strip trailing `(R0…)` / requisition suffixes, keep seniority (`senior` ≠ `staff`) because they are different jobs.
- `loc_norm`: `city, ST` or `remote-us`. Map `washington, d.c.` / `district of columbia` / `washington dc` → `washington, dc`; `tysons` / `tysons corner` → `mclean, va` only for distance, **not** for fingerprint (keep Tysons distinct if the posting says Tysons).
- `req_id`: Greenhouse id, Ashby uuid, Workday req, Booz `R0246909`, USAJOBS `MatchedObjectId`, Dice uuid, LinkedIn numeric id. If present, **req_id + company** is sufficient even when title changes.

**Secondary match (aggregator duplicate):** same `company_norm` + `title_norm` + `loc_norm` with Jaccard(title tokens) ≥ 0.8, first seen within 90 days, even if req_id missing.

**Canonical apply URL (keep this one, drop the rest):**

1. Company ATS host: `job-boards.greenhouse.io`, `jobs.ashbyhq.com`, `jobs.lever.co`, `*.myworkdayjobs.com`, `amazon.jobs/…/jobs/`, `careers.microsoft.com` / `apply.careers.microsoft.com`, `google.com/about/careers/…`, `capitalonecareers.com/job/`, `usajobs.gov/GetJob/ViewDetails/`.
2. Else first-party careers path on the employer domain.
3. Else LinkedIn `/jobs/view/{id}` (strip `refId`, `trackingId`, `position`, `pageNum`).
4. Else Dice `/job-detail/{uuid}`.
5. Else Indeed/Glassdoor/ZipRecruiter (last resort).

Strip tracking: `utm_*`, `gh_src`, `lever-source`, `ashby_jid` duplicates, LinkedIn `refId`/`trackingId`, Indeed `vjk` keep (that's the job key) but drop `from`/`alid`.

**Memory fields (matches CONTEXT.md):** fingerprint, first_seen, last_seen, status (`new` / `shown` / `not_interested` / `applied` / `cooldown`), canonical_url, source_urls[], posted_at, expires_at. 14-day cooldown for un-actioned jobs is a **display** rule, not a crawl rule — still refresh `last_seen` and expired flags in the background.

---

## Seed config file

Draft of `config/job-board-links.md`. The skill should parse the markdown table (pipe-separated). `{remote}` substitution: if the template has no remote slot, run a second row or drop the param. **Enabled = default-on for a Reston AI search.** Ten boards on; everything else is inventory the user can flip.

```markdown
# config/job-board-links.md
# Placeholders: {keywords} {location} {radius} {remote}
# Method: firecrawl | webfetch | playwright
# Enabled: default crawl set for Reston-area AI/ML/platform searches (2026-08-19)

| Board | Search URL template | Method | Login required | Enabled | Notes |
|---|---|---|---|---|---|
| LinkedIn | https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&distance={radius}&f_TPR=r604800&sortBy=DD | firecrawl | no (guest); yes to apply | true | Guest SERP verified. If {remote}=true append &f_WT=2. Do not use logged-in scrape. Detail: https://www.linkedin.com/jobs/view/{id} |
| Dice | https://www.dice.com/jobs?q={keywords}&location={location}&radius={radius}&radiusUnit=mi | firecrawl | no; yes for Easy Apply | true | Verified Reston SERP. Strong NoVA tech/contract. Scrape /job-detail/{uuid} for JD. |
| USAJOBS | https://data.usajobs.gov/api/search?Keyword={keywords}&LocationName={location}&Radius={radius}&ResultsPerPage=50&HiringPath=public&DatePosted=14 | webfetch | no (API key); yes to apply | true | Headers: Host=data.usajobs.gov, User-Agent=email, Authorization-Key=key. If {remote}=true add RemoteIndicator=true. Also search LocationName=Washington DC, District of Columbia. Cap 10k rows/query. |
| ClearanceJobs | https://www.clearancejobs.com/jobs?keywords={keywords}&location={location} | firecrawl | no; yes to apply | true | Verified. Radius unsupported. Essential for TS/SCI AI. |
| Built In DC | https://builtin.com/jobs/washington-dc | firecrawl | no; yes for Easy Apply | true | Metro hub not city radius. If {remote}=true use https://builtin.com/jobs/remote/washington-dc . Keyword box is JS; Firecrawl search site:builtin.com/job as backup. |
| Google Careers | https://www.google.com/about/careers/applications/jobs/results/?q={keywords}&location=Reston,%20VA,%20USA | firecrawl | no; yes to apply | true | Reston office is real. 59 AI-engineer matches on 2026-08-19. Ignore {location}/{radius} for this row (office-scoped). |
| Capital One | https://www.capitalonecareers.com/search-jobs?k={keywords}&l={location} | firecrawl | no; yes (Workday) to apply | true | Use location=McLean, VA not Reston. Posted dates on cards. |
| Amazon AWS Herndon | https://www.amazon.jobs/en/search?base_query={keywords}&loc_query=Herndon%2C%20VA%2C%20United%20States&latitude=38.96969&longitude=-77.38555&radius=40km&distanceType=Mi&city=Herndon&country=USA&region=Virginia&county=Fairfax&business_category[]=amazon-web-services | firecrawl | no; yes to apply | true | Full geo params required. radius param is km (~25mi). |
| ATS public boards | site:job-boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com {keywords} (Reston OR Herndon OR McLean OR Arlington OR "Washington, DC") | firecrawl | no | true | Discovery via Firecrawl search; hydrate with webfetch JSON: https://boards-api.greenhouse.io/v1/boards/{company}/jobs?content=true ; https://api.lever.co/v0/postings/{company}?mode=json ; https://api.ashbyhq.com/posting-api/job-board/{company}?includeCompensation=true . Maintain company token allowlist. |
| HN Who's Hiring | https://hn.algolia.com/api/v1/search_by_date?query=Ask%20HN%3A%20Who%20is%20hiring&tags=story,author_whoishiring | webfetch | no | true | Resolve current month thread; filter comments for {keywords} and REMOTE/DC/VA. Aug 2026: https://news.ycombinator.com/item?id=49156683 |
| RemoteOK | https://remoteok.com/api | webfetch | no | false | Enable when query is remote-first. Filter JSON client-side. HTML tag pages are thin. |
| We Work Remotely | https://weworkremotely.com/remote-jobs/search?term={keywords} | webfetch | no | false | Prefer RSS https://weworkremotely.com/remote-jobs.rss (attribute). Enable with RemoteOK. |
| Wellfound | https://wellfound.com/location/district-of-columbia | firecrawl | no; yes to apply | false | /jobs?q= does not filter. Use location slug or /role/l/{role}/district-of-columbia. |
| Indeed | https://www.indeed.com/jobs?q={keywords}&l={location}&radius={radius}&fromage=7&sort=date | playwright | no; yes for apply | false | Akamai wall. Coverage backfill only. If {remote}=true set l=Remote. |
| Glassdoor | https://www.glassdoor.com/Job/jobs.htm?sc.keyword={keywords}&locKeyword={location}&radius={radius} | playwright | often | false | Overlaps Indeed. Reston IC1130404. |
| ZipRecruiter | https://www.ziprecruiter.com/Jobs/{keywords}/-in-Reston,VA | playwright | no; yes for 1-click | false | Cloudflare. Slug form is what indexes; jobs-search query is challenged. |
| WTTJ / Otta | https://www.welcometothejungle.com/en/jobs?query={keywords} | playwright | yes | false | Otta rebrand. US app is preference-gated. |
| Microsoft Reston | https://apply.careers.microsoft.com/careers?query={keywords}&location=United+States%2C+Virginia&hl=en | playwright | no to browse; yes to apply | false | Eightfold SPA. DC metro page: https://careers.microsoft.com/professionals/us/en/l-dcmetro |
| Booz Allen | https://careers.boozallen.com/jobs/search?q={keywords} | playwright | no; yes to apply | false | Keyword facet flaky on scrape. Workday: https://bah.wd1.myworkdayjobs.com/BAH_Jobs?q={keywords} |
| Leidos | https://careers.leidos.com/search/jobs?q={keywords}&location={location} | playwright | no; yes to apply | false | HQ Reston. Cloudflare from datacenter. Firecrawl search site:careers.leidos.com as discovery. |
| CACI | https://searchcareers.caci.com/careers?query={keywords}&location={location} | playwright | no; yes to apply | false | Eightfold. Default radius 80km. Clearance facet. |
| SAIC | https://jobs.saic.com/search/jobs?q={keywords}&location={location} | playwright | no; yes to apply | false | HQ 12010 Sunset Hills Rd, Reston. Reston slice: /search/jobs/in/reston |
| MITRE | https://careers.mitre.org/us/en/search-results?keywords={keywords} | playwright | no; yes to apply | false | Phenom SPA. McLean HQ. Citizenship/clearance common. |
| Anthropic | https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true | webfetch | no; yes to apply | false | Filter JSON location contains Washington, DC. HTML: https://www.anthropic.com/careers/jobs |
| OpenAI | https://api.ashbyhq.com/posting-api/job-board/openai?includeCompensation=true | webfetch | no; yes to apply | false | Filter JSON location Washington, DC. HTML: https://jobs.ashbyhq.com/openai |
| YC Work at a Startup | https://www.workatastartup.com/jobs | firecrawl | no; yes to apply | false | Startup-only. Enable if user asks for startups. |
| SimplyHired | https://www.simplyhired.com/search?q={keywords}&l={location} | playwright | no | false | Indeed network. Cloudflare. Skip. |
| Google Jobs | https://www.google.com/search?q={keywords}+jobs+{location}&udm=8 | firecrawl | no | false | Do not scrape google.com HTML. If enabled, use Firecrawl search, not this URL, then canonicalize off-Google. |
```

Parser notes for the skill: skip heading lines; split on `|`; treat `true`/`false` case-insensitively; leave `{remote}` empty unless the user asked for remote-only; URL-encode after substitution **in Python 3** (`urllib.parse.quote`); for the ATS row, run Firecrawl `search` then JSON hydrate. Do not parse this table with `sed`/`awk` — GNU vs BSD flag differences will break on macOS. Resolve `$JOB_SEARCH_HOME` (default `$HOME/development/random/job-search`) the same way on both OSes; the relative path `config/job-board-links.md` lives under that home.

---

## Freshness & dedup

### Posted date

| Source | Where the date lives | Reliability |
|---|---|---|
| USAJOBS | `PublicationStartDate`, `PositionStartDate` (ISO) | High |
| Capital One | card text `08/18/2026` | High |
| Greenhouse JSON | `updated_at` / `absolute_url` page | High (updated ≠ first posted) |
| Ashby JSON | `publishedAt` when present | High |
| Lever JSON | `createdAt` epoch ms | High |
| LinkedIn guest | relative (“4 hours ago”, “3 months ago”) | Medium; parse to an estimated date, store `date_precision=relative` |
| Dice | “Today”, “13d ago” | Medium |
| ClearanceJobs | “Posted yesterday”, “2 months ago” | Medium |
| Built In | “7 Hours Ago”, **“Reposted 7 Hours Ago”** | Medium; **Reposted** is a first-class freshness signal |
| RemoteOK API | unix `epoch` | High |
| WWR | “2d”, “New” | Medium |
| HN | comment `created_at` (Algolia) | High for the comment; the job may be older |
| Google Careers | often no date on the card | Low — use first_seen |
| Amazon | “Posted August 14, 2026” on cards when JS renders | Medium |
| Indeed/Glassdoor | `fromage` filter + relative | Medium; lots of recycled ages |

If no date: set `posted_at=null`, `first_seen=now`, and do not pretend it is new. Rank recency below fit when `date_precision` is null.

### Expired postings

Drop or mark `status=expired` when any of:

- HTTP 404 / 410 on the **canonical apply URL**.
- Page text matches `/no longer (accepting|available)|this job has expired|position (has been )?filled|requisition closed/i`.
- USAJOBS `ApplicationCloseDate` < now (the HTML may still be up).
- Greenhouse/Ashby/Lever JSON no longer contains that id on the next board pull (keep for 7 days as `missing`, then expire).
- Indeed “This job has expired” interstitial.

Do **not** expire solely because LinkedIn says “3 months ago”; defense contractors leave reqs open. Re-check canonical URL before hiding.

### Reposts

A **repost** is the same fingerprint with a new `posted_at` after a gap, or Built In/Indeed explicitly labeling “Reposted.”

- Keep one memory row; set `repost_count += 1`, `last_posted_at=new`, `last_seen=now`.
- If the user marked `not_interested`, **stay suppressed** (CONTEXT.md pattern memory). A repost is not a new job.
- If status is `cooldown` (shown, un-actioned, 14 days), a genuine new req_id with a similar title **is** a new job; a repost of the same req_id is not.
- LinkedIn “relisted” jobs often change the numeric id. Prefer company+title+loc over LinkedIn id when an ATS canonical URL exists.

### Aggregator duplicates (Indeed + LinkedIn + company)

Same opening commonly appears on: company ATS, LinkedIn, Indeed, Dice, Glassdoor, ZipRecruiter, Google Jobs, Built In.

**Winner = canonical apply URL** (priority list in Search strategy). Store `source_urls[]` for provenance but show one card.

**Req id wins:** Booz `R0246909` on ClearanceJobs and Dice is one job. Capital One SmashFly id `99414812720` on Capital One and Dice is one job.

**Do not merge** across seniority (`AI Engineer` vs `Lead AI Engineer` vs `Distinguished AI Engineer` at Capital One are separate, all live in McLean today) or across offices (Reston vs NYC listings of the same title).

**Staffing-firm clones:** Dice/ClearanceJobs will list “AI Engineer, Reston” from Hexaware / SGS / Insight Global that are vendor reqs against a hidden end client. Fingerprint includes the **vendor company** (that is who you apply to). Optionally cluster `title_norm + loc_norm` without company as `maybe_same_req` for the report, but do not auto-drop — applying to two vendors for the same end client is sometimes rational.

### What to show the user

After crawl → fingerprint merge → drop expired → apply not-interested patterns → apply 14-day cooldown → resume-fit score → keep ≥10. In the report, print **canonical apply URL**, sources merged, posted/repost date, and clearance if any. Write `reports/YYYY-MM-DD.md` with `datetime.date.today().isoformat()` (Python), not `date +%Y-%m-%d` vs GNU `date`.

---

## Cross-platform notes

The board URLs, JSON APIs, RSS feeds, and Firecrawl/WebFetch recipes above are OS-agnostic. Everything that touches a **browser, PDF, filesystem, or scheduler** must work on macOS *and* Linux (Debian/Ubuntu/Fedora-class, including headless cron containers). Prefer **Python 3 stdlib** helpers over bash.

### Data home and skill code

| What | Portable default |
|---|---|
| Data home | `$JOB_SEARCH_HOME` if set, else `$HOME/development/random/job-search` (`resume/`, `config/`, `memory/`, `reports/`, `applications/`) |
| Skill code | `$HOME/.claude/skills/job-search/` |
| Browser profile | `$JOB_SEARCH_HOME/config/browser-profile/` (Playwright `user_data_dir`, both OSes) |
| Board table | `$JOB_SEARCH_HOME/config/job-board-links.md` |

`$HOME` expands correctly under bash and zsh. Never hard-code `/Users/...` or `/home/...`. Create the tree with `pathlib.Path.mkdir(parents=True, exist_ok=True)`.

### Chrome / Chromium discovery (for Playwright MCP, HTML-print PDFs, and apply)

Resolve in this order; first executable that exists wins. Same logic on both OSes:

1. `PLAYWRIGHT_CHROMIUM` env override, if set.
2. Playwright bundled Chromium from `npx playwright install chromium` (this is the **default on Linux servers** and the fallback on macOS).
3. System browser:
   - **macOS:** `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, then `/Applications/Chromium.app/Contents/MacOS/Chromium`.
   - **Linux:** `google-chrome`, `google-chrome-stable`, `chromium-browser`, `chromium` on `PATH`.
4. If none found: print the install commands below and stop. Do not assume Chrome is at the macOS app-bundle path on Linux.

Headless print (tailored resume/cover PDF) should use Playwright `page.pdf()` against bundled Chromium so it does not depend on a system Chrome. If a raw Chrome CLI is required:

```text
chrome --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=out.pdf file:///abs/path/to/resume.html
```

On Linux containers add `--no-sandbox` only when running as root (not the default).

### Playwright install

```text
# both OSes (user-space browsers)
npx playwright install chromium

# Linux (Debian/Ubuntu/Fedora) — also install OS libraries (fonts, nss, atk, etc.)
npx playwright install --with-deps chromium
```

`@playwright/mcp` should launch with `userDataDir=$JOB_SEARCH_HOME/config/browser-profile` and `channel` unset (bundled Chromium) unless the user explicitly wants system Chrome. **Headless Linux cron:** `headless=true` after the profile has cookies. **First login** (Indeed, Workday, USAJOBS login.gov, LinkedIn Easy Apply): needs a display — macOS Aqua, Linux desktop, or a one-shot `ssh -X` / VNC / `xvfb-run` session. `xvfb-run` is Linux-only (`sudo apt-get install -y xvfb` / `sudo dnf install -y xorg-x11-server-Xvfb`); macOS does not need Xvfb.

### pdftotext / poppler (resume PDF ingest)

The skill reads `./resume/` PDFs. pandoc has no PDF engine; use poppler `pdftotext` **or** Python (`pypdf` / already-available reportlab is write-only). Install:

```text
# macOS (Homebrew)
brew install poppler

# Debian / Ubuntu
sudo apt-get update && sudo apt-get install -y poppler-utils

# Fedora
sudo dnf install -y poppler-utils
```

Call `pdftotext -layout "$pdf" -` (stdout). That flag is the same on both poppler builds. If `pdftotext` is missing, fall back to a Python extractor rather than `strings`.

### Fonts for PDF rendering on minimal Linux

macOS already has Arial/Helvetica/Times. Debian/Fedora containers often do not, so Playwright `page.pdf()` and reportlab output come out as boxes.

```text
# Debian / Ubuntu
sudo apt-get install -y fonts-liberation fonts-dejavu-core fonts-noto-core fontconfig
fc-cache -f

# Fedora
sudo dnf install -y liberation-fonts dejavu-sans-fonts google-noto-sans-fonts fontconfig
fc-cache -f
```

HTML print CSS should use a portable stack: `"Liberation Sans", "DejaVu Sans", "Noto Sans", Arial, Helvetica, sans-serif`. Do not reference `/System/Library/Fonts/` or macOS-only family names.

### Scheduler (headless cron on both; plus the native timer)

Interactive: `/job-search …`. Headless: `claude -p "…"` from the data home. Schedule the **same** wrapper (Python or a POSIX `sh` script, not zsh-only).

**cron (macOS and Linux):**

```cron
# every weekday 07:00 local — crontab -e
0 7 * * 1-5 cd "$HOME/development/random/job-search" && claude -p "/job-search AI jobs in Reston, VA" >> reports/cron.log 2>&1
```

Use `#!/bin/sh` in the wrapper. Set `HOME`, `PATH` (`$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin` plus nvm/fnm if the user has them), `JOB_SEARCH_HOME`, and `PLAYWRIGHT_BROWSERS_PATH` if browsers are not in the default cache.

**macOS launchd** extra (`~/Library/LaunchAgents/com.user.job-search.plist`): `StartCalendarInterval` weekdays 07:00, `WorkingDirectory` = data home, `StandardOutPath`/`StandardErrorPath` under `reports/`. `launchctl load` / `bootout` as the user (not root).

**Linux systemd user timer** extra (`~/.config/systemd/user/job-search.service` + `job-search.timer`): `OnCalendar=Mon..Fri 07:00`, `WorkingDirectory` = data home. Enable with `systemctl --user enable --now job-search.timer`. Lingering: `loginctl enable-linger $USER` so it fires without a GUI login — required on headless servers.

Do not put launchd XML on Linux or systemd units on macOS. Detect with Python `sys.platform` (`darwin` vs `linux`).

### Shell differences (avoid them)

| Pitfall | macOS (BSD) | Linux (GNU) | Portable replacement |
|---|---|---|---|
| `sed -i` | `sed -i '' 's/a/b/' f` | `sed -i 's/a/b/' f` | Python `pathlib` rewrite |
| `date` 14 days ago | `date -v-14d +%Y-%m-%d` | `date -d '14 days ago' +%Y-%m-%d` | `datetime.date.today() - timedelta(days=14)` |
| SHA-256 | `shasum -a 256` | `sha256sum` | `hashlib.sha256` |
| URL encode | python or python3 | python3 | `urllib.parse.quote` |
| Default interactive shell | zsh | bash | helper scripts `#!/usr/bin/env python3` |
| Timeout a crawl | `gtimeout` (coreutils) | `timeout` | Python `signal` / Playwright timeouts |
| Open a PDF | `open f.pdf` | `xdg-open f.pdf` | not needed in headless runs |

Firecrawl CLI, `npx`, `node`, and `python3` are the same commands on both OSes once on `PATH`. Pin `python3` not `python`.

### Headless-server implications for *this* board list

- **Enabled-by-default boards** (`webfetch` / `firecrawl`) need no display: USAJOBS, RemoteOK API, WWR RSS, HN Algolia, ATS JSON, LinkedIn guest, Dice, ClearanceJobs, Built In, Google Careers, Capital One, Amazon search.
- **Playwright boards** (Indeed, Glassdoor, ZipRecruiter, Eightfold Microsoft/CACI, Phenom MITRE/Leidos, SAIC, WTTJ) fail on a fresh container until Chromium + `--with-deps` + fonts are installed. Keep them `Enabled=false` unless the host has a profile.
- Cloudflare/Akamai walls are identical on both OSes; datacenter Linux IPs are *more* likely to see the challenge than a residential macOS laptop. That is an IP issue, not a path issue.
- Persistent cookies in `config/browser-profile` are portable **if** Chromium versions stay close; do not copy a macOS Chrome profile directory onto Linux Chrome and expect it to work. Create the profile with Playwright on the machine that will apply.

---

## Confidence

- **LinkedIn guest SERP + parameters (`keywords`, `location`, `distance`, `f_WT`, `f_TPR`):** high — live Reston search on 2026-08-19; ToS scrape ban: high (https://www.linkedin.com/legal/user-agreement).
- **Dice Reston URL + scrapeability:** high — live 1,694-result SERP.
- **ClearanceJobs search URL:** high — live SERP with Reston TS/SCI cards.
- **USAJOBS API shape, headers, 10k/500 limits, RemoteIndicator, Radius:** high — https://developer.usajobs.gov/api-reference/get-api-search and https://developer.usajobs.gov/guides/rate-limiting. HTML keyword search for “artificial intelligence” in Reston: high that it is the wrong interface (zero hits).
- **Built In DC listing page:** high — live cards including “Reposted”.
- **Capital One `search-jobs?k=&l=`:** high — 796 results, dated cards including 2026-08-18.
- **Google Careers Reston office + search URL:** high — location page + 59-job SERP. Google Jobs `udm=8` HTML scrape: low (interstitial); use Firecrawl search instead.
- **Amazon Herndon geo search:** medium-high — indexed live SERP with full lat/long; a reduced query without geo fields returned empty chrome.
- **Microsoft Reston presence:** high (https://careers.microsoft.com/professionals/us/en/l-dcmetro). Microsoft Eightfold listing scrape without Playwright: low.
- **CACI Eightfold `query`+`location`:** high that the URL is right (“Ai jobs in Reston, Va”); low that Firecrawl `scrape` alone yields cards.
- **Leidos / SAIC / MITRE HTML templates:** medium (official domains and HQ Reston/McLean confirmed; datacenter Cloudflare/Phenom shells). Playwright likely required.
- **Booz Allen search URL:** medium — page is real; keyword filter did not clearly apply on scrape.
- **Greenhouse / Lever / Ashby public JSON:** high — vendor docs still current in 2026 (Greenhouse Job Board API, Ashby posting API, Lever v0 postings).
- **Anthropic DC hiring:** high — `/careers/jobs` lists DC on multiple reqs including public-sector architecture and Staff+ Public Sector engineering. Not a Reston office.
- **OpenAI DC hiring:** high — Ashby board lists multiple Washington, DC hybrid gov roles.
- **Otta → Welcome to the Jungle:** high — US site and App Store still say formerly Otta. Public search quality for Reston: low (login/preferences).
- **Wellfound location hub:** high for `/location/district-of-columbia`; high that `/jobs?q=` does not filter.
- **RemoteOK API + WWR RSS:** high (footer/API and official RSS page). RemoteOK HTML tag tables: low information density.
- **HN August 2026 thread id 49156683:** high.
- **Indeed / ZipRecruiter / SimplyHired / Glassdoor as Playwright-only:** high bot-wall from this environment (Security Check / Just a moment…). Exact Indeed ToS clause not re-fetched; treat as prohibited automation.
- **Default-on set of 10:** medium-high judgment call (covers guest aggregators + federal API + cleared + DC tech hub + Google/Capital One/AWS + ATS discovery + HN). Indeed omitted on purpose because of the wall.
- **Nextdoor / Victory Lakes:** high that it is Bristow, VA, not a job board.
- **Cross-platform paths/commands (Chrome vs Chromium, poppler packages, Playwright `--with-deps`, cron/launchd/systemd, BSD vs GNU `sed`/`date`):** high for the dual recipes; medium that every Linux distro names the Chromium package identically (`chromium` vs `chromium-browser`) — discovery walks PATH plus both names.
