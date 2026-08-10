# verify-update-\<type\>-test-agent pattern

This doc describes the **per-type** `verify-update-<type>-test-agent` pattern — one agent per supported test type (`test-authoring:verify-update-unit-test-agent`, `test-authoring:verify-update-integration-test-agent`). The agents share the same six-step flow (below); type-specific extensions live in each per-type file — unit writers focus on deletion confirmations and build/run, integration adds `env_failure` distinction.

The `verify-update-<type>-test-agent` is a strictly **read-only** verification subagent spawned by the `update-<type>-test` orchestrator after the matching `update-<type>-test-agent` completes Phase 2 execution. Its purpose is to independently verify that deletions are justified by audit status, valid tests were preserved unmodified, all tests pass, no anti-deletion gaming occurred, and every action the writer reported or the record planned is actually visible in the diff. The verifier uses the `git show HEAD:<file>` committed state as its pre-change baseline. It never modifies any file -- it reports a structured pass/fail verdict to the orchestrator, which decides whether to offer rollback or proceed.

Template sources: [`test-authoring:verify-update-unit-test-agent.md`](../../agents/verify-update-unit-test-agent.md), [`test-authoring:verify-update-integration-test-agent.md`](../../agents/verify-update-integration-test-agent.md). Shared role boundary and output schema live in [`common-verifier-checks.md`](../../resources/templates/rules/common-verifier-checks.md).

---

## Lifecycle Diagram

```mermaid
flowchart TD
    A["Orchestrator spawns verify-update-&lt;type&gt;-test-agent"] --> B["Receive inputs:<br/>audit output, action record,<br/>git HEAD pre-change baseline, build/test command"]
    B --> C["Step 1: Audit-Justified Deletions"]
    C --> D["Step 2: Valid Tests Preserved"]
    D --> E["Step 3: All Tests Pass"]
    E --> F["Step 4: Anti-Deletion Gaming Check"]
    F --> F2["Step 5: Claimed Actions Happened"]
    F2 --> G["Step 6: Test Count Cross-check"]
    G --> H{"Any violations?"}
    H -- No --> I["Return PASS verdict"]
    H -- Yes --> J["Return FAIL verdict<br/>with violation list"]
    I --> K["Orchestrator receives report"]
    J --> K
```

