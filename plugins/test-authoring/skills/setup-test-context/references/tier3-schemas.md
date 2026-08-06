# Tier 3 File Generation Schemas

Read this file during Step 3.3 — it is dispatched to the subagents as a reference, per item 10 of the prompt contract. It contains the generation recipes for all analysis-derived files. These files are too repo-specific for templates — generate them directly using the analysis from Step 1. All Tier 3 files live under `.claude/conventions/tests/`.

The frontmatter shown below is what each generated file must carry — a `description` and, where the file is scoped to particular paths, a `paths` list. Generated conventions carry no version field: the plugin keeps no per-run state, so there is nothing to compare a version against.

Keep every generated frontmatter block closing within the first 20 lines — Step 4's verification reads only that bounded window,
and a later closing `---` would be mis-read as invalid frontmatter (false rollback).

---

## `project-architecture.md`

Frontmatter:
```yaml
---
description: Documents the source and test directory structure, naming conventions, and feature organisation.
paths: ["{{SRC_GLOB}}", "{{TEST_GLOB}}"]
---
```

Content:
- **Source structure** — directory tree from Step 1.3, showing typical feature organisation (e.g., Commands/, Handlers/, Services/ subdirectories)
- **Test structure** — directory tree for each test project, with an example of how a feature is organised. Note mirroring style (mirror source vs scenario-based) and file organisation (flat vs subfolder-per-SUT).
- **Naming conventions** — source file naming patterns and test file naming patterns
- **Feature components** — if the source uses a consistent per-feature structure, document the pattern

---

## `{type}-test-conventions.md` — one per confirmed test type

> **Slim default: NOT generated.** This schema is retained for a manual full regeneration, but the Slim default does not produce `{type}-test-conventions.md` for any test type — writers derive these conventions from the nearest sibling at runtime.

Frontmatter:
```yaml
---
description: Derivation rules, sibling convention checklist, and type-specific patterns for {type} tests.
paths: ["<test project path>/**/*.<ext>"]
---
```

Content:
- **Cross-reference note (at top of file)**:
  > This file documents conventions and derivation rules, not directory structure.
  > For the directory tree and naming conventions, see `.claude/conventions/tests/project-architecture.md`.
  > For shared utilities (if available), see `.claude/conventions/tests/common-test-utilities.md`.
  > For cross-type verification patterns (if available), see `.claude/conventions/tests/common-verification-patterns.md`.
- **Test project mapping** (for integration-like) — which source areas map to which test project
- **Source → test path derivation rules** — how to transform a source path into a test path (NOT a restatement of the directory tree; reference `project-architecture.md` instead). Include only:
  - Base transformation formula in plain text (e.g., `src/<feature>/<Class>.cs` → `tests/<TestProject>/<feature>/<Class>Tests.cs`)
  - Detection logic for flat (`{Class}Tests.cs`) vs subfolder-per-SUT (`{Class}Tests/{Method}Test.cs`) — when each applies, based on sibling observation
  - Repo-specific exceptions to the base rule, if any
- **Sibling convention checklist** — fields adapted to the test type:
  - Unit-like: mocking library, verification idiom (mock-interaction verification call syntax observed in siblings — e.g., `.Received()` / `.Verify()` for .NET, `mock.assert_called_with(...)` / `mock.assert_any_call(...)` for Python `unittest.mock`, `expect(...).toHaveBeenCalled()` for Jest/Vitest), assertion library (assertion API style observed in siblings — e.g., FluentAssertions `.Should().Be(...)`, xUnit `Assert.Equal(...)`, plain pytest `assert x == y`, Jest `expect(...).toBe(...)`), fixture pattern, base class, SUT construction, naming pattern, AAA comments, file organisation, member ordering, builder/generator location (repo-specific — may not exist)
  - Integration-like: base class, data factory, HTTP client pattern, security/auth context, naming pattern, AAA comments, file organisation, member ordering, builder/generator location (repo-specific — may not exist)
  - **Emit as markdown table** in `<type>-test-conventions.md` (columns: `Field` / `Typical value in this repo`) — downstream agents locate each entry by table-row label, not by YAML key. YAML output is reserved for the writer's structured response (see **Convention spec output format** below).
- **Learn from sibling tests (CRITICAL)** — priority rule (siblings are source of truth), search priority, "do not blend styles"
- **Convention spec output format** — exact YAML format writer agents should output
- **Authorization/security policy detection** (for integration-like, if applicable) — the policy → forbidden account types mapping from Step 1.6.1
- **Type-specific common patterns** — recurring patterns observed only in this test type (not layer-correlated). Cross-type recurring patterns go into `common-verification-patterns.md` instead.
- **Integration-specific test coverage** (for integration-like) — what to test and what NOT to do at this level

---

## `common-test-utilities.md` — conditional (shared test project detected)

Generate ONLY if Step 1.3 detected a shared test project (Tests.Common-style) providing utilities used across multiple test projects.

Frontmatter:
```yaml
---
description: Shared test utilities available across test types (extensions, helpers, custom assertions from a shared test project).
paths: ["<shared test project path>/**/*.<ext>"]
---
```

Content structure:
- **Project location** (path from Step 1.3) — which test projects reference it
- **Cross-reference note**:
  > For the structural fact of which test projects reference this shared project, see `.claude/conventions/tests/project-architecture.md`.
- **Utility sections** — one per category of utility discovered in Step 1.3 (e.g., "AutoFixture extensions", "FluentAssertions extensions", "Reflection helpers"). Each utility entry includes:
  - Name (class/method/extension)
  - Brief description of purpose
  - Usage example extracted from actual test code (NOT invented)

If multiple shared test projects exist (unlikely), use one section per project.

---

## `common-verification-patterns.md` — conditional (≥1 qualifying pattern detected)

Generate ONLY if Step 1.4 pattern detection yielded ≥1 "layer common" or "cross-layer common" pattern.

Frontmatter:
```yaml
---
description: Layer-specific and cross-layer recurring verification patterns observed across test types. Writer agents consult this before finalising tests.
paths: ["{{TEST_GLOB}}"]
---
```

Content structure:
- **Cross-reference note** at top:
  > Writer agents: after determining the SUT's layer, read the relevant layer section plus the "General" section. Siblings still take priority if their patterns differ.
- **General (cross-layer) section** — patterns observed across multiple layers and multiple test types
- **Per-layer sections** — use the repo's actual layer naming (Handler, Controller, Service, Repository, Consumer, Worker, etc. as detected in Step 1.6)

Each pattern entry includes:
- Observed frequency across buckets (e.g., "unit handler tests 8/10, integration handler tests 5/7")
- Pattern code extracted from an actual sibling test (NOT invented)
- When to apply (which dependency or SUT trait triggers this pattern)

If repo had no clear layers (layered sampling fallback), include only a "General" section with project-wide patterns.

