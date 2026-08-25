---
name: review-plan-risk
description: >
  Adversarially review a DESIGN ARTIFACT —
  a plan, spec, RFC, or another skill / command / agent / workflow definition —
  for design risks BEFORE implementation begins.
  Packages pre-mortem, red-teaming, and falsification into a repeatable process:
  find and rate risks,
  verify the plan's load-bearing premises about the current codebase against ground truth,
  auto-fix the risks rated real — in the plan itself, never its execution —
  and independently verify the fixes before reporting a result table.
  Use this whenever someone wants a plan or design pressure-tested,
  wants a spec reviewed before building,
  or wants a SKILL.md / workflow definition checked for gaps —
  even if they don't say "pre-mortem".
  Trigger phrases: "pre-mortem this", "stress-test this design", "what could make this fail",
  "find the holes in this plan", "review this spec before we build",
  "does this plan's premise about the current code hold", "review this skill's design",
  "propagate this fix to the plugin's other skills", "/review-plan-risk".
  Do NOT trigger for: reviewing code or diffs, debugging an existing implementation,
  post-implementation code review,
  propagating a code change across source files (refactoring, not design review),
  or confirmatory "is this correct?" checks that want validation rather than adversarial
  enumeration — those want normal review, not this skill.
---

# Review Plan Risk

Find and fix **design risks in a plan before it is built**. Humans and LLMs share a positive test strategy: reading a coherent plan pulls toward confirming it. This skill replaces "is this good?" with deliberate disconfirmation — search for the ways the design fails, then close them in the plan.

**Scope: the design, not its execution.** If the target is code, a diff, or an existing implementation, say so and stop. Runtime concerns (crashes, races, malformed inputs) belong to implementation review — unless the design fails to account for them, in which case the gap is the risk.

## Step 1 — Scan the plan

Read the artifact in full — a plan, spec, RFC, or a workflow definition (SKILL.md, command, agent prompt; a first-class case). If no concrete artifact is given, ask for one — do not pre-mortem a vague idea. A caller may additionally name a **baseline copy** of the artifact in its invocation — a pre-fix snapshot of a file it deliberately keeps untracked and owns; note it if present, as Step 3 uses it to decide whether an otherwise-unrecoverable file can still be auto-fixed.

The artifact may span more than one file. List the files it references and classify each: **contract-bearing** — the artifact depends on its behaviour, outputs, or guarantees, or hands work off to it (a spawned agent prompt, a consumed schema, a shared rule file) — or **incidental** — a doc pointer, background reading. Read the contract-bearing partners, **one hop only** — never recurse further unless a specific seam risk demands it, and say why. Present the resolved scope before finding risks — which partners are pulled in, which references were judged incidental — and let the human promote or drop. This scope confirmation is the **only gate that blocks before Step 3 starts editing** — surface it and let the human adjust before auto-fixing, rather than scanning and fixing in one unbroken sweep. (The Step 3.6 `edge-case` opt-in batch is a human touchpoint too, but it lands *after* the real fixes are applied and verified — not before editing begins; and the `proposed` / `needs decision` routings surface at the result table, after the edits.) Any partner left unread, by choice or because it is not readable, is declared in the final output as "seam with X not assessed": a voiced limit, never a silent blind spot.

Partner files are evidence for judging the main artifact's seams; **the review's anchor never moves to a partner** — auditing a partner is its own separate invocation.

One default extension, set at the scope gate and never grown mid-review: when the anchor is a workflow definition that **spawns subagents** (an orchestrator skill delegating to writer / verifier / capture agents), the spawned subagent definitions are **co-anchors, not partners** — the workflow's behaviour lives across the orchestrator and its agents together, so reviewing the orchestrator alone loses half the picture, and per-agent follow-up invocations re-read the same shared partners each time. Read each co-anchor in full and sweep it in Step 2 like the anchor itself; its references join the partner pool (one hop, as usual). The human may drop any co-anchor at the scope gate; a dropped or unreadable co-anchor is declared "subagent X not assessed". Files merely referenced — shared rules, schemas, callers — stay partners: evidence only, the anchor rule above stands.

