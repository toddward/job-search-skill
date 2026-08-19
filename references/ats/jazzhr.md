# JazzHR

## Recognize
Hosted candidate URLs use `{company}.applytojob.com/apply/{job_key}/{slug}` (and
`/apply/jobs/` listings); legacy resources/API use the "Resumator" name. Page title or
footer often reads "JazzHR » Job Listings".

## Posting API
Authenticated API at `https://www.resumatorapi.com/v1/...`; the key comes from an
employer's Integrations settings — not an anonymous posting contract.
`api_kind: employer_authenticated`.

## Form shape
Usually one long page: `First name`, `Last name`, `Email address`, location broken
into `Address`/`City`/`State`/`Postal`, `Phone number`, résumé attachment or pasted
résumé, then custom text/select/checkbox questions. Résumé limit commonly 5 MB. Links
via custom LinkedIn/website/GitHub labels. Eligibility/preference wording is
employer-defined.

## Intermediate controls
None typical — single-page form.

## Final controls
`submit application`, `apply now`. Context: on the `applytojob.com` application form
with the required-field block visible, not the initial job-listing page.

## Signals
No uniform documented challenge; variable employer custom validation, edge protection,
spam controls, or CAPTCHA may appear. Any challenge → manual.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://www.resumatorapi.com/
- https://www.jazzhr.com/onboarding/careers-page
