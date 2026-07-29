---
name: review-issue-fact
description: >
  Fact-check an ISSUE — a bug report, story, or incident description, given as a Jira link / key
  (via Atlassian MCP when available) or as plain / markdown text — against the codebase that is
  its ground truth, BEFORE any fix is planned. The issue-altitude sibling of review-plan-risk and
  review-code-risk: this guards the ISSUE, one guards the PLAN, one guards the FIX.
  The issue is NOT a source of truth — it may carry a misattributed root cause or plain wrong
  information — so the distinct question is diagnosis alignment:
  do its factual claims hold in THIS code, or is the bug misdiagnosed.
  Use this whenever someone wants an issue, bug report, or repro fact-checked or sanity-checked
  before planning a fix, or wants to gate the issue-to-PR pipeline on a verified diagnosis —
  even if they don't say "review-issue-fact".
  Trigger phrases: "fact-check this issue", "is this bug report accurate", "does this issue
  reproduce", "is the root cause right", "is this issue real / misdiagnosed", "/review-issue-fact".
  Do NOT trigger for: reviewing a plan / spec / RFC before implementation (review-plan-risk);
  reviewing an implemented fix / diff (review-code-risk); creating, editing, or transitioning a Jira issue;
  generic line-level bug-hunting (code-review / coderabbit) or
  security scanning (security-review); debugging a failing test; or confirmatory "is my
  understanding correct?" checks that want validation, not adversarial fact-checking.
---

# Review Issue Fact

Fact-check an **issue against the codebase before any fix is planned**. Humans and LLMs share a positive-reading bias: a coherent bug report that names a file, a method, and a plausible cause pulls toward believing it. This skill replaces "the issue looks right" with deliberate disconfirmation — treat the issue as a set of claims under test and check each against the code that is its only ground truth, because the issue is exactly the artifact most likely to be wrong.

**Scope: the issue's diagnosis, anchored to the code — not the plan, not the fix, not generic code quality.** The anchor is the issue (a bug report, story, or incident description) together with the codebase that is its oracle. The issue is the claim under test; the code is the source of truth — when they disagree on a structural fact, the code wins. If the target is a plan, spec, or RFC before implementation, this is the wrong skill — say so and stop (that is review-plan-risk). If it is an implemented fix or diff, say so and stop (that is review-code-risk). A request to create, edit, or transition a Jira issue is also the wrong skill — say so and stop. This skill's distinct question is **diagnosis alignment**: do the issue's factual claims actually hold in THIS code, or is the bug misdiagnosed before we spend the pipeline fixing it — a question generic code review does not ask.

**This is the verdict sibling of the review family — lighter than the two fix skills.** `review-plan-risk` and `review-code-risk` find risks and *auto-fix the artifact*. An issue has nothing to auto-fix: its truth lives in the code, not in text we could rewrite to match it, and the issue is usually external and human-owned. So this skill produces a **verdict**, never an edit — and it drops the auto-fix, opt-in-batch, and propagate machinery the fix siblings need. What it keeps is the family's spine: enumeration separated from calibration, an independent adversarial verifier, and honest voiced limits over silent guesses.

## Step 1 — Resolve and scan the issue

Resolve the issue from whichever source was given, so the skill works whether or not a tracker is reachable:

- **A Jira link or key**, when the Atlassian MCP is available and authenticated — fetch the issue (summary, description, repro steps, comments) with the get-issue tool the session exposes. The tool's namespace varies by environment (`mcp__atlassian__*` or `mcp__claude_ai_Atlassian__*`); detect the one actually available rather than hardcoding it. If the input looks like a Jira reference but the MCP is unavailable or unauthenticated, do not invent the issue: declare `Jira anchor not available` and proceed with whatever text was given, stopping only if there is no content at all.
- **Plain or markdown text** pasted directly — treat it as the issue verbatim.

**The codebase is the oracle.** The current repo is the ground truth the claims are tested against. Identify the areas of code the issue points at — the files, methods, or behaviours its diagnosis names.