## Step 2 — Find possible risks

Find risks through an **independent fan-out**, not one reading — confirmation bias is heaviest at the find stage, where a single mind sweeping every lens anchors on its first coherent theory and stops seeing past it. Fresh finder agents do the sweeping; **delegate before you form your own view** — do not read the artifact for risks yourself first, or you will re-seed the finders with your theory and re-admit the bias the fan-out exists to break. The adversarial lenses below (with their depth and type-weighting) are the finders' brief — derive risks from what THESE artifacts actually say, citing the exact location (file and line) for each; the spawn mechanics and the merge follow the lenses:

- **Backward from failure** — assume the built result failed; what in the plan allowed it?
- **Assumption surfacing** — what does the design silently rely on, and what happens when it is false? When a load-bearing assumption is a *checkable claim about the current codebase* — a file, method, behaviour, or config the plan treats as already true — it is a **premise to verify against the code**, not merely to reason about; the ground-truth pass in calibration settles it.
- **Invariant violation** — for each claimed rule or property, what maintains it, and which path can break it?
- **Silent failure / boundary** — where would a wrong value, missing input, or skipped step degrade quietly instead of loudly?
- **Second-order effects** — what new failure does each proposed change itself introduce?
- **Cross-artifact contract** — for each contract-bearing partner: does the producer's output satisfy the consumer's assumptions, and which obligation sits in a seam neither side owns?
- **Executability** — will the intended executor actually follow the design as written? For a plan, the implementer; for a SKILL.md, command, or agent prompt, the LLM at runtime. Hunt what makes execution diverge from intent: an ambiguous or reorderable step, a completion criterion loose enough to declare done early, guidance phrased as a negation the executor drifts past, a trigger scoped so it fires too broadly or too narrowly, dead or self-contradictory instructions. The recurring shapes have names — premature completion, sprawl, no-op steps, negation-based steering, sediment — and each is a risk when the artifact is a workflow definition.
- **Necessity** — for each element the design introduces, is it load-bearing or speculative? Flag gold-plating: an abstraction with a single caller, a configuration knob no requirement asks for, an escape hatch built before the boundary it guards exists. The failure here is not that the design breaks but that it carries cost and surface area nothing needs — the mirror image of the other lenses, which hunt what is missing or wrong rather than what is superfluous.

Push each lens past its first obvious hit; stop only when further risks become forced or implausible.

Not every lens carries equal weight for every artifact — before sweeping, name the artifact's type and spend the enumeration budget where that type concentrates risk. A SKILL.md, command, or agent prompt foregrounds **Executability** and the trigger-misfire it covers; a plan that changes behaviour already in place foregrounds migration and reversibility — the rollback, the backward-compatibility, the version and downstream-consumer impact — as a sharpened case of second-order effects; a high-fan-out workflow adds a cost angle — tokens, latency, agent count. Every lens still runs; the type only decides where to push hardest and which conditional angle to add.

Spawn the finders with the `Agent` tool — **read-only, blind to one another, and each given the full lens set, not a slice of it**. Diversity comes from their independence, so every finder sweeps **all** the lenses on the anchor and every co-anchor: a lens handed to only one finder is unwatched everywhere else, and a miss there is unrecovered. Give each finder the same inputs — the anchor, each co-anchor, **the contents (or readable paths) of every contract-bearing partner** so the cross-artifact lens has something to run on, and the resolved scope; when the artifact is not a readable file (a plan-mode draft, an in-context-only artifact), **inline its full text into every prompt**, since there is nothing to hand by reference. **Default to two finders** — enough for independent corroboration without redundancy — dropping to one only when a second would merely re-read the same few paragraphs, and rising to a small handful only for a large or multi-co-anchor artifact. Keep the count small: the fan-out should cost less than the bias it removes. Each finder only **enumerates** — risks with cited locations, no plausibility or severity rating — which keeps enumeration ahead of calibration exactly as the next pass requires.

