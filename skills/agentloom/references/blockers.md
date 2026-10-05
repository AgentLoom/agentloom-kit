# Manual blockers

A blocker is a prerequisite only a human can satisfy. They live in
`.seed-engine/blockers-registry.yml`; each entry's `file` points at the guide
section (`.seed-engine/docs/bootstrap-guide.md#…`) or the upstream document
that explains it. The AgentLoom dashboard Inbox lists the open ones.

## Two kinds, two paths

- **Planning blockers (`BLK-001`, …)** gate roadmap tasks. You can complete
  them here, in the registry, with `blocker-complete.py` — or, connected, with
  `complete_blocker`, which runs the same secret screening and commits for you.
- **Resolver blockers (`BLK-RES-<issue>-<n>`, or `origin: resolver`)** belong
  to a paused run. They are answered with `respond_to_blocker` when connected,
  or in the AgentLoom dashboard with **Record answers & resume** — either
  records the answers and resumes the run. Never edit them in the registry.
  A resume on its own is not an answer: a blocker is settled only by live
  evidence that its condition now holds, or by your recorded answer, which
  names the blocker's id.

## Statuses

Statuses only move forward.

- `operator_action` and `other`: `pending` → `completed`
- `upstream_request`: `pending` → `raised` → `in_discussion` → `agreed` → `rejected` → `completed`

`agreed`, `rejected` and `completed` need a resolution summary.

## Completing a planning blocker

1. Read the entry and the guide section or document its `file` names.
2. Do the operator steps, or explain them to the user and wait until they are
   done. Run the section's `Validate:` check from a public vantage — a check
   from inside your own network can pass while CI and resolver vantages fail.
3. Record it:

   ```sh
   python3 $KIT/scripts/blocker-complete.py BLK-007 --status completed \
     --resolution "Created the webhook secret in Secret Manager as STRIPE_WEBHOOK_SECRET."
   ```

   The script writes `status`, `resolved` and `resolution_summary` the way the
   engine's `blocker resolve` does (and the `## Resolution` section of an
   upstream document), after screening the summary with AgentLoom's secret
   patterns: a credential token shape is refused outright; a secret-labelled
   assignment (`API_KEY=…`) is refused until you confirm it with
   `--ack API_KEY`.
4. Review the diff, commit and push to the default branch. The push wakes
   AgentLoom, which re-plans the gated tasks.

The summary is committed to the repository forever. Say where a value lives
(`in Secret Manager as STRIPE_WEBHOOK_SECRET`), never the value.

To check a hand edit: `python3 $KIT/scripts/validate.py blocker BLK-007`.

---

*Generated from AgentLoom's authoring rules `6d0c4044f0e2`.*
