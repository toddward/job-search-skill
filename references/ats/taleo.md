# Oracle Taleo Enterprise

## Recognize
`*.taleo.net/careersection/{section}/jobdetail.ftl?job={requisition}`; apply path is
`jobapply.ftl`. The combination of `.ftl`, `/careersection/`, `lang`, and `job`
parameters is highly distinctive, e.g.
`https://abc.taleo.net/careersection/5/jobdetail.ftl?lang=en&job=51380`.

## Posting API
Customer APIs/RSS integrations exist but require customer configuration/credentials —
no dependable anonymous JSON endpoint across Enterprise tenants. `api_kind:
undocumented`. The career-section URL contract itself is documented.

## Form shape
Configurable page sequence, commonly: login/account, résumé upload, personal
information, education, work experience, screening, e-signature/privacy, diversity,
Review and Submit, then a Thank You page. Labels: `First Name`, `Middle Name`,
`Last Name`, `Email Address`, `Home Number`, `Cellular Number`, `Address`, `City`,
`State/Province`, `Zip/Postal Code`, `Country`; links via custom `Web Site`, social
URL, or attachment fields. Blocks include Disqualification Questions, Screening,
Diversity, E-Signature. Legacy tenants can run longer than Oracle's recommended <7
pages and are brittle.

## Intermediate controls
`save and continue` — always intermediate, never a final target even though it
resembles a submit action.

## Final controls
`submit`, `submit application`. Context: the Review and Submit page specifically.

## Signals
Account creation, password rules, session expiry, e-signature, and occasional CAPTCHA
vary by tenant; legacy pages are brittle. Persistent headed profile; user handles
account creation, e-signature, and any challenge.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://docs.oracle.com/en/cloud/saas/taleo-enterprise/25b/otcug/c-optimizedjobapplicationflow.html
- https://docs.oracle.com/en/cloud/saas/taleo-enterprise/22c/otcug/c-careersectionurl.html
