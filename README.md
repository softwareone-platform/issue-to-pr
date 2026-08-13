# issue-to-pr

A [Claude Code](https://claude.com/claude-code) **plugin marketplace** (`itpr`) — a set of skills and subagents that take a ticket from diagnosis to a reviewed pull request, plus the review, test-authoring, and housekeeping tools that support that flow.

![The resolve-issue-dashboard visualising a run mid-pipeline](docs/resolve-issue-dashboard.png)

<sub>The `resolve-issue-dashboard` (in `issue-to-pr-pipeline`) watching a run move through the pipeline — illustrative example data.</sub>

## Install

Requires Claude Code with plugin support (a recent version — dependency auto-install and enable-time dependency handling need v2.1.143 or later; on older versions use the explicit per-plugin list below).

Install `issue-to-pr-pipeline` — it declares the other three plugins as dependencies, so Claude Code resolves and installs them from this marketplace automatically and lists what was added at the end of the install output.

```
/plugin marketplace add https://github.com/softwareone-platform/issue-to-pr.git
/plugin install issue-to-pr-pipeline@itpr
```

Alternatively — on older Claude Code (before v2.1.143, where dependency auto-install is unavailable) or when you want only some of the plugins — install each explicitly:

```
/plugin marketplace add https://github.com/softwareone-platform/issue-to-pr.git
/plugin install disconfirm-first@itpr
/plugin install pr-lifecycle@itpr
/plugin install test-authoring@itpr
/plugin install issue-to-pr-pipeline@itpr
```

Then run `/reload-plugins` to activate — it also re-resolves any missing dependencies. Install only the plugins you need — they work standalone, except `issue-to-pr-pipeline`, which builds on the other three.

## Plugins at a glance

| Plugin | What it gives you |
|---|---|
| [`disconfirm-first`](#disconfirm-first) | Adversarial review at the issue, plan, and code altitudes |
| [`pr-lifecycle`](#pr-lifecycle) | Pull-request lifecycle (Azure DevOps or GitHub) |
| [`test-authoring`](#test-authoring) | Test authoring — unit and integration |
| [`issue-to-pr-pipeline`](#issue-to-pr-pipeline) | Issue-to-PR orchestration (chains the three above) |

Invoke any skill as `/<plugin>:<skill>`, or just describe the task — each skill auto-triggers from natural language.

## How they fit together

The review, test, and PR plugins are independently useful. `issue-to-pr-pipeline` composes them: `resolve-issue` drives one ticket through the pipeline below, gated on plan approval and pausing again wherever a decision is yours, delegating each stage to the skill that owns it — the review, test, and PR skills, plus Claude Code's built-in `security-review`.

```
  PLAN
   ●─  1  Fact-check issue    does the bug actually hold in the code? (may ask)
   │
   ●─  2  Resolve decisions   settle open design decisions before planning (may ask)
   │
   ●─  3  Draft plan          sketch how the fix will be made
   │
   ●─  4  Harden plan         pre-mortem the plan, fix its design risks (may ask)
   │
   ◆─  5  Plan approval       you approve the plan before any code changes (always waits)
  BUILD
   ●─  6  Implement fix       make the code change
   │
   ●─  7  Write tests         cover the change with tests, then commit them (may ask)
   │
   ●─  8  Review security     scan the diff for vulnerabilities (may ask)
   │
   ●─  9  Review fix          pressure-test that the fix resolves the issue (may ask)
   │
   ●─ 10  Open PR             raise the pull request (always waits)
  DONE
   ◉─ 11  Done                pipeline complete, PR awaiting review
```

**Drafting the plan and making the code change are the only steps that run without you.** Two stops are unconditional — plan approval and the open-PR confirmation — and every other step can pause to ask: a design decision it is barred from guessing, a risk to disposition, a test-type call, a quality flag. Each wait is unbounded — a paused run sits there until it is answered. It names what it is waiting for in `state.md`, and `resolve-issue-dashboard` shows it. Full breakdown, grouped by why each stop exists: [resolve-issue's README](plugins/issue-to-pr-pipeline/skills/resolve-issue/README.md#where-the-run-stops-for-you).

**What a run costs you.** Most steps delegate to subagents, and the test and review steps each pay for a writer plus an independent verifier — so even a one-line fix pays for that pair. Nothing in the pipeline can report its own spend: the orchestrator cannot see its own token usage, and the dashboard's counters are volume, not price. Wall-clock is no more quotable — a run's elapsed time is mostly how long it waited for **you** at a gate, which is why no duration is quoted here. Watch your first run's usage rather than trusting an estimate.

The whole run checkpoints to `.claude/resolve/<ticket>/`, so a fresh session can resume it. `resolve-issue-dashboard` visualises a run live; `resolve-issue-learnings` distils what the pipeline learned across runs.

**One thing lands outside the repo you invoked it in.** `resolve-issue` appends candidate learnings to `~/.claude/resolve-learnings/candidates.md`, and `resolve-issue-learnings` promotes the verified ones into `~/.claude/resolve-learnings/conventions.md` for later runs to honour. Both are user-global, shared across all your repos, and plain markdown you can read, edit, or delete — and they are the only files these plugins write outside the repo. Everything else stays in that repo's `.claude/`; the dashboard reads `~/.claude/projects/` but never writes there.

## Skills

### disconfirm-first

Three adversarial reviewers, one per altitude — each pressure-tests a different artifact before it moves downstream.

- **review-issue-fact** — Fact-checks an *issue* (bug report, story, incident) against the codebase before any fix is planned; produces a per-claim verdict and a HALT / PROCEED / RESOLVE recommendation.
- **review-plan-risk** — Pre-mortems a *plan / spec / SKILL.md*, auto-fixes the design risks it rates real, and independently verifies each fix before reporting.
- **review-code-risk** — Adversarially reviews an *implemented fix* against its issue and plan before the PR opens; auto-fixes real risks in the changed files and re-runs build and tests.

### pr-lifecycle

Team-agnostic PR lifecycle for Azure DevOps or GitHub — the platform is detected from the git remote at runtime. Both skills confirm before making any outward change.

- **open-pr** — Opens a PR whose title and description follow *your own* past-PR conventions, learned at runtime. Handles standard PRs and backports to `release/*`.
- **resolve-pr-comments** — Fetches a PR's review threads, triages each, drafts the code fixes and replies, and — after one confirmation — commits, pushes, replies, and updates thread status.

### test-authoring

Test authoring that delegates to writer and verifier subagents (8 in total). The rules the agents obey ship with the plugin and are read from there, so nothing is copied into your repo. A one-time `setup-test-context` run additionally caches the repo's cross-layer map; without it, every workflow still runs by learning from the nearest sibling tests. See the [plugin README](plugins/test-authoring/README.md) for the full architecture.

- **setup-test-context** — One-time profile of the repo; caches its cross-layer map as conventions under `.claude/conventions/tests/`. Re-runnable, and re-running is the refresh.
- **scan-test-gaps** — Finds untested code and stale tests, then iteratively delegates generation and updates.
- **add-{unit,integration}-test** — Generate tests for changed source or a named target.
- **update-{unit,integration}-test** — Two-phase audit → execute refresh of existing tests.

### issue-to-pr-pipeline

Issue-to-PR orchestration. Depends on `disconfirm-first`, `test-authoring`, and `pr-lifecycle`.

- **resolve-issue** — Drives one ticket through the full pipeline (see [above](#how-they-fit-together)), gated on plan approval and pausing again wherever a decision is yours; resumable from `.claude/resolve/<ticket>/`.
- **resolve-issue-dashboard** — A live, read-only dashboard that visualises a run — pipeline step, per-subagent activity, metrics, and the gate it is paused at — by tailing the transcript and `state.md`. Observes only; never drives.
- **resolve-issue-learnings** — Harvests the cross-repo learnings a run captured, verifies each against the current skill as ground truth, and writes the survivors to a conventions file the pipeline reads next time.

## Prerequisites

The plugins themselves are just Markdown and JSON — nothing to build. A few skills reach external services; install what the plugins you actually use require:

- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) with the `azure-devops` extension (`az extension add --name azure-devops`) — required by `pr-lifecycle` on Azure DevOps remotes, which it drives through `az repos` / `az devops`.
- [GitHub CLI](https://cli.github.com/) (`gh`, authenticated) — required by `pr-lifecycle` on GitHub remotes, which it drives through `gh pr` / `gh api`.
- [Atlassian MCP Server](https://www.npmjs.com/package/@anthropic-ai/atlassian-mcp) in your Claude Code MCP settings — optional; enables Jira integration for `review-issue-fact`, `resolve-issue`, and the Jira link in `open-pr`. These skills fall back to a pasted link or plain text when it is absent.

## Repository layout

```
.claude-plugin/marketplace.json   the registry — lists every published plugin
plugins/<plugin>/
├── .claude-plugin/plugin.json     plugin metadata (name, version, dependencies)
├── skills/<skill>/SKILL.md        a user-invocable skill
├── agents/<agent>.md              a subagent (test-authoring only)
├── resources/                     bundled templates, static files, hook blocks
└── docs/                          deeper design docs
```