Then **merge and dedup** the finders' returns yourself: collapse risks that share a cause even when finders reached them through different lenses, worded them differently, or cited slightly different lines — match on the failure, not the phrasing — and when finders cite different locations for one risk, **keep every cited location** so the Step 3 fix and the Step 3.5 containment check see all of its sites. Then confirm the merged set covers the ground it should — both the lenses this artifact's type foregrounds and, the check no lens runs on itself, any plausible failure that falls **outside every lens above** (the unknown-unknowns the deleted completeness pass existed to doubt). A foregrounded lens that produced nothing, or such an out-of-lens gap, earns **one** more sweep before calibration — at most once, no loop: the follow-up does not re-run this coverage check — not a pass; scoped this way it neither re-opens a partner the scope gate dropped nor recurses. The fan-out widens enumeration only; calibration, premise verification, and every gate below stay with you. If fresh agents cannot be spawned — this skill is itself running inside a subagent, which cannot spawn its own, the same limit Step 3.5's verifier faces — or the artifact is too small to warrant even a second reader, sweep once yourself with the full lens set and carry **`find: not independently fanned out`** into the Step 4 result as a voiced limit beside the table, never silently, under Step 1's voiced-limit rule.

**Then enumerate the elements the design itself introduces** — the new tables, fields, axes, commands, rules, abstractions, and escape hatches it adds — **and list which of the merged risks cite each one**, from the cited locations you retained. Read that element list off the **artifact**, never off the risk set and never off what the Necessity lens already flagged: that lens reaches leaf elements freely and tends not to aim at the mechanism the artifact is built around, so sourcing the list from its findings inherits exactly that blind spot.

Two things this is not. Not a second dedup — the collapse above merged risks that *are* the same risk, and every risk here stays distinct. And not a repartition of the whole set: you iterate the introduced elements, which are few, not the risks, which are many.

Where several independent risks cite one introduced element, that is the one question the per-risk fixes cannot reach on their own — whether the element should exist at all, rather than whether each risk inside it can be closed — and the smallest revision closing every risk on such an element is sometimes removing it. Carry it into Step 3's fix planning, which already holds the whole fix set in view before touching anything. Report it as **one table, largest first, and let that table be the whole deliverable** — restating it as prose afterwards buries the few elements that carry the concentration under the many that carry two. The count is data for the reader, **never a trigger**: an element the design did not introduce is outside this question however many risks cite it, and one it did introduce earns the question at two.

Then **calibrate**, as its own pass after enumerating — blending them lets confirmation bias back in, and manufactured edge-cases pass unflagged:

- Rate each risk by **plausibility** (real / edge-case / theoretical) and **severity** (low / medium / high).
- **Verify the load-bearing premises against ground truth.** The design rests on factual claims about the *current* codebase — a file, method, behaviour, or config it treats as already true. Enumerate the **load-bearing** ones (a premise a fix would build on, not every incidental detail) and check each against the code, which is the oracle: a premise the code **refutes is itself a `real` risk** — a false foundation, the highest-value class to catch before building — so promote it into the risk table rather than emitting a separate verdict. Stay scoped: verify only load-bearing premises, and leave the exhaustive issue-against-code fact-check to `review-issue-fact` (a different artifact, an issue not a plan) — this pass exists to stop the design from resting on a false fact, not to grade every claim. Never refute a *post-change* path with the pre-change files it will replace, and say plainly when a premise is reasoning-only, unverified.
- Drop what the evidence contradicts; flag the theoretical.

When the premise check runs and a fact-check verdict for this run already exists on disk — `.claude/resolve/<ticket>/fact-check.md`, written by `review-issue-fact` before planning — reuse it instead of re-verifying the same ground. Trust a premise **only when it confidently matches** a fact-check claim already marked `confirmed` with verifier `survived` — an unmatched or only loosely-matched premise is verified, not assumed, so trust is the narrow case and direct verification the default — and spend the check only on the **delta**: premises the plan introduces that the fact-check never saw, plus any it left at verdict `needs-info`, or flagged `disputed` by its verifier, that the plan has now made load-bearing — a plan promoting an unsettled claim to a foundation is exactly when that claim earns a look. A plan resting on a premise the fact-check `refuted` is a `real` risk: flag it, never silently re-confirm. This is how `review-plan-risk` composes with `review-issue-fact` in the `resolve-issue` pipeline instead of double-checking it; standalone, with no such file, every load-bearing premise is verified directly. Read it if present, degrade if absent — never depend on an orchestrator that may not exist.

