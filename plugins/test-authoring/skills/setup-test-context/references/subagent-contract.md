# Subagent contract for setup-test-context Step 3 file generation

This contract governs the parallel subagents the setup-test-context orchestrator spawns in Step 3
to generate per-repo conventions, rules, and shared files.
The orchestrator owns user interaction, atomicity, backup, and rollback;
subagents are an internal optimization for parallelizing independent file writes.

**Scope guard**: setup-test-context writes ONLY per-repo files under
`.claude/{conventions,rules,shared}/tests/`.
Agents, commands, skills, hooks, and static assets are plugin-bundled and never scaffolded here.
This supersedes the older bootstrap contract that also scaffolded `.claude/agents/tests/`
and `.claude/commands/tests/` — those tiers no longer exist in this skill.

## When the orchestrator spawns subagents

After Step 2 confirmation and §3.1 (backup) complete, the orchestrator spawns N subagents
**in a single message with multiple `Agent` tool calls** so they run in parallel (SKILL.md §3.2).

Subagent counts by repo shape (**Slim default: per-type subagents are NOT spawned** — their sole output `{type}-test-conventions.md` is no longer generated; writers derive per-type conventions from the nearest sibling at runtime):
- 1 supported test type (unit only): **2 subagents** — `shared-tier2`, `shared-tier3`
- 2 supported test types (unit + integration): **2 subagents** — `shared-tier2`, `shared-tier3`
- extra test types: **no additional subagent** (was: + one per-type each)

## Subagent kinds

### Per-type subagent — **Slim default: NOT spawned**

> Under the Slim default no per-type subagent is spawned for any test type: its sole output `{type}-test-conventions.md` is no longer generated, and writers derive per-type conventions from the nearest sibling at runtime. This section documents the legacy / full-regeneration behaviour only.

Owns the Tier 3 generated conventions for one test type
(generated per `references/tier3-schemas.md`, not template-copied).

Files owned (e.g. for `type=unit`) — paths relative to repo root:
- `.claude/conventions/tests/unit-test-conventions.md`

### `shared-tier2` subagent

Owns the universal rule set plus the scope-resolution shared utility.
Independent of per-type analysis.

Files owned:
- `.claude/rules/tests/test-rules.md`, `.claude/rules/tests/test-writer-rules.md`, `.claude/rules/tests/fix-protocol.md`, `.claude/rules/tests/sut-analysis.md`, `.claude/rules/tests/common-orchestrator-flow.md`, `.claude/rules/tests/common-writer-instructions.md`, `.claude/rules/tests/common-update-instructions.md`, `.claude/rules/tests/common-verifier-checks.md`
- `.claude/shared/tests/scope-resolution.md`

### `shared-tier3` subagent

Owns Tier 3 conventions that are not type-scoped.

Files owned:
- `.claude/conventions/tests/project-architecture.md`
- `.claude/conventions/tests/common-test-utilities.md` (only if Step 1.3 detected a shared test project)
- `.claude/conventions/tests/common-verification-patterns.md` (only if Step 1.4 detected ≥1 qualifying pattern)

## Input contract (passed inline in the orchestrator's `Agent` prompt)

The orchestrator passes everything inline as structured text in the prompt.
**No temp files, no shared state files.** Each subagent receives:

