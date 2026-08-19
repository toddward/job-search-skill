# Indeed Apply — manual-only

## Recognize
Job URL often `indeed.com/viewjob?jk={job_key}`; direct application stays inside an
Indeed dialog or moves to an `apply.indeed.com`/Indeed Apply route. Confirm with an
Indeed-owned form/dialog and text such as **Apply now**. An employer-site redirect
must be re-detected as that destination's own adapter — it is not this one.

## Posting API
No public applicant API for this use. Partner products exist for employers/vendors,
not for an individual applicant's automated client.

## Form shape
Authenticated or email-verified staged flow: contact, résumé, employer questions,
review, then **Submit your application**/**Submit application**. Some postings
redirect to the employer's own ATS rather than staying in Indeed Apply.

## Intermediate controls
Staged-flow Next/Continue; not driven by this skill regardless.

## Final controls
`submit your application`, `submit application` — inside the Indeed Apply review
step. Never clicked by this skill under any configuration.

## Signals
Email/phone verification, application limits, and anti-automation controls may
appear.

## manual_only: true

**Why:** Indeed's current Terms of Service state that users may not use automated
systems to access, data-mine, or submit content without written permission, and
expressly prohibit automating Indeed Apply outside official vendors/tooling. This
skill may record the job and prepare tailored documents, and it may open the
canonical posting URL for the user to apply by hand. It must never fill, click, or
simulate submission on an Indeed Apply page, regardless of `apply.auto_submit` or
`--i-mean-it`.

## last_verified: 2026-08-19

## Sources
- https://www.indeed.com/legal?hl=en_US
- https://support.indeed.com/hc/en-us/articles/204652920
