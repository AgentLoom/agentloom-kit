# Writing steer guidance

`steer_run` puts your guidance in front of AgentLoom's resolver on its next
round for the issue and sets the run going again. The resolver reads it as the
operator's word, so it is worth one careful pass. At most 3900
characters.

## Before you write

1. `get_run_failure` for the run: read `failure_summary`, `failure_detail`, and
   the two verdicts. If `steerable.ok` is false, stop and tell the user its
   `reason` — the dashboard would refuse the same click. If `reachable_by` is
   `automation` or `platform`, guidance cannot change the failing step; say so
   instead of steering.
2. Read the evidence yourself with your own tools: the PR's round-by-round
   history and review comments (`gh pr view`, `gh pr diff`), the failing CI job
   (`gh run view --log-failed`), and the code at the lines involved. Guidance
   written from the summary alone repeats what the resolver already tried.

## What to write, in this order

1. **What is ruled out.** The hypotheses the evidence falsifies, each with the
   evidence in one line. This stops the next round re-guessing.
2. **The confirmed root cause**, with exact `path:line` references you verified
   in the checkout.
3. **What to read before changing anything** — the files, tests or logs that
   show the cause.
4. **The change**, described as a working-tree edit: which file, which
   function, what it should do instead.
5. **How to verify**: the command to run and what passing looks like.

## Never

- Tell the resolver to commit, push, check out, reset, rebase, merge, open or
  edit a PR, or comment on GitHub. AgentLoom's automation does those; the
  resolver cannot run them, and the platform refuses guidance that asks.
- Paste a secret or a credential. Name where it lives.
- Restate the whole issue. The resolver has it; add what it does not know.

## Before sending

Call `steer_run` with `preview: true` first: it checks steerability and the
guidance without writing. Then send the same call with `preview: false` and a
new `request_id`, reusing that `request_id` if you have to retry.

---

*Generated from AgentLoom's authoring rules `6d0c4044f0e2`.*
