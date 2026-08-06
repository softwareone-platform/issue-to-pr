---
name: add-unit-test
description: >
  Generate unit tests for changed source files or a user-specified target (class, method, file, directory). Trigger phrases: "add unit tests for X", "write tests for X.cs", "create unit test for ComponentY.MethodZ". Do NOT trigger for: discussions about why a test failed, TDD philosophy, test runner configuration, mocking framework comparisons.
---


## Step -1 — Resolve context source (fast path vs cacheless)

This skill runs **with or without** a prior `setup-test-context`. First resolve where rules/conventions come from, then proceed.

**Resolve the plugin templates root once** — you pass it to every subagent, because subagents cannot resolve it themselves. The bundled templates sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`): on the **cacheless path** (where it is load-bearing) resolve it at runtime — run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool, and if `$CLAUDE_SKILL_DIR` is empty, ask the user for the `test-authoring` plugin install path. On the **fast path** its only use is the Step 7 status icons — do **not** prompt; if it stays unresolved, use plain status labels. The Read tool normalises the `../..` segments.

Then check `.claude/conventions/tests/project-architecture.md`:

- **Exists → fast path.** A prior setup cached per-repo files. **Resolve, do not bulk-read**: every `.claude/{conventions,rules,shared}/tests/<f>` reference below resolves to the repo file — read each file lazily, at the first step that uses it (see "Orchestrator reading list" below). **Per-file fallback still applies at read time**: any individual file that is absent falls through to the cacheless source below (e.g. setup generated unit-only, now a missing integration convention) — a missing file is never fatal.
- **Absent → cacheless.** setup has never run. **Do NOT stop.** Announce once: `"No precomputed test conventions found — running cacheless (sibling-driven). Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then for the rest of the flow:
  - Resolve every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` reference to `<PLUGIN_TEMPLATES>/{rules,shared}/<f>` instead — same lazy rule: read at the step that uses it, never as an upfront batch. Cosmetic frontmatter/example tokens (`{{TEST_GLOB}}`, `{{SRC_DIR}}`) are inert when read explicitly — substitute the detected value.
  - Treat `.claude/conventions/tests/<f>` as **optional**: prefer the nearest sibling test for the scope (the writer's top-priority source anyway); when no sibling exists either, the writer reports the gap rather than inventing conventions — there is no language baseline to fall back to.
  - **Detect once, reuse this session**: the language, and an *executable* build/test invocation (test-project path + filter syntax, e.g. `dotnet test <proj> --filter "FullyQualifiedName~<Class>"`) from the project manifest. `test-rules.md` carries no command list — the detected command is the only source, used everywhere (writer build, verifier U4 build, and this orchestrator's own final build). Pass it to subagents as `build_test_command`.

Resolve `common-orchestrator-flow.md` the same way: fast path reads `.claude/rules/tests/common-orchestrator-flow.md`; cacheless reads `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `common-orchestrator-flow.md` (previous paragraph).
- **At the step that uses it**: Step 1 → `.claude/shared/tests/scope-resolution.md`. Step 2 → `.claude/conventions/tests/project-architecture.md` + `.claude/conventions/tests/unit-test-conventions.md` (cacheless: optional — sibling-first). Step 4, only when it runs → `.claude/rules/tests/test-rules.md` (cacheless: skip the read — use the session-detected `build_test_command`). First verifier finding or attributable build failure → `.claude/rules/tests/fix-protocol.md`. A writer stopping on missing framework source → `.claude/rules/tests/sut-analysis.md` → "Runtime resolution flow". A writer stopping on no convention source → `.claude/rules/tests/common-orchestrator-flow.md` → "Writer stop on no convention source".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, and the other flow's rule book (`common-update-instructions.md`). They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Add Unit Tests for Pending Changes

You are the orchestrator for unit test generation. Your job is to **resolve scope** and then **delegate** actual test writing to the `test-authoring:add-unit-test-agent` subagent, then verify via `test-authoring:verify-add-unit-test-agent`. Follow the universal flow in `.claude/rules/tests/common-orchestrator-flow.md`; this file only documents unit-specific pieces.

