---
name: setup-test-context
description: >
  Analyse the current repo and cache its test profile as one or two convention files under
  `.claude/conventions/tests/`, so the plugin's other skills skip re-deriving it every run.
  Optional: every test skill works without it. Works for any language with a detectable test
  framework (C#, Python, TypeScript, Go, Java, etc.) — auto-detects language and derives every
  convention from the repo's own tests, never a language baseline. Re-running is the refresh:
  it re-analyses and rewrites every file it manages.
  Trigger phrases: "setup test context", "initialise test conventions", "set up the test plugin",
  "set up tests for my Python repo", "scaffold test conventions for a TypeScript project",
  "cache the test conventions for this repo", "refresh the generated test conventions".
---

# Setup Test Context

You are the setup orchestrator for the `test-authoring` plugin. Your job is to **analyse this repository** and cache what analysis found as **per-repo conventions**, so the plugin's other skills do not re-derive the same profile on every run.

You write those conventions and nothing else. The rule books the agents obey (`test-rules.md`, `test-writer-rules.md`, `fix-protocol.md`, `sut-analysis.md`, the `common-*` files, `scope-resolution.md`) ship with the plugin and are read from there directly — they carry no repo-specific value, so copying them into a repo would only create a second copy to go stale. Agents, skills, and the status legend are likewise plugin-bundled.

## Pre-existing files at managed paths

The skill keeps **no state between runs** — no manifest, no recorded hashes. It knows only the fixed
set of paths *this version* writes. So a file already sitting at one of those paths is simply
**existing**: it is overwritten (§2.1). A file under
`.claude/{conventions,rules,shared}/tests/` that is *not* in this version's write set is **reported and
left alone** — never deleted, because without state the skill cannot tell its own retired output from
something you wrote yourself. A repo set up by an older version has a populated
`.claude/rules/tests/` and a `scope-resolution.md`; those are all unmanaged now, and the report is
where you will see them.

**There is no undo.** Re-running **is** the refresh, and an overwritten file is gone. Do not count on
git: §4.5a gitignores that path, so an untracked file cannot be staged at all (`git add` on it silently
does nothing). The one exception is a repo that committed these files before adopting the ignore rule
— §4.5b detects exactly that case — where the previous content is in `HEAD` and `git restore` recovers
it.

The protection that always applies is the §2.1 write list: it labels every target `NEW` or `OVERWRITE`
*before* anything is written. If a file you hand-tuned is marked `OVERWRITE`, copy it out then, or
answer No.

That is deliberate. These are generated artifacts, not documents you maintain — with one or two files
listed up front, a copy-out is cheaper than a backup mechanism, and the mechanism carried its own
hazard (two runs stamping the same folder name and the second destroying the first's only copy).

After a plugin upgrade, prefer a **clean** re-setup: delete `.claude/{conventions,rules,shared}/tests/`
outright (which also removes the rule-book copies, `scope-resolution.md`, the `README.md`, and the
`.setup-manifest.json` that older versions left behind), then run. Nothing is then left behind that
this version no longer writes.

## Supporting assets

Located relative to this skill's base directory:

- **`<plugin-root>/resources/templates/{rules,shared}/`** — the 9 rule books the plugin's agents read at runtime. **This skill does not write, fill, or copy them**; they are listed here only so you can see they are accounted for.
- **`<plugin-root>/resources/static/status-legend.md`** — plugin-internal, never written per-repo.
- **Conventions have no templates** — both conventions files are generated from Step 1 analysis per `references/generated-conventions.md`.
- **`references/`** — the detection recipes (`analysis.md`) and the generation schemas (`generated-conventions.md`). Loaded on demand during the relevant step.

## Output overview

One or two files, in one directory, and the set does not vary by test type:
- `.claude/conventions/tests/project-architecture.md` — always
- `.claude/conventions/tests/common-verification-patterns.md` — only when §1.4 found at least one **qualifying** pattern (layer-common **or** cross-layer-common; `generated-conventions.md` is the single definition)

Per-type `{type}-test-conventions.md` are **not** written: writers derive those from the nearest sibling at runtime.

setup-test-context does NOT write any of: rule books, agents, commands, skills, status legend — all plugin-bundled and read from there. It writes no README either: every other output exists because a *skill* reads it, and a provenance note nothing reads is not worth a file.

## Design principles

- **Re-runnability**: safely re-run; every existing file at a target path is rewritten (§2.1).
- **Managed files are generated artifacts, not user documents**: re-running setup IS the refresh. Every file this run will overwrite is listed in the §2.2 confirmation block — never silently — and that gate, not a backup, is where a hand-edit is protected.
- **Defensive reading of CLAUDE.md**: never modified; treated as a hint, not source of truth.

---

## Step 1 — Analyse the Repository

Read `references/analysis.md` before starting this step. **Work through them in the order below, which
is not the order they are numbered in** — the numbers are stable identifiers other documents cite, and
§1.4 consumes what §1.6 and §1.7 produce:

1. §1.1 — read CLAUDE.md as hints only
2. §1.2 — detect language and frameworks
3. §1.3 — map project structure (source dirs, test dirs, mirroring pattern, shared test project)
4. §1.7 — classify each test project (combo-cell matrix). **Run it here, not last**: it needs only §1.3, and it tells you which projects are worth sampling.
   - **No test project at all, or no 🟩 project** → skip §1.6 and §1.4 entirely and go straight to §2.1's zero-supported exit. Sampling a repo you cannot write for is wasted work, and §1.3's "read 3–5 existing test files" and §1.4's "minimum of 8 files" have no meaning when there are none.
5. §1.6 — identify architectural patterns. **Before §1.4**, which maps each sampled file to one of the layers this step names.
6. §1.4 — learn test conventions via layered sampling, over the 🟩 projects only

Order matters here, it is not tidiness: §1.4 buckets by `(layer, test type)` and its layer-common threshold is "≥2 samples within a layer". Run without §1.6's layers and every repo silently falls through to the no-layer branch (">50% of samples"), which discards patterns that are strong inside one layer and rare overall — a different `common-verification-patterns.md`, with no error to show for it.

Proceed to Step 2 with the completed analysis.

---

## Step 2 — Confirm Analysis with User

### 2.1 Present findings

**Zero supported types — stop here.** If Step 1.7 classified no project 🟩 (a Gherkin-only repo, or no test project at all), do not render the write list: report that this repo has no test project the plugin can author for, and list each skipped project with its reason. **Still run the unmanaged-files report below** before exiting — a repo an older version set up has leftovers, and this is the only run that would have shown them. Then exit without writing.

Render the findings table with the columns: language, test framework, mocking library, build tool, and a per-test-project table showing path / type / supported flag / infrastructure summary. Add a **CLAUDE.md drift** section listing every claim §1.1/§1.2 found the codebase contradicting, or say there was none — Step 5's CLAUDE.md follow-up is conditioned on this and fires only if it appears here. Then render the write list.

**Resolve each target path's state first — this is the step that makes the confirmation gate mean
something.** For every path this run will write, check whether it already exists (Glob or a bounded
Read) and label it `NEW` or `OVERWRITE`. Do not render the list from this document's example: build it
from what you found on disk. Since there is no backup and no undo, an `OVERWRITE` line is the **only**
warning the user gets that content is about to be destroyed — a canned list that always looks the same
would silently hand a hand-tuned file to the next write.

```
Files setup-test-context will write:

  NEW        .claude/conventions/tests/project-architecture.md
  OVERWRITE  .claude/conventions/tests/common-verification-patterns.md   <- current content is lost

Not generated this run:
  common-verification-patterns.md -- no qualifying pattern detected (layer-common or cross-layer)
  (omit this section when nothing was skipped)

Not written -- read from the plugin at runtime:
  the 9 rule books (.claude/rules/tests/* and scope-resolution.md in earlier versions),
  the status legend, every agent and skill.
  Per-type {type}-test-conventions.md are not written either -- writers derive those
  from the nearest sibling at runtime.
```

State each `OVERWRITE` path on its own line. If there are none, say so — "all targets are new, nothing
will be lost" is worth one line, because it tells the user they can answer Yes without checking.

### What happens to a path that already exists

It is overwritten, with no undo. There is no pristine / user-modified distinction (that needed recorded
hashes, which the skill does not keep) and no per-file prompt — with one or two paths, the labelled
list above plus the §2.2 batch confirmation carry the same information without asking twice.

### Unmanaged files at managed paths (report only)

List any file under `.claude/{conventions,rules,shared}/tests/` that is **not** among this run's write
targets, and say plainly that it is not written by this version and will be left untouched. **Include
dotfiles** — a repo set up by an older version still has `.setup-manifest.json` there, and a plain
listing hides it. Do not
delete it and do not offer to — without recorded state, a leftover from a retired template and a file
you wrote by hand are indistinguishable, and deleting the wrong one is unrecoverable.

This report covers **files that exist on disk**. A conditional file that was not generated this run is
not one of them — it has no file to report. Name that skip in the write list's "Not generated this run"
section instead, so a mis-detection is still visible. The one case where
`common-verification-patterns.md` *does* appear here is a repo where an earlier run generated it and
this run's detection found no qualifying pattern. Do not treat that as routine: it is on disk, outside
this run's write set, and left alone — but writer agents consult it whenever it exists, with no notion
of freshness, so it will keep steering every future run. Say so explicitly and recommend deleting it,
because this run's analysis is the evidence that its patterns no longer hold.

Collect the list before reaching the confirmation.

### 2.2 Ask for final confirmation

Ask:
1. Are the test types and Supported flags correct? This is not a formality — the labels you confirm are written into `project-architecture.md`'s test-structure section, and a `hybrid × code-driven` project has **no** default label until you give it one. If the user corrects a label or a flag, apply the correction, re-render §2.1, and ask again; do not proceed on the set they just rejected.
2. Review the `OVERWRITE` lines in §2.1's write list — there is no undo, so copy out anything you hand-tuned before answering — and the unmanaged files that will be left untouched.
3. **Proceed?** (Yes / No)

Single yes/no for the whole set. Proceed to Step 3 only after confirmation.

---

## Step 3 — Write the conventions

Apply all changes based on the confirmed analysis.

### 3.1 Generate the conventions files

Read `references/generated-conventions.md` and write what it specifies:

1. `.claude/conventions/tests/project-architecture.md` — always.
2. `.claude/conventions/tests/common-verification-patterns.md` — only when §1.4's detection yielded at least one qualifying pattern, **as `generated-conventions.md` defines qualifying** (layer-common or cross-layer-common — not cross-layer alone). Decide this **before** rendering §2.1, so the write list the user approves is the set actually written. Otherwise skip it and name the skip in the write list; a skip is not a failure.

**Write them yourself — no subagent.** The analysis these are generated from already sits in your
context, so handing it to a subagent would copy it rather than save it, and two files offer no
parallelism to win. Keep a write log as you go — one line per file actually written. It is the **list of paths** Step 4
checks and Step 5 renders; it is not evidence that any of them exist or are correct, and Step 4 must
still touch the filesystem to establish that.

---

## Step 4 — Verify

After all writes:

1. Confirm every file exists.
2. **Frontmatter check (bounded read — never re-read whole files into the main context)**: for each file in this run's write log — every generated conventions file carries frontmatter, and the log is the authority on which were actually written (a skipped conditional is not in it) — read only the opening frontmatter block — a bounded read of the first ~20 lines (Read with a line limit, or `sed -n '1,20p'`). Assert the block closes with `---` inside that bound **and** carries a non-empty `description`; either failing is a verification failure. Whole-file content checks belong to item 3's mechanical sweep; re-reading every generated file would pull the entire rule set into the main context — the exact bloat the per-type skills' lazy loading removed. (Unresolved `{{PLACEHOLDER}}` tokens and leaked HTML comments are item 3's greps — do not re-check them by reading file bodies.)
3. **Mechanical grep sweep** — run against the files written THIS run, never the whole directory: unmanaged files (§2.1) are outside this run's contract, and their content (e.g. quoted `{{ }}` template syntax) must not fail verification.
   ```bash
   # <written-files…> = every path in this run's write log
   grep -n "{{" <written-files…>
   ```
   It MUST return no output. A match is a verification failure, and this is the check that earns its
   keep: a leaked `{{SRC_GLOB}}` reaches a writer as a literal token and there is nothing downstream
   that would notice. (There is no HTML-comment sweep any more — that guarded template fill-guidance
   leaking through a copy, and nothing is copied now; keeping it would only reject a legitimate comment
   in a generated file.)
4. **Path plausibility spot-check** — `project-architecture.md` is mostly directory trees, and a tree naming a directory that does not exist is the failure this catches. Take the source and test root paths from **your own §1.3 analysis** (not by re-reading the generated file — item 2's prohibition still stands) and confirm each with Glob. A miss is a warning (🟨), not a failure: it usually means the tree drifted from what you observed, which is worth reporting but not worth discarding the run over.
5. **On failure**: **delete every file in this run's write log, then report loudly and stop** — name
   the file that failed, quote the failing check, and say the run wrote nothing. Deleting is not a
   rollback (the previous content was not kept and does not come back); it is removal of a known-bad
   artifact. It is the right move because every downstream agent reads
   `.claude/conventions/tests/project-architecture.md` *if present* with no validity check of its
   own — so a file left behind with a leaked `{{SRC_GLOB}}` in it would be consumed silently by every
   later add / update / scan run. Removing it puts the repo in the no-setup state, which every skill in
   this plugin already handles by deriving from siblings. Tell the user that: the run failed, nothing
   was written, the skills still work sibling-driven, and re-running is the fix.
6. **On success**: keep all written files. Do NOT auto-commit.

Render a Verification Results table: one row per check above, each with a status icon and a one-line result. Use 🟩 passed / 🟨 warning / 🟥 failed — those three, from the plugin's `resources/static/status-legend.md`, are the only ones this skill needs, so do not read the legend file for them.

---

## Step 4.5 — Gitignore the per-repo files (user-scope) + migrate already-tracked files

Run this **only after Step 4 reports success** (item 6). If Step 4 failed it deleted this run's output, so there is nothing to ignore and nothing to untrack — skip straight past Step 5 as well and end on the failure report.

setup-test-context's per-repo files are **user-scope** — local, never committed — so a teammate who has not adopted the test-skills plugin never carries generated files in their tree, and there is no PR clutter or merge conflict. The skills run without these files at all — the rules they obey come from the plugin — so user-scope costs only a per-developer setup run, not correctness.

**4.5a — Add the ignore line.** Ensure `.gitignore` (at repo root) contains this one line, added only if not already present (newline-safety: if `.gitignore` exists but does not end with a newline, append one first so the new line never concatenates onto the previous; create the file with just this line + newline if it does not exist):
```
.claude/conventions/tests/
```

That is now the only directory this skill writes to. `.claude/rules/tests/`, `.claude/shared/tests/`
and `.claude/backup/` were on this list in earlier versions; nothing writes to any of them now. This
step only *adds* lines and never removes one, so an upgraded repo still carries the old three — leave
them. Removing an entry from someone's `.gitignore` can un-ignore files they still have on disk, and
§2.1's unmanaged-file report reads the directories directly, so it surfaces leftovers regardless of
what `.gitignore` says. If the report named some, tell the user they can delete both the leftovers and
the stale ignore lines by hand.

**4.5b — Untrack anything already committed (migration).** `.gitignore` does not affect files git already tracks. Run `git ls-files .claude/conventions/tests` — **this directory only**. Earlier versions also wrote `.claude/rules/tests` and `.claude/shared/tests`, but this version neither writes nor manages them: §2.1 reports them and leaves them alone precisely because it cannot tell its own retired output from something you wrote, and it would be incoherent to then hand you a command that removes them from every teammate's working copy on the next pull. If you want those untracked too, that is your call to make deliberately. If it lists any files, **print this notice; do NOT run the command automatically** — then continue to Step 5 (this skill never auto-commits; untracking is a committable change the user owns and reviews):
```
These per-repo test files are already tracked by git and will keep showing in PRs until untracked:
  <list the files>
To make them user-scope, run this and commit the removal as its own change:
  git rm -r --cached .claude/conventions/tests
Heads-up: once that commit is pushed, teammates' working copies are deleted on pull — they re-create them by running setup-test-context themselves.
```
If `git ls-files` returns nothing (fresh setup, or already untracked) → say nothing; there is nothing to migrate.

---

## Step 5 — Report

**Only on the Step 4 success path.** If Step 4 failed, its own item 5 already reported the failure and
deleted this run's output — do not also render the report below, which would list files that no longer
exist and invite the user to try skills against them.

### Repo profile recap

One short block, so the user can see what the run concluded without opening the generated files:
language, test framework, mocking library, build tool, one line per test project (path, confirmed type,
🟩/🟨), and **Files written** — which counts only what this run actually wrote, one or two conventions
files. If §2.1 reported CLAUDE.md drift, repeat the one-line summary here so next step 4 has a referent.

### File index

```
Generated files (per-repo, managed by setup-test-context):

Conventions (.claude/conventions/tests/):
  - project-architecture.md
  - common-verification-patterns.md (if applicable)
  (per-type {type}-test-conventions.md not written -- sibling-derived at runtime)

Plugin-bundled (NOT written here -- read from the test-authoring plugin at runtime):
  - 9 rule books (resources/templates/{rules,shared}/)
  - status-legend.md (resources/static/)
  - 8 agents (test-authoring: namespace)
  - 6 skills (setup-test-context, scan-test-gaps, add-* / update-*)
```

### Recommended next steps

1. Review the generated per-repo files to ensure they match your repo.
2. Try `/test-authoring:scan-test-gaps` to test gap scanning on a small area.
3. Try `/test-authoring:add-unit-test ComponentName` on a small change to verify the add workflow.
4. (If CLAUDE.md drift was reported) Update CLAUDE.md to reflect the current codebase — setup-test-context did not modify CLAUDE.md.
5. To remove this scaffolding later, delete `.claude/conventions/tests/`, plus the line this skill added to `.gitignore` (§4.5a). An upgraded repo may also hold `.claude/rules/tests/`, `.claude/shared/tests/` and `.claude/backup/` from earlier versions — those are safe to delete too.

---
