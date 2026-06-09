# AGENTS.md

## Project Context

VideoMaker is a competition project for an AI short-video creation system. The product goal is a "viral structure migration engine": analyze high-performing sample videos, extract reusable creative structure, map that structure to a new topic or user assets, identify material gaps, and generate an explainable storyboard, timeline, packaging plan, and demo video.

The competition brief is stored in `VideoMaker.md`. The user's original solution sketch is stored in `VideoMakerDesign.md`. The refined project design and implementation plans are the source of truth for development:

- `docs/superpowers/specs/2026-05-27-videomaker-design.md` (architecture spec)
- `docs/superpowers/plans/P0/` (archived P0 implementation plans; see index below)
- `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md` (P1 master plan; merged on `main`)
- Post-P1 extension plans: `2026-06-02-master-narration-layer-plan.md`, `2026-06-03-knowledge-deposition-plan.md`, `2026-06-04-multi-sample-analysis-plan.md`, `2026-06-06-sample-analysis-cost-resilience-plan.md`, `2026-06-08-generation-human-review-and-duration-strategy-plan.md`

### P0 Plan Archive (`docs/superpowers/plans/P0/`)

| Plan | Purpose |
|------|---------|
| `2026-05-27-videomaker-p0-implementation-plan.md` | Master P0 execution order |
| `2026-05-27-contracts-foundation-plan.md` | Shared schemas and TypeScript types |
| `2026-05-27-api-task-artifacts-plan.md` | FastAPI tasks, SSE, artifacts |
| `2026-05-27-worker-video-analysis-plan.md` | FFmpeg, OpenCV, Whisper, sample pipeline |
| `2026-05-27-web-workbench-plan.md` | Next.js workbench and task progress |
| `2026-05-27-agent-generation-plan.md` | Slot mapping, gap report, generation plan |
| `2026-05-27-hyperframes-render-plan.md` | RenderTimeline → HyperFrames preview |
| `2026-05-27-integration-p0-demo-flow-plan.md` | End-to-end API + worker wiring |
| `2026-05-28-web-workbench-hardening-plan.md` | Workbench persistence and UX hardening |
| `2026-05-28-parallel-agent-prompts.md` | Parallel worktree agent prompts |

Legacy copies may still exist under `docs/superpowers/plans/`; prefer the `P0/` archive for completed work.

## Product Direction

P0 is not a full video editor and not a direct sample-video copier. P0 must demonstrate a stable, explainable core loop:

```text
sample video input
-> video analysis and structure extraction
-> standardized structure slots
-> new brief and user asset analysis
-> slot matching and gap detection
-> completion planning
-> storyboard / render timeline / packaging plan
-> HyperFrames demo and process visualization
```

The key scoring dimensions are:

- clear definition of "video structure"
- explainable structure migration
- material gap detection and completion
- visible migration process
- verifiable output such as storyboard, timeline, or demo video

P1 extends the loop with **LLM structure evidence**, **semantic slot mapping**, **AIGC gap completion**, **dual-variant generation**, **NL revise**, plus post-P1 **knowledge deposition** and **multi-sample structure synthesis**:

```text
sample video input (+ optional batch / knowledge context)
-> perception + LLM structure_analyst (+ knowledge draft)
-> brief + asset understanding (content_strategist)
-> slot mapping + gap planning (LLM Agents)
-> storyboard (masterNarration) + packaging + material completion (AIGC / HyperFrames / TTS)
-> dual variants (high_click / high_conversion) + HyperFrames preview
-> optional NL revise + generation run history
```

## P0 Status (merged on `main`)

P0 module work is complete on `main`. The following feature/integration branches were implemented and merged:

- `feature/contracts-foundation`
- `feature/api-task-artifacts`
- `feature/worker-video-analysis`
- `feature/web-workbench`
- `feature/agent-generation`
- `feature/hyperframes-render`
- `integration/p0-demo-flow`

Post-P0 fixes (also on `main`) include checkpoint resume, global cookie upload, project/sample/asset API hydration, workbench result reload (`GET .../generations/latest`), and upload UX improvements.

Demo verification checklist: `docs/demos/p0-demo-checklist.md`.

## P1 Status (merged on `main`)

P1 upgrades P0 from deterministic demo to **LLM Agent + ModelGateway + AIGC material completion**. Core loop is verified end-to-end on `main`: live sample analysis → structure evidence → slot mapping / gap → dual-variant generation (`high_click`, `high_conversion`) → HyperFrames preview / optional MP4 render, with NL revise and agent-run observability.

**Master plan:** `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md`

