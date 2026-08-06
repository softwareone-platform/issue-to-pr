# test-authoring

A self-contained plugin for test authoring in your codebases. Ships a cohesive set of 6 skills, 8 subagents, and per-repo template scaffolding.

The plugin is **cohesive**: skills are designed to work together. `setup-test-context` is an **optional accelerator** — it profiles the consumer repo once and caches per-repo conventions/rules/shared files under `.claude/` (the **fast path**). Without it, every test workflow (`scan-test-gaps`, `add/update {unit,integration} test`) still runs in **cacheless mode** — reading rules from the plugin's bundled `resources/templates/` and discovering conventions from the nearest sibling tests at runtime. Repos that have run setup take the unchanged fast path (zero migration); running setup additionally unlocks cross-layer pattern analysis and user-editable convention files.

---

## Plugin structure

```
plugins/test-authoring/
├── .claude-plugin/plugin.json              # plugin metadata
├── README.md                               # this file
├── skills/                                 # 6 plugin-bundled skills
│   ├── setup-test-context/SKILL.md         # one-time bootstrap
│   ├── scan-test-gaps/SKILL.md
│   ├── add-unit-test/SKILL.md
│   ├── add-integration-test/SKILL.md
│   ├── update-unit-test/SKILL.md
│   └── update-integration-test/SKILL.md
├── agents/                                 # 8 plugin-bundled subagents (flat, bare names)
│   ├── add-{unit,integration}-test-agent.md
│   ├── update-{unit,integration}-test-agent.md
│   ├── verify-add-{unit,integration}-test-agent.md
│   └── verify-update-{unit,integration}-test-agent.md
├── resources/
│   ├── templates/                          # filled by setup-test-context, written per-repo
│   │   ├── template-schema-versions.json   # per-category schema versions (one JSON, three fields)
│   │   ├── rules/                          # 8 .md
│   │   └── shared/                         # scope-resolution.md
│   └── static/                             # plugin-internal, never written per-repo
│       └── status-legend.md                # controlled vocabulary, do not extend
└── docs/                                   # detailed per-skill / per-agent / shared docs
    ├── skills/{readme-*.md}                # one per skill
    ├── agents/{readme-*.md}                # high-complexity update + verify-update agents
    └── shared/{readme-*.md}                # cross-cutting concept primers
```

**Plugin-bundled vs per-repo**: skills, agents, and `resources/static/` ship in the plugin and are not scaffolded into consumer repos. Plugin upgrades reach all consumers immediately. The only files setup-test-context writes per-repo are filled-in copies of `resources/templates/` content.

---

## What setup-test-context writes per-repo

When `/test-authoring:setup-test-context` runs in a consumer repo, it produces files under `.claude/` split into three folders. Repo-specific values (language, framework, paths, exclusion lists) replace `{{PLACEHOLDERS}}` in the templates.

```
.claude/
├── conventions/tests/                  # repo-specific patterns, learned from codebase
│   ├── project-architecture.md         # source/test layout, naming, mirroring (Tier 3 — generated from analysis)
│   ├── {type}-test-conventions.md      # code-driven per-type (unit/integration): NOT written (Slim default) — writers use siblings at runtime
│   ├── common-test-utilities.md        # if shared test project detected (Tier 3 — conditional)
│   └── common-verification-patterns.md # if cross-type patterns detected (Tier 3 — conditional)
├── rules/tests/                        # strict, prescriptive (must-follow), filled from plugin templates
│   ├── test-rules.md
│   ├── test-writer-rules.md
│   ├── fix-protocol.md
│   ├── sut-analysis.md
│   ├── common-orchestrator-flow.md
│   ├── common-writer-instructions.md
│   ├── common-update-instructions.md
│   └── common-verifier-checks.md
└── shared/tests/
    ├── scope-resolution.md             # filled from plugin template
    └── .setup-manifest.json            # uninstall inventory + schema-version tracking
```

**Why `rules/` vs `conventions/`**: writer agents treat them differently. **Rules are non-negotiable**; **conventions are descriptive patterns** that observed sibling tests can override.

**Not written per-repo** (lives in plugin):
- 6 user-invocable skills (invoked as `/test-authoring:<name>`)
- 8 subagents (invoked as `Agent(subagent_type="test-authoring:<name>-agent")`)
- `status-legend.md` — controlled vocabulary, plugin-internal at `resources/static/status-legend.md`
- Guarded hook block templates — for plugin authors only

---

## Skills (user-invocable)

Run via `/test-authoring:<skill-name> [scope]` in the Claude Code prompt. Auto-trigger from natural language is supported when the description matches.

