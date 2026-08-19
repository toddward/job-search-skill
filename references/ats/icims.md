# iCIMS

## Recognize
`*.icims.com/jobs/{job_id}/{slug}/job`, `jobs-*.icims.com`, or legacy query URLs such
as `/jobs/intro?mode=job`. Embedded portals often expose an iCIMS iframe/container and
scripts from iCIMS hosts — inspect every frame.

## Posting API
`GET https://api.icims.com/customers/{customerId}/search/portals/{portal}` and
`.../portalposts/job/{jobId}` — a supported Job Portal API, but official examples
require Basic authentication; not a universal anonymous feed. `api_kind:
employer_authenticated`.

## Form shape
Tenant-configurable single- or multi-page portal: résumé upload/import, contact/
address, work/education, source/referral, profile questions, acknowledgments, optional
EEO (often a separate `Voluntary Self-Identification` step). Account creation or email
validation is common. Labels: `First Name`, `Middle Name`, `Last Name`, `Email`,
`Phone`, `Street Address`, `City`, `State/Province`, `Postal Code`, `Country`; links
`LinkedIn Profile`, `Website`, or custom social/profile fields. Often
`Are you authorized...`, `Do you require sponsorship...`, `Willing to relocate`.
Tenant labels are highly configurable.

## Intermediate controls
Portal step navigation; treat unrecognized labels as intermediate.

## Final controls
`submit application`, `submit profile`, `finish`. Context: job/profile application
context on the final/review page.

## Signals
Tenant-configurable account/email/CAPTCHA friction; iframe and cross-origin behavior
can complicate control access. Manual on login verification, CAPTCHA, an inaccessible
frame, or a session loop.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://developer-community.icims.com/applications/applicant-tracking/job-portal
