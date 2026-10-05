# Roadmap task

A roadmap task in `.seed-engine/roadmap.yml` is a **planned intent**: what the
task delivers and why, grounded in the repository. The engine's
plan → generate → resolve pipeline later expands it into a GitHub issue.

> **A roadmap task is not an issue.** An issue is implementation-ready: Goal /
> Scope / Implementation Notes / an Acceptance-Criteria checklist, built now. A
> roadmap task is prose the generator turns into an issue later. Never write
> those sections or checklists into a task `description`.

## Where it goes

Append new tasks to the `items:` list of the version whose `id` equals the
file's `current_version` — or, for a fix to a maintenance line, of a version
listed in `maintenance_versions`. The generator schedules only those versions:
a task anywhere else is never built, and the validator rejects it. Read the file first: mirror the siblings' id style,
check that the id is unused across **all** versions, and look at how completed
tasks of the same shape were tagged.

## Fields you write

| field | required | meaning |
|---|---|---|
| `id` | yes | Lowercase slug, hyphen/dot separated (`fleet-wide-vehicle-list`), unique across all versions, at most 100 characters. |
| `description` | yes | Prose intent in Markdown: what and why, citing the repository paths you read, at most 16,384 characters. Not an issue body. |
| `priority` | yes | `low` · `medium` · `high`. |
| `status` | yes | Always `planned` on a new task. Every other status is written by the engine. |
| `dependencies` | — | Roadmap ids this task must wait for — existing items or tasks added in the same change. The generator reads **only** this field: a dependency stated in prose is invisible and mis-schedules the work. |
| `parent_id` | — | An existing or sibling id when this task is a follow-up or subtask of another. |
| `scheduling` | — | `pinned` or `parked`, or absent. See below. |
| `tech_skills` | — | Ids from `references/tech-skills.json`. See below. |
| `docs` | — | Repository paths of relevant design documents. |
| `manual_blockers` | — | Human prerequisites as `{ id: BLK-…, title, kind, doc }` (plus `recipient` for an `upstream_request`); author the matching registry row and guide section in the same commit. |
| `tags` | — | Written only by `roadmap-tag.py`. See Provenance. |

Quote any value that contains ` #` or `: ` (`'…'` or `"…"`): unquoted, YAML
reads ` #` as a comment and silently drops the rest (`title: … (issue #12)` is
stored as `… (issue`).

**Engine-owned — never write them:** `status` (beyond `planned` on a new task), `created_by`, `created_at`, `triaged`, `sprint_ref`, `issue_ref`, `planned_at`, `completed_at`, `deferred_from`, `source_repo`. A task another
repository handed over carries `deferred_from` / `source_repo`; preserve those
exactly as read.

**Choosing `tech_skills`.** **Default to `[]`**, but tag **every** clear match — the field is a list, and each id stages a skill the resolver otherwise works without; "the description already implies that work" is not a reason to omit its skill. **Check the roadmap's precedent first**: how completed tasks of the same shape are tagged is the strongest signal (e.g. UI tasks whose verification bar is browser-driven pair `frontend-design` with `playwright-cli` when the repo has a Playwright harness). **Never** invent ids from the repo's org-chart roles or `.claude/skills/` dirs (e.g. `backend-platform`, `web-frontend`): those are role skills, silently invalid as `tech_skills`.

## Editing an existing task

Only while its `status` is `planned`: once it reaches `sprint_planned` an issue
is frozen against it — file a follow-up issue instead. Change only the fields
that alter what the pipeline builds (scope, a missing structured dependency,
priority, scheduling); never reword for style, never touch engine-owned fields
or tags, and never delete a task.

## Settling a task

A task whose work already exists, or whose plan no longer applies, while the
roadmap still shows it open, is settled: `revise_roadmap` → `settle`, `done`
or `obsolete`. Verify first: find its issues, their pull requests and the
delivering commit; confirm in this checkout that the behaviour exists or the
plan was replaced (a resolver's "already implemented" is evidence, not
proof); and confirm nothing is running on it —
unfinished work is resumed or steered, not settled. The evidence names the
delivering commit or the superseding decision. `obsolete` does not satisfy
dependencies, so `patch` its dependents in the same call; set
`verified_landing: true` only on the user's word. Close a still-open issue with
`gh issue close` and a comment: `--reason completed` lets what depends on it
proceed, `--reason "not planned"` keeps it waiting.

## Scheduling

`scheduling: pinned` makes the next backlog-generation run prioritise the task;
`scheduling: parked` keeps it on the roadmap but the generator skips it until
it is unparked. Absent is the normal state. To clear it, remove the key — an
explicit `null` is malformed. Pin all tasks of a time-sensitive effort; park
when the user wants it recorded but not started. Changing only `scheduling` is
allowed at any status.

### `scheduling` replaced the retired `pinned` flag

The roadmap used to carry a top-level boolean `pinned`. It is **retired**: the
engine replaced it with the `scheduling` axis above (plus `tags`), and it stops
reading the legacy key entirely after **2026-11-15**. Two consequences you must
respect:

- **Never author the retired `pinned` key anywhere** — not on an `add`, not in a
  `patch` `set`. The contract rejects it, and an item that ends up carrying the
  legacy flag beside `scheduling: parked` is a refused conflict upstream, which
  fails the repository's **whole** next generation run — not just that item.
- If you *read* the legacy flag on an old item, treat it as pinned for reasoning
  purposes and say so in prose; migrating those values is the engine's own
  maintenance job, not something to propose as a changeset.

Issues have their own, separate scheduling labels (`se:pinned` /
`se:parked`); if the work already has an issue, it is that plane,
not the roadmap.

## Provenance

Every task you add carries the tag `user-generated`, and — when you are
connected to AgentLoom — `requested-by:<your AgentLoom user uuid>`.
Run `python3 $KIT/scripts/roadmap-tag.py <new-id> …` after adding the tasks —
connected, add `--context <saved get_authoring_context result>`, which stamps
your user id; it writes the tags exactly as the engine's own
`roadmap tag` command would. Offline, the commit author attributes the task.

- **A tag is never an email address**, and never any other personal detail.
  Tags live in `.seed-engine/roadmap.yml`, which is committed to the customer's
  git history and readable by anyone with repo access — an email there is
  permanent customer PII. The id is opaque; the dashboard resolves it to a
  display name at render time.

The tags also let an operator generate a backlog from agent-authored work only:
New run → Generate backlog → tag scope `user-generated`.

## Example

```yaml
      - id: fleet-csv-export
        description: >-
          Add a CSV export to the fleet list so operators can reconcile vehicles
          offline. The list is rendered from `dashboard/app/fleet/list.tsx` and
          already holds the filtered rows, so the export reuses them.
        priority: medium
        status: planned
        dependencies: [fleet-list]
        tech_skills: [frontend-design]
        tags:
          - user-generated
```

---

*Generated from AgentLoom's authoring rules `6d0c4044f0e2`.*
