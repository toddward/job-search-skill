# Greenhouse

## Recognize
`job-boards.greenhouse.io/{board}/jobs/{job_id}` (current) or legacy
`boards.greenhouse.io/{board}/jobs/{job_id}`, including as an iframe/resource src on a
branded careers page. Corroborating signals: `#application_form`,
`job_application[...]` input names, "Powered by Greenhouse" footer text.

## Posting API
`GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true`
— public, unauthenticated, `api_kind: public_posting_read_only`. Returns custom,
location, compliance, and demographic question definitions. The application `POST`
exists but needs the employer's secret Job Board API key — not an applicant route.

## Form shape
Usually one long page: First Name, Last Name, Email, Phone, Location (City), résumé/
cover-letter file inputs, employer-defined custom questions, consent, then an optional
EEO/demographic block. Link labels: `LinkedIn Profile`, `Website`, `Portfolio`, custom
`GitHub`. Authorization/sponsorship/relocation/salary/start-date are usually custom
free-text/select questions, not a fixed schema — map by normalized full question text.

## Intermediate controls
None typical — usually a single scrollable page (rare multi-page tenants use their own
Next/Continue labels; treat unrecognized labels as intermediate, never final).

## Final controls
`submit application`, `submit`. Context: application form plus identity/résumé/
questions visible, not a newsletter/contact form elsewhere on the page.

## Signals
Documented invisible Google reCAPTCHA on the career-page integration, sometimes with
email-code verification depending on risk/employer sensitivity. Any visible challenge
→ `needs_manual_apply`.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://developer.greenhouse.io/job-board.html
- https://support.greenhouse.io/hc/en-us/articles/115005448066-Invisible-reCAPTCHA
