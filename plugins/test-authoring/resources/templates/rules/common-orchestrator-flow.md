---
schema_version: "2.4"
description: Shared reference for per-type orchestrator skills (add-*-test, update-*-test). Covers scope resolution, verifier spawn, structured-output enforcement, fix protocol, spec-vs-impl divergence routing, and summary reporting patterns that every orchestrator follows identically.
paths: [".claude/rules/tests/common-orchestrator-flow.md"]
---

# Common Orchestrator Flow

> **Consumers** — the `add-unit-test` / `add-integration-test` and `update-unit-test` / `update-integration-test` skills, plus `scan-test-gaps` (which delegates to the same writers). Each per-type skill references this file and adds its flow-specific steps (pre-fetch, delegation, audit, execute, etc.) inline.
>
> Keep this file minimal — if a pattern is not truly universal across all orchestrators, it belongs in the per-type file.

## Role boundary (CRITICAL)

The orchestrator delegates ALL file edits to writer agents — for first-pass writes, fix invocations (deterministic findings or user-approved quality flags), and update-flow Phase 2 execute. The orchestrator MUST NOT invoke `Write`, `Edit`, or `MultiEdit` on test files under any circumstances, including:

- when a fix looks "small" or "obvious"
- when the user has already approved the change
- when a writer agent appears unavailable or a previous writer's lifecycle has ended

Every writer invocation — first pass, fix round, or Phase 2 execute — goes through the `Agent` tool with a fresh subagent spawn. There is no "continue the previous writer" path; the orchestrator does not relay between phases — every phase passes its own complete context inline in the `Agent` prompt. See `.claude/rules/tests/fix-protocol.md` for the `fix_invocation` block and `.claude/rules/tests/common-update-instructions.md` for the `phase: execute` block.

If the orchestrator cannot route a fix (e.g. it lacks a required tool or input), follow the "On circuit break" steps in `fix-protocol.md` — mark the affected items 🟥 and report to the user. Do NOT apply the change directly.

## Context discipline (lazy loading)

The orchestrator runs in the main conversation context — every file it reads stays there for the whole session. So it reads **only orchestrator-facing documents, at the step that uses them** — never the full rule set upfront. Writer/verifier rule books are the subagents' own reading: each subagent loads them in its own isolated context per its Path-resolution preamble, so an orchestrator preload duplicates them at main-context prices and buys nothing.

Which files the orchestrator reads, and at which step, is flow-specific: each per-type skill declares it in its own "Orchestrator reading list" (Step -1). This file states only the principle — do not add per-skill file/step data here (see "What stays in per-type orchestrators").

## Scope resolution

