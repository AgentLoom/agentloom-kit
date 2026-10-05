# agentloom-kit

The AgentLoom skill for your own coding agent. It teaches an IDE agent — Claude
Code, Codex, Cursor, Copilot, anything that loads [Agent Skills](https://agentskills.io) —
to author work for AgentLoom correctly: resolver-ready GitHub issues,
dependency-ordered issue batches, roadmap tasks, and manual-blocker
resolutions, checked by a deterministic validator before anything is filed or
pushed. Your agent files with your own `gh` and `git`; no AgentLoom credentials
are needed.

Kit version **`2026.10.5.1`**, built from AgentLoom's authoring rules
`6d0c4044f0e23d57d9a4bb2f7f0ebaacc8bfdaaeee7486fe5f467589eb9227da`. The kit's release tag equals the kit version: the date
of the change (`YYYY.M.D`, or `YYYY.M.D.N` for a second release that day). The
kit is tied to the rules it enforces, not to an engine pin: an engine upgrade
that changes no authoring rule needs no new kit.

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
| Codex | `~/.codex/skills/agentloom/` (`$CODEX_HOME/skills/` when set) | — |
| Cursor (without the plugin) | `~/.agents/skills/agentloom/` | `.cursor/skills/agentloom/` |
| GitHub Copilot (in VS Code) | `~/.agents/skills/agentloom/` | `.github/skills/agentloom/` |

**Optional live connection.** Both plugins declare the AgentLoom MCP server
(`https://api.agent-loom.com/api/mcp`) in their manifests. Without a plugin, add that URL as an
HTTP MCP server:

- **Codex:** `codex mcp add agentloom --url https://api.agent-loom.com/api/mcp`, then
  `codex mcp login agentloom` — Codex signs in only through that command
  (`--no-browser` prints the link instead of opening it).
- **Cursor:** the **Install in Cursor** button under AgentLoom's Settings →
  Integrations → Connected agents, or `{"mcpServers": {"agentloom": {"url":
  "https://api.agent-loom.com/api/mcp"}}}` in `.cursor/mcp.json`.
- **VS Code:** the **Install in VS Code** button there, or `{"servers":
  {"agentloom": {"type": "http", "url": "https://api.agent-loom.com/api/mcp"}}}` in
  `.vscode/mcp.json`.
- **claude.ai:** Settings → Connectors → add a custom connector with the URL.

Connected, the skill validates against the platform's live pin and
your repository's resolver roles and stamps your AgentLoom user id on what you
author. The first use opens a browser sign-in to AgentLoom (in Codex,
`codex mcp login agentloom` does); there is no token to paste. Without it, everything works offline.

## Update

Every change ships as a new version. When AgentLoom's authoring rules change,
an older kit stops filing until it is updated.

- **Claude Code:** turn on auto-update once (`/plugin` → Marketplaces →
  agentloom-kit → Enable auto-update) and new versions install as a session
  starts. By hand, run both — the first refreshes the catalog only:

  ```sh
  claude plugin marketplace update agentloom-kit
  claude plugin update agentloom@agentloom-kit
  ```

  Then start a new session.
- **Cursor:** update the plugin from **Customize**, or `git pull` in your
  clone and reload Cursor.
- **A copied skill:** copy `skills/agentloom/` again from the new release.
- **An organization on Claude Code:** managed settings install it for every
  member and keep it current:

  ```json
  {
    "extraKnownMarketplaces": {
      "agentloom-kit": {
        "source": { "source": "github", "repo": "AgentLoom/agentloom-kit" },
        "autoUpdate": true
      }
    },
    "enabledPlugins": { "agentloom@agentloom-kit": true }
  }
  ```

## What is in it

- `skills/agentloom/SKILL.md` — when to file an issue and when to plan a
  roadmap task, and the workflow for each.
- `skills/agentloom/references/` — the issue body, batch, roadmap task,
  label and blocker guides, and the engine's tech-skill pool.
- `skills/agentloom/scripts/validate.py` — validates an issue draft, a batch,
  a roadmap change or a blocker completion. Exit codes: 0 pass, 1 errors,
  2 usage, 3 provisional (the pin-dependent checks could not be confirmed
  against the platform's rules — pass `--context` or `--rules-fingerprint`).
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

This repository is generated from AgentLoom's authoring rules, assistant
references and kit templates, and released on every change to them; changes
made here are overwritten by the next release.
