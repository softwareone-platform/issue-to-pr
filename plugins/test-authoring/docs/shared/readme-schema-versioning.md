# Shared Primer — Schema Versioning and Drift Handling

`test-authoring` writes per-repo files (`conventions/`, `rules/`, `shared/`) that the plugin's skills and agents read at runtime. As the plugin evolves, the section structure of these files may change — new headings appear, placeholders are renamed, sections are reorganised. Without versioning, an upgraded plugin would silently mis-read older per-repo files, producing wrong or empty results.

This primer documents the three-layer mechanism that makes schema evolution safe: per-category versions in `template-schema-versions.json`, per-file frontmatter `schema_version`, and skill/agent-side defensive parsing.

---

## Why three layers

| Layer | Where | Detects | Triggered by |
|---|---|---|---|
| **1. Plugin per-category version** | `<plugin-root>/resources/templates/template-schema-versions.json` (per-category fields) | Plugin author bumped a category version | Human author |
| **2. setup-test-context drift check** | At `.claude/shared/tests/.setup-manifest.json` `schema_versions.{category}` | Plugin's current category version ≠ manifest's recorded version | `/test-authoring:setup-test-context` re-run |
| **3. Skill/agent defensive parsing** | At skill/agent body — frontmatter `expected_schema_version` vs file's frontmatter `schema_version` | A skill is reading a per-repo file written by an older plugin version | Skill or agent at runtime |

Layer 1 declares "what version is the plugin currently producing" (per category); Layer 2 detects "consumer is on an older version, prompt to refresh"; Layer 3 detects "we already loaded a possibly-stale file, warn the user".

The three layers complement each other — Layer 2 fires only when setup-test-context runs (which user might forget); Layer 3 catches the case where user upgraded the plugin but forgot to re-run setup.

---

## Layer 1 — per-category versions in `template-schema-versions.json` (plugin author)

`resources/templates/template-schema-versions.json` is a single JSON file with one field per category (`conventions`, `rules`, `shared`) plus a `$comment` header explaining its purpose. The plugin author manually bumps a category's field when:

- A required section header is renamed
- A `{{PLACEHOLDER}}` is renamed, added, or removed
- A section's expected structure (table columns, list shape) changes
- The semantic contract that skills/agents read changes

```
plugins/test-authoring/resources/templates/
├── template-schema-versions.json   # { conventions: "1.0", rules: "1.3", shared: "1.0" }
├── conventions/
│   ├── component-test-conventions.md
│   └── fixture-capabilities.md
├── rules/
│   ├── common-orchestrator-flow.md
│   └── ... (8 more)
└── shared/
    └── scope-resolution.md
```

Each individual template file also has `schema_version` in its frontmatter:

```markdown
---
schema_version: "1.0"
description: ...
---
```

When `setup-test-context` writes the filled file to `.claude/`, the frontmatter `schema_version` is preserved. This lets Layer 3 (skill-side check) verify version compatibility per file.

Tier 3 dynamic files (`project-architecture.md`, `{type}-test-conventions.md`, `common-test-utilities.md`, `common-verification-patterns.md`) are not template-driven — they are generated per the recipes in `skills/setup-test-context/references/tier3-schemas.md`. Those recipes use the placeholder `{{CONVENTIONS_SCHEMA_VERSION}}` (resolved at orchestration time from `template-schema-versions.json` field `conventions`) so the generated files carry a frontmatter `schema_version` consistent with Layer 1 — same value also recorded in manifest `files[].schema_version`.

### Bump policy

Use SemVer-like progression:

- **Minor** (1.0 → 1.1) — additive / backward-compatible (new optional section, new field, clarified wording). Triggers a setup-test-context (Layer 2) regeneration prompt so consumers pick up the additions, but does **not** trigger a runtime (Layer 3) warning — skills and agents tolerate any file version that shares their expected **major**.
- **Major** (1.x → 2.0) — breaking change (renamed/removed section, removed placeholder, restructured contract). Triggers **both** the Layer 2 prompt **and** a Layer 3 runtime warning until each affected skill/agent bumps the **major** of its `expected_schema_version`.

