---
name: add-unit-test
description: >
  Generate unit tests for changed source files or a user-specified target (class, method, file, directory). Trigger phrases: "add unit tests for X", "write tests for X.cs", "create unit test for ComponentY.MethodZ". Do NOT trigger for: discussions about why a test failed, TDD philosophy, test runner configuration, mocking framework comparisons.
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

**Detect once, reuse this session**: the language, and an *executable* build/test invocation (test-project path + filter syntax, e.g. `dotnet test <proj> --filter "FullyQualifiedName~<Class>"`) from the project manifest. `test-rules.md` carries no command list — the detected command is the only source, used everywhere (writer build, verifier U4 build, and this orchestrator's own final build). Pass it to subagents as `build_test_command`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.
- **At the step that uses it**: Step 1 → `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`. Step 2 → `.claude/conventions/tests/project-architecture.md` + `.claude/conventions/tests/unit-test-conventions.md` (optional — sibling-first). Step 4, only when it runs → `<PLUGIN_TEMPLATES>/rules/test-rules.md` (use the session-detected `build_test_command`). First verifier finding or attributable build failure → `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`. A writer stopping on missing framework source → `<PLUGIN_TEMPLATES>/rules/sut-analysis.md` → "Runtime resolution flow". A writer stopping on no convention source → `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Writer stop on no convention source".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, and the other flow's rule book (`common-update-instructions.md`). They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Add Unit Tests for Pending Changes

You are the orchestrator for unit test generation. Your job is to **resolve scope** and then **delegate** actual test writing to the `test-authoring:add-unit-test-agent` subagent, then verify via `test-authoring:verify-add-unit-test-agent`. Follow the universal flow in `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`; this file only documents unit-specific pieces.

> Every `<PLUGIN_TEMPLATES>/…` and `.claude/conventions/tests/…` read below follows **Step -1's resolution** — and happens lazily, at the step that uses it, never as an upfront batch. A body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. You pass `plugin_resources_path` and `build_test_command` into every subagent prompt — they cannot resolve these themselves.

## Step 1 — Identify Scope

Follow the procedure in `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Focus on new public/internal methods or classes, modified method signatures or logic branches, new command/query handlers, and new service methods.
- **Mode B** (argument provided, e.g., `/test-authoring:add-unit-test ComponentName`): Resolve by directory, component, class, method, or file name.

## Step 2 — Pre-fetch Context

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Pre-fetch context (add-flow only)":

1. For each source file, find the corresponding test directory — from the sibling tests that mirror it, and from `.claude/conventions/tests/project-architecture.md` when a prior setup cached it.
2. If sibling test files exist in the mapped directory, read them and extract the convention spec. If none exist there, widen once — the nearest test files in the same test project (parent directory or adjacent feature folder) — and label them in the writer prompt as `nearest sibling (not exact mirror)` so the writer weighs them below an exact-mirror sibling.
3. If no siblings are found at all, omit the sibling fields from the Step 3 template and state instead: `No sibling tests found and no convention source — apply test-writer-rules.md → Fallback Chain`. Nothing generates `{type}-test-conventions.md`, so do not point the writer at it. Never invent a sibling path to satisfy the template.
4. Pass this context to the writer.

## Step 3 — Delegate to Agent

Spawn `test-authoring:add-unit-test-agent` — one agent per source class, all in parallel. Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Writer delegation".

```
Agent(subagent_type="test-authoring:add-unit-test-agent"):
  Generate unit tests for:
  - <source file path>
    Changed/Cover: <methods>
  Pre-fetched context (acceleration hint — if sibling differs, agent follows sibling):
    Sibling test: <sibling file path>
    Convention spec observed:
      <fields per convention spec>
  Plugin context (always — the subagent cannot resolve either of these itself):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <session-detected executable build/test invocation>
```

### Method-scoped

When the user specifies a method, include it in the agent prompt as "Focus only on <method>".

## Step 4 — Verify Build (multi-agent only)

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Multi-agent build check" (run a final build only when multiple agents were spawned; attribute each failure to the owning writer and route it via `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`, else report 🟥 unresolved — the orchestrator never fixes it directly). Use the session-detected `build_test_command`.

## Step 5 — Review via Verify Agent

Spawn **one** `test-authoring:verify-add-unit-test-agent` to independently review the generated tests. Always spawn the verifier — quality control must not be bypassed.

```
Agent(subagent_type="test-authoring:verify-add-unit-test-agent"):
  Review unit tests generated by writer agents.
  Test type: unit
  Original task: <the scope/spec as given to the writers — required by the verifier's U2b divergence cross-check>
  Pre-writer source snapshot: <the source diff state recorded before writers were spawned — baseline for the U3 SUT-modification check>
  source_pathspec: <the exact pathspec that snapshot was taken over — the verifier re-runs the diff over it verbatim>
  Plugin context (always — the subagent cannot resolve either of these itself):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <session-detected executable build/test invocation>

  Writer 1 output:
  - files_created: <path>
  - files_modified: <path, or "none" — existing tests the writer touched, verbatim from the writer>
  - sibling_tests_referenced:
    - <sibling path>
      <convention spec>
  - test_count: <N>
  - test_results: <per-test passed | failed (<reason>), verbatim from the writer>
  - spec_vs_impl_divergence: <writer's entries verbatim, or "none">
  - build_status: <success | failed (<errors>), verbatim from the writer>

  Writer 2 output:
  ...
```

Every field is filled from the writer's structured return — never assume a happy-path value the writer did not report.

## Step 6 — Handle Verifier Findings

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Role boundary" + "Fix-verify loop" and `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`:

- **Deterministic** → fresh-spawn `test-authoring:add-unit-test-agent` via `Agent` with a `fix_invocation` block (writer reads its previously produced files and applies targeted fixes). Circuit-breaker limits per `<PLUGIN_TEMPLATES>/rules/fix-protocol.md` — the single source of truth for the counters.
- **Non-deterministic** → present to user. If the user approves a fix for a quality flag or anti-gaming finding, route via the same fresh-spawn `fix_invocation` block with `findings_to_fix.user_approved_actions` populated.

The orchestrator MUST NOT invoke `Write` / `Edit` / `MultiEdit` directly — even for "small" fixes or after user approval. All edits go through the writer.

## Step 7 — Summary

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Summary reporting". Status per file uses the icons in the plugin's `resources/static/status-legend.md` (= `<PLUGIN_TEMPLATES>/../static/status-legend.md`, resolved in Step -1; plugin-internal controlled vocabulary). `PLUGIN_TEMPLATES` is always resolved by this point — Step -1 stops rather than continuing without it.



