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

## Language fragments

Language-specific baselines for placeholder fills live under `resources/templates/lang/<derived-dir>/`. The orchestrator (Step 3.3) derives the directory name from the detected `{{LANGUAGE}}` via the rule below, probes the filesystem for that directory, and — if it exists — passes the relevant fragment file paths to the subagent. If the directory or a specific fragment is missing, the orchestrator passes a degradation sentinel so the subagent falls back to Step 1 analysis only. This is **open by default** — adding a language is purely a `lang/<derived-dir>/` filesystem addition; no edit to this document or to skill code.

### Directory name derivation rule

The orchestrator computes the fragment directory name from `{{LANGUAGE}}` by applying these substitutions, in order:

1. Lowercase the string.
2. Replace `#` with `sharp` (so `C#` → `csharp`, `F#` → `fsharp`).
3. Replace `++` with `pp` (so `C++` → `cpp`).
4. Remove whitespace and hyphens.

Examples: `C#` → `csharp`, `Python` → `python`, `TypeScript` → `typescript`, `Go` → `go`, `Java` → `java`, `JavaScript` → `javascript`, `Rust` → `rust`, `Kotlin` → `kotlin`.

### Probe-based discovery

After deriving the directory name, the orchestrator probes `<plugin-root>/resources/templates/lang/<derived-dir>/`:

- **Directory exists** → resolve absolute paths to the fragment files relevant to each spawned subagent's owned templates (see § Placeholder → fragment mapping below), and pass them in the subagent prompt (`references/subagent-contract.md` item 10).
- **Directory does not exist** → emit a Step 2.1 informational notice (`"Language <lang>: no fragments under lang/<derived-dir>/ — subagents will rely on Step 1 analysis observations only"`) and, in subagent prompts, pass the literal sentinel `"(no fragment available for <lang>; rely on Step 1 analysis only)"` in place of each fragment path. The subagent treats the sentinel as "no baseline — write the placeholder from Step 1 analysis alone".
- **Directory exists but a specific fragment file is missing** (partial coverage) → pass the sentinel for that specific file only; other fragments in the same directory still flow normally.

### Placeholder → fragment mapping

Each fragment file provides the language-specific baseline for one or more placeholders. Fragment **file names** are fixed across languages (so the probe is uniform); the **directory** carries the per-language content. The owning subagent reads only the fragments relevant to the templates it owns (see `references/subagent-contract.md` § Subagent kinds for ownership).

| Placeholder(s) | Fragment file name | Owning subagent | Template |
|---|---|---|---|
| `{{PROJECT_WIDE_RULES}}` | `project-wide-rules.md` | shared-tier2 | `rules/test-rules.md` |
| `{{VISIBILITY_NOTE}}` | `visibility-note.md` | shared-tier2 | `rules/sut-analysis.md` |
| `{{KNOWN_PACKAGES_TABLE}}` (and naming-convention prose preceding it) | `known-packages-naming.md` | shared-tier2 | `rules/sut-analysis.md` |
| `{{BUILD_COMMAND}}`, `{{TEST_COMMAND_ALL}}`, `{{TEST_COMMAND_FEATURE_FILTER}}`, `{{TEST_COMMAND_SCENARIO_FILTER}}` | `component-build-commands.md` | component subagent | `rules/test-component-rules.md` |

### Adding a language

1. Derive the directory name per the rule above (e.g., `Python` → `python`).
2. Create `resources/templates/lang/<derived-dir>/` with the fragment files that apply to your case. The `lang/csharp/` directory is the canonical reference for fragment shape and frontmatter.
3. Partial coverage is fine — ship only the fragments where the language baseline differs meaningfully from "let the writer infer from siblings". Missing fragments degrade per the sentinel rule above.

**Size guideline**: keep each fragment terse — ideally under 50 lines. Fragments are language-specific *baselines*, not exhaustive style guides. If content is growing past that, ask whether it belongs in:

