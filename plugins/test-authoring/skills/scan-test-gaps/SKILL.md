---
name: scan-test-gaps
description: >
  Scan pending changes (or a given scope) for untested areas and stale tests, prioritise gaps, and iteratively delegate test generation/updates. Trigger phrases: "find test gaps", "which classes lack tests", "scan for untested code", "check coverage holes". Do NOT trigger for: questions about why a specific test failed, coverage tool configuration, or general TDD discussions.
---


## Step -1 — Resolve where the rule books and conventions come from

This skill runs **with or without** a prior `setup-test-context`.

**Resolve the plugin templates root once, unconditionally** — you also pass it to every subagent you delegate to (add / update writers and their verifiers), because subagents cannot resolve it themselves. The bundled rule books sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`), run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool; if `$CLAUDE_SKILL_DIR` is empty too, ask the user for the `test-authoring` plugin install path. The Read tool normalises the `../..` segments.

**If it still cannot be resolved, degrade — loudly — rather than stopping.** The sibling-learning path does not depend on the plugin, so tests can still be written; what is lost is the rule books, and that loss must be visible rather than silent. Print this **as prose in your reply**, not merely as reasoning, so it lands in the transcript and the dashboard:

```
⚠ Rule books unreachable — running in DEGRADED mode.
  Could not resolve the test-authoring plugin path, so the shared rule books are not
  loaded: fix rules, the verifier's check sequence, the fix protocol, SUT analysis.
  Tests will still be written from the nearest sibling, but the anti-gaming guardrails
  and the full independent-verifier sequence are NOT in force. Review the output
  yourself, and re-run once the plugin path resolves.
```

Then carry on, and pass every subagent a `fallback_rules` block **in place of** `plugin_resources_path`, carrying the non-negotiable core inline:

```
fallback_rules: |
  - **NEVER** weaken an assertion to make a test pass
  - **NEVER** delete a test case that fails — fix the root cause or report it as failed
  - **NEVER** add skip/ignore attributes or comment out a test to bypass a failure
  - **NEVER** change the SUT (source code) to make tests pass
  - If a test fails after **2 fix attempts**, report it as `failed` — do not keep weakening it
  - The nearest sibling test is the only convention source. Where none exists, report the gap
    and write nothing — never infer conventions from what the language usually does.
```

Degraded mode is for an **environment** failure only. It is not licence to omit `plugin_resources_path` when you did resolve it: a subagent that receives neither field stops, and that stop is a caller bug.

Two kinds of file, resolved differently:

- **Rule books.** Every `<PLUGIN_TEMPLATES>/rules/…` and `<PLUGIN_TEMPLATES>/shared/…` path below is literal — read it from there. Inside a rule book, a bare filename means a sibling rule book in that same `rules/` directory, and a `../shared/<f>` path is relative to it. Nothing writes any of them into a repo, so there is no per-repo copy to prefer and none to fall out of date. Read each lazily, at the step that uses it — never as an upfront batch (see "Orchestrator reading list").
- **Conventions.** `.claude/conventions/tests/…` is the repo's own cache, written only where `setup-test-context` has run. Treat every one as **optional**: derive source/test layout and conventions from the repo structure + nearest sibling tests; the delegated writers and verifiers prefer siblings too. A missing conventions file is never fatal.

If `.claude/conventions/tests/project-architecture.md` is absent, say so once: `"No cached repo profile — deriving from siblings. Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then carry on — it blocks nothing.

