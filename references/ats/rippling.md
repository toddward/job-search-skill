# Rippling Recruiting

## Recognize
`ats.rippling.com/{job_board_slug}/jobs/{job_uuid}`; application path ends `/apply`
and includes `jobBoardSlug`, `jobId`, and often `step=application`. Corroborate with
"Exit to job board" text plus Rippling-owned assets.

## Posting API
No supported anonymous public job-board JSON API documented as of research date. Read
the rendered board/job page or its runtime network responses; treat any private XHR
as unstable. `api_kind: undocumented`. Example public board:
`https://ats.rippling.com/amopportunities/jobs`.

## Form shape
Compact page: Résumé, `First name`, `Last name`, `Email`, `Pronouns`,
`Current company`, `Phone number`, `Location`, `LinkedIn Link`, `Cover letter` (file),
employer questions/consent; résumé parsing may add fields. Consent may include text
messages and privacy/AI notices — must be user-reviewed, never auto-accepted.
Authorization, salary, relocation, and self-ID are employer-configured.

## Intermediate controls
`apply now` on the job-detail page is navigation into the form, not a submit action —
do not confuse it with the final control below.

## Final controls
`apply`, `submit application`. Context: URL is `/apply?...step=application`; distinct
from the job-detail `Apply now` navigation link.

## Signals
No uniform public CAPTCHA documentation; variable identity, résumé-parsing, employer
questions, and edge/bot controls. AI/privacy consent screens require user action —
never auto-accept.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://ats.rippling.com/rippling/jobs/17ac34d3-704d-4115-9de0-77e409e68069/apply?jobBoardSlug=rippling&jobId=17ac34d3-704d-4115-9de0-77e409e68069&step=application
