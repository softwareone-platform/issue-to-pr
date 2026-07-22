---
schema_version: "1.1"
description: Derivation rules, sibling convention checklist, and type-specific patterns for component ({{SCENARIO_FRAMEWORK}}/Gherkin) tests.
paths: ["{{COMPONENT_TEST_PROJECT_PATH}}/**"]
---

# Component Test Conventions

> Mandatory rules live in `.claude/rules/tests/test-component-rules.md` (component-specific) and `.claude/rules/tests/test-rules.md` (common).
> For the test directory tree, see `.claude/conventions/tests/project-architecture.md`.
> For shared utilities, see `.claude/conventions/tests/common-test-utilities.md`.
> For the catalog of substitutes/fakes currently wired into the fixture class, see `.claude/conventions/tests/fixture-capabilities.md` (generated only when a fixture class is detected).

## Source → feature/steps path derivation rules

Component tests are organised **by feature area**, not by source class. A single `.feature` file plus a step folder per area covers the area.

### Layout

<!-- Bootstrap fills the layout section from the target repo's actual `.feature` and `Steps/` tree. Show the real top-level shape. -->

```
{{FEATURES_DIR}}/
├── {{FEATURE_EXAMPLE_1}}.feature
├── {{FEATURE_EXAMPLE_2}}.feature
└── ...

{{STEPS_DIR}}/
├── {{STEPS_FOLDER_EXAMPLE_1}}/       ← matches {{FEATURE_EXAMPLE_1}}.feature
│   ├── {{STEP_CLASS_EXAMPLE_1}}
│   ├── {{STEP_CLASS_EXAMPLE_2}}
│   └── ...
└── ...
```

**Naming pairing:**

<!-- Bootstrap samples 2-3 actual (.feature, step-folder) pairs from the target repo and fills this table. Leave the last row as a generic pattern description. -->

| `{{FEATURES_DIR}}/` file | `{{STEPS_DIR}}/` folder | Step class prefix |
|---|---|---|
{{NAMING_PAIRING_ROWS}}

**Source → coverage mapping:**

The skill is invoked with an explicit scope (Mode B): a feature area and a scenario name. Use the scope to choose the target `.feature` and `{{STEPS_DIR}}/<Area>/`:

1. **Existing feature area** → append a new `Scenario:` block to the existing `.feature` and any new step variants to the existing step files.
2. **New feature area** → create a new `.feature` plus a new `{{STEPS_DIR}}/<Area>/` folder following the step-class split observed in existing areas.

When uncertain whether the area is "existing", grep `{{FEATURES_DIR}}/` for a `.feature` whose name overlaps with the scope name.

## Sibling convention checklist

When learning from siblings, you have **two** sources of truth (not one as in unit tests):

### A. Nearest `.feature` file (the scenario shape)

<!-- Bootstrap samples 1-2 real `.feature` files from the target repo and fills the "Typical values" column with observed patterns. Leave generic values as fallbacks. -->

| Field | What to observe | Typical values in this repo |
|---|---|---|
| `feature_header` | `Feature:` line + free-text description below | {{FEATURE_HEADER_VALUE}} |
| `rule_usage` | Whether scenarios are grouped under `Rule:` blocks | {{RULE_USAGE_VALUE}} |
| `background_usage` | Presence of a `Background:` block for shared `Given`s | {{BACKGROUND_USAGE_VALUE}} |
| `scenario_naming` | Shape observed (Subject + verb + object, etc.) | {{SCENARIO_NAMING_VALUE}} |
| `scenario_outline_usage` | Whether `Scenario Outline:` + `Examples:` are used | {{SCENARIO_OUTLINE_USAGE_VALUE}} |
| `variable_naming` | Bracket style and case convention | {{VARIABLE_NAMING_VALUE}} |
| `tag_usage` | Presence of `@<tag>` annotations and their semantics | {{TAG_USAGE_VALUE}} |
| `data_table_format` | Table-style step args | {{DATA_TABLE_FORMAT_VALUE}} |
| `step_phrasing_style` | Voice and form observed | {{STEP_PHRASING_STYLE_VALUE}} |

