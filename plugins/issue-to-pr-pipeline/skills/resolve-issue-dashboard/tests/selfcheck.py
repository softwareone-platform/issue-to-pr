"""Deterministic self-check for the resolve-issue-dashboard PURE logic.

Grounds the model-building invariants that an LLM would otherwise have to
re-reason probabilistically on every change: the gate/blocked-vs-approaching
status rules, the main-session liveness parse, run-id round-trip, state.md
field parsing, and the test-contention filter. It deliberately does NOT cover
the I/O / UI surface (HTTP server, SSE, browser launch, live tailing, the JS
client) - that layer has no cheap deterministic oracle and is left to the eye.

Pure stdlib, ASCII-only output (Windows cp1252 console). Exits non-zero on any
failure so a Stop hook can surface it. Run from anywhere:
    python selfcheck.py
"""

import io
import json
import os
import sys
import tempfile

# import the module under test from the sibling scripts/ dir without installing
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "scripts")))
import parse_session as ps  # noqa: E402

NL = chr(10)


# every check records (group, name, ok, detail) so a manual run can list the
# greens, not only the reds; the group is the test function currently running
_results = []
_group = ""


def check(name, got, want):
    ok = got == want
    _results.append((_group, name, ok, "" if ok else "got %r, want %r" % (got, want)))


# ----- build_model: the gate/blocked-vs-approaching status rules --------------

def _model(next_step, attention="", main_active=False, main_seen=False):
    state = {
        "next-step": next_step,
        "attention": attention,
        "ticket": "acme-1",
        "plan-approved": "yes",
    }
    m = ps.build_model(state, [], 0, 0, {"cwd": "."}, None, main_active, main_seen=main_seen)
    cur = next((s for s in m["steps"] if s["id"] == next_step), None)
    return {
        "status": m["status"],
        "gate": m["gate"] is not None,
        "blocked": m["blocked"] is not None,
        "awaiting": m["awaitingInput"] is not None,
        "cur": cur["status"] if cur else None,
    }


def test_status_rules():
    # a gate step, genuinely parked -> gate cue shown (amber at the client)
    check("a-gate-approve parked", _model("a-gate-approve", "", False),
          {"status": "paused", "gate": True, "blocked": False, "awaiting": False, "cur": "paused"})
    # a gate step, still approaching (main session busy) -> demoted to running,
    # gate payload suppressed so the client keeps the amber cue off
    check("a-gate-approve approaching", _model("a-gate-approve", "", True),
          {"status": "running", "gate": False, "blocked": False, "awaiting": False, "cur": "running"})
    # attention set, genuinely parked -> blocked cue shown (amber, not red - a
    # human disposition is a wait, not an error)
    check("b-open-pr blocked parked", _model("b-open-pr", "awaiting confirm", False),
          {"status": "blocked", "gate": False, "blocked": True, "awaiting": False, "cur": "blocked"})
    # attention set but still drafting (busy) -> demoted, blocked payload suppressed
    check("b-open-pr blocked approaching", _model("b-open-pr", "awaiting confirm", True),
          {"status": "running", "gate": False, "blocked": False, "awaiting": False, "cur": "running"})
    # a genuine disposition wait at b-code-risk must still show blocked (no regression)
    check("b-code-risk disposition parked", _model("b-code-risk", "unresolved risk", False),
          {"status": "blocked", "gate": False, "blocked": True, "awaiting": False, "cur": "blocked"})
    # a non-gate step with no attention and no tailing is running either way
    check("b-implement non-gate busy", _model("b-implement", "", True),
          {"status": "running", "gate": False, "blocked": False, "awaiting": False, "cur": "running"})
    check("b-implement non-gate untailed", _model("b-implement", "", False),
          {"status": "running", "gate": False, "blocked": False, "awaiting": False, "cur": "running"})


# ----- Collector.main_active: main-session liveness parse ---------------------

def _collector(lines):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "sess.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for o in lines:
            f.write(json.dumps(o) + "\n")
    c = ps.Collector(d, p)
    c.refresh()
    return c


def _main_active(lines):
    return _collector(lines).main_active()


