---
description: C# / .NET language baseline for `{{KNOWN_PACKAGES_TABLE}}` placeholder content (and the naming-convention prose preceding it) in `rules/sut-analysis.md`.
fills_placeholder:
  - "{{KNOWN_PACKAGES_TABLE}}"
template: rules/sut-analysis.md
---

# C# / .NET — Known-internal-packages Baseline

Bootstrap (shared-tier2 subagent) uses this fragment when filling `{{KNOWN_PACKAGES_TABLE}}` and the naming-convention prose above it in `.claude/rules/tests/sut-analysis.md`.

## Naming convention (typical .NET internal-package layout)

Internal packages often map package names to local repo folders via a stable prefix. Example for an org with an `Acme.` prefix:

| Package | Typical local repo folder |
|---|---|
| `Acme.Framework` | `acme-library-framework` |
| `Acme.Rql` | `acme-library-rql` |
| `Acme.<X>` | `acme-library-<x>` (commonly) |

If a naming convention exists, document it above the filled table.

## Filled-table example (replace with Step 1.2.1 detected packages)

| Package | Expected local path | Status |
|---|---|---|
| `Acme.Framework` | `../acme-library-framework` | 🟩 |
| `Acme.Rql` | `../acme-library-rql` | 🟨 not found (checked at bootstrap time) |

Status values:
- 🟩 — path exists (verified at bootstrap time)
- 🟨 — path does not exist on this machine (informational; runtime resolution flow handles the case)

## Empty-table form (if none detected)

| Package | Expected local path | Status |
|---|---|---|
| (none detected — user can add entries here) | | |
