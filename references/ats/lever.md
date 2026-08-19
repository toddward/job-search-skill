# Lever

## Recognize
`jobs.lever.co/{site}/{posting_uuid}` (EU: `jobs.eu.lever.co`); application URL
normally ends `/apply`. DOM/resource signals: `lever`, `.application-form`, inputs
named `name`, `email`, `phone`, `resume`.

## Posting API
`GET https://api.lever.co/v0/postings/{site}/{posting_uuid}` or list
`.../{site}?mode=json` — public, `api_kind: public_posting_read_only`; response
includes `hostedUrl`/`applyUrl`. It does **not** expose custom application questions —
those must come from the rendered form. The application `POST .../{posting_uuid}?key=APIKEY`
requires an employer-generated key and is rate-limited; not an applicant route.

## Form shape
Single page: `Full name` (maps to legal first+middle+last in display order), `Email`,
`Phone`, `Current company`, résumé, links (`LinkedIn URL`, `Portfolio URL`, `Website`,
sometimes `Twitter URL`), free-form additional information, consent, employer
questions. Diversity/EEO may be a separate optional section or follow-up screen.

## Intermediate controls
None typical — single-page form.

## Final controls
`submit application`. Context: URL ends `/apply` and the Lever application container
is present.

## Signals
No uniform public CAPTCHA guarantee found; variable rate limits, account/form
configuration, or email validation by tenant. Any challenge/verification →
`needs_manual_apply`.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://github.com/lever/postings-api
