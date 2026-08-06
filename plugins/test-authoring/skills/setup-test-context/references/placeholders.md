# Step 3.2/3.3 — Template Files (Placeholder Reference)

Read this file during Step 3.2 (subagent dispatch) and Step 3.3 (subagent prompt construction). It contains the full placeholder tables and per-type selection rules.

> **Scope note**: setup-test-context only writes `rules`, `shared`, and `conventions` per-repo. The tables below may include rows referencing `templates/commands/...` or `templates/agents/...` paths — those describe placeholder schemas for files now plugin-bundled. Treat those rows as reference for the placeholder schemas they define; the actual writes setup-test-context performs are limited to rules, shared, and conventions templates.

---

## Standard placeholders (most templates use these)

| Placeholder | Example values | Source |
|---|---|---|
| `{{LANGUAGE}}` | `C#`, `TypeScript`, `Python`, `Go` | Step 1.2 |
| `{{PROJECT_DESCRIPTION}}` | `the <repo name> project (<runtime>, <test framework>)` | derived from Step 1.2 + repo name |
| `{{SRC_DIR}}` | `src/`, `lib/`, `app/` | Step 1.3 |
| `{{TEST_DIR}}` | `tests/`, `__tests__/` | Step 1.3 |
| `{{SRC_GLOB}}` | `src/**/*.cs`, `src/**/*.ts` | Step 1.3 + Step 1.2 |
| `{{TEST_GLOB}}` | `tests/**/*.cs`, `__tests__/**/*.ts` | Step 1.3 + Step 1.2 |
| `{{TEST_TYPE}}` | `unit`, `integration` | per-type, Step 1.7 |
| `{{TEST_TYPE_TITLE}}` | `Unit`, `Integration` | Title-case of `{{TEST_TYPE}}` |
| `{{CONVENTIONS_SCHEMA_VERSION}}` | `1.0` | `<plugin-root>/resources/templates/template-schema-versions.json` field `conventions`. Used only in `tier3-schemas.md` dynamic conventions recipes; the same value is also written to manifest `files[].schema_version` for matching files (single source of truth). |

## No language baselines

The plugin ships **no per-language baseline files**, and no placeholder is filled from one. What a
repo's tests should look like — framework, mocking library, assertion style, naming, layout — comes
from that repo's own tests, or is reported as unknown.

Why, precisely:

- **A style baseline is an assumption about someone else's codebase.** The baselines this plugin used
  to ship stated one organisation's preferences (assertion library, comment casing, an `Async`-suffix
  rule, a package-name-to-folder prefix) as mandatory rules. Shipped to a repo that does not follow
  them, they present a convention the code contradicts as established.
- **Priming.** A style example visible while a subagent fills a template competes with the siblings it
  is supposed to be reading.

The line is between **style** and **mechanism**. Language and toolchain *mechanics* — how an access
grant is declared, where a runner's collection config lives, how a link-install resolves to a path —
are facts a sibling test can never reveal, because they live outside the test file. Those stay, written
language-neutrally as *what to check*, in `rules/sut-analysis.md`. What must not ship is a prescription
of how this repo's tests ought to look.

Concretely: templates carry no language-specific style example **in a `{{PLACEHOLDER}}` fill or its
HTML-comment guidance**. Illustrative syntax elsewhere in a rule's prose (naming a runner's skip
attribute, or a filter flag) is fine — it teaches the rule, it does not fill a value.

When observation yields nothing, the correct output is a **report**, not an inferred default — see
`rules/test-writer-rules.md` → Fallback Chain.

## File-specific placeholders

Templates are **per-type** (not `{{TEST_TYPE}}`-parameterised). Bootstrap copies the matching per-type template for each supported cell in the Step 1.7 combo matrix. Standard placeholders (`{{PROJECT_DESCRIPTION}}`, `{{SRC_DIR}}`, `{{TEST_DIR}}`, `{{SRC_GLOB}}`, `{{TEST_GLOB}}`) are substituted in every template.

### Always-generated shared files (independent of test types)

