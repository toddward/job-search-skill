# ATS and auto-apply mechanics

Research verified 2026-08-19. URL templates below use braces for values extracted from a real job URL; they are interface notation, not missing research. “Public posting API” means a supported way to read published jobs. It does **not** imply that an applicant may submit through that API: most application-create endpoints require an employer credential, and the skill must never possess one.

## ATS landscape

### Detection order

Detection should run after redirects and should inspect every frame, because a branded company page often embeds the real ATS form. Use this order and retain all matching evidence in `platform_detection`:

1. Match the final URL and iframe `src` hosts/paths against the high-confidence patterns below.
2. Match vendor-owned form actions, script/resource hosts, stable field names, and vendor footer text. Do not classify on a generic word such as “greenhouse” in the job description.
3. Probe the documented posting endpoint only when the URL exposes the required tenant/board token. A successful response whose job ID/title agrees with the page raises confidence; a 401/403 does not disprove the platform.
4. Otherwise classify `company_custom`, record the page’s `application/ld+json` `JobPosting`, form action, iframe hosts, and relevant XHR URLs. Never guess an adapter at low confidence.

### Recognition, form, and posting API matrix

| Platform | High-confidence URL / DOM recognition | Typical candidate form | Posting JSON/API and example |
|---|---|---|---|
| **Greenhouse** | `job-boards.greenhouse.io/{board}/jobs/{job_id}`, legacy `boards.greenhouse.io/{board}/jobs/{job_id}`, or an iframe/resource from those hosts. Common legacy signals include `#application_form`, `job_application[...]` input names, and “Powered by Greenhouse.” Custom company careers pages can still send “Apply” to Greenhouse. | Usually one long page: first/last name, email, phone, location, résumé/cover-letter file inputs, employer-defined questions, consent, then optional EEO/demographic blocks. The employer controls which questions and compliance blocks appear. Final action is normally **Submit Application**. | Supported unauthenticated reads: `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true`; `questions=true` returns custom, location, compliance, and demographic question definitions. Application `POST` exists but requires the employer’s secret Job Board API key, so it is **not** an applicant route. See [Greenhouse Job Board API](https://developer.greenhouse.io/job-board.html). |
| **Lever** | `jobs.lever.co/{site}/{posting_uuid}` or EU `jobs.eu.lever.co`; application URL normally ends in `/apply`. DOM/resources commonly include `lever`, `.application-form`, and inputs named `name`, `email`, `phone`, `resume`. | Normally a single page: full name, email, phone, current company, résumé, links, free-form additional information, consent, and configurable questions. Diversity/EEO may be a separate optional section or follow-up. Final action is **Submit application**. | Public read: `GET https://api.lever.co/v0/postings/{site}/{posting_uuid}` or list `.../{site}?mode=json`; response includes `hostedUrl` and `applyUrl`. The documented application `POST .../{posting_uuid}?key=APIKEY` requires an employer-generated key and is rate-limited. Lever also warns that the API does not expose custom application questions, making browser inspection necessary. See [Lever Postings API](https://github.com/lever/postings-api). |
| **Ashby** | `jobs.ashbyhq.com/{job_board_name}/{posting_uuid}` and an apply URL containing `/application` or `/apply`; Ashby script/resource hosts and the board footer corroborate. | Typically a compact application view with résumé parsing, name, email, phone/location, links, employer questions, and optional surveys. It may expose sections progressively after résumé parsing. Final action is usually **Submit Application**. | Public board read: `GET https://api.ashbyhq.com/posting-api/job-board/{job_board_name}?includeCompensation=true`; records include description, `publishedAt`, `jobUrl`, and `applyUrl`. The public API documents postings, not applicant submission. See [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api). |
| **Workable** | `apply.workable.com/{account}/j/{shortcode}`, `{account}.workable.com/jobs/...`, or an application route ending `/candidates/new`; assets/footer identify Workable when the company uses a custom domain. | Commonly a short staged flow or one page: résumé import/upload, first/last name, email, phone/address, profile fields, cover letter, custom paragraph/multiple-choice questions, and optional candidate survey. Résumés accept PDF and common document formats, currently up to 5 MB. Final action is **Submit application** or **Submit**. | Supported public reads include `GET https://www.workable.com/api/accounts/{account}?details=true`; employer-authenticated SPI is `GET https://{account}.workable.com/spi/v3/jobs/{shortcode}`. Creating a candidate requires employer `w_candidates` scope. See [Workable careers API guidance](https://help.workable.com/hc/en-us/articles/115012771647-Using-the-Workable-API-to-create-a-careers-page) and [upload limits](https://help.workable.com/hc/en-us/articles/115012238108-What-types-of-files-can-be-uploaded-on-the-application-form). |
| **SmartRecruiters** | `jobs.smartrecruiters.com/{company}/{posting_id}-{slug}`, `careers.smartrecruiters.com/{company}`, or an apply flow/resource on a SmartRecruiters host. Confirm with stable footer/resource origins. | Usually a multi-screen candidate flow: résumé/profile import, contact information and location, experience, employer questionnaire, privacy/consents, review, and optional diversity data. Some tenants require sign-in/email verification. Final action is **Submit application**. | Posting endpoint: `GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings/{postingId}` and list `.../postings`. Official documentation calls it the Posting API and states API-key authentication; probe without credentials, handle 401/403, and never invent a token. See [Posting API overview](https://developers.smartrecruiters.com/docs/posting-api) and [endpoints](https://developers.smartrecruiters.com/docs/endpoints). |
| **Workday** | Host commonly matches `{tenant}.wd{number}.myworkdayjobs.com` or `{tenant}.myworkdayjobs.com`; job paths contain `/{career_site}/job/{location}/{slug}_{requisition}`. Strong DOM signal: many `data-automation-id` attributes and Workday resource/XHR paths containing `/wday/cxs/`. Branded sites often redirect into this host. | Long multi-step wizard, often account/email-verification first: My Information, My Experience (work/education/languages/websites and résumé), Application Questions, Voluntary Disclosures, Self Identify, and Review. Resume parsing can populate repeated work/education entries. Final control on the last stage is normally **Submit**; intermediate controls often use `data-automation-id="bottom-navigation-next-button"`. | No single supported, cross-tenant, anonymous public jobs API is documented. The browser client commonly calls tenant-specific `/wday/cxs/{tenant}/{career_site}/jobs` and job-detail routes. Treat those routes as undocumented web backends whose contract may change. Workday documents configurable external career sites and sections in [Create External Career Sites](https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/career-sites/san1394588983205.html) and [Quick Apply/resume parsing](https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/career-sites/san1431625385171.html). |
| **iCIMS** | `*.icims.com/jobs/{job_id}/{slug}/job`, `jobs-*.icims.com`, or legacy query URLs such as `/jobs/intro?mode=job`; embedded portals often expose an iCIMS iframe/container and scripts from iCIMS hosts. | Tenant-configurable single- or multi-page portal: résumé upload/import, contact/address, work/education, source/referral, profile questions, acknowledgments, and optional EEO. Account creation or email validation is common. Final labels include **Submit Application**, **Submit Profile**, or **Finish**. | A supported Job Portal API exists, for example `GET https://api.icims.com/customers/{customerId}/search/portals/{portal}` and `.../portalposts/job/{jobId}`, but official examples require Basic authentication; it is not a universal anonymous feed. See [iCIMS Job Portal API](https://developer-community.icims.com/applications/applicant-tracking/job-portal). |
| **Oracle Taleo Enterprise** | `*.taleo.net/careersection/{section}/jobdetail.ftl?job={requisition}`; apply path is `jobapply.ftl`. The `.ftl`, `/careersection/`, `lang`, and `job` parameters together are highly distinctive. | A configurable page sequence, commonly login/account, résumé upload, personal information, education, work experience, screening, e-signature/privacy, diversity, and Review and Submit. Oracle recommends fewer than seven pages, but older tenants can be longer. The final page is **Review and Submit** and then a Thank You page. See Oracle’s [application-flow example](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/25b/otcug/c-optimizedjobapplicationflow.html). | Taleo customer APIs/RSS integrations exist but require customer configuration/credentials; there is no dependable anonymous JSON endpoint across Enterprise tenants. The URL contract is documented, including `https://abc.taleo.net/careersection/5/jobdetail.ftl?lang=en&job=51380`: [Career Section URL](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/22c/otcug/c-careersectionurl.html). |
| **LinkedIn Easy Apply** | Final job URL `linkedin.com/jobs/view/{job_id}` plus an authenticated button whose accessible name is **Easy Apply**. Clicking opens a modal/dialog; use role/name and dialog heading, not rapidly changing CSS classes. A plain **Apply** button means the flow leaves LinkedIn and must be re-detected at the destination. | Authenticated multi-screen modal: contact info, résumé selection/upload, employer screening questions, optional demographic questions, Review, then **Submit application**. LinkedIn’s own instructions explicitly separate Review and Submit. | No public job-seeker posting/submission JSON API. Treat Easy Apply as **manual-only**: LinkedIn says third-party software that automates activity on its website is prohibited. See [application steps](https://www.linkedin.com/help/linkedin/answer/a512388/applying-for-jobs-on-linkedin?lang=en) and [prohibited software](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en). |
| **Indeed Apply** | Job URL often `indeed.com/viewjob?jk={job_key}`; direct application stays in an Indeed dialog or moves to an `apply.indeed.com`/Indeed Apply route. Confirm with an Indeed-owned form/dialog and text such as **Apply now**; an employer-site redirect must be re-detected. | Authenticated or email-verified staged flow: contact, résumé, employer questions, review, and **Submit your application**/**Submit application**. Some postings redirect to the employer ATS rather than using Indeed Apply. | No public applicant API for this use. Partner products exist, but Indeed’s current terms prohibit automation, scripting, or bots that automate Indeed Apply outside official vendors/tooling. Treat as **manual-only**. See [Indeed Terms of Service](https://www.indeed.com/legal?hl=en_US) and [candidate application help](https://support.indeed.com/hc/en-us/articles/204652920-Applying-for-a-Job-on-Indeed). |
| **BambooHR** | Current hosted pages commonly use `{company}.bamboohr.com/careers/{job_id}`; legacy pages may use `/jobs/view.php?id={id}`. Confirm with BambooHR assets/footer and application form action because company subdomains can proxy or redirect elsewhere. | Usually a single page or short flow: résumé, first/last name, email, phone/address, employer questions, cover letter, and acknowledgments; links, authorization, and EEO are tenant-defined custom fields. Final label commonly contains **Submit Application** or **Apply for this Job**. | `GET https://{companyDomain}.bamboohr.com/api/v1/applicant_tracking/jobs` is supported but requires an authenticated caller with ATS access; it is not a public candidate feed. See [Get Job Summaries](https://documentation.bamboohr.com/reference/get-job-summaries) and [API authentication](https://documentation.bamboohr.com/docs/getting-started). |
| **JazzHR** | Hosted candidate URLs use `{company}.applytojob.com/apply/{job_key}/{slug}` (and `/apply/jobs/` listings); legacy resources/API use the Resumator name. Page title/footer often says **JazzHR » Job Listings**. | Usually one long page: first name, last name, email address, location broken into address/city/state/postal, phone, résumé attachment or pasted résumé, then custom text/select/checkbox questions. Final action is **Submit Application**. A live example shows these exact labels and a 5 MB résumé limit: [JazzHR-hosted application](https://ansiblegovernmentsolutions.applytojob.com/apply/jobs/details/sf1nmwvtF9). | JazzHR has an authenticated API at `https://www.resumatorapi.com/v1/...`; the API key comes from an employer’s Integrations settings, so it is not an anonymous posting contract. See [JazzHR API](https://www.resumatorapi.com/) and [careers-page integration options](https://www.jazzhr.com/onboarding/careers-page). |
| **Rippling Recruiting** | `ats.rippling.com/{job_board_slug}/jobs/{job_uuid}`; application path ends `/apply` and includes `jobBoardSlug`, `jobId`, and often `step=application`. Text such as **Exit to job board** plus Rippling-owned assets corroborates. | Current forms use a compact page: Résumé, First name, Last name, Email, Pronouns, Current company, Phone number, Location, LinkedIn Link, Cover letter, employer questions/consent; résumé parsing may add fields. The final control can read **Apply**, so distinguish it from the earlier **Apply now** navigation link. See a [live Rippling application form](https://ats.rippling.com/rippling/jobs/17ac34d3-704d-4115-9de0-77e409e68069/apply?jobBoardSlug=rippling&jobId=17ac34d3-704d-4115-9de0-77e409e68069&step=application). | No supported anonymous public job-board JSON API was found in Rippling’s public developer material as of the research date. Read the rendered board/job page or its runtime network responses, treating any private XHR as unstable. Example public board: `https://ats.rippling.com/amopportunities/jobs`. |
| **Company-custom form** | Company domain remains final; inspect `form[action]`, iframes, scripts, XHR, JSON-LD `JobPosting`, headings, and accessible labels. Re-run detection after every Apply redirect. A custom shell around a known ATS should be classified by the application destination, not the shell. | Unknown until inspected. Could be a single native form, a multi-step SPA, email link, third-party assessment, or an embedded ATS. Resume may be a normal `input[type=file]`, a drag/drop control, or absent. EEO may be absent or independently hosted. | No generic API. Prefer a documented company jobs feed or `application/ld+json`; otherwise scrape the public posting with the layered search strategy. Runtime XHR is evidence, not a stable contract, unless the company documents it. |

### Adapter recognition contract

Each adapter should return:

```yaml
platform: greenhouse
confidence: 0.99
evidence:
  - kind: final_url_host
    value: job-boards.greenhouse.io
  - kind: form_signature
    value: job_application[first_name]
posting_id: "1234567"
tenant_or_board: example-company
apply_url: https://job-boards.greenhouse.io/example-company/jobs/1234567
api_kind: public_posting_read_only
```

If `confidence < 0.85`, use `company_custom`; do not run another vendor’s selectors. Store the original discovery URL, final URL, redirect chain, frame URLs, locale, and detection version so a broken adapter can be reproduced.

## Playwright MCP driving patterns

### Server configuration

The current Microsoft README says the browser is headed by default; `--headless` opts into headless mode. It documents `--browser`, `--user-data-dir`, `--isolated`, `--storage-state`, `--config`, `--output-dir`, the timeout flags, and the corresponding JSON schema. It also warns that only one browser instance may use a persistent profile at a time. See [@playwright/mcp README: configuration and profiles](https://github.com/microsoft/playwright-mcp#configuration) and its [configuration schema](https://github.com/microsoft/playwright-mcp#configuration-file).

Use a dedicated Chrome or Chromium profile, separate from the user’s everyday browser profile. Resolve all home-relative paths before writing MCP JSON because JSON does not expand `~`, `$HOME`, or shell variables. This Python 3 setup code works on macOS and Linux and chooses installed Chrome/Chromium before falling back to Playwright’s bundled Chromium:

```python
import json
import os
import platform
import shutil
from pathlib import Path

home = Path.home()
data_home = Path(os.environ.get(
    "JOB_SEARCH_HOME", home / "development" / "random" / "job-search"
)).expanduser().resolve()
config_dir = data_home / "config"
profile_dir = data_home / "memory" / "playwright-profile"
evidence_dir = data_home / "applications" / "evidence"
for path in (config_dir, profile_dir, evidence_dir):
    path.mkdir(parents=True, exist_ok=True, mode=0o700)

candidates = []
if platform.system() == "Darwin":
    candidates.extend([
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        str(home / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
    ])
else:
    candidates.extend(filter(None, (
        shutil.which("google-chrome-stable"),
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    )))
browser_path = next((path for path in candidates if Path(path).is_file()), None)

launch_options = {"headless": False}
if browser_path:
    launch_options["executablePath"] = browser_path

config = {
    "browser": {
        "browserName": "chromium",
        "isolated": False,
        "userDataDir": str(profile_dir),
        "launchOptions": launch_options,
        "contextOptions": {"viewport": {"width": 1440, "height": 1000}},
    },
    "outputDir": str(evidence_dir),
    "timeouts": {"action": 10000, "navigation": 90000, "expect": 10000, "settle": 1000},
    "snapshot": {"mode": "full", "boxes": False},
}
(config_dir / "playwright-mcp.json").write_text(
    json.dumps(config, indent=2) + "\n", encoding="utf-8"
)
```

The README’s exact JSON keys are `browser.browserName`, `browser.isolated`, `browser.userDataDir`, `browser.launchOptions`, `browser.contextOptions`, `outputDir`, and `timeouts.action|navigation|expect|settle`. Register the MCP server from an installer that inserts the resolved config path into the client configuration. A shell launch works unchanged in macOS zsh and Linux bash:

```sh
JOB_SEARCH_HOME="${JOB_SEARCH_HOME:-$HOME/development/random/job-search}"
npx -y @playwright/mcp@latest \
  --config="$JOB_SEARCH_HOME/config/playwright-mcp.json"
```

`@latest` matches the upstream example. Pin the version from an acceptance-tested lockfile in production because MCP tool schemas can change. The equivalent flag-based launch, useful for diagnosing generated config, is:

```sh
JOB_SEARCH_HOME="${JOB_SEARCH_HOME:-$HOME/development/random/job-search}"
npx -y @playwright/mcp@latest \
  --user-data-dir="$JOB_SEARCH_HOME/memory/playwright-profile" \
  --output-dir="$JOB_SEARCH_HOME/applications/evidence" \
  --timeout-action=10000 \
  --timeout-navigation=90000 \
  --timeout-settle=1000
```

This flag form uses bundled Chromium unless the installer adds `--browser=chrome` for an installed branded Chrome or `--executable-path` for a discovered binary. Do not pass a guessed Linux browser command or the macOS app-bundle path on the other OS.

`--storage-state` provides an isolated alternative to a persistent profile. This portable shell form expands the path before `npx` receives it:

```sh
JOB_SEARCH_HOME="${JOB_SEARCH_HOME:-$HOME/development/random/job-search}"
npx -y @playwright/mcp@latest \
  --isolated \
  --storage-state="$JOB_SEARCH_HOME/memory/auth-state.json"
```

Storage state restores cookies and local storage into an isolated context; a persistent `userDataDir` retains broader browser state and suits ATS accounts. The profile and state file are bearer credentials: permissions `0700` for their directories and `0600` for state files. Never commit or mirror them to Notion. Run one application worker against each profile. Login and MFA require a headed, user-driven bootstrap session on both operating systems.

### One-tab-per-application loop

Process tabs sequentially even if several are open:

1. Call `browser_tabs` with `action: "new"` and the application URL; record `{fingerprint, tab_index, apply_url}`. The README documents `new`, `select`, `close`, and `list` operations for `browser_tabs` ([tool reference](https://github.com/microsoft/playwright-mcp#tools)). Re-list tabs after any popup or close because indexes can change.
2. Call `browser_snapshot`. The accessibility snapshot is the action source; screenshots are evidence only. Snapshot refs are ephemeral after navigation, SPA rerender, revealing a conditional question, or file parsing, so never reuse a ref across those events.
3. Map accessible labels to the canonical profile. Use `browser_fill_form` for a batch of textboxes/checkboxes/comboboxes, then snapshot and validate actual values and errors. For event-sensitive widgets, use `browser_type` with the current emitted ref/target and `slowly: true`; always set `submit: false` in application forms. Current README tool schemas describe the emitted element reference as the action `target`; some MCP clients render the argument name as `ref`. Use the schema exposed by the installed server, passing the exact current snapshot reference rather than a hand-written CSS selector.
4. For a résumé control, click the upload/drop-zone ref so the chooser opens, then call `browser_file_upload` with `paths` containing `str((DATA_HOME / "applications" / fingerprint / "tailored-resume.pdf").resolve())`. The README requires absolute paths. Snapshot after parsing finishes and check both the displayed filename and fields the parser overwrote. The [tool reference](https://github.com/microsoft/playwright-mcp#tools) documents `browser_snapshot`, `browser_fill_form`, `browser_file_upload`, and `browser_take_screenshot`.
5. For an intermediate **Next**, **Continue**, **Save and Continue**, or **Review** action, run validation first, click only its new snapshot ref, wait for the heading/progress indicator to change, then snapshot again. Do not press Enter to advance. Detect inline errors (`alert`, `aria-invalid=true`, “required,” “invalid,” “please enter/select”) and remain on the step until resolved or marked manual.
6. When the final-boundary classifier identifies a final control, do not click it in the filling loop. Capture the review snapshot and screenshot, transition to `review`, close/select another tab, or let the separate guarded commit path decide whether submission is permitted.

### Final-boundary detection and stop rules

Normalize accessible names by Unicode normalization, lowercasing, collapsing whitespace, and removing terminal punctuation. Match the adapter’s locale-specific allowlist. CSS is secondary evidence because classes change.

| Adapter | Final-control accessible-name candidates | Context needed to avoid a false positive |
|---|---|---|
| Greenhouse | `submit application`, `submit` | Application form plus identity/resume/questions visible; not a newsletter form. |
| Lever | `submit application` | URL ends `/apply` and Lever application container is present. |
| Ashby | `submit application`, `submit` | Apply route and last application section; no remaining Next/Continue. |
| Workable | `submit application`, `submit` | Candidate application route/review step, not an intermediate questionnaire form. |
| SmartRecruiters | `submit application`, `submit` | Review/final stage in SmartRecruiters flow. |
| Workday | `submit` | Progress/heading is Review or last configured section. Never equate the reusable bottom-navigation selector with finality by itself. |
| iCIMS | `submit application`, `submit profile`, `finish` | Job/profile application context and final/review page. |
| Taleo | `submit`, `submit application` | Review and Submit page; **Save and Continue** is intermediate. |
| LinkedIn | `submit application` | Easy Apply review dialog. Platform remains manual-only regardless of config. |
| Indeed | `submit your application`, `submit application` | Indeed Apply review step. Platform remains manual-only regardless of config. |
| BambooHR | `submit application`, `apply for this job` | Button is inside the filled application form, not the job-detail navigation CTA. |
| JazzHR | `submit application`, `apply now` | `applytojob.com` application form and required-field block are visible. |
| Rippling | `apply`, `submit application` | URL is `/apply?...step=application`; **Apply now** on job detail is navigation, not final. |
| Custom | `submit application`, `send application`, `complete application`, `apply` | All three required: inside candidate form, no remaining intermediate control, and either review/final heading or form action observed. Otherwise block as unknown. |

Also treat the following as potential submission attempts and route them through the guard: click on `button/input[type=submit]`; `browser_type(..., submit:true)`; Enter while focus is inside the final form; a control with form action/method that creates the application; or arbitrary page JavaScript. Because `type=submit` is frequently used for intermediate SPA steps, it is a **block candidate**, not sufficient proof of finality.

The fill worker must not have `browser_run_code_unsafe` or equivalent unrestricted execution capability; it could bypass the button policy. A robust implementation exposes a restricted MCP proxy that:

- records the last snapshot’s ref/target → role/name/form mapping;
- intercepts `browser_click`, Enter/submit keystrokes, and `browser_type submit:true`;
- denies any known or ambiguous final action;
- exposes a separate `commit_application` operation whose deterministic policy checks `auto_submit`, fit, cap, platform policy, unanswered/flagged questions, and evidence; and
- denies direct JavaScript/evaluate tools during application sessions.

A prompt-only “do not submit” rule supplies no hard enforcement.

### Evidence before and after the boundary

At the stop point call `browser_snapshot` with a relative file such as `{fingerprint}/2026-08-19T153012Z-review.md`, then `browser_take_screenshot` with `{fingerprint}/2026-08-19T153012Z-pre-submit.png`, `fullPage: true`, and `scale: "css"`. Store a companion JSON manifest containing final URL, platform/detection evidence, posting ID, page title, UTC timestamp, tailored résumé SHA-256, visible field names, filled/unfilled/flagged field IDs, final control accessible name, and state. Redact values for EEO, disability, veteran status, salary, phone/email, passwords, and tokens from the manifest and accessibility snapshot where feasible. The screenshot itself contains applicant PII, so keep it local with restrictive permissions and a retention setting.

If guarded auto-submit is permitted, take a second screenshot only after a confirmation heading/message and/or application ID is visible. A network 200, a button disappearance, or a URL change alone is not proof of submission.

## Form field mapping

### Canonical profile schema

Keep `false`, `unknown`, and missing distinct. Every sensitive fact should have `source` and `confirmed_at`; never infer a protected trait, immigration category, clearance, conviction, or disability from résumé text.

```yaml
schema_version: 1
identity:
  legal_first_name: ""
  legal_middle_name: ""
  legal_last_name: ""
  preferred_name: ""
contact:
  email: ""
  phone_e164: ""
  phone_country_code: "US"
location:
  address_line_1: ""
  address_line_2: ""
  city: ""
  region: ""
  postal_code: ""
  country_code: "US"
links:
  linkedin: ""
  github: ""
  website: ""
work_eligibility:
  country_code: "US"
  authorized_now: unknown
  sponsorship_now: unknown
  sponsorship_future: unknown
  citizenship_or_status: unknown
preferences:
  willing_to_relocate: unknown
  relocation_locations: []
  earliest_start_date: unknown
  notice_period_days: unknown
  salary:
    currency: USD
    period: year
    minimum: unknown
    target: unknown
    negotiable: unknown
self_identification:
  gender: decline
  race_ethnicity: decline
  protected_veteran: decline
  disability: decline
  pronouns: decline
structured_resume:
  employment: []
  education: []
  licenses_certifications: []
provenance:
  source: user_profile
  confirmed_at: "2026-08-19"
```

Empty strings above mean the profile validator must obtain them before applying; `unknown` means the fact is not established and must never be converted to yes/no. In the durable user profile, omit or reject empty required identity/contact values rather than treating the example as usable data. A user may explicitly choose actual EEO values instead of `decline`, but the auto-apply system must not derive them. EEOC guidance says self-identification data is for recordkeeping and should not be used in employment decisions, and OFCCP’s disability form says completion is voluntary ([EEOC guidance](https://www.eeoc.gov/laws/guidance/questions-and-answers-clarify-and-provide-common-interpretation-uniform-guidelines), [OFCCP CC-305](https://www.dol.gov/agencies/ofccp/self-id-forms)).

### Label aliases by platform

Resolve by accessible label first, then associated `<label for>`, `name`, autocomplete token, and nearby section heading. Fuzzy matching must be field-type constrained: for example, “Current location” must not match “Willing to relocate.” Employer-defined questions remain variable even on a known ATS.

| Platform | Name/contact/location labels | Link labels | Eligibility, preferences, and self-ID labels |
|---|---|---|---|
| Greenhouse | `First Name`, `Last Name`, `Email`, `Phone`, `Location (City)`, sometimes `Address` | `LinkedIn Profile`, `Website`, `Portfolio`, custom `GitHub` | Usually custom prose for authorization/sponsorship/relocation/salary/start; compliance blocks commonly `Gender`, `Race`, `Veteran Status`, `Disability Status`. |
| Lever | `Full name`, `Email`, `Phone`, `Current company`; location may be custom | `LinkedIn URL`, `Portfolio URL`, `Website`, sometimes `Twitter URL` | Employer custom questions; optional diversity survey wording varies. A single `Full name` maps to legal first + middle + last in display order. |
| Ashby | `First Name`, `Last Name` or `Name`, `Email`, `Phone`, `Location` | `LinkedIn Profile`, `Website`, `Portfolio`, custom GitHub | Employer questions commonly use full-sentence authorization, sponsorship, relocation, and salary labels; demographic survey headings/answers vary by country. |
| Workable | `First name`, `Last name`, `Email`, `Phone`, `Address`, sometimes `Headline` | `LinkedIn profile`, `Website`, custom GitHub/portfolio | Custom Yes/No, dropdown, paragraph questions; optional candidate survey. Workable supports auto-disqualifying Yes/No questions, so exact truth matters ([Workable knockout questions](https://help.workable.com/hc/en-us/articles/115012238688-Auto-disqualify-candidates-using-application-form-questions)). |
| SmartRecruiters | `First name`, `Last name`, `Email`, `Phone number`, `Location`/`City`, address components | `LinkedIn`, `Website`, `Portfolio` | `Are you legally authorized...`, `Will you now or in the future require sponsorship...` and preference/self-ID wording are tenant-configured; map only normalized full questions. |
| Workday | `Country`, `Legal First Name`, `Legal Middle Name`, `Legal Last Name`, `Address Line 1/2`, `City`, `State/Province`, `Postal Code`, `Email Address`, `Phone Device Type`, `Country Phone Code`, `Phone Number` | Under `Websites`: `Website URL` plus `Type` such as LinkedIn | Sections `Application Questions`, `Voluntary Disclosures`, `Self Identify`; labels commonly mention `legally authorized to work`, `require sponsorship`, `Gender`, `Race/Ethnicity`, `Veteran Status`, and the disability form. Repeated structured work/education is under `My Experience`. |
| iCIMS | `First Name`, `Middle Name`, `Last Name`, `Email`, `Phone`, `Street Address`, `City`, `State/Province`, `Postal Code`, `Country` | `LinkedIn Profile`, `Website`, or custom social/profile fields | Often `Are you authorized...`, `Do you require sponsorship...`, `Willing to relocate`; EEO may be a separate `Voluntary Self-Identification` step. Tenant labels are highly configurable. |
| Taleo | `First Name`, `Middle Name`, `Last Name`, `Email Address`, `Home Number`, `Cellular Number`, `Address`, `City`, `State/Province`, `Zip/Postal Code`, `Country` | Custom `Web Site`, social URL, or attachment fields | Blocks include `Disqualification Questions`, `Screening`, `Diversity`, `E-Signature`, and employer-specific eligibility/preference questions. Oracle documents personal information, work, education, e-signature, and review blocks in its [application flow](https://docs.oracle.com/en/cloud/saas/taleo-enterprise/25b/otcug/c-optimizedjobapplicationflow.html). |
| LinkedIn Easy Apply | `Email address`, `Phone country code`, `Mobile phone number`; name/location often inherited from profile | `LinkedIn` is implicit; employer questions may request `Website`, `Portfolio`, `GitHub` | Employer screening labels vary; never use remembered answers without checking the exact question. Optional self-ID can appear. Manual-only. |
| Indeed Apply | `First name`, `Last name`, `Email`, `Phone number`, `City, State`; contact may be inherited | Employer questions may request LinkedIn/website/GitHub | Employer screener wording varies; Indeed may remember previous answers. Inspect each. Manual-only. |
| BambooHR | `First Name`, `Last Name`, `Email`, `Phone`, `Address`, `City`, `State`, `ZIP`, `Country` | Custom `LinkedIn URL`, `Website`, `Portfolio`, `GitHub` | Authorization, sponsorship, relocation, salary, start, and EEO are employer-configured fields; do not assume a stable ID. |
| JazzHR | `First name`, `Last name`, `Email address`, `Location` with `Address`, `City`, `State`, `Postal`, and `Phone number` | Custom LinkedIn/website/GitHub labels | Custom select/text/checkbox questions commonly follow Résumé; eligibility and preference wording is employer-defined. |
| Rippling | Current observed labels: `First name`, `Last name`, `Email`, `Pronouns`, `Current company`, `Phone number`, `Location` | `LinkedIn Link`; website/GitHub can be custom; `Cover letter` is a file | Employer questions follow the core block; consent may include text messages and privacy/AI notices. Authorization, salary, relocation, and self-ID are employer-configured. |
| Company custom | Discover from accessibility tree; honor HTML `autocomplete=given-name|family-name|email|tel|street-address|address-level2|address-level1|postal-code|country` | Normalize labels containing LinkedIn, GitHub, portfolio, personal site, website | Match the normalized full question through the taxonomy below. Low-confidence mapping is flagged, never filled. |

### Mapping rules that prevent silent errors

- Normalize URLs to HTTPS, E.164 phone for storage, ISO country codes, ISO dates, and salary currency/period. Render into the site’s locale only at fill time.
- Never split a full name on whitespace without a configured legal-name decomposition; suffixes and multi-part family names make that unsafe.
- After résumé parsing, compare name, email, phone, current employer, dates, and education against canonical data. Restore parser-corrupted values and flag any field with ambiguous overwrite.
- For Workday/Taleo repeated experience, add rows from `structured_resume` only; do not synthesize duties. Treat “currently work here” separately from an absent end date.
- Do not fill hidden inputs directly. Interact with the visible accessible control so React/Angular state and validation events update.
- Do not accept privacy notices, e-signatures, SMS consent, arbitration, background-check authorization, or “I certify” statements from the generic profile. They require an explicit per-application user decision.
- Treat salary as a range with period and currency. Never place an annual target in an hourly field or vice versa.

## Screening questions

### Taxonomy and answer policy

| Category and examples | Policy | Reason / implementation |
|---|---|---|
| Contact and links: email, phone, LinkedIn, GitHub, website | **Auto-fill** | Direct canonical facts; validate URL and phone format. |
| Exact résumé facts: employer/title/dates, degree/school, named certification | **Auto-fill when structurally exact** | Copy facts only. If the form asks equivalence, recency, proficiency, or an aggregate such as “years of Kubernetes,” draft and flag. |
| Work authorization and sponsorship for a named country | **Auto-answer only from explicit country-scoped profile** | `unknown` stops. Do not infer status from address, school, employer, name, or résumé. DOJ says employers generally may ask whether an applicant has the legal right to work and needs sponsorship, but specific citizenship-status inquiries are best avoided ([DOJ IER FAQ](https://www.justice.gov/crt/iers-frequently-asked-questions-faqs)). |
| Minimum age, driver’s license, professional license, security clearance, export-control eligibility | **Auto-answer only from an explicit, current fact with exact scope; otherwise flag** | These are legal/credential facts. Never turn “clearance eligible” into “holds active clearance,” or infer citizenship. |
| Location, on-site/hybrid schedule, time zone, travel percentage | **Auto-answer if the approved preference exactly covers the requirement** | A new commute, travel percentage, or schedule is a material commitment; otherwise draft and flag. |
| Relocation | **Auto-answer only for an explicit destination or universal preference** | “Willing to relocate” does not imply every country/city or self-funded relocation. |
| Start date / notice period | **Auto-answer when explicit and still current** | Compute a date only from an approved notice rule and current date; flag employer-specific urgency. |
| Salary expectation | **Draft and flag**, unless user configured a role/location-aware rule that produces an in-range answer | Preserve currency/period and do not undercut a minimum. “Negotiable” must be allowed by the control. |
| Skills/proficiency/years: “expert?”, “how many years?”, “recent production experience?” | **Draft and flag** | Résumé evidence can support a proposed answer, but semantic level and overlapping dates require judgment. Include evidence citations to résumé bullets in the review record. |
| Knockout qualifications: degree required, clearance, license, shift, travel, physical requirement | **Exact fact only; flag if any interpretation** | A false answer is harmful and may auto-reject. Do not optimize for passing. |
| Motivation and fit: “Why us?”, “Why this role?”, “What interests you?” | **AI-draft and flag** | Generate a tailored, truthful draft grounded in the posting and résumé; user reviews voice and claims. |
| Behavioral/scenario/technical free response, portfolio explanation, accomplishments | **AI-draft and flag** | Do not invent an example, metric, employer detail, or technology. Shorten to the stated limit and preserve provenance. |
| Employment gaps, reasons for leaving, performance/termination, conflicts, noncompete, relatives/government ethics | **Must be answered by user** | Personal, contextual, or legally sensitive; do not draft a factual answer without supplied content. |
| Criminal history, background-check disclosures, drug testing, credit checks | **Must be answered by user** | Jurisdiction-sensitive and consequential. Never infer or reuse across employers. |
| EEO/race/ethnicity/gender, veteran, disability, medical/accommodation, religion, sexual orientation | **Use only explicit self-ID preference; otherwise select “Decline/I do not wish to answer” if available, or leave optional** | Never infer protected traits. Disability and veteran self-ID are voluntary; OFCCP confirms voluntary veteran disclosure ([VEVRAA FAQ](https://www.dol.gov/agencies/ofccp/faqs/vevraa?lang=en)). |
| Pronouns | **Use explicit preference only; default decline/blank** | Do not derive from name, photo, or profile. |
| Privacy policy, e-signature, truth certification, arbitration, SMS/email marketing, talent-community consent | **Must be reviewed/acted on by user** | These create attestations or consent. SMS recruiting consent should not inherit from general communication preferences. |
| “Did you use AI?”, original-work attestation, assessment honor code | **Must be answered by user, truthfully** | The system knows it drafted content but cannot decide how the employer’s wording applies. Preserve an AI-assistance audit trail. |

Every draft should be stored as `{question_text, normalized_category, proposed_answer, evidence, confidence, review_required: true}`. A required question with `unknown`, an unrecognized question, or a control whose selected value cannot be re-read moves the application to `review`; it must never be silently skipped or guessed.

## Anti-bot & ToS risk

### Platform risk matrix

“Variable” means an employer, geography, traffic pattern, or vendor configuration can add a challenge; it does not mean the platform is challenge-free.

| Platform | CAPTCHA / bot friction expected | Automation stance |
|---|---|---|
| Greenhouse | **Documented:** invisible Google reCAPTCHA on career-page integration options, with possible email-code verification depending on risk and employer sensitivity. Greenhouse says it analyzes activity such as mouse movement and typing ([Greenhouse reCAPTCHA, updated 2026-03-02](https://support.greenhouse.io/hc/en-us/articles/115005448066-Invisible-reCAPTCHA)). | Browser fill may proceed to review; any challenge is manual. Do not use the employer-key application API. |
| Lever | Variable: rate limits, account/form configuration, email validation, or a challenge can appear; no uniform public CAPTCHA guarantee was found. | Respect hosted form and normal pace; manual on challenge. Employer-key POST is unavailable to an applicant. |
| Ashby | Variable; employer questions, file parsing, verification, and edge/WAF behavior can change. No uniform documented CAPTCHA claim found. | Headed browser to review; runtime-detect challenges. |
| Workable | **Documented multi-layer defense:** WAF, IP reputation, browser-integrity validation, rate limiting, bot management, and CAPTCHA for suspicious traffic. It also tags detected AI-assisted applications ([Workable bot-prevention guidance](https://help.workable.com/hc/en-us/articles/35293126257815-Managing-AI-generated-and-automated-job-applications)). | Use the applicant’s real email and truthful content; manual on CAPTCHA. Expect automation metadata to be evaluated. |
| SmartRecruiters | Variable by tenant/region; login/email verification, rate limiting, or edge challenges may appear. | Headed to review; stop on challenge or identity verification. |
| Workday | High-friction multi-step account/email verification is common; tenant WAF/challenge behavior varies. | Persistent headed profile; manual login/MFA/challenge. Never depend on undocumented CXS requests for submission. |
| iCIMS | Tenant-configurable account/email/CAPTCHA friction; iframe and cross-origin behavior can complicate control access. | Manual on login verification, CAPTCHA, inaccessible frame, or session loop. |
| Taleo | Account creation, password rules, session expiry, e-signature, and occasional CAPTCHA vary by tenant; legacy pages are brittle. | Persistent headed profile; user handles account, e-signature, and challenge. |
| LinkedIn Easy Apply | LinkedIn actively limits Easy Apply volume/speed and says automation/bots are prohibited; its help page describes daily and speed limits ([Easy Apply limits](https://www.linkedin.com/help/linkedin/answer/a512348/?lang=en_US)). | **Manual-only.** Discovery may save the public job URL, but do not drive authenticated LinkedIn or Easy Apply with Playwright. |
| Indeed Apply | Email/phone verification, application limits, and anti-automation controls may appear. Terms expressly prohibit external automation of Indeed Apply. | **Manual-only.** Do not automate Indeed application pages. |
| BambooHR | Variable by employer/site; validation, throttling, or a challenge can appear. The authenticated API itself can throttle requests ([BambooHR technical overview](https://documentation.bamboohr.com/docs/api-details)). | Browser fill to review only; manual on challenge. |
| JazzHR | Variable: employer custom validation, edge protection, spam controls, or CAPTCHA may appear; no uniform documented challenge was found. | Browser fill to review; manual on challenge. |
| Rippling | Variable: identity, parsing, employer questions, and edge/bot controls can change; no uniform public CAPTCHA documentation was found. | Browser fill to review; manual on challenge or AI/privacy consent. |
| Company custom | Unknown until inspected: reCAPTCHA, hCaptcha, Cloudflare Turnstile/challenge pages, Arkose, email/SMS OTP, WAF, or custom honeypots are all possible. | Detect and stop. Never interact with a honeypot or bypass a control. |

### Terms risk

LinkedIn states that it does not permit third-party software, including bots, browser plug-ins, or extensions, that scrapes or automates activity on LinkedIn. Its crawling terms require express permission ([LinkedIn prohibited software](https://www.linkedin.com/help/linkedin/answer/a1341387/prohibited-software-and-extensions?lang=en), [LinkedIn crawling terms](https://www.linkedin.com/legal/crawling-terms)). Indeed’s 2026 Terms say users may not use automated systems to access, data-mine, or submit content without written permission and prohibit automating Indeed Apply outside official vendors/tooling ([Indeed Terms](https://www.indeed.com/legal?hl=en_US)). These terms require the following policy:

- `linkedin_easy_apply` and `indeed_apply` adapters must set `application_mode: manual_only`, regardless of `auto_submit`.
- The skill can record the job, prepare tailored documents, and open the URL for the user. It must not fill, click, scrape authenticated pages, or simulate submission there.
- For every other site, absence of an explicit prohibition in this research is not permission. The adapter should link the current candidate-site terms/privacy notice in the review record; company terms can differ from the ATS vendor’s terms.

### Safe operational mitigations

- Use one dedicated, persistent, headed Chrome or Chromium profile. Let the user perform login, MFA, email/SMS verification, and any identity check. Never run headless for login-walled sites.
- Use human-scale, sequential pacing: wait for actual UI state changes and keep conservative per-domain request/application limits. This is reliability and load hygiene, not a detection-evasion technique.
- Use the candidate’s normal network and true user agent. Do not rotate proxies, spoof fingerprints, patch automation signals, use stealth plugins, farm accounts, or outsource CAPTCHA solving.
- Never solve, relay, or bypass reCAPTCHA, hCaptcha, Turnstile, Cloudflare challenges, OTP, or identity verification. Detect challenge text/iframes/hosts, capture a screenshot, preserve the tab, and mark `needs_manual_apply` with the exact blocker.
- Stop after repeated session expiration, 401/403/429, “unusual activity,” access denied, robot verification, or an application limit. Do not retry more than once automatically; honor `Retry-After` and require manual continuation.
- Keep passwords and OTPs outside the profile/schema and evidence. The agent must not read the password manager, email, or SMS unless a separately authorized workflow explicitly supplies that access.

## Recommended design

### Adapter package

Ship the following files under `~/.claude/skills/job-search/references/ats/`:

```text
_base.md
greenhouse.md
lever.md
ashby.md
workable.md
smartrecruiters.md
workday.md
icims.md
taleo.md
linkedin-easy-apply.md
indeed-apply.md
bamboohr.md
jazzhr.md
rippling.md
company-custom.md
```

`_base.md` should define the adapter contract, canonical schema, question taxonomy, state machine, evidence manifest, challenge detectors, and guard semantics. Each vendor note should contain:

- ordered URL/frame/DOM/resource signatures with positive and negative fixtures;
- extraction of tenant/board/posting ID and documented posting endpoint, including whether it is unauthenticated, employer-authenticated, or undocumented;
- stage headings and typical fields, label aliases by locale, résumé-upload behavior and accepted formats;
- intermediate action names, final-boundary names plus required context, success-confirmation names, and known false positives;
- login/MFA/CAPTCHA/bot signals and `manual_only` policy where applicable;
- a `last_verified: 2026-08-19` line and source URLs;
- anonymized accessibility snapshots for unit tests, including a page whose CTA says Apply but is not final.

Do not put live CSS selectors in the central skill prompt. Load only the detected adapter note, prefer accessible role/name/ref at runtime, and keep selectors as adapter fallbacks with fixtures.

### Hard “never submit” guard

Use two phases with different capabilities:

1. **Fill phase:** may navigate, create/select tabs, snapshot, fill, select, upload, and take evidence. It cannot run arbitrary JavaScript, press Enter in forms, use `browser_type submit:true`, or click any known/ambiguous final target.
2. **Commit phase:** accessible only through `commit_application(job_fingerprint, evidence_hash)`. A deterministic policy outside the language model must verify all of:
   - `config.auto_submit is true`;
   - `fit_score >= config.auto_submit_threshold` (default `80`);
   - successful submits in this run are below `config.max_auto_submits_per_run` (default `5`);
   - adapter is not `manual_only` and detection confidence is at least `0.85`;
   - no CAPTCHA, login/MFA, verification, terms conflict, missing required field, inline validation error, unknown answer, AI-drafted answer awaiting review, sensitive consent, or user-only question;
   - current posting ID and final URL still match the draft;
   - pre-submit snapshot/screenshot and manifest exist and their hash matches the request; and
   - a fresh snapshot identifies the same final target in the expected final context.

If any check fails, deny the click and transition to `review` or `needs_manual_apply`. A fit score never overrides a question/consent/platform-policy failure. Increment the cap only after positive confirmation; reserve a slot atomically before clicking so a crash or concurrent worker cannot exceed five. The `auto_submit` default must be `false`.

Because raw Playwright MCP tools can otherwise bypass policy, put the guard in a small MCP proxy or tool broker and do not expose raw click/evaluate/run-code tools to the commit caller. Log every denied and allowed submission attempt with a reason code. This is the strongest practical improvement the skill can make over a prose-only instruction.

### State and artifact model

Use an append-only event log plus a materialized application record:

```text
draft
  -> filled
  -> review
  -> submitted
  -> needs_manual_apply
```

- **`draft`**: tailored résumé/cover letter exist; posting fingerprint, apply URL, adapter/version, fit score, and document hashes are stored.
- **`filled`**: all unambiguous fields on the current form have been filled and re-read; this is not a claim that required questions are resolved. Save per-field `{canonical_key, page_label, answer_source, status}`.
- **`review`**: final boundary reached, or any AI draft/user-only answer/consent requires review. Record final-control evidence, remaining questions, validation messages, and pre-submit artifacts. This is the normal terminal state when `auto_submit` is false.
- **`submitted`**: only after the guarded commit and positive confirmation page/message/application ID. Store submission UTC time, confirmation URL/text, post-submit screenshot, and guard decision. Never infer submission from an HTTP response alone.
- **`needs_manual_apply`**: CAPTCHA/challenge, login/MFA/OTP, platform `manual_only`, inaccessible/cross-origin control, unsupported widget, session/rate block, terms issue, closed posting, or unresolved required fact. Store `reason_code`, human-readable reason, preserved tab/URL when possible, and evidence.

Allowed transitions should be explicit: `draft -> filled|needs_manual_apply`; `filled -> review|needs_manual_apply`; `review -> submitted|needs_manual_apply`; and `needs_manual_apply -> filled|review|submitted` only after a user resumes the same posting. Never transition backward by overwriting history. A newly changed/republished job creates a new posting version but retains the original fingerprint linkage.

Suggested local layout:

```text
applications/{fingerprint}/
  application.json
  events.jsonl
  tailored-resume.md
  tailored-resume.pdf
  cover-letter.md
  cover-letter.pdf
  answers.json
  evidence/
    2026-08-19T153012Z-pre-submit.png
    2026-08-19T153012Z-review.md
    2026-08-19T153012Z-manifest.json
    2026-08-19T153455Z-confirmation.png
```

Mirror only non-sensitive summary fields to Notion: company, role, fit, source URL, state, dates, and local artifact references. Do not mirror browser state, full answers, EEO data, screenshots, salary constraints, phone/address, or signed consent evidence.

### Acceptance tests

Before enabling fill on an adapter, replay anonymized snapshots for: URL recognition, custom-domain iframe recognition, field alias mapping, résumé parse overwrite, conditional question reveal, multi-step ref invalidation, inline errors, final-button false positives, challenge detection, and confirmation detection. Before enabling `auto_submit` for any non-manual platform, run dry-run tests proving the proxy blocks every final-action route, including click, Enter, `submit:true`, CSS/role selector, and arbitrary-code tools, when each gate condition is false. Keep production `auto_submit: false` until those tests pass for the pinned MCP version.

## Cross-platform notes

### Runtime contract and paths

Support macOS and Linux with one Python 3 code path. Resolve paths with `pathlib`; do not concatenate `/Users/...` or `/home/...` strings:

```python
import os
from pathlib import Path

HOME = Path.home()
DATA_HOME = Path(os.environ.get(
    "JOB_SEARCH_HOME", HOME / "development" / "random" / "job-search"
)).expanduser().resolve()
SKILL_HOME = Path(os.environ.get(
    "JOB_SEARCH_SKILL_HOME", HOME / ".claude" / "skills" / "job-search"
)).expanduser().resolve()

for name in ("resume", "config", "memory", "reports", "applications", "logs"):
    (DATA_HOME / name).mkdir(parents=True, exist_ok=True, mode=0o700)
```

Use `JOB_SEARCH_HOME` and `JOB_SEARCH_SKILL_HOME` as the two supported overrides. Expand and resolve them once, pass absolute paths to MCP and file-upload calls, and serialize absolute paths into launchd files and MCP JSON. `$HOME/development/random/job-search` works in interactive zsh/bash and cron commands; launchd `ProgramArguments` and JSON do not expand it. Linux systemd units can use `%h` for the user home.

Use POSIX file modes on both systems: directory/profile/evidence roots `0700`, ordinary sensitive files `0600`. Permission modes do not provide a useful control on every mounted container or network filesystem, so the startup check must reject a world-readable storage-state file and warn on mounts that do not honor modes.

### Browser discovery and installation

Use the Python discovery code in **Playwright MCP driving patterns**. Its search order covers:

- macOS: `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`, the user app directory, then Chromium’s app bundle;
- Linux: `google-chrome-stable`, `google-chrome`, `chromium`, then `chromium-browser` through `shutil.which()`; and
- both: Playwright’s bundled Chromium when no installed executable matches.

Do not assume `/usr/bin/google-chrome`, Homebrew’s `/opt/homebrew` prefix, an Intel Mac’s `/usr/local` prefix, or Ubuntu’s `chromium-browser` wrapper. `--browser=chrome` selects a branded channel and fails on a host without Google Chrome. Omit that flag for bundled Chromium or set `launchOptions.executablePath` to the discovered file.

Install the Playwright browser that matches the pinned Playwright dependency:

```sh
# macOS
npx playwright install chromium

# Debian or Ubuntu; installs Chromium and required OS libraries
npx playwright install --with-deps chromium

# Fedora-class host; install the distro browser/dependencies, then the Playwright browser
sudo dnf install -y chromium nss atk at-spi2-atk cups-libs libdrm \
  libXcomposite libXdamage libXrandr mesa-libgbm pango alsa-lib
npx playwright install chromium
```

Playwright documents `npx playwright install chromium`, `install-deps chromium`, and the combined `install --with-deps chromium`. Its browser cache defaults to `~/Library/Caches/ms-playwright` on macOS and `~/.cache/ms-playwright` on Linux ([Playwright browser installation](https://playwright.dev/docs/browsers)). The Debian and Fedora archives also ship Chromium as `chromium` ([Debian Chromium packages](https://packages.debian.org/search?keywords=chromium&lang=en), [Fedora Chromium package](https://packages.fedoraproject.org/pkgs/chromium/chromium/)).

Run `npx playwright install --list` and a one-page launch/screenshot smoke test after install or package upgrades. Playwright’s `--with-deps` path targets supported Debian/Ubuntu environments. On Fedora, use the distro dependency transaction above or an official Playwright container based on a supported Linux image. Pin the container image and MCP/npm versions together.

### Headed applications and headless scheduled work

Split scheduled work into two capability sets:

- `scheduled_headless`: search public postings, update memory, score jobs, write reports, tailor documents, and print PDFs. It sets `auto_submit: false` and does not open login-walled application flows.
- `interactive_headed`: fill ATS forms and use the persistent profile after the user logs in. On macOS it runs in the logged-in Aqua session. On Linux it requires the user’s active X11 or Wayland desktop session and its existing `DISPLAY`/`WAYLAND_DISPLAY` environment.

A headless server or container can complete the first mode. It must set an application to `needs_manual_apply` with `reason_code: headed_session_required` when the next step needs login, MFA, CAPTCHA, browser identity, or user review. Xvfb can satisfy display requirements for test fixtures, but it does not turn a login-walled production flow into an approved headed user session. The Playwright MCP README says its Docker implementation supports headless Chromium only ([Playwright MCP Docker note](https://github.com/microsoft/playwright-mcp#docker)).

Mount `DATA_HOME` on persistent storage when a container runs scheduled work. Do not mount the interactive browser profile into a shared or ephemeral container. One profile may have one browser owner; use a lock file and a unique profile directory per host.

### PDF input, output, and fonts

Install Poppler’s `pdftotext`, Pandoc, and deterministic fonts by OS:

```sh
# macOS with Homebrew
brew install poppler pandoc
brew install --cask font-liberation

# Debian or Ubuntu
sudo apt-get update
sudo apt-get install -y poppler-utils pandoc fonts-liberation fonts-dejavu-core

# Fedora-class Linux
sudo dnf install -y poppler-utils pandoc liberation-fonts-all dejavu-sans-fonts
```

Homebrew documents `brew install poppler` and the Liberation font cask ([Poppler formula](https://formulae.brew.sh/formula/poppler), [Liberation font cask](https://formulae.brew.sh/cask/font-liberation)). Debian’s `poppler-utils` package includes `pdftotext`, and Fedora publishes the package under the same name ([Debian poppler-utils](https://packages.debian.org/stable/utils/poppler-utils), [Fedora poppler-utils](https://packages.fedoraproject.org/pkgs/poppler/poppler-utils/)). Debian and Fedora package Liberation/DejaVu fonts under the names used above ([Debian Liberation fonts](https://packages.debian.org/fonts-liberation), [Fedora Liberation fonts](https://packages.fedoraproject.org/pkgs/liberation-fonts/), [Fedora DejaVu fonts](https://packages.fedoraproject.org/pkgs/dejavu-fonts/)).

Extract résumé text with the same command on both systems:

```sh
pdftotext -layout "$JOB_SEARCH_HOME/resume/resume.pdf" -
```

Call it from Python with `subprocess.run([...], check=True, capture_output=True, text=True)` so spaces and shell quoting cannot change the argument list. Detect a scanned PDF when output has little text, then report `unknown: no text layer; check OCR` instead of treating the résumé as empty.

Generate PDFs through a pinned Playwright Node script that calls `page.pdf()`, not a hard-coded Chrome executable command. Convert the source to HTML with Pandoc, use `pathToFileURL()` for `file:` navigation on both systems, wait for `document.fonts.ready`, and set CSS fonts to `"Liberation Sans", "DejaVu Sans", Arial, sans-serif`. Set `printBackground: true`, explicit Letter/A4 selection from config, and fixed margins. Check the PDF with `pdffonts` and `pdftotext`; a missing expected font or empty text layer fails the artifact. ReportLab fallback code should register the installed Liberation/DejaVu TTF or a font bundled with the skill under a compatible license.

Minimal Linux images often lack fontconfig and common fonts. The package recipes above supply them through their dependencies; run `fc-cache -f` after adding fonts to a running container. On macOS, install the cask once per user before a launchd job prints documents.

### Scheduler recipes

All schedulers should invoke one Python entrypoint, `~/.claude/skills/job-search/scripts/scheduled_run.py`. That script resolves paths, loads a small environment file from `DATA_HOME/config/scheduler.env`, acquires an exclusive run lock, calls the configured absolute `claude` executable with `-p`, writes UTC timestamps, and forces `scheduled_headless`. Discover and persist the `claude`, `npx`, `pandoc`, and `pdftotext` executable paths during installation with `shutil.which()`; scheduler environments have a smaller `PATH` than interactive shells.

Cron works on macOS and Linux. Edit the user crontab with `crontab -e` and add:

```cron
SHELL=/bin/sh
PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
0 8 * * * /usr/bin/env python3 "$HOME/.claude/skills/job-search/scripts/scheduled_run.py" >> "$HOME/development/random/job-search/logs/cron.log" 2>&1
```

This schedule uses the host’s local 08:00. Avoid `CRON_TZ` because BSD cron on macOS and Linux cron implementations differ. The crontab manual confirms that cron supplies `HOME` and uses `/bin/sh` by default ([crontab(5)](https://man7.org/linux/man-pages/man5/crontab.5.html)). The Python lock must cause overlapping runs to exit without changing application state.

On macOS, prefer a per-user launchd agent for a job that needs the user session. Generate `~/Library/LaunchAgents/io.local.job-search.plist` with Python so every path is absolute:

```python
import plistlib
from pathlib import Path

home = Path.home()
data = home / "development" / "random" / "job-search"
agent = home / "Library" / "LaunchAgents" / "io.local.job-search.plist"
(data / "logs").mkdir(parents=True, exist_ok=True)
agent.parent.mkdir(parents=True, exist_ok=True)
payload = {
    "Label": "io.local.job-search",
    "ProgramArguments": [
        "/usr/bin/env", "python3",
        str(home / ".claude" / "skills" / "job-search" / "scripts" / "scheduled_run.py"),
    ],
    "WorkingDirectory": str(data),
    "StartCalendarInterval": {"Hour": 8, "Minute": 0},
    "EnvironmentVariables": {
        "PATH": "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin",
        "JOB_SEARCH_HOME": str(data),
    },
    "StandardOutPath": str(data / "logs" / "launchd.out.log"),
    "StandardErrorPath": str(data / "logs" / "launchd.err.log"),
}
with agent.open("wb") as handle:
    plistlib.dump(payload, handle)
```

Load and test it:

```sh
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/io.local.job-search.plist" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/io.local.job-search.plist"
launchctl kickstart -k "gui/$(id -u)/io.local.job-search"
```

Apple documents per-user agents under `~/Library/LaunchAgents`, `ProgramArguments`, and `StartCalendarInterval` ([Apple launchd jobs](https://developer.apple.com/library/archive/documentation/MacOSX/Conceptual/BPSystemStartup/Chapters/CreatingLaunchdJobs.html)). Use a LaunchAgent in the logged-in user domain, not a root LaunchDaemon, for any headed browser work.

On Linux, prefer a systemd user timer. Write `~/.config/systemd/user/job-search.service`:

```ini
[Unit]
Description=Scheduled job search

[Service]
Type=oneshot
WorkingDirectory=%h/development/random/job-search
Environment=PATH=/usr/local/bin:/usr/bin:/bin
ExecStart=/usr/bin/python3 %h/.claude/skills/job-search/scripts/scheduled_run.py
```

Write `~/.config/systemd/user/job-search.timer`:

```ini
[Unit]
Description=Run job search each morning

[Timer]
OnCalendar=*-*-* 08:00:00
Persistent=true
RandomizedDelaySec=10m

[Install]
WantedBy=timers.target
```

Enable and inspect it:

```sh
systemctl --user daemon-reload
systemctl --user enable --now job-search.timer
systemctl --user list-timers job-search.timer
journalctl --user -u job-search.service -n 100 --no-pager
```

The `%h` specifier resolves to the user manager's home directory ([systemd.unit(5)](https://man7.org/linux/man-pages/man5/systemd.unit.5.html)). `Persistent=true` records the previous trigger and catches a missed calendar run after the timer becomes active again ([systemd.timer(5)](https://man7.org/linux/man-pages/man5/systemd.timer.5.html)). A Linux server that must run the user timer without a login session needs administrator-approved lingering (`sudo loginctl enable-linger "$USER"`), which starts the user manager at boot and retains it after logout ([loginctl(1)](https://man7.org/linux/man-pages/man1/loginctl.1.html)). Scheduled headless mode still forbids authenticated auto-apply.

### Portable helper code and test matrix

Write helper scripts in Python 3 stdlib unless a browser action requires Node/Playwright. Use `datetime.now(timezone.utc)` plus `strftime()` for timestamps instead of BSD/GNU `date` arithmetic. Use `Path.read_text()`/`write_text()` for edits instead of the incompatible macOS `sed -i ''` and GNU `sed -i` forms. Use `tempfile.TemporaryDirectory`, `shutil.which`, `subprocess.run` with argument arrays, `os.replace` for atomic state writes, and `fcntl.flock` for the macOS/Linux run lock. If a shell wrapper remains, target POSIX `sh`, quote every expansion, and avoid bash arrays and GNU-only flags.

Run CI or acceptance tests on a current macOS runner, Debian/Ubuntu, and Fedora. Add a minimal Linux container test for browser launch, font availability, HTML-to-PDF, `pdftotext`, absolute upload paths, config generation, and scheduled-headless refusal to apply. Keep a separate headed manual test on macOS and Linux desktop for persistent login, one-profile locking, file upload, pre-submit stop, and evidence capture.

## Confidence

ATS URL recognition and supported posting APIs: **high** for Greenhouse, Lever, Ashby, Workable, SmartRecruiters, iCIMS, BambooHR, JazzHR, and Taleo because vendor documentation provides the URL/API contracts; **medium** for Workday and Rippling because their public candidate backends are not documented as stable APIs.

Typical form structures and label aliases: **medium** because vendor flows have solid evidence, while employers, countries, locales, and product releases can change labels, required fields, EEO, and step order; runtime accessibility inspection remains authoritative.

Playwright MCP flags, config keys, tab/snapshot/fill/upload/screenshot behavior: **high** because the Microsoft repository README and current schema documented them on 2026-08-19; read exact nested tool argument names from the installed pinned server.

Final-submit heuristics and guard design: **medium-high** because the browser exposes accessible names and stages and the proxy closes known bypasses; localized/custom controls require adapter fixtures and unknown finality must fail closed.

Screening-answer safety and self-identification handling: **high** for the conservative policy because it follows EEOC, DOJ, and OFCCP primary guidance; the user must review employer- and jurisdiction-specific legal interpretation.

CAPTCHA and anti-bot behavior: **high** for Greenhouse and Workable because vendors document controls; **medium-low** for other ATSs because challenge deployment changes by tenant and traffic, so the design uses runtime detection and manual fallback.

LinkedIn and Indeed manual-only policy: **high** because both companies’ current official terms/help restrict external automation.

Cross-platform paths, dependencies, and schedulers: **high** for macOS and Debian/Ubuntu because the recipes follow vendor and distribution documentation; **medium-high** for Fedora because Playwright does not document Fedora as a supported `--with-deps` target, so that recipe installs Fedora's Chromium and runtime libraries explicitly.
