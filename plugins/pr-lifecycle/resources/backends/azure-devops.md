# Backend adapter — Azure DevOps

Reference doc for the PR-platform operations `open-pr` and `resolve-pr-comments`
run against Azure DevOps.
The skill body detects the platform (Step 0) and follows the recipes here,
so no `az`-specific field parsing lives in the skill body itself.

> **Scope:** this file covers both the **open-pr** operations
> (create PR, list existing PR for dup-check,
> read a target's previous PRs out of git for convention learning,
> with an API fallback for a marker-less target, add label, PR cross-reference link)
> and the **resolve-pr-comments** thread operations
> (identity / belongs-to-repo check, fetch + normalize review threads,
> post a reply, set thread status).

## Detection signature

Detect Azure DevOps from `git remote get-url origin`:

- host contains `dev.azure.com`, or
- host matches `*.visualstudio.com`.

## Tool precondition

- `az` CLI is on PATH **and** the `azure-devops` extension is installed,
  and the session is authenticated (`az login` / a valid PAT).
- If `az` or the `azure-devops` extension is missing or unauthenticated,
  the skill voices the limit and prints the prepared title and description
  for manual creation — it does not fail silently and does not create the PR.

## Recipes

### Create PR

Write the full description to a **UTF-8 temp file** and pass it as `--description "@<file>"`,
never as an inline string:

```
az repos pr create \
  --title "<title>" \
  --description "@<utf8-file>" \
  --target-branch <target> \
  [--labels ai-assisted] [--open] [--draft true] [--auto-complete true] [--reviewers <r> ...]
```

- `--labels ai-assisted` is **opt-in and omitted by default** — include it only when the
  invoking request explicitly asked to mark the PR as AI-assisted (see the skill's Step 3,
  item 5). By default the PR is created with no label.

