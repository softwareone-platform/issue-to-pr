# Step 3.5 — Tier 3 File Generation Schemas

Read this file during Step 3.5. It contains the generation recipes for all analysis-derived files. These files are too repo-specific for templates — generate them directly using the analysis from Step 1. All Tier 3 files live under `.claude/conventions/tests/`.

Each frontmatter `schema_version` field below uses the placeholder `{{CONVENTIONS_SCHEMA_VERSION}}`, resolved by the orchestrator (Step 3.3) to `template-schema-versions.json` field `conventions` (see `placeholders.md`). All four dynamic files belong to the `conventions` category, so the same placeholder applies everywhere; the orchestrator must substitute it before write, and the same value is recorded in the manifest `files[].schema_version` for each (single source of truth).

Keep every generated frontmatter block closing within the first 20 lines — Step 4's verification reads only that bounded window,
and a later closing `---` would be mis-read as invalid frontmatter (false rollback).

---

## `project-architecture.md`

Frontmatter:
```yaml
---
schema_version: "{{CONVENTIONS_SCHEMA_VERSION}}"
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

> **Slim default: NOT generated for code-driven types.** This schema is retained for backward-compat (existing files keep validating) and for a manual full regeneration, but the Slim default does not produce `unit` / `integration` / extra code-driven `{type}-test-conventions.md` — writers derive these conventions from the nearest sibling at runtime. `component-test-conventions.md` (config-driven, its own section below) IS still generated.

Frontmatter:
```yaml
---
schema_version: "{{CONVENTIONS_SCHEMA_VERSION}}"
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
schema_version: "{{CONVENTIONS_SCHEMA_VERSION}}"
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
schema_version: "{{CONVENTIONS_SCHEMA_VERSION}}"
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

---

## `component-test-conventions.md` — conditional (component-like × config-driven supported)

When Step 1.7 classified a project as `component-like × config-driven 🟩`, the template `templates/conventions/component-test-conventions.md` is copied (Step 3.4) with its methodology sections verbatim. The **observed-values sections** must be filled by sampling real `.feature` files and step classes:

### Sampling procedure

1. **`.feature` sampling** — pick 1-2 real `.feature` files from `{{FEATURES_DIR}}`. Extract:
   - `feature_header` — the literal text of the `Feature:` line + description
   - `rule_usage` — observed `Rule:` usage (none / single / multiple)
   - `background_usage` — observed `Background:` usage (yes / no)
   - `scenario_naming` — pattern (Subject + verb + object, question, directive, etc.)
   - `scenario_outline_usage` — yes / no
   - `variable_naming` — bracket style and case convention (`{camelCase}`, `<placeholder>`, etc.)
   - `tag_usage` — observed tags (`@pending`, `@ignore`, none, etc.)
   - `data_table_format` — pipe-delimited with header / other
   - `step_phrasing_style` — voice / form observed

2. **Step-class sampling** — pick 2-3 step classes from different `{{STEPS_DIR}}/<Area>/` folders. Extract:
   - `class_split` — how step methods are organised (4-class Setup/Request/Response/Assertion, 3-class Given/When/Then, single combined, other)
   - `binding_attribute` — `[Binding]` or framework equivalent
   - `constructor_injection` — primary-constructor parameters per class role
   - `step_attribute_form` — regex vs literal, quoting style
   - `step_method_naming` — PascalCase verb-led / other
   - `dto_location` — nested record inside step class / separate file / other
   - `default_dto_factory` — presence and form of a `Default` factory
   - `state_setup_style` — black-box API / direct DB / mixed
   - `assertion_library` — FluentAssertions / xUnit Assert / other
   - `response_reader_pattern` — `PeekAsync<T>` / one-shot reader / other

3. **Area-mapping examples** — pick 2-3 real `(.feature, Steps/<folder>)` pairs, fill the "Naming pairing" table in the template.

4. **Layout tree** — sample the top 5-10 entries under `{{FEATURES_DIR}}` and `{{STEPS_DIR}}` to populate the layout block.

Fill all `{{FEATURE_HEADER_VALUE}}`, `{{RULE_USAGE_VALUE}}`, …, `{{NAMING_PAIRING_ROWS}}`, `{{FEATURE_EXAMPLE_*}}`, `{{STEPS_FOLDER_EXAMPLE_*}}`, `{{STEP_CLASS_EXAMPLE_*}}`, and `{{DEFAULT_*}}` fallback-spec placeholders with observed values. For `{{*_DETAIL}}` pattern-section placeholders, insert short narratives describing what was actually observed; if a pattern is not used, write "not used in this repo" rather than inventing content.

---

## `fixture-capabilities.md` — conditional (fixture class detected)

**Detection signal**: a class under the component test project that composes Testcontainers / `WebApplicationFactory` (or framework equivalent) and exposes `Reset()` (or equivalent scenario reset) and wire-up for fakes. Typical file name forms: `*ComponentTestsFixture*.cs`, `*TestFixture*.cs`, `conftest.py` (behave), `IntegrationSteps.java` (Cucumber-JVM).

**If no fixture class is detected**:
- Do NOT generate `.claude/conventions/tests/fixture-capabilities.md`.
- Warn in Step 2.1 preview: "Component tests detected but no fixture class observed; `fixture-capabilities.md` will NOT be generated. Orchestrator pre-flight and writer assertion-mode gate will fall back to the no-fixture path."

**If a fixture class is detected**:

1. Copy `templates/conventions/fixture-capabilities.md` to `.claude/conventions/tests/fixture-capabilities.md` (already listed in Step 3.4).
2. Fill the role-boundary / workflow-assumption / maintenance-checklist / fixture-gap-response-options sections verbatim (repo-agnostic policy).
3. Parse the fixture class source with regex:
   - `services.Replace(ServiceDescriptor...)` / `services.AddSingleton<I…, Fake…>()` / `services.AddScoped<...>()` invocations → wired substitutes
   - Exposed properties / methods returning fakes (`public Fake<X> GetX() => ...`) → observation APIs
   - `Reset()` body (if present) → between-scenario reset list
   - Host / subsystem splits (e.g., separate `ConfigureApiServices` vs `ConfigureWorkerServices` methods) → host-grouped catalog tables
4. Populate `{{SUBSTITUTES_WIRED_TODAY_TABLES}}` grouped by host/subsystem (e.g., Both / Api host only / Worker host only / Cross-cutting). If no clear host split, use a single "All hosts" table.
5. Populate `{{RESET_CLEARS_LIST}}` from the `Reset()` body. If no `Reset()` method detected, emit a note asking the operator to confirm inter-scenario state leakage is controlled.
6. Leave the "Not wired today" section empty on first generation.
7. Fill `{{FIXTURE_CLASS_NAME}}` and `{{FIXTURE_SOURCE_PATH}}` from the detected file.

**Confidence threshold**: if the parser cannot confidently extract at least 3 wired substitutes from the fixture class, skip generation entirely and warn — partial catalogs mislead the writer. The operator can fill the file manually later.
