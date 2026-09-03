# Backend adapter — Azure DevOps

Reference doc for the PR-platform operations `open-pr` and `resolve-pr-comments`
run against Azure DevOps.
The skill body detects the platform (Step 0) and follows the recipes here,
so no `az`-specific field parsing lives in the skill body itself.

> **Scope:** this file covers both the **open-pr** operations
> (create PR, list existing PR for dup-check,
> read the repository's previous PRs out of git for convention learning,
> with an API fallback for a marker-less repository, add label, PR cross-reference link)
> and the **resolve-pr-comments** thread operations
> (identity / belongs-to-repo check, fetch + normalize review threads,
> post a reply, set thread status).

## Detection signature

Detect Azure DevOps from `git remote get-url origin`:

- host **is** `dev.azure.com`, or **ends with** `.dev.azure.com`, or
- host **ends with** `.visualstudio.com`.

Match the end of the host, never a substring. The `.dev.azure.com` suffix is not defensive
padding — Azure DevOps's own SSH clone URL is `git@ssh.dev.azure.com:v3/<org>/<project>/<repo>`,
so an equality-only rule rejects every SSH-cloned repository while the legacy
`vs-ssh.visualstudio.com` form keeps matching under the other suffix, which is what makes the
gap easy to miss. The extension itself recognises both (`ssh.dev.azure.com` and
`vs-ssh.visualstudio.com`) when it parses a remote.

An on-premises Azure DevOps Server has an arbitrary hostname and no equivalent probe, so it
falls to the skill's ask branch.

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
az repos pr create -o json \
  --title "<title>" \
  --description "@<utf8-file>" \
  --target-branch <target> \
  --source-branch <branch> \
  [--labels ai-assisted] [--open]
```

- **Description limit: 4,000 characters, and the platform *rejects* rather than truncates.**
  This is the limit the skill's Step 4 measures against before creating; it is stated here,
  in the create recipe, because that is where Step 4 looks for it.
  **The figure is observed, not published** *(external)*.
  Checked against the REST 7.1 create-pull-request reference on 2026-09-03: `description` is a bare `string` there with no maximum stated,
  so nothing on the vendor's side confirms 4,000 and nothing would announce a change to it.
  Treat it as a working assumption, and re-check it if a create ever fails on length alone.
  **Reject-rather-than-truncate is the load-bearing half of this bullet**, and it is much the more stable one:
  it is the whole reason the measurement happens before the create rather than after,
  and it holds whatever the number turns out to be.
  Both ways of the number being wrong are loud rather than silent —
  too low and a description that would have been accepted gets trimmed,
  too high and the create fails carrying the platform's own error.
- **Ask for `-o json` explicitly rather than relying on the default.** `az`'s own default is
  JSON, but it is a *configurable* default — `az configure` can set `table`, per user or per
  folder — and this command has a table transformer that emits only
  `ID / Created / Creator / Title / Status / IsDraft / Repository`, truncating the title and
  carrying neither the description nor any URL. `pullRequestId` is read off this result and
  nowhere else (the read-back below needs it), so the format cannot be left to a user setting.
- **How to obtain the pull request's web URL is UNRESOLVED, and this adapter does not yet say.**
  `GitPullRequest` exposes `remoteUrl` and `url`, but Microsoft documents both as
  *"Used internally"* and the extension composes the browser URL itself rather than reading
  either, so neither is established as the web URL. Composing it needs the organization and
  project, which nothing in the open-pr flow surfaces. Until this is settled against a real
  response, return whatever `az` reports and say the URL is unverified — do not present a
  constructed or guessed URL as the pull request's own.

- `--labels ai-assisted` is **opt-in and omitted by default** — include it only when the
  invoking request explicitly asked to mark the PR as AI-assisted (see the skill's Step 3,
  under "AI-provenance markers"). By default the PR is created with no label.

- **Pass `--source-branch` explicitly.** Left off, the extension infers it from the current
  branch, and on a detached HEAD there is no current branch — so the run fails inside the
  create call, after the human has already confirmed. The skill's Step 2 stops that case
  before the gate; naming the branch here removes the inference as the second half.

- **Pass no flag that is not in the recipe above.** The rule is closed rather than a list of
  named offenders, because `az repos pr create` accepts a good many more outward-acting flags
  than any list would remember — `--auto-complete`, `--bypass-policy`, `--delete-source-branch`,
  `--squash`, `--transition-work-items`, `--work-items`, `--required-reviewers`,
  `--merge-commit-message` — and a list of three reads as exhaustive to the next reader.
  Three of those deserve naming anyway, because they contradict the skill's stated behaviour
  rather than merely exceeding it: **`--auto-complete`** makes the pull request merge itself
  once policies pass, when this skill opens a pull request and stops there;
  **`--delete-source-branch`** violates the safety rail "Never delete branches" outright;
  and **`--bypass-policy`** completes the pull request while overriding the very checks the
  reviewers rely on. `--draft` and `--reviewers` are simply values nobody chose.
  `--open` is the one optional flag with a legitimate caller: pass it **only when the request
  asked for the pull request to be opened in a browser**, and never in a non-interactive
  context, which the skill's Step 4 forbids independently.

- If the source branch is not on the remote, or is behind local HEAD, **publish it first**
  (`git push -u origin <branch>`) — `az repos pr create` needs the source branch on the
  remote, and the pull request carries whatever that remote branch holds. Publish only
  after the human confirmation (see the skill's invariant).
- **Read the description back and compare it to the file you sent.** The `@<file>`
  form **fails open**: when `az` cannot read the file it logs
  `Failed to open <path>, assume not a file` at **debug** level and sends the literal
  `@<path>` string as the description. The pull request is created, the URL comes back,
  and nothing above debug level says the body never arrived. So after creating, read the
  stored description (`az repos pr show --id <pullRequestId> -o json` — no `--org`, for the
  same reason the recipes here never pass it) and
  compare it with the content of the file. **Compare the content — do not just test whether
  the first character is `@`.** That shortcut is wrong in both directions: a description
  that legitimately opens with an `@user` mention (valid link syntax here, and a shape the
  sample may well have taught) is condemned as a failure, while a file that was readable but
  empty passes with an empty body. A mismatch means the body never arrived.
- **Repair the cause before repeating the mechanism.** The only reason the send failed is
  that the file could not be read, and that is still true at repair time — so re-issuing
  `az repos pr update --id <pullRequestId> --description "@<file>"` against the same
  unreadable path writes the literal `@<path>` a second time and reports success. First
  confirm the file exists and is readable (rewrite it if not), then update, then **read back
  and compare again**; if the second comparison also fails, stop and hand the prepared
  description to the user rather than looping. Repair in place either way — never open a
  second pull request.
- **On that update call, pass only `--id` and `--description`.** `az repos pr update` also
  accepts `--status completed|abandoned`, `--auto-complete`, `--bypass-policy`,
  `--delete-source-branch`, `--squash` and `--draft`. Every one of them is an outward action
  the confirmation gate never described, and two of them contradict the skill's own safety
  rails outright, so the create recipe's flag prohibition above applies here unchanged.
- **Compare on the ASCII text, and treat a non-ASCII-only difference as a console artefact,
  not a drop.** The cp1252 caveat below applies to everything `az` writes to a Windows
  console, `-o json` included — no output format exempts the `🤖` footer or a non-ASCII
  diagram glyph from being mangled on the way out, so a comparison that demands byte equality
  will report failures that are not real. A body that never arrived looks nothing like the
  file (it is a bare `@<path>`); a body that arrived intact differs, if at all, only in those
  characters. Where only they differ, confirm in the web UI or through the REST API rather
  than repairing.
- Return the PR URL, subject to the unresolved note above.

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
az repos pr list --source-branch <branch> --status active -o json
```

