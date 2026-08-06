---
name: add-integration-test
description: >
  Generate integration tests for changed source files or a user-specified target (endpoint, handler, command, service). Trigger phrases: "add integration tests for X", "create endpoint test for /foo", "write integration test for HandlerY". Do NOT trigger for: discussions about test infrastructure, container setup questions, or end-to-end test strategy.
---


## Step -1 — Resolve where the rule books and conventions come from

This skill runs **with or without** a prior `setup-test-context`.

**Resolve the plugin templates root once, unconditionally** — you also pass it to every subagent, because subagents cannot resolve it themselves. The bundled rule books sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`), run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool; if `$CLAUDE_SKILL_DIR` is empty too, **stop and ask the user for the `test-authoring` plugin install path**. Do not carry on with it unresolved: every rule this skill obeys lives under it, so continuing would drop the rule books silently instead of failing. The Read tool normalises the `../..` segments.

Two kinds of file, resolved differently:

- **Rule books.** Every `<PLUGIN_TEMPLATES>/rules/…` and `<PLUGIN_TEMPLATES>/shared/…` path below is literal — read it from there. Inside a rule book, a bare filename means a sibling rule book in that same `rules/` directory, and a `../shared/<f>` path is relative to it. Nothing writes any of them into a repo, so there is no per-repo copy to prefer and none to fall out of date. Read each lazily, at the step that uses it — never as an upfront batch (see "Orchestrator reading list").
- **Conventions.** `.claude/conventions/tests/…` is the repo's own cache, written only where `setup-test-context` has run. Treat every one as **optional**: prefer the nearest sibling test for the scope (the writer's top-priority source anyway); when no sibling exists either, the writer reports the gap rather than inventing conventions — there is no language baseline to fall back to. A missing conventions file is never fatal.

If `.claude/conventions/tests/project-architecture.md` is absent, say so once: `"No cached repo profile — deriving from siblings. Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then carry on — it blocks nothing.

**Detect once, reuse this session**: the language, and the *executable* build/test invocation **form** (test-project path + filter syntax, e.g. `dotnet test <proj> --filter "FullyQualifiedName~<Class>"`) from the project manifest. `test-rules.md` carries no command list — the detected form is the only source, used everywhere (writer build, verifier U4 build, this orchestrator's final build). Integration may span several test projects (Step 1.5): **instantiate the form per target test project** and pass each writer the command for ITS project as `build_test_command` (do not reuse one project's path for another).

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.
- **At the step that uses it**: Step 1 → `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`. Step 1.5 → `.claude/conventions/tests/integration-test-conventions.md` (test project mapping, when a prior setup cached it; otherwise infer from siblings). Step 2 → `.claude/conventions/tests/project-architecture.md` (reuse the conventions doc from Step 1.5). Step 4, only when it runs → `<PLUGIN_TEMPLATES>/rules/test-rules.md` (use the session-detected per-project `build_test_command`). First verifier finding or attributable build failure → `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`. A writer stopping on missing framework source → `<PLUGIN_TEMPLATES>/rules/sut-analysis.md` → "Runtime resolution flow". A writer stopping on no convention source → `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Writer stop on no convention source".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, and the other flow's rule book (`common-update-instructions.md`). They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Add Integration Tests for Pending Changes

You are the orchestrator for integration test generation. Your job is to **resolve scope**, **determine the target test project**, and then **delegate** actual test writing to the `test-authoring:add-integration-test-agent` subagent, then verify via `test-authoring:verify-add-integration-test-agent`. Follow the universal flow in `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`; this file only documents integration-specific pieces.

> Every `<PLUGIN_TEMPLATES>/…` and `.claude/conventions/tests/…` read below follows **Step -1's resolution** — and happens lazily, at the step that uses it, never as an upfront batch. A body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. You pass `plugin_resources_path` and `build_test_command` into every subagent prompt — they cannot resolve these themselves.

## Step 1 — Identify Scope

Follow the procedure in `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Focus on modified API endpoints (controllers, routes), command/query handlers, worker operations or event consumers, sync consumers, and changes to persistence logic.
- **Mode B** (argument provided, e.g., `/test-authoring:add-integration-test ComponentName`): Resolve by directory, component, class, endpoint, or file name.