Both minor and major trigger Layer 2 (so consumers regenerate). They differ at Layer 3: only a **major** difference warrants a runtime warning. This is why an additive bump like conventions 1.0 → 1.1 regenerates files at setup time but does not nag on every subsequent skill/agent run.

---

## Layer 2 — setup-test-context drift check

Whenever `/test-authoring:setup-test-context` runs (install or re-run), Phase 0 reads:

- Plugin's current `resources/templates/template-schema-versions.json` for each of `conventions`, `rules`, `shared` fields
- Consumer's `.claude/shared/tests/.setup-manifest.json` `schema_versions.{category}` (if manifest exists)

Then routes:

| State | Action |
|---|---|
| Manifest absent | Fresh install — write all files; manifest will record current schema_versions |
| All categories match + plugin_version unchanged | Ask "all current; refresh anyway? [y/N]" |
| Plugin_version changed but schemas match | "Plugin patched; refresh? [y/N]" |
| Any category schema differs (e.g. plugin conventions=2.0, manifest conventions=1.0) | **Warn + three-way prompt**: (a) back up affected files into the run's backup folder (`.claude/backup/setup-{timestamp}/`) + regenerate (recommended) / (b) skip that category, leave existing (risky — schema mismatch) / (c) abort |

After processing, the manifest's `schema_versions.{category}` and per-file `schema_version` are updated to current —
except categories skipped via option (b), which retain their previous manifest value
so the unresolved drift is re-detected on the next run.

### What setup-test-context does NOT do

- **Auto-migrate content from schema 1.0 to 2.0.** Migrations are content-shape transformations and are too varied to automate safely. Instead, regeneration from current templates + Tier 3 fill from analysis is the migration path.
- **Silently discard user edits.** A file with `sha256` not matching the manifest (user-modified) IS refreshed on re-run — managed files are generated artifacts — but never silently: it is backed up into the run's backup folder, flagged in the confirmation block, and the backup folder is kept and its path reported.
- **Touch files outside its categories.** setup-test-context only manages `.claude/{conventions,rules,shared}/tests/`; other `.claude/` namespaces are never read or written.

---

## Layer 3 — skill/agent defensive parsing

Each skill and agent has `expected_schema_version` in its frontmatter; skills additionally declare `expected_rules_schema_version` because the conventions and rules template categories version independently:

```markdown
---
name: add-unit-test
expected_schema_version: "1.0"
expected_rules_schema_version: "1.0"
description: ...
---
```

At runtime (Step -1 of every skill, schema check section in every agent), the model:

1. Reads `.claude/conventions/tests/project-architecture.md` frontmatter
2. Extracts the file's `schema_version`
3. Compares its **major** component with the major of this skill/agent's `expected_schema_version`
4. (Skills only) repeats the same check on `.claude/rules/tests/common-orchestrator-flow.md` against `expected_rules_schema_version` — a passing conventions check says nothing about the rules files

| Result | Behaviour |
|---|---|
| Same major (e.g. file 1.1 vs expected 1.0) | Continue silently — minor bumps are additive and backward-compatible, not worth a warning |
| Major differs (e.g. file 2.0 vs expected 1.x) | Warn "skill expects major X, file is major Y; some sections may be restructured", continue best-effort |
| Key missing (file exists, no `schema_version`) | Warn "frontmatter has no schema_version; please re-run setup-test-context to refresh", continue best-effort |
| File does not exist (skills) | **Cacheless mode** (not a stop) — setup never ran, so per-repo files are absent; the skill does NOT halt. It reads rules from the plugin's bundled `resources/templates/`, discovers conventions from sibling tests, and announces the cacheless banner once. Agents are passed the resolved plugin templates path; they warn-and-continue |

