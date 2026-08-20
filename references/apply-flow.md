# Apply flow

Filling and submitting an ATS application is the one place this skill touches a real
world side effect it cannot undo. Two rules govern everything below: **the model fills,
a deterministic script decides whether to submit**, and **`auto_submit` defaults to
`false`** — every run ends in `review` unless the user opted in.

The model cannot enable `auto_submit`: only the human edits `config/settings.toml`.
`config.py set-local` refuses any `apply.*` key (exit 2, `refused: apply.* is
hand-edited in settings.toml only`), so nothing the skill can call reaches the submit
gate — not `auto_submit`, `submit_threshold`, or `max_submits_per_run`.

## State machine

```text
draft -> filled | needs_manual_apply
filled -> review | needs_manual_apply
review -> submitted | needs_manual_apply
needs_manual_apply -> filled | review | submitted   (only after the user resumes)
```

- **`draft`** — tailored résumé/cover letter exist; posting fingerprint, apply URL,
  adapter/version, fit score, and document hashes are recorded in `application.json`.
- **`filled`** — every unambiguous field on the current form has been filled and
  re-read from a fresh snapshot. This is not a claim that required questions are
  resolved.
- **`review`** — the final boundary was reached, or any AI-drafted / user-only answer
  / consent still needs a human. This is the normal terminal state when
  `apply.auto_submit` is `false`.
- **`submitted`** — only after `apply_guard.py decide` returned `allow: true` *and* a
  positive confirmation (page text or application ID) was observed post-click. Never
  infer submission from an HTTP 200 or a button disappearing.
- **`needs_manual_apply`** — CAPTCHA/challenge, login/MFA/OTP, `manual_only` adapter,
  inaccessible/cross-origin control, unsupported widget, session/rate block, closed
  posting, or an unresolved required fact. Record `reason_code` and preserve the tab.

Never transition backward by overwriting history — append events; a republished
posting gets a new version but keeps the original fingerprint link.

## Launching the browser (Playwright MCP)

Headed by default, one dedicated persistent profile, never the user's everyday Chrome.
**The fill process must not own the Chrome process.** A child Chrome dies when the
fill script or MCP session ends, which is exactly when the user needs the filled
form still on screen.

1. `python3 ${CLAUDE_SKILL_DIR}/scripts/chrome_keep.py ensure` → `{endpoint, launched}`.
   It reuses `apply.cdp_endpoint` if that port is already up, otherwise starts Chrome
   on port 9223 with `--user-data-dir=$JOBSEARCH_HOME/config/browser-profile`,
   `--remote-debugging-port`, and `start_new_session=True` so a wrapper timeout cannot
   take Chrome down.
2. Attach Playwright (MCP or Python) over CDP. Never
   `launch_persistent_context` / `browser.launch` as a child of the fill process.
   ```sh
   npx -y @playwright/mcp@latest \
     --browser=chrome \
     --cdp-endpoint <endpoint from chrome_keep> \
     --output-dir="$JOBSEARCH_HOME/applications/_artifacts" \
     --save-session
   ```
3. One new tab per application (`browser_tabs new` / `context.new_page`). Never reuse
   a snapshot ref across a navigation, SPA rerender, or file-parse event — re-snapshot
   instead.

**After fill, never close the headed browser.** No `browser.close()`, no
`browser_close`, no killing the Chrome PID, no letting a `with sync_playwright()`
block call `close()` on a browser it launched. Disconnect Playwright if you must;
leave the tab on the filled form so the user can verify and click Submit. Tell them
the window is still up. `auto_submit=false` (the default) makes this the normal
stop: the form is filled, the guard denies submit, the tab stays.

- **Headless only** when `JOBSEARCH_BROWSER_MODE=headless` is set (a headless Linux
  host): `config.load()` applies that env override as `apply.browser_mode =
  "headless"`, so read the mode off the loaded config rather than the environment. In that mode every headed-only ATS (Workday, Taleo, iCIMS, anything with
  login/MFA) is downgraded straight to `needs_manual_apply` with
  `reason_code: headed_session_required` — headless never attempts login-walled fill
  and never calls `chrome_keep.py` (it is headed-only).
