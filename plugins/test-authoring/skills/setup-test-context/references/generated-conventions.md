# Generated Conventions — Generation Schemas

Read this file during Step 3.1. It carries the recipe for every file setup-test-context generates.
These are analysis-derived, not template-filled: there is no template to copy, so write each one
directly from the Step 1 analysis. They all live under `.claude/conventions/tests/`.

**Recipes describe a discovery procedure — they do not prescribe structure and they carry no worked
example.** The self-check: if a recipe needs an example before it makes sense, it has drifted into
specifying content instead of describing behaviour. The line to hold is **style versus mechanism** —
how to find out what this repo does, never what a repo's tests ought to look like.

The frontmatter shown below is what each generated file must carry — a `description` and, where the file is scoped to particular paths, a `paths` list. Generated conventions carry no version field: the plugin keeps no per-run state, so there is nothing to compare a version against.

`{{SRC_GLOB}}` and `{{TEST_GLOB}}` in the frontmatter below are the only placeholders left in this
file — substitute the values §1.3 resolved (e.g. `src/**/*.cs`, `tests/**/*.cs`) as you write. `paths:`
is a YAML **list**: where §1.3 found several source or test roots, emit one entry per root rather than
picking one and dropping the rest — the two slots shown below are the single-root case, not a limit.

## No inferred defaults

Every value in a generated file comes from what §1 observed in **this** repo. The plugin ships no
per-language baseline and no style template, so there is nothing to fall back on and nothing to copy:
a style baseline is an assumption about someone else's codebase, and an example visible while you write
competes with the siblings the analysis actually read.

The line is **style versus mechanism**. Language and toolchain *mechanics* — how an access grant is
declared, where a runner's collection config lives — are facts a sibling test cannot reveal, and they
live in the plugin's rule books, not here. What must never be generated is a prescription of how this
repo's tests ought to look.

---

Keep every generated frontmatter block closing within the first 20 lines — Step 4's verification reads only that bounded window,
and a later closing `---` would be mis-read as invalid frontmatter (a false verification failure).

---

## `project-architecture.md`

Frontmatter:
```yaml
---
description: Documents the source and test directory structure, naming conventions, and feature organisation.
paths: ["{{SRC_GLOB}}", "{{TEST_GLOB}}"]
---
```

Content:
- **Source structure** — directory tree from Step 1.3, showing typical feature organisation (e.g., Commands/, Handlers/, Services/ subdirectories)
- **Test structure** — directory tree for each test project, with an example of how a feature is organised. Note mirroring style (mirror source vs scenario-based) and file organisation (flat vs subfolder-per-SUT). Label each project with the **test type the user confirmed in §2.1** (`unit`, `integration`, …), and mark a 🟨-skipped project as such rather than omitting it — a writer that finds an unlisted test project has no way to know it was skipped deliberately.
- **Naming conventions** — source file naming patterns and test file naming patterns. **Where a convention is not uniform, do not collapse it into one rule.** Record what it varies *by* — the observable trait that predicts which form applies (a directory, a test type, how many public entry points the SUT has) — or, if you cannot identify the determinant from the sample, say plainly that it varies and that the sibling decides. A single over-general rule is worse than none: it reads as authoritative, and it is wrong for every area that does not follow it. (Observed in the field: a generated file asserted "method names start with the member under test" for a repo where one directory named tests behaviour-first; the writer read the sibling, disagreed with the cached profile, and was right.)
- **Feature components** — if the source uses a consistent per-feature structure, document the pattern
- **Shared test project** — if Step 1.3 found one, give its path and which test projects reference it. Location only: a writer reads the helper it needs from the sibling that already calls it, so an inventory of utilities here would compete with that sibling and go stale behind it.

---

## `common-verification-patterns.md` — conditional (≥1 qualifying pattern detected)

Generate ONLY if Step 1.4 pattern detection yielded ≥1 "layer common" or "cross-layer common" pattern.

Frontmatter:
```yaml
---
description: Layer-specific and cross-layer recurring verification patterns observed across test types. Writer agents consult this before finalising tests.
paths: ["{{TEST_GLOB}}"]
---
```

Content structure:
- **Cross-reference note** at top:
  > Writer agents: after determining the SUT's layer, read the relevant layer section plus the "General" section. Siblings still take priority if their patterns differ.
- **General (cross-layer) section** — patterns observed across multiple layers and multiple test types
- **Per-layer sections** — use the repo's actual layer naming (Handler, Controller, Service, Repository, Consumer, Worker, etc. as detected in Step 1.6)

Each pattern entry includes:
- Observed frequency across buckets (e.g., "unit handler tests 8/10, integration handler tests 5/7")
- Pattern code extracted from an actual sibling test (NOT invented)
- When to apply (which dependency or SUT trait triggers this pattern)

If repo had no clear layers (layered sampling fallback), include only a "General" section with project-wide patterns.

