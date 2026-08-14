# issue-to-pr-pipeline

The orchestration layer of the skill marketplace. It composes the independent component plugins — `disconfirm-first`, `test-authoring`, and `pr-lifecycle` — into end-to-end workflows. It ships three skills: `resolve-issue`, the issue-to-PR pipeline; `resolve-issue-dashboard`, a read-only dashboard that visualises a run; and `resolve-issue-learnings`, which harvests the generic learnings captured across runs into honoured conventions.

This is the last block of the blocks-first roadmap: the review trio, the test family, and the PR-lifecycle skills were each built and validated standalone first; this plugin wires them together.

## Installation

```
/plugin marketplace add https://github.com/softwareone-platform/issue-to-pr.git
/plugin install issue-to-pr-pipeline@itpr
```

Installing `issue-to-pr-pipeline` auto-installs its three dependencies (`disconfirm-first`, `test-authoring`, `pr-lifecycle`); dependency auto-install needs Claude Code v2.1.143 or later, and on older versions you install those three explicitly with `/plugin install <name>@itpr`. The security pass delegates to Claude Code's built-in `security-review` — no install needed.

After installing, run `/reload-plugins` to activate.

## Plugin structure

```
plugins/issue-to-pr-pipeline/
├── .claude-plugin/plugin.json     # metadata + dependencies
├── README.md                      # this file
├── resources/
│   └── resolve-issue-steps.json   # canonical pipeline step registry (shared by both skills)
└── skills/
    ├── resolve-issue/
    │   ├── SKILL.md                # the orchestrator (lean spine)
    │   ├── README.md               # flow diagram + governing rules
    │   ├── PLANNING.md             # planning-cluster reference (disclosed on entry)
    │   ├── REVIEW-PASSES.md        # review-cluster reference (disclosed on entry)
    │   └── {ARCHIVING,DASHBOARD,GIT-HANDLING,LEARNINGS}.md   # branch-conditional refs
    ├── resolve-issue-dashboard/    # read-only progress dashboard
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── scripts/                # serve_progress.py + parse_session.py (stdlib only)
    │   └── assets/index.html       # self-contained dashboard
    └── resolve-issue-learnings/    # harvest captured learnings into conventions
        ├── SKILL.md
        └── README.md
```

## Skills

Run via `/issue-to-pr-pipeline:resolve-issue [ticket]` in the Claude Code prompt, or by natural language matching the description ("take ACME-12345 from diagnosis to PR").

| Skill | Source | Purpose |
|---|---|---|
| `resolve-issue` | [SKILL.md](skills/resolve-issue/SKILL.md) · [README](skills/resolve-issue/README.md) | Drive one ticket through the full pipeline — fact-check the issue, draft and harden a plan, implement, write tests, review the fix, open the PR — gated on plan approval and pausing again wherever a decision is yours, resumable from `.claude/resolve/<ticket>/`. Ends at PR-created. |
| `resolve-issue-dashboard` | [SKILL.md](skills/resolve-issue-dashboard/SKILL.md) · [README](skills/resolve-issue-dashboard/README.md) | Open a live, **read-only** dashboard that visualises a `resolve-issue` run — pipeline step, per-subagent activity, metrics, and the gate it is paused at — by tailing the transcript and `state.md`. A stdlib-only Python server plus one self-contained HTML page; it observes, never drives. |
| `resolve-issue-learnings` | [SKILL.md](skills/resolve-issue-learnings/SKILL.md) · [README](skills/resolve-issue-learnings/README.md) | Harvest the generic learnings `resolve-issue` captured across runs from the user-global dead-drop, verify each against the current skill as ground truth, and write the survivors to a user-global conventions file honoured on the next run (or, inside the plugin source, propose them as SKILL.md edits). |

`resolve-issue` runs in the **main conversation loop**, not as a subagent: the component skills spawn their own verifier subagents, and the gates are interactive. `resolve-issue-dashboard` runs alongside it as a separate local server and only reads — it never advances the pipeline or answers a gate. `resolve-issue-learnings` is invoked separately (or by `resolve-issue`'s own end-of-run upkeep) to distil captured learnings — it never drives a run either.

## Dependencies

`plugin.json` declares three dependencies, auto-installed with this plugin:

- **`disconfirm-first`** — `review-issue-fact` (fact-check the issue), `review-plan-risk` (harden the plan), `review-code-risk` (review the committed fix).
- **`test-authoring`** — `add-*-test` / `update-*-test` (write tests scoped to the change).
- **`pr-lifecycle`** — `open-pr` (open the PR at the end of the pipeline).

The component skills coordinate only by natural-language invocation — there is no skill-to-skill API — so `resolve-issue` invokes each by its slash form and never threads one component's output into another as data.

## Consumer-repo note — `.claude/resolve/` is self-ignored

`resolve-issue` writes its handoff artifacts (`state.md`, `fact-check.md`, `plan.md`) under `.claude/resolve/<ticket>/` in the repo it runs in, and drops a self-scoped `.claude/resolve/.gitignore` (`*`) there so those artifacts stay out of git automatically — without editing the consumer repo's root `.gitignore`. `review-code-risk` reads `plan.md` from the working-tree disk, so it need not be committed, and committing it would add the internal design doc to the PR diff. Gitignored files do not make the working tree "dirty", so `review-code-risk`'s clean-tree precondition still holds. A team that wants the plan in the PR for context may commit `plan.md` explicitly, but that is a preference, not the default.

## What lands outside the repo — two files, both yours to read or delete

Everything above stays inside the repo you invoked the pipeline in. Two files do not:

- `~/.claude/resolve-learnings/candidates.md` — `resolve-issue` appends a candidate learning here at a step boundary, but only when the observation is generic, orchestration-scoped, grounded in a concrete signal, and novel. The bias is silence, so most steps append nothing. Writing is append-only and never blocks a run; at the end of an interactive run the pipeline counts the fresh entries and, once enough accumulate, auto-invokes the harvest below as internal upkeep.
- `~/.claude/resolve-learnings/conventions.md` — `resolve-issue-learnings` verifies the candidates against the current skill and writes the survivors here; `resolve-issue` reads it at startup and honours what still fits, as preferences rather than hard rules.

Both are **user-global**, so they are shared by every repo you run the pipeline in — that is deliberate, since a lesson about the pipeline's own flow is not repo-specific. Both are plain markdown you can read, edit, or delete at any time, and deleting them costs nothing but the accumulated learnings. Nothing else these skills do reaches outside the repo: `resolve-issue-dashboard` reads `~/.claude/projects/` to tail transcripts but never writes there.
