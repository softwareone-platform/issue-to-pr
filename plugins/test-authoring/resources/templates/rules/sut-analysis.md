---
schema_version: "1.2"
description: Standard procedure for analysing SUT source files before test generation or auditing, including framework source location.
paths: ["{{TEST_GLOB}}"]
---

# SUT Analysis Procedure

When reading a source file (SUT) before generating or auditing tests, perform all of the following checks:

1. **Read the source file** — understand its public/internal methods, dependencies, return types, exception handling, and control flow.
2. **Check framework base class** — if the SUT inherits from a framework base class, read that base class to understand the lifecycle and virtual method call order. Test the overridden methods, not the base class plumbing.
3. **Check visibility for tests** — confirm the SUT's visibility lets the test project reach it. Where the language has assembly-, module-, or package-level access control, verify the grant the test project needs actually exists; if it is missing, note that in the result so the caller can inform the user. Never widen the SUT's visibility to suit a test.
4. **Note recent changes** — look for signs of recent modifications: new patterns, renamed parameters, added validation, changed business rules. This context helps identify outdated tests during audits and informs test generation.
5. **Check for stale test dependencies** — when existing tests use auto-wiring frameworks (e.g., AutoFixture `fixture.Create<SUT>()`, auto-mocking containers), verify that explicitly registered dependencies still match the SUT's actual constructor parameters. Auto-wiring frameworks silently ignore surplus registrations, so a test may pass despite configuring dependencies the SUT no longer accepts. Explicit `Inject()`, `Register()`, or `Customize()` calls whose target type does not appear in the SUT's current constructor are a stale-dependency signal — flag them during audits. Note: a `Freeze<T>()` is not necessarily stale even if the SUT constructor does not directly accept `T` — auto-wiring containers may inject it into a nested dependency, or the test may `Freeze` it to verify mock interactions.

## Framework / External Dependency Source Resolution (CRITICAL)

### Universal prohibition

**NEVER decompile compiled artifacts from the package cache** (e.g., DLLs, JARs, `.whl` binaries). Decompilation output is unreliable and can lead to incorrect tests.

### Runtime resolution flow

When you need to read a framework/external type:

1. **Check whether a local checkout exists** at the path this repo's own documented convention implies. Do not assume one: many internal packages are consumed from a private feed with no local source at all, so treat "no convention documented" as the normal case and go straight to step 3.
2. **If the path exists** → read the source directly from there.
3. **If the path does not exist** (not cloned, moved, different machine, etc.):
   - **DO NOT decompile artifacts** from the package cache.
   - Stop and report to the orchestrator — a subagent cannot wait for user input, so "stop" means **return your structured output now**, naming in `issues:`:
     - Which package you need
     - The path you tried
   - The orchestrator asks the user:
     - **Option A** — provide the correct local source path
     - **Option B** — proceed without local source, inferring behaviour from:
       - Interface/abstract signatures available via language server/IDE exposure
       - Existing usage patterns in the test codebase (how sibling tests interact with the framework)
       - Public API surface visible in the compiled assembly metadata (types, method signatures — NOT the body)
   - The orchestrator then **re-spawns the agent fresh** with the chosen option in the prompt; the new instance reads from the provided path (A) or proceeds by inference (B). There is no resume of the stopped instance.
