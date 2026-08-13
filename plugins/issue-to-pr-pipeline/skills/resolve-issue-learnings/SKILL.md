---
name: resolve-issue-learnings
description: >
  Harvest the generic, cross-repo learnings that resolve-issue captured during its runs and turn the real
  ones into honored conventions — reading the accumulated candidate "dead-drop", verifying each candidate
  against the current resolve-issue skill as ground truth, then (by default, mode X) writing the survivors to
  a user-global conventions file that resolve-issue reads on its next run, or — only when invoked inside the
  editable plugin source (mode Y) — proposing them as edits to resolve-issue's own SKILL.md for a PR.
  Use whenever someone wants to distil / harvest / review / apply the learnings resolve-issue has accumulated,
  says "harvest resolve-issue learnings", "distil the resolve-issue runs", "update my resolve-issue conventions",
  "apply what resolve-issue learned", or "/resolve-issue-learnings".
  Do NOT trigger to RUN the issue-to-PR pipeline (that is resolve-issue) or to watch a run (resolve-issue-dashboard);
  this skill neither drives a run nor reads a single run's state.md — it processes the accumulated learning store.
  Trigger phrases: "harvest resolve-issue learnings", "distil resolve-issue runs", "update resolve-issue conventions",
  "/resolve-issue-learnings".
---

# Resolve issue learnings

Turn the generic, cross-repo observations that `resolve-issue` quietly captured while running — about its own gate flow, step sequencing, state handling, and how it chains its component skills — into learnings that actually improve future runs. This skill is the *harvest* half of a capture-then-harvest loop: `resolve-issue` captures cheap, unverified candidates during every run (see its own "Capturing generic learnings" section); this skill verifies them against the current skill as ground truth and applies only the ones that survive. The split is on purpose — the capture moment (mid-run, sample-of-one, no skill source on hand) is the worst time to decide a learning is true, so nothing is trusted until it is verified here. It runs **two ways** — automatically, as `resolve-issue`'s own internal upkeep (a safe machine subset, no human in the loop), and deliberately, when a person invokes it by hand (the full version, including the human-judged backlog and promotion to the shipped skill); see Invocation below.

It has **two modes**, and the mode is chosen by *what is reachable*, never by a folder or repo name (those are unreliable — a checkout's folder and its remote repo name routinely differ):

- **Mode X (default, any user, any repo)** — write the verified learnings to a **user-global conventions file** that `resolve-issue` reads at the start of its next run and honors when consistent. Fully local, self-contained, no outward action. This is what makes "the more I use resolve-issue, the better my runs get" true for an individual.
- **Mode Y (maintainer, only when the editable plugin source is reachable)** — instead of (or as well as) writing the personal conventions file, propose the verified learnings as **edits to `resolve-issue`'s own source `SKILL.md`**, so a release carries the improvement to everyone. Always explicit and confirmed; never inferred silently.

This skill never drives a `resolve-issue` run, answers a gate, or reads a single run's `state.md`. It only reads the accumulated learning store and writes conventions / proposes edits. (Being *invoked by* `resolve-issue`'s end-of-run upkeep is not "driving" it — the call goes one way.)

## Invocation — unattended (auto) vs attended (manual)

How far this skill goes depends on how it was invoked. Detect it from an explicit `unattended` / `auto` argument (which `resolve-issue` passes when it auto-invokes at `done`): present → unattended; absent → attended.

