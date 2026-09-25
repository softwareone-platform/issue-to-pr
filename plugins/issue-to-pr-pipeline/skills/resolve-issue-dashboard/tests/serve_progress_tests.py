"""Deterministic self-check for the resolve-issue-dashboard SERVER logic.

Grounds the decisions serve_progress makes that no one can eyeball from the rendered page:
that an archived run is never tailed,
the two load-bearing orderings inside RunManager.build
(contention before the status reconcile, the reconcile before bucketing),
the Hub's no-republish and drop-a-full-client rules,
the selection reset, the /health version read,
and the poller tick's error containment.

It deliberately does NOT cover the I/O / UI surface
(HTTP handler, SSE stream, browser launch, serve_forever, main() wiring) -
the same exclusion the sibling parse_session self-check declares, for the same reason.
It also leaves the idle-shutdown arithmetic and pick_port alone:
both read a real clock or a real socket,
and testing them would mean reshaping the source to inject one.

Pure stdlib, ASCII-only output (Windows cp1252 console). Exits non-zero on any
failure so a Stop hook can surface it. Run from anywhere:
    python tests/serve_progress_tests.py
"""

import calendar
import contextlib
import json
import os
import sys
import tempfile

# import the modules under test from the sibling scripts/ dir without installing.
# serve_progress imports parse_session at load and both live there,
# so the one path insert covers both
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "scripts")))
import parse_session as ps  # noqa: E402
import serve_progress as sp  # noqa: E402


# every check records (group, name, ok, detail) so a manual run can list the
# greens, not only the reds; the group is the test function currently running
_results = []
_group = ""


def check(name, got, want):
    ok = got == want
    _results.append((_group, name, ok, "" if ok else "got %r, want %r" % (got, want)))