The verifier is a **single-pass** agent. It runs six checks in sequence, collects all findings, and returns a structured report. It is never resumed across rounds — a fresh instance is spawned for each verification round (including [re-verification](../shared/readme-shared-orchestration.md#re-verification) after fix rounds). Writer agents now follow the same fresh-spawn pattern for fix invocations and update-flow Phase 2 — see [readme-shared-orchestration.md#fix-protocol](../shared/readme-shared-orchestration.md#fix-protocol) and [readme-shared-update-patterns.md#two-phase-lifecycle](../shared/readme-shared-update-patterns.md#two-phase-lifecycle).

---

## Inputs / Outputs

### Inputs

| Input | Source | Description |
|---|---|---|
| **Audit output** | Update agent (Phase 1) | Pre-change test list with pass/fail status for every method |
| **Action record** | Orchestrator (Step 4) | Per-test entries with `audit_status`, `action` (each action derived from audit status). Also decides whether the verifier is spawned at all, and for which files — never the writer's report of what it executed |
| **Execution results** | Update agent (Phase 2) | Every writer's Phase 2 output whole, one labelled set per source class: `changes_applied` (per method, `action: updated \| deleted`), the test file paths, `build_status`, `test_results`, `issues` (all self-reported). Step 5 reads `changes_applied`, so a summarised or single-writer hand-off strips what it needs |
| **git HEAD pre-change baseline** | Orchestrator (Step 4.5) | `git show HEAD:<file>` committed state for every file the action record names -- not only the ones reported as modified, or a writer that did nothing leaves nothing to diff |
| **Test type** | Orchestrator | `unit` or `integration` -- determines build/test commands |
| **Test project** | Orchestrator | Path to the test project under change |
| **Raw Phase 1 audit outputs** | Orchestrator (Step 2) | The audit records behind the action record -- the baseline for Step 1's transcription cross-check |
| **Consent-proceeded files** | Orchestrator (Step 4.5) | Files found untracked/dirty and proceeded on with explicit consent; their `HEAD` baseline is not faithful |
| **Step 5b add-writer outputs** | Orchestrator (Step 5b) | `files_created` / `files_modified` / `test_count`, when add writers also ran -- needed by Step 6's count arithmetic and by Step 5's per-method attribution |
| **Skipped files** | Orchestrator (Step 4.5) | Files the user declined -- a separate list from the consent-proceeded one. Step 5 treats a planned action with no visible change as a violation, and this list is the only thing that distinguishes "the user said no" from "the writer dropped it silently" |

### Output structure

The verifier returns a `verification_summary` with six sections (one per check), each containing a verdict and any violations, plus an overall verdict. PASS requires all six checks to pass with zero violations. Any single violation flips the overall verdict to FAIL.

---

## Verification Checks

All six checks always run -- the verifier does **not** short-circuit on the first violation, so the orchestrator receives a complete picture.

### Step 1 -- Audit-Justified Deletions

Every deleted test must have a corresponding action record entry with `action: delete` whose `audit_status` is `wrong` or `duplicated` (outdated-major is rewritten, never deleted).

1. Collect deleted test methods from the execution results.
2. Search the action record for a matching entry per deleted test.
3. **Independently verify** by diffing the committed baseline against the current file to catch deletions the writer failed to self-report:

   ```bash
   git diff HEAD -- tests/.../TestFile.cs
   ```

   The portable form. `diff <(git show HEAD:<file>) <file>` is equivalent only in a POSIX shell -- its process substitution is a syntax error in PowerShell.

**VIOLATION** if a deleted test has no `action: delete` entry, or its `audit_status` is anything other than `wrong` or `duplicated` (e.g. `valid`, `outdated-major`, or absent).

### Step 2 -- Valid Tests Preserved and Unmodified

Every test classified `valid` in the audit must still exist with content unchanged.

1. Find all action record entries with `audit_status: valid`.
2. Confirm each valid method is present in the current file.
3. Diff `git show HEAD:<file>` against the current file -- inspect for changes to valid test bodies, signatures, or attributes. Whitespace-only changes are ignored.

**VIOLATION** if a valid test was deleted or its content was modified.

### Step 3 -- All Tests Pass

All remaining tests must compile and pass.

1. Build the test project (`dotnet build <test_project>`).
2. Run tests filtered to the affected class (`dotnet test ... --filter`).
3. Classify failures using the pre-change pass/fail baseline (see [Failure Classification](#failure-classification)).

**VIOLATION** if the build fails due to the writer's changes, or any test updated by the writer now fails.

### Step 4 -- Anti-Deletion Gaming Check

Detect cases where a previously-failing test was silently removed to fake a passing suite. This is the most critical check -- see the full [decision table](#anti-deletion-gaming-decision-table) below.

1. From the audit output, collect all tests that were **failing** before Phase 2.
2. For each, check whether it still exists in the current file.
3. If missing, look up the action record (`action: delete`?) and the `audit_status`.
4. Apply the decision table to determine the verdict.

**VIOLATION** if a failing test disappeared without an audit-justified `action: delete` entry.

### Step 5 -- Claimed Actions Actually Happened

Steps 1-4 are all negative checks -- they ask whether something was done wrongly. None asks whether anything was done at all, so an execution agent that reports success and changes nothing passes all four. This step closes that by pairing the claim against the diff in both directions, and it is the mirror of Step 2: a `valid` method must be unchanged, a method reported as updated must be changed.

Every method that appears in `changes_applied` or is planned in the action record lands in exactly one of three sets, and each set has its own verdict rule. Evidence is attributed **per method inside its own hunk**, never at file grain — the Step 5b add writer may have written to the same file. Renames were already paired to their baseline names before Step 1, so a renamed method reads as changed here and not as an unjustified deletion in Steps 1 / 4.

1. **Reported and planned** — a reported `updated` method must differ from the baseline (whitespace-only does not count); a reported `deleted` method must be absent. Either failing is a violation, as is a reported update that turns out to be a deletion.
2. **Reported but not planned** — a violation **against the report, not the file**: E3 forbade touching the method, so the finding is that the writer's account is untrue and the remedy is not to make the change. Step 2 cannot cover this, because Step 2 only checks that `valid` methods are *unchanged* — which a false report of updating one leaves green.
3. **Planned but not reported** — a violation **unless a named exemption applies**: the file is in the skipped-files list (the user declined it at Step 4.5), the writer's `issues` records an E1 stop, the entry was evidenced in a carried-forward first round of a `fix_invocation`, or the entry is out of this verifier's scope. Without the exemption this is a planned action dropped in silence, the failure the whole check exists to catch.

A file whose baseline cannot be obtained is `not_performed`, and that is **a violation of the check, not a pass** — the absence of verification is never evidence of work. Rows on consent-proceeded files degrade to `baseline_unreliable` notes for the `updated` and `planned-only` cases, because `HEAD` is not their pre-change state and `unchanged` therefore proves nothing in either direction; the `deleted` rows stay live, since whether a method is present *now* is observable without a faithful baseline.

The verifier's own verdict is read row by row — every row `OK` or `note` — with no counter arithmetic to evaluate.

### Step 6 -- Test Count Cross-check

The final test count must match expectations.

```
expected = pre_change_count - planned_deletions + added_by_step_5b
```

`planned_deletions` are the action record's `action: delete` entries, not the deletions the writer reported — keying it on the report would make the check tautological, and a planned deletion that never happened is exactly what it should surface. `added_by_step_5b` comes from the add-writer outputs, and is `0` when Step 5b did not run.

Count `[Fact]` and `[Theory]` attributes in the post-change file and compare. Any mismatch is a red flag for unauthorized additions or removals outside the action record.

---

## Anti-Deletion Gaming Decision Table

This table is the centrepiece of the verifier's anti-gaming enforcement. It determines whether a test that existed in the `git show HEAD:<file>` baseline but is missing from the current file is a legitimate audit-justified deletion or a suspicious silent removal.

| In `git show HEAD`? | In current? | Was failing? | Audit status (in action record) | Verdict |
|:---:|:---:|:---:|:---:|---|
| Yes | Yes | -- | -- | **Preserved** -- test still present, no deletion to verify |
| Yes | No | Any | `action: delete` + wrong / duplicated | **Legitimate deletion** -- justified by audit status |
| Yes | No | Yes | any other status, or no delete entry | **VIOLATION: silent deletion of failing test** (anti-gaming) |
| Yes | No | No | any other status, or no delete entry | **VIOLATION: unjustified deletion** -- removed without audit justification |
| Yes | No | Yes | `action: delete`, but `audit_status: valid` | **VIOLATION: contradictory state** -- a "valid" test should not be both failing and deleted |
| No | Yes | -- | -- | **New test** -- expected if add-agent ran in Step 5b |

### Interpreting the table

The verifier iterates over every test method found in the `git show HEAD:<file>` baseline. If the method still exists in the current file, it was preserved and no further check is needed. If it is missing, the verifier cross-references the action record and the pre-change pass/fail baseline.

**A failing test that disappears without an audit-justified `action: delete` entry is the clearest signal of gaming.** The writer agent's fix rules ([`test-rules.md`](../../resources/templates/rules/test-rules.md)) explicitly prohibit deleting a failing test -- doing so removes evidence of a bug or regression. If such a deletion slips past the writer, the verifier catches it here.

The contradictory-state row (valid + failing + deleted) addresses a subtler scenario: a test classified as `valid` during audit should not be failing, and certainly should not be deleted. This combination suggests the audit classification was incorrect or the agent manipulated the status to justify removal.

Tests that appear in the current file but not in the `git show HEAD:<file>` baseline are new additions, typically produced by add-agents in Step 5b. These are verified by a separate `verify-add-<type>-test-agent` instance running in parallel (Step 6b), not by this agent.

---

## Why git HEAD as the baseline

The verifier diffs against `git show HEAD:<file>` because the orchestrator's Step 4.5 guarantees that committed state is a faithful pre-change baseline:

1. **Step 4.5 gate** -- before Phase 2, the orchestrator only auto-proceeds on files that are git-tracked and clean. Untracked or dirty files are flagged and proceeded on only with explicit user consent.

2. **Faithful pre-change state** -- because clean-and-tracked is the default precondition, `git show HEAD:<file>` reflects exactly what the file contained before Phase 2 wrote anything, with no contamination from the agent's edits.

3. **No sidecar files to manage** -- using git as the baseline removes the need to create, track, and clean up `.bak` files; there is one source of truth for the pre-change state.

4. **Rollback** -- `git restore <file>` returns a file to its committed state, so a failed verification can be undone without bespoke backup handling.

For the full git-based rollback model, see [readme-shared-update-patterns.md#git-based-rollback](../shared/readme-shared-update-patterns.md#git-based-rollback).

---

## Read-Only Constraints

The verifier enforces a strict read-only contract:

- **Never modifies files in `src/` or `tests/`** -- all checks use `diff` and file reads, never edits.
- **Checks the writer did not modify source code** by running `git diff src/` and verifying no SUT files were changed. Source changes are reported as an anti-gaming violation.
- **Never creates `[Skip]` attributes** or comments out tests -- explicitly prohibited by the [fix rules](../../resources/templates/rules/test-rules.md).
- **Never deletes tests** -- even clearly wrong tests are reported, not removed.
- **Never attempts repair** -- all findings go to the orchestrator, which routes deterministic issues to the writer agent and presents non-deterministic issues to the user.

This independence is essential for trust. By restricting the verifier to observation and reporting, the orchestrator can rely on its findings as an unbiased audit.

---

## Failure Classification

The verifier distinguishes pre-existing failures from failures introduced by the writer agent, preventing false positives.

**Pre-existing failures**: the test was already failing in the audit output's pass/fail baseline (Phase 1). Noted in the report but **not** counted as violations.

**New failures introduced by Phase 2**: the test was passing before and now fails, or was updated by the writer and now fails, or the build fails due to the writer's changes. Reported as **violations** and routed to the original writer agent via the [fix protocol](../shared/readme-shared-orchestration.md#fix-protocol). The [circuit breaker](../shared/readme-shared-orchestration.md#circuit-breaker) limits how many fix-verify rounds can occur.

### Classification flow

```mermaid
flowchart TD
    A["Test failure detected"] --> B{"Was this test<br/>failing before Phase 2?"}
    B -- Yes --> C["Pre-existing failure<br/>(not a violation)"]
    B -- No --> D{"Was this test<br/>modified by the writer?"}
    D -- Yes --> E["New failure: VIOLATION<br/>Route to writer via fix protocol"]
    D -- No --> F["New failure: VIOLATION<br/>Possible collateral damage"]
```