| Template | Destination | Special placeholders |
|---|---|---|
| `templates/shared/scope-resolution.md` | `.claude/shared/tests/scope-resolution.md` | (standard only) |
| `templates/rules/test-rules.md` | `.claude/rules/tests/test-rules.md` | `{{BUILD_AND_TEST_COMMANDS}}` — one section per test project from Step 1.5 |
| `templates/rules/test-writer-rules.md` | `.claude/rules/tests/test-writer-rules.md` | (standard only) |
| `templates/rules/fix-protocol.md` | `.claude/rules/tests/fix-protocol.md` | (standard only) |
| `templates/rules/sut-analysis.md` | `.claude/rules/tests/sut-analysis.md` | `{{KNOWN_PACKAGES_TABLE}}` — packages Step 1.2.1 detected, with the install model that located each and its verified local path; empty form if none |
| `templates/rules/common-orchestrator-flow.md` | `.claude/rules/tests/common-orchestrator-flow.md` | (standard only) |
| `templates/rules/common-writer-instructions.md` | `.claude/rules/tests/common-writer-instructions.md` | (standard only) |
| `templates/rules/common-update-instructions.md` | `.claude/rules/tests/common-update-instructions.md` | (standard only) |
| `templates/rules/common-verifier-checks.md` | `.claude/rules/tests/common-verifier-checks.md` | (standard only) |

### Code-driven per-type files — copy the matching per-type template when the corresponding combo cell is 🟩 supported

| Template | Destination | Copied when |
|---|---|---|
| `templates/commands/add-unit-test.md` | `.claude/commands/tests/add-unit-test.md` | `unit-like × code-driven` supported |
| `templates/commands/add-integration-test.md` | `.claude/commands/tests/add-integration-test.md` | `integration-like × code-driven` supported |
| `templates/commands/update-unit-test.md` | `.claude/commands/tests/update-unit-test.md` | `unit-like × code-driven` supported |
| `templates/commands/update-integration-test.md` | `.claude/commands/tests/update-integration-test.md` | `integration-like × code-driven` supported |
| `templates/agents/add-unit-test-agent.md` | `.claude/agents/tests/add-unit-test-agent.md` | same |
| `templates/agents/add-integration-test-agent.md` | `.claude/agents/tests/add-integration-test-agent.md` | same |
| `templates/agents/update-unit-test-agent.md` | `.claude/agents/tests/update-unit-test-agent.md` | same |
| `templates/agents/update-integration-test-agent.md` | `.claude/agents/tests/update-integration-test-agent.md` | same |
| `templates/agents/verify-add-unit-test-agent.md` | `.claude/agents/tests/verify-add-unit-test-agent.md` | same |
| `templates/agents/verify-add-integration-test-agent.md` | `.claude/agents/tests/verify-add-integration-test-agent.md` | same |
| `templates/agents/verify-update-unit-test-agent.md` | `.claude/agents/tests/verify-update-unit-test-agent.md` | same |
| `templates/agents/verify-update-integration-test-agent.md` | `.claude/agents/tests/verify-update-integration-test-agent.md` | same |

Hybrid types: if a test project is classified `hybrid × code-driven`, bootstrap asks the user (Step 2.1 confirmation) which type label to use and copies the corresponding per-type pair. Hybrid-specific detection happens at runtime inside the generated agent (sibling-based).

### Batch scanner

| Template | Destination | Special placeholders |
|---|---|---|
| `templates/commands/scan-test-gaps.md` | `.claude/commands/tests/scan-test-gaps.md` | `{{LANGUAGE_EXCLUSIONS}}`, `{{COVERAGE_EXCLUSION_HANDLING}}`, `{{TEST_TYPES_LIST}}` (must exclude Gherkin / config-driven projects — scan is unit + integration only), `{{HIGH_PRIORITY_CRITERIA}}`, `{{TEST_TYPES_COUNT_BREAKDOWN}}`, `{{EXAMPLE_TYPE_1}}`, `{{EXAMPLE_TYPE_2}}`. Uses `SINGLE_TYPE_ONLY` / `MULTI_TYPE_ONLY` HTML conditional blocks for single-type vs multi-type repos. |

## Per-type selection rules

- **Only copy a per-type template pair when that combo cell is 🟩 in Step 1.7.** A repo with only unit tests gets only the unit templates; a repo with unit + integration gets both tracks.
- **🟨 Skipped cells** (Gherkin `.feature` suites, standalone Pact, YAML suites): do NOT generate any per-type files for these. They still appear in the Step 2.1 confirmation table for visibility.
- **`SINGLE_TYPE_ONLY` / `MULTI_TYPE_ONLY` HTML conditional blocks** (scan-test-gaps only): when exactly ONE test type is supported (by scan's scope — unit or integration), keep `SINGLE_TYPE_ONLY` blocks and remove `MULTI_TYPE_ONLY` blocks. When ≥2, keep `MULTI_TYPE_ONLY` blocks and remove `SINGLE_TYPE_ONLY` blocks.

Remove HTML comments from the final output after substitution.
