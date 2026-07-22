---
description: C# / .NET language baseline for `{{PROJECT_WIDE_RULES}}` placeholder content in `rules/test-rules.md`.
fills_placeholder:
  - "{{PROJECT_WIDE_RULES}}"
template: rules/test-rules.md
---

# C# / .NET — Project-wide Test Rules Baseline

Bootstrap (shared-tier2 subagent) uses this as the language-specific baseline when filling `{{PROJECT_WIDE_RULES}}` in `.claude/rules/tests/test-rules.md`.
Extend or override based on actual Step 1.4 sibling observations — sibling code is always the source of truth.

- **xUnit** with `[Fact]` and `[Theory]`
- **FluentAssertions** for assertions
- File-scoped namespaces
- `var` for local variables
- 4-space indentation
- No `Async` suffix on method names
- Inline comments start with lowercase
- `CancellationToken.None` for cancellation tokens in tests
