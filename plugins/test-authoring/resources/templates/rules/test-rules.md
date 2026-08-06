---
description: Mandatory rules for all test writing and editing — fix rules and build verification. Conventions come from the nearest sibling, not from here.
---

# Test Writing Rules

These rules apply to ALL test agents (writers, updaters, verifiers) when working with test files.

## Project-wide Conventions

This file does not carry a list of them, and no such list is shipped or generated. Framework, mocking
library, assertion style, naming, and layout are read from the **nearest sibling test** at the moment
you write — that is the declared source of truth (`test-writer-rules.md` → Context Priority), and a
list here would only compete with it while going stale. When no sibling exists, report the gap; do
not fill it from what the language usually does.

## Fix Rules (CRITICAL)

- **NEVER** weaken an assertion to make a test pass (e.g., changing `.Be(5)` to `.BeGreaterThan(0)`)
- **NEVER** delete a test case that fails — fix the root cause or report it as failed
- **NEVER** add skip/ignore attributes or comment out a test to bypass a failure
- **NEVER** change the SUT (source code) to make tests pass
- If a test fails after **2 fix attempts**, report it as `failed` in the output — do not keep weakening it

## Build and Test Verification

After writing or modifying tests, build and run them.

The invocation is **handed to you**, not listed here. Your caller detects it once per session from the
project manifest — the test project's build command plus its filtered-run syntax — and passes it as
`build_test_command`. Adjust the filter to the test class you actually wrote: the caller's guess at the
class name can differ from the sibling-driven name you chose. Where several test projects are in play,
each one has its own command and they are not interchangeable.

No command list is cached anywhere, deliberately: a stored command goes stale the moment a test project
is added, renamed, or re-targeted, and it fails in a way that looks like a broken test rather than a
stale note. If no invocation reached you, report that in your output — never guess a command line.

### Verification procedure
- If the build has errors, check whether they are **pre-existing** or caused by your changes. Only fix errors caused by your changes.
- If a test fails, read the error output, diagnose the root cause, fix the test, and re-run.
- Iterate until all new/modified tests pass. Max **2 fix rounds** — after that, report as failed.
- If a test fails due to environmental issues (e.g., container runtime, network), report it as `env_failure` rather than silently skipping.
