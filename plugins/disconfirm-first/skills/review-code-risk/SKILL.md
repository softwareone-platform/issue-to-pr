---
name: review-code-risk
description: >
  Adversarially review an IMPLEMENTED FIX — a committed diff on a branch —
  against the issue it claims to resolve and the plan it was built from, BEFORE the PR is opened.
  Its question is intent alignment:
  does THIS change resolve THAT issue, per THAT plan, without regressing callers or hiding a band-aid.
  Use whenever someone has an implemented fix and wants it challenged before opening a PR.
  Trigger phrases: "challenge this fix / diff", "will this change regress anything",
  "red-team this implementation", "pre-mortem this diff",
  "review my fix before the PR", "/review-code-risk".
  Do NOT trigger for: reviewing a plan / spec / RFC before implementation (review-plan-risk);
  generic line-level bug-hunting or style / simplification cleanup (code-review / coderabbit);
  security-vulnerability scanning (security-review);
  debugging a failing test;
  addressing PR reviewer comments;
  refactoring;
  or confirmatory "is this correct?" checks that want validation, not adversarial enumeration.
---

# Review Code Risk

Find and fix **risks in an implemented fix before the PR is opened**. Humans and LLMs share a positive test strategy: reading a coherent diff that compiles and passes its tests pulls toward confirming it. This skill replaces "the fix looks right" with deliberate disconfirmation — search for the ways the change fails to resolve its issue, regresses, or hides a band-aid, then close them in the diff.

**Scope: the fix, anchored to intent — not the design, not generic code quality.** The anchor is the diff together with the issue it claims to resolve and the plan it was built from. If the target is a plan, spec, or RFC before implementation, this is the wrong skill — say so and stop (that is review-plan-risk). If the request is line-level bug-hunting, simplification, or a security sweep with no intent to verify, say so and stop (that is code-review / coderabbit / security-review). This skill's distinct question is **intent alignment**: did THIS change resolve THAT issue, per THAT plan, without opening a new failure path — a question generic code review does not ask.

## Step 1 — Scan the fix

Read the **anchor triple** in full:

- **The diff** — the committed change under review, taken against the branch's fork point, not the base tip: `git diff $(git merge-base origin/<base> HEAD)..HEAD`, or the three-dot `git diff origin/<base>...HEAD` which resolves the merge-base for you (`<base>` is usually master). The fork-point form avoids pulling in commits the base advanced past since the branch diverged.
- **The issue** — the bug or story the fix claims to resolve (its stated failure scenario, repro steps, acceptance criteria). Fetch it from the tracker if a reference is given.
- **The approved plan** — the design the fix was built from (e.g. a committed `.claude/resolve/<ticket>/plan.md`), so divergence is checkable.

The issue and plan are the **intent baseline**; without them this skill degrades to a generic read. If either anchor cannot be obtained (no tracker access, no plan was recorded), do not invent it and do not silently proceed as if it were present: declare `anchor <issue|plan> not available` in the final output and review against the anchors you do have — a voiced limit, never a silent blind spot.

**Precondition — the fix and its tests are committed before this runs.** This skill runs at the point where the fix and its tests are already committed on the branch (after tests are written, before the PR is opened). That makes `git show HEAD:<file>` a faithful pre-fix-review baseline and the working tree clean, so the skill's own auto-fixes (Step 3) are the **only** uncommitted edits and `git restore <file>` reverts the whole batch. If the working tree is dirty when the skill starts, a clean baseline is not guaranteed: judge per file as in Step 3 (a clean, tracked file is still auto-fixable even when a sibling is dirty), and leave the rest proposed.

**Establish the build/test command up front.** Calibration (Step 2) and the verifier (Step 3.5) run the build and the affected tests, so settle the command the same way test-authoring does — detect it from the repo (build / test config, CI scripts) or a known session value, or ask for it. Record it once and carry it forward, including into the verifier's prompt. If no command can be established, the verifier cannot execute: the review degrades to a static adversarial read, declared in Step 4 and never silently assumed to have run.

