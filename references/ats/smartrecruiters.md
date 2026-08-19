# SmartRecruiters

## Recognize
`jobs.smartrecruiters.com/{company}/{posting_id}-{slug}`,
`careers.smartrecruiters.com/{company}`, or an apply flow/resource on a
SmartRecruiters host. Confirm with stable footer/resource origins.

## Posting API
`GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings/{postingId}`
and list `.../postings` — documented "Posting API"; states API-key authentication, so
probe without credentials and handle 401/403 as inconclusive, never invent a token.
`api_kind: undocumented` for applicant purposes.

## Form shape
Multi-screen candidate flow: résumé/profile import, contact information + location,
experience, employer questionnaire, privacy/consents, review, optional diversity data.
Some tenants require sign-in/email verification. Labels: `First name`, `Last name`,
`Email`, `Phone number`, `Location`/`City`, address components; links `LinkedIn`,
`Website`, `Portfolio`. `Are you legally authorized...`,
`Will you now or in the future require sponsorship...` and preference/self-ID wording
are tenant-configured — map only the normalized full question.

## Intermediate controls
Screen-to-screen Next/Continue in the multi-step flow; treat unrecognized labels as
intermediate.

## Final controls
`submit application`, `submit`. Context: review/final stage of the SmartRecruiters
flow.

## Signals
Variable by tenant/region: login/email verification, rate limiting, or edge
challenges may appear. Any sign-in requirement beyond the applicant's own account →
manual.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://developers.smartrecruiters.com/docs/posting-api
- https://developers.smartrecruiters.com/docs/endpoints
