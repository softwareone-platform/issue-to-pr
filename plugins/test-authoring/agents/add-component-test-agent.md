---
name: add-component-test-agent
expected_schema_version: "1.0"
description: >
  Subagent that generates a single {{SCENARIO_FRAMEWORK}}/Gherkin component test scenario for the
  {{COMPONENT_TEST_PROJECT_PATH}} project. Receives an explicit area + scenario title,
  finds the nearest .feature and {{STEPS_DIR}}/<Area>/ siblings, learns local conventions,
  reuses existing step phrasings before writing new ones, writes the scenario
  (and any new step methods), and returns a structured result.
  Called by add-component-test skill.
---

## Schema check (run before any other step)

Read `.claude/conventions/tests/project-architecture.md` frontmatter. Extract `schema_version` and compare its **major** component against the major of this agent's `expected_schema_version` (declared in this file's frontmatter).

- **Same major** (e.g. file `1.1` vs expected `1.0`) → continue silently. Minor bumps are additive and backward-compatible by contract, so they do not warrant a warning.
- **Major differs** (e.g. file `2.0` vs expected `1.x`) → emit a warning to the orchestrator's spawning prompt: `"Conventions schema_version <found> is a different major version than <expected> expected by test-authoring:<agent-name>. Ask user to run /test-authoring:setup-test-context to refresh."` Continue best-effort. Do NOT abort; the orchestrator decides whether to proceed.
- **Missing** → if your spawning prompt includes `plugin_resources_path` (cacheless mode — setup never ran), this is **expected, not an error**: do not warn, and resolve files per "Path resolution" below. Otherwise emit the same warning (cannot confirm compatibility).

This check is cheap (single file read) and prevents silent drift after plugin upgrades.

---

## Path resolution (cacheless-aware — governs every file reference below)

Your spawning prompt may include `plugin_resources_path` and `build_test_command`; the orchestrator sets these when the repo has no precomputed conventions ("cacheless mode"). Resolve every `.claude/…` reference in this agent and in the rule files it points to accordingly:

- **`plugin_resources_path` present (cacheless):** read every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` from `<plugin_resources_path>/{rules,shared}/<f>` instead (includes `test-component-rules.md`). Treat every `.claude/conventions/tests/<f>` as **optional** — your top-priority source is the nearest sibling `.feature` + step/binding class (per context priority in `test-writer-rules.md`). Resolve the plugin-file tokens from siblings, not the absent conventions docs: `{{FEATURES_DIR}}`/`{{STEPS_DIR}}` from the sibling paths the orchestrator passed (or glob `**/*.feature` + the binding-class folder); `{{SCENARIO_FRAMEWORK}}` from the sibling step class's binding attribute/runner; `{{FIXTURE_SOURCE_PATH}}` by locating the fixture / test-host class the sibling step classes use — there is no `fixture-capabilities.md` to name it, so find it from a sibling and read that source as the authoritative wiring check. When neither a convention doc nor a sibling exists, fall back to `<plugin_resources_path>/lang/<derived>/` fragments for the language baseline (probe `lang/` subdirs; partial baseline only). For build/run, use `build_test_command` as the base invocation — adjust its filter to the target feature/class; do **not** use the `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` tokens in `test-component-rules.md` (unfilled in cacheless mode). You cannot resolve `${CLAUDE_SKILL_DIR}` yourself; rely solely on the absolute `plugin_resources_path` passed in.
- **Absent (fast path):** read all `.claude/{conventions,rules,shared}/tests/<f>` from the repo as written below.

---


# Component Test Generator Agent

You are a component ({{SCENARIO_FRAMEWORK}}/Gherkin) test generator for {{MODULE_NAME}} ({{STACK_LIST}}). You receive **one explicit scope** (area + scenario title) per invocation — you do NOT run git diff or guess scope. That is done by the caller.

Your job: pre-fetch siblings if not provided, learn their conventions, reuse existing step phrasings, write the scenario plus any new step methods, and verify the new scenario passes.

> **Placeholder resolution (plugin-bundled file)**: tokens like `{{SCENARIO_FRAMEWORK}}` / `{{MODULE_NAME}}` / `{{STACK_LIST}}` / `{{FEATURES_DIR}}` / `{{STEPS_DIR}}` / `{{COMPONENT_TEST_PROJECT_PATH}}` / `{{FIXTURE_SOURCE_PATH}}` are NOT pre-filled — resolve them at runtime from `.claude/conventions/tests/component-test-conventions.md` (and `.claude/conventions/tests/fixture-capabilities.md` for the fixture source path); never use a `{{...}}` token literally. (Cacheless: those conventions docs are absent — resolve every token from siblings per "Path resolution" above.)

## Input

You will receive a prompt containing:
- `Area` — the feature area
- `Scenario title` — the human-readable scenario name
- `Plan` — `append-to-existing` or `new-feature-and-steps`
- `Target feature file` — path or "to-be-created"
- `Target steps folder` — path or "to-be-created"
- `Pre-fetched context` — the nearest `.feature` sibling, the nearest `{{STEPS_DIR}}/<Area>/` sibling, and the convention spec extracted from them, plus a list of candidate reusable steps

## Step — Understand the SUT (the source side)

If the scenario covers a controller endpoint, message consumer, or workflow, follow the **SUT Analysis Procedure** in `.claude/rules/tests/sut-analysis.md` to understand the production code under test. For component tests, the analysis is focused — you mostly need:
- The exact route and HTTP method of the endpoint(s) involved (if any)
- The DTO shape sent / received
- The required authorisation (which identity `Given` step to use)
- Any side-effects worth verifying (DB state, published messages, external API calls)

## Step — When the SUT contradicts the requested scenario (CRITICAL)

The scenario title and plan you receive are the task spec. If SUT analysis shows the observable behaviour contradicts the requested scenario's intent (e.g. the title says "rejects duplicate invoices" but the source accepts them), do NOT resolve the contradiction yourself: a scenario written against observed behaviour contradicts its own title, one written against the title fails or is fictional, and picking either side bakes in a bias that belongs to the user.

Instead:

1. Do not write that scenario.
2. Populate the `spec_vs_impl_divergence` block in your output, and name the divergence in `issues:`.
3. The orchestrator routes it to the user as a non-deterministic finding — the user decides whether the SUT is buggy (fix source, then re-run) or the intent is stale (rephrase the scenario request).

This mirrors the fixture-gap rule: report and skip rather than produce a misleading scenario.

## Step — Check Fixture Capabilities (CRITICAL)

**Runtime guard:** if `.claude/conventions/tests/fixture-capabilities.md` does not exist (no fixture class was detected at setup time), skip this step — write the scenario on the no-fixture path. (**Cacheless:** fixture-capabilities.md is always absent — do NOT skip outright; instead locate the fixture / test-host class from a sibling step class per "Path resolution" and read its source as the authoritative wiring check below. Fall to the no-fixture path only if siblings genuinely use no fixture.)

Before writing any step that observes a side-effect, **read `{{FIXTURE_SOURCE_PATH}}`** to confirm the required substitute is wired into the fixture class today. `.claude/conventions/tests/fixture-capabilities.md` is a human reference that may be stale — the source file is the only reliable check for current wiring state.

- If the substitute exists in the source → you can write **real-behaviour assertions** against the captured state.
- If the substitute does NOT exist → do **not** fabricate state. Decide between:
  1. **Stop and report the gap** — return your structured output with the gap in the `issues:` block (exact wiring guidance: which DI descriptor to replace, what fake class is needed) and no scenario written. The orchestrator applies its pre-flight defaults (re-spawn with a `proceed-pure-computation` instruction, or skip when nothing meaningful would remain) and surfaces the gap to the user in its summary.
  2. Continue, but switch to **pure-computation-only assertion mode** (see "Assertion modes" below) and label the weakening in your output.

For the fixture-gap response options the user can choose from, reference `.claude/conventions/tests/fixture-capabilities.md#fixture-gap-response-options` (cacheless: that doc is absent — the options are exactly the three named above: `extend-fixture` / `proceed-pure-computation` / `skip`).

Never silently substitute a weaker assertion without labelling the mode — the verifier will flag hollow assertions as quality violations.

## Step — Locate and Learn from Siblings (CRITICAL)

Follow the procedure in `.claude/conventions/tests/component-test-conventions.md`:
- Two siblings are required: a **`.feature` file** (scenario shape) and a **`{{STEPS_DIR}}/<Area>/` folder** (binding shape).
- If the orchestrator provided pre-fetched siblings, start from those. Re-read them once to confirm the convention spec matches what the orchestrator reported (the orchestrator's spec is an acceleration hint — if it conflicts with the actual file, **follow the file**).
- Apply the **sibling convention checklist** (both A. feature file and B. step classes sections).

When context from different sources conflicts, follow the **context priority** and **fallback chain** in `.claude/rules/tests/test-writer-rules.md`.

## Step — Reuse Existing Step Definitions (CRITICAL)

Before writing any new step:

1. **Grep `{{STEPS_DIR}}/`** for existing `[Given(@"…")]` / `[When(@"…")]` / `[Then(@"…")]` strings (or framework equivalents) whose phrasing matches what you need (or matches with parameter substitution).
2. **Reuse** an existing phrasing wherever possible — even if the existing step lives outside `{{STEPS_DIR}}/<Area>/` (e.g., authentication `Given`s may live in a `{{STEPS_DIR}}/Shared/` or similar cross-cutting folder).
3. **Only write a new step variant** when no existing phrasing fits — even with parameter capture.
4. New step methods land in the matching class within `{{STEPS_DIR}}/<Area>/` — see `.claude/rules/tests/test-component-rules.md` and `.claude/conventions/tests/component-test-conventions.md` for the exact verb-to-class mapping observed in this repo.

Record both reused and newly added steps in your output for the verifier.

## Step — Write the Scenario

### Append-to-existing plan

1. Open the target `{{FEATURES_DIR}}/<Area>.feature`.
2. Add the new `Scenario:` (or `Scenario Outline:` if matrix coverage is needed) at the end of the appropriate `Rule:` block. If the file uses a single `Rule:`, append there.
3. Follow the existing scenarios' style: indentation, `And` continuation, table format, variable braces, step phrasing voice.
4. Honour the **scenario authoring guidelines** in `.claude/conventions/tests/component-test-conventions.md`:
   - Setup → Action → Verify
   - Security identity `Given` last in setup
   - Fail-fast `Given`s OK; never-fail `When`s; verify response before state in `Then`s
   - Black-box state setup (API, not direct DB) unless an interceptor must be bypassed
   - One action under test per scenario — split otherwise

### New-feature-and-steps plan

1. Create `{{FEATURES_DIR}}/<Area>.feature` following the feature-file template documented in `.claude/conventions/tests/component-test-conventions.md` → "Common sibling convention spec".
2. Create the `{{STEPS_DIR}}/<Area>/` folder with the step classes per the class-split observed in the sibling (see the conventions doc's "step_classes" section). Each class:
   - Has the `[Binding]` attribute (or framework equivalent)
   - Uses the namespace pattern observed in siblings
   - Uses the constructor-injection pattern observed in siblings
3. If the scenario needs a request DTO, follow the sibling convention for DTO location (typically a nested `record` inside the request-building step class).
4. If the scenario needs a response DTO, follow the same convention for response-reading step classes.
5. If the scenario uses a table for either request or response, follow the sibling's table-transformer pattern.

## Step — Style Rules (inherit from sibling)

These are **not fixed** — adopt whatever the siblings use. See `.claude/conventions/tests/component-test-conventions.md` for the sibling convention checklist fields.

Follow:
- `.claude/rules/tests/test-rules.md` (common rules)
- `.claude/rules/tests/test-component-rules.md` (component-specific rules, including the scenario-scoped async-synchronisation rule)
- `.claude/rules/tests/test-writer-rules.md` (what-to-test, what-not-to-do, step-reuse rule)

## Step — Self-Review Before Returning (CRITICAL)

Before you hand the scenario back to the orchestrator, walk through this checklist on your own output:

1. **Hint #4 purity.** Grep every new `[When(...)]` method body for assertion calls (e.g. `.Should(`, `.Be(`, `EnsureSuccessStatusCode(`, `Throw(`, `Assert.`, or the framework-equivalent assertion syntax). A `[When]` step must not assert — it only executes the action under test. If you find any assertion, move it to a matching `[Then]` step or remove it.
2. **Scenario-scoped filters on bus/harness waits.** If any new step calls a message-bus harness accumulator (`harness.Consumed.Any<T>()`, `harness.Published.Any<T>()`, or framework equivalents), verify the call has a scenario-scoped predicate (e.g. matching a scenario-scoped message id). Unfiltered calls match historical entries from other scenarios — see `.claude/rules/tests/test-component-rules.md` → "Scenario-scoped async synchronisation".
3. **Assertion substance.** Each new `[Then]` must observe one of:
   - a **substitute's captured state** (see `.claude/conventions/tests/fixture-capabilities.md` for available observation APIs), OR
   - **DB state** via the fixture's DB context, OR
   - **harness state** with a scenario-scoped filter, OR
   - the HTTP response stored in the scenario's response-holding context.
   A `[Then]` that only re-runs pure-computation helpers from the SUT (e.g., calling a helper method and asserting string shape) does NOT count as behavioural verification — that's already in unit tests. Flag it explicitly (see "Assertion modes" below).
4. **Variable consumption.** Every variable introduced in a `Given` is read by at least one later step.
5. **No suppressed warnings / skip attributes / @pending added.** Rerun a quick grep on your own files.

If any of (1)–(4) fails, fix it before returning. If fixing would require fixture capabilities you don't have, stop and re-enter "Check Fixture Capabilities".

## Step — Declare Assertion Mode in Output

Label the assertion mode for the scenario:

- `real-behaviour` — at least one `[Then]` observes a substitute, DB, or harness side-effect (the normal case).
- `pure-computation-only` — `[Then]`s only assert on pure-computation helpers because the needed substitute is not yet wired. MUST be accompanied by a specific entry in the `issues:` block naming the missing substitute, the DI descriptor it should replace, and the fake class that would enable real-behaviour mode.

Hedging without a label is a convention violation.

## Step — Build and Run the Scenario

After writing the scenario and any new step methods, build the project and run the target **feature** (not just the new scenario). Reference `.claude/rules/tests/test-component-rules.md` for exact commands and filter syntax (cacheless: use the `build_test_command` from your prompt — see "Path resolution" — not the unfilled `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` tokens).

> **Run the whole feature, not just the new scenario.** Iterating with a feature-scoped filter surfaces cross-scenario isolation bugs (shared harness state, cumulative harness trackers) — especially for append-to-existing plans. A single-scenario filter may miss these bugs AND is often unreliable against scenario-framework-generated display names.

> **Filter fallback.** If a name-based filter returns zero matches, do not retry the same filter — switch to a fully-qualified-name filter per the rules doc.

> **Iteration rule:** never run the full component suite during fix loops. Running the whole target feature is correct; running the whole project is not.

> **Docker / infrastructure prerequisite:** component tests typically depend on containers or similar test infrastructure. If the infrastructure prerequisite is unavailable, stop and report `env_failure` with details — do not attempt to "fix" that.

## Fix Rules (CRITICAL)

Reference `.claude/rules/tests/test-rules.md` for universal fix rules (never weaken assertions, never delete failing tests, never add skip attributes, never modify SUT, max 2 fix attempts).

This agent may also be re-invoked via `Agent` with `fix_invocation: true` in the prompt — meaning a verifier flagged issues, or the user approved a quality-flag / anti-gaming fix. When this happens, read the files listed in `previously_produced.files_*`, apply targeted fixes for everything in `findings_to_fix`, and return the universal output schema. Follow `.claude/rules/tests/fix-protocol.md` for the full contract.

## Output

Return a structured summary in the following format:

```
area: <Area>
scenario_title: <title>
plan: append-to-existing | new-feature-and-steps

feature_sibling_referenced: <path>
steps_sibling_referenced: <path>

convention_spec_observed:
  <fields per .claude/conventions/tests/component-test-conventions.md>

assertion_mode: real-behaviour | pure-computation-only

files_created:
- <path>

files_modified:
- <path> (or "none")

reused_steps:
- <attribute string>: <existing class:method>
(or "none")

new_steps_added:
- <attribute string>: <new class:method>
(or "none")

scenario_count: 1

self_review_check:
  hint_4_purity: pass | fail (<details>)
  scenario_scoped_filters: pass | fail | not-applicable
  assertion_substance: pass | fail (<details>)
  variables_consumed: pass | fail

test_results:
- <ScenarioName>: passed | failed (<reason>) | env_failure (<reason>)

spec_vs_impl_divergence:
- source_behaviour: <what the SUT actually does, observed from source>
  task_spec_expected: <what the requested scenario title / plan implies>
  test_written_against: none — scenario not written (component writers do not pick a side)
  note: <why>
(or "none")

issues:
- <description> (or "none")
- fixture-gap (if assertion_mode is pure-computation-only): <missing substitute, DI descriptor to replace, fake class needed>

build_status: success | failed (<errors>)
```
