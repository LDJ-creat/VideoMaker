# VideoMaker P1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade VideoMaker from P0 deterministic demo to P1 production-intelligence: real LLM-driven structure analysis and generation, pluggable multi-provider ModelGateway, AIGC material completion (image + video + TTS), HyperFrames as a first-class material generator, two configurable generation variants (`high_click`, `high_conversion`), and natural-language revise — with no rule-based semantic fallback.

**Architecture:** Keep P0 module boundaries and core contracts (`VideoStructure`, `AssetInventory`, `GapReport`, `GenerationPlan`, `RenderTimeline`). Replace deterministic semantic pipelines with a constrained multi-Agent orchestration layer backed by a thin `ModelGateway` (OpenAI-compatible adapters for text/vision/TTS; pluggable adapters for image/video). Perception facts (FFmpeg, OpenCV, Whisper) remain algorithm inputs to Agents, not fallbacks. Material completion uses four providers: `hyperframes_material`, `image_generation`, `video_generation`, `tts`. Failures surface as structured `ToolError`; tasks retry via existing checkpoint resume.

**Tech Stack:** Next.js, TypeScript, FastAPI, Python, SQLite, JSON Schema, HyperFrames CLI, httpx, existing worker/API task+SSE infrastructure, external model APIs via ModelGateway.

**Spec references:**

- `docs/superpowers/specs/2026-05-27-videomaker-design.md` (§2.2 P1, §6–8 Agents/Tools, §16 extension points)
- `VideoMaker.md` (P1 tasks 9–13)
- P0 archive: `docs/superpowers/plans/P0/`

---

## 1. Locked P1 Decisions

These decisions are fixed for P1 execution. Sub-plans must not contradict them.

| Topic | Decision |
| --- | --- |
| ModelGateway | Self-built thin gateway. **No LiteLLM.** Text, vision, TTS via OpenAI-compatible HTTP adapter; image and video each via one pluggable provider adapter (config-driven). |
| Semantic fallback | **None.** Remove P0 rule-based semantic pipelines (`structure_pipeline`, deterministic slot/gap/storyboard rules). LLM/AIGC failure → task `failed` with explicit error. |
| Test fixtures | `LLMTool.fixture_mode` and recorded JSON fixtures remain **test/CI only**, not production fallback. |
| Perception layer | Keep FFmpeg / OpenCV / Whisper / keyframe extraction as factual inputs (`SampleAnalysisResult`). |
| Default variants | Ship **`high_click`** and **`high_conversion`** only. Design variant registry so more variants can be enabled without code changes. |
| Video generation quota | **Max 1** external `video_generation` call per `generationId`. |
| HyperFrames role | **Dual role:** (1) clip-level material generation via `HyperFramesMaterialTool`; (2) final timeline composition render via existing `HyperFramesRenderBackend`. |
| NL revise | **In scope for P1.** Implement `EditIntent` + `POST /api/generations/{id}/revise` + workbench UI. |

---

## 2. P1 Scope Summary

### 2.1 In Scope

1. **ModelGateway** with five capability providers and unified logging/metrics.
2. **LLM Agent pipeline** for structure analysis, asset understanding, slot mapping, gap planning, storyboard, packaging.
3. **AIGC tools:** image generation, video generation (quota 1), TTS.
4. **HyperFrames material generation** for packaging/motion-graphic slots.
5. **Two-variant generation** via registry-driven `agentOverrides`.
6. **Natural-language revise** with partial pipeline re-run.
7. **Frontend** upgrades: evidence display, AIGC previews, variant tabs, NL input, edit diff.
8. **Remove** P0 deterministic semantic code paths; migrate tests to Agent fixtures.
9. **Optional late P1:** LangfuseSink behind `ObservabilitySink` interface.

### 2.2 Out of Scope (P1)

1. Full timeline editor / NLE.
2. Multi-user collaboration.
3. Music generation.
4. Knowledge-base auto-merge and long-term learning.
5. PostgreSQL / object storage migration.
6. More than two **default enabled** variants (registry may list future variants as `enabled: false`).

