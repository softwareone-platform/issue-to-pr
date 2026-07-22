---
schema_version: "1.2"
description: Component-test-specific rules — {{SCENARIO_FRAMEWORK}}/Gherkin runner, {{INFRA_PREREQUISITE}} prerequisite, build/test commands, step-class organisation.
paths: ["{{COMPONENT_TEST_PROJECT_PATH}}/**"]
---

# Component Test Rules

These rules apply **only to the `{{COMPONENT_TEST_PROJECT_PATH}}` project**. They sit on top of the cross-type rules in `.claude/rules/tests/test-rules.md` — read both.

## Mandatory Component-test Rules

### Tooling (observed at bootstrap time — do not deviate without team agreement)

<!-- Bootstrap fills the following table from the test project's dependency manifest. Each row records a library and its role; keep the table minimal — only libraries that component tests depend on for their core mechanism belong here. -->

| Library | Role |
|---|---|
| {{SCENARIO_FRAMEWORK}} | scenario runner; `.feature` files are the only test entry points — never add code-driven test attributes to this project |
{{TOOLING_TABLE_EXTRA}}
<!-- TOOLING_TABLE_EXTRA is filled by bootstrap with detected dependencies, e.g.:
| Testcontainers.MsSql / Testcontainers.Azurite | SQL / blob test containers; Docker must run before any build/test command |
| MassTransit.Testing | Message-bus test harness; do not use a real bus connection in tests |
| WireMock | External HTTP API stubs |
| Respawn | Between-scenario DB reset |
| Microsoft.Extensions.TimeProvider.Testing | `FakeTimeProvider` for time control |
-->

Do not introduce alternative libraries for the roles above without updating this rules file.

### Step class shape

<!-- Bootstrap fills the step class table by sampling 2-3 existing `Steps/<Area>/` folders and detecting the class-split pattern. For repos using the 4-class split (Setup/Request/Response/Assertion), the table below is the default. For repos using a different split (e.g., Given/When/Then, Arrange/Act/Assert, single combined class), bootstrap regenerates this table from observation. -->

- All step classes carry the binding marker observed in siblings (e.g., `[Binding]` attribute for Reqnroll/SpecFlow, `@given`/`@when`/`@then` decorators for behave/pytest-bdd, `@Given`/`@When`/`@Then` annotations for Cucumber-JVM) and follow the namespace/module organisation pattern recorded in `.claude/conventions/tests/component-test-conventions.md`.
- All transformation classes (under `{{STEPS_DIR}}/../Bindings/Transformations/` or equivalent) and hook classes (`{{STEPS_DIR}}/../Bindings/Hooks/`) also require the same binding marker.
- Steps split into siblings per `<Area>` folder following the detected pattern:

{{STEP_CLASS_SPLIT_TABLE}}
<!-- Example for the 4-class split (fill when bootstrap detects this pattern):

  | Class | Purpose | Predominant attribute |
  |---|---|---|
  | `<Area>SetupSteps` | Black-box state setup via API | `[Given]` |
  | `<Area>RequestSteps` | Build the action-under-test request body / parameters | `[When]` (occasionally a `[Given]` for direct-DB setup that bypasses domain rules) |
  | `<Area>ResponseSteps` | Verify the HTTP response stored in the response-holding context | `[Then]` |
  | `<Area>AssertionSteps` | Verify side-effect state (DB queries, harness messages) | `[Then]` |

If bootstrap detects a 3-class split (Given/When/Then), a single combined class, or some other organisation, regenerate this table to match.
-->

- New steps go into the matching class. **Do not** create an additional class for a new area unless the canonical roles observed here do not fit.
- Steps are matched via regex strings in the binding attribute (or framework-equivalent form).

### Dependency injection in steps

- Inject runner-managed services via primary constructor: the fixture class (test-run scope), HTTP client abstractions, request/response context holders, variable context, message client (scenario scope) — exact set depends on the detected sibling pattern.
- Do **not** newly construct fixtures or HTTP clients — always inject.

### Variable convention

<!-- Bootstrap fills variable convention details from observation. The table below shows the pattern observed in this repo. -->

- Variables in feature files follow the sibling pattern (typically `{camelCase}` braces).
- Step methods receive them via the typed-variable parameter type (resolved by a variable-transformer binding).
- A `Given` step that produces a variable assigns its value; downstream `When`/`Then` steps consume the same variable instance.

### Scenario-scoped async synchronisation (CRITICAL)

