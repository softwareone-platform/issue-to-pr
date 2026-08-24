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

### Reading previous pull requests out of git — the whole sample, no API

Completing a pull request writes one commit that carries the whole pull request, so
git holds both halves and no `az` call, authentication, or identity lookup is needed:

```
git log origin/<default-branch> -i --author=<token> --format='%x1e%an%x1f%s%n%b' -n 200
```

- **Subject** — the field after the `0x1f`, of the form `Merged PR <n>: <title>`; strip a
  leading `Merged PR [0-9]+: ` from it (the record no longer starts there, so an anchored
  pattern will not match). A subject that
  does not match never went through a pull request, so ignore it — and count the ones
  that *do* match, because that is the sample size, not `-n`.
- **Body** — whatever the description was, verbatim: the completion copies it rather
  than summarising, so headings, bullets, and fenced blocks survive when they were
  there. How often they were there varies enormously between repositories; read the
  sample rather than expecting either answer.
- **Author** — `%an`, ahead of a `%x1f` unit separator, so each record reads
  *author*, `0x1f`, *subject*, newline, *body*. It is the identity **the organisation
  directory holds**, not the one in the contributor's `git config`: those routinely
  differ in both spelling and word order, which is why the skill matches a token rather
  than a whole name, and `-i` handles the casing half of that and nothing more. Carry
  the author through rather than dropping it — a sample can be dominated by one person
  or by automation, and that is only visible if the author is in front of you.
- **`%x1e`** is a record separator, and it is load-bearing: descriptions are multi-line,
  so without a delimiter nothing distinguishes a body's continuation line from the next
  commit's subject. It is emitted *before* each record, so the first field is empty.
- **`origin/<default-branch>`, never a bare local name** — a local branch of the same
  name is routinely behind the remote and reading it fails *silently* with a stale
  sample. This applies to `git log` only: the API recipes below take a bare branch
  name, and prefixing one there matches nothing at a success exit.

**Not every repository yields markers.** Completion strategy is a per-repo, per-branch
policy, and a rebase-and-fast-forward completion writes no merge commit at all — that
is a healthy configuration, not a rewritten history. A no-fast-forward policy also
mixes the source branch's own commits into the range, so the marker count can be a
small fraction of `-n`. Where the markers are too few, say so and use the API fallback
below rather than reporting "no history".

### List merged pull requests (API fallback, for a marker-less repository)

```
az repos pr list --status completed --top 100 -o json
```

Needed only where the git read above found too few markers. Each result carries both
`title` and `description`, so this serves both halves.

- **`-o json` is not optional.** The default table output carries no description at all
  and truncates the title, so a user whose `az` output default is `table` would learn a
  body convention from nothing. Ask for JSON explicitly.
- **Do not add `--creator`.** It resolves through the organisation directory and
  **raises** (`Could not resolve identity`, `There are multiple identities found`)
  rather than returning an empty list, so a commit email that is not a directory
  identity stops the call outright. Filter by author yourself, over the returned JSON.
- **Do not add `--org`.** Organisation, project, and repository are detected from the
  git remote, which is the only reason this adapter was loaded; passing `--org` is what
  *disables* that detection, and an unresolved repository is not an error — the
  extension falls back to listing the whole project's pull requests, drawing the sample
  from other repositories.
- The window here (`--top`) and the git window (`-n`) are different sizes; report which
  one the sample came from.
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

### Diagram form

Azure DevOps does **not** reliably render Mermaid in a pull request description, so a diagram
here is a fenced **plain-ASCII** one — boxes, arrows, and `+ - | > v` glyphs, which survive an
encoding downgrade as well as a font change. Two constraints come with it, both from this
file's create recipe: the description travels through the UTF-8 temp file described there, and
the platform enforces a hard **4,000-character** description limit that it *rejects* rather
than truncates — so a diagram that pushes a description past it fails the create after the
human has already confirmed. Check the length before offering a large one.

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
