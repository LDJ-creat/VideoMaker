# Composition ACP Author E2E Checklist

## Prerequisites

- Node.js >= 22, FFmpeg on PATH, repo root `npm install` + `npm run hyperframes:doctor`
- `services/composition/composition/build/` is **tracked source** (HTML templates + builder); included via `.gitignore` exception for this path
- For live ACP (Layer C/D): install target agent binary and credentials
  - Claude: `npx @agentclientprotocol/claude-agent-acp` + `ANTHROPIC_API_KEY`
  - Codex: `npx @zed-industries/codex-acp` + OpenAI auth
  - Cursor: `agent.cmd --trust --model auto acp` + Cursor subscription

## Env

| Env | Default | Notes |
|-----|---------|-------|
| `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND` | `react` | Set `acp` to enable external agent author |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT` | `claude` | `claude` / `codex` / `cursor` |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND` | empty | JSON array override spawn command |
| `VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC` | `600` | Per-slot author timeout |
| `VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE` | `true` | Headless tool/terminal approval |
| `VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX` | `1` | Post-turn lint failure → extra ACP repair sessions |
| `VIDEOMAKER_COMPOSITION_LINT_CACHE` | `true` | Skip duplicate HF lint when spec hash matches session lint |
| `VIDEOMAKER_MCP_WRITE_SKIP_LINT` | `true` (ACP) | MCP `write_material_spec` skips HF lint; worker gate remains |

## A. Module automation

```powershell
cd services/composition
pip install -e ".[mcp]"
python -m pytest tests/test_mcp_server.py tests/test_lint_pipeline.py tests/test_cli_lint_spec.py -q

cd ../worker
pip install -e ".[acp]"
python -m pytest tests/test_acp_agent_registry.py tests/test_acp_author.py tests/test_terminal_bridge.py -q
python -m pytest tests/test_hyperframes_material_provider.py::test_hyperframes_provider_uses_acp_author_backend -q
```

## B. MCP smoke (no external agent)

Layer B covered by `test_mcp_server.py` (`skill_view`, `write_material_spec` with fixture lint).

## B2. CLI lint-spec smoke

```powershell
cd D:\VideoMaker
$scratch = "services\api\storage\smoke\cli-lint-scratch"
New-Item -ItemType Directory -Force -Path $scratch | Out-Null
@'
{"template":"benefit-card","durationSec":3,"params":{"title":"Cli","bullets":["A"],"colors":{"primary":"#2563eb","background":"#0f172a","text":"#ffffff"}}}
'@ | Set-Content -Encoding utf8 "$scratch\material-spec.json"
$env:VM_ACP_FIXTURE_LINT="1"
$env:PYTHONPATH="services\composition;services\shared"
python -m composition.cli lint-spec --scratch $scratch --repo-root . --schema-only --json
python -m composition.cli lint-spec --scratch $scratch --repo-root . --json
```

**Pass:** exit 0; full lint writes `{scratch}/lint-draft/.lint-passed.json`.

## B3. Lint hash cache (automation)

Covered by `test_lint_pipeline.py::test_skip_hf_if_cached` and `test_composition_engine.py::test_render_clip_reuses_lint_scratch`.

Manual ACP trace check after full author: `outcome.json` may include `"lintCached": true` when session lint hash matches post-turn gate.

## C. Live ACP smoke (manual)

```powershell
cd services/worker
$env:VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND="acp"
$env:VIDEOMAKER_COMPOSITION_ACP_AGENT="claude"   # or codex / cursor
python scripts/smoke_composition_acp.py
```

Repeat for each agent (`claude`, `codex`, `cursor`).

**Pass:** JSON `ok: true`, MP4 exists, `material-spec.json` under scratch dir, ACP trace under `storage/projects/composition-acp-smoke/logs/composition-author/acp/`.

Optional: set `VIDEOMAKER_ACP_SMOKE_SIMPLE=false` for full author with session lint iteration.

## D. Workbench full pipeline (manual)

1. Worker env: `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=acp`, pick agent via `VIDEOMAKER_COMPOSITION_ACP_AGENT`.
2. Run generation with HF packaging slots to MP4.
3. Confirm artifact paths match react backend:
   - `generations/{generationId}/generated/{actionId}.mp4`
   - `generations/{generationId}/generated/{actionId}/composition/`
4. Agent run log shows `prompt_version=composition-acp-v1` and `backend=acp`.

## Repair round (manual / automation)

Automation: `test_acp_author.py::test_acp_lint_repair_retries_after_post_turn_failure`.

Manual: induce post-turn lint failure with invalid spec + `VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX=1`; trace should show second prompt with `validationErrors`.

## Fallback

On ACP author failure, provider still falls back to ken-burns / legacy spec when assets exist (same as ReAct failure path).

## CLI wrapper (Windows)

```powershell
.\scripts\lint-material-spec.ps1 -Scratch services\api\storage\smoke\cli-lint-scratch --schema-only
```
