---
name: resolve-issue-dashboard
description: >
  Open a live, read-only dashboard that visualises resolve-issue runs across all your repos — each run's
  pipeline step, what each component skill and subagent is doing, the running metrics, and the gate it is
  paused at — by tailing the Claude Code transcripts and each repo's .claude/resolve/<ticket>/state.md.
  One global dashboard lists every run in a left panel; pick one to watch.
  Use whenever someone wants to see / watch / visualise the progress of an issue-to-PR run, says
  "open the pipeline dashboard", "show resolve progress", "watch the resolve-issue run",
  "visualise what the agents are doing", or "/resolve-issue-dashboard".
  Do NOT trigger to RUN the pipeline — that is resolve-issue — nor for any single stage
  (route those to the component skill: review-issue-fact, review-plan-risk, review-code-risk,
  test-authoring, open-pr, resolve-pr-comments). This skill only observes; it never drives the
  pipeline, answers a gate, or edits anything.
---

# Resolve issue dashboard

Open a small local dashboard that visualises `resolve-issue` runs as they happen. **One global dashboard** discovers every run across your repos — by reading the files Claude Code already writes (the session transcripts under `~/.claude/projects/` and each repo's `.claude/resolve/<ticket>/state.md`, plus the run's append-only `timings.md`) — and lists them in a left panel; pick one to watch its pipeline step, per-subagent activity, running metrics, and any gate it is paused at. It is a **read-only observer**: it never writes to a transcript or to `.claude/resolve/`, never answers a gate, and never edits code. Gates are still answered in the Claude Code terminal; the dashboard only shows that one is waiting.

Because it is global, launch it **once** (from any repo) and reuse it — running `resolve-issue` in several repos does not need several dashboards. Start it any time; runs appear, switch, and can be inspected after they finish or pause.

## Locate the server

The dashboard is served by a stdlib-only Python script bundled with this skill. Resolve the skill directory once via bash injection at load time:

!`echo "${CLAUDE_SKILL_DIR}"`

Call that `SKILL_DIR`. The server is `SKILL_DIR/scripts/serve_progress.py` and it serves `SKILL_DIR/assets/index.html`. If the line above did not expand to a real absolute path (it still shows a literal `${CLAUDE_SKILL_DIR}`), resolve it at runtime — run `echo "$CLAUDE_SKILL_DIR"` with the Bash tool; if it is empty, ask the user for the `issue-to-pr-pipeline` plugin install path and use `<that>/skills/resolve-issue-dashboard`.

## Preflight — confirm Python is available

The server needs Python 3.8+ on the user's machine, standard library only — there is never a `pip install`. Before launching, confirm an interpreter exists: run `python --version` with the Bash tool; if that fails, try `py -3 --version` (the Windows launcher). Use whichever responds as the interpreter in the launch step. If neither resolves, **do not attempt to launch** — tell the user the dashboard needs Python 3.8+ on PATH (a one-time install from python.org or their package manager) and stop. Python is the only prerequisite; nothing else here depends on it.

## Launch the dashboard

One global dashboard serves every repo, so launch it **once** and reuse it.

**First, check for a running dashboard — and that it is the current version.** Run `curl -s http://127.0.0.1:4317/health` with the Bash tool. The reply is `{"app":"resolve-issue-dashboard","version":"<v>","viewers":<n>}`, where `viewers` is the number of browser tabs currently connected (used by the reuse branch below to decide whether to reopen a tab). Read the **installed** version from this skill's bundled plugin manifest — `python -c "import json,os;print(json.load(open(os.path.join(r'SKILL_DIR','..','..','.claude-plugin','plugin.json')))['version'])"` (substitute the real `SKILL_DIR`) — and compare:

- **No reply at all** → none is running; start one (next section).
- **Reply, and its `version` matches the installed version** → one is already up and current; do **not** start another. Whether to open a tab now is decided by `viewers` in the same `/health` reply (the count of tabs currently connected), so the server's lifetime and the tab's presence stay decoupled — the server rightly outlives a closed tab (see its idle grace under Degradation), and this branch only decides whether a tab needs (re)showing:
  - **`viewers` is 0** — every tab was closed while the server kept running inside its idle grace. Reopen exactly one at `http://127.0.0.1:4317/?cwd=<ABS>` with `python -c "import webbrowser; webbrowser.open('http://127.0.0.1:4317/?cwd=<ABS>')"` (Python is already confirmed present from the preflight). This restores the view the user lost without starting a second server.
  - **`viewers` is 1 or more** — a tab is already watching, so **do not** pop another: a `claude --continue` can re-trigger this skill, and a fresh tab on every resume is exactly the noise to avoid. Just give the user the URL to click.
  - **`viewers` is absent** — an older server predating this field (should not occur on a version match, but be defensive): treat it as the 1-or-more case and only print the URL, never auto-open.

  In every case `<ABS>` is this repo's absolute path computed the way the server stores it — `python -c "import os; print(os.path.abspath('.'))"` — so it focuses this repo's run (its path matching is case- and separator-insensitive). Tell the user whether it was already running and whether you reopened a tab, and stop here.
- **Reply, but its `version` differs from the installed version** → a **stale dashboard is squatting the port**. Because the server is a detached process, it survives a Claude restart and keeps serving its own old assets, so an upgrade looks like it did nothing. Replace it: the process on 4317 is confirmed to be this dashboard (the `/health` signature matched), so stopping it by port is safe. On Windows, `netstat -ano | findstr :4317` to find the listening PID, then `taskkill /PID <pid> /F`; on macOS/Linux, `lsof -ti tcp:4317 | xargs -r kill`. Then start the current version (next section), poll `/health` until its `version` equals the installed version, open the browser, and tell the user to **hard-reload** (Ctrl+Shift+R) any tab they already had open so the new assets load.

**Otherwise, start it in the background** from this repo (its working directory sets the default-selected run):

```
python "SKILL_DIR/scripts/serve_progress.py"
```

- Use the interpreter the preflight resolved (`python` or `py -3`).
- Run it with the **Bash tool in the background** so the conversation (and any `resolve-issue` run) continues while it serves. It binds 4317 (it opens the default browser itself); if **another program** holds 4317 it steps to the next free port.
- **Confirm readiness by polling `/health`, not by reading its stdout.** A backgrounded (non-TTY) process can block-buffer stdout, so the printed URL may not reach the output file promptly. Poll `curl -s http://127.0.0.1:4317/health` a few times until it returns the `resolve-issue-dashboard` health JSON with the installed `version` (use your `--port` value if you passed one), then give the user `http://127.0.0.1:4317/`.
- Optional flags: `--cwd <path>` (which run to select by default), `--port <n>`, `--no-browser` (headless — just print the URL).

To stop it: the dashboard **stops itself after about 30 minutes with no connected viewer** (closing the browser tab is enough — a tab left genuinely open counts as watching and keeps it alive). To stop it sooner, stop the background task you launched (e.g. `TaskStop` on it). A dashboard left from an earlier or exited session that `TaskStop` can no longer reach is killed by port — `netstat -ano | findstr :4317` then `taskkill /PID <pid> /F`, or `lsof -ti tcp:4317 | xargs -r kill`. If you started it yourself in a terminal, press Ctrl+C there.

**A stopped-server notification on resume is expected, not a prompt to relaunch.** Because the server is a background task, resuming a session (`claude --continue`) surfaces a stopped-background-task notification for it once the launching process has exited or it self-stopped on idle — that is the normal end of an ephemeral observer, not interrupted work that must be resumed. Do not relaunch the dashboard on that signal alone: (re)launch only when the user asks to watch a run, or when `resolve-issue`'s P1 preamble brings it up. If the run is still being worked and the server is in fact gone, that next P1 — or an explicit `/resolve-issue-dashboard` — starts it cleanly through the singleton check above, so nothing is lost by leaving the bare notification alone.

## What the dashboard shows

