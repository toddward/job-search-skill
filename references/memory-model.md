# Memory model

Everything the skill remembers lives under `$JOBSEARCH_HOME` (`common.data_home()`),
resolved from `--home`, then `$JOBSEARCH_HOME`, then `~/.config/job-search/home`, then
`~/job-search`. **Rules are evaluated by scripts, never by the model** — `jobs_db.py`,
`rank.py`, and `disinterest.py` are the only code paths allowed to decide eligibility,
cooldown, or suppression. The agent reads their output; it does not re-derive it.

## Layout

```text
$JOBSEARCH_HOME/
├── resume/                      # resume.md/.pdf/.txt (+ resume.url)
├── config/settings.toml         # committed, hand-authored (config.py)
├── config/settings.local.json   # machine-written overrides; git-ignored
├── memory/
│   ├── jobs.jsonl               # one JSON object per line, keyed by fingerprint
│   ├── disinterest.json         # {"rules": [...]}; hand-editable
│   ├── runs.jsonl                # one record per invocation
│   ├── jobs.badlines.jsonl      # quarantined corrupt lines (jobs_db.py)
│   └── logs/
├── reports/YYYY-MM-DD[.rN].md
└── applications/YYYY-MM-DD-<fp>/
```

`memory/` is a git repo; auto-commit at the end of a run
(`git -C memory add -A && git -C memory commit -q -m "job-search run <run_id>: ..."`),
never `git push`. `config/settings.local.json` and `applications/*/screenshots/` are
git-ignored. JSONL, not SQLite: diffable, greppable, survives one bad line instead of
one bad file.

## `memory/jobs.jsonl`

One line per fingerprint, `json.dumps(..., ensure_ascii=False, separators=(",", ":"))`,
fixed key order (`jobs_db.KEY_ORDER`), rows sorted by `(first_seen, fingerprint)`. Never
delete a row — an `expired` row is what stops a dead posting from being "discovered"
again. A hand-edit that breaks a line gets quarantined to `jobs.badlines.jsonl` on next
load; the run continues.

| Field | Type | Notes |
|---|---|---|
| `schema` | int | Always `1`. |
| `fingerprint` | str | 16-hex identity key; primary key of the file. |
| `title`, `company` | str | As posted. |
| `company_key`, `title_key` | str | Normalized, used for matching/dedup and disinterest rules. |
| `location`, `location_key` | str | Raw and normalized. |
| `remote` | str | `remote`/`hybrid`/`onsite`/`unknown`. |
| `url`, `canonical_url` | str | Original and tracking-param-stripped. |
| `source`, `sources[]` | str, array | Winning board and every posting seen (`source, url, canonical_url, posting_id, first_seen, last_seen`). |
| `posted_at`, `closes_at` | date or null | `YYYY-MM-DD`. |
| `comp_min`, `comp_max`, `comp_currency`, `comp_basis` | number/str or null | |
| `first_seen`, `last_seen` | datetime | RFC 3339 UTC `Z`. |
| `last_shown` | datetime or null | Set only when a report containing this job is written to disk. |
| `shown_count` | int | Increments with `last_shown`. |
| `snooze_until` | datetime or null | Hides without learning. |
| `status` | str | See Statuses below. |
| `status_changed_at`, `status_reason` | datetime, str or null | |
| `fit_score`, `adjusted_fit` | int 0–100 or null | Raw and (in ranked output) penalty-adjusted. |
| `fit_breakdown`, `fit_reasons` | object, array | From `fit_score.py`; `fit_breakdown.missing_must_haves` feeds the report. |
| `suppressed_by` | str or null | Disinterest rule id, if any. |
| `content_hash` | str or null | 16-hex hash of normalized JD text; repost detection. |
| `version` | int | Bumped on a materially-changed repost. |
| `application_dir`, `applied_at`, `submitted` | str/null, datetime/null, bool | |
| `notion_page_id`, `notion_synced_at` | str/null, datetime/null | |
| `run_ids` | array | Every run that touched this row. |
| `description_path` | str or null | Path to cached JD text. |
| `notes` | str | Free text. |

