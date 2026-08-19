# job-search: Claude Code skill architecture

Research date: 2026-08-19. Verified against the machine's installed Claude Code **v2.1.235** (`claude --version`) on macOS (Darwin 25.6.0). Claims marked **[verified locally]** were reproduced by running the CLI on this machine during research; everything else is cited to current docs.

**Target platforms: macOS and Linux** (Debian/Ubuntu/Fedora-class, including headless servers and containers). Every recipe below is either portable or given in both variants, and the portability rules are collected in [Cross-platform notes](#cross-platform-notes). Helper scripts are Python 3 stdlib rather than shell wherever the shell would differ. All **[verified locally]** claims were reproduced on macOS only; the Linux variants come from vendor documentation and are rated accordingly in [Confidence](#confidence).

Primary sources: [Extend Claude with skills](https://code.claude.com/docs/en/skills), [Run Claude Code programmatically](https://code.claude.com/docs/en/headless), [CLI reference](https://code.claude.com/docs/en/cli-reference), [Permission modes](https://code.claude.com/docs/en/permission-modes), [Connect Claude Code to tools via MCP](https://code.claude.com/docs/en/mcp), [Environment variables](https://code.claude.com/docs/en/env-vars), [Agent Skills specification](https://agentskills.io/specification).

---

## Skill anatomy

### Two layers of spec

A Claude Code skill obeys the open [Agent Skills](https://agentskills.io) standard, and Claude Code adds fields on top of it. The docs state this explicitly: "Claude Code skills follow the [Agent Skills](https://agentskills.io) open standard… Claude Code extends the standard with additional features like invocation control, subagent execution, and dynamic context injection" ([skills](https://code.claude.com/docs/en/skills)).

This matters for `job-search`: as long as the skill lives in `~/.claude/skills/`, every Claude Code field is available. If it is ever uploaded to claude.ai, the Skills API, or packaged with `package_skill.py`, only six fields survive — `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools` — and any other key is a **hard error**, not a silently ignored field:

```
Unexpected key(s) in SKILL.md frontmatter: argument-hint. Allowed properties are: allowed-tools, compatibility, description, license, metadata, name
```

Recommendation: keep `job-search` a **personal skill on disk only**. It shells out to a local browser profile, a local resume directory and a local memory store; it is not portable to Cowork/cloud sessions anyway, because "Cowork sessions and cloud sessions… don't read `~/.claude/skills/` on your machine" ([skills](https://code.claude.com/docs/en/skills)).

### Where it lives and what it is called

| Location | Path | Applies to |
| :-- | :-- | :-- |
| Personal | `~/.claude/skills/<skill-name>/SKILL.md` | All your projects |
| Project | `.claude/skills/<skill-name>/SKILL.md` | This project only |
| Plugin | `<plugin>/skills/<skill-name>/SKILL.md` | Where plugin is enabled |
| Enterprise | managed settings dir | All users in the org |

For a personal or project skill, **the directory name is the command**, and frontmatter `name` is only a display label: "In a personal or project skill, `name` sets only the display label shown in skill listings, and the command still comes from the directory name" ([skills](https://code.claude.com/docs/en/skills)). So `~/.claude/skills/job-search/SKILL.md` → `/job-search`. Keep `name: job-search` anyway; the Agent Skills spec requires `name` to match the parent directory name.

Precedence when names collide: enterprise > personal > project; a same-named local skill also overrides a bundled skill (but not the bundled skill's aliases); plugin skills are namespaced `plugin:skill` and cannot collide.

Claude Code watches skill directories and picks up `SKILL.md` edits **within the current session, without a restart** ("Live change detection"), which makes iterating on this skill cheap. That watch covers `SKILL.md` text only.

### Frontmatter reference (current, Claude Code v2.1.x)

Every field is optional; only `description` is recommended. Booleans accept `yes/no/on/off/1/0/true/false` in any case (v2.1.218+).

| Field | What it does |
| :-- | :-- |
| `name` | Display name in skill listings. Defaults to the directory name. |
| `description` | What the skill does and when to use it; drives auto-invocation. |
| `when_to_use` | Extra trigger phrases; appended to `description` in the listing. |
| `argument-hint` | Autocomplete hint, e.g. `[query] \| pick <n,n> [--from DATE]`. |
| `arguments` | Named positional args for `$name` substitution (space-separated string or YAML list). |
| `disable-model-invocation` | `true` = only the user can invoke it. Also blocks preloading into subagents and blocks a [scheduled task](https://code.claude.com/docs/en/scheduled-tasks) firing with the skill as its prompt (v2.1.196+). |
| `user-invocable` | `false` = only Claude can invoke it. |
| `allowed-tools` | Tools pre-approved **for the turn that invokes the skill**; the grant clears on your next message. |
| `disallowed-tools` | Tools removed from Claude's pool while the skill is active; also clears on your next message. |
| `model` | Model override for the turn (or for the forked subagent when `context: fork`). |
| `effort` | `low`/`medium`/`high`/`xhigh`/`max` for the turn. |
| `context` | `fork` runs the skill in a subagent with its own context. |
| `agent` | Which subagent type to use with `context: fork` (default `general-purpose`). |
| `background` | With `context: fork`, `false` waits for the result in the invoking turn (default `true`, v2.1.218+). |
| `hooks` | Hooks registered when the skill is invoked, kept for the rest of the session. |
| `paths` | Globs that limit automatic activation to matching files. |
| `shell` | `bash` (default) or `powershell` for `` !`cmd` `` injection. |
| `metadata` | Free-form YAML map for your own tooling. |
| `license`, `compatibility` | Accepted, not acted on by Claude Code. |

### Size limits that actually bite

| Limit | Value | Source |
| :-- | :-- | :-- |
| `name` | 1–64 chars, lowercase `a-z0-9-`, no leading/trailing/consecutive hyphens, must match directory name | [Agent Skills spec](https://agentskills.io/specification) |
| `description` | 1–1024 chars (spec) | [Agent Skills spec](https://agentskills.io/specification) |
| `description` + `when_to_use` in the listing | truncated at **1,536 characters**, tunable via `skillListingMaxDescChars` | [skills](https://code.claude.com/docs/en/skills) |
| Whole skill-listing budget | **1% of the model's context window**, tunable via `skillListingBudgetFraction` or `SLASH_COMMAND_TOOL_CHAR_BUDGET` | [skills](https://code.claude.com/docs/en/skills) |
| `compatibility` | 1–500 chars | [Agent Skills spec](https://agentskills.io/specification) |
| `SKILL.md` body | "Keep `SKILL.md` under 500 lines" / "< 5000 tokens recommended" | [skills](https://code.claude.com/docs/en/skills), [spec](https://agentskills.io/specification) |
| Re-attach after auto-compaction | first **5,000 tokens** per skill, **25,000 tokens** combined across skills | [skills](https://code.claude.com/docs/en/skills) |

There is no documented hard byte cap on `SKILL.md` in Claude Code. The 500-line guidance is the operative constraint, and the compaction budget is the reason it matters: a long-running `/job-search` run will compact, and only the first 5,000 tokens of the skill survive. **Put the non-negotiable rules (never auto-submit unless `auto_submit: true`; the cooldown rule; the "flag unknown screening answers" rule) in the first ~150 lines of `SKILL.md`.**

### Progressive disclosure layout

The spec's three-stage model: metadata (~100 tokens, always loaded) → `SKILL.md` body (loaded on activation) → `scripts/`, `references/`, `assets/` (loaded only when required). Reference supporting files from `SKILL.md` so Claude knows what each contains and when to load it.

Proposed tree for `~/.claude/skills/job-search/`:

```text
job-search/
├── SKILL.md                      # <500 lines: contract, run loop, hard rules, file map
├── references/
│   ├── search-strategy.md        # Firecrawl -> Playwright -> WebSearch layering, per-board recipes
│   ├── scoring-rubric.md         # resume-fit score definition, 0-100 bands
│   ├── memory-schema.md          # jobs.jsonl JSON Schema + disinterest.yaml grammar
│   ├── title-families.md         # title -> family normalization table for "not interested"
│   ├── notion-mirror.md          # DDL, property map, upsert procedure, gotchas
│   ├── apply-playbook.md         # Playwright form-fill patterns per ATS
│   └── report-template.md        # reports/YYYY-MM-DD.md structure incl. machine index block
├── scripts/                      # all Python 3 stdlib, chmod +x, #!/usr/bin/env python3
│   ├── runtime_probe.py          # prints mode=headless|interactive + os (see Headless section)
│   ├── platform_paths.py         # OS detection, XDG/Library paths, Chrome/Chromium discovery
│   ├── preflight.py              # dependency check per OS; writes host block + generated configs
│   ├── jobs_db.py                # atomic upsert/query/cooldown over memory/jobs.jsonl
│   ├── fingerprint.py            # canonical URL + identity fingerprint
│   ├── resume_text.py            # PDF/md/txt/URL -> plain text (pdftotext, pypdf, or fetch)
│   ├── render_pdf.py             # Markdown -> HTML -> PDF via headless Chrome/Chromium
│   ├── config.py                 # load + validate settings.yaml, apply precedence
│   └── run_headless.py           # scheduler entrypoint: lock, invoke claude -p, verify the result
└── assets/
    ├── resume.css                # print stylesheet for the PDF pipeline
    └── settings.example.yaml
```

Every helper is Python 3 (stdlib only, 3.9+) rather than shell, and that is a portability decision rather than a stylistic one: `flock` is **absent on macOS** (`command -v flock` → missing on this machine) and present on Linux; `sed -i` takes a mandatory argument on BSD and none on GNU; `date -v-14d` is BSD-only while `date -d '14 days ago'` is GNU-only. `os.mkdir`, `os.replace`, `shutil.which`, `hashlib`, and `datetime` behave identically on both. The only shell that survives is the scheduler stanza, written in POSIX `sh`. See [Cross-platform notes](#cross-platform-notes) for the full substitution table.

### Invocation: slash command vs auto-trigger

- Typing `/job-search …` always works for a user-invocable skill.
- Claude auto-invokes based on `description` unless `disable-model-invocation: true`.
- With `disable-model-invocation: true`, the description is **not** loaded into context at all, which saves listing budget — and if Claude tries to run it anyway, "Claude Code blocks the call and instructs it not to reproduce the deploy steps another way."

For `job-search`: this skill logs into job boards, writes durable memory, and can submit applications. That is exactly the "workflows with side effects or that you want to control timing" case the docs call out for `disable-model-invocation: true`. **Set it.** The cost is that Claude will never say "I notice you're job hunting, let me run /job-search" — which is the desired behavior. Cron invokes it explicitly by name, so nothing is lost headlessly (verified below).

### Arguments

| Placeholder | Meaning |
| :-- | :-- |
| `$ARGUMENTS` | The full argument string exactly as typed. If absent from the body, Claude Code appends `ARGUMENTS: <value>`. |
| `$ARGUMENTS[N]` / `$N` | 0-based positional argument; shell-style quoting, so `"hello world"` is one argument. |
| `$name` | Named argument declared in the `arguments:` frontmatter list; expands to empty string if not supplied. |
| `${CLAUDE_SKILL_DIR}` | Directory containing `SKILL.md` — substituted in the body **and** in `allowed-tools` Bash rules. |
| `${CLAUDE_PROJECT_DIR}` | Project root (v2.1.196+). |
| `${CLAUDE_SESSION_ID}` | Current session id. |
| `${CLAUDE_EFFORT}` | `low`…`max`. |

Escape a literal `$` before a digit or `ARGUMENTS` with a backslash (`\$1.00`).

**[verified locally] `$ARGUMENTS` and `$N` both expand correctly inside `claude -p`.** A test skill echoing `ALL=<$ARGUMENTS> A0=<$ARGUMENTS[0]> S0=<$0>` invoked as `claude -p "/echo-args alpha bravo charlie delta"` returned:

```
ALL=<alpha bravo charlie delta>
A0=<alpha>
A1=<bravo>
S0=<alpha>
S1=<bravo>
```

### Two verified gotchas that shape the design

**Gotcha 1 — the word `select` silently eats two positional arguments.** [verified locally, v2.1.235]

| Invocation | `$ARGUMENTS` | `$0` | `$1` |
| :-- | :-- | :-- | :-- |
| `/echo-args alpha bravo charlie delta` | `alpha bravo charlie delta` | `alpha` | `bravo` |
| `/echo-args alpha 2,4 charlie delta` | `alpha 2,4 charlie delta` | `alpha` | `2,4` |
| `/echo-args select bravo charlie delta` | `select bravo charlie delta` | `charlie` | `delta` |
| `/echo-args select 2,4 --from 2026-08-19` | `select 2,4 --from 2026-08-19` | `--from` | `2026-08-19` |
| `/echo-args pick 2,4 --from 2026-08-19` | `pick 2,4 --from 2026-08-19` | `pick` | `2,4` |

`$ARGUMENTS` is always correct; the positional tokenizer parses arguments with shell-style quoting and evidently treats a leading `select` as the bash `select NAME in …` compound command, swallowing the keyword and the following token. This is undocumented behavior, so treat it as fragile rather than as a rule to exploit.

Two consequences, both adopted below:
1. **Use `pick`, not `select`, as the sub-command verb** in the `/job-search` grammar.
2. **Parse `$ARGUMENTS` in the skill body (or in `scripts/config.py`), do not build the grammar on `$0`/`$1`.** Positional substitution is a convenience, not a parser.

**Gotcha 2 — an injected `` !`command` `` containing any shell expansion aborts the entire invocation, and under `-p` it fails *silently*.** [verified locally]

A skill body line `` - Entrypoint: !`printf '%s' "${CLAUDE_CODE_ENTRYPOINT:-unset}"` `` produced, in the `stream-json` output:

```json
{"type":"user","message":{"role":"user","content":"<local-command-stderr>Error: Shell command permission check failed for pattern \"!`printf '%s' \"${CLAUDE_CODE_ENTRYPOINT:-unset}\"`\": Contains expansion</local-command-stderr>"}}
```

…followed by `{"type":"result","subtype":"success","is_error":false,"num_turns":0,...}` with an **empty result and exit code 0**. A cron job would record a clean success and do nothing at all. This matches the documented abort semantics — "A failed command aborts the entire skill invocation, not just its own placeholder… Injected commands never prompt for permission. When a command's permission check returns anything other than allow, Claude Code aborts the invocation" ([skills](https://code.claude.com/docs/en/skills)) — but the `Contains expansion` rejection and the silent `-p` failure are worth designing around.

The working pattern, **[verified locally]**: put all environment-dependent logic in a bundled script, reference it by `${CLAUDE_SKILL_DIR}` (substituted before the permission check, so the final command string contains no `$`), and pre-approve exactly that path:

```yaml
allowed-tools: Bash(date *) Bash(${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py)
```

```markdown
- Runtime: !`${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py`
```

which rendered as `Runtime: mode=headless entrypoint=sdk-cli` inside a `claude -p` run. (The verification used a shell script of exactly this shape; the shipped probe is a Python script with a `#!/usr/bin/env python3` shebang and the executable bit, which renders identically because `${CLAUDE_SKILL_DIR}` is substituted before the permission check runs. Python also lets the same probe report the host OS, which the shell version could not do portably.)

Also note: `` !`cmd` `` is only recognized at line start or after whitespace; with the default bash shell any non-zero exit fails the invocation (append `|| true` to commands that legitimately exit non-zero); each injected command runs under the Bash tool's 2-minute default timeout in the session's current working directory. So keep injection to cheap probes (~1s) and do the real work in tool calls.

### Recommended `SKILL.md` frontmatter

```yaml
---
name: job-search
description: >-
  Find, rank, and apply to jobs that fit the user's resume. Use when the user asks to
  search for jobs, run a job scan, review today's job report, pick jobs to apply to,
  mark a job "not interested", or generate a tailored resume and cover letter.
  Reads ~/development/random/job-search (resume/, config/, memory/, reports/, applications/).
argument-hint: "<query> | pick <n,n> [--from YYYY-MM-DD] | no <n> \"reason\" | status"
disable-model-invocation: true
allowed-tools: >-
  Bash(${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py)
  Bash(${CLAUDE_SKILL_DIR}/scripts/platform_paths.py *)
  Bash(${CLAUDE_SKILL_DIR}/scripts/preflight.py *)
  Bash(${CLAUDE_SKILL_DIR}/scripts/jobs_db.py *)
  Bash(${CLAUDE_SKILL_DIR}/scripts/config.py *)
  Bash(${CLAUDE_SKILL_DIR}/scripts/fingerprint.py *)
  Bash(${CLAUDE_SKILL_DIR}/scripts/resume_text.py *)
  Bash(${CLAUDE_SKILL_DIR}/scripts/render_pdf.py *)
  Read Write Edit Glob Grep WebSearch WebFetch
  mcp__firecrawl__* mcp__playwright__* mcp__notion__*
metadata:
  data_home: ~/development/random/job-search
  platforms: macos,linux
  schema_version: "1"
---
```

Notes on that block:
- `allowed-tools` grants **for the invoking turn only**; it does not restrict anything. It is a prompt-avoidance mechanism, not a sandbox. The docs are blunt: "A skill can grant itself broad tool access, so review the `allowed-tools` of skills checked into a repository before you run Claude Code there."
- Do **not** put `disallowed-tools: AskUserQuestion` in frontmatter — that would also break the interactive path. Suppress it per-run from the CLI instead (see next section).
- Do **not** use `context: fork` here. A forked skill "won't have access to your conversation history", and the interactive selection step is a conversation. Under `-p` a fork is awaited rather than backgrounded, but a backgrounded fork also runs "with the narrower tool set that applies to background subagents", which would jeopardize the MCP browser work.

### Skill content lifecycle (why the body must be standing instructions)

"When you or Claude invoke a skill, the rendered `SKILL.md` content enters the conversation as a single message and stays there for the rest of the session… Claude Code does not re-read the skill file on later turns, so write guidance that should apply throughout a task as standing instructions rather than one-time steps." Re-invoking with identical rendered content adds only a short "already loaded" note; different arguments or different injected output append the full content again.

For `job-search` this means: write the safety rules as invariants ("Never click a final submit control unless…"), not as step 7 of a numbered procedure.

---

## Headless / cron invocation

### The core fact

"User-invoked skills and custom commands work in `-p` mode: include `/skill-name` in the prompt string and Claude Code expands it before running" ([headless](https://code.claude.com/docs/en/headless)). **[verified locally, macOS]** — `claude -p "/echo-args select 2,4 --from 2026-08-19"` expanded the project skill and returned its rendered output; `system/init` listed the skill in `slash_commands`. Nothing in this mechanism is platform-specific.

`disable-model-invocation: true` does **not** block this: the user (here, the scheduler) is invoking it by name. It *does* block Claude Code's own [scheduled tasks](https://code.claude.com/docs/en/scheduled-tasks) from firing with the skill as the prompt (v2.1.196+), which is why an OS scheduler + `claude -p` is the right unattended path rather than `CronCreate` or `/schedule`.

### Path conventions

Nothing below hardcodes a home directory. Three variables carry every platform difference:

| Variable | macOS | Linux |
| :-- | :-- | :-- |
| `DATA_HOME` | `$HOME/development/random/job-search` | `$HOME/development/random/job-search` |
| `SKILL_DIR` | `$HOME/.claude/skills/job-search` | `$HOME/.claude/skills/job-search` |
| `CLAUDE_BIN` | `$HOME/.local/bin/claude` (this machine) | `$HOME/.local/bin/claude` or `/usr/local/bin/claude` |
| Scheduler `PATH` | `$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin` | `$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin` |
| Browser profile | `$DATA_HOME/config/browser-profile` | `$DATA_HOME/config/browser-profile` |
| Playwright browser cache | `$HOME/Library/Caches/ms-playwright` | `$HOME/.cache/ms-playwright` |

`CLAUDE_BIN` is resolved once by `scripts/preflight.py` (`shutil.which("claude")`) and written into `config/settings.local.yaml`, because the scheduler's `PATH` is not the login shell's `PATH` on either OS.

### The unattended command

```sh
DATA_HOME="$HOME/development/random/job-search"
CLAUDE_BIN="$(command -v claude || echo "$HOME/.local/bin/claude")"

"$CLAUDE_BIN" \
  -p "/job-search scan --headless --max 12" \
  --model opus \
  --fallback-model sonnet \
  --permission-mode dontAsk \
  --settings "$DATA_HOME/config/headless.settings.json" \
  --mcp-config "$DATA_HOME/config/mcp.headless.json" \
  --strict-mcp-config \
  --disallowedTools "AskUserQuestion" \
  --max-turns 120 \
  --max-budget-usd 4.00 \
  --session-id "$(python3 -c 'import uuid; print(uuid.uuid4())')" \
  --output-format json \
  < /dev/null
```

`python3 -c 'import uuid; print(uuid.uuid4())'` rather than `uuidgen`: `uuidgen` ships with macOS and with `util-linux` on most Linux distros, but is absent from minimal container images, and Python 3 is a hard dependency of this skill anyway.

Flag-by-flag rationale, with the documented behavior:

| Flag | Why |
| :-- | :-- |
| `-p` / `--print` | Non-interactive. "Claude Code exits with code 0 on success and a non-zero code when the run fails." SIGTERM aborts the turn, kills the Bash process tree, runs `SessionEnd` hooks, exits **143**. |
| `--permission-mode dontAsk` | "Claude Code auto-denies every tool call that would otherwise prompt you. Claude runs only actions matching your `permissions.allow` rules, read-only Bash commands, and calls approved by a PreToolUse hook… the session never waits for input." This is the documented CI recommendation. It also **denies `AskUserQuestion` outright**, which is the safety property we want. |
| **not** `--dangerously-skip-permissions` | `bypassPermissions` is documented as "Isolated containers and VMs only". On a developer laptop this job writes to a real browser profile holding logged-in job-board sessions, so use an explicit allowlist. In a genuinely disposable Linux container the calculus changes — see [Cross-platform notes](#cross-platform-notes). |
| `--settings <file>` | Carries `permissions.allow` for the run without polluting `~/.claude/settings.json`. "Values you set here override the same keys in your `settings.json` files for this session." |
| `--mcp-config` + `--strict-mcp-config` | Loads exactly the three servers this run needs and ignores every other MCP configuration, so a stray server in `~/.claude.json` can't change behavior. |
| `--disallowedTools "AskUserQuestion"` | Belt-and-braces with `dontAsk`. A bare tool name "removes the matching tools from Claude's context". |
| `--max-turns` | "Limit the number of agentic turns (print mode only). Exits with an error when the limit is reached." A runaway board crawl stops instead of billing forever. |
| `--max-budget-usd` | Hard dollar ceiling per run; subagent spend counts toward it (v2.1.217+). |
| `--session-id <uuid>` | Correlates the run log entry with a resumable transcript; `--resume <id>` works from any directory as of v2.1.223. |
| `--output-format json` | Machine-readable wrapper; the text is in `.result`, plus `total_cost_usd` and a per-model cost breakdown (client-side estimates). |
| `< /dev/null` | **Required on both platforms.** [verified locally] Without it the run printed `Warning: no stdin data received in 3s, proceeding without it. If piping from a slow command, redirect stdin explicitly: < /dev/null to skip, or wait longer.` and, in that attempt, produced no output at all. systemd services have no stdin by default, but cron and launchd both attach one. |

**Do not add `--bare`.** It skips auto-discovery of "hooks, skills, plugins, MCP servers, auto memory, and CLAUDE.md" — which removes the skill itself — and "In bare mode, Claude Code never reads OAuth credentials or the system keychain", which would break the OAuth-authenticated Notion MCP server. That second point bites harder on Linux, where there may be no keychain agent running under a systemd timer at all (see [Cross-platform notes](#cross-platform-notes)).

### Permission mode you actually get by default

The docs' starting-mode table lists `claude -p` or the Agent SDK → built-in starting mode `default` (Manual). **[verified locally]**: the `system/init` event of a plain `claude -p` run reported `"permissionMode": "default"`. In Manual mode with no allow rules, every board fetch and every file write prompts — and in `-p` there is nobody to answer, so the run stalls or denies. **Always pass `--permission-mode dontAsk` (or `acceptEdits` plus an allowlist) for scheduled runs.**

### `headless.settings.json`

Permission rules are matched literally — they do **not** expand `$HOME` or `~` — so this file is **generated**, not hand-written. `scripts/preflight.py --write-settings` renders it with the local absolute paths and the Chrome/Chromium binaries it actually found. The macOS instance:

```json
{
  "permissions": {
    "allow": [
      "Read",
      "Write",
      "Edit",
      "Glob",
      "Grep",
      "WebSearch",
      "WebFetch",
      "Bash(/Users/toddwardzinski/.claude/skills/job-search/scripts/*)",
      "Bash(python3 *)",
      "Bash(mkdir *)",
      "Bash(cp *)",
      "Bash(mv *)",
      "Bash(pandoc *)",
      "Bash(pdftotext *)",
      "Bash(firecrawl *)",
      "Bash(/Applications/Google Chrome.app/Contents/MacOS/Google Chrome *)",
      "mcp__firecrawl__firecrawl_search",
      "mcp__firecrawl__firecrawl_scrape",
      "mcp__firecrawl__firecrawl_map",
      "mcp__firecrawl__firecrawl_extract",
      "mcp__playwright__*",
      "mcp__notion__*"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push *)",
      "WebFetch(domain:mail.google.com)"
    ]
  },
  "env": {
    "MCP_TIMEOUT": "60000",
    "BASH_DEFAULT_TIMEOUT_MS": "180000"
  },
  "disableSkillShellExecution": false
}
```

On Linux the same generator emits `"Bash(/home/<user>/.claude/skills/job-search/scripts/*)"` and replaces the macOS app-bundle rule with whichever of these `preflight.py` resolved:

```json
"Bash(/usr/bin/google-chrome-stable *)",
"Bash(/usr/bin/google-chrome *)",
"Bash(/usr/bin/chromium *)",
"Bash(/usr/bin/chromium-browser *)",
"Bash(/snap/bin/chromium *)",
"Bash(/home/<user>/.cache/ms-playwright/chromium-*/chrome-linux/chrome *)"
```

Emitting only the binary that exists keeps the allowlist honest; emitting all of them would silently pre-approve a browser the machine does not have. MCP tool names follow `mcp__<server>__<tool>`, where `<server>` is the key you used in `--mcp-config`; that full name is what goes in permission rules, a skill's `allowed-tools`, a subagent `tools` field, or a hook matcher. The trailing-space prefix form matters for Bash rules: `Bash(git diff *)` prefix-matches, while `Bash(git diff*)` would also match `git diff-index`.

### `mcp.headless.json`

Also generated, because `--user-data-dir` and `--output-dir` need absolute paths:

```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": [
        "@playwright/mcp@latest",
        "--browser", "chrome",
        "--user-data-dir", "/Users/toddwardzinski/development/random/job-search/config/browser-profile",
        "--output-dir", "/Users/toddwardzinski/development/random/job-search/applications/_artifacts",
        "--save-session"
      ],
      "timeout": 600000
    },
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" },
      "timeout": 300000
    },
    "notion": {
      "type": "http",
      "url": "https://mcp.notion.com/mcp",
      "timeout": 120000
    }
  }
}
```

Platform differences in the `playwright` entry:

- **macOS desktop / Linux desktop with a live GUI session** — as written, headed, `--browser chrome`.
- **Headless Linux server or container** — add `"--headless"`, and switch `"--browser", "chrome"` to `"--browser", "chromium"` unless Google Chrome is actually installed; Playwright's bundled Chromium is the dependable choice on a server. In a container also add `"--no-sandbox"`: the project's own container image "only supports headless chromium at the moment" and the documented service invocation passes `--no-sandbox` ([playwright-mcp README](https://github.com/microsoft/playwright-mcp)).
- **`--user-data-dir` is the "log in once" mechanism on both platforms.** Omit `--isolated`, which "keep[s] the browser profile in memory". Without `--user-data-dir`, "a temporary directory will be created" and every login is lost. The defaults, if you ever let it pick: `~/Library/Caches/ms-playwright/mcp-{channel}-{workspace-hash}` on macOS, `~/.cache/ms-playwright/mcp-{channel}-{workspace-hash}` on Linux.
- **A profile directory is single-writer.** Chrome/Chromium locks it, so the run lock below is what stops a second scheduled run from failing with a profile-in-use error.

Firecrawl's stdio server is `npx -y firecrawl-mcp` with `FIRECRAWL_API_KEY` ([Firecrawl local MCP docs](https://docs.firecrawl.dev/mcp-server/local), [npm: firecrawl-mcp](https://www.npmjs.com/package/firecrawl-mcp)) — identical on both platforms, since it is pure Node. Notion's hosted server is `https://mcp.notion.com/mcp` with OAuth ([Connect to Notion MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp)); authorize it **once interactively** with `/mcp` on each machine before the first scheduled run.

An entry with a `url` but no `type` is a config error: Claude Code reads it as a stdio server and skips it with `MCP server "<name>" has a "url" but no "type"…`. A JSON entry's `type` accepts `streamable-http` as an alias for `http`.

**Caveat worth planning for:** MCP servers you authenticated interactively through claude.ai (the "connector" style) may be absent in headless/cron runs. That is why the scheduled config declares `notion` explicitly as an HTTP server rather than relying on a connector.

### Verifying MCP actually loaded

When `--mcp-config` is passed with `-p`, "Claude Code waits for still-pending servers before running the first turn, up to the `MCP_TIMEOUT` startup timeout, 30 seconds by default" (v2.1.221+). Invalid entries are **skipped, and the run continues and exits cleanly** — so a scheduled job can succeed while silently having no browser. `run_headless.py` gates on the init event rather than piping through `jq` (which is present on macOS by default but not on a minimal Linux image):

```python
# inside scripts/run_headless.py, when --output-format stream-json is used
for line in stream:
    ev = json.loads(line)
    if ev.get("type") == "system" and ev.get("subtype") == "init":
        errs = ev.get("mcp_server_errors") or []
        if errs:
            fail(f"mcp server errors: {errs}")
        missing = {"playwright", "firecrawl", "notion"} - {s["name"] for s in ev.get("mcp_servers", [])}
        if missing:
            warn(f"mcp servers absent: {sorted(missing)}")
        break
```

`mcp_server_errors` carries `name`, `type` (`unknown_type`, `url_missing_type`, `invalid_config`, `reserved_name`, …) and `message`; the key is omitted when there are none. `plugin_errors` works the same way for plugins.

### Detecting headless vs interactive (and which OS) from inside the skill

Three independent signals, in order of reliability:

1. **`CLAUDE_CODE_ENTRYPOINT`** — **[verified locally, macOS]**: `cli` in an interactive terminal session, `sdk-cli` in a `claude -p` run. `CLAUDECODE=1` is set in both, so `CLAUDECODE` alone tells you nothing about interactivity. This is a Claude Code variable, not an OS one, so it behaves the same on Linux. The env-vars doc documents `CLAUDE_CODE_ENTRYPOINT` as indicating "the entry point or mode of Claude Code execution" but does not enumerate values, so treat the exact strings as observed-not-contractual and default to headless on anything unrecognized.
2. **Absence of `AskUserQuestion`** — **[verified locally]**: the `system/init` `tools` array of a `claude -p` run on v2.1.235 did not contain `AskUserQuestion` (it listed `Task, Bash, Cron*, DesignSync, Edit, Enter/ExitWorktree, ListAgents, LSP, Monitor, NotebookEdit, PushNotification, Read, RemoteTrigger, ReportFindings, ScheduleWakeup, SendMessage, Skill, Task*, ToolSearch, WebFetch, WebSearch, Workflow, Write`). Independently, `dontAsk` mode "denies the built-in `AskUserQuestion` tool… even if your allow rules match", and no permission mode ever auto-approves it.
3. **An explicit `--headless` argument** in `$ARGUMENTS`, which the scheduler always passes. This is the override of record.

The probe is Python, not shell, so it behaves identically on both platforms and can report the OS in the same breath. `scripts/runtime_probe.py` (keep it under ~50 ms; it runs at skill-render time):

```python
#!/usr/bin/env python3
"""One line: mode=<interactive|headless> entrypoint=<v> os=<macos|linux|other> display=<yes|no> tty=<yes|no>"""
import os, sys, platform, shutil

INTERACTIVE = {"cli", "vscode", "jetbrains", "desktop"}
HEADLESS = {"sdk-cli", "sdk-py", "sdk-ts"}

entry = os.environ.get("CLAUDE_CODE_ENTRYPOINT", "unset")
mode = "interactive" if entry in INTERACTIVE else "headless"  # fail safe: never prompt when unsure

sysname = platform.system()
osname = {"Darwin": "macos", "Linux": "linux"}.get(sysname, sysname.lower() or "other")

if osname == "macos":
    display = "yes" if os.environ.get("SSH_CONNECTION") is None else "unknown"
elif osname == "linux":
    display = "yes" if (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")) else "no"
else:
    display = "unknown"

tty = "yes" if (sys.stdin.isatty() and sys.stdout.isatty()) else "no"
print(f"mode={mode} entrypoint={entry} os={osname} display={display} tty={tty} "
      f"python={platform.python_version()} chrome={'yes' if shutil.which('google-chrome') or shutil.which('chromium') or os.path.exists('/Applications/Google Chrome.app') else 'bundled-only'}")
```

Make it executable (`chmod +x`) so it can be invoked directly — that keeps the injected command free of a `$`, which is what the permission check rejects:

```yaml
allowed-tools: Bash(${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py)
```

```markdown
## Runtime
!`${CLAUDE_SKILL_DIR}/scripts/runtime_probe.py`

If `mode=headless` or `$ARGUMENTS` contains `--headless`:
- Never call AskUserQuestion. Never wait for input.
- Ambiguity resolves to the conservative branch: skip the job, record `needs_manual_apply`,
  and write the open question into the report under "Needs your decision".
- Never submit an application unless `auto_submit: true` AND `fit_score >= submit_threshold`
  AND the per-run submit cap has not been reached.
- End by writing reports/<date>.md, mirroring to Notion, and appending one run record.

If `display=no` (headless Linux host), do not attempt a headed browser: pass `--headless`
to Playwright, and mark any job whose ATS defeats headless mode as `needs_manual_apply`.
```

`tty` is a weak signal on its own (a piped interactive session also fails it), which is why it is reported but not decisive. `display` is the signal that decides whether a headed browser is even possible: on Linux, no `DISPLAY`/`WAYLAND_DISPLAY` means a headed Chrome will fail to start.

### Idempotence

Six mechanisms, all cheap and all platform-neutral:

1. **Single-flight lock.** `flock` exists on Linux and **not on macOS** (`command -v flock` → missing on this machine), and `mkdir` is atomic on APFS, ext4, xfs, btrfs, and overlayfs alike. So the lock is Python, in `scripts/run_headless.py`:

   ```python
   import os, sys, errno, signal, atexit, shutil
   from pathlib import Path

   def acquire(lock: Path):
       try:
           lock.mkdir(parents=False, exist_ok=False)          # atomic on every POSIX fs
       except FileExistsError:
           pid_file = lock / "pid"
           try:
               pid = int(pid_file.read_text().strip())
               os.kill(pid, 0)                                 # signal 0 == liveness probe
               print("job-search already running (pid %d); exiting 0" % pid)
               sys.exit(0)
           except (ValueError, FileNotFoundError, ProcessLookupError):
               shutil.rmtree(lock, ignore_errors=True)         # stale lock
               lock.mkdir()
           except PermissionError:                             # pid exists, owned by another user
               print("lock held by a live process; exiting 0"); sys.exit(0)
       (lock / "pid").write_text(str(os.getpid()))
       atexit.register(shutil.rmtree, str(lock), True)
       for sig in (signal.SIGINT, signal.SIGTERM):
           signal.signal(sig, lambda *_: sys.exit(143))
   ```

2. **Run id = the session id.** Pass `--session-id "$RUN_ID"`; the skill writes `memory/runs.jsonl` keyed by it and the report references it. Re-running the same `RUN_ID` is refused by `jobs_db.py`.
3. **Upsert, never append-blind.** Every job write goes through `scripts/jobs_db.py upsert`, keyed by `fingerprint`. A second run the same day updates `last_seen` and leaves `first_seen`, `status`, and `last_shown` alone.
4. **Cooldown deduplicates *attention*.** Even if the boards return identical results twice, the 14-day rule means an already-shown job cannot re-enter a report.
5. **Atomic file writes.** Write `X.tmp` in the same directory, then `os.replace()` — atomic on POSIX and the reason not to use `shutil.move` across filesystems.
6. **Reports are date-stamped and versioned.** `reports/2026-08-19.md` is overwritten only by the run recorded as the owner of that date; a second run the same day writes `reports/2026-08-19.r2.md`. Applications go to `applications/<date>-<fingerprint>/`, which is inherently idempotent.

### Scheduling: cron (both platforms)

`cron` exists on macOS and Linux and is the lowest common denominator. Its `PATH` is minimal on both, and the binaries this skill needs are not on it: on this Mac `claude`, `node`, and `npx` are in `$HOME/.local/bin` and `python3`/`pandoc`/`firecrawl` in `/opt/homebrew/bin`; on a typical Linux host they are in `$HOME/.local/bin` and `/usr/bin`. Set `PATH` in the crontab itself, and let `run_headless.py` do everything else:

```crontab
SHELL=/bin/sh
# macOS (Apple silicon Homebrew). On Intel macOS use /usr/local/bin instead of /opt/homebrew/bin.
PATH=/Users/toddwardzinski/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin
MAILTO=""
30 6 * * 1-5 /Users/toddwardzinski/.claude/skills/job-search/scripts/run_headless.py scan >> /Users/toddwardzinski/development/random/job-search/memory/logs/cron.log 2>&1 < /dev/null
```

```crontab
SHELL=/bin/sh
# Linux
PATH=/home/todd/.local/bin:/usr/local/bin:/usr/bin:/bin
MAILTO=""
30 6 * * 1-5 /home/todd/.claude/skills/job-search/scripts/run_headless.py scan >> /home/todd/development/random/job-search/memory/logs/cron.log 2>&1 < /dev/null
```

Two platform caveats:

- **macOS**: `/usr/sbin/cron` needs **Full Disk Access** (System Settings → Privacy & Security → Full Disk Access) to read most user data, and cron jobs run outside the GUI session's Keychain unlock in some configurations. launchd is the better answer below.
- **Linux**: a bare `cron` job runs without a D-Bus session or keyring agent, which matters if Claude Code's OAuth credentials are stored in a Secret Service keyring rather than a file. Check with a manual run under `env -i` before trusting the schedule.

### Scheduling: launchd (macOS, recommended)

`~/Library/LaunchAgents/info.wardzinski.job-search.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>info.wardzinski.job-search</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/toddwardzinski/.claude/skills/job-search/scripts/run_headless.py</string>
    <string>scan</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/toddwardzinski/development/random/job-search</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/Users/toddwardzinski/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    <key>HOME</key>
    <string>/Users/toddwardzinski</string>
    <key>MCP_TIMEOUT</key>
    <string>60000</string>
  </dict>
  <key>StartCalendarInterval</key>
  <array>
    <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
    <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>6</integer><key>Minute</key><integer>30</integer></dict>
  </array>
  <key>RunAtLoad</key>
  <false/>
  <key>StandardOutPath</key>
  <string>/Users/toddwardzinski/development/random/job-search/memory/logs/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>/Users/toddwardzinski/development/random/job-search/memory/logs/launchd.err.log</string>
  <key>ProcessType</key>
  <string>Background</string>
</dict>
</plist>
```

```sh
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/info.wardzinski.job-search.plist
launchctl enable gui/$(id -u)/info.wardzinski.job-search
launchctl kickstart -k gui/$(id -u)/info.wardzinski.job-search   # run it now
launchctl print gui/$(id -u)/info.wardzinski.job-search | head -30
```

`ProcessType Background` keeps the agent out of the foreground QoS band. A `gui/$UID` LaunchAgent has a GUI session when the user is logged in — which a headed Chrome needs; a `system/` LaunchDaemon does not.

### Scheduling: systemd user timer (Linux, recommended)

`~/.config/systemd/user/job-search.service`:

```ini
[Unit]
Description=job-search scan
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=%h/development/random/job-search
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin
Environment=MCP_TIMEOUT=60000
ExecStart=%h/.claude/skills/job-search/scripts/run_headless.py scan
StandardInput=null
TimeoutStartSec=45min
```

`~/.config/systemd/user/job-search.timer`:

```ini
[Unit]
Description=job-search weekday scan at 06:30

[Timer]
OnCalendar=Mon..Fri 06:30
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

```sh
systemctl --user daemon-reload
systemctl --user enable --now job-search.timer
systemctl --user list-timers job-search.timer
systemctl --user start job-search.service     # run it now
journalctl --user -u job-search.service -n 200 --no-pager
loginctl enable-linger "$USER"                # required for timers to fire with no active login
```

Three things this buys over cron on Linux: `Persistent=true` catches up a run missed while the machine was off; `journalctl` gives structured logs without shell redirection; `StandardInput=null` is the systemd equivalent of `< /dev/null`. `loginctl enable-linger` is mandatory on a server — without it, user units stop when the last session ends.

For a **headless Linux host** the service should additionally set `Environment=JOBSEARCH_BROWSER_MODE=headless`, which `config.py` reads as an override that forces Playwright's `--headless` and downgrades any ATS that requires a headed browser to `needs_manual_apply`.

### `scripts/run_headless.py`

One Python entrypoint that every scheduler calls, so the scheduler stanza stays trivial and identical across platforms.

```python
#!/usr/bin/env python3
"""Scheduler entrypoint for the job-search skill. Portable across macOS and Linux."""
import json, os, shutil, subprocess, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

DATA_HOME = Path(os.environ.get("JOBSEARCH_HOME", Path.home() / "development/random/job-search"))
SKILL_DIR = Path.home() / ".claude/skills/job-search"
SUB = sys.argv[1] if len(sys.argv) > 1 else "scan"
RUN_ID = str(uuid.uuid4())

(DATA_HOME / "memory/logs").mkdir(parents=True, exist_ok=True)
(DATA_HOME / "memory/runs").mkdir(parents=True, exist_ok=True)

acquire(DATA_HOME / "memory/.run.lock")          # see the lock helper above

claude = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or str(Path.home() / ".local/bin/claude")
if not Path(claude).exists():
    sys.exit("claude CLI not found; set CLAUDE_BIN or add it to PATH")

result_path = DATA_HOME / f"memory/runs/{RUN_ID}.json"
cmd = [
    claude, "-p", f"/job-search {SUB} --headless --run {RUN_ID}",
    "--model", "opus", "--fallback-model", "sonnet",
    "--permission-mode", "dontAsk",
    "--settings", str(DATA_HOME / "config/headless.settings.json"),
    "--mcp-config", str(DATA_HOME / "config/mcp.headless.json"), "--strict-mcp-config",
    "--disallowedTools", "AskUserQuestion",
    "--max-turns", "120", "--max-budget-usd", "4.00",
    "--session-id", RUN_ID,
    "--output-format", "json",
]

started = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
with open(os.devnull) as devnull, open(result_path, "w") as out:
    rc = subprocess.call(cmd, cwd=str(DATA_HOME), stdin=devnull, stdout=out)

try:
    res = json.loads(result_path.read_text())
except (ValueError, OSError):
    print(f"{started} run={RUN_ID} rc={rc} (no JSON result)"); sys.exit(rc or 3)

print("{} run={} error={} turns={} cost={}".format(
    started, res.get("session_id"), res.get("is_error"), res.get("num_turns"), res.get("total_cost_usd")))

# A skill invocation aborted at render time returns success with zero turns and an empty result.
if res.get("is_error") or not res.get("num_turns"):
    sys.exit("job-search: empty run — skill likely aborted at render time (check injected commands)")
sys.exit(rc)
```

Exit-code contract for the caller: `0` success; non-zero failure (including `--max-turns` exhaustion, which "Exits with an error when the limit is reached"); `143` if something SIGTERM'd it. The `num_turns == 0` guard exists because of the verified silent-abort failure mode: an invocation killed by a failed injected command returns `subtype: "success"`, `is_error: false`, `num_turns: 0`, empty `result` **[verified locally]**, which every scheduler would otherwise record as a clean success.

### Follow-up runs from scheduled output

Because sessions resume by id from any directory (v2.1.223+), a later interactive review can attach to the scan:

```sh
claude --resume "$RUN_ID"                       # interactive, full context
claude -p "/job-search pick 2,4 --run $RUN_ID"  # headless, fresh session, resolves via memory
```

Prefer the second form: it does not depend on transcript retention, and it is the same code path a human uses.

---

## State & memory design

### Layout

```text
~/development/random/job-search/
├── resume/                     # resume.pdf / resume.md / resume.txt (+ resume.url)
├── config/
│   ├── settings.yaml           # committed, human-authored
│   ├── settings.local.yaml     # machine-written (notion ids, bootstrap results); git-ignored
│   ├── profile.md              # personal answers to screening questions
│   ├── job-board-links.md      # the board list (does not exist yet — bootstrap creates it)
│   ├── headless.settings.json
│   ├── mcp.headless.json
│   └── browser-profile/        # Playwright persistent profile; git-ignored
├── memory/
│   ├── jobs.jsonl              # one JSON object per line, keyed by fingerprint
│   ├── disinterest.yaml        # "not interested" patterns, human-editable
│   ├── runs.jsonl              # one record per invocation
│   ├── runs/<run_id>.json      # raw --output-format json result per run
│   ├── notion-outbox.jsonl     # rows that failed to mirror; flushed next run
│   ├── logs/
│   └── .run.lock/
├── reports/YYYY-MM-DD.md
└── applications/YYYY-MM-DD-<fp>/{resume.md,resume.pdf,cover-letter.md,cover-letter.pdf,answers.json,screenshots/}
```

`memory/` is a git repository (`git init` on first run). One JSON object per line, keys emitted in a fixed order, `ensure_ascii=false`, LF endings, no trailing whitespace — so a diff of `jobs.jsonl` shows exactly which jobs changed and how. `disinterest.yaml` is authored to be edited by hand. `config/browser-profile/`, `config/settings.local.yaml`, and anything under `applications/*/screenshots/` are git-ignored.

Why JSONL and not SQLite: `sqlite3` ships with macOS and with nearly every Linux distribution, but JSONL is diffable, greppable, editable in any editor, survives partial corruption (one bad line, not one bad file), and the working set here is thousands of rows, not millions. `jobs_db.py` loads the whole file, mutates, and rewrites atomically — at 10k rows that is a few megabytes and single-digit milliseconds.

### Dedup key

Two identifiers, because "the same job" and "the same posting" are different things.

**`fingerprint`** — job identity, stable across boards. This is the primary key of `jobs.jsonl` and the Notion upsert key.

```python
# scripts/fingerprint.py
import hashlib, re, unicodedata
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

LEGAL = r"\b(inc|inc\.|llc|l\.l\.c\.|ltd|limited|corp|corporation|co|company|gmbh|plc|s\.?a\.?|n\.?v\.?|ag|ab|oy|pty)\b"
NOISE = r"\((remote|hybrid|onsite|on-site|us|usa|united states)\)|\b(req|requisition|job)\s*#?\s*[a-z0-9\-]{3,}\b|\b[a-z]{1,3}-?\d{4,}\b"
STATES = {"virginia": "va", "maryland": "md", "district of columbia": "dc", "california": "ca",
          "new york": "ny", "texas": "tx", "washington": "wa", "massachusetts": "ma"}

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def company_key(company: str) -> str:
    return _norm(re.sub(LEGAL, " ", _norm(company)))

def title_key(title: str) -> str:
    t = re.sub(NOISE, " ", (title or "").lower())
    t = _norm(t)
    t = re.sub(r"\b(sr|snr)\b", "senior", t)
    t = re.sub(r"\b(jr)\b", "junior", t)
    t = re.sub(r"\bmgr\b", "manager", t)
    t = re.sub(r"\beng\b", "engineer", t)
    t = re.sub(r"\bswe\b", "software engineer", t)
    return re.sub(r"\s+", " ", t).strip()

def location_key(location: str, remote: str = "") -> str:
    loc = _norm(location)
    if remote == "remote" or "remote" in loc:
        return "remote-us" if ("us" in loc or "united states" in loc or not loc) else f"remote-{loc.replace(' ', '-')}"
    for long, short in STATES.items():
        loc = re.sub(rf"\b{long}\b", short, loc)
    parts = [p for p in loc.split() if p not in ("usa", "us", "united", "states")]
    return "-".join(parts) or "unknown"

TRACKING = re.compile(r"^(utm_|gh_|lever-|ref$|source$|src$|trk$|trackingId$|refId$|jk$|from$|fbclid$|gclid$|mc_)", re.I)

def canonical_url(url: str) -> str:
    p = urlsplit(url.strip())
    host = p.netloc.lower().removeprefix("www.")
    path = p.path.rstrip("/") or "/"
    q = [(k, v) for k, v in parse_qsl(p.query, keep_blank_values=False) if not TRACKING.match(k)]
    q.sort()
    return urlunsplit(("https", host, path, urlencode(q), ""))

def fingerprint(company: str, title: str, location: str, remote: str = "") -> str:
    raw = "\x1f".join([company_key(company), title_key(title), location_key(location, remote)])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

def posting_id(url: str) -> str:
    return hashlib.sha256(canonical_url(url).encode()).hexdigest()[:16]
```

**`posting_id`** — one specific listing URL. Each job record holds a `sources[]` array of postings, so "Staff AI Solutions Architect @ Anthropic, Reston VA" found on Greenhouse, LinkedIn, and Indeed is **one** row with three sources, shown once and mirrored to one Notion page.

Collision guard: before merging a new posting into an existing fingerprint, require `SequenceMatcher(a=title_key_new, b=title_key_existing).ratio() >= 0.90` **or** an exact `canonical_url` match on an existing source. If the fingerprint matches but the titles diverge, write a new row with fingerprint `<fp>-2` and log a `collision` event in `runs.jsonl`. This is rare but silent-wrong if unhandled.

Re-post detection: `content_hash = sha256(normalized description text)[:16]`. If an existing job's `content_hash` changes materially **and** `posted_at` moves forward, bump `version`, reset `last_shown` to `null` and `status` to `new` — a genuinely re-opened req deserves to be shown again before the 14 days elapse.

### JSON Schema for `memory/jobs.jsonl`

One object per line, validated against this (draft 2020-12) by `jobs_db.py --validate`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://wardzinski.info/schemas/job-search/job-1.json",
  "title": "job-search job record",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema", "fingerprint", "title", "company", "canonical_url", "source",
               "first_seen", "last_seen", "status"],
  "properties": {
    "schema":         { "const": 1 },
    "fingerprint":    { "type": "string", "pattern": "^[0-9a-f]{16}(-[0-9]+)?$" },
    "title":          { "type": "string", "minLength": 1 },
    "company":        { "type": "string", "minLength": 1 },
    "company_key":    { "type": "string" },
    "title_key":      { "type": "string" },
    "location":       { "type": "string" },
    "location_key":   { "type": "string" },
    "remote":         { "enum": ["remote", "hybrid", "onsite", "unknown"] },
    "url":            { "type": "string", "format": "uri" },
    "canonical_url":  { "type": "string", "format": "uri" },
    "source":         { "type": "string", "description": "board key of the primary source, e.g. greenhouse, lever, linkedin, indeed, ashby, workday, builtin, weworkremotely" },
    "sources": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["source", "canonical_url", "posting_id", "first_seen", "last_seen"],
        "properties": {
          "source":        { "type": "string" },
          "url":           { "type": "string", "format": "uri" },
          "canonical_url": { "type": "string", "format": "uri" },
          "posting_id":    { "type": "string", "pattern": "^[0-9a-f]{16}$" },
          "first_seen":    { "type": "string", "format": "date-time" },
          "last_seen":     { "type": "string", "format": "date-time" }
        }
      }
    },
    "posted_at":      { "type": ["string", "null"], "format": "date" },
    "closes_at":      { "type": ["string", "null"], "format": "date" },
    "comp_min":       { "type": ["number", "null"] },
    "comp_max":       { "type": ["number", "null"] },
    "comp_currency":  { "type": ["string", "null"], "default": "USD" },
    "comp_basis":     { "enum": ["year", "hour", "day", "unknown", null] },
    "first_seen":     { "type": "string", "format": "date-time" },
    "last_seen":      { "type": "string", "format": "date-time" },
    "last_shown":     { "type": ["string", "null"], "format": "date-time" },
    "shown_count":    { "type": "integer", "minimum": 0, "default": 0 },
    "snooze_until":   { "type": ["string", "null"], "format": "date-time" },
    "status": {
      "enum": ["new", "shown", "selected", "applied", "not_interested", "expired", "needs_manual_apply"]
    },
    "status_changed_at": { "type": "string", "format": "date-time" },
    "status_reason":  { "type": ["string", "null"] },
    "fit_score":      { "type": ["integer", "null"], "minimum": 0, "maximum": 100 },
    "fit_reasons":    { "type": "array", "items": { "type": "string" } },
    "suppressed_by":  { "type": ["string", "null"], "description": "id of the disinterest rule that hid this job" },
    "content_hash":   { "type": ["string", "null"], "pattern": "^[0-9a-f]{16}$" },
    "version":        { "type": "integer", "minimum": 1, "default": 1 },
    "application_dir":{ "type": ["string", "null"] },
    "applied_at":     { "type": ["string", "null"], "format": "date-time" },
    "submitted":      { "type": "boolean", "default": false },
    "notion_page_id": { "type": ["string", "null"] },
    "notion_synced_at": { "type": ["string", "null"], "format": "date-time" },
    "run_ids":        { "type": "array", "items": { "type": "string" } },
    "notes":          { "type": "string", "default": "" }
  }
}
```

All timestamps are RFC 3339 UTC with a `Z` suffix, second precision. Dates (`posted_at`, `closes_at`) are plain `YYYY-MM-DD` because boards rarely give more.

### Four example records

(shown pretty-printed; on disk each is a single line)

```json
{"schema":1,"fingerprint":"b7f3c1a9d2e40185","title":"Staff AI Solutions Architect","company":"Anthropic","company_key":"anthropic","title_key":"staff ai solutions architect","location":"Reston, VA","location_key":"reston-va","remote":"hybrid","url":"https://job-boards.greenhouse.io/anthropic/jobs/4512345?gh_src=linkedin","canonical_url":"https://job-boards.greenhouse.io/anthropic/jobs/4512345","source":"greenhouse","sources":[{"source":"greenhouse","url":"https://job-boards.greenhouse.io/anthropic/jobs/4512345?gh_src=linkedin","canonical_url":"https://job-boards.greenhouse.io/anthropic/jobs/4512345","posting_id":"1c9a44e0bb7f2d31","first_seen":"2026-08-19T10:31:04Z","last_seen":"2026-08-19T10:31:04Z"},{"source":"linkedin","url":"https://www.linkedin.com/jobs/view/4198877612/?trackingId=abc","canonical_url":"https://linkedin.com/jobs/view/4198877612","posting_id":"7d2b0f5c8e1a4460","first_seen":"2026-08-19T10:31:44Z","last_seen":"2026-08-19T10:31:44Z"}],"posted_at":"2026-08-17","closes_at":null,"comp_min":215000,"comp_max":270000,"comp_currency":"USD","comp_basis":"year","first_seen":"2026-08-19T10:31:04Z","last_seen":"2026-08-19T10:31:44Z","last_shown":"2026-08-19T10:33:12Z","shown_count":1,"snooze_until":null,"status":"shown","status_changed_at":"2026-08-19T10:33:12Z","status_reason":null,"fit_score":91,"fit_reasons":["8 yrs enterprise AI architecture matches 'staff' scope","Reston HQ is 6 mi from home location","resume lists vLLM + OpenShift AI, JD asks for inference serving at scale"],"suppressed_by":null,"content_hash":"55ab90c3e7d14f02","version":1,"application_dir":null,"applied_at":null,"submitted":false,"notion_page_id":"26ab1f9f-4c5f-80b1-8d3b-d10a6b1d2f4e","notion_synced_at":"2026-08-19T10:34:02Z","run_ids":["9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"],"notes":""}
```

```json
{"schema":1,"fingerprint":"3ac91b7e55d0f284","title":"Senior Sales Engineer, AI Platform","company":"Databricks","company_key":"databricks","title_key":"senior sales engineer ai platform","location":"Remote - US","location_key":"remote-us","remote":"remote","url":"https://www.databricks.com/company/careers/open-positions/job?gh_jid=7712233","canonical_url":"https://databricks.com/company/careers/open-positions/job?gh_jid=7712233","source":"greenhouse","sources":[{"source":"greenhouse","url":"https://www.databricks.com/company/careers/open-positions/job?gh_jid=7712233","canonical_url":"https://databricks.com/company/careers/open-positions/job?gh_jid=7712233","posting_id":"a0e4417cb2d95f68","first_seen":"2026-08-05T11:02:19Z","last_seen":"2026-08-19T10:31:20Z"}],"posted_at":"2026-08-04","closes_at":null,"comp_min":null,"comp_max":null,"comp_currency":"USD","comp_basis":"unknown","first_seen":"2026-08-05T11:02:19Z","last_seen":"2026-08-19T10:31:20Z","last_shown":"2026-08-05T11:04:40Z","shown_count":1,"snooze_until":null,"status":"not_interested","status_changed_at":"2026-08-05T11:19:08Z","status_reason":"quota-carrying sales role; wants engineering ownership","fit_score":54,"fit_reasons":["strong platform overlap","role is quota-carrying pre-sales, not IC engineering"],"suppressed_by":"dis-002","content_hash":"91cc07be4a2d8351","version":1,"application_dir":null,"applied_at":null,"submitted":false,"notion_page_id":"26ab1f9f-4c5f-8022-9f01-c3d40e5a6b71","notion_synced_at":"2026-08-05T11:19:31Z","run_ids":["1b2c3d4e-5f60-4712-8934-a5b6c7d8e9f0","9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"],"notes":"Recruiter emailed 2026-08-06; declined."}
```

```json
{"schema":1,"fingerprint":"e21d7f04c6b93a5a","title":"Principal Solutions Architect, Generative AI","company":"Red Hat","company_key":"red hat","title_key":"principal solutions architect generative ai","location":"Raleigh, NC","location_key":"raleigh-nc","remote":"hybrid","url":"https://redhat.wd5.myworkdayjobs.com/en-US/jobs/job/Raleigh/Principal-Solutions-Architect_R-051884","canonical_url":"https://redhat.wd5.myworkdayjobs.com/en-US/jobs/job/Raleigh/Principal-Solutions-Architect_R-051884","source":"workday","sources":[{"source":"workday","url":"https://redhat.wd5.myworkdayjobs.com/en-US/jobs/job/Raleigh/Principal-Solutions-Architect_R-051884","canonical_url":"https://redhat.wd5.myworkdayjobs.com/en-US/jobs/job/Raleigh/Principal-Solutions-Architect_R-051884","posting_id":"4f7b1ae09c25d836","first_seen":"2026-08-12T06:31:55Z","last_seen":"2026-08-19T10:32:03Z"}],"posted_at":"2026-08-11","closes_at":null,"comp_min":185000,"comp_max":230000,"comp_currency":"USD","comp_basis":"year","first_seen":"2026-08-12T06:31:55Z","last_seen":"2026-08-19T10:32:03Z","last_shown":"2026-08-12T06:34:10Z","shown_count":1,"snooze_until":null,"status":"applied","status_changed_at":"2026-08-12T19:22:41Z","status_reason":"tailored resume + cover letter submitted","fit_score":88,"fit_reasons":["direct OpenShift AI experience","JD names vLLM and llm-d explicitly"],"suppressed_by":null,"content_hash":"c8140b9a67e3fd25","version":1,"application_dir":"applications/2026-08-12-e21d7f04c6b93a5a","applied_at":"2026-08-12T19:22:41Z","submitted":true,"notion_page_id":"26ab1f9f-4c5f-8033-b117-2ea5f9c0d3b8","notion_synced_at":"2026-08-12T19:23:05Z","run_ids":["c3d4e5f6-0718-4923-9a45-b6c7d8e9f012"],"notes":"Workday required a 'Why Red Hat?' essay; answer stored in answers.json and reviewed before submit."}
```

```json
{"schema":1,"fingerprint":"5d0aa38f91c7e462","title":"Machine Learning Engineer II","company":"Capital One","company_key":"capital one","title_key":"machine learning engineer ii","location":"McLean, VA","location_key":"mclean-va","remote":"hybrid","url":"https://www.capitalonecareers.com/en/job/mclean/machine-learning-engineer-ii/1732/84991123","canonical_url":"https://capitalonecareers.com/en/job/mclean/machine-learning-engineer-ii/1732/84991123","source":"phenom","sources":[{"source":"phenom","url":"https://www.capitalonecareers.com/en/job/mclean/machine-learning-engineer-ii/1732/84991123","canonical_url":"https://capitalonecareers.com/en/job/mclean/machine-learning-engineer-ii/1732/84991123","posting_id":"90c1de274ab5f306","first_seen":"2026-08-19T10:32:31Z","last_seen":"2026-08-19T10:32:31Z"}],"posted_at":"2026-08-18","closes_at":null,"comp_min":158000,"comp_max":180000,"comp_currency":"USD","comp_basis":"year","first_seen":"2026-08-19T10:32:31Z","last_seen":"2026-08-19T10:32:31Z","last_shown":"2026-08-19T10:33:12Z","shown_count":1,"snooze_until":null,"status":"needs_manual_apply","status_changed_at":"2026-08-19T10:41:07Z","status_reason":"ATS required SMS verification before the application form loaded","fit_score":76,"fit_reasons":["MLE II is a level below current scope","strong local match, 11 mi commute"],"suppressed_by":null,"content_hash":"2b6f8ce0417da39c","version":1,"application_dir":"applications/2026-08-19-5d0aa38f91c7e462","applied_at":null,"submitted":false,"notion_page_id":"26ab1f9f-4c5f-8044-a2f9-77b0c1d2e3f4","notion_synced_at":"2026-08-19T10:41:22Z","run_ids":["9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"],"notes":"Resume PDF generated; form blocked at step 2. Retry interactively."}
```

### The 14-day cooldown, stated precisely

```
COOLDOWN = 14 days = 1209600 seconds
now      = run start time, UTC

eligible_to_show(job, now):
  1. if job.status in {applied, not_interested, expired}                    -> false
  2. if job.snooze_until is not null and now < job.snooze_until             -> false
  3. if matches_hard_disinterest(job)                                       -> false  (set job.suppressed_by)
  4. if job.status == needs_manual_apply                                    -> false for the ranked list;
                                                                               always listed in the report's
                                                                               "Needs your decision" section
  5. if job.status == new                                                   -> true
  6. if job.status in {shown, selected}:
        return job.last_shown is null
               or (now - job.last_shown) >= COOLDOWN
```

Rules that keep this honest:

- **`last_shown` is written only when the job actually reaches the user** — i.e. when the report file has been written to disk (interactive or headless). Scraping a job, scoring it, or ranking it 14th out of 12 does **not** set `last_shown`. Set it in one place, immediately after the report write succeeds, in the same transaction that appends the run record.
- **`shown_count` increments with `last_shown`.** After `shown_count >= 3` with no action, extend the cooldown to 45 days rather than 14 — three ignores is a preference signal.
- **Cooldown is wall-clock, not calendar.** `(now - last_shown) >= 14*86400` on UTC instants. A job shown 2026-08-05T10:33Z is eligible again from 2026-08-19T10:33Z. No timezone or DST arithmetic anywhere.
- **`selected` decays.** If a job sits at `selected` for more than 7 days with no `application_dir`, revert it to `shown` with `status_reason: "selection expired"` so it re-enters the pool after its cooldown instead of being lost.
- **Version bump beats cooldown** (see re-post detection above): a materially changed req resets `status` to `new` and `last_shown` to `null`.
- **Expiry**: if `now - last_seen > 45 days`, set `status = expired`. Never delete rows — an expired row is what stops the same dead posting from being "discovered" again next quarter.
- **`--force`** on the CLI overrides rules 5–6 for one run (used when the user says "show me everything again"); it never overrides rules 1–3.

### `memory/disinterest.yaml`

Human-editable, ordered, and auditable. Every rule carries the evidence that created it.

```yaml
# memory/disinterest.yaml
# Rules are evaluated top to bottom. strength: hard -> job is never shown.
#                                     soft -> fit_score penalty, still shown if it survives.
# Regex is Python re, applied case-insensitively to the normalized title_key/company_key.
version: 1
rules:
  - id: dis-001
    scope: title
    pattern: '\b(intern|internship|co-?op|apprentice)\b'
    strength: hard
    reason: "Not seeking early-career roles"
    created: 2026-07-02
    created_by: user
    hits: 14

  - id: dis-002
    scope: title
    family: sales-engineering
    pattern: '\b(sales|pre-?sales|field|account)\s+(engineer|architect|consultant|executive)\b|\bsolutions?\s+engineer\b'
    strength: hard
    reason: "Dismissed 'Senior Sales Engineer, AI Platform' @ Databricks: quota-carrying, wants engineering ownership"
    created: 2026-08-05
    created_by: generalized
    promoted_from: soft
    promoted_on: 2026-08-14
    evidence: ["3ac91b7e55d0f284", "77e2b1c40a9d3f18"]
    hits: 6

  - id: dis-003
    scope: company
    pattern: '^(acme staffing|talentbridge|robert half|teksystems|insight global)$'
    strength: hard
    reason: "Staffing agencies / body shops"
    created: 2026-07-02
    created_by: user
    hits: 41

  - id: dis-004
    scope: title
    family: management
    pattern: '\b(director|vp|vice president|head of)\b'
    strength: soft
    penalty: 20
    reason: "Prefers hands-on IC/architect scope; open to player-coach"
    created: 2026-07-19
    created_by: generalized
    evidence: ["c4a1e9b3d5027f6a"]
    hits: 9

  - id: dis-005
    scope: comp
    min_base: 170000
    strength: soft
    penalty: 30
    reason: "Below current base; only worth showing if the rest is exceptional"
    created: 2026-07-02
    created_by: user
    hits: 22

  - id: dis-006
    scope: location
    pattern: '^(?!remote-|reston-va|mclean-va|arlington-va|herndon-va|tysons-va|washington-dc|raleigh-nc)'
    strength: soft
    penalty: 15
    reason: "Outside NoVA/DC or remote; relocation only for exceptional fit"
    created: 2026-07-02
    created_by: user
    hits: 130
```

### How "not interested" generalizes

Dismissing one job must suppress the *family*, not just that row — but it must not silently blacklist half the market. The escalation ladder:

1. **Record the instance.** Set the job's `status = not_interested`, `status_reason = <the user's words>`, `status_changed_at = now`. This alone is permanent for that fingerprint.
2. **Derive a family.** Look the job's `title_key` up in `references/title-families.md`, a curated table mapping ~60 normalized title stems to a family id plus a vetted regex. Example rows:

   | title stem | family | regex |
   | :-- | :-- | :-- |
   | `sales engineer`, `solutions engineer`, `presales engineer`, `field engineer` | `sales-engineering` | `\b(sales\|pre-?sales\|field\|account)\s+(engineer\|architect\|consultant\|executive)\b\|\bsolutions?\s+engineer\b` |
   | `engineering manager`, `director of engineering`, `head of platform` | `management` | `\b(director\|vp\|vice president\|head of\|engineering manager)\b` |
   | `data engineer`, `analytics engineer` | `data-engineering` | `\b(data\|analytics)\s+engineer\b` |
   | `devops engineer`, `sre`, `platform engineer` | `infrastructure` | `\b(devops\|site reliability\|sre\|platform)\s*engineer\b` |

   A curated table beats letting the model invent a regex per dismissal: it is reviewable, it is stable across runs, and it cannot produce a pattern like `.*engineer.*` that nukes the whole search.
3. **First dismissal in a family → `strength: soft`** with `penalty: 20` and `created_by: generalized`. The family still appears, ranked lower, so a false generalization is visible and cheap to reverse.
4. **Second dismissal in the same family within 90 days → promote to `strength: hard`**, stamping `promoted_from: soft`, `promoted_on`, and appending both fingerprints to `evidence`. Two independent dismissals is a real preference.
5. **Company-scope and comp-scope dismissals go straight to `hard`** — "not this employer" and "not below $X" are unambiguous, and neither generalizes beyond its literal target.
6. **Explain, then apply.** When a rule created by `generalized` first suppresses a *different* job, the report says so: `— suppressed by dis-002 (sales-engineering, learned 2026-08-05). Undo: /job-search unhide dis-002`. Silent suppression is how a job-search tool quietly stops working.
7. **No auto-created rule ever suppresses a job with `fit_score >= 90`.** It downgrades it into the "Suppressed but high-fit" section of the report instead. Hand-written user rules have no such override — if the user wrote it, obey it.
8. **`hits` is maintained** on every evaluation. A `soft` rule with `hits > 100` and zero subsequent dismissals in that family is surfaced in the monthly summary as "possibly over-broad".

### `memory/runs.jsonl`

```json
{"run_id":"9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f","started_at":"2026-08-19T10:30:02Z","ended_at":"2026-08-19T10:41:30Z","mode":"headless","entrypoint":"sdk-cli","subcommand":"scan","args":"scan --headless --run 9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f","query":"AI/ML architect, Reston VA + remote US","boards_attempted":11,"boards_ok":9,"boards_failed":[{"board":"indeed","reason":"403 from Firecrawl; Playwright fallback hit a captcha"},{"board":"dice","reason":"MCP tool timeout after 600000ms"}],"jobs_seen":142,"jobs_new":17,"jobs_suppressed":38,"jobs_in_cooldown":24,"jobs_shown":12,"report":"reports/2026-08-19.md","notion_upserts":12,"notion_failures":0,"applications_started":1,"applications_submitted":0,"cost_usd":2.86,"num_turns":74,"exit":"ok"}
```

`boards_failed` with a human-readable `reason` is the single most useful field here: a silently shrinking result set is the characteristic failure mode of a scraper-backed job search, and this makes it visible in `git log`.

### Human-editable and git-friendly, concretely

- `jobs_db.py` writes with `json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False)` over an explicit key order, so a status change is a one-line diff.
- Rows are kept sorted by `first_seen` then `fingerprint`, so new jobs append near the end and diffs stay local.
- `jobs_db.py --validate` runs the JSON Schema over every line and exits non-zero with `line N: <error>`; the skill runs it before and after every mutation.
- If a hand-edit corrupts a line, `jobs_db.py` quarantines that single line to `memory/jobs.badlines.jsonl` and continues, rather than failing the run.
- Auto-commit at the end of each run: `git -C memory add -A && git -C memory commit -q -m "job-search run <run_id>: +<new> new, <shown> shown, <applied> applied"`. Never `git push` (denied in `headless.settings.json`).

---

## Interactive selection UX

### The constraint that decides the design

`AskUserQuestion` in Claude Code v2.1.235 accepts **1–4 questions**, each with **2–4 options**, with an optional `multiSelect` flag; an "Other" free-text row is always appended automatically. Ten jobs therefore **cannot** be expressed as one multi-select question. Any design that tries to shoehorn them in ends up as three awkward questions ("jobs 1–4?", "jobs 5–8?", "jobs 9–10?") that read like a phone tree.

So: **the numbered list is the interface, typed numbers are the primary input, and `AskUserQuestion` is used for the one genuinely multiple-choice decision — what to do with the picks.**

### Interactive flow

**Step 1 — the skill prints the ranked list** (markdown table, terminal-friendly, `file_path:line`-style links are useless here so full URLs are shown):

```
Today's top 12 — 2026-08-19 · run 9f1c2d3e · 142 seen, 17 new, 38 suppressed, 24 in cooldown

 #  fit  role                                        company        location       comp            posted  source
 1   91  Staff AI Solutions Architect                Anthropic      Reston, VA     $215–270k       Aug 17  greenhouse
 2   88  Principal Architect, Generative AI          Red Hat        Raleigh, NC    $185–230k       Aug 11  workday
 3   84  Lead ML Platform Engineer                   Capital One    McLean, VA     $190–225k       Aug 18  phenom
 ...
12   61  AI Enablement Architect                     Booz Allen     McLean, VA     not listed      Aug 15  workday

Needs your decision (2)
 M1      ML Engineer II                              Capital One    McLean, VA     — ATS blocked at SMS verification
 M2      Applied Scientist                           Amazon         Arlington, VA  — job closed while applying

Suppressed but high-fit (1)
 S1  93  Solutions Architect, AI Infrastructure      NVIDIA         Santa Clara    — dis-002 (sales-engineering, learned 2026-08-05)

Reply with numbers, or tell me what you want:
  apply 1,3      · tailor a resume + cover letter and fill the application
  no 5 "reason"  · not interested, and learn from it
  more           · next 10
  snooze 7 30d   · hide #7 for 30 days
```

**Step 2 — one `AskUserQuestion` call**, used for disposition rather than enumeration:

```json
{"questions":[{
  "header":"Today's picks",
  "question":"What do you want to do with today's 12 jobs? Type numbers in the Other row, e.g. \"apply 1,3\" or \"no 5,9 too sales-heavy\".",
  "multiSelect": false,
  "options":[
    {"label":"Apply to the top 3 (1, 2, 3)","description":"Fit 91/88/84. Generates tailored resume + cover letter for each and fills the application; stops before final submit."},
    {"label":"Just show me #1 in full","description":"Print the full JD, my fit reasoning, and the tailored-resume diff before deciding."},
    {"label":"Nothing today","description":"Marks all 12 as shown. They will not reappear for 14 days."},
    {"label":"Nothing today, and stop showing me sales-adjacent roles","description":"As above, plus promotes dis-002 to a hard rule."}
  ]}]}
```

The four options cover the actual modal answers; anything else the user types goes through the "Other" row, which is where `apply 1,3` and `no 5 "too sales-heavy"` land. That is the honest division of labor: the picker handles the common case in one keystroke, free text handles the long tail.

**Step 3 — echo the parsed intent before acting.** Always, in both modes:

```
Parsed: apply -> #1 Anthropic Staff AI Solutions Architect (b7f3c1a9), #3 Capital One Lead ML Platform Engineer (5d0aa38f)
        not_interested -> none
This will generate 2 tailored resumes + cover letters and fill 2 applications.
auto_submit is OFF -> I will stop at the review step on both.
```

Number-to-fingerprint mistakes are the expensive failure here (applying to the wrong job), so the confirmation names both.

### Selection after a cron run

The follow-up invocation must work in a **fresh session with no memory of the list**. Two things make that work: the report carries a machine-readable index, and `runs.jsonl` maps `run_id → report path`.

At the bottom of every `reports/YYYY-MM-DD.md`:

````markdown
## Index (machine-readable — do not edit)

```json job-index
{"run_id":"9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f","date":"2026-08-19","generated_at":"2026-08-19T10:33:12Z",
 "items":[
  {"n":1,"fp":"b7f3c1a9d2e40185","title":"Staff AI Solutions Architect","company":"Anthropic","fit":91},
  {"n":2,"fp":"e21d7f04c6b93a5a","title":"Principal Architect, Generative AI","company":"Red Hat","fit":88},
  {"n":3,"fp":"5d0aa38f91c7e462","title":"Lead ML Platform Engineer","company":"Capital One","fit":84}],
 "manual":[{"n":"M1","fp":"5d0aa38f91c7e462"}],
 "suppressed":[{"n":"S1","fp":"77e2b1c40a9d3f18","rule":"dis-002"}]}
```
````

Grammar (note: **`pick`, not `select`** — see the verified positional-argument gotcha above):

```
/job-search <free-text query>                 run a scan now with this query
/job-search scan [--headless] [--max N] [--run ID]
/job-search pick 2,4 [--from 2026-08-19]      mark selected + generate + fill applications
/job-search pick 2,4 --run 9f1c2d3e           same, addressed by run id
/job-search no 5 "too sales-heavy"            not interested + learn
/job-search no 5,9 --reason "wrong level"     multiple, one reason
/job-search snooze 7 30d                      hide #7 for 30 days, no learning
/job-search show 1                            full JD + fit reasoning + tailored-resume diff
/job-search status                            counts by status, active disinterest rules, last 5 runs
/job-search unhide dis-002                    delete or downgrade a learned rule
/job-search submit 1 --i-mean-it              explicit one-off submit, ignores auto_submit=false
```

Resolution order for a bare number:
1. `--run <id>` if given → that run's index.
2. `--from <date>` if given → `reports/<date>.md` index (or `<date>.rN.md`, highest N).
3. Otherwise the most recent entry in `runs.jsonl` **whose report file still exists**.
4. A token that looks like a 16-hex fingerprint, or a ≥6-char unique prefix of one, is accepted anywhere a number is — `/job-search no b7f3c1` always works even with no report at hand.
5. If the resolved index is older than 14 days, refuse and say so: stale numbers are how you apply to the wrong job.

The whole grammar is parsed from `$ARGUMENTS` by `scripts/config.py parse-args "$ARGUMENTS"`, which prints a normalized JSON intent. Do not build it out of `$0`/`$1`.

### "Not interested" plus reason in one step

`/job-search no 5 "too sales-heavy"` performs, in one turn:

1. Resolve `5` → fingerprint via the index.
2. `jobs_db.py set-status <fp> not_interested --reason "too sales-heavy"`.
3. Look the job's `title_key` up in `references/title-families.md` → family `sales-engineering`.
4. Apply the escalation ladder (soft on first dismissal, hard on the second within 90 days).
5. Print exactly what was learned and how to undo it:

```
#5 Senior Sales Engineer, AI Platform @ Databricks -> not_interested ("too sales-heavy")
Learned: dis-002 sales-engineering is now HARD (2nd dismissal in this family since 2026-08-05).
  pattern: \b(sales|pre-?sales|field|account)\s+(engineer|architect|consultant|executive)\b|\bsolutions?\s+engineer\b
  This would have hidden 6 of the 142 jobs seen today.
  Undo: /job-search unhide dis-002        Soften: /job-search unhide dis-002 --to soft
```

Reporting the retrospective hit count ("would have hidden 6 of 142") is what makes an over-broad rule obvious at the moment it is created rather than three weeks later.

If the reason is omitted: **interactive** → one `AskUserQuestion` with four common reasons (wrong level / wrong function / comp too low / company) plus Other; **headless** → record `status_reason: "dismissed without reason (headless)"`, create **no** rule, and list it in the next report under "Tell me why so I can learn". A cron run must never invent a preference.

### Deferred and partial states

- `pick` that hits a blocked ATS writes `status = needs_manual_apply` with a concrete `status_reason`, keeps the generated artifacts in `applications/<date>-<fp>/`, and screenshots the blocking step. These rows appear in the report's "Needs your decision" section on every run until resolved — they are exempt from the 14-day cooldown, because the whole point is that they are waiting on the user.
- Screening questions the model had to invent an answer for are written to `applications/<date>-<fp>/answers.json` with `"needs_review": true` and are listed inline in the report. In headless mode a job with any `needs_review: true` answer is never submitted, regardless of `fit_score` or `auto_submit`.

---

## Config design

### `config/settings.yaml` (committed, hand-authored, platform-neutral)

Paths are written relative to the data home, or as `~`-prefixed, and are resolved with `Path.expanduser()` — never as literal `/Users/...` or `/home/...`. Anything that genuinely differs per machine lives in `platform_overrides:` or is discovered at runtime.

```yaml
# ~/development/random/job-search/config/settings.yaml
schema_version: 1

search:
  query: "AI/ML solutions architect, platform engineering"
  default_location: "Reston, VA"
  radius_miles: 35
  remote_preference: prefer          # require | prefer | allow | exclude
  include_hybrid: true
  min_results: 10                    # keep widening until at least this many survive filters
  max_results: 12                    # ranked list length
  max_age_days: 30                   # ignore postings older than this
  boards_file: config/job-board-links.md
  board_timeout_seconds: 90
  strategy_order: [firecrawl, playwright, websearch]   # layered fallback, in this order

scoring:
  resume_path: resume/resume.pdf     # or resume.md / resume.txt
  resume_url: "https://wardzinski.info"   # used when no local file is present
  resume_extractor: auto             # auto | pdftotext | pypdf | firecrawl | url
  rubric: references/scoring-rubric.md
  min_fit_to_show: 55
  weights:                           # must sum to 100
    skills_overlap: 40
    seniority_match: 20
    domain_match: 15
    location_fit: 15
    comp_fit: 10

memory:
  cooldown_days: 14
  extended_cooldown_days: 45         # applied after shown_count >= 3
  expire_after_days: 45              # last_seen older than this -> status expired
  selection_expiry_days: 7
  git_autocommit: true

apply:
  auto_submit: false                 # NEVER submits unless this is true
  submit_threshold: 80               # fit_score floor for auto-submit
  max_submits_per_run: 5
  max_applications_per_run: 5        # includes fill-but-don't-submit
  browser_profile_path: config/browser-profile   # relative to the data home
  browser_mode: auto                 # auto | headed | headless
  browser_channel: auto              # auto | chrome | chromium | msedge
  browser_no_sandbox: false          # set true only inside a container
  screenshot_every_step: true
  stop_on_unknown_question: true     # in headless mode, always effectively true
  profile: config/profile.md

output:
  report_dir: reports
  applications_dir: applications
  pdf_engine: auto                   # auto | chrome | chromium | playwright | reportlab
  chrome_path: auto                  # auto = discovery order below; or an absolute path
  pdf_font_family: "Liberation Sans, Helvetica, Arial, DejaVu Sans, sans-serif"

notion:
  enabled: true
  database_id: ""                    # bootstrapped on first run -> settings.local.yaml
  data_source_id: ""                 # bootstrapped on first run -> settings.local.yaml
  parent_page_id: ""                 # optional; empty = workspace-level private page
  database_title: "Job Search"
  mirror: shown                      # all | shown | selected   (which rows reach Notion)

runtime:
  model: opus
  fallback_model: sonnet
  max_turns: 120
  max_budget_usd: 4.00
  log_level: info
  python: auto                       # auto = sys.executable of the running interpreter

# Merged over the base config when platform.system() matches. Everything above stays
# platform-neutral; only genuinely machine-shaped values belong here.
platform_overrides:
  macos:
    output:
      chrome_path: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    apply:
      browser_channel: chrome
  linux:
    apply:
      browser_channel: chromium      # Playwright's bundled build is the dependable one on a server
      browser_no_sandbox: false      # flipped to true by preflight.py when /.dockerenv exists
```

### `config/settings.local.yaml` (machine-written, git-ignored)

```yaml
# Written by the skill. Hand edits are preserved but may be overwritten on re-bootstrap.
schema_version: 1
host:
  os: macos                          # macos | linux
  arch: arm64
  python: "/opt/homebrew/bin/python3"
  claude_bin: "/Users/toddwardzinski/.local/bin/claude"
  chrome_path: "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
  chrome_kind: chrome                # chrome | chromium | playwright-bundled
  pdftotext: "/opt/homebrew/bin/pdftotext"
  has_display: true
  detected_at: "2026-08-19T10:29:12Z"
notion:
  database_id: "26ab1f9f-4c5f-8012-9a3c-000b1d2e3f40"
  data_source_id: "f336d0bc-b841-465b-8045-024475c079dd"
  bootstrapped_at: "2026-08-19T10:29:41Z"
  schema_hash: "a41c7f9e"
last_run_id: "9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"
```

Splitting hand-authored from machine-written config is what lets the skill write back a Notion id or a discovered Chrome path without ever mangling the user's comments in `settings.yaml`. It is also what makes the same `settings.yaml` usable on a Mac laptop and a Linux server: the `host:` block differs, the committed config does not.

The equivalent Linux `host:` block:

```yaml
host:
  os: linux
  arch: x86_64
  python: "/usr/bin/python3"
  claude_bin: "/home/todd/.local/bin/claude"
  chrome_path: "/home/todd/.cache/ms-playwright/chromium-1187/chrome-linux/chrome"
  chrome_kind: playwright-bundled
  pdftotext: "/usr/bin/pdftotext"
  has_display: false
  detected_at: "2026-08-19T10:29:12Z"
```

### `config/profile.md`

Free-form markdown with H2 sections; the skill reads it whole when filling forms and quotes from it verbatim rather than paraphrasing. Nothing here is platform-specific.

```markdown
# Applicant profile

## Identity
Name: Todd Wardzinski
Email: wardzinski.todd@gmail.com
Phone: <your number>
Location: Reston, VA 20190, USA
LinkedIn: https://www.linkedin.com/in/toddwardzinski
Portfolio: https://wardzinski.info

## Work authorization
- Authorized to work in the US: Yes
- Require sponsorship now or in future: No
- Willing to relocate: No (open to hybrid within 40 mi of Reston, VA)
- Notice period: 2 weeks

## Voluntary disclosures
- Veteran status: <answer, or "prefer not to say">
- Disability status: <answer, or "prefer not to say">
- Race/ethnicity, gender: prefer not to say

## Compensation
- Target base: $210,000
- Minimum base: $185,000
- When a form demands a single number: 210000
- When a form allows text: "Targeting $210k base; flexible on structure for the right role."

## Stock answers
### Why this company?
<3-4 sentences the skill adapts per company; it must keep the factual claims and change only the company-specific clause.>

### Biggest impact in the last two years
<one paragraph>

### Preferred work model
Hybrid, 2-3 days on site in the NoVA/DC corridor, or fully remote US.
```

Anything the skill cannot answer from `profile.md` goes into `answers.json` with `"needs_review": true` — it never guesses a work-authorization, veteran-status, or compensation answer.

### Precedence

Highest wins:

1. **CLI arguments** in `$ARGUMENTS` (`--max 20`, `--from`, `--force`, `--headless`, `--auto-submit`, `--no-notion`).
2. **Environment variables** prefixed `JOBSEARCH_` (`JOBSEARCH_AUTO_SUBMIT=0`, `JOBSEARCH_BROWSER_MODE=headless`, `JOBSEARCH_HOME=/srv/job-search`), for scheduler overrides without editing files. This is the layer a systemd unit or a container `ENV` uses.
3. **`config/settings.local.yaml`** (machine-written state: `host:`, Notion ids).
4. **`platform_overrides.<os>`** from `settings.yaml`, merged key-by-key over the base.
5. **`config/settings.yaml`** base keys (the user's intent).
6. **Built-in defaults** compiled into `scripts/config.py`.

Two exceptions, both deliberate:

- **`auto_submit` and `submit_threshold` are floor-only from layers 1–2.** `--auto-submit` on the command line, or `JOBSEARCH_AUTO_SUBMIT=1`, cannot turn on submission when `settings.yaml` says `auto_submit: false`; either can only turn it *off*. Turning it on requires editing the file, or the explicit one-off `/job-search submit 1 --i-mean-it`. A flag that silently starts submitting applications is not a flag anyone should be able to typo, and an inherited environment variable on a shared Linux host is exactly the way that happens by accident.
- **`max_submits_per_run` takes the minimum** of every layer's value, never the maximum.

### Validation

`scripts/config.py validate` runs at the top of every invocation and hard-fails with a one-line reason. It checks, on both platforms: weights sum to 100; `resume_path` exists (after `expanduser`) or `resume_url` is set; `browser_profile_path` exists or can be created; `submit_threshold` ∈ [0,100]; `cooldown_days ≥ 1`; `auto_submit: true` is accompanied by a non-empty `profile.md`; and every discovered binary in `host:` is still present and executable (`os.access(p, os.X_OK)`).

`scripts/preflight.py` is the platform half of that, run on first use and whenever `host.detected_at` is older than 30 days. It resolves the interpreter, `claude`, a browser, `pdftotext`, and the presence of a display; writes the `host:` block; regenerates `headless.settings.json` and `mcp.headless.json` with absolute paths; and prints a per-OS fix command for anything missing rather than a bare failure. Its full dependency matrix is in [Cross-platform notes](#cross-platform-notes).

Secrets never live in `settings.yaml`. `FIRECRAWL_API_KEY` comes from the environment (the Firecrawl CLI is already authenticated on this machine); Notion uses OAuth held by Claude Code's credential store; job-board logins live only in the Playwright profile directory, which is git-ignored on both platforms.

---

## Notion mirror

### Which Notion interface to use

Two live options as of Aug 2026:

- **Notion MCP** (`https://mcp.notion.com/mcp`) — "Notion's hosted, actively maintained server… supports OAuth authorization and requires no infrastructure setup" ([Connect to Notion MCP](https://developers.notion.com/guides/mcp/get-started-with-mcp)). This is what the skill should use: Claude Code holds the OAuth token, and the tools below are already shaped for agent use.
- **Notion REST API**, current version **`2025-09-03`**, which introduced **data sources**: "Database endpoints return responses with `object: "data_source"`, accept a specific data source ID in query, body, and path parameters (not a database ID), and exist under the `/v1/data_sources` namespace" ([Upgrade guide 2025-09-03](https://developers.notion.com/guides/get-started/upgrade-guide-2025-09-03)). Keep this as the documented fallback if MCP is unavailable in a given run.

Either way the unit you write to is a **data source**, not a database. A database is a container for one or more data sources; the ids are different and the MCP tools ask for the data source id.

### Minimal database schema

Created with `notion-create-database`, whose `schema` parameter takes SQL DDL. Column names are double-quoted; type options use single quotes.

```sql
CREATE TABLE (
  "Role"          TITLE                                                     COMMENT 'Job title as posted',
  "Company"       RICH_TEXT                                                 COMMENT 'Employer name',
  "Fingerprint"   RICH_TEXT                                                 COMMENT '16-hex identity key; upsert key. Do not edit.',
  "Status"        SELECT('new':gray, 'shown':blue, 'selected':purple, 'applied':green, 'not interested':red, 'expired':brown, 'needs manual apply':orange),
  "Fit"           NUMBER                                                    COMMENT '0-100 resume-fit score',
  "Location"      RICH_TEXT,
  "Work Model"    SELECT('remote':green, 'hybrid':blue, 'onsite':gray, 'unknown':default),
  "Comp Min"      NUMBER FORMAT 'dollar',
  "Comp Max"      NUMBER FORMAT 'dollar',
  "Posting URL"   URL                                                       COMMENT 'Canonical posting URL',
  "Source"        SELECT('greenhouse':blue, 'lever':purple, 'ashby':pink, 'workday':orange, 'linkedin':blue, 'indeed':yellow, 'phenom':gray, 'other':default),
  "Posted"        DATE,
  "First Seen"    DATE,
  "Last Seen"     DATE,
  "Last Shown"    DATE,
  "Applied On"    DATE,
  "Submitted"     CHECKBOX,
  "Why It Fits"   RICH_TEXT                                                 COMMENT 'Top 3 fit reasons, one per line',
  "Notes"         RICH_TEXT,
  "Run ID"        RICH_TEXT
)
```

Three deliberate choices:

1. **`"Posting URL"`, not `"URL"`.** The `notion-update-page` contract states: *"Properties named `id` or `url` (case insensitive) must be prefixed with `userDefined:` (e.g., `userDefined:URL`, `userDefined:id`)"*. Naming the column `Posting URL` sidesteps that footgun entirely — no prefix, no special case, no chance of a silently dropped write.
2. **`SELECT`, not `STATUS`, for `Status`.** `SELECT` options and their colors are fully specifiable in the DDL; Notion's `STATUS` type carries its own To-do/In-progress/Complete groups that do not map onto this workflow.
3. **`Fingerprint` is `RICH_TEXT`, not `UNIQUE_ID`.** `UNIQUE_ID` is Notion-generated and auto-incrementing; the upsert key has to be *ours*.

Page **body** (Notion-flavored Markdown, passed as `content`) holds the job description excerpt, the fit reasoning, and links to the generated resume/cover letter — keeping the row itself scannable. Page `icon` mirrors status (🆕 / 👀 / ✅ / 🚫 / ⚠️) for at-a-glance scanning in board view.

### Bootstrap on first run

```
if notion.enabled and not settings.local.notion.data_source_id:
  1. If notion.parent_page_id is set, verify it with notion-fetch; otherwise create at workspace level.
  2. Call notion-create-database:
       { "title": "<notion.database_title>",
         "parent": {"type":"page_id","page_id":"<parent_page_id>"},   # omit key entirely if unset
         "description": "Mirror of ~/development/random/job-search/memory/jobs.jsonl. Upsert key: Fingerprint.",
         "schema": "<the CREATE TABLE above>" }
  3. The tool "Returns Markdown with schema, SQLite definition, and data source ID in <data-source> tag".
     Parse the <data-source url="collection://<uuid>"> tag -> data_source_id; the database id is in the
     returned database URL.
  4. Write BOTH ids to config/settings.local.yaml, plus bootstrapped_at and a schema_hash
     (sha256 of the DDL text, first 8 hex).
  5. Re-read settings.local.yaml and assert the ids round-tripped. If the write fails, abort the mirror
     for this run and log it — never leave a database orphaned with no recorded id.
```

On every later run, if `schema_hash` in `settings.local.yaml` differs from the hash of the DDL in the skill (i.e. the skill was upgraded), reconcile with `notion-update-data-source` using additive DDL only:

```json
{"data_source_id": "f336d0bc-b841-465b-8045-024475c079dd",
 "statements": "ADD COLUMN \"Closes\" DATE; ADD COLUMN \"Screening Flags\" RICH_TEXT"}
```

`ADD COLUMN` / `RENAME COLUMN` are safe; **never emit `DROP COLUMN` automatically** — it destroys user data in a workspace the skill does not own. If a column would need to be dropped, print the DDL and let the user run it.

### Upsert by fingerprint

Notion has no native upsert; it is query-then-branch. Per run, for every job whose `notion_synced_at` is older than its `status_changed_at` (or null):

**1. Look up the existing page** with `notion-query-data-sources` in SQL mode, batching the run's fingerprints into one parameterized query:

```json
{"data": {
  "mode": "sql",
  "data_source_urls": ["collection://f336d0bc-b841-465b-8045-024475c079dd"],
  "query": "SELECT \"Fingerprint\", \"Status\" FROM \"collection://f336d0bc-b841-465b-8045-024475c079dd\" WHERE \"Fingerprint\" IN (?, ?, ?)",
  "params": ["b7f3c1a9d2e40185", "e21d7f04c6b93a5a", "5d0aa38f91c7e462"]
}}
```

The result rows carry their page URLs, from which the page id is the trailing 32-hex segment. Cache `notion_page_id` back into `jobs.jsonl` so subsequent runs skip the lookup entirely and go straight to update.

**2a. New → `notion-create-pages`**, up to **100 pages per call** (the tool's `maxItems`):

```json
{"parent": {"type": "data_source_id", "data_source_id": "f336d0bc-b841-465b-8045-024475c079dd"},
 "pages": [{
   "icon": "🆕",
   "properties": {
     "Role": "Staff AI Solutions Architect",
     "Company": "Anthropic",
     "Fingerprint": "b7f3c1a9d2e40185",
     "Status": "shown",
     "Fit": 91,
     "Location": "Reston, VA",
     "Work Model": "hybrid",
     "Comp Min": 215000,
     "Comp Max": 270000,
     "Posting URL": "https://job-boards.greenhouse.io/anthropic/jobs/4512345",
     "Source": "greenhouse",
     "date:Posted:start": "2026-08-17",
     "date:Posted:is_datetime": 0,
     "date:First Seen:start": "2026-08-19",
     "date:First Seen:is_datetime": 0,
     "date:Last Shown:start": "2026-08-19",
     "date:Last Shown:is_datetime": 0,
     "Submitted": "__NO__",
     "Why It Fits": "8 yrs enterprise AI architecture matches staff scope\nReston HQ, 6 mi commute\nJD names vLLM + inference serving at scale",
     "Run ID": "9f1c2d3e-4a5b-4c6d-8e7f-0a1b2c3d4e5f"
   },
   "content": "## Fit 91/100\n\n…excerpt of the JD and the scoring rationale…\n\n## Local artifacts\n`applications/2026-08-19-b7f3c1a9d2e40185/`"
 }]}
```

**2b. Existing → `notion-update-page`** with `command: "update_properties"`; omitted properties are left unchanged, so send only what moved:

```json
{"page_id": "26ab1f9f-4c5f-80b1-8d3b-d10a6b1d2f4e",
 "command": "update_properties",
 "icon": "✅",
 "properties": {
   "Status": "applied",
   "date:Applied On:start": "2026-08-19",
   "date:Applied On:is_datetime": 0,
   "date:Last Seen:start": "2026-08-19",
   "date:Last Seen:is_datetime": 0,
   "Submitted": "__YES__",
   "Notes": "Workday essay answered from profile.md; reviewed before submit."
 }}
```

**3. Record success** — set `notion_page_id` and `notion_synced_at` in `jobs.jsonl` in the same write that follows the mirror.

### Property-format gotchas (from the tool contracts)

| Type | Required format |
| :-- | :-- |
| Date | split into `date:{Property}:start`, optional `date:{Property}:end`, and `date:{Property}:is_datetime` (`0` or `1`) |
| Checkbox | `"__YES__"` / `"__NO__"` — **not** `true`/`false` |
| Number | a JSON number, not a string |
| Relation | array of related page URLs or page ids |
| Files | JSON array of file ids / Notion folder URLs |
| Place | split into `place:{Property}:name`, `:address`, `:latitude`, `:longitude` |
| A property literally named `id` or `url` | must be written as `userDefined:id` / `userDefined:URL` |
| Checkbox in a SQL query | bind `"__YES__"` / `"__NO__"` as the parameter |

Both `notion-create-pages` and `notion-update-page` instruct the caller to run `notion-fetch` on the database first to get the exact property names and the SQLite schema. Do that **once per run** and cache it — the property names are the contract, and a renamed column in Notion should surface as a clear error, not a silent no-op.

### Failure handling and limits

- **Never let Notion failure fail the run.** `jobs.jsonl` is the source of truth; Notion is a mirror. On any Notion error, append the intended operation to `memory/notion-outbox.jsonl` and continue. The next run flushes the outbox before doing new work, and `/job-search status` reports its depth.
- **Only mirror what changed.** `notion.mirror` in config controls scope (`all` / `shown` / `selected`); the dirty check is `notion_synced_at is null or notion_synced_at < status_changed_at`. A daily run should push a handful of rows, not 142.
- **SQL query limits.** The tool contract notes: "SQL is unlimited on Business and Enterprise plans with Notion AI. Other plans have a shared workspace usage limit for single-data-source queries and cannot query multiple data sources at once." On a Free/Plus workspace, prefer the cached `notion_page_id` path and fall back to **view mode** (`{"mode":"view","view_url":"…"}`) or a single `notion-fetch` of the data source rather than repeated SQL.
- **Headless availability.** Interactively-authenticated claude.ai connectors may be absent from cron runs, which is why `mcp.headless.json` declares `https://mcp.notion.com/mcp` explicitly. Verify it is live by checking `mcp_servers` in the `system/init` event before attempting the mirror; if it is missing, go straight to the outbox.
- **REST fallback shape** (API version `2025-09-03`): `POST /v1/data_sources/{data_source_id}/query` with a `filter` on the `Fingerprint` rich-text property to find the page, then `PATCH /v1/pages/{page_id}` to update or `POST /v1/pages` with `parent: {"type":"data_source_id","data_source_id":"…"}` to create. Headers: `Authorization: Bearer <token>`, `Notion-Version: 2025-09-03`. Same query-then-branch logic; there is still no upsert endpoint.

---

## Cross-platform notes

The skill targets **macOS** (Apple silicon and Intel) and **Linux** (Debian/Ubuntu and Fedora class, including headless servers and containers). Claude Code itself, the MCP servers, the memory format, the Notion mirror, and the whole `-p` invocation model are identical on both. What differs is entirely at the edges: where binaries live, which scheduler runs the job, and which shell built-ins behave differently.

### What actually differs

| Concern | macOS | Linux |
| :-- | :-- | :-- |
| Skill + data home | `~/.claude/skills/job-search`, `~/development/random/job-search` | same |
| Claude Code behavior (`-p`, skills, MCP, permissions) | identical | identical |
| Default scheduler | launchd user agent (cron also works, needs Full Disk Access) | systemd user timer (cron also works) |
| Browser | Google Chrome app bundle | `google-chrome-stable` / `chromium` / Playwright's bundled Chromium |
| Playwright cache | `~/Library/Caches/ms-playwright` | `~/.cache/ms-playwright` |
| Config-ish caches | `~/Library/Application Support`, `~/Library/Caches` | `$XDG_CONFIG_HOME` (`~/.config`), `$XDG_CACHE_HOME` (`~/.cache`) |
| `flock` | absent | present |
| `sed -i` | requires an argument (`sed -i '' …`) | takes none (`sed -i …`) |
| `date` arithmetic | `date -v-14d` | `date -d '14 days ago'` |
| Checksums | `shasum -a 256` | `sha256sum` |
| Open a file | `open` | `xdg-open` |
| Homebrew prefix | `/opt/homebrew` (arm64), `/usr/local` (Intel) | n/a |
| Fonts for PDF | system fonts always present | must install `fonts-liberation` / `dejavu-sans-fonts` on a minimal image |
| GUI session for a headed browser | present when the user is logged in | requires `DISPLAY`/`WAYLAND_DISPLAY`; absent on servers |

**Design rule that follows:** every helper is Python 3 stdlib (3.9+), because `os.mkdir`, `os.replace`, `shutil.which`, `pathlib.Path.expanduser`, `datetime`, `hashlib`, and `platform.system()` behave identically on both. The only shell that survives is the scheduler stanza, written in POSIX `sh`. No `zsh`-isms, no `bash`-isms, no `sed -i`, no `date -v`, no `flock`, no `jq` in any required path.

### OS detection and path resolution — `scripts/platform_paths.py`

```python
#!/usr/bin/env python3
"""OS detection, XDG-aware paths, and browser discovery. Stdlib only."""
import glob, os, platform, shutil
from pathlib import Path

def os_name() -> str:
    return {"Darwin": "macos", "Linux": "linux"}.get(platform.system(), platform.system().lower())

def data_home() -> Path:
    return Path(os.environ.get("JOBSEARCH_HOME", Path.home() / "development/random/job-search")).expanduser()

def cache_dir(app: str) -> Path:
    if os_name() == "macos":
        return Path.home() / "Library/Caches" / app
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / app

def config_dir(app: str) -> Path:
    if os_name() == "macos":
        return Path.home() / "Library/Application Support" / app
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / app

def in_container() -> bool:
    return Path("/.dockerenv").exists() or "docker" in Path("/proc/1/cgroup").read_text(errors="ignore") \
        if Path("/proc/1/cgroup").exists() else Path("/.dockerenv").exists()

def has_display() -> bool:
    if os_name() == "macos":
        return os.environ.get("SSH_CONNECTION") is None
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
```

Never write `/Users/...` or `/home/...` into a script. Anywhere an absolute path must reach a config file (Claude Code permission rules, `--user-data-dir`), it is **generated** by `preflight.py` from these functions, not typed by hand.

### Browser discovery — one function, both platforms

```python
MAC_APPS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "~/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]
LINUX_BINS = [
    "google-chrome-stable", "google-chrome", "chromium", "chromium-browser",
    "microsoft-edge-stable",
]
# Playwright's bundled build; the directory carries the build number and, on macOS, the arch.
BUNDLED_GLOBS = {
    "macos": ["chromium-*/chrome-mac*/*.app/Contents/MacOS/*"],
    "linux": ["chromium-*/chrome-linux/chrome"],
}

def find_browser() -> tuple[str, str]:
    """Returns (absolute_path, kind) where kind is chrome | chromium | edge | playwright-bundled."""
    osn = os_name()
    if osn == "macos":
        for p in MAC_APPS:
            q = Path(p).expanduser()
            if q.exists():
                kind = "chrome" if "Google Chrome" in p else ("edge" if "Edge" in p else "chromium")
                return str(q), kind
    else:
        for b in LINUX_BINS:
            p = shutil.which(b)
            if p:
                return p, ("chrome" if "chrome" in b and "chromium" not in b else
                           "edge" if "edge" in b else "chromium")
    root = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "")) or cache_dir("ms-playwright")
    for pat in BUNDLED_GLOBS.get(osn, []):
        hits = sorted(glob.glob(str(root / pat)))
        if hits:
            return hits[-1], "playwright-bundled"     # highest build number
    raise SystemExit(
        "No Chrome/Chromium found. Install one:\n"
        "  macOS:          brew install --cask google-chrome\n"
        "  Debian/Ubuntu:  sudo apt-get install -y chromium   (or install Google Chrome's .deb)\n"
        "  Fedora:         sudo dnf install -y chromium\n"
        "  Any platform:   npx playwright install chromium   (bundled build, no root needed)")
```

**[verified locally, macOS]** the bundled layout on this machine is `~/Library/Caches/ms-playwright/chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing`, with a sibling `chromium_headless_shell-1234/` — which is why the macOS glob ends in `*.app/Contents/MacOS/*` rather than a fixed binary name. On Linux the corresponding path is `chromium-<build>/chrome-linux/chrome`. Playwright documents the cache roots as `~/Library/Caches/ms-playwright` (macOS) and `~/.cache/ms-playwright` (Linux), overridable with `PLAYWRIGHT_BROWSERS_PATH` ([Playwright: Browsers](https://playwright.dev/docs/browsers)).

Also **[verified locally]**: the Playwright MCP profile directories on this machine are named `mcp-chrome-<hash>` under `~/Library/Caches/ms-playwright/`, matching the README's documented `mcp-{channel}-{workspace-hash}` pattern. Passing `--user-data-dir` explicitly is what stops the profile from moving when the workspace hash changes.

### PDF rendering (Markdown → HTML → PDF)

`pandoc` is installed here but has **no PDF engine** (no LaTeX), so PDF generation goes through headless Chrome on both platforms. The command is the same; only the binary differs, and it comes from `find_browser()`:

```sh
"$CHROME" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="$OUT/resume.pdf" "file://$OUT/resume.html"
```

Platform notes:

- **Linux, running as root or in a container**: add `--no-sandbox`. Without it Chrome refuses to start as root. `preflight.py` sets `apply.browser_no_sandbox: true` automatically when `/.dockerenv` exists.
- **Linux, minimal image**: Chrome needs fonts, or the PDF renders with tofu boxes. Install at least one of `fonts-liberation` (Debian/Ubuntu) or `liberation-fonts` (Fedora), plus `fonts-dejavu-core` / `dejavu-sans-fonts` for broad Unicode coverage. The `output.pdf_font_family` default (`Liberation Sans, Helvetica, Arial, DejaVu Sans, sans-serif`) is metric-compatible with Helvetica/Arial, so a resume typesets nearly identically on a Mac with Helvetica and a Linux box with Liberation Sans.
- **No browser at all** (locked-down server): fall back to `pdf_engine: reportlab`. `reportlab` 4.4.10 is installed here and is pure Python, so it works anywhere Python does; it produces a plainer document, which `render_pdf.py` notes in the run log so the difference is not a surprise.
- **`--headless=new`** is the current flag on both platforms; older `--headless` still works but is deprecated in recent Chrome.

### Resume text extraction

The resume may be a PDF. `render_pdf.py`'s inverse, `scripts/resume_text.py`, tries in order and records which path it used:

1. `pdftotext -layout resume.pdf -` (poppler) — best fidelity, keeps column structure.
2. `python3 -c "import pypdf; …"` if `pypdf` is importable — no system package needed.
3. Firecrawl's parse capability, or `WebFetch` against `scoring.resume_url`, when neither is available.
4. Fail loudly and ask for `resume/resume.md`, rather than scoring against an empty string.

Poppler install:

| OS | Command |
| :-- | :-- |
| macOS (Homebrew) | `brew install poppler` |
| Debian / Ubuntu | `sudo apt-get install -y poppler-utils` |
| Fedora / RHEL | `sudo dnf install -y poppler-utils` |
| Alpine | `apk add poppler-utils` |
| No root, any OS | `python3 -m pip install --user pypdf` and use path 2 |

`pdftotext` is present at `/opt/homebrew/bin/pdftotext` on this machine only if poppler is installed — `preflight.py` checks with `shutil.which("pdftotext")` and prints the matching command above rather than failing with `FileNotFoundError`.

### Playwright browser installation

```sh
# Either platform, no root required, installs into the ms-playwright cache:
npx playwright install chromium

# Linux, first time on a fresh host — also installs the OS packages Chromium needs:
npx playwright install --with-deps chromium
```

"It's possible to combine `install-deps` with `install` so that the browsers and OS dependencies are installed with a single command" ([Playwright: Browsers](https://playwright.dev/docs/browsers)). `--with-deps` needs sudo/root on Linux and is a no-op on macOS. `npx playwright install chrome` installs the branded Google Chrome channel instead, which requires root on Linux; prefer plain `chromium` for servers.

Container option: the project publishes `mcr.microsoft.com/playwright/mcp`, whose "Docker implementation only supports headless chromium at the moment" and which needs `--no-sandbox` when run as a service ([playwright-mcp README](https://github.com/microsoft/playwright-mcp)). That is a reasonable way to run the scan half of this skill on a Linux server; the apply half will hit more ATS bot-detection headless than headed, so expect a higher `needs_manual_apply` rate and treat the container as a scanner, not an applier.

`node` and `npx` are required on both platforms for the Playwright and Firecrawl MCP servers. On this Mac they are in `~/.local/bin`; on Debian/Ubuntu use nodesource or `nvm` rather than the distro `nodejs` package, which is often too old for `@playwright/mcp@latest`.

### Scheduler matrix

| Platform | First choice | Why | Fallback |
| :-- | :-- | :-- | :-- |
| macOS desktop/laptop | launchd user agent (`gui/$UID`) | Has a GUI session, so a headed browser works; survives reboot; `StartCalendarInterval` catches the machine being asleep on wake | `cron` with Full Disk Access granted to `/usr/sbin/cron` |
| Linux desktop | systemd **user** timer + `loginctl enable-linger` | `Persistent=true` catches missed runs; `journalctl` logging; `DISPLAY` available for a headed browser | `cron` with an explicit `PATH` |
| Linux server / container | systemd user timer with `JOBSEARCH_BROWSER_MODE=headless` | No display; Playwright must run headless | container `CMD` on a schedule, or the host's `cron` |

All three call the same `scripts/run_headless.py`, so the scheduler is the only thing that varies. Both unit files and the plist are given in full in [Headless / cron invocation](#headless--cron-invocation).

One asymmetry worth stating plainly: **a headed browser needs a live graphical session.** On macOS a `gui/$UID` LaunchAgent has one whenever the user is logged in. On a Linux server there is none, and `xvfb-run` is the only way to fake it (`sudo apt-get install -y xvfb`, then wrap the command in `xvfb-run -a`). That is worth doing only if a specific ATS refuses headless Chrome; otherwise run headless and let the blocked jobs land in `needs_manual_apply` for the next interactive session.

### Shell and CLI differences the scripts must never depend on

| Task | Do **not** write | Portable form used here |
| :-- | :-- | :-- |
| In-place edit | `sed -i '' s/a/b/ f` (BSD) or `sed -i s/a/b/ f` (GNU) | Python `Path.write_text()` after `read_text()` |
| Date arithmetic | `date -v-14d` (BSD) / `date -d '14 days ago'` (GNU) | `datetime.now(timezone.utc) - timedelta(days=14)` |
| Timestamp | `date -u +%FT%TZ` | `datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")` |
| SHA-256 | `shasum -a 256` (macOS) / `sha256sum` (Linux) | `hashlib.sha256()` |
| UUID | `uuidgen` | `uuid.uuid4()` |
| Locking | `flock` (Linux only) | atomic `os.mkdir` + pid liveness probe |
| Absolute path | `readlink -f` (GNU only on older macOS) | `Path(...).resolve()` |
| File size / mtime | `stat -f%z` (BSD) / `stat -c%s` (GNU) | `Path.stat().st_size` |
| Base64 one line | `base64 -w0` (GNU only) | `base64.b64encode()` |
| Temp file | `mktemp` flag differences | `tempfile.NamedTemporaryFile` |
| Open a file for the user | `open` / `xdg-open` | print the path; let the user open it |
| JSON in a pipeline | `jq` | `python3 -m json.tool` or a `json.loads` in `run_headless.py` |

`jq` is present on this Mac and on most Linux dev boxes, but not on minimal images, so no required code path uses it. The `jq` examples in the [Headless](#headless--cron-invocation) section are convenience one-liners for a human at a terminal, not part of the skill.

Scheduler stanzas use `SHELL=/bin/sh`, not `/bin/zsh` (macOS default login shell) or `/bin/bash` (most Linux), so the same crontab text works on both.

### Dependency matrix and what `preflight.py` prints

| Dependency | Required for | macOS | Debian/Ubuntu | Fedora |
| :-- | :-- | :-- | :-- | :-- |
| Claude Code | everything | `curl -fsSL https://claude.ai/install.sh \| sh` | same | same |
| Python ≥ 3.9 | all helper scripts | preinstalled / `brew install python` | `sudo apt-get install -y python3` | `sudo dnf install -y python3` |
| Node + npx | Playwright & Firecrawl MCP | `brew install node` | nodesource or `nvm` | `sudo dnf install -y nodejs` |
| Chrome/Chromium | PDF render + apply | `brew install --cask google-chrome` | `sudo apt-get install -y chromium` | `sudo dnf install -y chromium` |
| Playwright browsers | apply | `npx playwright install chromium` | `npx playwright install --with-deps chromium` | `npx playwright install --with-deps chromium` |
| poppler (`pdftotext`) | read a PDF resume | `brew install poppler` | `sudo apt-get install -y poppler-utils` | `sudo dnf install -y poppler-utils` |
| Fonts | legible PDFs | built in | `sudo apt-get install -y fonts-liberation fonts-dejavu-core` | `sudo dnf install -y liberation-fonts dejavu-sans-fonts` |
| `xvfb` (optional) | headed browser on a server | n/a | `sudo apt-get install -y xvfb` | `sudo dnf install -y xorg-x11-server-Xvfb` |
| pandoc (optional) | Markdown conversions | `brew install pandoc` | `sudo apt-get install -y pandoc` | `sudo dnf install -y pandoc` |
| reportlab (fallback PDF) | no-browser hosts | `pip install --user reportlab` | same | same |

`preflight.py` prints exactly the row that is missing, for the OS it is running on, and exits non-zero — never a bare `FileNotFoundError`. Verified present on this macOS machine: `jq`, `python3` (Homebrew, reportlab 4.4.10), `pandoc`, `node`/`npx` (`~/.local/bin`), `firecrawl`, `sqlite3`, `shasum`, Google Chrome, Playwright Chromium build 1234; **absent**: `flock`.

### Portability rules for the skill author

1. `${CLAUDE_SKILL_DIR}` for anything inside the skill; `JOBSEARCH_HOME` or `Path.home()` for anything in the data home. Never a literal home directory.
2. Every helper script starts with `#!/usr/bin/env python3` and is `chmod +x`, so `` !`${CLAUDE_SKILL_DIR}/scripts/x.py` `` injects cleanly on both platforms — recall that any `$` surviving into an injected command is rejected with `Contains expansion` and aborts the invocation.
3. All timestamps UTC, RFC 3339, `Z`-suffixed. Never a local-time string in `jobs.jsonl` — the same memory directory may be synced between a laptop in `America/New_York` and a server in `UTC`.
4. Files written with `newline="\n"` and `encoding="utf-8"` explicitly, so `jobs.jsonl` diffs cleanly across hosts.
5. `git config core.autocrlf false` in `memory/` at init.
6. Config paths stored relative to the data home; resolved with `expanduser().resolve()` at load.
7. Anything absolute in a generated file (`headless.settings.json`, `mcp.headless.json`) is regenerated by `preflight.py`, and both files are git-ignored for that reason.
8. Case-sensitivity: macOS APFS is case-insensitive by default and Linux ext4 is not. Keep every filename in `memory/`, `reports/`, and `applications/` lowercase, and never rely on `Reports/` and `reports/` being the same directory.

### Smoke test for a new host

```sh
python3 "$HOME/.claude/skills/job-search/scripts/preflight.py" --verbose   # deps + writes host block
"$HOME/.claude/skills/job-search/scripts/runtime_probe.py"                 # expect os=..., display=...
claude -p "/job-search status" --permission-mode dontAsk \
  --settings "$HOME/development/random/job-search/config/headless.settings.json" \
  --mcp-config "$HOME/development/random/job-search/config/mcp.headless.json" \
  --strict-mcp-config --output-format json < /dev/null | python3 -m json.tool
"$HOME/.claude/skills/job-search/scripts/run_headless.py" scan             # full unattended run, once, by hand
```

Run all four before enabling the timer or the LaunchAgent. The third is the one that catches a missing MCP server, and the fourth is the one that catches a scheduler `PATH` problem — because it is the exact command the scheduler will run.

---

## Confidence

- **Skill anatomy — frontmatter fields, locations, precedence, invocation control, string substitutions, size limits.** **High.** Taken verbatim from the current [skills](https://code.claude.com/docs/en/skills) page and the [Agent Skills specification](https://agentskills.io/specification), and consistent with the installed v2.1.235. The one soft spot is that no hard byte limit for `SKILL.md` is documented anywhere — the 500-line / <5,000-token guidance and the 5,000-token-per-skill compaction budget are the real constraints, and I say so rather than inventing a number.
- **The two verified behavioral gotchas — `Contains expansion` aborting a skill silently under `-p`, and a leading `select` token shifting `$N` positional arguments.** **High** that they reproduce on Claude Code v2.1.235 on this machine: I ran each case and pasted the actual output (including the `<local-command-stderr>` payload and the `num_turns: 0` result). **Medium** that they generalize — the abort semantics are documented ([skills](https://code.claude.com/docs/en/skills)), but the `Contains expansion` rejection string and the `select` tokenizer behavior are undocumented, so treat both as version-specific and re-test after a Claude Code upgrade. The design avoids depending on either.
- **Headless invocation — flags, permission modes, stdin, exit codes, MCP loading and `mcp_server_errors`.** **High.** Every flag is quoted from the [CLI reference](https://code.claude.com/docs/en/cli-reference) and [headless](https://code.claude.com/docs/en/headless) pages; the `-p` default mode (`default`/Manual), the absence of `AskUserQuestion` from the `-p` tool list, `CLAUDE_CODE_ENTRYPOINT=cli` vs `sdk-cli`, and the stdin warning were each confirmed by running the CLI locally. `dontAsk` denying `AskUserQuestion` is quoted from [permission modes](https://code.claude.com/docs/en/permission-modes).
- **`CLAUDE_CODE_ENTRYPOINT` values as a headless signal.** **Medium.** `cli` and `sdk-cli` were observed directly, but [env-vars](https://code.claude.com/docs/en/env-vars) documents only that the variable "indicates the entry point or mode of Claude Code execution" without enumerating values. The probe script therefore fails safe to headless on any unrecognized value, and the design also accepts an explicit `--headless` argument and cross-checks against `AskUserQuestion` availability.
- **Local macOS toolchain facts.** **High.** I checked this machine directly: `jq`, `python3` (Homebrew, reportlab 4.4.10), `pandoc`, `node`/`npx` (in `~/.local/bin`), `firecrawl`, `sqlite3`, `shasum`, BSD `date -v`, Google Chrome, and Playwright Chromium build 1234 are all present; **`flock` is absent**, which is why the lock is Python `os.mkdir`. The Playwright cache layout (`chromium-1234/chrome-mac-arm64/Google Chrome for Testing.app/…` alongside `chromium_headless_shell-1234`, and `mcp-chrome-<hash>` profile directories) was listed on disk.
- **Scheduler recipes — cron, launchd, systemd user timers.** **Medium.** The launchd plist keys, `launchctl bootstrap gui/$UID`, the systemd unit/timer keys, `Persistent=true`, `StandardInput=null`, and `loginctl enable-linger` are all standard and stated correctly to the best of my knowledge, but **I installed and fired none of them during this research** — not on macOS and not on Linux. Smoke-test with `launchctl kickstart -k` or `systemctl --user start job-search.service` before trusting a schedule. The macOS Full Disk Access requirement for `/usr/sbin/cron` and the Linux keyring/D-Bus caveat under a bare cron job are both well-known behaviors rather than cited ones — verify them on the host rather than assuming.
- **State and memory design — schema, fingerprint algorithm, 14-day cooldown, disinterest generalization.** **Medium-high.** This is a design proposal, not a citation of anything; it is internally consistent, the JSON Schema validates the four example records, and the cooldown rule is stated as executable pseudocode. The judgment calls I would flag for review: the two-level `fingerprint`/`posting_id` split (right for cross-board dedup, adds merge complexity), and the soft→hard escalation for learned dismissal rules, whose 90-day window and 20-point penalty are reasoned defaults rather than measured ones.
- **Interactive selection UX.** **High** on the `AskUserQuestion` shape constraint (1–4 questions, 2–4 options each, automatic "Other" row), which is read straight from the tool's schema in this Claude Code version and is what forces typed numbers to be the primary input. **Medium** on the specific grammar — `pick`/`no`/`snooze`/`show` is a proposal, though the choice of `pick` over `select` is forced by the verified tokenizer bug.
- **Config design.** **Medium-high.** A proposal, not a citation. The precedence chain is conventional; the two exceptions (`auto_submit` is floor-only from the CLI, `max_submits_per_run` takes the minimum) are deliberate safety inversions of normal precedence and should be reviewed as such — they are the reason a typo cannot start submitting applications.
- **Notion tool contracts — DDL syntax, `data_source_id` parent, `date:{prop}:start`, `__YES__`/`__NO__`, `userDefined:` prefix, 100-page batch cap, SQL-mode plan limits.** **High.** These are quoted from the live Notion MCP tool definitions loaded in this session (`notion-create-database`, `notion-create-pages`, `notion-update-page`, `notion-query-data-sources`, `notion-update-data-source`), which is the most authoritative source available for the tools the skill will actually call. **Medium** on the exact bootstrap parsing step — the tool documents that it "Returns Markdown with schema, SQLite definition, and data source ID in `<data-source>` tag", but I did not create a real database during this research, so the first bootstrap should be run interactively once and the parsed ids eyeballed before cron depends on them.
- **Notion REST fallback and API version `2025-09-03` data-source model.** **High** on the version and the data-source migration ([Upgrade guide](https://developers.notion.com/guides/get-started/upgrade-guide-2025-09-03), [Data source reference](https://developers.notion.com/reference/data-source)); **medium** on the precise endpoint paths for create/update in that version, since I read the upgrade guide summary rather than each endpoint page — verify `POST /v1/data_sources/{id}/query` and the `parent.data_source_id` shape against [the API reference](https://developers.notion.com/reference/post-database-query) before writing fallback code.
- **Playwright MCP flags, browser locations, and the persistent-profile approach.** **High** on the flags and paths: `--user-data-dir`, `--isolated`, `--storage-state`, `--browser`, `--headless`, `--output-dir`, `--save-session`, the per-OS profile roots (`~/Library/Caches/ms-playwright/mcp-{channel}-{workspace-hash}` on macOS, `~/.cache/ms-playwright/…` on Linux), the Docker image's headless-chromium-only limitation, and the `--no-sandbox` requirement are quoted from the [playwright-mcp README](https://github.com/microsoft/playwright-mcp); the browser cache roots and `PLAYWRIGHT_BROWSERS_PATH` from [Playwright: Browsers](https://playwright.dev/docs/browsers); and I confirmed the macOS layout on disk. **Medium** on the exact Linux bundled path (`chromium-<build>/chrome-linux/chrome`), which I did not observe directly — which is why the discovery code globs rather than hardcodes. The GUI-session caveat (a headed Chrome needs `DISPLAY`/`WAYLAND_DISPLAY` on Linux and a live `gui/$UID` session on macOS) is reasoned from how those systems work, not cited — treat it as a thing to test.
- **Cross-platform notes — path/XDG conventions, shell-difference table, portability rules.** **High** for the facts about the two platforms (`flock` on Linux only, BSD vs GNU `sed -i` and `date`, `shasum` vs `sha256sum`, `open` vs `xdg-open`, XDG base directories, macOS case-insensitive APFS vs case-sensitive ext4) — these are long-standing, stable platform behaviors, and the macOS half was observed on this machine. **Medium** that the substitution table is *complete*: it covers everything this design touches, but a new helper script can always reach for a utility that differs, so the standing rule "write it in Python 3 stdlib" matters more than the table.
- **Per-OS install commands (poppler, fonts, Chromium, Node, xvfb) and the Playwright install commands.** **Medium-high.** `npx playwright install chromium` and `npx playwright install --with-deps chromium` are quoted from [Playwright: Browsers](https://playwright.dev/docs/browsers). The package names — `poppler-utils`, `fonts-liberation`, `fonts-dejavu-core` on Debian/Ubuntu; `poppler-utils`, `liberation-fonts`, `dejavu-sans-fonts` on Fedora; `brew install poppler` on macOS — are standard and stable, but I verified none of them against a live package index during this research, and Fedora in particular renames packages between releases. `preflight.py` should print the command and let the human run it, rather than shelling out to a package manager itself.
- **The claim that the whole Claude Code layer behaves identically on Linux.** **Medium.** Skills, `-p`, `--permission-mode dontAsk`, MCP loading, `$ARGUMENTS` substitution, and the two verified gotchas are all implemented inside Claude Code rather than by the OS, so there is no mechanism by which they should differ — but **every `[verified locally]` result in this document was produced on macOS**, and none was re-run on Linux. The single highest-value verification before shipping is re-running the `runtime_probe.py` injection test and the empty-run (`num_turns == 0`) check on a Linux host.
- **Firecrawl MCP server invocation (`npx -y firecrawl-mcp`, `FIRECRAWL_API_KEY`).** **Medium-high.** Confirmed via [Firecrawl's local MCP docs](https://docs.firecrawl.dev/mcp-server/local) and [npm](https://www.npmjs.com/package/firecrawl-mcp); the exact tool names used in the allowlist (`mcp__firecrawl__firecrawl_search`, `…_scrape`, `…_map`, `…_extract`) follow the documented naming convention but were not enumerated from a running server — run `/mcp` once and copy the real names into `headless.settings.json`.
