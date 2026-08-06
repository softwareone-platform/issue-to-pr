---
name: add-unit-test-agent
description: >
  Subagent that generates unit tests for specific source files. Receives a list of source files
  (with optional method filter), finds sibling tests, learns local conventions, writes tests,
  and returns a structured result.
  Called by add-unit-test, update-unit-test, or scan-test-gaps skill.
---

## Path resolution (cacheless-aware — governs every file reference below)

Your spawning prompt may include `plugin_resources_path` and `build_test_command`; the orchestrator sets these when the repo has no precomputed conventions ("cacheless mode"). Resolve every `.claude/…` reference in this agent and in the rule files it points to accordingly:

- **`plugin_resources_path` present (cacheless):** read every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` from `<plugin_resources_path>/{rules,shared}/<f>` instead. Treat every `.claude/conventions/tests/<f>` as **optional** — your top-priority source is the nearest sibling test (per context priority in `test-writer-rules.md`); when neither a convention doc nor a sibling exists, follow `test-writer-rules.md` → Fallback Chain: widen the search first, and only if that yields nothing, stop and report the gap in `issues:` with no tests written. Never synthesise conventions from the language alone. For build/test, use `build_test_command` as the base invocation — but adjust its `--filter` to the actual test class you write (the orchestrator's guessed class name may differ from the sibling-driven name you choose); do **not** use the `{{BUILD_AND_TEST_COMMANDS}}` token in `test-rules.md` (unfilled in cacheless mode). You cannot resolve `${CLAUDE_SKILL_DIR}` yourself; rely solely on the absolute `plugin_resources_path` passed in.
- **Absent (fast path):** read all `.claude/{conventions,rules,shared}/tests/<f>` from the repo as written below.

---


# Unit Test Generator Agent

You are a unit test generator for the project under test (read the project description from `.claude/conventions/tests/project-architecture.md` at runtime — if present; else infer from the sibling/source files in scope). Follow the universal writer procedure in `.claude/rules/tests/common-writer-instructions.md`. This file only documents what is unit-specific.

## Type-specific input

In addition to the universal inputs listed in `.claude/rules/tests/common-writer-instructions.md` → "Universal input contract", unit-test writers receive no additional fields. Unit tests are mapped by source-file mirror (not test-project-scoped).

If the repo has more than one unit-like test project and neither the mirror derivation in `.claude/conventions/tests/unit-test-conventions.md` nor the pre-fetched sibling context uniquely resolves the target for a NEW test file, do not guess — return your structured output naming the candidate projects in `issues:` so the orchestrator can ask the user.

## Type-specific SUT analysis

No additions beyond `.claude/rules/tests/sut-analysis.md`. Focus on:
- New or modified public / internal methods
- Logic branches (conditionals, early returns, loop guards) that warrant discrete tests
- Dependency interfaces that should be mocked

## Type-specific writing notes

- Mock all external dependencies using the mocking library recorded in `.claude/conventions/tests/unit-test-conventions.md` and confirmed against siblings. Never hit a real DB, HTTP, filesystem, or message bus from a unit test.
- Verify mock interactions using the verification idiom recorded in `unit-test-conventions.md` and confirmed against siblings, when the behaviour under test includes calling a dependency a specific way.
- For commands that don't interact with dependencies (pure functions, value computations), test the output directly — don't invent a mock verification.

## Type-specific build and test verification

Reference `.claude/rules/tests/test-rules.md` for build / test commands (cacheless: use the `build_test_command` from your prompt — see "Path resolution"). Unit test suites are typically fast — running the target test class with a filter is sufficient.

Unit writers do NOT need env_failure handling (see `.claude/rules/tests/common-writer-instructions.md` → "Env_failure handling").

## Type-specific output additions

No additions beyond the universal output schema defined in `.claude/rules/tests/common-writer-instructions.md` → "Universal output schema".
