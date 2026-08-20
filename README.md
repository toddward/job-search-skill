# job-search — a Claude Code skill

Resume-aware job discovery, deterministic ranking, tailored applications, and a guarded
auto-apply flow, driven from `/job-search` inside Claude Code.

## What it does

- **Scans** job boards/aggregators for roles matching your resume and search config
  (`references/search-strategy.md`), via `WebFetch`, the Firecrawl MCP/CLI, and Playwright as a
  last resort.
- **Scores** every job with a deterministic, reproducible fit rubric (`scripts/fit_score.py`,
  `references/scoring-rubric.md`) — the model never invents the number.
- **Ranks and reports** into `reports/YYYY-MM-DD.md` with a machine-readable index so you can
  reply `pick 1,3`, `no 5 "reason"`, `snooze 7 30d`, `show 1` in plain text.
- **Remembers** what you've seen, dismissed, or applied to — a 14-day cooldown, a learned
  disinterest ladder (soft → hard after a repeat dismissal), never re-showing `applied`/
  `not_interested`/`expired` jobs (`references/memory-model.md`).
- **Tailors** a resume + cover letter per selected job — truthful bullet selection/reordering,
  keyword mirroring only where earned, a reviewable diff — and renders both to ATS-safe PDF
  (`references/tailoring.md`).
- **Fills applications** via the Playwright MCP, screenshotting every step, and **never clicks a
  final submit control** without a deterministic guard decision (`references/apply-flow.md`).
- **Mirrors to Notion** (optional) — summary fields only, never EEO answers, screenshots, or
  contact details (`references/notion-mirror.md`).
- **Runs headless** from cron/launchd/systemd for scheduled scans (`references/headless.md`).

## Install

As a plugin, from this repo's marketplace (`.claude-plugin/marketplace.json`) — the route to use
when adding the skill to a harness or sharing it with a team:

```sh
claude plugin marketplace add toddward/job-search-skill
claude plugin install job-search@job-search-skill
```

`claude plugin marketplace add` also accepts a local checkout path, which is handy while
developing. Or install it as a plain skill directory:

```sh
git clone https://github.com/toddward/job-search-skill ~/.claude/skills/job-search
```

Or symlink an existing checkout:

```sh
ln -s /path/to/job-search-skill ~/.claude/skills/job-search
```

Either way the skill is the repo root: `.claude-plugin/plugin.json` declares `"skills": ["./"]`,
so `SKILL.md`, `scripts/`, `references/`, and `assets/` are the same files in both layouts.

Contributors — enable the pre-commit hook that blocks personal data (resume, profile, browser
profile, memory, applications) from ever being committed to this repo:

```sh
git config core.hooksPath .githooks
```

The skill's own data (resume, config, memory, reports, applications) lives outside the repo by
default, in a separate **data home** — see "Data home" below.

## Requirements

| | macOS | Linux |
|---|---|---|
| Python | ≥ 3.11 | ≥ 3.11 |
| Browser | Google Chrome, or `npx playwright install chromium` | Chromium (`apt`/`dnf`), or `npx playwright install --with-deps chromium` |
| PDF text extraction | `brew install poppler` | `apt-get install poppler-utils` / `dnf install poppler-utils` |
| Fonts | built in | `fonts-liberation fonts-dejavu-core` (or `liberation-fonts dejavu-sans-fonts`) — page counts drift without these |
| Node / npx | required (Playwright MCP, Firecrawl MCP) | required |
| Claude Code | with the Playwright MCP/plugin registered | same |
| Firecrawl | CLI (`npm i -g firecrawl-cli && firecrawl login`) and/or MCP | same |
| Notion | optional — MCP, authorized once via `/mcp` | same |

Run `python3 scripts/doctor.py` (or `/job-search setup`) any time to check all of the above and
get exact per-OS fix commands for whatever's missing.

## Quick start

```
/job-search setup
```
Bootstraps `config/`, registers the Firecrawl MCP, and tells you what's still missing — usually
just dropping a resume (PDF/Markdown/text) into `resume/`, or pointing `scoring.resume_url` at a
hosted one, then editing `config/profile.md` and `config/cover-letter-style.md`. Every scan
regenerates `resume/master.md` from that source document, so keep editing the source — a
hand-edit to `master.md` is overwritten the next time the source changes.

