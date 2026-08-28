---
name: resolve-pr-comments
description: >
  Resolve the review comments on an existing Azure DevOps or GitHub pull request:
  fetch the PR's comment threads, triage each one, draft the code fixes and replies,
  and — after a single human confirmation — commit, push, reply, and update thread status.
  Use whenever someone wants to address, resolve, handle, action, or reply to PR comments
  or review feedback, fix the comments on a PR, or "go through the comments on PR <id>",
  even if they don't say "resolve-pr-comments". Takes the PR id as an argument or from natural language.
  It respects the reviewer — it triages and drafts, and never auto-dismisses a comment —
  and it makes no outward change (commit, push, reply, resolve) without explicit confirmation.
  Do NOT trigger for: opening or creating a PR (that is open-pr); summarizing or reviewing a PR's diff;
  reviewing a plan or code risk; or merging / completing a PR.
  This skill actually acts on the comments (commit, push, reply, resolve) —
  it does not merely read and summarize them.
  Trigger phrases: "resolve PR comments", "address the review comments", "fix the comments on PR 12345",
  "handle the PR feedback", "reply to the PR comments", "/resolve-pr-comments".
---

# Resolve PR comments

Work through the review comments on an existing Azure DevOps or GitHub pull request and bring each one to a disposition — a code fix, a reply, an explanation, an intentional skip, or a hand-off. Everything up to the gate is read-only or local-only: comments are fetched, triaged, and the fixes and replies are drafted, but **no outward change happens until a single human confirmation**. Acting on a reviewer's words is people-facing and hard to retract, so the bar is the same one `open-pr` holds for creating a PR: never commit, push, reply, or resolve a thread without explicit approval.

This skill respects the reviewer. It triages and drafts; it does not sit in judgement of whether a human reviewer was right, and it never silently dismisses a comment. Where a comment looks like a false positive (a tool flag that does not apply), it drafts an explanation for the human to send or edit — it does not decide the reviewer was wrong on its own.

This skill **acts on** the feedback — it does not merely read and summarize. It is backend-agnostic: the platform-specific mechanics (identity check, fetch + normalize threads, post reply, set thread status) live in **backend adapter reference docs** under `resources/backends/`. The skill body detects the platform, loads the matching adapter, and works only on the **normalized thread/comment model** the adapter produces — it holds **no `az`/`gh`-specific field parsing** of its own. Its filtering and all of its write paths are its own, expressed over that normalized model.

## Step 0 — Detect the platform, load the backend adapter, announce

Before anything else, resolve which backend this run targets, from `git remote get-url origin`:

**Extract the host before matching anything.** Use `git remote get-url` rather than the raw `remote.origin.url` config, since it expands an `insteadOf` alias to the real URL. What comes back is still often not a tidy URL: `https://host/path` and `ssh://git@host/path` parse normally, the SCP-like `git@host:path` has no scheme and its `:` separates host from *path* rather than a port, a `https://org@host/…` form carries userinfo to strip, and an explicit `:<port>` is part of connecting but not of the name to match. Where no host can be extracted even so — a local or relative path — say so and ask, rather than treating the string as a hostname. **When that ask cannot be reached** (non-interactive, or a subagent that cannot prompt), stop and say which host could not be resolved, the same way the Voiced limits below treat an unobtainable confirmation.

- host **is** `dev.azure.com` or **ends with** `.dev.azure.com`, or **ends with** `.visualstudio.com` → **Azure DevOps** (`resources/backends/azure-devops.md`). The `.dev.azure.com` suffix matters: Azure DevOps's own SSH clone URL is `git@ssh.dev.azure.com:v3/<org>/<project>/<repo>`, so an equality-only rule rejects every SSH-cloned Azure DevOps repository while the legacy `vs-ssh.visualstudio.com` form keeps working, which is what hides the gap.
- host **is** `github.com`, or **ends with** `.github.com` → **GitHub** (`resources/backends/github.md`).
- **Match the end of the host, never a substring** — `github.company.com` contains `github.com` and is not it.
- Any other host may still be a **GitHub Enterprise** server, whose hostname is arbitrary and cannot be recognised by name. Ask `gh` instead of guessing: `gh auth status --hostname <host>` (with any `:<port>` stripped) exiting 0 means the user has configured that host, which identifies it as a GitHub-family server — use the GitHub adapter. **A non-zero exit does not mean "not GitHub"**: the same command is the GitHub adapter's tool precondition, so it also fails when `gh` is absent, or when the host is an Enterprise server the user has not logged into or whose token has expired. Offer both readings — name the host, say `gh` could not confirm it, and ask whether it needs `gh` auth or is another platform — rather than asking a platform question of someone whose remedy is `gh auth login --hostname <host>`.