**Execution order & session prompts:** `docs/superpowers/plans/2026-05-29-p1-execution-order-and-prompts.md`

**Demo verification:** `docs/demos/p1-demo-checklist.md` (steps in `docs/demos/p1-manual-test-guide.md`)

### P1 Submodule Plans (implemented)

| Plan | Purpose |
|------|---------|
| `2026-05-29-p1-contracts-extension-plan.md` | `EditIntent`, `MaterialSpec`, `AgentRunLog`, variant registry |
| `2026-05-29-p1-model-gateway-plan.md` | ModelGateway, OpenAI-compatible + image/video/TTS adapters |
| `2026-05-29-p1-agent-orchestration-plan.md` | Agent runners, prompt wiring, remove rule pipelines |
| `2026-05-29-p1-llm-structure-analysis-plan.md` | `structure_analyst`, multimodal inputs, evidence UI data |
| `2026-05-29-p1-asset-understanding-plan.md` | `content_strategist`, visual tags, highlight moments |
| `2026-05-29-p1-semantic-mapping-gap-plan.md` | `slot_mapper`, `gap_planner`, provider selection |
| `2026-05-29-p1-aigc-material-completion-plan.md` | ImageGen, VideoGen, TTS, per-generation video quota |
| `2026-05-29-p1-hyperframes-material-plan.md` | `HyperFramesMaterialTool`, templates, `material_author` |
| `2026-05-29-p1-multi-variant-generation-plan.md` | Variant registry, parallel generation tasks |
| `2026-05-29-p1-nl-revise-plan.md` | `EditIntent`, revise API, incremental re-run |
| `2026-05-29-p1-web-workbench-plan.md` | Variant UI, gateway status, multi-task progress, evidence, NL bar |
| `2026-05-29-p1-observability-plan.md` | Model gateway status API, agent-runs, optional Langfuse sink |

**Locked P1 behaviors (no rule semantic fallback in production):**

- Sample structure extraction uses **`structure_analyst`** LLM Agent (perception facts from FFmpeg/OpenCV/Whisper remain algorithm inputs).
- Generation uses Agent pipeline for mapping, gap, storyboard, packaging; material completion via `hyperframes_material` / `image_generation` / `video_generation` / `tts`.
- **`VIDEOMAKER_FIXTURE_MODE=true`** — test/CI fixtures only; not a production fallback when live models fail.
- Default variants: **`high_click`** + **`high_conversion`**. Video generation quota: max **1** successful `video_generation` per `generationId` (configurable via env; see below).

### Post-P1 Extensions (also on `main`)

| Plan | Purpose | E2E checklist |
|------|---------|---------------|
| `2026-06-02-master-narration-layer-plan.md` | Full-video `masterNarration` before per-scene scripts (`storyboard_writer` 档 A) | covered in P1 demo § storyboard |
| `2026-06-03-knowledge-deposition-plan.md` | Karpathy-style structure skills, promote, recommend/bind, progressive disclosure in generation | `docs/demos/knowledge-deposition-e2e-checklist.md` |
| `2026-06-09-knowledge-category-template-bootstrap-plan.md` | Homepage category template discovery, detail sample pick (1+2 entries), import samples + bootstrap project | `docs/demos/knowledge-category-template-e2e-checklist.md` |
| `2026-06-04-multi-sample-analysis-plan.md` | Upload-batch, parallel analyze, sample selection, structure synthesis, generation runs | `docs/demos/multi-sample-e2e-test-plan.md` |
| `2026-06-07-direct-multimodal-sample-analysis-plan.md` | `videoUnderstanding` provider, direct multimodal sample analysis route, preferences toggle | `docs/demos/direct-multimodal-analysis-e2e-checklist.md` |
| `2026-06-07-direct-multimodal-asset-understanding-and-brief-v2-plan.md` | UserBrief v2, direct multimodal asset inventory analyst, text asset upload, legacy fallback | `docs/demos/direct-multimodal-asset-understanding-e2e-checklist.md` |
| `2026-06-06-sample-analysis-cost-resilience-plan.md` | Batch vision incremental persist/retry, keyframe sampling, segment vision dedup, analysis depth | `docs/demos/sample-analysis-depth-e2e-checklist.md` § 成本与韧性 |
| `2026-06-05-sample-analysis-depth-plan.md` | SampleFacts (audioProfile + batch vision), multi-pass structure v2, warnings checklist, knowledge/promote gate | `docs/demos/sample-analysis-depth-e2e-checklist.md` |
| `2026-06-08-sample-structure-output-v3-plan.md` | **p1-v3-only** VideoStructure, coercer v3 enrich, sample-analysis slim, promoteReady gate, four-track UI | `docs/superpowers/plans/2026-06-08-sample-structure-output-v3-plan.md` |
| `2026-06-08-narration-alignment-plan.md` | Global TTS, subtitle–WAV alignment, timeline `hold_tail`, DashScope WAV header fallback | `docs/demos/narration-alignment-e2e-checklist.md` |
| `2026-06-08-ffmpeg-render-backend-plan.md` | Default FFmpeg final MP4; HF for slot material + preview fallback | `docs/demos/ffmpeg-render-e2e-checklist.md` |
| `2026-06-08-composition-pattern-promote-plan.md` | Result 区 composition pattern 入库：skill + HTML 泛化 + relint；无 userScore | `docs/demos/composition-agent-e2e-checklist.md` § Pattern promote |
| HyperFrames Agent composition (in-repo) | `services/composition/` ReAct material author, `template=composition`, skill_view bootstrap, pattern deposit/promote | `docs/demos/composition-agent-e2e-checklist.md` |

