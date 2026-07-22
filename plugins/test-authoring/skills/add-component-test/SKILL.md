---
name: add-component-test
expected_schema_version: "1.0"
expected_rules_schema_version: "2.1"
description: >
  Generate a component (Gherkin/scenario) test for a specific feature area and scenario title. Trigger phrases: "add component test for <Area>: <Scenario>", "create scenario for X workflow". Do NOT trigger for: discussions about component test infrastructure, scenario design philosophy, or step-class organisation.
---


## Step -1 — Resolve context source (fast path vs cacheless)

This skill runs **with or without** a prior `setup-test-context`. First resolve where rules/conventions come from, then proceed.

**Resolve the plugin templates root once** — you pass it to every subagent, because subagents cannot resolve it themselves. The bundled templates sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`): on the **cacheless path** (where it is load-bearing) resolve it at runtime — run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool, and if `$CLAUDE_SKILL_DIR` is empty, ask the user for the `test-authoring` plugin install path. On the **fast path** its only use is Step 7's status icons — do **not** prompt; if it stays unresolved, fall back to plain status labels there (R4). The Read tool normalises the `../..` segments.

Then check `.claude/conventions/tests/project-architecture.md`:

- **Exists → fast path.** A prior setup cached per-repo files. Compare its `schema_version` **major** against this skill's `expected_schema_version`: same major → continue silently; major differs or key missing → warn `"Conventions schema major <found> differs from <expected>. Run /test-authoring:setup-test-context to refresh."` and continue best-effort (may-be-stale). **Resolve, do not bulk-read**: every `.claude/{conventions,rules,shared}/tests/<f>` reference below resolves to the repo file — read each file lazily, at the first step that uses it (see "Orchestrator reading list" below). **Per-file fallback still applies at read time**: any individual file that is absent falls through to the cacheless source below — a missing file is never fatal.
- **Absent → cacheless.** setup has never run. **Do NOT stop.** Announce once: `"No precomputed test conventions found — running cacheless (sibling-driven). Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then for the rest of the flow:
  - Resolve every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` reference to `<PLUGIN_TEMPLATES>/{rules,shared}/<f>` instead (includes `test-component-rules.md`) — same lazy rule: read at the step that uses it, never as an upfront batch. Cosmetic frontmatter/example tokens are inert when read explicitly.
  - Treat `.claude/conventions/tests/<f>` as **optional**: prefer the nearest sibling `.feature` / step class for the area (the writer's top-priority source anyway); fall back to `<PLUGIN_TEMPLATES>/lang/<derived>/` fragments for the language baseline. Discover `{{FEATURES_DIR}}`/`{{STEPS_DIR}}`/`{{SCENARIO_FRAMEWORK}}` per the "Placeholder resolution" note below.
  - **Detect once, reuse this session**: the language, and the *executable* component build + feature-run invocation. In cacheless mode the component commands `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` in `test-component-rules.md` are unfilled — derive them from `<PLUGIN_TEMPLATES>/lang/<derived>/component-build-commands.md` (which still carries `<project>`/`<FeatureName>` placeholders to substitute from the detected test project + target feature). The detected commands replace those tokens everywhere (writer build/feature-run, verifier U4, orchestrator Step 4). Pass them to subagents as `build_test_command` — a **set**, not one string: the build command, the feature-filter run form, and the fully-qualified-name filter fallback (used when a name-based filter returns zero matches, per `test-component-rules.md`).

Resolve `common-orchestrator-flow.md` the same way: fast path reads `.claude/rules/tests/common-orchestrator-flow.md` (same schema-major check against `expected_rules_schema_version`); cacheless reads `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `common-orchestrator-flow.md` (previous paragraph), then `.claude/conventions/tests/component-test-conventions.md` + `.claude/conventions/tests/project-architecture.md` — the "Placeholder resolution" note below needs both before Step 1 (cacheless: token discovery per that note, no read).
- **At the step that uses it**: Step 2.5 → `.claude/conventions/tests/fixture-capabilities.md`. Step 4 → `.claude/rules/tests/test-rules.md` plus the build-command and "Iteration rule" sections of `.claude/rules/tests/test-component-rules.md` (cacheless: the session-detected `build_test_command` set replaces the unfilled tokens). First verifier finding or attributable build/feature-run failure → `.claude/rules/tests/fix-protocol.md`. A writer stopping on missing framework source → `.claude/rules/tests/sut-analysis.md` → "Runtime resolution flow".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, `common-update-instructions.md`, and the writer/verifier body of `test-component-rules.md` beyond the two sections above. They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Add Component Test