On a major mismatch the skill does **not** crash — it warns and continues with best-effort parsing, so user upgrades that forget setup re-run get a clear message rather than silent failure. A wholly absent conventions file no longer stops a skill either: it switches to **cacheless mode** (rules from the plugin's bundled templates, conventions from sibling tests). Section-level lookup uses tolerant parsing — find sections by heading text, fall back gracefully if absent.

### What defensive parsing does NOT do

- **Does not attempt schema migration in-flight.** If section "X" was renamed to "Y", the skill warns and proceeds with whatever it found; it does not try to re-derive the missing section from context.
- **Does not block on missing optional sections.** If an expected optional placeholder (e.g. coverage exclusion list) is absent, the skill uses a reasonable default.
- **Does not over-defend.** Hard errors (e.g. file completely empty, frontmatter malformed) still surface; the goal is "warn loudly and continue", not "silently work around any input".

---

## Drift scenarios — behaviour matrix

| Scenario | Layer 2 (setup) behaviour | Layer 3 (runtime) behaviour |
|---|---|---|
| **Fresh install** | Write all files; manifest records schema 1.0 | Normal |
| **Setup never run** (no per-repo files at all) | (Setup not triggered) | **Cacheless mode** — skills run without setup: rules from the plugin's bundled templates, conventions from sibling tests, with a one-time banner. Agents receive the resolved plugin templates path |
| **Plugin patch** (plugin_version bumped, schemas unchanged) | "Plugin patched; refresh? [y/N]" | Normal |
| **Plugin minor** (additive schema bump) | Warn schema change; offer backup+regen | Skill warns "expected 1.0, file is 1.x"; continues best-effort |
| **Plugin major** (breaking schema bump) | Strong warn, default to backup+regen | Skill warns "expected 1.0, file is 2.0"; continues best-effort but flags results may be incomplete |
| **User edited a per-repo file** (sha256 mismatch in manifest) | Idempotent overwrite-safe flow: back up into the run's backup folder, overwrite, flag in confirmation block | sha256 changed but schema_version still matches — runtime is normal |
| **User upgraded plugin but forgot to re-run setup** | (Setup not triggered) | Layer 3 catches it: "schema mismatch — please re-run /test-authoring:setup-test-context" |
| **User downgraded plugin** (rollback) | Layer 2 detects manifest's schema is newer than plugin's; warn "downgrade detected; offer reset to current plugin schema" | Skill expects older schema, file uses newer schema; warns + continues |

---

## Practical authoring rules

For plugin maintainers:

1. **Bump the relevant category in `template-schema-versions.json` whenever you change a template's section structure or placeholder names.** Even small changes warrant a bump — Layer 2's prompt costs nothing if the user accepts.
2. **Update each template file's frontmatter `schema_version` to match.** Layer 3 reads frontmatter, not `template-schema-versions.json`. (Tier 3 dynamic files in `skills/setup-test-context/references/tier3-schemas.md` use the `{{CONVENTIONS_SCHEMA_VERSION}}` placeholder, so they pick up the new value automatically from the JSON on next regeneration — no manual frontmatter edit needed.)
3. **Document the change in the plugin's README** (or `CHANGELOG.md` if added later). Helps consumers decide whether to refresh.
4. **Update affected skill/agent `expected_schema_version`** to match. If a skill body's lookup logic still works against the new schema, increment the major version of `expected_schema_version`. If multiple skills read different categories, only update the ones whose category schema bumped.
5. **Don't rely on auto-migration.** The system is "warn and refresh", not "auto-translate".

For consumers:

1. After plugin upgrade, run `/test-authoring:setup-test-context` to re-sync.
2. If you've manually edited a per-repo file, re-running setup backs it up into the run's backup folder and overwrites it with fresh template content — recover your edits from the reported backup path if you still need them. Durable customisations belong in CLAUDE.md or your own (orphan) files, not in managed files.
3. If runtime warnings about schema mismatch persist, your manifest is stale — re-running setup refreshes the managed files and the manifest together.