## Current Implementation State

### Contracts (`packages/contracts`)

TypeScript types and JSON Schemas for:

- `ArtifactRef`, `ToolError`, `TaskEvent`
- `VideoStructure`, `AssetInventory`, `GapReport`, `GenerationPlan`, `RenderTimeline`
- P1: `EditIntent`, `MaterialSpec` (+ `CompositionFragment`, `template=composition`), `AgentRunLog`; variant registry (`variants/registry.yaml`)
- Knowledge: `KnowledgeEntry` (+ `entryKind: structure | composition_pattern`), `KnowledgeRecommendation`, `ProjectKnowledgeSelection`
- Multi-sample: `UploadBatch`, `SampleRecommendation`, `ProjectSampleSelection`, `StructureProvenance`, `GenerationRun`

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

### API (`services/api`)

FastAPI app factory: `app.main.create_app`. SQLite metadata in `services/api/storage/videomaker.sqlite3` (gitignored). Runtime artifacts under repo `storage/`.

**Task progress (authoritative in SQLite, SSE + polling on frontend):**

```http
GET /health
POST /api/tasks
GET /api/tasks/{task_id}
POST /api/tasks/{task_id}/events
GET /api/tasks/{task_id}/events
POST /api/tasks/{task_id}/retry
POST /api/tasks/{task_id}/cancel
```

`POST /api/tasks/{task_id}/retry` re-dispatches the worker for the same `task_id` with `resume=true` for sample analysis or generation. Do not create a new analyze task for retries.

**Projects and demo flow:**

```http
GET /api/projects
POST /api/projects
GET /api/projects/{project_id}
GET /api/projects/{project_id}/brief
POST /api/projects/{project_id}/brief
GET /api/projects/{project_id}/assets
POST /api/projects/{project_id}/assets/upload
GET /api/projects/{project_id}/samples
GET /api/projects/{project_id}/samples/active
POST /api/projects/{project_id}/samples/upload
POST /api/projects/{project_id}/samples/upload-batch
POST /api/projects/{project_id}/samples/analyze-batch
POST /api/projects/{project_id}/samples/recommend
GET /api/projects/{project_id}/samples/selection
PUT /api/projects/{project_id}/samples/selection
POST /api/projects/{project_id}/samples/selection/reset
GET /api/projects/{project_id}/upload-batches
POST /api/projects/{project_id}/samples/from-url
GET /api/projects/{project_id}/generation-runs
GET /api/projects/{project_id}/generation-runs/{run_id}
GET /api/projects/{project_id}/media/samples/{sample_id}
GET /api/projects/{project_id}/media/assets/{asset_id}
GET /api/projects/{project_id}/duration-recommendation
POST /api/projects/{project_id}/generation-plan
GET /api/projects/{project_id}/generations/latest
GET /api/settings/cookies
POST /api/settings/cookies/upload
GET /api/settings/model-gateway
PUT /api/settings/model-gateway
GET /api/settings/stock-media
PUT /api/settings/stock-media
POST /api/settings/stock-media/test
```

Per-project cookie routes under `/api/projects/{id}/cookies*` are deprecated; use global settings routes.

Model gateway provider credentials (base URL, model, encrypted API key) persist in SQLite table `model_gateway_providers`; encryption key file: `storage/global/model-gateway.key`. `GET` never returns secrets. `fixtureMode` in the response reflects env `VIDEOMAKER_FIXTURE_MODE` only (configure in the API process, not via PUT). Global preferences (e.g. `directMultimodalAnalysisEnabled`, default `true`) live in `model_gateway_preferences`; `analysisRoutePreview` is computed server-side from provider readiness + preference.

