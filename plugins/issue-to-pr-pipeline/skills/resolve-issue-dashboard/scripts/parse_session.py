"""Locate and parse the live Claude Code transcript for a resolve-issue run,
and build a read-only progress model the dashboard renders.

This is a pure observer: it only reads files Claude Code already writes
(`~/.claude/projects/<encoded-cwd>/<session>.jsonl` plus that session's
`<session>/subagents/agent-*.jsonl`) and the orchestrator's
`.claude/resolve/<ticket>/state.md` and per-step `timings.md`. It never writes
to either.

Run standalone for a dry-run of the model:
    python parse_session.py [--cwd PATH] [--ticket TICKET]
"""

import argparse
import base64
import glob
import json
import os
import re
from datetime import datetime, timezone


# the resolve-issue pipeline skeleton. Canonical source is the plugin resource
# resources/resolve-issue-steps.json (shared with resolve-issue, the registry of
# record); this embedded copy is only a fallback if that file cannot be read, so
# the dashboard never breaks on a missing resource. The JSON wins when present.
_DEFAULT_STEPS = [
    {"id": "a-fact-check", "label": "Fact-check issue", "component": "review-issue-fact", "gate": False},
    {"id": "a-elicit-decisions", "label": "Resolve decisions", "component": None, "gate": False},
    {"id": "a-draft-plan", "label": "Draft plan", "component": None, "gate": False},
    {"id": "a-harden-plan", "label": "Harden plan", "component": "review-plan-risk", "gate": False},
    {"id": "a-gate-approve", "label": "Plan approval", "component": None, "gate": True},
    {"id": "b-implement", "label": "Implement fix", "component": None, "gate": False},
    {"id": "b-write-tests", "label": "Write tests", "component": "test-authoring", "gate": False, "runsTests": True},
    {"id": "b-commit-tests", "label": "Prepare for review", "component": None, "gate": False},
    {"id": "b-security-review", "label": "Review security", "component": "security-review", "gate": False, "runsTests": True},
    {"id": "b-code-risk", "label": "Finalise fix", "component": "review-code-risk", "gate": False, "runsTests": True},
    {"id": "b-open-pr", "label": "Open PR", "component": "open-pr", "gate": False},
    {"id": "done", "label": "Done", "component": None, "gate": False},
]


def _load_steps():
    """Load the canonical step registry from the plugin resource; fall back to
    the embedded default if it is missing or malformed."""
    path = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "resources", "resolve-issue-steps.json"))
    try:
        with open(path, encoding="utf-8") as f:
            raw = json.load(f).get("steps") or []
        steps = []
        for s in raw:
            if isinstance(s, dict) and s.get("id"):
                steps.append({
                    "id": s["id"],
                    "label": s.get("label") or s["id"],
                    "component": s.get("component"),
                    "gate": bool(s.get("gate")),
                    "runsTests": bool(s.get("runsTests")),
                })
        if steps:
            return steps
    except (OSError, ValueError):
        pass
    return _DEFAULT_STEPS


STEPS = _load_steps()
STEP_IDS = [s["id"] for s in STEPS]

# steps that pause for a human gate in the CLI (the orchestrator waits here)
GATE_STEPS = {s["id"] for s in STEPS if s["gate"]}
GATE_LABELS = {s["id"]: s["label"] for s in STEPS if s["gate"]}

# steps that execute integration / component tests against the shared host
# container stack (Podman + SQL + Azurite); two runs here at once contend for it
TEST_STEPS = {s["id"] for s in STEPS if s.get("runsTests")}

STATE_FIELDS = [
    "next-step",
    "ticket",
    "base-branch",
    "work-branch",
    "plan-approved",
    "pr-url",
    "attention",
    "started",
    "ended",
]


# ----- path resolution -------------------------------------------------------

def projects_root():
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


def encode_cwd(cwd):
    """Mirror Claude Code's project-dir naming: every non-alphanumeric character
    in the absolute cwd becomes a dash.

    Example: C:\\Users\\alex\\source\\repos\\my-service
          -> C--Users-alex-source-repos-my-service
    """
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd))


def find_project_dir(cwd):
    """Resolve the ~/.claude/projects directory for this cwd.

    Prefer the deterministic encoding; fall back to a case-insensitive match,
    then to the project dir holding the most recently touched session, so an
    encoding edge case degrades to a best guess rather than failing outright.
    """
    root = projects_root()
    if not os.path.isdir(root):
        return None
    enc = encode_cwd(cwd)
    cand = os.path.join(root, enc)
    if os.path.isdir(cand):
        return cand
    dirs = [d for d in glob.glob(os.path.join(root, "*")) if os.path.isdir(d)]
    for d in dirs:
        if os.path.basename(d).lower() == enc.lower():
            return d
    newest = None
    newest_mtime = -1.0
    for d in dirs:
        sessions = glob.glob(os.path.join(d, "*.jsonl"))
        for s in sessions:
            m = os.path.getmtime(s)
            if m > newest_mtime:
                newest_mtime = m
                newest = d
    return newest


