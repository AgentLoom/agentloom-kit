---
name: agentloom
description: File work for AgentLoom correctly from the IDE — resolver-ready GitHub issues, dependency-ordered issue batches, roadmap tasks in .seed-engine/roadmap.yml, and manual-blocker resolutions — checked by a deterministic validator before anything is filed or pushed. Use when the user asks to file, queue, plan or hand work to AgentLoom or Seed-Engine, to put something on the roadmap, to pin or park a roadmap task, to complete a BLK-* blocker, or to check a hand-written issue or roadmap edit before pushing.
compatibility: Needs Python 3.10+ with PyYAML and ruamel.yaml, git, and the GitHub CLI (gh) for filing issues. Works offline with no AgentLoom credentials; the optional AgentLoom MCP server adds the live authoring context and your user id.
metadata:
  built_for_rules_fingerprint: "6d0c4044f0e23d57d9a4bb2f7f0ebaacc8bfdaaeee7486fe5f467589eb9227da"
---

# AgentLoom

AgentLoom runs Seed-Engine on repositories that carry a `.seed-engine/`
directory. It picks up issues labelled `se` and roadmap changes pushed to the
default branch on its own. Your job is to author those artifacts so the engine
can act on them without a repair round: thorough, grounded in this checkout,
and in the exact shape the engine reads. The scripts in `scripts/` check the
shape; you supply the substance.

Setup, once per machine: `python3 -m pip install pyyaml ruamel.yaml`. Below,
`$KIT` is this skill's directory (the one holding this file); run every script
from the repository root.

## Connected or offline

If the AgentLoom MCP server is available to you (the plugin declares it; any
client can add `https://api.agent-loom.com/api/mcp`), start every authoring task with it:

1. `resolve_repo` with this checkout's `owner/name` (or `git remote get-url origin`) — it returns the repository
   id and whether AgentLoom is enabled on it.
2. `get_authoring_context` with that id. Save the result as JSON, e.g.
   `/tmp/agentloom-context.json`.
3. Pass `--context /tmp/agentloom-context.json` to every `validate.py` and
   `roadmap-tag.py` run below. The validator then checks against the
   platform's authoring rules and the repository's live resolver roles, and the tag script
   stamps your user id. Use the context's `provenance.issue_origin_marker` as
   an issue's origin line.

The first tool call opens a browser sign-in; the user approves it once. If the
server is not available, or the user declines, continue offline — every step
below works without it.

## Acting through AgentLoom (connected)

The server can also act for the user, each kind of action behind a permission
they grant by name at sign-in (starting runs, cap resets, steering, answering
blockers, filing, roadmap changes, accepting recommendations). A call that
needs one they have not granted makes the client ask them to sign in again for
it — tell them what it is for.

Every write:

1. Call it with `preview: true` first and show the user what it would do.
2. Then call it for real with a new `request_id` (a UUID you generate). If the
   call errors or the reply is lost, retry with the **same** `request_id` and
   the same arguments: the platform finishes or replays the first attempt
   instead of acting twice. Changed arguments are a new change and need a new
   `request_id`. A retry reports what the first attempt did; if it says the
   run's launch failed, start or resume it again with a new `request_id`.
3. A refusal is the dashboard's own reason for the same click — relay it
   verbatim; do not work around it.

| The user wants | Tool |
|---|---|
| File without `gh` or a checkout | `open_issue`, or `open_issue_batch` for 2–10 linked issues — the platform checks, labels and stamps them; `scheduling: "parked"` files one that must not start yet (`references/labels.md`) |
| "Run it now" | `dispatch_run` on the issue |
| A stopped run going again | `get_run_failure`, then `steer_run` (read `references/steer-guidance.md` first) or `resume_run`; `reset_cap: true` only when the run's cap is exhausted — it is limited per day |
| A roadmap change the platform commits | `revise_roadmap` — its preview is the exact diff; `git pull` after; a task already delivered or no longer wanted is settled, after you verify it (`references/roadmap-task.md`) |
| A manual blocker recorded | `complete_blocker` (instead of `blocker-complete.py`) |
| A resolver's questions answered | `respond_to_blocker` — its preview returns the questions and the revision to answer |
| A recommendation accepted | `get_recommendation`, then `accept_recommendation` |
| An approval decided | `decide_approval` — preview first: approving a merge gate merges its pull request, and merge gates cannot be rejected |

`list_inbox` names, per row, the tool that resolves it (`resolve_with`).

## Decide: now or plan

- **Now → an issue.** One concrete, implementation-ready unit a resolver can
  build today: a bug you diagnosed, a feature whose design is settled. Several
  ready units → **one issue batch**, opened in dependency order.
- **Plan → roadmap tasks.** An effort too large for one issue that decomposes
  into dependency-linked tasks, or work that should be recorded but not built
  yet. The engine's plan → generate pipeline turns roadmap tasks into issues
  later.
- **A roadmap task is not an issue.** It is prose intent: what and why,
  grounded in the code. No Scope / Implementation Notes / Acceptance Criteria
  sections and no checklists — the generator writes those.

Tell the user which one you chose and why before you write anything.

## Before filing: is it already covered?

Search `.seed-engine/roadmap.yml` for the subject, and list open issues:
`gh issue list --label se --state open --limit 200 --json number,title > /tmp/open-issues.json`.
Pass that file to `validate.py issue --existing`. If the work is already
planned or open, report it and stop; never file over it.

## File one issue

1. Investigate first. Read the code, reproduce or locate the failure, and
   verify every `path:line` you will cite.