**Video generation (worker):** Configure a `video` provider in the workbench (DashScope: `baseUrl` e.g. `https://dashscope.aliyuncs.com/compatible-mode/v1`, models such as `wan2.6-i2v-flash` / `wan2.1-t2v-plus`). When `baseUrl` contains `dashscope`, the worker uses the `dashscope_wan` driver (`video-synthesis` + task poll). Otherwise set `VIDEO_DRIVER=generic_job` for a custom `POST /videos` job API.

| Env (worker) | Meaning | Default |
|--------------|---------|---------|
| `VIDEOMAKER_VIDEO_GEN_MAX_PER_SLOT` | Max successful video jobs per structure slot | `1` |
| `VIDEOMAKER_VIDEO_GEN_MAX_SLOTS` | Cap on slots that may consume video quota in one generation | structure visual weak/missing count (min 1) |
| `VIDEOMAKER_VIDEO_GEN_QUOTA` | Legacy alias for generation-level cap | — |
| `VIDEOMAKER_VIDEO_GEN_FALLBACK` | On video failure: `hyperframes_material` or `image_generation` | fail fast |
| `VIDEOMAKER_VISION_BATCH_SIZE` | Max keyframes per vision batch call during sample analysis | `8` |
| `VIDEOMAKER_VISION_BATCH_MAX_CALLS` | Safety cap on batch vision calls per sample | `6` (4 when `analysisDepth=fast`) |
| `VIDEOMAKER_VISION_BATCH_MIN_COVERAGE` | Minimum completed batch ratio to finish `extracting_visual_facts` after partial failures | `0.67` |
| `VIDEOMAKER_ANALYSIS_DEPTH` | Sample analysis depth: `auto`, `fast`, `standard`, or `deep` | `auto` → `standard` |
| `VIDEOMAKER_KEYFRAME_MAX_PER_VIDEO` | Hard cap on keyframes sent to LLM vision (overrides duration formula) | `min(30, max(12, round(durationSec/6)))` |
| `VIDEOMAKER_SHOT_MERGE_MAX_SEC` | Merge adjacent short shots before LLM keyframe sampling | `1.0` |
| `VIDEOMAKER_MIN_SHOT_DURATION_SEC` | OpenCV shot detection minimum cut interval | `0.45` |
| `VIDEOMAKER_SEGMENT_VISION_MIN_COVERAGE` | Skip segment-level vision when batch digest time coverage meets ratio | `0.6` |
| `VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_MB` | Max sample file size for direct multimodal structure analysis | `50` |
| `VIDEOMAKER_VIDEO_UNDERSTANDING_MAX_SEC` | Max sample duration for direct multimodal structure analysis | `300` |
| `VIDEOMAKER_ASSET_UNDERSTANDING_MAX_MEDIA_COUNT` | Max video/image attachments per direct multimodal asset call | `6` |
| `VIDEOMAKER_ASSET_UNDERSTANDING_MAX_TOTAL_MB` | Max total video/image MB per direct multimodal asset call | `80` |
| `VIDEOMAKER_ASSET_TEXT_MAX_CHARS` | Max UTF-8 chars read from text assets during understanding | `8000` |
| `VIDEO_DRIVER` | `dashscope_wan` or `generic_job` | auto from `baseUrl` |
| `VIDEO_MAX_POLL_SEC` | Async video task poll timeout | `600` |
| `VIDEOMAKER_SHORT_FORM_MAX_SEC` | Target duration ≤ this uses `short_form_direct` strategy | `60` |
| `VIDEOMAKER_DURATION_TARGET_MAX_SEC` | Max user-configurable target duration (seconds) | `600` |
| `VIDEOMAKER_SHORT_FORM_VIDEO_GEN` | Allow one full short-form `video_generation` job | `1` |
| `VIDEOMAKER_HUMAN_REVIEW_MODE` | Pause generation for master/storyboard approval (API default `true`; set `false` for CI/fixture one-shot) | `true` |
| `VIDEOMAKER_PEXELS_API_KEY` | Pexels API Authorization header for stock media search | empty (skip stock layer) |
| `VIDEOMAKER_STOCK_MEDIA_ENABLED` | Enable Pexels stock search in gap completion | `true` |
| `VIDEOMAKER_STOCK_MATCH_MIN_SCORE` | Minimum relevance score to accept a Pexels candidate | `0.55` |
| `VIDEOMAKER_STOCK_MAX_CANDIDATES` | Max Pexels results evaluated per query | `5` |
| `VIDEOMAKER_TTS_MODE` | TTS synthesis: `global` (single `master.wav`) or `per_scene` (`{slotId}.wav`) | unset → `long_form_composed` uses `global`, else `per_scene` |
| `VIDEOMAKER_NARRATION_TIMELINE_MODE` | After TTS: `hold_tail` (extend last scene), `ripple_overflow` (per-scene shift), or `scale_to_target` | `hold_tail` |
| `VIDEOMAKER_RENDER_BACKEND` | Final MP4: `ffmpeg`, `hyperframes`, or unset (auto: ffmpeg with HF fallback on effect/packaging text) | unset (auto) |
| `VIDEOMAKER_FFMPEG_RENDER_FPS` | FFmpeg render FPS for still→video and re-encode | `30` |
| `VIDEOMAKER_FFMPEG_VIDEO_CRF` | libx264 CRF for FFmpeg final encode | `23` |
| `VIDEOMAKER_FFMPEG_BGM_VOLUME` | BGM level in FFmpeg audio mix | `0.25` |
| `VIDEOMAKER_FFMPEG_TRANSITION_MODE` | Scene transitions: `cut`, `overlay_fade`, or `xfade` | `cut` |