---

## 3. Submodule Plans

Each row below has an executable sub-plan under `docs/superpowers/plans/`. See **`2026-05-29-p1-execution-order-and-prompts.md`** for wave order, parallel groups, and copy-paste session prompts.

| Sub-plan file | Owns | Depends on |
| --- | --- | --- |
| `2026-05-29-p1-contracts-extension-plan.md` | Schemas/types: `EditIntent`, `MaterialSpec`, `AgentRunLog`, variant registry, contract extensions | — |
| `2026-05-29-p1-model-gateway-plan.md` | `ModelGateway`, OpenAI-compatible + image/video adapters, env config | contracts |
| `2026-05-29-p1-agent-orchestration-plan.md` | Agent runners, prompt wiring, remove rule pipelines, `agent_runs` persistence | gateway, contracts |
| `2026-05-29-p1-llm-structure-analysis-plan.md` | StructureAnalyst, multimodal inputs, evidence UI data | agent orchestration |
| `2026-05-29-p1-asset-understanding-plan.md` | ContentStrategist, visual tags, highlight moments | agent orchestration |
| `2026-05-29-p1-semantic-mapping-gap-plan.md` | SlotMapper, GapPlanner, provider selection | agent orchestration |
| `2026-05-29-p1-aigc-material-completion-plan.md` | ImageGen, VideoGen, TTS tools, quota enforcement | gateway, contracts |
| `2026-05-29-p1-hyperframes-material-plan.md` | `HyperFramesMaterialTool`, templates, MaterialAuthor | hyperframes render patterns |
| `2026-05-29-p1-multi-variant-generation-plan.md` | Variant registry, parallel generation tasks, API + **frontend contract** | semantic mapping, material completion |
| `2026-05-29-p1-nl-revise-plan.md` | EditIntent parser, IntentApplier, revise API, incremental stages | agent orchestration |
| `2026-05-29-p1-web-workbench-plan.md` | Variant UI, **gateway status**, **multi-task progress**, **artifact preview**, NL bar, evidence, diff | API routes from above |
| `2026-05-29-p1-observability-plan.md` | **Model gateway status API (required)**, agent-runs, optional LangfuseSink | agent orchestration, model-gateway |

---

## 4. Execution Phases

```text
P1-0  Foundation (week 1–2)
  contracts extension + ModelGateway + delete rule semantic pipelines + Agent skeleton

P1-1  Intelligence (week 2–4)
  StructureAnalyst + asset understanding + SlotMapper + GapPlanner (all LLM)

P1-2  Material & packaging (week 4–6)
  hyperframes_material + image_generation + video_generation (quota 1) + tts
  PackagingDesigner + clip assembly into RenderTimeline

P1-3  Variants & revise (week 6–7)
  high_click + high_conversion registry + parallel generation
  EditIntent + revise API + workbench NL UI

P1-4  Hardening (week 7–8)
  integration tests, demo script, observability, remove dead P0 rule code
```

---

## 5. File Structure To Create Or Modify

### 5.1 New packages / worker modules

