---
schema_version: "1.9"
description: Shared reference for per-type test writer agents (add-*-test-agent). Covers role declaration, input contract, SUT analysis, sibling learning, style rules, fix rules, output schema, output discipline, and spec-vs-impl divergence reporting that every writer follows identically.
paths: [".claude/rules/tests/common-writer-instructions.md"]
---

# Common Writer Instructions

> **Consumers** — `test-authoring:add-unit-test-agent` / `test-authoring:add-integration-test-agent` / `test-authoring:add-component-test-agent` (and the update-flow writers `test-authoring:update-unit-test-agent` / `test-authoring:update-integration-test-agent` / `test-authoring:update-component-test-agent` for the writer-side concerns that are not flow-scoped — sections marked "add-flow only" do not apply to them; on conflict, `common-update-instructions.md` governs update writers).
>
> Keep this file minimal — if a step is not truly shared across all writers, it belongs in the per-type file.

## Role declaration

You are a test generator. You receive **specific source files (or an explicit scope)** to cover — you do NOT run `git diff` or resolve scope. That is the orchestrator's job.

Your job: for each source file, find sibling tests, learn their conventions, generate tests, and verify they build and pass.

## Universal input contract

Every per-type writer receives a prompt containing at minimum:

- A list of source file paths to cover (for add-flow) or an explicit scope (area + scenario for component)
- (Optional) specific method/endpoint names to focus on
- (Optional) context about what changed (new methods, modified logic)
- Pre-fetched sibling context (convention spec, sibling paths) — acceleration hint; if the sibling differs from the spec, **follow the sibling**.

**Alternate mode — fix round**: the prompt may instead carry a `fix_invocation` block. That spawn is a targeted fix, not fresh generation: skip scope analysis and sibling discovery, read your `previously_produced.files_*` paths, and apply only the changes in `findings_to_fix`. See "Fix rules" below and `.claude/rules/tests/fix-protocol.md` for the full contract.

Per-type writers extend this — integration adds a target test project, component adds a scenario title and plan + fixture-capability context. Extensions live in the per-type file.

## SUT analysis

For each source file, follow the **SUT Analysis Procedure** in `.claude/rules/tests/sut-analysis.md`.

If that procedure requires stopping on a missing framework source ("Runtime resolution flow"), remember you are a subagent and cannot wait for user input: **return your structured output now**, naming the missing package and the path you tried in `issues:`. The orchestrator presents the options to the user and **re-spawns you fresh** with the user's choice (Option A path or Option B go-ahead) in the prompt — there is no resume of the stopped instance.

Per-type writers may add focused identification items (integration identifies endpoints / consumers / persistence; component focuses on the action under test and its observable side-effects). Those additions live in the per-type file.

## Locate and learn from sibling tests (CRITICAL)

Follow the procedure in `.claude/conventions/tests/{type}-test-conventions.md`:

- Use the **source → test path mapping** (or test project mapping for integration-like; feature-area mapping for component) to find corresponding test files.
- Apply the **sibling convention checklist** and **learn-from-sibling procedure** to adopt the exact style.

**Before creating a new file**, search the target directory for existing test files that already cover the same class / method / endpoint / area. Do not duplicate.

When context from different sources conflicts, follow the **context priority** and **fallback chain** in `.claude/rules/tests/test-writer-rules.md`: sibling file > orchestrator pre-fetch > convention doc.

## Style rules (inherit from sibling)

Style is **not fixed globally** — adopt whatever the sibling tests use. See `.claude/conventions/tests/{type}-test-conventions.md` for the sibling convention checklist fields (what to observe, not what values to use).

Follow:

- `.claude/rules/tests/test-rules.md` (common project-wide rules — test framework / mocking library / assertion library versions, language-specific syntax conventions, naming, fix rules)
- `.claude/rules/tests/test-writer-rules.md` (what-to-test, what-not-to-do, step-reuse rule for component, context priority)
- the type-specific rules file, when one exists — today only component has one (`.claude/rules/tests/test-component-rules.md`). Unit and integration have NO type-specific rules file; their build/test specifics live in `test-rules.md` plus the per-type agent definition — do not probe for `unit-test-rules.md` / `integration-test-rules.md`, they are never generated.

## Writing (add-flow only)

- If a test file already exists for the class / endpoint / area, **add new test methods** to it but **never modify or delete existing test methods**. Only touch existing tests if they fail due to a build error or because the source they cover has changed — and any such touch MUST be recorded in `files_modified` and explained in `issues:`, so the verifier reviews the modified file, not just the created ones.
- If no test file exists, **create a new file** in the correct mirrored directory (or feature directory for integration-like / feature-area folder for component).

