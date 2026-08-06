---
schema_version: "1.5"
description: Shared reference for per-type update writer agents (update-*-test-agent). Covers the two-phase fresh-spawn pattern, audit flow, output discipline, Phase 2 fresh-spawn invocation contract, and git-based rollback coordination (including the source-change advisory) that every update writer follows identically.
paths: [".claude/rules/tests/common-update-instructions.md"]
---

# Common Update Instructions

> **Consumers** — `test-authoring:update-unit-test-agent` / `test-authoring:update-integration-test-agent`. Each per-type update writer references this file and adds type-specific audit / execute pieces inline.
>
> Universal writer concerns (SUT analysis, sibling learning, fix rules, style rules) live in `.claude/rules/tests/common-writer-instructions.md` — update writers reference both.

## Two-phase fresh-spawn pattern

Update writers run in **two phases**, each as a separate fresh-spawn invocation by the orchestrator:

1. **Phase 1 — Audit**: read-only analysis of existing tests; return a structured audit result, then terminate. The orchestrator derives an action plan from your audit (by status) and spawns Phase 2 — there is no user-confirmation gate.
2. **Phase 2 — Execute**: a **fresh-spawn** invocation by the orchestrator with `phase: execute` in the prompt and the action record derived from the audit. You re-read source / test files using the paths the orchestrator passes back; you do NOT continue from a live Phase 1 instance.

> **CRITICAL**: In Phase 1 you MUST NOT modify any files. In Phase 2 you MUST only apply changes explicitly listed in the action record (each justified by its audit status), and you MUST NOT touch any test classified `valid`.

### Why fresh-spawn, not continuation

Every Phase 2 invocation is a fresh `Agent` spawn — there is no continuation of a live Phase 1 instance. The orchestrator carries forward the audit record (which you returned at the end of Phase 1) plus the planned actions (derived from the audit) in the `phase: execute` prompt; you treat the prompt as authoritative and re-read the test/source files at the listed paths before applying changes.

## Phase 2 invocation contract

The orchestrator spawns Phase 2 via the `Agent` tool with this prompt structure:

```
Agent(subagent_type="test-authoring:update-<type>-test-agent"):
  phase: execute

  original_scope:
    source_files: [...]               # same as Phase 1
    method_filter: ...                # if any
    test_type: unit | integration

  pre_fetch:
    sibling_paths: [...]              # from the Phase 1 audit (test_file + sibling_conventions)
    convention_spec: {...}            # from the Phase 1 audit's sibling_conventions

  audit_record:
    (the full structured audit result you returned at end of Phase 1 —
     includes test_audit, missing_coverage, pre_change_test_results, etc.)

  planned_actions:
    update: [...]                     # tests to update (by audit status)
    delete: [...]                     # tests to delete (audit status wrong | duplicated — outdated-major is rewritten, never deleted)
    add: []                           # add actions are delegated to add-*-test-agent, not handled here

  test_file_paths: [...]              # explicit paths to read

  consent_proceeded_files: [...]      # files Step 4.5 found untracked/dirty and proceeded on user consent — see Step E1; empty when none

  cacheless_context:                  # cacheless path ONLY — the orchestrator omits this block on the fast path
    plugin_resources_path: ...        # absolute plugin templates root; read rules/shared from <here>/{rules,shared}, per your agent's Path-resolution preamble
    build_test_command: ...           # session-detected build/test invocation (adjust --filter to the actual test class)

  instructions: |
    Read the test files at test_file_paths (verify they have not been modified
    externally since Phase 1 — see Step E1).
    Apply planned_actions only — never anything outside that list; never touch a `valid` test.
    Return the execute output contract.
```

Phase 2 input fields are everything the orchestrator captured during Phase 1 + the action record (derived from the audit). No session-state handoff is required.

## Phase 1 — Audit

### Universal input contract

You will receive a prompt containing at minimum:

- A list of source file paths to audit
- (Optional) specific method / endpoint names to focus on

Per-type writers extend this — integration adds a target test project.