def _asst(stop, block="text"):
    return {"type": "assistant", "timestamp": "2026-07-13T00:00:00Z",
            "message": {"stop_reason": stop, "content": [{"type": block}]}}


def _user():
    return {"type": "user", "timestamp": "2026-07-13T00:00:01Z",
            "message": {"content": [{"type": "tool_result", "tool_use_id": "i"}]}}


def test_main_active():
    # a turn ending in tool_use is still working
    check("last tool_use", _main_active([_asst("tool_use", "tool_use")]), True)
    # a tool_result / user line means the loop is about to run
    check("last user result", _main_active([_asst("tool_use", "tool_use"), _user()]), True)
    # a turn that ended (end_turn) has yielded to the user
    check("last end_turn", _main_active([_asst("tool_use", "tool_use"), _user(), _asst("end_turn")]), False)
    # the thinking+text end_turn pair, then trailing non-message noise, still yielded
    check("end_turn pair + noise",
          _main_active([_asst("end_turn", "thinking"), _asst("end_turn", "text"),
                        {"type": "mode"}, {"type": "permission-mode"}]), False)
    # stop_sequence is also a yield
    check("last stop_sequence", _main_active([_asst("stop_sequence")]), False)
    # nothing read yet defaults to not-active (falls back to cursor-only reading)
    check("noise only", _main_active([{"type": "mode"}]), False)
    # main_seen: True once any main line is read, so a genuine yield (main_active
    # False AFTER a main turn) is told apart from a never-tailed run's default
    check("main_seen after asst", _collector([_asst("end_turn")]).main_seen(), True)
    check("main_seen noise only", _collector([{"type": "mode"}]).main_seen(), False)


# ----- a backgrounded subagent must not read as a yield to the human -----------

def _at(kind, ts, stop="end_turn"):
    if kind == "assistant":
        return {"type": "assistant", "timestamp": ts,
                "message": {"stop_reason": stop, "content": [{"type": "text"}]}}
    return {"type": "user", "timestamp": ts,
            "message": {"content": [{"type": "text", "text": "go"}]}}


