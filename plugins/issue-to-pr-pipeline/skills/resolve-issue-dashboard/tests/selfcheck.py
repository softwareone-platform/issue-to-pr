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

import json
import os
import sys
import tempfile

# import the module under test from the sibling scripts/ dir without installing
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "scripts")))
import parse_session as ps  # noqa: E402


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


_TESTS = (test_status_rules, test_main_active, test_run_id_roundtrip,
          test_parse_state, test_encoding_tolerance, test_contention, test_timings,
          test_waiting_detection, test_step_activity, test_session_selection)


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
