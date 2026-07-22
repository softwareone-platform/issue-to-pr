---
description: C# / .NET (typically Reqnroll/SpecFlow) language baseline for component-test build/run command placeholders in `rules/test-component-rules.md`.
fills_placeholder:
  - "{{BUILD_COMMAND}}"
  - "{{TEST_COMMAND_ALL}}"
  - "{{TEST_COMMAND_FEATURE_FILTER}}"
  - "{{TEST_COMMAND_SCENARIO_FILTER}}"
template: rules/test-component-rules.md
---

# C# / .NET — Component Test Build/Run Commands Baseline

Bootstrap (component subagent) uses this fragment when filling the four command placeholders in `.claude/rules/tests/test-component-rules.md`. Substitute project path and feature/scenario name based on the detected stack.

| Slot | Command |
|---|---|
| `{{BUILD_COMMAND}}` | `dotnet build <project> -c Debug` |
| `{{TEST_COMMAND_ALL}}` | `dotnet test <project>` |
| `{{TEST_COMMAND_FEATURE_FILTER}}` | `dotnet test <project> --filter "FullyQualifiedName~<FeatureName>"` |
| `{{TEST_COMMAND_SCENARIO_FILTER}}` | `dotnet test <project> --filter "Name~<ScenarioName>"` |