Subtitles are rebuilt after material completion from voiceover WAV windows (not storyboard char-weight placeholders). Global TTS writes one `vo-master` clip; timeline may extend to `narrationDurationSec` when narration exceeds the planned duration.

Pexels API key also persists in SQLite `stock_media_providers` (encrypted with `storage/global/model-gateway.key`). Worker subprocesses receive `VIDEOMAKER_PEXELS_API_KEY` from API `pipeline_runner` when env is unset.

Gap completion priority for eligible visual slots (`usage_scene`, generic `hook_visual`; never `product_closeup`): user video weak match → `asset_reuse`; else when Pexels configured → `stock_media_search` (LLM `stock_query_author` + deterministic fallback); else `video_generation` / `image_generation`. Stock miss falls back to AIGC without failing the generation. Video weak matches → `asset_reuse` (trim only). `asset_reuse` rejects `type=image`.

**Samples, generations, and revise:**

```http
POST /api/samples/{sample_id}/analyze
GET /api/samples/{sample_id}/structure
GET /api/samples/{sample_id}/analysis
GET /api/samples/{sample_id}/sample-analysis
GET /api/samples/{sample_id}/keyframes
GET /api/generations/{generation_id}
GET /api/generations/{generation_id}/composition-patterns
GET /api/generations/{generation_id}/script-draft
PUT /api/generations/{generation_id}/script-draft
POST /api/generations/{generation_id}/approve-master
POST /api/generations/{generation_id}/approve-storyboard
POST /api/generations/{generation_id}/revise
GET /api/generations/{generation_id}/agent-runs
```

Generation with human review (default): worker pauses at `awaiting_master_review` and `awaiting_storyboard_review` with task `status=awaiting_review`. Approve routes update `script-draft.json` and call `POST /api/tasks/{task_id}/retry` (resume). Per-variant `script-draft.json` lives under `generations/{generationId}/`. Revise re-runs skip human review gates (`human_review_mode=false`).

Local dev server: `services/api/run-dev.ps1` (or `uvicorn` via project conventions).

```powershell
cd services/api
python -m pytest
python -m compileall app
```

`pyproject.toml` sets pytest `--basetemp=.pytest-tmp` because the default Windows temp path may be inaccessible in this environment.

### Worker (`services/worker`)

Pipelines and tools:

- **Perception:** `SampleAnalysisPipeline` — metadata, shots, Whisper ASR, keyframe extraction (algorithm inputs to Agents)
- **Sample analysis:** `p0_demo_pipeline.analyze_sample` — perception → **`structure_analyst`** LLM → `structure_coercer` validation → optional **`knowledge_author`** draft
- **Generation:** `generation_pipeline` — `content_strategist` → optional **`structure_synthesizer`** (multi-sample) → `slot_mapper` → `gap_planner` → **`storyboard_writer`** (two-phase master/storyboard when human review enabled) → user approval gates → `packaging_designer` → material completion (`short_form_direct` ≤60s or `long_form_composed`) → HyperFrames render
- **Revise:** `revise_pipeline` — `edit_intent_parser` + partial stage re-run
- **ModelGateway:** `app/gateway/` — OpenAI-compatible text/vision/TTS; pluggable image/video (DashScope Wan, etc.)
- **Agents:** `structure_analyst`, `content_strategist`, `slot_mapper`, `gap_planner`, `storyboard_writer`, `packaging_designer`, `material_author`, `knowledge_author`, `knowledge_selector`, `structure_synthesizer`, `edit_intent_parser`
- **Tools:** `ffmpeg_tool`, `opencv_tool`, `whisper_tool`, `ytdlp_tool`, `llm_tool`, `image_gen_tool`, `video_gen_tool`, `tts_tool`, `hyperframes_tool`
- **Render:** `render_timeline_to_hyperframes`, `composition_preview`, `ffmpeg_backend` (default final MP4), `hyperframes_backend` (fallback / slot material via `hyperframes_material_tool`)
- **Composition (thin adapter):** `app/composition/engine_factory.py` → `services/composition/` `CompositionEngine` for material author + build/lint/render + pattern deposit

