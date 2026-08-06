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

**There is no undo.** Re-running **is** the refresh, and an overwritten file is gone — git cannot help
either, because §4.5a gitignores the very path it sits at, so `git add` on it silently does nothing.
The protection is the §2.2 confirmation gate: it names every file this run will overwrite *before*
anything is written. If you hand-tuned one, copy it out at that point, or answer No.

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
- `.claude/conventions/tests/common-verification-patterns.md` — only when Step 1.4 found a qualifying cross-layer pattern

Per-type `{type}-test-conventions.md` are **not** written: writers derive those from the nearest sibling at runtime.

setup-test-context does NOT write any of: rule books, agents, commands, skills, status legend — all plugin-bundled and read from there. It writes no README either: every other output exists because a *skill* reads it, and a provenance note nothing reads is not worth a file.

## Design principles

- **Re-runnability**: safely re-run; every existing file at a target path is rewritten (§2.1).
- **Managed files are generated artifacts, not user documents**: re-running setup IS the refresh. Every file this run will overwrite is listed in the §2.2 confirmation block — never silently — and that gate, not a backup, is where a hand-edit is protected.
- **Defensive reading of CLAUDE.md**: never modified; treated as a hint, not source of truth.

---

## Step 1 — Analyse the Repository

Read `references/analysis.md` before starting this step. Work through §1.1–1.7 in order:

1. §1.1 — read CLAUDE.md as hints only
2. §1.2 — detect language and frameworks
3. §1.3 — map project structure (source dirs, test dirs, mirroring pattern, shared test project)
4. §1.4 — learn test conventions via layered sampling
5. §1.6 — identify architectural patterns
6. §1.7 — classify each test project (combo-cell matrix)

Proceed to Step 2 with the completed analysis.

---

## Step 2 — Confirm Analysis with User

### 2.1 Present findings

**Zero supported types — stop here.** If Step 1.7 classified no project 🟩 (a Gherkin-only repo, or no test project at all), do not render the write list and do not spawn anything: report that this repo has no test project the plugin can author for, list each skipped project with its reason, and exit cleanly without writing.

Render the findings table with the columns: language, test framework, mocking library, build tool, and a per-test-project table showing path / type / supported flag / infrastructure summary. Files to be created / overwritten lists reflect ONLY the per-repo files setup-test-context manages:

```
Files setup-test-context will write (new or refresh):

Conventions (.claude/conventions/tests/):
- project-architecture.md
- common-verification-patterns.md    (if cross-layer pattern detected)
  NOTE: per-type {type}-test-conventions.md are NOT written
  -- writers derive per-type conventions from the nearest sibling at runtime.

Not written -- read from the plugin at runtime:
  the 9 rule books (.claude/rules/tests/* and scope-resolution.md in earlier versions),
  the status legend, every agent and skill.
```

### What happens to a path that already exists

It is overwritten, and the confirmation block says so. There is no pristine / user-modified
distinction (that needed recorded hashes, which the skill does not keep) and no per-file prompt — with
one or two paths, the §2.2 batch confirmation carries the same information without asking twice.

### Unmanaged files at managed paths (report only)

List any file under `.claude/{conventions,rules,shared}/tests/` that is **not** among this run's write
targets, and say plainly that it is not written by this version and will be left untouched. **Include
dotfiles** — a repo set up by an older version still has `.setup-manifest.json` there, and a plain
listing hides it. Do not
delete it and do not offer to — without recorded state, a leftover from a retired template and a file
you wrote by hand are indistinguishable, and deleting the wrong one is unrecoverable.

The conditional convention (`common-verification-patterns.md`) lands here whenever its generation
condition is unmet this run. That is correct: it is simply not written, and the report names it so a
mis-detection is visible rather than silent.

Collect the list before reaching the confirmation.

### 2.2 Ask for final confirmation

Ask:
1. Are the test types and Supported flags correct?
2. Review the two lists from §2.1: files that will be **overwritten** — there is no undo, so copy out anything you hand-tuned before answering — and unmanaged files that will be left untouched.
3. **Proceed?** (Yes / No)

