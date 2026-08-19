# Report format

`scripts/report.py` renders every report; the skill never hand-writes report markdown.
Call `render()`/`write()` and print/relay the result — do not reformat or re-summarize
it in prose. This document is the skeleton those functions produce, plus the rules
that keep `reports/YYYY-MM-DD.md` and `memory/jobs.jsonl` honest with each other.

## Skeleton (top to bottom)

```markdown
# Job search — 2026-08-19 · run 9f1c2d3e · 142 seen, 17 new, 38 suppressed, 24 in cooldown, 12 listed

Query: AI/ML architect, Reston VA + remote US
Boards failed: Indeed (captcha); Dice (MCP tool timeout after 600000ms)

## Top matches

| # | fit | role | company | location | comp | posted | source | link |
|---|---|---|---|---|---|---|---|---|
| 1 | 91 | Staff AI Solutions Architect | Anthropic | Reston, VA | $215–270k | 2026-08-17 | greenhouse | https://... |

- **#1 Staff AI Solutions Architect @ Anthropic** — why: 8 yrs enterprise AI architecture matches 'staff' scope; Reston HQ is 6 mi from home; resume lists vLLM + OpenShift AI · missing must-haves: none

## Needs your decision

- M1 ML Engineer II @ Capital One — ATS blocked at SMS verification — https://...

## Suppressed but high-fit

- S1 93 Solutions Architect, AI Infrastructure @ NVIDIA — rule dis-002 (undo: /job-search unhide dis-002)

## Learned today

- dis-002 sales-engineering promoted to hard (2nd dismissal in 90d)

## Tell me why so I can learn

- #9 Data Engineer @ Foo — dismissed without reason (headless)

## Reply with

```
apply 1,3        tailor + fill applications (stops before submit)
no 5 "reason"    not interested, and learn from it
snooze 7 30d     hide #7 for 30 days
show 1           full JD, fit breakdown, tailored-resume diff
```

## Index (machine-readable — do not edit)

```json job-index
{"run_id":"9f1c2d3e-...","date":"2026-08-19","generated_at":"2026-08-19T10:33:12Z",
 "items":[{"n":1,"fp":"b7f3c1a9d2e40185","title":"Staff AI Solutions Architect","company":"Anthropic","fit":91,"url":"https://..."}],
 "manual":[{"n":"M1","fp":"5d0aa38f91c7e462"}],
 "suppressed":[{"n":"S1","fp":"77e2b1c40a9d3f18","rule":"dis-002"}]}
```
```

## Section rules

- **Title line.** Always present: date, first 8 hex chars of `run_id`, and the five
  counts from `result["counts"]` in the fixed order `seen, new, suppressed,
  in cooldown, listed`. Query line and boards-failed line are each printed only when
  non-empty — a clean run has neither.
- **Top matches table.** Columns are fixed and exactly `# | fit | role | company |
  location | comp | posted | source | link`. `fit` is `adjusted_fit` (penalty already
  applied), never the raw `fit_score`. `comp` renders `$min–maxk`, `up to $maxk` when
  only a ceiling exists, or `not listed` — never a blank cell. `#` is the row's
  position in `result["ranked"]`, 1-based, and is also the number the user types back.
- **Per-row sub-bullets** follow the table, one per ranked job, in the same order:
  `why` is up to 3 items from `fit_reasons` joined with `; ` (never invent reasons not
  in that list); `missing must-haves` lists up to 4 entries from
  `fit_breakdown.missing_must_haves`, or the literal word `none`. If the job carries a
  disinterest `penalty`, append `· penalty −N (rule_id)` — a suppressed-but-shown job
  must never look identical to a clean one.
- **Needs your decision** lists every item in `result["manual"]` (status
  `needs_manual_apply`), numbered `M1, M2, …`. This section is omitted entirely when
  `manual` is empty — never print an empty heading. These rows are exempt from
  cooldown and reappear on every report until the user resolves them.
- **Suppressed but high-fit** lists `result["suppressed_high_fit"]` (auto-generalized
  rules never hide `fit ≥ 90`), numbered `S1, S2, …`, each naming the rule id and the
  `unhide` command. Omitted when empty.
- **Learned today / Tell me why so I can learn** are populated by the caller
  (`learned`/`decisions` args to `render()`), not derived from `result` — the scan/pick
  commands pass what they actually learned or need explained. Both omitted when empty.
- **Reply with** is a fixed, literal help block — do not localize or shorten it; it is
  the user's cheat sheet for the command grammar in `references/` command docs.

## The `job-index` block

The single source of truth for turning what a human typed back (`apply 1,3`, `no 5`)
into fingerprints, including in a brand-new session with no memory of the list. Always
the last thing in the file, fenced exactly as ` ```json job-index ` … ` ``` ` so
`report.INDEX_RE` finds it. Never hand-edit a report file — the heading above the
fence says so for a reason.

Schema: `{run_id, date, generated_at, items: [{n, fp, title, company, fit, url}],
manual: [{n, fp}], suppressed: [{n, fp, rule}]}`. `items[].n` is an int matching the
table row; `manual[].n` / `suppressed[].n` are the strings `"M1"`/`"S1"` etc. Load it
with `report.load_index(path)` (or `load_index_text(md)` on an in-memory string) and
resolve user tokens with `report.resolve_numbers(tokens, index, db)`, which also
accepts a bare fingerprint or any unique ≥6-hex prefix of one, anywhere a number is
valid — so `no b7f3c1` works even with no report open.

## State rules tying reports to `jobs.jsonl`

- **`last_shown` is set only after the report file exists on disk.** `write()` calls
  `db.mark_shown(...)` and `db.save()` *after* `atomic_write()` succeeds, in the same
  call — scoring or ranking a job never marks it shown; only a report the user could
  actually have read does. This is what makes the 14-day cooldown honest.
- **Same-day re-runs version.** `write(home, date, run, result, db=db)` writes
  `reports/<date>.md` the first time. A second call for the same `date` with a
  **different** `run_id` writes `<date>.r2.md`, then `.r3.md`, and so on — it never
  overwrites another run's report. A retry of the *same* `run_id` (matched by reading
  the existing file's own `job-index.run_id`) reuses that file instead of minting a
  new version.
- **`latest_report(home, date=None, run_id=None)`** resolves "which report was that":
  pass `run_id` (a prefix is fine) to look it up via `memory/runs.jsonl`; pass `date`
  to get the highest-numbered file for that day; pass neither to get the most recent
  run in `runs.jsonl` whose report file still exists on disk.
- **`resolve_numbers(tokens, index, db, now=None)` refuses a stale index**: if
  `index["generated_at"]` is more than 14 days before `now`, it raises `ValueError`
  rather than resolve a number — a two-week-old list is exactly the situation where a
  remembered "#3" no longer means what the user thinks it means. It also raises
  `ValueError` (not `KeyError`/`IndexError`) with a clear message for a token that
  matches nothing, so the caller can relay it verbatim to the user.
- Every `write()` call appends one line to `memory/runs.jsonl` via `append_run()`,
  including the report's path relative to `home` and the run's `counts` — that line,
  not the report file's mtime, is what `latest_report()` trusts.
