---
name: open-pr
description: >
  Open a pull request (Azure DevOps or GitHub) for the current branch,
  giving it a title and description that follow the CALLER's own conventions —
  learned at runtime from their past merged PRs —
  with a ticket link, a concise summary, and a bulleted what/why.
  Use whenever someone wants to open / raise / put up a PR, finish a branch,
  or send changes for review on Azure DevOps or GitHub, even if they don't say "open-pr".
  Handles both a standard PR (to master / main) and a backport (to a release/* branch).
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

Open a pull request for the current branch on the detected PR platform (Azure DevOps or GitHub). The title and description are drafted to match **the calling user's own past-PR conventions** rather than a fixed house style, then shown for confirmation. The PR is **never created without explicit approval** — opening a PR is an outward-facing action.

This skill is backend-agnostic: the platform-specific mechanics (create PR, dup-check, label, backport link) live in **backend adapter reference docs** under `resources/backends/`, and the ticket-link mechanics live in **tracker adapter reference docs** under `resources/trackers/`. The skill body detects platform and tracker, loads the matching adapters, and follows their recipes — it holds **no `az`/`gh`-specific field parsing and no tracker-specific id/URL parsing** of its own. It borrows the safety rails of a PR-creation flow but is deliberately narrower: it opens a PR for the branch **as it is** — publishing it to the remote first if it is not there yet, since the PR needs it. It does not merge the base branch in, does not delete branches, and does not triage review comments (that is `resolve-pr-comments`).

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

- Default to `master`, else `main`.
- If the current branch targets a release line (e.g. `release/2.5`), treat it as a **backport** (see the backport format below).
- If the correct target is genuinely ambiguous, ask rather than guess.

## Step 2 — Preconditions (stop and report if any fails)

Run these before drafting anything, because each is a common first-run blocker:

- **Has commits to PR.** The branch must be ahead of the target: `git fetch`, then `git rev-list --count origin/<target>..HEAD` must be greater than 0.
- **On the remote — publish if needed.** Creating the PR needs the source branch on the remote. A not-yet-pushed branch is **not** a stop: after confirmation, open-pr publishes it (`git push -u origin <branch>`) as part of the create in Step 4. (Running non-interactively it does not push and does not create — see Step 4.)
- **No duplicate.** Check for an existing open PR for this source to target via the **backend adapter's dup-check recipe**. If one exists, **stop and point the user to it** — do not open a second PR, and do not modify the existing one here.

## Step 3 — Learn the caller's convention, then draft

Identify the caller from `git config user.email` (preferred) and `user.name`, then read their recent merged PRs in this repo: `git log <target> --author="<email or name>"` (try both forms; treat it as "no history" only when both return nothing). From the last several, infer **title casing** and **description layout** (sectioned vs a flat bullet list) by majority — newest by commit date breaks a tie, a single prior PR is used directly. Announce the outcome (`learned from K of your past PRs` or `no matching history -> using default`), so a silent wrong guess is impossible.

Learning adjusts **presentation only** (casing, section wording, sectioned-vs-flat). It must never drop or reorder the **mandatory content** below — the ticket link, summary, and bullets; the diagram in item 4 is optional, and the provenance footer in item 5 is off by default, but **when the provenance footer is opted in** learning must keep it last and never drop it. Do not bias the learning to this repository if it is single-author — the convention that matters is the caller's, in whatever repo the skill runs in.

### Default format (the fallback; the caller's learned convention overrides presentation)

**Title:** derive the ticket id and its casing from the **tracker adapter**:
- **Jira tracker:** `[acme-xxxxx] <concise one-line summary>` — the bracketed, lowercased key (the adapter also yields the uppercase form for the URL).
- **GitHub Issues tracker:** `#<n> <concise one-line summary>` — the `#<n>` reference in place of the bracket form.
- No ticket found means use `ad-hoc <summary>` and omit the ticket line. Two or more *different* ticket ids means ask which, rather than silently taking the first.

**Description (standard PR):**
1. **Ticket link** — built by the **tracker adapter**: for Jira, `https://<jira_base_url>/browse/<KEY>` (uppercase key); for GitHub Issues, `#<n>` (GitHub auto-links a same-repo issue). This is the **first line** so the platform auto-links it; omit the whole line only when there is no ticket.
2. **Summary** — one or two sentences.
3. **Description** — a bullet list, one bullet per discrete change as *action plus brief why/impact*. Omit file / class / method / path identifiers — describe intent, do not paste the diff.
4. **A short ASCII diagram, wrapped in a fenced code block (optional)** — include one only when a picture lets the reviewer grasp the change faster than prose; otherwise leave it out. When you do: a real monospace structure diagram (boxes / arrows, or a small tree / table — never prose dressed up as a diagram), kept high-level, wrapped in a triple-backtick fence, drawn with **plain ASCII glyphs** (`+ - | > v`), **not Mermaid**; split any wide or complex diagram into smaller ones rather than forcing one unreadable block. Full drawing guidance, the fence/encoding rationale, and an illustrative shape: `resources/diagram-guidance.md`.
5. **AI-provenance markers (opt-in — off by default)** — the footer (a `---` divider, then `🤖 _Drafted with Claude Code._`) and the `ai-assisted` label applied in Step 4 are added **only when the invoking request explicitly asks to mark / label / flag the PR as AI-assisted** (or passes an explicit opt-in). Absent that phrasing — including every automated `resolve-issue` pipeline call, which carries no such phrasing — **add neither**. Announce the decision on the same line as the platform / tracker / learning outcome (`provenance: off (say "mark as AI-assisted" to add)`, or `provenance: on (footer + best-effort label)`) so a silently dropped marker is impossible. When opted in the footer is the **last** element on every path — append it after the learned-convention body and never let learning drop or reorder it — and it renders identically on Azure DevOps and GitHub, the portable marker; the label is the platform-native badge alongside it (best-effort — see Step 4). If a team ever needs mandatory AI disclosure for audit, reintroduce it then as a config flag — deliberately not built now.

**Backport (target is `release/*`):**
- Title (Jira tracker): `[acme-xxxxx] [release] <summary>`; (GitHub Issues tracker): `#<n> [release] <summary>`.
- Description is the ticket link, then `cherry pick from <PR-link>` where the **backend adapter** supplies the PR-link syntax (Azure DevOps `!<pr_number>`, GitHub `#<pr_number>` — both render as a link to that PR), then — **only when provenance is opted in (Step 3, item 5)** — the AI-provenance footer (`---` + `🤖 _Drafted with Claude Code._`). No summary block, bullets, or diagram — the real review happened on the original PR.
- Ask the user for (or accept as input) the **source PR number** it was cherry-picked from, and reuse that PR's one-line summary for `<summary>`. A backport learns only the title casing, not the description layout.

**On every path (including the backport):** the title and description are in **English**. Do **not** add a git `Co-Authored-By` trailer — that is forbidden team-wide and is a commit concern, not a PR-description one. The AI-provenance footer and the `ai-assisted` label are a different thing and are **off by default** — added only on the explicit opt-in described in Step 3 (footer) and applied in Step 4 (label) — and are never the forbidden trailer.

## Step 4 — Present, confirm, create

Show the drafted title and description and let the user edit them. Then:

- **Standalone:** create only after the user explicitly confirms. If the source branch is not yet on the remote, publish it first (`git push -u origin <branch>`), then create the PR via the **backend adapter's create recipe** — writing the full description to a temp file and passing it as the adapter's body-file flag, never as an inline string. The adapter documents the platform's file-encoding traps (e.g. Azure DevOps's `az.cmd` cp1252/UTF-8 `@<file>` quirks) and — **only when provenance is opted in (Step 3)** — how the `ai-assisted` label is applied (Azure DevOps creates the tag inline via `--labels`; GitHub adds it *after* create with `gh pr edit --add-label`, because `gh pr create --label` aborts if the label does not exist). When opted in the label is best-effort either way (see Voiced limits); by default no label is applied. Return the PR URL.
- **Cannot get a confirmation** (running non-interactively, or inside a subagent that cannot prompt): **do not push the branch and do not create the PR.** Print the prepared title and description for the user to create manually, and say so. When provenance was opted in, the printed description already carries the footer; tell the user to add the `ai-assisted` label when they create the PR. By default (no opt-in) neither marker is printed or mentioned.

The invariant: **never publish the branch or open a PR without an explicit human confirmation** — both are outward-facing.

## Safety rails

- Never resolve merge conflicts automatically — stop and report them.
- Never delete branches.
- Never force-push without an explicit request.

## Voiced limits

- If the detected platform's PR tool is missing or unauthenticated (see each backend adapter's precondition — e.g. `az` + the `azure-devops` extension for Azure DevOps, `gh` authed for GitHub), say so and print the prepared title and description for manual creation — do not fail silently.
- Learned convention is best-effort: if a squash workflow left no description body, casing still comes from the commit subject and the layout falls back to the default — announced, not silent.
- Provenance markers are **off by default** — no footer and no label unless the invoking request explicitly opts in (Step 3, item 5). When opted in, the `ai-assisted` label is best-effort: if the platform rejects it (an org that disallows ad-hoc PR tags on Azure DevOps, or a label that does not yet exist on GitHub), drop the label, create the PR with the footer alone (the opted-in marker), and say so — the backend adapter documents the per-platform behaviour.