### B. Matching `{{STEPS_DIR}}/<Area>/` folder (the binding shape)

<!-- Same treatment — bootstrap samples 2-3 step classes and fills observed values. -->

| Field | What to observe | Typical values in this repo |
|---|---|---|
| `class_split` | How step methods are organised per area | {{CLASS_SPLIT_VALUE}} |
| `binding_attribute` | Attribute on the class | {{BINDING_ATTRIBUTE_VALUE}} |
| `constructor_injection` | Primary constructor parameters per class role | {{CONSTRUCTOR_INJECTION_VALUE}} |
| `step_attribute_form` | `[Given(@"…")]` / `[When(@"…")]` / `[Then(@"…")]` shape (or framework equivalent) | {{STEP_ATTRIBUTE_FORM_VALUE}} |
| `step_method_naming` | Method naming convention | {{STEP_METHOD_NAMING_VALUE}} |
| `dto_location` | Where request/response DTOs live | {{DTO_LOCATION_VALUE}} |
| `default_dto_factory` | Default-values factory pattern | {{DEFAULT_DTO_FACTORY_VALUE}} |
| `state_setup_style` | Black-box (API) vs direct DB | {{STATE_SETUP_STYLE_VALUE}} |
| `assertion_library` | Assertion helper usage | {{ASSERTION_LIBRARY_VALUE}} |
| `response_reader_pattern` | Response-body reader | {{RESPONSE_READER_PATTERN_VALUE}} |

### Common sibling convention spec (most-likely default)

When no sibling exists for a brand-new feature area (fallback), the default is:

```yaml
feature_file:
  feature_header: "Feature: <Area> Management" + one-line description
  rule_usage: {{DEFAULT_RULE_USAGE}}
  background_usage: {{DEFAULT_BACKGROUND_USAGE}}
  scenario_naming: "<Subject> <verb> <object>"
  scenario_outline_usage: only when matrix-style coverage is required
  variable_naming: {{DEFAULT_VARIABLE_NAMING}}
  tag_usage: {{DEFAULT_TAG_USAGE}}

step_classes:
  class_split: {{DEFAULT_CLASS_SPLIT}}
  binding_attribute: {{DEFAULT_BINDING_ATTRIBUTE}}
  constructor_injection: {{DEFAULT_CONSTRUCTOR_INJECTION}}
  step_attribute_form: {{DEFAULT_STEP_ATTRIBUTE_FORM}}
  step_method_naming: {{DEFAULT_STEP_METHOD_NAMING}}
  dto_location: {{DEFAULT_DTO_LOCATION}}
  default_dto_factory: {{DEFAULT_DEFAULT_DTO_FACTORY}}
  state_setup_style: {{DEFAULT_STATE_SETUP_STYLE}}
  assertion_library: {{DEFAULT_ASSERTION_LIBRARY}}
  response_reader_pattern: {{DEFAULT_RESPONSE_READER_PATTERN}}
```

## Learn from siblings (CRITICAL)

Siblings are the source of truth. Priority for each of the two sources:

### `.feature` siblings
1. The target `.feature` file itself (when appending a scenario)
2. Closely related areas (often shared domain concepts)
3. Any other feature using the same setup style

### `{{STEPS_DIR}}/<Area>/` siblings
1. The matching `{{STEPS_DIR}}/<Area>/` folder (when adding to an existing area)
2. The nearest area's step folder with the same class role (Setup/Request/Response/Assertion or the repo's equivalent)
3. Any step folder for a feature with a similar shape

**Do not blend styles.** If the matching area's Setup class uses primary-constructor injection of a specific set of services, follow that exact pattern — do not switch to a different initialiser style or property injection.

## Convention spec output format

When reporting to an orchestrator, emit the following YAML block:

```yaml
convention_spec:
  feature_sibling_path: <path to nearest .feature>
  steps_sibling_path: <path to nearest step folder>
  feature_file:
    feature_header: <observed text>
    rule_usage: <none | single | multiple>
    background_usage: <yes | no>
    scenario_naming: <pattern observed>
    scenario_outline_usage: <yes | no>
    variable_naming: <observed>
    tag_usage: <observed>
    data_table_format: <observed>
  step_classes:
    class_split: <observed pattern>
    binding_attribute: <observed>
    constructor_injection:
      <class role>: <observed signature>
    step_attribute_form: <observed>
    step_method_naming: <observed>
    dto_location: <observed>
    default_dto_factory: <observed>
    state_setup_style: <observed>
    response_reader_pattern: <observed>
  reused_steps:
  - <attribute string>: <existing class:method>
```

`reused_steps` is the list of existing step phrasings the writer matched against (and reused) before writing any new step variants.

## Component-test-specific patterns

<!-- Bootstrap fills this section by scanning sample step classes and bindings in the target repo. Each pattern below is an example shape — only keep patterns actually present in this repo; regenerate values per repo. -->

### Variable pattern

{{VARIABLE_PATTERN_DETAIL}}
<!-- Example shape:
- Defined in a `Given` step that captures or generates an ID and assigns to `<variable>.Value`.
- Consumed in later `When`/`Then` steps via the same typed parameter — the variable transformer resolves the same instance for the same name within a scenario.
- Inside URI strings the variable is substituted at request-build time by a context-evaluator; step methods that build URIs receive plain `string` and substitution is implicit.
-->

### Request builder pattern

{{REQUEST_BUILDER_PATTERN_DETAIL}}
<!-- Example shape:
- A `When the caller makes a <METHOD> request to <URI>` step configures the request builder (set method, set URI).
- A subsequent `And the following body is sent in the request body:` step sets the request body.
- The actual HTTP call is dispatched by an `AfterScenarioBlock` hook when the `When` block completes; the response is stored in the scenario's response-holding context.
- **Never** call `HttpClient` directly from a step — go through the API client helper (for setup `Given`s) or the request builder (for the action-under-test `When`).
-->

### Reading the response

{{RESPONSE_READER_PATTERN_DETAIL}}
<!-- Example shape:
```csharp
var item = await responseContext.Response.Content.PeekAsync<ItemResponse>();
var items = await responseContext.Response.Content.PeekCollectionAsync<ItemResponse>();
```

The reader must reset the content stream so subsequent `Then` steps can read again, possibly as a different type.
-->

### Table transformers

{{TABLE_TRANSFORMER_DETAIL}}
<!-- Example shape:
- Strongly-typed table → DTO (or collection of DTOs) for request bodies and exact-match responses.
- Partial-match table helpers for response verification (e.g., "all rows are a subset of" / "all rows exactly match").
- Each new DTO that travels through a table needs its own transformer subclass in the transformers folder (one per type).
-->

### Fixture access

{{FIXTURE_ACCESS_DETAIL}}
<!-- Example shape:
- Test-run scope (one instance per test run, not per scenario).
- Exposes the DB context, blob fixture, message-bus harnesses, time provider, identity context, HTTP mock servers, and a range of fakes for outbound services — see `.claude/conventions/tests/fixture-capabilities.md` for the full catalog and the observation API for each.
- Use direct-DB access only when an API path cannot establish the precondition (e.g., bypassing domain interceptors). Document the bypass in a code comment.

If bootstrap did not generate `fixture-capabilities.md` (no fixture class detected), this section should note that the fixture catalog is not available and the writer should inspect the fixture source directly.
-->

### Scenario-scoped async synchronisation

When a scenario's action-under-test is a message publish to an async consumer, the consumer runs asynchronously. A `[Then]` step that reads state is racing against the consumer. The pattern:

