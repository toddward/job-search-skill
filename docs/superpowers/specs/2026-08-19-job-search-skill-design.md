# job-search skill — design spec

Date: 2026-08-19
Status: approved by user (design conversation 2026-08-19); this document is the reference for the implementation plan.
Research inputs: `docs/research/{ats-autoapply,job-boards,skill-architecture,resume-tailoring}.md` (Codex, Grok, Claude×2 via Herdr; facts marked `[verified locally]`/`[tested]` in those files were executed on this machine).

## 1. Purpose

A Claude Code skill, `/job-search`, that on demand or on a schedule:

1. reads the user's resume (PDF/MD/TXT in `resume/`, or a hosted URL);
2. searches a user-editable list of job boards with a layered strategy (JSON APIs / WebFetch → Firecrawl MCP → Playwright MCP);
3. keeps durable, human-editable memory of every job seen, what the user dismissed (and why), what was applied to, and a 14-day re-show cooldown;
4. produces a stack-ranked list of ≥10 jobs with a deterministic resume-fit score, written to `reports/` and mirrored to Notion (destination configurable);
5. lets the user pick 1..N jobs → tailored resume + cover letter per job (Markdown + PDF);
6. fills the application via Playwright MCP with a persistent logged-in browser profile, AI-drafts answers to unknown screening questions and flags them, and **never submits** unless the persistent `auto_submit` flag is on and a deterministic guard passes.

Runs identically in an interactive session and under `claude -p` from cron / launchd / systemd, on macOS and Linux.

## 2. Decisions made with the user

| Topic | Decision |
|---|---|
| Where it lives | Public repo `https://github.com/toddward/job-search-skill` **is the skill** (SKILL.md at repo root) — install by cloning/symlinking to `~/.claude/skills/job-search/`. The personal **data home is outside the repo**: `$JOBSEARCH_HOME` → pointer file `~/.config/job-search/home` → default `~/job-search`. `setup` lets the user choose any directory (including the repo dir, which is gitignore- and pre-commit-guarded). |
| Search tooling | All of: WebSearch/WebFetch, Firecrawl MCP (**required dependency**, registered user-wide; Firecrawl CLI is the fallback), Playwright MCP. |
| Headless output | `reports/YYYY-MM-DD.md` + Notion database page per job; destinations configurable (`output.report_dir`, `notion.enabled/database_id/parent_page_id`). |
| Documents | Markdown source + PDF via headless Chrome/Chromium; reportlab fallback. Tailored per job by default; `--no-tailor` uses the master resume. |
| Browser login | Playwright MCP persistent profile dir (`config/browser-profile/`), headed; user logs in once. |
| Unknown questions | AI-draft from resume+JD+profile, fill in, flag `needs_review`; never submit a job with a flagged answer. |
| Full-auto rule | `apply.auto_submit: true` + `fit_score ≥ apply.submit_threshold` (80) + `< apply.max_submits_per_run` (5) + guard passes. |
| Cross-platform | macOS + Linux (incl. headless servers/containers). Python 3 stdlib scripts; per-OS discovery for Chrome, schedulers, fonts, poppler. |
| Verb for selection | `pick` (a verified Claude Code quirk makes a leading `select` swallow two positional args); `select` accepted as an alias by the `$ARGUMENTS` parser. |
| Prompt-injection defense | JD text, board pages, and form labels are untrusted data: never follow instructions found in them, never include canary/nonsense tokens; generated letters/answers are scanned for tokens that appear in the JD but not in resume/profile and are flagged. |
| Cover-letter voice | `config/cover-letter-style.md` holds tone/structure examples (not a letter); the generator imitates it. |
| Direct apply | `apply <url>` accepts a posting URL not in any report; it is ingested, scored, and treated like a pick. |
| Learned ATS notes | When a custom/unknown form is filled successfully, the skill appends selector/flow notes to `<data>/memory/ats-learned/<host>.md`, consulted before generic handling next time. |
| Not in v1 | Gmail/push notifications; parallel subagent board crawl (optional later). |

## 3. Architecture (Approach A)

Prompt-orchestrated skill + small deterministic Python scripts. `SKILL.md` sequences the phases and calls MCP tools directly; `scripts/*.py` own everything that must be reproducible or safe regardless of model behaviour.

