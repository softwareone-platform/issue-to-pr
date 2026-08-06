---
name: update-unit-test
description: >
  Audit and update unit tests for changed source signatures or a user-specified target. Two-phase: audit first, then execute automatically (no confirmation gate — actions derive from audit status; git is the rollback). Trigger phrases: "update unit tests for X", "the test for X is stale", "refresh unit tests". Do NOT trigger for: questions about how to write a unit test, refactoring discussions, or general test maintenance topics.
---


## Step -1 — Resolve where the rule books and conventions come from

This skill runs **with or without** a prior `setup-test-context`.

**Resolve the plugin templates root once, unconditionally** — you also pass it to every subagent (audit, execute, add, and both verifiers), because subagents cannot resolve it themselves. The bundled rule books sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`), run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool; if `$CLAUDE_SKILL_DIR` is empty too, **stop and ask the user for the `test-authoring` plugin install path**. Do not carry on with it unresolved: every rule this skill obeys lives under it, so continuing would drop the rule books silently instead of failing. The Read tool normalises the `../..` segments.

Two kinds of file, resolved differently:

- **Rule books.** Every `<PLUGIN_TEMPLATES>/rules/…` and `<PLUGIN_TEMPLATES>/shared/…` path below is literal — read it from there. Inside a rule book, a bare filename means a sibling rule book in that same `rules/` directory, and a `../shared/<f>` path is relative to it. Nothing writes any of them into a repo, so there is no per-repo copy to prefer and none to fall out of date. Read each lazily, at the step that uses it — never as an upfront batch (see "Orchestrator reading list").
- **Conventions.** `.claude/conventions/tests/…` is the repo's own cache, written only where `setup-test-context` has run. Treat every one as **optional**: prefer the nearest sibling test for the scope (the audit's top-priority source anyway); when no sibling exists either, the writer reports the gap rather than inventing conventions — there is no language baseline to fall back to. A missing conventions file is never fatal.

If `.claude/conventions/tests/project-architecture.md` is absent, say so once: `"No cached repo profile — deriving from siblings. Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then carry on — it blocks nothing.

**Detect once, reuse this session**: the language, and an *executable* build/test invocation (test-project path + filter syntax, e.g. `dotnet test <proj> --filter "FullyQualifiedName~<Class>"`) from the project manifest. `test-rules.md` carries no command list — the detected command is the only source, used everywhere (audit test-run, execute build, both verifiers' build, the final multi-agent build). Pass it as `build_test_command` to **every** subagent spawn (audit, execute, add, verify-update, verify-add); the writer/verifier adjust its `--filter` to the actual test class.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.
- **At the step that uses it**: Step 1 → `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`. Step 3 (an audit issue cites the Source-change advisory) or Step 5a (the full `phase: execute` structure beyond the inlined block) → `<PLUGIN_TEMPLATES>/rules/common-update-instructions.md`, and only its orchestrator-facing sections ("Phase 2 invocation contract", the advisory) — the Phase 1 audit and Phase 2 execute procedure bodies are the update-writer's own rule book. Final multi-agent build → `<PLUGIN_TEMPLATES>/rules/test-rules.md` (use the session-detected `build_test_command`). First verifier finding or attributable build failure → `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`. A writer stopping on missing framework source → `<PLUGIN_TEMPLATES>/rules/sut-analysis.md` → "Runtime resolution flow". A writer stopping on no convention source → `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Writer stop on no convention source".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`. They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Update Unit Tests

You are the orchestrator for unit test maintenance. Your job is to **audit existing tests**, **present findings**, and then **delegate changes** derived from the audit status to subagents (no confirmation gate — git is the rollback). Follow the universal flow in `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`; this file only documents unit-specific pieces.

> Every `<PLUGIN_TEMPLATES>/…` and `.claude/conventions/tests/…` read below follows **Step -1's resolution** — and happens lazily, at the step that uses it, never as an upfront batch; a body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. Pass `plugin_resources_path` and `build_test_command` into **every** subagent spawn — audit, execute, add, and both verifiers — they cannot resolve these themselves. All `<plugin-root>/resources/static/status-legend.md` references below resolve to `<PLUGIN_TEMPLATES>/../static/status-legend.md` (Step -1), which is always resolved by then — Step -1 stops rather than continuing without it.

> **CRITICAL — Deletion safety**: deletions and rewrites are driven by the **audit status** (not a user gate) and applied automatically. A test may be deleted only when the audit classified it `wrong` or `duplicated` — never when `valid` or `outdated-major` (an outdated-major test still carries intent worth preserving: it is rewritten, never deleted). Every action is recorded in an **action record** and passed to `test-authoring:verify-update-unit-test-agent`, which independently re-checks each deletion against `git show HEAD:<file>`. Git is the safety net: a tracked test file can be restored with `git restore`.

## Step 1 — Identify Scope

Follow the procedure in `<PLUGIN_TEMPLATES>/shared/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Focus on new public/internal methods or classes, modified method signatures or logic branches, new command/query handlers, and new service methods.
- **Mode B** (argument provided, e.g., `/test-authoring:update-unit-test ComponentName`): Resolve by directory, component, class, method, or file name.

## Step 2 — Audit via Agent

Spawn `test-authoring:update-unit-test-agent` — one per source class, all in parallel. These agents perform Phase 1 (audit) and return structured results, then terminate.

Parallel audits may contend on the shared test project build during the audit's test-run step (e.g. Windows file locks). If an audit reports a build failure that looks like contention rather than a real break, re-run that audit serially before trusting the result.

**Retain each agent's audit output** — Phase 2 in Step 5a is a fresh `Agent` spawn whose prompt carries the audit record forward (the orchestrator does not continue a live Phase 1 instance).

```
Agent(subagent_type="test-authoring:update-unit-test-agent"):
  Audit existing unit tests for:
  - <source file path>
  Plugin context (always — the subagent cannot resolve either of these itself):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <session-detected build/test invocation>
```

### Method-scoped

When the user specifies a method, include it in the agent prompt as "Focus only on <method>".

## Step 3 — Present Audit Summary

Collect audit results from all agents and present a structured summary to the user. Group by source class.

> **Rendering rule (MUST)**: the Test Audit section MUST be rendered as a single markdown table — never as a numbered list, bullet list, or separator-bar format (e.g., `────`). Missing coverage items are appended as rows with status `🟦 pending` (per `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary)), continuing the `#` numbering.

