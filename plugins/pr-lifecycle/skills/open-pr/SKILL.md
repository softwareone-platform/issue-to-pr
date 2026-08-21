---
name: open-pr
description: >
  Open a pull request (Azure DevOps or GitHub) for the current branch,
  giving it a title and description that follow the CALLER's own conventions —
  learned at runtime from their past merged PRs —
  with a ticket link and a description of what changed and why,
  in whatever shape those PRs use.
  Use whenever someone wants to open / raise / put up a PR, finish a branch,
  or send changes for review on Azure DevOps or GitHub, even if they don't say "open-pr".
  The target branch is taken from the request or defaults to the repo's own default branch,
  and the convention is learned from the target's own previous PRs where it has any —
  so a backport onto a maintenance or release line can follow that line's convention.
  It always shows the title and description for confirmation first
  and never creates the PR without explicit approval.
  Trigger phrases: "open a PR", "raise a PR", "create a pull request",
  "put this up for review", "PR this branch", "backport this to a release line",
  "open-pr", "/open-pr".
  Do NOT trigger for: reviewing or summarizing an existing PR;
  triaging or replying to PR comments (that is a separate resolve-pr-comments skill);
  completing / merging a PR; starting a branch; or plain git operations.
  This is the team-agnostic open-pr skill for the issue-to-PR workflow.
---

# Open PR

Open a pull request for the current branch on the detected PR platform (Azure DevOps or GitHub). The title and description are drafted to match **the caller's own previous PRs**, read off the repo's own history — falling back to everyone's PRs, and then to no convention at all — rather than a fixed house style, then shown for confirmation. The PR is **never created without explicit approval** — opening a PR is an outward-facing action.

This skill is backend-agnostic: the platform-specific mechanics (create PR, dup-check, label, merged-PRs-by-target query, PR cross-reference link) live in **backend adapter reference docs** under `resources/backends/`, and the ticket-link mechanics live in **tracker adapter reference docs** under `resources/trackers/`. The skill body detects platform and tracker, loads the matching adapters, and follows their recipes — it holds **no `az`/`gh`-specific field parsing and no tracker-specific id/URL parsing** of its own. It borrows the safety rails of a PR-creation flow but is deliberately narrower: it opens a PR for the branch **as it is** — publishing it to the remote first if it is not there yet, since the PR needs it. It does not merge the base branch in, does not delete branches, and does not triage review comments (that is `resolve-pr-comments`).

## Step 0 — Detect platform + tracker, load adapters, announce

Before anything else, resolve which backend and tracker this run targets:

- **PR platform** — from `git remote get-url origin`:
  - `dev.azure.com` or `*.visualstudio.com` → **Azure DevOps** (`resources/backends/azure-devops.md`).
  - `github.com` → **GitHub** (`resources/backends/github.md`).
  - Ambiguous or another host → voice the limit and ask the user which platform to target rather than guessing.
- **Issue tracker (precedence — first match wins):**
  1. **Explicit config wins:** if `.claude/pr-lifecycle.json` (optional, gitignored) pins the tracker type, use it (and take the Jira base URL from it).
  2. else **infer** the type from an existing ticket ref: `[A-Z][A-Z0-9]+-\d+` → **Jira** (either platform); a bare numeric issue ref → **GitHub Issues** — but only on a **GitHub** remote (on Azure DevOps `#<n>` is a work-item link, not a GitHub issue, so a bare number does not imply GitHub Issues there).
  3. else **default by platform**: a GitHub remote → **GitHub Issues** (zero-config); an Azure DevOps remote → **Jira**.
  4. No ticket at all → produce no tracker line (same as today).
  - Jira → `resources/trackers/jira.md`; GitHub Issues → `resources/trackers/github-issues.md`.
- **Announce** the detected platform and tracker so a silent wrong guess is impossible.

Load the matching backend and tracker adapters and run the platform/tracker-specific parts of the steps below through them. The **only** backend seam in this body is recognising the remote string to *select* the adapter — no field access beyond that. (Adapter paths are relative to the **plugin root** — `plugins/pr-lifecycle/resources/backends/` and `resources/trackers/` — not the skill directory.)

## Step 1 — Detect the target branch