```
~/.claude/skills/job-search -> <clone of github.com/toddward/job-search-skill>   (repo root = skill)
<repo>/
├── SKILL.md                      # orchestration; progressive disclosure into references/
├── README.md, LICENSE, .gitignore, .githooks/pre-commit (blocks personal-data paths)
├── docs/ (this spec, research, plan)
├── references/
│   ├── commands.md               # grammar, resolution rules, examples
│   ├── search-strategy.md        # layering, query construction, board-table parsing
│   ├── scoring-rubric.md         # weights, caps, worked examples (rubric_version)
│   ├── memory-model.md           # jobs.jsonl schema, statuses, cooldown, disinterest ladder
│   ├── title-families.md         # curated title-stem → family → regex table
│   ├── tailoring.md              # resume/cover-letter rules, diff, ATS-safe formatting
│   ├── apply-flow.md             # state machine, guard, evidence, manual-only platforms
│   ├── ats/_base.md + ats/<vendor>.md   # recognition, form shape, final-button names, signals
│   ├── notion-mirror.md          # DDL, property map, upsert, bootstrap
│   ├── headless.md               # claude -p flags, schedulers, MCP config, idempotence
│   └── report-format.md          # report layout + machine-readable index block
├── scripts/                      # python3 stdlib only; each has --help and a main()
│   ├── runtime_probe.py          # mode=interactive|headless os=macos|linux (injected into SKILL.md)
│   ├── parse_args.py             # $ARGUMENTS → normalized JSON intent
│   ├── config.py                 # load/merge settings.yaml + settings.local.yaml + platform overrides
│   ├── doctor.py                 # dependency checks + per-OS install hints; bootstrap dirs/config
│   ├── resume_ingest.py          # pdf/md/txt/url → resume/master.md (cached by hash)
│   ├── boards.py                 # parse job-board-links.md; render URLs for a query
│   ├── jd_extract.py             # JSON-LD / ATS JSON / heading harvest → job.json (+low_confidence)
│   ├── fingerprint.py            # company/title/location keys, canonical URL, fingerprint, posting_id
│   ├── jobs_db.py                # jsonl upsert/set-status/list/validate; atomic writes; quarantine
│   ├── disinterest.py            # rule evaluation + escalation ladder + retrospective hit counts
│   ├── fit_score.py              # deterministic 0-100 w/ breakdown, caps, rubric_version
│   ├── rank.py                   # cooldown + rules + score → ranked list; widening until min_results
│   ├── report.py                 # write reports/<date>.md with job-index block; set last_shown
│   ├── html2pdf.py               # md/html → PDF via Chrome discovery; reportlab fallback; page count
│   ├── apply_guard.py            # deterministic submit decision; reserves cap slot; logs reason codes
│   ├── notion_sync.py            # builds upsert payloads; outbox for failures (MCP calls made by skill)
│   └── run_headless.py           # scheduler entrypoint: lock, claude -p, MCP-init check, run log
├── assets/
│   ├── resume-template.html      # ATS-safe single-column Letter template (Liberation/Arial stack)
│   ├── cover-letter-template.html
│   ├── settings.example.yaml, profile.example.md, job-board-links.default.md
│   ├── headless.settings.example.json, mcp.headless.example.json
│   └── schedulers/{crontab.txt, launchd.plist, systemd.service, systemd.timer}
└── tests/                        # pytest; fixtures for ATS snapshots, JDs, resumes

$JOBSEARCH_HOME (default ~/job-search)   # DATA HOME — personal; its own local git repo, never pushed
├── resume/                      # resume.pdf|md|txt, optional resume.url, master.md (generated)
├── config/                      # settings.yaml, settings.local.yaml, profile.md, cover-letter-style.md,
│                                # job-board-links.md, headless.settings.json, mcp.headless.json, browser-profile/
├── memory/                      # jobs.jsonl, disinterest.yaml, runs.jsonl, runs/<id>.json,
│                                # notion-outbox.jsonl, ats-learned/<host>.md, logs/, .run.lock/
├── reports/YYYY-MM-DD[.rN].md
└── applications/<YYYY-MM-DD>-<fp>/
```
Data-home resolution order: `--home <path>` arg → `$JOBSEARCH_HOME` → `~/.config/job-search/home` (one-line pointer written by `setup`) → `~/job-search`.

## 4. Command surface

Parsed from `$ARGUMENTS` by `scripts/parse_args.py` (never from `$0`/`$1`). Output is a JSON intent the skill acts on.