### Test Audit: `{ClassName}` (unit)

| # | Method | Status | Confidence | Description |
|---|---|---|---|---|
| 1 | `<TestMethod>` | 🟩 valid | — | matches current SUT logic |
| 2 | `<TestMethod>` | 🟨 outdated-major | high | <what changed> |
| 3 | `<TestMethod>` | 🟨 outdated-minor | high | <tweak needed> |
| 4 | `<TestMethod>` | 🟪 duplicated | medium | overlaps with #2 |
| 5 | `<SUTMethod>` | 🟦 pending | — | no test covers this (to add) |

**Status legend**: see `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Statuses used: 🟩 valid, 🟨 outdated-minor, 🟨 outdated-major, 🟥 wrong, 🟪 duplicated, 🟦 pending.

**Confidence legend**:
- **high** — clear structural evidence
- **medium** — requires behavioural analysis, review recommended
- **low** — subjective assessment, **review carefully before confirming**

Flag medium/low confidence items prominently — review happens post-run (Step 7 summary + `git restore`), not as a pre-execution gate.

Use a **sequential number (#)** across all source classes so the user can reference items by number.

### Pre-change Test Results

Render as a single markdown table. Use only icons defined in `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary).

| # | Test Method | Status | Notes |
|---|---|---|---|
| 1 | `<TestMethod>` | 🟩 pass | baseline |
| 2 | `<TestMethod>` | 🟥 fail | pre-existing (inspect before update) |

### Audit Issues

Surface any `issues:` entries from the audit records verbatim — in particular the **source-change advisory** (the audit detected that test staleness comes from uncommitted source changes; see `<PLUGIN_TEMPLATES>/rules/common-update-instructions.md` → "Source-change advisory"). The advisory is informational — execution proceeds without a gate — but surfacing it now lets the user interrupt and commit/stash the source, keeping a single coherent git baseline for rollback.

## Step 4 — Determine Actions (from audit status)

Derive each item's action from its **audit status** — there is no user gate:

- 🟨 `outdated-major` → **Update (rewrite)**
- 🟨 `outdated-minor` → **Update (tweak)**
- 🟥 `wrong` → **Update** (or **Delete** if the test asserts behaviour the SUT no longer has and no corrected assertion is meaningful)
- 🟪 `duplicated` → **Delete** (the surviving duplicate stays)
- 🟦 `pending` → **Add**
- 🟩 `valid` → **no change** (never modified or deleted)

> **Rendering rule (MUST)**: present the planned actions as a single markdown table — never bracket codes. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Action verbs (Update / Tweak / Delete / Add / —) stay plain text. This table is the **audit trail for the summary**, not a gate — execution proceeds without waiting for a reply.

### Proposed Actions

