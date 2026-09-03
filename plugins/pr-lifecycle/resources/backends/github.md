# Backend adapter — GitHub

Reference doc for the PR-platform operations `open-pr` and `resolve-pr-comments`
run against GitHub.
The skill body detects the platform (Step 0) and follows the recipes here,
so no `gh`-specific field parsing lives in the skill body itself.

> **Scope:** this file covers both the **open-pr** operations
> (create PR, list existing PR for dup-check,
> list the repository's merged PRs for convention learning,
> add label, PR cross-reference link)
> and the **resolve-pr-comments** thread operations
> (identity / belongs-to-repo check, fetch + normalize review threads via
> `gh api graphql`, post a reply, resolve via `resolveReviewThread`).
>
> **Partly runtime-verified (2026-07-03).** A real-PR smoke test verified: platform detection,
> identity / belongs-to-repo, GraphQL fetch + normalize, triage, the gate, commit/push, REST inline
> reply (via `databaseId`), and the pending-review submit workaround. **Still by-design only:**
> `resolveReviewThread` (resolve), bot-thread handling, PR-level conversation comments, and
> multi-thread batches. The skill voices this partial-verification limit on GitHub.

## Detection signature

Detect GitHub from `git remote get-url origin`: the host **is** `github.com`, or
**ends with** `.github.com`. Match the end of the host, never a substring —
`github.company.com` contains `github.com` and is not it.

A **GitHub Enterprise** host is arbitrary and cannot be recognised by name, so it is
identified by asking `gh` rather than by the hostname: `gh auth status --hostname <host>`
exiting 0 means the user has configured that host, which is what makes it a
GitHub-family server. Every recipe below then applies unchanged.

## Tool precondition

- `gh` CLI is on PATH and authenticated **for the host this remote names**:
  `gh auth status --hostname <host>` succeeds. **The unscoped `gh auth status` is not a
  substitute** — it exits 0 whenever *any* host is configured, so on a GitHub Enterprise
  remote it passes on the strength of a github.com login while every call this run makes
  goes to a host `gh` knows nothing about. Measured: `--hostname` on a configured host
  exits 0, on an unconfigured one exits 1, while the unscoped form exits 0 for both.
  Strip any `:<port>` from the host before passing it — a self-hosted Enterprise server on
  a non-standard port is configured under its bare hostname, and the ported form exits 1.
- **A non-zero exit says three different things, and only one of them is "not GitHub".**
  `gh` may be absent from PATH; the host may be a GitHub-family server the user has not
  logged into, or whose token has expired; or the host may genuinely be another platform.
  On a `github.com` remote the platform is already known by name, so a failure here is
  purely the authentication limit — say so and print the prepared title and description
  for manual creation. On an unrecognised host, where this same command is also what
  *identifies* the platform, do not report it as an unknown platform: name the host, say
  `gh` could not confirm it, and offer both readings, so the user whose real remedy is
  `gh auth login --hostname <host>` is not asked which platform they are on.
- If `gh` is missing or unauthenticated, the skill voices the limit and prints
  the prepared title and description for manual creation — it does not fail
  silently and does not create the PR.

## Recipes

### Create PR

Write the full description to a temp file and pass it as `--body-file <file>`:

```
gh pr create \
  --title "<title>" \
  --body-file <file> \
  --base <target>
```

