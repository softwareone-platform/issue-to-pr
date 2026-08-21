# Tracker adapter — Jira

Reference doc for how `open-pr` derives the ticket id and ticket link when the
issue tracker is **Jira**. The skill body routes the ticket-link content through
this adapter, so no Jira-specific id-regex or URL parsing lives in the skill body.

The PR platform (Azure DevOps / GitHub) and the tracker (Jira / GitHub Issues)
are **orthogonal** — Jira can back a PR on either platform.

## Ticket-id extraction

- Match a Jira key with `[A-Z][A-Z0-9]+-\d+` (case-insensitive first match),
  typically from the branch name.
- **Normalise case twice** from that one value:
  - lowercase for the PR title (e.g. `[acme-12345]`),
  - uppercase for the Jira URL (e.g. `ACME-12345`).
  Never reuse one casing for both.
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
