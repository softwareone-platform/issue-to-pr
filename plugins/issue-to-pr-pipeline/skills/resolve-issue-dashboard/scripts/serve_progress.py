"""Local, read-only progress server for resolve-issue runs.

One global server serves a single self-contained dashboard and streams, over
Server-Sent Events, a payload of every resolve run it can see across all repos
plus the full live model of the selected run. It tails only the files Claude
Code already writes; it never writes to a transcript or to `.claude/resolve/`,
and it exposes nothing beyond localhost.

    python serve_progress.py [--cwd PATH] [--ticket TICKET] [--port N] [--no-browser]
"""

import argparse
import json
import os
import queue
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

import parse_session as ps

ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
PLUGIN_JSON = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "..", ".claude-plugin", "plugin.json"))
POLL_INTERVAL_S = 1.0
KEEPALIVE_S = 15.0
# self-terminate after this long with no connected viewer, so a dashboard whose
# launching session has gone (closed tab, exited or orphaned session) does not
# linger forever. the watchdog lives in this process, so it runs even when the
# parent session is gone - the only place a cleanup is guaranteed to execute
IDLE_SHUTDOWN_S = 30 * 60


def plugin_version():
    """Read this dashboard's bundled plugin version so /health can advertise it.
    A stale detached server keeps serving its own (old) assets and survives a
    Claude restart, so exposing the version lets the launcher tell an
    out-of-date server from a current one and replace it rather than silently
    reusing it."""
    try:
        with open(PLUGIN_JSON, encoding="utf-8") as f:
            return json.load(f).get("version") or "unknown"
    except (OSError, ValueError):
        return "unknown"


