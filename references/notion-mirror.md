# Notion mirror

`scripts/notion_sync.py` builds payloads (properties, page body, icon) and manages the
failure outbox. It never calls Notion itself — the skill text makes the MCP calls with
the payloads this script produces.

## Interface

Use the **hosted Notion MCP**, `https://mcp.notion.com/mcp`. It holds the OAuth token
and its tools are already shaped for agent use — no self-hosted infrastructure. In an
interactive session, authorize it once via `/mcp`; the token persists after that.
Headless runs need the server declared explicitly in `config/mcp.headless.json` (see
Tool names below) because interactively-authenticated claude.ai connectors can be
absent from cron.

## Schema (`notion_sync.DDL`)

Identical to the module constant — do not hand-edit one without the other:

```sql
CREATE TABLE (
  "Role"        TITLE COMMENT 'Job title as posted',
  "Company"     RICH_TEXT,
  "Fingerprint" RICH_TEXT COMMENT 'upsert key; do not edit',
  "Status"      SELECT('new':gray, 'shown':blue, 'selected':purple, 'applied':green, 'not interested':red, 'expired':brown, 'needs manual apply':orange),
  "Fit"         NUMBER,
  "Location"    RICH_TEXT,
  "Work Model"  SELECT('remote':green, 'hybrid':blue, 'onsite':gray, 'unknown':default),
  "Comp Min"    NUMBER FORMAT 'dollar',
  "Comp Max"    NUMBER FORMAT 'dollar',
  "Posting URL" URL,
  "Source"      SELECT('greenhouse':blue, 'lever':purple, 'ashby':pink, 'workday':orange, 'linkedin':blue, 'indeed':yellow, 'phenom':gray, 'usajobs':green, 'dice':gray, 'other':default),
  "Posted"      DATE,
  "First Seen"  DATE,
  "Last Seen"   DATE,
  "Last Shown"  DATE,
  "Applied On"  DATE,
  "Submitted"   CHECKBOX,
  "Why It Fits" RICH_TEXT,
  "Notes"       RICH_TEXT,
  "Run ID"      RICH_TEXT
)
```

Three deliberate choices:

1. **`"Posting URL"`, not `"URL"`.** `notion-update-page` requires properties named
   `id` or `url` (case-insensitive) to be prefixed `userDefined:` (e.g.
   `userDefined:URL`). Naming the column `Posting URL` avoids that footgun entirely.
2. **`SELECT`, not `STATUS`, for `Status`.** `SELECT` options and colors are fully
   specifiable in the DDL; Notion's `STATUS` type carries its own To-do/In-progress/
   Complete groups that don't map onto this workflow.
3. **`Fingerprint` is `RICH_TEXT`, not `UNIQUE_ID`.** `UNIQUE_ID` is Notion-generated
   and auto-incrementing; the upsert key has to be *ours* — the same 16-hex value
   `jobs.jsonl` uses.

Page body (`notion_sync.page_content`) carries the JD excerpt, fit reasons, and
artifact paths, keeping the row itself scannable. Page `icon` mirrors status
(`notion_sync.status_icon`: 🆕 👀 📝 ✅ 🚫 🗄️ ⚠️).

## Bootstrap (first run, `notion.enabled` and no `settings.local.json` `notion.data_source_id`)

1. Call `notion-create-database` with `title: notion.database_title`, `parent`
   (`page_id: notion.parent_page_id` if set, else workspace-level — omit the key
   entirely rather than send it empty), and `schema: notion_sync.DDL`.
2. The tool returns Markdown containing a `<data-source url="collection://<uuid>">`
   tag. Parse the UUID out of that tag → `data_source_id`; the database id is in the
   returned database URL.
3. Write both ids with `config.py set-local notion.data_source_id <id>` and
   `config.py set-local notion.database_id <id>` (plus `bootstrapped_at` and
   `schema_hash`, the value of `notion_sync.schema_hash()`).
4. Re-read `settings.local.json` (`config.py get notion.data_source_id`) and assert it
   round-tripped to what was just written.
5. If the write or the round-trip check fails, **abort the mirror for this run** and
   log it — never leave a database created in the workspace with no id recorded
   locally, since that orphans it on every later run.

On a later run, if the stored `schema_hash` differs from `notion_sync.schema_hash()`
(the skill was upgraded), reconcile with `notion-update-data-source` using **additive
DDL only** (`ADD COLUMN`/`RENAME COLUMN`). Never emit `DROP COLUMN` automatically — it
can destroy user data in a workspace the skill doesn't own; print the DDL and let the
user run a drop by hand if one is ever needed.

## Upsert by fingerprint

Notion has no native upsert; it's query-then-branch, once per job whose
`notion_synced_at` is null or older than `status_changed_at`:

1. **Look up** the existing page with `notion-query-data-sources`, filtering
   `Fingerprint equals <fp>` against the stored `data_source_id` (batch a run's
   fingerprints into one query where possible). Cache the resulting `notion_page_id`
   back into `jobs.jsonl` so later runs skip the lookup.
2. **No match → `notion-create-pages`** with `parent.data_source_id`, `properties`
   from `notion_sync.page_properties(job, run_id)`, `content` from
   `notion_sync.page_content(job)`, `icon` from `notion_sync.status_icon(job.status)`.
3. **Match → `notion-update-page`** with `command: "update_properties"`, sending only
   the properties that changed plus a refreshed `icon`.
4. Record `notion_page_id` and `notion_synced_at` in `jobs.jsonl` in the same write
   that follows the mirror.

Only mirror jobs `notion_sync.should_mirror(job, notion.mirror)` allows — policy
`all`/`shown`/`selected` compares against `job["status"]`.

## Outbox

At the **start** of every run, before any new mirror work: `notion_sync.outbox_drain(home)`
and retry each entry. `jobs.jsonl` is the source of truth; Notion is a mirror, so a
Notion error must never fail the run. On any Notion call failure, `notion_sync.outbox_add(home, payload)`
the intended operation to `memory/notion-outbox.jsonl` and continue; the next run's
flush retries it.

## Privacy — never mirrored

Notion receives job-level summary fields only. These never appear in
`page_properties`, `page_content`, or anywhere else sent to Notion:

- EEO/self-identification answers
- Phone number
- Address
- Screenshots
- Salary constraints or expectations from the user's profile

## MCP tool names

Interactive sessions on this machine expose the connector as
`mcp__claude_ai_Notion__notion-*` (e.g. `mcp__claude_ai_Notion__notion-create-database`).
Headless runs, using this skill's `config/mcp.headless.json` (server key `notion`),
expose the same tools as `mcp__notion__notion-*`. The skill text should match on the
`notion-` tool suffix (`notion-create-database`, `notion-query-data-sources`,
`notion-create-pages`, `notion-update-page`, `notion-update-data-source`,
`notion-fetch`) rather than hardcode either server prefix, so the same instructions
work in both contexts.