def _collector_with_agent(main_lines, agent_lines):
    """Same as _collector but also writes one subagent transcript, which the
    Collector discovers at <project_dir>/<session_id>/subagents/agent-*.jsonl."""
    d = tempfile.mkdtemp()
    p = os.path.join(d, "sess.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for o in main_lines:
            f.write(json.dumps(o) + "\n")
    sub = os.path.join(d, "sess", "subagents")
    os.makedirs(sub)
    with open(os.path.join(sub, "agent-abc12345.jsonl"), "w", encoding="utf-8") as f:
        for o in agent_lines:
            f.write(json.dumps(o) + "\n")
    c = ps.Collector(d, p)
    c.refresh()
    return c


def test_background_agent_is_not_a_yield():
    main_yielded = [_at("assistant", "2026-07-13T00:00:10Z", "end_turn")]
    # the Agent tool backgrounds by default, so the main loop ends its turn while
    # the subagent runs on: newer subagent records mean working, not parked
    check("subagent newer than main",
          _collector_with_agent(main_yielded,
                                [_at("assistant", "2026-07-13T00:05:00Z")]).main_active(),
          True)
    # once the subagent has finished and the main turn is the newest line, the
    # yield is genuine and must still read as waiting for the human
    check("main newer than subagent",
          _collector_with_agent([_at("assistant", "2026-07-13T00:09:00Z", "end_turn")],
                                [_at("assistant", "2026-07-13T00:05:00Z")]).main_active(),
          False)
    # a subagent transcript with no main lines at all keeps the cursor-only reading
    check("subagent but no main",
          _collector_with_agent([], [_at("assistant", "2026-07-13T00:05:00Z")]).main_active(),
          False)
    # a main turn still mid-work wins regardless of subagent timestamps
    check("main mid-work wins",
          _collector_with_agent([_asst("tool_use", "tool_use")],
                                [_at("assistant", "2020-01-01T00:00:00Z")]).main_active(),
          True)


# ----- run_id / decode_run_id round-trip --------------------------------------

def test_run_id_roundtrip():
    cwd = os.path.abspath(".")
    # live run (no run_key)
    check("run_id live", ps.decode_run_id(ps.run_id(cwd, "acme-1")), (cwd, "acme-1", ""))
    # archived run carries its stamp as the run_key
    check("run_id archived", ps.decode_run_id(ps.run_id(cwd, "acme-1", "2026-07-13T00-00-00Z")),
          (cwd, "acme-1", "2026-07-13T00-00-00Z"))
    # a ticketless (ad-hoc) run decodes ticket as None
    check("run_id no ticket", ps.decode_run_id(ps.run_id(cwd, None)), (cwd, None, ""))


# ----- parse_state: field parsing incl. the empty-field boundary --------------

def test_parse_state():
    d = tempfile.mkdtemp()
    p = os.path.join(d, "state.md")
    # an empty `attention:` must read as empty and must NOT swallow the next line
    # (`started:`) - the regression the horizontal-whitespace pattern guards
    with open(p, "w", encoding="utf-8") as f:
        f.write("- **next-step:** b-open-pr\n")
        f.write("- **ticket:** acme-1\n")
        f.write("- **attention:**\n")
        f.write("- **started:** 2026-07-13T00:00:00Z\n")
    st = ps.parse_state(p)
    check("parse next-step", st.get("next-step"), "b-open-pr")
    check("parse empty attention", st.get("attention"), "")
    check("parse started not swallowed", st.get("started"), "2026-07-13T00:00:00Z")
    check("empty attention not blocked", ps._is_blocked(st.get("attention")), False)


# ----- encoding: a bad file must cost only its own run, never the payload -----

def test_encoding_tolerance():
    d = tempfile.mkdtemp()

    # a UTF-8 BOM does NOT raise, so it used to leave ﻿ on the first
    # character - and `next-step` is state.md's first field, so the whole cursor
    # went missing and the run rendered as idle with no error to explain it
    bom = os.path.join(d, "bom-state.md")
    with open(bom, "wb") as f:
        f.write(b"\xef\xbb\xbfnext-step: b-open-pr\nticket: acme-1\n")
    check("BOM state.md still yields next-step",
          ps.parse_state(bom).get("next-step"), "b-open-pr")

    bomt = os.path.join(d, "bom-timings.md")
    with open(bomt, "wb") as f:
        f.write(b"\xef\xbb\xbf- 2026-07-13T00:00:00Z a-fact-check\n"
                b"- 2026-07-13T00:10:00Z a-draft-plan\n")
    check("BOM timings.md keeps its first entry",
          [e["step"] for e in ps.parse_timings(bomt)],
          ["a-fact-check", "a-draft-plan"])

    # an undecodable file must degrade to "no data" rather than raise: parse_state
    # is reached from list_runs inside the poll loop, so one unreadable file used
    # to replace the entire payload - every repo's run list - with an error
    utf16 = os.path.join(d, "utf16-state.md")
    with open(utf16, "wb") as f:
        f.write("next-step: b-open-pr\n".encode("utf-16"))
    check("undecodable state.md returns empty, no raise", ps.parse_state(utf16), {})

    utf16t = os.path.join(d, "utf16-timings.md")
    with open(utf16t, "wb") as f:
        f.write("- 2026-07-13T00:00:00Z a-fact-check\n".encode("utf-16"))
    check("undecodable timings.md returns empty, no raise", ps.parse_timings(utf16t), [])

    # the blast radius that made this worth fixing: runs_for_cwd must still answer
    run_dir = os.path.join(d, ".claude", "resolve", "acme-9")
    os.makedirs(run_dir)
    with open(os.path.join(run_dir, "state.md"), "wb") as f:
        f.write("next-step: b-open-pr\n".encode("utf-16"))
    check("a bad state.md does not stop the run list",
          isinstance(ps.runs_for_cwd(d), list), True)


# ----- contention: the coarse-status test-step filter (R1's oracle) -----------

def test_contention():
    # registry drift guard: contention keys on this being a test-executing step
    check("b-code-risk is a test step", "b-code-risk" in ps.TEST_STEPS, True)
    base = {"repo": "r", "ticket": "acme-1", "runKey": "", "nextStep": "b-code-risk"}
    # a blocked run at a test step is NOT counted (contention wants coarse "active")
    check("blocked excluded", ps.contention([dict(base, status="blocked")])["count"], 0)
    # two active runs at a test step ARE counted
    two = [dict(base, status="active"), dict(base, ticket="acme-2", status="active")]
    check("two active counted", ps.contention(two)["count"], 2)


# ----- parse_timings / compute_step_durations: per-step wall-clock ------------

def _ts(sec):
    """A UTC-with-Z timestamp `sec` seconds past a fixed midnight, built without
    reading the clock so the duration folds are deterministic."""
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    return "2026-07-13T%02d:%02d:%02dZ" % (h, m, s)


def _entries(pairs):
    return [{"ts": _ts(sec), "step": step} for sec, step in pairs]


def test_timings():
    # parse_timings: markdown decoration tolerated, a prose line and an
    # unknown-id line dropped, a bare (undecorated) line accepted, order kept
    d = tempfile.mkdtemp()
    p = os.path.join(d, "timings.md")
    with open(p, "w", encoding="utf-8") as f:
        f.write("- 2026-07-13T00:00:00Z a-fact-check\n")
        f.write("some prose that is not an entry\n")
        f.write("- 2026-07-13T00:05:00Z not-a-real-step\n")
        f.write("2026-07-13T00:06:00Z a-draft-plan\n")
    parsed = ps.parse_timings(p)
    check("parse_timings count", len(parsed), 2)
    check("parse_timings first", parsed[0], {"ts": "2026-07-13T00:00:00Z", "step": "a-fact-check"})
    check("parse_timings skips unknown id", parsed[1]["step"], "a-draft-plan")
    check("parse_timings missing file", ps.parse_timings(os.path.join(d, "none.md")), [])

    # a-fact-check spans 10s, a-draft-plan spans 15s, done is terminal (no span)
    dur = ps.compute_step_durations(_entries([(0, "a-fact-check"), (10, "a-draft-plan"), (25, "done")]))
    check("closed step dur", dur["a-fact-check"], {"durationMs": 10000, "occurrences": 1, "open": False})
    check("second step dur", dur["a-draft-plan"], {"durationMs": 15000, "occurrences": 1, "open": False})
    check("done terminal not open", dur["done"], {"durationMs": None, "occurrences": 1, "open": False})

    # the last non-done entry is still open (running); the earlier step is closed
    dur = ps.compute_step_durations(_entries([(0, "a-fact-check"), (10, "b-implement")]))
    check("open last step", dur["b-implement"], {"durationMs": None, "occurrences": 1, "open": True})
    check("closed before open", dur["a-fact-check"]["durationMs"], 10000)

    # a gate re-entry: a-harden-plan runs twice, its spans SUM and the count is 2 -
    # the re-run cost flat state.md fields could not represent (the log's reason)
    dur = ps.compute_step_durations(_entries([
        (0, "a-harden-plan"), (5, "a-gate-approve"), (8, "a-harden-plan"),
        (12, "a-gate-approve"), (20, "b-implement")]))
    check("re-entry sums duration", dur["a-harden-plan"], {"durationMs": 9000, "occurrences": 2, "open": False})
    check("re-entry sums gate", dur["a-gate-approve"], {"durationMs": 11000, "occurrences": 2, "open": False})

    # a clock that went backwards across a resume yields a non-positive span ->
    # dropped, so no negative time is charted, but the occurrence still counts
    dur = ps.compute_step_durations(_entries([(10, "a-fact-check"), (5, "a-draft-plan")]))
    check("clock reversal dropped", dur["a-fact-check"]["durationMs"], None)
    check("clock reversal count kept", dur["a-fact-check"]["occurrences"], 1)

    # empty log is safe
    check("empty entries", ps.compute_step_durations([]), {})


# ----- waiting-for-you on a non-gate step (the yield signal) ------------------

def test_waiting_detection():
    # a-elicit-decisions is neither a gate nor attention-flagged; once the session
    # has yielded (main_seen True, main_active False) it must read as waiting - amber
    check("elicit yielded is waiting",
          _model("a-elicit-decisions", "", False, True),
          {"status": "paused", "gate": False, "blocked": False, "awaiting": True, "cur": "paused"})
    # the same step still working (main_active True) is running, not waiting
    check("elicit working is running",
          _model("a-elicit-decisions", "", True, True),
          {"status": "running", "gate": False, "blocked": False, "awaiting": False, "cur": "running"})
    # never tailed (main_seen False): the default-False main_active must NOT read as
    # a false wait - stays running (cursor-only reading)
    check("elicit untailed is running",
          _model("a-elicit-decisions", "", False, False),
          {"status": "running", "gate": False, "blocked": False, "awaiting": False, "cur": "running"})
    # a done run that happens to be yielded is not a wait
    check("done not waiting",
          _model("done", "", False, True),
          {"status": "done", "gate": False, "blocked": False, "awaiting": False, "cur": "completed"})
    # a gate step keeps its own gate cue when yielded (not the generic awaitingInput)
    check("gate yielded stays gate",
          _model("a-gate-approve", "", False, True),
          {"status": "paused", "gate": True, "blocked": False, "awaiting": False, "cur": "paused"})
    # attention (disposition) keeps its blocked cue when yielded
    check("attention yielded stays blocked",
          _model("b-code-risk", "unresolved risk", False, True),
          {"status": "blocked", "gate": False, "blocked": True, "awaiting": False, "cur": "blocked"})


# ----- compute_step_activity: per-step output-token bucketing -----------------

def _toks(pairs):
    return [{"ts": _ts(sec), "output_tokens": n} for sec, n in pairs]


def test_step_activity():
    entries = _entries([(0, "a-fact-check"), (10, "a-draft-plan"), (25, "done")])
    toks = _toks([(3, 100), (12, 50), (20, 70)])
    act = ps.compute_step_activity(entries, toks)
    # record at 3s -> [0,10) fact-check; 12s & 20s -> [10,25) draft (summed)
    check("bucket fact-check", act.get("a-fact-check"), 100)
    check("bucket draft sums", act.get("a-draft-plan"), 120)
    check("done window empty", act.get("done"), None)
    # summing is order-independent: reversed input yields the same result
    check("order-independent", ps.compute_step_activity(entries, list(reversed(toks))), act)
    # a record before the first entry (preamble) is skipped, not misattributed
    check("pre-first-window skipped",
          ps.compute_step_activity(_entries([(10, "a-fact-check"), (20, "a-draft-plan")]), _toks([(5, 999)])), {})
    # zero / non-positive output_tokens are dropped
    check("zero tokens skipped", ps.compute_step_activity(entries, _toks([(3, 0)])), {})
    # a re-entered step (two windows) sums its tokens across occurrences
    reentry = _entries([(0, "a-harden-plan"), (10, "a-gate-approve"), (20, "a-harden-plan"), (30, "done")])
    check("re-entry sums tokens",
          ps.compute_step_activity(reentry, _toks([(5, 40), (25, 60)])).get("a-harden-plan"), 100)
    check("no entries -> empty", ps.compute_step_activity([], _toks([(3, 100)])), {})
    # build_model attaches activity.tokensOut per step
    m = ps.build_model({"next-step": "a-draft-plan", "ticket": "acme-1"}, [], 0, 0, {"cwd": "."},
                       None, False, entries, False, toks)
    fc = next(s for s in m["steps"] if s["id"] == "a-fact-check")
    check("build_model activity attached", fc["activity"]["tokensOut"], 100)


# ----- token accounting: one API response counted once ------------------------

def _usage(mid, inp=0, out=0, cread=0, ccreate=0, ts="2026-07-13T00:00:00Z", block="text"):
    """An assistant record carrying usage. Claude Code writes one record PER
    CONTENT BLOCK and repeats the same message.usage on every one, so several of
    these sharing a message id is the normal shape, not a malformed transcript."""
    msg = {"stop_reason": "tool_use", "content": [{"type": block}],
           "usage": {"input_tokens": inp, "output_tokens": out,
                     "cache_read_input_tokens": cread,
                     "cache_creation_input_tokens": ccreate}}
    if mid is not None:
        msg["id"] = mid
    return {"type": "assistant", "timestamp": ts, "message": msg}


def test_token_totals():
    # the defect this pins: three records of ONE response, each repeating its
    # usage, so a per-record sum counts it three times. remove the dedupe and
    # every check in this block goes red
    c = _collector([_usage("msg_a", inp=100, out=40, cread=900, ccreate=10)] * 3)
    check("repeated usage counted once (in)", c.tokens_in, 100)
    check("repeated usage counted once (out)", c.tokens_out, 40)
    check("repeated usage counted once (cached)", c.tokens_cached, 910)
    # the per-step samples ride the same gate, or a step window re-inflates
    check("per-step sample deduped", len(c.token_records()), 1)

    # distinct responses still sum
    c2 = _collector([_usage("msg_a", inp=10, out=1, cread=5),
                     _usage("msg_b", inp=20, out=2, cread=7),
                     _usage("msg_b", inp=20, out=2, cread=7)])
    check("distinct ids sum", (c2.tokens_in, c2.tokens_out, c2.tokens_cached), (30, 3, 12))

    # a record with no message id cannot be deduplicated, so it is counted -
    # over-counting an unidentifiable record beats dropping a real one
    c3 = _collector([_usage(None, inp=5, out=5), _usage(None, inp=5, out=5)])
    check("id-less records both counted", (c3.tokens_in, c3.tokens_out), (10, 10))

    # ids are NOT unique across files, so the key is the pair: the same id in a
    # subagent transcript is a different response and must still be counted
    c4 = _collector_with_agent([_usage("msg_dup", inp=100, out=10)],
                               [_usage("msg_dup", inp=100, out=10)])
    check("same id in another file still counts", (c4.tokens_in, c4.tokens_out), (200, 20))

    # cache_creation and cache_read both land in cached; absent fields are 0
    c5 = _collector([{"type": "assistant", "timestamp": "2026-07-13T00:00:00Z",
                      "message": {"id": "m", "stop_reason": "end_turn",
                                  "content": [{"type": "text"}],
                                  "usage": {"input_tokens": 7}}}])
    check("missing cache fields default 0", (c5.tokens_in, c5.tokens_cached), (7, 0))

    # tool_use pairing must survive the gate: the blocks are written once each, so
    # a duplicate-usage record still contributes its own tool event
    dup_tool = [_usage("msg_t", out=5, block="text"),
                _usage("msg_t", out=5, block="text")]
    dup_tool[1]["message"]["content"] = [{"type": "tool_use", "id": "t1", "name": "Bash",
                                          "input": {"command": "ls"}}]
    c6 = _collector(dup_tool)
    check("duplicate-usage record still yields its tool event", len(c6.events()), 1)
    check("tool event's usage not double counted", c6.tokens_out, 5)

    # build_model surfaces cached alongside input/output
    m = ps.build_model({"next-step": "a-draft-plan", "ticket": "acme-1"}, [], 11, 22,
                       {"cwd": "."}, None, False, None, False, None, 33)
    check("model exposes cached", m["metrics"]["tokens"],
          {"input": 11, "cached": 33, "output": 22})


# ----- find_live_session: ticket-aware session selection (R3) -----------------

def test_session_selection():
    d = tempfile.mkdtemp()
    older = os.path.join(d, "older.jsonl")   # references the ticket
    newer = os.path.join(d, "newer.jsonl")   # unrelated, but newer mtime
    with open(older, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "cwd": "x",
                            "message": {"content": "/resolve-issue acme-42 please"}}) + "\n")
    with open(newer, "w", encoding="utf-8") as f:
        f.write(json.dumps({"type": "user", "cwd": "x",
                            "message": {"content": "unrelated work here"}}) + "\n")
    os.utime(older, (1000, 1000))
    os.utime(newer, (2000, 2000))  # newer mtime
    # no ticket -> newest overall (unchanged legacy behaviour)
    check("no ticket picks newest", os.path.basename(ps.find_live_session(d)), "newer.jsonl")
    # ticket-aware -> the session that references it, despite its older mtime
    check("ticket-aware picks matching", os.path.basename(ps.find_live_session(d, "acme-42")), "older.jsonl")
    # ticket present in no session -> fall back to newest (no regression)
    check("ticket-aware falls back", os.path.basename(ps.find_live_session(d, "acme-99")), "newer.jsonl")
    check("_session_mentions hit", ps._session_mentions(older, "acme-42"), True)
    check("_session_mentions miss", ps._session_mentions(newer, "acme-42"), False)
    check("_session_mentions no ticket", ps._session_mentions(older, None), False)


