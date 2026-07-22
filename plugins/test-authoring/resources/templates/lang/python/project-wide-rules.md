---
description: Python language baseline for `{{PROJECT_WIDE_RULES}}` placeholder content in `rules/test-rules.md`.
fills_placeholder:
  - "{{PROJECT_WIDE_RULES}}"
template: rules/test-rules.md
---

# Python — Project-wide Test Rules Baseline

Bootstrap (shared-tier2 subagent) uses this as the language-specific baseline when filling `{{PROJECT_WIDE_RULES}}` in `.claude/rules/tests/test-rules.md`.
Extend or override based on actual Step 1.4 sibling observations — sibling code is always the source of truth.

- **pytest** with `def test_*()` functions (and optional `class TestX:` grouping for related tests)
- **`unittest.mock`** for mocking (`MagicMock`, `patch` as context manager or decorator)
- **Plain `assert`** statements (pytest rewrites assertions for rich failure messages — no third-party assertion library needed)
- **`freezegun`** for time-sensitive tests where the repo uses it
- snake_case for files (`test_<module>.py`) and functions (`test_<scenario>`)
- Per-folder `conftest.py` for shared fixtures; root `conftest.py` for project-wide environment setup
- `@pytest.mark.parametrize` for table-driven test cases
- Each test method commonly carries a one-line docstring (`"""..."""`) describing intent — match sibling style
- Use the formatter / linter configured in the repo (e.g., `ruff`, `black`, `flake8`); do not introduce a different style mid-file
