---
schema_version: "1.2"
description: Human reference for {{FIXTURE_CLASS_NAME}} — catalog of wired substitutes, known gaps, fixture-gap response policy. Not the authoritative source for "is substitute X wired?" queries.
paths: ["{{COMPONENT_TEST_PROJECT_PATH}}/**"]
---

# Component-test Fixture Capabilities

This document is a **human reference** for `{{FIXTURE_CLASS_NAME}}`. It holds:

- A catalog of substitutes currently wired (section: _Substitutes wired today_)
- Known fixture gaps that scenarios have hit but haven't been filled yet (section: _Not wired today_)
- The canonical response options when a scenario encounters a fixture gap (section: _Fixture-gap response options_)

## Role boundary and authority

> **Machine behaviour is NOT sourced from this document for "is substitute X wired?" queries.** The authoritative source for that question is `{{FIXTURE_SOURCE_PATH}}` itself. Skills and agents that need to check wiring state **should read the source file**, not this document.
>
> This document holds **policy** (response options) and **human context notes** (catalog narrative, known gaps with wiring hints). A stale entry here will degrade human guidance but will not affect machine correctness.

## Workflow assumption

This document and every consumer of it **assume a source-first workflow** — production code is implemented first, tests are written afterwards. `add-component-test` takes an explicit area + scenario scope, reads the existing production code under test, and derives what fixture substitutes the scenario needs. (`scan-test-gaps` does not use this document — it is scoped to unit and integration tests, which do not rely on the component fixture.)

**BDD / outside-in / test-first workflows are not supported.** If `.feature` scenarios are authored before the corresponding production code exists, this skill set does not apply — the developer should author scenarios and fixture wiring by hand until the production code settles.

## Maintenance checklist (when adding a new fake)

When you add a new fake / substitute to `{{FIXTURE_CLASS_NAME}}`:

1. Add the corresponding row to the _Substitutes wired today_ section below.
2. If _Not wired today_ previously had a matching entry, **remove it** — the gap is now filled.
3. If the new fake introduces a `Reset()` call wired into `{{FIXTURE_CLASS_NAME}}.Reset()`, update the _Reset between scenarios_ section.
4. If the new fake exposes an observation helper (e.g., `GetWorker<X>()`), consumers that scan the fixture source for the helper whitelist will pick it up automatically; no action needed here.

## Substitutes wired today

<!-- Bootstrap's Tier-3 generator parses `{{FIXTURE_SOURCE_PATH}}` and fills the tables below with detected substitutes, grouped by host/subsystem heuristics (e.g., Api host vs Worker host vs cross-cutting). If the fixture has no clear host split, use a single "All hosts" table. Leave the tables empty if no substitutes could be parsed with confidence — the human operator will fill in manually. -->

{{SUBSTITUTES_WIRED_TODAY_TABLES}}

## Reset between scenarios

<!-- Bootstrap inspects `{{FIXTURE_CLASS_NAME}}.Reset()` (or equivalent) and lists what is reset between scenarios. If no Reset() method is detected, the list below will be empty and a note should be added asking the operator to confirm whether inter-scenario state leakage is controlled. -->

`{{FIXTURE_CLASS_NAME}}.Reset()` is invoked between scenarios and clears:

{{RESET_CLEARS_LIST}}

> Message-bus harness accumulators (e.g., `harness.Consumed` / `harness.Published`) typically are **not** reset between scenarios — they accumulate. When synchronising on async consumption, filter by a scenario-scoped key — see the "Scenario-scoped async synchronisation" note in `.claude/conventions/tests/component-test-conventions.md`.

## Not wired today

Known fixture gaps — substitutes that scenarios have requested but aren't yet in `{{FIXTURE_CLASS_NAME}}`. This section grows organically: when a scan or skill run encounters a new gap, it proposes adding an entry here; the human operator accepts the proposal before the entry is added.

**Entry schema:**

| Field | Purpose | Required? |
|---|---|---|
| `Substitute` | What's missing (e.g., a hub-client connection, a messaging endpoint) | Yes |
| `First observed in` | Which source file or scenario triggered the entry | Yes |
| `Notes` | Free text — known obstacles, wiring hints, related PRs, anything that helps someone filling the gap | Optional |

### Current entries

<!-- Bootstrap leaves this empty on first generation. The human operator and subsequent skill runs accumulate entries here. -->

(none yet)

### Deprecation

When a `Not wired today` entry is fulfilled (the substitute is wired into `{{FIXTURE_CLASS_NAME}}`), follow the _Maintenance checklist_ above: move the substitute into the _Substitutes wired today_ section and **delete the entry here**. Do not leave stale entries.

## Fixture-gap response options

When a scenario needs a substitute that is not wired, this section is **the single source of truth** for the response taxonomy: consumers (writer, orchestrator pre-flight, future batch workflows) MUST draw their responses from exactly these options and MUST NOT invent additional ones. **When** each consumer surfaces the choice is governed by its own flow — `/add-component-test`'s pre-flight applies `proceed-pure-computation` (or `skip` when nothing meaningful would remain to assert) automatically and reports the gap with the `extend-fixture` suggestion in its summary; it does not gate mid-run.

| Option | Description | Applies to |
|---|---|---|
| `extend-fixture` | User applies the wiring change to `{{FIXTURE_CLASS_NAME}}` (outside the skill), then re-invokes. Produces a scenario with real-behaviour assertions. | All contexts |
| `proceed-pure-computation` | The scenario is written with `pure-computation-only` assertion mode (see `component-test-conventions.md` _Assertion modes_) — surfaces the gap rather than fabricates coverage. Verifier will flag weakened assertions as a quality signal, not as an error. | All contexts |
| `skip` | Skip this scenario rather than produce a hollow test; continue with any remaining items. | Applied automatically by `/add-component-test`'s pre-flight (and on a writer-reported gap) when `proceed-pure-computation` would leave nothing meaningful to assert — single- or multi-scenario invocations alike. Also reserved for future batch workflows. |

Consumers reference this section by its anchor (`.claude/conventions/tests/fixture-capabilities.md#fixture-gap-response-options`) and MUST note which options apply in their specific context.
