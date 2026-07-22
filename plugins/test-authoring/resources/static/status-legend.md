# Status Icons

| Icon | Status | When to use |
|---|---|---|
| 🟩 | Pass / Valid | Tests pass, valid state, no action needed. Includes scan results where coverage already exists (note "(already covered)" when relevant). |
| 🟨 | Warning | Non-error issue needing attention but not fatal. Examples: outdated tests (minor/major), env_failure, partial coverage, build OK but tests unverifiable. |
| 🟥 | Failed / Wrong | Error state. Examples: build failures, tests failed after max fix attempts, test logic incorrect, unresolved verify violations. |
| 🟦 | Pending | Awaiting user confirmation or not yet implemented. |
| 🟪 | Quality flag | Subjective improvement opportunity. Examples: trivial assertions, redundant/duplicated tests, missing dependency verification. |