# ----- run panel: cursor-vs-attention precedence, bucketing, ordering ---------

def _summary(next_step, attention=""):
    """Write a minimal state.md and read it back through _run_summary,
    so the cursor-vs-attention precedence is exercised through the real parse path
    rather than against a hand-built dict."""
    d = tempfile.mkdtemp()
    p = os.path.join(d, "state.md")
    with io.open(p, "w", encoding="utf-8") as f:
        f.write(NL.join([u"- next-step: " + next_step,
                         u"- ticket: acme-1",
                         u"- attention: " + attention, u""]))
    return ps._run_summary(d, "acme-1", "", "", p, d)


def test_run_summary_precedence():
    # a finished run stays finished.
    # resolve-issue leaves a handoff note in `attention` after the PR is open,
    # and reading that as a run state pinned a done run to the top of the panel forever - nothing ever clears it
    check("done outranks attention",
          _summary("done", "PR open; six tickets left for the developer")["status"], "done")
    # an unfinished step with a note is still the human's to dispose of
    check("attention on an open step", _summary("b-open-pr", "confirm the PR")["status"], "blocked")
    check("no attention", _summary("b-implement")["status"], "active")
    check("gate step", _summary("a-gate-approve")["status"], "paused")
    check("unknown cursor still classified", _summary("A1-fact-check")["status"], "idle")


