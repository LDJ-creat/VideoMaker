# Composition ACP Author E2E Checklist

## Prerequisites

- Node.js >= 22, FFmpeg on PATH, repo root `npm install` + `npm run hyperframes:doctor`
- `services/composition/composition/build/` is **tracked source** (HTML templates + builder); included via `.gitignore` exception for this path
- For live ACP (Layer C/D): install target agent binary and credentials
  - Claude: `npx @agentclientprotocol/claude-agent-acp` + `ANTHROPIC_API_KEY`
  - Codex: `npx @zed-industries/codex-acp` + OpenAI auth
  - Cursor: `cursor --acp` + Cursor subscription

## Env

| Env | Default | Notes |
|-----|---------|-------|
| `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND` | `react` | Set `acp` to enable external agent author |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT` | `claude` | `claude` / `codex` / `cursor` |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND` | empty | JSON array override spawn command |
| `VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC` | `600` | Per-slot author timeout |
| `VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE` | `true` | Headless tool/terminal approval |

## A. Module automation

```powershell
cd services/composition
pip install -e ".[mcp]"
python -m pytest tests/test_mcp_server.py -q

cd ../worker
pip install -e ".[acp]"
python -m pytest tests/test_acp_agent_registry.py tests/test_acp_author.py -q
python -m pytest tests/test_hyperframes_material_provider.py::test_hyperframes_provider_uses_acp_author_backend -q
```

## B. MCP smoke (no external agent)

Layer B covered by `test_mcp_server.py` (`skill_view`, `write_material_spec` with fixture lint).

## C. Live ACP smoke (manual)

```powershell
cd services/worker
$env:VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND="acp"
$env:VIDEOMAKER_COMPOSITION_ACP_AGENT="claude"   # or codex / cursor
python scripts/smoke_composition_acp.py
```

Repeat for each agent (`claude`, `codex`, `cursor`).

**Pass:** JSON `ok: true`, MP4 exists, `material-spec.json` under scratch dir, ACP trace under `storage/projects/composition-acp-smoke/logs/composition-author/acp/`.

## D. Workbench full pipeline (manual)

1. Worker env: `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=acp`, pick agent via `VIDEOMAKER_COMPOSITION_ACP_AGENT`.
2. Run generation with HF packaging slots to MP4.
3. Confirm artifact paths match react backend:
   - `generations/{generationId}/generated/{actionId}.mp4`
   - `generations/{generationId}/generated/{actionId}/composition/`
4. Agent run log shows `prompt_version=composition-acp-v1` and `backend=acp`.

## Fallback

On ACP author failure, provider still falls back to ken-burns / legacy spec when assets exist (same as ReAct failure path).