- **Git cannot tell you which branch this one was cut from, so do not try to work it out.** There is no field for it: before the first push there is no upstream, and after `git push -u` the upstream is this branch's *own* remote copy; the reflog says only `branch: Created from HEAD`, names no branch, is local, and expires. Reconstructing it from topology fails on ordinary cases rather than exotic ones — a branch already on the remote scores as its own parent, and merging the base in before opening the PR reverses the ranking. What follows is a default plus two ways for a human to name something else, not a derivation.
- **Take the target from the request or the session whenever either names it.** "backport this to release/2.5"; the branch this one was checked out from earlier in this same session; a branch name that spells the line out. Each is the human telling you the target. Note which end a signal points at: a cherry-pick names the commit's **source**, which on a backport is the branch you are porting *from* — the target is in the checkout, not the pick.
- **Otherwise default to the repo's own default branch.** `git symbolic-ref --short refs/remotes/origin/HEAD` yields `origin/<branch>` — strip the prefix. That ref is written by `git clone` and **`git fetch` never refreshes it**, so confirm it against the remote with `git ls-remote --symref origin HEAD` (read-only, changes no local state) rather than trusting a stale local copy; if neither resolves, fall back to whichever of `main` / `master` the remote actually has, and ask if both exist. Both PR platforms default to exactly this when no base is given, so it is the least surprising answer rather than a guess dressed up as one.
- **Announce the target and where it came from** — `target: release/2.5 (from your request)`, `target: master (repo default)` — and **ask rather than guess** whenever the request is ambiguous, two candidates are in play, or the branch plainly does not sit on the default line. Everything downstream is silent about a wrong target: Step 2's ahead-count still passes, and Step 3 happily learns the wrong branch's convention.
- **When that ask cannot be reached** — running non-interactively, or inside a subagent that cannot prompt — do **not** fall through to the default as though it had been chosen. Say `target: master (repo default, unconfirmed — could not ask)` and treat it as a voiced limit, the same way Step 4 treats a confirmation it cannot obtain.
- **A branch name never changes the format.** A maintenance or release line is an ordinary target; the only thing that differs is what Step 3's sample turns out to contain.

## Step 2 — Preconditions (stop and report if any fails)

Run these before drafting anything, because each is a common first-run blocker:

- **Has commits to PR.** The branch must be ahead of the target: `git fetch`, then `git rev-list --count origin/<target>..HEAD` must be greater than 0.
- **On the remote — publish if needed.** Creating the PR needs the source branch on the remote. A not-yet-pushed branch is **not** a stop: after confirmation, open-pr publishes it (`git push -u origin <branch>`) as part of the create in Step 4. (Running non-interactively it does not push and does not create — see Step 4.)
- **No duplicate.** Check for an existing open PR for this source to target via the **backend adapter's dup-check recipe**. If one exists, **stop and point the user to it** — do not open a second PR, and do not modify the existing one here.

## Step 3 — Learn the convention for this target, then draft

**No shape is assumed.** How a title and description look is read off previous pull requests, in this order:

Two things narrow a sample — **whose** PRs and **which branch** they landed on — so there are four probes. Take the first that clears a small floor of about **three**; one prior PR is a data point rather than a convention, and a repo where the caller has a single merge while the branch has sixty is precisely where copying that one is wrong.

1. **Yours, into this target.**
2. **Anyone's, into this target.**
3. **Yours, anywhere in the repo.**
4. **Anyone's, anywhere in the repo.**

Whose it is outranks which branch it landed on, because it is their pull request. If none of the four clears the floor, **no convention is known and none is invented**: draft plainly (below) and say that is what happened.

**Where that sample comes from is the backend adapter's call, and it genuinely differs by platform.** On one, completing a PR writes its title *and* its whole description into a commit on the target branch, so git holds everything and no API call is needed. On the other, several merge strategies coexist in one repo and some leave no trace of a pull request at all, so the platform's own PR list is the only sound source. Ask the adapter which; do not assume git has it.

Three rules bind whichever source the adapter names:

