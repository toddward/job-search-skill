# Phenom / Eightfold (company career sites)

Phenom (phenom.com) and Eightfold.ai are two distinct AI-driven talent-platform
vendors, both typically embedded inside a company's own careers domain rather than a
vendor-branded job-board host. Coverage here is lighter than the researched vendors
above — treat detection confidence conservatively and fall back to `custom.md`
whenever a signature below is not clearly matched.

## Recognize
Company domain remains final (e.g. `careers.{company}.com`); look for Phenom/Eightfold
resource hosts, script tags, or API calls (`*.phenompeople.com`, `*.eightfold.ai`) in
the page's network requests, and matching footer/attribution text such as "Powered by
Phenom" or an Eightfold AI-matching widget. Re-run detection after any Apply redirect
since the shell page is often generic company branding.

## Posting API
No documented, stable, anonymous applicant-facing API found for either vendor. Prefer
the page's own `application/ld+json` `JobPosting` block or a company jobs feed if one
exists. `api_kind: undocumented`.

## Form shape
Typically a résumé-first flow: upload/parse résumé, then contact fields (name, email,
phone, location), employer screening questions, and an optional EEO/self-ID block.
Both vendors emphasize AI-driven job matching and résumé parsing widgets on the
job-search page itself, separate from the actual application form. Treat all field
labels as company-configured; resolve via accessible label, not assumed field names.

## Intermediate controls
Vendor-styled Next/Continue buttons in a staged flow; treat any unrecognized label as
intermediate, never final.

## Final controls
`submit application`, `submit`, `apply` — same caution as `custom.md`: require the
control to be inside the filled candidate form, no remaining intermediate step, and a
review/final heading or form action as corroborating context before treating it as
final.

## Signals
Unknown/variable — inspect for reCAPTCHA/hCaptcha/Cloudflare challenge markers, login
walls, or email/SMS verification like any unresearched platform. Any challenge →
`needs_manual_apply`.

## manual_only: false

## last_verified: 2026-08-19

## Sources
- https://www.phenom.com/
- https://eightfold.ai/
