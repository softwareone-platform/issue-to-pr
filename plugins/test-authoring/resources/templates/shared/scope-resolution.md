---
schema_version: "1.0"
description: Standard procedure for resolving which source files to process. Used by all test skills.
---

# Scope Resolution

Standard procedure for resolving which source files to process. Used by all test skills.

## Mode A — Pending Changes (default, no argument)

Run `git diff` (staged + unstaged) to find all modified/added {{LANGUAGE}} source files under `{{SRC_DIR}}`. Ignore test files, migrations, and generated code.

```bash
git diff HEAD --name-only --diff-filter=ACM -- '{{SRC_GLOB}}'
```

For each changed file, run `git diff HEAD -- <file>` to understand **what** changed.

If no pending changes are found, inform the user and stop.

## Mode B — Explicit Scope (argument or file list)

If the user provides an argument or the caller provides specific source files, **skip git diff** and resolve the scope. Try these in order until one matches:

1. **Directory path** — use if path exists
2. **Component name** (e.g., a feature/module name) — Glob `{{SRC_DIR}}/**/Components/{arg}/**/*` and `{{SRC_DIR}}/**/{arg}/**/*` (adjust to repo conventions)
3. **Class name** — Grep for class/type declaration under `{{SRC_DIR}}`
4. **Method name** (e.g., `ClassName.MethodName`) — split on `.`, find the class file, then pass both the file and method name to the agent
5. **File name** — Glob `{{SRC_DIR}}/**/{arg}`
