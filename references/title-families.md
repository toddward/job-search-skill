# Title families (curated)

Used by `scripts/disinterest.py` to generalize a "not interested" into a family-level rule.
Never let the model invent a regex; add rows here instead. Regex is case-insensitive.

| Title stems (examples) | Family | Regex |
|---|---|---|
| sales engineer, solutions engineer, presales engineer, field engineer, account executive | sales-engineering | `\b(sales\|pre-?sales\|field\|account)\s+(engineer\|architect\|consultant\|executive)\b\|\bsolutions?\s+engineer\b` |
| engineering manager, director of engineering, head of platform, vp engineering | management | `\b(director\|vp\|vice president\|head of\|engineering manager\|chief)\b` |
| data engineer, analytics engineer, etl developer | data-engineering | `\b(data\|analytics\|etl)\s+(engineer\|developer)\b` |
| data scientist, research scientist, applied scientist | data-science | `\b(data\|research\|applied)\s+scientist\b` |
| devops engineer, sre, site reliability, platform engineer | infrastructure | `\b(devops\|site reliability\|sre\|platform\|infrastructure)\s*(engineer)?\b` |
| machine learning engineer, ml engineer, ai engineer, mlops | ml-engineering | `\b(machine learning\|ml\|ai\|mlops)\s+engineer\b\|\bmlops\b` |
| solutions architect, cloud architect, enterprise architect, ai architect | architecture | `\b(solutions?\|cloud\|enterprise\|ai\|platform\|principal)\s+architect\b` |
| software engineer, backend engineer, full stack, frontend | software-engineering | `\b(software\|backend\|back-end\|full ?stack\|frontend\|front-end)\s+(engineer\|developer)\b` |
| product manager, program manager, project manager, tpm | product-program | `\b(product\|program\|project\|technical program)\s+manager\b\|\btpm\b` |
| consultant, advisory, professional services | consulting | `\b(consultant\|advisory\|professional services)\b` |
| intern, internship, co-op, new grad, associate | early-career | `\b(intern(ship)?\|co-op\|new grad\|graduate\|entry[- ]level\|associate)\b` |
| recruiter, talent, hr | recruiting | `\b(recruit(er\|ing)\|talent acquisition\|people operations)\b` |
| security engineer, appsec, soc analyst | security | `\b(security\|appsec\|soc)\s+(engineer\|analyst\|architect)\b` |
| qa engineer, test engineer, sdet | quality | `\b(qa\|quality\|test)\s+engineer\b\|\bsdet\b` |
| support engineer, customer success, technical account manager | customer-facing | `\b(support\|customer success\|technical account)\s+(engineer\|manager)\b` |