Present the surviving risks ranked by **plausibility then severity** — so the `real` risks head the table, `real` + high first (Step 3 auto-fixes the `real` tier and Step 3.6 offers the eligible `edge-case` tier as an opt-in batch, so the reader sees the actionable set first) — as a **single summary table** — one row per risk: ID, title, severity, plausibility, and a description carrying the concrete failure scenario in one or two sentences. No location column (file/line citations are noise to the reader) and no separate per-risk list after the table — the table alone is the deliverable. Exact locations were already cited during enumeration; retain them internally — the Step 3 fixes and the Step 3.5 verifier's containment check both need them, even though the human-facing table omits them. Few risks is a valid outcome — do not pad.

## Step 3 — Fix the risks (automatic, in the plan)

Risks rated **real** are fixed automatically — there is no per-risk pick gate. `edge-case` risks are not auto-fixed; instead, after the real fixes are applied and verified, the eligible ones are offered in a **single multi-select opt-in batch** (Step 3.6) — one confirmation for all, not a per-risk gate and not a hand re-derivation from the table. `theoretical` risks are never auto-fixed or batch-offered: they stay **proposed** in the Step 4 table for the human to weigh.

Two preconditions decide whether a **real** risk is auto-fixed (and, applied the same way, whether an `edge-case` risk is *eligible* for the Step 3.6 batch):

- **Recoverable artifact, judged per file.** Auto-fix only a file that has a safe pre-fix baseline and an undo. The default source of both is git: a file that is editable, git-tracked, and clean, so `git show HEAD:<file>` is a faithful baseline and `git restore <file>` is a one-command undo. A plan-mode draft, a non-file artifact, or a dirty / untracked file has no git baseline — **with one exception**: when the caller names, in its invocation, a **baseline copy** of a file it deliberately keeps untracked and owns (an orchestrator whose design artifact is gitignored on purpose), that copy is the safe baseline and *restore-from-copy* is the undo — reverting the whole file, or a single section, by rewriting it back to the baseline copy. Such a file is recoverable and auto-fixed like a tracked one. Absent both git-recoverability and a caller-supplied baseline copy, leave the file's risks **proposed** and present the revised text instead of writing it. A multi-file artifact is judged file by file — a clean or baseline-copy-backed file is auto-fixed even when a sibling is not.
- **Fix derivable from the artifact's own intent.** Auto-fix only when the smallest revision follows from what the artifact already says. If closing the risk needs a product or design decision no one has made yet (support X or not, which default to pick), do not invent it: leave the risk **proposed (needs decision)** and name the decision the human must make.

Plan the whole fix set before touching anything — hold every real risk and the full artifact in view at once, note where two fixes interact or would leave a seam, then apply the **smallest revision** that closes each failure path. Holistic awareness is not licence to rewrite: each edit stays minimal and within its risk's reach; the point is only that the minimal edits compose into a coherent whole. Stream progress as you go (`Fixing R2: …`) so the human can follow and interrupt.

- Never start building the plan itself — Step 3 revises design text, nothing more.
- If a derivable fix would itself introduce a new risk, say so as you apply it; the Step 3.5 verifier is the independent check on exactly this.
- After applying, re-check each changed section with the Step 2 lenses — but the authoritative quality gate is the independent verifier, not this self-check.

## Step 3.5 — Verify the fixes (independent, adversarial)

Self-review by the agent that wrote the fixes inherits its bias: reading one's own coherent edit pulls toward confirming it. So whenever **one or more fixes were applied**, spawn a single fresh agent to verify the batch; skip this step only when nothing was auto-fixed.