- The message-bus harness's accumulators (e.g., `harness.Consumed`, `harness.Published`) **accumulate across scenarios** within a single test run (scenarios may run sequentially but the harness typically has test-run scope).
- When awaiting async consumption, **always filter by a scenario-scoped key** — typically the published message's Id:
  ```
  // CORRECT — scenario-scoped filter, deterministic across multi-scenario runs
  await consumed.Any<EventMessage>(x => x.Context.Message.Id == currentScenarioMessageId);

  // WRONG — matches the first-ever consumed message, so a prior scenario's record
  //         makes this call return before the CURRENT scenario's message is processed
  await consumed.Any<EventMessage>();
  ```
- To thread a scenario-scoped key from the `[When]` step that publishes to the `[Then]` step that waits, define a POCO scenario-context class and let the scenario runner inject a fresh instance per scenario.
- This pitfall only surfaces when two or more scenarios in the same feature publish the same message type — **which is exactly what happens when you add a new scenario to an existing feature**. Iterate with the full-feature filter (see below) to catch it.

### Request and response handling

- Build HTTP requests through the request-builder helper observed in siblings (e.g., `ApiRequestBuilder` or equivalent); the actual call is dispatched in an `After` hook when the `When` block completes.
- Read response bodies via a re-readable reader (e.g., a `PeekAsync<T>` / `PeekCollectionAsync<T>` helper) — never a one-shot reader that consumes the stream, since multiple `[Then]` steps may need to read the same response.
- For table-style assertions and request bodies, follow the sibling's table-transformer pattern.
- For per-record DTOs used by table transformers, follow the sibling's DTO location convention (commonly nested records inside the request/response step class).

### Scenario authoring guidelines (enforced by verifiers)

- **Setup → Action → Verify**: a scenario is a sequence of `Given`s, then a single `When` (or a small `When`+`And` group describing one action), then `Then`s.
- **Security last in `Given`**: identity-changing setup goes after data setup.
- **Fail fast in `Given`**: setup steps may assert so a misconfigured precondition fails with a clear message.
- **Never fail in `When`**: a `When` step must not assert outcomes — error responses may be the expected result.
- **Verify response before state in `Then`**: if the action under test was an HTTP request, the first `Then` checks the response (status code / body) before any state-verification step that would issue a new HTTP call (which overwrites the response holder).
- **Black-box state setup**: prefer setup via API steps over direct DB writes. Direct DB writes are permitted only when no API path can establish the precondition (e.g., bypassing interceptor logic).
- **One action under test per scenario**: do not chain multiple distinct actions into a single scenario. Split into two scenarios instead.
- Do not introduce `@ignore` / `@pending` to silence failing scenarios; legitimate uses of `@pending` are reserved for known-incomplete features, not fix bypasses.

## Build and Test Verification

> {{INFRA_PREREQUISITE_NOTE}}
<!-- Example: "Docker must be running. The Testcontainers SQL Server / Azurite containers are spawned per test run." Bootstrap fills this with the infrastructure prerequisite detected from the fixture class wiring. -->

```bash
# Build
{{BUILD_COMMAND}}

# Run all component tests (slow — full suite spins multiple containers / test infrastructure)
{{TEST_COMMAND_ALL}}

# Run all scenarios for a single feature (preferred while iterating — reliable match
# AND catches cross-scenario isolation issues)
{{TEST_COMMAND_FEATURE_FILTER}}

# Run a single scenario by name (secondary — use only when the feature has many
# co-located scenarios and you are certain the new scenario has no shared-state
# interaction with them)
{{TEST_COMMAND_SCENARIO_FILTER}}
```

<!-- Bootstrap (component subagent) fills the four command slots above from the `component-build-commands.md` fragment under the detected language's directory. See references/placeholders.md § Language fragments. -->

> **Filter reliability.** The feature-scoped filter matches scenario-framework-generated test-class names deterministically. Name-based filters match the framework's generated display name, which often applies transformations (underscore insertion, punctuation removal) that cause the filter not to match. When a name-based filter returns zero matches, **fall back to the feature-scoped filter** — do not retry the same filter.

### Iteration rule

Always iterate via the feature-scoped filter when adding or reviewing a scenario — this runs the new scenario **plus all co-located scenarios** in the same feature, which surfaces cross-scenario isolation issues (e.g., shared harness state, cumulative accumulators) that a single-scenario filter would miss. The full suite is slow (container startup + sequential execution) — never run the whole project repeatedly during fix loops, but DO run the whole target feature.

### Notes on env_failure

Component tests **do** have environmental dependencies (containers, port binding, image pulls). When a test fails because the infrastructure prerequisite is not satisfied, report `env_failure` rather than a fix attempt. Genuine assertion failures or stuck-state failures still go through the regular fix loop.