**Cross-repo discovery — read what is already on disk, never fetch.** When a claim depends on code outside the current repo, look for the other repo as a sibling already checked out under the same parent folder, and read it one hop deep as evidence. Do not clone it and do not decompile a binary to approximate it: a fetched-or-decompiled approximation is a degraded oracle, and testing a suspect claim against a fuzzy source manufactures exactly the false verdicts this skill exists to prevent. If the repo is not already on disk, the claim is not assessable here — record it for `needs-info` and declare `seam with <repo> not assessed`.

**Surface the resolved scope — informational, not a gate.** State what is under review: which issue, which areas of the codebase its claims touch, which sibling repos were pulled in, and which claims will fall to a cross-repo `needs-info`. Because this skill never edits, there is nothing to gate before — the surface is transparency, not the editing gate the fix siblings hold. Run standalone, it lets the human redirect; run inside the orchestrator, it proceeds unattended.

## Step 2 — Extract and verify the claims

**(a) Enumerate the claims first, without judging them.** Break the issue's diagnosis into discrete, testable propositions — and surface its *assumptions* as claims too, because the issue is precisely the artifact whose assumptions are suspect. A claim is a single checkable statement about the code:

- C1 — the failure occurs in `MethodX` when the input is null
- C2 — the root cause is a missing null-check in `Y`
- C3 — the affected component is `Z`

Enumerate before verifying, as its own pass — judging while enumerating lets the issue's framing pre-filter which claims you bother to write down, and a misframed issue's most load-bearing claim is the one it states most confidently.

**(b) Verify each claim against the code, citing evidence.** Walk the relevant code path and assign each claim a verdict, with the exact location (`file:line`) as evidence. **This pass spawns zero agents** — you do the walking, in this context. Splitting the claims across agents leaves each claim with exactly one judge, so it buys no independent corroboration while multiplying the cost; the independent read is Step 3's, and it is deliberately a separate pass over verdicts that were actually reached here.

- **`confirmed`** — the code corroborates the claim.
- **`refuted`** — the code contradicts it: the named path does not exist, the behaviour is actually correct, or the root cause is misattributed. On a structural fact, a conflict between issue and code is resolved in the code's favour — that is the whole point of having an oracle.
- **`needs-info`** — the code cannot settle it: the claim hinges on runtime behaviour reading cannot decide, the evidence lives in a cross-repo seam, or the issue is too vague to locate. For a runtime-only claim, mark the evidence `static-only: runtime behaviour not verifiable by reading` rather than guessing a confirm — this skill reads code paths, it does not run the repro (running needs a build / env this skill deliberately does without).

**Rate each claim's centrality** — `load-bearing` (a claim a fix would depend on: the root cause, the existence of the failing path) or `incidental`. Centrality decides how the verdict rolls up: an incidental claim being wrong does not sink the issue, a load-bearing one does.

Retain the per-claim verdicts and their cited locations internally — the Step 3 verifier's containment check needs them. Few claims is a valid outcome; do not pad.

## Step 3 — Verify the verdict (independent, adversarial, bidirectional)

A fact-checker that grades its own verdict inherits the bias that produced it. So whenever any verdict was reached, spawn a single fresh agent to challenge the verdict batch.

Spawn it with the `Agent` tool, **read-only**, with an **adversarial prompt** — it did not reach these verdicts, and its job is to falsify them, not bless them. Its skepticism is **bidirectional**, because the two ways to be wrong have opposite costs:

- For each **`confirmed`** claim — try to refute it. A false confirm sends the whole expensive pipeline down a misdiagnosed path.
- For each **`refuted`** claim — try to salvage it. A false refute kills a valid issue that deserved a fix.
- For each **`needs-info`** claim — check whether it is genuinely unassessable, or whether the oracle was in fact reachable and the verdict was just lazy.

