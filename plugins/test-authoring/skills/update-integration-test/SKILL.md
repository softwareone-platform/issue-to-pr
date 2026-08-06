---
name: update-integration-test
expected_schema_version: "1.0"
expected_rules_schema_version: "2.1"
description: >
  Audit and update integration tests for changed handlers/endpoints. Two-phase: audit first, then execute automatically (no confirmation gate — actions derive from audit status; git is the rollback). Trigger phrases: "update integration tests for X", "refresh endpoint test for /foo". Do NOT trigger for: integration test infrastructure questions, container/fixture refactoring, or test strategy discussions.
---


## Step -1 — Resolve context source (fast path vs cacheless)

This skill runs **with or without** a prior `setup-test-context`. First resolve where rules/conventions come from, then proceed.

**Resolve the plugin templates root once** — you pass it to every subagent (audit, execute, add, and both verifiers), because subagents cannot resolve it themselves. The bundled templates sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`): on the **cacheless path** (where it is load-bearing) resolve it at runtime — run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool, and if `$CLAUDE_SKILL_DIR` is empty, ask the user for the `test-authoring` plugin install path. On the **fast path** its only use is the status-legend icons (Steps 3/4/7) — do **not** prompt; if it stays unresolved, use plain status labels. The Read tool normalises the `../..` segments.

Then check `.claude/conventions/tests/project-architecture.md`:

- **Exists → fast path.** A prior setup cached per-repo files. Compare its `schema_version` **major** against this skill's `expected_schema_version`: same major → continue silently; major differs or key missing → warn `"Conventions schema major <found> differs from <expected>. Run /test-authoring:setup-test-context to refresh."` and continue best-effort (may-be-stale). **Resolve, do not bulk-read**: every `.claude/{conventions,rules,shared}/tests/<f>` reference below resolves to the repo file — read each file lazily, at the first step that uses it (see "Orchestrator reading list" below). **Per-file fallback still applies at read time**: any individual file that is absent falls through to the cacheless source below — a missing file is never fatal.
- **Absent → cacheless.** setup has never run. **Do NOT stop.** Announce once: `"No precomputed test conventions found — running cacheless (sibling-driven). Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then for the rest of the flow:
  - Resolve every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` reference to `<PLUGIN_TEMPLATES>/{rules,shared}/<f>` instead (includes `common-update-instructions.md`) — same lazy rule: read at the step that uses it, never as an upfront batch. Cosmetic frontmatter/example tokens are inert when read explicitly.
  - Treat `.claude/conventions/tests/<f>` as **optional**: prefer the nearest sibling test for the scope (the audit's top-priority source anyway); when no sibling exists either, the writer reports the gap rather than inventing conventions — there is no language baseline to fall back to. Infer the target test project from siblings per Step 1.5.
  - **Detect once, reuse this session**: the language, and the *executable* build/test invocation **form** (test-project path + filter syntax) from the project manifest. In cacheless mode the template `test-rules.md` carries an unfilled `{{BUILD_AND_TEST_COMMANDS}}` token whose filled form lists **one command per test project** — the detected form replaces it everywhere (audit test-run, execute build, both verifiers' build, the final multi-agent build). Integration may span several test projects (Step 1.5): **instantiate the form per target test project** and pass each spawn the command for ITS project as `build_test_command`; subagents adjust its `--filter` to the actual test class.

Resolve `common-orchestrator-flow.md` the same way: fast path reads `.claude/rules/tests/common-orchestrator-flow.md` (same schema-major check against `expected_rules_schema_version`); cacheless reads `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `common-orchestrator-flow.md` (previous paragraph).
- **At the step that uses it**: Step 1 → `.claude/shared/tests/scope-resolution.md`. Step 1.5 → `.claude/conventions/tests/integration-test-conventions.md` (test project mapping; cacheless: sibling inference instead of a read). Step 3 (an audit issue cites the Source-change advisory) or Step 5a (the full `phase: execute` structure beyond the inlined block) → `.claude/rules/tests/common-update-instructions.md`, and only its orchestrator-facing sections ("Phase 2 invocation contract", the advisory) — the Phase 1 audit and Phase 2 execute procedure bodies are the update-writer's own rule book. Final multi-agent build → `.claude/rules/tests/test-rules.md` (cacheless: skip the read — use the session-detected per-project `build_test_command`). First verifier finding or attributable build failure → `.claude/rules/tests/fix-protocol.md`. A writer stopping on missing framework source → `.claude/rules/tests/sut-analysis.md` → "Runtime resolution flow". A writer stopping on no convention source → `.claude/rules/tests/common-orchestrator-flow.md` → "Writer stop on no convention source".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`. They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Update Integration Tests

