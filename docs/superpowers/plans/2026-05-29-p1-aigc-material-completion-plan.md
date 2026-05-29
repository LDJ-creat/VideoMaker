# P1 AIGC Material Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ImageGenTool, VideoGenTool, TTSTool, completion provider registry, and execute CompletionActions in generation pipeline with **video quota = 1 per generationId**.

**Architecture:** Tools call `ModelGateway` media methods; write artifacts under `storage/projects/{projectId}/generations/{generationId}/generated/`. Providers implement `CompletionStrategyProvider` interface; registry invoked after GapPlanner.

**Tech Stack:** ModelGateway, ArtifactStore, FFmpeg optional for format conversion.

---

## Session Context

**Depends on:**

1. `feature/p1-model-gateway` merged
2. `feature/p1-semantic-mapping-gap` merged (CompletionAction.provider populated)

**Master plan:** §8.1, §8.3, video quota.

**Branch:** `feature/p1-aigc-material`

**Parallel with:** `feature/p1-hyperframes-material` (merge both before multi-variant).

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/tools/image_gen_tool.py
services/worker/app/tools/video_gen_tool.py
services/worker/app/tools/tts_tool.py
services/worker/app/providers/__init__.py
services/worker/app/providers/completion_registry.py
services/worker/app/providers/image_generation_provider.py
services/worker/app/providers/video_generation_provider.py
services/worker/app/providers/tts_provider.py
services/worker/app/providers/asset_reuse_provider.py
services/worker/app/runtime/video_gen_quota.py
services/worker/tests/test_image_gen_tool.py
services/worker/tests/test_video_gen_quota.py
services/worker/tests/test_completion_registry.py
```

**Modify:**

```text
services/worker/app/pipelines/generation_pipeline.py
services/worker/app/pipelines/p0_demo_pipeline.py
```

**Out of scope:** HyperFramesMaterialTool (separate plan), web UI, API variant routes.

---

## Tool Interfaces

### ImageGenTool

```python
def generate(self, *, prompt: str, output_path: Path, options: dict | None = None) -> ArtifactRef:
    bytes = self.gateway.generate_image(prompt, options=options)
    output_path.write_bytes(bytes)
    return artifact_ref("image", output_path)
```

Emit stage `generating_image`.

### VideoGenTool

```python
def generate(self, *, prompt: str, output_path: Path, quota: VideoGenQuota, options: dict | None = None) -> ArtifactRef:
    if not quota.consume():
        raise ToolError(code="video_quota_exceeded", retryable=False)
    job_id = self.gateway.submit_video_job(prompt, options=options)
    result = self.gateway.poll_video_job(job_id)
    ...
```

Emit stages `generating_video`.

### TTSTool

```python
def synthesize(self, *, text: str, output_path: Path, voice: str = "default") -> ArtifactRef:
```

Emit stage `generating_tts`.

---

## VideoGenQuota

```python
@dataclass
class VideoGenQuota:
    max_calls: int = 1
    used: int = 0

    def consume(self) -> bool:
        if self.used >= self.max_calls:
            return False
        self.used += 1
        return True
```

Persist `used` in generation checkpoint JSON for resume idempotency — do not double-consume on retry if artifact already exists.

---

## Completion Registry

```python
class CompletionStrategyProvider(Protocol):
    name: str
    def execute(self, action: CompletionAction, ctx: MaterialContext) -> MaterialResult: ...

def execute_completion_plan(actions: list[CompletionAction], ctx: MaterialContext) -> list[MaterialResult]:
    ...
```

Register: `asset_reuse`, `image_generation`, `video_generation`, `tts` (hyperframes provider registered in HF plan).

**MaterialContext:** project_id, generation_id, render_root, gateway, tools, quota, inventory.

---

## Pipeline Integration

After `planning_completion`:

```text
generating_material:
  for action in completion_actions ordered by slot importance (must_have first):
    result = registry.execute(action, ctx)
    record artifactRef on action
    update storyboard placeholder sources
  checkpoint
```

On tool failure → task failed (no fallback).

---

## TaskEvent artifactRefs (required for web Phase B)

After each material tool succeeds, append to the current stage's TaskEvent:

```python
artifactRefs=[{
  "id": artifact_ref.id,
  "type": "image" | "video" | "audio",
  "uri": artifact_ref.uri,
  "createdAt": ...
}]
```

Emit updated event on stages: `generating_image`, `generating_video`, `generating_tts`, `generating_material`, `rendering_material`.

Web `TaskArtifactPreview` depends on incremental refs — do not wait until task terminal.

---

## Asset Reuse Provider

Use FFmpegTool to trim user video to slot duration:

- Input: weak match moment + slot time range
- Output: mp4 clip in `generated/`

---

## Task Checklist

- [ ] **Task 1:** VideoGenQuota tests.
- [ ] **Task 2:** ImageGenTool with mocked gateway bytes.
- [ ] **Task 3:** VideoGenTool with mocked submit/poll.
- [ ] **Task 4:** TTSTool with mocked wav bytes.
- [ ] **Task 5:** completion_registry executes actions in tests.
- [ ] **Task 6:** Wire into generation_pipeline; timeline clips get `generatedBy`.

---

## Verification

```powershell
cd services/worker
python -m pytest tests/test_image_gen_tool.py tests/test_video_gen_quota.py tests/test_completion_registry.py -v
python -m pytest tests/test_generation_plan.py -v
```

---

## Acceptance Criteria

1. Second video_generation call in same generation fails with `video_quota_exceeded`.
2. Generated files registered as artifacts with correct URIs.
3. TaskEvent stages emitted for image/video/tts.
4. Checkpoint resume skips completed material actions.

---

## Commit Message

```text
feat(worker): AIGC material tools with video generation quota
```
