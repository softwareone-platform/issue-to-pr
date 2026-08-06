# test-authoring

A self-contained plugin for test authoring in your codebases. Ships a cohesive set of 6 skills, 8 subagents, and the rule books they obey.

The plugin is **cohesive**: skills are designed to work together. Every skill reads its rule books straight from the plugin's `resources/templates/{rules,shared}/` — nothing is copied into a consumer repo, so a plugin upgrade reaches every repo at once. `setup-test-context` is an **optional accelerator** on top of that: it profiles the consumer repo once and caches the cross-layer map (project architecture, recurring verification patterns) under `.claude/conventions/tests/`. Without it every workflow (`scan-test-gaps`, `add/update {unit,integration} test`) still runs, discovering conventions from the nearest sibling tests at runtime.

---

## Plugin structure

```
plugins/test-authoring/
├── .claude-plugin/plugin.json              # plugin metadata
├── README.md                               # this file
├── skills/                                 # 6 plugin-bundled skills
│   ├── setup-test-context/SKILL.md         # one-time repo profile (optional)
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
│   ├── templates/                          # the rule books; read from here, never copied per-repo
│   │   ├── rules/                          # 8 .md
│   │   └── shared/                         # scope-resolution.md
│   └── static/                             # plugin-internal, never written per-repo
│       └── status-legend.md                # controlled vocabulary, do not extend
└── docs/                                   # detailed per-skill / per-agent / shared docs
    ├── skills/{readme-*.md}                # one per skill
    ├── agents/{readme-*.md}                # high-complexity update + verify-update agents
    └── shared/{readme-*.md}                # cross-cutting concept primers
```

**Plugin-bundled vs per-repo**: everything under `plugins/test-authoring/` — skills, agents, rule books, static assets — ships in the plugin and is read from there, so a plugin upgrade reaches every consumer at once. The only per-repo files are the one or two conventions `setup-test-context` generates from analysis — no template exists for them, because they exist precisely for what cannot be shipped.

---

## What setup-test-context writes per-repo

When `/test-authoring:setup-test-context` runs in a consumer repo it writes one or two files, both generated from the analysis — no template is copied or filled. The only thing it touches outside this directory is one line appended to the repo-root `.gitignore`.

```
.claude/
└── conventions/tests/                  # repo-specific patterns, learned from the codebase
    ├── project-architecture.md         # source/test layout, naming, mirroring, shared test project
    └── common-verification-patterns.md # only if a cross-layer pattern was detected
```

Per-type `{type}-test-conventions.md` are **not** written — writers read the nearest sibling instead, which is always more current than a cache.

**Why `conventions/` holds the only per-repo *content***: writer agents treat rules and conventions differently. **Rules are non-negotiable** and identical in every repo, so they ship with the plugin. **Conventions are descriptive patterns** that observed sibling tests can override, and they are the only thing analysis can discover that shipping cannot supply.

**Not written per-repo** (lives in plugin):
- the 9 rule books — `resources/templates/{rules,shared}/`, read directly at runtime
- 6 user-invocable skills (invoked as `/test-authoring:<name>`)
- 8 subagents (invoked as `Agent(subagent_type="test-authoring:<name>-agent")`)
- `status-legend.md` — controlled vocabulary, plugin-internal at `resources/static/status-legend.md`

---

## Skills (user-invocable)

Run via `/test-authoring:<skill-name> [scope]` in the Claude Code prompt. Auto-trigger from natural language is supported when the description matches.

| Skill | Source | Detail | Purpose |
|---|---|---|---|
| `setup-test-context` | [SKILL.md](skills/setup-test-context/SKILL.md) | [docs](docs/skills/readme-setup-test-context.md) | One-time profile of the repo, cached as conventions; re-runnable, and re-running is the refresh |
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

## Rule books (strict, prescriptive, plugin-bundled)

Read directly from `resources/templates/{rules,shared}/` by every skill and agent — nothing writes them into a repo. All of them are universal; there is no type-specific rules file. A skill resolves the absolute path of `resources/templates/` once in its Step -1 and hands it to every subagent as `plugin_resources_path`, because a subagent cannot resolve it itself; if it cannot be resolved, the skill stops rather than running without its rules.

**Context discipline (lazy loading)**: the orchestrator never bulk-reads this rule set upfront — each skill's Step -1 only *resolves* where the references live, and its "Orchestrator reading list" reads each orchestrator-facing document at the step that first uses it. The writer/verifier rule books (`common-writer-instructions.md`, `common-verifier-checks.md`, `test-writer-rules.md`, …) are read by the subagents in their own isolated contexts and are never preloaded into the main context.

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

