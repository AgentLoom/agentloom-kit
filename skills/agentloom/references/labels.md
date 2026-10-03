# Labels

An issue AgentLoom should build carries exactly these labels:

| label | count | meaning |
|---|---|---|
| `se` | 1 | The engine only selects issues that carry it. |
| `se:type:<type>` | 1 | `security` · `bugfix` · `feature` · `refactor` · `dependency` · `docs` · `chore` · `test` · `other` |
| `se:priority:<priority>` | 1 | `low` · `medium` · `high` |
| `se:resolve-worker:<role>` | 1–2 | Role keys from `.seed-engine/org-chart.yml` (`roles[].key`), primary role first. Keep assignment conservative. |
| `agentloom:user-generated` | 1 | Marks agent-authored work for AgentLoom; outside the engine's label plane. |

You may also set the operator scheduling labels (`se:parked`, `se:pinned`) and any of
the repository's own non-`se:` labels.

**Engine-owned — never apply them.** The engine writes these as it works; a
hand-applied one makes it skip or misread the issue:

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

*Generated from AgentLoom's authoring rules for engine pin `2026.10.02-stable`.*
