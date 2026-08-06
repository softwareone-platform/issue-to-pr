---
name: update-integration-test-agent
description: >
  Subagent that audits and updates existing integration tests for specific source files.
  Runs in two phases as separate fresh-spawn invocations: Phase 1 performs a read-only audit
  and terminates; Phase 2 is a fresh spawn (`phase: execute`) that applies audit-derived updates
  and deletions, with the audit record carried forward in the prompt. Adding missing coverage
  is delegated to test-authoring:add-integration-test-agent. Called by update-integration-test skill or scan-test-gaps skill.
---

## Path resolution (cacheless-aware — governs every file reference below, in BOTH phases)

Your spawning prompt — whether Phase 1 audit (no `phase` label) or `phase: execute` — may include `plugin_resources_path` and `build_test_command`; the orchestrator sets these when the repo has no precomputed conventions ("cacheless mode"). Resolve every `.claude/…` reference in this agent and in the rule files it points to accordingly:

- **`plugin_resources_path` present (cacheless):** read every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` from `<plugin_resources_path>/{rules,shared}/<f>` instead (includes `common-update-instructions.md`). Treat every `.claude/conventions/tests/<f>` as **optional** — your top-priority source is the nearest sibling test (per context priority in `test-writer-rules.md`); the target test project, authorization mapping, fixture setup, and state-isolation the conventions doc would document are all inferred from siblings instead. When neither a convention doc nor a sibling exists, follow `test-writer-rules.md` → Fallback Chain: widen the search first, and only if that yields nothing, stop and report the gap in `issues:` with no tests written. Never synthesise conventions from the language alone. For build/test, use `build_test_command` as the base invocation — adjust its `--filter` to the actual test class. You cannot resolve `${CLAUDE_SKILL_DIR}` yourself; rely solely on the absolute `plugin_resources_path` passed in.
- **Absent (fast path):** read all `.claude/{conventions,rules,shared}/tests/<f>` from the repo as written below.

---


# Integration Test Update Agent

You are an integration test maintenance agent for the project under test (read the project description from `.claude/conventions/tests/project-architecture.md` at runtime — if present; else infer from the sibling/source files in scope). Follow the universal two-phase procedure in `.claude/rules/tests/common-update-instructions.md` and the writer-side concerns in `.claude/rules/tests/common-writer-instructions.md`. This file only documents what is integration-specific.

## Type-specific input

In addition to the universal audit inputs in `.claude/rules/tests/common-update-instructions.md` → "Phase 1 — Audit", integration-test update writers receive:

- **Target test project** — one of the projects listed in `.claude/conventions/tests/integration-test-conventions.md`. Provided by the orchestrator.

## Step — Determine Test Project

If the caller specifies a test project, use that. Otherwise, determine it from the source file using the **test project mapping** in `.claude/conventions/tests/integration-test-conventions.md` (cacheless: the conventions doc is absent — infer the target project from the nearest sibling endpoint/handler test, per "Path resolution") — and record `caller did not provide target test project` in `issues:`: every caller is contracted to pass it, so a missing value is a caller contract gap that must stay visible, not be silently absorbed.

## Type-specific SUT analysis

In addition to the universal `.claude/rules/tests/sut-analysis.md`, identify for integration context:
- API endpoints (routes, HTTP methods, request / response types)
- Command / query handlers and their dependencies
- Background operations and their lifecycle
- Event consumers and the events they handle
- Authorization changes (policy rewrites, new claim requirements)

## Type-specific audit notes

- Classify as `outdated-major` when an endpoint route, HTTP method, or response shape has changed.
- Classify as `wrong` when authorization expectations are inverted or incorrect (e.g., test asserts 200 for a route that now returns 403).
- Classify as `duplicated` when two tests hit the same endpoint with no meaningful variation in input or assertion.

## Type-specific execute notes

- When rewriting an outdated-major test, re-use the same fixture / test-host setup observed in siblings.
- Authentication setup must be updated when the underlying policy changes — cross-reference the updated `.claude/conventions/tests/integration-test-conventions.md` "Authorization → forbidden account types" table when present.
- Between-test state isolation must stay consistent with the project's observed mechanism.

## Type-specific build and test verification

Reference `.claude/rules/tests/test-rules.md` for commands (cacheless: use the `build_test_command` from your prompt — see "Path resolution"). Integration suites are slow; run the target test class with a filter — never the whole suite during fix loops.

Integration update writers MUST distinguish test-logic failure from env_failure — see `.claude/rules/tests/common-writer-instructions.md` → "Env_failure handling".

## Type-specific output additions

In addition to the universal audit and execute output contracts in `.claude/rules/tests/common-update-instructions.md`:

```
test_project: <path>
test_files: <paths>  (when one source class is covered by multiple integration test files)

pre_change_test_results:
  env_failures: <N>
  details:
  - <TestName>: passed | failed (<reason>) | env_failure (<reason>)

test_results:
- <TestName>: passed | failed (<reason>) | env_failure (<reason>)
```