```text
packages/contracts/
  schemas/edit-intent.schema.json
  schemas/material-spec.schema.json
  schemas/agent-run-log.schema.json
  variants/registry.yaml
  src/variants.ts

packages/prompts/agents/
  structure_analyst.md          # expand multimodal instructions
  content_strategist.md         # NEW
  slot_mapper.md                # expand semantic matching
  gap_planner.md                # expand provider selection
  storyboard_writer.md
  packaging_designer.md
  material_author.md            # NEW — HyperFrames MaterialSpec
  edit_intent_parser.md         # NEW
  critique_reviser.md           # NEW (optional P1 late)

services/worker/app/
  gateway/
    __init__.py
    model_gateway.py
    providers/
      base.py
      openai_compatible_text.py
      openai_compatible_vision.py
      openai_compatible_tts.py
      openai_compatible_image.py   # default image adapter
      pluggable_video.py           # default video adapter (config driver name)
  agents/
    __init__.py
    runner.py
    structure_analyst.py
    content_strategist.py
    slot_mapper.py
    gap_planner.py
    storyboard_writer.py
    packaging_designer.py
    material_author.py
    edit_intent_parser.py
  providers/
    __init__.py
    completion_registry.py
    hyperframes_material_provider.py
    image_generation_provider.py
    video_generation_provider.py
    tts_provider.py
    asset_reuse_provider.py
  tools/
    image_gen_tool.py
    video_gen_tool.py
    tts_tool.py
    hyperframes_material_tool.py
  pipelines/
    generation_pipeline.py      # rewrite — Agent orchestration
    p1_generation_pipeline.py   # optional rename from p0_demo_pipeline
    sample_pipeline.py          # keep perception stages; structure stage → Agent

services/api/app/
  routers/generations.py        # revise, multi-variant
  routers/agent_runs.py         # optional debug
  db/schema.sql                 # agent_runs columns if needed

apps/web/features/
  generation-variants/
  nl-revise/
  aigc-preview/
  structure-evidence/
```

### 5.2 Files to remove or gut (after Agent path passes tests)

```text
services/worker/app/pipelines/structure_pipeline.py     # DELETE
services/worker/tests/test_structure_pipeline.py        # REPLACE with agent tests
Deterministic-only helpers in generation_pipeline.py    # DELETE rule branches
packages/prompts/agents/gap_planner.md                  # remove P0-only strategy list
```

### 5.3 Files explicitly out of scope

```text
services/api/storage/*
storage/projects/**           # runtime artifacts — never commit
Full NLE / timeline editor components
LiteLLM dependency
```

---

## 6. ModelGateway Design

### 6.1 Interface

```python
# services/worker/app/gateway/model_gateway.py (conceptual)

class ModelGateway:
    def complete_json(self, task: str, inputs: dict, schema_name: str, *, profile: str = "text") -> dict: ...
    def complete_text(self, task: str, inputs: dict, *, profile: str = "text") -> str: ...
    def generate_image(self, prompt: str, *, options: dict) -> ArtifactRef: ...
    def submit_video_job(self, prompt: str, *, options: dict) -> str: ...
    def poll_video_job(self, job_id: str) -> VideoJobResult: ...
    def synthesize_speech(self, text: str, *, options: dict) -> ArtifactRef: ...
```

Cross-cutting behavior on every call:

1. Timeout and retry (max 2 retries on `retryable` HTTP errors).
2. Record `AgentRunLog` / tool metrics: model name, latency, token usage if available.
3. Never bypass schema validation in `LLMTool` / Agent runner.

### 6.2 Provider configuration

Environment-driven YAML or `.env` + Python settings (no secrets in repo):

```yaml
gateway:
  text:
    driver: openai_compatible
    base_url: ${TEXT_API_BASE}
    api_key_env: TEXT_API_KEY
    default_model: ${TEXT_MODEL}
  vision:
    driver: openai_compatible
    base_url: ${VISION_API_BASE}      # may equal TEXT_API_BASE
    api_key_env: VISION_API_KEY
    default_model: ${VISION_MODEL}
  tts:
    driver: openai_compatible
    base_url: ${TTS_API_BASE}
    api_key_env: TTS_API_KEY
    default_model: ${TTS_MODEL}
  image:
    driver: openai_compatible         # or named driver e.g. jimeng
    base_url: ${IMAGE_API_BASE}
    api_key_env: IMAGE_API_KEY
    default_model: ${IMAGE_MODEL}
  video:
    driver: ${VIDEO_DRIVER}           # pluggable: kling, runway, etc.
    base_url: ${VIDEO_API_BASE}
    api_key_env: VIDEO_API_KEY
    default_model: ${VIDEO_MODEL}
    max_poll_sec: 300
```

### 6.3 LLMTool integration

Modify `services/worker/app/tools/llm_tool.py`:

- Production: `fixture_mode=False`, delegate to `ModelGateway.complete_json`.
- Tests: `fixture_mode=True`, load JSON from `tests/fixtures/agents/{task}.json`.
- On validation failure: raise `LLMToolValidationError` (no rule fallback).
- On provider failure: raise with `ToolError.retryable` from gateway.

---

## 7. Agent Pipeline (Replaces Rule Semantics)

### 7.1 Sample analysis → VideoStructure

**Stage flow (worker):**

```text
sample_pipeline (unchanged perception)
  → extract metadata, audio, transcribe, shots, keyframes
  → StructureAnalystAgent
  → validate VideoStructure schema
  → persist artifact + checkpoint
```

**StructureAnalyst inputs:**

```json
{
  "metadata": { "...": "..." },
  "transcript": [{ "startSec": 0, "endSec": 2.1, "text": "..." }],
  "shots": [{ "startSec": 0, "endSec": 1.4, "changeReason": "scene_change" }],
  "keyframes": [{ "shotId": "shot-1", "timeSec": 0.7, "imageRef": "artifact://..." }]
}
```

**Rules (prompt + post-check, not fallback generation):**

1. Prompt forbids copying sample script verbatim; migrate method only.
2. Every `NarrativeSegment` and `StructureSlot` must cite `StructureEvidence` from transcript, shot, or keyframe.
3. Post-validator rejects segments with zero evidence refs.
4. On Agent failure → task stage `extracting_structure` fails.

### 7.2 Generation pipeline

```text
ContentStrategist → AssetInventory enrichment
SlotMapper → slotMatches (+ matchReason)
GapPlanner → missing/weak + CompletionAction[] with provider
Material execution:
  hyperframes_material | image_generation | video_generation | tts | asset_reuse
StoryboardWriter → storyboard
PackagingDesigner → packagingPlan
Timeline builder → RenderTimeline
HyperFramesRenderBackend → preview/output
```

Each stage writes checkpoint under `storage/projects/{projectId}/generations/{generationId}/checkpoint.json`.

---

## 8. Material Completion

### 8.1 Provider registry

Implement `CompletionStrategyProvider` in `services/worker/app/providers/completion_registry.py`:

| Provider name | Tool | Output |
| --- | --- | --- |
| `asset_reuse` | ffmpeg/opencv | trimmed clip or still |
| `hyperframes_material` | `HyperFramesMaterialTool` | `generated/{clipId}.mp4` |
| `image_generation` | `ImageGenTool` | `generated/{imageId}.png` |
| `video_generation` | `VideoGenTool` | `generated/{videoId}.mp4` |
| `tts` | `TTSTool` | `generated/{audioId}.wav` |

### 8.2 HyperFrames material generation

**`MaterialSpec` contract (summary):**

```json
{
  "template": "benefit-card" | "title-lower-third" | "ken-burns" | "custom",
  "durationSec": 3.0,
  "params": {
    "title": "…",
    "bullets": ["…"],
    "colors": { "primary": "#…" },
    "assetRefs": ["artifact://…"]
  }
}
```

**Flow:**

1. `MaterialAuthor` Agent (or PackagingDesigner) emits `MaterialSpec`.
2. `HyperFramesMaterialTool` renders template → isolated composition dir → `npx hyperframes render` → clip artifact.
3. `TimelineClip.sourceRef` points to clip; `generatedBy` records template + prompt version.

**Security:** Agents never emit arbitrary executable JS. `custom` template still passes through allowlisted HTML scaffold (same boundary as `write_composition`).

### 8.3 External AIGC

- **Image:** default for realistic `hook_visual`, `product_closeup`, `usage_scene` when no user asset.
- **Video:** max **1** call per generation; only when slot role ∈ `{ hook_visual, product_closeup }` AND `importance = must_have` AND `impact = high`.
- **TTS:** voiceover tracks when scriptIntent requires narration and no user audio.

### 8.4 Provider selection algorithm (GapPlanner)

Execute in order for each missing/weak slot:

```text
1. If user asset or moment can cover slot (SlotMapper weak match score ≥ 0.38):
     → asset_reuse (crop/reframe/reorder)

2. Else if slot.role ∈ { hook_text, benefit_card, comparison } OR requiredAssetType includes packaging:
     → hyperframes_material

3. Else if slot.role ∈ { hook_visual, product_closeup, usage_scene }:
     a. If video_generation quota remaining AND importance must_have AND impact high:
          → video_generation (consume quota)
     b. Else:
          → image_generation
     c. If image exists and slot needs motion:
          → hyperframes_material (ken-burns template) wrapping image

4. Else if scriptIntent needs spoken narration:
     → tts

5. Else:
     → hyperframes_material (text-forward card)

Hard limits:
- video_generation count per generationId ≤ 1 (enforce in worker before tool call).
- If video_generation fails → task fails (no rule fallback).
```

Log each decision in `CompletionAction.rationale` for frontend explainability.

---

## 9. Generation Variants

### 9.1 Registry

File: `packages/contracts/variants/registry.yaml`

```yaml
variants:
  high_click:
    label: 高点击版
    enabled: true
    description: 更强 hook、更快节奏、前 3 秒信息密度更高
    agentOverrides:
      storyboard_writer:
        hookStrength: high
        tempo: fast
        subtitleDensity: medium
      gap_planner:
        preferProviders: [hyperframes_material, video_generation]
        videoGenPriority: high
  high_conversion:
    label: 高转化版
    enabled: true
    description: 卖点提前、proof/CTA 加重、包装偏卖点卡
    agentOverrides:
      storyboard_writer:
        sellingPointOrder: early
        ctaWeight: high
        subtitleDensity: high
      gap_planner:
        preferProviders: [hyperframes_material, image_generation]
        videoGenPriority: low
  fast_paced:
    label: 高节奏版
    enabled: false
  premium:
    label: 高质感版
    enabled: false
```

TypeScript loader validates registry at build time; API rejects unknown or disabled variant IDs.

### 9.2 API behavior

```http
POST /api/projects/{projectId}/generation-plan
Content-Type: application/json

{
  "variants": ["high_click", "high_conversion"]
}
```

Response creates **two** generation records and **two** task IDs (or one orchestrator task with sub-stages — sub-plan must pick one pattern and document SSE stages).

Default when `variants` omitted: `["high_click", "high_conversion"]`.

Each variant gets distinct `generationId`; shared inputs: latest `VideoStructure`, `AssetInventory`, `GapReport` base.

---

## 10. Natural Language Revise

### 10.1 EditIntent contract (summary)

```json
{
  "intents": [
    {
      "target": "generation_plan.storyboard" | "render_timeline" | "generation_params",
      "operation": "adjust_hook" | "reduce_subtitles" | "reorder_selling_points" | "change_pace" | "…",
      "params": { "strength": "high" },
      "rationale": "用户希望开头更抓人"
    }
  ]
}
```

### 10.2 API

```http
POST /api/generations/{generationId}/revise
Content-Type: application/json

{ "instruction": "开头更抓人一些，字幕少一点" }
```

Behavior:

1. Load source generation artifacts.
2. `EditIntentParser` Agent → `EditIntent[]`.
3. `IntentApplier` computes affected stages (minimum: storyboard, packaging, material, timeline, render).
4. New `generationId` (never overwrite source).
5. Return `{ generationId, taskId, intents }`.

### 10.3 Frontend (workbench)

- NL input bar on generation/result panel.
- Show parsed intents before/during task.
- Side-by-side or diff view for timeline/storyboard changes.

---

## 11. API Additions And Changes

| Method | Route | Purpose |
| --- | --- | --- |
| POST | `/api/projects/{id}/generation-plan` | Accept `variants: string[]` |
| POST | `/api/generations/{id}/revise` | NL revise → new generation |
| GET | `/api/generations/{id}/agent-runs` | Debug: Agent call history |
| GET | `/api/settings/model-gateway` | **P1 required:** provider configured status (no secrets) |

