# Workable

## Recognize
`apply.workable.com/{account}/j/{shortcode}`, `{account}.workable.com/jobs/...`, or an
application route ending `/candidates/new`. On a custom domain, confirm via Workable
assets/footer text.

## Posting API
`GET https://www.workable.com/api/accounts/{account}?details=true` is a supported
public read. The employer-authenticated SPI (`GET
https://{account}.workable.com/spi/v3/jobs/{shortcode}`) and candidate creation both
require employer `w_candidates` scope — not applicant routes. `api_kind:
public_posting_read_only` for the accounts read only.

## Form shape
Short staged flow or single page: résumé import/upload (PDF/common formats, ≤5 MB),
`First name`/`Last name`, `Email`, `Phone`/`Address`, sometimes `Headline`, cover
letter, custom Yes/No/dropdown/paragraph questions, optional candidate survey. Link
labels: `LinkedIn profile`, `Website`, custom GitHub/portfolio. Workable supports
auto-disqualifying Yes/No knockout questions — exact truth matters, never optimize for
passing.

## Intermediate controls
Staged-flow tenants use their own Next/Continue labels; treat any unrecognized label
as intermediate.

## Final controls
`submit application`, `submit`. Context: candidate application/review step, not an
intermediate questionnaire form.

## Signals
**Documented multi-layer defense**: WAF, IP reputation, browser-integrity validation,
rate limiting, bot management, CAPTCHA for suspicious traffic, and it tags detected
AI-assisted applications. Use the applicant's real email and truthful content; any
CAPTCHA → manual.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://help.workable.com/hc/en-us/articles/115012771647
- https://help.workable.com/hc/en-us/articles/35293126257815
- https://help.workable.com/hc/en-us/articles/115012238688
