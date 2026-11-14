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

`agreed`, `rejected` and `completed` need a resolution summary. For
`agreed` and `completed` it must say what was actually decided or done: a
placeholder (`done`, `ok`, `okay`, `yes`, `fixed`, `close`, `closed`, `complete`, `completed`, `confirmed`, `validated`, `resolved`, `agreed`, `marked as complete`, `marked as completed`, `n/a`, compared case-insensitively without
trailing punctuation) or anything under 12 characters is
refused, because the engine's planner reads the summary as the only record of
what happened.

## Completing a planning blocker

1. Read the entry and the guide section or document its `file` names.
2. Do the operator steps, or explain them to the user and wait until they are
   done. Run the section's `Validate:` check from a public vantage — a check
   from inside your own network can pass while CI and resolver vantages fail —
   and keep what it showed.
3. Record it:

   ```sh
   python3 $KIT/scripts/blocker-complete.py BLK-007 --status completed \
     --resolution "Created the webhook secret in Secret Manager as STRIPE_WEBHOOK_SECRET." \
     --observed "gcloud secrets versions list STRIPE_WEBHOOK_SECRET showed 1 enabled version"
   ```

   When an `operator_action`'s guide section carries a `**Validate:**` block,
   `completed` needs `--observed`: what the check showed, never secret values.
   It is recorded as the entry's `observed` field (with `observed_by:
   operator`) — the same record Mark completed and `complete_blocker` leave —
   and the planner reads it as the evidence the gate is met; a settled entry
   without it stays an unverified claim, so a summary carrying an `Observed:`
   line is refused: keep the summary to what was done. The script writes `status`,
   `resolved`, `resolution_summary` and `observed` the way the engine's
   `blocker resolve` does (and the `## Resolution` section of an upstream
   document), after screening the summary and the observation with
   AgentLoom's secret patterns: a credential token shape is refused outright;
   a secret-labelled assignment (`API_KEY=…`) is refused until you confirm it
   with `--ack API_KEY`.

   A planning blocker that a resolver round tied to an issue (`origin:
   planning` with an `issue_number`) completes the same way, and the script
   drops the `issue_number`, as the engine does.
4. Review the diff, commit and push to the default branch. The push wakes
   AgentLoom, which re-plans the gated tasks.

The summary is committed to the repository forever. When the guide section
asks you to record a non-secret value (a URL, an id, a parameter), put the
value itself in the summary: the task the blocker gates commits it. A secret
never goes in: say where it lives (`in Secret Manager as
STRIPE_WEBHOOK_SECRET`), never the secret.

To check a hand edit: `python3 $KIT/scripts/validate.py blocker BLK-007`.

---

*Generated from AgentLoom's authoring rules `b1cfb5d7a075`.*
