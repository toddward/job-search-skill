# Apply flow

Filling and submitting an ATS application is the one place this skill touches a real
world side effect it cannot undo. Two rules govern everything below: **the model fills,
a deterministic script decides whether to submit**, and **`auto_submit` defaults to
`false`** — every run ends in `review` unless the user opted in.

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

Headed by default, one dedicated persistent profile, never the user's everyday Chrome:

```sh
npx -y @playwright/mcp@latest \
  --browser=chrome \
  --user-data-dir="$JOBSEARCH_HOME/config/browser-profile" \
  --output-dir="$JOBSEARCH_HOME/applications/_artifacts" \
  --save-session
```

- **`--cdp-endpoint`** attaches to an already-running Chrome started with
  `--remote-debugging-port` instead of launching a new one — use it when the user
  wants to drive their own logged-in browser (`apply.cdp_endpoint` in config).
- **Headless only** when `JOBSEARCH_BROWSER_MODE=headless` is set (a headless Linux
  host). In that mode every headed-only ATS (Workday, Taleo, iCIMS, anything with
  login/MFA) is downgraded straight to `needs_manual_apply` with
  `reason_code: headed_session_required` — headless never attempts login-walled fill.
- One tab per application via `browser_tabs`; never reuse a snapshot ref across a
  navigation, SPA rerender, or file-parse event — re-snapshot instead.

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
7. **Screenshot** after every meaningful step into `applications/<fingerprint>/evidence/`.
8. On an intermediate **Next/Continue/Save** control: validate first, click only its
   current ref, wait for the heading/progress indicator to change, snapshot again.
   Never press Enter to advance.

## HARD RULE — the submit boundary

Before clicking any control whose accessible name matches the adapter's `Final
controls`, run `scripts/apply_guard.py decide` with the current state JSON; click
only on `allow: true`; otherwise set state `review` or `needs_manual_apply` and stop;
never bypass via Enter, JS, or another selector.

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
`applications/<fingerprint>/evidence/`:

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

## `jobs.jsonl` write-back

On any state change, update the job's row: `status` (`applied` only after
`submitted`), `application_dir`, `applied_at` (UTC, only on `submitted`), `submitted`
(bool). Mirror only non-sensitive summary fields to Notion — never browser state,
full answers, EEO data, screenshots, or salary constraints.
