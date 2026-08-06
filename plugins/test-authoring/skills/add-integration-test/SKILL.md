---
name: add-integration-test
expected_schema_version: "1.0"
expected_rules_schema_version: "2.1"
description: >
  Generate integration tests for changed source files or a user-specified target (endpoint, handler, command, service). Trigger phrases: "add integration tests for X", "create endpoint test for /foo", "write integration test for HandlerY". Do NOT trigger for: discussions about test infrastructure, container setup questions, or end-to-end test strategy.
---


## Step -1 — Resolve context source (fast path vs cacheless)

This skill runs **with or without** a prior `setup-test-context`. First resolve where rules/conventions come from, then proceed.

**Resolve the plugin templates root once** — you pass it to every subagent, because subagents cannot resolve it themselves. The bundled templates sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`): on the **cacheless path** (where it is load-bearing) resolve it at runtime — run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool, and if `$CLAUDE_SKILL_DIR` is empty, ask the user for the `test-authoring` plugin install path. On the **fast path** its only use is Step 7's status icons — do **not** prompt; if it stays unresolved, fall back to plain status labels there (R4). The Read tool normalises the `../..` segments.

Then check `.claude/conventions/tests/project-architecture.md`:

- **Exists → fast path.** A prior setup cached per-repo files. Compare its `schema_version` **major** against this skill's `expected_schema_version`: same major → continue silently; major differs or key missing → warn `"Conventions schema major <found> differs from <expected>. Run /test-authoring:setup-test-context to refresh."` and continue best-effort (may-be-stale). **Resolve, do not bulk-read**: every `.claude/{conventions,rules,shared}/tests/<f>` reference below resolves to the repo file — read each file lazily, at the first step that uses it (see "Orchestrator reading list" below). **Per-file fallback still applies at read time**: any individual file that is absent falls through to the cacheless source below — a missing file is never fatal.
- **Absent → cacheless.** setup has never run. **Do NOT stop.** Announce once: `"No precomputed test conventions found — running cacheless (sibling-driven). Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then for the rest of the flow:
  - Resolve every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` reference to `<PLUGIN_TEMPLATES>/{rules,shared}/<f>` instead — same lazy rule: read at the step that uses it, never as an upfront batch. Cosmetic frontmatter/example tokens (`{{TEST_GLOB}}`, `{{SRC_DIR}}`) are inert when read explicitly — substitute the detected value.
  - Treat `.claude/conventions/tests/<f>` as **optional**: prefer the nearest sibling test for the scope (the writer's top-priority source anyway); fall back to `<PLUGIN_TEMPLATES>/lang/<derived>/` fragments for the language baseline.
  - **Detect once, reuse this session**: the language, and the *executable* build/test invocation **form** (test-project path + filter syntax, e.g. `dotnet test <proj> --filter "FullyQualifiedName~<Class>"`) from the project manifest. In cacheless mode the template `test-rules.md` carries an unfilled `{{BUILD_AND_TEST_COMMANDS}}` token whose filled form lists **one command per test project** — the detected form replaces it everywhere (writer build, verifier U4 build, this orchestrator's final build). Integration may span several test projects (Step 1.5): **instantiate the form per target test project** and pass each writer the command for ITS project as `build_test_command` (do not reuse one project's path for another).

Resolve `common-orchestrator-flow.md` the same way: fast path reads `.claude/rules/tests/common-orchestrator-flow.md` (same schema-major check against `expected_rules_schema_version`); cacheless reads `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `common-orchestrator-flow.md` (previous paragraph).
- **At the step that uses it**: Step 1 → `.claude/shared/tests/scope-resolution.md`. Step 1.5 → `.claude/conventions/tests/integration-test-conventions.md` (test project mapping; cacheless: sibling inference instead of a read). Step 2 → `.claude/conventions/tests/project-architecture.md` (reuse the conventions doc from Step 1.5). Step 4, only when it runs → `.claude/rules/tests/test-rules.md` (cacheless: skip the read — use the session-detected per-project `build_test_command`). First verifier finding or attributable build failure → `.claude/rules/tests/fix-protocol.md`. A writer stopping on missing framework source → `.claude/rules/tests/sut-analysis.md` → "Runtime resolution flow".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, and the other flow's rule book (`common-update-instructions.md`). They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Add Integration Tests for Pending Changes

You are the orchestrator for integration test generation. Your job is to **resolve scope**, **determine the target test project**, and then **delegate** actual test writing to the `test-authoring:add-integration-test-agent` subagent, then verify via `test-authoring:verify-add-integration-test-agent`. Follow the universal flow in `.claude/rules/tests/common-orchestrator-flow.md`; this file only documents integration-specific pieces.

> Every `.claude/{conventions,rules,shared}/tests/…` read below follows **Step -1's resolution**: the repo file on the fast path, or `<PLUGIN_TEMPLATES>/…` (rules/shared) plus sibling/lang-fragment (conventions) on the cacheless path — and happens lazily, at the step that uses it, never as an upfront batch. A body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. On the cacheless path you also pass `plugin_resources_path` and `build_test_command` into every subagent prompt — they cannot resolve these themselves.

## Step 1 — Identify Scope

