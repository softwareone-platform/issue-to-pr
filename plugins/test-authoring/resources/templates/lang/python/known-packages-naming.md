---
description: Python language baseline for `{{KNOWN_PACKAGES_TABLE}}` placeholder content (and the install-model prose preceding it) in `rules/sut-analysis.md`.
fills_placeholder:
  - "{{KNOWN_PACKAGES_TABLE}}"
template: rules/sut-analysis.md
---

# Python — Known-internal-packages Baseline

Bootstrap (shared-tier2 subagent) uses this fragment when filling `{{KNOWN_PACKAGES_TABLE}}` and the install-model prose above it in `.claude/rules/tests/sut-analysis.md`.

## Package source location model

Python packages do **not** use a stable name → repo prefix convention (unlike .NET's `Acme.X.*` → `acme-library-x`). The local source location depends on the install model:

| Install model | Detection signal | Local source path |
|---|---|---|
| **Editable install** (`pip install -e ../repo`) | Sibling repo path appears in `pip list --editable` output, in `*.pth` files under site-packages, or in `pyproject.toml` direct refs / `requirements.txt` `-e ../repo` lines | The path passed to `-e` (typically a sibling repo) |
| **PyPI install** | Package shows up in `pip list` without `-e`; source under `site-packages/<package>/` | Site-packages — **DO NOT** read decompiled `.pyc` bytecode; treat as opaque, fall back to public API surface |
| **Vendored** | Subdirectory inside the repo (e.g., `vendor/<package>/`, `third_party/<package>/`) carrying the package's `__init__.py` | Repo-relative path |

For each detected internal package, record install model + local source path.

## Filled-table example (replace with Step 1.2.1 detected packages)

| Package | Install model | Expected local path | Status |
|---|---|---|---|
| `acme-internal-lib` | editable | `../acme-internal-lib` | 🟩 |
| `acme-other-lib` | PyPI | n/a (site-packages not read) | 🟨 — falls back to public API surface |

Status values:
- 🟩 — local path exists (editable / vendored install verified at bootstrap time)
- 🟨 — no local path (PyPI install; runtime resolution flow falls back to interface / usage inference)

## Empty-table form (if none detected)

| Package | Install model | Expected local path | Status |
|---|---|---|---|
| (none detected — user can add entries here) | | | |
