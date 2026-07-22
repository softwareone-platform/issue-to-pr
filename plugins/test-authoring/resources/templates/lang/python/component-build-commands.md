---
description: Python (typically behave or pytest-bdd) language baseline for component-test build/run command placeholders in `rules/test-component-rules.md`.
fills_placeholder:
  - "{{BUILD_COMMAND}}"
  - "{{TEST_COMMAND_ALL}}"
  - "{{TEST_COMMAND_FEATURE_FILTER}}"
  - "{{TEST_COMMAND_SCENARIO_FILTER}}"
template: rules/test-component-rules.md
---

# Python — Component Test Build/Run Commands Baseline

Bootstrap (component subagent) uses this fragment when filling the four command placeholders in `.claude/rules/tests/test-component-rules.md`. Python has no build step; commands run the interpreter directly. Two Gherkin frameworks see common use — bootstrap detects which from sibling step-code imports and fills the matching family.

## Family: behave (`@given` / `@when` / `@then` imported from `behave`)

| Slot | Command |
|---|---|
| `{{BUILD_COMMAND}}` | n/a (ensure deps installed: `pip install -r requirements*.txt` or `pip install -e .`) |
| `{{TEST_COMMAND_ALL}}` | `behave` |
| `{{TEST_COMMAND_FEATURE_FILTER}}` | `behave <features-dir>/<FeatureFileName>.feature` |
| `{{TEST_COMMAND_SCENARIO_FILTER}}` | `behave -n "<ScenarioName>"` (regex match on scenario name) |

## Family: pytest-bdd (`scenarios(...)` / `@scenario(...)` imported from `pytest_bdd`)

| Slot | Command |
|---|---|
| `{{BUILD_COMMAND}}` | n/a |
| `{{TEST_COMMAND_ALL}}` | `pytest <bdd-test-dir>/` |
| `{{TEST_COMMAND_FEATURE_FILTER}}` | `pytest <bdd-test-dir>/test_<feature>.py` or `pytest -k "<feature_keyword>"` |
| `{{TEST_COMMAND_SCENARIO_FILTER}}` | `pytest <bdd-test-dir>/test_<feature>.py::<scenario_function_name>` |