- **Bound the sample to the target's own history.** A branch inherits every commit made before it was cut, so an unbounded read of a young maintenance line returns the *default branch's* PRs and presents them as the line's. Where the source is git, bound it at the branch point — `git merge-base origin/<default> origin/<target>` — and where it is the platform API, its base filter already does this.
- **Read remote-tracking refs, never bare local branch names.** A local `release/5` is routinely many commits behind `origin/release/5`, and in a fresh clone it does not exist at all: the first is silent and yields a stale sample, the second is a loud unknown-revision error. `git fetch` updates `origin/*` and leaves local branches untouched, so fetching is not protection against this.
- **Identify a person by a pattern, and expect it to be imprecise.** One person's display name appears in more than one form inside a single repo (`Surname, First` alongside `First Surname`), and matching is case-sensitive unless you ask otherwise. Use a distinctive substring of `git config user.name` or `user.email`, and if the sample it returns contains more than one person, widen to rung 2 rather than learning a stranger's style.

Probes 3 and 4 are the same commands without the target bound, and reaching them means the target has little history of its own. **Say which probe you used** — that is the honest form of what an unbounded read of a young branch would have done silently.

From whatever sample you get, infer the shape by **majority**, with the most recently merged breaking a tie and a single prior PR used directly.

**Expect the answer to be "no structure", and treat that as a finding about form only.** A short, plain, unformatted description is what most people write most of the time; headings, bullet lists, and diagrams are the exception. So a sample of one-line bodies tells you the *form* is plain prose — write plain prose, and do not promote it to headings or bullets because those look more thorough. That is imposing a shape, which is the one thing this step exists to avoid. The same applies to whatever a layout points at: where a majority of the sample references the pull request a change was ported from, reproduce that; where only some do, it is not the convention.

**What the sample must never teach you is how little to say.** Form is a convention; substance is not. Nobody's house style is "say nothing" — an empty or one-word description is what happens when writing one costs effort and no reviewer insists, which is precisely the gap this skill exists to close. So the two are learned differently: take the *form* from the sample every time, and hold the *substance* to the floor below regardless of what the sample did. Getting form wrong is mildly wrong and nothing enforces it; matching a repo's silence makes the draft worthless, which is the failure that matters.

Where the sample's bodies are empty or near-empty there is, in any case, no form in them to copy — so use the least form that carries the substance, which is plain prose, and **say in the announcement that you did**: `their descriptions are empty or one line; drafting a real one in plain prose`. That line is what lets a caller who genuinely wants the house silence say so.

**Announce what you learned in enough detail to be contradicted** — the rung, the sample size, and each shape with the count that carried it: `release/5: yours 1, all authors 41 -> used all authors; ticket prefix "ACME-123:" 28/41, port marker "Backport ... to release/5" 9/41, flat bullet body 31/41`. **Count them; do not estimate.** Every fraction here has to come from tallying the sample you actually read, over that one sample's size — a figure you did not count is decoration, and a detailed-looking announcement nobody counted is worse than a bare one, because it invites the human not to check. If you cannot tally a feature, name it without a fraction. Showing the rung and both counts is what makes the rung choice itself reviewable — a habit of the caller's that their team does not share, or a marker some tool wrote, is visible here and nowhere else. A convention read off history can be an artefact of that history — one prolific author's habit outvoting the team's, or a marker some tool wrote — and the human is the only party who can recognise that. A bare count hides precisely the thing worth vetoing.

**An empty sample and a failed command are different, and only one of them means "no history".** `git log` fails loudly for a ref that does not exist, so an empty result from it is real. The adapter's API fallback does not: it returns an empty list with a *success* exit both for a nonexistent target and for a host it is not authenticated against. Confirm the command actually ran before reading emptiness as history; when it did not, name what failed and degrade with an announcement, never silently.

