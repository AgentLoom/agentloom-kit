# How an issue review works

Read this before you start a review with `open_issue_reviewed` or
`review_issue`, and before you rely on an issue a review has touched. The
dashboard shows the same review on the run's **Review** tab; the MCP tools
below return what that tab shows, in the same terms.

## The two kinds of review

- **A plain issue** gets a writer/reviewer loop (an `issue_onboard` run with
  review on). A reviewer judges the issue body and records findings; a writer
  answers each finding — adopts it and amends the body, or rejects it with a
  reason — and the loop runs again until it converges or stops. It **may
  rewrite the issue in place**: the body, and sometimes the title.
  - `get_issue_review` reports it as kind `review` when the issue already
    existed (the dashboard titles the run "Issue review" and the Backlog row
    reads "Reviewing"), and as kind `onboarding` when the loop ran on a newly
    filed or imported issue. `get_issue_status` carries the same `kind` on its
    `onboard` block.
- **A sprint-published issue** (one the generator published from a sprint)
  gets a read-only `issue_review`. It changes nothing on the issue: it posts
  its verdict and findings as a comment. `get_issue_review` reports it as kind
  `issue_review`.

## What changes on GitHub

For the writer/reviewer loop, when it publishes:

- The issue body is **replaced** by the reviewed body, which starts with an
  onboarding header: a `**Baseline:**` line naming the commit it was checked
  against and an `SE_ONBOARD` marker.
- The title may change (`title_changed`, `proposed_title`).
- The original title and body are kept in a comment on the issue marked
  `seed-engine:onboard-original`. `get_issue_review` links it as
  `original_body_comment_url`, and `get_issue_status` as the `onboard` block's
  `original_body_comment_url`.
- `se:issue-reviewed` is added when the loop converges.

The findings and the writer's answers are **not** posted to GitHub: they are
AgentLoom's record (see "Where the review is").

The read-only `issue_review` only adds its comment.

## How to follow it

Poll `get_issue_status` with the repository id and issue number:

- `onboard.run_status` is the loop's run; `onboard.stop` is why it stopped.
- Converging stops are `approved_clean` and `settled_by_maintainer`. Any other
  stop — `round_cap`, `cost_cap`, `review_incomplete` — did not converge: the
  issue does not get `se:issue-reviewed`, and a person decides
  what happens next. `get_issue_review` says what the loop did
  (`published`, `body_changed`, the rounds).
- A run `waiting` with `questions_count > 0` is asking you something. Answer
  with `respond_to_blocker` and `family: "onboard"` (preview first: it returns
  the questions). `get_issue_review` also returns the questions.
- For a read-only review, `review.verdict` is the newest `issue_review`'s
  verdict.

## The park

- `open_issue_reviewed` files the issue parked and holds that park for the
  review: `get_issue_status` reports `review_park: true` while it is held. When
  the loop converges, the platform removes `se:parked` itself and
  applies `after_review` (`pin` or `run`); any other stop leaves the issue
  parked.
- `review_issue` on an issue that is already parked the plain way (by hand or
  from the Backlog) does **not** lift that park on convergence. Unpark it
  yourself when the user wants it built.

## Where the review is

Read it with `get_issue_review` (`repo_id`, `issue_number`, and optionally a
`run_id` of one of the issue's review runs). It returns the newest review,
open issue or closed:

- `round_reviews` — one entry per round: the reviewer's `verdict`, `summary`
  and `findings` (`id`, `severity`, `blocking`, `location`, `claim`,
  `evidence`, `recommendation`), and the writer's `dispositions` — `adopted`
  or `rejected` per finding, with its `reason`. `findings_total` /
  `dispositions_total` appear when the stored list was cut short.
- `stop`, `rounds`, `blocking_rejected` (blocking findings the writer
  rejected), `title_changed`, `proposed_title`, `body_changed`,
  `original_body_comment_url`.
- For kind `issue_review`: its `verdict`, one round, and `review_comment_url`,
  the comment it posted.

Every value the engine did not report is `null`, never guessed: a run still in
flight has `round_reviews: null`. The same review is on the dashboard run's
**Review** tab. Do not look for the findings in GitHub or in logs: the
writer/reviewer loop's review exists only in AgentLoom; only a read-only
review is also on GitHub, as the comment at `review_comment_url`.

## What to check after

- **Re-read the published body before relying on it** — for a summary to the
  user, a follow-up issue, or a dependency. It is no longer your draft:
  `gh issue view <n>` shows what the review published, and
  `original_body_comment_url` what it replaced.
- Report what changed and why from `get_issue_review`, not from a diff you
  reconstruct yourself.
- A fresh `se:issue-reviewed` (the body still matches what the
  review published) makes `review_issue` refuse a second review. To have the
  issue reviewed again, its body must have changed since.

---

*Generated from AgentLoom's authoring rules `b1cfb5d7a075`.*
