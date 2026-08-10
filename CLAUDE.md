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

Only `test-authoring` ships subagents, in a flat `agents/` dir with bare-name files (e.g. `add-unit-test-agent.md`). Frontmatter carries `name` (bare) and `description` — **and deliberately no `model:`**. At runtime Claude Code applies the plugin namespace, so they are spawned as `Agent(subagent_type="test-authoring:<agent-name>")`.

**Do not add `model:` to an agent's frontmatter.** It overrides the model the user chose for their session, and this is a publicly-installed plugin: picking the cost/quality trade-off is the consumer's call, not ours. The predecessor plugin (`swo/mpt-test-skills`) pinned `model: sonnet` on all 12 of its agents — that was an internal plugin, and it is not the precedent to follow here. Its absence is a decision, not an oversight; if cost guidance is wanted, put a measured figure in the README and let the consumer choose.

The architecture is **orchestrator → writer → verifier**:
- A skill body is the *orchestrator* (top-level caller). It resolves scope, delegates to writer agents, spawns read-only verifier agents, and runs the fix→verify loop.
- Writers generate/update tests. Verifiers are strictly read-only and report violations.
- Crucial constraint: **a subagent cannot spawn another subagent.** So writers/verifiers never spawn follow-ups themselves — they *emit structured output* and the orchestrator merges it and does any downstream spawning.

## test-authoring: what ships vs what is generated

`setup-test-context` is an **optional accelerator**, not a prerequisite. Every test workflow works with or without it:
- **Rule books are never copied.** Every skill and agent reads `resources/templates/{rules,shared}/` from the plugin, in both cases below. A skill resolves that root once in Step -1 and passes it to every subagent (a subagent cannot resolve it itself); if it cannot be resolved, the skill stops rather than running unruled.
- **Without setup**: conventions are discovered from the nearest sibling tests at runtime.
- **With setup** (run once in the consumer repo): the cross-layer map is cached at `.claude/conventions/tests/{project-architecture,common-verification-patterns}.md`. Nothing else is written per-repo — no rule books, no README, no manifest, and no backup: an overwrite has no undo, and the confirmation gate is the protection.

Distinction that matters when editing content: **rules are non-negotiable**; **conventions are descriptive patterns** that observed sibling tests can override. `resources/templates/rules/` = strict, and shipped; the per-repo `.claude/conventions/tests/` files setup generates = descriptive, and generated. There is no conventions *template* dir, and after the rule books stopped being copied there is no template *filling* either — the shipped files carry no placeholders and every convention file is written from analysis.

`common-*` files are role-lifecycle documents (one per actor: orchestrator/writer/update-writer/verifier); the other rule files are rule books. Put an actor's procedure in its `common-*` file and a constraint in the matching rule book — never both, or the rule drifts into two sources of truth.

**No versioning of the generated files, and no state between runs.** There is no manifest, no recorded hashes, and no per-file `schema_version`: `setup-test-context` knows only the fixed set of paths the current version writes. An existing file at one of those paths is rewritten with no undo — the confirmation gate labels it `OVERWRITE` beforehand, and that is the only protection; anything else under `.claude/{conventions,rules,shared}/tests/` is reported and left alone. Re-running is the refresh, so a template change reaches a repo when someone re-runs setup — nothing detects staleness for them.

## Making changes

- **Editing a skill/agent**: edit the `.md`, then in a consumer session run `/reload-plugins` to pick it up. There is nothing to build.
- **Releasing a version bump**: update the version in **both** the plugin's `.claude-plugin/plugin.json` **and** the corresponding entry in `.claude-plugin/marketplace.json` — they must stay in sync. `marketplace.json` is the registry consumers read.
- **Before pushing, derive which plugins need a bump from the diff — do not recall it.** The cache is keyed by version, so a changed plugin at an unchanged version reaches nobody, and the push looks successful. A late commit touching a *different* plugin than the earlier ones is how this slips (it has, once). Run:
  ```bash
  for n in adversarial-review pr-lifecycle test-authoring issue-to-pr-pipeline; do
    printf '%-22s changed=%s version=%s
' "$n"       "$(git diff --name-only origin/main HEAD -- plugins/$n | wc -l)"       "$(grep -o '"version": "[^"]*"' plugins/$n/.claude-plugin/plugin.json)"
  done
  ```
  Any plugin with `changed>0` whose version equals the one already on `origin/main` is the bug.