HyperFrames slot material env (worker):

| Env | Meaning | Default |
|-----|---------|---------|
| `VIDEOMAKER_COMPOSITION_MODE` | `hybrid` (CompositionEngine) or `legacy` (old scaffold-only author) | `hybrid` |
| `VIDEOMAKER_COMPOSITION_AGENT_MODE` | `react` (tool loop), `single_shot`, or `legacy` | `react` |
| `VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS` | Max ReAct turns for material author | `5` |
| `VIDEOMAKER_COMPOSITION_SKIP_LINT` | Skip hyperframes lint before render | unset |
| `VIDEOMAKER_SKILL_VIEW_TOKEN_CAP` | Cumulative skill_view token cap per generation | `6000` |

Skills layout (repo root):

```text
skills/public/{skill-name}/SKILL.md     # HyperFrames official skills (hyperframes, gsap, registry, cli, …)
skills/private/videomaker-composition/  # VideoMaker MaterialSpec / shell constraints
storage/knowledge/{category}/{entryId}/ # structure + composition_pattern (composition-skill.md + spec.template.json + spec.instance.json)
storage/projects/{projectId}/knowledge/drafts/composition/{generationId}/{slotId}/
```

Composition pattern promote (方案 C): worker `mode=composition_pattern_promote` runs `prepare_promoted_pattern_bundle` (sanitize → `composition_pattern_author` LLM → build + relint; one LLM retry on lint failure) then API publishes to `storage/knowledge/{categorySlug}/comp-{generationId}-{slotId}/` with `spec.template.json` (generalized) + `spec.instance.json` (deposit archive). Promote request: `{ generationId, slotId, confirm: true }` only (no userScore). Workbench **CompositionPatternPromotePanel** lists draft-only HF slots after MP4 ready.

```powershell
cd services/composition
python -m pytest
python -m compileall composition
```

### Composition (`services/composition`)

Facade: `composition.api.CompositionEngine` — `author_material_spec`, `build_composition`, `lint_composition`, `render_clip`, `deposit_pattern_candidate`, `promote_pattern`. Skill bootstrap: `SkillCatalog` → `<available_skills>` + `skill_view` tool. Promote requires draft lint passed; `prepare_promoted_pattern_bundle` generalizes instance spec via `composition_pattern_author` before publish (no user score gate).

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

### HyperFrames CLI (repo root)

Full `output.mp4` render uses the HyperFrames CLI from the **repository root** (not only a global `npx` install):

```powershell
cd D:\VideoMaker
npm install
npm run hyperframes:version
npm run hyperframes:doctor
```

Worker resolves `node_modules/.bin/hyperframes` when present; override with `VIDEOMAKER_HYPERFRAMES_CMD`. API worker subprocesses get `node_modules/.bin` on `PATH` automatically.

Requires **Node.js >= 22** and **FFmpeg** on PATH.

### Web (`apps/web`)

Next.js workbench at `/projects` and `/projects/{projectId}`:

- Task progress: SSE primary, polling fallback (`useTaskProgress`); **MultiTaskProgressPanel** for dual-variant runs
- Panels: input (multi-upload, batch analyze), **sample selection**, **knowledge selection/draft**, progress, **SampleAnalysisPanel** (analyzed-sample master-detail), structure evidence (keyframe lightbox), structure slots, gap, **master narration**, **variant tabs/compare**, timeline, result, **CompositionPatternPromotePanel** (HF 分镜入库), **generation run history**, **NL revise**, **ModelGateway status**, **AgentRunsDrawer**
- Loads projects, samples, assets, brief, knowledge selection, sample selection, and latest generation from API on mount (not sessionStorage-only)

```powershell
cd apps/web
npm run typecheck
npm run test
npm run dev
```

Fixture fallback when API unreachable: `VIDEOMAKER_USE_FIXTURE_FALLBACK=true` (see `apps/web/lib/server/fixture-resolver.ts`).

### Checkpoint Resume (P0)

Worker pipelines persist stage checkpoints under stable business IDs (not `task_id`):