Spawn it with the `Agent` tool, read-only, with an **adversarial prompt** — it did not write these fixes, and its job is to falsify them, not bless them. One hop only: the verifier is not itself verified. An inline prompt to a fresh general agent is enough — no dedicated agent file. If a fresh agent cannot be spawned (this skill is itself running inside a subagent, which cannot spawn subagents), do not silently skip verification — but do not self-verify either (an in-context re-read by the fix author re-admits the bias this step exists to remove). Instead record the batch as **`flagged: not independently verified`** in the result table (the Verifier column's existing `flagged: <reason>` form) and stop: a voiced limit, never a silent blind spot (Step 1's rule).

Give it the pre-fix baseline (`git show HEAD:<file>`, or the caller-supplied baseline copy for a baseline-copy-backed file), the full applied diff (`git diff -- <file>`, or the target diffed against that baseline copy), the Step 2 risks **with their cited locations** (retained internally even though the human-facing table omits them — the verifier needs them as the containment baseline), each claimed revision, and the whole artifact for context. If the cited locations were lost (e.g. to context compaction across a long fix phase), the verifier re-derives them from the artifact and the risk descriptions — not from the diff, which would make the containment check circular (an edit cannot be its own baseline) — and if they cannot be re-derived, declares the containment check not performed rather than skipping it silently.

It reports two kinds of finding, routed differently:

- **Objective violations** — checkable from the diff, no judgement needed: an edit beyond a risk's cited location; a claimed fix the diff does not show or shows differently; an edit to a file outside the anchor (a partner or a sibling); implementation leaked into a design artifact; one risk's fix clobbering another's text. Route each as a deterministic finding: **re-fix once, then re-verify**; if it still violates, revert that hunk (`git restore` the hunk, or rewrite that section back to the baseline copy for a baseline-copy-backed file) and mark the risk **proposed (failed verification)**. Re-fix is attempted **at most once** — there is no loop; emit a one-line status (`re-fix R3: attempt 1/1`) so the bound survives context compaction.
- **Adversarial judgements** — no objective oracle; the verifier raises a hand, never reverts: the revision does not actually close the stated failure path; the fix introduces a new real risk (any severity — the auto-fix tier itself fixes all real risks); the risk itself looks unsubstantiated (its `real` rating overstated); a fix is a band-aid over a structural problem; two fixes read coherently apart but conflict or leave a seam together (judge the combined diff as a whole, not fix by fix). These are **flagged into the result table** for the human — never re-fixed or reverted.

A verifier pass means "survived an adversarial read", not "proven correct". It cannot confirm a risk was genuinely real — that residual judgement stays the human's, made cheaply against the result table. Do not overstate the verdict.

## Step 3.6 — Opt-in batch for `edge-case` risks (single multi-select gate)

Run this **after** Step 3.5 has verified the real fixes, and only when at least one `edge-case` risk is **eligible** — eligible meaning it met both Step 3 preconditions (recoverable artifact, fix derivable from intent). If none are eligible, skip this step silently and go to Step 4.

Present every eligible edge-case risk in **one** multi-select prompt — id, title, severity, and the concrete one-line revision that would be applied — and let the human accept any subset in a **single confirmation** (zero is a valid answer). That one-line revision is a **preview** of the intended edit — the holistic plan below may refine it but stays within the risk's reach, and the final diff and result table show what was actually applied; surface any material divergence from the preview. This is the human's "is this worth fixing?" judgement — the one the verifier cannot make for them (it checks a fix is correct and contained, never whether the risk was worth closing); batching it to one gate is what keeps the hardest-to-spot risks from being lost to the per-risk friction of the `proposed` tier.

