# Generated Conventions — Generation Schemas

Read this file during Step 3.2. It carries the recipe for every file setup-test-context generates.
These are analysis-derived, not template-filled: there is no template to copy, so write each one
directly from the Step 1 analysis. They all live under `.claude/conventions/tests/`.

**Recipes describe a discovery procedure — they do not prescribe structure and they carry no worked
example.** The self-check: if a recipe needs an example before it makes sense, it has drifted into
specifying content instead of describing behaviour. The line to hold is **style versus mechanism** —
how to find out what this repo does, never what a repo's tests ought to look like.

The frontmatter shown below is what each generated file must carry — a `description` and, where the file is scoped to particular paths, a `paths` list. Generated conventions carry no version field: the plugin keeps no per-run state, so there is nothing to compare a version against.

`{{SRC_GLOB}}` and `{{TEST_GLOB}}` in the frontmatter below are the only placeholders left in this
file — substitute the values Step 1.3 resolved (e.g. `src/**/*.cs`, `tests/**/*.cs`) as you write.

## No language baselines

The plugin ships **no per-language baseline files**, and no placeholder is filled from one. What a
repo's tests should look like — framework, mocking library, assertion style, naming, layout — comes
from that repo's own tests, or is reported as unknown.

Why, precisely:

- **A style baseline is an assumption about someone else's codebase.** The baselines this plugin used
  to ship stated one organisation's preferences (assertion library, comment casing, an `Async`-suffix
  rule, a package-name-to-folder prefix) as mandatory rules. Shipped to a repo that does not follow
  them, they present a convention the code contradicts as established.
- **Priming.** A style example visible while a subagent fills a template competes with the siblings it
  is supposed to be reading.

The line is between **style** and **mechanism**. Language and toolchain *mechanics* — how an access
grant is declared, where a runner's collection config lives, how a link-install resolves to a path —
are facts a sibling test can never reveal, because they live outside the test file. Those stay, written
language-neutrally as *what to check*, in `rules/sut-analysis.md`. What must not ship is a prescription
of how this repo's tests ought to look.

Concretely: templates carry no language-specific style example **in a `{{PLACEHOLDER}}` fill or its
HTML-comment guidance**. Illustrative syntax elsewhere in a rule's prose (naming a runner's skip
attribute, or a filter flag) is fine — it teaches the rule, it does not fill a value.

When observation yields nothing, the correct output is a **report**, not an inferred default — see
`rules/test-writer-rules.md` → Fallback Chain.

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
- **Test structure** — directory tree for each test project, with an example of how a feature is organised. Note mirroring style (mirror source vs scenario-based) and file organisation (flat vs subfolder-per-SUT).
- **Naming conventions** — source file naming patterns and test file naming patterns
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

