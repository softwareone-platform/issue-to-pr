"""Deterministic self-check for the resolve-issue-dashboard PURE logic.

Grounds the model-building invariants that an LLM would otherwise have to
re-reason probabilistically on every change: the gate/blocked-vs-approaching
status rules, the main-session liveness parse, run-id round-trip, state.md
field parsing, and the test-contention filter. It deliberately does NOT cover
the I/O / UI surface (HTTP server, SSE, browser launch, live tailing, the JS
client) - that layer has no cheap deterministic oracle and is left to the eye.

Pure stdlib, ASCII-only output (Windows cp1252 console). Exits non-zero on any
failure so a Stop hook can surface it. Run from anywhere:
    python tests/parse_session_tests.py
"""

import calendar
import contextlib
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
    # the legacy decorated form, kept so older state.md files still parse.
    # it cannot guard the swallow regression: the `**` after the colon sits between it and the newline,
    # so a line-crossing gap has nothing to cross and this arm stays green under that mutation
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

    # the plain form resolve-issue writes today, with `attention:` empty while the run is not waiting.
    # this arm carries the guard: an empty `attention:` must read as empty and must NOT swallow `started:`,
    # which a whitespace gap allowed to cross the newline would do, rendering the run as blocked
    plain = os.path.join(d, "plain-state.md")
    with open(plain, "w", encoding="utf-8") as f:
        f.write("next-step: b-open-pr\n")
        f.write("ticket: acme-1\n")
        f.write("attention:\n")
        f.write("started: 2026-07-13T00:00:00Z\n")
    pst = ps.parse_state(plain)
    check("plain parse next-step", pst.get("next-step"), "b-open-pr")
    check("plain parse empty attention", pst.get("attention"), "")
    check("plain parse started not swallowed", pst.get("started"), "2026-07-13T00:00:00Z")
    check("plain empty attention not blocked", ps._is_blocked(pst.get("attention")), False)


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
                            "message": {"content": "reading .claude/resolve/acme-42/state.md"}}) + "\n")
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


# ----- _session_mentions: the handoff-dir reference, scanned whole ------------

