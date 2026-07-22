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

def _model(next_step, attention="", main_active=False):
    state = {
        "next-step": next_step,
        "attention": attention,
        "ticket": "acme-1",
        "plan-approved": "yes",
    }
    m = ps.build_model(state, [], 0, 0, {"cwd": "."}, None, main_active)
    cur = next((s for s in m["steps"] if s["id"] == next_step), None)
    return {
        "status": m["status"],
        "gate": m["gate"] is not None,
        "blocked": m["blocked"] is not None,
        "cur": cur["status"] if cur else None,
    }


def test_status_rules():
    # a gate step, genuinely parked (yielded) -> amber gate shown
    check("a-gate-approve parked", _model("a-gate-approve", "", False),
          {"status": "paused", "gate": True, "blocked": False, "cur": "paused"})
    # a gate step, still approaching (main session busy) -> demoted to running,
    # gate payload suppressed so the client keeps the amber cue off
    check("a-gate-approve approaching", _model("a-gate-approve", "", True),
          {"status": "running", "gate": False, "blocked": False, "cur": "running"})
    # attention set, genuinely parked -> red blocked shown
    check("b-open-pr blocked parked", _model("b-open-pr", "awaiting confirm", False),
          {"status": "blocked", "gate": False, "blocked": True, "cur": "blocked"})
    # attention set but still drafting (busy) -> demoted, blocked payload suppressed
    check("b-open-pr blocked approaching", _model("b-open-pr", "awaiting confirm", True),
          {"status": "running", "gate": False, "blocked": False, "cur": "running"})
    # a genuine disposition wait at b-code-risk must still show blocked (no regression)
    check("b-code-risk disposition parked", _model("b-code-risk", "unresolved risk", False),
          {"status": "blocked", "gate": False, "blocked": True, "cur": "blocked"})
    # a non-gate step with no attention is unaffected by main_active either way
    check("b-implement non-gate busy", _model("b-implement", "", True),
          {"status": "running", "gate": False, "blocked": False, "cur": "running"})
    check("b-implement non-gate idle", _model("b-implement", "", False),
          {"status": "running", "gate": False, "blocked": False, "cur": "running"})


# ----- Collector.main_active: main-session liveness parse ---------------------

def _main_active(lines):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "sess.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for o in lines:
            f.write(json.dumps(o) + "\n")
    c = ps.Collector(d, p)
    c.refresh()
    return c.main_active()


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


_TESTS = (test_status_rules, test_main_active, test_run_id_roundtrip,
          test_parse_state, test_contention)


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
