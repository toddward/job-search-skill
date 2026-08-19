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
