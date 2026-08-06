---
name: setup-test-context
description: >
  Analyse the current repo and write per-repo test conventions, rules, and shared utility files
  to `.claude/{conventions,rules,shared}/tests/`. Plugin-bundled agents and skills (in
  `test-authoring`) read these per-repo files at runtime. Works for any language with a
  detectable test framework (C#, Python, TypeScript, Go, Java, etc.) — auto-detects language
  and derives every convention from the repo's own tests, never a language baseline. Re-running
  is the refresh: it re-analyses and rewrites every file it manages.
  Trigger phrases: "setup test context", "initialise test conventions", "set up the test plugin",
  "set up tests for my Python repo", "scaffold test conventions for a TypeScript project",
  "bootstrap test files for this repo", "refresh the generated test conventions".
---

# Setup Test Context

You are the setup orchestrator for the `test-authoring` plugin. Your job is to **analyse this repository** and write the **per-repo files** that the plugin's skills and agents read at runtime: conventions, rules, and shared utilities. Agents and skills themselves live in the plugin and are not scaffolded.

## Pre-existing files at managed paths

The skill keeps **no state between runs** — no manifest, no recorded hashes. It knows only the fixed
set of paths *this version* writes. So a file already sitting at one of those paths is simply
**existing**: it is backed up into this run's backup folder and then overwritten (§2.1). A file under
`.claude/{conventions,rules,shared}/tests/` that is *not* in this version's write set is **reported and
left alone** — never deleted, because without state the skill cannot tell its own retired output from
something you wrote yourself.

Keeping a hand-edit therefore means committing it (or copying it out) before re-running. Re-running
**is** the refresh.

## Supporting assets

Located relative to this skill's base directory:

- **`<plugin-root>/resources/templates/rules/`** — 8 rules templates with `{{PLACEHOLDER}}` markers.
- **`<plugin-root>/resources/templates/shared/`** — `scope-resolution.md` template only (`status-legend.md` is plugin-internal at `<plugin-root>/resources/static/`, never written per-repo).
- **Conventions have no templates** — every conventions file (`project-architecture.md`, the conditional `common-*`) is generated dynamically from Step 1 analysis per `references/tier3-schemas.md`.
- **`references/`** — detailed detection recipes, placeholder rules, and subagent contracts. Loaded on demand during the relevant step.

## Output overview

setup-test-context produces files only in three per-repo namespaces. Under the Slim default the set does not vary by test type — only the conditional `common-*` conventions change it:
- 1 shared (`scope-resolution.md`)
- 8 rules (`test-rules`, `test-writer-rules`, `fix-protocol`, `sut-analysis`, `common-orchestrator-flow`, `common-writer-instructions`, `common-update-instructions`, `common-verifier-checks`)
- 1 conventions (`project-architecture`) + optional `common-test-utilities` / `common-verification-patterns` — code-driven per-type `{type}-test-conventions.md` are **NOT** written under the Slim default; writers derive those conventions from the nearest sibling at runtime
- 1 README (`.claude/shared/tests/README.md`)

setup-test-context does NOT write any of: agents, commands, skills, status-legend (all plugin-bundled).

## Design principles

- **Re-runnability**: safely re-run; every existing file at a target path is backed up and then rewritten (§2.1).
- **Managed files are generated artifacts, not user documents**: re-running setup IS the refresh that delivers template fixes. Every existing file is backed up into this run's backup folder (§3.1) before being overwritten, and listed in the §2.2 confirmation block — never silently.
- **Defensive reading of CLAUDE.md**: never modified; treated as a hint, not source of truth.

---

## Step 1 — Analyse the Repository

Read `references/analysis.md` before starting this step. Work through §1.1–1.7 in order:

1. §1.1 — read CLAUDE.md as hints only
2. §1.2 / §1.2.1 — detect language, frameworks, internal package paths
3. §1.3 — map project structure (source dirs, test dirs, mirroring pattern)
4. §1.4 — learn test conventions via layered sampling
5. §1.5 — identify build and test commands per test project
6. §1.6 / §1.6.1 — identify architectural patterns
7. §1.7 — classify each test project (combo-cell matrix)

Proceed to Step 2 with the completed analysis.

---

## Step 2 — Confirm Analysis with User

### 2.1 Present findings

**Zero supported types — stop here.** If Step 1.7 classified no project 🟩 (a Gherkin-only repo, or no test project at all), do not render the write list and do not spawn anything: report that this repo has no test project the plugin can author for, list each skipped project with its reason, and exit cleanly without writing.

Render the findings table with the columns: language, test framework, mocking library, build tool, and a per-test-project table showing path / type / supported flag / infrastructure summary. Files to be created / overwritten lists reflect ONLY the per-repo files setup-test-context manages:

```
Files setup-test-context will write (new or refresh):

Conventions (.claude/conventions/tests/):
- project-architecture.md
- common-test-utilities.md           (if shared test project detected)
- common-verification-patterns.md    (if cross-layer pattern detected)
  NOTE (Slim default): code-driven per-type {type}-test-conventions.md are NOT written
  -- writers derive per-type conventions from the nearest sibling at runtime.

Rules (.claude/rules/tests/):
- test-rules.md
- test-writer-rules.md
- fix-protocol.md
- sut-analysis.md
- common-orchestrator-flow.md
- common-writer-instructions.md
- common-update-instructions.md
- common-verifier-checks.md

Shared (.claude/shared/tests/):
- scope-resolution.md
- README.md
```

### Overwrite-safe per-file decision

For each path setup-test-context will write:

| State | Condition | Action | In the confirmation block? |
|---|---|---|---|
| **fresh** | path does not exist | write new file | listed |
| **existing** | path exists | back up into this run's backup folder (§3.1), then overwrite | listed |

There is no pristine / user-modified distinction — that needed recorded hashes, and the skill keeps
none. Every existing file is backed up before it is touched, so the safe case and the edited case get
the same treatment, and §3.1 always retains the folder when anything was overwritten.

There is no per-file prompt. One existed to ask about files the skill could not prove it wrote; it can
now prove that of no file, so the prompt would fire on every path on every re-run. The batch
confirmation in §2.2 covers the whole set instead.

### Unmanaged files at managed paths (report only)

List any file under `.claude/{conventions,rules,shared}/tests/` that is **not** among this run's write
targets, and say plainly that it is not written by this version and will be left untouched. **Include
dotfiles** — a repo set up by an older version still has `.setup-manifest.json` there, and a plain
listing hides it. Do not
delete it and do not offer to — without recorded state, a leftover from a retired template and a file
you wrote by hand are indistinguishable, and deleting the wrong one is unrecoverable.

The conditional conventions (`common-test-utilities.md`, `common-verification-patterns.md`) land here
whenever their generation condition is unmet this run. That is correct: they are simply not written,
and the report names them so a mis-detection is visible rather than silent.

Collect the list before reaching the final atomic confirmation.

### 2.2 Ask for final confirmation

Ask:
1. Are the test types and Supported flags correct?
2. Review the two lists from §2.1: files to be backed up + overwritten, and unmanaged files that will be left untouched.
3. **Proceed with all per-repo file changes as a single atomic operation?** (Yes / No)

Single yes/no for the entire batch. Proceed to Step 3 only after confirmation.

---

## Step 3 — Generate / Update Per-Repo Files

Apply all changes based on confirmed analysis. Treat as a single atomic operation.

### 3.1 Backup strategy — timestamped folder

**Reading the real clock.** Wherever a timestamp is needed — the backup folder name (§3.1) and the
README's "generated at" line (§3.4) — obtain it by **executing a shell command**, never by writing one
from the model: Claude has no real-time clock and a model-written value comes out as a stub such as a
date with a `00:00:00Z` time. Two stubbed runs collide on the same backup folder name and the second
overwrites the first — which now destroys the only copy of what the first run replaced.

- bash / zsh: `date -u +"%Y-%m-%dT%H:%M:%SZ"`
- PowerShell: `(Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")`

Capture the output and use it verbatim.

If any target file is being **overwritten** (§2.1), create `.claude/backup/setup-{timestamp}/` mirroring the target structure. This folder is the ONLY backup mechanism — no sibling `.bak` files are ever created at managed paths. Backup every file that will be overwritten before any write begins. On verification failure (Step 4), restore from backup.

On success, **keep the folder** whenever anything was overwritten and report its path in Step 5 (§ Recommended next steps) — the skill cannot tell which of those files you had edited, so the backup is your only route back. Delete it only when the run wrote nothing but new files.

When every target is fresh, an in-memory new-files list drives rollback (`rm` each on failure).

### 3.2 Spawn parallel subagents to write rules + shared + conventions

Read `references/subagent-contract.md` first. Note that for setup-test-context, subagents own ONLY conventions, rules, and the scope-resolution shared utility — no agents/commands.

**Spawn protocol** — issue a SINGLE message with multiple `Agent` tool calls so all subagents run in parallel. **Subagent kinds, counts, and ownership are defined canonically in `references/subagent-contract.md`** (§ "When the orchestrator spawns subagents" and § "Subagent kinds"). The table below mirrors it for convenience — if the two ever diverge, the contract wins.

| Repo shape | Subagents spawned (Slim default) |
|---|---|
| 0 supported types | none — Step 2.1 already exited |
| 1 supported type (unit only) | `shared-tier2`, `shared-tier3` (2) |
| 2 supported types (unit + integration) | `shared-tier2`, `shared-tier3` (2) |
| + extra test types | no additional subagent (per-type conventions no longer generated) |

The `shared-tier2` subagent owns the universal rule set (`test-rules`, `test-writer-rules`, `fix-protocol`, `sut-analysis`, `common-orchestrator-flow`, `common-writer-instructions`, `common-update-instructions`, `common-verifier-checks`) plus the `scope-resolution.md` shared utility.

The `shared-tier3` subagent owns the `project-architecture.md` convention (universal) plus the optional `common-test-utilities.md` / `common-verification-patterns.md` (when applicable).

**Slim default — per-type subagents are not spawned**: `<type>-test-conventions.md` is no longer generated for any test type; writers derive those conventions from the nearest sibling at runtime. Only the two shared subagents run.

### 3.3 Subagent prompt skeleton

Pass everything inline. The prompt MUST include:

1. Working directory (repo root, absolute).
2. Backup folder path (already created in §3.1, if applicable).
3. Subagent kind (`shared-tier2` / `shared-tier3`; the legacy `per-type` kind is never dispatched under the Slim default).
4. Test type label — legacy `per-type` field only, so never populated under the Slim default.
5. The write set for this run — which target paths are fresh and which already exist (every existing one is backed up by the orchestrator in §3.1 before subagents spawn, then overwritten).
6. The relevant slice of Step 1 analysis as structured text.
7. Pre-resolved standard placeholder values (`{{LANGUAGE}}`, `{{SRC_DIR}}`, `{{TEST_DIR}}`, etc. — `{{TEST_TYPE}}` / `{{TEST_TYPE_TITLE}}` are legacy per-type placeholders with no surviving consumer).
8. Source template paths (e.g. `<plugin-root>/resources/templates/rules/test-rules.md`).
9. Destination paths (e.g. `.claude/rules/tests/test-rules.md`).
10. Pointers to `references/placeholders.md` (fill rules) and `references/tier3-schemas.md` (Tier 3 generation schemas), per `references/subagent-contract.md` item 10 — single source of truth, do not duplicate it here.

After every write, the subagent **adds an entry** to its return payload with the path and category — the orchestrator aggregates these into the §3.4 report and uses them as this run's write log for the Step 4 checks.

### 3.4 Aggregate subagent output and write README

After all subagents return, render an aggregation table (same shape as the older bootstrap's §3.4 table). Then write `.claude/shared/tests/README.md` documenting the new layout (see `<plugin-root>/resources/templates/` for the template if needed; for now, write a minimal README with: the list of files generated; the plugin version, read from `<plugin-root>/.claude-plugin/plugin.json` (write `unknown` if unreadable); the generation timestamp, obtained per §3.1's **Reading the real clock**; and a link to the plugin docs). That version line is the only on-disk record of which plugin version produced these files — nothing reads it automatically, but it is what a human checks when the files look wrong.

---

## Step 4 — Verify

After all writes:

1. Confirm every file exists.
2. **Frontmatter check (bounded read — never re-read whole files into the main context)**: for each written file with frontmatter (every generated conventions and rules file carries one), read only the opening frontmatter block — a bounded read of the first ~20 lines (Read with a line limit, or `sed -n '1,20p'`). Assert the block closes with `---` inside that bound **and** carries a non-empty `description`; either failing is a verification failure → rollback. Whole-file content checks belong to item 3's mechanical sweep; re-reading every generated file would pull the entire rule set into the main context — the exact bloat the per-type skills' lazy loading removed. (Unresolved `{{PLACEHOLDER}}` tokens and leaked HTML comments are item 3's greps — do not re-check them by reading file bodies.)
3. **Mechanical grep sweep** — run against the files written THIS run, never the whole directory: unmanaged files (§2.1) are outside this run's contract, and their content (e.g. quoted `{{ }}` template syntax) must not fail verification.
   ```bash
   # <written-files…> = every path in this run's write log
   grep -n "{{" <written-files…>
   grep -n "<!-- " <written-files-except-README.md…>
   ```
   Both MUST return no output. Any match → verification failure → rollback.
4. **Path existence check** — extract concrete paths mentioned in generated output, verify with Glob. Missing paths are warnings (🟨), not failures.
5. **Cross-reference check**: for each plugin agent matching a test type confirmed as supported in Step 2 — the plugin agents live at `<plugin-root>/agents/` (e.g. `<plugin-root>/agents/add-unit-test-agent.md` for `unit`) — extract the `.claude/{conventions,rules,shared}/tests/` paths it references and check each against disk:
   - exists → pass.
   - missing but **conditional** (`common-test-utilities.md`, `common-verification-patterns.md`) with its generation condition unmet this run → warning (🟨), not a failure.
   - **missing `{type}-test-conventions.md`** (`unit`, `integration`, or any extra type) → **expected-absent / silent pass**. The Slim default does not generate these — writers derive per-type conventions from the nearest sibling at runtime — so an agent referencing one while it is absent is the normal state: NOT a warning, NOT a failure.
   - missing and non-conditional → verification failure → rollback.
   Agents for unsupported test types are skipped entirely — their dangling references are expected. The plugin's agents are read-only here; this check confirms our outputs satisfy their input expectations.

   Distinguish two kinds of absence: a missing *referenced output path* is judged by the bullets above (a non-conditional one → rollback, since it is our output). A missing *agent definition file* under `<plugin-root>/agents/` (e.g. plugin-layout drift) is instead a warning (🟨) — skip that agent's cross-reference check rather than rolling back, because a missing plugin file says nothing about whether our outputs are correct.
6. **On failure**: roll back per §3.1 strategy. Do NOT leave the system partially updated.
7. **On success**: keep all written files. Do NOT auto-commit. Keep or delete the backup folder per §3.1's retention rule.

Render the same Verification Results table the older bootstrap uses (Step 4.x).

---

## Step 4.5 — Gitignore the per-repo files (user-scope) + migrate already-tracked files

Run this **only after Step 4 reports success** (item 7). If Step 4 rolled back, skip this step entirely — keeping the `.gitignore` change on the success path means a rollback never strands a `.gitignore` edit, so the whole run stays atomic from the user's perspective.

setup-test-context's per-repo files are **user-scope** — local, never committed — so a teammate who has not adopted the test-skills plugin never carries generated files in their tree, and there is no PR clutter or merge conflict. The skills run cacheless without these files, so user-scope costs only a per-developer setup run, not correctness.

**4.5a — Add the ignore lines.** Ensure `.gitignore` (at repo root) contains all four lines, each added only if not already present (newline-safety: if `.gitignore` exists but does not end with a newline, append one first so a new line never concatenates onto the previous; create the file with just these lines + newline if it does not exist):
```
.claude/conventions/tests/
.claude/rules/tests/
.claude/shared/tests/
.claude/backup/
```

**4.5b — Untrack anything already committed (migration).** `.gitignore` does not affect files git already tracks. Run `git ls-files .claude/conventions/tests .claude/rules/tests .claude/shared/tests`. If it lists any files, **print this notice; do NOT run the command automatically** — then continue to Step 5 (this skill never auto-commits; untracking is a committable change the user owns and reviews):
```
These per-repo test files are already tracked by git and will keep showing in PRs until untracked:
  <list the files>
To make them user-scope, run this and commit the removal as its own change:
  git rm -r --cached .claude/conventions/tests .claude/rules/tests .claude/shared/tests
Heads-up: once that commit is pushed, teammates' working copies are deleted on pull — they re-create them by running setup-test-context themselves.
```
If `git ls-files` returns nothing (fresh setup, or already untracked) → say nothing; there is nothing to migrate. Because this step runs only on the Step 4 success path, the `.gitignore` change and the per-repo files are committed-to or rolled-back-from together — a rollback can never leave a `.gitignore` edit behind.

---

## Step 5 — Report

Render the report below.

### Repo profile recap

Same shape as the older bootstrap, with the **Files written** count reflecting only conventions + rules + shared + README (no agents / commands).

### File index

```
Generated files (per-repo, managed by setup-test-context):

Conventions (.claude/conventions/tests/):
  - project-architecture.md
  - common-test-utilities.md (if applicable)
  - common-verification-patterns.md (if applicable)
  (Slim default: code-driven {type}-test-conventions.md not written -- sibling-derived at runtime)

Rules (.claude/rules/tests/):
  - test-rules.md, test-writer-rules.md, fix-protocol.md, sut-analysis.md
  - common-orchestrator-flow.md, common-writer-instructions.md
  - common-update-instructions.md, common-verifier-checks.md

Shared (.claude/shared/tests/):
  - scope-resolution.md
  - README.md

Plugin-bundled (NOT written here — supplied by test-authoring plugin):
  - status-legend.md (in plugin static)
  - 8 agents (test-authoring: namespace)
  - 6 skills (setup-test-context, scan-test-gaps, add-* / update-*)
  - guarded hook templates
```

### Recommended next steps

1. Review the generated per-repo files to ensure they match your repo.
2. Try `/test-authoring:scan-test-gaps` to test gap scanning on a small area.
3. Try `/test-authoring:add-unit-test ComponentName` on a small change to verify the add workflow.
4. (If CLAUDE.md drift was reported) Update CLAUDE.md to reflect the current codebase — setup-test-context did not modify CLAUDE.md.
5. If a backup folder was kept (§3.1), report its path here and say what it holds — it is the only copy of whatever this run overwrote.
6. To remove this scaffolding later, delete `.claude/{conventions,rules,shared}/tests/`. Two things live outside those directories: any kept `.claude/backup/setup-*/` folder, and the four lines this skill added to `.gitignore` (§4.5a).

---
