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
  The target branch is taken from the request, or defaults to the repo's own default branch.
  Presentation is learned from previous PRs; substance is learned only where they have some,
  so a repo whose PRs carry no real description still gets one that does.
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
  - host **is** `dev.azure.com`, or **ends with** `.visualstudio.com` → **Azure DevOps** (`resources/backends/azure-devops.md`).
  - host **is** `github.com`, or **ends with** `.github.com` → **GitHub** (`resources/backends/github.md`).
  - **Match the end of the host, never a substring** — `github.company.com` contains `github.com` and is not it.
  - Any other host may still be a **GitHub Enterprise** server, whose hostname is arbitrary and cannot be recognised by name. Ask `gh` instead of guessing: `gh auth status --hostname <host>` exiting 0 means the user has configured that host, which identifies it as a GitHub-family server — use the GitHub adapter. If it does not, voice the limit and ask which platform to target.
- **Issue tracker (precedence — first match wins):**
  1. **Infer** the type from an existing ticket ref, matched **case-sensitively**: `[A-Z][A-Z0-9]+-\d+` → **Jira** (either platform). Case matters here more than it looks: read case-insensitively the same pattern swallows ordinary branch names (`patch-1`, `electron-41-eol`, `esbuild-0.28.2`) and invents a ticket key out of a slug, which then sends the run asking for a tracker instance that has nothing to do with the change; a bare numeric issue ref → **GitHub Issues** — but only on a **GitHub** remote (on Azure DevOps `#<n>` is a work-item link, not a GitHub issue, so a bare number does not imply GitHub Issues there).
  2. else **default only where the platform supplies the tracker**: a GitHub remote → **GitHub Issues**, which is same-repo and needs no configuration. An Azure DevOps remote gets **no default** — its native tracker is Azure Boards work items, no adapter ships for those, and assuming Jira instead would send the run asking for a Jira instance the team may not have. Ask which tracker to use, or produce no tracker line.
  3. No ticket at all → produce no tracker line (same as today).
  - Jira → `resources/trackers/jira.md`; GitHub Issues → `resources/trackers/github-issues.md`. The Jira adapter resolves its own base URL — `.claude/pr-lifecycle.json`, the Atlassian MCP, or a one-time prompt — so that lookup is not a step here.
- **Announce** the detected platform and tracker so a silent wrong guess is impossible.

**Resolve the plugin root first, and stop if you cannot.** Every adapter this skill reads lives under the plugin root, at `resources/backends/` and `resources/trackers/` — never under the skill directory, and never at a path containing `plugins/pr-lifecycle/`, which exists only in this marketplace's own source tree and not in an install. Resolve that root the way this Claude Code build exposes it (`${CLAUDE_PLUGIN_ROOT}` where available, otherwise the directory holding this skill's plugin manifest), and read one adapter to confirm the resolution before going further.

**If the adapters cannot be read, stop and say so — do not continue unadapted.** The whole platform-specific half of this skill lives in them: how a sample is obtained, how a duplicate is detected, how the pull request is created, how a ticket reference is built. Without them there is no sample to learn from and no create recipe, so proceeding produces either a wrong pull request or an invented one. Report which path failed and let the human point you at the plugin, the same way Step 4 prints a prepared draft rather than guessing when it cannot get a confirmation.

Then load the matching backend and tracker adapters and run the platform/tracker-specific parts of the steps below through them. The **only** backend seam in this body is recognising the remote string to *select* the adapter — no field access beyond that.

## Step 1 — Detect the target branch