Existing routes unchanged unless noted in sub-plans. Retry remains `POST /api/tasks/{taskId}/retry` with same LLM path.

---

## 12. TaskEvent Stage Extensions

Add stages to worker emissions (contracts sub-plan must update schema):

```text
running_agent
generating_material
generating_image
generating_video
generating_tts
rendering_material
parsing_edit_intent
applying_edit_intent
```

Update progress weights in generation task (suggested):

```text
analyzing_assets       10%
mapping_slots          10%
planning_completion    10%
generating_material    25%   # includes AIGC + HF clips
generating_storyboard  15%
building_timeline      10%
rendering              20%
```

---

## 13. Development Order

### 13.1 Must be sequential

1. **P1 contracts extension** before gateway and frontend variant types.
2. **ModelGateway** before any live Agent work.
3. **Agent orchestration + remove rule pipelines** before integration demo.
4. **Material providers** before multi-variant render quality pass.
5. **Revise API** after base generation pipeline stable.

### 13.2 Parallel streams (after P1-0 merges to integration branch)

| Stream | Branch | Can parallel with |
| --- | --- | --- |
| `feature/p1-model-gateway` | gateway + llm_tool | contracts |
| `feature/p1-agent-orchestration` | agents, delete rules | gateway (after gateway MVP) |
| `feature/p1-aigc-material` | image/video/tts/hf material | agent orchestration |
| `feature/p1-multi-variant` | registry + API | web (mocked) |
| `feature/p1-nl-revise` | edit intent | web (mocked) |
| `feature/p1-web-workbench` | UI | all (fixtures first) |

### 13.3 Recommended merge order

```text
1. feature/p1-contracts-extension
2. feature/p1-model-gateway
3. feature/p1-agent-orchestration
4. feature/p1-llm-structure-analysis (may merge with 3)
5. feature/p1-asset-understanding + feature/p1-semantic-mapping-gap
6. feature/p1-aigc-material + feature/p1-hyperframes-material
7. feature/p1-multi-variant-generation
8. feature/p1-nl-revise
9. feature/p1-web-workbench
10. integration/p1-demo-flow
```

---

## 14. Worktree Setup

```powershell
git checkout main
git pull

git worktree add .worktrees/p1-gateway -b feature/p1-model-gateway main
git worktree add .worktrees/p1-agents -b feature/p1-agent-orchestration main
git worktree add .worktrees/p1-aigc -b feature/p1-aigc-material main
git worktree add .worktrees/p1-web -b feature/p1-web-workbench main
```

Requires `.worktrees/` in `.gitignore` (already P0 convention).

---

## 15. Master Task Checklist

### Task 1: P1 contracts extension

**Owner sub-plan:** `2026-05-29-p1-contracts-extension-plan.md`

- [ ] Add `edit-intent.schema.json`, `material-spec.schema.json`, `agent-run-log.schema.json`
- [ ] Extend `CandidateMoment`, `CompletionAction`, `TimelineClip.generatedBy`
- [ ] Add `packages/contracts/variants/registry.yaml` + TS loader
- [ ] Run `npm run check` and `npm run validate:schemas`

### Task 2: ModelGateway

**Owner sub-plan:** `2026-05-29-p1-model-gateway-plan.md`

- [ ] Implement OpenAI-compatible text/vision/TTS/image adapters (httpx)
- [ ] Implement pluggable video adapter (submit + poll)
- [ ] Wire `LLMTool` to gateway; keep fixture mode for tests
- [ ] Unit tests with mocked HTTP; integration tests gated `@pytest.mark.integration`

### Task 3: Agent orchestration; remove rule semantics

**Owner sub-plan:** `2026-05-29-p1-agent-orchestration-plan.md`

- [ ] Implement `AgentRunner` with prompt loading from `packages/prompts/agents/`
- [ ] Replace `extract_video_structure` call chain with StructureAnalyst
- [ ] Delete `structure_pipeline.py` and deterministic generation branches
- [ ] Persist `agent_runs` per call
- [ ] Migrate worker tests to agent JSON fixtures