Single yes/no for the whole set. Proceed to Step 3 only after confirmation.

---

## Step 3 — Write the conventions

Apply all changes based on the confirmed analysis.

### 3.1 Generate the conventions files

Read `references/generated-conventions.md` and write what it specifies:

1. `.claude/conventions/tests/project-architecture.md` — always.
2. `.claude/conventions/tests/common-verification-patterns.md` — only when Step 1.4's pattern detection yielded at least one qualifying pattern. Otherwise skip it and name it in the report; a skip is not a failure.

**Write them yourself — no subagent.** The analysis these are generated from already sits in your
context, so handing it to a subagent would copy it rather than save it, and two files offer no
parallelism to win. Keep a write log as you go — one line per file — because every Step 4 check reads from it rather
than re-reading the files, and Step 5 renders it.

---

## Step 4 — Verify

After all writes:

1. Confirm every file exists.
2. **Frontmatter check (bounded read — never re-read whole files into the main context)**: for each written file (both carry frontmatter), read only the opening frontmatter block — a bounded read of the first ~20 lines (Read with a line limit, or `sed -n '1,20p'`). Assert the block closes with `---` inside that bound **and** carries a non-empty `description`; either failing is a verification failure. Whole-file content checks belong to item 3's mechanical sweep; re-reading every generated file would pull the entire rule set into the main context — the exact bloat the per-type skills' lazy loading removed. (Unresolved `{{PLACEHOLDER}}` tokens and leaked HTML comments are item 3's greps — do not re-check them by reading file bodies.)
3. **Mechanical grep sweep** — run against the files written THIS run, never the whole directory: unmanaged files (§2.1) are outside this run's contract, and their content (e.g. quoted `{{ }}` template syntax) must not fail verification.
   ```bash
   # <written-files…> = every path in this run's write log
   grep -n "{{" <written-files…>
   grep -n "<!-- " <written-files…>
   ```
   Both MUST return no output. Any match is a verification failure. This is the check that earns its
   keep: a leaked `{{SRC_GLOB}}` reaches a writer as a literal token.
4. **Path existence check** — extract concrete paths mentioned in generated output, verify with Glob. Missing paths are warnings (🟨), not failures.
5. **On failure**: **report it loudly and stop** — name the failing file, quote the failing check, and
   say plainly that the file is on disk and wrong. Do **not** attempt a rollback: the previous content
   was not kept, and deleting the file instead would leave a repo that looks un-set-up while the user
   believes it is set up. The fix is to correct the cause and re-run — the outputs are regenerable by
   this same skill, which is why no undo is carried.
6. **On success**: keep all written files. Do NOT auto-commit.

Render a Verification Results table: one row per check above, each with its status icon and a one-line result.

---

## Step 4.5 — Gitignore the per-repo files (user-scope) + migrate already-tracked files

Run this **only after Step 4 reports success** (item 6). If Step 4 failed, skip it — a repo whose generated file is known-wrong should not also acquire a `.gitignore` edit before the user has decided what to do.

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

**4.5b — Untrack anything already committed (migration).** `.gitignore` does not affect files git already tracks. Run `git ls-files .claude/conventions/tests .claude/rules/tests .claude/shared/tests`. If it lists any files, **print this notice; do NOT run the command automatically** — then continue to Step 5 (this skill never auto-commits; untracking is a committable change the user owns and reviews):
```
These per-repo test files are already tracked by git and will keep showing in PRs until untracked:
  <list the files>
To make them user-scope, run this and commit the removal as its own change:
  git rm -r --cached .claude/conventions/tests .claude/rules/tests .claude/shared/tests
Heads-up: once that commit is pushed, teammates' working copies are deleted on pull — they re-create them by running setup-test-context themselves.
```
If `git ls-files` returns nothing (fresh setup, or already untracked) → say nothing; there is nothing to migrate.

---

## Step 5 — Report

Render the report below.

### Repo profile recap

**Files written** counts only what this run actually wrote: one or two conventions files.

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