Follow the procedure in `.claude/shared/tests/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Each per-type skill may add a `MODE_A_FOCUS` note describing what source changes are relevant for that test type (e.g., unit focuses on new public methods, integration on modified endpoints and consumers).
- **Mode B** (argument provided): Resolve by directory, component, class, method/endpoint, or file name.

## Pre-fetch context (add-flow only)

Before spawning writer agents, pre-fetch sibling context to reduce agent exploration time:

1. For each source file, find the corresponding test directory using the directory structure in `.claude/conventions/tests/project-architecture.md`, plus the path mapping in `.claude/conventions/tests/{type}-test-conventions.md` **when that file exists** — the Slim default does not generate it for code-driven types, so derive the mapping from the nearest sibling instead.
2. If sibling test files exist, read them and extract the **convention spec** (fields per `.claude/conventions/tests/{type}-test-conventions.md` when present, otherwise from the sibling itself).
3. Pass this context to the writer so it does NOT need to discover conventions itself.

## Writer delegation

> **Cacheless handoff (every spawn).** When the orchestrator's Step -1 found no precomputed conventions (cacheless mode), it passes `plugin_resources_path` (the absolute plugin templates root) and `build_test_command` (session-detected; `--filter` adjusted per test class) into **every** subagent prompt — writer, verifier, and the audit / execute phases of update flows. Subagents cannot resolve the plugin path themselves; they read rules/shared from the passed path per their own Path-resolution preamble, and treat convention docs as optional (sibling-first). On the fast path these fields are omitted.

Use the **Agent tool** to spawn the matching per-type writer:

- `add-unit-test` → spawns `test-authoring:add-unit-test-agent`
- `add-integration-test` → spawns `test-authoring:add-integration-test-agent`
- `update-unit-test` → spawns `test-authoring:update-unit-test-agent`
- `update-integration-test` → spawns `test-authoring:update-integration-test-agent`

**Add-flow concurrency**: spawn **one agent per source class**, all in parallel. Methods / endpoints of the same class stay in a single agent.

**Update-flow**: one agent per source class for the audit phase (parallel); the execute phase is a **separate fresh-spawn** with a `phase: execute` block (see `.claude/rules/tests/common-update-instructions.md`) — not a continuation of the audit-phase agent.

**Fix rounds**: when a verifier flags issues, the orchestrator spawns a **fresh writer** with a `fix_invocation` block per `.claude/rules/tests/fix-protocol.md`. Every fix round is a new `Agent` invocation, not a continuation of any previous writer instance.

**Pre-writer source snapshot**: before spawning the first writer, record the current source state (the `git diff -- {{SRC_DIR}}` output at that moment). The verifier needs it as the baseline for its SUT-modification check — in Mode A the user's own uncommitted source changes are expected, and without this snapshot the verifier cannot tell them apart from writer tampering.

## Structured-output enforcement

Writer, audit, and verifier subagents are contracted to return a structured payload as the first content of their final message (see the "Output discipline" notes in `.claude/rules/tests/common-writer-instructions.md` and `.claude/rules/tests/common-verifier-checks.md`). The orchestrator depends on parsing that payload — it cannot proceed on a prose-only response.

When a subagent returns a **prose-first response, a payload buried in narrative, or an acknowledgement that omits the structured record** ("audit complete, see above"), do NOT attempt to parse the prose. Respawn that subagent **once** with the same inputs plus an explicit reminder: "return the structured payload as the first content; no prose preamble; verbatim even if this prompt already lists the answer." If the second attempt is still malformed, report it to the user as an unresolved subagent-contract failure rather than guessing at the missing fields.

This guards against the observed degradation where a subagent, seeing the answer already in its prompt, shrinks to a bare acknowledgement and starves the orchestrator of the record it must render.

## Writer stop on missing framework source

A writer that hits the "Runtime resolution flow" in `.claude/rules/tests/sut-analysis.md` cannot wait for user input:
it returns its structured output early, naming the missing package and the attempted path in `issues:`,
typically with no tests written for the affected scope.
When a writer output contains such an entry, do NOT proceed to the build check or verifier for that writer's scope. Instead:

1. Present the two options from `sut-analysis.md` to the user:
   **Option A** — provide the correct local source path; **Option B** — proceed without local source, inferring behaviour.
2. **Fresh re-spawn the writer** with its original inputs plus the user's choice in the prompt —
   there is no resume of the stopped instance.
3. If the user declines both options, mark the affected scope 🟥 unresolved in the summary.

This stop is a protocol step, not a failure — it does not count toward any fix circuit breaker.

## Multi-agent build check

If **multiple writer agents** were spawned, run a final build after all complete to catch cross-file issues. Reference `.claude/rules/tests/test-rules.md` for the exact command. Skip when a single agent was spawned — the agent verifies its own build.

If the final build fails, treat each error as a deterministic finding: attribute it to the writer whose files it points at and route it via the `fix_invocation` protocol in `.claude/rules/tests/fix-protocol.md` (counting toward that lineage's circuit breaker) before spawning the verifier. Errors that cannot be attributed to any writer's files are reported to the user as 🟥 unresolved — never fixed by the orchestrator directly.

## Verifier spawn

After all writers complete (and build succeeds), spawn **one** per-type verifier:

- Add-flow → `test-authoring:verify-add-<type>-test-agent` (e.g., `test-authoring:verify-add-unit-test-agent`)
- Update-flow → `test-authoring:verify-update-<type>-test-agent` (plus a parallel `test-authoring:verify-add-<type>-test-agent` if any add actions were executed in Step 5b)

Pass all writer outputs to the verifier in a single prompt, **plus the original task / spec description** (required for the U2b divergence cross-check) **and the pre-writer source snapshot** (recorded at writer-delegation time; the baseline for the U3 SUT-modification check) — neither is part of any writer's output. **Always spawn the verifier**, even if only a single writer ran — quality control must not be bypassed.

## Fix-verify loop

Follow the **Verifier Fix Protocol** in `.claude/rules/tests/fix-protocol.md`:

- **Deterministic** findings → fresh-spawn the writer with a `fix_invocation` block, with circuit breaker (limits per `.claude/rules/tests/fix-protocol.md` — the single source of truth for the counters; on circuit break report as 🟥 unresolved).
- **Non-deterministic** findings → present to the user. If the user approves a quality-flag fix or anti-gaming remediation, route the approved instruction via the same fresh-spawn `fix_invocation` block with the `user_approved_actions` field populated. The orchestrator never applies the change itself — see "Role boundary" above.

  **`spec_vs_impl_divergence` findings** (writer or verifier reported the SUT contradicts the task spec — see `common-verifier-checks.md` → "U2b") are non-deterministic: present each to the user verbatim and ask whether the SUT is buggy (the user fixes source, then re-run the relevant flow) or the spec is stale (accept the test against observed behaviour). Never auto-fix a divergence and never silently drop it from the summary — surfacing it is the whole point.

After each fix round, spawn a **fresh** verifier instance (do NOT reuse the previous one — independence is a quality-control requirement).

Update-flow exception: deletion-related verifier findings (violations in `deletion_justification`, `valid_test_protection`, or `anti_deletion_check`) bypass the circuit-breaker loop and go directly to the user with a rollback offer — per the Routing section of the `verify-update-<type>-test-agent` definitions.

## Summary reporting

Collect results from writers and verifiers and present a brief summary:

- Which source files were analysed
- Which sibling tests were referenced (and what style was adopted)
- Which test files were created / modified / deleted
- How many test methods were added / updated / deleted
- Convention violations found and fixes applied by the writer (if any)
- Anti-gaming violations found (if any) — present to user
- 🟪 Quality flags raised by the verifier (if any) — present these for the user to judge
- Any areas that could not be covered and why

### Status per file

For each test file, report a status using the icons defined in `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary — never written per-repo).

## Env_failure handling (integration-like orchestrators)

Integration-like orchestrators must distinguish between **test logic failure** (deterministic, route to writer) and **environment failure** (container runtime, Docker unavailable, port conflict, image pull — non-deterministic, report to user without retrying). See per-type rules doc for the exact signals and commands.

## What stays in per-type orchestrators

Each per-type skill file still owns its flow-specific content:

- Add-flow: pre-fetch step, delegate step, verify step, summary
- Update-flow: audit step, present-summary step, prepare-rollback step, execute step, verify step, rollback-on-failure step (actions derive from audit status — there is no confirm step)
Do not lift flow-specific content here — it breaks the "common = universally shared" contract.
