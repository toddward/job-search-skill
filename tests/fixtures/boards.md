# test boards
| Board | Search URL template | Method | Login required | Enabled | Notes |
|---|---|---|---|---|---|
| LinkedIn | https://www.linkedin.com/jobs/search/?keywords={keywords}&location={location}&distance={radius}&f_TPR=r604800 | firecrawl | no | true | guest |
| USAJOBS | https://data.usajobs.gov/api/search?Keyword={keywords}&LocationName={location}&Radius={radius} | webfetch | no | true | api |
| Indeed | https://www.indeed.com/jobs?q={keywords}&l={location}&radius={radius} | playwright | no | false | wall |
| ATS public boards | site:job-boards.greenhouse.io OR site:jobs.lever.co {keywords} {location} | firecrawl | no | true | discovery |