- If the source branch is not on the remote, or is behind local HEAD, **publish it first
  with `git push -u origin <branch>`** — the PR needs the source branch on the remote, and
  it carries whatever the remote branch holds. Publish only after the human confirmation
  (see the skill's invariant).
- **Do not leave the publishing to `gh pr create`.** Its own help: "When the current branch
  isn't fully pushed to a git remote, a prompt will ask where to push the branch and offer
  an option to fork the base repository." Creating a fork is an outward action the
  confirmation gate never described, and a push that happens inside the create also bypasses
  the skill's push-failure branch — so a rejected publish surfaces as a create error whose
  cause the caller cannot read. Push explicitly first; `--head` is the documented way to
  suppress the behaviour outright if a run ever needs the belt as well as the braces.
- The `🤖` footer and plain-ASCII fenced diagram round-trip intact through
  `--body-file` (UTF-8); no cp1252 quirk applies here.
- **Description limit: not established here.** GitHub does enforce a maximum body size and
  rejects an over-long body, but no figure has been verified for this file, so the skill's
  Step 4 has no number to measure against. Report the description as *unmeasured* rather
  than treating this silence as "no limit exists" — the unverified case and the
  no-limit case are not the same, and only one of them is safe to imply.
  **The vendor does not publish one either** *(external)*:
  checked against the pull-requests REST reference on 2026-09-03, which states no maximum for `body`.
  So the gap here is not an unfinished job — the figure is not available to look up,
  and a number invented for this file would be worse than an honest absence.
  If one is ever established, record where it was measured and when, the way the Azure DevOps adapter's create recipe now does.
  Whether this platform's sample probe truncates a body the way that one's does is **unmeasured** —
  do not read the Azure DevOps note as covering GitHub.
- Return the PR URL, which `gh pr create` prints on success.

### Dup-check (list existing PR)

```
gh pr list --head <branch> --state open \
  --json number,url,baseRefName,isCrossRepository,headRepositoryOwner
```

**Query by head branch alone — do not add `--base`.** The two filters are ANDed, so
narrowing by a target the caller defaulted to wrongly returns nothing and the skill
opens a second pull request for a branch that already has one.

**`--json` is not optional.** Without it the output is a human table carrying neither the
base branch nor the fork flag, and both are values the skill's Step 2 has to judge on.

Map each result into the normalized entry Step 2 expects:

- `url` ← `url`.
- `target` ← `baseRefName`, which GitHub returns as a **plain** branch name needing no
  stripping. (Azure DevOps returns a full `refs/heads/…` ref and does need it — the two
  platforms differ here, which is exactly why the skill body is given a normalized name
  rather than a field.)
- `from_fork` ← `isCrossRepository`; `headRepositoryOwner.login` names whose branch it is.

**A plain `--head <branch>` does match a pull request opened from a fork** — measured
against a public repository that takes fork contributions: `gh pr list --head <branch>`
returned an entry with `isCrossRepository: true` at exit 0. So this query is not blind to
forks, and no hedge about that is owed. The consequence runs the other way: on a repository
that accepts fork contributions, a common branch name can match **a stranger's** pull
request, which is why `from_fork` is in the mapping — such an entry is somebody else's
branch sharing a name, not a duplicate of yours.

`gh pr list --help` states for **this** flag that the `<owner>:<branch>` syntax is **not
supported**, and it fails silently: measured, `--head "<owner>:<branch>"` returns `[]` at
exit 0, which reads as "no duplicate". So do not reach for that form here. (The prohibition
is scoped to `gh pr list`; `gh pr create --head` does support the `<user>:<branch>` syntax.)

### Add label (opt-in, best-effort) — do NOT pass `--label` to `gh pr create`

The `ai-assisted` label is **off by default** — apply it only when the invoking
request explicitly opted in (see the skill's Step 3, under "AI-provenance
markers"). The create recipe
above never passes `--label`, so the default (no opt-in) needs no change here.

**Real bug:** `gh pr create --label X` **aborts creating the PR** if the label
`X` does not already exist — it is not best-effort. So, **when opted in**:

1. Create the PR **without** `--label` (recipe above).
2. Then add the label separately:

   ```
   gh pr edit <pr-number> --add-label ai-assisted
   ```

3. If the `ai-assisted` label does not exist, `gh pr edit` fails — **tolerate it**:
   the PR is already created with the opted-in footer; drop the
   label and **voice a note** that the tag could not be applied (the label must
   be pre-created in the repo to be filterable). Never let a missing label
   abort or undo the PR.

### Reading the repository's previous PRs — use the API, not git

Git is **not** a sound source on GitHub, and the reason is structural rather than
fussy: several merge strategies coexist, one repo can show all of them, and the list
is not closed.

- **Squash merge** — subject `<title> (#<n>)`; body is either the PR description or
  the branch's own commit messages, depending on a repo setting.
- **Merge commit** — subject `Merge pull request #<n> from <owner>/<branch>`; the title
  is the body's first line and the description is absent entirely.
- **Rebase merge** — nothing marks a pull request at all.
- **Merge queues and merge bots** add their own subjects (`Auto merge of #<n> - …`,
  `Rollup merge of #<n> - …`), so any fixed taxonomy is incomplete.

Two consequences make git unusable here. A multi-line body has no delimiter, so
nothing distinguishes a body's continuation line from the next commit's subject —
and merge commits are common enough to dominate a window. And an ordinary
direct-push commit that references an *issue* (`Bump dep to 4.2 (#1234)`) is
indistinguishable from a squashed PR title.

So use the API:

```
gh pr list --state merged --limit 60 \
  --json number,title,body,mergedAt,author [--author <login>]
```

- **`--json` is not optional.** Without it the output is a human table whose last
  column is the *creation* date, and which carries **no body at all**.
- **`--author` takes a GitHub login, not an email**, and it is how the caller-scoped
  rung is expressed here. Passing the caller's git email returns an empty list with a
  **success** exit, which reads as "no history" — and note that the exit-status rule below
  cannot catch this one, because the call genuinely succeeded. Resolve the login with
  `gh api user --hostname <host> --jq .login`: **host-scope it**, because on a GitHub
  Enterprise remote the unscoped form answers from the default host and hands back a
  github.com login that does not exist on this server, producing exactly the empty-at-exit-0
  result described above. Note this is the `gh`-authenticated account, which need not be the
  same person as `git config user.email` — where the two disagree, say so rather than
  sampling silently. Drop the flag for the all-authors rung.
- **The list is creation-ordered, not merge-ordered.** `mergedAt` is in the JSON —
  sort on it yourself for any "most recent" decision.
- **An empty list and a failure are distinguishable here, so distinguish them.**
  A target branch that does not exist yields `[]` at exit 0. Bad credentials and an
  unreachable host **fail** instead — `HTTP 401: Bad credentials`, or a remote
  mismatch — at a non-zero exit. Check the exit status; do not read every empty
  result as history.

### Diagram form

GitHub renders a ```` ```mermaid ```` fence in a pull request body, so a Mermaid diagram is
the first choice here — it reads as a drawing rather than as monospace art, and it survives
the reader's font. A fenced plain-ASCII diagram also renders and is the fallback where the
shape does not suit Mermaid.

### PR cross-reference link syntax

GitHub auto-links `#<pr_number>` to that PR in the same repo — the form to use when the
sampled PRs for a target reference the PR a change was ported from. Which number that is
comes from whoever asked for the port, not from this adapter.

## Thread operations (resolve-pr-comments)

> **Partly runtime-verified** — see the scope note at the top for what is verified vs by-design only.

These recipes cover the resolve-pr-comments flow. The skill body works only on
the **normalized thread/comment model** below — it never reads `gh` JSON or
GraphQL fields directly. This adapter fetches, parses, and maps into that model
(in), and maps the skill's normalized verbs back to `gh` calls (out).

### Identify the PR and confirm it belongs to this repo

Take the PR id (a positive integer). On GitHub a PR number is **repo-scoped**, so
identity is simply `owner/repo` from the remote (`git remote get-url origin`) —
there is no cross-org GUID confusion to guard against as on Azure DevOps. Read
the PR to confirm it exists on this repo and capture its branches and state:

```
gh pr view <PR_ID> --json number,headRefName,baseRefName,state
```

If the PR is not found on `owner/repo`, report a wrong-repo mismatch. If it is not
open (already merged or closed), report that it is not active.

### Fetch review threads → normalized model

**Fetch inline review threads via GraphQL** — `gh pr view --json comments` returns
only PR-level (issue) comments and cannot see inline review threads or their
resolved state, so it must **not** be used as the thread fetch:

```
gh api graphql -f query='
  query($owner:String!, $repo:String!, $pr:Int!) {
    repository(owner:$owner, name:$repo) {
      pullRequest(number:$pr) {
        reviewThreads(first:100) {
          nodes {
            id
            isResolved
            path
            line
            comments(first:100) {
              nodes {
                id
                databaseId
                body
                author { login __typename }
              }
            }
          }
        }
      }
    }
  }' -F owner=<owner> -F repo=<repo> -F pr=<PR_ID>
```

Map each `reviewThreads.nodes[]` into a normalized thread:

- `id` ← the thread's **GraphQL node id** (needed later for `resolveReviewThread`,
  which takes the node id, **not** a REST comment id).
- `resolvable` ← **`true`** for these inline review threads.
- `status` ← `isResolved` → `resolved`; `false` → `unresolved`.
- `context` ← `{ path, line }`.
- `comments[]` ← one per `comments.nodes[]`:
  - `author_name` / `author_id` ← the author `login`.
  - `is_bot` ← the author `login` ends with `[bot]` (e.g. `coderabbitai[bot]`),
    **or** GraphQL `author.__typename == "Bot"`. Ambiguous → `false`.
  - `type` ← `human` (GitHub review-thread comments have no `commentType: system`
    equivalent — those are timeline events outside the thread, so the system set
    is normally empty here).
  - `text` ← `body`.
  - `id` ← the comment's numeric **`databaseId`** — the REST reply (`in_reply_to`, below) needs the
    numeric id, **not** the GraphQL node id (`PRRC_…`), which 422s there. The thread's GraphQL node
    `id` (above) is separate and used only by `resolveReviewThread`.
  - `pending` ← `true` if the comment belongs to an **unsubmitted PENDING review** (see "Pending
    reviews" below); otherwise `false`. A pending comment is visible only to its author and cannot
    be replied to until that review is submitted.

**PR-level (conversation) comments** are **not** resolvable review threads —
`resolveReviewThread` acts on inline threads only — but a human's general comment
is real feedback the skill **must not miss**. So **also fetch** them
(`gh pr view <PR_ID> --json comments`, author included) and map each to a
normalized thread with `resolvable: false`, `status: null`, `context: null`. The
skill drops bots/system the same as any thread; the remaining PR-level comments
get a reply only, never a resolve action. (This matches Azure DevOps, where a
PR-level comment is a `threadContext: null` thread and is always fetched.)

**Review summary bodies** — a reviewer's top-level review comment (the body left on
an Approve / Comment / Request-changes submission) lives in `PullRequestReview.body`,
which is **neither** an issue comment nor a review thread, so both fetches above miss
it. **Also fetch** it (`gh pr view <PR_ID> --json reviews` → each review's `body` and
`author`; skip empty bodies and the caller's own) and map each non-empty body to a
normalized thread with `resolvable: false`, `status: null`, `context: null` —
reply-only, like a PR-level comment. (Azure DevOps has no separate review-summary
body, so this source is GitHub-only.)

### Pending reviews (unsubmitted)

A review left **unsubmitted** (state `PENDING`) has comments that are visible **only to their
author** — the GraphQL `reviewThreads` query above returns them (to that author) without marking
them pending. Replying to one via REST fails with
`422 … user_id can only have one pending review per pull request`.

Detect them: `gh api repos/<owner>/<repo>/pulls/<PR_ID>/reviews`; any review with `state: PENDING`
is unsubmitted, and its comments (`.../reviews/<review_id>/comments`) belong to threads that must be
mapped `pending: true`.

Handling a pending thread (pick per the gate, never silently):
1. **Submit the review, then reply** — `POST .../reviews/<review_id>/events` with `event=COMMENT`,
   which publishes all of that review's comments; then reply normally. Submitting is an **outward
   action**, only valid when the caller **is** the review's author, and requires **explicit user
   confirmation** — never auto-submit a review (least of all someone else's).
2. **Append into the same pending review** — GraphQL `addPullRequestReviewThreadReply` attaches the
   reply to the pending review without publishing it.
3. **Skip** — leave the pending thread for the author to submit themselves.

### Post a reply to a thread

- **PR-level (conversation) reply:**

  ```
  gh pr comment <PR_ID> --body "<text>"
  ```

- **Inline reply** (reply within an existing review thread) via REST:

  ```
  gh api repos/<owner>/<repo>/pulls/<PR_ID>/comments \
    -f body="<text>" -F in_reply_to=<comment_databaseId>
  ```

  `in_reply_to` is the comment's numeric **`databaseId`** (from the fetch query), not the GraphQL
  node id. If the target comment belongs to a pending review, this 422s — handle per "Pending
  reviews" first.

### Set thread status

Only `resolvable: true` inline threads can be resolved, via GraphQL using the
thread's **GraphQL node id**:

```
gh api graphql -f query='
  mutation($id:ID!) {
    resolveReviewThread(input:{threadId:$id}) {
      thread { isResolved }
    }
  }' -F id=<thread_node_id>
```

Map the skill's normalized verb: `resolve` → this mutation; `leave` → no call.
For a `resolvable: false` comment there is **no resolve** — the skill offers a
reply only and never emits a resolve verb for it.
