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

import contextlib
import io
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
                  plugin_version="1.0.0",
                  manifest_json=None, frontmatter=None, extra_doc=None, files=None):
    """A minimal but valid plugin repository, with one seam per defect to plant."""
    for rel, text in (files or {}).items():
        write(os.path.join(root, rel), text)
    plugin = "demo-plugin"
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


def captured(fn, *args):
    """Run fn and return (its result, everything it printed)."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        result = fn(*args)
    return result, out.getvalue()


def restore_env(name, saved):
    # restoring the prior value rather than deleting it is defensive,
    # so the environment is left as the caller left it.
    if saved is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = saved


# a root README with one of everything the translation gate compares,
# and its translation built from parts so each case can break exactly one of them.
README_SOURCE = (
    "# Demo\n\n" + check.SWITCHER + "\n\n"
    "Read [the guide](docs/guide.md), then [install](#install).\n\n"
    "## Install\n\n```\n/plugin install demo@market\n```\n\n"
    "## Notes\n\n| a | b |\n|---|---|\n| 1 | 2 |\n"
)
TRANSLATED = {
    "switcher": check.SWITCHER,
    "links": "閱讀 [指南](docs/guide.md)，然後 [安裝](#install)。",
    "install": '<a id="install"></a>\n## 安裝',
    "code": "```\n/plugin install demo@market\n```",
    "notes": "## 備註",
    "table": "| a | b |\n|---|---|\n| 1 | 2 |",
}


def translation(source=README_SOURCE, **override):
    parts = {**TRANSLATED, **override}
    mark = "<!-- translated from README.md, source sha256 %s; see CLAUDE.md -->" % check.source_digest(source)
    return "\n\n".join([mark + "\n# Demo", parts["switcher"], parts["links"], parts["install"],
                        parts["code"], parts["notes"], parts["table"]]) + "\n"


def translated_repo(source=README_SOURCE, zh_tw=None, zh_cn=None):
    files = {"README.md": source, "README.zh-TW.md": zh_tw if zh_tw is not None else translation(source)}
    if zh_cn is not False:
        files["README.zh-CN.md"] = zh_cn if zh_cn is not None else translation(source)
    return {"files": files}


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

        # each translation defect below breaks one thing the gate compares, and only that one,
        # so deleting any single comparison from the gate leaves its case unreported.
        case(tmp, "translations-current", None, **translated_repo())
        # a Windows checkout turns the README's line endings into CRLF while CI reads LF,
        # and both must agree that a translation made from either is current
        crlf = translated_repo()
        crlf["files"]["README.md"] = README_SOURCE.replace("\n", "\r\n")
        case(tmp, "translations-current-on-crlf-checkout", None, **crlf)
        case(tmp, "translation-stale", "translations",
             **translated_repo(zh_tw=translation(source=README_SOURCE + "\nA new paragraph.\n")))
        case(tmp, "translation-missing", "translations", **translated_repo(zh_cn=False))
        case(tmp, "translation-code-changed", "translations",
             **translated_repo(zh_tw=translation(code="```\n/plugin install 示範@market\n```")))
        case(tmp, "translation-link-dropped", "translations",
             **translated_repo(zh_tw=translation(links="閱讀指南，然後 [安裝](#install)。")))
        case(tmp, "translation-heading-dropped", "translations",
             **translated_repo(zh_tw=translation(notes="備註")))
        case(tmp, "translation-table-row-dropped", "translations",
             **translated_repo(zh_tw=translation(table="| a | b |\n|---|---|")))
        case(tmp, "translation-anchor-broken", "translations",
             **translated_repo(zh_tw=translation(install="## 安裝")))
        # the same three links in another order: only the switcher comparison can see it
        case(tmp, "translation-switcher-reordered", "translations",
             **translated_repo(zh_tw=translation(
                 switcher="[繁體中文](README.zh-TW.md) | [English](README.md) | [简体中文](README.zh-CN.md)")))
        # the source's own broken anchor, with translations that carry a matching explicit one
        broken_source = README_SOURCE + "\nSee [later](#later).\n"
        later = translation(source=broken_source, table="| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                            '<a id="later"></a>見 [稍後](#later)。')
        case(tmp, "readme-anchor-broken", "translations",
             **translated_repo(source=broken_source, zh_tw=later, zh_cn=later))

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

        print("\nRelease notice (says what a push releases, never fails one):")
        notice_root = build_fixture(os.path.join(tmp, "notice"))
        listed = check.release_notice(notice_root, published={"demo-plugin": "0.9.0"})
        ok("a changed version is listed as published -> local",
           listed == ["demo-plugin 0.9.0 -> 1.0.0"], f"got {listed}")
        # the case that goes red if the comparison is inverted to ==.
        same = check.release_notice(notice_root, published={"demo-plugin": "1.0.0"})
        ok("a plugin at its published version is not listed", same == [], f"got {same}")
        absent = check.release_notice(notice_root, published={"other-plugin": "1.0.0"})
        ok("a plugin missing from the published copy reads 'unpublished'",
           absent == ["demo-plugin unpublished -> 1.0.0"], f"got {absent}")

        many_root = build_fixture(os.path.join(tmp, "notice-many"))
        for name, version in (("zeta-plugin", "2.0.0"), ("alpha-plugin", "3.1.0"),
                              ("mid-plugin", "1.2.0")):
            write(os.path.join(many_root, "plugins", name, ".claude-plugin", "plugin.json"),
                  '{"name": "%s", "version": "%s"}' % (name, version))
        many = check.release_notice(many_root, published={
            "demo-plugin": "0.9.0", "mid-plugin": "1.2.0", "zeta-plugin": "1.9.0"})
        ok("several changed plugins come out sorted by name, the unchanged one omitted",
           many == ["alpha-plugin unpublished -> 3.1.0",
                    "demo-plugin 0.9.0 -> 1.0.0",
                    "zeta-plugin 1.9.0 -> 2.0.0"], f"got {many}")

        # an empty dict is an injected answer meaning nothing is published yet,
        # which is not the same as having no published ref to ask at all.
        empty = check.release_notice(notice_root, published={})
        ok("an empty published copy lists every plugin as unpublished",
           empty == ["demo-plugin unpublished -> 1.0.0"], f"got {empty}")

        notice_git = build_fixture(os.path.join(tmp, "notice-git"))
        quiet_git = build_fixture(os.path.join(tmp, "notice-quiet"))
        if init_git_history(notice_git) and init_git_history(quiet_git):
            bump(notice_git, version="1.1.0")
            bump(quiet_git, version=None)
            through_git = check.release_notice(notice_git)
            ok("real history: a bumped version is listed",
               through_git == ["demo-plugin 1.0.0 -> 1.1.0"], f"got {through_git}")

            saved = os.environ.get("ITPR_PUBLISHED_REF")
            os.environ["ITPR_PUBLISHED_REF"] = "refs/heads/deliberately-absent"
            try:
                unresolvable = check.release_notice(notice_git)
            finally:
                restore_env("ITPR_PUBLISHED_REF", saved)
            # the same fixture lists a line through a resolvable ref just above,
            # so an empty answer here can only come from the unresolvable ref.
            ok("an unresolvable published ref lists nothing, unlike an empty published copy",
               unresolvable == [], f"got {unresolvable}")

            rc, printed = captured(check.print_release_notice, quiet_git)
            ok("print_release_notice is silent when no version moved", printed == "",
               f"printed {printed!r}")
            ok("print_release_notice returns 0 when silent", rc == 0, f"returned {rc}")
            rc, printed = captured(check.print_release_notice, notice_git)
            block = printed.lstrip("\n").splitlines()
            ok("print_release_notice opens with the release header, then the line",
               block[:2] == ["release: this push publishes",
                             "         demo-plugin 1.0.0 -> 1.1.0"], f"printed {printed!r}")
            ok("print_release_notice returns 0 when it prints", rc == 0, f"returned {rc}")
        else:
            ok("real history: git unavailable, the notice lists nothing rather than failing",
               check.release_notice(notice_git) == [])

        print("\nmain --release-notice runs only the notice:")
        # a fixture whose gates fail, so falling through to them would return 1,
        # and run() is recorded as a second witness in case a gate stops failing.
        main_root = build_fixture(os.path.join(tmp, "notice-main"))
        has_git = init_git_history(main_root)
        if has_git:
            bump(main_root, version="1.1.0")
        write(os.path.join(main_root, "plugins", "demo-plugin", "skills", "demo-skill", "SKILL.md"),
              "---\nname: not-the-directory\ndescription: A demo skill.\n---\n\n# Demo\n")
        ok("precondition: the gates fail on this fixture",
           "frontmatter" in gates_reporting(main_root))

        real_run = check.run
        run_calls = []

        def recording_run(*args, **kwargs):
            run_calls.append(args)
            return real_run(*args, **kwargs)

        prog = "pre_publish_check.py"
        invocations = {
            "flag before the root": [prog, "--release-notice", main_root],
            "flag after the root": [prog, main_root, "--release-notice"],
            "no root, from the working directory": [prog, "--release-notice"],
        }
        cwd = os.getcwd()
        check.run = recording_run
        try:
            for label, argv in invocations.items():
                run_calls.clear()
                if len(argv) == 2:
                    os.chdir(main_root)
                try:
                    rc, printed = captured(check.main, argv)
                finally:
                    os.chdir(cwd)
                ok(f"{label}: returns 0", rc == 0, f"returned {rc}")
                ok(f"{label}: never runs the gates", run_calls == [] and "gates" not in printed,
                   f"run called {len(run_calls)} time(s)")
                if has_git:
                    # proves the root resolved to the fixture rather than to the flag.
                    ok(f"{label}: prints the fixture's release line",
                       "demo-plugin 1.0.0 -> 1.1.0" in printed, f"printed {printed!r}")
        finally:
            check.run = real_run

        print("\nGate coverage:")
        covered = {"json", "frontmatter", "descriptions", "leaks", "versions", "translations"}
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