You are the orchestrator for component ({{SCENARIO_FRAMEWORK}}/Gherkin) test generation. Your job is to **resolve scope**, **pre-fetch sibling context**, and then **delegate** scenario writing to the `test-authoring:add-component-test-agent` subagent, then verify via `test-authoring:verify-add-component-test-agent`.

> **Scope is explicit only (Mode B).** Component tests do not map 1:1 to source files — a single source change can map to many scenarios, none, or live in any of several `.feature` areas. The user must name the area and scenario. There is no Mode A (git diff) for component tests.

> **Placeholder resolution (plugin-bundled file)**: tokens like `{{SCENARIO_FRAMEWORK}}`, `{{FEATURES_DIR}}`, `{{STEPS_DIR}}` in this skill are NOT pre-filled — this file ships with the plugin, not generated per-repo. Resolve each token at runtime from the per-repo conventions: `.claude/conventions/tests/component-test-conventions.md` (framework, feature/steps layout) and `.claude/conventions/tests/project-architecture.md` (directory trees). Never glob or reference a `{{...}}` token literally — a literal glob returns zero matches and falsely reads as "feature does not exist".
>
> **Cacheless (R5 — those conventions docs are absent):** discover the tokens directly — `{{FEATURES_DIR}}` by globbing `**/*.feature` and taking their common root; `{{STEPS_DIR}}` from the folder holding a sibling step/binding class near those `.feature` files; `{{SCENARIO_FRAMEWORK}}` from that step class's binding attribute/runner or the test project's package reference (NOT the `.feature` Gherkin, which is framework-agnostic). If the glob finds multiple feature roots or none, ask the user rather than guess. Every other `.claude/{conventions,rules,shared}/tests/…` read follows **Step -1's resolution** (repo on fast path, `<PLUGIN_TEMPLATES>` on cacheless) — and happens lazily, at the step that uses it, never as an upfront batch; a body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. On the cacheless path you pass `plugin_resources_path` + `build_test_command` into every subagent prompt — they cannot resolve these themselves.

## Step 1 — Identify Scope (Mode B only)

The user invokes this skill with an explicit scope. Accepted forms:

- `/test-authoring:add-component-test <Area>: <Scenario title>` — area + scenario name (preferred)
- `/test-authoring:add-component-test <Area>` — area only; ask the user for the scenario title before proceeding
- `/test-authoring:add-component-test` — no argument; ask the user for both area and scenario title

**Ask the user, do not infer**, if either the area or the scenario title is missing. Do not run `git diff` to guess scope — Mode A is intentionally not supported for component tests.

### Resolve "area" to feature/steps paths

Use the path mapping in `.claude/conventions/tests/component-test-conventions.md` ("Source → feature/steps path derivation rules") — **cacheless:** that doc is absent, so use the R5 token discovery from the Placeholder-resolution note above (grep the discovered `{{FEATURES_DIR}}`/`{{STEPS_DIR}}`):

1. Grep `{{FEATURES_DIR}}` for a `.feature` whose name matches the area.
2. Grep `{{STEPS_DIR}}` for a folder whose name matches the area.
3. Decide:
   - **Existing area** — both grep results found something. Plan: append a scenario to the existing `.feature` and any new step variants to the existing step files.
   - **New area** — neither found. Plan: create a new `.feature` + a new `{{STEPS_DIR}}/<Area>/` folder with the canonical step classes (see `component-test-conventions.md` → step-class split).
   - **Partial** (one found, the other not) — unusual; ask the user to clarify before proceeding.

## Step 2 — Pre-fetch Context

Before spawning the writer, pre-fetch sibling context to reduce agent exploration time:

1. **Nearest `.feature` sibling**:
   - Existing area → the existing `{{FEATURES_DIR}}/<Area>.feature`.
   - New area → the closest related `.feature` (per `.claude/conventions/tests/component-test-conventions.md` "Learn from siblings" priority).
2. **Nearest `{{STEPS_DIR}}/<Area>/` sibling**:
   - Existing area → the existing `{{STEPS_DIR}}/<Area>/` folder.
   - New area → the closest related `{{STEPS_DIR}}/<OtherArea>/` folder.