**Detect once, reuse this session**: the language, and the *executable* build/test invocation **form** (test-project path + filter syntax). `test-rules.md` carries no command list — the detected form is the only source: it drives this skill's own quick build (Step 4, "Stale test detection") and is passed to every delegated agent as `build_test_command`. For integration spanning several test projects, instantiate the form per target test project (Step 7); subagents adjust its `--filter`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`, then `.claude/conventions/tests/project-architecture.md` — the "Placeholder resolution" note below needs it before Step 1 (absent: per-invocation detection per that note, no read).
- **At the step that uses it**: Step 1 → `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`. Steps 2–3 reuse `project-architecture.md` (already loaded). The "Stale test detection" quick build → `<PLUGIN_TEMPLATES>/rules/test-rules.md` (use the session-detected `build_test_command`). Delegation and update segments, on demand → `<PLUGIN_TEMPLATES>/rules/common-update-instructions.md` (orchestrator-facing sections only), `<PLUGIN_TEMPLATES>/rules/fix-protocol.md` (first verifier finding or attributable build failure).
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`. They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


## Step 1.5 — Inferred scope echo (informational, no block)

Immediately after Step 1 resolves the scope, print it to chat for transparency:

```
Scanning: <resolved scope>
Mode: <Mode A (git diff) | Mode B (explicit argument)>
Test types inferred: <e.g. unit, integration> — say if this is wrong
```

The inferred-types line is not decoration: the count drives the single-type vs multi-type shape of the whole report, nothing else confirms it, and this echo is the only place you can correct it.

scan-test-gaps does NOT block here — its existing Step 6 ("Ask User What to Implement") is the user's explicit-consent gate before any test writing.


# Scan Test Gaps

You are a test coverage analyst for {{PROJECT_DESCRIPTION}}. Your job is to find untested code and stale tests, prioritise the gaps, and delegate test generation/updates to subagents.

> **Placeholder resolution (plugin-bundled file)**: tokens like `{{PROJECT_DESCRIPTION}}`, `{{TEST_TYPES_LIST}}`, `{{LANGUAGE_EXCLUSIONS}}`, `{{COVERAGE_EXCLUSION_HANDLING}}`, `{{HIGH_PRIORITY_CRITERIA}}`, `{{TEST_TYPES_COUNT_BREAKDOWN}}` are NOT pre-filled — this file ships with the plugin, not generated per-repo. Resolve them at runtime: project description and language from `.claude/conventions/tests/project-architecture.md`, supported test types inferred from the filesystem per the note below, exclusions and priority criteria derived from the detected language and repo conventions. Never render a `{{...}}` token literally in user-facing output.
>
> **Inferring the test types (always):** resolve `{{PROJECT_DESCRIPTION}}` and language from `project-architecture.md` when a prior setup cached it, and from per-invocation detection (project manifest + file extensions) when it did not — never render the token literally. The plugin records no confirmed type list between runs, so **infer the supported test types from the filesystem every time** — unit-like (mirrors source, mocks deps) and/or integration-like (HTTP/DB/container fixtures). **A test project containing `.feature` / Gherkin files (or Gherkin-binding step classes) is not a supported target — exclude it from the inferred types even though it uses containers/fixtures** (do NOT count it as integration-like). Use the inferred count to drive the SINGLE_TYPE_ONLY vs MULTI_TYPE_ONLY behaviour below, and **echo the inferred types in the Step 1.5 scope echo** so the user can correct them. Exclusions and priority criteria come from the detected language + nearest siblings.

> Every `<PLUGIN_TEMPLATES>/…` and `.claude/conventions/tests/…` read below follows **Step -1's resolution** — and happens lazily, at the step that uses it, never as an upfront batch; a body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. Pass `plugin_resources_path` and `build_test_command` (per target test project for integration) into **every** subagent you delegate to — add / update writers and their verifiers — they cannot resolve these themselves. The `<plugin-root>/resources/static/status-legend.md` reference (Step 8) resolves to `<PLUGIN_TEMPLATES>/../static/status-legend.md` (Step -1); If `PLUGIN_TEMPLATES` was never resolved (Step -1's degraded mode), use plain text status labels.

## Scope: unit and integration tests only

This skill analyses **unit and integration test gaps only**. Both are code-driven with clear class/endpoint-to-test-file boundaries, so class-level gap detection is reliable.

**Not analysed:**

- **Gherkin scenario tests** (`.feature` files and their step classes). They map by feature area, not by source class, and an N:M mapping between source classes and scenarios cannot be resolved reliably from code alone. Scan does not read `.feature` files, does not count scenarios as cross-coverage, and does not list them as a gap type. **This plugin does not author Gherkin scenarios at all** — if the user asks for one, say so plainly rather than routing them to another skill.
- **Config-driven or otherwise non-code test projects** — out of scope by construction: this skill authors only code-driven unit and integration tests.

## Step 1 — Identify Scope

Follow the procedure in `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`.

- **Mode A** (no argument): Use git diff to find modified/added source files. Scope the scan to only those files and their corresponding tests.
- **Mode B** (argument provided, e.g., `/test-authoring:scan-test-gaps ComponentName`): Resolve by directory, component, class, method, or file name.

## Step 2 — Inventory Source Files

Reference `.claude/conventions/tests/project-architecture.md` for source directory layout.

Collect production source files within the resolved scope. Exclude:
{{LANGUAGE_EXCLUSIONS}}
<!-- Resolve at runtime from the detected language, e.g.:
  C#: `migrations/`, `obj/`, `bin/`, `Properties/`, auto-generated (`*.Designer.cs`, `*.g.cs`, `GlobalUsings.cs`), `Program.cs`/`Startup.cs` unless logic
  TypeScript: `node_modules/`, `dist/`, `.next/`, `*.d.ts`, generated code
  Python: `__pycache__/`, `venv/`, `build/`, `__init__.py` without logic
  Go: `vendor/`, generated files (`*_gen.go`)
-->

### Coverage-exclusion markers

{{COVERAGE_EXCLUSION_HANDLING}}
<!-- For repos with coverage exclusion markers (e.g., `[ExcludeFromCodeCoverage]` in .NET, `/* istanbul ignore */` in JS), describe how to detect and list them in a separate Excluded table:

When a class/method is decorated with the exclusion marker, **do not analyse it for gaps**. Instead, track it in a separate **Excluded** table at the end of Step 5 with method-level detail.
-->

## Step 3 — Inventory Existing Tests

Reference `.claude/conventions/tests/project-architecture.md` for test directory layout.

Scan ALL test files across the confirmed test projects. Do NOT pre-filter by keyword — a helper or dependency class may be tested in a differently-named directory. Mode A narrows the **source** scope only — the test inventory stays global, because cross-coverage may live in any test file.

For each test file, identify which source class(es) it covers by:
- Matching the test class name
- Reading the file to see which SUT is constructed or which endpoint is called
- Cross-referencing imports / using statements and class references

**Do not scan `.feature` files or Gherkin step classes.** They are out of scope — see the "Scope" notice at the top.

## Step 4 — Identify Gaps

**First, read the answer Step 3 already gave you.** If its global inventory found no test file at all, every gap below has one cause and one remedy, and fanning out a writer per gap buys nothing — each would walk its own Fallback Chain and stop for the same repo-level reason. Take the bootstrap path once for the whole batch instead, per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Writer stop on no convention source", and skip Steps 5 to 7.5.
A partial inventory is not this case: with even one test file the chain may reach it, so scan and fan out as normal.

Cross-reference source files against test files to find gaps. **Be thorough** — do not just match by file name. A class may be tested inside a combined test file.

<!-- MULTI_TYPE_ONLY: keep if ≥2 supported test types -->
### Gaps per test type

List gaps grouped by inferred test type ({{TEST_TYPES_LIST}}):
- Source classes with **no corresponding test file** and not tested elsewhere
- Source classes with a test file but **missing coverage for public methods/endpoints**

> **Runtime rule:** when resolving `{{TEST_TYPES_LIST}}`, exclude any Gherkin scenario project even if the repo has one. Its gaps are intentionally not produced by this skill — see the "Scope" notice at the top.
<!-- END MULTI_TYPE_ONLY -->

<!-- SINGLE_TYPE_ONLY: keep if exactly 1 supported test type -->
### Gap list

List gaps of two kinds:
- Source classes with **no corresponding test file** and not tested elsewhere
- Source classes with a test file but **missing coverage for public methods/endpoints**
<!-- END SINGLE_TYPE_ONLY -->

### Stale test detection

For source classes that **have existing tests**, check if the tests may be outdated:
- Source signatures changed but test references the old signature
- Test file has build errors
- Test has failing assertions

Do not deeply audit every test method — that is `update-*-test-agent`'s job. Only flag classes where there are **clear signals** of staleness. Build errors and failing assertions are only knowable from a build — do a quick build of the affected test projects (and a focused run where cheap) rather than guessing from code alone (use the session-detected `build_test_command`); the full audit stays the update agent's job. List these with Type = `Update` in the gap tables.

<!-- MULTI_TYPE_ONLY: keep if ≥2 supported test types -->
### Cross-coverage exclusion

Before listing a method as a gap, check whether it is already exercised by **unit or integration tests** (directly or indirectly). Gherkin scenarios are not considered here — see the "Scope" notice at the top. A method counts as covered if:

- It has a **direct test**
- It is **directly exercised by a higher-level test** (e.g., integration endpoint test triggers the handler)
- It is **indirectly but reliably exercised** by a higher-level test that asserts on the outcome

**Exclusion rules:**

1. **Fully covered by other test type** — all public methods are exercised → do NOT list the class.
2. **Partially covered** — some methods exercised, others not → list ONLY the uncovered methods.
3. **No tests at all** — list as a gap.

When in doubt, err on the side of **excluding** — a false negative is less costly than a false positive.
<!-- END MULTI_TYPE_ONLY -->

<!-- SINGLE_TYPE_ONLY: keep if exactly 1 supported test type -->
### Coverage exclusion

Before listing a method as a gap, check whether it is already exercised by **any existing test** (directly or indirectly). A method counts as covered if:

- It has a **direct test** targeting it
- It is **indirectly but reliably exercised** by another test that asserts on the outcome (e.g., a test for a higher-level class that triggers this method and asserts the result)

**Exclusion rules:**

1. **Fully covered** — all public methods are exercised → do NOT list the class.
2. **Partially covered** — some methods exercised, others not → list ONLY the uncovered methods.
3. **No tests at all** — list as a gap.

When in doubt, err on the side of **excluding** — a false negative is less costly than a false positive.
<!-- END SINGLE_TYPE_ONLY -->

## Step 5 — Prioritise and Present Summary

Assign priority based on:

| Priority | Criteria |
|---|---|
| **High** | {{HIGH_PRIORITY_CRITERIA}} |
| **Medium** | Supporting services, validation logic, data transformations |
| **Low** | Utilities, extensions, configuration, simple CRUD with no business rules |

<!-- Resolve HIGH_PRIORITY_CRITERIA at runtime from the repo's domain, e.g.:
  Billing: "Business-critical logic: command handlers, billing calculations, state transitions, financial operations, sync consumers"
  Auth service: "Token handling, permission checks, session lifecycle"
  Data pipeline: "Transformation logic, error recovery, exactly-once guarantees"
-->

Present results in **three tables** — one per priority level. Each table uses the same columns. Each row has a **sequential number (#)** across all tables.

### Table format

<!-- MULTI_TYPE_ONLY: keep if ≥2 supported test types -->
| # | Source/Class | Method/Endpoint | Gap Description | Type |
|---|---|---|---|---|
| 1 | `<Class>` | `<method>` | No tests at all | {{EXAMPLE_TYPE_1}} |
| 2 | `<Class>` | `<endpoint>` | No test of this type | {{EXAMPLE_TYPE_2}} |
| 3 | `<Class>` | (class) | Tests have build errors | Update |

**Column definitions (initial scan):**
- **#**: sequential item number
- **Source/Class**: source class name (short, without full path)
- **Method/Endpoint**: method name or endpoint route
- **Gap Description**: what is missing
- **Type**: one of the confirmed test types, or `Update`
<!-- END MULTI_TYPE_ONLY -->

<!-- SINGLE_TYPE_ONLY: keep if exactly 1 supported test type -->
| # | Source/Class | Method/Endpoint | Gap Description |
|---|---|---|---|
| 1 | `<Class>` | `<method>` | No tests at all |
| 2 | `<Class>` | (class) | Tests have build errors (`Update`) |

**Column definitions (initial scan):**
- **#**: sequential item number
- **Source/Class**: source class name (short, without full path)
- **Method/Endpoint**: method name or endpoint route
- **Gap Description**: what is missing; annotate stale-test items with `(Update)`
<!-- END SINGLE_TYPE_ONLY -->

Include a brief count summary:

<!-- MULTI_TYPE_ONLY: keep if ≥2 supported test types -->
```
Total items: X — High: N, Medium: N, Low: N, Excluded: N
  Breakdown: {{TEST_TYPES_COUNT_BREAKDOWN}}