You are the orchestrator for integration test maintenance. Your job is to **audit existing tests**, **present findings**, and then **delegate changes** derived from the audit status to subagents (no confirmation gate — git is the rollback). Follow the universal flow in `.claude/rules/tests/common-orchestrator-flow.md`; this file only documents integration-specific pieces.

> Every `.claude/{conventions,rules,shared}/tests/…` read below follows **Step -1's resolution** (repo on fast path; `<PLUGIN_TEMPLATES>/…` rules/shared + sibling-derived conventions on cacheless) — and happens lazily, at the step that uses it, never as an upfront batch; a body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. On the cacheless path, pass `plugin_resources_path` and `build_test_command` (the latter instantiated **per target test project**) into **every** subagent spawn — audit, execute, add, and both verifiers — they cannot resolve these themselves. All `<plugin-root>/resources/static/status-legend.md` references below resolve to `<PLUGIN_TEMPLATES>/../static/status-legend.md` (Step -1); if `PLUGIN_TEMPLATES` is unresolved, use plain text status labels rather than prompting.

> **CRITICAL — Deletion safety**: deletions and rewrites are driven by the **audit status** (not a user gate) and applied automatically. A test may be deleted only when the audit classified it `wrong` or `duplicated` — never when `valid` or `outdated-major` (an outdated-major test still carries intent worth preserving: it is rewritten, never deleted). Every action is recorded in an **action record** and passed to `test-authoring:verify-update-integration-test-agent`, which independently re-checks each deletion against `git show HEAD:<file>`. Git is the safety net: a tracked test file can be restored with `git restore`.

## Step 1 — Identify Scope

Follow the procedure in `.claude/shared/tests/scope-resolution.md`.

- **Mode A** (no argument): Use git diff. Focus on modified API endpoints (controllers, routes), command/query handlers, worker operations or event consumers, sync consumers, and changes to persistence logic.
- **Mode B** (argument provided, e.g., `/test-authoring:update-integration-test ComponentName`): Resolve by directory, component, class, endpoint, or file name.

## Step 1.5 — Determine Test Project Mapping

Before auditing, determine which test project each source file maps to. Use the **test project mapping** in `.claude/conventions/tests/integration-test-conventions.md`. **Cacheless** (the conventions doc is absent): infer the target test project(s) from siblings — locate the integration test project(s) whose tests mirror the source area; if several exist and none clearly mirrors the source, ask the user rather than guess. If a single source file maps to multiple test projects (e.g., both API and worker), audit each (source, project) pair separately — one Phase 1 agent per pair, so neither project's stale tests are missed.

## Step 2 — Audit via Agent

Spawn `test-authoring:update-integration-test-agent` — one per (source, project) pair from Step 1.5 (a multi-project source class gets one audit agent per pair), all in parallel. Phase 1 (audit) only — agents return structured audit output and terminate.

Parallel audits may contend on the shared test project build and container resources (Docker, ports) during the audit's test-run step. If an audit reports a build failure or env_failure that looks like contention rather than a real break, re-run that audit serially before trusting the result.

**Retain each agent's audit output** — Phase 2 in Step 5a is a fresh `Agent` spawn whose prompt carries the audit record forward (the orchestrator does not continue a live Phase 1 instance).

```
Agent(subagent_type="test-authoring:update-integration-test-agent"):
  Audit existing integration tests for:
  - <source file path>
  Target test project: <path from Step 1.5>
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build/test command for this Target test project>
```

### Endpoint-scoped

When the user specifies an endpoint, include it in the agent prompt as "Focus only on <endpoint>".

## Step 3 — Present Audit Summary

Collect audit results and present a structured summary. Group by source class.

