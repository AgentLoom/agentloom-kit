# Labels

## Labels you set

These tell the engine what to build and when. Set them when you file; you may
change them later.

| label | count | meaning |
|---|---|---|
| `se` | 1 | The engine only selects issues that carry it. |
| `se:type:<type>` | 1 | `security` · `bugfix` · `feature` · `refactor` · `dependency` · `docs` · `chore` · `test` · `other` |
| `se:priority:<priority>` | 1 | `low` · `medium` · `high` |
| `se:resolve-worker:<role>` | 1–2 | Role keys from `.seed-engine/org-chart.yml` (`roles[].key`), primary role first. Keep assignment conservative. |
| `agentloom:user-generated` | 1 | Marks agent-authored work for AgentLoom; outside the engine's label plane. |
| `se:parked` or `se:pinned` | 0–1 | Scheduling — the dashboard's Park and Pin. Parked: the backlog leaves the issue alone until the label is removed (an explicit Start run still runs it). Pinned: the backlog takes it first. |

**When you may change them.** The boundary is the same as for the issue body:

- **An issue you are opening:** set all of them.
- **An existing issue no run has started on:** park or pin it freely. Change
  its type, priority or roles only after deliberate review: they route the
  work, and someone chose them. Tell the user why, and ask first.
- **Once a run has started** (`get_issue_status` shows a run, or the issue
  carries labels the engine sets): change none of them. A park would not stop
  the run, so use the dashboard's Cancel for that. Corrections go in a
  follow-up issue.

**File parked** when the backlog starts issues on its own and this one should
not start yet: its design still needs review (always, when it removes or
changes existing behaviour), it waits on another repository or an unreleased
engine version, or it waits for a deploy. When in doubt, park. State the unpark
condition in one line of the body ("Unpark after review", "Unpark when
owner/repo#12 merges") and tell the user which issues you parked. Connected,
pass `scheduling: "parked"` to `open_issue` (or per item to
`open_issue_batch`); offline, put the label in the draft's front matter —
either way the issue is created parked. In a batch, an item that depends on a
parked one through `SE_DEPENDS_ON_ISSUES` waits anyway. Unpark by removing the
label: the dashboard's Park, or
`gh issue edit <n> --remove-label se:parked`.

## Labels the engine sets

The engine records its state in these as it works. Never apply or remove them:
a hand-applied one makes it skip or misread the issue.

- `se:resolve-status:*`
- `se:review-worker:*`
- `se:review-status:*`
- `se:roadmap:*`
- `se:open-pr`
- `se:blocked-manual`
- `se:needs-attention`
- `se:already-resolved`
- `se:verified`
- `se:claude-md-refresh`

Any other `se:` label is outside the authoring scheme and is rejected.

---

*Generated from AgentLoom's authoring rules `6d0c4044f0e2`.*
