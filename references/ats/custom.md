# Company-custom form

Used whenever detection confidence is `< 0.85` for every known vendor, or the final
URL/DOM matches none of them. Never guess a vendor adapter at low confidence — load
this note instead, and be more conservative than any researched vendor above.

## Recognize
Company domain remains final. Inspect `form[action]`, iframes, scripts, XHR,
`application/ld+json` `JobPosting`, headings, and accessible labels. Re-run detection
after every Apply redirect — a custom shell around a known ATS should be classified by
the application's actual destination, not by the shell page's branding.

## Posting API
No generic API. Prefer a documented company jobs feed or the page's own
`application/ld+json`; otherwise scrape the public posting via the layered search
strategy. Any runtime XHR observed is evidence only, not a stable contract, unless the
company documents it. `api_kind: undocumented`.

## Form shape
Unknown until inspected — could be a single native form, a multi-step SPA, an email
link, a third-party assessment, or an embedded (unrecognized) ATS. Résumé input may be
a normal `input[type=file]`, a drag/drop control, or absent entirely. EEO may be
absent or independently hosted. Match employer questions through the taxonomy in
`apply-flow.md`; a low-confidence field mapping is flagged, never filled.

## Intermediate controls
Whatever the page labels Next/Continue/Save — validate before advancing, never press
Enter, re-snapshot after each step.

## Final controls
`submit application`, `send application`, `complete application`, `apply` — all three
required together before treating one as final: (1) inside the candidate form, (2) no
remaining intermediate control, and (3) either a review/final heading or a
form-submission action observed. Otherwise block as unknown and route to
`needs_manual_apply`.

## Signals
Unknown until inspected: reCAPTCHA, hCaptcha, Cloudflare Turnstile/challenge pages,
Arkose, email/SMS OTP, WAF, or custom honeypots are all possible. Detect and stop —
never interact with a honeypot field or attempt to bypass a control.

## manual_only: false

(Not ToS-restricted by default, but the low-confidence/no-known-adapter posture means
almost every ambiguous signal should route to `review` or `needs_manual_apply` rather
than proceeding.)

## last_verified: 2026-08-19

## Sources
- docs/research/ats-autoapply.md ("ATS landscape → Company-custom form" row)
