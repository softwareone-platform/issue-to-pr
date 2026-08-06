---
schema_version: "1.2"
description: Standard procedure for analysing SUT source files before test generation or auditing, including framework source location.
paths: ["{{TEST_GLOB}}"]
---

# SUT Analysis Procedure

When reading a source file (SUT) before generating or auditing tests, perform all of the following checks:

1. **Read the source file** — understand its public/internal methods, dependencies, return types, exception handling, and control flow.
2. **Check framework base class** — if the SUT inherits from a framework base class, read that base class to understand the lifecycle and virtual method call order. Test the overridden methods, not the base class plumbing.
3. **Check the test can reach the SUT at all** — three distinct obstacles, all of which live *outside* the test file, so no amount of sibling reading reveals them. Check each that applies to this language:
   - **Access grant.** Where the language enforces assembly-, module-, or package-level access control, a non-public SUT needs an explicit grant declared in the **source** project — e.g. .NET's `[InternalsVisibleTo("<test-project>")]` in `AssemblyInfo.cs` or an `<InternalsVisibleTo>` item in the `.csproj`; the equivalent in other ecosystems is a module export, a `friend` declaration, or placing the test in the same package. If the grant is missing, say so in the result and let the caller decide. **Never widen the SUT's visibility to suit a test** — that is a source change, and the fix rules forbid it.
   - **Import reachability.** Where visibility is convention rather than enforcement (Python's leading underscore, for instance), confirm the symbol is actually importable from where the test will sit — the package's `__init__.py` (or equivalent barrel/index) may not re-export it.
   - **Runner collection.** Confirm the test runner is even configured to collect tests for this area — an `--ignore` / `testpaths` entry in `pytest.ini` or `pyproject.toml`, an excluded path in the test project file, a workspace filter. A SUT sitting under an ignored path is often *deliberately* untested (ops-only scripts, generated code); flag it rather than adding a test that will never run.
4. **Note recent changes** — look for signs of recent modifications: new patterns, renamed parameters, added validation, changed business rules. This context helps identify outdated tests during audits and informs test generation.
5. **Check for stale test dependencies** — when existing tests use auto-wiring frameworks (e.g., AutoFixture `fixture.Create<SUT>()`, auto-mocking containers), verify that explicitly registered dependencies still match the SUT's actual constructor parameters. Auto-wiring frameworks silently ignore surplus registrations, so a test may pass despite configuring dependencies the SUT no longer accepts. Explicit `Inject()`, `Register()`, or `Customize()` calls whose target type does not appear in the SUT's current constructor are a stale-dependency signal — flag them during audits. Note: a `Freeze<T>()` is not necessarily stale even if the SUT constructor does not directly accept `T` — auto-wiring containers may inject it into a nested dependency, or the test may `Freeze` it to verify mock interactions.

## Framework / External Dependency Source Resolution (CRITICAL)

### Universal prohibition

**NEVER decompile compiled artifacts from the package cache** (e.g., DLLs, JARs, `.whl` binaries). Decompilation output is unreliable and can lead to incorrect tests.

### Known internal packages

{{KNOWN_PACKAGES_TABLE}}
<!-- Bootstrap (shared-tier2 subagent) fills this from the packages Step 1.2.1 detected in THIS repo, as a table with
exactly these columns — Package | Install model | Local source path | Status — followed by the status legend:
  🟩 — path verified to exist at analysis time
  🟨 — path expected but absent on this machine (informational; the resolution flow below handles it)
Record a 🟨 row rather than dropping the package: an expected-but-absent path is exactly what the writer needs to
know. Never infer a path from a name-to-folder naming convention — every path here comes from the install model
Step 1.2.1 identified. If none were detected, keep the header row and add one row reading
"(none detected — add entries here)". -->

### Runtime resolution flow

When you need to read a framework/external type:

1. **Look up the package in the table above.** If it is absent from the table, work out whether a local checkout exists by install model, not by guessing a folder name:
   - **Workspace / solution member** — the package is another project in the same workspace, solution, or monorepo manifest; the manifest gives its path directly.
   - **Link / editable install** — the dependency resolves to a path outside the package cache (a `-e ../repo` line, a `*.pth` entry, a `file:` / `link:` protocol dependency, a path-type project reference). That path is the source.
   - **Vendored** — the package source sits inside this repo under a `vendor/`, `third_party/`, or similar directory.
   - **Registry install** — the package resolves only into the package cache. There is **no** local source: go to step 3 without inventing a path to try.
2. **If the path exists** → read the source directly from there.
3. **If the path does not exist** (not cloned, moved, different machine, etc.):
   - **DO NOT decompile artifacts** from the package cache.
   - Stop and report to the orchestrator — a subagent cannot wait for user input, so "stop" means **return your structured output now**, naming in `issues:`:
     - Which package you need
     - The path you tried, or `registry-only — no local path to try` when step 1 established there is none
   - The orchestrator asks the user:
     - **Option A** — provide the correct local source path
     - **Option B** — proceed without local source, inferring behaviour from:
       - Interface/abstract signatures available via language server/IDE exposure
       - Existing usage patterns in the test codebase (how sibling tests interact with the framework)
       - Public API surface visible in the compiled assembly metadata (types, method signatures — NOT the body)
   - The orchestrator then **re-spawns the agent fresh** with the chosen option in the prompt; the new instance reads from the provided path (A) or proceeds by inference (B). There is no resume of the stopped instance.