1. **Working directory** — repo root (absolute path).
2. **Backup folder path** — already created in §3.1, e.g. `.claude/backup/setup-2026-04-28-103045/` (if applicable).
3. **Subagent kind** — one of `shared-tier2`, `shared-tier3` (the legacy `per-type` kind is never dispatched under the Slim default).
4. **Test type label + authoring model** — legacy `per-type` field only (e.g. `unit`, `integration`; `code-driven` or `config-driven`, the user-confirmed values from Step 2.1). Never populated under the Slim default, which dispatches no per-type subagent. Item numbers below are stable — other documents cite them by number.
5. **The write set for this run** — which target paths are fresh and which already exist. Every existing one is backed up by the orchestrator in §3.1 before subagents spawn, then overwritten; there is no keep option and no per-file classification.
6. **Analysis slice** — only the parts of Step 1 output relevant to this subagent. Examples by kind:
   - shared-tier2: language, universal rule set inputs (verifier expectations, fix protocol settings), full build/test commands across all test projects (for `test-rules.md`), and the internal packages detected in §1.2.1 with their install models and verified paths (for `sut-analysis.md`'s `{{KNOWN_PACKAGES_TABLE}}`).
   - shared-tier3: project structure (§1.3), shared test project info if any, cross-layer verification patterns (§1.4 global), architectural patterns (§1.6).
7. **Pre-resolved standard placeholders** — `{{LANGUAGE}}`, `{{PROJECT_DESCRIPTION}}`, `{{SRC_DIR}}`, `{{TEST_DIR}}`, `{{SRC_GLOB}}`, `{{TEST_GLOB}}`, and `{{TEST_TYPE}}` / `{{TEST_TYPE_TITLE}}` (legacy per-type placeholders with no surviving consumer). The orchestrator has already computed these.
8. **Files to write** — explicit list of absolute target paths under `.claude/{conventions,rules,shared}/tests/`.
9. **Files NOT to touch** — explicit list of paths owned by other subagents (defensive boundary).
10. **References to consult** — paths to:
    - `references/placeholders.md` (plugin-side fill rules)
    - `references/tier3-schemas.md` (Tier 3 generation schemas)

    Subagents read these for fill rules and generation schemas; do not duplicate the schemas in the prompt.

### Boundary condition (note, do not design around)

Inline handoff scales fine for typical repos — per-type analysis slice is a few KB to ~10 KB. It would start to strain prompt budgets only on outlier repos: §1.2.1 internal-package tables with 50+ entries, or unusually deep §1.4 sampling output across many test projects. If that materializes, revisit by spilling the largest sections to a file under the backup folder; do not pre-build that path.

## Output contract (returned by the subagent in its final message)

The subagent returns a structured response.
Format MUST be parseable by the orchestrator without re-reading file content —
in particular, the orchestrator's §3.4 report and the Step 4 write log come directly from these payloads,
so every `written` entry carries its path and category inline.

```
written:
  - path: <absolute file path>
    category: <conventions | rules | shared>
skipped:
  - <absolute file path> — <reason, e.g. "no shared test project detected", "a conditional file whose condition was unmet">
errors:
  - <absolute file path> — <single-line error message>
```

Rules:
- `written` lists every file actually written, each entry with `path` and `category` — both mandatory. Empty list ⇒ subagent did nothing (must also be reflected in `errors` or `skipped`).
- `skipped` is for files the subagent did not generate: conditional files whose condition was unmet (per `tier3-schemas.md`). Skips are not failures.
- `errors` is empty on success. Any non-empty `errors` list signals failure for this subagent.
- One terse entry per file. The orchestrator aggregates and renders the user-facing table; do not emit prose summaries, narrative text, or repeated content.

## Failure protocol

- **Subagent does not delete files on its own failure.** It writes what it can, populates `errors`, and stops.
- **Orchestrator waits for ALL spawned subagents to return** before deciding success/failure. There is no mid-flight cancellation — subagents already in flight run to completion.
- If any subagent returns a non-empty `errors` list, the orchestrator skips §3.4 (README) and goes straight to rollback.
- Rollback at the orchestrator: take the union of every subagent's `written:` list, restore overwritten files from the §3.1 backup folder, and delete files that were fresh writes (per the §3.1 in-memory new-files list).
- Backup folder is preserved for inspection.

## What subagents must NOT do

- Modify files outside their assigned `files to write` list.
- Read or modify files belonging to another subagent (the orchestrator enumerates the boundary explicitly).
- Touch the backup folder.
- Run `git` commands.
- Print prose / narrative output to the user — only the structured response above. The orchestrator filters and re-renders all user-facing output.
- Spawn further subagents.

## Atomicity — what stays in the orchestrator

Orchestrator-only responsibilities (subagents do not participate):
- Step 1 analysis (sequential)
- Step 2 user confirmation
- §3.1 backup folder creation
- §3.4 aggregation table + `.claude/shared/tests/README.md` (must enumerate every written file, runs after all subagents return)
- Step 4 verification (mechanical greps, path existence, cross-reference checks)
- Step 4 rollback decision and execution
- Step 5 final report

This division keeps the setup atomic from the user's perspective: one entry point, one confirmation gate, one verification pass, one all-or-nothing rollback.