### Task 4: LLM structure analysis

**Owner sub-plan:** `2026-05-29-p1-llm-structure-analysis-plan.md`

- [ ] Multimodal keyframe packaging for vision model
- [ ] Evidence post-validation
- [ ] API unchanged (`GET .../structure`); artifact quality upgraded

### Task 5: Asset understanding

**Owner sub-plan:** `2026-05-29-p1-asset-understanding-plan.md`

- [ ] ContentStrategist for brief → `ContentFact[]`
- [ ] Visual tagging and highlight scoring on user video shots
- [ ] `candidateMoments.suggestedSegmentRoles`

### Task 6: Semantic mapping and gap planning

**Owner sub-plan:** `2026-05-29-p1-semantic-mapping-gap-plan.md`

- [ ] SlotMapper with natural-language `matchReason`
- [ ] GapPlanner with provider selection algorithm (§8.4)
- [ ] Hard validation: type/duration constraints after LLM output

### Task 7: AIGC + HyperFrames material

**Owner sub-plans:** `2026-05-29-p1-aigc-material-completion-plan.md`, `2026-05-29-p1-hyperframes-material-plan.md`

- [ ] ImageGenTool, VideoGenTool, TTSTool
- [ ] Enforce `video_generation` quota = 1 per generationId
- [ ] HyperFramesMaterialTool + templates: benefit-card, title-lower-third, ken-burns
- [ ] MaterialAuthor Agent → MaterialSpec
- [ ] Clips wired into RenderTimeline

### Task 8: Multi-variant generation

**Owner sub-plan:** `2026-05-29-p1-multi-variant-generation-plan.md`

- [ ] Default variants `high_click`, `high_conversion`
- [ ] API accepts `variants[]`; parallel tasks
- [ ] PackagingDesigner per variant

### Task 9: Natural language revise

**Owner sub-plan:** `2026-05-29-p1-nl-revise-plan.md`

- [ ] EditIntentParser Agent
- [ ] IntentApplier + partial stage re-run
- [ ] `POST /api/generations/{id}/revise`
- [ ] New generationId; checkpoint compatible

### Task 10: Web workbench P1

**Owner sub-plan:** `2026-05-29-p1-web-workbench-plan.md`

**Phase A (early):**

- [ ] VariantPicker + VariantTabs + evidence + NL revise (fixtures)
- [ ] apiClient + fixture-resolver for P1 routes

**Phase B (after multi-variant + model-gateway status API):**

- [ ] Full P1 TaskStage Chinese labels (`stageLabels.ts`)
- [ ] ModelGatewayStatusPanel (read-only diagnostics)
- [ ] TaskArtifactPreview + MultiTaskProgressPanel
- [ ] AgentRunsDrawer (optional)
- [ ] P1 formatTaskError codes

### Task 11: Integration and demo

- [ ] End-to-end: sample → LLM structure → dual variant generation → NL revise → render
- [ ] Update `docs/demos/p0-demo-checklist.md` or add `docs/demos/p1-demo-checklist.md`
- [ ] Remove dead P0 rule code and tests

### Task 12: Observability

**Owner sub-plan:** `2026-05-29-p1-observability-plan.md`

- [ ] **Required:** `GET /api/settings/model-gateway` (no secrets)
- [ ] `GET /api/generations/{id}/agent-runs`
- [ ] Optional LangfuseSink behind env flag

---

## 16. Test And Verification Matrix

Run before claiming P1 complete:

```powershell
cd packages/contracts
npm run check
npm run validate:schemas

cd ../../services/api
python -m pytest
python -m compileall app

cd ../worker
python -m pytest
python -m compileall app

cd ../../apps/web
npm run typecheck
npm run test
```

Integration (requires API keys, mark separately):

```powershell
cd services/worker
python -m pytest -m integration
```

