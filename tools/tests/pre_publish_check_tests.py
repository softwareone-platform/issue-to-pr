#!/usr/bin/env python3
"""Known-answer cases for tools/pre_publish_check.py, plus the mutation test.

This repo's own rule is that a check which has only ever run against good input
has not been tested, and that deleting any one check must turn the suite red.
Both are enforced here: every gate owns a fixture that plants exactly the defect
it exists to catch, and the suite asserts that **no other gate** reports that
fixture. Sole detection is what makes the mutation test real -- remove a gate and
its fixture becomes invisible, so the suite goes red.

Run: python tools/tests/pre_publish_check_tests.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pre_publish_check as check  # noqa: E402

PASSED = []
FAILED = []


def ok(name, condition, detail=""):
    (PASSED if condition else FAILED).append(name)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {name}{('  -- ' + detail) if detail and not condition else ''}")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def build_fixture(root, *, skill_name="demo-skill", description="A demo skill.",
                  plugin_version="1.0.0", registry_version="1.0.0",
                  manifest_json=None, frontmatter=None, extra_doc=None):
    """A minimal but valid marketplace, with one seam per defect to plant."""
    plugin = "demo-plugin"
    write(os.path.join(root, ".claude-plugin", "marketplace.json"),
          '{"name": "itpr", "plugins": [{"name": "%s", "version": "%s", "source": "./plugins/%s"}]}'
          % (plugin, registry_version, plugin))
    write(os.path.join(root, "plugins", plugin, ".claude-plugin", "plugin.json"),
          manifest_json if manifest_json is not None
          else '{"name": "%s", "version": "%s"}' % (plugin, plugin_version))
    fm = frontmatter if frontmatter is not None else (
        "---\nname: %s\ndescription: %s\n---\n\n# Demo\n\nBody.\n" % (skill_name, description))
    write(os.path.join(root, "plugins", plugin, "skills", "demo-skill", "SKILL.md"), fm)
    if extra_doc:
        write(os.path.join(root, "plugins", plugin, "docs", "note.md"), extra_doc)
    return root


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=selfcheck",
                           "-c", "user.email=selfcheck@noreply.invalid", *args],
                          cwd=root, capture_output=True, text=True)


def init_git_history(root):
    """A repo whose refs/remotes/origin/main points at the initial commit.

    No remote is involved -- the ref is written directly, which is enough for the
    gate's own comparison and keeps the fixture offline. Returns False when git
    cannot run, so the suite degrades instead of failing on a machine without it."""
    if git(root, "init", "-q").returncode != 0:
        return False
    git(root, "add", "-A")
    if git(root, "commit", "-q", "-m", "initial").returncode != 0:
        return False
    sha = git(root, "rev-parse", "HEAD").stdout.strip()
    git(root, "update-ref", "refs/remotes/origin/main", sha)
    return True


def bump(root, version):
    """Change the plugin, optionally bumping its version, and commit."""
    skill = os.path.join(root, "plugins", "demo-plugin", "skills", "demo-skill", "SKILL.md")
    write(skill, open(skill, encoding="utf-8").read() + "\nAnother line.\n")
    if version:
        write(os.path.join(root, "plugins", "demo-plugin", ".claude-plugin", "plugin.json"),
              '{"name": "demo-plugin", "version": "%s"}' % version)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "change")


def gates_reporting(root):
    """Names of the gates that found something, with the version gate given
    explicit inputs so a fixture needs no git remote."""
    results = check.run(root, [n for n in check.GATES if n != "versions"])
    return {name for name, failures in results.items() if failures}


def case(tmp, label, expected_gate, **kwargs):
    root = os.path.join(tmp, label)
    build_fixture(root, **kwargs)
    reporting = gates_reporting(root)
    if expected_gate is None:
        ok(f"{label}: clean fixture is green", reporting == set(), f"reported {sorted(reporting)}")
        return
    ok(f"{label}: '{expected_gate}' catches it", expected_gate in reporting,
       f"reported {sorted(reporting)}")
    others = reporting - {expected_gate}
    ok(f"{label}: no other gate catches it (sole detector)", others == set(),
       f"also reported {sorted(others)}")


def main():
    tmp = tempfile.mkdtemp(prefix="itpr-selfcheck-")
    try:
        print("Known-answer cases (each must make exactly one gate red):")
        case(tmp, "clean", None)

        # pins the placeholder exemptions: prose that writes a bare host or an
        # ssh remote is not a leak, and the real tree contains all three shapes.
        case(tmp, "placeholders-are-not-leaks", None,
             extra_doc="Use `https://host/path`, or `https://org`, "
                       "or clone from git@ssh.dev.azure.com:v3/x/y/z.\n")

        case(tmp, "bad-json", "json",
             manifest_json='{"name": "demo-plugin", "version": "1.0.0",}')

        case(tmp, "name-mismatch", "frontmatter",
             frontmatter="---\nname: not-the-directory\ndescription: A demo skill.\n---\n\n# Demo\n")

        case(tmp, "no-description", "frontmatter",
             frontmatter="---\nname: demo-skill\n---\n\n# Demo\n")

        case(tmp, "long-description", "descriptions",
             description="word " * 250)

        # the leak tokens are assembled at runtime rather than written as literals,
        # because this file is itself scanned by the leaks gate and a literal here
        # would fail the real repo -- which is also a live demonstration that it works.
        case(tmp, "leak-host", "leaks",
             extra_doc="See https://" + "tickets.internal" + ".invalid/board for detail.\n")

        case(tmp, "leak-ticket", "leaks",
             extra_doc="Fixes " + "PROJ" + "-" + "4821" + " in the billing path.\n")

        case(tmp, "manifest-drift", "manifest-sync",
             plugin_version="1.1.0", registry_version="1.0.0")

        print("\nVersion gate (through the registry, against a real git history):")
        # routed through GATES rather than the function, because the first version
        # of this suite called check_version_bumps directly and the mutation test
        # then found that disabling the registered gate left the suite green.
        gate = check.GATES["versions"]
        root = build_fixture(os.path.join(tmp, "versions"))
        stuck = gate(root, changed={"demo-plugin": True}, published={"demo-plugin": "1.0.0"})
        ok("changed plugin at an unchanged version is caught", len(stuck) == 1)
        bumped = gate(root, changed={"demo-plugin": True}, published={"demo-plugin": "0.9.0"})
        ok("changed plugin that was bumped passes", bumped == [])
        untouched = gate(root, changed={"demo-plugin": False}, published={"demo-plugin": "1.0.0"})
        ok("unchanged plugin at the same version passes", untouched == [])

        git_root = build_fixture(os.path.join(tmp, "versions-git"))
        if init_git_history(git_root):
            bump(git_root, version=None)
            ok("real history: changed but unbumped is caught", gate(git_root) != [])
            bump(git_root, version="1.1.0")
            ok("real history: changed and bumped passes", gate(git_root) == [])
        else:
            ok("real history: git unavailable, gate skipped rather than failed",
               gate(git_root) == [])

        print("\nA declined gate must say so (a silent skip reads as a pass):")
        os.environ["ITPR_PUBLISHED_REF"] = "refs/heads/deliberately-absent"
        try:
            check.run(git_root, ["versions"])
            ok("an unresolvable published ref is announced", len(check.NOTES) == 1,
               f"notes were {check.NOTES}")
            ok("the note names the ref it could not resolve",
               any("deliberately-absent" in n for n in check.NOTES))
        finally:
            del os.environ["ITPR_PUBLISHED_REF"]
        check.run(git_root, ["versions"])
        ok("a resolvable ref produces no note", check.NOTES == [], f"notes were {check.NOTES}")

        print("\nGate coverage:")
        covered = {"json", "frontmatter", "descriptions", "leaks", "manifest-sync", "versions"}
        ok("every gate owns at least one known-answer case",
           covered == set(check.GATES), f"uncovered: {sorted(set(check.GATES) - covered)}")

        print("\nReal repository:")
        repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        results = check.run(repo)
        for name, failures in results.items():
            ok(f"repo passes '{name}'", failures == [], "; ".join(failures[:3]))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