**Query by source branch alone — do not add `--target-branch`.** The two filters are
ANDed, so narrowing by a target the caller defaulted to wrongly returns nothing and the
skill opens a second pull request for a branch that already has one.

**`-o json` is not optional here.** The table transformer emits only
`ID / Created / Creator / Title / Status / IsDraft / Repository` — **no source or target
branch at all** — so a user whose `az` output default is `table` would hand the skill body a
result that cannot answer the question it was fetched for. This is the same trap the API
fallback recipe below already guards against, on a recipe that needs the target.

Map each result into the normalized entry the skill's Step 2 judges on:

- `url` ← report `pullRequestId`, which is what identifies the pull request to a human here.
  A web URL is not available from this result (see the create recipe's unresolved note above),
  so do not construct one.
- `target` ← `targetRefName` **with the `refs/heads/` prefix stripped**. The API stores and
  returns a full ref while the skill body holds a plain branch name, so an unstripped value
  never compares equal and every existing pull request reads as going to a *different*
  target — which turns the same-target duplicate stop into a question, silently, on every run.
- `from_fork` ← true when the pull request's `forkSource` is present. **Azure Repos does
  support forks and cross-fork pull requests** — `GitPullRequest` carries a `forkSource` and
  `GitRepository` an `isFork` — so this is not a GitHub-only case, and a fork pull request
  sharing a branch name would otherwise hard-stop the run as a duplicate of somebody else's
  work. Do **not** test `repository.id` instead: that field names the repository of the
  pull request's *target* branch, which for a cross-fork pull request is this repository,
  so the test would never fire for the case it exists to catch.

**Report only pull requests in this repository.** Passing neither `--repository` nor `--org`
leaves both to git detection, and when the repository does not resolve the extension does not
error — it lists the whole *project*'s pull requests instead (the same widening the API
fallback below documents). A same-named branch in a sibling repository would then read as a
duplicate and hard-stop the run, so drop any result whose `repository.name` is not this
repository's. Take that name from the git remote — it is the last path segment of
`git remote get-url origin`, with any trailing `.git` stripped — since nothing else in the
open-pr flow surfaces it.

### Add label (opt-in, best-effort)

