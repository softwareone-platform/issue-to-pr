# PR description diagram — drawing guidance

Disclosed reference for `open-pr` (Step 3, standard-PR description, item 4). Read only when you decide to include a diagram in a PR description — it is optional on a standard PR and excluded on a backport. The inline item keeps the decision (when to include, and the core constraints); this file holds the drawing mechanics, the rationale, and an illustrative shape.

When you do include one it must be a real monospace structure diagram — boxes and arrows, or a small tree / table — **never a bulleted list or a paragraph dressed up as a diagram**. Its job is to **visualise and highlight what the PR does** — the context, flow, or overview that lets a reviewer see the shape of the change at a glance — kept high-level, not a redraw of the diff's details. Pick whatever *view* makes the change legible (a process or data flow, a context / component sketch, a state transition, or a before/after when the change genuinely is a swap); there is no required view, so choose the one that communicates *this* PR best rather than defaulting to before/after — but the *output* is always a drawn diagram, not prose.

Prioritise clear visualisation over any fixed layout, and let the presentation be a best-effort, per-PR choice: if a before/after (or any comparison) would cram into a wide, hard-to-align side-by-side block, **split it into separate diagrams**, and likewise split any diagram that grows large or complex into smaller ones, rather than forcing one unreadable block. How each diagram is drawn is your call; a side-by-side block of two columns of text is the one shape to avoid.

**Always wrap the diagram in a triple-backtick fenced code block.** A PR platform renders an unfenced diagram in a proportional font with collapsed whitespace — that is what makes the boxes drift out of alignment; the fence forces a monospace font and preserves the spacing exactly. Two authoring rules keep it aligned and intact end to end: for any non-trivial diagram, generate it with a small throwaway script rather than hand-aligning the borders, so the columns line up before the fence ever has to preserve them; and draw it with **plain ASCII glyphs only** (`+ - | > v`, not the `─ │ ┌ ┐` box-drawing set), so it survives even when the transport downgrades the encoding (the backend adapter documents the platform's encoding traps for the create call in Step 4). Use ASCII, not Mermaid (Azure DevOps does not render Mermaid reliably in PR descriptions).

Illustrative shape (match the view to *your* PR; vertical flow, plain ASCII, inside a fence):

```
+-------------+      +-------------+
|  caller     | ---> |  new guard  |
+-------------+      +------+------+
                            |
                            v
                     +-------------+
                     |  existing   |
                     |  handler    |
                     +-------------+
```