- **Git cannot tell you which branch this one was cut from, so do not try to work it out.** There is no field for it: before the first push there is no upstream, and after `git push -u` the upstream is this branch's *own* remote copy; the reflog says only `branch: Created from HEAD`, names no branch, is local, and expires. Reconstructing it from topology fails on ordinary cases rather than exotic ones — a branch already on the remote scores as its own parent, and merging the base in before opening the PR reverses the ranking. What follows is a default plus two ways for a human to name something else, not a derivation.
- **Take the target from the request or the session whenever either names it.** "backport this to v2-maintenance"; the branch this one was checked out from earlier in this same session; a branch name that spells the line out. Each is the human telling you the target. Note which end a signal points at: a cherry-pick names the commit's **source**, which on a backport is the branch you are porting *from* — the target is in the checkout, not the pick.
- **Otherwise default to the repo's own default branch, and ask the remote for it.** `git ls-remote --symref origin HEAD` reports it directly, is read-only, and cannot be stale. The local `refs/remotes/origin/HEAD` is a weaker source: whether `git fetch` maintains it depends on the client's `remote.<name>.followRemoteHEAD` setting, so it may be absent, stale, or silently updated mid-run — use it only as a cross-check. **Do not guess a name.** A default branch is often neither `main` nor `master` (a version number and a word like `dev` are both common), so if the remote does not answer, ask rather than trying candidates — and note that asking a platform API whether a branch exists can answer *yes* for a renamed one, because the rename redirect follows. Both PR platforms default the base to this same branch when none is given, so it is the least surprising answer rather than a guess dressed up as one.
- **Announce the target and where it came from** — `target: <branch> (from your request)`, `target: <branch> (repo default)` — and **ask rather than guess** whenever the request names two candidates, or names none and the remote could not tell you the default. Everything downstream is silent about a wrong target: Step 2's ahead-count still passes against the wrong base, and the PR simply opens against it.
- **When that ask cannot be reached** — running non-interactively, or inside a subagent that cannot prompt — do **not** fall through to the default as though it had been chosen. Say `target: <branch> (repo default, unconfirmed — could not ask)` and treat it as a voiced limit, the same way Step 4 treats a confirmation it cannot obtain.
- **A branch name never changes the format.** A maintenance or release line is an ordinary target. Step 3 reads its sample from the repo's previous pull requests, not from the target, so the target decides where the PR lands and nothing else.

## Step 2 — Preconditions (stop and report if any fails)

Run these before drafting anything, because each is a common first-run blocker:

- **Has commits to PR.** The branch must be ahead of the target: `git fetch`, then `git rev-list --count origin/<target>..HEAD` must be greater than 0.
- **On the remote — publish if needed.** Creating the PR needs the source branch on the remote. A not-yet-pushed branch is **not** a stop: after confirmation, open-pr publishes it (`git push -u origin <branch>`) as part of the create in Step 4. (Running non-interactively it does not push and does not create — see Step 4.)
- **No duplicate.** Check for an existing open PR **from this source branch** via the **backend adapter's dup-check recipe** — by source alone, never narrowed to the target, since a target that defaulted wrongly hides the very PR this check exists to find. One to the **same** target is a duplicate: **stop and point the user to it** — do not open a second PR, and do not modify the existing one here. One to a **different** target is not automatically a duplicate — the same branch can legitimately go to both a release line and the default branch — so show it, name the target it goes to, and ask before creating another.

## Step 3 — Learn from previous pull requests, then draft

**This skill ships no title or description shape.** How a pull request looks in this repo is read off ones that already merged, in this order — take the first that yields more than a couple:

1. **the caller's own previous PRs** — their style is the one to match, since it is their pull request;
2. **anyone's**, when the caller has too few here for a pattern to be visible.

If neither yields anything, no convention is known: draft plainly (below) and say so.

**The backend adapter supplies the sample.** Where it comes from differs by platform, for reasons the adapter documents — so ask the adapter rather than assuming git holds it.

**Identify the caller loosely, and expect the match to be imprecise.** One person appears under more than one display name in a single repo (`Surname, First` alongside `First Surname`), and the name the platform recorded is routinely not the one in `git config`. So match a distinctive *token* — a surname, a handle — rather than a whole name or address, and match it case-insensitively. Two cautions. On some platforms that filter is a regular expression, so a token containing `[`, `.`, `+` or `(` either aborts the read outright or silently widens it: pick a token without them rather than escaping. And if the sample plainly contains more than one person, widen to the second probe rather than learning a stranger's style.

### Presentation is learned — all of it

Reproduce what the sample does, and introduce nothing it does not do.

- **The title's shape, whatever that is** — a ticket reference in brackets, bare with a colon, a Conventional Commits type, a component or subsystem tag in brackets, or no prefix at all. Where the sampled titles carry no ticket reference, do not introduce one — and look for where the sample *does* put one, since a repo that keeps ticket references out of its titles often has a dedicated slot for them in the body.
- **The body's shape** — prose, bullets, a heading structure, a filled-in template, a bare reference to the PR a change was ported from. Where the sampled bodies share a heading structure, reproduce it, dropping only what is not content: the template's own instruction comments, and any heading left blank across most of the sample. Never copy a checkbox's state, and never carry over a provenance footer some earlier run left behind.
- **The language the sample is written in.** A repo whose pull requests are written in the maintainers' language gets one written in that language.