2. Write a draft file (front matter + the exact body) following
   `references/issue-body.md`. Labels follow `references/labels.md`.
3. `python3 $KIT/scripts/validate.py issue draft.md --existing /tmp/open-issues.json --emit-body draft.body.md`
   (plus `--context …` when connected, here and in every command below)
4. Fix every error. Treat warnings as defects unless the user decides otherwise.
   The body file and the `gh` command are only produced when the run has no
   error at all and no rules mismatch.
5. File with the printed command:
   `gh issue create --title … --body-file draft.body.md --label …`

To have it built right away, the user presses **Start run** on the issue in the
AgentLoom dashboard; otherwise the backlog picks it up — unless you filed it
parked, which `references/labels.md` says when to do.

## File an issue batch

For several ready units with a real execution order. See
`references/issue-batch.md`.

1. One draft per unit in a directory, each with `ref` and `depends_on` in its
   front matter.
2. `python3 $KIT/scripts/validate.py batch drafts/` — validates every item and
   the graph, and prints the opening order.
3. Open in that order. For each ref:
   `python3 $KIT/scripts/validate.py batch drafts/ --open <ref> --numbers <ref>=<number>,… --emit-body <ref>.body.md`
   then the printed `gh issue create`. Record the number it returns and pass
   it in `--numbers` for the items that depend on it. Never open a dependent
   before its dependencies exist.

## Add roadmap tasks

See `references/roadmap-task.md` and, for several linked tasks,
`references/roadmap-batch.md`.

1. `git pull --rebase` and read `.seed-engine/roadmap.yml`: mirror the id
   style, check what exists, and how similar tasks were tagged with
   `tech_skills`.
2. Append the task(s) to the `items:` of the version whose `id` equals
   `current_version` (or of a version listed in `maintenance_versions`, for a
   fix to that line), with `status: planned`. The generator ignores tasks in
   any other version, and the validator rejects them.
3. `python3 $KIT/scripts/roadmap-tag.py <new-id> [<new-id> …]` — stamps the
   provenance tags (with `--context`, your user id too). Never write `tags` by
   hand.
4. `python3 $KIT/scripts/validate.py roadmap`
5. One commit for the whole change; `git pull --rebase`; push to the default
   branch. The push wakes AgentLoom.

**Pin or park an existing task:** set `scheduling: pinned` (the next backlog
generation prioritises it) or `scheduling: parked` (the generator skips it
until unparked); remove the key to clear it. Validate, commit, push. An issue
is pinned or parked with labels instead (`references/labels.md`).

## Complete a manual blocker

See `references/blockers.md`. Find the `BLK-*` entry in
`.seed-engine/blockers-registry.yml`, read the guide section its `file` points
at, do (or walk the user through) the steps, run the section's `Validate:`
check, then:

`python3 $KIT/scripts/blocker-complete.py BLK-007 --status completed --resolution "<what was done and where the values live>"`

Review the diff, commit and push. `BLK-RES-*` blockers belong to a run: they
are answered with `respond_to_blocker` when connected, or in the AgentLoom
dashboard (**Record answers & resume**) — never in the registry.

## Check something written by hand

`validate.py issue <draft>`, `validate.py batch <dir>`, `validate.py roadmap`
or `validate.py blocker <BLK-id>`. Add `--json` for machine-readable findings
(rule, path, message, fix).

## Never

- Apply or remove a label the engine sets (`se:resolve-status:*`, `se:review-*`,
  `se:open-pr`, `se:blocked-manual`, …) or name a reviewer. The engine
  applies them; a hand-applied one makes it skip the issue.
- Write engine markers other than `SE_DEPENDS_ON_ISSUES`, or edit an issue's body or labels
  after a run started on it — file a follow-up issue instead.
- Write roadmap `tags` other than through `roadmap-tag.py`, or put an email or
  login anywhere in the roadmap.
- Edit engine-owned roadmap fields (`status` past `planned`, `created_*`,
  `triaged`, `sprint_ref`, `issue_ref`, done-state fields) or edit a task that
  is no longer `planned`.
- Commit a credential. Name where a secret lives, never its value.

## Exit codes and the platform's rules

This kit was built from AgentLoom's authoring rules `6d0c4044f0e23d57d9a4bb2f7f0ebaacc8bfdaaeee7486fe5f467589eb9227da`
(`scripts/authoring-rules.json`, `rules_fingerprint`). Some checks depend on
the engine the platform runs: the tech-skill pool, the `scheduling` / `tags`
grammar, the label root. Unconfirmed against the platform, those results are
**provisional** and the scripts exit `3`. That is not a pass — say so to the
user. A provisional run with no errors may still be filed; one with any error
may not. Connected, `--context` supplies the platform's `rules_fingerprint`
(a context without one is provisional); offline, pass `--rules-fingerprint <fp>`
when the user knows it. If it differs from this kit's, the kit is out of date
and nothing may be filed until it is updated; give the user the update steps
the validator prints.

`0` pass · `1` errors · `2` usage or environment problem · `3` provisional.

## References

- `references/issue-body.md` — sections, quality bar, evidence, markers, draft format
- `references/issue-batch.md` — refs, dependencies, opening protocol
- `references/roadmap-task.md` — fields, what you may and may not write, scheduling, provenance
- `references/roadmap-batch.md` — decomposing an effort into linked tasks
- `references/labels.md` — the label scheme
- `references/blockers.md` — manual blockers, statuses, resolutions
- `references/steer-guidance.md` — writing guidance for `steer_run`
- `references/tech-skills.json` — the engine's tech-skill pool