**Anti-circularity:** the verifier must re-derive evidence independently, walking from the claim and the codebase — not merely re-reading the `file:line` the verdict cited, which would be using the verdict to prove itself. An inline prompt to a fresh general agent is enough — no dedicated agent file. If a fresh agent cannot be spawned (this skill is itself running inside a subagent, which cannot spawn subagents), do not silently skip and do not self-verify: record the verdict as `not-verified` (`verdict not independently verified`) in the table and stop — a voiced limit.

Give it the issue (the claims under test), the codebase (the oracle), the enumerated claims with their cited locations, and the per-claim verdicts.

It reports two kinds of finding, routed differently:

- **Objective contradiction** — checkable without judgement: the cited evidence does not say what the verdict claims (the verdict points at a `file:line` as proof, but the code there reads the other way; a `confirmed` rests on a path that does not exist). The verdict is mechanically wrong. The **main flow — not the read-only verifier — corrects that one verdict once**, then spawns **one fresh verifier to re-check** (the re-check must be a fresh independent spawn, never an in-context self-review by the main flow, which would re-admit the very bias Step 3 removes). At most one correction and one re-check — there is no loop; emit a one-line status (`re-check C2: attempt 1/1`). If the re-check still disagrees, the claim terminates at verdict `needs-info` with verifier `disputed` — there is no compound `needs-info (disputed)` verdict. (Nothing is git-restored here — the corrected "artifact" is the verdict text, not a file.)
- **Adversarial judgement** — no objective oracle; the verifier offers a plausible alternative reading but no decisive evidence either way. It **keeps the verdict's value and flags the claim `disputed`** for the human — never silently flips it.

A verifier pass means "survived an adversarial read", not "proven true". The residual judgement on a disputed claim stays the human's. Do not overstate the verdict.

## Step 4 — Report the verdict table and recommendation

The deliverable is a single table, one row per claim — every column a closed set so each row fills deterministically:

| Claim ID | Claim | Centrality | Verdict | Evidence | Verifier |

- **Centrality** — `load-bearing` or `incidental`.
- **Verdict** — `confirmed`, `refuted`, or `needs-info`. There is no fourth value; `disputed` is not a verdict.
- **Evidence** — a `file:line`, `static-only` (runtime behaviour not verifiable by reading), or `seam <repo>` (cross-repo, not on disk).
- **Verifier** — `survived` (could not be overturned), `corrected` (the verdict was mechanically wrong and the Verdict column shows the corrected value), `disputed` (verifier raised a hand; lives only here, never in Verdict), or `not-verified` (no fresh agent could be spawned).

Then state the **overall verdict and recommendation**, rolled up from the load-bearing claims (read the final Verdict, and treat any load-bearing claim whose Verifier is `disputed` as `needs-info`, because a disputed verdict is not safe to act on):

- Any load-bearing claim **`refuted`** (and not disputed) → overall **`refuted` → recommend HALT**: do not plan a fix until the diagnosis is corrected. Name the claim and why.
- All load-bearing claims **`confirmed`** (and not disputed) → overall **`confirmed` → recommend PROCEED** to planning.
- Otherwise (a load-bearing claim is `needs-info`, or any load-bearing claim is disputed) → overall **`needs-info` → recommend RESOLVE**: name exactly what is missing — which repo, which runtime check, which clarification, or which verdict is disputed.

The recommendation is **advisory, not a hard gate.** Standalone, it tells the human where the diagnosis stands; inside the orchestrator, it is the artifact the next phase reads — the human still decides at the existing plan-approval gate. State every degradation prominently where it applies — `Jira anchor not available`, `seam with <repo> not assessed`, `static-only`, `not-verified` — so reduced assurance is always visible, never silently assumed.

When the run has a ticket or resolve context (a Jira key was the source, or a `.claude/resolve/<ticket>/` directory exists), write the verdict to `.claude/resolve/<ticket>/fact-check.md` so the orchestrator can pick it up; otherwise just print it. Keep this optional — the skill stands alone and must not depend on an orchestrator that may not exist yet.
