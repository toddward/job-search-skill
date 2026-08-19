# Ashby

## Recognize
`jobs.ashbyhq.com/{job_board_name}/{posting_uuid}`; apply URL usually contains
`/application` or `/apply`. Corroborate with Ashby script/resource hosts and the board
footer text.

## Posting API
`GET https://api.ashbyhq.com/posting-api/job-board/{job_board_name}?includeCompensation=true`
— public, `api_kind: public_posting_read_only`; records include description,
`publishedAt`, `jobUrl`, `applyUrl`. Documents postings only, not applicant
submission.

## Form shape
Compact application view: résumé parsing, `First Name`/`Last Name` or `Name`, `Email`,
`Phone`/`Location`, links (`LinkedIn Profile`, `Website`, `Portfolio`, custom
`GitHub`), employer questions, optional surveys. Sections may reveal progressively
after résumé parsing completes — re-snapshot after upload. Authorization/sponsorship/
relocation/salary questions are usually full-sentence custom text; demographic survey
wording varies by country.

## Intermediate controls
Progressive-reveal sections generally do not require a Next click, but where present
treat any non-final label as intermediate.

## Final controls
`submit application`, `submit`. Context: on the apply route, last application section
visible, no remaining Next/Continue control.

## Signals
No uniform documented CAPTCHA claim; variable employer questions, file-parsing
behavior, verification, and edge/WAF configuration. Any challenge → manual.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://developers.ashbyhq.com/docs/public-job-posting-api