**Resolve the plugin root first, and stop if you cannot.** The backend adapter lives under the plugin root at `resources/backends/` — never under the skill directory, and never at a path containing `plugins/pr-lifecycle/`, which exists only in this marketplace's own source tree and not in an install. Resolve that root the way this Claude Code build exposes it (`${CLAUDE_PLUGIN_ROOT}` where available, otherwise the directory holding this skill's plugin manifest), and read the adapter to confirm the resolution before going further.

**If the adapter cannot be read, stop and say so — do not continue unadapted.** Every platform-specific operation this skill performs is in it: fetching the threads, normalizing them, posting a reply, setting a thread's status. Without it there is nothing to triage and no way to answer, so proceeding would either act on nothing or invent a shape for someone else's review comments. Report which path failed and let the human point you at the plugin.

**Announce** the detected platform so a silent wrong guess is impossible, then load the matching backend adapter and run the platform-specific parts of the steps below through it. The backend seam in this body is **selecting** the adapter and nothing else — recognising the remote string, plus the one `gh auth status --hostname` exit code above, which is a deliberate exception because a GitHub Enterprise host cannot be selected by name and no adapter can be loaded before the selection is made. **No field access beyond that**: past this point every platform value comes from an adapter recipe. The normalized model the adapter produces is defined in Step 3.

## Step 1 — Identify the PR and confirm it belongs to this repo

Take the PR id from the skill argument or from natural language ("PR 12345", "the comments on 148409"); validate it is a positive integer.

Run the **backend adapter's identity / belongs-to-repo recipe** — it derives the repository from the current `git remote`, reads the PR (capturing the source branch, target branch, and status), and confirms the PR belongs to **this** repository (Azure DevOps guards a cross-org id collision by GUID; GitHub's PR number is repo-scoped). If the adapter reports a wrong-repo mismatch, stop and say so — a PR from another repo would send every downstream code edit and reply to the wrong place. If the adapter reports the PR is not active (already completed / merged / abandoned), warn and stop — there is nothing to resolve.

## Step 2 — Preconditions (stop and report if any fails)

- **On the PR's source branch.** The current local branch must equal the PR's source branch — fixes must land on the branch the PR actually tracks. If it does not match, warn and ask the user to `git switch` to the correct branch before continuing; do not switch for them.
- **Local branch in sync.** `git fetch`, then compare the local branch with its remote source branch. If it is behind, warn — committing and pushing from a stale branch can conflict with or undo work already on the PR. If it is ahead (has unpushed commits), warn too — the fix push will carry those commits onto the PR as well. Let the user reconcile before proceeding.
- **Tooling present.** The detected platform's PR tool is installed and authenticated (see the backend adapter's precondition — `az` + the `azure-devops` extension for Azure DevOps, `gh` authed for GitHub); otherwise take the voiced-limit path below.
- **Working tree.** If there are uncommitted changes unrelated to this task, note them — the fix commit must include only the changes made for these comments, not pre-existing noise.

## Step 3 — Fetch the threads → normalized model

Run the **backend adapter's fetch recipe**. The adapter fetches the raw threads and maps them into the platform-agnostic **normalized thread/comment model** — the only shape this skill body reads:

```
thread {
  id,
  resolvable: bool,                       // false → this comment cannot be resolved (e.g. a GitHub PR-level conversation comment)
  status: unresolved | resolved | null,   // null when resolvable is false
  context: { path, line } | null,         // null for PR-level comments
  pending: bool,                          // GitHub-only: comment belongs to an unsubmitted PENDING review (Azure DevOps always false)
  comments: [
    { author_name, author_id, is_bot, type: human | system, text, id }
  ]
}
```

The adapter also does the backend-specific parts of this mapping (documented in each adapter): dropping pure system threads, the status mapping, and `is_bot` detection — because these depend on backend fields (`commentType: system` / `CodeReviewThreadType` on Azure DevOps, a `[bot]` login suffix or GraphQL `__typename == "Bot"` on GitHub) that must not leak into this body. On Azure DevOps every thread is `resolvable: true`; on GitHub inline review threads are `resolvable: true`, while PR-level (conversation) comments are `resolvable: false, status: null` (they are not resolvable review threads).

Then filter and classify — operating **on the normalized model, not raw JSON**:

- System threads are already dropped by the adapter (all-`system` threads / vote / status / reviewer / ref / policy events). Keep threads with at least one `type: human` comment.
- Default to threads whose `status` is `unresolved` — needing attention; report how many are already `resolved` so nothing looks lost. A `resolvable: false` thread (`status: null`) is never "resolved" and always surfaces as needing a look — the re-run guard, not status, decides whether it has been handled.
- Bots are already marked (`is_bot`) by the adapter (SonarCloud by default). When it is genuinely unclear whether an author is a bot, the adapter defaults to human: a missed reply is recoverable, an unanswered reviewer is not.
- **Re-run guard.** A `resolvable: false` comment carries `status: null`, so status cannot tell whether it was already handled — instead key on **whether the latest comment on the thread is the caller's own**. If a thread's most recent comment is already from the caller (`author_id` matches `git config user.email`/`user.name`), mark it "possibly already replied" but still show it at the gate — do not silently drop it. Default to not replying or re-fixing it, and let the user decide whether to follow up. This single signal works for every thread (resolvable or not): it avoids duplicate replies when the skill is run twice on the same PR — including re-replying a PR-level comment that has no status to key on — while still surfacing a thread where the reviewer replied again between runs. **Self-review exception:** a thread with **only one comment** that is the caller's own is the *original review comment* (a self-review), not an already-sent reply — surface it as needing attention, do not mark it "possibly already replied".

## Step 4 — Triage each open comment

For each kept comment, work out three things, and present them; do not act yet:

- **Source** — human reviewer or automated tool.
- **Kind** — a blocking issue or bug, a suggestion or nit, a question, or a likely false positive.
- **What it needs** — a code fix, a reply, both, or no action.

Triage informs the human; it is not an automatic verdict. Respect the reviewer's standing — the classification is a starting point for the gate, never grounds for the skill to dismiss a comment by itself.

## Step 5 — Draft the resolution for each comment (nothing outward yet)