The diff may touch more than one file. Classify what it touches and pull in **contract-bearing partners — one hop only**: the **callers and consumers** of any changed signature, contract, or behaviour, read as **evidence** for judging the change's seams. Never recurse further, and never move the anchor onto a partner — auditing a caller is its own separate concern. Present the resolved scope before finding risks — which changed files are the anchor, which callers were pulled in as partners — and let the human promote or drop. This scope confirmation is the **only gate that blocks before Step 3 starts editing**. Any partner left unread is declared "seam with X not assessed".

## Step 2 — Find possible risks

Sweep the diff against its issue and plan with adversarial lenses, deriving risks from what the change actually does — cite the exact location (file and line) for each:

- **Does it close the stated failure path** — the core lens. Walk the issue's repro / failure scenario through the *new* code path. Is the path that produced the bug actually unreachable now, or only the one symptom the reporter happened to hit?
- **Plan divergence** — does the diff implement what the approved plan said, or silently do something else, narrower, or broader? An undocumented expansion is as much a risk as a shortfall.
- **Regression / contract** — for each changed signature or behaviour, do the partner callers still hold? Which obligation now sits in a seam neither side owns?
- **Edge / boundary** — inputs the issue or plan implied (null, empty, zero, concurrent, boundary, failure of a dependency) that the new path does not handle.
- **Second-order effects** — what new failure does the change itself introduce (performance cliff, deadlock, ordering, resource leak, a now-dead branch)?
- **Band-aid vs root cause** — does the fix patch the symptom while the structural cause remains, so the next variant of the same bug will recur?
- **Test adequacy** — does the change's own new test actually exercise the fixed failure path, or is it green-but-vacuous (asserts a tautology, mocks away the thing under test, never hits the branch the fix added)?

Push each lens past its first obvious hit; stop only when further risks become forced or implausible.

Then **calibrate**, as its own pass after enumerating — blending them lets confirmation bias back in, and manufactured edge-cases pass unflagged:

- Rate each risk by **plausibility** (real / edge-case / theoretical) and **severity** (low / medium / high).
- **Ground-truth by running, not just reasoning.** Where a risk is checkable, verify against reality: build the change and run the relevant tests; confirm the bug's repro no longer reproduces and that nothing already breaks. Prefer an executed check over an argued one; say plainly when a risk is reasoning-only, unverified (e.g. the build/test command is unavailable — see Step 4).
- Drop what the evidence contradicts; flag the theoretical.

Present the surviving risks ranked by **plausibility then severity** as a **single summary table** — one row per risk: ID, title, severity, plausibility, and a one-or-two-sentence concrete failure scenario. No location column (citations are noise to the reader); retain the exact locations internally — the Step 3 fixes and the Step 3.5 verifier's containment check both need them. Few risks is a valid outcome — do not pad.

## Step 3 — Fix the risks (automatic, in the diff)

Risks rated **real** are fixed automatically — there is no per-risk pick gate. `edge-case` risks are not auto-fixed; after the real fixes are applied and verified, the eligible ones are offered in a **single multi-select opt-in batch** (Step 3.6). `theoretical` risks stay **proposed** in the Step 4 table.

Two preconditions decide whether a **real** risk is auto-fixed (and, applied the same way, whether an `edge-case` risk is *eligible* for the Step 3.6 batch):

- **Recoverable, judged per file.** Auto-fix only a file that is editable, git-tracked, and clean, so `git show HEAD:<file>` is a faithful baseline and `git restore <file>` is a one-command undo. A dirty / untracked file has no safe baseline: leave its risks **proposed** and present the revised code instead of writing it. Judge file by file.
- **Fix derivable from intent.** Auto-fix only when the smallest revision follows from what the issue and plan already require. If closing the risk needs a product or design decision no one has made yet, do not invent it: leave the risk **proposed (needs decision)** and name the decision.