@contextlib.contextmanager
def _faked(**attrs):
    """Temporarily replace attributes on parse_session, restored in a finally
    so a check that raises inside the block cannot leak the stand-in into later tests."""
    old = dict((k, getattr(ps, k)) for k in attrs)
    for k, v in attrs.items():
        setattr(ps, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(ps, k, v)


def _jsonl(path, records, mode="w"):
    with open(path, mode, encoding="utf-8") as f:
        for o in records:
            f.write(json.dumps(o) + "\n")
    return path


def _said(text):
    return {"type": "user", "message": {"content": text}}


def _filler(n):
    return [_said("filler line %d with no path in it" % i) for i in range(n)]


def test_session_mentions():
    d = tempfile.mkdtemp()

    # the driving session is often resumed deep into a long transcript,
    # so a reference after the first 40 lines must still count.
    # restore the 40-line head scan and this goes red
    deep = _jsonl(os.path.join(d, "deep.jsonl"),
                  _filler(100) + [_said("reading .claude/resolve/acme-42/state.md")])
    check("reference after 100 lines found", ps._session_mentions(deep, "acme-42"), True)
    shallow = _jsonl(os.path.join(d, "shallow.jsonl"), _filler(100))
    check("100 filler lines alone do not match", ps._session_mentions(shallow, "acme-42"), False)

    # a session that only talked about the ticket did not drive the run,
    # so a bare mention with no resolve/ path is not a match
    bare = _jsonl(os.path.join(d, "bare.jsonl"), [_said("/resolve-issue acme-42 please")])
    check("bare ticket mention is not a match", ps._session_mentions(bare, "acme-42"), False)
    handoff = _jsonl(os.path.join(d, "handoff.jsonl"), [_said("wrote .claude/resolve/acme-42/state.md")])
    check("handoff path is a match", ps._session_mentions(handoff, "acme-42"), True)

    # a Windows path reaches the transcript JSON-escaped, so each separator is two backslash bytes on disk
    win = _jsonl(os.path.join(d, "win.jsonl"),
                 [_said(r"C:\repo\.claude\resolve\acme-42\state.md")])
    with open(win, "rb") as f:
        raw = f.read()
    check("escaped separators are doubled on disk", b"resolve\\\\acme-42\\\\state.md" in raw, True)
    check("escaped Windows path matches", ps._session_mentions(win, "acme-42"), True)

    # a ticket that prefixes another must not match it.
    # drop the trailing alphanumeric guard and acme-4 claims acme-42's session
    longer = _jsonl(os.path.join(d, "longer.jsonl"), [_said("reading .claude/resolve/acme-42/state.md")])
    check("acme-4 does not match resolve/acme-42", ps._session_mentions(longer, "acme-4"), False)
    check("same file matches acme-42", ps._session_mentions(longer, "acme-42"), True)
    exact = _jsonl(os.path.join(d, "exact.jsonl"), [_said("reading .claude/resolve/acme-4/state.md")])
    check("acme-4 matches resolve/acme-4", ps._session_mentions(exact, "acme-4"), True)


def test_session_mentions_incremental():
    d = tempfile.mkdtemp()

    # a negative result is remembered only for the bytes already read,
    # so a reference appended later is found on the next call
    grow = _jsonl(os.path.join(d, "grow.jsonl"), [_said("unrelated work")])
    check("before the append", ps._session_mentions(grow, "acme-42"), False)
    _jsonl(grow, [_said("reading .claude/resolve/acme-42/state.md")], mode="a")
    check("appended reference found", ps._session_mentions(grow, "acme-42"), True)

    # a file that shrank was rewritten, so the cached hit no longer describes it.
    # drop the size-below-offset reset and the stale True survives
    shrink = _jsonl(os.path.join(d, "shrink.jsonl"),
                    [_said("reading .claude/resolve/acme-42/state.md and a long tail of words")])
    check("before the rewrite", ps._session_mentions(shrink, "acme-42"), True)
    before = os.path.getsize(shrink)
    _jsonl(shrink, [_said("x")])
    check("rewrite really is smaller", os.path.getsize(shrink) < before, True)
    check("rewritten file without the reference", ps._session_mentions(shrink, "acme-42"), False)


def test_session_mentions_chunk_boundary():
    d = tempfile.mkdtemp()
    path = _jsonl(os.path.join(d, "split.jsonl"),
                  _filler(3) + [_said("reading .claude/resolve/acme-42/state.md")])
    with open(path, "rb") as f:
        raw = f.read()
    ref = b"resolve/acme-42"
    at = raw.index(ref)
    # the boundary lands four bytes into the reference, so neither chunk holds it whole
    chunk = at + 4
    check("boundary really splits the reference", at < chunk < at + len(ref), True)
    # the carried tail is what joins the two halves - drop it and this goes red
    with _faked(_MENTION_CHUNK=chunk):
        check("reference split across chunks found", ps._session_mentions(path, "acme-42"), True)
    check("chunk size restored", ps._MENTION_CHUNK, 8 * 1024 * 1024)


# ----- find_live_session: a session last written before the run is no candidate -----

def test_session_selection_since():
    d = tempfile.mkdtemp()
    stale = _jsonl(os.path.join(d, "stale.jsonl"), [_said("reading .claude/resolve/acme-42/state.md")])
    fresh = _jsonl(os.path.join(d, "fresh.jsonl"), [_said("unrelated work here")])
    os.utime(stale, (1000, 1000))
    os.utime(fresh, (2000, 2000))
    # mtimes are 1,000,000 and 2,000,000 ms, so the stamp sits well clear of both
    since = 1500 * 1000
    # a session that ended before the run began cannot have driven it,
    # even though it references the ticket and the fresh one does not
    check("stale reference excluded, fresh returned",
          os.path.basename(ps.find_live_session(d, "acme-42", since)), "fresh.jsonl")
    check("no since keeps the stale reference",
          os.path.basename(ps.find_live_session(d, "acme-42")), "stale.jsonl")

    # with every session stale there is nothing honest to tail
    old = tempfile.mkdtemp()
    a = _jsonl(os.path.join(old, "a.jsonl"), [_said("reading .claude/resolve/acme-42/state.md")])
    b = _jsonl(os.path.join(old, "b.jsonl"), [_said("unrelated work here")])
    os.utime(a, (1000, 1000))
    os.utime(b, (1100, 1100))
    check("all stale returns None", ps.find_live_session(old, "acme-42", since), None)
    check("all stale without since still returns a path",
          os.path.basename(ps.find_live_session(old, "acme-42")), "a.jsonl")


# ----- Collector(since_ms): records before the run's start are not this run's -----

def _epoch_ms(h, m, s=0):
    # independent of the module's own ISO parse, so a wrong _iso_to_ms cannot cancel itself out
    return calendar.timegm((2026, 7, 13, h, m, s, 0, 0, 0)) * 1000


def _windowed(main_lines, since_ms, agent_lines=None, agent_mtime=None, until_ms=None):
    d = tempfile.mkdtemp()
    p = _jsonl(os.path.join(d, "sess.jsonl"), main_lines)
    if agent_lines is not None:
        sub = os.path.join(d, "sess", "subagents")
        os.makedirs(sub)
        ap = _jsonl(os.path.join(sub, "agent-abc12345.jsonl"), agent_lines)
        if agent_mtime is not None:
            os.utime(ap, (agent_mtime, agent_mtime))
    c = ps.Collector(d, p, since_ms=since_ms, until_ms=until_ms)
    c.refresh()
    return c


def _shape(c):
    return {"events": len(c.events()), "tokens_in": c.tokens_in, "tokens_out": c.tokens_out,
            "main_seen": c.main_seen(), "main_active": c.main_active()}


def test_collector_since():
    since = _epoch_ms(0, 10)
    old = [_usage("m_old", inp=100, out=40, ts="2026-07-13T00:05:00Z", block="tool_use")]
    # a record before the stamp belongs to earlier work in the same session,
    # so it must move none of the counters or the liveness signals
    check("record before since dropped", _shape(_windowed(old, since)),
          {"events": 0, "tokens_in": 0, "tokens_out": 0, "main_seen": False, "main_active": False})
    check("no since counts the same record", _shape(_windowed(old, None)),
          {"events": 1, "tokens_in": 100, "tokens_out": 40, "main_seen": True, "main_active": True})

    mixed = old + [_usage("m_new", inp=7, out=3, ts="2026-07-13T00:20:00Z", block="tool_use")]
    c = _windowed(mixed, since)
    check("mixed keeps only the new record", (len(c.events()), c.tokens_in, c.tokens_out), (1, 7, 3))
    check("mixed keeps the new record's event", c.events()[0]["ts"], "2026-07-13T00:20:00Z")

    # a record that cannot be placed outside the window is kept, as the source comment states
    unstamped = _usage("m_none", inp=9, out=2, block="tool_use")
    del unstamped["timestamp"]
    garbled = _usage("m_bad", inp=5, out=1, ts="not-a-time", block="tool_use")
    c = _windowed([unstamped, garbled], since)
    check("unparseable stamps kept", (len(c.events()), c.tokens_in, c.tokens_out), (2, 14, 3))


def test_collector_since_skips_stale_subagent():
    since = _epoch_ms(0, 10)
    main = [_usage("m_main", inp=100, out=10, ts="2026-07-13T00:20:00Z")]
    # the subagent's records are all inside the window, so only its mtime can exclude it.
    # restore reading every subagent file and its usage and event come back
    agent = [_usage("m_sub", inp=7, out=3, ts="2026-07-13T00:30:00Z", block="tool_use")]
    stale = _windowed(main, since, agent, agent_mtime=since // 1000 - 60)
    check("stale-mtime subagent not counted",
          (len(stale.events()), stale.tokens_in, stale.tokens_out), (0, 100, 10))
    fresh = _windowed(main, since, agent, agent_mtime=since // 1000 + 60)
    check("fresh-mtime subagent counted",
          (len(fresh.events()), fresh.tokens_in, fresh.tokens_out), (1, 107, 13))


# ----- collect_model: state.md's started picks the session and windows it ------

def _run_repo(started, sessions, ended=None, plain=False):
    """A cwd holding .claude/resolve/acme-42/state.md, and a projects dir holding
    `sessions` as (name, records, mtime_seconds) - returned as (cwd, project_dir).
    `plain` writes the canonical block resolve-issue emits -
    bare `field: value` lines, every field present, an empty one keeping its colon -
    instead of the legacy `- **field:** value` form."""
    cwd = tempfile.mkdtemp()
    run = os.path.join(cwd, ".claude", "resolve", "acme-42")
    os.makedirs(run)
    if plain:
        lines = ["# resolve-issue state", "", "next-step: b-implement", "ticket: acme-42",
                 "base-branch: main", "work-branch:", "plan-approved: yes", "pr-url:",
                 "attention:", "started:" + (" " + started if started else ""),
                 "ended:" + (" " + ended if ended else "")]
    else:
        lines = ["- **next-step:** b-implement", "- **ticket:** acme-42"]
        if started:
            lines.append("- **started:** " + started)
        if ended:
            lines.append("- **ended:** " + ended)
    with open(os.path.join(run, "state.md"), "w", encoding="utf-8") as f:
        f.write(NL.join(lines) + NL)
    proj = tempfile.mkdtemp()
    for name, records, mtime in sessions:
        p = _jsonl(os.path.join(proj, name + ".jsonl"), records)
        os.utime(p, (mtime, mtime))
    return cwd, proj


def _tool(ts, tid):
    return {"type": "assistant", "timestamp": ts,
            "message": {"stop_reason": "tool_use",
                        "content": [{"type": "tool_use", "id": tid, "name": "Bash",
                                     "input": {"command": "ls"}}]}}


def test_collect_model_since():
    since_s = _epoch_ms(0, 10) // 1000
    handoff = _said("reading .claude/resolve/acme-42/state.md")
    cwd, proj = _run_repo("2026-07-13T00:10:00Z", [
        ("fresh", [handoff, _tool("2026-07-13T00:05:00Z", "t_before"),
                   _tool("2026-07-13T00:20:00Z", "t_after")], since_s + 3600),
        ("stale", [handoff, _tool("2026-07-13T00:01:00Z", "t_stale")], since_s - 3600),
    ])
    with _faked(find_project_dir=lambda c: proj):
        m = ps.collect_model(cwd, "acme-42")
    # started windows the Collector, so the tool call before it is not this run's
    check("only the call after started counted", m["metrics"]["toolCalls"], 1)
    check("fresh session selected", m["session"]["id"], "fresh")
    check("startedMs from state.md", m["metrics"]["startedMs"], _epoch_ms(0, 10))

    # started must also reach find_live_session:
    # here only the stale session references the ticket, so without the stamp it would win
    cwd2, proj2 = _run_repo("2026-07-13T00:10:00Z", [
        ("fresh", [_said("unrelated work"), _tool("2026-07-13T00:20:00Z", "t1")], since_s + 3600),
        ("stale", [handoff, _tool("2026-07-13T00:01:00Z", "t2")], since_s - 3600),
    ])
    with _faked(find_project_dir=lambda c: proj2):
        m2 = ps.collect_model(cwd2, "acme-42")
    check("stale referencing session not selected", m2["session"]["id"], "fresh")
    # control: the same arrangement with no started falls back to the ticket reference
    cwd3, proj3 = _run_repo(None, [
        ("fresh", [_said("unrelated work"), _tool("2026-07-13T00:20:00Z", "t1")], since_s + 3600),
        ("stale", [handoff, _tool("2026-07-13T00:01:00Z", "t2")], since_s - 3600),
    ])
    with _faked(find_project_dir=lambda c: proj3):
        m3 = ps.collect_model(cwd3, "acme-42")
    check("no started selects the stale reference", m3["session"]["id"], "stale")


# ----- Collector(until_ms): records after the run's end are not this run's -----

def test_collector_until():
    until = _epoch_ms(0, 30)
    in_window = _usage("m_in", inp=10, out=4, ts="2026-07-13T00:20:00Z")
    in_window["message"]["stop_reason"] = "end_turn"
    late = _usage("m_late", inp=100, out=40, ts="2026-07-13T00:40:00Z", block="tool_use")
    # the session went on to other work after the run ended,
    # so the late tool call must move neither the counters nor the liveness.
    # drop the until clause and the late record reads as this run still working
    check("record after until dropped", _shape(_windowed([in_window, late], None, until_ms=until)),
          {"events": 0, "tokens_in": 10, "tokens_out": 4, "main_seen": True, "main_active": False})
    check("no until counts the late record", _shape(_windowed([in_window, late], None)),
          {"events": 1, "tokens_in": 110, "tokens_out": 44, "main_seen": True, "main_active": True})

    # a record with no stamp cannot be placed after the window either, so it is kept
    unstamped = _usage("m_none", inp=9, out=2, block="tool_use")
    del unstamped["timestamp"]
    c = _windowed([unstamped], None, until_ms=until)
    check("stampless record kept under until only", (len(c.events()), c.tokens_in, c.tokens_out), (1, 9, 2))


def test_collector_until_grace_second():
    until = _epoch_ms(0, 30)
    # ended is written in whole seconds, so a record half a second into that second is still the run's own.
    # remove the +1000 grace and this record is dropped
    grace = _usage("m_grace", inp=3, out=2, ts="2026-07-13T00:30:00.500Z", block="tool_use")
    c = _windowed([grace], None, until_ms=until)
    check("record inside the ended second kept", (len(c.events()), c.tokens_in, c.tokens_out), (1, 3, 2))
    # the next second is outside the run, and its very first millisecond already is.
    # relax >= to > and this boundary record is kept
    edge = _usage("m_edge", inp=3, out=2, ts="2026-07-13T00:30:01.000Z", block="tool_use")
    c = _windowed([edge], None, until_ms=until)
    check("record at the next second dropped", (len(c.events()), c.tokens_in, c.tokens_out), (0, 0, 0))


def test_collector_until_subagent():
    until = _epoch_ms(0, 30)
    main = [_at("assistant", "2026-07-13T00:25:00Z", "end_turn")]
    agent = [_usage("s_in", inp=7, out=3, ts="2026-07-13T00:20:00Z", block="tool_use"),
             _usage("s_late", inp=50, out=20, ts="2026-07-13T00:40:00Z", block="tool_use")]
    # the subagent file was written after the run ended, so only a per-record check can split it.
    # skip it by mtime and the in-window record goes too
    after = until // 1000 + 3600
    c = _windowed(main, None, agent, agent_mtime=after, until_ms=until)
    check("only the in-window subagent record counted",
          (len(c.events()), c.tokens_in, c.tokens_out), (1, 7, 3))
    # the dropped late record must not advance the subagent's last stamp past the main yield,
    # or a finished run reads as a background agent still working
    check("late subagent record does not keep the run active", c.main_active(), False)
    ctl = _windowed(main, None, agent, agent_mtime=after)
    check("no until counts both subagent records",
          (len(ctl.events()), ctl.tokens_in, ctl.tokens_out), (2, 57, 23))
    check("no until reads the late subagent as working", ctl.main_active(), True)


def test_collect_model_until():
    since_s = _epoch_ms(0, 10) // 1000
    handoff = _said("reading .claude/resolve/acme-42/state.md")
    records = [handoff, _tool("2026-07-13T00:05:00Z", "t_before"),
               _tool("2026-07-13T00:20:00Z", "t_during"), _tool("2026-07-13T00:40:00Z", "t_after")]
    cwd, proj = _run_repo("2026-07-13T00:10:00Z", [("fresh", records, since_s + 3600)],
                          ended="2026-07-13T00:30:00Z")
    with _faked(find_project_dir=lambda c: proj):
        m = ps.collect_model(cwd, "acme-42")
    # ended must reach the Collector, or the call after the run is counted as its own
    check("only the call between started and ended counted", m["metrics"]["toolCalls"], 1)
    cwd2, proj2 = _run_repo("2026-07-13T00:10:00Z", [("fresh", records, since_s + 3600)])
    with _faked(find_project_dir=lambda c: proj2):
        m2 = ps.collect_model(cwd2, "acme-42")
    check("no ended counts the call after it", m2["metrics"]["toolCalls"], 2)


def test_collect_model_in_progress_plain_state():
    since_s = _epoch_ms(0, 10) // 1000
    handoff = _said("reading .claude/resolve/acme-42/state.md")
    records = [handoff, _tool("2026-07-13T00:05:00Z", "t_before"),
               _tool("2026-07-13T00:20:00Z", "t_during"), _tool("2026-07-13T00:40:00Z", "t_after")]
    # the state.md mtime stands in for "last progress" while ended is empty,
    # so pin it well clear of every stamp in the fixture
    state_mtime = since_s + 7200
    cwd, proj = _run_repo("2026-07-13T00:10:00Z", [("fresh", records, since_s + 3600)], plain=True)
    state_path = os.path.join(cwd, ".claude", "resolve", "acme-42", "state.md")
    os.utime(state_path, (state_mtime, state_mtime))
    with open(state_path, encoding="utf-8") as f:
        raw = f.read()
    check("plain fixture has an empty ended line", raw.endswith(NL + "ended:" + NL), True)
    st = ps.parse_state(state_path)
    check("plain empty ended reads as empty", st.get("ended"), "")
    # only the plain form puts a bare newline right after an empty field's colon,
    # so this is where a value pattern that crosses lines makes `attention:` swallow `started:`.
    # the model cannot show it here - the live tool call reads as approaching and masks blocked
    check("plain empty attention reads as empty", st.get("attention"), "")
    with _faked(find_project_dir=lambda c: proj):
        m = ps.collect_model(cwd, "acme-42")
    # an in-progress run leaves the window open at the far end, so the late call is its own.
    # parse the empty ended as a stamp - epoch 0, or started - and this drops to 0
    check("empty ended leaves the window open", m["metrics"]["toolCalls"], 2)
    # a plain started line that fails to parse lets the pre-start call in, and startedMs falls back to it
    check("plain started read", m["metrics"]["startedMs"], _epoch_ms(0, 10))
    check("empty ended falls back to the state.md mtime", m["metrics"]["endedMs"], state_mtime * 1000)
    check("fresh session selected", m["session"]["id"], "fresh")

    # control: the same fixture with ended stamped in the plain form caps the window
    cwd2, proj2 = _run_repo("2026-07-13T00:10:00Z", [("fresh", records, since_s + 3600)],
                            ended="2026-07-13T00:30:00Z", plain=True)
    os.utime(os.path.join(cwd2, ".claude", "resolve", "acme-42", "state.md"), (state_mtime, state_mtime))
    with _faked(find_project_dir=lambda c: proj2):
        m2 = ps.collect_model(cwd2, "acme-42")
    check("plain ended caps the window", m2["metrics"]["toolCalls"], 1)
    check("plain ended read", m2["metrics"]["endedMs"], _epoch_ms(0, 30))


_TESTS = (test_status_rules, test_main_active, test_background_agent_is_not_a_yield,
          test_run_id_roundtrip, test_parse_state, test_encoding_tolerance,
          test_contention, test_timings, test_waiting_detection, test_step_activity,
          test_token_totals, test_session_selection, test_run_summary_precedence,
          test_run_panel, test_session_mentions, test_session_mentions_incremental,
          test_session_mentions_chunk_boundary, test_session_selection_since,
          test_collector_since, test_collector_since_skips_stale_subagent,
          test_collect_model_since, test_collector_until, test_collector_until_grace_second,
          test_collector_until_subagent, test_collect_model_until,
          test_collect_model_in_progress_plain_state)


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
    the stop and NEVER exits non-zero - a broken or half-edited check must
    not lock anyone out of finishing a turn (the "warn, never block" contract
    lives here, in tested code, rather than in fragile shell escaping). Silent on
    success."""
    try:
        _run_all()
        fails = _fails()
        if fails:
            body = "resolve-issue-dashboard parse_session tests FAILED (%d):\n" % len(fails)
            body += "\n".join("  - %s / %s: %s" % (g, name, detail)
                              for g, name, detail in fails)
            print(json.dumps({"systemMessage": body}))
    except Exception as exc:  # never let a test crash block the stop
        print(json.dumps({"systemMessage":
                          "resolve-issue-dashboard parse_session tests could not run: %s" % exc}))
    return 0


if __name__ == "__main__":
    if "--hook" in sys.argv[1:]:
        sys.exit(hook_main())
    sys.exit(main())