- **Needs a code fix.** Make the smallest change the comment asks for, in the relevant files, as a local edit — do not commit. Keep it within what the comment requests; this is not a licence to do a broader code review. If the change ought to come with new or updated tests, flag it for hand-off to `test-authoring` (`add-*-test` / `update-*-test`) — do not write the tests here.
- **Needs a reply.** Draft the reply text (you may use the platform's mention and PR/work-item link syntax — the backend adapter documents it). For a likely false positive, draft an explanation rather than a dismissal.
- **Automated / SonarCloud.** Do not draft a reply and do not plan to resolve the thread by hand: the resolution is to push the fix so the CI re-run closes the tool's own stale comments. Many SonarCloud comments are trivial or arguably pointless — make the minimal change that satisfies the check and move on; do not over-invest.
- **Proposed thread-status action.** For each comment, note whether you would propose to resolve the thread or leave it active — applied only if the user allows status changes at the gate (Step 7). For a `resolvable: false` comment (e.g. a GitHub PR-level conversation comment) there is **no resolve action** — offer a reply only; do not propose a status change for it.

## Step 6 — Verify the code fixes

Scale verification to the size of the change, borrowing the independent-verifier idea from `review-code-risk` without doing a full code-risk review. First determine the repo's build and test command from the repo itself — its build files and CI config. Nothing caches one for you: `test-authoring` detects the command per session rather than recording it anywhere, so there is no per-repo file to look in. If it cannot be determined, ask rather than guess or skip silently.

- A behavioural fix runs the build and the affected tests; for a non-trivial fix, you may spawn one fresh read-only agent to check it adversarially (one hop, not itself verified). If this skill is itself running inside a subagent and cannot spawn one, mark the fix `not independently verified` at the gate rather than self-verifying or skipping silently.
- A trivial fix (a rename, a format change, most SonarCloud nits) needs only a build to confirm the process is satisfied.
- Triage any red test by intent: a fix that broke still-valid behaviour is re-fixed once or reverted; a test that is now legitimately stale is flagged for hand-off to `test-authoring`, not edited here.

## Step 7 — One final confirmation: present everything

This is the only gate, and nothing outward has happened before it. Present a single consolidated view — one row per comment — showing: the comment (author, file/line, kind), the proposed disposition (the code-fix diff, the drafted reply, the explanation, an intentional skip with its reason, or a hand-off), the proposed thread-status action, and the verification result. For a `resolvable: false` comment, mark the status column **no resolve action available (reply only)** so the user sees there is nothing to opt into. For a `pending: true` thread, mark it **comment not yet published (pending review)** — replying to it requires publishing that review first (an outward action, and only when the caller is its author) or skipping; the backend adapter documents the options. Include the "possibly already replied" threads from Step 3 so the user can choose to follow up.

Let the user adjust freely in prose: which fixes to keep, edits to any reply text, which comments to skip and why. And ask explicitly whether to allow updating thread status, and how far — the default is to **never close a human reviewer's thread** (the reviewer closes their own), so an opt-in is required to resolve human threads at all. Bot threads are left to CI regardless. A `resolvable: false` comment has no resolve to opt into — only a reply.

## Step 8 — Apply, after confirmation

First, reconcile the working tree to exactly the approved set. The drafted fixes from Step 5 are already applied, and two fixes can touch one file — so a per-file `git restore` could wipe a kept fix. Instead, revert all drafted edits to their pre-draft baseline (`git restore` the touched tracked files; delete any files the drafts newly created), then re-apply only the kept fixes. If none were kept, skip the commit and push (nothing to build on) and go straight to the replies. Then apply in this fixed order, so the fix is visible before any reply refers to it:

1. **Commit** the kept fixes (generic git), following the repo's own commit convention — **read it off the repo, do not assume one.** `git log --format=%s -n 30` shows the shape the repo actually uses: whether subjects carry a ticket prefix and in what form, or a Conventional Commits type, or nothing. Match what you find, including its subject length — a repo whose subjects run to 70 characters has told you its limit. Only when the history is empty or shows no consistent shape, fall back to a plain `<summary>` (≤50 characters) and say that is what you did. If the branch carries a ticket id and the history prefixes with one, use the repo's own form for it. (Squash-merge repos collapse per-commit messages anyway, so do not over-invest here.) **No AI co-author trailer**: do not add a `Co-authored-by` line naming Claude or any other agent unless the invoking request explicitly asked to mark this work as AI-assisted — the same single opt-in that turns on `open-pr`'s provenance footer and `ai-assisted` label, and off by default here too. The repo's own history does not decide this one: the trailer names *who wrote this commit*, so it is a claim about this run, not a shape to copy. Commit only the changes made for these comments. One commit for the batch is the default.
2. **Push** (generic git) — this updates the PR and triggers the CI re-run (which is what closes SonarCloud's own stale comments).
3. **Reply** — post each approved reply to its thread via the **backend adapter's post-reply recipe** (given the thread id and reply text). Replies were drafted before the commit existed, so they do not hard-code a commit hash; reference the PR or work item with the platform's link syntax instead.
4. **Update thread status** — only for threads the user approved and only where `resolvable: true`, via the **backend adapter's set-status recipe** with the normalized verb `resolve` (the adapter maps it per platform — Azure DevOps PATCH `{ status: fixed }`, GitHub `resolveReviewThread`). A `resolvable: false` comment gets no status call. Never touch a bot thread, and never close a human thread without explicit approval.

## Step 9 — Completeness report

Confirm that every comment captured in the initial fetch (Step 3) reached a disposition: fixed and committed, replied, explained, intentionally skipped with a reason, handed off to `test-authoring`, or left to CI. Report the dispositions as a table.

Do not re-fetch the threads to verify their status changed. SonarCloud closes its own comments only after the CI re-run, which is asynchronous and not observable within this session — say so rather than implying it is done.

## Safety rails

- No outward action before the Step 7 confirmation — no commit, push, reply, or status change.
- Never close a human reviewer's thread without explicit approval; bot threads are left to CI.
- Never dismiss a reviewer's comment on the skill's own judgement — triage and draft, the human decides.
- Never resolve merge conflicts automatically, and never force-push.
- Commit only the changes made for these comments, not unrelated working-tree changes.
- If the local branch does not match the PR's source branch, stop and ask the user to switch.

## Voiced limits

- If the detected platform's PR tool is missing or unauthenticated (see the backend adapter's precondition, named at Step 2), say so and print the drafted fixes and replies for manual handling — do not act and do not fail silently.
- **GitHub path is partly verified.** A real-PR smoke test (2026-07-03) verified platform detection, identity, GraphQL fetch + normalize, triage, the gate, commit/push, REST inline reply, and the pending-review workaround. **Still by-design only:** the resolve action (`resolveReviewThread`), bot-thread handling, PR-level conversation comments, and multi-thread batches. Announce this partial-verification limit when running on GitHub; do not imply full parity with the Azure DevOps path.
- If a confirmation cannot be obtained (running non-interactively, or inside a subagent that cannot prompt), do not apply anything, `git restore` the local fix edits so nothing is left half-applied, and print the full set of drafts for the user to act on.
- If the current repository has no remote, or several remotes leave the org/project ambiguous, report it and ask the user to specify — do not guess.
- Verification is best-effort, and bot auto-close is asynchronous — neither is claimed as a guarantee.
- Bot detection is a heuristic (SonarCloud by default); when unsure, an author is treated as human — announced, not silent.