```
<!-- END MULTI_TYPE_ONLY -->

<!-- SINGLE_TYPE_ONLY: keep if exactly 1 supported test type -->
```
Total items: X — High: N, Medium: N, Low: N, Excluded: N
```
<!-- END SINGLE_TYPE_ONLY -->

## Step 6 — Ask User What to Implement

Ask the user which items they want to implement. Reference by number, priority, or area.

### Batch size limit

Process at most **5–8 items per batch**. If the user selects more, split into batches and confirm before starting each batch.

## Step 7 — Delegate Test Generation to Agents

Based on the user's selection, group the items by type and spawn subagents.

Before spawning the first writer of a batch, record the **pre-writer source snapshot** per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Pre-writer source snapshot" — the verifiers need it as the baseline for their SUT-modification check, and pass the pathspec you used alongside it as `source_pathspec` so they re-run the diff over the same set.

- For **add** gaps → spawn one `test-authoring:add-<type>-test-agent` per source class (per type, e.g., `test-authoring:add-unit-test-agent`, `test-authoring:add-integration-test-agent`)
- For **Update** gaps → spawn one `test-authoring:update-<type>-test-agent` per source class (per type)

For integration-like types, include the target test project in the agent prompt. If the sibling tests show a source mirrored into MULTIPLE integration test projects (e.g. API + worker), split into one (source, project) pair per writer — same rule as `add-integration-test` Step 1.5; passing only one project silently drops the other's coverage.

### Passing context to agents

When the gap analysis identified sibling test files, pass that to the agent to avoid redundant exploration. Always pass `plugin_resources_path` (= the `PLUGIN_TEMPLATES` value resolved in Step -1) and `build_test_command` (the integration project's command per (source, project) pair) into every delegated add / update writer and every Step 7.5 verifier — per the governing note; they cannot resolve these themselves.

### Parallelism

<!-- MULTI_TYPE_ONLY: keep if ≥2 supported test types -->
- The parallelism unit is the **source class × test type** — one agent per (class, type) pair.
- Methods of the same class and type must stay in the same agent.
- **Concurrency limit**: spawn at most **4 agents in parallel**. If more are needed, split into rounds.
<!-- END MULTI_TYPE_ONLY -->

<!-- SINGLE_TYPE_ONLY: keep if exactly 1 supported test type -->
- The parallelism unit is the **source class** — one agent per class.
- Methods of the same class must stay in the same agent.
- **Concurrency limit**: spawn at most **4 agents in parallel**. If more are needed, split into rounds.
<!-- END SINGLE_TYPE_ONLY -->

### Update workflow caveat

For Type = `Update` items, the Phase 1 agent performs the audit only and terminates. Present the audit findings inline within the scan results **as a single markdown table** (same rendering rules as the `update-<type>-test` skill's Step 3 — never a bullet list or separator-bar format), and surface the audit's `issues:` entries verbatim alongside — in particular the source-change advisory, per the `update-<type>-test` skill's "Audit Issues" section. Then derive the action plan from each item's audit status (no per-item confirmation gate — same as `update-*-test`). **Fresh-spawn** the Phase 2 agent via `Agent` with `phase: execute` and the audit-derived `planned_actions` (per `<PLUGIN_TEMPLATES>/rules/common-update-instructions.md` → "Phase 2 invocation contract") — do not continue a live Phase 1 instance. The Step 4.5 git safety check and audit-status-based deletion justification apply as in `update-*-test`.

## Step 7.5 — Review via Verify Agents

After all writer/update agents in the batch complete, spawn verifiers **per test type and workflow**:

- For items routed to add writers → spawn one `test-authoring:verify-add-<type>-test-agent` per type (e.g., `test-authoring:verify-add-unit-test-agent`, `test-authoring:verify-add-integration-test-agent`), passing the inputs per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Verifier spawn": all writer outputs (including `files_modified`), the original task, and the pre-writer source snapshot.
- For items routed to update writers (if Phase 2 was executed) → spawn `test-authoring:verify-update-<type>-test-agent`. **One per test *project* named in the action record, not one per type** — for `integration` a batch can span several test projects, and deriving the spawn set from what changed would leave an inert writer's project unverified, which is the failure that verifier's own claimed-action check exists to catch. Unit batches are normally one project, so per-type and per-project coincide there.

  Pass what this skill actually has: pre-change state, the action record (**scoped to that project**), the update writers' Phase 2 output **whole and one set per writer that ran** — `changes_applied` and `issues` included, since the verifier pairs those against the diff — the `git show HEAD:<file>` baseline for **every file the action record names** (not only the ones reported as modified), test type, the test project, the raw Phase 1 audit outputs, the add-writer outputs from Step 7 for any file they also touched, and the plugin context (`plugin_resources_path` + `build_test_command`, already required for every Step 7.5 verifier by the standing instruction above).

  **Two inputs that flow exists cannot supply, and saying so is the point:** `update-<type>-test` has a Step 4.5 pre-write git safety check that yields a *consent-proceeded* list and a *skipped* list; **this skill has no such gate**, so it passes neither. Tell the verifier that explicitly rather than omitting it — otherwise an absent list reads as "empty", and the difference matters: with no gate, nothing has confirmed the touched files were tracked and clean, so `git show HEAD:<file>` is an **unconfirmed** baseline here rather than the faithful one that skill's Step 4.5 guarantees. The verifier should report diff-based findings on this path as unconfirmed-baseline notes where a dirty file would explain them, and never assume the stronger guarantee it gets from the dedicated skill. **This weakens its Steps 1 and 2 only — its Step 5 is unaffected**, because every Step 5 verdict reads whether a method is present in the file now and never consults a baseline, so it runs at full strength on this path.

Spawn multiple verifiers in parallel if the batch spans multiple test types / workflows.

## Step 7.7 — Handle Verifier Findings

Follow the **Verifier Fix Protocol** in `<PLUGIN_TEMPLATES>/rules/fix-protocol.md` and the role boundary in `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`:

- **Deterministic** → fresh-spawn the respective writer (`test-authoring:add-<type>-test-agent` or `test-authoring:update-<type>-test-agent`) with a `fix_invocation` block per `fix-protocol.md`.
- **Non-deterministic** → present to user. If the user approves a fix, route via the same fresh-spawn `fix_invocation` block with `findings_to_fix.user_approved_actions` populated.
- **Update-side exception**: deletion-related verifier findings (violations in `deletion_justification`, `valid_test_protection`, or `anti_deletion_check`) bypass the circuit-breaker loop and go directly to the user **with a rollback offer** (`git restore <file>`, per the `update-<type>-test` skill's "Rollback on Failure") — never routed to a writer.

The orchestrator MUST NOT invoke `Write` / `Edit` / `MultiEdit` directly — even for "small" fixes or after user approval. All edits go through writer agents.

## Step 8 — Show Updated Summary

Present **updated versions** of the tables from Step 5 with two additional columns: **Status** and **Note**.

**Status icons:** Use the icons defined in `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary).

Only show the tables relevant to the user's selection.

Then ask the user which items to implement next, or "done" to end.

Repeat Steps 6–8 until the user says to stop or all gaps are covered.



