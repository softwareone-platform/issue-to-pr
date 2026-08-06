# Step 1 Analysis — Detection Recipes

Read this file at the start of Step 1. It carries the detection recipe for each numbered sub-step Step 1 works through. The numbering is stable so other documents can cite it, which is why it has gaps.
Return to SKILL.md for Step 2 once analysis is complete.

---

## 1.1 Read existing context (hints only)

Read `CLAUDE.md` (if it exists) to gather **hints** about build/test commands, project structure, coding conventions, and test-related instructions.

Do NOT treat CLAUDE.md as authoritative. Record what it claims so drift can be compared against codebase findings in Step 2.1.

If no `CLAUDE.md` exists, inform the user and recommend running `/init` separately (not as part of this setup run), but continue with codebase-based analysis.

## 1.2 Detect language and frameworks (from codebase)

Determine from **actual files in the repo** (solution/project files, package manifests, test project references, import statements):
- **Primary language** (e.g., C#, TypeScript, Python, Go, Java)
- **Test framework** (e.g., xUnit, Jest, pytest, Go testing, JUnit)
- **Assertion library** (e.g., FluentAssertions, Chai, pytest assertions)
- **Mocking library/libraries** — note if different areas use different libraries
- **Build tool** (e.g., dotnet, npm, cargo, go, maven/gradle)
- **Package manager**

If CLAUDE.md claims different values, record the drift — use codebase findings.

## 1.3 Map project structure

Determine:
- **Source directories** (e.g., `src/`, `lib/`, `app/`)
- **Test directories** (e.g., `tests/`, `__tests__/`, `*_test.go`)
- **Source ↔ test mirroring pattern** — read 3–5 existing test files to understand directory mirroring and file naming
- **File organization pattern** — flat files (`FooTests.cs`) or subfolder-per-SUT (`FooTests/BarTest.cs`). Different areas may use different patterns — generated agents must detect and match sibling pattern, not assume a global default.
- **Test project separation** — list ALL test projects found. Do not assume a fixed number or naming convention.
- **Shared test utilities** — detect shared test projects (Tests.Common-style) that provide extensions, helpers, base classes, or custom assertions used across multiple test projects. Record its path and which test projects reference it — that pair is all `project-architecture.md` carries. Do **not** inventory the utilities themselves: a writer needs to know the project exists, then reads the one helper it needs from the sibling that already calls it. Repo-specific: may or may not exist.
- **Completeness check** — list ALL project directories under the source root. For each, find where its tests live. Flag non-obvious placements.
- **Mixed test project layouts** — if unit-style tests are found inside an integration test project (or vice versa), document explicitly. Generated agents must pick conventions based on sibling tests, not project name.

### Output format (when presented to user in §2.1)

Render the source layout as an **ASCII tree** with `├──`, `│`, `└──` connectors — not as nested bullets. Keep it compact: fold same-level siblings using **brace-expansion** notation (`{a,b,c}/`) rather than expanding each on its own line. Append short purpose notes after `#` on the same line for projects whose role is non-obvious from the name.

Render `File organisation` (test placement pattern + exceptions) as a flat bullet list following the tree — it is not hierarchical data.

The exact format and placeholder shape is specified in `SKILL.md` §2.1 under "Project structure". Do not bake any specific repo's project names into the format spec — placeholders are filled at presentation time from the analysis above.

## 1.4 Learn test conventions

### Layered sampling

This sampling feeds **one** consumer: the verification-pattern detection below, which writes `common-verification-patterns.md`. Per-file style dimensions (mocking approach, naming, AAA usage, assertion style) are deliberately **not** recorded — nothing generates a per-type conventions file to hold them, and the writer reads them off the nearest sibling at the moment it writes, which is always more current than a cache.

Use the architectural patterns detected in Step 1.6 to map each test file to a **layer** (Handler, Controller, Service, Repository, Consumer, Worker, etc. — use the repo's actual naming).

Sample tests in a **layered** fashion:
- Sample 2–3 files per `(layer, test type)` combination.
- Maintain a project-wide minimum of 8 files total.
- If a layer has fewer than 3 test files, record it but skip pattern detection for that layer (sample too small).
- If the repo has **no clear layers** (small project, single layer), fall back to project-wide sampling (3–5 files per test project).

### Verification pattern detection (for `common-verification-patterns.md`)

For each `(layer, test type)` bucket, extract all mock verification calls (`.Received()`, `.Verify()`, `expect(...).toHaveBeenCalled()` — language/framework-specific).

Compute frequency per `(layer, test type)`. Classify:
- **Layer common**: appears in ≥2 samples within the same layer (any count of test types) → will go into `common-verification-patterns.md` under that layer's section.
- **Cross-layer common**: appears across multiple layers → "General" section of `common-verification-patterns.md`.
- **Type-specific** (only in one test type, not layer-correlated) → **discard**. Nothing generates a per-type conventions file, so a type-specific pattern has nowhere to go — and it needs nowhere: the nearest sibling carries it to the writer at runtime. Only layer-common and cross-layer-common patterns feed `common-verification-patterns.md`.
- **Single-sample occurrences** → discard (noise).

Fallback for no-layer repos: project-wide, >50% of samples (≥5/8) → `common-verification-patterns.md` general section.

For each qualifying pattern record: observed frequency per bucket, pattern code (extracted from an actual sibling test — not invented), applicable dependency/context.

**Important**: note if different areas use different conventions. Generated agents must learn from siblings, not assume one global convention.

## 1.6 Identify architectural patterns

Note patterns affecting test writing:
- CQRS / mediator patterns
- Controller / route handler patterns
- Service layer patterns
- Event / message handling patterns
- Background job / worker patterns
- ORM / database access patterns
- Integration test infrastructure

## 1.7 Classify test projects

For each test project, determine two independent dimensions.

### Infrastructure classification

- **Classification** — `unit-like`, `integration-like`, or `hybrid`
- **Classification basis** — evidence:
  - `unit-like` — all dependencies mocked; no containers, no DB, no real HTTP
  - `integration-like` — Testcontainers / real DB / real HTTP / `WebApplicationFactory` / equivalent
  - `hybrid` — areas of the same project follow different patterns

**Gherkin-project detection procedure** (feeds the authoring model below, not this classification):
1. Glob the repo for `**/*.feature` files. If none found, no project is Gherkin-driven.
2. For each `.feature`-containing directory, walk up to the test project root. Glob the project for step-definition code — files with `[Binding]` (Reqnroll/SpecFlow), `@Given` / `@When` / `@Then` annotations (Cucumber-JVM), `@given` / `@when` / `@then` decorators (behave), or the framework-specific equivalent.
3. A project whose test entry points are `.feature` files is **config-driven** — with or without step code — which makes it 🟨 skip in the matrix below. This plugin does not author Gherkin scenarios.

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
| unit-like / integration-like / hybrid | config-driven | 🟨 skip | — (Gherkin `.feature` suites, standalone Pact, YAML-driven, etc. are not supported) |

Config-driven projects are 🟨 skip because their execution model does not map to the per-type writer / verifier pattern — the unit of authoring is a scenario in a non-code file, not a test method mirroring a source class. **Classify by entry point, not by fixtures**: a Gherkin project usually carries integration-like infrastructure (containers, `WebApplicationFactory`), so reading its fixtures alone would wrongly admit it as an integration target.

**No 🟩 project at all** — zero supported types is a reachable outcome (a repo whose only test project is Gherkin-driven, or one with no test project at all). Step 2.1 enforces the exit; record which projects were skipped and why so it can report them.

### Full classification record

For each test project, record:
- **Test type label** — short identifier (e.g., `unit`, `integration`, `e2e`, `sync`)
- **Classification** — `unit-like`, `integration-like`, or `hybrid`
- **Authoring** — `code-driven` or `config-driven` (note what drives it, e.g., "Reqnroll/Gherkin", "Pact contracts")
- **Supported** — 🟩 yes or 🟨 skip (with reason)
- **Test infrastructure** — key base classes, fixtures, factories
- **Source mapping** — which source projects / layers map here