For the selected risks:
- **Plan the selected set holistically before touching anything** — the same whole-set discipline Step 3 applies to the real tier, but over the *current* artifact: hold every selected edge-case risk, the already-applied real fixes, and the full post-real-fix artifact in view at once, and note where two selected fixes interact, or where one would leave a seam against another or against a real fix already in place. The already-applied real fixes are **frozen** here (they are verified and locked) — the edge-case edits adapt to them, never re-open them.
- **Apply the smallest revision** that closes each selected path, within that risk's reach, so the edits compose into a coherent whole — not fix-by-fix in isolation. Stream progress (`Applying E2: …`) so the human can interrupt.
- **Then verify the selected set with Step 3.5** (a fresh independent adversarial agent), giving it the **combined** applied diff — the real fixes plus these edge-case fixes — so any seam, whether between two edge-case fixes or between an edge-case fix and an already-applied real fix, is judged as a whole, not in isolation. **Scope its routed findings to the edge-case fixes**: the real-fix hunks are frozen, already-verified context, shown only so seams are visible — the verifier must not raise objective violations against a real hunk or re-open one. Objective violations *in the edge-case fixes* re-fix once then revert; judgements are flagged — exactly as in Step 3.5. If the verifier judges a frozen real fix itself flawed, it emits a one-line advisory for the human, not a routed finding (real fixes were verified in Step 3.5 and are not re-fixed here).

Unselected eligible risks, edge-case risks that were ineligible (needs decision / unrecoverable), and all `theoretical` risks remain `proposed` in the Step 4 table.

## Step 4 — Report the result table

The deliverable is a single table, one row per risk:

| ID | Title | Severity | Plausibility | Disposition | Revision | Verifier |

- **Disposition** — `auto-fixed` (a `real` risk), `opted-in` (an `edge-case` risk the human accepted in the Step 3.6 batch), `proposed`, `proposed (needs decision)`, or `proposed (failed verification)`.
- **Revision** — a one-line summary: the applied edit, or the proposed revision for an un-applied risk (a summary, not the full text).
- **Verifier** — `passed`, `flagged: <reason>`, or `n/a` when nothing was applied to verify.

The applied edits are in the working tree: `git diff` shows them in full, and `git restore <file>` reverts the whole batch if the human disagrees (for a baseline-copy-backed file, the diff is against the supplied baseline copy and the undo is restoring that copy over the target). Point the human at every `flagged` row, every `proposed (needs decision)` row, and any one-line advisory the Step 3.6 verifier raised about a frozen real fix — that is where the residual human judgement lives. If the find stage could not be independently fanned out (Step 2's degrade), state **`find: not independently fanned out`** beside the table — a review-wide limit like Step 1's "seam not assessed" — so the reduced independence is visible, not silent.

## Step 5 — Propagate (optional, only when a fixed risk's pattern recurs elsewhere)

A fixed risk sometimes has siblings — the same pattern in other skills, agents, or reference files of the same plugin or repo. If you notice candidates while fixing — or the human asks to propagate — do not edit them silently and do not expand silently: propagation is its own gated pass, and the gate applies *especially* when the human asked, because a one-line request authorises intent, not each edit.

Propagation patches the verified pattern at its cited locations and nothing else. It is NOT a review of the target files — the anchor does not move (Step 1's rule stands), and a full audit of a sibling remains its own separate invocation.

1. **Verify per target, never apply per pattern.** A pattern that is a risk in the anchor may be intentional in another context (the same "skip silently" that masks a failure in one workflow is a correct opt-in guard in another). For each candidate target, confirm against the actual file: the pattern exists there — cite the exact location — AND it constitutes a risk in THAT artifact's context, not just a textual match. Run the relevant Step 2 lens against the target's context; calibrate the same way. Unsure means ask, not edit.

2. **Present the batch before touching anything.** List every verified target: file, location, why the risk holds there, and the smallest revision proposed. Let the human prune — approve, drop, or question each target, as with the Step 1 scope gate. A "yes" to propagating intent is not a "yes" to each edit.

3. **Fix with Step 3 discipline, per target.** Smallest revision per file; after each fix, re-check the changed section with the Step 2 lenses — a propagated fix is a design change with its own failure modes.

If the same pattern keeps recurring across reviews, flag it to the human as a candidate anti-pattern convention — propagation clears the stock; a convention stops the flow.