- the Tier 3 sampler logic (`references/tier3-schemas.md`), which generates per-repo conventions from sibling code, or
- the per-repo conventions file itself (regenerated from observation at each setup-test-context run).

The baseline answers "what does the language bring to the table by default"; sibling observation overrides it.

No template changes required, no edit to this document required — the HTML-comment guidance in `rules/*.md` already routes through the language fragment via the derivation-and-probe mechanism, and the orchestrator picks up the new directory on next setup-test-context run.

### Why language-specific examples must not be inlined in templates

Templates carry no language-specific examples in HTML comments — fragments under `lang/<derived-dir>/` are the single dispatch point. Two reasons:

- **N-place update risk**: adding a new language would require remembering to update every template that has an inline example. Miss one and the subagent receives an inconsistent baseline (fragment says one thing, template comment says another).
- **Subagent priming**: when the subagent reads the template, any inline language example becomes an in-context prior. Even with the fragment supplied, the subagent biases toward whatever language is most visible in the template prose. Keeping templates language-neutral keeps the fragment as the sole source of language signal.

When a new language-varying placeholder appears, add its fragment file name to § Placeholder → fragment mapping above, extract the example to `lang/<derived-dir>/<concern>.md`, and update the template's HTML comment to point at it (no inline example).

## File-specific placeholders

Templates are **per-type** (not `{{TEST_TYPE}}`-parameterised). Bootstrap copies the matching per-type template for each supported cell in the Step 1.7 combo matrix. Standard placeholders (`{{PROJECT_DESCRIPTION}}`, `{{SRC_DIR}}`, `{{TEST_DIR}}`, `{{SRC_GLOB}}`, `{{TEST_GLOB}}`) are substituted in every template.

### Always-generated shared files (independent of test types)

| Template | Destination | Special placeholders |
|---|---|---|
| `templates/shared/scope-resolution.md` | `.claude/shared/tests/scope-resolution.md` | (standard only) |
| `templates/rules/test-rules.md` | `.claude/rules/tests/test-rules.md` | `{{PROJECT_WIDE_RULES}}` — bullet list from Step 1.4; `{{BUILD_AND_TEST_COMMANDS}}` — one section per test project from Step 1.5 |
| `templates/rules/test-writer-rules.md` | `.claude/rules/tests/test-writer-rules.md` | (standard only) |
| `templates/rules/fix-protocol.md` | `.claude/rules/tests/fix-protocol.md` | (standard only) |
| `templates/rules/sut-analysis.md` | `.claude/rules/tests/sut-analysis.md` | `{{VISIBILITY_NOTE}}` — language-appropriate visibility check; `{{KNOWN_PACKAGES_TABLE}}` — table from Step 1.2.1 |
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

### Component-track files — copy when `component-like × config-driven` is 🟩 supported