3. Read the siblings and extract the **convention spec** using the format in `.claude/conventions/tests/component-test-conventions.md`.
4. **Inventory existing step phrasings** — grep `{{STEPS_DIR}}/<Area>/` (or all of `{{STEPS_DIR}}/` for a new area) for `[Given(@"…")]` / `[When(@"…")]` / `[Then(@"…")]` strings (or framework equivalents) whose phrasing might be reusable for this scenario. Record them as candidate `reused_steps`.

## Step 2.5 — Pre-flight Fixture Capability Check

**Runtime guard:** if `.claude/conventions/tests/fixture-capabilities.md` does not exist (no fixture class was detected at setup time), skip this whole step — the writer falls back to the no-fixture path. (**Cacheless:** this file is always absent, so this step skips here by the guard; the writer still re-checks the actual fixture source — the authoritative wiring state — per the note at the end of this step, which needs no cached doc.)

Before delegating to the writer, read `.claude/conventions/tests/fixture-capabilities.md` and make an early judgement about whether the scenario can be verified with the fixture's current substitutes.

Reason about the action under test and map each observable side-effect to a substitute, using the categories documented in the fixture's _Substitutes wired today_ section. Examples of the reasoning shape (actual substitutes depend on the fixture's catalog):

- **HTTP endpoint** → the API response is always observable; no fixture gap for response assertions.
- **Message consumer writing to DB** → the DB context exposed by the fixture is always observable.
- **Message consumer publishing via a test-harnessed bus** → the harness captures published messages with a scenario-scoped filter.
- **Message consumer dispatching to an external service (email, push, webhook, …)** → must have a corresponding fake listed in `fixture-capabilities.md`. If not listed, flag a fixture gap.
- **External HTTP API call** → the HTTP mock observability (e.g., WireMock) is always available.

If a fixture gap is identified, do NOT stop to ask — apply the default automatically and record it:

1. **Default to `proceed-pure-computation`** — instruct the writer (via its prompt) to assert only the observable behaviour and skip the side-effect that has no substitute. Do NOT auto-extend the fixture: building a missing fake / wiring is a test-infrastructure change that must not happen silently.
2. **If pure-computation would leave nothing meaningful to assert** (the scenario's whole point is the unverifiable side-effect), skip generating that scenario rather than produce a hollow test.
3. **Report the gap in the summary** — which substitute is missing, what the user could add (`extend-fixture`) to cover it, and whether the scenario was narrowed or skipped — so the user can act later.

The pre-flight judgement is an **acceleration hint, not the final word** — the writer re-checks the fixture source (the authoritative wiring state) and may find a gap the pre-flight missed. If the writer returns a fixture-gap report instead of a scenario, apply the same defaults (re-spawn the writer with a `proceed-pure-computation` instruction, or skip when nothing meaningful would remain to assert) and report the gap in the summary — the writer's return is not a failure.

If no gap is identified, continue directly to Step 3.

## Step 3 — Delegate to Writer Agent

Use the **Agent tool** to spawn `test-authoring:add-component-test-agent` with the resolved scope, the append-vs-new decision, and the pre-fetched context.

**One agent per scenario.** Component tests are slow to iterate (container startup, sequential scenario runner); concurrency is not useful here. If the user requested multiple scenarios in one invocation, run Steps 3–6 as a loop per scenario (write → build & feature run → verify → handle findings) before starting the next — one verifier per writer invocation, matching `update-component-test` Step 6b.

```
Agent(subagent_type="test-authoring:add-component-test-agent"):
  Generate a component test scenario:
  - Area: <AreaName>
  - Scenario title: <"Subject verb object">
  - Plan: <append-to-existing | new-feature-and-steps>
  - Target feature file: <path or "to-be-created at {{FEATURES_DIR}}/<Area>.feature">
  - Target steps folder: <path or "to-be-created at {{STEPS_DIR}}/<Area>/">

  Pre-fetched context (acceleration hint — if sibling differs, agent follows sibling):
    Feature sibling: <path>
    Steps sibling folder: <path>
    Convention spec observed:
      <fields per convention spec>
    Candidate reusable steps:
    - <attribute string>: <existing class:method>
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build command + feature-filter run form + FQN-filter fallback — not a single string>
```

## Step 4 — Verify Build

After the writer completes, run a focused build to catch any compile issues across feature/step files. Reference `.claude/rules/tests/test-rules.md` (common) and `.claude/rules/tests/test-component-rules.md` (component-specific) for the exact command (cacheless: use the session-detected `build_test_command` — the component build + feature-run invocation — not the unfilled `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` tokens).

After a successful build, also run the **target feature** (not just the new scenario). See `.claude/rules/tests/test-component-rules.md` → "Iteration rule". Running only the new scenario may hide cross-scenario isolation bugs that break previously-passing sibling scenarios — especially for `append-to-existing` plans.

If the build or the feature run fails after the writer reported success — including a sibling scenario broken by the append — route the failure to the writer as a deterministic finding via the `fix_invocation` protocol in `.claude/rules/tests/fix-protocol.md` (counting toward the lineage's circuit breaker) before proceeding to Step 5.

## Step 5 — Review via Verify Agent

After the writer completes (and build succeeds), spawn **one** `test-authoring:verify-add-component-test-agent` to independently review the generated scenario.

```
Agent(subagent_type="test-authoring:verify-add-component-test-agent"):
  Review the component test scenario generated by the writer agent.
  Test type: component
  Original task: <the area + scenario title and plan as given to the writer — required by the verifier's U2b divergence cross-check>
  Pre-writer source snapshot: <the source diff state recorded before the writer was spawned — baseline for the U3 SUT-modification check>
  Cacheless context (include ONLY on the cacheless path — omit on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build command + feature-filter run form + FQN-filter fallback — not a single string>

  Writer output:
  - files_created: <feature path>, <new step files (if any)>
  - files_modified: <existing step files (if any)>
  - feature_sibling_referenced: <path>
  - steps_sibling_referenced: <path>
  - convention_spec_observed:
      <…>
  - reused_steps:
    - <attribute string>: <existing class:method>
  - new_steps_added:
    - <attribute string>: <new class:method>
  - scenario_name: <scenario title>
  - assertion_mode: <real-behaviour | pure-computation-only>
  - test_results:
    - <ScenarioName>: passed | failed (<reason>) | env_failure (<reason>)
  - spec_vs_impl_divergence: <writer's entries verbatim, or "none">
  - build_status: <success | failed (<errors>), verbatim from the writer>
```

Every field is filled from the writer's structured return — never assume a happy-path value the writer did not report.

**Always spawn the verifier** — quality control must not be bypassed.

## Step 6 — Handle Verifier Findings

Follow the **Verifier Fix Protocol** in `.claude/rules/tests/fix-protocol.md` and the role boundary in `.claude/rules/tests/common-orchestrator-flow.md`:

- **Deterministic** (convention violations, build/test failures, step-class placement, step duplication, Gherkin-shape violations) → fresh-spawn `test-authoring:add-component-test-agent` via `Agent` with a `fix_invocation` block. Circuit-breaker limits per `.claude/rules/tests/fix-protocol.md` — the single source of truth for the counters; on circuit break report as 🟥 unresolved.
- **Non-deterministic** (anti-gaming violations, scenario quality flags, `spec_vs_impl_divergence`, env_failure) → present to the user. If the user approves a fix for a quality flag or anti-gaming finding, route via the same fresh-spawn `fix_invocation` block with `findings_to_fix.user_approved_actions` populated. For `spec_vs_impl_divergence` the user decides whether the SUT is buggy or the requested scenario intent is stale — the writer skipped that scenario; re-run after the user's call. `env_failure` is informational only — the writer cannot fix infrastructure.

The orchestrator MUST NOT invoke `Write` / `Edit` / `MultiEdit` directly. All edits go through the writer.

## Step 7 — Summary

Collect results from the writer and the verifier, and provide a brief summary:

- Area and plan (append vs. new)
- Feature/steps siblings referenced (and what style was adopted)
- Files created / modified
- Scenario name added
- Step phrasings reused vs. new step methods added
- Assertion mode declared (`real-behaviour` or `pure-computation-only`)
- Convention violations found and fixes applied (if any)
- Anti-gaming violations found (if any) — present to user
- 🟪 Quality flags raised by verifier (if any) — present these for the user to judge
- Pass/fail of the new scenario

### Status per file

For each feature/step file, report a status using the icons defined in the plugin's `resources/static/status-legend.md` (= `<PLUGIN_TEMPLATES>/../static/status-legend.md`, resolved in Step -1; plugin-internal controlled vocabulary). If `PLUGIN_TEMPLATES` is unresolved (fast-path injection failure), use plain text status labels rather than prompting.


## Out of scope

- **Mode A (git-diff)** — not supported. Source-to-feature mapping is fuzzy for component tests.
- **Multiple scenarios per invocation** — supported but spawned sequentially, not in parallel.
- **Updating existing scenarios** — covered by `update-component-test`.