| File | Source | Purpose |
|---|---|---|
| `test-rules.md` | [resources/templates/rules/test-rules.md](resources/templates/rules/test-rules.md) | Fix rules (never weaken/skip/delete-failing) and build/test verification. **Not** a conventions list — conventions come from the sibling |
| `test-writer-rules.md` | [resources/templates/rules/test-writer-rules.md](resources/templates/rules/test-writer-rules.md) | What to test (happy path, validation, exceptions, edges) and what not to do |
| `fix-protocol.md` | [resources/templates/rules/fix-protocol.md](resources/templates/rules/fix-protocol.md) | Verifier fix protocol; circuit breaker (3 global / 2 per-issue) |
| `sut-analysis.md` | [resources/templates/rules/sut-analysis.md](resources/templates/rules/sut-analysis.md) | SUT analysis procedure; runtime resolution flow for external / internal package source |
| `common-orchestrator-flow.md` | [resources/templates/rules/common-orchestrator-flow.md](resources/templates/rules/common-orchestrator-flow.md) | Universal orchestrator flow: scope resolution, writer delegation, verifier spawn, fix-verify loop, summary |
| `common-writer-instructions.md` | [resources/templates/rules/common-writer-instructions.md](resources/templates/rules/common-writer-instructions.md) | Universal writer procedure: role, input contract, SUT analysis, sibling learning, output schema |
| `common-update-instructions.md` | [resources/templates/rules/common-update-instructions.md](resources/templates/rules/common-update-instructions.md) | Universal two-phase audit→execute procedure for update writers |
| `common-verifier-checks.md` | [resources/templates/rules/common-verifier-checks.md](resources/templates/rules/common-verifier-checks.md) | Universal verifier check sequence, output schema, routing |
| `scope-resolution.md` | [resources/templates/shared/scope-resolution.md](resources/templates/shared/scope-resolution.md) | Mode A (git diff) vs Mode B (explicit argument) scope resolution procedure |

---

## Per-repo conventions (descriptive, learned from code)

Repo-specific patterns derived from actual codebase analysis — the only thing written per-repo. Writer agents use these as context; sibling tests still take priority at runtime.

| File | Source | Purpose |
|---|---|---|
| `project-architecture.md` | _(generated from analysis, no template)_ | Source/test directory structure, naming conventions, feature organisation, shared test project |
| `common-verification-patterns.md` | _(generated from analysis, conditional on a cross-layer pattern being detected)_ | Recurring verification patterns |

`status-legend.md` is **not** written per-repo. It lives at [`resources/static/status-legend.md`](resources/static/status-legend.md) and skills read it directly via `<plugin-root>/resources/static/status-legend.md`. This keeps the controlled-vocabulary single-sourced; user extensions to a per-repo copy are not honoured.

---

## No generated-file versioning

`setup-test-context` keeps **no state between runs** — no manifest, no recorded hashes, no per-file
`schema_version`. It knows only the fixed set of paths the current plugin version writes.

- An existing file at one of those paths is rewritten, with no undo — the confirmation gate lists it first, which is where you copy out a hand-edit.
- Anything else under `.claude/{conventions,rules,shared}/tests/` is reported and left untouched —
  without recorded state, a retired template's leftover and a file you wrote by hand look identical.
- Nothing detects staleness on a consumer's behalf. A template change reaches a repo when someone
  re-runs setup there. Bump the plugin version so `/plugin update` actually fetches the change.

To keep a hand-edit, copy it out before re-running — the write list marks it `OVERWRITE` first. Committing it does not work: `.gitignore` covers that path.

---

## docs/ — deeper documentation

- [`docs/skills/`](docs/skills/) — one readme per skill
- [`docs/agents/`](docs/agents/) — readmes for high-complexity update + verify-update agents
- [`docs/shared/`](docs/shared/) — cross-cutting concept primers:
  - [readme-shared-orchestration.md](docs/shared/readme-shared-orchestration.md) — circuit breaker, fix-verify loop
  - [readme-shared-scope-and-status.md](docs/shared/readme-shared-scope-and-status.md) — Mode A/B scope, status legend
  - [readme-shared-update-patterns.md](docs/shared/readme-shared-update-patterns.md) — two-phase update lifecycle

Rule files and simple agents (add + verify-add) are not individually wrapped in readmes — read the source files directly.