**Blast-radius guardrail — auto-fix stays inside the anchor.** The diff under review is the anchor; the partner callers are evidence only. Auto-fix touches **only the changed files**. If closing a risk would require editing a caller or any file outside the anchor, that is an out-of-anchor edit: **leave it proposed**, name the file that must change, and do not edit it. This keeps an aggressive auto-fix policy from quietly rippling into the rest of the codebase.

Plan the whole fix set before touching anything — hold every real risk and the full diff in view at once, note where two fixes interact or would leave a seam, then apply the **smallest revision** that closes each failure path. Holistic awareness is not licence to rewrite: each edit stays minimal and within its risk's reach. Stream progress as you go (`Fixing R2: …`) so the human can follow and interrupt.

After applying, run a quick build sanity so the verifier is not handed code that fails to compile — but the **authoritative quality gate is the independent verifier (Step 3.5), not this self-check**. If a derivable fix would itself introduce a new risk, say so as you apply it.

**Do not edit tests here.** A test-adequacy risk (a vacuous or missing test) is **flagged and handed off** to `test-authoring` (`add-*-test` / `update-*-test`) — never fixed inside this skill, and never by auto-invoking that orchestrator mid-review (no nested workflow in the main loop). The handoff is a recommendation for the human or the next step.

## Step 3.5 — Verify the fixes (independent, adversarial, executed)

Self-review by the agent that wrote the fixes inherits its bias. So whenever **one or more fixes were applied**, spawn a single fresh agent to verify the batch; skip this step only when nothing was auto-fixed.

