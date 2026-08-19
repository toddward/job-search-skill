# LinkedIn Easy Apply — manual-only

## Recognize
Final job URL `linkedin.com/jobs/view/{job_id}` plus an authenticated button whose
accessible name is **Easy Apply**. Clicking opens a modal/dialog — identify it by
role/name and the dialog heading, not fast-changing CSS classes. A plain **Apply**
button means the flow leaves LinkedIn entirely and must be re-detected at the
destination (it is not this adapter).

## Posting API
No public job-seeker posting/submission JSON API.

## Form shape
Authenticated multi-screen modal: contact info, résumé selection/upload, employer
screening questions, optional demographic questions, Review, then a distinct
**Submit application** step. LinkedIn's own help documentation separates Review from
Submit as different screens.

## Intermediate controls
Modal step navigation (Next/Review); not driven by this skill regardless.

## Final controls
`submit application` — inside the Easy Apply review dialog. Never clicked by this
skill under any configuration.

## Signals
LinkedIn actively rate-limits Easy Apply volume/speed and documents daily/speed
limits; automation/bots are stated as prohibited.

## manual_only: true

**Why:** LinkedIn's terms explicitly prohibit third-party software — including bots,
browser plug-ins, or extensions — that scrapes or automates activity on LinkedIn, and
its crawling terms require express permission. This skill may record the job and
prepare tailored documents, and it may open the canonical posting URL for the user to
apply by hand. It must never fill, click, or simulate submission on an authenticated
LinkedIn page, regardless of `apply.auto_submit` or `--i-mean-it`.

## last_verified: 2026-08-19

## Sources
- https://www.linkedin.com/help/linkedin/answer/a512388
- https://www.linkedin.com/help/linkedin/answer/a1341387
- https://www.linkedin.com/help/linkedin/answer/a512348
- https://www.linkedin.com/legal/crawling-terms