```
/job-search AI jobs in Reston, VA
```
Scans, scores, ranks, and prints a report with numbered rows.

```
/job-search pick 1,3
```
Resolves #1 and #3, writes tailored `resume.md`/`cover-letter.md`/`diff.md` + PDFs into
`applications/<date>-<fp>/`, and stops for your review — nothing is filled or submitted yet.

```
/job-search apply 1,3
```
Same tailoring, then opens a Playwright browser tab per job and fills what it can. It **stops
before the final submit control** unless `apply.auto_submit` is true and the deterministic guard
allows it for that job and run.

## Headless / scheduled runs

```sh
python3 scripts/run_headless.py scan
```
is the one entrypoint every scheduler calls — it takes a single-flight lock, invokes
`claude -p "/job-search scan --headless --run <uuid>"` with a locked-down permission mode and
MCP config, and exits non-zero on failure so cron/launchd/systemd's own alerting works. Copy a
template from `assets/schedulers/` (`crontab.txt`, `launchd.plist` for macOS, `job-search.service`
+ `job-search.timer` for Linux systemd), fill in the `{{HOME}}`/`{{SKILL}}`/`{{HOME_DIR}}`
tokens, and install it with the OS scheduler. Full details, gotchas (the `select`-vs-`pick`
tokenizer bug, the `$`-in-injection abort, idempotence, headless-Linux browser downgrade) in
`references/headless.md`.

## Safety model

- **`apply.auto_submit` defaults to `false`.** Every application stops at `review` unless you
  opt in; `--i-mean-it` on a single `submit` command overrides only `auto_submit`,
  `submit_threshold`, and the per-run cap — never CAPTCHA, an unreviewed AI-drafted answer, or a
  posting-identity mismatch.
- **A deterministic script decides, the model only fills.** `scripts/apply_guard.py` is the sole
  gate on any final-submit click; the model text can never bypass it via Enter, JS, or another
  selector (`references/apply-flow.md`).
- **Manual-only platforms.** LinkedIn Easy Apply and Indeed Apply are never filled or clicked —
  their ToS prohibit automation; the skill records the posting and links it for you.
- **Prompt-injection defense.** Job descriptions, board pages, and form labels are treated as
  untrusted data, never instructions. `scripts/canary_check.py` blocks upload/submit if generated
  text contains a token pulled from the JD that isn't grounded in your resume/profile.
- **Privacy.** Your resume, profile, browser session, screenshots, and full screening answers
  never leave your machine except to the job boards/ATSes you're actually applying to. Notion
  (if enabled) receives summary fields only — never EEO answers, phone/address, salary
  constraints, or screenshots.

## Data home

The skill directory itself is stateless — it can be deleted, re-downloaded, or updated at any
time without losing anything. Your state lives in a **data home**, resolved in order:

1. `--home <dir>` on any script call
2. `$JOBSEARCH_HOME`
3. the pointer file `$XDG_CONFIG_HOME/job-search/home` (default `~/.config/job-search/home`) —
   one line naming your chosen directory, written by `doctor.py bootstrap` on first setup
4. `~/job-search`

On a fresh install, `/job-search setup` announces where the data home will be created and asks
before defaulting to `~/job-search`; scripts print the resolved home and its source
(`doctor.py` shows `<path> (via pointer)` etc.), so where state lives is never a surprise.
Kept separate from this repo so a public checkout of the skill never carries your personal data.

```text
$JOBSEARCH_HOME/
├── resume/              # your resume (PDF/MD/DOCX) + master.md, generated from it
├── config/               # settings.toml (committed), profile.md, cover-letter-style.md, browser-profile/
├── memory/               # jobs.jsonl, disinterest.json, runs.jsonl — its own git repo, auto-committed, never pushed
├── reports/YYYY-MM-DD.md
└── applications/YYYY-MM-DD-<fp>/
```

Full schema and lifecycle rules: `references/memory-model.md`.

## Design docs

- Spec: `docs/superpowers/specs/2026-08-19-job-search-skill-design.md`
- Plan: `docs/superpowers/plans/2026-08-19-job-search-skill.md`
- Research (resume tailoring, fit scoring, PDF generation, cross-platform notes):
  `docs/research/resume-tailoring.md`

## License

MIT — see `LICENSE`. Example files under `assets/` use placeholder identities only.