- `apply.cdp_endpoint` (e.g. `http://localhost:9223`) still attaches to a Chrome the
  user already started; `chrome_keep.py` will not spawn a second one if that port is
  live. Never close that Chrome either.

## Fill procedure

1. **Detect** the adapter (URL/DOM signatures) and load exactly one
   `references/ats/<vendor>.md`, then any learned note at
   `memory/ats-learned/<host>.md` (see below). Confidence `< 0.85` → treat as `custom`.
2. **`browser_snapshot`** — the accessibility tree is the action source; screenshots
   are evidence only, never used to locate a control.
3. **Map fields** from `config/profile.md` (canonical identity/links/authorization/
   sponsorship/relocation/salary/start-date/self-ID schema) and the parsed résumé to
   the form's accessible labels, using the vendor note's label aliases.
4. **`browser_fill_form`** for the batch of text/checkbox/combobox fields, then
   snapshot again and diff actual values against what was sent.
5. **`browser_file_upload`** with the absolute path to the tailored PDF for any
   résumé/cover-letter control; re-snapshot after parsing and reconcile any field the
   parser silently overwrote (name, email, phone, employer, dates).
6. For each answered or flagged question, append an entry to `answers.json`:
   `{question, answer, source: profile|resume|ai_draft, needs_review}`.
7. **Screenshot** after every meaningful step into
   `applications/<YYYY-MM-DD>-<fingerprint>/evidence/`.
8. On an intermediate **Next/Continue/Save** control: validate first, click only its
   current ref, wait for the heading/progress indicator to change, snapshot again.
   Never press Enter to advance.
9. **Before building `state.json`**, run the canary/injection check on every
   AI-generated text block (cover letter, drafted answers):
   ```sh
   python3 ${CLAUDE_SKILL_DIR}/scripts/canary_check.py \
     --generated cover-letter.md --jd job.md \
     --master resume/master.md --profile config/profile.md
   ```
   Exit `0` → set `canary_ok: true` in state; exit `3` (suspects or injected phrases
   found) → `canary_ok: false`, which the guard below denies unconditionally.

## HARD RULE — the submit boundary

Before clicking any control whose accessible name matches the adapter's `Final
controls`, run:

```sh
python3 ${CLAUDE_SKILL_DIR}/scripts/apply_guard.py decide \
  --state-json state.json --run <run_id> [--i-mean-it]