```text
storage/projects/{projectId}/
  samples/{sampleId}/analysis/checkpoint.json
  generations/{generationId}/checkpoint.json
```

Sample analysis artifacts live in `samples/{sampleId}/analysis/`. Generation stage JSON lives in `generations/{generationId}/`. The frontend retry button calls `POST /api/tasks/{taskId}/retry` and keeps the same SSE/polling task id.

Global yt-dlp cookies: `storage/global/cookies/` (shared across projects).

## Architecture Rules

Use these core contracts as module boundaries:

- `VideoStructure` is the authoritative result of sample structure extraction (**version `p1-v3` only**; blocks `context` / `verbal` / `visual` / `audio` / `transfer` + migration chain `narrative` / `rhythm` / `slots` / `evidence`). `sample-analysis.json` is slim by default; full audio/digest via `?include=audioFull,digestFull`.
- `AssetInventory` describes the user brief and available materials.
- `GapReport` describes matched, weak, and missing structure slots.
- `GenerationPlan` describes storyboard, completion actions, packaging, and timeline.
- `RenderTimeline` is the shared contract between frontend timeline preview and render backends.
- `TaskEvent` is the shared contract for long-task progress, SSE, and polling.

Do not bypass these contracts with ad hoc JSON shapes. If a contract must change, update schemas, TypeScript types, tests, and the relevant plan/spec notes together.

## Long Task Progress

```text
SQLite task/artifact state is authoritative.
SSE is the primary realtime channel.
Polling is the fallback and page-refresh recovery channel.
```

```http
GET /api/tasks/{task_id}/events
GET /api/tasks/{task_id}
```

The SSE route supports `?once=true` for tests and one-shot reads. Frontend clients should use default streaming behavior.

## Storage Rules

Runtime artifacts belong under:

```text
storage/projects/{projectId}/
storage/global/cookies/
storage/knowledge/                          # published global knowledge library
```

Project knowledge drafts (pre-promote):

```text
storage/projects/{projectId}/knowledge/drafts/{sampleId}/
  structure-skill.md
  video-structure.json
  entry-meta.json
```

Published entries:

```text
storage/knowledge/{categorySlug}/{entryId}/
  structure-skill.md          # structure entries
  video-structure.json
  composition-skill.md        # composition_pattern entries
  spec.template.json          # generalized MaterialSpec (relint passed)
  spec.instance.json          # deposit instance archive
  entry-meta.json
  lint-log.json
  provenance.json
  references/
```

Knowledge API (index in SQLite `knowledge_entries`, selection in `project_knowledge_selection`):

```http
GET /api/knowledge/entries
GET /api/knowledge/entries/{entry_id}
GET /api/knowledge/entries/{entry_id}/skill
GET /api/projects/{project_id}/samples/{sample_id}/knowledge-draft
POST /api/projects/{project_id}/samples/{sample_id}/knowledge/promote
POST /api/projects/{project_id}/knowledge/composition/promote
POST /api/projects/{project_id}/knowledge/recommend
GET /api/projects/{project_id}/knowledge/selection
PUT /api/projects/{project_id}/knowledge/selection
POST /api/projects/{project_id}/knowledge/selection/reset
POST /api/projects/{project_id}/structure-from-knowledge
```

Brief save and `POST .../generation-plan` call `ensure_selection` for knowledge and sample selection (see `docs/superpowers/plans/2026-06-03-knowledge-deposition-plan.md` and `docs/superpowers/plans/2026-06-04-multi-sample-analysis-plan.md`).

API-local runtime storage is ignored:

```text
services/api/storage/*
```

Do not commit generated videos, SQLite databases, temp files, model outputs, or runtime artifacts. Register artifacts through `ArtifactStore` and persist only references in SQLite.

### Path segment validation (security)

User-controlled or API-supplied IDs that become filesystem path segments (`projectId`, `generationId`, `slotId`, `sampleId`, `entryId`, `categorySlug`, etc.) **must not** be concatenated into `Path(...)` without validation. Prefer shared helpers over ad hoc string joins.

**Canonical helpers** (`services/shared/knowledge/paths.py`):

| Helper | Purpose |
|--------|---------|
| `validate_storage_segment(value, field=...)` | Reject unsafe segment before path construction |
| `assert_under_storage_root(path, storage_root)` | After join, ensure resolved path stays under storage root |
| `resolve_storage_path(storage_root, relative_uri)` | Resolve storage-relative URIs (reject `..` escape) |
| `published_entry_dir(...)` | Published knowledge entry dir; validates slug + entry id |