### Substance is learned only where the sample has some

One question decides it: **does that body, on its own, tell a reviewer what changed — without following a link?**

- **Where it does, match it, length included.** A complete two-line description is a convention, not a shortfall. Do not inflate it, and do not promote plain prose to headings or bullets because those look more thorough.
- **Where it does not** — an empty body, or a bare cross-reference with no account of the change — the sample has nothing to teach here, and matching it would make this skill pointless: writing the description is the work it exists to do. So write one that passes the test, in the presentation the sample taught, and **say that you overrode the sample on substance**.

Substance is the one element the sample gets no vote on. Keep it proportionate all the same: a one-line change earns a sentence, not a manufactured list.

**Where the change has a shape, draw it.** Some changes are a sentence — a value, a threshold, a rename. Others are structural: work moves between components, a sequence reorders, a control path is replaced, one thing becomes two. For those a small diagram carries in a glance what a paragraph carries slowly, and readers skim a long description however well it is written. So include one when the change has that kind of shape, and leave it out when it does not — a diagram of a one-line change is noise, and putting one on every description destroys the signal that a diagram is worth stopping for.

This is the one element the sample cannot teach in either direction. Almost no repository's pull requests carry a diagram, so their absence is not evidence that one would not help here — it sits on the substance side for the same reason the description does: it is how the reader understands the change, not how the repository dresses it up. Keep it high-level, showing the shape of the change rather than redrawing the diff, and take the form that renders on this platform from the **backend adapter**.

**Announce the probe, the sample size, and the shape you took** — plainly, and without invented precision: `learned from 12 of your previous PRs: bare ticket reference with a colon, two-line prose body`. Where you overrode the sample's substance, say so on the same line. State only what you actually observed; a fraction nobody counted is worse than no fraction, because it invites the reader not to check. This announcement is the only place a convention that is really one person's habit becomes visible.

**An empty sample and a failed query are different, and only one means "no history".** A query can come back empty because the filter was wrong — a mis-picked identity token, an unknown branch — and on some platforms that looks identical to genuine absence. Confirm the query ran before reading emptiness as history; when it did not, name what failed and degrade with an announcement, never silently.

### When nothing was learned

**Title** — a concise one-line summary of the change, introducing no prefix, no bracket, no marker, and no casing rule. Where a ticket exists, include its reference in the form the **tracker adapter** yields, wherever it reads naturally. Two or more *different* ticket ids means ask which, rather than silently taking the first.

**Description** — the ticket link when there is a ticket (the **tracker adapter** builds it), then what the change does and why, in plain prose as short as the change allows. Describe intent, omit file and symbol names, and do not paste the diff. That is the content any description owes a reviewer; it is not a layout, and with no sample there is no layout to apply.

**AI-provenance markers are opt-in and off by default.** Add the footer (a `---` divider, then `🤖 _Drafted with Claude Code._`) and the `ai-assisted` label of Step 4 **only when the invoking request explicitly asks to mark the pull request as AI-assisted**. Absent that, add neither, and say which way it went so a dropped marker is never silent. When opted in, the footer is the last element and learning never drops or reorders it.


## Step 4 — Present, confirm, create

Show the drafted title and description and let the user edit them. Where the draft carries a diagram, add one line saying it can be dropped or redrawn — it is the element most likely to be wanted differently, and the reader cannot edit what they do not know is optional. Then:

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
- Learned convention is best-effort, and the two halves fail separately: a sample can teach a title shape while teaching nothing about a body. Say which half you learned rather than implying both.
- Provenance markers are **off by default** — no footer and no label unless the invoking request explicitly opts in (Step 3). When opted in, the `ai-assisted` label is best-effort: if the platform rejects it (an org that disallows ad-hoc PR tags on Azure DevOps, or a label that does not yet exist on GitHub), drop the label, create the PR with the footer alone (the opted-in marker), and say so — the backend adapter documents the per-platform behaviour.
