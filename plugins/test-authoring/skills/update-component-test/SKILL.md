---
name: update-component-test
expected_schema_version: "1.0"
expected_rules_schema_version: "2.1"
description: >
  Audit and update component (Gherkin) scenarios for changed feature behaviour. Two-phase: audit first, then execute automatically (no confirmation gate — actions derive from audit status; git is the rollback). Trigger phrases: "update component scenario for X", "refresh feature file for Y". Do NOT trigger for: scenario design discussions, step-definition refactoring, or component test strategy.
---


## Step -1 — Resolve context source (fast path vs cacheless)

This skill runs **with or without** a prior `setup-test-context`. First resolve where rules/conventions come from, then proceed.

**Resolve the plugin templates root once** — you pass it to every subagent (audit, execute, add, and both verifiers), because subagents cannot resolve it themselves. The bundled templates sit two directories above this `SKILL.md`, under `resources/templates`. Prefer bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}/../../resources/templates"`

Call the result `PLUGIN_TEMPLATES`. If that line did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`): on the **cacheless path** (where it is load-bearing) resolve it at runtime — run `echo "$CLAUDE_SKILL_DIR/../../resources/templates"` with the Bash tool, and if `$CLAUDE_SKILL_DIR` is empty, ask the user for the `test-authoring` plugin install path. On the **fast path** its only use is the status-legend icons (Steps 3/4/7) — do **not** prompt; if it stays unresolved, use plain status labels. The Read tool normalises the `../..` segments.

Then check `.claude/conventions/tests/project-architecture.md`:

- **Exists → fast path.** A prior setup cached per-repo files. Compare its `schema_version` **major** against this skill's `expected_schema_version`: same major → continue silently; major differs or key missing → warn `"Conventions schema major <found> differs from <expected>. Run /test-authoring:setup-test-context to refresh."` and continue best-effort (may-be-stale). **Resolve, do not bulk-read**: every `.claude/{conventions,rules,shared}/tests/<f>` reference below resolves to the repo file — read each file lazily, at the first step that uses it (see "Orchestrator reading list" below). **Per-file fallback still applies at read time**: any individual file that is absent falls through to the cacheless source below — a missing file is never fatal.
- **Absent → cacheless.** setup has never run. **Do NOT stop.** Announce once: `"No precomputed test conventions found — running cacheless (sibling-driven). Run /test-authoring:setup-test-context once to cache the repo cross-layer test map."` Then for the rest of the flow:
  - Resolve every `.claude/rules/tests/<f>` and `.claude/shared/tests/<f>` reference to `<PLUGIN_TEMPLATES>/{rules,shared}/<f>` instead (includes `common-update-instructions.md` and `test-component-rules.md`) — same lazy rule: read at the step that uses it, never as an upfront batch. Cosmetic frontmatter/example tokens are inert when read explicitly.
  - Treat `.claude/conventions/tests/<f>` as **optional**: prefer the nearest sibling `.feature` / step class for the area (the audit's top-priority source anyway); fall back to `<PLUGIN_TEMPLATES>/lang/<derived>/` fragments for the language baseline. Discover `{{FEATURES_DIR}}`/`{{STEPS_DIR}}`/`{{SCENARIO_FRAMEWORK}}`/`{{COMPONENT_TEST_PROJECT_PATH}}` per the "Placeholder resolution" note below.
  - **Detect once, reuse this session**: the language, and the *executable* component build + feature-run invocation. In cacheless mode the component commands `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` in `test-component-rules.md` are unfilled — derive them from `<PLUGIN_TEMPLATES>/lang/<derived>/component-build-commands.md` (which still carries `<project>`/`<FeatureName>` placeholders to substitute from the detected test project + target feature). The detected commands replace those tokens everywhere (audit feature-run, execute build/feature-run, both verifiers, the final build). Pass them as `build_test_command` to **every** subagent spawn (audit, execute, add, verify-update, verify-add) — a **set** (build command, feature-filter run, FQN-filter fallback), not one string.

Resolve `common-orchestrator-flow.md` the same way: fast path reads `.claude/rules/tests/common-orchestrator-flow.md` (same schema-major check against `expected_rules_schema_version`); cacheless reads `<PLUGIN_TEMPLATES>/rules/common-orchestrator-flow.md`.

**Orchestrator reading list (context discipline).** Load into the main context only what this orchestrator itself needs, when it needs it:

- **Now**: `common-orchestrator-flow.md` (previous paragraph), then `.claude/conventions/tests/component-test-conventions.md` + `.claude/conventions/tests/project-architecture.md` — the "Placeholder resolution" note below needs both before Step 1 (cacheless: R5 token discovery per that note, no read).
- **At the step that uses it**: Step 3 → `.claude/rules/tests/test-rules.md` plus the build-command sections of `.claude/rules/tests/test-component-rules.md` (Pre-change Test Results filter command — first use; reused at Step 5; cacheless: the session-detected `build_test_command` set replaces the unfilled tokens), and `.claude/rules/tests/common-update-instructions.md` when an audit issue cites the Source-change advisory — read only its orchestrator-facing sections ("Phase 2 invocation contract", the advisory); the Phase 1 audit and Phase 2 execute procedure bodies are the update-writer's own rule book. Step 5a needs that same contract section if the inlined block does not suffice. First verifier finding or attributable build/feature-run failure → `.claude/rules/tests/fix-protocol.md`. A writer stopping on missing framework source → `.claude/rules/tests/sut-analysis.md` → "Runtime resolution flow".
- **Never**: `common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, and the writer/verifier body of `test-component-rules.md` beyond the build-command sections above. They are subagent rule books — the writers/verifiers read them in their own isolated contexts; preloading them here only bloats the main context.


