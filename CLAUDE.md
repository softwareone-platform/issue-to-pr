# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A **Claude Code plugin marketplace** for an engineering team. There is no compiled code and no build system — the "source" is almost entirely Markdown (`SKILL.md`, agent `.md`, `README.md`, docs), JSON manifests, and three Python scripts (the dashboard's server and parser, plus a self-check test). The deliverable is skills and subagents that other repos install and invoke.

Distribution is the GitHub marketplace repo `https://github.com/softwareone-platform/issue-to-pr.git` (git origin). Consumers install with `/plugin marketplace add <url>` then `/plugin install <plugin>@itpr`, and activate with `/reload-plugins`.

## Repository layout

```
.claude-plugin/marketplace.json      # THE registry — lists every published plugin, its version + source path
plugins/<plugin>/
├── .claude-plugin/plugin.json        # plugin metadata: name, description, version, optional dependencies[]
├── skills/<skill>/SKILL.md           # a user-invocable skill (frontmatter + body)
├── skills/<skill>/evals/evals.json   # skill evals (prompt → expected behaviour + assertions)
├── skills/<skill>/README.md          # optional per-skill doc
├── agents/<agent>.md                 # a subagent (flat dir, bare-name files) — test-authoring only
├── resources/                        # templates / static assets bundled with the plugin
└── docs/                             # deeper design docs
```

`.claude/` is **gitignored** (see `.gitignore`) — it holds local session state, and in *consumer* repos it is where `setup-test-context` writes the generated conventions. Never rely on it being present in this repo.

## The four plugins

| Plugin | Contains |
|---|---|
| `adversarial-review` | Adversarial review at 3 altitudes: `review-issue-fact` (issue), `review-plan-risk` (plan/design), `review-code-risk` (implemented fix) |
| `pr-lifecycle` | PR lifecycle (Azure DevOps or GitHub): `open-pr`, `resolve-pr-comments` |
| `test-authoring` | Test authoring: 6 skills + 8 subagents (see below) |
| `issue-to-pr-pipeline` | `resolve-issue` (full issue→PR pipeline), `resolve-issue-dashboard`, `resolve-issue-learnings` |

Current versions live in `.claude-plugin/marketplace.json` — do not duplicate them here.

`issue-to-pr-pipeline` declares `dependencies` on `adversarial-review`, `test-authoring`, and `pr-lifecycle` in its `plugin.json` — `resolve-issue` chains those component skills into one pipeline. When changing a component skill's inputs/outputs, check `resolve-issue` still calls it correctly.

## Anatomy of a skill

A skill is `skills/<name>/SKILL.md` with YAML frontmatter (`name`, `description`) followed by a Markdown body of instructions. Invoked as `/<plugin>:<skill>` or auto-triggered.

The `description` field is **load-bearing**: it is how Claude decides when to auto-trigger the skill. It typically packs three things — what the skill does, "Use when…" trigger phrases, and an explicit "Do NOT trigger for…" list that routes look-alike requests to sibling skills. Preserve this structure and do not compress or shorten descriptions casually; terse descriptions break triggering.

**Description length cap**: Claude Code truncates each description at **1,536 characters** in the skill listing (`skillListingMaxDescChars` default) — whatever sits past the cap is silently invisible at trigger time, and the trailing "Do NOT trigger for…" list is exactly what gets cut. When editing a description, measure its whitespace-normalized length and keep it **≤ ~1,450** (headroom matters: with many skills installed, least-used descriptions get compressed further). If space is tight, cut how-it-works mechanism detail (the body covers that after invoke) and quotes that duplicate the trigger-phrase list — never the "Do NOT trigger for…" routing. All shipped descriptions were audited and brought under the cap on 2026-07-03.

## Subagents (test-authoring)

Only `test-authoring` ships subagents, in a flat `agents/` dir with bare-name files (e.g. `add-unit-test-agent.md`). Frontmatter carries `name` (bare), `description`, and `model`. At runtime Claude Code applies the plugin namespace, so they are spawned as `Agent(subagent_type="test-authoring:<agent-name>")`.

The architecture is **orchestrator → writer → verifier**:
- A skill body is the *orchestrator* (top-level caller). It resolves scope, delegates to writer agents, spawns read-only verifier agents, and runs the fix→verify loop.
- Writers generate/update tests. Verifiers are strictly read-only and report violations.
- Crucial constraint: **a subagent cannot spawn another subagent.** So writers/verifiers never spawn follow-ups themselves — they *emit structured output* and the orchestrator merges it and does any downstream spawning.

## test-authoring: what ships vs what is generated

`setup-test-context` is an **optional accelerator**, not a prerequisite. Every test workflow works with or without it:
- **Rule books are never copied.** Every skill and agent reads `resources/templates/{rules,shared}/` from the plugin, in both cases below. A skill resolves that root once in Step -1 and passes it to every subagent (a subagent cannot resolve it itself); if it cannot be resolved, the skill stops rather than running unruled.
- **Without setup**: conventions are discovered from the nearest sibling tests at runtime.
- **With setup** (run once in the consumer repo): the cross-layer map is cached at `.claude/conventions/tests/{project-architecture,common-verification-patterns}.md`, plus a provenance `README.md` at `.claude/shared/tests/`. Nothing else is written per-repo.