## Step 1.5 — Determine Test Project Mapping

Before spawning agents, determine which test project each source file maps to. Use the **test project mapping** in `.claude/conventions/tests/integration-test-conventions.md`.

**When that doc is absent** (no prior setup, or it cached no per-type conventions): infer the target test project from siblings — locate the existing integration test project whose tests mirror the source area (an endpoint/handler test for a nearby source file). If several integration test projects exist and none clearly mirrors the source, do not guess — state the candidates and ask the user.

If a single source change covers multiple projects (e.g., both API and worker), split the source list and spawn one agent per (source, project) pair.

## Step 2 — Pre-fetch Context

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Pre-fetch context (add-flow only)":

1. For each source file, find the corresponding test directory within the target test project using `.claude/conventions/tests/integration-test-conventions.md` and `.claude/conventions/tests/project-architecture.md`.
2. If sibling test files exist in the mapped directory, read them and extract the convention spec. Include the authorization mapping (where applicable) so the writer uses the correct account-type identity helpers. If none exist there, widen once — the nearest test files in the same target test project — and label them in the writer prompt as `nearest sibling (not exact mirror)` so the writer weighs them below an exact-mirror sibling.
3. If no siblings are found at all, omit the sibling fields from the Step 3 template and state instead: `No sibling tests found and no convention source — apply test-writer-rules.md → Fallback Chain`. Nothing generates `{type}-test-conventions.md`, so do not point the writer at it. Never invent a sibling path to satisfy the template.
4. Pass this context to the writer.

## Step 3 — Delegate to Agent

Spawn `test-authoring:add-integration-test-agent` — one agent per (source, project) pair from Step 1.5, all in parallel. Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Writer delegation".

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
  Plugin context (always — the subagent cannot resolve either of these itself):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build/test command for THIS writer's Target test project>
```

### Endpoint-scoped

When the user specifies an endpoint, include it in the agent prompt as "Focus only on <endpoint>".

## Step 4 — Verify Build (multi-agent only)

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Multi-agent build check" (run a final build only when multiple agents were spawned; attribute each failure to the owning writer and route it via `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`, else report 🟥 unresolved — the orchestrator never fixes it directly), **but build each affected test project separately** — one per (source, project) split from Step 1.5, using that project's command. Use the session-detected `build_test_command` for each project.

## Step 5 — Review via Verify Agent

Spawn **one** `test-authoring:verify-add-integration-test-agent` to independently review the generated tests. Always spawn the verifier.

```
Agent(subagent_type="test-authoring:verify-add-integration-test-agent"):
  Review integration tests generated by writer agents.
  Test type: integration
  Original task: <the scope/spec as given to the writers — required by the verifier's U2b divergence cross-check>
  Pre-writer source snapshot: <the source diff state recorded before writers were spawned — baseline for the U3 SUT-modification check>
  Plugin context (always — the subagent cannot resolve either of these itself):
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

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Role boundary" + "Fix-verify loop" and `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`:

- **Deterministic** → fresh-spawn `test-authoring:add-integration-test-agent` via `Agent` with a `fix_invocation` block. Circuit-breaker limits per `<PLUGIN_TEMPLATES>/rules/fix-protocol.md` — the single source of truth for the counters.
- **Non-deterministic** (including `env_failure`) → present to user. If the user approves a fix for a quality flag or anti-gaming finding, route via the same fresh-spawn `fix_invocation` block with `findings_to_fix.user_approved_actions` populated. `env_failure` is informational only — the writer cannot fix infrastructure.

The orchestrator MUST NOT invoke `Write` / `Edit` / `MultiEdit` directly. All edits go through the writer.

## Step 7 — Summary

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Summary reporting". Note any env_failures distinctly — they are infrastructure issues, not test-quality issues. Status per file uses the icons in the plugin's `resources/static/status-legend.md` (= `<PLUGIN_TEMPLATES>/../static/status-legend.md`, resolved in Step -1; plugin-internal controlled vocabulary). `PLUGIN_TEMPLATES` is always resolved by this point — Step -1 stops rather than continuing without it.



