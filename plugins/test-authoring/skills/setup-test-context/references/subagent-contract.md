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

Subagent counts by repo shape (**Slim default: code-driven per-type subagents are NOT spawned** — their sole output `{type}-test-conventions.md` is no longer generated; writers derive per-type conventions from the nearest sibling at runtime):
- 1 supported test type (unit only): **2 subagents** — `shared-tier2`, `shared-tier3`
- 2 supported test types (unit + integration): **2 subagents** — `shared-tier2`, `shared-tier3`
- 3 supported test types (incl. component): **3 subagents** — `shared-tier2`, `shared-tier3`, `component` (component is config-driven and IS spawned — it owns more than a per-type conventions file)
- extra code-driven types: **no additional subagent** (was: + one per-type each)

## Subagent kinds

### Per-type subagent (code-driven types) — **Slim default: NOT spawned**

> Under the Slim default, code-driven per-type subagents (`unit`, `integration`, and any extra code-driven type) are **not spawned**: their sole output `{type}-test-conventions.md` is no longer generated (writers derive per-type conventions from the nearest sibling at runtime). This section documents the legacy / full-regeneration behaviour. The component-type subagent below is config-driven and IS still spawned.

Owns the Tier 3 generated conventions for one test type
(generated per `references/tier3-schemas.md`, not template-copied).

Files owned (e.g. for `type=unit`) — paths relative to repo root:
- `.claude/conventions/tests/unit-test-conventions.md`

### Component-type subagent (special case)

Same shape as a per-type subagent, but writes its three files in a fixed sequence
inside the subagent (cross-file references):
1. `.claude/conventions/tests/component-test-conventions.md` first
2. `.claude/conventions/tests/fixture-capabilities.md` (only if a fixture class was detected in Step 1)
3. `.claude/rules/tests/test-component-rules.md`

Cross-type parallelism with other subagents is unaffected.

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
3. **Subagent kind** — one of `per-type`, `shared-tier2`, `shared-tier3`. The component subagent (§ Component-type subagent) is dispatched as `per-type` with test type label `component` (item 4); its three-file, fixed-sequence behaviour is driven by that section plus the explicit Files-to-write list (item 8), not by a distinct kind value.
4. **Test type label + authoring model** (per-type only) — e.g. `unit`, `integration`, `component`;
   `code-driven` or `config-driven`. The user-confirmed values from Step 2.1.
5. **Per-file decision flags** — from Step 2.2: which targets to overwrite (pristine and user-modified alike — user-modified files are backed up by the orchestrator in §3.1 before subagents spawn), and which legacy targets the user chose to keep.
6. **Analysis slice** — only the parts of Step 1 output relevant to this subagent. Examples by kind:
   - per-type: language, frameworks, mocking library, src/test dirs and globs, conventions for THIS type (from §1.4 sampling), build/test commands for THIS type's projects (from §1.5), source mapping for this type, internal package paths (from §1.2.1).
   - shared-tier2: language (drives fragment dispatch per `references/placeholders.md` § Language fragments), universal rule set inputs (verifier expectations, fix protocol settings), full build/test commands across all test projects (for `test-rules.md`).
   - shared-tier3: project structure (§1.3), shared test project info if any, cross-layer verification patterns (§1.4 global), architectural patterns (§1.6).