def _session_mentions(path, ticket):
    """Cheap head-scan: does this session's opening reference the ticket? A
    resolve-issue run's driving session starts with the `/resolve-issue <ticket>`
    invocation, so a bounded read of the first records tells it apart from an
    unrelated session in the same repo. Best-effort - any read issue returns
    False, and the caller falls back to the newest session."""
    if not ticket:
        return False
    tl = ticket.lower()
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 40:
                    break
                if tl in line.lower():
                    return True
    except OSError:
        pass
    return False


def find_live_session(project_dir, ticket=None):
    """The live session is the most recently modified top-level *.jsonl
    (subagent transcripts live one level down and are excluded here). When a
    `ticket` is given, prefer the newest session that references that ticket, so
    an unrelated newer session in the same repo cannot hijack the view (the
    metrics/activity/gate cues are session-derived); fall back to the newest
    overall when none reference it (no regression from the ticketless behaviour)."""
    if not project_dir:
        return None
    files = glob.glob(os.path.join(project_dir, "*.jsonl"))
    if not files:
        return None
    files.sort(key=os.path.getmtime, reverse=True)
    if ticket:
        for f in files:
            if _session_mentions(f, ticket):
                return f
    return files[0]


def session_id_of(session_path):
    return os.path.basename(session_path)[: -len(".jsonl")]


def subagent_files(project_dir, session_id):
    sub = os.path.join(project_dir, session_id, "subagents")
    if not os.path.isdir(sub):
        return []
    return sorted(glob.glob(os.path.join(sub, "agent-*.jsonl")))


_cwd_cache = {}


def session_cwd(path):
    """Read the repo cwd recorded in a transcript. The first lines may be
    non-message entries (mode / permission-mode) without a cwd, so scan a few
    until one carries it. Cached, since a transcript's cwd never changes."""
    if not path:
        return None
    if path in _cwd_cache:
        return _cwd_cache[path]
    cwd = None
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                if i >= 12:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                except ValueError:
                    continue
                if o.get("cwd"):
                    cwd = o["cwd"]
                    break
    except OSError:
        pass
    _cwd_cache[path] = cwd
    return cwd


