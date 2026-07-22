# Step 1 Analysis — Detection Recipes

Read this file at the start of Step 1. It contains the full detection recipes for §1.1–1.7.
Return to SKILL.md for Step 2 once analysis is complete.

---

## 1.1 Read existing context (hints only)

Read `CLAUDE.md` (if it exists) to gather **hints** about build/test commands, project structure, coding conventions, and test-related instructions.

Do NOT treat CLAUDE.md as authoritative. Record what it claims so drift can be compared against codebase findings in Step 2.1.

If no `CLAUDE.md` exists, inform the user and recommend running `/init` separately (not as part of bootstrap), but continue with codebase-based analysis.

## 1.2 Detect language and frameworks (from codebase)

Determine from **actual files in the repo** (solution/project files, package manifests, test project references, import statements):
- **Primary language** (e.g., C#, TypeScript, Python, Go, Java)
- **Test framework** (e.g., xUnit, Jest, pytest, Go testing, JUnit)
- **Assertion library** (e.g., FluentAssertions, Chai, pytest assertions)
- **Mocking library/libraries** — note if different areas use different libraries
- **Build tool** (e.g., dotnet, npm, cargo, go, maven/gradle)
- **Package manager**

If CLAUDE.md claims different values, record the drift — use codebase findings.

## 1.2.1 Detect local source for external dependencies

When writer agents need to read framework/external dependency source code, they should read from **local source** when available. **Never decompile compiled artifacts** from the package cache.

**Internal packages often have a naming convention linking package names to repo names**. Example from an org with an `Mpt` prefix:

| Package name | Typical local repo folder |
|---|---|
| `Acme.Framework` | `acme-library-framework` |
| `Acme.Rql` | `acme-library-rql` |
| `Acme.<Something>` | `acme-library-<something>` (commonly) |

Try to detect the convention by inspecting `CLAUDE.md` or asking the user.

**What to record for each detected internal package**:
- Package name
- Expected local source path
- Verification status

**Verification procedure**: for each expected local path, use the Glob tool to check whether the directory exists at bootstrap time. Record:
- 🟩 — path exists
- 🟨 — path does not exist (informational; does not block bootstrap)

Missing paths do not affect bootstrap. When an agent later needs to read from a missing path, the runtime resolution flow in `sut-analysis.md` handles the situation (stops and asks the user).

These results are documented in `sut-analysis.md` (Status column in the `{{KNOWN_PACKAGES_TABLE}}`).

If no internal packages detected, still generate `sut-analysis.md` with the universal "never decompile" rule.

## 1.3 Map project structure

Determine:
- **Source directories** (e.g., `src/`, `lib/`, `app/`)
- **Test directories** (e.g., `tests/`, `__tests__/`, `*_test.go`)
- **Source ↔ test mirroring pattern** — read 3–5 existing test files to understand directory mirroring and file naming
- **File organization pattern** — flat files (`FooTests.cs`) or subfolder-per-SUT (`FooTests/BarTest.cs`). Different areas may use different patterns — generated agents must detect and match sibling pattern, not assume a global default.
- **Test project separation** — list ALL test projects found. Do not assume a fixed number or naming convention.
- **Shared test utilities** — detect shared test projects (Tests.Common-style) that provide extensions, helpers, base classes, or custom assertions used across multiple test projects. Record location and key utility types found. Repo-specific: may or may not exist.
- **Completeness check** — list ALL project directories under the source root. For each, find where its tests live. Flag non-obvious placements.
- **Mixed test project layouts** — if unit-style tests are found inside an integration test project (or vice versa), document explicitly. Generated agents must pick conventions based on sibling tests, not project name.

### Output format (when presented to user in §2.1)

Render the source layout as an **ASCII tree** with `├──`, `│`, `└──` connectors — not as nested bullets. Keep it compact: fold same-level siblings using **brace-expansion** notation (`{a,b,c}/`) rather than expanding each on its own line. Append short purpose notes after `#` on the same line for projects whose role is non-obvious from the name.

Render `File organisation` (test placement pattern + exceptions) as a flat bullet list following the tree — it is not hierarchical data.

The exact format and placeholder shape is specified in `SKILL.md` §2.1 under "Project structure". Do not bake any specific repo's project names into the format spec — placeholders are filled at presentation time from the analysis above.

## 1.4 Learn test conventions

### Layered sampling

Use the architectural patterns detected in Step 1.6 to map each test file to a **layer** (Handler, Controller, Service, Repository, Consumer, Worker, etc. — use the repo's actual naming).

Sample tests in a **layered** fashion:
- Sample 2–3 files per `(layer, test type)` combination.
- Maintain a project-wide minimum of 8 files total.
- If a layer has fewer than 3 test files, record it but skip pattern detection for that layer (sample too small).
- If the repo has **no clear layers** (small project, single layer), fall back to project-wide sampling (3–5 files per test project).

### Per-file observations

> **Slim mode (default): skip this sub-pass.** These per-file dimensions feed only the per-type `{type}-test-conventions.md` checklist, which the Slim default does not generate for code-driven types — writers derive them from the nearest sibling at runtime (siblings are the primary source of truth). Run this sub-pass ONLY when a per-type conventions file is actually being generated (e.g. `component-test-conventions.md`, or a manual full regeneration). The **layered sampling above** and the **verification-pattern detection below** are independent of this sub-pass and run regardless — they feed `common-verification-patterns.md`, which Slim retains. So the layered sampling read is NOT eliminated by skipping per-file observations.

For each sampled file, note:
- Which test project it belongs to
- Which layer it covers (if identifiable)
- Mocking approach and library
- Fixture/setup pattern
- Test naming pattern
- Assertion style
- AAA comment usage
- SUT construction approach
- **Test data creation patterns** — including builder/factory/generator directory location (e.g., sibling `Generators/` or `Builders/` subfolder). Repo-specific — may or may not exist.
- File organization pattern
- Member ordering within test classes

### Verification pattern detection (for `common-verification-patterns.md`)

For each `(layer, test type)` bucket, extract all mock verification calls (`.Received()`, `.Verify()`, `expect(...).toHaveBeenCalled()` — language/framework-specific).

Compute frequency per `(layer, test type)`. Classify:
- **Layer common**: appears in ≥2 samples within the same layer (any count of test types) → will go into `common-verification-patterns.md` under that layer's section.
- **Cross-layer common**: appears across multiple layers → "General" section of `common-verification-patterns.md`.
- **Type-specific** (only in one test type, not layer-correlated) → `{type}-test-conventions.md` common patterns section. **Slim mode (default):** no code-driven `{type}-test-conventions.md` is generated, so a type-specific pattern has no destination — do not separately capture it (the nearest sibling conveys it to the writer at runtime). Only layer-common / cross-layer-common patterns feed the retained `common-verification-patterns.md`.
- **Single-sample occurrences** → discard (noise).

Fallback for no-layer repos: project-wide, >50% of samples (≥5/8) → `common-verification-patterns.md` general section.

For each qualifying pattern record: observed frequency per bucket, pattern code (extracted from an actual sibling test — not invented), applicable dependency/context.

**Important**: note if different areas use different conventions. Generated agents must learn from siblings, not assume one global convention.

## 1.5 Identify build and test commands (from codebase)

For **each test project**, determine from the actual project manifest:
- Build the test project
- Run all tests
- Run filtered tests (single class/file)

If CLAUDE.md lists different commands, record the drift. Use codebase findings in generated files.

## 1.6 Identify architectural patterns

Note patterns affecting test writing:
- CQRS / mediator patterns
- Controller / route handler patterns
- Service layer patterns
- Event / message handling patterns
- Background job / worker patterns
- ORM / database access patterns
- Integration/component test infrastructure

## 1.6.1 Detect authorization and security patterns

For repos with API endpoints or boundary code where authorization matters, detect:
- **Authorization attributes / decorators / middleware**
- **Policy definitions** — what account types/claims they represent
- **Account type abstraction for tests** — how tests change current user's identity

Record a **policy → forbidden account types** mapping. Example:
```
OPERATIONS_ONLY_POLICY → Client and Vendor are Forbidden
CLIENT_OR_OPERATIONS_POLICY → only Vendor is Forbidden
```

This goes into `{type}-test-conventions.md` for integration-like types **when that file is generated** (manual full regeneration / legacy installs). **Slim default:** code-driven integration `{type}-test-conventions.md` is not generated, so the policy → forbidden map is **not separately cached** — integration writers derive auth / account-type setup from sibling tests (the integration writer agent already cross-references the auth table only "when present" and otherwise follows the sibling auth convention). Known minor loss: a brand-new area with no sibling lacks the consolidated map; a wrong account type then surfaces as a 401/403 at test-run time.

If no authorization layer, skip.

## 1.7 Classify test projects

For each test project, determine two independent dimensions.

### Infrastructure classification

- **Classification** — `unit-like`, `integration-like`, `hybrid`, or `component-like`
- **Classification basis** — evidence:
  - `unit-like` — all dependencies mocked; no containers, no DB, no real HTTP
  - `integration-like` — Testcontainers / real DB / real HTTP / `WebApplicationFactory` / equivalent
  - `hybrid` — areas of the same project follow different patterns
  - `component-like` — project contains `.feature` files **AND** step classes carrying `[Binding]` / `[Given]` / `[When]` / `[Then]` attributes (or framework equivalents — SpecFlow, Cucumber-JVM, behave, Gauge). Usually also carries integration-like infrastructure (containers, WebApplicationFactory), but the defining signal is the presence of a scenario framework with real step code, not pure Gherkin

**Gherkin-project detection procedure** (for recognising `component-like`):
1. Glob the repo for `**/*.feature` files. If none found, no project is `component-like`.
2. For each `.feature`-containing directory, walk up to the test project root. Glob the project for step-definition code — files with `[Binding]` (Reqnroll/SpecFlow), `@Given` / `@When` / `@Then` annotations (Cucumber-JVM), `@given` / `@when` / `@then` decorators (behave), or the framework-specific equivalent.
3. If both `.feature` files AND step-definition code are found in the same project → classify as `component-like`.
4. If `.feature` files exist but no step code is found (pure Gherkin / spec-only) → classify the `.feature`s as `config-driven` and mark the project 🟨 skip (no per-test-type generation).

### Authoring model

Determine whether the test entry point is code or non-code:

- **code-driven** — test entry points are code files with framework attributes or conventions (e.g., `[Fact]` / `[Theory]`, `describe` / `it`, `def test_`, `func Test`). This includes tests that use specialised strategies internally (property-based, snapshot, mutation) as long as the test structure is still code-driven.
- **config-driven** — test entry points are non-code files that drive execution (e.g., `.feature` files for Gherkin via Reqnroll / SpecFlow / Cucumber, `.pact` contract files, declarative YAML test suites). Code exists as glue (step definitions, contract verifiers) — it does not define the test structure.

### Supported combinations (combo-cell matrix)

Determine support status per project by the **combined** infrastructure × authoring cell — not by authoring alone:

| Infrastructure | Authoring | Supported? | Default type label |
|---|---|---|---|
| unit-like | code-driven | 🟩 yes | `unit` |
| integration-like | code-driven | 🟩 yes | `integration` |
| hybrid | code-driven | 🟩 yes | (user decides in Step 2.1) |
| **component-like** | **config-driven** | 🟩 yes | `component` |
| unit-like / integration-like / hybrid | config-driven | 🟨 skip | — (pure Pact, YAML-driven, etc. are not supported) |
| component-like | code-driven | 🟨 skip — unusual combination; ask user | — |

The `component-like × config-driven` cell is supported because Gherkin-hybrid projects carry real step code (via Reqnroll / SpecFlow / Cucumber / etc.) even though the entry point is `.feature`. Pure config-driven projects (Gherkin without step code, standalone Pact, YAML test suites) remain 🟨 skip because their execution model does not map to the per-type writer / verifier pattern.

### Full classification record

For each test project, record:
- **Test type label** — short identifier (e.g., `unit`, `integration`, `component`, `e2e`, `sync`)
- **Classification** — `unit-like`, `integration-like`, `hybrid`, or `component-like`
- **Authoring** — `code-driven` or `config-driven` (note what drives it, e.g., "Reqnroll/Gherkin", "Pact contracts")
- **Supported** — 🟩 yes or 🟨 skip (with reason)
- **Test infrastructure** — key base classes, fixtures, factories
- **Source mapping** — which source projects / layers map here; for component-like, note the feature-area structure (e.g., `Features/` + `Steps/<Area>/`) instead of source-class mirror
