# ATS adapter contract (base)

Load exactly one vendor note (this file plus `<vendor>.md`) per application, after
detection. Detection order: final URL/iframe host+path match → vendor-owned form
action/resource host/field-name/footer match → probe the documented posting endpoint
only when the URL exposes the required tenant/board token → otherwise `custom`.
`confidence < 0.85` ⇒ treat as `custom`; never run another vendor's selectors at low
confidence. See `apply-flow.md` for the state machine, fill loop, and the submit-guard
hard rule — this file only holds the schema and per-adapter contract shape.

## Adapter recognition record

Every detection stores:

```yaml
platform: greenhouse
confidence: 0.99
evidence: [{kind: final_url_host, value: job-boards.greenhouse.io}, {kind: form_signature, value: job_application[first_name]}]
posting_id: "1234567"
tenant_or_board: example-company
apply_url: https://job-boards.greenhouse.io/example-company/jobs/1234567
api_kind: public_posting_read_only | employer_authenticated | undocumented | none
```

## Canonical profile schema (`config/profile.md` → structured)

Keep `false`, `unknown`, and missing distinct. Never infer a protected trait,
immigration category, clearance, conviction, or disability from résumé text — every
sensitive fact needs an explicit `source` and `confirmed_at`.

```yaml
schema_version: 1
identity: {legal_first_name, legal_middle_name, legal_last_name, preferred_name}
contact: {email, phone_e164, phone_country_code}
location: {address_line_1, address_line_2, city, region, postal_code, country_code}
links: {linkedin, github, website}
work_eligibility: {country_code, authorized_now: unknown, sponsorship_now: unknown, sponsorship_future: unknown, citizenship_or_status: unknown}
preferences:
  willing_to_relocate: unknown
  relocation_locations: []
  earliest_start_date: unknown
  notice_period_days: unknown
  salary: {currency: USD, period: year, minimum: unknown, target: unknown, negotiable: unknown}
self_identification: {gender: decline, race_ethnicity: decline, protected_veteran: decline, disability: decline, pronouns: decline}
structured_resume: {employment: [], education: [], licenses_certifications: []}
provenance: {source: user_profile, confirmed_at: "2026-08-19"}
```

`unknown` must never be silently converted to yes/no. A user may set explicit
self-identification values instead of `decline`; the system must never derive them.

## Vendor-note section shape

Each file in this directory (≤60 lines) uses exactly these sections:

- **Recognize** — URL/DOM signatures, in priority order
- **Posting API** — read-only endpoint if any, and its `api_kind`
- **Form shape** — steps, field labels/aliases, résumé-upload control, EEO section
- **Intermediate controls** — Next/Continue/Save accessible names
- **Final controls** — exact accessible names + the context required to treat one as final
- **Signals** — CAPTCHA/login/MFA/verification indicators
- **manual_only** — `true` or `false`
- **last_verified** — `2026-08-19`
- **Sources** — URLs

## Mapping rules

- Resolve by accessible label first, then `<label for>`, `name`, `autocomplete` token,
  then nearby section heading. Fuzzy-match field-type-constrained only (`Current
  location` must never match `Willing to relocate`).
- Never split a full name on whitespace without a configured decomposition.
- After résumé parsing, diff name/email/phone/employer/dates/education against the
  canonical profile; restore any parser-corrupted value and flag ambiguous overwrites.
- Fill the visible accessible control, never a hidden input directly, so framework
  state/validation events fire.
- Never accept privacy/e-signature/SMS/arbitration/"I certify" consent from the
  generic profile — each requires an explicit per-application user decision.