| # | Item | Action | Audit Status | Confidence | Notes |
|---|---|---|---|---|---|
| 2 | `<Test>` | Update (rewrite) | 🟨 outdated-major | high | <reason> |
| 3 | `<Test>` | Update (tweak) | 🟨 outdated-minor | high | <tweak description> |
| 4 | `<Test>` | Delete | 🟪 duplicated | medium | overlaps with #2 |
| 5 | `<method>` | Add | 🟦 pending | — | no test covers this |
| 1 | `<Test>` | — | 🟩 valid | — | no change |

Flag any `low`/`medium`-confidence action in the Notes column so the user can review it post-run (the summary is where they catch a mis-classified action and `git restore` it).

### Build Action Record

Build a structured **action record** with `audit_status`, `confidence`, and `action` for each item. This drives Phase 2 and is the baseline the verifier checks deletions against — a deletion whose `audit_status` is anything other than `wrong` or `duplicated` is a violation.

## Step 4.5 — Pre-write git safety check

Git is the backup — there are no `.bak` files. Before executing changes, check each test file that will be modified:

```bash
git status --porcelain -- <test-file>
```

- **Tracked and clean** (no output) → proceed. `git show HEAD:<test-file>` is the faithful pre-change baseline the verifier diffs against, and `git restore <test-file>` undoes the change.
- **Untracked, or has uncommitted modifications** (any porcelain output) → warn the user: this file has no reliable committed baseline, so an automatic update cannot be safely diffed or restored. Ask whether to proceed for that file or skip it; proceed only on explicit confirmation.

Record, per modified file, that the pre-change baseline is `git show HEAD:<file>` — this is what the verifier uses in Step 6a. Also record which files were proceeded on explicit consent despite being untracked/dirty: that list goes to the verifier in Step 6a, because HEAD is not a reliable baseline for them.

## Step 5 — Execute Changes

Split the action record's actions and execute **sequentially** (update/delete first, then add). Before spawning the first execution agent (5a or 5b), record the **pre-writer source snapshot** per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Pre-writer source snapshot" — the add-verifier needs it as the baseline for its SUT-modification check.

### Step 5a — Update and Delete (fresh-spawn Phase 2)

Phase 2 is a **fresh-spawn** `Agent` invocation with `phase: execute` in the prompt. Do not attempt to continue a Phase 1 agent — every Phase 2 is a new spawn that re-reads files from the paths in the prompt. See `<PLUGIN_TEMPLATES>/rules/common-update-instructions.md` → "Phase 2 invocation contract" for the full structure.

Spawn one `test-authoring:update-unit-test-agent` per source class whose action record has update/delete actions.

Phase 2 agents that share a test project hit the same build contention as Step 2's parallel audits (e.g. Windows file locks) — spawn them **sequentially per test project**; if a contended-looking build failure still appears, re-run that agent serially before trusting the result.

```
Agent(subagent_type="test-authoring:update-unit-test-agent"):
  phase: execute

  original_scope:
    source_files: [<from Step 1>]
    method_filter: <if any>
    test_type: unit

  pre_fetch:
    sibling_paths: [<from Step 2 audit>]
    convention_spec: {<from Step 2 audit>}

  audit_record:
    <full audit output from this source class's Phase 1 agent>

  planned_actions:
    update:
    - <Test>: <audit_status>
    delete:
    - <Test>: <audit_status>
    add: []   # add actions handled in Step 5b via test-authoring:add-unit-test-agent

  test_file_paths: [<from audit_record.test_file>]
  consent_proceeded_files: [<from Step 4.5, or empty>]

  plugin_context:      # always — the subagent cannot resolve either of these itself
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <session-detected build/test invocation>
```

### Step 5b — Add Missing Coverage via `test-authoring:add-unit-test-agent`

After update/delete agents complete, spawn `test-authoring:add-unit-test-agent` for the action record's **add** actions — one agent per source class.

```
Agent(subagent_type="test-authoring:add-unit-test-agent"):
  Generate unit tests for:
  - <source path>
    Cover <method>: no tests exist
  Sibling tests found during audit (adopt their conventions):
  - <path> (<convention spec summary>)
  Plugin context (always — the subagent cannot resolve either of these itself):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <session-detected build/test invocation>
```

If the audit reported `no_existing_tests: true` (no siblings found), omit the sibling lines and state instead: `No sibling tests found and no convention source — apply test-writer-rules.md → Fallback Chain`. Nothing generates `{type}-test-conventions.md`, so do not point the writer at it. Never invent a sibling path to satisfy the template.

Skip this step if the action record has no add actions.