> **Rendering rule (MUST)**: the Test Audit section MUST be rendered as a single markdown table — never as a numbered list, bullet list, or separator-bar format (e.g., `────`). Missing coverage items are appended as rows with status `🟦 pending` (per `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary)), continuing the `#` numbering.

### Test Audit: `{ClassName}` (integration)

| # | Method / Endpoint | Status | Confidence | Description |
|---|---|---|---|---|
| 1 | `<TestMethod>` | 🟩 valid | — | matches current SUT logic |
| 2 | `<TestMethod>` | 🟨 outdated-major | high | <what changed> |
| 3 | `<TestMethod>` | 🟨 outdated-minor | high | <tweak needed> |
| 4 | `<TestMethod>` | 🟪 duplicated | medium | overlaps with #2 |
| 5 | `<endpoint>` | 🟦 pending | — | no test covers this (to add) |

**Status legend**: `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Statuses used: 🟩 valid, 🟨 outdated-minor, 🟨 outdated-major, 🟥 wrong, 🟪 duplicated, 🟦 pending.

**Confidence legend**:
- **high** — clear structural evidence
- **medium** — requires behavioural analysis, review recommended
- **low** — subjective assessment, **review carefully before confirming**

### Pre-change Test Results

Render as a single markdown table. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary) — `env_failure` maps to 🟨 per the legend's "Warning" definition.

| # | Test Method | Status | Notes |
|---|---|---|---|
| 1 | `<TestMethod>` | 🟩 pass | baseline |
| 2 | `<TestMethod>` | 🟥 fail | pre-existing (inspect before update) |
| 3 | `<TestMethod>` | 🟨 env_failure | Docker / Testcontainers / external dep unavailable — not the writer's fault |

### Audit Issues

Surface any `issues:` entries from the audit records verbatim — in particular the **source-change advisory** (the audit detected that test staleness comes from uncommitted source changes; see `.claude/rules/tests/common-update-instructions.md` → "Source-change advisory"). The advisory is informational — execution proceeds without a gate — but surfacing it now lets the user interrupt and commit/stash the source, keeping a single coherent git baseline for rollback.

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
| 5 | `<endpoint>` | Add | 🟦 pending | — | no test covers this |
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

Before spawning the first execution agent (5a or 5b), record the **pre-writer source snapshot** per `.claude/rules/tests/common-orchestrator-flow.md` → "Pre-writer source snapshot" — the add-verifier needs it as the baseline for its SUT-modification check.

### Step 5a — Update and Delete (fresh-spawn Phase 2)

Phase 2 is a **fresh-spawn** `Agent` invocation with `phase: execute` in the prompt. Do not attempt to continue a Phase 1 agent — every Phase 2 is a new spawn that re-reads files from the paths in the prompt. See `.claude/rules/tests/common-update-instructions.md` → "Phase 2 invocation contract" for the full structure.

Spawn one `test-authoring:update-integration-test-agent` per (source, project) pair whose action record has update/delete actions — a class audited as two pairs gets two Phase 2 agents, each carrying its own pair's audit record and `test_project`; collapsing pairs into one per-class spawn silently drops the other project's actions.

Phase 2 agents that share a test project hit the same build and container contention as Step 2's parallel audits (Docker, ports, file locks) — spawn them **sequentially per test project**; if a contended-looking failure still appears, re-run that agent serially before trusting the result.

```
Agent(subagent_type="test-authoring:update-integration-test-agent"):
  phase: execute

  original_scope:
    source_files: [<from Step 1>]
    method_filter: <if any>
    test_type: integration

  pre_fetch:
    sibling_paths: [<from Step 2 audit>]
    convention_spec: {<from Step 2 audit>}

  audit_record:
    <full audit output from this source class's Phase 1 agent — includes test_project>

  planned_actions:
    update:
    - <Test>: <audit_status>
    delete:
    - <Test>: <audit_status>
    add: []   # add actions handled in Step 5b via test-authoring:add-integration-test-agent

  test_file_paths: [<from audit_record.test_file(s)>]
  test_project: <from audit_record.test_project>
  consent_proceeded_files: [<from Step 4.5, or empty>]

  cacheless_context:   # include ONLY on the cacheless path — omit entirely on the fast path
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build/test command for THIS pair's Target test project>
```

### Step 5b — Add Missing Coverage via `test-authoring:add-integration-test-agent`

After update/delete agents complete, spawn `test-authoring:add-integration-test-agent` for the action record's **add** actions — one per (source, project) pair with add actions; the Target test project comes from that pair's audit.

```
Agent(subagent_type="test-authoring:add-integration-test-agent"):
  Generate integration tests for:
  - <source path>
    Cover <endpoint>: no tests exist
  Target test project: <path>
  Sibling tests found during audit (adopt their conventions):
  - <path> (<convention spec summary>)
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <build/test command for THIS pair's Target test project>
```

If the audit reported `no_existing_tests: true` (no siblings found), omit the sibling lines and state instead: `No sibling tests found and no convention source — apply test-writer-rules.md → Fallback Chain`. Under the Slim default `{type}-test-conventions.md` is generated on neither path, so do not point the writer at it. Never invent a sibling path to satisfy the template.

Skip if the action record has no add actions.

### Multi-agent build check

If multiple agents were spawned across 5a and 5b, run a final build of **each affected test project**. Reference `.claude/rules/tests/test-rules.md` (cacheless: use each project's `build_test_command`, not the unfilled `{{BUILD_AND_TEST_COMMANDS}}` token).

## Step 6 — Verify

### Step 6a — Verify Updates and Deletions

Spawn **one** `test-authoring:verify-update-integration-test-agent` per affected test project (a single spawn when only one project was touched). Pass, scoped to that project:
1. Pre-change state (including env_failures)
2. Action record (audit_status + action per item)
3. Execution results
4. Pre-change baseline: `git show HEAD:<file>` for each modified file (no `.bak`)
5. Test type: `integration`
6. Test project path
7. Raw Phase 1 audit outputs (retained in Step 2) — so the verifier can cross-check that the action record faithfully transcribes each audit classification
8. Consent-proceeded files from Step 4.5 (untracked/dirty at check time) — their HEAD baseline is unreliable; the verifier treats diff-based findings on them as advisory, not violations
9. Step 5b add-writer outputs (`files_created` / `files_modified` / `test_count`), when Step 5b ran — the add writer may insert tests into the SAME files 6a inspects, and without these the verifier's test-count cross-check reads the additions as out-of-record changes
10. **Cacheless context** (cacheless path only): `plugin_resources_path` + the `build_test_command` for this project — so the verifier reads rules from the plugin templates and runs the build/test via the detected command (it cannot resolve these itself)

### Step 6b — Verify Added Tests

If Step 5b produced new tests, spawn **one** `test-authoring:verify-add-integration-test-agent`. Read-only. Pass the inputs per `.claude/rules/tests/common-orchestrator-flow.md` → "Verifier spawn": the Step 5b writer outputs (including `files_modified`), the original task, and the pre-writer source snapshot (cacheless: also pass `plugin_resources_path` + the project's `build_test_command`, per the governing note).

6a and 6b can run **in parallel**. Skip 6a if no update/delete actions were executed; skip 6b if no add actions were executed.

### Step 6c — Handle Add-Verifier Findings

If `test-authoring:verify-add-integration-test-agent` reports deterministic issues → fresh-spawn `test-authoring:add-integration-test-agent` with a `fix_invocation` block (re-using the prior Step 5b writer's structured output). Non-deterministic (including `env_failure`) → present to user; route any user-approved fix via the same `fix_invocation` block with `findings_to_fix.user_approved_actions`. The orchestrator never edits files directly.

## Step 7 — Summary

Present the final summary.

### Changes Applied

Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Action verbs are plain text. `🟨` in the Status column indicates env_failure (Docker / Testcontainers / external dep) — not the writer's fault.

| # | Test Method | File | Action | Agent | Status | Notes |
|---|---|---|---|---|---|---|
| 2 | `<Test>` | `<file>` | Update | update | 🟩 | pass |
| 3 | `<Test>` | `<file>` | Update | update | 🟨 | env_failure (Docker unavailable) |
| 4 | `<Test>` | `<file>` | Delete | update | 🟩 | deletion justified by audit status |
| 5 | `<new>` | `<file>` | Add | add | 🟩 | pass |

### Verification Results

Render as a single markdown table per verifier agent. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Last row of each table is the bold "Overall verdict". env_failure is a 🟨 warning, not a 🟥 violation.

**Update verification (`test-authoring:verify-update-integration-test-agent`)**

| Check | Result | Violations | Details |
|---|---|---|---|
| Deletion justification | 🟩 | 0 | Every deletion justified by audit status (none were valid) |
| Valid test protection | 🟩 | 0 | No valid tests were modified or removed |
| Test results | 🟩 | 0 | All tests pass (🟨 env_failures noted separately) |
| Anti-gaming | 🟩 | 0 | No failed test was deleted to make the suite pass |
| **Overall verdict** | **🟩** | **0** | — |

**Add verification (`test-authoring:verify-add-integration-test-agent`)** (only if Step 5b ran)

| Check | Result | Violations | Details |
|---|---|---|---|
| Convention compliance | 🟩 | 0 | All new tests follow conventions |
| Anti-gaming | 🟩 | 0 | No trivial assertions |
| env_failures | 🟨 | <count> | <list of tests that hit env failures, if any> |
| Quality flags | 🟪 | <count> | <list of subjective improvement opportunities, if any> |
| **Overall verdict** | **🟩** | **0** | — |

### Rollback on Failure

If either verify agent reports **any violations**:
1. Present violations prominently, naming the specific deletions / rewrites at fault.
2. Offer rollback via git — for each affected tracked file, `git restore <file>` returns it to the committed state. (Files flagged untracked/dirty in Step 4.5 were proceeded on with explicit consent; advise the user to inspect those manually.)
3. Do not auto-restore without the user's go-ahead — they may prefer to keep some changes and fix forward.

Note: do NOT rollback on env_failures alone — those are not the writer's fault.

### Status per file

Per `.claude/rules/tests/common-orchestrator-flow.md` → "Summary reporting". Icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary).


