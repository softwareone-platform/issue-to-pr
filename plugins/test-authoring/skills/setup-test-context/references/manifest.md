# `.setup-manifest.json` schema

Inventory of every per-repo file written by `/test-authoring:setup-test-context`. Lives at `.claude/shared/tests/.setup-manifest.json`. Used by Uninstall mode to classify pristine vs user-modified files, and by re-install runs to detect schema drift.

## Schema (`manifest_schema_version: "1.0"`)

```json
{
  "manifest_schema_version": "1.0",
  "generated_at": "2026-05-01T12:34:56Z",
  "plugin_version": "0.1.0",
  "schema_versions": {
    "conventions": "1.0",
    "rules": "1.0",
    "shared": "1.0"
  },
  "test_types": ["unit", "integration"],
  "files": [
    {
      "path": ".claude/conventions/tests/project-architecture.md",
      "sha256": "abc123…",
      "category": "conventions",
      "schema_version": "1.0",
      "test_type": null
    },
    {
      "path": ".claude/conventions/tests/unit-test-conventions.md",
      "sha256": "def456…",
      "category": "conventions",
      "schema_version": "1.0",
      "test_type": "unit"
    },
    {
      "path": ".claude/rules/tests/test-rules.md",
      "sha256": "789abc…",
      "category": "rules",
      "schema_version": "1.0",
      "test_type": null
    },
    {
      "path": ".claude/shared/tests/scope-resolution.md",
      "sha256": "fed321…",
      "category": "shared",
      "schema_version": "1.0",
      "test_type": null
    }
  ]
}
```

### Field semantics

| Field | Meaning |
|---|---|
| `manifest_schema_version` | Version of THIS manifest format (the JSON shape). Bump when fields are added/renamed. setup-test-context refuses to touch a manifest with an unsupported version. |
| `generated_at` | UTC ISO-8601 timestamp of the install/re-install run. |
| `plugin_version` | `version` field from `plugins/test-authoring/.claude-plugin/plugin.json` at the time of write; `unknown` if unreadable. |
| `schema_versions.{category}` | Per-category template schema version, sourced from `<plugin-root>/resources/templates/template-schema-versions.json` field `<category>` at the time of write — EXCEPT categories the user chose to skip via Step 0 option (b), which retain their previous manifest value so the unresolved drift re-surfaces on the next run. Used by Step 0 to detect drift on re-install. |
| `test_types` | List of test-type labels confirmed in Step 2 (`unit`, `integration`, etc.). |
| `files[].path` | Repo-relative path of a per-repo file written by setup. |
| `files[].sha256` | Lowercase hex digest of the file's content as written **by the most recent setup run that wrote it**, line endings normalised CRLF→LF before hashing (see § SHA-256 calculation). Used to classify pristine vs user-modified at re-install / uninstall. |
| `files[].category` | One of `conventions`, `rules`, `shared`. Determines which `<plugin-root>/resources/templates/{category}/` the file came from. |
| `files[].schema_version` | The category's version (from `template-schema-versions.json`) at the time this file was written. May lag behind the global `schema_versions.{category}` after a partial re-install. |
| `files[].test_type` | `null` for files always present, otherwise one of the test types in `test_types[]`. Drives "did this test type get scaffolded?" checks. |

## Per-file frontmatter `schema_version` vs `files[].schema_version`

A written file's frontmatter `schema_version` and the manifest's `files[].schema_version` for the same path **CAN legitimately diverge**. They represent different facts:

- **Frontmatter `schema_version`** = version of this **individual template's** content shape. The plugin author bumps it when *that specific file* changes structurally.
- **Manifest `files[].schema_version`** = the **umbrella category** version at the time of write (sourced from `<plugin-root>/resources/templates/template-schema-versions.json` field `<category>`). The plugin author bumps the umbrella when *any* file in the category changes in a way requiring consumer regeneration.

Two cases by file type:

| File type | Frontmatter source | Agreement with manifest |
|---|---|---|
| **Tier 3 dynamic** (`project-architecture.md`, `{type}-test-conventions.md`, `common-test-utilities.md`, `common-verification-patterns.md`) | Frontmatter `schema_version` is the `{{CONVENTIONS_SCHEMA_VERSION}}` placeholder, filled by the orchestrator from `template-schema-versions.json.conventions` at write time. | **MUST match manifest** — single source of truth. Step 4 verification enforces this; mismatch → rollback. |
| **Static templates** (rule templates, `scope-resolution.md`) | Frontmatter `schema_version` is a hand-managed value baked into the template source by the plugin author. | **May diverge from manifest** — frontmatter tracks per-template change history, manifest tracks umbrella category bump. Not enforced, not a bug. |

Example of legitimate divergence: a consumer's `test-rules.md` frontmatter reads `schema_version: "1.0"` because that template hasn't been structurally modified since v1.0; the manifest records `files[].schema_version: "1.4"` because the `rules` umbrella was bumped to 1.4 (driven by other template changes in the same category). Drift detection on next re-install uses the umbrella; per-file frontmatter is informational.

## Classification (used by re-install drift handling and by uninstall)

For each file in `files[]`:

| State | Condition |
|---|---|
| **pristine** | file exists AND sha256 matches `files[].sha256` |
| **user-modified** | file exists AND sha256 differs |
| **missing** | file does not exist on disk |

Files present on disk under `.claude/{conventions,rules,shared}/tests/` whose path is **not** in `files[]` are **orphans** — never deleted by uninstall, and re-install treats them as `existing-but-unmanaged` (prompt user before overwriting).

## SHA-256 calculation

- **Normalise line endings first**: convert CRLF→LF in the content before hashing, both when recording a hash at write time and when re-computing one for comparison (classification at re-install / uninstall, Step 4 manifest validity). Without this, a git `autocrlf` checkout rewrites LF→CRLF on disk and every pristine file mis-classifies as user-modified.
- Compute on the normalised content as written, before any later editor reflows.
- Use lowercase hex digest. No prefix (no `sha256:`).
- Recompute on every re-install run for files that get rewritten — do not carry stale hashes forward.
- Backward compatibility is mostly clean: manifests written by older plugin versions hashed raw bytes, so if an old run left CRLF bytes on disk, the first normalised comparison mis-classifies those files as user-modified **once** (benign: backup + flag in the confirmation block, refresh rewrites them) — the manifest self-heals after that run.

## Manifest rewrite ordering

1. Compute the per-file plan for this run (fresh + overwrite — pristine and user-modified alike, the latter backed up first — + stale deletions + category-skip from Step 0 option (b)).
2. After every per-repo file write succeeds, build the new `files[]` array from TWO sources:
   - the in-memory write log (entries for every file written this run, with freshly computed hashes), AND
   - **carry-forward entries, copied verbatim from the previous manifest**, for every previously-managed path intentionally not written this run (Step 0 option (b) category skips and the Slim default `{type}-test-conventions.md` carve-out). Never silently drop a previously-managed path that still exists on disk — dropping it orphans the file from uninstall tracking and drift detection. The one deliberate drop is a stale managed file deleted this run (SKILL.md §2.1) — backed up and listed in the confirmation block, so the removal is never silent.
3. Atomic write to `.claude/shared/tests/.setup-manifest.json` (write to temp file, rename).
4. Manifest itself is NOT included in `files[]` — it is meta-data, not a managed file.

## What this manifest does NOT track

- Plugin-bundled files (agents, skills, plugin static, hooks). They live in the plugin folder and are uninstalled by `/plugin uninstall test-authoring`.
- User code (production source, test files in test projects).
- Pre-existing files at managed paths that this skill did not write (orphans — surfaced in uninstall report, never deleted).
