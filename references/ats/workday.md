# Workday

## Recognize
Host commonly `{tenant}.wd{number}.myworkdayjobs.com` or
`{tenant}.myworkdayjobs.com`; job paths contain
`/{career_site}/job/{location}/{slug}_{requisition}`. Strong DOM signal: many
`data-automation-id` attributes and XHR paths containing `/wday/cxs/`. Branded company
sites often redirect into this host — re-detect after the redirect.

## Posting API
No documented, cross-tenant, anonymous public jobs API. The browser client calls
tenant-specific `/wday/cxs/{tenant}/{career_site}/jobs` routes — undocumented web
backends whose contract may change; treat as evidence, not a stable contract.
`api_kind: undocumented`.

## Form shape
Long multi-step wizard, often account/email verification first, then: My Information,
My Experience (work/education/languages/websites, résumé), Application Questions,
Voluntary Disclosures, Self Identify, Review. Résumé parsing can populate repeated
work/education entries — add rows from `structured_resume` only, never synthesize
duties. Labels: `Country`, `Legal First/Middle/Last Name`, `Address Line 1/2`, `City`,
`State/Province`, `Postal Code`, `Email Address`, `Phone Device Type`,
`Country Phone Code`, `Phone Number`; under Websites: `Website URL` + `Type`
(e.g. LinkedIn). Voluntary Disclosures/Self Identify carry `legally authorized to
work`, `require sponsorship`, `Gender`, `Race/Ethnicity`, `Veteran Status`, disability
form.

## Intermediate controls
`data-automation-id="bottom-navigation-next-button"` — reusable across every step;
never treat this selector alone as proof of finality.

## Final controls
`submit`. Context: progress/heading reads Review or the last configured section.

## Signals
High-friction multi-step account/email verification is common; tenant WAF/challenge
behavior varies. Persistent headed profile required; manual login/MFA/challenge —
downgrade to `needs_manual_apply` under `JOBSEARCH_BROWSER_MODE=headless`.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/career-sites/san1394588983205.html
- https://doc.workday.com/admin-guide/en-us/human-capital-management/recruiting/career-sites/san1431625385171.html
