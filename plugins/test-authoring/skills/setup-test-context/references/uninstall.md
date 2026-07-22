# Uninstall mode

Disclosed reference for `setup-test-context`. Entered when the first invocation argument is `uninstall`; the install / re-install path never reads this file.

Removes every per-repo file setup-test-context wrote, classified against `.setup-manifest.json` so user-modified files are not silently deleted.

Does NOT touch:
- `CLAUDE.md`.
- User's production code or test code.
- Files inside `.claude/{conventions,rules,shared}/tests/` that are NOT in the manifest (orphans — files this skill did not write, including user-added or pre-existing files). These are reported as orphans.
- The plugin itself (uninstalled by `/plugin uninstall test-authoring`).

## U1 — Locate manifest

1. Try to read `.claude/shared/tests/.setup-manifest.json`.
2. If the file exists:
   - Parse as JSON. On parse failure → print `setup-test-context manifest is malformed JSON. Repair manually or remove and re-run setup.` and exit.
   - Check `manifest_schema_version`. If not `"1.0"` → print `Manifest schema version <N> not supported by this skill version. Upgrade the plugin or remove the manifest manually.` and exit.
   - Continue to U2.
3. If the file does not exist:
   - Print `No setup-test-context manifest found. Nothing to uninstall (this skill never wrote anything here, OR the manifest was deleted manually).` and exit.

## U2 — Classify

For each entry in `manifest.files[]`:

| State | Condition | Default action |
|---|---|---|
| `pristine` | file exists AND sha256 matches | delete |
| `user-modified` | file exists AND sha256 differs | per-file Y/N prompt in U3 |
| `missing` | file does not exist | silently skip |

Hash comparisons normalise line endings (CRLF→LF) before computing SHA-256 — see `references/manifest.md` § SHA-256 calculation. A manifest written by an older plugin version may have hashed raw CRLF bytes; such files one-time classify as user-modified — benign here, since the per-file Y/N gate in U3 still guards deletion.

Then enumerate **orphans**: files present in `.claude/{conventions,rules,shared}/tests/` (recursive) whose path is not in `manifest.files[]` and is not the manifest itself. Orphans are reported but never deleted.

## U3 — Single batch confirmation

Render a confirmation block. Omit any sub-section that has nothing to report.

```
The following will be removed:

  Pristine files (will be deleted):
    .claude/conventions/tests/project-architecture.md
    .claude/conventions/tests/unit-test-conventions.md
    .claude/rules/tests/test-rules.md
    …

  User-modified files (you edited these after install):
    .claude/conventions/tests/<file>.md   [keep / delete?]
    …

  Empty directories that will be removed after file deletion:
    .claude/conventions/tests/
    .claude/rules/tests/
    .claude/shared/tests/

  Manifest itself:
    .claude/shared/tests/.setup-manifest.json

NOT touched:
  CLAUDE.md
  Your test code
  .claude/agents/, .claude/commands/, .claude/skills/   (managed by plugins, not here)
  Orphan files in tests/ namespace not written by setup-test-context:
    <list of orphans, one per line>
  (Empty if no orphans detected.)

Proceed? (Yes / No)
```

For each `user-modified` row, collect a per-file Y/N **before** the final batch Yes/No.

- **No** → print `No changes made.` and exit.
- **Yes** → continue to U4.

## U4 — Execute and report

1. Delete every confirmed file.
2. For each of `.claude/conventions/tests/`, `.claude/rules/tests/`, `.claude/shared/tests/`: if now empty → `rmdir`. Do not rmdir parents (`.claude/conventions/`, etc.) — other plugins may have sibling subdirs.
3. Delete the manifest.
4. Report.

```
Uninstall complete (setup-test-context).

Files removed:
  Conventions:
    .claude/conventions/tests/project-architecture.md
    …
  Rules:
    …
  Shared:
    .claude/shared/tests/scope-resolution.md
    .claude/shared/tests/README.md

Files kept (you chose not to delete):
  .claude/conventions/tests/<file>.md   (user-modified)

Empty directories removed:
  .claude/conventions/tests/
  …

Manifest removed:
  .claude/shared/tests/.setup-manifest.json

NOT touched:
  CLAUDE.md
  Your test code
  Other .claude/ namespaces
  Orphan files (still present):
    .claude/conventions/tests/<orphan>.md

To re-install:
  /test-authoring:setup-test-context

Verify with:
  git diff .claude
```

Exit. Do NOT auto-commit. Do NOT touch any other file.
