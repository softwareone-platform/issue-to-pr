#!/usr/bin/env python3
"""Pre-publish gates for the issue-to-pr plugins.

Every gate here was a prose instruction in CLAUDE.md that someone had to
remember and run by hand, and this session ran four of them manually before
one commit. Each gate returns a list of human-readable failures rather than
printing or exiting, so tools/tests/pre_publish_check_tests.py can plant one known-answer defect
per gate and assert that exactly that gate reports it.

Standard library only, to match the dashboard's server and for the reason the
repo gives there: a contributor should need nothing installed to run it.
"""

import json
import os
import re
import subprocess
import sys

PLUGINS = "plugins"

# the description ceiling is the Agent Skills specification's, not any one
# harness's. measured in characters on the whitespace-normalised value, which
# is also why this does not shell out to skills-ref: that validator reads the
# file with no encoding and counts bytes on a cp1252 Windows locale, so it
# inflates every em-dash into two phantom characters.
DESCRIPTION_MAX = 1024

# hosts the published files are allowed to reference. derived from the tracked
# tree, so anything new is a deliberate addition rather than a silent leak.
ALLOWED_HOSTS = {
    "github.com", "docs.github.com", "cli.github.com",
    "claude.com", "www.python.org", "www.npmjs.com",
    "learn.microsoft.com", "www.apache.org",
    "acme.atlassian.net", "127.0.0.1", "localhost",
}

# ticket-shaped tokens that are placeholders or generic examples rather than a
# real tracker key. anything else with three or more digits is treated as a leak.
ALLOWED_TICKET_PREFIXES = {"acme", "gh", "issue", "hotfix", "backup"}

TICKET_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{2,10})-([0-9]{3,})(?![0-9])")
HOST_RE = re.compile(r"https?://([A-Za-z0-9._-]+)")
# a host with no dot cannot be a real machine name in published prose, and both
# occurrences in this repo are placeholders (`https://host/path`, `https://org`).
# the cost of this exemption is a bare intranet short name, which would slip.
PLACEHOLDER_HOST = re.compile(r"^[A-Za-z0-9_-]+$")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

TEXT_SUFFIXES = {".md", ".json", ".py", ".yml", ".yaml", ".txt", ".html", ".sh"}

# gates append here when they decline to run rather than when they fail. a gate
# that skips silently reads exactly like a gate that passed, which is how a
# fallback path hides for months.
NOTES = []


def _read(path):
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def _tracked_files(root):
    """Files git knows about, so an untracked scratch file cannot fail a gate.

    Falls back to walking the tree where git cannot answer. Returning an empty
    list there would make every file-scanning gate pass by finding nothing,
    which is the failure mode a gate must never have."""
    out = subprocess.run(["git", "ls-files"], cwd=root, capture_output=True, text=True)
    if out.returncode == 0 and out.stdout.strip():
        return [p for p in out.stdout.splitlines() if p]
    walked = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", "node_modules"}]
        for name in filenames:
            walked.append(os.path.relpath(os.path.join(dirpath, name), root).replace("\\", "/"))
    return sorted(walked)


def _skill_files(root):
    base = os.path.join(root, PLUGINS)
    if not os.path.isdir(base):
        return []
    found = []
    for plugin in sorted(os.listdir(base)):
        skills = os.path.join(base, plugin, "skills")
        if not os.path.isdir(skills):
            continue
        for skill in sorted(os.listdir(skills)):
            p = os.path.join(skills, skill, "SKILL.md")
            if os.path.isfile(p):
                found.append(p)
    return found


def _agent_files(root):
    base = os.path.join(root, PLUGINS)
    if not os.path.isdir(base):
        return []
    found = []
    for plugin in sorted(os.listdir(base)):
        agents = os.path.join(base, plugin, "agents")
        if not os.path.isdir(agents):
            continue
        for name in sorted(os.listdir(agents)):
            if name.endswith(".md"):
                found.append(os.path.join(agents, name))
    return found


