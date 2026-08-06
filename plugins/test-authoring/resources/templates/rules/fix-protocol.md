---
description: Protocol for handling verifier findings — routing deterministic issues to writer agents via fresh-spawn fix_invocation with circuit breaker, presenting non-deterministic issues to user.
---

# Verifier Fix Protocol

When a read-only verifier agent (`test-authoring:verify-add-<type>-test-agent` or `test-authoring:verify-update-<type>-test-agent` — one per supported test type, e.g. `test-authoring:verify-add-unit-test-agent`, `test-authoring:verify-add-integration-test-agent`) reports findings, the orchestrator routes them based on determinism.

> **Orchestrator role boundary (CRITICAL)** — The orchestrator NEVER applies file edits itself. It does not invoke `Write` / `Edit` / `MultiEdit` on test files under any circumstances, including when a fix is small, when the user has already approved the change, or when a writer agent appears unavailable. All edits go through writer agents. If you cannot route a fix, follow the "On circuit break" steps below — do not "just do it yourself".

## Deterministic issues → fresh-spawn writer with `fix_invocation` block

Convention violations and build/test failures are deterministic — there is a correct fix. Re-invoke the writer agent **as a fresh spawn via the `Agent` tool**, passing a structured `fix_invocation` block. The orchestrator does NOT continue a previous writer instance — every fix round is a new agent spawn (mirroring the verifier's single-pass pattern).

```
Agent(subagent_type="test-authoring:<add-or-update>-<type>-test-agent"):
  fix_invocation: true

  plugin_context:                     # always — a fresh spawn resolves neither field itself
    plugin_resources_path: ...        # absolute path of the plugin's resources/templates dir
    build_test_command: ...           # session-detected; the writer adjusts --filter to its test class

  original_scope:
    source_files: [...]               # same list passed to the first writer
    method_filter: ...                # if any
    test_type: unit | integration

  pre_fetch:
    sibling_paths: [...]              # from orchestrator pre-fetch (add flow) or the Phase 1 audit (update flow)
    convention_spec: {...}            # same provenance as sibling_paths

  previously_produced:
    files_created: [...]              # from prior writer's universal output schema
    files_modified: [...]
    convention_spec_adopted: {...}    # what the prior writer actually adopted
    last_build_status: success | failed (<errors>)

  findings_to_fix:
    convention_violations:
    - <file>:<line>: <what was used> → should be <correct convention>
    build_failures:
    - <test name>: <error message>
    test_failures:
    - <test name>: <reason>
    user_approved_actions: []         # populated only on the quality-flag / anti-gaming user-approval path; see "Non-deterministic issues" below

  instructions: |
    Read your previously_produced files at the listed paths.
    Apply targeted fixes for everything in findings_to_fix.
    Do NOT regenerate from scratch.
    Return the universal output schema (files_modified, build_status, ...).
```

The orchestrator already holds every field of this block in working state (plugin_context from Step -1, pre_fetch from Step 2, previously_produced from the prior writer's structured return, findings_to_fix from the verifier's structured return). `plugin_context` is not optional here: a fix spawn is a *fresh* agent that stops immediately without it, so omitting it turns every fix round into a stop. No new caching mechanism is required — this is a structured prompt assembled from records the orchestrator already keeps for the final summary.

The block is written in add-flow terms; map the equivalents for other writers. **Update writers** (the verify-update single-fix-attempt path): `pre_fetch` comes from the Phase 1 audit, `previously_produced` maps from the execute output contract (`changes_applied` and `deleted_tests_record` → files_modified, `build_status` → last_build_status). Fields with no equivalent are omitted — the writer treats the prompt as authoritative.

### Protocol stops do not count

A subagent that returns early with a `stop_reason` — `no_convention_source`, `missing_framework_source`,
or `missing_plugin_context` (see `common-orchestrator-flow.md`) — has not failed a fix attempt. It wrote nothing, so there is nothing
to have got wrong. **Do not increment any counter below for such a return**, and do not route it through
the fix protocol at all: it has its own handler.

## Circuit breaker (CRITICAL)

Two independent counters prevent infinite loops. **Either counter reaching its limit triggers a stop.**

#### Counters

| Counter | Limit | Scope | Purpose |
|---|---|---|---|
| **Global round count** | **3** | Per source-class fix lineage | Caps total fix-verify cycles regardless of which issues appear. The lineage spans every fix round for one source-class writer chain — whether each round is a fresh-spawn of the same writer type, the counter accumulates across rounds. Prevents cascading-fix loops where fixing A reveals B, fixing B reveals C, etc. |
| **Per-issue retry** | **2** | Per individual issue | Caps retries for the same issue. If the same issue is reported again after being sent for fix, increment its retry count. Issue identity is `(file, violation_type, location)` — prefer the test/method name over a raw line number for `location`, so the identity survives line shifts caused by earlier fixes in the same lineage; independent of which writer agent ID handled the previous round. Prevents a stubborn issue from consuming all global rounds. |

#### Tracking

Each round, the orchestrator spawns a fresh writer with **all** outstanding issues in the `findings_to_fix` block of the `fix_invocation` prompt. After the writer returns and a new verifier verifies:

1. For each issue reported by the new verifier, check if it was also reported in a **previous round of the same fix lineage**:
   - **Same issue** (same file, same violation type, same location) → increment that issue's per-issue retry count
   - **New issue** (not seen before) → initialize its per-issue retry count at 1
2. Increment the global round count for this lineage.

Keep both counters visible in the conversation — emit one status line per round (e.g. `lineage <class>: global round N/3; <issue> retry M/2`) so the counts survive context compaction in long sessions.

#### Stop conditions

Stop the fix loop when **any** of these is true:

- **Global round count reaches 3** — regardless of issue status
- **A specific issue reaches per-issue retry 2** — stop retrying that issue (it may still be included in the unresolved list, but do not send it back again; other new issues in the same round can still be sent if global count allows)
- **Verifier reports zero issues** — all fixed, exit successfully

#### On circuit break

When a stop condition is reached with issues still remaining:
- Report remaining issues as **unresolved** in the summary
- Mark affected test files as 🟥 Failed
- Do NOT attempt further fix rounds
- Do NOT delete or skip the problematic tests
- Present the unresolved issues to the user with the error details so they can fix manually

#### Example flows

**Normal (cascading fix, resolved in 3 rounds):**
```
Round 1: issues [A, B] → writer fixes both → verifier: A fixed, B fixed, new C found
Round 2: issues [C] → writer fixes C → verifier: C fixed, new D found
Round 3: issues [D] → writer fixes D → verifier: all clear ✓
```

**Stubborn issue (per-issue limit):**
```
Round 1: issues [A] → writer attempts fix → verifier: A still present (A retry 1)
Round 2: issues [A] → writer attempts fix → verifier: A still present (A retry 2 = limit)
Stop: A reported as 🟥 unresolved
```

**Cascading with no convergence (global limit):**
```
Round 1: issues [A] → writer fixes A → verifier: new B (global 1)
Round 2: issues [B] → writer fixes B → verifier: new C (global 2)
Round 3: issues [C] → writer fixes C → verifier: new D (global 3 = limit)
Stop: D reported as 🟥 unresolved
```

### Re-verification after fixes

After each fix round, the orchestrator should re-run the verifier to check if the fixes resolved the issues. Use the same verifier agent invocation pattern — spawn a new instance of the verifier type that produced the findings (`test-authoring:verify-add-<type>-test-agent`, or `test-authoring:verify-update-<type>-test-agent` on the update-writer single-fix-attempt path). Do NOT reuse the previous instance — independence is a quality-control requirement.

## Non-deterministic issues → present to user

Anti-gaming violations and quality flags require human judgement. The orchestrator presents them directly to the user without attempting automated fixes.

### Anti-gaming violations
- Skip/ignore attributes found → ask user whether to remove and accept potential test failures
- Commented-out tests → ask user whether to uncomment
- SUT modifications detected → diff the current source against the **pre-writer source snapshot**: only changes that appeared after the writers started are writer tampering — the user's own uncommitted changes (expected in Mode A) must NOT be touched. Present the writer-introduced diff to the user and revert it only with their consent; never run a blanket `git restore` over the source tree
- Test count mismatch → investigate and report discrepancy

### Quality flags
- Present each flag with the test method name, concern, and suggested improvement
- The user decides whether to act on them — these are subjective observations, not errors

### Routing user-approved fixes

After the user approves a quality-flag fix or anti-gaming remediation, the orchestrator routes the approved action to the writer using the **same fresh-spawn `fix_invocation` protocol** as deterministic findings — populate the `findings_to_fix.user_approved_actions` field with the user's confirmed instruction (e.g. "rename test method `X` to `Y` per quality flag", "remove `[Skip]` attribute on `Z` and accept the resulting failure"). The orchestrator NEVER applies the change itself, even if the change looks small or the user is in a hurry — its role is to package the user's decision into the writer's input contract and spawn the writer.

The circuit breaker still applies: a round triggered by `user_approved_actions` counts toward the same global round count and any same-issue retry counter.
