# Reading a run

`get_issue_status` and `list_runs` give a run's raw `status` (`pending`,
`queued`, `running`, `waiting`, `waiting_approval`, `interrupted`, `succeeded`,
`failed`, `cancelled`). The AgentLoom dashboard shows each run with one of the
statuses below: `pending` and `queued` both read **Queued**, `waiting_approval`
reads **Pending approval**, and **Rate limited**, **No changes**, **Deferred**,
**Not started**, **Budget cap** and **Superseded** refine a raw status from the
run's outcome. Use the dashboard's words with the user.

## Statuses

| Status               | What it means                                                                                                                                                                                                                                                  |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Queued**           | Not started yet, often because the repository is at its **Max concurrent runs**, which counts the runs that resolve issues and close out landings. It starts when a slot frees; **Up next** on the Runs screen lists the waiting runs in the order they start. |
| **Running**          | A leg is working.                                                                                                                                                                                                                                              |
| **Waiting**          | Between legs, waiting for CI, for the pull request to become mergeable, or for its turn to merge.                                                                                                                                                              |
| **Pending approval** | Waiting for a person to approve, such as a merge your policy holds.                                                                                                                                                                                            |
| **Interrupted**      | Stopped part-way, holding its place until it resumes, on its own or when someone resumes it.                                                                                                                                                                   |
| **Rate limited**     | Paused by a provider's rate or usage limit. Its card says when the limit resets; the run resumes then if your automation policy allows it.                                                                                                                     |
| **Succeeded**        | Finished its work. For a run that resolves an issue, its change merged.                                                                                                                                                                                        |
| **No changes**       | Finished without changing anything, for example because the work had already landed.                                                                                                                                                                           |
| **Deferred**         | Not run yet, because an issue it depends on hasn't finished.                                                                                                                                                                                                   |
| **Not started**      | Refused before it began, because its dependencies weren't done.                                                                                                                                                                                                |
| **Failed**           | Ended on an error it couldn't recover from. Its page says why and what to do.                                                                                                                                                                                  |
| **Cancelled**        | Stopped before it finished.                                                                                                                                                                                                                                    |
| **Budget cap**       | Canceled because its cost reached the per-run cap. Its page offers to reset the cap and resume it.                                                                                                                                                             |
| **Superseded**       | A newer run took over its issue. This run's own outcome is on its page.                                                                                                                                                                                        |

## Stages

A run's page groups the engine's steps into five stages:

| Stage         | What it covers                                                                                                                                                                                         |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Implement** | Writing the change: planning and coding it, fixing what a failed check or a review found, and resolving conflicts with the default branch. For a pull request handed over to the engine, taking it on. |
| **CI**        | Waiting for the checks to start and finish on the pull request, and for it to become mergeable.                                                                                                        |
| **Review**    | The reviewer roles reviewing the change.                                                                                                                                                               |
| **Merge**     | The run's closeout on the pull request, waiting for its turn to merge, and the checks on the merged code.                                                                                              |
| **Paused**    | Stopped between steps until what it waits on arrives. It doesn't by itself mean someone has to act; the run's card says when they do.                                                                  |

For anything else about a run, `search_docs` finds the help center page.

---

*Generated from AgentLoom's authoring rules `b1cfb5d7a075`.*