Distinction that matters when editing content: **rules are non-negotiable**; **conventions are descriptive patterns** that observed sibling tests can override. `resources/templates/rules/` = strict, and shipped; the per-repo `.claude/conventions/tests/` files setup generates = descriptive, and generated. There is no conventions *template* dir, and after the rule books stopped being copied there is no template *filling* either — the shipped files carry no placeholders and every convention file is written from analysis.

`common-*` files are role-lifecycle documents (one per actor: orchestrator/writer/update-writer/verifier); the other rule files are rule books. Put an actor's procedure in its `common-*` file and a constraint in the matching rule book — never both, or the rule drifts into two sources of truth.

**No versioning of the generated files, and no state between runs.** There is no manifest, no recorded hashes, and no per-file `schema_version`: `setup-test-context` knows only the fixed set of paths the current version writes. Existing files at those paths are backed up and rewritten; anything else under `.claude/{conventions,rules,shared}/tests/` is reported and left alone. Re-running is the refresh, so a template change reaches a repo when someone re-runs setup — nothing detects staleness for them.

## Making changes

- **Editing a skill/agent**: edit the `.md`, then in a consumer session run `/reload-plugins` to pick it up. There is nothing to build.
- **Releasing a version bump**: update the version in **both** the plugin's `.claude-plugin/plugin.json` **and** the corresponding entry in `.claude-plugin/marketplace.json` — they must stay in sync. `marketplace.json` is the registry consumers read.
- **Adding a skill**: create `plugins/<plugin>/skills/<skill>/SKILL.md` with `name` + `description` frontmatter; add `evals/evals.json` if it warrants evals.
- **Adding a plugin hook**: no plugin ships one today. If you add one it belongs at `plugins/<plugin>/hooks/hooks.json` — a **plugin-root** directory, not inside `.claude-plugin/` and not under `resources/` — and `/reload-plugins` picks it up. Getting the location wrong fails silently: the hook simply never loads.
- **Changing the step registry**: `plugins/issue-to-pr-pipeline/resources/resolve-issue-steps.json` is canonical, but `parse_session.py`'s `_DEFAULT_STEPS` is an embedded fallback copy that **must stay in the same order** — the dashboard does index arithmetic over it. Removing a step id also needs a redirect in `resolve-issue/SKILL.md`'s State reconcile, so a run whose `state.md` still names it resumes cleanly.
- **Validating**: there is no linter. At minimum verify JSON parses (`marketplace.json`, `plugin.json`, `evals.json`) and that frontmatter is well-formed before committing.

## Running skill evals

Each `evals/evals.json` pairs prompts with an `expected_output` and a list of `assertions`. Run and author these via the `skill-creator` skill (its eval/benchmark tooling), not a standalone test runner.

## resolve-issue-dashboard

The only executable code lives under `plugins/issue-to-pr-pipeline/skills/resolve-issue-dashboard/`: `scripts/{serve_progress.py,parse_session.py}` — a read-only, localhost-only observer that tails Claude Code transcripts and `.claude/resolve/<ticket>/state.md` (plus the run's append-only `timings.md`, for per-step durations) to visualise a `resolve-issue` run (it never writes to transcripts or `.claude/resolve/`) — plus `tests/selfcheck.py`, a stdlib deterministic self-check of the parser's pure logic. Run the dashboard: `python serve_progress.py [--cwd PATH] [--ticket TICKET] [--port N] [--no-browser]`; run the checks: `python tests/selfcheck.py`.

**Where the screen's data comes from.** Most of it is *not* `state.md`. That file supplies the ticket, the cursor, the branches, `plan-approved`, `pr-url`, `attention`, and `started`/`ended`; `timings.md` supplies the per-step durations and the `×N` re-entry count. Everything else is derived from the Claude Code **transcript** — `~/.claude/projects/<encoded-cwd>/<session>.jsonl` and that session's `<session>/subagents/agent-*.jsonl`: the agent-activity feed, the token and tool-call totals, the session id in the header, whether the run reads as running or parked, and (via each transcript's `cwd`) the cross-repo run list in the left panel. Worth knowing before debugging a blank panel — and it is why a fixture built from the two Markdown files alone renders an empty feed, zero counters, a single repo, and an idle status.

**Transcript record shape.** Claude Code does not document it, so this was read off `Collector._parse_line`; you need it whenever you synthesise a transcript, e.g. to rebuild the README screenshot after a pipeline change. One JSON object per line. Only `type` `"user"` and `"assistant"` are parsed — everything else is skipped silently. Tokens come from `message.usage.{input_tokens,output_tokens}`. Tool events come from `tool_use` blocks in `message.content[]`, and a tool's duration from pairing its `tool_use.id` with the later `tool_result.tool_use_id`. A main-session assistant record whose `stop_reason` is `"tool_use"` is what marks the session as still working; any other stop reads as yielded to the human, which is what flips the run from running to parked. The top-level `cwd` field is how a project dir is mapped back to its repo.

## Conventions

- Commits: plain `<summary>` (≤50 chars), no ticket prefix; commit to `main`; no `Co-Authored-By`.
- **This repo is public.** Nothing that reaches the remote may carry internal detail — no ticket ids in commit subjects, bodies, **or branch names**, and no internal host or repo names. Skill prose uses `acme-…` as the placeholder ticket format. Grep a diff before committing.
- Prose in skills/docs uses semantic line breaks (break at clause boundaries), except rendered Markdown like READMEs (one line per paragraph). See the user's global CLAUDE.md for the full prose/comment style rules.
