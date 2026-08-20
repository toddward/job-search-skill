# Fit-score rubric (`rubric_version = 1`)

Scores are produced by `scripts/fit_score.py`; the skill never computes the number itself.

Seven additive components summing to 100 (weights are config, not code — `scoring.weights` in
`config.DEFAULTS`), then hard-flag caps are applied to the total afterward.

## Weights

| # | Component | Weight | How it is computed | Why this weight |
|---|---|---|---|---|
| 1 | Hard requirements (`must_have`) | 35 | Fraction of `must_have` items covered by the resume: 1.0 exact/synonym hit, 0.6 if every word of a multi-word requirement appears somewhere, 0 otherwise. No `must_have` listed → neutral 0.75. | Only component that maps to a screening decision; everything else is preference. |
| 2 | Skills overlap (`nice_to_have`) | 20 | Same coverage function over `nice_to_have`. Neutral 0.5 if absent. | Kept below 35 so keyword overlap can never outvote a missing hard requirement (and the <50% floor caps the total regardless). |
| 3 | Seniority / title | 12 | Ordinal ladder (intern 0 … VP 7) on both titles. Δ=0 → 1.0; Δ=+1 → 0.75 (stretch is fine); Δ=−1 → 0.85 (slight down-level); \|Δ\|=2 → 0.45; else 0.15. | A level mismatch routinely kills an application on its own, so it must move the score meaningfully without sinking an otherwise perfect match alone. |
| 4 | Location / remote | 12 | Remote, or in `home_metro` → 1.0; in `ok_metros` → 0.7; location unknown → 0.5; anything else → 0.0. | Same reasoning as seniority: a real screening factor, sized to matter but not dominate. |
| 5 | Domain / industry | 8 | Job's `domain_tags` intersects `target_domains` → 1.0; no tags → 0.5; tags present but no match → 0.25. | Real but weak signal. |
| 6 | Recency | 5 | Posting age ≤7d → 1.0; ≤21d → 0.8; ≤45d → 0.5; older → 0.2. | Stale requisitions are frequently already filled. |
| 7 | Compensation signal | 8 | `comp_max` ≥ `target_base` → 1.0; ≥90% → 0.7; ≥80% → 0.35; below → 0.0. **No range posted → 0.6, not 0.** | As of 2026, several states require a posted range but Virginia (and many others) do not — an unposted range on a local posting is normal and must not be punished. `target_base`, not the weight, is the lever to recalibrate. |

## Caps (applied after the additive sum)

Caps, not subtractions, so a red-flagged job can never out-rank a clean one on component strength:

| Flag | Condition | Effect |
|---|---|---|
| `clearance_not_held` | JD requires an **active** clearance and the candidate does not hold it (`holds_clearance: false`) and the posting is not "eligible to obtain" (`clearance_eligible_ok`) | `total = min(total, 25)` |
| `citizenship_or_sponsorship` | JD requires citizenship the candidate lacks, or states no sponsorship while the candidate needs it | `total = min(total, 20)` |
| `must_have_floor` | `must_have` coverage < 0.50 | `total = min(total, 45)` |

**"Eligible to obtain" is not a blocker.** Individuals cannot self-apply for a clearance — it must
be sponsored by an employer or agency — so "must be eligible to obtain" or "clearance sponsorship
available" is a normal open door, not a red flag. Only an **active, already-held** clearance
requirement the candidate cannot satisfy triggers the cap. Other signals worth a `notes` line
without capping: unpaid/equity-only, "rockstar/ninja" language, an email-only apply flow, a
`validThrough` date already past.

## What gets scored (the input contract)

`covered()` matches **terms**, not sentences, so `fit_score.score()` reads
`job["must_have_terms"]` / `job["nice_to_have_terms"]` — the term lists
`jd_extract.terms_from_bullets()` harvests out of the bullet prose (`must_have` /
`nice_to_have` remain in the output for humans, and are the fallback when no term list is
present). Feeding whole bullets ("Have 8+ years designing ML platforms on Kubernetes") to the
scorer would score 0 coverage and report covered skills as missing.

Two fields the extract output does not carry come from the stored row: pass
`fit_score.py --row <jobs_db record>` to merge `location_key` and `remote`, or the location
component sits at the "unknown" 0.5 ratio forever.

## Synonym equivalence groups

Coverage for `must_have` / `nice_to_have` uses `SYN_GROUPS`: symmetric **equivalence groups**, not
one-way aliases. A requirement matches if *any* member of its group appears in the resume's 1–3
word n-grams, e.g. `{kubernetes, k8s, eks, gke, aks, openshift}` or `{python, py}`. One-way aliases
are a bug: mapping only `aws → amazon web services` would score a JD requiring "AWS" as missing
against a resume that literally says "AWS". Groups fix this — `covered()` looks up all variants of
the term being tested and checks the resume's n-gram set for any of them, so `k8s` and `Kubernetes`
are always interchangeable in either direction.

## Reproducibility rules

1. **Version the rubric.** `rubric_version` (currently `1`) travels with every score. Never
   silently re-weight history under the same version number.
2. **Freeze inputs.** The score is a pure function of `(master.md, job dict, scoring config,
   age_days)` — no clock, no RNG, no network call inside `score()`. Callers cache on a hash of
   those inputs; a cache hit means the score is never recomputed and cannot drift.
3. **No clock inside the function.** `age_days` is passed in by the caller; a job must not score
   differently tomorrow for a reason the user can't see in the inputs.
4. **Always emit the breakdown**, not just the total: `components` (weight/ratio/points per
   component), `caps`, `notes`, `must_have_coverage`, `missing_must_haves`. That is what lets a
   report say "83 — missing must-have: Rust; comp 12% under target" instead of just a number.
5. **Calibrate before trusting `apply.submit_threshold`.** Score roughly 30 labelled jobs (user
   marks each *would apply / would not*), confirm the threshold sits between the two populations,
   and adjust `target_base`, metro lists, and `target_domains` first — not the weights.

## Worked example

Config: `resume_seniority=staff`, home metro Reston VA, `target_base=200000`, `holds_clearance=false`.

| Job | must | skills | sen | loc | dom | rec | comp | **Total** | Caps |
|---|---|---|---|---|---|---|---|---|---|
| Staff ML Platform Eng, Reston VA, $210–250k, 3d old | 35.0 | 12.0 | 12.0 | 12.0 | 8.0 | 5.0 | 8.0 | **92** | — |
| Senior AI Eng, Chantilly VA, active TS/SCI | 35.0 | 20.0 | 10.2 | 0.0 | 8.0 | 2.5 | 8.0 | **25** | `clearance_not_held` |
| Director of Eng, Austin TX, Salesforce/SAP/Java | 0.0 | 0.0 | 5.4 | 0.0 | 2.0 | 1.0 | 2.8 | **11** | `must_have_floor` |

The `k8s`-spelled variant of the first job scores identically, confirming synonym symmetry.
Re-running any of these produces a byte-identical result.