Learning covers **how the sampled PRs are written**, not just typography: title casing, description layout — which, far more often than not, turns out to be one or two plain lines with no structure at all, rather than anything sectioned or bulleted, **and the title's ticket-prefix shape** — bracketed (`[acme-123] …`), bare (`acme-123 …`), a Conventional Commits type (`fix(scope): …`), or no prefix at all. Read the shape off the same sample; if the observed PRs carry no ticket prefix, **do not add one** — a repo whose PRs have never carried one is not an oversight to correct. A repo's PR template is likewise part of its convention rather than noise: where the sampled bodies share a heading structure, reproduce it, dropping only what is not content — the template's own instruction comments (`<!-- … -->`) and any heading left unfilled across most of the sample. Never copy a checkbox's *state*, and never copy an AI-provenance footer out of a sampled body: both are item 5's decision, item 5 is off by default, and neither a template checkbox nor a footer some earlier run left behind is the explicit opt-in it requires. The defaults below are what to use when the sample is empty, never a format to impose on a branch that visibly does something else.

**What learning may and may not change.** Reproduce the sample's shape instead of padding it back up: where the majority of those PRs are plainer than a summary plus bullets, that plainness *is* the convention for **form**, not a gap to fill — though it never licenses saying less (see the substance floor below) — a maintenance line whose PRs are a ticket link plus a line pointing at the PR this was ported from is honoured as written, and when a layout references another PR the **backend adapter** supplies the platform's link form (Azure DevOps `!<pr_number>`, GitHub `#<pr_number>`). Two things hold whatever the sample looks like. **A ticket link whenever there is a ticket** — it is mechanical and the platform auto-links it; where neither the sampled PRs nor this branch carry one there is nothing to link and the line is simply omitted, so this is not licence to invent a reference. The same holds for any *other* reference the sampled layout contains: where those PRs point at the pull request a change was ported from, that number comes from whoever asked for the port and from nowhere else — if nobody named one, drop that element and say so rather than inventing a number, which would silently link a reader to an unrelated PR. And **the description must say what the change does and why, whether or not the sampled PRs bothered** — in whatever form the sample uses, whether that is three bullets, a paragraph, or one clause naming the originating PR. This is the one thing the sample does not get a vote on. Keep it proportionate: a one-line change earns a sentence, not a manufactured list, and padding is its own failure. But a body that names no change at all is a failed draft rather than a learned convention — redraft it, and never ship a placeholder or an empty description because the history is full of them. The diagram in item 4 is optional, and the provenance footer in item 5 is off by default, but **when the provenance footer is opted in** learning must keep it last and never drop it. Announce which shape you took, so a deliberately terse draft is never mistaken for a truncated one.

### When no convention was found (rung 3 — invent nothing)

**Title:** there is no house shape to fall back on, so do not introduce one — no bracket convention, no casing rule, no marker, no prefix nobody in this repo has used. Write a concise one-line summary of the change. Where a ticket exists, include its reference in the form the **tracker adapter** yields (Jira: the key; GitHub Issues: `#<n>`), placed wherever it reads naturally. With no ticket, the title is the summary alone.
- Two or more *different* ticket ids means ask which, rather than silently taking the first.

**Description — what to include, which is not the same as a shape to copy:**
1. **Ticket link** — built by the **tracker adapter**: for Jira, `https://<jira_base_url>/browse/<KEY>` (uppercase key); for GitHub Issues, `#<n>` (GitHub auto-links a same-repo issue). First line, for the mechanical reason that the platform auto-links it there — not because any repo was observed doing it. Omit the line entirely when there is no ticket.
2. **Summary** — one or two sentences.
3. **What the change does** — in plain prose, as short as the change allows. Reach for a bullet per discrete change only when there genuinely are several and prose would obscure them; a one-part change gets a sentence, not a one-item list. Either way, describe intent and omit file / class / method / path identifiers — do not paste the diff. This is the *content* required of any description; it is not a layout, and with no sample to copy there is no layout to apply.
4. **A short ASCII diagram, wrapped in a fenced code block (optional)** — include one only when a picture lets the reviewer grasp the change faster than prose; otherwise leave it out — and leave it out outright when the layout learned for this target is terser than the default, since a diagram in a one-line PR is noise. When you do: a real monospace structure diagram (boxes / arrows, or a small tree / table — never prose dressed up as a diagram), kept high-level, wrapped in a triple-backtick fence, drawn with **plain ASCII glyphs** (`+ - | > v`), **not Mermaid**; split any wide or complex diagram into smaller ones rather than forcing one unreadable block. Full drawing guidance, the fence/encoding rationale, and an illustrative shape: `resources/diagram-guidance.md`.
5. **AI-provenance markers (opt-in — off by default)** — the footer (a `---` divider, then `🤖 _Drafted with Claude Code._`) and the `ai-assisted` label applied in Step 4 are added **only when the invoking request explicitly asks to mark / label / flag the PR as AI-assisted** (or passes an explicit opt-in). Absent that phrasing — including every automated `resolve-issue` pipeline call, which carries no such phrasing — **add neither**. Announce the decision on the same line as the platform / tracker / learning outcome (`provenance: off (say "mark as AI-assisted" to add)`, or `provenance: on (footer + best-effort label)`) so a silently dropped marker is impossible. When opted in the footer is the **last** element on every path — append it after the learned-convention body and never let learning drop or reorder it — and it renders identically on Azure DevOps and GitHub, the portable marker; the label is the platform-native badge alongside it (best-effort — see Step 4). If a team ever needs mandatory AI disclosure for audit, reintroduce it then as a config flag — deliberately not built now.