## Statuses and transitions

`new → shown → {selected, not_interested, expired}`; `selected → {applied,
needs_manual_apply, shown (decay)}`; `needs_manual_apply → {applied, not_interested}`.
`new` also reaches `new` again via a version bump (material repost). All transitions
are driven by `rank.py`/`jobs_db.py`, keyed on wall-clock UTC:

- **Cooldown, 14 days.** `shown`/`selected` is eligible to show again only when
  `now − last_shown ≥ 14d` (`memory.cooldown_days`). After `shown_count ≥ 3` with no
  action, the window extends to **45 days** (`extended_cooldown_days`) — repeated
  ignoring is a signal.
- **`applied`, `not_interested`, `expired`** are never re-listed.
- **`needs_manual_apply`** is exempt from cooldown — always listed in "Needs your
  decision" until resolved.
- **Selection decay.** `selected` with no `application_dir` for more than 7 days
  (`selection_expiry_days`) reverts to `shown`, `status_reason: "selection expired"`.
- **Expiry.** `closes_at` in the past, or `last_seen` more than 45 days ago
  (`expire_after_days`) with no `closes_at` → `expired`.
- **Version bump beats cooldown.** A materially changed repost (`content_hash`
  changes and `posted_at` moves forward) sets `status=new`, `last_shown=null`,
  `version += 1` — it re-enters the pool immediately regardless of cooldown.

## `memory/disinterest.json`

**JSON, not YAML** — `{"rules": [...]}`, read/written by `disinterest.load_rules` /
`save_rules`, hand-editable. Each rule: `{id: "dis-NNN", scope: title|company|location|
keyword|comp, pattern (regex, all scopes but comp) | min_base (comp), family,
strength: hard|soft, penalty (soft only), reason, created, created_by: user|
generalized, evidence: [fingerprint...], hits, promoted_from, promoted_on}`. `hard` →
job never shown; `soft` → `fit_score` penalty, still shown if it survives.

**Ladder on a `no`:** record the instance on the job row (permanent for that
fingerprint) → look up `title_key` in `references/title-families.md` (curated;
regexes are never model-invented) → first dismissal in a family → new `soft` rule,
penalty 20, `created_by: generalized` → second dismissal in the same family within 90
days → promote to `hard`, stamping `promoted_from`/`promoted_on`, appending both
fingerprints to `evidence`. Company- and comp-scope dismissals go straight to `hard`.
Auto-generalized rules never hide `fit ≥ 90` (routed to "Suppressed but high-fit"
instead); user-written rules have no such override. Every suppression the report shows
names its rule id and the `unhide` command; the rule's retrospective hit count is
printed at creation time. A headless dismissal with no reason creates **no** rule —
only records the instance and lists it under "Tell me why so I can learn".

## `memory/runs.jsonl`

One line per invocation, newest last. Example:

```json
{"run_id":"9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f","started_at":"2026-08-19T10:30:02Z","ended_at":"2026-08-19T10:41:30Z","mode":"headless","subcommand":"scan","query":"AI/ML architect, Reston VA + remote US","boards_attempted":11,"boards_ok":9,"boards_failed":[{"board":"indeed","reason":"403 from Firecrawl; Playwright fallback hit a captcha"}],"counts":{"seen":142,"new":17,"suppressed":38,"in_cooldown":24,"listed":12},"report":"reports/2026-08-19.md","cost_usd":2.86,"num_turns":74,"exit":"ok"}
```

`report.latest_report()` walks this file in reverse to resolve "the most recent report
whose file still exists" or a `run_id` prefix to its report path — never trust a report
file's mtime for that. `boards_failed` with a human-readable `reason` is what keeps a
silently shrinking result set visible in `git log` instead of hidden.