### Step A1 — Understand the SUT

Follow `.claude/rules/tests/sut-analysis.md` and the pointers in `.claude/rules/tests/common-writer-instructions.md` → "SUT analysis".

### Step A2 — Locate and read existing tests

Follow the **learn from sibling tests** procedure in `.claude/conventions/tests/{type}-test-conventions.md`.

For each source file:

1. Find the corresponding test file(s).
2. **Read every test method thoroughly**. Understand what each verifies: setup, action, assertions.
3. Record the conventions using the **sibling convention checklist** from the conventions doc.

If no test file exists, report `no_existing_tests: true`.

### Step A3 — Classify each test

Compare each test against the current SUT and classify using the icons defined in `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary — never written per-repo):

- 🟩 **valid** — still aligned with current SUT behaviour
- 🟨 **outdated-minor** — needs targeted tweak (specific assertion, value, detail)
- 🟨 **outdated-major** — needs rewrite while preserving intent
- 🟥 **wrong** — logic is incorrect; rewrite required
- 🟪 **duplicated** — overlaps with another test; candidate for deletion

For each non-valid classification, describe **what specifically** is wrong / outdated / duplicated. For duplicated, reference **which other test** it overlaps with.

#### Confidence (for non-valid classifications)

- **high** — clear structural evidence (signature change, dependency removed, identical code)
- **medium** — requires behavioural analysis, review recommended
- **low** — subjective assessment, review carefully before confirming

Valid tests do not need a confidence level.

### Step A4 — Identify missing coverage

Compare the SUT's public / internal methods (or endpoints for integration-like) against the test files. List any with **no test coverage at all**. Respect the method / endpoint focus when one was given — report missing coverage only within that focus.

### Step A5 — Run existing tests

Run existing tests to record their current pass/fail state per `.claude/rules/tests/test-rules.md` — it is the only rules file that pins build/test commands.

For integration-like writers, distinguish `passed` / `failed (<reason>)` / `env_failure (<reason>)`.

### Audit output contract

Return a structured summary and terminate. The orchestrator will spawn a fresh Phase 2 invocation if the action record contains any update/delete actions. Make the audit output self-contained — Phase 2 is your only handoff and it is delivered through the orchestrator's `phase: execute` prompt.

> **Output discipline (CRITICAL)**: the audit record is data the orchestrator
> renders for the user — not a human-facing message. The same three rules as in
> `.claude/rules/tests/common-writer-instructions.md` → "Output discipline"
> apply: **payload first** (no prose preamble), **verbatim always**, **English
> payload**. "Verbatim always" matters most here: even when the spawning prompt
> already lists known-failing tests or prior findings, return the **full** audit
> record — do NOT shrink to "audit complete, see lines above". The orchestrator
> cannot render the audit table to the user from an acknowledgement, and a
> degraded second-round audit leaves the user blind to what changed.

```
mode: audit

source_file: <path>

test_file: <path> (or "none")

sibling_conventions:
  (use format from .claude/conventions/tests/{type}-test-conventions.md)

test_audit:
- method: <TestMethodName>
  status: valid | outdated-minor | outdated-major | wrong | duplicated
  confidence: high | medium | low (omit for valid)
  reason: <detailed explanation>
  overlaps_with: <other test name> (duplicated only)

missing_coverage:
- <method or endpoint or area>:
  description: <what should be tested>

pre_change_test_results:
  total: <N>
  passed: <N>
  failed: <N>
  details:
  - <TestName>: passed | failed (<reason>) | env_failure (<reason>)