> Every `.claude/{conventions,rules,shared}/tests/…` read below follows **Step -1's resolution**: the repo file on the fast path, or `<PLUGIN_TEMPLATES>/…` (rules/shared) plus sibling-derived (conventions) on the cacheless path — and happens lazily, at the step that uses it, never as an upfront batch. A body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. On the cacheless path you also pass `plugin_resources_path` and `build_test_command` into every subagent prompt — they cannot resolve these themselves.

## Step 1 — Identify Scope

Follow the procedure in `.claude/shared/tests/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Focus on new public/internal methods or classes, modified method signatures or logic branches, new command/query handlers, and new service methods.
- **Mode B** (argument provided, e.g., `/test-authoring:add-unit-test ComponentName`): Resolve by directory, component, class, method, or file name.

## Step 2 — Pre-fetch Context

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Pre-fetch context (add-flow only)":

1. For each source file, find the corresponding test directory using `.claude/conventions/tests/unit-test-conventions.md` and `.claude/conventions/tests/project-architecture.md`.
2. If sibling test files exist in the mapped directory, read them and extract the convention spec. If none exist there, widen once — the nearest test files in the same test project (parent directory or adjacent feature folder) — and label them in the writer prompt as `nearest sibling (not exact mirror)` so the writer weighs them below an exact-mirror sibling.
3. If no siblings are found at all, omit the sibling fields from the Step 3 template and state instead: `No sibling tests found and no convention source — apply test-writer-rules.md → Fallback Chain`. Under the Slim default `{type}-test-conventions.md` is generated on neither path, so do not point the writer at it. Never invent a sibling path to satisfy the template.
4. Pass this context to the writer.

## Step 3 — Delegate to Agent

Spawn `test-authoring:add-unit-test-agent` — one agent per source class, all in parallel. Per `.claude/rules/tests/common-orchestrator-flow.md` → "Writer delegation".

```
Agent(subagent_type="test-authoring:add-unit-test-agent"):
  Generate unit tests for:
  - <source file path>
    Changed/Cover: <methods>
  Pre-fetched context (acceleration hint — if sibling differs, agent follows sibling):
    Sibling test: <sibling file path>
    Convention spec observed:
      <fields per convention spec>
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <session-detected executable build/test invocation>
```

### Method-scoped

When the user specifies a method, include it in the agent prompt as "Focus only on <method>".

## Step 4 — Verify Build (multi-agent only)

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Multi-agent build check" (run a final build only when multiple agents were spawned; attribute each failure to the owning writer and route it via `.claude/rules/tests/fix-protocol.md`, else report 🟥 unresolved — the orchestrator never fixes it directly). Use the session-detected `build_test_command`.

## Step 5 — Review via Verify Agent

Spawn **one** `test-authoring:verify-add-unit-test-agent` to independently review the generated tests. Always spawn the verifier — quality control must not be bypassed.

```
Agent(subagent_type="test-authoring:verify-add-unit-test-agent"):
  Review unit tests generated by writer agents.
  Test type: unit
  Original task: <the scope/spec as given to the writers — required by the verifier's U2b divergence cross-check>
  Pre-writer source snapshot: <the source diff state recorded before writers were spawned — baseline for the U3 SUT-modification check>
  Cacheless context (include ONLY on the cacheless path — omit on the fast path):
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

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Role boundary" + "Fix-verify loop" and `.claude/rules/tests/fix-protocol.md`:

- **Deterministic** → fresh-spawn `test-authoring:add-unit-test-agent` via `Agent` with a `fix_invocation` block (writer reads its previously produced files and applies targeted fixes). Circuit-breaker limits per `.claude/rules/tests/fix-protocol.md` — the single source of truth for the counters.
- **Non-deterministic** → present to user. If the user approves a fix for a quality flag or anti-gaming finding, route via the same fresh-spawn `fix_invocation` block with `findings_to_fix.user_approved_actions` populated.

The orchestrator MUST NOT invoke `Write` / `Edit` / `MultiEdit` directly — even for "small" fixes or after user approval. All edits go through the writer.

## Step 7 — Summary

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Summary reporting". Status per file uses the icons in the plugin's `resources/static/status-legend.md` (= `<PLUGIN_TEMPLATES>/../static/status-legend.md`, resolved in Step -1; plugin-internal controlled vocabulary). If `PLUGIN_TEMPLATES` is unresolved (fast-path injection failure), use plain text status labels rather than prompting.