- **Unattended (automatic) — resolve-issue's own internal upkeep.** When `resolve-issue` finishes a run and enough candidates have accumulated, it auto-invokes this skill with no human present. Do **only the safe, reversible machine subset**: verify, auto-apply the **high-confidence, structurally-verified** confirmed-X learnings to `conventions.md`, mark anything not machine-decidable (or only borderline-confirmed) as `deferred`, archive what was decided, and stop. **Never prompt a human, never do mode Y.** Hold the auto-apply bar **stricter than attended** — with no human net, the verifier's "drop unless it is a slam-dunk" stance is the *only* guard. A slam-dunk needs **two** things, not one: the observation is structurally confirmed true against the SKILL.md, **and** the preference it implies is a *self-evidently safe, low-risk improvement*. "Confirmed true" is not "wise to honor" — an observation can be factually correct yet imply a preference that is a judgement call (the current behaviour may be deliberate). If turning the observation into a standing preference takes any worth-it / wisdom judgement, it is borderline → **`deferred`, never auto-applied**. The `deferred` backlog is not touched here beyond marking and TTL age-out.
- **Attended (manual) — the full, deliberate harvest.** When a person runs `/resolve-issue-learnings` by hand, do the whole thing: verify any fresh candidates, then bring the human their **worth-it judgement** on the fresh-borderline **and the accumulated `deferred` backlog** — this attended pass is the **only exit** for the low-confidence items the auto runs leave behind, without it they would pile up forever. Then, if mode Y is available and chosen, promote the high-value entries from `conventions.md` into the shipped `SKILL.md`. **Attended is the superset; unattended is its machine-only subset.**

## Locate the stores and the oracle

Resolve the skill directory once via bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}"`

