---
name: open-pr
description: >
  Open a pull request (Azure DevOps or GitHub) for the current branch,
  giving it a title and description that follow the CALLER's own conventions —
  learned at runtime from their past merged PRs —
  with a ticket link, a concise summary, and a bulleted what/why.
  Use whenever someone wants to open / raise / put up a PR, finish a branch,
  or send changes for review on Azure DevOps or GitHub, even if they don't say "open-pr".
  The convention is learned per target branch,
  so a PR onto a maintenance or release line follows that line's own convention.
  It always shows the title and description for confirmation first
  and never creates the PR without explicit approval.
  Trigger phrases: "open a PR", "raise a PR", "create a pull request",
  "put this up for review", "PR this branch", "open-pr", "/open-pr".
  Do NOT trigger for: reviewing or summarizing an existing PR;
  triaging or replying to PR comments (that is a separate resolve-pr-comments skill);
  completing / merging a PR; starting a branch; or plain git operations.
  This is the team-agnostic open-pr skill for the issue-to-PR workflow.
---

# Open PR

Open a pull request for the current branch on the detected PR platform (Azure DevOps or GitHub). The title and description are drafted to match **the conventions of the PRs that already landed on this target branch** — the caller's own first — rather than a fixed house style, then shown for confirmation. The PR is **never created without explicit approval** — opening a PR is an outward-facing action.

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

- **Read the repo's own default branch; never assume one.** `git symbolic-ref --short refs/remotes/origin/HEAD` yields `origin/<branch>` — strip the prefix. That ref is written by `git clone`, so a remote built by `git init` + `git fetch` can lack it; then ask the remote directly with `git ls-remote --symref origin HEAD`, which is read-only and changes no local state.
- Only when neither resolves, fall back to whichever of `main` / `master` the remote actually has — and if **both** exist, ask. A repo part-way through a rename keeps the old one as a stale branch, so choosing silently would base the PR on the wrong target, which also invalidates Step 2's ahead-count and the history Step 3 learns the caller's convention from.
- **The target need not be the default branch, and its name never changes the format.** An explicitly given target is used as-is; a maintenance or release line is an ordinary target. Do not pattern-match a branch name into a special description shape — Step 3 learns the shape from the PRs that actually landed on that target, so a line whose PRs are terse produces a terse PR without any rule here saying so.
- If the correct target is genuinely ambiguous, ask rather than guess.

## Step 2 — Preconditions (stop and report if any fails)

Run these before drafting anything, because each is a common first-run blocker:

- **Has commits to PR.** The branch must be ahead of the target: `git fetch`, then `git rev-list --count origin/<target>..HEAD` must be greater than 0.
- **On the remote — publish if needed.** Creating the PR needs the source branch on the remote. A not-yet-pushed branch is **not** a stop: after confirmation, open-pr publishes it (`git push -u origin <branch>`) as part of the create in Step 4. (Running non-interactively it does not push and does not create — see Step 4.)
- **No duplicate.** Check for an existing open PR for this source to target via the **backend adapter's dup-check recipe**. If one exists, **stop and point the user to it** — do not open a second PR, and do not modify the existing one here.

## Step 3 — Learn the convention for this target, then draft

Identify the caller from `git config user.email` (preferred) and `user.name`, then sample past merged PRs **that targeted this same branch**, via the **backend adapter's merged-PRs-by-target recipe** — scoping the sample to the target is what makes the learned convention that target's own rather than the default branch's. Widen only as far as needed, stopping at the first rung that yields a sample: (1) the caller's merged PRs into this target; (2) any author's merged PRs into this target — on a shared maintenance line the convention belongs to the line, not to one person; (3) the caller's merged PRs anywhere in this repo (`git log --author="<email or name>"`, trying both forms); (4) nothing at all — use the default shape below. Never skip a rung to reach a bigger sample: one PR that landed on this target outranks twenty that landed elsewhere. From the sample, infer **title casing** and **description layout** by majority — newest breaks a tie, a single prior PR is used directly. Announce the target, the rung, and the count (`learned from K of your past PRs into release/2.5`, `no PRs into release/2.5 -> learned from your PRs repo-wide`, or `no matching history -> using default`), so a silent wrong guess is impossible.

Learning covers **how this repo, this target, and this caller write things**, not just typography: title casing, description layout (sectioned, a flat bullet list, or a deliberately terse form such as a bare cross-reference to an originating PR), **and the title's ticket-prefix shape** — bracketed (`[acme-123] …`), bare (`acme-123 …`), a Conventional Commits type (`fix(scope): …`), or no prefix at all. Read the shape off the same sample; if the observed PRs carry no ticket prefix, **do not add one**. The defaults below are what to use when there is no history to learn from, never a format to impose on a repo — or a branch — that visibly does something else.