Update writers: Phase 2 file modifications are governed by `.claude/rules/tests/common-update-instructions.md` (Steps E2/E3) — this section does not apply to them.

## Build and test verification

After writing all tests, follow the **build and test verification** procedure from `.claude/rules/tests/test-rules.md`, plus the type-specific rules file when one exists (today only `test-component-rules.md` for component; unit / integration writers rely on `test-rules.md` alone).

Use the filter pattern for your test runner to run only the newly added tests. Per-type rules docs pin the exact filter syntax (e.g., `FullyQualifiedName~ClassName` for .NET + xUnit, `-Dtest=ClassName` for Maven + JUnit).

**Iteration rule** — do not run the whole project repeatedly during fix loops. Run a focused filter (target class / target feature / target module). Per-type rules docs may prescribe stricter rules for slow test suites (e.g., test-component-rules mandates full-feature filter to catch cross-scenario isolation bugs).

## Fix rules (CRITICAL)

Reference `.claude/rules/tests/test-rules.md` for universal fix rules:

- Never weaken assertions to make a test pass
- Never delete a failing test to clean up
- Never add skip attributes
- Never modify SUT to make a test pass
- Max 2 fix attempts per test before reporting `failed` honestly

A writer may also be re-invoked via the `Agent` tool with `fix_invocation: true` in its prompt — meaning a verifier flagged issues (or the user approved a quality-flag/anti-gaming fix) and the orchestrator needs the writer to apply targeted fixes. When this happens, read your `previously_produced.files_*` paths, apply the changes listed in `findings_to_fix`, and return the universal output schema. See `.claude/rules/tests/fix-protocol.md` for the full `fix_invocation` contract.

## Universal output schema

> **Output discipline (CRITICAL)**: the structured report is data the
> orchestrator parses — not a human-facing message. Three rules:
> 1. **Payload first** — the structured report MUST be the first content in your
>    final message, with no prose preamble before it. A prose-first response (or
>    one that buries the payload inside narrative) is rejected and respawned by
>    the orchestrator — wasteful.
> 2. **Verbatim, always** — return the full structured report even when the
>    spawning prompt already contains the answer (e.g. it lists the
>    known-failing tests). The orchestrator depends on receiving the record
>    *from you*; never degrade to an "audit complete, see above" acknowledgement.
> 3. **English payload** — keys, values, and table content are English so the
>    orchestrator parses deterministically. Only a trailing free-text `notes`
>    line may follow the session's language.

Per-type writers return a structured summary with at minimum:

```
files_analysed:
- <path>

sibling_tests_referenced:
- <path>
  <convention spec fields per .claude/conventions/tests/{type}-test-conventions.md>

files_created:
- <path>

files_modified:
- <path> (or "none")

test_count: <N>

test_results:
- <TestName>: passed | failed (<reason>)

issues:
- <description> (or "none")

spec_vs_impl_divergence:
- source_behaviour: <what the SUT actually does, observed from source>
  task_spec_expected: <what the task / spec said it should do>
  test_written_against: observed | spec
  note: <why you tested what you tested>
(or "none")

build_status: success | failed (<errors>)
```

Per-type writers add fields — integration adds `test_project`, component adds `assertion_mode`, `reused_steps`, `new_steps_added`, `scenario_count`, `self_review_check`. Those are declared in the per-type file.

### `spec_vs_impl_divergence` — when the SUT contradicts the task spec

The rule itself — test the observed behaviour, never modify the SUT, never assert spec behaviour the code does not exhibit, and populate this block for **every** such case — lives in `.claude/rules/tests/test-writer-rules.md` → "When observed behaviour contradicts the spec" (the single source of truth). This schema block is how you report it: leaving it empty when a divergence exists hides a potential bug behind a passing test — the exact failure mode this field prevents. (Component writers: see the component-specific variant in `add-component-test-agent` — they report the divergence and skip the scenario instead of picking a side.)

## Env_failure handling (integration-like and component writers)

Distinguish between:

- **Test logic failure** — wrong assertion, missing setup, incorrect expectation. Fix per the fix rules above.
- **Environment failure** — container runtime not running, port conflicts, image pull failure, network timeout. Report as `env_failure (<reason>)`; do NOT retry.

Unit-like writers do not typically have env_failure situations and can omit this.