**Project-scoped artifacts:** `ArtifactStore.resolve_project_path(project_id, relative_path)` (API) applies the same confinement under `storage/projects/{projectId}/`.

**Composition pattern drafts/publish:** `composition_draft_dir`, `composition_drafts_generation_dir`, and `composition_pattern_entry_id` in `services/composition/composition/patterns/deposit.py` call `validate_storage_segment` + `assert_under_storage_root`.

**Segment rules** (`validate_storage_segment`):

- Non-empty, max 128 chars
- Charset: `^[A-Za-z0-9._-]+$` (letters, digits, `.`, `_`, `-`)
- Reject `.`, `..`, any `..` substring, `/`, `\`
- On violation: raise `ValueError("invalid_{field}")` (API maps to HTTP 422)
- After path join: `assert_under_storage_root` → `ValueError("path_escape_storage_root")`

**When adding routes or storage writers:** validate every external id at the API/service boundary; never trust client JSON or URL params in raw `Path / user_input`. Structure UUID `entryId` values from promote are fine (hyphens only). Fixed composition entry ids use `comp-{generationId}-{slotId}` with both parts validated separately.

## Worktree And Branch Workflow

Use isolated worktrees for feature work. Do not implement substantial features directly on `main`.

P0 and P1 feature branches listed above are merged; new work should start from current `main` with a new `feature/<name>` or `integration/<name>` branch.

```powershell
git worktree add .worktrees/<name> -b feature/<name> main
```

Ensure `.worktrees/` remains ignored.

## Post-P1 Development

When extending beyond the current P1 + post-P1 extensions on `main`:

1. Read `docs/superpowers/specs/2026-05-27-videomaker-design.md` for boundaries.
2. Use `docs/superpowers/plans/P0/` and P1 plans under `docs/superpowers/plans/2026-05-29-p1-*` for how the current system works; add new plans under `docs/superpowers/plans/YYYY-MM-DD-<module-name>-plan.md`.
3. Do not parallelize schema changes casually — update `packages/contracts` first, then dependents.
4. Run module verification (below) before claiming work is done.

Likely next themes (not yet planned here): async job queue, production auth, full timeline editor / NLE, music generation, PostgreSQL / object storage migration, Langfuse production rollout.

## Testing Expectations

Use TDD for implementation work. Write tests first, confirm they fail for the expected reason, then implement the minimum code to pass.

Before claiming a module is done, run the relevant verification commands:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas
```

```powershell
cd services/api
python -m pytest
python -m compileall app
```

```powershell
cd services/worker
python -m pytest
python -m compileall app
```

```powershell
cd apps/web
npm run typecheck
npm run test
```

Document new module-specific commands in the subsystem plan file.

## Code Style And Safety

- Keep module boundaries narrow and contract-driven.
- Prefer small focused files over large mixed-responsibility files.
- Do not commit runtime artifacts or generated media.
- Do not let LLM output execute code.
- Validate model/agent JSON output against schemas before use.
- Do not copy sample video content; migrate structure and creative method only.
- Avoid broad refactors unrelated to the active plan.
- **Storage path security:** any user/API-supplied id used as a path segment must go through `validate_storage_segment` (or an equivalent confining helper); see Storage Rules § Path segment validation.

## Notes For New AI Sessions

When starting a new session:

1. Read this file first.
2. Read `docs/superpowers/specs/2026-05-27-videomaker-design.md`.
3. For P0 behavior, read the relevant plan in `docs/superpowers/plans/P0/` (or the master P0 plan).
4. For P1 behavior, read `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md` and the relevant `2026-05-29-p1-*` sub-plan; for knowledge / multi-sample / master narration, read the `2026-06-0*` extension plans.
5. For new features, read or write the active plan under `docs/superpowers/plans/`.
6. Check `git status --short`.
7. Use a feature worktree unless the user explicitly asks for a small docs-only change on `main`.
8. Run existing tests before and after changes.
9. Keep commits scoped to the task.

## Plan Quality Gate

Subsystem plans are executable specifications, not lightweight outlines. Before handing a plan to a new AI session, confirm it states:

- Exact user-facing P0 flows owned by the module.
- Exact API routes, request shapes, or artifact shapes the module consumes or produces.
- Concrete algorithms for nontrivial processing, especially video shot detection, keyframe selection, timeline conversion, and slot matching.
- Tool collaboration order and fallback behavior when optional binaries or model services are missing.
- Files allowed to change and files explicitly out of scope.
- Tests that prove both happy path and fallback/error behavior.

Do not hand off a plan that leaves core behavior to "decide during implementation." If a plan is intentionally deferring a capability to integration, it must name the integration plan and the exact route/artifact that will complete it.
