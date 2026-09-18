# tools

Pre-publish gates for this marketplace. Standard library only, no `pip install`.

```
python tools/check.py        # run the gates against the working tree
python tools/selfcheck.py    # known-answer cases for the gates themselves
```

Every gate here replaced a prose instruction that someone had to remember and run by hand. They are mechanical because they are all counting and string comparison, which is the part of the work an executor is least reliable at; anything requiring judgement stays in prose deliberately.

| Gate | What it catches |
|---|---|
| `json` | A manifest, registry or eval set that does not parse. A malformed step registry silently resurrects a deleted step. |
| `frontmatter` | A skill with no `name` or `description`, or a name that disagrees with its directory. |
| `descriptions` | A skill or agent description over the Agent Skills specification's 1,024-character limit. Counted in characters, which is why this does not shell out to `skills-ref` — that validator reads the file with no encoding and counts bytes on a cp1252 Windows locale, inflating every em-dash into two phantom characters. |
| `versions` | A plugin changed against the published tree but still carrying the version already published. The install cache is keyed by version, so that change reaches nobody while the push still looks successful. |
| `manifest-sync` | A plugin whose `plugin.json` version disagrees with its `marketplace.json` entry. |
| `leaks` | A URL host outside the allowlist, a ticket-shaped token whose prefix is not a known placeholder, or an address that is not a `noreply` form. This repository is public. |

## How the gates are tested

`selfcheck.py` plants exactly one defect per gate and asserts two things: that the gate reports it, and that **no other gate does**. Sole detection is what makes the mutation test meaningful — remove a gate and its case becomes invisible, so the suite goes red.

The mutation test is not decorative. It has already found a real hole: the version assertions originally called the gate function directly rather than through the registry, so disabling the registered gate left the suite green. The fix was to route them through `GATES` and add a fixture with a real git history.

Two exemptions are pinned by their own case, so a later tightening cannot quietly remove them: a URL host with no dot is prose placeholder syntax (`https://host/path`), and `git@<host>` is the universal SSH user for a git remote rather than an address.

## What the version gate compares against

`ITPR_PUBLISHED_REF` names the already-published commit. It defaults to `origin/main`, which is right for a local run and for a pull request whose base is `main`. It is wrong on a push to `main`, because by then that ref points at the commit being pushed and the comparison reports nothing changed — so the workflow overrides it with the push's own before-SHA. `HEAD~1` is not a substitute: a push carrying several commits would hide any plugin changed in all but the last of them, which is the exact case the gate exists to catch.

When the ref cannot be resolved the gate declines and **says so**, and the summary line counts the skip. A gate that skips quietly reads exactly like a gate that passed, which is how a fallback path hides for months.

## Where the enforcement actually is

CI (`.github/workflows/checks.yml`) runs both files, but this repository publishes by direct push to `main`, so CI reports *after* the push has landed. The gate that can stop a bad push is the hook:

```
git config core.hooksPath .githooks     # once per clone
git push --no-verify                    # deliberate bypass
```