```

Exit `0` = `allow: true` — click only on that result. Exit `3` = deny, for **any**
failed gate, any malformed/uncoercible field (e.g. a stringly `fit_score`), or a
malformed/unreadable `state.json` or unexpected internal failure (denied as
`bad_state`, never a traceback — the CLI wraps the whole decision in one handler so no
input can ever crash the guard). Any exit other than `0` means: set state `review` or
`needs_manual_apply` and stop; never bypass via Enter, JS, or another selector.

**`decide` always runs before `reserve`.** Its cap gate (`submits_this_run`) only
reflects reservations *already completed* earlier in this run — it never counts the
in-flight one — so `decide: allow` is a pre-flight check, not the atomic claim.
`reserve` is the atomic operation that actually claims the slot for the current
application, and it must independently succeed (it re-verifies the cap itself) before
the control is clicked; under concurrent runs a `decide: allow` does not guarantee a
following `reserve` will also succeed.

```sh
python3 ${CLAUDE_SKILL_DIR}/scripts/apply_guard.py reserve --run <run_id> --fp <fp>
# {"reserved": true, "nonce": "<nonce>"} — capture the nonce for a precise release later
# only if reserve printed reserved:true AND decide printed allow:true, click the control
python3 ${CLAUDE_SKILL_DIR}/scripts/apply_guard.py record --run <run_id> --fp <fp> --submitted
```

If `reserve` returns `reserved: false`, or `decide` denies *after* a successful
`reserve`, or the post-click confirmation never appears, release the slot instead of
recording a submit — the per-run cap counts **active reservations net of releases**,
not raw click attempts or lifetime history, so a released slot becomes available again
for a later application in the same run:

```sh
python3 ${CLAUDE_SKILL_DIR}/scripts/apply_guard.py release --run <run_id> --fp <fp> --nonce <nonce>
# --nonce may be omitted: it falls back to releasing the newest unreleased reservation
# for that --fp, for a caller that did not retain the nonce from `reserve`
```

This is not a prose reminder — the fill worker must not have `browser_run_code_unsafe`
or arbitrary-JS access during an application session, `browser_type` must always be
called with `submit: false`, and any `type=submit` control, Enter-in-form keystroke,
or unrecognized/ambiguous control is a **block candidate**, routed through the guard
exactly like a known final control. A fit score never overrides a question/consent/
platform-policy failure; `--i-mean-it` overrides only `auto_submit`, `submit_threshold`,
and the per-run cap.

## Screening-question taxonomy

| Category | Policy |
|---|---|
| Contact/links, exact résumé facts (title, dates, degree) | **safe-from-profile** — auto-fill from `profile.md`/résumé, no review |
| Work authorization/sponsorship for a named country, clearance, age, license | **safe-from-profile only when the profile has an explicit, current, exactly-scoped fact**; `unknown` → flag |
| Location/schedule/travel/relocation/start date matching an approved preference | **safe-from-profile** |
| Salary, "years of X", proficiency, motivation, behavioral/free-response | **ai_draft** — generated from posting + résumé, `needs_review: true`, evidence cited |
| Knockout qualifications (degree/clearance/license/shift/travel) | exact fact only; any interpretation → flag, never optimize for passing |
| Employment gaps, terminations, conflicts, background/criminal, EEO/self-ID, pronouns, e-signature/consent/attestation, "did you use AI" | **must be answered by the user** — never auto-filled or AI-drafted |

A required question left `unknown`, unrecognized, or with an unverifiable selected
value moves the application to `review`; it is never silently skipped or guessed.

## Evidence manifest

At the stop point (final boundary, or any `needs_manual_apply`), write into
`applications/<YYYY-MM-DD>-<fingerprint>/evidence/`:

- `<ts>-review.md` — the `browser_snapshot` at the stop point
- `<ts>-pre-submit.png` — full-page screenshot (`scale: "css"`)
- `<ts>-manifest.json` — final URL, platform/detection evidence, posting ID, page
  title, UTC timestamp, tailored-résumé SHA-256, filled/unfilled/flagged field IDs,
  final-control accessible name, state
- `<ts>-confirmation.png` — only after a guarded submit's positive confirmation

Redact EEO/disability/veteran/salary/phone/email/passwords/tokens from the manifest
and snapshot where feasible. Screenshots contain PII: keep local, `0600`, never
mirrored to Notion.

## Learned notes

After a successful fill on a `custom`/unrecognized form, write what worked to
`memory/ats-learned/<host>.md` (same section shape as a vendor note: Recognize, Form
shape, Final controls, Signals) so the next visit to that host skips re-discovery.
Never write a learned note from a failed or partial fill.

## Manual-only platforms

`linkedin-easy-apply` and `indeed-apply` are `manual_only: true` regardless of
`auto_submit` (platform ToS prohibit automating their apply flow). The skill may
record the posting and open the URL for the user; it must not fill, click, or
simulate submission there.

This is enforced on the adapter **name**, not on the `adapter_manual_only` flag the
caller passes: `apply_guard.MANUAL_ONLY_ADAPTERS` (`linkedin-easy-apply`,
`indeed-apply`, `linkedin`, `indeed`) denies with `manual_only` even when the state
file claims `adapter_manual_only: false`, and `--i-mean-it` does not reopen it.

## `jobs.jsonl` write-back

On any state change, update the job's row: `status` (`applied` only after
`submitted`), `application_dir`, `applied_at` (UTC, only on `submitted`), `submitted`
(bool). Mirror only non-sensitive summary fields to Notion — never browser state,
full answers, EEO data, screenshots, or salary constraints.
