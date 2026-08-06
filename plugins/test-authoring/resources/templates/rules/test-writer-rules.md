---
description: Guidelines for test generation — what to test, what not to do, and how to report spec-vs-implementation divergence. Applies to writer agents only, not verifiers.
---

# Test Generation Guidelines

These guidelines apply to **writer agents** (add-*-test-agent, update-*-test-agent) when generating or rewriting tests. Verifier agents do not generate tests and should ignore these guidelines.

## What to Test

For each method, generate tests covering:
- **Happy path** — normal successful execution
- **Validation failures** — invalid inputs, null arguments
- **Exception scenarios** — expected exceptions from dependencies
- **Edge cases** — empty collections, boundary values
- **Dependency interactions** — verify correct calls to mocked dependencies

## What NOT to Do

- Do not test private methods directly
- Do not add excessive comments or documentation
- Do not add features or refactor the source code
- Do not generate tests for trivial getters/setters or DTOs unless logic is involved
- Do not introduce a mocking library or pattern that differs from sibling tests

## When observed behaviour contradicts the spec

A test must reflect **what the code actually does**, not what a task description claims it should do. When the two conflict — e.g. the task says "propagates `RuntimeError`" but the SUT swallows it and returns `None` — you are sitting on a possible source bug, and you must not silently bake a decision into the suite. The failure mode to avoid: writing a test that asserts the spec behaviour (it fails or is fictional), OR asserting the observed behaviour with no flag (a real bug gets frozen behind a green test, and nobody notices).

Do this instead:

1. **Test the observable behaviour** so the suite stays honest and green.
2. **Do NOT modify the SUT** to match the spec — that is out of a test writer's remit (see fix rules in `test-rules.md`).
3. **Populate the `spec_vs_impl_divergence` block** in your output (schema in `common-writer-instructions.md` → "Universal output schema") for every such case. The orchestrator routes it to the user as a non-deterministic finding; the user decides whether to fix the source or accept the current behaviour. Your job is to surface it, not to decide it.

This keeps the writer from quietly resolving a design question that belongs to the user.

## Oracle for deterministic transforms (golden / known-answer values)

Some SUTs are **deterministic transforms** whose output is an opaque value a human cannot eyeball for correctness — a hash / fingerprint, a canonical serialization, an encoding, a formatted string. For these the expected value in the assertion is a **golden value**, and where that golden comes from decides whether the test has any power:

- **Sound (implementation-independent oracle)** — derive the expected value from a source **independent of the SUT**: a spec, a known-answer test vector, or an independent tool (e.g. `sha256sum` over the canonical bytes). The assertion then genuinely constrains the SUT. Prefer this.
- **Vacuous (tautological golden)** — run the SUT, observe what it returns, and paste that back as the expected value. The test then asserts "the SUT returns what the SUT returns": it can never fail for a logic bug in the code under test, and it freezes a day-one bug behind a green test. **Never do this.**

Because the two produce **byte-identical** assertion code, no one can tell them apart later — so **record the golden's provenance**: state, in a comment beside the assertion (or in a shared test-vector), how the expected value was derived and from what input. When the expected value **can only** come from running the SUT (no independent derivation exists), say so explicitly rather than presenting it as an oracle. Caveat: for a hash-of-serialization, re-deriving the golden with the same serialization code is **self-circular** — it can replicate the SUT's own bug — so the strongest oracle is a known-answer vector from a genuinely independent tool.

This is the writer-side guard against a **green-but-vacuous** test (an assertion that holds by tautology); the verifier independently re-checks provenance.

## Context Priority (when signals conflict)

Writer agents may receive context from three sources. When they disagree, follow this priority:

1. **Sibling tests** (highest) — what you observe in the actual nearest sibling file is the source of truth.
2. **Orchestrator pre-fetched context** — provided as an acceleration hint. If it conflicts with what you see in the sibling, **follow the sibling**.
3. **Convention file** (`.claude/conventions/tests/<type>-test-conventions.md` — e.g., `unit-test-conventions.md`, `integration-test-conventions.md`) — documents the most common patterns in the repo. Use as fallback only when no sibling exists. **Normally absent**: nothing generates this file. A repo has one only where someone deliberately wrote it to pin a convention the siblings do not show.

## Fallback Chain (when no sibling exists in the immediate directory)

If the target directory has no existing test files, **widen the search** before falling back to the convention file:

1. Parent directory
2. Nearby directory with the same base class or test infrastructure
3. Same layer in a different feature (e.g., another handler's tests)
4. Any test file in the same test project

Only if all of the above yield nothing: use the convention file's documented patterns as the sole reference **when that file exists**. When it does not — the normal case — **stop and report**: return your structured output now with no tests written, naming in `issues:` that neither a sibling nor a convention source was found and which directories you searched. Do not invent conventions, and do not write a test against conventions you inferred from the language alone. The orchestrator handles this stop (`common-orchestrator-flow.md` → "Writer stop on no convention source").

## Common Utilities Check

Before writing a new helper, assertion, or test data construct, check whether one already exists:

1. **Sibling first.** Whatever helper the sibling test uses is the one to use, even where something more
   generic exists elsewhere. In the common case this is the whole check.
2. **Widen only to remove duplication you would otherwise write.** If following the sibling would make
   you repeat the same construct several times, look for an existing shared helper: when the repo has a
   shared test project, `.claude/conventions/tests/project-architecture.md` names it and says which test
   projects reference it, and those tests show how it is called. Read the helper's own source before
   using it.
3. **Never introduce a utility that siblings do not use.** A helper nobody in this area calls is a new
   convention rather than a reuse — surface it as a suggestion in your output instead of writing it in.
4. **If `.claude/conventions/tests/project-architecture.md` is absent** (the normal state where setup has not run), step 2 has no
   catalogue to consult: widen to the sibling tests you already read and stop there. Do not go hunting
   the repo for a shared test project — an unused helper found that way is step 3's forbidden case.

## Common Verification Patterns Check

Before finalising a test, consult `.claude/conventions/tests/common-verification-patterns.md` (if it exists):

1. Determine the SUT's layer from its path (e.g., `/Handlers/` → Handler layer). Fall back to type inheritance if the path is ambiguous.
2. Read the layer-specific section plus the "General" section.
3. For each documented pattern: if the SUT uses the dependency or trait the pattern verifies, **include the verification** in your test.
4. **Sibling still takes priority** — if the sibling test has a different approach, follow the sibling.
5. If the file does not exist, skip this check.

This is a safety net for recurring verifications the codebase relies on (e.g., security checks). It is not a strict rule; sibling divergence is a valid reason to deviate.
