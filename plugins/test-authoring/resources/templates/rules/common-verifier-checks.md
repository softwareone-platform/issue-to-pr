---
schema_version: "1.8"
description: Shared reference for per-type test verifier agents. Covers the universal review methodology, anti-gaming checks, spec-vs-impl divergence cross-check, build/test execution, output discipline, output schema, and orchestrator routing. Each verify-add-{type}-test-agent (and verify-update-{type}-test-agent) references this file and adds its own type-specific checks on top.
paths: [".claude/rules/tests/common-verifier-checks.md"]
---

# Common Verifier Checks

> **Consumers** — `test-authoring:verify-add-unit-test-agent`, `test-authoring:verify-add-integration-test-agent`. The `verify-update-*-test-agent` variants are **partial consumers**: they follow their own input contract, check sequence, output schema, and routing (defined in their agent files), and consume only the role boundary and the U4 build/run expectations here.
>
> This document holds what every per-type verifier does identically. Per-type checks (assertion-style fidelity for unit, seeded-data expectations for integration, etc.) live in each per-type verifier file. Keep this file minimal — if a check is not truly universal, it belongs in the per-type file.

## Role boundary

> **Verifier agents are strictly read-only.** You MUST NOT modify any files. You check conventions, detect gaming, evaluate quality, and run build/tests. You report all findings to the orchestrator — the orchestrator decides how to handle fixes.

You did NOT write the tests under review. Your job is **independent** quality control. Do not re-do the writer's work; check it.

## Universal input contract

Every per-type verifier receives a prompt containing one or more writer agent results, each including at minimum:

- **Test file paths** — files the writer created or modified
- **Convention spec** — structured conventions the writer claims to have adopted
- **Sibling test paths** — sibling files the writer referenced
- **Test results** — which tests the writer reported as passed/failed
- **Test type** — one of the confirmed test types (all items in a single invocation share the same type)
- **Original task / spec description** — the task as originally given (not only the writer's reported results), so you can sanity-check the writer's `spec_vs_impl_divergence` flags (see U2b) against what the task actually asked for
- **Pre-writer source snapshot** — the orchestrator's record of `{{SRC_DIR}}`'s state taken before any writer was spawned (e.g. the `git diff -- {{SRC_DIR}}` output at that moment); the baseline for the U3 SUT-modification check

Per-type verifiers may extend this with extra fields. Extensions live in the per-type file, not here.

## Universal check sequence

Per-type verifiers run these five checks (U1, U2, U2b, U3, U4) in order before any type-specific checks. Per-type files may insert additional steps between or after these — the ordering contract is that **spot-check happens first, the divergence cross-check (U2b) follows convention compliance (U2), build/run happens last, anti-gaming happens before quality review**.

### U1. Spot check convention spec

The writer reports which conventions it adopted. You MUST NOT blindly trust this — **read 1-2 sibling test files** from the provided paths to independently verify the claim.

Check against the sibling convention checklist in the applicable `.claude/conventions/tests/{test-type}-test-conventions.md` for the test type under review.

If the writer's reported spec does not match the actual sibling, use **what you observe in the sibling** as the source of truth — not what the writer claimed.

If the writer reported `No sibling tests found` (the orchestrator's no-sibling fallback), there are no paths to spot-check — verify the new tests directly against the convention doc instead, which was the writer's mandated fallback source.

### U2. Convention compliance check (report only)

Read each generated **or modified** test file and compare against the verified conventions from U1.

Universal checks that apply across all test types:

- Wrong mocking/stubbing approach vs siblings
- Wrong fixture/setup helper vs siblings
- Wrong base class / missing inheritance vs siblings
- Wrong naming pattern vs siblings
- Missing or extra AAA-style comments inconsistent with sibling style
- Wrong SUT construction approach
- Project-wide rule violations (formatting, naming, language-idiom) as defined in `.claude/rules/tests/test-rules.md`

For each violation, record:

- File path and line number(s)
- What the writer used vs what the sibling convention requires
- Whether it is a mechanical fix (find-and-replace) or requires logic changes

Per-type verifiers add type-specific compliance checks (e.g. assertion-style fidelity for unit). Those belong in the per-type file, not here.

**Do NOT modify the files.** The orchestrator will apply fixes.

### U2b. Spec-vs-implementation divergence cross-check (report only)

A writer tests **observable behaviour**, which is correct — but when the SUT contradicts the task spec, the writer is required to report it via `spec_vs_impl_divergence` rather than silently codify it (see `.claude/rules/tests/test-writer-rules.md` → "When observed behaviour contradicts the spec"). You are the safety net that this was not lost:

1. Read the **original task / spec description** from your input.
2. For each `spec_vs_impl_divergence` entry the writer reported, confirm the test was written against the observed behaviour (not the spec) and that the note accurately describes the mismatch.
3. **Independently** scan for a divergence the writer did NOT flag — a test that asserts behaviour contradicting the task description with no matching divergence entry. A silently-codified divergence (a real bug frozen behind a green test) is exactly what this check exists to catch.

Surface every divergence as a **non-deterministic finding** — the user decides whether the SUT is buggy (fix source) or the spec is stale (accept the test). Do NOT treat a divergence as a convention violation to auto-fix, and do NOT pass `🟩` purely because the test matches the SUT — a test can match a buggy SUT.

**Do NOT modify the files.**

### U3. Anti-gaming check (report only)

Search all generated **or modified** test files for signs that the writer bypassed failures instead of fixing them:

1. **Skip/ignore attributes** — no test should be skipped. Exact form depends on framework; grep for the equivalents: `[Fact(Skip=...)]`, `[Theory(Skip=...)]`, `@Ignore`, `@pytest.mark.skip`, `xit(`, `test.skip(`, etc.
2. **Commented-out test methods**
3. **Test count mismatch** — does the number of test attributes match what the writer reported? For files the writer created, count all test attributes; for files the writer modified, count the added attributes in that file's diff — the writer's `test_count` covers only its own additions.
4. **SUT modifications** — compare the current `{{SRC_DIR}}` state against the **pre-writer source snapshot** from your input. In Mode A the user's own uncommitted source changes are expected, so `git diff` alone cannot distinguish them from writer tampering — flag only differences that appeared **after** the writers started.
5. **Tautological / vacuous golden value** (deterministic-transform SUTs only) — when a test asserts an **opaque expected value** from a deterministic transform (hash / fingerprint, canonical serialization, encoding, formatting), decide whether that golden is an **implementation-independent oracle** or merely **captured from the SUT's own output** (a tautology: the test asserts the SUT returns what it returns, freezing a day-one bug green). You **cannot** tell from the assertion text alone — an independently-derived golden and a pasted-back one are byte-identical — so check **provenance**: is the golden's derivation stated (a comment, a known-answer vector, an independent tool such as `sha256sum` over a stated input), and can you **independently recompute** it from that stated derivation and get a match? A golden with no stated provenance, or one you cannot independently reproduce, is a **green-but-vacuous** finding. This is a provenance / adequacy check — it shows the golden is not a tautology, it does not prove the oracle is semantically correct.

For each violation, record:

- File path and line number(s)
- Type of violation (skip, commented-out, count mismatch, SUT modified, tautological-golden)
- Details

**Do NOT modify the files.** The orchestrator routes these to the user (non-deterministic — needs human judgement).

### U4. Build and run verification (report only)

Build and run the tests. Reference `.claude/rules/tests/test-rules.md` for the exact build/test commands per test project.

- If the build fails, report the errors.
- If tests fail, report which tests failed and why.
- If tests fail due to environmental issues (container runtime, Docker unavailable, network), report as `env_failure` rather than attempt a fix.

Do NOT attempt to fix any failures — only report.

## Universal output schema

> **Output discipline (CRITICAL)**: the structured summary is data the
> orchestrator parses — not a human-facing message. (1) **Payload first** — it
> MUST be the first content in your final message, no prose preamble. (2)
> **Verbatim, always** — return the full summary even when the spawning prompt
> already contains the answer; never degrade to a "review complete, see above"
> acknowledgement. (3) **English payload** — keys, values, table content in
> English; only a trailing free-text note may follow the session's language.

Per-type verifiers return a structured summary with at minimum the following fields. Per-type verifiers MAY add extra fields (e.g. `guideline_violations`, `step_reuse_violations`, `assertion_mode_validation`) — those are declared in the per-type file.

```
test_type: <one of the confirmed test types>

files_reviewed:
- <path>

convention_spec_verified: yes | no (<discrepancies found>)

convention_violations:
- <path>:<line>: <what writer used> → should be <what sibling/convention requires> (mechanical: yes | no)
(or "none")

anti_gaming_violations:
- <path>:<line>: <type> — <details>
(or "none")

quality_flags:
- <TestName or ScenarioName>: <concern> — suggested: <improvement>
(or "none")

spec_vs_impl_divergence:
- <path>: SUT does <source behaviour> vs task/spec expected <expected> — writer_flagged: yes | no
(or "none")

build_status: success | failed (<errors>)

test_results:
- <TestName or ScenarioName>: passed | failed (<reason>) | env_failure (<reason>)

issues:
- <description> (or "none")
```

## Routing for the orchestrator

See `.claude/rules/tests/fix-protocol.md` for the authoritative fix-protocol. In summary:

- **Deterministic** — orchestrator fresh-spawns the writer with a `fix_invocation` block, with circuit breaker (limits per `.claude/rules/tests/fix-protocol.md` — the single source of truth for the counters):
  - `convention_violations`
  - `build_status: failed`
  - `test_results: failed` (non-environmental)
  - Per-type deterministic additions declared in the per-type verifier file
- **Non-deterministic** — present to the user, do not auto-route:
  - `anti_gaming_violations`
  - `quality_flags`
  - `spec_vs_impl_divergence` (the user decides whether the SUT is buggy or the spec is stale — never auto-fixed)
  - `env_failure`

  When the user approves a fix for a non-deterministic finding, the orchestrator routes the approved instruction via the same fresh-spawn `fix_invocation` block (with `findings_to_fix.user_approved_actions` populated). The orchestrator does NOT edit files itself — see `.claude/rules/tests/common-orchestrator-flow.md` → "Role boundary".

Re-verification after each fix round spawns a **fresh** verifier instance (do NOT reuse the previous one — independence is a quality-control requirement).

## Extending this file

When you find yourself writing the same check in two or more per-type verifier files, consider lifting it here. Conversely, if a check in this file only applies to one test type in practice, move it out to that per-type file. The goal is: each per-type verifier file reads like `common-verifier-checks.md` + the narrow delta for its test type.