Spawn it with the `Agent` tool, with an **adversarial prompt** — it did not write these fixes, and its job is to falsify them, not bless them. It is **read-only on source** but **executes build and the affected tests** (verification by running, not just reading). One hop only: the verifier is not itself verified. An inline prompt to a fresh general agent is enough — no dedicated agent file. If a fresh agent cannot be spawned — the `Agent` tool is unavailable, or spawning it returns an error — do not silently skip and do not self-verify: record the batch as **`flagged: not independently verified`** in the result table and stop — a voiced limit (Step 1's rule).

Give it the pre-fix-review baseline (`git show HEAD:<file>`), the full applied diff (`git diff -- <file>`), the Step 2 risks with their cited locations (the containment baseline), the issue and plan (the intent oracle), the build/test command (so it can execute build and the affected tests), each claimed revision, and the changed files for context.

It reports two kinds of finding, routed differently:

- **Objective violations** — checkable without judgement: the build fails; an edit beyond a risk's cited location; a claimed fix the diff does not show or shows differently; an edit to a file outside the anchor (a caller or sibling); one risk's fix clobbering another's. Route each as a deterministic finding: **re-fix once, then re-verify**; if it still violates, `git restore` that hunk and mark the risk **proposed (failed verification)**. Re-fix is attempted **at most once** — there is no loop; emit a one-line status (`re-fix R3: attempt 1/1`) so the bound survives context compaction.
- **Adversarial judgements** — no objective oracle; the verifier raises a hand, never reverts: the revision does not actually close the stated failure path; the fix introduces a new real risk; the risk itself looks unsubstantiated; a fix is a band-aid over a structural problem; two fixes leave a seam together. These are **flagged into the result table** for the human — never re-fixed or reverted.

**A failing test is not automatically an objective violation — triage it against intent:**

- (a) The fix broke a test that asserts **still-valid** behaviour → an objective regression → **re-fix once, else revert** (as above).
- (b) The fix correctly changed behaviour the issue / plan **intended to change**, leaving a **pre-existing suite test** (one *outside* this change's committed diff, not authored for this fix) now **stale** → **flag and hand off to `update-*-test`; do NOT revert.** The oracle is the issue / plan's intent, not "a red test means the fix is wrong".
- A test **newly written in this change** cannot be "stale" — it was authored for the fix. If it is red, it is case (a), or the fix itself is wrong.

Discovering *which* pre-existing tests touch the changed behaviour (so the verifier knows what to run for case (b)) uses the change's touched symbols/files to select the affected suite — run that subset, or fall back to running the suite and diffing the failure set against the pre-change baseline.

A verifier pass means "survived an adversarial read", not "proven correct". It cannot confirm a risk was genuinely real — that residual judgement stays the human's. Do not overstate the verdict.

## Step 3.6 — Opt-in batch for `edge-case` risks (single multi-select gate)

Run this **after** Step 3.5 has verified the real fixes, and only when at least one `edge-case` risk is **eligible** (met both Step 3 preconditions). If none are eligible, skip silently and go to Step 4.

Present every eligible edge-case risk in **one** multi-select prompt — id, title, severity, and the concrete one-line revision that would be applied — and let the human accept any subset in a **single confirmation** (zero is valid). That one-line revision is a preview; the final diff and table show what was actually applied. This is the human's "is this worth fixing?" judgement — the one the verifier cannot make for them.

For the selected risks: plan the selected set holistically over the *current* code (the already-applied real fixes are **frozen** — verified and locked; edge-case edits adapt to them, never re-open them), apply the smallest revision each within the blast-radius guardrail, then verify the selected set with Step 3.5, giving the verifier the **combined** applied diff so any seam is judged as a whole. Scope its routed findings to the edge-case fixes; the frozen real-fix hunks are context only.

Unselected eligible risks, edge-cases that need a decision, and all `theoretical` risks remain `proposed` in the Step 4 table.

## Step 4 — Report the result table

The deliverable is a single table, one row per risk:

| ID | Title | Severity | Plausibility | Disposition | Revision | Verifier |

- **Disposition** — `auto-fixed`, `opted-in`, `proposed`, `proposed (needs decision)`, `proposed (failed verification)`, or `flagged: handed off to <skill>` (a test-adequacy or out-of-anchor risk routed elsewhere).
- **Revision** — a one-line summary of the applied edit, or the proposed revision for an un-applied risk.
- **Verifier** — `passed`, `flagged: <reason>`, `not independently verified`, or `n/a`.

If the build/test command could not be obtained, the verifier could not execute: say so explicitly in the table — `tests not executed; verification limited to static adversarial read` — so the reduced assurance is visible, never silently assumed.

The applied edits are in the working tree: `git diff` shows them in full, and `git restore <file>` reverts the whole batch. Point the human at every `flagged` row, every `proposed (needs decision)` row, and every test-adequacy hand-off — that is where the residual human judgement and follow-up live.

## Step 5 — Propagate (optional, only when a fixed risk's pattern recurs in the change's blast radius)

A fixed risk sometimes recurs at sibling locations **within the same change's reach** — the same missing guard in another arm the diff touched, the same contract gap at another changed call site. If you notice candidates while fixing — or the human asks to propagate — do not edit them silently and do not expand silently: propagation is its own gated pass, and the gate applies *especially* when the human asked, because a one-line request authorises intent, not each edit.

**This is not a refactoring tool and not a repo-wide sweep.** It patches the verified pattern at sibling locations inside the change's blast radius and nothing else; a broad cleanup across the codebase is a separate, deliberate change with its own review.

1. **Verify per target, never apply per pattern.** A pattern that is a risk at one site may be intentional at another. For each candidate, confirm against the actual code that the pattern exists there (cite the location) AND constitutes a risk in that context — run the relevant Step 2 lens, calibrate the same way. Unsure means ask, not edit.
2. **Present the batch before touching anything.** List every verified target: file, location, why the risk holds there, the smallest revision proposed. Let the human prune — approve, drop, or question each. A "yes" to propagating intent is not a "yes" to each edit.
3. **Fix with Step 3 discipline, per target**, then re-verify with Step 3.5 — a propagated fix is a change with its own failure modes.

If the same pattern keeps recurring across reviews, flag it to the human as a candidate anti-pattern convention rather than re-propagating forever.