| Template | Destination | Component-specific placeholders |
|---|---|---|
| `templates/commands/add-component-test.md` | `.claude/commands/tests/add-component-test.md` | `{{SCENARIO_FRAMEWORK}}`, `{{COMPONENT_TEST_PROJECT_PATH}}`, `{{FEATURES_DIR}}`, `{{STEPS_DIR}}` |
| `templates/agents/add-component-test-agent.md` | `.claude/agents/tests/add-component-test-agent.md` | `{{SCENARIO_FRAMEWORK}}`, `{{MODULE_NAME}}`, `{{STACK_LIST}}`, `{{COMPONENT_TEST_PROJECT_PATH}}`, `{{FEATURES_DIR}}`, `{{STEPS_DIR}}` |
| `templates/agents/verify-add-component-test-agent.md` | `.claude/agents/tests/verify-add-component-test-agent.md` | `{{SCENARIO_FRAMEWORK}}`, `{{MODULE_NAME}}`, `{{STACK_LIST}}`, `{{STEPS_DIR}}` |
| `templates/commands/update-component-test.md` | `.claude/commands/tests/update-component-test.md` | `{{SCENARIO_FRAMEWORK}}`, `{{COMPONENT_TEST_PROJECT_PATH}}`, `{{FEATURES_DIR}}`, `{{STEPS_DIR}}` |
| `templates/agents/update-component-test-agent.md` | `.claude/agents/tests/update-component-test-agent.md` | `{{SCENARIO_FRAMEWORK}}`, `{{MODULE_NAME}}`, `{{STACK_LIST}}`, `{{COMPONENT_TEST_PROJECT_PATH}}`, `{{FEATURES_DIR}}`, `{{STEPS_DIR}}` |
| `templates/agents/verify-update-component-test-agent.md` | `.claude/agents/tests/verify-update-component-test-agent.md` | `{{MODULE_NAME}}`, `{{STACK_LIST}}`, `{{SCENARIO_FRAMEWORK}}`, `{{COMPONENT_TEST_PROJECT_PATH}}`, `{{STEPS_DIR}}` |
| `templates/rules/test-component-rules.md` | `.claude/rules/tests/test-component-rules.md` | `{{SCENARIO_FRAMEWORK}}`, `{{INFRA_PREREQUISITE}}`, `{{COMPONENT_TEST_PROJECT_PATH}}`, `{{SOURCE_EXT}}`, `{{STEPS_DIR}}`, `{{TOOLING_TABLE_EXTRA}}`, `{{STEP_CLASS_SPLIT_TABLE}}`, `{{INFRA_PREREQUISITE_NOTE}}`, `{{BUILD_COMMAND}}`, `{{TEST_COMMAND_ALL}}`, `{{TEST_COMMAND_FEATURE_FILTER}}`, `{{TEST_COMMAND_SCENARIO_FILTER}}` |
| `templates/conventions/component-test-conventions.md` | `.claude/conventions/tests/component-test-conventions.md` | Methodology sections verbatim; example / derivation sections + sibling checklist "Typical values" columns filled from Step 3.5 convention-checklist sampler |

### Fixture catalog — copy + fill only if a fixture class was detected in Step 1.7

| Template | Destination | Fill condition |
|---|---|---|
| `templates/conventions/fixture-capabilities.md` | `.claude/conventions/tests/fixture-capabilities.md` | Only when fixture class detected; catalog sections filled by Step 3.5 generator. If no fixture class detected, do NOT generate this file and warn in Step 2.1. |

### Batch scanner

| Template | Destination | Special placeholders |
|---|---|---|
| `templates/commands/scan-test-gaps.md` | `.claude/commands/tests/scan-test-gaps.md` | `{{LANGUAGE_EXCLUSIONS}}`, `{{COVERAGE_EXCLUSION_HANDLING}}`, `{{TEST_TYPES_LIST}}` (must exclude `component` — scan is unit + integration only), `{{HIGH_PRIORITY_CRITERIA}}`, `{{TEST_TYPES_COUNT_BREAKDOWN}}`, `{{EXAMPLE_TYPE_1}}`, `{{EXAMPLE_TYPE_2}}`. Uses `SINGLE_TYPE_ONLY` / `MULTI_TYPE_ONLY` HTML conditional blocks for single-type vs multi-type repos. |

## Per-type selection rules

- **Only copy a per-type template pair when that combo cell is 🟩 in Step 1.7.** A repo with only unit tests gets only the unit templates; a repo with unit + integration + component gets all three tracks.
- **🟨 Skipped cells** (pure Gherkin without step code, pure Pact, YAML suites, `component-like × code-driven` outliers): do NOT generate any per-type files for these. They still appear in the Step 2.1 confirmation table for visibility.
- **`SINGLE_TYPE_ONLY` / `MULTI_TYPE_ONLY` HTML conditional blocks** (scan-test-gaps only): when exactly ONE test type is supported (by scan's scope — unit or integration), keep `SINGLE_TYPE_ONLY` blocks and remove `MULTI_TYPE_ONLY` blocks. When ≥2, keep `MULTI_TYPE_ONLY` blocks and remove `SINGLE_TYPE_ONLY` blocks. Component does not count toward this.

Remove HTML comments from the final output after substitution.
