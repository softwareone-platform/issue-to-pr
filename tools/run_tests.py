#!/usr/bin/env python3
"""Run every test suite in the repo, one process each.

Discovery is a glob rather than a list, because a list is a thing to forget:
the CI workflow named its suites individually and a newly written one ran
nowhere until somebody noticed. The pre-push hook calls this after the gates,
so a suite now fails before a push instead of after it.

Deliberately NOT a gate inside pre_publish_check.py. That file's own tests run
every gate against a temporary fixture root, where this one would find zero
suites and fail - and the only way out would be a carve-out exempting exactly
the case that exercises it.

Standard library only, ASCII-only output, same as everything else here.
"""

import os
import re
import subprocess
import sys

# a suite is a file named for the module it covers, under a tests/ directory.
# the runner itself sits in tools/, not tools/tests/, so it cannot match itself.
SUITE = re.compile(r"_tests\.py$")
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv"}

# each suite prints this as its last line; the count is worth surfacing because
# a suite that silently stopped collecting still exits zero.
TALLY = re.compile(r"(\d+) passed, (\d+) failed")


def discover(root):
    """Every `<name>_tests.py` under a `tests/` directory, walked from disk.

    Walked rather than taken from `git ls-files` on purpose: a suite written but
    not yet staged is exactly the one most likely to be broken, and skipping it
    would reproduce the gap this runner exists to close."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        if os.path.basename(dirpath) != "tests":
            continue
        for name in sorted(filenames):
            if SUITE.search(name):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def run_suite(path, root):
    """Run one suite in its own process and return (ok, passed, failed, output).

    `sys.executable` rather than a bare `python`, so a CI matrix cell runs the
    interpreter it selected instead of whatever is first on PATH."""
    proc = subprocess.run([sys.executable, path], cwd=root,
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    out = (proc.stdout or "") + (proc.stderr or "")
    passed = failed = None
    for m in TALLY.finditer(out):
        passed, failed = int(m.group(1)), int(m.group(2))
    return proc.returncode == 0, passed, failed, out


def main(argv):
    root = os.path.abspath(argv[1]) if len(argv) > 1 else os.getcwd()
    suites = discover(root)

    # finding nothing must never read as everything passing - the failure mode
    # this repo already names for its file-scanning gates
    if not suites:
        print("FAIL: no *_tests.py found under any tests/ directory in " + root)
        return 1

    broken = []
    total_passed = total_failed = 0
    counted = 0
    for path in suites:
        rel = os.path.relpath(path, root).replace("\\", "/")
        ok, passed, failed, out = run_suite(path, root)
        if passed is None:
            # a suite that did not print a tally is reported by exit code alone,
            # and says so, rather than being silently counted as zero checks
            print("[%s] %s (no tally printed)" % ("ok  " if ok else "FAIL", rel))
        else:
            counted += 1
            total_passed += passed
            total_failed += failed
            print("[%s] %-64s %4d passed, %d failed"
                  % ("ok  " if ok else "FAIL", rel, passed, failed))
        if not ok:
            broken.append((rel, out.strip()))

    print("")
    print("%d suite(s), %d passed, %d failed" % (len(suites), total_passed, total_failed)
          + ("" if counted == len(suites) else " (%d of %d reported a tally)" % (counted, len(suites))))

    for rel, out in broken:
        print("")
        print("----- %s -----" % rel)
        print(out)

    return 1 if broken else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