def _r(rid, status, ms, next_step="b-implement", cwd="/repo-a", repo="repo-a"):
    return {"id": rid, "repo": repo, "cwd": cwd, "ticket": rid, "runKey": "",
            "runStamp": "", "nextStep": next_step, "status": status,
            "lastActivityMs": ms}


def _ids(bucket):
    return [r["id"] for r in bucket]


def test_run_panel():
    # a cursor the registry does not have is a data defect rather than a run state,
    # so it is dropped from the panel entirely rather than shown as a peer run
    dirty = _r("legacy", "idle", 900, next_step="A1-fact-check")
    panel = ps.plan_run_panel([dirty, _r("live", "active", 500)])
    check("dirty run dropped", _ids(panel[0]["open"]) + _ids(panel[0]["done"]), ["live"])
    check("dirty run does not create a group", len(panel), 1)

    # a run with no cursor at all is NOT a defect -
    # it is the launch-cwd placeholder, or a resolve dir created before state.md is written
    nostep = ps.plan_run_panel([_r("fresh", "idle", 100, next_step=None)])
    check("no cursor is kept", _ids(nostep[0]["open"]), ["fresh"])

    # bucketing: done collapses, everything else stays open
    mixed = ps.plan_run_panel([
        _r("d1", "done", 900), _r("open1", "paused", 100), _r("d2", "done", 800),
    ])
    check("open bucket", _ids(mixed[0]["open"]), ["open1"])
    check("done bucket newest first", _ids(mixed[0]["done"]), ["d1", "d2"])

    # open ordering is by status band first, and by recency only inside a band.
    # the panel cannot know which run is live, because it never tails,
    # so this orders by how much the run still needs rather than by a liveness claim it cannot make
    bands = ps.plan_run_panel([
        _r("i", "idle", 900, next_step=None), _r("p", "paused", 800),
        _r("b", "blocked", 700), _r("a", "active", 600),
    ])
    check("open ordered by band", _ids(bands[0]["open"]), ["a", "b", "p", "i"])

    within = ps.plan_run_panel([_r("older", "active", 100), _r("newer", "active", 900)])
    check("recency inside a band", _ids(within[0]["open"]), ["newer", "older"])

    # groups: most-recently-active repo first,
    # keyed on cwd so two repos sharing a basename stay distinct
    two = ps.plan_run_panel([
        _r("a1", "done", 100, cwd="/repo-a", repo="repo-a"),
        _r("b1", "done", 900, cwd="/repo-b", repo="repo-b"),
    ])
    check("groups by recency", [g["cwd"] for g in two], ["/repo-b", "/repo-a"])

    dup = ps.plan_run_panel([
        _r("x", "done", 100, cwd="/one/name", repo="name"),
        _r("y", "done", 900, cwd="/two/name", repo="name"),
    ])
    check("same basename stays distinct", len(dup), 2)

    # the selected run must stay visible,
    # so a selection inside the collapsed bucket flags its group for the client to open
    sel = ps.plan_run_panel([_r("d1", "done", 900), _r("o1", "active", 100)], "d1")
    check("selection in done flags the group", sel[0]["selectedInDone"], True)
    check("selection in open does not", 
          ps.plan_run_panel([_r("d1", "done", 900), _r("o1", "active", 100)], "o1")[0]["selectedInDone"],
          False)
    check("no selection does not",
          ps.plan_run_panel([_r("d1", "done", 900)])[0]["selectedInDone"], False)

    check("empty list", ps.plan_run_panel([]), [])