### Multi-agent build check

If multiple agents were spawned across 5a and 5b, run a final build. Follow `<PLUGIN_TEMPLATES>/rules/test-rules.md` → Build and Test Verification, using the session-detected `build_test_command`.

## Step 6 — Verify

### Step 6a — Verify Updates and Deletions

Spawn **one** `test-authoring:verify-update-unit-test-agent`. Strictly read-only. Pass:
1. Pre-change state (including which tests were failing)
2. Action record (audit_status + action per item)
3. Execution results
4. Pre-change baseline: `git show HEAD:<file>` for each modified file (no `.bak`)
5. Test type: `unit`
6. Test project path
7. Raw Phase 1 audit outputs (retained in Step 2) — so the verifier can cross-check that the action record faithfully transcribes each audit classification
8. Consent-proceeded files from Step 4.5 (untracked/dirty at check time) — their HEAD baseline is unreliable; the verifier treats diff-based findings on them as advisory, not violations
9. Step 5b add-writer outputs (`files_created` / `files_modified` / `test_count`), when Step 5b ran — the add writer may insert tests into the SAME files 6a inspects, and without these the verifier's test-count cross-check reads the additions as out-of-record changes
10. **Plugin context** (always): `plugin_resources_path` + `build_test_command` — so the verifier reads its rule books from the plugin and runs the build/test via the detected command (it cannot resolve either itself)

### Step 6b — Verify Added Tests

If Step 5b produced new tests, spawn **one** `test-authoring:verify-add-unit-test-agent`. Read-only. Pass the inputs per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Verifier spawn": the Step 5b writer outputs (including `files_modified`), the original task, and the pre-writer source snapshot (plus `plugin_resources_path` + `build_test_command`, per the governing note).

Steps 6a and 6b can run **in parallel**. Skip 6a if no update/delete actions were executed; skip 6b if no add actions were executed.

### Step 6c — Handle Add-Verifier Findings

If `test-authoring:verify-add-unit-test-agent` reports violations, follow `<PLUGIN_TEMPLATES>/rules/fix-protocol.md`. Deterministic issues → fresh-spawn `test-authoring:add-unit-test-agent` with a `fix_invocation` block (re-using the prior writer's structured output). Non-deterministic → present to user; route any user-approved fix via the same `fix_invocation` block with `findings_to_fix.user_approved_actions`. The orchestrator never edits files directly.

## Step 7 — Summary

Present the final summary.

### Changes Applied

Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Action verbs are plain text. Status column reflects the post-execute outcome of that single change.

| # | Test Method | File | Action | Agent | Status | Notes |
|---|---|---|---|---|---|---|
| 2 | `<Test>` | `<file>` | Update | update | 🟩 | pass |
| 3 | `<Test>` | `<file>` | Update | update | 🟩 | pass |
| 4 | `<Test>` | `<file>` | Delete | update | 🟩 | deletion justified by audit status |
| 5 | `<new>` | `<file>` | Add | add | 🟩 | pass |

### Verification Results

Render as a single markdown table per verifier agent. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Last row of each table is the bold "Overall verdict".

**Update verification (`test-authoring:verify-update-unit-test-agent`)**

| Check | Result | Violations | Details |
|---|---|---|---|
| Deletion justification | 🟩 | 0 | Every deletion justified by audit status (none were valid) |
| Valid test protection | 🟩 | 0 | No valid tests were modified or removed |
| Test results | 🟩 | 0 | All tests pass |
| Anti-gaming | 🟩 | 0 | No failed test was deleted to make the suite pass |
| **Overall verdict** | **🟩** | **0** | — |

**Add verification (`test-authoring:verify-add-unit-test-agent`)** (only if Step 5b ran)

| Check | Result | Violations | Details |
|---|---|---|---|
| Convention compliance | 🟩 | 0 | All new tests follow conventions |
| Anti-gaming | 🟩 | 0 | No trivial assertions |
| Quality flags | 🟪 | <count> | <list of subjective improvement opportunities, if any> |
| **Overall verdict** | **🟩** | **0** | — |

### Rollback on Failure

If either verify agent reports **any violations**:
1. Present violations prominently, naming the specific deletions / rewrites at fault.
2. Offer rollback via git — for each affected tracked file, `git restore <file>` returns it to the committed state. (Files flagged untracked/dirty in Step 4.5 were proceeded on with explicit consent; advise the user to inspect those manually.)
3. Do not auto-restore without the user's go-ahead — they may prefer to keep some changes and fix forward.

### Status per file

Per `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md` → "Summary reporting". Icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary).



