# Tracker adapter — GitHub Issues

Reference doc for how `open-pr` derives the ticket id and ticket link when the
issue tracker is **GitHub Issues**. The skill body routes the ticket-link content
through this adapter, so no tracker-specific parsing lives in the skill body.

This is the **default tracker** when the remote is a GitHub remote and there is
no Jira configuration — zero-config on GitHub.

The PR platform (Azure DevOps / GitHub) and the tracker (Jira / GitHub Issues)
are **orthogonal**, though GitHub Issues is most natural on a GitHub remote
(same-repo auto-linking depends on it).

## Ticket-id extraction

- A GitHub issue is written `#<n>` in text, but `#` is rarely used in branch names
  (and is a shell-comment / URL-fragment character, so unreliable there) — so
  extract the bare number `<n>` from an **issue-shaped** branch form
  (`issue-123`, `issue/123`, `gh-123`, or GitHub's own `123-<slug>` create-branch
  form), or take it from the caller, then render it as `#<n>`.
- **Be conservative.** Do not grab a number that is plainly a version / sprint /
  date (`hotfix-2024`, `sprint-42`, `backup-20240703`). If the branch has no clearly
  issue-shaped ref, or more than one candidate, **ask rather than guess** — a wrong
  `#<n>` auto-links to an unrelated issue or PR (GitHub shares one number series).
- No issue number found → omit the link, and title it however this repo titles
  ticket-less PRs (Step 3's learned convention). Where that history yielded
  nothing, the title is the summary alone — introduce no marker of your own.

## Ticket link

- Format: `#<n>` — GitHub auto-links a same-repo issue reference, so no base URL
  and no full URL are needed.
- Use `#<n>` both in the title (in place of the Jira `[acme-xxxxx]` bracket form)
  and in the description.
- There is **no base URL** to resolve for this tracker.
