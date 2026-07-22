# Language Dispatch Fragments

This directory holds language-specific baseline content used by the `setup-test-context` skill when filling placeholders in rule templates (`{{PROJECT_WIDE_RULES}}`, `{{VISIBILITY_NOTE}}`, `{{KNOWN_PACKAGES_TABLE}}`, component build commands, etc.).

The dispatch mechanism — derivation rule (e.g., `C#` → `csharp`), filesystem probe, per-subagent fragment ownership, sentinel handling — is documented in:

- [`skills/setup-test-context/references/placeholders.md`](../../skills/setup-test-context/references/placeholders.md) § Language fragments
- [`skills/setup-test-context/references/subagent-contract.md`](../../skills/setup-test-context/references/subagent-contract.md) item 10

## Adding a new language

1. Derive the directory name from `{{LANGUAGE}}` per the rule in `placeholders.md` (e.g., `Go` → `go`, `JavaScript` → `javascript`).
2. Create `lang/<derived>/` with the fragment files you have content for. **Partial coverage is fine** — the orchestrator passes a sentinel for any missing fragment and the subagent then generates the placeholder from Step 1 analysis observations only.
3. Use `lang/csharp/` as the canonical reference for fragment shape and frontmatter (`description`, `fills_placeholder` as YAML list, `template` pointer).

**Size guideline**: keep each fragment terse — ideally under 50 lines. Fragments are language-specific *baselines*, not exhaustive style guides. Content that's repo-specific belongs in tier-3 sampler logic (`references/tier3-schemas.md`) or per-repo conventions, not the static baseline.

## Currently shipped languages

The filesystem is the truth here — there is no allowlist to maintain. To see which languages ship today, list the subdirectories of this folder.