- **Adding a skill**: create `plugins/<plugin>/skills/<skill>/SKILL.md` with `name` + `description` frontmatter; add `evals/evals.json` if it warrants evals.
- **Adding a plugin hook**: no plugin ships one today. If you add one it belongs at `plugins/<plugin>/hooks/hooks.json` — a **plugin-root** directory, not inside `.claude-plugin/` and not under `resources/` — and `/reload-plugins` picks it up. Getting the location wrong fails silently: the hook simply never loads.
- **Changing the step registry**: `plugins/issue-to-pr-pipeline/resources/resolve-issue-steps.json` is canonical, but `parse_session.py`'s `_DEFAULT_STEPS` is an embedded fallback copy that **must stay in the same order** — the dashboard does index arithmetic over it. Removing a step id also needs a redirect in `resolve-issue/SKILL.md`'s State reconcile, so a run whose `state.md` still names it resumes cleanly.
- **Citing a file from a rule book**: check the citation against the orchestrators' Step -1 reading lists before adding it. Each lists writer/verifier rule books under **Never** for context discipline, so a document on that list **cannot** be cited as the definition of something the orchestrator must produce — inline what it needs instead, and say which copy is authoritative. This has bitten once (`common-orchestrator-flow.md` was pointed at `common-writer-instructions.md` for the convention-spec field set); the target existing is not the same as this reader being allowed to reach it.
- **Validating**: there is no linter. At minimum verify JSON parses (`marketplace.json`, `plugin.json`, `evals.json`) and that frontmatter is well-formed before committing.

## Running skill evals

Each `evals/evals.json` pairs prompts with an `expected_output` and a list of `assertions`. Author these via the `skill-creator` skill, not a standalone test runner.

**They have never been executed, and three things block running the trigger eval from this repo on Windows — verified 2026-08-06, do not re-discover them:**

1. **Wrong artifact.** `skill-creator`'s `scripts/run_eval.py` does not read `evals/evals.json`. It wants a separate flat trigger set, `[{"query": ..., "should_trigger": bool}]`. Ours is the qualitative set (prompt / expected_output / assertions), which belongs to the grader workflow instead. A trigger set can be derived: `should_trigger` = the eval has no `skill_not_triggered` assertion.
2. **The runner is Windows-incompatible.** Its read loop gates on `select.select([process.stdout], ...)`; on Windows `select` supports sockets only, so it raises `OSError` WinError 10093, unwinds to `return triggered` with `triggered` still `False`, and reports **every** query as not-triggered. Positives all fail, negatives all pass vacuously — a clean 19/19 + 21/21 split that looks like data and is not. Replace the streaming read with `communicate(timeout=...)` to fix it.
3. **The prompts do not match this repo.** They name a C#/.NET billing domain (`BillingService.CreateInvoice`, `POST /invoices`, `InvoiceConsumer`). Run here, the model greps, finds nothing, and correctly declines — so every positive is a false miss. Running them needs a fixture repo in that domain, or prompts rewritten to this repo's own subject matter.

A fourth, milder caveat: the runner counts the **first** `tool_use`, so any exploratory `Glob`/`Grep` before the skill is selected reads as not-triggered. A skill whose own first step is "locate the artifact" (e.g. `review-plan-risk`) will look like a miss even when it behaves correctly.

## Measuring anything (tools we build to check our own work)

**A measurement tool gets checked harder than the thing it measures.** Its output carries the authority of "this was measured", so a wrong number does not just fail — it launders a false conclusion into a decision. Several instruments built here were wrong on their first version and three of those shipped: the dashboard's token count reads one of four `usage` fields and double-counts the rest; the skill-eval runner reported a clean 19/19 + 21/21 split that was `select.select` failing on Windows; `resolve-issue/SKILL.md`'s cost anchor is ~4.3× too high. (That is not a base rate — an instrument that was right first time leaves no debugging trace, so it cannot enter the denominator. It says only that the failure is common enough to need a process rather than care.)

Three rules, in order:

1. **Every check needs a known-answer case that makes it fail.** A check that has only ever been run against good input has not been tested.
2. **Mutation-test the check set**: delete any one check and the known-answer set must go red. A check that can be deleted without turning the suite red does not exist. This is not hypothetical — an audit tool here passed 4/4 with two of its five checks stubbed out. (A companion example once cited here — "a self-check case had frozen a bug in place" — was withdrawn: on inspection the case was pinning *correct* semantics, and "fixing" it would have weakened the only check that catches a leaked read.)
3. **No result is quotable until 1 and 2 hold.** State the limit instead ("the tool has not been validated"), the same voiced-limit discipline the review skills use.

**Reading Claude Code transcripts — two traps that have already bitten.** Each is verified in this repo, do not re-derive them:

- **`usage` is repeated, tool calls are not.** One API response is written as several `assistant` records — one per content block — and *every* record repeats the same `message.usage`. Summing usage per record inflates it (measured on one session: output 2.71×, `cache_read` 2.34×, `input_tokens` 3.55×). Deduplicate on `message.id`. Tool calls are the sound basis for comparison and token sums are not — `tool_use` blocks are written once each, so counts do not inherit the inflation. **But "ids are unique" is not an invariant**: across the whole corpus 73 ids appear more than once, all but one of them across different files. **Pair a `tool_use` to its `tool_result` on `(source file, id)`, never on `id` alone**, and do not restate either figure as a fixed number — the corpus grows.
- **A whole session expires together, and a resume reprieves all of it.** Cleanup keys on the **top-level session file's `mtime`**, default **30 days** (`~/.claude/.last-cleanup` records the last run), and it removes the session **together with its `subagents/` directory** — subagent files are not separately retained. Touching a session resets its mtime and spares the entire bundle, so **file age is not evidence of the retention rule**. Evidence (2026-08-07): subagent mtimes cluster at 0–30 days, then a completely empty band from 31 to 43 days, then 14 `agent-*.jsonl` at 44–45 days whose two parent sessions were resumed 3.2 days ago; 0 orphans across 32 subagent directories, in a corpus 129+ days old. **Read that evidence with its limit:** no top-level session older than 30 days survives anywhere, so "zero orphans" is consistent both with "the directory is deleted with its parent" and with "those sessions simply had no subagents". The empty 31–43 band is the load-bearing part; the deletion mechanism itself is inferred, not observed. Plan any transcript-based audit against **30 days from the session's last activity**.

  This one question has now been answered wrongly three times, each way: first a cliff "found" by scanning `find -mtime +28` (a filtered subset cannot establish where a distribution ends — it manufactures the edge it reports); then an over-correction declaring the question unknowable when ten minutes of measurement settles it; then a backwards model built by reading subagent mtimes as exemption instead of as reprieve. **`mtime` is last-append, not creation — it bounds retention but says nothing about content age**, and a resumed session carries months-old records under a recent mtime.

Beyond that: `input_tokens` counts only the cache-miss delta once prompt caching is on, so it is not "the input size"; and a per-step window contains whatever the human did during it (one measured step window spent ~47 minutes on an unrelated ticket), so per-step figures are upper bounds on pipeline work, never measurements of it.

## resolve-issue-dashboard

The only executable code lives under `plugins/issue-to-pr-pipeline/skills/resolve-issue-dashboard/`: `scripts/{serve_progress.py,parse_session.py}` — a read-only, localhost-only observer that tails Claude Code transcripts and `.claude/resolve/<ticket>/state.md` (plus the run's append-only `timings.md`, for per-step durations) to visualise a `resolve-issue` run (it never writes to transcripts or `.claude/resolve/`) — plus `tests/selfcheck.py`, a stdlib deterministic self-check of the parser's pure logic. Run the dashboard: `python serve_progress.py [--cwd PATH] [--ticket TICKET] [--port N] [--no-browser]`; run the checks: `python tests/selfcheck.py`.

**Where the screen's data comes from.** Most of it is *not* `state.md`. That file supplies the ticket, the cursor, the branches, `plan-approved`, `pr-url`, `attention`, and `started`/`ended`; `timings.md` supplies the per-step durations and the `×N` re-entry count. Everything else is derived from the Claude Code **transcript** — `~/.claude/projects/<encoded-cwd>/<session>.jsonl` and that session's `<session>/subagents/agent-*.jsonl`: the agent-activity feed, the token and tool-call totals, the session id in the header, whether the run reads as running or parked, and (via each transcript's `cwd`) the cross-repo run list in the left panel. Worth knowing before debugging a blank panel — and it is why a fixture built from the two Markdown files alone renders an empty feed, zero counters, a single repo, and an idle status.

**Transcript record shape.** Claude Code does not document it, so this was read off `Collector._parse_line`; you need it whenever you synthesise a transcript, e.g. to rebuild the README screenshot after a pipeline change. One JSON object per line. Only `type` `"user"` and `"assistant"` are parsed — everything else is skipped silently. Tokens come from `message.usage.{input_tokens,output_tokens}`. Tool events come from `tool_use` blocks in `message.content[]`, and a tool's duration from pairing its `tool_use.id` with the later `tool_result.tool_use_id`. A main-session assistant record whose `stop_reason` is `"tool_use"` is what marks the session as still working; any other stop reads as yielded to the human, which is what flips the run from running to parked. The top-level `cwd` field is how a project dir is mapped back to its repo.

## Conventions

- Commits: plain `<summary>` (≤50 chars), no ticket prefix; commit to `main`; no `Co-Authored-By`.
- **This repo is public.** Nothing that reaches the remote may carry internal detail — no ticket ids in commit subjects, bodies, **or branch names**, and no internal host or repo names. Skill prose uses `acme-…` as the placeholder ticket format. Grep a diff before committing.
- Prose in skills/docs uses semantic line breaks (break at clause boundaries), except rendered Markdown like READMEs (one line per paragraph). See the user's global CLAUDE.md for the full prose/comment style rules.