# Update Component Tests

You are the orchestrator for component ({{SCENARIO_FRAMEWORK}}/Gherkin) test maintenance. Your job is to **audit existing scenarios**, **present findings**, and then **delegate changes** derived from the audit status to subagents (no confirmation gate — git is the rollback). Follow the universal flow in `.claude/rules/tests/common-orchestrator-flow.md`; this file only documents component-specific pieces.

> Every `.claude/{conventions,rules,shared}/tests/…` read below follows **Step -1's resolution** (repo on fast path; `<PLUGIN_TEMPLATES>/…` rules/shared + sibling/lang-fragment conventions on cacheless) — and happens lazily, at the step that uses it, never as an upfront batch; a body reference to one of these files at a step IS that step's read instruction: Read the file before acting on it, never from memory of its name. On the cacheless path, pass `plugin_resources_path` and `build_test_command` (a set — build + feature-filter run + FQN-filter fallback) into **every** subagent spawn — audit, execute, add, and both verifiers — they cannot resolve these themselves. All `<plugin-root>/resources/static/status-legend.md` references below resolve to `<PLUGIN_TEMPLATES>/../static/status-legend.md` (Step -1); if `PLUGIN_TEMPLATES` is unresolved, use plain text status labels rather than prompting.

> **CRITICAL — Deletion safety**: deletions and rewrites are driven by the **audit status** (not a user gate) and applied automatically. A scenario or step method may be deleted only when the audit classified it `wrong` or `duplicated` — never when `valid` or `outdated-major` (an outdated-major scenario still carries intent worth preserving: it is rewritten, never deleted). Every action is recorded in an **action record** and passed to `test-authoring:verify-update-component-test-agent`, which independently re-checks each deletion against `git show HEAD:<file>`. Git is the safety net: a tracked file can be restored with `git restore`.

> **Scope is explicit only (Mode B).** Component tests do not map 1:1 to source files — a single source change can map to many scenarios, none, or live in any of several `.feature` areas. The user must name the feature, area, or scenario. There is no Mode A (git-diff) — same reasoning as `add-component-test`.