- If the source branch is not yet on the remote, **publish it first**
  (`git push -u origin <branch>`) — `az repos pr create` needs the source branch
  on the remote. Publish only after the human confirmation (see the skill's invariant).
- Return the PR URL.

#### az.cmd cp1252 / UTF-8 `@<file>` quirks (Azure-specific)

These traps are why the description must go through a UTF-8 file, not an inline string:

- On Windows `az` is a batch shim (`az.cmd`) that stores only the **first line**
  of an inline multi-line `--description`, and under PowerShell the diagram's
  backtick fence would be eaten as an escape character — the `@<file>` form
  sidesteps both.
- Write that file with a **literal** writer that emits UTF-8 — the Write tool
  (literal content, UTF-8 by default) is simplest; a single-quoted here-string
  keeps the backticks too but only if it is itself written as UTF-8
  (the diagram and footer reach the server only when the file is UTF-8).
  Never an interpolating PowerShell `"..."` string — it eats the same backticks
  before they reach disk.
- Do **not** fall back to `az rest --body @<file>` for the description: that path
  decodes the file as cp1252 and silently strips the `🤖` footer and any
  non-ASCII diagram glyphs. Keep to the high-level
  `az repos pr create --description "@<file>"` with a UTF-8 file: that path
  preserves the whole body — verified on Windows, the fenced diagram and the
  `🤖` footer round-trip intact on the server.
- If you verify it, do **not** trust `az repos pr show ... -o tsv`: az's stdout
  is cp1252 on a Windows console and drops the `🤖` (and other non-ASCII glyphs)
  on the way out even though the server stored them, so a footer that looks
  missing there is a console artefact, not a real drop — confirm in the web UI,
  or via the REST API where the bytes stay UTF-8.

### Dup-check (list existing PR)

```
az repos pr list --source-branch <branch> --target-branch <target> --status active
```

If one exists, **stop and point the user to it** — do not open a second PR,
and do not modify the existing one.

### Add label (opt-in, best-effort)

The `ai-assisted` label is **off by default** — add it only when the invoking
request explicitly opted in (see the skill's Step 3, item 5). When opted in,
Azure DevOps creates the tag on the fly via `--labels ai-assisted` on
`az repos pr create` (above), so no separate call is needed.
It is then **best-effort**: if the org disallows ad-hoc PR tags and
`az repos pr create` rejects `--labels`, drop the tag, create the PR with the
opted-in footer alone, and say so.

### Reading a target's previous PRs out of git — the whole sample, no API

Completing a pull request writes one commit onto the target branch that carries the
whole pull request, so git holds both halves:

- **Subject** — `Merged PR <n>: <title>`. Strip `^Merged PR [0-9]+: ` **once**.
  A subject that does not match never went through a pull request; ignore it.
  A completion message is a free-text box a human may edit, and re-completions happen,
  so `Merged PR <n>: Merged PR <m>: <title>` is a real shape: a residual
  `Merged PR <n>: ` after one strip is that case rather than part of the title.
- **Body** — whatever the pull request's description was, verbatim: the completion copies
  it rather than summarising it, so headings, bullets, and fenced blocks survive if they
  were there. Expect that they usually were not. Across these repos most descriptions are
  one or two lines, a quarter of them on some branches are empty, and fenced blocks are
  close to absent — so the body is a faithful sample, not a rich one.
- **Author** — the pull request's author, so `-i --author=<pattern>` selects that
  person's own PRs.

```
git log $(git merge-base origin/<default> origin/<target>)..origin/<target> \
  -i --author=<pattern> --format='%x1e%s%n%b' -n 60
```

Every part of that line is load-bearing:

- **`origin/<target>`, not `<target>`** — a local branch of the same name is routinely
  behind the remote, and reading it fails *silently* with a stale sample; in a fresh
  clone it does not exist and the command errors instead. `git fetch` updates
  `origin/*` and never the local branch, so fetching does not protect you.
- **The `merge-base ..` bound** keeps the sample inside the target's own history.
  Without it a young maintenance line returns the default branch's PRs, and a line
  with no commits of its own yet returns *nothing but* the default branch's.
- **`-i`** because `git log --author` is case-sensitive, and one person's display name
  appears in more than one form in the same repo (`Surname, First` alongside
  `First Surname`).
- **`%x1e`** is a record separator, and it is not decoration: descriptions are
  multi-line, so without a delimiter nothing distinguishes a body's continuation line
  from the next commit's subject.

Where a target carries no `Merged PR` markers at all — a rewritten branch, or
completions predating the current policy — say so and use the API fallback below
rather than reporting "no history".

### List merged PRs by target (API fallback, for a marker-less target)

```
az repos pr list --target-branch <target> --status completed --top 20
```

Needed only where the git read above found no markers. Each result carries both
`title` and `description`, so this fallback serves *both* halves — it is not a
descriptions-only path. Note the two windows differ (`--top 20` here against 60
commits above), so report whichever you actually used.
Two flags to leave off, both verified against the extension's behaviour:

- **`--creator`** is resolved through the directory and **raises** on failure
  (`Could not resolve identity`, or `There are multiple identities found`) instead of
  returning an empty list, so a commit email that is not a directory identity
  (a `noreply` address, a machine account) stops the call outright. Filter by author
  with git's `--author` instead.
- **`--org`** disables the git-remote detection that supplies organisation, project,
  and repository. That detection is reliable here — this adapter is only ever loaded
  because the remote is an Azure DevOps one — and an unresolved repository is *not*
  an error: the extension falls back to listing the whole project's pull requests,
  drawing the sample from other repositories. So leave detection alone.

### PR cross-reference link syntax

Azure DevOps renders `!<pr_number>` as a link to that PR — the form to use when the
sampled PRs for a target reference the PR a change was ported from. Which number that is
comes from whoever asked for the port, not from this adapter.

## Thread operations (resolve-pr-comments)

These recipes cover the resolve-pr-comments flow. The skill body works only on
the **normalized thread/comment model** below — it never reads `az` JSON fields
directly. This adapter fetches, parses, and maps into that model (in), and maps
the skill's normalized verbs back to `az` calls (out).

### Identify the PR and confirm it belongs to this repo

Take the PR id (a positive integer). Derive the organization, project, and
repository from the current `git remote` (the same remote `open-pr` pushes to),
then read the PR:

```
az repos pr show --id <PR_ID> --org <org>
```

Capture the source branch, target branch, `repository.id` (a GUID), project, and
status.

Confirm the PR belongs to **this** repository by GUID — the robust check:

```
az repos show --repository <name> --query id
```

Compare that id to the PR's `repository.id`. If you compare names or URLs
instead, normalise first — lowercase, ignore the SSH-versus-HTTPS form, and strip
a trailing `.git` (an Azure DevOps repository name can really end in `.git`), or
a raw string compare gives false mismatches. A PR id is only unique **within an
org**, so a number from one repo can resolve to a different PR — or nothing —
when you are standing in another repo, which would send every downstream code
edit and reply to the wrong place. If the ids do not match, report a wrong-repo
mismatch to the skill. If the PR is not active (already completed or abandoned),
report that it is not active — there is nothing to resolve.

### Fetch review threads → normalized model

```
az devops invoke --area git --resource pullRequestThreads \
  --route-parameters project=<project> repositoryId=<repoId> pullRequestId=<PR_ID> \
  --org <org>
```

This is the underlying `GET .../pullRequests/{prId}/threads`; `az devops invoke`
resolves auth and org, and the exact resource names can be confirmed with
`az devops invoke --area git` if a call fails.

Map each raw thread into a normalized thread:

- `id` ← the thread id.
- `resolvable` ← **always `true`**. On Azure DevOps both PR-level and inline
  threads can carry a resolvable status.
- `status` ← from the raw thread status:
  `active` / `pending` → `unresolved`;
  `fixed` / `closed` / `wontFix` / `byDesign` → `resolved`.
- `context` ← from `threadContext`: `{ path, line }` (from the file path and
  the right/left file line). Absent `threadContext` (a PR-level comment) → `null`.
- `comments[]` ← one per raw comment:
  - `author_name` ← the comment author's display name.
  - `author_id` ← the author's unique name / id.
  - `is_bot` ← `true` when the comment is `commentType: system`, **or** the
    author identity is a known automation (SonarCloud by default). Ambiguous →
    `false` (treat as human).
  - `type` ← `system` when `commentType: system`, else `human`.
  - `text` ← the comment content.
  - `id` ← the comment id.

**Drop-as-system:** a thread whose comments are **all** `commentType: system`, or
that carries a `properties.CodeReviewThreadType` (a vote / status / reviewer /
ref / policy update), is a pure system thread — the adapter marks it dropped so
the skill excludes it. Keep any thread with at least one `commentType: text`
comment (human or tool feedback).

### Post a reply to a thread

```
az devops invoke --area git --resource pullRequestThreadComments --http-method POST \
  --route-parameters project=<project> repositoryId=<repoId> pullRequestId=<PR_ID> threadId=<threadId> \
  --org <org>
```

with a body of `{ "content": "<text>", "commentType": "text" }`. Reply text may
use `@user`, `#workitem`, and `!<prId>` link syntax.

### Set thread status

PATCH the thread:

```
az devops invoke --area git --resource pullRequestThreads --http-method PATCH \
  --route-parameters project=<project> repositoryId=<repoId> pullRequestId=<PR_ID> threadId=<threadId> \
  --org <org>
```

with `{ "status": "fixed" }`. Valid statuses are `active`, `pending`, `fixed`,
`wontFix`, `closed`, `byDesign`. Map the skill's normalized verb: `resolve` →
`{ "status": "fixed" }`; `leave` → no call. Every Azure thread is `resolvable`,
so there is no non-resolvable case here.
