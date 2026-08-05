---
name: setup-test-context
expected_schema_version: "1.0"
description: >
  Analyse the current repo and write per-repo test conventions, rules, and shared utility files
  to `.claude/{conventions,rules,shared}/tests/`. Plugin-bundled agents and skills (in
  `test-authoring`) read these per-repo files at runtime. Works for any language with a
  detectable test framework (C#, Python, TypeScript, Go, Java, etc.) — auto-detects language
  and dispatches the matching baseline via `resources/templates/lang/` fragments. Pass
  `uninstall` as the first argument to remove every file this skill previously wrote, classified
  pristine vs user-modified.
  Trigger phrases: "setup test context", "initialise test conventions", "set up the test plugin",
  "set up tests for my Python repo", "scaffold test conventions for a TypeScript project",
  "bootstrap test files for this repo", "uninstall setup-test-context",
  "remove generated test conventions".
---

# Setup Test Context

You are the setup orchestrator for the `test-authoring` plugin. Your job is to **analyse this repository** and write the **per-repo files** that the plugin's skills and agents read at runtime: conventions, rules, and shared utilities. Agents and skills themselves live in the plugin and are not scaffolded.

## Pre-existing files at managed paths

When setup-test-context runs against a repo that already has files at `.claude/{conventions,rules,shared}/tests/` paths but no `.setup-manifest.json` (or the manifest does not list those files), the **idempotent overwrite-safe flow** (Step 3 below) handles each per-conflict: user chooses keep / overwrite / backup-and-overwrite per file.

## Step 0a — Mode dispatch

If the user invocation includes the literal token `uninstall` as the first argument (e.g. `/test-authoring:setup-test-context uninstall`), enter **Uninstall mode** immediately — the full procedure (U1 locate manifest → U2 classify → U3 batch confirm → U4 execute + report) is in `references/uninstall.md`. Skip Step 0 schema check, Step 1 analysis, Step 2 confirmation, and Step 3 generation entirely.

Otherwise proceed to Step 0 below.

## Step 0 — Schema-drift check (re-install only)

Goal: detect when the plugin's template schema has changed since the last setup run.

1. Determine `<plugin-root>` (two directories above this `SKILL.md`: `<skill-dir>/../..`).
2. Read `<plugin-root>/resources/templates/template-schema-versions.json` (single JSON file with per-category fields `conventions`, `rules`, `shared`).
3. Try to read `.claude/shared/tests/.setup-manifest.json`. If it does not exist → **fresh install**, skip drift check, continue to Step 1.
4. Parse the manifest. Compare its `schema_versions.{category}` with each plugin per-category version from step 2:
   - **All categories match AND `plugin_version` matches** → no drift. **Schema = file *format*, not content**: the analysis-derived cross-layer map (`project-architecture.md` / `common-*` / `fixture-capabilities.md`) can be stale relative to repo evolution even when schemas match, and re-running setup IS how it refreshes. Ask the user: "Schemas current, but the analysis-derived test map may be stale relative to repo changes — re-write per-repo files anyway to refresh? [y/N]". If `y` → continue Step 1; if no → exit cleanly.
   - **Any category schema version differs** → schema-drift detected. For each diverged category, present this prompt:
     ```
     Category <conventions/rules/shared> schema changed: was <manifest-version>, now <plugin-version>.
     Existing files may not match the format expected by current skills/agents.

     Choose one:
       (a) Back up existing <category> files into this run's backup folder (§3.1), regenerate from new templates  [recommended]
       (b) Skip this category — leave existing files unchanged (risky: schema mismatch)
       (c) Abort setup
     ```
   - **Plugin_version differs but every schema_version matches** → minor patch. Ask: "Plugin version changed (X → Y). Refresh all template-derived files anyway? [y/N]".
5. Continue to Step 1 with the user's drift-handling choices recorded.

The manifest's `schema_versions` are updated only at the end of Step 3 (after successful writes) — do not bump them in Step 0.

## Supporting assets

Located relative to this skill's base directory:

- **`<plugin-root>/resources/templates/rules/`** — 9 rules templates with `{{PLACEHOLDER}}` markers.
- **`<plugin-root>/resources/templates/shared/`** — `scope-resolution.md` template only (`status-legend.md` is plugin-internal at `<plugin-root>/resources/static/`, never written per-repo).
- **`<plugin-root>/resources/templates/conventions/`** — 2 fixed templates (`component-test-conventions.md`, `fixture-capabilities.md`); the rest (`project-architecture.md`, `<type>-test-conventions.md`) are generated dynamically from Step 1 analysis per `references/tier3-schemas.md`.
- **`references/`** — detailed detection recipes, placeholder rules, manifest schema, subagent contracts, and the uninstall procedure. Loaded on demand during the relevant step.

## Output overview

setup-test-context produces files only in three per-repo namespaces. Counts scale with supported test types:

For a typical repo with **unit + integration**:
- 1 shared (`scope-resolution.md`)
- 8 rules (`test-rules`, `test-writer-rules`, `fix-protocol`, `sut-analysis`, `common-orchestrator-flow`, `common-writer-instructions`, `common-update-instructions`, `common-verifier-checks`)
- 1 conventions (`project-architecture`) + optional `common-test-utilities` / `common-verification-patterns` — code-driven per-type `{type}-test-conventions.md` are **NOT** written under the Slim default; writers derive those conventions from the nearest sibling at runtime
- 1 manifest (`.setup-manifest.json`)
- 1 README (`.claude/shared/tests/README.md`)

Adding **component** support adds:
- 1 rule (`test-component-rules`)
- 1–2 conventions (`component-test-conventions` + `fixture-capabilities` if fixture detected)

setup-test-context does NOT write any of: agents, commands, skills, status-legend (all plugin-bundled).

## Design principles

- **Re-runnability**: safely re-run; existing files at target paths are processed via the **idempotent overwrite-safe flow** (per-file decision based on manifest hash and user choice).
- **Managed files are generated artifacts, not user documents**: re-running setup IS the refresh that delivers template fixes. A file whose hash differs from the manifest is classified user-modified and is backed up into this run's backup folder (§3.1), then overwritten — flagged in the §2.2 confirmation block, never silently.
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

Render the findings table with the columns: language, test framework, mocking library, build tool, and a per-test-project table showing path / type / supported flag / infrastructure summary. Files to be created / overwritten lists reflect ONLY the per-repo files setup-test-context manages:

```
Files setup-test-context will write (new or refresh):

Conventions (.claude/conventions/tests/):
- project-architecture.md
- component-test-conventions.md     (if component supported)
- fixture-capabilities.md            (if component + fixture detected)
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
- test-component-rules.md            (if component supported)

Shared (.claude/shared/tests/):
- scope-resolution.md
- README.md
- .setup-manifest.json (install inventory)
```

### Idempotent overwrite-safe per-file decision

For each path setup-test-context will write, classify against `.claude/shared/tests/.setup-manifest.json`:

| State | Condition | Default action | Confirmation needed? |
|---|---|---|---|
| **fresh** | path does not exist | write new file | no |
| **pristine** | path exists, in manifest, hash matches | overwrite (refresh from current template + analysis) | no |
| **user-modified** | path exists, in manifest, hash differs | **back up into this run's backup folder (§3.1), then overwrite** | flag in confirmation block |
| **legacy** | path exists, NOT in manifest | per-file three-way prompt below | yes |

Hash comparisons for this classification normalise line endings (CRLF→LF) before computing SHA-256 — see `references/manifest.md` § SHA-256 calculation.

The **legacy** state covers files at managed paths that this skill did not write (no manifest entry). For each legacy file, ask before Step 3:

```
Existing file (not managed by setup-test-context): <path>

Choose:
  (a) Keep as-is, do NOT overwrite
  (b) Overwrite with the new version (lose any modifications)
  (c) Back up into this run's backup folder (§3.1), then overwrite
```

### Stale managed files (template renames / retirements)

A manifest-listed path that is NOT among this run's write targets is a leftover from a renamed or retired template (e.g. an old `test-verifier-rules.md` after the template became `fix-protocol.md`). Default action: **back up into this run's backup folder (§3.1), delete the file, and drop its manifest entry** — listed in the §2.2 confirmation block.

Two exclusions are NOT stale and stay carried forward (§3.5):
- files of a category the user chose to skip via Step 0 option (b) — deleting them would contradict that choice;
- code-driven `{type}-test-conventions.md` kept by the Slim default carve-out.

Conditional files (`fixture-capabilities.md`, `common-test-utilities.md`, `common-verification-patterns.md`) are deliberately NOT excluded: when their generation condition is unmet this run they are not write targets, so they follow stale semantics — the managed set reflects THIS run's analysis, and the backup + confirmation listing is the guard against a mis-detection.

Collect the user's per-file decisions in a planning table before reaching the final atomic confirmation.

### 2.2 Ask for final confirmation

Ask:
1. Are the test types and Supported flags correct?
2. Confirm per-file decisions for legacy files (above).
3. Review the flagged lists: user-modified files to be backed up + overwritten, and stale managed files to be backed up + deleted (§2.1).
4. Confirm per-category drift decisions from Step 0 (if any).
5. **Proceed with all per-repo file changes as a single atomic operation?** (Yes / No)

Single yes/no for the entire batch. Proceed to Step 3 only after confirmation.

---

## Step 3 — Generate / Update Per-Repo Files

Apply all changes based on confirmed analysis. Treat as a single atomic operation.

### 3.1 Backup strategy — timestamped folder

If any target file is being **overwritten** (pristine, user-modified, drift option (a), or legacy with user choosing overwrite/backup), or any stale managed file is being **deleted** (§2.1), create `.claude/backup/setup-{timestamp}/` mirroring the target structure. This folder is the ONLY backup mechanism — no sibling `.bak` files are ever created at managed paths. Backup every file that will be overwritten or deleted before any write begins. On verification failure (Step 4), restore from backup. On success, delete the backup folder — UNLESS it contains user-modified files that were overwritten, stale managed files that were deleted, or files backed up at the user's explicit request (Step 0 drift option (a) or legacy option (c)); in any of those cases keep the folder and report its path in Step 5 so the user can recover or discard it themselves.

For **fresh installs** (no manifest), an in-memory new-files list drives rollback (`rm` each on failure).

### 3.2 Spawn parallel subagents to write rules + shared + conventions

Read `references/subagent-contract.md` first. Note that for setup-test-context, subagents own ONLY conventions, rules, and the scope-resolution shared utility — no agents/commands.

**Spawn protocol** — issue a SINGLE message with multiple `Agent` tool calls so all subagents run in parallel. **Subagent kinds, counts, and ownership are defined canonically in `references/subagent-contract.md`** (§ "When the orchestrator spawns subagents" and § "Subagent kinds"). The table below mirrors it for convenience — if the two ever diverge, the contract wins.

| Repo shape | Subagents spawned (Slim default) |
|---|---|
| 1 supported type (unit only) | `shared-tier2`, `shared-tier3` (2) |
| 2 supported types (unit + integration) | `shared-tier2`, `shared-tier3` (2) |
| + component support | + `component` (3) |
| + extra code-driven types | no additional subagent (per-type conventions no longer generated) |

The `shared-tier2` subagent owns the universal rule set (`test-rules`, `test-writer-rules`, `fix-protocol`, `sut-analysis`, `common-orchestrator-flow`, `common-writer-instructions`, `common-update-instructions`, `common-verifier-checks`) plus the `scope-resolution.md` shared utility.

The `shared-tier3` subagent owns the `project-architecture.md` convention (universal) plus the optional `common-test-utilities.md` / `common-verification-patterns.md` (when applicable).

**Slim default — code-driven per-type subagents are not spawned**: `<type>-test-conventions.md` for code-driven types (`unit`, `integration`, extra) is no longer generated; writers derive those conventions from the nearest sibling at runtime. Among per-type kinds only the **component** subagent (config-driven) is still spawned — it owns `component-test-conventions.md`, `fixture-capabilities.md` (if fixture detected), and `test-component-rules.md`.

### 3.3 Subagent prompt skeleton

Pass everything inline. The prompt MUST include:

1. Working directory (repo root, absolute).
2. Backup folder path (already created in §3.1, if applicable).
3. Subagent kind (`per-type` / `shared-tier2` / `shared-tier3`). The component subagent is dispatched as `per-type` with test type label `component` (item 4); its three-file, fixed-sequence special-case behaviour is driven by the explicit destination paths (item 9) plus the `Component-type subagent` section of `subagent-contract.md`, not by a distinct kind value.
4. Test type label (per-type only).
5. Per-file decision flags from Step 2.2 (which targets to overwrite — pristine and user-modified alike, the latter already backed up per §3.1 — and which legacy targets the user chose to keep).
6. The relevant slice of Step 1 analysis as structured text.
7. Pre-resolved standard placeholder values (`{{LANGUAGE}}`, `{{SRC_DIR}}`, `{{TEST_DIR}}`, etc.), **including `{{CONVENTIONS_SCHEMA_VERSION}}`** read from `<plugin-root>/resources/templates/template-schema-versions.json` field `conventions`. This placeholder is used by Tier 3 conventions recipes (see `references/tier3-schemas.md`) to fill their frontmatter `schema_version`; the same JSON value is also written into the manifest `files[].schema_version` for matching files in §3.5 — single source of truth.
8. Source template paths (e.g. `<plugin-root>/resources/templates/rules/test-rules.md`).
9. Destination paths (e.g. `.claude/rules/tests/test-rules.md`).
10. Pointers to `references/placeholders.md` (fill rules + Language fragments § dispatch documentation) and `references/tier3-schemas.md` (Tier 3 generation schemas), plus **pre-resolved absolute paths of language fragment files** per `references/subagent-contract.md` item 10 (covers the derivation rule, filesystem probe, per-subagent ownership, and the missing-fragment sentinel — single source of truth, do not duplicate the dispatch spec here).

After every write, the subagent **adds an entry** to its return payload with the path, sha256 (computed over the written content with line endings normalised CRLF→LF before hashing — see `references/manifest.md` § SHA-256 calculation), and category — these are aggregated by the orchestrator into the manifest in §3.5.

### 3.4 Aggregate subagent output and write README

After all subagents return, render an aggregation table (same shape as the older bootstrap's §3.4 table). Then write `.claude/shared/tests/README.md` documenting the new layout (see `<plugin-root>/resources/templates/` for the template if needed; for now, write a minimal README with: list of files generated, plugin version, schema versions, when generated, link to plugin docs).

### 3.5 Write the install manifest

After README, build and write `.claude/shared/tests/.setup-manifest.json` per the schema in `references/manifest.md`:

1. Build `files[]` from two sources:
   - **Written this run** — the aggregated subagent `written:` payloads (§3.2–3.3) plus the orchestrator's own writes (§3.4 README).
   - **Carried forward verbatim** — the previous manifest's entries (path, sha256, category, schema_version, test_type unchanged) for paths intentionally not written this run: every file of a category the user chose to skip via Step 0 option (b), **and existing code-driven `{type}-test-conventions.md` that the Slim default no longer generates** (present on disk from an older full setup, intentionally not regenerated — carry their entries verbatim so they stay tracked for uninstall + drift). Dropping these entries would silently orphan the files from uninstall tracking and drift detection. Stale managed files deleted this run (§2.1) are the one deliberate removal: their entries are dropped from the manifest — non-silent, because each was backed up and listed in the §2.2 confirmation.
2. For each path written this run, record the SHA-256 of the written content (lowercase hex, line endings normalised CRLF→LF before hashing per `references/manifest.md` § SHA-256 calculation — taken from the subagent payload, or computed directly for orchestrator-written files), `category` (`conventions` / `rules` / `shared`), `schema_version` (from `<plugin-root>/resources/templates/template-schema-versions.json` field `<category>` — for the four Tier 3 dynamic conventions files this is the **same** value already substituted into the file's frontmatter via `{{CONVENTIONS_SCHEMA_VERSION}}` in §3.3, so manifest and frontmatter MUST agree), and `test_type` (`null` for universal files, otherwise the type label). Carried-forward entries keep their previous values untouched — their sha256 records the run that last wrote them.
3. Set top-level `schema_versions.{category}` from the same `template-schema-versions.json` fields — EXCEPT categories the user chose to skip via Step 0 option (b): retain the previous manifest value for those, so the unresolved drift is re-detected on the next run instead of being permanently masked.
4. Set `plugin_version` from `<plugin-root>/.claude-plugin/plugin.json` (write `unknown` if unreadable).
5. Set `generated_at` by **executing a shell command to read the real clock** — do NOT model-generate the timestamp (Claude has no real-time clock; a model-written value will be a stub like a date with `00:00:00Z` time). Use:
   - bash / zsh: `date -u +"%Y-%m-%dT%H:%M:%SZ"`
   - PowerShell: `(Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")`
   Capture the command output and write it verbatim into the manifest.
6. Set `test_types` to the list confirmed in Step 2.
7. Atomic write (temp file + rename) to `.claude/shared/tests/.setup-manifest.json`.

Register the manifest path with rollback bookkeeping (same as any other written file).

---

## Step 4 — Verify

After all writes:

1. Confirm every file exists.
2. **Frontmatter check (bounded read — never re-read whole files into the main context)**: for each written file with frontmatter (conventions/rules carry `schema_version`), read only the opening frontmatter block — a bounded read of the first ~20 lines (Read with a line limit, or `sed -n '1,20p'`), treating a missing closing `---` within that bound as invalid frontmatter → verification failure. Whole-file content checks belong to item 3's mechanical sweep; re-reading every generated file would pull the entire rule set into the main context — the exact bloat the per-type skills' lazy loading removed. For every Tier 3 dynamic conventions file (`project-architecture.md`, `{type}-test-conventions.md`, `common-test-utilities.md`, `common-verification-patterns.md`), assert: (a) frontmatter contains a `schema_version` field, AND (b) its value equals `template-schema-versions.json.conventions`. Any missing/mismatched value → verification failure with message `"Tier 3 dynamic file <path> missing or mismatched schema_version; recipe in references/tier3-schemas.md is broken — file an upstream bug."` → rollback. (Unresolved `{{PLACEHOLDER}}` tokens and leaked HTML comments are item 3's greps — do not re-check them by reading file bodies.)
3. **Mechanical grep sweep** — run against the files written THIS run (from the §3.5 write log), never the whole directory: kept-legacy and orphan files are outside this run's contract, and their content (e.g. quoted `{{ }}` template syntax) must not fail verification.
   ```bash
   # <written-files…> = every path in this run's write log
   grep -n "{{" <written-files…>
   grep -n "<!-- " <written-files-except-README.md…>
   ```
   Both MUST return no output. Any match → verification failure → rollback.
4. **Path existence check** — extract concrete paths mentioned in generated output, verify with Glob. Missing paths are warnings (🟨), not failures.
5. **Manifest validity**:
   - Parses as JSON.
   - `manifest_schema_version == "1.0"`.
   - Every `files[].path` exists on disk.
   - SHA-256 (CRLF→LF-normalised before hashing, per `references/manifest.md` § SHA-256 calculation) of each file **written this run** matches `files[].sha256`. Carried-forward entries (§3.5 step 1) are exempt — their hashes record the run that last wrote them.
   - Failure here → rollback.
6. **Cross-reference check**: for each plugin agent matching a test type confirmed as supported in Step 2 — the plugin agents live at `<plugin-root>/agents/` (e.g. `<plugin-root>/agents/add-unit-test-agent.md` for `unit`) — extract the `.claude/{conventions,rules,shared}/tests/` paths it references and check each against disk:
   - exists → pass.
   - missing but **conditional** (`fixture-capabilities.md`, `common-test-utilities.md`, `common-verification-patterns.md`) with its generation condition unmet this run → warning (🟨), not a failure.
   - **missing code-driven `{type}-test-conventions.md`** (`unit`, `integration`, or any extra code-driven type) → **expected-absent / silent pass**. The Slim default does not generate these — writers derive per-type conventions from the nearest sibling at runtime — so an agent referencing one while it is absent is the normal state: NOT a warning, NOT a failure. (`component-test-conventions.md` is config-driven and still generated, so it keeps the conditional/exists semantics above.)
   - missing and non-conditional → verification failure → rollback.
   Agents for unsupported test types are skipped entirely — their dangling references are expected. The plugin's agents are read-only here; this check confirms our outputs satisfy their input expectations.

   Distinguish two kinds of absence: a missing *referenced output path* is judged by the bullets above (a non-conditional one → rollback, since it is our output). A missing *agent definition file* under `<plugin-root>/agents/` (e.g. plugin-layout drift) is instead a warning (🟨) — skip that agent's cross-reference check rather than rolling back, because a missing plugin file says nothing about whether our outputs are correct.
7. **On failure**: roll back per §3.1 strategy. Do NOT leave the system partially updated.
8. **On success**: keep all written files. Do NOT auto-commit. Delete the backup folder — unless §3.1's retention rule keeps it (user-modified overwrites, stale deletions, or user-requested backups).

Render the same Verification Results table the older bootstrap uses (Step 4.x), with the manifest validity row referring to the new manifest path and schema version.

---

## Step 4.5 — Gitignore the per-repo files (user-scope) + migrate already-tracked files

Run this **only after Step 4 reports success** (item 8). If Step 4 rolled back, skip this step entirely — keeping the `.gitignore` change on the success path means a rollback never strands a `.gitignore` edit, so the whole run stays atomic from the user's perspective.

setup-test-context's per-repo files are **user-scope** — local, never committed — so a teammate who has not adopted the test-skills plugin never carries generated files in their tree, and there is no PR clutter or merge conflict. The skills run cacheless without these files, so user-scope costs only a per-developer setup run, not correctness.

**4.5a — Add the ignore lines.** Ensure `.gitignore` (at repo root) contains all three lines, each added only if not already present (newline-safety: if `.gitignore` exists but does not end with a newline, append one first so a new line never concatenates onto the previous; create the file with just these lines + newline if it does not exist):
```
.claude/conventions/tests/
.claude/rules/tests/
.claude/shared/tests/
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

Same shape as the older bootstrap, with the **Files written** count reflecting only conventions + rules + shared + manifest + README (no agents / commands).

### File index

```
Generated files (per-repo, managed by setup-test-context):

Conventions (.claude/conventions/tests/):
  - project-architecture.md
  - component-test-conventions.md (if component supported)
  - fixture-capabilities.md (if component + fixture)
  - common-test-utilities.md (if applicable)
  - common-verification-patterns.md (if applicable)
  (Slim default: code-driven {type}-test-conventions.md not written -- sibling-derived at runtime)

Rules (.claude/rules/tests/):
  - test-rules.md, test-writer-rules.md, fix-protocol.md, sut-analysis.md
  - common-orchestrator-flow.md, common-writer-instructions.md
  - common-update-instructions.md, common-verifier-checks.md
  - test-component-rules.md (if component supported)

Shared (.claude/shared/tests/):
  - scope-resolution.md
  - README.md
  - .setup-manifest.json (install inventory)

Plugin-bundled (NOT written here — supplied by test-authoring plugin):
  - status-legend.md (in plugin static)
  - 12 agents (test-authoring: namespace)
  - 7 skills (setup-test-context, scan-test-gaps, add-* / update-*)
  - guarded hook templates
```

### Recommended next steps

1. Review the generated per-repo files to ensure they match your repo.
2. Try `/test-authoring:scan-test-gaps` to test gap scanning on a small area.
3. Try `/test-authoring:add-unit-test ComponentName` on a small change to verify the add workflow.
4. (If CLAUDE.md drift was reported) Update CLAUDE.md to reflect the current codebase — setup-test-context did not modify CLAUDE.md.
5. To remove this scaffolding later, run `/test-authoring:setup-test-context uninstall`.

---