**On every path:** the title and description are in **English**. Do **not** add a git `Co-Authored-By` trailer of your own — it is a commit concern, not a PR-description one, and whether this repo wants one is the repo's call, observable from its own history (`git log -n 50 --format=%b | grep -c '^Co-Authored-By'`) rather than something this skill decides. Default to not adding it; if the repo's commits routinely carry it, follow that instead of overriding it. The AI-provenance footer and the `ai-assisted` label are a different thing and are **off by default** — added only on the explicit opt-in described in Step 3 (footer) and applied in Step 4 (label) — and are never the forbidden trailer.

## Step 4 — Present, confirm, create

Show the drafted title and description and let the user edit them. Then:

- **Standalone:** create only after the user explicitly confirms. If the source branch is not yet on the remote, publish it first (`git push -u origin <branch>`), then create the PR via the **backend adapter's create recipe** — writing the full description to a temp file and passing it as the adapter's body-file flag, never as an inline string. The adapter documents the platform's file-encoding traps (e.g. Azure DevOps's `az.cmd` cp1252/UTF-8 `@<file>` quirks) and — **only when provenance is opted in (Step 3)** — how the `ai-assisted` label is applied (Azure DevOps creates the tag inline via `--labels`; GitHub adds it *after* create with `gh pr edit --add-label`, because `gh pr create --label` aborts if the label does not exist). When opted in the label is best-effort either way (see Voiced limits); by default no label is applied. Return the PR URL.
- **Cannot get a confirmation** (running non-interactively, or inside a subagent that cannot prompt): **do not push the branch and do not create the PR.** Print the prepared title and description for the user to create manually, and say so. Do not use an open-in-browser flag (e.g. Azure DevOps `--open`) in a non-interactive context. When provenance was opted in, the printed description already carries the footer; tell the user to add the `ai-assisted` label when they create the PR. By default (no opt-in) neither marker is printed or mentioned.

The invariant: **never publish the branch or open a PR without an explicit human confirmation** — both are outward-facing.

## Safety rails

- Never resolve merge conflicts automatically — stop and report them.
- Never delete branches.
- Never force-push without an explicit request.

## Voiced limits

- If the detected platform's PR tool is missing or unauthenticated (see each backend adapter's precondition — e.g. `az` + the `azure-devops` extension for Azure DevOps, `gh` authed for GitHub), say so and print the prepared title and description for manual creation — do not fail silently.
- Target detection is best-effort by design, not by omission: git cannot say which branch this one was cut from, so a target nobody named defaults to the repo's default branch. Name the target you used on every run, and ask whenever it is not obvious — a wrong target is silent everywhere else in this flow.
- Learned convention is best-effort: where the sampled PRs have empty or template-only bodies, the title shape is still learnable from their subjects while the body shape is not, so say which half was learned rather than implying both were.
- Provenance markers are **off by default** — no footer and no label unless the invoking request explicitly opts in (Step 3, item 5). When opted in, the `ai-assisted` label is best-effort: if the platform rejects it (an org that disallows ad-hoc PR tags on Azure DevOps, or a label that does not yet exist on GitHub), drop the label, create the PR with the footer alone (the opted-in marker), and say so — the backend adapter documents the per-platform behaviour.