Call that `SKILL_DIR`. If the line above did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`), run `echo "$CLAUDE_SKILL_DIR"` with the Bash tool; if it is empty, ask the user for the `issue-to-pr-pipeline` plugin install path and use `<that>/skills/resolve-issue-learnings`.

- **Learning store (user-global, the same on every repo this user works in):** `$HOME/.claude/resolve-learnings/` with three files — `candidates.md` (the unverified dead-drop that `resolve-issue` appends to), `conventions.md` (the verified, honored output — mode X writes here), and `archive.md` (processed candidates, kept for history). Resolve `$HOME` with the Bash tool (`echo "$HOME"`); on Windows Git Bash this is the user profile. If the directory or `candidates.md` does not exist, there is nothing captured yet — say so and stop.
- **The oracle (ground truth for verification):** in **mode X**, the **currently installed** `resolve-issue` SKILL.md, always reachable as a sibling of this skill — `SKILL_DIR/../resolve-issue/SKILL.md` — because both live in the same `issue-to-pr-pipeline` plugin (name-independent, works in any repo). In **mode Y the oracle is instead the working-tree *source* SKILL.md you are about to edit** (`<repo-root>/plugins/issue-to-pr-pipeline/skills/resolve-issue/SKILL.md`), because that source may be ahead of the installed sibling — always verify against whatever you will edit, so a candidate already satisfied in the source is not re-proposed. Read the right one; it is what every candidate is checked against. **The oracle is that `SKILL.md` *plus its disclosed sibling reference files*** in the same directory — `resolve-issue` discloses some branch-conditional behaviour (archiving, git-handling, and any later siblings) to `*.md` files beside its SKILL.md, so glob `SKILL_DIR/../resolve-issue/*.md`, exclude `README.md`, and treat the whole set as the oracle. Otherwise a candidate about behaviour that now lives in a sibling file would be falsely `confirmed` as a gap merely because `SKILL.md` no longer restates it.

**Subagents cannot self-locate.** Any read-only verifier this skill spawns runs in an isolated subagent that cannot resolve `${CLAUDE_SKILL_DIR}` or `$HOME` for itself. Resolve every path it needs — the oracle SKILL.md and the candidate text — **in this main loop first**, and pass them as **absolute paths** in the subagent's prompt. A subagent given only a relative path or a token reads nothing and verifies nothing silently.

## Mode — X by default, Y only when the editable source is reachable

Decide the mode from reachability, in this order:

1. **Default to X.** X is always available and never takes an outward action, so it is the floor.
2. **Detect whether Y is *possible* — structurally, not by name.** Y edits the plugin's own source, which only exists when this skill is being run from a checkout of the marketplace source repo. Confirm all of: `git rev-parse --show-toplevel` succeeds; the repo root holds `.claude-plugin/marketplace.json` that declares the `issue-to-pr-pipeline` plugin; and the resolve-issue source `<root>/plugins/issue-to-pr-pipeline/skills/resolve-issue/SKILL.md` both exists and is git-tracked (`git ls-files --error-unmatch <path>` succeeds). This is independent of the folder name and the remote repo name, and works for forks. If any check fails, Y is not possible — run X only.
3. **Y is always explicit, confirmed, and attended-only — never inferred, never automatic.** Even when Y is possible, do not switch to it silently, and **never** in an unattended auto-run (which has no human to confirm an outward source edit). Run X, then — only in an attended invocation, and only if the user passed an explicit maintainer intent (e.g. an arg like `to-skill` / `maintainer`) or you surfaced that editable source was detected and they confirmed — additionally run Y. A wrong structural detection is therefore benign: at worst it *offers* an option the user declines; it never edits the source on its own.

## Process

### 1. Read and cluster the candidates

Read `candidates.md`. Group entries by the concept they touch and drop exact duplicates. Each entry is a generic observation plus its evidence (the triggering signal, the relevant `SKILL.md` area, the run it came from) — see the format below. If there are zero candidates, say so and stop; an empty harvest is a normal, healthy outcome.

### 2. Accuracy check — review-issue-fact-shaped, both modes

This is a **fact-check of a claim against an oracle**, the shape of `review-issue-fact` — *not* a hunt for new design risks (that is `review-plan-risk`, used only for the mode-Y edit in step 3b). For each candidate, the question is single and objective: **does this observation still hold against the oracle resolve-issue SKILL.md** (the installed sibling in mode X, the working-tree source in mode Y — see Locate)?

Spawn one fresh, read-only verifier subagent for the batch, with an adversarial prompt — it should try to *refute* each candidate, defaulting to "drop" when unsure. Per the rule above, pass it the **absolute** oracle paths (`SKILL_DIR/../resolve-issue/SKILL.md` **plus every disclosed sibling `*.md` in that directory except `README.md`**, all resolved here) and the candidate text inline. It returns, per candidate, one of:

- **confirmed** — the observation holds against the current skill (e.g. the SKILL.md genuinely has the gap the candidate describes). Carry it forward.
- **already-satisfied** — the skill already does what the candidate asks (it was fixed since capture, or a release absorbed it). **Drop** — and in mode X this is exactly how a convention that a newer release made native gets retired (see Backward compatibility).
- **refuted / not-grounded** — the observation does not hold, or has no checkable basis. **Drop.**
- **not-verifiable / borderline** — a judgement-shaped observation with no objective oracle (e.g. "the gate felt noisy"), or a confirmed one too borderline to apply without a human net. **Never auto-apply.** *Unattended:* mark it `deferred` (with today's date) in `candidates.md` and leave it; **skip entries already marked `deferred` on future auto-runs** — re-verifying will not make a judgement call machine-decidable, so re-checking them every trigger is wasted work. *Attended:* this is where they get their exit.

(Attended only.) The human's residual judgement is "is this worth keeping?" on the fresh-borderline **and the accumulated `deferred` backlog**, presented as one small, pre-filtered batch in a focused maintenance frame — not a per-candidate gate during a run. An unattended run never asks: it applies the slam-dunks and defers the rest, and the attended pass (or TTL) is the only thing that ever clears the deferred set.

### 3a. Apply — mode X (write the conventions file)

Write a convention entry to `conventions.md` for each qualifying learning. **Which qualify depends on the invocation:** *unattended* applies **only the slam-dunks — structurally confirmed true *and* implying a self-evidently safe preference** (the two-part bar in Invocation), so any confirmation whose preference is a judgement call is left `deferred`, not applied; *attended* applies those **plus** the borderline / `deferred` items the human accepted. Each entry (format below) is the preference phrased as a **natural-language rule anchored to a stable, orchestration-scoped concept** — resolve-issue's own gate flow, sequencing, state, the a-draft-plan step, or component-choice, never a delegated component's internals and never keyed to a step id or a rich schema; plus its rationale; the verification date; and a TTL — **an unattended auto-apply always uses a finite TTL, never `structural`**, so a convention the no-human bar wrongly let through self-expires rather than persisting forever; `structural` (no expiry) is reserved for a convention an *attended* pass deliberately kept. `resolve-issue` reads these and honors them when consistent — they are preferences, not hard rules, so a stale one simply stops applying.

**Write atomically.** `conventions.md` is a single user-global file that a concurrent `resolve-issue` run may be reading and a concurrent harvest may be rewriting. Write the new content to a temp file in the same directory and `mv` it over `conventions.md`, so a reader never sees a half-written file (last atomic writer wins). Never do a non-atomic in-place rewrite.

### 3b. Apply — mode Y (promote conventions into SKILL.md), attended-only, when chosen

Mode Y promotes the **already-verified, high-value entries in `conventions.md`** — the set automatic upkeep has been accumulating on this machine — into the smallest edits to the **working-tree source** `resolve-issue/SKILL.md`. It reads **`conventions.md`, not raw `candidates.md`**: under automatic upkeep the confirmed candidates have already been verified and moved into `conventions.md`, so that file *is* the verified staging area Y promotes from (raw `candidates.md` by then holds only the deferred / un-decidable remainder, which is not promotion material); any fresh candidates the attended pass just verified join `conventions.md` first. This is exactly `review-plan-risk`'s native job — hardening a skill definition in place, with its real/edge/theoretical calibration, auto-fix, and independent verifier — so invoke `/disconfirm-first:review-plan-risk` on that SKILL.md, feeding the chosen conventions as the claimed gaps to address. It edits in the working tree; do not commit inside this skill. Then hand control back to the human to review the diff, bump the plugin version **as its own isolated commit**, and open a PR. (`review-plan-risk` spawns its *own* internal verifier and self-sources its baseline from the working-tree file via `git show HEAD`, so the absolute-path rule above does not need to reach into it — that rule covers only the read-only accuracy verifier this skill spawns directly in step 2.)

Note the calibration in `review-plan-risk` was built to rate *risks*, and here it is rating *improvement candidates*; the fit is close (it accepts arbitrary skill definitions) but not exact — treat its real/edge/theoretical split as a usefully-shaped triage, not a precise verdict.

### 4. Archive and prune (lifecycle cleanup)

After applying, in one pass:

- **Archive every *decided* candidate** — adopted (to conventions or a Y edit), dropped (refuted / already-satisfied), or human-discarded — by moving it from `candidates.md` into `archive.md` with its disposition and date, so the next harvest does not reprocess it. It is a move, not a hard delete (history is kept).
- **Leave `deferred` candidates in place — but age them out.** A `deferred` candidate has no disposition yet (it awaits a human), so it stays in `candidates.md`, not the archive. To keep the low-confidence backlog from growing without bound, an unattended run **archives as `expired` any `deferred` entry whose `deferred` date is older than the TTL window** — the automatic backstop behind the attended exit; the next attended pass clears the rest by human judgement. Age-out is opportunistic — it happens on the next harvest (auto or attended), so it is gated behind there being a next harvest; that is acceptable because a `deferred` entry is **inert** (never honored, never counted toward the trigger), so even if no further harvest ever runs, lingering deferred entries do no harm beyond a slowly-growing file — there is no need to age them out on a timer.
- **Prune expired conventions.** This skill is the **single place** that physically deletes from `conventions.md`: drop entries past their per-entry `ttl`, and — if the file's top-line `schema_version` marker is one the current format no longer reads — re-derive what you can or drop the whole file (that marker is per-file, not per-entry, so it is a whole-file decision, never a per-entry skip). `resolve-issue`'s run-start read only skips stale entries in memory and never writes, so this prune is the only writer that competes with nothing for those deletions. Do this with the same atomic temp-then-`mv` write.

## File formats

Each file starts with a one-line schema marker and holds Markdown entries; the content is prose so it never "version-breaks", and the marker exists only so a future format change can be detected and the old file cheaply re-derived or ignored rather than mis-parsed. An entry is one `## …` block; it counts as **fresh** unless that block's own bullets include a `deferred:` line — bind and count `deferred` **per block**, never as a loose file-wide substring. This per-block rule is the contract `resolve-issue`'s `done` trigger relies on to tell fresh from deferred.

`candidates.md` (appended by resolve-issue, read here):

```
<!-- resolve-learnings/candidates schema_version: 1 -->

## <yyyy-mm-dd> · <short-slug>
- observation: <one-line generic, repo-independent, orchestration-scoped preference (resolve-issue's own surface, not a component's internals)>
- evidence: <the concrete trigger — a gate interaction, a SKILL.md area, an observed state>
- origin-step: <the resolve-issue step it surfaced at, e.g. a-gate-approve — metadata/evidence only, not a key>
- run: <ticket> @ <repo path or cwd>
- deferred: <yyyy-mm-dd>   # optional — set by an unattended run that could not machine-decide it; awaits an attended human pass or TTL age-out
```

`conventions.md` (written here, read by resolve-issue):

```
<!-- resolve-learnings/conventions schema_version: 1 -->

## <short-slug>
- preference: <natural-language rule anchored to a stable concept — what resolve-issue should prefer to do>
- rationale: <why, in one line>
- verified: <yyyy-mm-dd> against the resolve-issue SKILL.md oracle   # only mode X writes this file, so the installed sibling
- ttl: <yyyy-mm-dd expiry>   # unattended auto-apply: ALWAYS a finite date. `structural` (no expiry) only for an attended, human-kept convention
```

`archive.md` (written here): the original candidate block, plus `- disposition: adopted-X | adopted-Y | dropped-already-satisfied | dropped-refuted | discarded | expired` and `- processed: <yyyy-mm-dd>`.

## Backward compatibility (no migration engine)

- **Loose coupling does the heavy lifting.** Conventions are natural-language preferences about stable concepts, honored only when consistent — so when resolve-issue's steps are renamed or reordered, a convention is at worst a no-op, never a parse break. There is deliberately no version-to-version migration code.
- **Re-verify, don't migrate.** Every harvest re-checks each convention/candidate against the *current* SKILL.md (step 2). A learning the skill has outgrown comes back `already-satisfied` or `refuted` and is dropped — the verify step is itself the only "migration" needed.
- **TTL ages out the un-verifiable.** Judgement learnings that no oracle can re-check carry a TTL and lapse unless reaffirmed, so they cannot accumulate as silent stale guidance — and the same TTL is the backstop that bounds the `deferred` backlog (the low-confidence candidates an attended pass never reaches are archived `expired`).
- **Schema marker, not schema migration.** If a file's `schema_version` is not the one this skill reads, do the cheap thing — re-derive what you can or ignore the file — never attempt a structured migration.

## Degradation and safety

- **No store / no candidates** — `$HOME/.claude/resolve-learnings/candidates.md` absent or empty: nothing captured yet; say so and stop.
- **Oracle unreachable** — `SKILL_DIR/../resolve-issue/SKILL.md` cannot be resolved or read: verification has no ground truth, so do not guess-apply; report and stop (this should not happen, since the two skills ship together).
- **Mode Y unavailable** — structural detection fails: run X only, and say plainly that source edits were not offered because no editable plugin source is in this working tree.
- **Read-only verifier cannot be spawned** — do not self-verify in the main loop (that re-admits the bias the separate verifier exists to remove); report the candidates as unverified and stop rather than applying unchecked learnings.
- **Never an outward action without confirmation** — mode X is local-only; mode Y edits source but commits nothing and opens no PR itself — it stops at the working-tree diff for the human to review, version-bump (own commit), and PR.
- **Auto-apply has one residual the other guards miss — do not claim it is self-healing.** A convention that is structurally *consistent* with the skill but whose *preference* is an unwise judgement call slips past re-verify (which checks fact, not wisdom) and past honor-if-consistent (which honors it precisely *because* it is consistent). Its real guards are only: the two-part apply-time bar (anything needing a wisdom call is `deferred`, not applied), the **finite TTL** every auto-applied entry carries (it self-expires rather than persisting forever), and the **attended pass** as the periodic human backstop that can prune it. Auto-applied conventions are advisory and honored-if-consistent, so the blast radius is a per-run nudge, not a broken run — but only a human (attended) pass truly clears a bad one.