The `ai-assisted` label is **off by default** — add it only when the invoking
request explicitly opted in (see the skill's Step 3, under "AI-provenance
markers"). When opted in,
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
  **The body is truncated, though, so this read teaches shape and not length.**
  Measured 2026-09-03 on a repository whose merged pull requests run long:
  7 of 18 bodies came back at exactly 3,003 characters, each ending in an ellipsis.
  A length range derived from this probe is therefore a lower bound and never a ceiling.
  Do not hand it onward as a budget — say the sample could not teach length,
  rather than reporting a range as though it were one.
- **Author** — `%an`, ahead of a `%x1f` unit separator, so each record reads
  *author*, `0x1f`, *subject*, newline, *body*. It is the identity **the organisation
  directory holds**, not the one in the contributor's `git config`: those routinely
  differ in both spelling and word order, which is why the skill matches a token rather
  than a whole name, and `-i` handles the casing half of that and nothing more. Carry
  the author through rather than dropping it — a sample can be dominated by one person
  or by automation, and that is only visible if the author is in front of you.
- **Where `<token>` comes from, since this platform has no identity lookup to ask.**
  Take it from `git config user.name` (a distinctive word from it, per the skill's
  Step 3) — and expect it to be imprecise, which the skill already says to expect. Two
  properties of `--author` make it more so, and both widen the sample rather than
  narrowing it: git matches the pattern against the whole `Name <email>` line, so a
  token that also appears in an email domain matches every colleague at that domain;
  and the pattern is a regular expression, so `.` and `+` match more than themselves
  while an unbalanced `[` aborts the read with exit 128. Pick a plain alphabetic token,
  and read the authors that come back rather than trusting the filter.
- **An empty result is indistinguishable from a failed filter here.** A `git log` whose
  `--author` matches nobody prints nothing and exits **0**, exactly like a repository
  with no history. Git offers no way to tell them apart, so the skill's "confirm the
  query ran before reading emptiness as history" cannot be satisfied on this platform by
  exit status. Confirm it the only way available: re-run without `--author` — if that
  yields records, the filter is what emptied the sample, not the history.
- **`%x1e`** is a record separator, and it is load-bearing: descriptions are multi-line,
  so without a delimiter nothing distinguishes a body's continuation line from the next
  commit's subject. It is emitted *before* each record, so the first field is empty.
- **`origin/<default-branch>`, never a bare local name** — a local branch of the same
  name is routinely behind the remote and reading it fails *silently* with a stale
  sample. This applies to `git log` only: the API recipes below take a bare branch name,
  which the extension normalises to `refs/heads/<name>` for you. Give them the bare name
  for consistency with the rest of this file, not because a prefixed one would fail —
  the normalisation is idempotent, so `refs/heads/main` and `main` behave identically
  there, and an executor who is told otherwise will build on a false premise the next
  time it matters.

**Not every repository yields markers.** Completion strategy is a per-repo, per-branch
policy, and a rebase-and-fast-forward completion writes no merge commit at all — that
is a healthy configuration, not a rewritten history. A no-fast-forward policy also
mixes the source branch's own commits into the range, so the marker count can be a
small fraction of `-n`. Where the markers do not amount to a **usable sample** — the skill's
Step 3 defines that, and deliberately sets no number — say so and use the API fallback below
rather than reporting "no history".

### List merged pull requests (API fallback, for a marker-less repository)

```
az repos pr list --status completed --top 100 -o json
```

Needed only where the git read above did not yield a usable sample. Each result carries both
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
- **`description` comes back truncated at 400 characters**, cut mid-word — measured 2026-09-03.
  So for anything length-related this fallback is worse than the git read above, not better:
  it teaches the body's opening shape and nothing about its extent.
  Neither probe can teach length on this platform; the Body note in the git section above owns that point.
- The window here (`--top`) and the git window (`-n`) are different sizes; report which
  one the sample came from.

### Diagram form

Azure DevOps does **not** reliably render Mermaid in a pull request description, so a diagram
here is a fenced **plain-ASCII** one — boxes, arrows, and `+ - | > v` glyphs, which survive an
encoding downgrade as well as a font change. Two constraints come with it, both from this
file's create recipe: the description travels through the UTF-8 temp file described there, and
it is subject to the description limit stated there, which the platform *rejects* rather than
truncates — so a diagram that pushes a description past it fails the create after the human
has already confirmed. The figure is stated in the create recipe and only there; check the
length against it before offering a large diagram.

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
az repos show --repository <name> --query id -o tsv
```

**`-o tsv` is not optional.** Under the default JSON formatter `--query id` emits the GUID
*as a JSON string*, quotes included — `"7f3a…"` — while the PR's `repository.id` comes back
bare. A raw compare of the two therefore never matches, so every legitimate pull request is
condemned as belonging to another repository and `resolve-pr-comments` stops before it starts.
`-o tsv` returns the bare value; if you read it some other way, strip the surrounding quotes
and compare case-insensitively before deciding.

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