issues:
- <description> (or "none")
```

Per-type writers add fields — integration adds `test_project` (singular — each audit covers one (source, project) pair), `env_failure_count`, and `env_failure` details.

## Phase 2 — Execute

You are spawned fresh via `Agent` with `phase: execute` in the prompt. The prompt carries the full audit record (your Phase 1 output), the action record (the audit-derived `planned_actions`), and the test file paths. Treat the prompt as authoritative — there is no live state from Phase 1 to inherit. Re-read source / test files from the listed paths; do not assume cached file content.

### Step E1 — Verify test file unchanged

Quickly verify the test file(s) have not been modified between Phase 1 and Phase 2. **You own this check** (the orchestrator does not re-do it):

```bash
git diff -- <test_file_path>
```

- For files the orchestrator's Step 4.5 confirmed **tracked and clean**, any non-empty diff means external modification — **stop and report** the discrepancy rather than proceed with stale context.
- For files listed in `consent_proceeded_files` (untracked/dirty at Step 4.5, proceeded on explicit user consent), a non-empty diff is **expected** and is NOT a stop signal — instead spot-check that the methods named in the audit record still exist in the file before applying changes.

### Step E2 — Apply confirmed changes (in order)

#### Update — outdated-minor

1. Locate the test method (already read in Phase 1).
2. Make **targeted changes only** — specific assertions, values, details.
3. Do NOT rewrite the entire method. Preserve existing structure.
4. Keep the test method name.

#### Update — outdated-major or wrong

1. Locate the test method.
2. Understand the original intent.
3. Rewrite to correctly reflect current SUT logic while preserving **intent**.
4. Follow sibling conventions exactly.
5. Keep the test method name unless a rename is necessary for accuracy.

#### Delete (duplicated tests)

1. Remove the test method.
2. If it was the only user of a private helper or field, remove that helper/field too.
3. Record the exact method signature that was deleted.

### Step E3 — CRITICAL constraints

- **ONLY** process items in the action record (each justified by its audit status); the consequential cleanup in E2 — removing a private helper or field whose only user was a deleted test — counts as part of that delete action, not as an out-of-record change
- **NEVER** modify or delete a test not in the action record
- **NEVER** touch a test with `audit_status: valid` and `action: none`
- **NEVER** process `action: add` items — those are handled by the corresponding `test-authoring:add-<type>-test-agent`

All other fix rules are defined in `.claude/rules/tests/test-rules.md`.

### Step E4 — Build and test verification

After applying all changes, follow the build and test verification procedure from `.claude/rules/tests/test-rules.md`.

### Execute output contract

```
mode: execute

source_file: <path>

test_file: <path>

changes_applied:
- method: <TestMethodName>
  action: updated | deleted
  result: passed | failed (<reason>) | env_failure (<reason>)
  notes: <brief description of what changed>

tests_updated: <N>
tests_deleted: <N>

deleted_tests_record:
- method: <exact method signature>
  audit_status: <status from the action record — must be wrong | duplicated>

build_status: success | failed (<errors>)

test_results:
- <TestName>: passed | failed (<reason>) | env_failure (<reason>)

fix_rounds: <N>

issues:
- <description> (or "none")
```

Per-type writers add fields — integration adds `env_failure` details.

## Git-based rollback coordination

There are no `.bak` files — git is the backup. The orchestrator's Step 4.5 confirms each test file is tracked and clean before Phase 2 (warning and asking if it is untracked or dirty), so `git show HEAD:<file>` is the faithful pre-change baseline and `git restore <file>` is the rollback. The update writer does NOT manage backups — just apply the changes and let the orchestrator handle the git safety check and any rollback per the `update-<type>-test` skill's Step 4.5 and Step 7 (rollback on failure).

> **Source-change advisory.** A common update trigger is "the source changed,
> so the test now asserts stale behaviour". If your Step A1 / A5 analysis shows
> the staleness was caused by an **uncommitted** source change (e.g. `git diff`
> shows modified source the tests cover), note it in the audit `issues` so the
> orchestrator can surface it in its audit summary. Execution proceeds without
> a gate, but the surfaced advisory lets the user interrupt and **commit or
> stash the source change** — keeping a single coherent git baseline, so if
> Phase 2 verification fails, `git restore` returns both source and tests to a
> consistent state.

When Phase 2 produces a failing build or a failing test updated by this agent, the verifier (`test-authoring:verify-update-<type>-test-agent`) will flag it and the orchestrator will offer rollback to the user. You do NOT attempt to recover — report honestly.