_TESTS = (test_status_rules, test_main_active, test_background_agent_is_not_a_yield,
          test_run_id_roundtrip, test_parse_state, test_encoding_tolerance,
          test_contention, test_timings, test_waiting_detection, test_step_activity,
          test_token_totals, test_session_selection, test_run_summary_precedence,
          test_run_panel)


def _run_all():
    global _group
    for t in _TESTS:
        _group = t.__name__
        try:
            t()
        except Exception as exc:  # a check that raises is itself a failure
            _results.append((_group, "(crashed)", False,
                             "raised %s: %s" % (type(exc).__name__, exc)))
    return _results


def _fails():
    return [(g, name, detail) for g, name, ok, detail in _results if not ok]


def main():
    """Manual run: print a per-check PASS/FAIL breakdown grouped by test, so you
    can see exactly what is green, then a summary. Exits non-zero if any fail."""
    _run_all()
    order, groups = [], {}
    for g, name, ok, detail in _results:
        if g not in groups:
            groups[g] = []
            order.append(g)
        groups[g].append((name, ok, detail))
    for g in order:
        print(g)
        for name, ok, detail in groups[g]:
            line = "  [%s] %s" % ("PASS" if ok else "FAIL", name)
            if not ok:
                line += " -- " + detail
            print(line)
    npass = sum(1 for r in _results if r[2])
    nfail = len(_results) - npass
    print("")
    print("%d passed, %d failed" % (npass, nfail))
    return 0 if nfail == 0 else 1


def hook_main():
    """Stop-hook adapter: run the checks and, only on failure, emit a
    non-blocking systemMessage the harness surfaces to the user. It NEVER blocks
    the stop and NEVER exits non-zero - a broken or half-edited selfcheck must
    not lock anyone out of finishing a turn (the "warn, never block" contract
    lives here, in tested code, rather than in fragile shell escaping). Silent on
    success."""
    try:
        _run_all()
        fails = _fails()
        if fails:
            body = "resolve-issue-dashboard selfcheck FAILED (%d):\n" % len(fails)
            body += "\n".join("  - %s / %s: %s" % (g, name, detail)
                              for g, name, detail in fails)
            print(json.dumps({"systemMessage": body}))
    except Exception as exc:  # never let a selfcheck crash block the stop
        print(json.dumps({"systemMessage":
                          "resolve-issue-dashboard selfcheck could not run: %s" % exc}))
    return 0


if __name__ == "__main__":
    if "--hook" in sys.argv[1:]:
        sys.exit(hook_main())
    sys.exit(main())
