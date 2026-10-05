# Issue body

An AgentLoom issue is implementation-ready: a resolver run acts on it directly,
with no sprint and no roadmap linkage. Write it as a strong human contributor
would — thorough, detail-rich, and self-contained enough that a future agent can
act on it without rediscovering, re-reasoning, or hitting design gaps.

## Required sections (in this order)

1. A one-paragraph preamble stating what the issue delivers and why it matters now.
2. `## Goal`
3. `## Background`
4. `## Scope`
5. `## Implementation Notes`
6. `## Acceptance Criteria`

## Optional sections (when they materially help)

- `## Risks`
- `## Open Questions`
- `## Out of Scope`
- `## Manual Verification` — checks that genuinely need an operator, a deployed
  environment or more than one push; never acceptance criteria.

A `## References` section is welcome only when it points at real repository
documents the resolver should read, as relative Markdown links. Each is loaded
in full into the resolver's context: link only the few design documents the
change depends on — never source files, never a path containing `)`.
`## Tech Skills` is described below.

## Content guidance

- **Goal** — what the change delivers and why now.
- **Background** — enough context for a resolver to act without re-reading the
  whole codebase (cite the files/areas you found while investigating).
- **Scope** — the intended execution boundary; what's in and what's out.
- **Implementation Notes** — likely technical approach, constraints, sequencing,
  integration concerns. For a bug, include the root cause and the file:line you
  located.
- **Acceptance Criteria** — a testable/reviewable checklist, every item
  satisfiable by **one resolver round**: one commit and one push, judged on the
  final head, without an operator act, a deployed environment or a multi-push
  CI sequence. Write a proof that the change can fail as a test, or give an
  alternative the resolver can meet ("or an equivalent documented check"); a
  check that genuinely needs an operator goes in `## Manual Verification`.
- Never instruct the resolver to hand-author a `BLK-*` guide anchor, add a
  blocker-registry row, or otherwise edit blocker planes as an acceptance
  criterion. Planning blockers belong in roadmap `manual_blockers`; a resolver
  reports newly discovered blockers through its typed episode/deferral output,
  and Seed Engine stamps anchors itself.
- Never write scope or acceptance criteria that require editing a **connected
  repository** — a peer declared under `reference_trees.peers` or a submodule.
  Those trees are read-only to the resolver; it hands such
  work off as a targeted deferred-work record instead. Name the peer
  dependency in **Scope** or **Implementation Notes** as `<owner/repo>: <what
  must change>` so the resolver knows to hand it off, and keep this issue's
  acceptance criteria satisfiable inside this repository (an inert-safe change
  — deprecated alias kept, new path dormant until the peer adopts it).

## Quality bar

- Detailed and useful to both humans and a future Claude Code resolver run.
- Explicit about the goal, constraints, likely implementation space, and
  acceptance criteria.
- Names the alternatives you rejected and why, so the resolver does not
  reopen them.
- Free of meta narration about your own process.
- Implementation-ready, not a thin summary — as if authored by a strong human
  contributor.

## Grounding and evidence

- Ground every claim in this checkout. Cite the verified call chain as
  `path/to/file.ext:line`; the validator warns when a cited path does not exist.
- **Forensics first, then the fix.** Background states what was observed and
  where, with the evidence itself — quoted log lines, the error, what the run
  or screen showed — since the resolver may not reach anything outside this
  repository; Implementation Notes carry the proposed change concretely — a
  draft diff where feasible — plus the callers in scope, sequencing and risks.
- For a `bugfix` or `security` issue, Background opens with a
  `### Observed failure` subsection (failing test, log line, screenshot, the
  exact reproduction) and the root cause names the code at fault and the
  adjacent correct-by-design code.
- Acceptance Criteria are testable `- [ ] …` items.
- No meta narration ("I investigated…", "let me…") and no deferred
  investigation ("investigate whether…"): do the investigation before filing.

The validator enforces the structural half: required sections in order, a
preamble, and a content floor per section —

- `## Goal` — at least 40 characters
- `## Background` — at least 150 characters
- `## Scope` — at least 60 characters
- `## Implementation Notes` — at least 200 characters
- `## Acceptance Criteria` — at least 40 characters

## Tech Skills

When the work clearly needs one of the engine's pool skills, end the body with:

```markdown
## Tech Skills

- `playwright-cli`
```

One backticked pool id per line, ids from `references/tech-skills.json` only.
Omit the section when none applies. Org-chart role keys are never tech skills;
roles go on labels (`references/labels.md`).

## Markers

Hidden HTML comments the engine and AgentLoom read. Write exactly these:

- **Origin (required).** The last line of the body:
  `<!-- agentloom-origin: ide -->` — or, when you are connected to AgentLoom, the
  `provenance.issue_origin_marker` line from `get_authoring_context`
  (`<!-- agentloom-origin: ide; requested-by: <uuid> -->` with your user id). Never an email or login.
- **Execution order (only when needed).** The first line of the body:
  `<!-- SE_DEPENDS_ON_ISSUES: 412, 415 -->`. The backlog then holds this issue
  until every listed issue is closed as completed. Numbers may be bare or
  `#`-prefixed. One marker at most — the engine keeps only the last one.

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

Every other engine marker (`<!-- SE_… -->`, `<!-- SEED_ENGINE_… -->`) is written
by the engine; never write one.

## The draft file

`validate.py issue` reads a Markdown file whose front matter carries the title
and the exact label set, followed by the exact body:

```markdown
---
title: Stop unbounded webhook redelivery
labels:
  - se
  - se:type:bugfix
  - se:priority:high
  - se:resolve-worker:platform
  - agentloom:user-generated
---
Fix the webhook retry loop that re-delivers events forever when the mirror
upsert fails, so one bad payload stops wedging the ingestion queue.

## Goal

…

## Background

### Observed failure

…

## Scope

…

## Implementation Notes

…

## Acceptance Criteria

- [ ] …

<!-- agentloom-origin: ide -->
```

`--emit-body PATH` writes the body alone for `gh issue create --body-file`.

## After filing

The issue body is frozen once a run starts on it. New findings go in a
follow-up issue that references this one by number.

---

*Generated from AgentLoom's authoring rules `6d0c4044f0e2`.*
