---
description: Standard procedure for resolving which source files to process. Used by all test skills.
---

# Scope Resolution

Standard procedure for resolving which source files to process. Used by all test skills.

## Mode A — Pending Changes (default, no argument)

Nothing upstream hands you the repo's layout — the reader of this file is the orchestrator itself, so
**detect it first**: the source root(s) and the extension the source files carry, from the project
manifest and the directory tree. Build the pathspec from those two (`<source-root>/**/*.<ext>`) and run:

```bash
git diff HEAD --name-only --diff-filter=ACM -- '<source-pathspec>'
```

That lists every modified or added source file (staged and unstaged). Ignore test files, migrations,
and generated code. Where several source roots exist, or the repo is polyglot, run one pathspec per
root and name the roots you used — widening to the whole tree instead pulls in exactly the files the
line above tells you to ignore.

For each changed file, run `git diff HEAD -- <file>` to understand **what** changed.

If no pending changes are found, inform the user and stop.

## Mode B — Explicit Scope (argument or file list)

If the user provides an argument or the caller provides specific source files, **skip git diff** and resolve the scope. Try these in order until one matches:

1. **Directory path** — use if path exists
2. **Component name** (e.g., a feature/module name) — Glob `<source-root>/**/Components/{arg}/**/*` and `<source-root>/**/{arg}/**/*` (adjust to repo conventions)
3. **Class name** — Grep for class/type declaration under `<source-root>`
4. **Method name** (e.g., `ClassName.MethodName`) — split on `.`, find the class file, then pass both the file and method name to the agent
5. **File name** — Glob `<source-root>/**/{arg}`

`{arg}` above is the user's argument at runtime, not a template placeholder — substitute what they typed.