7. **Pre-resolved standard placeholders** — `{{LANGUAGE}}`, `{{PROJECT_DESCRIPTION}}`, `{{SRC_DIR}}`, `{{TEST_DIR}}`, `{{SRC_GLOB}}`, `{{TEST_GLOB}}`, `{{TEST_TYPE}}`, `{{TEST_TYPE_TITLE}}`, and `{{CONVENTIONS_SCHEMA_VERSION}}` (from `template-schema-versions.json` field `conventions`). The orchestrator has already computed these.
8. **Files to write** — explicit list of absolute target paths under `.claude/{conventions,rules,shared}/tests/`.
9. **Files NOT to touch** — explicit list of paths owned by other subagents (defensive boundary).
10. **References to consult** — paths to:
    - `references/placeholders.md` (plugin-side fill rules + Language fragments § dispatch documentation)
    - `references/tier3-schemas.md` (Tier 3 generation schemas)
    - **Pre-resolved language fragment files for the detected language**, absolute paths. The orchestrator derives the fragment directory name from `{{LANGUAGE}}` via the rule in `references/placeholders.md` § Language fragments, then probes `<plugin-root>/resources/templates/lang/<derived>/` on the filesystem. Only the fragments relevant to this subagent's owned templates are resolved. Examples (assuming the directory exists):
      - shared-tier2 receives: `<plugin-root>/resources/templates/lang/<derived>/project-wide-rules.md`, `<plugin-root>/resources/templates/lang/<derived>/visibility-note.md`, `<plugin-root>/resources/templates/lang/<derived>/known-packages-naming.md`
      - component subagent receives: `<plugin-root>/resources/templates/lang/<derived>/component-build-commands.md`
      - per-type subagents (unit, integration): no language fragments today — Tier 3 conventions are sampler-driven from siblings.
    If the derived directory does not exist, OR a specific fragment file is missing from a directory that does exist, the orchestrator passes the literal sentinel `"(no fragment available for <lang>; rely on Step 1 analysis only)"` in place of that path. The sentinel signals to the subagent: no baseline available, generate the placeholder content from Step 1 analysis observations only.

    Subagents read these for fill rules, generation schemas, and language-specific baselines; do not duplicate the schemas in the prompt.

### Boundary condition (note, do not design around)

Inline handoff scales fine for typical repos — per-type analysis slice is a few KB to ~10 KB. It would start to strain prompt budgets only on outlier repos: §1.2.1 internal-package tables with 50+ entries, or unusually deep §1.4 sampling output across many test projects. If that materializes, revisit by spilling the largest sections to a file under the backup folder; do not pre-build that path.

## Output contract (returned by the subagent in its final message)

The subagent returns a structured response.
Format MUST be parseable by the orchestrator without re-reading file content —
in particular, the manifest (SKILL.md §3.5) is built directly from these payloads,
so every `written` entry carries the hash and category inline.

```
written:
  - path: <absolute file path>
    sha256: <lowercase hex digest of the written content, line endings normalised CRLF→LF before hashing — see manifest.md § SHA-256 calculation>
    category: <conventions | rules | shared>
skipped:
  - <absolute file path> — <reason, e.g. "no shared test project detected", "legacy keep, per Step 2 decision">
errors:
  - <absolute file path> — <single-line error message>
```

Rules:
- `written` lists every file actually written, each entry with `path`, `sha256`, and `category` — all three mandatory. Empty list ⇒ subagent did nothing (must also be reflected in `errors` or `skipped`).
- `skipped` is for files the subagent did not generate: conditional files whose condition was unmet (per `tier3-schemas.md`), and legacy targets the user chose to keep in the decision flags. Skips are not failures.
- `errors` is empty on success. Any non-empty `errors` list signals failure for this subagent.
- One terse entry per file. The orchestrator aggregates and renders the user-facing table; do not emit prose summaries, narrative text, or repeated content.

## Failure protocol

- **Subagent does not delete files on its own failure.** It writes what it can, populates `errors`, and stops.
- **Orchestrator waits for ALL spawned subagents to return** before deciding success/failure. There is no mid-flight cancellation — subagents already in flight run to completion.
- If any subagent returns a non-empty `errors` list, the orchestrator skips §3.4 (README) and §3.5 (manifest) and goes straight to rollback.
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
- §3.5 `.claude/shared/tests/.setup-manifest.json` (built from aggregated subagent payloads)
- Step 4 verification (mechanical greps, path existence, cross-reference checks)
- Step 4 rollback decision and execution
- Step 5 final report

This division keeps the setup atomic from the user's perspective: one entry point, one confirmation gate, one verification pass, one all-or-nothing rollback.