> **Placeholder resolution (plugin-bundled file)**: tokens like `{{SCENARIO_FRAMEWORK}}`, `{{FEATURES_DIR}}`, `{{STEPS_DIR}}`, `{{COMPONENT_TEST_PROJECT_PATH}}` in this skill are NOT pre-filled — this file ships with the plugin, not generated per-repo. Resolve each token at runtime from the per-repo conventions: `.claude/conventions/tests/component-test-conventions.md` (framework, feature/steps layout, test project path) and `.claude/conventions/tests/project-architecture.md` (directory trees). Never glob or reference a `{{...}}` token literally — a literal glob returns zero matches and falsely reads as "feature does not exist".
>
> **Cacheless (R5 — those conventions docs are absent):** discover the tokens directly — `{{FEATURES_DIR}}` by globbing `**/*.feature` and taking their common root; `{{STEPS_DIR}}` from the folder holding a sibling step/binding class; `{{SCENARIO_FRAMEWORK}}` from that step class's binding attribute/runner or the test project's package reference (NOT the `.feature` Gherkin, which is framework-agnostic); `{{COMPONENT_TEST_PROJECT_PATH}}` = the test project containing those step classes. If the glob finds multiple feature roots or none, ask the user rather than guess.

## Step 1 — Identify Scope (Mode B only)

The user invokes this skill with an explicit scope. Accepted forms:

- `/test-authoring:update-component-test <Area>` — area only (audit every scenario in the feature)
- `/test-authoring:update-component-test <Area>: <Scenario title>` — area + scenario (audit only that scenario)
- `/test-authoring:update-component-test <path-to-feature-file>` — feature path directly (e.g., `{{FEATURES_DIR}}/<Area>.feature`)
- `/test-authoring:update-component-test` — no argument; ask the user for the area or feature path before proceeding

**Ask the user, do not infer**, if the scope is missing or ambiguous. Do not run `git diff` to guess scope.

### Resolve "area" to feature/steps paths

1. Area name → Glob `{{FEATURES_DIR}}/<Area>.feature`
2. Area name → Glob `{{STEPS_DIR}}/<Area>/`
3. Scenario title → grep the `.feature` file for a `Scenario:` heading matching the title (exact match preferred; case-insensitive substring match as a fallback)

Decide:

- **Both found** — proceed with the feature + steps pair.
- **Only one found** — unusual; ask the user to clarify before proceeding.
- **Neither found** — feature does not exist; this is not an update case — suggest `/test-authoring:add-component-test` instead.

## Step 2 — Audit via Agent

Spawn **one** `test-authoring:update-component-test-agent` per feature file (audit is feature-scoped; scenario filter is passed as an input field). The agent returns structured audit output and terminates.

**Retain the agent's audit output** — Phase 2 in Step 5a is a fresh `Agent` spawn whose prompt carries the audit record forward (the orchestrator does not continue a live Phase 1 instance).

```
Agent(subagent_type="test-authoring:update-component-test-agent"):
  Audit existing component tests for:
  - Feature file: <path>
  - Steps folder: <path>
  - Scenario filter: <scenario title>  # optional; omit to audit the whole feature
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <component build + feature-run set (build, feature-filter, FQN fallback)>
```

## Step 3 — Present Audit Summary

Collect audit results from the agent and present a structured summary to the user. Group by feature.

For each feature:

> **Rendering rule (MUST)**: the Test Audit section MUST be rendered as a single markdown table — never as a numbered list, bullet list, or separator-bar format (e.g., `────`). Missing coverage items are appended as rows with status `🟦 pending` (per `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary)), continuing the `#` numbering.

### Test Audit: `{{FEATURES_DIR}}/<Area>.feature` (component)

| # | Scenario / SUT | Status | Confidence | Description |
|---|---|---|---|---|
| 1 | `<scenario title>` | 🟩 valid | — | matches current SUT |
| 2 | `<scenario title>` | 🟨 outdated-minor | high | SUT drift: `<what changed>` |
| 3 | `<scenario title>` | 🟥 wrong | medium | SUT drift: `<reason>` |
| 4 | `<scenario title>` | 🟨 outdated-major | high | step binding: `<phrase>` has no matching `[Given/When/Then]` |
| 5 | `<scenario title>` | 🟨 outdated-major | medium | fixture drift: `<FakeClass>` API changed |
| 6 | `<Controller>.<Method>` | 🟦 pending | — | no scenario covers this endpoint (to add) |
| 7 | `<Consumer>` failure path | 🟦 pending | — | no scenario asserts the expected domain event (to add) |

**Status legend**: see `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary) for icon definitions. Statuses used in this audit: 🟩 valid, 🟨 outdated-minor, 🟨 outdated-major, 🟥 wrong, 🟪 duplicated, 🟦 pending.

**Confidence legend:**
- **high** — clear structural evidence (endpoint removed, step attribute absent, fake method renamed)
- **medium** — behavioural comparison required; review recommended
- **low** — subjective assessment; review carefully before confirming

For items with **medium** or **low** confidence, add a note prompting the user to review.

Use a **sequential number (#)** across the feature so the user can reference items by number.

### Pre-change Test Results

Render as a single markdown table. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Reference `.claude/rules/tests/test-rules.md` (common) and `.claude/rules/tests/test-component-rules.md` (component-specific) for the filter command used (cacheless: use the session-detected `build_test_command`, not the unfilled `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` tokens). `env_failure` maps to 🟨 per the legend.

| # | Scenario | Status | Notes |
|---|---|---|---|
| 1 | `<scenario title>` | 🟩 pass | baseline |
| 2 | `<scenario title>` | 🟥 fail | pre-existing (inspect before update) |
| 3 | `<scenario title>` | 🟨 env_failure | Testcontainers / external dep unavailable |

### Audit Issues

Surface any `issues:` entries from the audit record verbatim — in particular the **source-change advisory** (the audit detected that scenario staleness comes from uncommitted source changes; see `.claude/rules/tests/common-update-instructions.md` → "Source-change advisory"). The advisory is informational — execution proceeds without a gate — but surfacing it now lets the user interrupt and commit/stash the source, keeping a single coherent git baseline for rollback.

## Step 4 — Determine Actions (from audit status)

Derive each item's action from its **audit status** — there is no user gate:

- 🟨 `outdated-major` → **Update (rewrite)**
- 🟨 `outdated-minor` → **Update (tweak)**
- 🟥 `wrong` → **Update** (or **Delete** if the scenario asserts behaviour the SUT no longer has and no corrected assertion is meaningful)
- 🟪 `duplicated` → **Delete** (the surviving duplicate stays)
- 🟦 `pending` → **Add**
- 🟩 `valid` → **no change** (never modified or deleted)

> **Rendering rule (MUST)**: present the planned actions as a single markdown table — never bracket codes. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Action verbs (Update / Tweak / Delete / Add / —) stay plain text. This table is the **audit trail for the summary**, not a gate — execution proceeds without waiting for a reply.

### Proposed Actions

| # | Scenario / SUT | Action | Audit Status | Confidence | Notes |
|---|---|---|---|---|---|
| 2 | `<scenario>` | Update (rewrite) | 🟨 outdated-major | high | <reason> |
| 3 | `<scenario>` | Update (tweak) | 🟨 outdated-minor | high | tweak Then status code |
| 5 | `<scenario>` | Delete | 🟪 duplicated | medium | overlaps with #2 — review |
| 6 | `<Controller>.<Method>` | Add | 🟦 pending | — | no scenario covers this |
| 7 | `<Consumer>` failure path | Add | 🟦 pending | — | no scenario asserts the expected domain event |
| 1 | `<scenario>` | — | 🟩 valid | — | no change |

Flag any `low`/`medium`-confidence action in the Notes column so the user can review it post-run (the summary is where they catch a mis-classified action and `git restore` it).

### Build Action Record

Build a structured **action record** including `audit_status`, `confidence`, `drift_cause`, and `action` for each scenario / gap. This drives Phase 2 and is the baseline the verifier checks deletions against — a deletion whose `audit_status` is anything other than `wrong` or `duplicated` is a violation.

## Step 4.5 — Pre-write git safety check

Git is the backup — there are no `.bak` files. Before executing changes, check **every file that Phase 2 will touch**:

- The `.feature` file (Phase 2 may edit or delete `Scenario:` blocks)
- **Every step class under `{{STEPS_DIR}}/<Area>/`** — which step files Phase 2 will touch is decided during execution (attribute-regex edits, orphaned-method removal), so check the whole area folder rather than guessing targets

Run, per file:

```bash
git status --porcelain -- <file>
```

- **Tracked and clean** (no output) → proceed. `git show HEAD:<file>` is the faithful pre-change baseline the verifier diffs against, and `git restore <file>` undoes the change.
- **Untracked, or has uncommitted modifications** (any porcelain output) → warn the user: this file has no reliable committed baseline, so an automatic update cannot be safely diffed or restored. Ask whether to proceed for that file or skip it; proceed only on explicit confirmation.

Record, per modified file, that the pre-change baseline is `git show HEAD:<file>` — this is what the verifier uses in Step 6a. Also record which files were proceeded on explicit consent despite being untracked/dirty: that list goes to the verifier in Step 6a, because HEAD is not a reliable baseline for them.

## Step 5 — Execute Changes

Split the action record's actions into two groups and execute them **sequentially** (update/delete first, then add). Before spawning the first execution agent (5a or 5b), record the **pre-writer source snapshot** per `.claude/rules/tests/common-orchestrator-flow.md` → "Pre-writer source snapshot" — the add-verifier needs it as the baseline for its SUT-modification check.

### Step 5a — Update and Delete (fresh-spawn Phase 2)

Phase 2 is a **fresh-spawn** `Agent` invocation with `phase: execute` in the prompt. Do not attempt to continue the Phase 1 agent — every Phase 2 is a new spawn that re-reads files from the paths in the prompt. See `.claude/rules/tests/common-update-instructions.md` → "Phase 2 invocation contract" for the full structure.

```
Agent(subagent_type="test-authoring:update-component-test-agent"):
  phase: execute

  original_scope:
    feature_file: <path>
    steps_folder: <path>
    scenario_filter: <if any>
    test_type: component

  pre_fetch:
    sibling_paths: [<feature_file, step_class_paths from Step 2 audit>]
    convention_spec: {<from Step 2 audit>}

  audit_record:
    <full audit output from the Phase 1 agent — includes scenario_audit, missing_coverage, etc.>

  planned_actions:
    update:
    - <Scenario>: outdated-major
    - <Scenario>: outdated-minor
    delete:
    - <Scenario>: duplicated
    add: []   # add actions handled in Step 5b via test-authoring:add-component-test-agent

  test_file_paths:
    feature_file: <path>
    steps_folder: <path>

  consent_proceeded_files: [<from Step 4.5, or empty>]

  cacheless_context:   # include ONLY on the cacheless path — omit entirely on the fast path
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <component build + feature-run set (build, feature-filter, FQN fallback)>
```

If the execute output contains `flagged_for_orchestrator` entries (drift that needs a new scenario or a new step class — Phase 2 never creates these), append any new-scenario flags to Step 5b's add actions (delegated to `test-authoring:add-component-test-agent`), and surface new-step-class flags to the user in the summary — restructuring the step-class split is out of scope (see "Out of scope").

### Step 5b — Add Missing Coverage via `test-authoring:add-component-test-agent`

After 5a completes, spawn `test-authoring:add-component-test-agent` for the action record's **add** actions — **one agent per scenario, sequential** (component tests are slow; parallelism is not useful here).

```
Agent(subagent_type="test-authoring:add-component-test-agent"):
  Generate a component test scenario:
  - Area: <Area>
  - Scenario title: <proposed scenario title from missing-coverage row>
  - Plan: append-to-existing
  - Target feature file: <path>
  - Target steps folder: <path>

  Context from audit:
    SUT to cover: <SUT path + method / branch>
    Why this is a gap: <from missing-coverage row>
  Cacheless context (include ONLY on the cacheless path — omit entirely on the fast path):
    plugin_resources_path: <PLUGIN_TEMPLATES>
    build_test_command: <component build + feature-run set (build, feature-filter, FQN fallback)>
```

Skip this step if the action record has no **add** actions.

If the add agent stops on a **fixture gap** (no scenario written, gap details in `issues:`), apply the same pre-flight defaults as the `add-component-test` skill — re-spawn once with a `proceed-pure-computation` instruction, or skip the scenario when nothing meaningful would remain — and surface the gap in the Step 7 summary either way.

### Multi-agent build check

If changes spanned **both** 5a and 5b, run a final build after all agents complete. Reference `.claude/rules/tests/test-rules.md` (common) and `.claude/rules/tests/test-component-rules.md` (component-specific) for the exact command (cacheless: use the session-detected `build_test_command`, not the unfilled `{{BUILD_COMMAND}}`/`{{TEST_COMMAND_*}}` tokens).

## Step 6 — Verify

After all execution agents complete, spawn verification agents.

### Step 6a — Verify Updates and Deletions

Spawn **one** `test-authoring:verify-update-component-test-agent` to verify the update/delete changes. This agent is **strictly read-only**.

Pass ALL of the following:

1. **Pre-change state** — scenarios that existed before and their pass/fail status
2. **Action record** (audit_status + action per item)
3. **Execution results** — what the update agent actually did
4. **Pre-change baseline**: `git show HEAD:<file>` for each modified file (no `.bak`)
5. **Test type** — `component`
6. **Test project** — `{{COMPONENT_TEST_PROJECT_PATH}}`
7. **Files in scope** — feature file + step class paths
8. **Add-agent results** (if Step 5b ran) — the full output from each `test-authoring:add-component-test-agent` invocation, including `files_modified`, `files_created`, and `scenario_title` for every scenario added; pass an empty list if Step 5b was skipped
9. **Raw Phase 1 audit output** (retained in Step 2) — so the verifier can cross-check that the action record faithfully transcribes each audit classification
10. **Consent-proceeded files** from Step 4.5 (untracked/dirty at check time) — their HEAD baseline is unreliable; the verifier treats diff-based findings on them as advisory, not violations
11. **Cacheless context** (cacheless path only): `plugin_resources_path` + the component `build_test_command` — so the verifier reads rules from the plugin templates and runs the build/feature-run via the detected command (it cannot resolve these itself)

### Step 6b — Verify Added Scenarios

If Step 5b produced new scenarios, spawn **one** `test-authoring:verify-add-component-test-agent` per `test-authoring:add-component-test-agent` invocation to review them. This agent is **read-only**. Pass the inputs per `.claude/rules/tests/common-orchestrator-flow.md` → "Verifier spawn": that writer invocation's outputs (including `files_modified`), the original task, and the pre-writer source snapshot (cacheless: also pass `plugin_resources_path` + the component `build_test_command`, per the governing note).

Steps 6a and 6b can run **in parallel**.

Skip 6a if no update/delete actions were executed; skip 6b if no add actions were executed.

### Step 6c — Handle Add-Verifier Findings

If `test-authoring:verify-add-component-test-agent` reports violations, follow the **Verifier Fix Protocol** in `.claude/rules/tests/fix-protocol.md`. Deterministic → fresh-spawn `test-authoring:add-component-test-agent` with a `fix_invocation` block (re-using the prior Step 5b writer's structured output). Non-deterministic → present to the user; route any user-approved fix via the same `fix_invocation` block with `findings_to_fix.user_approved_actions`.

### Step 6d — Handle Update-Verifier Findings

If `test-authoring:verify-update-component-test-agent` reports violations (deletion without audit justification, valid scenario modified, failing scenario after fix), follow the same Verifier Fix Protocol — when the violation is a deterministic execution issue (e.g. failing scenario after fix), fresh-spawn `test-authoring:update-component-test-agent` with a `fix_invocation` block per `.claude/rules/tests/fix-protocol.md`, using the update-writer field mapping documented there. Do NOT re-issue `phase: execute` — the fix prompt is the `fix_invocation` shape. Present non-deterministic issues (deletion violations, anti-gaming findings) directly to the user with a rollback offer. The orchestrator never edits files directly.

## Step 7 — Summary

Collect results from all agents and present a final summary.

### Changes Applied: Scenarios

Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Action verbs are plain text.

| # | Scenario | Action | Agent | Status | Notes |
|---|---|---|---|---|---|
| 2 | `<scenario>` | Update | update | 🟩 | pass |
| 3 | `<scenario>` | Update | update | 🟩 | pass |
| 5 | `<scenario>` | Delete | update | 🟩 | deletion justified by audit status |
| 6 | `<new scenario>` | Add | add | 🟩 | pass |

### Changes Applied: Step Methods

Render this sub-table only when scenarios were deleted and the agent identified step methods that became unused or were retained because still referenced. Omit the section entirely if no step methods were touched.

| Method | Class | Reason | Status |
|---|---|---|---|
| `<StepMethod>` | `StepsFor<Area>` | unused after scenario deletion | 🟩 deleted |
| `<StepMethod>` | `StepsFor<Area>` | still referenced by `<other scenario>` | 🟨 retained |

### Verification Results

Render as a single markdown table per verifier agent. Use only icons from `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary). Last row of each table is the bold "Overall verdict".

