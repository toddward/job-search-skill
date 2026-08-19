# BambooHR

## Recognize
Current hosted pages commonly use `{company}.bamboohr.com/careers/{job_id}`; legacy
pages may use `/jobs/view.php?id={id}`. Confirm with BambooHR assets/footer and the
application form's action, since a company subdomain can proxy or redirect elsewhere.

## Posting API
`GET https://{companyDomain}.bamboohr.com/api/v1/applicant_tracking/jobs` is supported
but requires an authenticated caller with ATS access — not a public candidate feed.
`api_kind: employer_authenticated`.

## Form shape
Usually a single page or short flow: résumé, `First Name`/`Last Name`, `Email`,
`Phone`/`Address`, `City`, `State`, `ZIP`, `Country`, employer questions, cover
letter, acknowledgments. Links via custom `LinkedIn URL`, `Website`, `Portfolio`,
`GitHub` fields. Authorization, sponsorship, relocation, salary, start date, and EEO
are all employer-configured custom fields — do not assume a stable field ID across
tenants.

## Intermediate controls
Short flows rarely have one; treat any unrecognized label as intermediate.

## Final controls
`submit application`, `apply for this job`. Context: button is inside the filled
application form, not the job-detail page's navigation CTA.

## Signals
Variable by employer/site: validation, throttling, or a challenge can appear; the
authenticated API itself can also throttle. Any challenge or unexpected sign-in wall →
manual.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://documentation.bamboohr.com/reference/get-job-summaries
- https://documentation.bamboohr.com/docs/getting-started
- https://documentation.bamboohr.com/docs/api-details
