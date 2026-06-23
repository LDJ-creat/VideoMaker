# Composition ACP Author E2E Checklist

## Prerequisites

- Node.js >= 22, FFmpeg on PATH, repo root `npm install` + `npm run hyperframes:doctor`
- `services/composition/composition/build/` is **tracked source** (HTML templates + builder); included via `.gitignore` exception for this path
- For live ACP (Layer C/D): install target agent binary and credentials
  - Claude: `npx @agentclientprotocol/claude-agent-acp` + `ANTHROPIC_API_KEY`
  - Codex: `npx @zed-industries/codex-acp` + OpenAI auth
  - Cursor: `agent.cmd --trust --model auto acp` + Cursor subscription

## Env

Copy [`services/api/.env.example`](../api/.env.example) → `services/api/.env` (gitignored). **`run-dev.ps1` loads `.env` automatically**; worker subprocesses inherit the same values—no need to export in the shell each session.

| Env | Default | Notes |
|-----|---------|-------|
| `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND` | `react` | Set `acp` in `.env` to enable external agent author |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT` | `claude` | `claude` / `codex` / `cursor` |
| `VIDEOMAKER_COMPOSITION_ACP_AGENT_COMMAND` | empty | JSON array override spawn command |
| `VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC` | unset | Per-slot timeout; **1800** when `template=composition` if unset |
| `VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE` | `true` | Headless tool/terminal approval |
| `VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS` | `5` | Same-session prompt turns (1 create + up to 4 in-session repair) |
| `VIDEOMAKER_COMPOSITION_ACP_SESSION_RETRY` | `1` | Retry whole session on connection/MCP env failures only |
| `VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX` | deprecated | Maps to `MAX_TURNS - 1`; prefer `MAX_TURNS` |
| `VIDEOMAKER_COMPOSITION_LINT_CACHE` | `true` | Skip duplicate HF lint when spec hash matches session lint |
| `VIDEOMAKER_ACP_SMOKE_SIMPLE` | **`false`** | **Production E2E must be `false`**; smoke scripts set `true` |
| `VIDEOMAKER_MCP_WRITE_LINT_FOR_ACP` | `true` | MCP `write_material_spec` runs lint with `hintCode` / `fixRecipe` |
| `VIDEOMAKER_MCP_WRITE_SKIP_LINT` | `false` (ACP) | When `true`, skips MCP lint; worker turn gate remains |

### Concurrency (dual-layer)

| Layer | Env | Default | Notes |
|-------|-----|---------|-------|
| API global | `VIDEOMAKER_MAX_CONCURRENT_GENERATIONS` | `2` | Generation + revise fork subprocesses; 3rd plan queues until slot frees |
| Worker per generation | `VIDEOMAKER_MATERIAL_MAX_CONCURRENT_SLOTS` | `3` | Cross-slot HF/ACP parallel; same slot stock→finish serial; master TTS last |

**Tuning when Cursor rate-limits:** keep `GENERATIONS=2`, lower `MATERIAL_MAX_CONCURRENT_SLOTS` to `2`, or set `GENERATIONS=1` for conservative runs. Worst case at defaults ≈ 2×3 = 6 parallel authors.

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

Production E2E: **`VIDEOMAKER_ACP_SMOKE_SIMPLE=false`** (default in `.env.example`) for full `skill_view` → `composition_lint_draft` → `write_material_spec` with in-session turn loop.

```powershell
python scripts/verify_acp_cursor_smoke.py
```

Smoke script sets `VIDEOMAKER_ACP_SMOKE_SIMPLE=true` explicitly for fast MCP-only path.

## D. Workbench full pipeline (manual)

1. Copy `services/api/.env.example` → `services/api/.env`; set `VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=acp` and `VIDEOMAKER_COMPOSITION_ACP_AGENT=cursor` (or claude/codex). Restart `run-dev.ps1`.
2. Run generation with HF packaging slots to MP4.
3. Confirm artifact paths match react backend:
   - `generations/{generationId}/generated/{actionId}.mp4`
   - `generations/{generationId}/generated/{actionId}/composition/`
4. Agent run log shows `prompt_version=composition-acp-v1` and `backend=acp`.
5. `logs/tool-runs/` contains `acp_session_start` / `acp_turn_lint_gate` / `acp_session_end` (and optional `acp_turn_followup`, `acp_session_update` spans).
6. `outcome.json` includes `turnCount`, `hintCodes` when lint failed before success.
7. `logs/agent-runs/` entry has `model=acp:claude` (or env override) and `inputSummary.slotId`.
8. With `LANGFUSE_ENABLED=true`, Langfuse trace shows `material_author:acp_session_*` spans under the same `taskId` trace.

## Turn loop repair (manual / automation)

Automation: `test_acp_author.py::test_acp_turn_loop_retries_in_same_session`.

Manual: induce post-turn lint failure; trace should show **same session** second prompt with `IN_SESSION_REPAIR` + `validationErrors` / `hintCode` (not a new `REPAIR:` session).

## Fallback

On ACP author failure, provider uses **tiered fallback**: `source_then_polish` + video base → video composition overlay; hf_native with refs → ken-burns / video composition; no refs → legacy placeholder with task warning (no silent `VideoMaker` title except fixture mode).

## CLI wrapper (Windows)

```powershell
.\scripts\lint-material-spec.ps1 -Scratch services\api\storage\smoke\cli-lint-scratch --schema-only
```
