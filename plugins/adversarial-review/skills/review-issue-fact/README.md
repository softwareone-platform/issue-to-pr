# review-issue-fact

Fact-check an issue — a bug report, story, or incident description, given as a Jira link / key or as plain / markdown text — against the codebase that is its ground truth, before any fix is planned. The issue-altitude sibling of `review-plan-risk` and `review-code-risk`: this guards the ISSUE (before planning), one guards the PLAN (before building), one guards the FIX (before review). Its premise is that the issue is *not* a source of truth — it may carry misleading assumptions, a misattributed root cause, or simply wrong information — so it treats the issue as a set of claims under test and the code as the oracle. It extracts the issue's claims and assumptions, verifies each against the code, then independently and bidirectionally falsifies the verdict, and reports `confirmed` / `refuted` / `needs-info` per claim with an overall `HALT` / `PROCEED` / `RESOLVE` recommendation.

This is the **verdict sibling** of the review family, and deliberately lighter than the two fix skills: an issue has nothing to auto-fix — its truth lives in the code, not in text we could rewrite to match it — so this skill produces a verdict, never an edit, and drops the auto-fix, opt-in-batch, and propagate machinery the fix siblings need. Its distinct question is **diagnosis alignment** — do the issue's factual claims hold in this code, or is the bug misdiagnosed before we spend the pipeline fixing it — which generic line-level review (`code-review` / `coderabbit`) and security scanning (`security-review`) do not ask.

## Process flow

```mermaid
flowchart TD
    T(["/adversarial-review:review-issue-fact<br>or trigger phrase"]) --> G{"An issue to fact-check,<br>not a plan / fix / Jira edit?"}
    G -- "no — scope guard" --> STOP(["Stop: wrong skill<br>(review-plan-risk / review-code-risk)"])
    G -- "yes" --> S1["Step 1 — resolve the issue (Jira or text);<br>codebase is the oracle;<br>cross-repo: read on-disk siblings,<br>else needs-info / seam"]
    S1 --> SC["Surface resolved scope<br>(issue, code areas, cross-repo seams)<br>— informational, not a gate (no edits)"]

    subgraph S2["Step 2 — enumerate, then verify (separate passes)"]
        EN["Enumerate the issue's claims<br>and assumptions — no judging"]
        EN --> VC["Verify each against the code:<br>confirmed / refuted / needs-info,<br>cite file:line; rate centrality"]
        VC --> RANK["Internal per-claim verdict table"]
    end
    SC --> EN

    RANK --> VER["Step 3 — fresh adversarial verifier (read-only):<br>refute every confirmed, salvage every refuted,<br>probe every needs-info, challenge centrality both ways,<br>re-walk evidence independently (no circularity)"]
    VER --> RT{"Finding<br>type?"}
    RT -- "objective contradiction" --> COR["main flow corrects verdict once,<br>one fresh re-check, no loop;<br>still wrong → needs-info / disputed"]
    RT -- "centrality challenged" --> CEN["corrected like an objective contradiction,<br>inside the same re-check budget;<br>verifier's rating wins a tie,<br>never sets disputed"]
    RT -- "adversarial judgement" --> DIS["keep verdict value,<br>flag claim disputed"]
    RT -- "none" --> SURV["verdict survives"]

    COR --> TBL
    CEN --> TBL
    DIS --> TBL
    SURV --> TBL["Step 4 — count line + verdict table<br>(load-bearing claims: N, then closed-enum columns)"]
    TBL --> ROLL{"Roll up, first rule that matches<br>(disputed and not-verified both read as needs-info)"}
    ROLL -- "zero load-bearing claims" --> RES
    ROLL -- "any refuted" --> HALT(["overall refuted → recommend HALT"])
    ROLL -- "all confirmed, each survived/corrected" --> PROC(["overall confirmed → recommend PROCEED"])
    ROLL -- "otherwise" --> RES(["overall needs-info → recommend RESOLVE"])
```

Five rules that govern the flow above:

- **The issue is the claim under test; the codebase is the oracle** — the issue is *not* a source of truth, so when the issue and the code disagree on a structural fact, the code wins, and what the code cannot settle is `needs-info`, never a guess.
- **Enumeration is separate from calibration** — the issue's claims and assumptions are listed without judging them; verifying happens only afterward, as its own pass, so the issue's own framing cannot pre-filter which claims get written down (a misframed issue states its most load-bearing claim most confidently).
- **Verdict-only, never rewrite the issue** — the product is a verdict (`confirmed` / `refuted` / `needs-info`) plus evidence; the issue is an external, human-owned artifact, so this skill never edits it and drops the auto-fix / opt-in / propagate machinery its fix siblings carry.
- **The verdict *and its centrality* are independently and bidirectionally falsified** — a fresh adversarial agent that did not reach the verdicts tries to *refute* every confirmed claim and *salvage* every refuted one, probes each `needs-info` for an oracle that was in fact reachable, and challenges the Centrality column in both directions (an `incidental` rating on a claim a fix would plainly depend on, and the reverse) — because centrality decides whether the rollup applies at all, so a wrong rating there is the cheapest route to a wrong recommendation. A challenged rating is corrected like an objective contradiction rather than flagged, and never sets `disputed`. It re-walks evidence from the claim and the code rather than re-reading the cited line (which would be circular). An objective contradiction is corrected once by the main flow then re-checked by one fresh spawn (no loop); a judgement-level dispute keeps the verdict value and is flagged.
- **Honest limits over silent guesses** — `Jira anchor not available`, `seam with <repo> not assessed` (no clone, no decompile), `static-only` for runtime-only claims, and `not-verified` when no fresh agent can be spawned are all voiced in the result, never silent. The overall `HALT` / `PROCEED` / `RESOLVE` recommendation is advisory, not a hard gate. Inside the orchestrator the human is asked at this step on HALT or RESOLVE (default toward stopping) and decides again at the plan-approval gate; standalone it is information, and nothing is gated.

## Relationship to siblings

The three are a graduated set, shipped together in `adversarial-review`, guarding the issue→PR pipeline at rising altitude:

- **`review-issue-fact`** (this skill) runs **first**, at the issue, before anything is planned. It reads the issue against the code, produces a *verdict*, and edits nothing — its oracle is the current code, and a `refuted` diagnosis is what stops the pipeline spending anything on a misdiagnosis — by putting the question to the human at that first step, defaulting toward stopping, not by hard-stopping on its own.
- **`review-plan-risk`** runs **next**, at the plan-approval gate, and edits **design text** (no execution side-effects — `git restore` reverts prose).
- **`review-code-risk`** runs **last**, at the pre-PR gate, and edits **code** — it requires a committed fix as its baseline and runs build and tests as part of verification.

They share one spine — enumeration separated from calibration, an independent adversarial verifier, honest voiced limits — but only the latter two auto-fix their artifact; this one stays a verdict, because an issue's truth is in the code, not in text to rewrite.