def run_id(cwd, ticket, run_key=""):
    """Stable, URL-safe id for a (repo, ticket, run) - survives list reordering.
    run_key is "" for the live run at the ticket top-level, or the archived run's
    timestamp subdir name for a historical run."""
    raw = (os.path.abspath(cwd) + "::" + (ticket or "") + "::" + (run_key or "")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_run_id(rid):
    if not rid:
        return None, None, ""
    pad = "=" * (-len(rid) % 4)
    try:
        raw = base64.urlsafe_b64decode(rid + pad).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None, None, ""
    if "::" not in raw:
        return None, None, ""
    # "cwd::ticket::run_key" - neither a path, a ticket, nor a stamp contains "::",
    # and a legacy 2-part id (no run_key) decodes to the live run (run_key "")
    parts = raw.split("::")
    cwd = parts[0]
    ticket = parts[1] if len(parts) > 1 else ""
    run_key = parts[2] if len(parts) > 2 else ""
    return cwd, (ticket or None), run_key


def resolve_dir_for(cwd, ticket, run_key=""):
    d = os.path.join(cwd, ".claude", "resolve", ticket)
    # a historical run lives in a timestamp subdir; the live run is the top-level
    return os.path.join(d, run_key) if run_key else d


def find_resolve_ticket(cwd, explicit=None):
    """Pick the ticket whose resolve dir we observe: explicit wins, else the
    most recently touched `.claude/resolve/<ticket>/` directory."""
    if explicit:
        return explicit
    base = os.path.join(cwd, ".claude", "resolve")
    if not os.path.isdir(base):
        return None
    dirs = [d for d in glob.glob(os.path.join(base, "*")) if os.path.isdir(d)]
    if not dirs:
        return None
    newest = max(dirs, key=os.path.getmtime)
    return os.path.basename(newest)


# ----- state.md --------------------------------------------------------------

def parse_state(path):
    """Read the orchestrator's cursor. Tolerant of light markdown decoration
    (`- **next-step:** b-write-tests` etc.); expects one `field: value` per line."""
    state = {}
    if not path or not os.path.isfile(path):
        return state
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return state
    for key in STATE_FIELDS:
        # the value must stay on the field's own line:
        # a \s gap after the colon crosses the newline and captures the next field,
        # so an empty field (e.g. `attention:`) swallowed the following `started:`
        # line and the run rendered as blocked.
        # horizontal whitespace only, and the value is optional,
        # so an empty field reads as empty rather than borrowing the next field
        pattern = r"(?im)^[ \t>\-*`|]*" + re.escape(key) + r"[ \t`*]*[:=][ \t]*(.*?)[ \t]*$"
        m = re.search(pattern, text)
        if m:
            state[key] = m.group(1).strip().strip("`*|").strip()
    return state


# ----- transcript parsing ----------------------------------------------------

def tool_target(inp):
    """Pull a short human-meaningful target out of a tool's input, matching the
    fields agent-ui keys on plus Task/Agent's description."""
    if inp is None:
        return ""
    if isinstance(inp, str):
        try:
            inp = json.loads(inp)
        except ValueError:
            return inp.replace("./", "", 1)
    if isinstance(inp, dict):
        for key in (
            "skill", "file_path", "path", "filePath", "filename", "pattern",
            "file", "command", "url", "description", "prompt", "query",
        ):
            v = inp.get(key)
            if isinstance(v, str) and v:
                return v
    return ""


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


class Collector:
    """Incrementally tails the live session and its subagent transcripts.

    State is kept across refreshes (byte offset per file, accumulated tool
    events, cached agent labels) so a long-running session is read once, not
    re-scanned every tick.
    """

    def __init__(self, project_dir, session_path):
        self.project_dir = project_dir
        self.session_path = session_path
        self.session_id = session_id_of(session_path) if session_path else None
        self._offsets = {}
        self._buffers = {}
        self._events = []
        self._pending = {}
        self._labels = {}
        self.tokens_in = 0
        self.tokens_out = 0
        # per-record output-token samples (ts + output_tokens), retained so
        # build_model can bucket them into per-step windows. only records that
        # actually produced output are kept; summing per window is
        # order-independent, so a late out-of-order sample just lands in its
        # window. includes subagent records (a step's tokens then cover its fan-out)
        self._token_records = []
        # whether the MAIN session is mid-work vs has yielded control to the user;
        # updated per main-session line, so it reflects the last one read. defaults
        # False so a run with no transcript keeps the cursor-only reading
        self._main_active = False
        # whether ANY main-session line has been read at all. distinguishes a
        # genuine yield (a main turn ended in end_turn) from the default-False of a
        # run we never tailed - only the former should read as "waiting for you"
        self._main_seen = False

    def refresh(self):
        """Read any bytes appended since the last call across the session file
        and every subagent file, parsing newly completed lines."""
        if self.session_path and os.path.isfile(self.session_path):
            self._consume(self.session_path, "main")
        for path in subagent_files(self.project_dir, self.session_id):
            self._consume(path, self._label_for(path))

    def _label_for(self, path):
        if path in self._labels:
            return self._labels[path]
        short = os.path.basename(path)
        short = short.replace("agent-", "").replace(".jsonl", "")[:8]
        label = "agent " + short
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    o = json.loads(line)
                    if o.get("type") != "user":
                        continue
                    content = (o.get("message") or {}).get("content")
                    txt = ""
                    if isinstance(content, str):
                        txt = content
                    elif isinstance(content, list):
                        txt = " ".join(
                            b.get("text", "")
                            for b in content
                            if isinstance(b, dict) and b.get("type") == "text"
                        )
                    txt = txt.strip()
                    if txt and not txt.startswith("<"):
                        label = "agent " + short + ": " + txt[:48]
                    break
        except (OSError, ValueError):
            pass
        self._labels[path] = label
        return label

    def _consume(self, path, agent):
        try:
            size = os.path.getsize(path)
        except OSError:
            return
        offset = self._offsets.get(path, 0)
        if size < offset:
            # file was truncated/rotated; restart from the top
            offset = 0
            self._buffers[path] = b""
        if size == offset:
            return
        try:
            with open(path, "rb") as f:
                f.seek(offset)
                chunk = f.read(size - offset)
        except OSError:
            return
        self._offsets[path] = size
        # buffer raw bytes and decode only complete lines, so a multi-byte
        # character split across a read boundary is never mangled
        data = self._buffers.get(path, b"") + chunk
        last_nl = data.rfind(b"\n")
        if last_nl < 0:
            self._buffers[path] = data
            return
        complete, self._buffers[path] = data[:last_nl], data[last_nl + 1:]
        for raw in complete.split(b"\n"):
            line = raw.decode("utf-8", "replace").strip()
            if line:
                self._parse_line(line, agent)

    def _parse_line(self, line, agent):
        try:
            o = json.loads(line)
        except ValueError:
            return
        if o.get("type") not in ("user", "assistant"):
            return
        msg = o.get("message") or {}
        ts = o.get("timestamp")
        # tell 'approaching a human gate' from 'actually parked at it': track
        # whether the MAIN session is still working. a main assistant turn ending
        # in tool_use means work continues; any other stop (end_turn / stop_sequence)
        # hands control back to the user. a user line is a tool_result being fed
        # back or the human's reply, so the loop is about to run either way.
        # verified on live transcripts: an end_turn is never resumed by a tool_use
        # without an intervening user line, so end_turn cleanly marks the yield
        if agent == "main":
            self._main_seen = True
            if o.get("type") == "assistant":
                self._main_active = (msg.get("stop_reason") == "tool_use")
            else:
                self._main_active = True
        usage = msg.get("usage")
        if usage:
            self.tokens_in += usage.get("input_tokens", 0) or 0
            out_tok = usage.get("output_tokens", 0) or 0
            self.tokens_out += out_tok
            # keep a per-step-bucketable sample; only assistant turns carry a
            # non-zero output_tokens, so this is effectively per-turn model output
            if out_tok and ts:
                self._token_records.append({"ts": ts, "output_tokens": out_tok})
        content = msg.get("content")
        if not isinstance(content, list):
            return
        for b in content:
            if not isinstance(b, dict):
                continue
            bt = b.get("type")
            if bt == "tool_use":
                ev = {
                    "agent": agent,
                    "tool": b.get("name"),
                    "target": tool_target(b.get("input")),
                    "status": "running",
                    "ts": ts,
                    "endTs": None,
                }
                self._events.append(ev)
                if b.get("id"):
                    self._pending[b["id"]] = ev
            elif bt == "tool_result":
                ev = self._pending.pop(b.get("tool_use_id"), None)
                if ev is not None:
                    ev["status"] = "error" if b.get("is_error") else "success"
                    ev["endTs"] = ts

    def events(self):
        return self._events

    def token_records(self):
        """Per-record {ts, output_tokens} samples, for per-step bucketing."""
        return self._token_records

    def main_active(self):
        """True while the main session is mid-work (a tool call is imminent or a
        tool result / human reply is about to be processed), False once its turn
        has yielded to the user or nothing has been read yet. Lets the model tell
        'approaching a human gate' from 'actually parked at it'."""
        return self._main_active

    def main_seen(self):
        """True once any main-session line has been read. Paired with a False
        main_active it means a genuine yield (the main turn ended, awaiting the
        human); without it a never-tailed run's default-False main_active would
        read as a false 'waiting for you'."""
        return self._main_seen


def _elapsed_ms(start, end):
    a, b = parse_ts(start), parse_ts(end)
    if not a or not b:
        return None
    return int((b - a).total_seconds() * 1000)


def _earliest_ms(events):
    """Epoch-ms of the run's first recorded tool call - the start anchor for the
    elapsed duration. Uses min, not events[0], because subagent events are
    appended out of order during a refresh."""
    starts = [t for t in (parse_ts(e.get("ts")) for e in events) if t]
    if not starts:
        return None
    return int(min(starts).timestamp() * 1000)


def _mtime_ms(path):
    """Epoch-ms mtime of a file, or None if it cannot be read. Never raises - a
    missing state.md (a run before its handoff dir exists) must not abort the
    build_model caller, which would surface as an {"error"} payload."""
    try:
        return int(os.path.getmtime(path) * 1000)
    except OSError:
        return None


def _iso_to_ms(s):
    """Epoch-ms of an ISO 8601 timestamp written into state.md, or None. The
    contract is UTC-with-Z, but a value that lost its Z would parse tz-naive and
    `.timestamp()` would read it as local time - skewing it against the run's
    state.md mtime by the local offset - so a naive value is pinned to UTC."""
    dt = parse_ts(s)
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# ----- per-step timing -------------------------------------------------------

def parse_timings(path):
    """Read the orchestrator's append-only per-step timing log
    (`.claude/resolve/<ticket>/timings.md`): one markdown line per step entry,
    `- <UTC-ISO-Z> <step-id>`. resolve-issue appends a line each time it enters a
    step, so a step re-entered by a Phase A gate revise (or a future Phase B
    rework loop) appears more than once, in file order. Tolerant of light
    markdown decoration and non-fatal - a missing or malformed file yields no
    entries, never an error, the same contract as parse_state."""
    entries = []
    if not path or not os.path.isfile(path):
        return entries
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
    except OSError:
        return entries
    for line in text.splitlines():
        m = re.match(
            r"^[ \t>\-*`]*([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z)[ \t]+([A-Za-z][A-Za-z0-9-]*)",
            line.strip())
        if not m:
            continue
        ts, step = m.group(1), m.group(2)
        # an id not in the registry (a typo, a renamed step) is skipped rather
        # than charted at a guessed position - the rule build_model's cursor uses
        # for an unknown next-step
        if step in STEP_IDS and parse_ts(ts):
            entries.append({"ts": ts, "step": step})
    return entries


def compute_step_durations(entries):
    """Pure: fold ordered timing entries into per-step wall-clock. Each entry
    marks entry INTO a step, so a step's span runs from its own entry to the next
    entry; the final entry is still open (running) unless it is the terminal
    `done`. Repeated entries for one step sum into its total and bump its count,
    so a re-entry's cost is measured rather than overwritten - the reason the log
    is a separate append-only file, not flat state.md fields. Returns
    {step-id: {durationMs, occurrences, open}}, durationMs None for a step with no
    closed span yet (only an open entry so far)."""
    out = {}
    n = len(entries)
    for i, e in enumerate(entries):
        step = e["step"]
        rec = out.setdefault(step, {"durationMs": None, "occurrences": 0, "open": False})
        rec["occurrences"] += 1
        if i + 1 < n:
            dur = _elapsed_ms(e["ts"], entries[i + 1]["ts"])
            # drop a non-positive span (a clock that went backwards across a
            # resume on another machine) rather than charting negative time
            if dur is not None and dur > 0:
                rec["durationMs"] = (rec["durationMs"] or 0) + dur
        elif step != "done":
            rec["open"] = True
    return out


def compute_step_activity(entries, token_records):
    """Pure: bucket per-record output_tokens into the step windows defined by the
    timings entries, summing per step-id. `token_records` is a list of
    {ts, output_tokens}. A record whose ts falls in [entries[i].ts,
    entries[i+1].ts) is attributed to entries[i].step (the last/open window
    extends to +inf); a record before the first entry (preamble) is skipped.
    Summing is order-independent - a late out-of-order sample lands in its window
    regardless of arrival order - so this is safe to recompute each build. Returns
    {step-id: tokensOut}. A window that changed step-id back (a re-entry) sums
    into that step across all its occurrences, matching compute_step_durations."""
    out = {}
    n = len(entries)
    if n == 0:
        return out
    bounds = [_iso_to_ms(e["ts"]) for e in entries]
    for rec in token_records:
        ms = _iso_to_ms(rec.get("ts"))
        tok = rec.get("output_tokens") or 0
        if ms is None or tok <= 0:
            continue
        for i in range(n):
            lo = bounds[i]
            if lo is None or ms < lo:
                continue
            hi = bounds[i + 1] if i + 1 < n else None
            if hi is None or ms < hi:
                out[entries[i]["step"]] = out.get(entries[i]["step"], 0) + tok
                break
    return out


def _is_blocked(attention):
    """A run is blocked (needs human disposition) when state.md carries a
    non-empty `attention` note - set by resolve-issue whenever it is waiting on
    the human (at the b-code-risk-to-b-open-pr checkpoint, and while `open-pr` waits for its
    create confirmation at b-open-pr) and cleared the moment that wait ends and the run
    resumes (not at the next-step transition). Liberal: any truthy reason counts."""
    a = (attention or "").strip().lower()
    return a not in ("", "no", "false", "none", "0")


def overall_status(next_step):
    """Derive the run-level status from the cursor. An in-progress step reads
    `running`; the genuinely-distinct waits get their own states (`paused` at a
    gate, `blocked` via the attention note, set by the caller). We deliberately
    do not flip to a quiet 'waiting' state on transcript silence - gaps are
    normal (the model thinking, a long tool call, or a subagent writing its own
    transcript) and reading them as 'waiting' was misleading."""
    if next_step == "done":
        return "done"
    if next_step in GATE_STEPS:
        return "paused"
    if next_step not in STEP_IDS:
        return "idle"
    return "running"


def list_status(next_step):
    """Coarse status for the run-list summary - next-step only, no tailing
    (done / paused at a gate / active / idle). A repo's newest session may
    belong to unrelated work, so the list stays cursor-based; the precise live
    status lives in the selected run's model."""
    if next_step == "done":
        return "done"
    if next_step in GATE_STEPS:
        return "paused"
    if next_step not in STEP_IDS:
        return "idle"
    return "active"


def build_model(state, events, tokens_in, tokens_out, session_meta, ended_ms=None, main_active=False, timings=None, main_seen=False, token_records=None):
    """Assemble the read-only progress model from the cursor plus the parsed
    activity. Pure: no I/O, no clock reads. `ended_ms` is the run's last-progress
    time (state.md mtime) supplied by the caller; defaults to None so the dry-run
    caller (collect_model) stays valid without it. `main_active` is the tailed
    main session's liveness (defaults False, so a caller with no transcript keeps
    the cursor-only reading); it demotes a not-yet-reached gate to running.
    `timings` is the parsed timings.md entries (defaults to empty, so a caller
    without them keeps the durationless reading), folded into per-step
    durationMs / occurrences. `main_seen` (defaults False) is whether any
    main-session line was read; paired with a False `main_active` it marks a
    genuine yield-to-human on a step that is neither a gate nor attention-flagged
    (e.g. a-elicit-decisions asking a question), which reads as waiting.
    `token_records` (defaults empty) are per-record {ts, output_tokens} samples,
    bucketed into per-step `activity.tokensOut` - the compute signal that tells a
    slow step that was computing from one that was waiting (a slow step with low
    tokensOut was mostly idle)."""
    next_step = state.get("next-step")
    step_durations = compute_step_durations(timings or [])
    step_tokens = compute_step_activity(timings or [], token_records or [])
    cur_idx = STEP_IDS.index(next_step) if next_step in STEP_IDS else -1
    is_done = next_step == "done"
    blocked = _is_blocked(state.get("attention"))
    at_gate = next_step in GATE_STEPS
    # the cursor (a gate step) or a set attention note says we are AT a human
    # gate, but the tailed session can show the main loop is still working toward
    # it and has not yet yielded control - e.g. b-open-pr sets attention BEFORE open-pr
    # spends time drafting, and the a-gate-approve cursor flips while the plan is still
    # being rendered. treat that in-progress window as running, not
    # waiting-for-you, so the amber attention cue fires only once the
    # session actually parks at the gate rather than the moment it enters the step
    approaching = bool(main_active) and (blocked or at_gate)
    # the session ended its turn and yielded to the human on a step the cursor
    # cannot flag as a wait - the orchestrator asked a question mid-step
    # (a-elicit-decisions, a fact-check HALT, a b-write-tests targeted question).
    # this is the positive end_turn signal, NOT transcript silence (gaps are
    # normal: a long tool call, a subagent writing its own transcript), and it is
    # gated on main_seen so a never-tailed run's default-False does not read as a
    # false wait. it never competes with a gate / attention (those own the wait),
    # nor with a done / unknown cursor
    yielded = (bool(main_seen) and not bool(main_active)
               and not at_gate and not blocked and not is_done and cur_idx >= 0)

    steps = []
    for i, s in enumerate(STEPS):
        if is_done:
            status = "completed"
        elif cur_idx < 0:
            status = "pending"
        elif i < cur_idx:
            status = "completed"
        elif i == cur_idx:
            # a non-empty attention note means the current step is stuck waiting
            # on the human, which outranks the running / gate-paused reading -
            # unless the session is only approaching the gate and still running.
            # a plain yield on a non-gate step is also a wait (paused), whereas a
            # non-gate step still working reads running
            if approaching:
                status = "running"
            elif blocked:
                status = "blocked"
            elif s["id"] in GATE_STEPS:
                status = "paused"
            elif yielded:
                status = "paused"
            else:
                status = "running"
        else:
            status = "pending"
        td = step_durations.get(s["id"])
        steps.append({
            "id": s["id"],
            "label": s["label"],
            "component": s["component"],
            "gate": s["id"] in GATE_STEPS,
            "status": status,
            "durationMs": (td["durationMs"] if td else None),
            "occurrences": (td["occurrences"] if td else 0),
            "activity": {"tokensOut": step_tokens.get(s["id"], 0)},
        })

    overall = overall_status(next_step)
    if blocked:
        overall = "blocked"
    elif yielded:
        overall = "paused"
    if approaching:
        overall = "running"

    # suppress the gate / blocked payload while only approaching: the client raises
    # the amber attention layer (frame + core takeover + screen-reader alert)
    # purely on these being present, so leaving them null keeps the cue off until
    # the session genuinely parks
    gate = None
    if next_step in GATE_STEPS and not approaching:
        gate = {"step": next_step, "label": GATE_LABELS.get(next_step, next_step)}

    blocked_info = None
    if blocked and not approaching:
        blocked_info = {"step": next_step, "reason": state.get("attention")}

    # a plain yield-to-human on a non-gate, non-attention step: the orchestrator
    # asked a question and parked. same amber "waiting for you" cue as a gate, but
    # keyed on the tailed session rather than the cursor, so a step the registry
    # cannot flag as a gate still shows as waiting
    awaiting = None
    if yielded:
        awaiting = {"step": next_step,
                    "label": next((s["label"] for s in STEPS if s["id"] == next_step), next_step)}

    activity = []
    for ev in events:
        activity.append({
            "agent": ev["agent"],
            "tool": ev["tool"],
            "target": ev["target"],
            "status": ev["status"],
            "ts": ev["ts"],
            "elapsedMs": _elapsed_ms(ev["ts"], ev["endTs"]),
        })
    activity.sort(key=lambda e: e["ts"] or "")
    activity = activity[-60:]

    # prefer the run-scoped timestamps resolve-issue writes into state.md; fall
    # back to the session-derived anchors for older runs that predate them (the
    # first tool event for start, the caller's state.md mtime for end)
    started_ms = _iso_to_ms(state.get("started")) or _earliest_ms(events)
    ended_ms = _iso_to_ms(state.get("ended")) or ended_ms

    model = {
        "ticket": state.get("ticket"),
        "baseBranch": state.get("base-branch"),
        "workBranch": state.get("work-branch"),
        "planApproved": (state.get("plan-approved", "").lower() in ("yes", "true")),
        "prUrl": state.get("pr-url"),
        "nextStep": next_step,
        "status": overall,
        "gate": gate,
        "blocked": blocked_info,
        "awaitingInput": awaiting,
        "steps": steps,
        "activity": activity,
        "metrics": {
            "stepIndex": (cur_idx + 1) if cur_idx >= 0 else 0,
            "stepCount": len(STEPS),
            "toolCalls": len(events),
            # elapsed anchored to the run's own timeline: startedMs is the first
            # event, endedMs is the run's state.md mtime (stable - the dashboard
            # never writes state.md, so reopening it the next day cannot inflate
            # a finished run). the client ticks now-startedMs while live and
            # freezes at endedMs-startedMs when done
            "startedMs": started_ms,
            "endedMs": ended_ms,
            "live": overall in ("running", "paused", "blocked"),
            "tokens": {"input": tokens_in, "output": tokens_out},
        },
        "session": session_meta,
    }
    return model


def collect_model(cwd, ticket):
    """One-shot convenience used by the dry-run CLI and the server's first
    build: locate everything, read it all, and return the model."""
    cwd = os.path.abspath(cwd)
    project_dir = find_project_dir(cwd)
    session_path = find_live_session(project_dir, ticket)
    resolve_dir = resolve_dir_for(cwd, ticket) if ticket else None
    state_path = os.path.join(resolve_dir, "state.md") if resolve_dir else None
    state = parse_state(state_path) if state_path else {}
    ended_ms = _mtime_ms(state_path) if state_path else None
    timings = parse_timings(os.path.join(resolve_dir, "timings.md")) if resolve_dir else []

    session_meta = {
        "id": session_id_of(session_path) if session_path else None,
        "projectDir": project_dir,
        "cwd": cwd,
    }
    events, tokens_in, tokens_out = [], 0, 0
    main_active = False
    main_seen = False
    token_records = []
    if session_path:
        collector = Collector(project_dir, session_path)
        collector.refresh()
        events = collector.events()
        tokens_in, tokens_out = collector.tokens_in, collector.tokens_out
        main_active = collector.main_active()
        main_seen = collector.main_seen()
        token_records = collector.token_records()

    return build_model(state, events, tokens_in, tokens_out, session_meta, ended_ms, main_active, timings, main_seen, token_records)


def _pretty_stamp(s):
    """Render an archive timestamp dir name (YYYY-MM-DDTHH-MM-SSZ) as a compact
    'YYYY-MM-DD HH:MM' label; fall back to the raw name if it is not a stamp."""
    try:
        date, sep, t = s.partition("T")
        if not sep:
            return s
        bits = t.rstrip("Z").split("-")
        return date + " " + bits[0] + ":" + bits[1]
    except (IndexError, ValueError):
        return s


def _run_summary(cwd, ticket, run_key, run_stamp, state_path, dir_path):
    """One coarse run-list entry from a run's own state.md (no tailing). Status is
    next-step-only on purpose (see list_status); recency is the run's own state.md
    mtime, else its dir, so a finished past run keeps its own time. ticket is the
    bare ticket; run_stamp is "" for the live run or the pretty archive stamp for a
    historical run - the dashboard groups by repo/ticket and composes the label."""
    state = parse_state(state_path)
    next_step = state.get("next-step")
    status = "blocked" if _is_blocked(state.get("attention")) else list_status(next_step)
    mtime_src = state_path if os.path.isfile(state_path) else dir_path
    try:
        last_ms = int(os.path.getmtime(mtime_src) * 1000)
    except OSError:
        last_ms = None
    return {
        "id": run_id(cwd, ticket, run_key),
        "repo": os.path.basename(cwd),
        "cwd": cwd,
        "ticket": ticket,
        "runKey": run_key,
        "runStamp": run_stamp,
        "nextStep": next_step,
        "status": status,
        "lastActivityMs": last_ms,
    }


def runs_for_cwd(cwd):
    """Lightweight run summaries for one repo - no tailing, just state.md. The
    live run sits at the ticket top-level (.claude/resolve/<ticket>/state.md);
    superseded runs are archived into timestamp subdirs
    (.claude/resolve/<ticket>/<stamp>/) and surface as their own history entries,
    labelled `<ticket> . <stamp>` so the flat run list distinguishes same-ticket
    runs. Status is coarse (list_status); each run's recency is its own state.md."""
    cwd = os.path.abspath(cwd)
    out = []
    base = os.path.join(cwd, ".claude", "resolve")
    if not os.path.isdir(base):
        return out
    for td in glob.glob(os.path.join(base, "*")):
        if not os.path.isdir(td):
            continue
        ticket = os.path.basename(td)
        # archived runs: subdirs carrying their own state.md
        hist = [sd for sd in sorted(glob.glob(os.path.join(td, "*")))
                if os.path.isdir(sd) and os.path.isfile(os.path.join(sd, "state.md"))]
        live_state = os.path.join(td, "state.md")
        # emit the live (top-level) run when it has a state.md, or when nothing is
        # archived yet (a freshly-created dir still shows as a pending run); skip
        # the phantom top-level entry only when every run for this ticket is archived
        if os.path.isfile(live_state) or not hist:
            out.append(_run_summary(cwd, ticket, "", "", live_state, td))
        for sd in hist:
            stamp = os.path.basename(sd)
            out.append(_run_summary(cwd, ticket, stamp, _pretty_stamp(stamp),
                                    os.path.join(sd, "state.md"), sd))
    return out


def list_runs(launch_cwd=None):
    """Discover every resolve run across all repos: enumerate the projects
    root, map each project dir to its repo cwd via the transcript, and collect
    the .claude/resolve/<ticket>/ runs there. The launch cwd is always included
    (with a placeholder if it has no run yet) so the caller sees its own repo."""
    runs = {}
    seen = set()
    root = projects_root()
    if os.path.isdir(root):
        for d in glob.glob(os.path.join(root, "*")):
            if not os.path.isdir(d):
                continue
            session = find_live_session(d)
            cwd = session_cwd(session) if session else None
            if not cwd:
                continue
            cwd = os.path.abspath(cwd)
            if cwd in seen or not os.path.isdir(cwd):
                continue
            seen.add(cwd)
            for r in runs_for_cwd(cwd):
                runs[r["id"]] = r
    if launch_cwd:
        lc = os.path.abspath(launch_cwd)
        lc_runs = runs_for_cwd(lc)
        if lc_runs:
            for r in lc_runs:
                runs.setdefault(r["id"], r)
        else:
            rid = run_id(lc, None)
            runs.setdefault(rid, {
                "id": rid, "repo": os.path.basename(lc), "cwd": lc,
                "ticket": None, "nextStep": None, "status": "idle", "lastActivityMs": None,
            })
    return sorted(runs.values(), key=lambda r: r["lastActivityMs"] or 0, reverse=True)


def contention(runs):
    """Cross-run heads-up derived purely from the run list (no extra I/O):
    which discovered runs are parked on a test-executing step. Those steps run
    integration / component tests against the shared host container stack
    (Podman + SQL + Azurite), so two or more on such a step can conflict, race,
    or starve each other. The status is the coarse next-step value, so a run
    parked at the step counts even if its session is momentarily idle - this is
    a 'positioned to collide' reminder, not a claim that tests run right now.
    Read-only: it only reports; staggering is the human's call in the terminal."""
    at_test = [
        r for r in runs
        if not r.get("runKey") and r.get("status") == "active" and r.get("nextStep") in TEST_STEPS
    ]
    return {
        "count": len(at_test),
        "runs": [
            {"repo": r.get("repo"), "ticket": r.get("ticket"), "step": r.get("nextStep")}
            for r in at_test
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="Dry-run the resolve-issue progress model.")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--ticket", default=None)
    parser.add_argument("--list", action="store_true", help="print runs discovered across all repos")
    args = parser.parse_args()

    if args.list:
        print(json.dumps(list_runs(args.cwd), indent=2, ensure_ascii=True))
        return

    ticket = find_resolve_ticket(args.cwd, args.ticket)
    model = collect_model(args.cwd, ticket)
    print(json.dumps(model, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