@contextlib.contextmanager
def _faked(**attrs):
    """Temporarily replace attributes on parse_session.

    serve_progress holds the module itself (`import parse_session as ps`),
    so patching the attribute is what the server actually calls.
    Restored in a finally, because a check that raises inside the block
    would otherwise leak the stand-in into every later test
    and make the failure look like someone else's.
    """
    old = dict((k, getattr(ps, k)) for k in attrs)
    for k, v in attrs.items():
        setattr(ps, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(ps, k, v)


def _mgr(ticket="acme-1", cwd=None):
    """A RunManager over a throwaway cwd, with the ticket passed explicitly
    so construction never goes looking for a real .claude/resolve tree."""
    return sp.RunManager(cwd or tempfile.mkdtemp(), ticket)


# ----- _ensure_session: an archived run is never tailed -----------------------

def test_archived_run_is_not_tailed():
    asked = []

    def _live_session(project_dir, ticket=None, since_ms=None):
        asked.append(ticket)
        return "/live/session.jsonl"

    made = []

    class _FakeCollector(object):
        def __init__(self, project_dir, path, since_ms=None, until_ms=None):
            made.append(path)

    mgr = _mgr()
    mgr.project_dir = "/proj"
    mgr.session_path = "/previous/session.jsonl"
    mgr.collector = object()
    with _faked(find_live_session=_live_session, find_project_dir=lambda cwd: "/proj",
                Collector=_FakeCollector):
        mgr._ensure_session("acme-1", True)
    # an archived run has no session of its own, so its tail is dropped outright
    check("archived clears session", mgr.session_path, None)
    check("archived clears collector", mgr.collector, None)
    # and the repo's newest session is never consulted:
    # it belongs to unrelated (usually live) work,
    # so tailing it would charge that activity and those tokens to the historical run
    check("archived never asks for a session", asked, [])
    check("archived never builds a collector", made, [])

    # the live branch is the control: the Nones above are the archived decision,
    # not something _ensure_session does unconditionally
    live = _mgr()
    with _faked(find_live_session=_live_session, find_project_dir=lambda cwd: "/proj",
                Collector=_FakeCollector):
        live._ensure_session("acme-1", False)
    check("live run tails the newest session", live.session_path, "/live/session.jsonl")
    check("live run builds a collector", made, ["/live/session.jsonl"])
    # ticket-aware, so an unrelated newer session in the same repo cannot hijack it
    check("live run asks ticket-aware", asked, ["acme-1"])


def test_changed_start_rebuilds_the_collector():
    made = []

    class _FakeCollector(object):
        def __init__(self, project_dir, path, since_ms=None, until_ms=None):
            self.since_ms = since_ms
            made.append(self)

    mgr = _mgr()
    with _faked(find_live_session=lambda project_dir, ticket=None, since_ms=None: "/live/s.jsonl",
                find_project_dir=lambda cwd: "/proj", Collector=_FakeCollector):
        mgr._ensure_session("acme-1", False, 1000)
        first = mgr.collector
        mgr._ensure_session("acme-1", False, 2000)
    # a new start on the same ticket is a new run,
    # and the old tail was read under the old window,
    # so the collector is rebuilt even though the session path never moved
    check("changed start builds a new collector", mgr.collector is first, False)
    check("changed start built twice", len(made), 2)
    check("new collector gets the new start", made[-1].since_ms, 2000)
    check("new start recorded", mgr.since_ms, 2000)

    # the control uses a real start rather than None,
    # because None then None would stay unchanged even if the start were never recorded
    same = []

    class _SameCollector(object):
        def __init__(self, project_dir, path, since_ms=None, until_ms=None):
            same.append(self)

    steady = _mgr()
    with _faked(find_live_session=lambda project_dir, ticket=None, since_ms=None: "/live/s.jsonl",
                find_project_dir=lambda cwd: "/proj", Collector=_SameCollector):
        steady._ensure_session("acme-1", False, 1000)
        kept = steady.collector
        steady._ensure_session("acme-1", False, 1000)
    # an unchanged start and path keep the tail, whose read offsets a rebuild would throw away
    check("unchanged start keeps the collector", steady.collector is kept, True)
    check("unchanged start built once", len(same), 1)


def test_changed_end_rebuilds_the_collector():
    made = []

    class _FakeCollector(object):
        def __init__(self, project_dir, path, since_ms=None, until_ms=None):
            self.since_ms = since_ms
            self.until_ms = until_ms
            made.append(self)

    mgr = _mgr()
    with _faked(find_live_session=lambda project_dir, ticket=None, since_ms=None: "/live/s.jsonl",
                find_project_dir=lambda cwd: "/proj", Collector=_FakeCollector):
        mgr._ensure_session("acme-1", False, 1000, 5000)
        first = mgr.collector
        mgr._ensure_session("acme-1", False, 1000, 6000)
    # a moved end is the run finishing or reopening,
    # and the old tail was cut at the old end,
    # so the collector is rebuilt even though the session path and the start never moved.
    # dropping the until_ms comparison from the rebuild condition turns these red
    check("changed end builds a new collector", mgr.collector is first, False)
    check("changed end built twice", len(made), 2)
    # dropping the until_ms kwarg from the Collector call leaves this None
    check("new collector gets the new end", made[-1].until_ms, 6000)
    check("new collector keeps the start", made[-1].since_ms, 1000)
    check("new end recorded", mgr.until_ms, 6000)

    # the control uses a real end rather than None,
    # because None then None would stay unchanged even if the end were never recorded
    same = []

    class _SameCollector(object):
        def __init__(self, project_dir, path, since_ms=None, until_ms=None):
            same.append(self)

    steady = _mgr()
    with _faked(find_live_session=lambda project_dir, ticket=None, since_ms=None: "/live/s.jsonl",
                find_project_dir=lambda cwd: "/proj", Collector=_SameCollector):
        steady._ensure_session("acme-1", False, 1000, 5000)
        kept = steady.collector
        steady._ensure_session("acme-1", False, 1000, 5000)
    # an unchanged window keeps the tail, whose read offsets a rebuild would throw away.
    # if the end were never stored, the second call would compare 5000 against None and rebuild
    check("unchanged end keeps the collector", steady.collector is kept, True)
    check("unchanged end built once", len(same), 1)


# ----- RunManager.build: the two orderings its own comments name --------------

def _entry(rid, status, next_step, ticket="acme-1", cwd="/repo", ms=100):
    """One run-list summary, shaped as ps.list_runs returns them."""
    return {"id": rid, "repo": os.path.basename(cwd), "cwd": cwd, "ticket": ticket,
            "runKey": "", "runStamp": "", "nextStep": next_step, "status": status,
            "lastActivityMs": ms}


def _run_build(mgr, runs, model_status):
    """Drive RunManager.build with the session tail and the model stubbed out.
    ps.contention and ps.plan_run_panel stay REAL -
    their output is the oracle for the orderings under test,
    so stubbing them would remove the very measurement."""
    with _faked(find_project_dir=lambda cwd: "/proj",
                find_live_session=lambda project_dir, ticket=None, since_ms=None: None,
                build_model=lambda *a, **k: {"status": model_status},
                list_runs=lambda launch_cwd: runs):
        return mgr.build()


def test_build_computes_contention_before_reconcile():
    d = tempfile.mkdtemp()
    mgr = _mgr("acme-1", d)
    sel = _entry(ps.run_id(d, "acme-1"), "paused", "b-code-risk", cwd=d)
    out = _run_build(mgr, [sel], "running")
    # contention counts runs whose COARSE status is active at a test-executing step.
    # the selected entry is reconciled to active a few lines later,
    # purely so the sidebar dot matches the hero,
    # so a contention computed after that reconcile
    # would report a shared-infrastructure collision the display fix itself invented
    check("contention sees the unmodified list", out["contention"]["count"], 0)
    check("contention names no run", out["contention"]["runs"], [])
    # the reconcile really did fire,
    # so the 0 above is the ordering rather than a scenario where nothing would have changed
    check("selected entry was reconciled", sel["status"], "active")


def test_build_reconciles_before_bucketing():
    d = tempfile.mkdtemp()
    mgr = _mgr("acme-1", d)
    sid = ps.run_id(d, "acme-1")
    other = ps.run_id(d, "acme-2")
    sel = _entry(sid, "done", "b-implement", cwd=d)
    peer = _entry(other, "done", "b-implement", ticket="acme-2", cwd=d, ms=900)
    out = _run_build(mgr, [sel, peer], "running")
    grp = out["runPanel"][0]
    # the reconcile walks the FLAT list;
    # once plan_run_panel has bucketed it, the selected entry sits inside runPanel[].done,
    # where that loop cannot reach it.
    # the bucket is the visible consequence:
    # a run reconciled off "done" has to leave the collapsed bucket,
    # and a reconcile running after the split could not move it
    check("selected run left the done bucket", [r["id"] for r in grp["done"]], [other])
    check("selected run is in open", [r["id"] for r in grp["open"]], [sid])
    check("selected id reported", out["selectedId"], sid)


def test_build_status_mapping():
    d = tempfile.mkdtemp()
    mgr = _mgr("acme-1", d)
    sid = ps.run_id(d, "acme-1")

    sel = _entry(sid, "paused", "b-implement", cwd=d)
    peer = _entry(ps.run_id(d, "acme-2"), "paused", "b-implement", ticket="acme-2", cwd=d)
    _run_build(mgr, [sel, peer], "running")
    # "running" is the model's word for the state the panel calls "active"
    check("running maps to active", sel["status"], "active")
    # only the selected entry is reconciled -
    # the rest of the list is cursor-only, and the tailed model says nothing about them
    check("peer entry untouched", peer["status"], "paused")

    # any other model status is copied across verbatim, no translation
    sel2 = _entry(sid, "paused", "b-implement", cwd=d)
    _run_build(_mgr("acme-1", d), [sel2], "blocked")
    check("other status copied verbatim", sel2["status"], "blocked")

    # a model with no status at all leaves the coarse cursor status alone
    sel3 = _entry(sid, "paused", "b-implement", cwd=d)
    with _faked(find_project_dir=lambda cwd: "/proj",
                find_live_session=lambda project_dir, ticket=None, since_ms=None: None,
                build_model=lambda *a, **k: {},
                list_runs=lambda launch_cwd: [sel3]):
        _mgr("acme-1", d).build()
    check("no model status leaves it alone", sel3["status"], "paused")


def _build_since(state_text):
    """Run build over a real state.md and record the since_ms that reaches
    the session lookup and the Collector."""
    asked, made = _build_window(state_text)
    return asked, [since for since, _ in made]


def _build_window(state_text):
    """Run build over a real state.md and record the since_ms that reaches
    the session lookup, and the (since_ms, until_ms) pair that reaches the Collector.
    The session path is one that does not exist, so the Collector is built
    and os.path.isfile then skips its refresh."""
    d = tempfile.mkdtemp()
    resolve_dir = os.path.join(d, ".claude", "resolve", "acme-1")
    os.makedirs(resolve_dir)
    _write(resolve_dir, "state.md", state_text)
    asked = []
    made = []

    def _live_session(project_dir, ticket=None, since_ms=None):
        asked.append(since_ms)
        return "/live/s.jsonl"

    class _FakeCollector(object):
        def __init__(self, project_dir, path, since_ms=None, until_ms=None):
            made.append((since_ms, until_ms))

    with _faked(find_project_dir=lambda cwd: "/proj",
                find_live_session=_live_session, Collector=_FakeCollector,
                build_model=lambda *a, **k: {"status": "running"},
                list_runs=lambda launch_cwd: []):
        _mgr("acme-1", d).build()
    return asked, made


def test_build_windows_the_session_by_the_run_start():
    asked, made = _build_since("started: 2026-09-01T10:00:00Z\n")
    # expected value derived with calendar.timegm, independent of the parser's own _iso_to_ms
    want = calendar.timegm((2026, 9, 1, 10, 0, 0)) * 1000
    # state.md is read before the session is chosen,
    # so its start both picks the session and windows the tail
    check("session lookup gets the start", asked, [want])
    check("collector gets the start", made, [want])

    # a state.md with no start leaves the window open, rather than inventing one
    asked, made = _build_since("next-step: b-implement\n")
    check("no start asks unwindowed", asked, [None])
    check("no start builds unwindowed", made, [None])


def test_build_closes_the_session_window_at_the_run_end():
    _, made = _build_window("started: 2026-09-01T10:00:00Z\nended: 2026-09-01T12:30:00Z\n")
    # expected values derived with calendar.timegm, independent of the parser's own _iso_to_ms
    start = calendar.timegm((2026, 9, 1, 10, 0, 0)) * 1000
    end = calendar.timegm((2026, 9, 1, 12, 30, 0)) * 1000
    # the start and the end both reach the Collector, each in its own slot.
    # passing None or the start as the end, or swapping the two, turns this red
    check("collector gets the start and the end", made, [(start, end)])

    # a run still in progress has no end yet, so the window stays open on that side
    _, made = _build_window("started: 2026-09-01T10:00:00Z\n")
    check("no end leaves the window open", made, [(start, None)])


# ----- Hub: republish gate, slow-client drop, registration round-trip ---------

def test_hub_publish():
    hub = sp.Hub()
    q = hub.register()
    hub.publish('{"a":1}')
    check("first publish delivered", q.get_nowait(), '{"a":1}')
    hub.publish('{"a":1}')
    # the poller ticks once a second,
    # so an unchanged run would otherwise wake every connected browser on every tick,
    # for a frame identical to the last
    check("identical payload not republished", q.qsize(), 0)
    hub.publish('{"a":2}')
    check("changed payload delivered", q.get_nowait(), '{"a":2}')
    check("snapshot is the latest payload", hub.snapshot(), '{"a":2}')
    # a client registering late still gets a frame from snapshot(), not silence
    check("snapshot before any publish", sp.Hub().snapshot(), "{}")


def test_hub_drop_does_not_reach_the_publisher():
    hub = sp.Hub()
    slow = hub.register()
    fast = hub.register()
    # register() caps each client queue at 8
    for i in range(8):
        hub.publish('{"n":%d}' % i)
    while fast.qsize():
        fast.get_nowait()
    hub.publish('{"n":99}')
    # the wedged client's queue is full, so its frame is dropped inside publish
    # instead of the failure travelling back out to the caller -
    # without that swallow the poller thread would die on one stalled browser,
    # taking the live frame away from every other viewer
    check("full client gains nothing", slow.qsize(), 8)
    # publish carried on past the full client rather than ending there
    check("healthy client still served", fast.get_nowait(), '{"n":99}')
    # the drop costs that client the frame, not the stream: it is still attached
    check("dropped client still registered", hub.client_count(), 2)
    # deliberately not covered: that the put is non-blocking rather than merely bounded -
    # a blocking put lands on this same end state, and the only cheap oracle is a wall clock


def test_hub_registration():
    hub = sp.Hub()
    check("no clients initially", hub.client_count(), 0)
    a = hub.register()
    b = hub.register()
    check("register counts up", hub.client_count(), 2)
    hub.unregister(a)
    check("unregister counts down", hub.client_count(), 1)
    # discard, not remove:
    # _stream's finally can run after an error path that already dropped the queue,
    # and a raise there would take the handler thread with it
    hub.unregister(a)
    check("unregister is idempotent", hub.client_count(), 1)
    hub.unregister(b)
    check("all unregistered", hub.client_count(), 0)
    # /health reads this to decide whether to pop a browser tab,
    # and publishing only moves frames into the queues -
    # it must not disturb the record of who is attached
    hub.register()
    hub.publish('{"a":1}')
    check("count survives a publish", hub.client_count(), 1)


# ----- RunManager.set_selected: rejection, and the no-op guard ----------------

def test_set_selected_rejects_unresolvable():
    mgr = _mgr()
    before = (mgr.sel_cwd, mgr.sel_ticket, mgr.sel_run_key)
    # /select answers ok:false and the dashboard keeps watching what it had;
    # a silent accept would repoint the whole server at a run that does not exist
    check("empty id rejected", mgr.set_selected(""), False)
    check("undecodable id rejected", mgr.set_selected("not-a-real-id!!"), False)
    # decodable base64 that is not a run id has no "::" separator, so no cwd
    check("well-formed but not a run id", mgr.set_selected("YWJjZGVm"), False)
    check("selection untouched", (mgr.sel_cwd, mgr.sel_ticket, mgr.sel_run_key), before)


def test_set_selected_only_resets_on_a_real_change():
    d = tempfile.mkdtemp()
    mgr = _mgr("acme-1", d)
    sentinel = object()
    mgr.project_dir, mgr.session_path, mgr.collector = "/proj", "/sess.jsonl", sentinel

    check("re-select accepted", mgr.set_selected(ps.run_id(d, "acme-1")), True)
    # re-selecting the run already shown must not drop the tail:
    # the Collector holds per-file read offsets,
    # and a fresh one re-reads the transcript from byte zero,
    # so the client clicking its own row would cost a full re-parse
    check("same selection keeps the collector", mgr.collector is sentinel, True)
    check("same selection keeps the session", mgr.session_path, "/sess.jsonl")
    check("same selection keeps the project dir", mgr.project_dir, "/proj")

    check("new ticket accepted", mgr.set_selected(ps.run_id(d, "acme-2")), True)
    check("changed selection drops collector", mgr.collector, None)
    check("changed selection drops session", mgr.session_path, None)
    check("changed selection drops project dir", mgr.project_dir, None)
    check("changed selection takes the ticket", mgr.sel_ticket, "acme-2")

    # the run_key is part of the identity:
    # the same repo and ticket at an archived stamp is a different run, so it must reset too
    mgr.collector = sentinel
    check("archived stamp accepted",
          mgr.set_selected(ps.run_id(d, "acme-2", "2026-07-13T00-00-00Z")), True)
    check("run_key change resets", mgr.collector, None)
    check("run_key recorded", mgr.sel_run_key, "2026-07-13T00-00-00Z")


# ----- plugin_version: /health's staleness signal -----------------------------

def _version_from(path):
    """plugin_version reads a module-level constant, so point it at a fixture
    and put the real path back."""
    old = sp.PLUGIN_JSON
    sp.PLUGIN_JSON = path
    try:
        return sp.plugin_version()
    finally:
        sp.PLUGIN_JSON = old


def _write(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(text)
    return p


def test_plugin_version():
    d = tempfile.mkdtemp()
    check("reads the version",
          _version_from(_write(d, "good.json", '{"name": "x", "version": "0.25.1"}')),
          "0.25.1")
    # a detached server keeps serving its own old assets across a Claude restart,
    # so /health must always answer something the launcher can compare -
    # every unreadable shape degrades to "unknown" rather than raising into the handler
    check("missing file", _version_from(os.path.join(d, "gone.json")), "unknown")
    check("malformed json", _version_from(_write(d, "bad.json", "{not json")), "unknown")
    check("no version key", _version_from(_write(d, "nov.json", '{"name": "x"}')), "unknown")
    # an explicitly empty version is no more useful than a missing one
    check("empty version", _version_from(_write(d, "empty.json", '{"version": ""}')), "unknown")
    # every failure branch above already degrades to "unknown",
    # so this is the one check that pins the PLUGIN_JSON path arithmetic itself:
    # one ".." short of the plugin root and the shipped plugin.json is never opened,
    # and /health would advertise "unknown" forever without a single check going red
    check("wired-up path reaches the shipped manifest",
          sp.plugin_version() != "unknown", True)


# ----- tick: a raising build must not escape into the poller ------------------

class _Mgr(object):
    """Minimal RunManager stand-in: build() either answers or raises."""

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def build(self):
        if self._error is not None:
            raise self._error
        return self._result


def test_tick_publishes_the_model():
    hub = sp.Hub()
    sp.tick(_Mgr(result={"selectedId": "abc"}), hub)
    # the control for the error case below: a healthy build reaches the hub whole
    check("model published", json.loads(hub.snapshot()), {"selectedId": "abc"})


def test_tick_contains_a_raising_build():
    hub = sp.Hub()
    sp.tick(_Mgr(error=RuntimeError("x" * 300)), hub)
    payload = json.loads(hub.snapshot())
    # poller calls tick once a second;
    # an exception escaping here kills that thread,
    # and every viewer then sits on the last good frame forever,
    # with nothing on screen to say the updates stopped
    check("error payload replaces the model", sorted(payload), ["error"])
    # truncated, so one enormous traceback cannot become the whole SSE frame
    check("error truncated to 200", len(payload["error"]), 200)
    check("error is the message head", payload["error"], "x" * 200)


_TESTS = (test_archived_run_is_not_tailed, test_changed_start_rebuilds_the_collector,
          test_changed_end_rebuilds_the_collector,
          test_build_computes_contention_before_reconcile,
          test_build_reconciles_before_bucketing, test_build_status_mapping,
          test_build_windows_the_session_by_the_run_start,
          test_build_closes_the_session_window_at_the_run_end,
          test_hub_publish, test_hub_drop_does_not_reach_the_publisher,
          test_hub_registration,
          test_set_selected_rejects_unresolvable,
          test_set_selected_only_resets_on_a_real_change,
          test_plugin_version, test_tick_publishes_the_model,
          test_tick_contains_a_raising_build)


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
    the stop and NEVER exits non-zero - a broken or half-edited check must not
    lock anyone out of finishing a turn. Silent on success."""
    try:
        _run_all()
        fails = _fails()
        if fails:
            body = "resolve-issue-dashboard serve_progress tests FAILED (%d):\n" % len(fails)
            body += "\n".join("  - %s / %s: %s" % (g, name, detail)
                              for g, name, detail in fails)
            print(json.dumps({"systemMessage": body}))
    except Exception as exc:  # never let a test crash block the stop
        print(json.dumps({"systemMessage":
                          "resolve-issue-dashboard serve_progress tests could not run: %s" % exc}))
    return 0


if __name__ == "__main__":
    if "--hook" in sys.argv[1:]:
        sys.exit(hook_main())
    sys.exit(main())