```
/job-search <free text>                      scan now with this query ("AI jobs in Reston, VA")
/job-search scan [--headless] [--max N] [--run ID] [--query "..."]
/job-search pick 1,3,5 [--from DATE | --run ID] [--no-tailor] [--apply|--no-apply]
/job-search no 5 "reason"  |  no 5,9 --reason "..."
/job-search snooze 7 30d
/job-search show 1
/job-search status
/job-search unhide dis-002 [--to soft]
/job-search submit 1 --i-mean-it             explicit one-off submit, ignores auto_submit=false
/job-search setup                            doctor + bootstrap (dirs, config, board list, Firecrawl MCP, resume prompt)
/job-search apply 1,3 | apply <url>          alias for pick --apply; a URL is ingested+scored then treated as a pick
/job-search pick 2 --note "emphasize K8s"     per-job guidance for tailoring and the cover letter
```

Number resolution: `--run` → `--from` → newest run in `runs.jsonl` whose report exists. Fingerprints (16-hex or unique ≥6-char prefix) are accepted anywhere a number is. Indexes older than 14 days are refused. Every action echoes `#n → <fingerprint> <title> @ <company>` before acting.

Mode: `mode=headless` (probe: `CLAUDE_CODE_ENTRYPOINT` not in {cli, vscode, jetbrains, desktop}, or `--headless` given) ⇒ never AskUserQuestion, ambiguity resolves conservatively (skip + record), end by writing report/Notion/run record.

## 5. Pipeline (scan)

1. **Preflight** — `config.py` merge; `doctor.py --quick` (Firecrawl MCP or CLI present? Chrome discoverable? resume present?). If `resume/` is empty and not headless: create it and ask the user to drop a PDF/MD/TXT or give a hosted URL (LinkedIn/personal site); headless: write the ask into the report and exit.
2. **Resume ingest** — `resume_ingest.py` → `resume/master.md` (sections: summary, skills, experience bullets, education, certs) cached by source hash. PDF via `pdftotext -layout`; URL via Firecrawl scrape; LinkedIn public profile via Firecrawl (best effort).
3. **Query parse** — free text → `{keywords[], location, radius_miles, remote}` with per-board location aliases (Reston→McLean for Capital One, Herndon for AWS, "Washington, DC" for metro boards, Reston VA USA for Google Careers). Always run local + remote-US passes unless `remote: exclude`.
4. **Board crawl** — `boards.py` renders URLs from `config/job-board-links.md` rows with `Enabled=true`, in `strategy_order`: (a) JSON/RSS/guest HTML via WebFetch (USAJOBS API, Greenhouse/Lever/Ashby board JSON, RemoteOK, WWR RSS, HN Algolia, LinkedIn guest search); (b) Firecrawl `search` (cross-ATS `site:` queries) / `scrape` (listing + ≤30 detail pages) / `extract` (SPA boards); (c) Playwright persistent profile (login-walled boards, only if yield is thin). Per-board timeout; failures recorded in `runs.jsonl.boards_failed`.
5. **JD extraction** — `jd_extract.py`: JSON-LD `JobPosting` → ATS JSON → heading-scoped bullet harvest (must/nice buckets) → model extraction only when `low_confidence`, cached by JD sha256. Regex facts: clearance, citizenship/sponsorship, years, salary.
6. **Identity & dedup** — `fingerprint.py`: `sha256(company_key|title_key|location_key)[:16]`; `posting_id` per canonical URL; canonical-URL priority (company ATS > first-party careers > LinkedIn view > Dice > aggregators); strip tracking params; aggregator dupes merge into one row with `sources[]`; collision guard on title similarity; repost detection via `content_hash` + forward `posted_at` bumps `version` and resets `status=new`.
7. **Filter** — expiry checks (404/410, closed-text regex, `closes_at` past, missing from board pull 7d); `disinterest.py` rules (hard → hidden, soft → penalty); cooldown (§6).
8. **Score & rank** — `fit_score.py` (§7); `rank.py` widens (radius 25→50, enable more boards, remote pass) until ≥ `search.min_results` survive; list length `search.max_results`.
9. **Report** — `report.py` writes `reports/YYYY-MM-DD.md`: summary counts, ranked table (fit, role, company, location, comp, posted, source, canonical URL, top fit reasons, missing must-haves), "Needs your decision" (needs_manual_apply + headless dismissals without reason), "Suppressed but high-fit", learned rules, and the fenced `json job-index` block. Then sets `last_shown`/`shown_count` for listed jobs and appends `runs.jsonl`. Same-day reruns write `.rN.md`.
10. **Notion mirror** — if enabled: bootstrap DB on first run (`notion-create-database`, DDL in `references/notion-mirror.md`, ids written to `settings.local.yaml`), then upsert by `Fingerprint` for rows per `notion.mirror` policy (`shown` default). Failures go to `memory/notion-outbox.jsonl` and flush next run. Only non-sensitive summary fields are mirrored.
11. **Commit** — `git -C memory add -A && commit` (never push).