| Skill | Source | Detail | Purpose |
|---|---|---|---|
| `setup-test-context` | [SKILL.md](skills/setup-test-context/SKILL.md) | [docs](docs/skills/readme-setup-test-context.md) | One-time profile of the repo and per-repo file generation; also handles uninstall, schema-drift, idempotent re-runs |
| `scan-test-gaps` | [SKILL.md](skills/scan-test-gaps/SKILL.md) | [docs](docs/skills/readme-scan-test-gaps.md) | Find untested code and stale tests; iteratively delegate generation/updates. Scope: unit and integration only |
| `add-unit-test` | [SKILL.md](skills/add-unit-test/SKILL.md) | [docs](docs/skills/readme-add-unit-test.md) | Generate unit tests for changed source or a specified target |
| `add-integration-test` | [SKILL.md](skills/add-integration-test/SKILL.md) | [docs](docs/skills/readme-add-integration-test.md) | Generate integration tests (endpoints, handlers, consumers) |
| `update-unit-test` | [SKILL.md](skills/update-unit-test/SKILL.md) | [docs](docs/skills/readme-update-unit-test.md) | Two-phase audit→execute update of unit tests |
| `update-integration-test` | [SKILL.md](skills/update-integration-test/SKILL.md) | [docs](docs/skills/readme-update-integration-test.md) | Same, integration-specific (with env_failure handling) |

---

## Agents (subagents spawned by skills)