- **Run panel (left)** — every resolve run discovered across your repos (repo, ticket, a coarse status dot — done / paused / active / idle — and last activity). Click one to switch the main view to it; the repo you launched from is selected by default. The list status is next-step-based only; the precise running / paused / blocked status is in the selected run's header (the list cannot tell them apart without tailing each repo).
- **Header + status pill** — the selected run's ticket, work and base branch, and a coloured status: running, paused (at a gate), blocked (needs you to unblock it), or done.
- **Pipeline** — the twelve steps (`a-fact-check` … `done`) as nodes; status is derived from `state.md`'s `next-step` (earlier steps completed, the current one running or paused, later ones pending). Each completed node also shows its wall-clock beneath the label, and a step re-entered by a gate revise shows a `×N` count — both read from the run's append-only `timings.md`, so you can see which step ate the run's time.
- **Agent activity** — the live tool-call stream from the session and its subagents, so you can see what each component's writer/verifier is doing (tool, target, status, duration).
- **Stat cards** — pipeline step `N/12`, active duration, tool-call count, and tokens in/out.
- **Gate banner** — when the run is paused at the plan-approval gate, an amber banner reminds you to respond in the Claude Code terminal.
- **Test-contention banner** — a global warning appears when two or more runs (any repo) are positioned at a test-executing step (the ones that run integration / component tests). Those steps share one host container stack — Podman, SQL, and Azurite — so running them at once can conflict, race, or starve. The banner names the colliding runs so you can stagger them; it only warns, since the dashboard never controls a run.

Updates arrive over Server-Sent Events at message granularity (Claude Code flushes the transcript per message), so the view is near-real-time rather than token-by-token.

## Degradation and safety

- **Run discovery** — a repo appears in the panel once it has a Claude session and a `.claude/resolve/<ticket>/`; the repo you launched from always shows (as a placeholder before its first run), and a repo whose path no longer exists is skipped.
- **No `.claude/resolve/<ticket>/` yet** — before `resolve-issue` creates its handoff dir, that run's pipeline shows all-pending; it fills in as soon as `state.md` appears.
- **Several runs in one repo** — each ticket's *live* run (the top-level `.claude/resolve/<ticket>/`) is one entry; runs that ticket has superseded are archived into timestamp subdirs and listed as their own history entries, labelled `<ticket> · <stamp>`. Pick the one you want rather than relying on a guess.
- **Selecting a past (archived) run** — a history entry renders statically from its own `state.md` (pipeline position and run-scoped duration); it does not tail a live session, so it shows no live activity feed (that belongs to the live run), and the contention warning counts live runs only, never archived ones.
- **New session / resumed run** — the selected run always follows that repo's most recently active session, so resuming `resolve-issue` in a fresh session keeps the view live.
- **Port 4317 held by another app** — the server picks the next free port and prints it; the singleton `/health` check only reuses a server that identifies as `resolve-issue-dashboard` **and reports the installed version**, so neither an unrelated process on 4317 nor a stale older dashboard is silently reused (the launch step replaces a version-mismatched one).
- **Pipeline definition** — the step ids, labels, components, and order come from the shared registry `issue-to-pr-pipeline/resources/resolve-issue-steps.json` (loaded at startup; an embedded copy is the fallback if it cannot be read). Add, rename, or reorder a step there and the dashboard picks it up — no code change. A `next-step` value absent from the registry still degrades the pipeline to idle / all-pending rather than guessing a position.
- **Which steps trigger the contention warning** — the same registry marks them with `runsTests: true`, so the warning tracks the registry too: mark a new test-running step there and it joins the check, no code change. The count is cursor-based (a run parked at the step counts even if its session is momentarily idle), so it reads as "positioned to collide", not a claim that tests are executing this instant — honest given the run list never tails each repo.
- **Metrics are session-scoped (except active duration)** — the tool-call count and tokens cover the whole Claude session, not only the `resolve-issue` run, so they read cleanest in a session dedicated to the run; the activity stream's tail still reflects what is happening right now regardless. **Active duration is run-scoped**: it reads the `started` / `ended` UTC timestamps `resolve-issue` records in `state.md`, so it stays correct even when you reopen a finished run later from a newer session — it ticks every second while the run is live (a heartbeat that keeps moving even while paused at a gate) and freezes at `ended` once done. A run that predates these timestamps (no `started` field) falls back to the session-derived anchors (first event / `state.md` mtime), which can read `-` when viewed from a different session — the only residual session-scoping for duration.
- **Per-step durations** — read from the run's append-only `timings.md`, which `resolve-issue` appends to at each step boundary. A run that predates the log (or whose `timings.md` is absent or malformed) simply shows no per-step wall-clock and renders exactly as before — the log is pure observability, so its absence is never an error. Re-entered steps (a gate revise, a future rework loop) sum their spans and show a `×N` count rather than overwriting, and an archived run keeps its own `timings.md`, so history entries show their durations too.
- **Read-only always** — this skill observes; it never advances the pipeline, answers a gate, opens a PR, or edits files. Those happen in the Claude Code terminal via `resolve-issue` and the component skills.
