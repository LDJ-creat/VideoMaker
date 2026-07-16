# AGENTS.md

Slim agent contract for VideoMaker. Detailed routes, env tables, and plan indexes live in [`docs/guides/agents-reference.md`](docs/guides/agents-reference.md).

## Project

Competition project for an AI short-video system: **viral structure migration** — analyze high-performing samples, migrate reusable creative structure to a new brief/assets, fill material gaps, and emit explainable storyboard / timeline / packaging / demo video.

```text
sample (+ optional batch/knowledge)
→ structure_analyst (+ knowledge draft)
→ brief + assets (content_strategist)
→ slot_mapper + gap_planner
→ storyboard (masterNarration) + packaging
→ material completion (HF / AIGC / TTS) + dual variants
→ human gates (master / storyboard / material) → assemble / render
→ optional NL revise
```

Architecture spec: `docs/superpowers/specs/2026-05-27-videomaker-design.md`.  
Plans: `docs/superpowers/plans/` (P0 archive under `plans/P0/`; indexes in [agents-reference](docs/guides/agents-reference.md)).  
Demos: `docs/demos/*-checklist.md`.

## Module map

| Area | Path | Verify |
|------|------|--------|
| Contracts | `packages/contracts` | `npm run check` · `npm run validate:schemas` |
| API | `services/api` | `python -m pytest` · `python -m compileall app` · `run-dev.ps1` |
| Worker | `services/worker` | `python -m pytest` · `python -m compileall app` |
| Composition | `services/composition` | `python -m pytest` · `python -m compileall composition` |
| Web | `apps/web` | `npm run typecheck` · `npm run test` |
| Shared path helpers | `services/shared/knowledge/paths.py` | — |

Local runtime storage (default dev): **`services/api/storage/projects/{projectId}/`** (API cwd). Repo-root `storage/` also appears in some tooling — if a path is missing, search both.

## Hard rules

- **Contracts are boundaries:** `VideoStructure` (**`p1-v3` only**), `AssetInventory`, `GapReport`, `GenerationPlan`, `RenderTimeline`, `TaskEvent`. No ad hoc JSON shapes; schema + TS + tests together.
- **No rule semantic fallback in production.** Structure/mapping/gap/storyboard/packaging/material go through Agents + providers. **`VIDEOMAKER_FIXTURE_MODE=true`** is test/CI only — never a live-model failure fallback.
- Default variants: **`high_click`** + **`high_conversion`**.
- Task truth: **SQLite** authoritative; **SSE** primary; **polling** fallback. Retry = `POST /api/tasks/{id}/retry` with `resume=true` (same task id).
- Generation human gates (default on): `awaiting_master_review` → `awaiting_storyboard_review` → visual material → `awaiting_material_review` → `assembling_final`. Details + env: [agents-reference](docs/guides/agents-reference.md) · E2E `docs/demos/material-review-gate-e2e-checklist.md`.
- Do not commit runtime media / SQLite / model dumps. Do not let LLM output execute code. Validate agent JSON against schemas. Migrate structure/method only — do not copy sample video content.
- **Path security:** any user/API id used as a filesystem segment must go through `validate_storage_segment` (and usually `assert_under_storage_root`). See Storage § in [agents-reference](docs/guides/agents-reference.md).
- Substantial features: **worktree** off `main` (`git worktree add .worktrees/<name> -b feature/<name> main`). Schema changes: contracts first, then dependents.
- Env source of truth: **`services/api/.env.example`** (loaded by `run-dev.ps1`). Do not duplicate long env tables here.

## Generation / material author (pointers)

- Material author: ReAct (`VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND=react`) or ACP (`acp` + Cursor/Claude/Codex). Composition facade: `services/composition`.
- Observability logs: `logs/model-calls/`, `logs/agent-runs/`, `logs/tool-runs/`, ACP traces under `logs/composition-author/acp/{runId}/`.
- Debug ACP/ReAct slots from disk: skill below + `summarize_acp_trace.py`.

## Cursor project skills

| Skill | When |
|-------|------|
| [`.cursor/skills/composition-agent-debug/SKILL.md`](.cursor/skills/composition-agent-debug/SKILL.md) | Debug composition material author (ReAct/ACP) via on-disk traces / scratch / material-review. Script: `python .cursor/skills/composition-agent-debug/scripts/summarize_acp_trace.py --project-id …` |

## Testing

TDD for implementation. Before claiming done, run the module commands in the table above (and `services/composition` when touching HF author). Document new commands in the subsystem plan.

`services/api` pytest uses `--basetemp=.pytest-tmp` (Windows temp path issues).

## Notes for new AI sessions

1. Read **this** file first; open [agents-reference](docs/guides/agents-reference.md) only when you need routes/env/plan indexes.
2. For architecture boundaries: `docs/superpowers/specs/2026-05-27-videomaker-design.md`.
3. For the active feature: the matching plan under `docs/superpowers/plans/`.
4. Composition/ACP debugging: follow `composition-agent-debug` before guessing.
5. `git status --short`; use a feature worktree unless the user asks for a small docs-only change on `main`.
6. Run relevant tests before/after; keep commits scoped.

## Plan quality gate

Subsystem plans are executable specs. Before handoff they must state: owned user flows; routes/artifacts; nontrivial algorithms; tool order/fallbacks; in/out-of-scope files; happy-path + error tests. Do not defer core behavior to “decide during implementation” without naming the integrating plan and route/artifact.

Further detail (HTTP catalogs, env tables, P0/P1 plan tables, storage layouts, LLM gate prose): **[`docs/guides/agents-reference.md`](docs/guides/agents-reference.md)**.