Not directly invoked by users. Spawned by orchestrator skills via `Agent(subagent_type="test-authoring:<agent-name>")` (Claude Code automatically applies the plugin namespace at runtime; the `name:` field in each agent's frontmatter is the bare identifier). One agent per (role × supported type) cell.

| Agent | Source | Purpose |
|---|---|---|
| `add-unit-test-agent` | [agents/add-unit-test-agent.md](agents/add-unit-test-agent.md) | Writer for unit tests |
| `add-integration-test-agent` | [agents/add-integration-test-agent.md](agents/add-integration-test-agent.md) | Writer for integration tests (test-project selection + env_failure handling) |
| `update-unit-test-agent` | [agents/update-unit-test-agent.md](agents/update-unit-test-agent.md) | Two-phase update writer for unit tests |
| `update-integration-test-agent` | [agents/update-integration-test-agent.md](agents/update-integration-test-agent.md) | Same, integration-specific |
| `verify-add-{unit,integration}-test-agent` | [agents/](agents/) | Read-only verifiers for add-flow output |
| `verify-update-{unit,integration}-test-agent` | [agents/](agents/) | Read-only verifiers for update-flow output (deletion confirmations, valid-test preservation, env_failure distinction) |

Detailed docs for the high-complexity update + verify-update agents in [`docs/agents/`](docs/agents/). Add-flow and verify-add agents are simpler — read the agent files directly.

**Model — subagents inherit the caller's model.** These agents declare no `model` in their frontmatter, so a writer or verifier runs on whatever model invoked the skill: a complex run at a stronger model lifts both the writer and its independent verifier together, and a cheap run keeps them cheap. We deliberately do **not** pin a model or downgrade to a cheaper one to save cost — that would trade the caller's chosen output quality for cost without consent. A large `scan-test-gaps` fan-out under a strong session model therefore costs more by design; lower the session model yourself if you want it cheaper.

---

## Per-repo rules (strict, prescriptive)

Filled from `resources/templates/rules/` at setup time and written to `.claude/rules/tests/` (the fast path); on the **cacheless path** the same files are read directly from the plugin's `resources/templates/rules/`. All of them are universal — there is no type-specific rules file.

**Context discipline (lazy loading)**: on both paths the orchestrator never bulk-reads this rule set upfront — each skill's Step -1 only *resolves* where the references live, and its "Orchestrator reading list" reads each orchestrator-facing document at the step that first uses it. The writer/verifier rule books (`common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, …) are read by the subagents in their own isolated contexts and are never preloaded into the main context.

**File taxonomy — `common-*` vs the rule books**: the `common-*` files are **role lifecycle documents** —
who the actor is, its input contract, procedure, and output schema; one per role
(orchestrator / writer / update-writer / verifier).
The remaining files are **rule books** — constraints and protocols, scoped by audience:
`test-rules.md` binds every agent, `test-writer-rules.md` binds writers,
and `fix-protocol.md` is read by the **orchestrator** (it routes verifier findings;
verifiers themselves follow `common-verifier-checks.md`).
When adding content, put the actor's procedure in its `common-*` file
and the constraint in the matching rule book — never both
(duplicating across the pair is how rules drift into two sources of truth).

| File | Template | Purpose |
|---|---|---|
| `test-rules.md` | [resources/templates/rules/test-rules.md](resources/templates/rules/test-rules.md) | Mandatory project-wide rules: fix rules (never weaken/skip/delete-failing), build/test verification |
| `test-writer-rules.md` | [resources/templates/rules/test-writer-rules.md](resources/templates/rules/test-writer-rules.md) | What to test (happy path, validation, exceptions, edges) and what not to do |
| `fix-protocol.md` | [resources/templates/rules/fix-protocol.md](resources/templates/rules/fix-protocol.md) | Verifier fix protocol; circuit breaker (3 global / 2 per-issue) |
| `sut-analysis.md` | [resources/templates/rules/sut-analysis.md](resources/templates/rules/sut-analysis.md) | SUT analysis procedure; known internal package → local source path mappings |
| `common-orchestrator-flow.md` | [resources/templates/rules/common-orchestrator-flow.md](resources/templates/rules/common-orchestrator-flow.md) | Universal orchestrator flow: scope resolution, writer delegation, verifier spawn, fix-verify loop, summary |
| `common-writer-instructions.md` | [resources/templates/rules/common-writer-instructions.md](resources/templates/rules/common-writer-instructions.md) | Universal writer procedure: role, input contract, SUT analysis, sibling learning, output schema |
| `common-update-instructions.md` | [resources/templates/rules/common-update-instructions.md](resources/templates/rules/common-update-instructions.md) | Universal two-phase audit→execute procedure for update writers |
| `common-verifier-checks.md` | [resources/templates/rules/common-verifier-checks.md](resources/templates/rules/common-verifier-checks.md) | Universal verifier check sequence, output schema, routing |

---

## Per-repo conventions (descriptive, learned from code)

Repo-specific patterns derived from actual codebase analysis. Writer agents use these as context; sibling tests still take priority at runtime.

| File | Source | Purpose |
|---|---|---|
| `project-architecture.md` | _(Tier 3 — generated from analysis, no template)_ | Source/test directory structure, naming conventions, feature organisation |
| `{type}-test-conventions.md` | _(Tier 3 — generated from analysis)_ | Per-type path mapping, sibling convention checklist, common patterns |
| `common-test-utilities.md` | _(Tier 3 — conditional, generated if shared test project detected)_ | Shared utilities across test types |
| `common-verification-patterns.md` | _(Tier 3 — conditional, generated if cross-type patterns detected)_ | Recurring verification patterns |

---

## Per-repo shared

Small shared specifications referenced by multiple skills and agents.

| File | Source | Purpose |
|---|---|---|
| `scope-resolution.md` | [resources/templates/shared/scope-resolution.md](resources/templates/shared/scope-resolution.md) | Mode A (git diff) vs Mode B (explicit argument) scope resolution procedure |
| `.setup-manifest.json` | _(generated by setup-test-context)_ | Inventory of every per-repo file with sha256 + schema_version + plugin_version. Drives idempotent re-install and uninstall |

`status-legend.md` is **not** written per-repo. It lives at [`resources/static/status-legend.md`](resources/static/status-legend.md) and skills read it directly via `<plugin-root>/resources/static/status-legend.md`. This keeps the controlled-vocabulary single-sourced; user extensions to a per-repo copy are not honoured.

---

## Schema versioning

A single JSON file at `resources/templates/template-schema-versions.json` carries per-category schema versions (`conventions`, `rules`, `shared`). Bump the relevant category field when:

- A required section header is renamed
- A `{{PLACEHOLDER}}` is renamed, added, or removed
- The semantic contract that skills/agents read changes shape

The plugin author is responsible for the bump. Consumers see the change next time they run `/test-authoring:setup-test-context` — the skill compares each plugin per-category version with the manifest at `.claude/shared/tests/.setup-manifest.json` and prompts for a guided refresh if they mismatch.

Per-file granularity: each generated convention/rule file carries its own `schema_version: "X.Y"` in frontmatter so individual skills/agents can verify before reading.

Full mechanism details: [`docs/shared/readme-schema-versioning.md`](docs/shared/readme-schema-versioning.md).

---

## docs/ — deeper documentation

- [`docs/skills/`](docs/skills/) — one readme per skill
- [`docs/agents/`](docs/agents/) — readmes for high-complexity update + verify-update agents
- [`docs/shared/`](docs/shared/) — cross-cutting concept primers:
  - [readme-shared-orchestration.md](docs/shared/readme-shared-orchestration.md) — circuit breaker, fix-verify loop
  - [readme-shared-scope-and-status.md](docs/shared/readme-shared-scope-and-status.md) — Mode A/B scope, status legend
  - [readme-shared-update-patterns.md](docs/shared/readme-shared-update-patterns.md) — two-phase update lifecycle
  - [readme-schema-versioning.md](docs/shared/readme-schema-versioning.md) — `template-schema-versions.json`, manifest schema_versions, drift handling

Rule files and simple agents (add + verify-add) are not individually wrapped in readmes — read the source files directly.