class Hub:
    """Holds the latest payload and fans it out to connected SSE clients.

    A single poller thread is the only writer; clients only read, so a plain
    lock around the published snapshot is enough.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._payload_json = "{}"
        self._clients = set()

    def publish(self, payload_json):
        with self._lock:
            if payload_json == self._payload_json:
                return
            self._payload_json = payload_json
            clients = list(self._clients)
        for q in clients:
            try:
                q.put_nowait(payload_json)
            except queue.Full:
                pass

    def snapshot(self):
        with self._lock:
            return self._payload_json

    def register(self):
        q = queue.Queue(maxsize=8)
        with self._lock:
            self._clients.add(q)
        return q

    def unregister(self, q):
        with self._lock:
            self._clients.discard(q)

    def client_count(self):
        with self._lock:
            return len(self._clients)


class RunManager:
    """Discovers runs across all repos and tails the one currently selected.

    The run list is cheap (no tailing); only the selected run gets a Collector.
    The selection is server-wide (one local viewer); switching rebuilds the
    Collector for the new run. A lock guards the selected state and collector,
    since `/select` (a request thread) and the poller both touch them.
    """

    def __init__(self, launch_cwd, explicit_ticket):
        self.launch_cwd = os.path.abspath(launch_cwd)
        self._lock = threading.Lock()
        self.sel_cwd = self.launch_cwd
        self.sel_ticket = explicit_ticket or ps.find_resolve_ticket(self.launch_cwd, None)
        self.sel_run_key = ""
        self.project_dir = None
        self.session_path = None
        self.collector = None

    def set_selected(self, run_id):
        cwd, ticket, run_key = ps.decode_run_id(run_id)
        if not cwd:
            return False
        cwd = os.path.abspath(cwd)
        with self._lock:
            if cwd != self.sel_cwd or ticket != self.sel_ticket or run_key != self.sel_run_key:
                self.sel_cwd = cwd
                self.sel_ticket = ticket
                self.sel_run_key = run_key
                # drop the old run's tail so the new run starts fresh
                self.project_dir = None
                self.session_path = None
                self.collector = None
        return True

    def _ensure_session(self):
        if not self.project_dir:
            self.project_dir = ps.find_project_dir(self.sel_cwd)
        latest = ps.find_live_session(self.project_dir)
        if latest != self.session_path:
            self.session_path = latest
            self.collector = ps.Collector(self.project_dir, latest) if latest else None

    def build(self):
        with self._lock:
            self._ensure_session()
            sel_cwd = self.sel_cwd
            ticket = self.sel_ticket or ps.find_resolve_ticket(sel_cwd, None)
            state = {}
            ended_ms = None
            if ticket:
                state_path = os.path.join(ps.resolve_dir_for(sel_cwd, ticket), "state.md")
                state = ps.parse_state(state_path)
                # run's last-progress time; stable across a next-day relaunch
                ended_ms = ps._mtime_ms(state_path)
            events, tin, tout = [], 0, 0
            main_active = False
            if self.collector and self.session_path and os.path.isfile(self.session_path):
                self.collector.refresh()
                events = self.collector.events()
                tin, tout = self.collector.tokens_in, self.collector.tokens_out
                main_active = self.collector.main_active()
            meta = {
                "id": ps.session_id_of(self.session_path) if self.session_path else None,
                "projectDir": self.project_dir,
                "cwd": sel_cwd,
                "ticketDetected": ticket,
            }
            model = ps.build_model(state, events, tin, tout, meta, ended_ms, main_active)
            selected_id = ps.run_id(sel_cwd, ticket)
        # run list is independent of selection state -> compute outside the lock
        runs = ps.list_runs(self.launch_cwd)
        # derive the cross-run test-contention heads-up from the UNMODIFIED list,
        # before the display-only reconciliation below. contention() also reads
        # runs[].status but deliberately uses the coarse cursor status (it counts
        # runs 'positioned to collide' on a test step even when momentarily idle,
        # and excludes non-active ones); the sidebar override must not leak into it
        contention = ps.contention(runs)
        # the list is cursor-only (no tailing), so its coarse status for the
        # selected run can disagree with the tailed model - e.g. still blocked /
        # paused while the model has demoted a not-yet-reached gate to running.
        # reconcile just that one entry so the sidebar dot matches the hero
        model_status = model.get("status")
        if model_status:
            for r in runs:
                if r.get("id") == selected_id:
                    r["status"] = "active" if model_status == "running" else model_status
                    break
        return {
            "runs": runs,
            "selectedId": selected_id,
            "model": model,
            "contention": contention,
        }


def tick(mgr, hub):
    try:
        hub.publish(json.dumps(mgr.build(), ensure_ascii=True))
    except Exception as exc:  # never let a transient read error kill the loop
        hub.publish(json.dumps({"error": str(exc)[:200]}, ensure_ascii=True))


def poller(mgr, hub, stop, server):
    """Publish the model every interval, and self-terminate the server once no
    viewer has been connected for IDLE_SHUTDOWN_S.

    The idle window is seeded at startup (not armed only after the first client),
    so a launch where the browser never connects still shuts down - the orphan
    this guards against. IDLE_SHUTDOWN_S far exceeds the launch-to-connect delay,
    so the startup gap never trips it. shutdown() is called from this thread, not
    the serve_forever thread - the required usage; main()'s finally re-call is
    idempotent. Wrapped so a transient error cannot kill the loop and freeze
    updates."""
    last_active = time.monotonic()
    while not stop.is_set():
        tick(mgr, hub)
        try:
            if hub.client_count() > 0:
                last_active = time.monotonic()
            elif time.monotonic() - last_active > IDLE_SHUTDOWN_S:
                server.shutdown()
                return
        except Exception:
            pass
        stop.wait(POLL_INTERVAL_S)


def make_handler(hub, mgr, version):
    index_path = os.path.normpath(os.path.join(ASSETS, "index.html"))

    class Handler(BaseHTTPRequestHandler):
        # keep the console quiet and ASCII-only
        def log_message(self, *args):
            return

        def _send(self, code, ctype, body):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # the page is read fresh from disk per request, so a redeploy's edited
            # CSS / JS must reach the browser on refresh. without this, a 200 with
            # no cache header is heuristically cached and the live SSE only swaps
            # data, leaving the stale page (e.g. old row heights) in place
            self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            if path in ("/", "/index.html"):
                try:
                    with open(index_path, "rb") as f:
                        body = f.read()
                    self._send(200, "text/html; charset=utf-8", body)
                except OSError:
                    self._send(500, "text/plain", b"index.html not found")
            elif path == "/model":
                self._send(200, "application/json", hub.snapshot().encode("utf-8"))
            elif path == "/health":
                # built per-request so viewers reflects the live SSE client count.
                # the skill's reuse path reads it to decide whether to reopen a browser
                # tab: 0 viewers means every tab was closed, so reopen one; a positive
                # count means a tab is already watching, so do not pop another
                body = json.dumps({
                    "app": "resolve-issue-dashboard",
                    "version": version,
                    "viewers": hub.client_count(),
                }).encode("utf-8")
                self._send(200, "application/json", body)
            elif path == "/select":
                rid = (parse_qs(parsed.query).get("run") or [""])[0]
                ok = mgr.set_selected(rid)
                if ok:
                    tick(mgr, hub)  # publish the new selection immediately
                self._send(200, "application/json",
                           b'{"ok":true}' if ok else b'{"ok":false}')
            elif path == "/events":
                self._stream()
            else:
                self._send(404, "text/plain", b"not found")

        def _stream(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            q = hub.register()
            try:
                self._write_event(hub.snapshot())
                while True:
                    try:
                        data = q.get(timeout=KEEPALIVE_S)
                        self._write_event(data)
                    except queue.Empty:
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                hub.unregister(q)

        def _write_event(self, data):
            self.wfile.write(b"data: " + data.encode("utf-8") + b"\n\n")
            self.wfile.flush()

    return Handler


def pick_port(preferred):
    """Bind the preferred port, or the next few if another program holds it."""
    import socket

    for port in range(preferred, preferred + 10):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
            s.close()
            return port
        except OSError:
            s.close()
            continue
    # every candidate is busy; fail loudly rather than return a port that will
    # then crash on bind
    raise SystemExit(
        "no free port in %d-%d; pass --port <n> to pick another" % (preferred, preferred + 9)
    )


def main():
    parser = argparse.ArgumentParser(description="Read-only resolve-issue progress dashboard (global, all repos).")
    parser.add_argument("--cwd", default=os.getcwd(), help="repo to select by default")
    parser.add_argument("--ticket", default=None)
    parser.add_argument("--port", type=int, default=4317)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    version = plugin_version()
    mgr = RunManager(args.cwd, args.ticket)
    hub = Hub()
    stop = threading.Event()

    # seed the first payload before the browser connects
    tick(mgr, hub)

    # build the server before starting the poller: the poller holds the server
    # reference to call shutdown() for the idle self-terminate
    port = pick_port(args.port)
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(hub, mgr, version))

    t = threading.Thread(target=poller, args=(mgr, hub, stop, server), daemon=True)
    t.start()

    url = "http://127.0.0.1:%d/" % port
    # flush each line: a background (non-TTY) launch block-buffers stdout, which
    # otherwise keeps the URL from reaching the output file promptly
    print("resolve-issue-dashboard %s (global, all repos)" % version, flush=True)
    print("  launch cwd : " + mgr.launch_cwd, flush=True)
    print("  url        : " + url, flush=True)
    print("  press Ctrl+C to stop", flush=True)
    if not args.no_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopping")
    finally:
        stop.set()
        server.shutdown()


if __name__ == "__main__":
    main()
