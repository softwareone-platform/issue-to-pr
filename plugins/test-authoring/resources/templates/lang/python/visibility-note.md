---
description: Python language baseline for `{{VISIBILITY_NOTE}}` placeholder content in `rules/sut-analysis.md`.
fills_placeholder:
  - "{{VISIBILITY_NOTE}}"
template: rules/sut-analysis.md
---

# Python — Visibility Note Baseline

Bootstrap (shared-tier2 subagent) uses this as the language-specific baseline when filling `{{VISIBILITY_NOTE}}` in `.claude/rules/tests/sut-analysis.md`.

> **Style note** (applies to every language's `visibility-note.md`): this fragment's content is spliced into the sentence "Check visibility for tests — <fragment>" in `sut-analysis.md`. Start the content with lowercase and omit a trailing period so the splice reads naturally.

confirm tests can import the module — check that the parent package's `__init__.py` exposes the symbol (or that the test sits within the package tree so private names starting with `_` remain importable from within-package). Python has no language-level visibility modifier; the leading-underscore convention signals intent but does not block import. If the SUT lives in a folder pytest is configured to ignore (check `pytest.ini` / `pyproject.toml` `--ignore=...` or `[tool.pytest.ini_options].testpaths`), flag this — the target may be deliberately untested (e.g., ops-only scripts)