Interactive: after the report, print the numbered list and one `AskUserQuestion` for disposition (apply top N / show #1 / nothing today / nothing + stop showing family); free text handles `apply 1,3` / `no 5 "reason"`.

## 6. Memory model

`memory/jobs.jsonl`: one record per fingerprint, JSON Schema in `references/memory-model.md` (fields: schema, fingerprint, title/company/location + keys, remote, url, canonical_url, source, sources[], posted_at, closes_at, comp_*, first_seen, last_seen, last_shown, shown_count, snooze_until, status, status_changed_at, status_reason, fit_score, fit_breakdown, fit_reasons, suppressed_by, content_hash, version, application_dir, applied_at, submitted, notion_page_id, notion_synced_at, run_ids, notes). Fixed key order, one line each, atomic rewrite, bad lines quarantined to `jobs.badlines.jsonl`.

Statuses: `new, shown, selected, applied, not_interested, expired, needs_manual_apply`.

**Cooldown (wall-clock UTC):** a job with status `shown`/`selected` is eligible to be listed again only when `now − last_shown ≥ 14d` (`memory.cooldown_days`); after `shown_count ≥ 3` with no action, 45d. `last_shown` is set only after the report file is on disk. `not_interested` and `applied` are never re-listed; `expired` hidden; `needs_manual_apply` always listed in "Needs your decision" until resolved (exempt from cooldown). `selected` with no `application_dir` after 7d reverts to `shown`. A version bump (material repost) resets `status=new`, `last_shown=null`. `snooze_until` hides without learning.

**Disinterest (`memory/disinterest.yaml`):** rules `{id, scope: title|company|comp|location|keyword, pattern|min_base, family, strength: hard|soft, penalty, reason, created, created_by: user|generalized, evidence[], hits}`. Ladder on `no`: record instance → look up title family in `references/title-families.md` (curated; never model-invented regex) → first dismissal in family ⇒ soft (−20) → second within 90d ⇒ hard; company/comp dismissals ⇒ hard immediately. Report always explains a suppression with its rule id and `unhide` command, and prints the retrospective hit count at creation. Auto-created rules never hide `fit ≥ 90` (moved to "Suppressed but high-fit"); user-written rules are absolute. Headless dismissals without a reason create no rule.

`memory/runs.jsonl`: run_id, timestamps, mode, subcommand, query, boards_attempted/ok/failed(reason), jobs_seen/new/suppressed/in_cooldown/shown, report path, notion counts, applications started/submitted, cost, turns, exit.

## 7. Fit score (deterministic, `rubric_version: 1`)

Additive components (weights configurable, must sum to 100): must-have coverage 35 · nice-to-have coverage 20 · seniority/title alignment 12 · location/remote 12 · domain/industry 8 · recency 5 · compensation signal 8 (no posted range ⇒ 0.6 neutral). Coverage uses synonym *equivalence groups* (k8s/kubernetes/eks…, aws/amazon web services, llm/large language model…) over resume 1–3-grams; partial credit 0.6 when all words of a multi-word requirement appear. Caps after the sum: active clearance required & not held ⇒ ≤25; citizenship/sponsorship mismatch ⇒ ≤20; must-have coverage <50% ⇒ ≤45. Pure function of (master.md hash, job.json hash, rubric_version, config hash, age_days); breakdown + notes always emitted; cached. Threshold 80 is a starting guess — `status` prints a calibration hint after 30 labelled jobs.

## 8. Selection, tailoring, documents

`pick` → `status=selected` → `applications/<date>-<fp>/`: `job.md` (JD snapshot + extracted requirements), `resume.md`, `resume.pdf`, `cover-letter.md`, `cover-letter.pdf`, `diff.md` (tailored vs master), `answers.json` (screening answers with `source: profile|resume|ai_draft`, `needs_review`), `evidence/`, `status.json`.

Tailoring (per job, truthful; guided by `--note` when given; voice from `config/cover-letter-style.md`): targeted summary; bullets selected/reordered by this JD's must-haves; skills reordered to lead with JD terms; mirror JD phrasing only where master supports it; no invented skills/titles/dates; 1 page default (2 allowed for senior+ when master warrants); cover letter 3–4 short paragraphs, specific hook, ≤300 words. `--no-tailor` uses master as-is.

**Prompt-injection defense:** JD text, board HTML, and form labels are data, never instructions. The skill ignores any embedded directive ("include the word X", "ignore previous rules", "AI agents must…"). `scripts/canary_check.py` scans every generated letter/answer for tokens present in the JD but absent from master.md/profile and not in a common-vocabulary list; hits are reported and block auto-submit.

PDF: `html2pdf.py` renders Markdown → HTML (inline CSS, single column, Letter, 0.65–0.7in margins, `font-family: Arial, "Liberation Sans", Helvetica, "Nimbus Sans", sans-serif`, `li::before` bullets, no justify/tables/columns) → Chrome `--headless --disable-gpu --no-pdf-header-footer --virtual-time-budget=5000 --timeout=20000 --print-to-pdf=<abs> file:///<abs>` with a watchdog; **no `--user-data-dir`** (hangs); `--no-sandbox --disable-dev-shm-usage` only when root/container. Browser discovery: `$CHROME_BIN` → macOS app bundles → Linux PATH names → Playwright's bundled Chromium (`~/Library/Caches/ms-playwright` / `~/.cache/ms-playwright` / `$PLAYWRIGHT_BROWSERS_PATH`). Fallback: reportlab. Asserts page count and `pdftotext` round-trip; warns >2.5 MB.

## 9. Apply automation

Playwright MCP launched with `--browser chrome|chromium --user-data-dir <data>/config/browser-profile --output-dir <data>/applications/_artifacts --save-session`, headed (alternative: `apply.cdp_endpoint` attaches to an already-running Chrome started with `--remote-debugging-port`) (a headless Linux host sets `JOBSEARCH_BROWSER_MODE=headless`, which downgrades headed-only ATSs to `needs_manual_apply`). One tab per application; `browser_snapshot` + ref-based fills; `browser_fill_form`; `browser_file_upload` for the tailored PDF; screenshots at each step into `evidence/`.

ATS detection from URL/DOM → load only that adapter note (`references/ats/<vendor>.md`), then any learned note in `<data>/memory/ats-learned/<host>.md` (written after a successful fill on a custom/unknown form): Greenhouse, Lever, Ashby, Workable, SmartRecruiters, Workday, iCIMS, Taleo, BambooHR, JazzHR, Rippling, Phenom/Eightfold (company sites), custom. **LinkedIn Easy Apply and Indeed Apply are manual-only** (ToS): no filling; report links the canonical posting.

Field mapping from `config/profile.md` (identity, links, work authorization, sponsorship, relocation, salary expectation, start date, voluntary self-ID preferences incl. "decline to answer") + resume. Screening questions: safe-from-profile vs AI-drafted (`needs_review: true`, listed in the report and `answers.json`).

State machine: `draft → filled → review → submitted | needs_manual_apply`. **`apply_guard.py`** decides submit: `auto_submit` (or `--i-mean-it` for one job) ∧ `fit ≥ submit_threshold` ∧ reserved slot `< max_submits_per_run` ∧ adapter not manual-only ∧ no CAPTCHA/login/MFA/OTP ∧ no inline validation errors ∧ no `needs_review` answers ∧ posting id/URL still match the draft ∧ pre-submit screenshot exists. Any failure ⇒ `review` (normal terminal state when `auto_submit=false`) or `needs_manual_apply` with reason code. `submitted` only after positive confirmation (page text/app id) + post-submit screenshot; `jobs.jsonl` updated to `applied`, Notion mirrored. The skill text never clicks a final-submit control without a passing guard result in hand.

## 10. Configuration

`config/settings.yaml` (hand-authored, platform-neutral; paths relative to data home or `~`): `search.{query,default_location,radius_miles,remote_preference,min_results:10,max_results:12,max_age_days,boards_file,strategy_order}`, `scoring.{resume_path,resume_url,weights,min_fit_to_show,rubric_version}`, `memory.{cooldown_days:14,extended_cooldown_days:45,expire_after_days,selection_expiry_days:7,git_autocommit}`, `apply.{auto_submit:false,submit_threshold:80,max_submits_per_run:5,max_applications_per_run:5,browser_profile_path,browser_mode,browser_channel,browser_no_sandbox,cdp_endpoint,tailor_by_default:true,profile,cover_letter_style}`, `output.{report_dir,applications_dir,pdf_engine,chrome_path,pdf_font_family}`, `notion.{enabled,database_id,data_source_id,parent_page_id,database_title,mirror}`, `runtime.{model,fallback_model,max_turns,max_budget_usd}`, `platform_overrides.{macos,linux}`. `config/settings.local.yaml` is machine-written (host facts, Notion ids, bootstrap hashes). Precedence: CLI args > settings.local > settings > defaults. `config/job-board-links.md`: table `Board | Search URL template | Method | Login required | Enabled | Notes`, seeded from Grok's verified list (10 enabled by default for the Reston AI case; remainder inventory).

## 11. Headless / scheduling

`scripts/run_headless.py <subcommand>` (same on every OS): `mkdir`-lock, `claude -p "/job-search <sub> --headless --run <uuid>" --model … --fallback-model … --permission-mode dontAsk --settings config/headless.settings.json --mcp-config config/mcp.headless.json --strict-mcp-config --disallowedTools AskUserQuestion --max-turns 120 --max-budget-usd 4 --session-id <uuid> --output-format json < /dev/null`, asserts MCP init had no `mcp_server_errors`, writes `memory/runs/<id>.json`, exits non-zero on failure/zero-turn runs. Templates for crontab, launchd plist (`gui/$UID`, needs GUI session for headed Chrome), and systemd user service+timer (`Persistent=true`, `loginctl enable-linger`). `mcp.headless.json` declares `playwright` (persistent profile), `firecrawl` (`npx -y firecrawl-mcp`, key from env/CLI config), `notion` (`https://mcp.notion.com/mcp`, OAuth'd once interactively). Firecrawl MCP is also registered user-wide by `setup` for interactive sessions.

## 12. Error handling

- Board failure ⇒ continue, record reason; if all boards fail ⇒ report says so, exit non-zero.
- MCP server missing ⇒ doctor message with exact fix; Firecrawl falls back to CLI; no Playwright ⇒ apply phase reports `needs_manual_apply`.
- Corrupt jsonl line ⇒ quarantine, continue. Notion failure ⇒ outbox. Chrome hang ⇒ watchdog kill, reportlab fallback.
- Headless ambiguity ⇒ conservative branch, listed under "Needs your decision". Never invent a preference or submit in doubt.

## 13. Testing

(adds) `canary_check.py` unit tests with a JD fixture containing an injected instruction and canary word; `apply <url>` ingestion test; data-home resolution order test.

- `pytest` over `skill/tests/`: fingerprint/canonical URL; cooldown arithmetic incl. 45d extension and selection decay; disinterest ladder (soft→hard, company→hard, fit≥90 exemption, retrospective hits); fit_score worked examples + synonym symmetry + determinism (md5 stable); jd_extract on Greenhouse/Ashby/JSON-LD/heading fixtures; parse_args grammar incl. `select` alias and fingerprint prefixes; report index round-trip; boards table parsing + URL rendering; apply_guard truth table (every gate false ⇒ deny); html2pdf smoke (skips if no browser; asserts page count + text round-trip).
- Manual acceptance: `/job-search setup` on a fresh checkout; `/job-search AI jobs in Reston, VA` interactive; `run_headless.py scan` from cron; `pick 1` dry-run apply proving the guard blocks submit.

## 14. Security & privacy

The public skill repo contains no personal data: the data home lives outside it by default, the repo's `.gitignore` and a `.githooks/pre-commit` hook block `resume/`, `config/profile.md`, `config/settings.local.yaml`, `config/browser-profile/`, `memory/`, `reports/`, `applications/` if someone points the data home at the repo. The data home is its own local git repo (auto-commit for diffable history) and `git push` is denied in headless settings. Example files in the repo use placeholder identities only. Notion receives summary fields only (no EEO answers, phone/address, salary constraints, screenshots). `bypassPermissions` is never used; headless runs use an explicit allowlist.