Follow the procedure in `.claude/shared/tests/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Focus on modified API endpoints (controllers, routes), command/query handlers, worker operations or event consumers, sync consumers, and changes to persistence logic.
- **Mode B** (argument provided, e.g., `/test-authoring:add-integration-test ComponentName`): Resolve by directory, component, class, endpoint, or file name.

## Step 1.5 — Determine Test Project Mapping

Before spawning agents, determine which test project each source file maps to. Use the **test project mapping** in `.claude/conventions/tests/integration-test-conventions.md`.

**Cacheless** (the conventions doc is absent): infer the target test project from siblings — locate the existing integration test project whose tests mirror the source area (an endpoint/handler test for a nearby source file). If several integration test projects exist and none clearly mirrors the source, do not guess — state the candidates and ask the user.

If a single source change covers multiple projects (e.g., both API and worker), split the source list and spawn one agent per (source, project) pair.

## Step 2 — Pre-fetch Context

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Pre-fetch context (add-flow only)":

1. For each source file, find the corresponding test directory within the target test project using `.claude/conventions/tests/integration-test-conventions.md` and `.claude/conventions/tests/project-architecture.md`.
2. If sibling test files exist in the mapped directory, read them and extract the convention spec. Include the authorization mapping (where applicable) so the writer uses the correct account-type identity helpers. If none exist there, widen once — the nearest test files in the same target test project — and label them in the writer prompt as `nearest sibling (not exact mirror)` so the writer weighs them below an exact-mirror sibling.
3. If no siblings are found at all, omit the sibling fields from the Step 3 template and state instead: `No sibling tests found — derive conventions from .claude/conventions/tests/integration-test-conventions.md` (cacheless: that doc is absent — derive from `<PLUGIN_TEMPLATES>/lang/<derived>/` fragments instead). Never invent a sibling path to satisfy the template.
4. Pass this context to the writer.

## Step 3 — Delegate to Agent

Spawn `test-authoring:add-integration-test-agent` — one agent per (source, project) pair from Step 1.5, all in parallel. Per `.claude/rules/tests/common-orchestrator-flow.md` → "Writer delegation".

```
Agent(subagent_type="test-authoring:add-integration-test-agent"):
  Generate integration tests for:
  - <source file path>
    Changed/Cover: <methods or endpoints>
  Target test project: <path from Step 1.5>
  Pre-fetched context (acceleration hint — if sibling differs, agent follows sibling):
    Sibling test: <sibling file path>
    Convention spec observed:
      <fields per convention spec>
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build/test command for THIS writer's Target test project>
```

### Endpoint-scoped

When the user specifies an endpoint, include it in the agent prompt as "Focus only on <endpoint>".

## Step 4 — Verify Build (multi-agent only)

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Multi-agent build check" (run a final build only when multiple agents were spawned; attribute each failure to the owning writer and route it via `.claude/rules/tests/fix-protocol.md`, else report 🟥 unresolved — the orchestrator never fixes it directly), **but build each affected test project separately** — one per (source, project) split from Step 1.5, using that project's command. Cacheless: use the session-detected `build_test_command` per project, not the unfilled `{{BUILD_AND_TEST_COMMANDS}}` token.

## Step 5 — Review via Verify Agent

Spawn **one** `test-authoring:verify-add-integration-test-agent` to independently review the generated tests. Always spawn the verifier.

```
Agent(subagent_type="test-authoring:verify-add-integration-test-agent"):
  Review integration tests generated by writer agents.
  Test type: integration
  Original task: <the scope/spec as given to the writers — required by the verifier's U2b divergence cross-check>
  Pre-writer source snapshot: <the source diff state recorded before writers were spawned — baseline for the U3 SUT-modification check>
  Cacheless context (include ONLY on the cacheless path — omit on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build/test command form; for each writer under review, instantiate it for that writer's reported `test_project`>

  Writer 1 output:
  - files_created: <path>
  - files_modified: <path, or "none" — existing tests the writer touched, verbatim from the writer>
  - test_project: <path>
  - sibling_tests_referenced:
    - <sibling path>
      <convention spec>
  - test_count: <N>
  - test_results: <per-test passed | failed (<reason>) | env_failure (<reason>), verbatim from the writer>
  - spec_vs_impl_divergence: <writer's entries verbatim, or "none">
  - build_status: <success | failed (<errors>), verbatim from the writer>

  Writer 2 output:
  ...
```

Every field is filled from the writer's structured return — never assume a happy-path value the writer did not report.

## Step 6 — Handle Verifier Findings

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Role boundary" + "Fix-verify loop" and `.claude/rules/tests/fix-protocol.md`:

- **Deterministic** → fresh-spawn `test-authoring:add-integration-test-agent` via `Agent` with a `fix_invocation` block. Circuit-breaker limits per `.claude/rules/tests/fix-protocol.md` — the single source of truth for the counters.
- **Non-deterministic** (including `env_failure`) → present to user. If the user approves a fix for a quality flag or anti-gaming finding, route via the same fresh-spawn `fix_invocation` block with `findings_to_fix.user_approved_actions` populated. `env_failure` is informational only — the writer cannot fix infrastructure.

The orchestrator MUST NOT invoke `Write` / `Edit` / `MultiEdit` directly. All edits go through the writer.

## Step 7 — Summary

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Summary reporting". Note any env_failures distinctly — they are infrastructure issues, not test-quality issues. Status per file uses the icons in the plugin's `resources/static/status-legend.md` (= `<PLUGIN_TEMPLATES>/../static/status-legend.md`, resolved in Step -1; plugin-internal controlled vocabulary). If `PLUGIN_TEMPLATES` is unresolved (fast-path injection failure), use plain text status labels rather than prompting.