1. In the `[When]` step, capture a scenario-scoped key (typically the published message's Id) into a scenario-scoped POCO — the scenario runner auto-registers and injects concrete types per scenario.
2. In the `[Then]` step's synchronisation helper, filter the harness by that key:
   ```
   var consumed = fixture.Harness.GetConsumerHarness<TheConsumer>().Consumed;
   await consumed.Any<TheMessage>(x => x.Context.Message.Id == scenarioContext.Id);
   ```
3. The harness's accumulator trackers typically persist across scenarios (test-run scope). Calling an accumulator without a scenario-scoped predicate matches historical consumption and returns before the CURRENT scenario's message is processed.

This pattern is mandatory — see `.claude/rules/tests/test-component-rules.md` → "Scenario-scoped async synchronisation".

### Assertion modes

Every component-test scenario falls into one of two assertion modes. The writer MUST declare which mode its scenario uses:

| Mode | When to use | Example observable |
|---|---|---|
| `real-behaviour` | The scenario's `[Then]` steps observe a substitute's captured state, the DB via the fixture, the message-bus harness (with a scenario-scoped filter), or the HTTP response. | A fake's captured-invocations bag, a DB read, a harness match with a scenario-scoped filter, or the response status / body |
| `pure-computation-only` | The scenario's `[Then]` steps only call pure-computation helpers from the SUT. Use ONLY when a needed substitute is not yet wired in the fixture. | A helper method's return value asserted against a string / numeric shape |

`pure-computation-only` mode is a weakening — unit tests already cover pure-computation helpers, so the scenario does not add behavioural coverage. If this mode is chosen, the writer's output MUST include a `fixture-gap` entry in `issues:` naming:
- the missing substitute
- the DI descriptor that should be replaced
- the fake class that would enable real-behaviour mode

The orchestrator surfaces the fixture gap to the user as a non-deterministic finding; the user decides whether to extend the fixture before re-running the skill.

### Hook lifecycle

{{HOOK_LIFECYCLE_DETAIL}}
<!-- Bootstrap fills this with the hooks observed in the target repo's `Bindings/Hooks/` (or equivalent). Example:

| Hook | Defined in | Purpose |
|---|---|---|
| `[BeforeTestRun]` | `FixtureSetupHooks` | Bootstraps the fixture, starts harnesses |
| `[BeforeScenario]` | `FixtureSetupHooks` | Resets DB/state; registers fixture in the scenario runner's DI container |
| `[AfterScenarioBlock]` | `ApiClientHooks` | After a `When` block, dispatches the HTTP request built by the request builder and stores the response |
| `[AfterTestRun]` | `FixtureSetupHooks` | Stops harnesses, disposes containers |

Do not add a new hook unless absolutely necessary; reuse the existing fixture lifecycle.
-->

### Scenario authoring guidelines

- **Setup → Action → Verify**: a sequence of `Given`s, then a single `When` (or a tight `When + And` group describing one action), then `Then`s.
- **Hint #1 — Security last**: identity-changing `Given`s come last in the setup phase.
- **Hint #2 — Black-box setup**: state setup is via API, not direct DB writes, unless bypassing interceptors.
- **Hint #3 — Fail fast**: setup `Given`s may assert so misconfigured preconditions fail with a clear message.
- **Hint #4 — Don't fail**: `When` steps must not assert outcomes — error responses may be the expected scenario result.
- **Hint #5 — Verify response first**: in `Then`, check the HTTP response before any state-verification step that would issue a new HTTP request (which overwrites the response holder).
- **Hint #6 — Verify state, not how**: state-verification `Then`s describe *what* to verify, not *how*.
- **Hint #7 — Split your tests**: one action under test per scenario; do not chain multiple distinct actions in a single scenario.

### Decision: append vs new feature file

- **Append a `Scenario:` block to an existing `.feature`** when the scope's feature area already exists in `{{FEATURES_DIR}}/`. Add the new scenario at the end of the existing `Rule:` block (or in the most appropriate `Rule:` if multiple exist). Reuse existing step phrasings; only add new step methods when no existing one fits.
- **Create a new `.feature` file + new `{{STEPS_DIR}}/<Area>/`** when the scope introduces a new area. Follow the pairing observed in existing areas for file and folder naming.

When in doubt about which existing area a scenario belongs to, prefer the area where the *primary entity under test* lives.
