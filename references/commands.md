# Command grammar

`scripts/parse_args.py` turns `$ARGUMENTS` into `{command, numbers, reason, flags, query, url}`.
Free text with no recognized leading verb is `scan` with that text as `query`. All flags are
`--name` or `--name value`; a `--name` not in the value-flag set is boolean.

| Command | Syntax | Flags | Semantics |
|---|---|---|---|
| *(free text)* | `<query text>` | `--home`, `--headless`, `--json`, `--max` | Same as `scan --query "<text>"`. |
| `scan` | `scan [query]` | `--query`, `--home`, `--headless`, `--json`, `--max` | Crawl boards, score, rank, write a report (§2 of `SKILL.md`). |
| `setup` | `setup` | `--home` | Bootstrap config/dirs, register Firecrawl MCP, print `doctor.py` table. |
| `pick` | `pick N[,N…]` | `--note`, `--apply`, `--no-tailor`, `--from`, `--run`, `--home` | Resolve numbers to jobs, tailor résumé/cover letter/diff, stop before filling unless `--apply`. |
| `apply` | `apply N[,N…]` \| `apply <url>` | `--note`, `--no-tailor`, `--from`, `--run`, `--home` | Same as `pick`, then continues into §4 (Playwright fill; never submits without the guard). A bare URL is scored and treated as one pick. |
| `no` | `no N "reason"` | `--reason` | Mark `not_interested`, call `disinterest.py learn`, show what was learned. No reason (headless) ⇒ status set, no rule. |
| `snooze` | `snooze N <duration>` | — | Hide job N until `<duration>` elapses (e.g. `30d`); no learning. |
| `show` | `show N` | — | Print the JD, fit breakdown, and `diff.md` if an application dir exists. |
| `status` | `status` | — | Status counts, active disinterest rules, last 5 runs, calibration hint at ≥30 labels. |
| `unhide` | `unhide dis-00N` | `--to soft\|hard` | Remove or soften a learned rule (default: delete). |
| `submit` | `submit N --i-mean-it` | `--i-mean-it` | Re-enter §4 for an already-filled job; `--i-mean-it` overrides only `auto_submit`/`submit_threshold`/per-run cap — never CAPTCHA, unreviewed answers, or a posting mismatch. |
| `help` | `help` | — | Print this grammar. Also the fallback for unrecognized input. |

## The `select` → `pick` note

`parse_args.py` accepts `select` as an alias and normalizes it to `pick` internally, but
**never type `select`**. Claude Code's own argument tokenizer treats a leading `select` token as
a shell `select NAME in …` compound and swallows it plus the next token before `$ARGUMENTS` is
even assembled (see `references/headless.md`, "verified gotchas"). By the time `parse_args.py`
would see `select`, the damage is already done. Always use `pick`.

## Number resolution

`report.py resolve` turns what a user types (`1`, `1,3`, a bare fingerprint, or any unique ≥6-hex
prefix of one) into `{n, fp, title, company}` pairs:

1. **`--run <id>`** — look up that run's report via `memory/runs.jsonl` (a prefix of the id
   works); highest priority when given.
2. **`--from <date>`** — otherwise, the newest report for that date (`<date>.md`, or the
   highest-numbered `<date>.rN.md` from a same-day re-run).
3. **Neither given** — the most recent run in `memory/runs.jsonl` whose report file still exists
   on disk.

A token that is not a table number is tried as a fingerprint or fingerprint prefix via
`jobs_db.find()`; prefixes shorter than 6 hex characters are never accepted (ambiguity risk). An
index whose `generated_at` is **more than 14 days** before now is refused outright — `resolve`
raises rather than silently resolving a number against a list the user can no longer see
correctly. A token matching nothing raises a clear "not a number nor a known fingerprint" error,
relayed to the user verbatim.

## Worked examples

**1. Free-text scan**

```
/job-search AI/ML architect jobs in Reston VA
```
→ `{command: scan, query: "AI/ML architect jobs in Reston VA"}`. Runs the full §2 pipeline and
prints the ranked report with the `Reply with` cheat sheet at the bottom.

**2. Tailor two picks with guidance**

```
/job-search pick 1,3 --note "emphasize K8s"
```
→ `{command: pick, numbers: [1, 3], flags: {note: "emphasize K8s"}}`. Resolves #1 and #3 against
the current report, marks both `selected`, and writes `resume.md`/`cover-letter.md`/`diff.md`
per job with the Kubernetes-relevant bullets and skills led to the front (see
`references/tailoring.md`). Stops before opening a browser — no `--apply`.

**3. Dismiss with a reason (and learn)**

```
/job-search no 5 "too sales-heavy"
```
→ `{command: no, numbers: [5], reason: "too sales-heavy"}`. Sets job #5 to `not_interested`
and runs `disinterest.py learn`, which prints something like:

```
Learned: dis-004 Sales Engineering is now SOFT (-20 fit). Second dismissal within 90 days makes it HARD.
  Undo: /job-search unhide dis-004
```

That message — rule id, what changed, and the undo command — is shown to the user verbatim, and
the next report's "Learned today" section repeats it.
