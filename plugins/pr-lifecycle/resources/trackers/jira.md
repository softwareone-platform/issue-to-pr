# Tracker adapter — Jira

Reference doc for how `open-pr` derives the ticket id and ticket link when the
issue tracker is **Jira**. The skill body routes the ticket-link content through
this adapter, so no Jira-specific id-regex or URL parsing lives in the skill body.

The PR platform (Azure DevOps / GitHub) and the tracker (Jira / GitHub Issues)
are **orthogonal** — Jira can back a PR on either platform.

## Ticket-id extraction

- Match a Jira key with `[A-Z][A-Z0-9]+-\d+`, **case-sensitively**, typically from the
  branch name. Case is what keeps this pattern honest: matched case-insensitively it
  swallows ordinary branch names (`patch-1`, `electron-41-eol`) and manufactures a key
  out of a slug word. Scan for *every* match, not the first — the next rule needs to know
  whether a second, different key exists.
- **The link needs the uppercase key** (e.g. `ACME-12345`) — that is Jira's own
  canonical form, and it is the one thing about the key this adapter decides.
- **How the key is written in the *title* is not this adapter's call.** Bracketed,
  bare with a colon, prefixed by a Conventional Commits type, lower case, upper case,
  or absent altogether are all real conventions in real repos, and which one applies
  is what Step 3 learns from previous PRs. Hand Step 3 the key and let the sample
  decide how it appears. With nothing learned, use the key as the tracker records it
  and add no bracket, no case change, and no marker of your own.
- Two or more *different* ticket keys → ask which, rather than silently taking
  the first.
- No key found → omit the Jira link line, and title it however this repo titles
  ticket-less PRs (Step 3's learned convention). Where that history yielded
  nothing, the title is the summary alone — introduce no marker of your own.

## Ticket link

- Format: `https://<jira_base_url>/browse/<KEY>` with the **uppercase** key
  (e.g. `https://acme.atlassian.net/browse/ACME-12345`).
- Place it as the **first line** of the description so Azure DevOps auto-links it.
- Omit the whole line only when there is no ticket.

## Resolving the Jira base URL

The base URL cannot be inferred from a Jira key, so resolve it in this order:

1. `.claude/pr-lifecycle.json` (gitignored, optional) `jira_base_url` field.
2. else Atlassian MCP, if available.
3. else prompt the user once, then reuse the answer for the run.

Placeholder example used throughout: base URL `acme.atlassian.net`, key `ACME-`.