**What learning may and may not change.** The **ticket link is mandatory** on every path — it is mechanical, and the platform auto-links it — and the description must never come out empty or contentless. Everything below it is the *default* shape rather than a floor: where the sample for this target consistently writes something terser than a summary plus bullets, reproduce that instead of padding it back up to the default. A maintenance line whose PRs carry only a link to the originating PR is a convention to honour, not a gap to fill. The diagram in item 4 is optional, and the provenance footer in item 5 is off by default, but **when the provenance footer is opted in** learning must keep it last and never drop it. Announce which shape you took, so a deliberately terse draft is never mistaken for a truncated one. Do not bias the learning to this repository if it is single-author — the convention that matters is the caller's, on this target, in whatever repo the skill runs in.

### Default format (the fallback; the learned convention overrides it — layout as well as presentation)

**Title:** derive the ticket id and its casing from the **tracker adapter**:
- **Jira tracker:** `[acme-xxxxx] <concise one-line summary>` — the bracketed, lowercased key (the adapter also yields the uppercase form for the URL).
- **GitHub Issues tracker:** `#<n> <concise one-line summary>` — the `#<n>` reference in place of the bracket form.
- No ticket found: omit the ticket line, and title it the way this repo titles ticket-less PRs. `ad-hoc <summary>` is the fallback **only when the history in Step 3 gave you nothing to copy** — it is one team's marker, not a convention to introduce into a repo that has never used it. A plain `<summary>` is the safer default.
- Two or more *different* ticket ids means ask which, rather than silently taking the first.

**Description (the default shape):**
1. **Ticket link** — built by the **tracker adapter**: for Jira, `https://<jira_base_url>/browse/<KEY>` (uppercase key); for GitHub Issues, `#<n>` (GitHub auto-links a same-repo issue). This is the **first line** so the platform auto-links it; omit the whole line only when there is no ticket.
2. **Summary** — one or two sentences.
3. **Description** — a bullet list, one bullet per discrete change as *action plus brief why/impact*. Omit file / class / method / path identifiers — describe intent, do not paste the diff.
4. **A short ASCII diagram, wrapped in a fenced code block (optional)** — include one only when a picture lets the reviewer grasp the change faster than prose; otherwise leave it out. When you do: a real monospace structure diagram (boxes / arrows, or a small tree / table — never prose dressed up as a diagram), kept high-level, wrapped in a triple-backtick fence, drawn with **plain ASCII glyphs** (`+ - | > v`), **not Mermaid**; split any wide or complex diagram into smaller ones rather than forcing one unreadable block. Full drawing guidance, the fence/encoding rationale, and an illustrative shape: `resources/diagram-guidance.md`.
5. **AI-provenance markers (opt-in — off by default)** — the footer (a `---` divider, then `🤖 _Drafted with Claude Code._`) and the `ai-assisted` label applied in Step 4 are added **only when the invoking request explicitly asks to mark / label / flag the PR as AI-assisted** (or passes an explicit opt-in). Absent that phrasing — including every automated `resolve-issue` pipeline call, which carries no such phrasing — **add neither**. Announce the decision on the same line as the platform / tracker / learning outcome (`provenance: off (say "mark as AI-assisted" to add)`, or `provenance: on (footer + best-effort label)`) so a silently dropped marker is impossible. When opted in the footer is the **last** element on every path — append it after the learned-convention body and never let learning drop or reorder it — and it renders identically on Azure DevOps and GitHub, the portable marker; the label is the platform-native badge alongside it (best-effort — see Step 4). If a team ever needs mandatory AI disclosure for audit, reintroduce it then as a config flag — deliberately not built now.

**When the layout learned for this target cross-references an originating PR** — the usual shape on a maintenance or release line, where the substantive review already happened on the original PR — reproduce that instead of the default above, and only because the sample showed it:
- Keep the ticket link, then the cross-reference written the way those PRs write it, with the **backend adapter** supplying the platform's PR-link syntax (Azure DevOps `!<pr_number>`, GitHub `#<pr_number>` — both render as a link to that PR), then — **only when provenance is opted in (Step 3, item 5)** — the AI-provenance footer (`---` + `🤖 _Drafted with Claude Code._`). Whatever title marker those PRs carry is learned from them too; do not add a marker they do not use.
- Resolve the originating PR from the branch before asking: `git log --format=%b origin/<target>..HEAD` carries a `cherry picked from commit <sha>` trailer whenever the pick used `git cherry-pick -x`, and that commit's PR is the answer. Confirm it with the user, and ask outright only when no trailer is there. Reuse that PR's one-line summary for `<summary>`.

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
- Learned convention is best-effort: if a squash workflow left no description body, casing still comes from the commit subject and the layout falls back to the default — announced, not silent.
- Provenance markers are **off by default** — no footer and no label unless the invoking request explicitly opts in (Step 3, item 5). When opted in, the `ai-assisted` label is best-effort: if the platform rejects it (an org that disallows ad-hoc PR tags on Azure DevOps, or a label that does not yet exist on GitHub), drop the label, create the PR with the footer alone (the opted-in marker), and say so — the backend adapter documents the per-platform behaviour.
