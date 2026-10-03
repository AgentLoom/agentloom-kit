# agentloom-kit

The AgentLoom skill for your own coding agent. It teaches an IDE agent — Claude
Code, Codex, Cursor, Copilot, anything that loads [Agent Skills](https://agentskills.io) —
to author work for AgentLoom correctly: resolver-ready GitHub issues,
dependency-ordered issue batches, roadmap tasks, and manual-blocker
resolutions, checked by a deterministic validator before anything is filed or
pushed. Your agent files with your own `gh` and `git`; no AgentLoom credentials
are needed.

Built for engine pin **`2026.10.02-stable`**. The kit's release tag equals the pin.

## Install

Requirements: Python 3.10+ with `pyyaml` and `ruamel.yaml`
(`python3 -m pip install -r skills/agentloom/scripts/requirements.txt`), `git`,
and the GitHub CLI `gh`.

**Claude Code (plugin):**

```text
/plugin marketplace add AgentLoom/agentloom-kit
/plugin install agentloom@agentloom-kit
```

**Cursor (plugin):** the repository root is a portable Agent Plugin
(`plugin.json` + `mcp.json`) carrying the skill and the server. Install it
from **Customize** once it is listed, or clone it under
`~/.cursor/plugins/local/` and reload Cursor.

**Any other Agent Skills client:** copy `skills/agentloom/` into the client's
skills directory:

| Client | All repositories | One repository |
|---|---|---|
| Claude Code (without the plugin) | `~/.claude/skills/agentloom/` | `.claude/skills/agentloom/` |
| Codex | `~/.agents/skills/agentloom/` | `.agents/skills/agentloom/` |
| Cursor (without the plugin) | `~/.agents/skills/agentloom/` | `.cursor/skills/agentloom/` |
| VS Code (GitHub Copilot) | `~/.agents/skills/agentloom/` | `.github/skills/agentloom/` |

**Optional live connection.** Both plugins declare the AgentLoom MCP server
(`https://api.agent-loom.com/api/mcp`) in their manifests. Without a plugin, add that URL as an
HTTP MCP server:

- **Codex:** in `~/.codex/config.toml`, `[mcp_servers.agentloom]` with
  `url = "https://api.agent-loom.com/api/mcp"`.
- **Cursor:** the **Install in Cursor** button under AgentLoom's Settings →
  Integrations → Connected agents, or `{"mcpServers": {"agentloom": {"url":
  "https://api.agent-loom.com/api/mcp"}}}` in `.cursor/mcp.json`.
- **VS Code:** the **Install in VS Code** button there, or `{"servers":
  {"agentloom": {"type": "http", "url": "https://api.agent-loom.com/api/mcp"}}}` in
  `.vscode/mcp.json`.
- **claude.ai:** Settings → Connectors → add a custom connector with the URL.

Connected, the skill validates against the platform's live pin and
your repository's resolver roles and stamps your AgentLoom user id on what you
author. The first use opens a browser sign-in to AgentLoom; there is no token
to paste. Without it, everything works offline.

## What is in it

- `skills/agentloom/SKILL.md` — when to file an issue and when to plan a
  roadmap task, and the workflow for each.
- `skills/agentloom/references/` — the issue body, batch, roadmap task,
  label and blocker guides, and the engine's tech-skill pool for this pin.
- `skills/agentloom/scripts/validate.py` — validates an issue draft, a batch,
  a roadmap change or a blocker completion. Exit codes: 0 pass, 1 errors,
  2 usage, 3 provisional (the pin-dependent checks could not be confirmed
  against the platform's pin — pass `--context` or `--pin`).
- `skills/agentloom/scripts/roadmap-tag.py` — stamps the provenance tag on new
  roadmap tasks, byte-for-byte as the engine writes it.
- `skills/agentloom/scripts/blocker-complete.py` — records a planning
  blocker's resolution the way the engine does, after the platform's secret
  screening.

The scripts make no network calls and fetch nothing at runtime; the live
context reaches them as a file your agent saved.

## Verify

```sh
sha256sum -c SHA256SUMS
```

## Source

This repository is generated from AgentLoom's authoring rules on every engine
pin; changes made here are overwritten by the next release.