**Update verification (`test-authoring:verify-update-component-test-agent`)**

| Check | Result | Violations | Details |
|---|---|---|---|
| Deletion justification | 🟩 | 0 | Every deletion justified by audit status (none were valid) |
| Valid scenario protection | 🟩 | 0 | No valid scenarios were modified or removed |
| Scenario results | 🟩 | 0 | All scenarios pass (🟨 env_failures noted separately) |
| Anti-gaming | 🟩 | 0 | No failed scenario was deleted to make the suite pass |
| **Overall verdict** | **🟩** | **0** | — |

**Add verification (`test-authoring:verify-add-component-test-agent`)** (only if Step 5b ran)

| Check | Result | Violations | Details |
|---|---|---|---|
| Convention compliance | 🟩 | 0 | All new scenarios follow conventions |
| Anti-gaming | 🟩 | 0 | No trivial assertions |
| Quality flags | 🟪 | <count> | <list of subjective improvement opportunities, if any> |
| **Overall verdict** | **🟩** | **0** | — |

### Rollback on Failure

If either verify agent reports **any violations**:
1. Present violations prominently, naming the specific deletions / rewrites at fault.
2. Offer rollback via git — for each affected tracked file, `git restore <file>` returns it to the committed state. (Files flagged untracked/dirty in Step 4.5 were proceeded on with explicit consent; advise the user to inspect those manually.)
3. Do not auto-restore without the user's go-ahead — they may prefer to keep some changes and fix forward.

### Status per file

For each feature file and step class touched, report a status using the icons defined in `<plugin-root>/resources/static/status-legend.md` (plugin-internal controlled vocabulary).

## Out of scope (v1)

- **Mode A (git-diff)** — not supported. Source-to-feature mapping is fuzzy.
- **Source-file scope** — reverse lookup from SUT file to scenarios is unreliable.
- **Full-suite audit** (`/test-authoring:update-component-test all`) — not supported; audit one feature at a time.
- **Integration-test support** — scoped to component tests only.
- **Creating new scenarios directly** — always delegated to `test-authoring:add-component-test-agent`.
- **Restructuring step-class split** — that is refactoring, not test maintenance.


