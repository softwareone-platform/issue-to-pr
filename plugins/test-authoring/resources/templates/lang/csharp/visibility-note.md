---
description: C# / .NET language baseline for `{{VISIBILITY_NOTE}}` placeholder content in `rules/sut-analysis.md`.
fills_placeholder:
  - "{{VISIBILITY_NOTE}}"
template: rules/sut-analysis.md
---

# C# / .NET — Visibility Note Baseline

Bootstrap (shared-tier2 subagent) uses this as the language-specific baseline when filling `{{VISIBILITY_NOTE}}` in `.claude/rules/tests/sut-analysis.md`.

> **Style note** (applies to every language's `visibility-note.md`): this fragment's content is spliced into the sentence "Check visibility for tests — <fragment>" in `sut-analysis.md`. Start the content with lowercase and omit a trailing period so the splice reads naturally.

if the SUT is an `internal` class, verify the source project has `[InternalsVisibleTo("<test-project>")]`. If missing, note it in the result so the caller can inform the user.