**CI default:** all tests use `fixture_mode=True`; no network.

---

## 17. P1 Demo Checklist

1. Upload sample video → LLM structure with narrative/rhythm/packaging/slots and **evidence** on keyframes/transcript.
2. Enter product brief + mixed user assets → asset tags and **recommended hook/mid/cta moments**.
3. Show slot mapping with semantic **matchReason**; show gaps with chosen provider per slot.
4. Generate **高点击版** and **高转化版**; compare storyboard/timeline side by side.
5. Demonstrate **one** AI-generated video clip (quota) and HyperFrames-generated benefit card.
6. TTS voiceover audible in final demo.
7. NL command: 「开头更抓人，字幕少一点」→ new generation with visible intent + diff.
8. Retry failed task resumes from checkpoint (same LLM path).

---

## 18. Environment Variables

```text
# Text / vision / TTS / image (OpenAI-compatible)
TEXT_API_BASE=
TEXT_API_KEY=
TEXT_MODEL=
VISION_API_BASE=
VISION_API_KEY=
VISION_MODEL=
TTS_API_BASE=
TTS_API_KEY=
TTS_MODEL=
IMAGE_API_BASE=
IMAGE_API_KEY=
IMAGE_MODEL=

# Video (pluggable driver)
VIDEO_DRIVER=
VIDEO_API_BASE=
VIDEO_API_KEY=
VIDEO_MODEL=

# Worker behavior
VIDEOMAKER_FIXTURE_MODE=false          # true only in tests
VIDEOMAKER_VIDEO_GEN_QUOTA=1
VIDEOMAKER_DEFAULT_VARIANTS=high_click,high_conversion

# Optional
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_ENABLED=false
```

---

## 19. Risks And Mitigations

| Risk | Mitigation |
| --- | --- |
| LLM output unstable | Strict schema validation; repair prompt once; then fail visibly |
| Model provider outage | Clear `ToolError`; user retry; pre-flight health in demo env |
| Video gen slow/expensive | Quota = 1; GapPlanner prefers image + HF ken-burns |
| Removing rules breaks CI | Agent JSON fixtures for all former rule tests |
| HyperFrames CLI missing | Same fallback as P0: structured error `hyperframes_missing`, retryable |
| Scope creep | Sub-plans own files; master plan merge order enforced |

---

## 20. Parallel Development Rules

Do not parallelize:

1. Contract schema changes without merging to integration branch first.
2. Deleting `structure_pipeline.py` while worker tests still import it on another branch.
3. `TaskEvent.stage` enum changes without updating contracts + web progress labels in same merge window.

Safe to parallelize:

1. Web UI with mocked Agent artifacts.
2. Gateway unit tests with httpx mock.
3. HyperFrames material templates with static MaterialSpec fixtures.
4. Variant registry + UI labels before backend parallel task wiring.

---

## 21. Self-Review

Spec coverage mapping:

| Requirement | Task |
| --- | --- |
| Real LLM structure analysis | Tasks 3, 4 |
| Real asset adaptation | Task 5 |
| Semantic slot/gap | Task 6 |
| AIGC image + video + TTS | Task 7 |
| HyperFrames as material generator | Task 7 |
| Packaging enhancement | Tasks 7, 8 |
| Two variants high_click + high_conversion | Task 8 |
| Extensible variant registry | Tasks 1, 8 |
| No rule semantic fallback | Task 3 |
| ModelGateway without LiteLLM | Task 2 |
| Video gen quota 1 | Task 7 |
| NL revise in P1 | Task 9 |
| Explainability UI | Task 10 |
| End-to-end demo | Task 11 |

No placeholder tasks at master level. Detailed TDD steps live in submodule plans listed in §3.

---

## 22. Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md`.

**Next steps:**

1. Review and approve this master plan.
2. Author submodule plans in §3 (start with contracts + ModelGateway).
3. Create `feature/p1-contracts-extension` worktree from `main`.
4. Choose execution mode: subagent-driven (recommended) or inline with executing-plans skill.
