# Issue batch

A batch is several ready units filed together, in dependency order, into one
repository. Use it for N ready units whether or not they are ordered — a batch
in which nothing depends on anything is valid. A single unit is a plain issue.
Work that is not ready to build belongs on the roadmap instead.

## Drafts

One draft file per unit in one directory, each an ordinary issue draft
(`references/issue-body.md`) with two more front-matter keys:

```markdown
---
ref: api-routes
depends_on: [api-schema, 412]
title: Serve fleet exports from the API
labels:
  - se
  - se:type:feature
  - se:priority:medium
  - se:resolve-worker:platform
  - agentloom:user-generated
---
…body…
```

- `ref` — a short slug you invent to name the unit within the batch
  (`api-schema`, `step-1`). Unique. Never an issue number: the batch's numbers
  do not exist yet.
- `depends_on` — what must ship before this unit starts: sibling `ref`s, or the
  real number of an issue that already exists in this repository. `[]` when it
  can start immediately.
- The body must **not** carry the `SE_DEPENDS_ON_ISSUES` marker: it is rendered
  from real numbers when the item is opened.

The graph must be a DAG: no duplicate ref, no unknown ref, no self-edge, no
cycle. Real numbers are leaves.

**Omit the marker unless there is a real ordering constraint** — one issue's work
being a premise for another's, not merely two issues touching the same area. An
unnecessary dependency delays work for no reason; a wrong one stops it
indefinitely. Four rules bound when you may use it:

- **Only reference issues you have actually read in the same repository**, by the
  number you saw. A dependency the engine cannot resolve fails closed: the
  dependent issue is skipped on every selection sweep until an operator edits the
  body by hand. Never guess a number, never infer one from a title, and never
  reference an issue in another repository — the engine resolves numbers inside
  the issue's own repository only. Work that belongs in another repository
  travels as a targeted `DEFERRED_WORK` record the resolver writes, never as an
  issue link.
- **"Closed as completed" is the bar.** An issue closed as not planned — a
  won't-do close, or a duplicate whose work moved elsewhere — never satisfies the
  dependency. When the real predecessor is a superseding issue, point at that one
  instead.
- **A cycle stops every issue in it.** Dependencies must run one way. Before
  adding the marker, check that the issue you are pointing at does not already
  depend, directly or transitively, on this one.

## Opening protocol

1. `python3 $KIT/scripts/validate.py batch drafts/` — fix every error; it
   prints the opening order (dependencies first).
2. For each ref, in that order:

   ```sh
   python3 $KIT/scripts/validate.py batch drafts/ --open api-routes \
     --numbers api-schema=101 --emit-body api-routes.body.md
   ```

   This renders the dependency marker from the numbers you pass, validates the
   rendered issue, writes its body, and prints the `gh issue create` command.
   It refuses to render an item whose dependency has no number yet.
3. Run the printed command, note the new number, and pass it in `--numbers`
   for every later item that depends on it.

If opening stops half-way, the issues already opened stay; resume from the next
ref in the order with the numbers you have.

---

*Generated from AgentLoom's authoring rules for engine pin `2026.10.02-stable`.*