def parse_frontmatter(text):
    """Frontmatter keys as a dict, or None when the block is absent or unterminated.

    Hand-rolled because PyYAML is not in the standard library and this file
    refuses a dependency. Values may be folded over continuation lines, which
    is how every description in this repo is written.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---", 4)
    if end == -1:
        return None
    block = text[4:end]
    keys, current = {}, None
    for line in block.split("\n"):
        m = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):(.*)$", line)
        if m:
            current = m.group(1)
            keys[current] = m.group(2).strip()
        elif current is not None and line.strip():
            keys[current] += " " + line.strip()
    return keys


def normalise(value):
    return re.sub(r"\s+", " ", value).strip()


# ----- gates ------------------------------------------------------------------

def check_json(root):
    """Every manifest and eval set parses. A malformed one fails silently at
    install time, and a malformed step registry silently resurrects a deleted step."""
    failures = []
    for rel in _tracked_files(root):
        if not rel.endswith(".json"):
            continue
        path = os.path.join(root, rel)
        try:
            json.loads(_read(path))
        except (ValueError, OSError) as exc:
            failures.append(f"{rel}: does not parse ({exc})")
    return failures


def check_frontmatter(root):
    """Every skill declares name and description, and the name matches its directory.

    A skill whose name disagrees with its directory is invoked by a slug nobody
    can predict from the tree."""
    failures = []
    for path in _skill_files(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        keys = parse_frontmatter(_read(path))
        if keys is None:
            failures.append(f"{rel}: frontmatter block missing or unterminated")
            continue
        for required in ("name", "description"):
            if not keys.get(required):
                failures.append(f"{rel}: frontmatter has no {required}")
        expected = os.path.basename(os.path.dirname(path))
        if keys.get("name") and keys["name"] != expected:
            failures.append(f"{rel}: name '{keys['name']}' does not match directory '{expected}'")
    for path in _agent_files(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        keys = parse_frontmatter(_read(path))
        if keys is None:
            failures.append(f"{rel}: frontmatter block missing or unterminated")
        elif not keys.get("description"):
            failures.append(f"{rel}: frontmatter has no description")
    return failures


def check_descriptions(root):
    """Descriptions stay under the Agent Skills specification's character limit.

    Over it, the reference validator rejects the skill outright and a harness may
    instead truncate, which silently eats the trailing 'Do NOT trigger for' routing."""
    failures = []
    for path in _skill_files(root) + _agent_files(root):
        rel = os.path.relpath(path, root).replace("\\", "/")
        keys = parse_frontmatter(_read(path))
        if not keys or not keys.get("description"):
            continue
        n = len(normalise(keys["description"]))
        if n > DESCRIPTION_MAX:
            failures.append(f"{rel}: description is {n} characters, over the {DESCRIPTION_MAX} limit")
    return failures


def plugin_versions(root):
    base = os.path.join(root, PLUGINS)
    versions = {}
    if not os.path.isdir(base):
        return versions
    for plugin in sorted(os.listdir(base)):
        manifest = os.path.join(base, plugin, ".claude-plugin", "plugin.json")
        if os.path.isfile(manifest):
            try:
                versions[plugin] = json.loads(_read(manifest)).get("version")
            except ValueError:
                versions[plugin] = None
    return versions


def check_version_bumps(root, changed=None, published=None):
    """A changed plugin must carry a version its published copy does not.

    The install cache is keyed by version, so a changed plugin at an unchanged
    version reaches nobody while the push still looks successful. `changed` and
    `published` are injectable so this is testable without a remote."""
    local = plugin_versions(root)
    if changed is None or published is None:
        changed, published = _git_change_facts(root, local)
        if changed is None:
            return []
    failures = []
    for plugin, version in sorted(local.items()):
        if changed.get(plugin) and version == published.get(plugin):
            failures.append(
                f"{plugin}: changed against the published tree but still at version {version}")
    return failures


def check_leaks(root):
    """Nothing reaching this public remote carries internal detail.

    Two shapes are unambiguous and generic enough to gate on: a host outside the
    allowlist, and a ticket-shaped token whose prefix is not a known placeholder.
    An address is allowed only in the noreply form git itself uses."""
    failures = []
    for rel in _tracked_files(root):
        if os.path.splitext(rel)[1] not in TEXT_SUFFIXES:
            continue
        path = os.path.join(root, rel)
        try:
            text = _read(path)
        except (OSError, UnicodeDecodeError):
            continue
        for host in set(HOST_RE.findall(text)):
            if host in ALLOWED_HOSTS or PLACEHOLDER_HOST.match(host):
                continue
            if True:
                failures.append(f"{rel}: references host '{host}', which is not on the allowlist")
        for prefix, digits in set(TICKET_RE.findall(text)):
            if prefix.lower() not in ALLOWED_TICKET_PREFIXES:
                failures.append(f"{rel}: carries ticket-shaped token '{prefix}-{digits}'")
        for address in set(EMAIL_RE.findall(text)):
            if address.startswith("git@") or "noreply" in address:
                continue
            if True:
                failures.append(f"{rel}: carries the address '{address}'")
    return failures


# ----- git facts for the version gate -----------------------------------------

def _git_change_facts(root, local):
    """Which plugins changed against the published branch, and its versions.

    Returns (None, None) when there is no published branch to compare against,
    so a fresh clone or a detached CI checkout skips the gate rather than
    failing it. Runs against HEAD, never the working tree: git diff cannot see
    an untracked file, so a plugin whose only change is a new file would report
    unchanged and the gate would pass the exact case it exists to catch."""
    # overridable because this repo publishes by direct push, where origin/main
    # is the commit being pushed and the comparison would be vacuous. a pre-push
    # hook and a push-triggered workflow both point this at the previous commit,
    # which is the state consumers actually have.
    # origin/main is right for a local run and for a pull request, whose base is
    # main. it is wrong only on a push to main, where it already points at the
    # commit being pushed — the workflow overrides it there with the push's
    # own before-SHA.
    ref = os.environ.get("ITPR_PUBLISHED_REF") or "origin/main"
    probe = subprocess.run(["git", "rev-parse", "--verify", ref],
                           cwd=root, capture_output=True, text=True)
    if probe.returncode != 0:
        NOTES.append(f"versions: skipped — the published ref {ref!r} does not resolve here")
        return None, None
    changed, published = {}, {}
    for plugin in local:
        diff = subprocess.run(
            ["git", "diff", "--name-only", ref, "HEAD", "--", f"{PLUGINS}/{plugin}"],
            cwd=root, capture_output=True, text=True)
        changed[plugin] = bool(diff.stdout.strip())
        show = subprocess.run(
            ["git", "show", f"{ref}:{PLUGINS}/{plugin}/.claude-plugin/plugin.json"],
            cwd=root, capture_output=True, text=True)
        if show.returncode == 0:
            try:
                published[plugin] = json.loads(show.stdout).get("version")
            except ValueError:
                published[plugin] = None
    return changed, published


GATES = {
    "json": check_json,
    "frontmatter": check_frontmatter,
    "descriptions": check_descriptions,
    "versions": check_version_bumps,
    "leaks": check_leaks,
}


def run(root, names=None):
    NOTES.clear()
    results = {}
    for name in (names or GATES):
        results[name] = GATES[name](root)
    return results


def main(argv):
    root = os.path.abspath(argv[1]) if len(argv) > 1 else os.getcwd()
    results = run(root)
    total = 0
    for name in GATES:
        failures = results[name]
        total += len(failures)
        mark = "FAIL" if failures else "ok  "
        print(f"[{mark}] {name}")
        for failure in failures:
            print(f"         {failure}")
    for note in NOTES:
        print(f"         {note}")
    print()
    print(f"{total} failure(s) across {len(GATES)} gates"
          + (f", {len(NOTES)} skipped" if NOTES else ""))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
