# P1 HyperFrames Material Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement clip-level HyperFrames material generation: `HyperFramesMaterialTool`, templates (benefit-card, title-lower-third, ken-burns), MaterialAuthor Agent, and `hyperframes_material` completion provider.

**Architecture:** MaterialAuthor emits `MaterialSpec` → template renderer builds isolated composition → `HyperFramesTool.render` → mp4 clip artifact. Register provider in completion registry (coordinate merge with aigc plan).

**Tech Stack:** HyperFrames CLI, existing `HyperFramesTool`, `render_timeline_to_hyperframes` patterns, AgentRunner.

---

## Session Context

**Depends on:**

1. `feature/p1-contracts-extension` (MaterialSpec schema)
2. `feature/p1-agent-orchestration` (AgentRunner)
3. Can start templates in parallel with model-gateway; **provider registration** merges after aigc-material branch or in integration branch

**Master plan:** §8.2.

**Branch:** `feature/p1-hyperframes-material`

**Reference P0 code:** `services/worker/app/render/render_timeline_to_hyperframes.py`, `services/worker/app/tools/hyperframes_tool.py`

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/tools/hyperframes_material_tool.py
services/worker/app/render/material_templates/benefit_card.html
services/worker/app/render/material_templates/title_lower_third.html
services/worker/app/render/material_templates/ken_burns.html
services/worker/app/render/material_templates/scaffold.py
services/worker/app/agents/material_author.py
services/worker/app/providers/hyperframes_material_provider.py
services/worker/tests/test_hyperframes_material_tool.py
services/worker/tests/fixtures/material_specs/benefit_card.json
packages/prompts/agents/material_author.md
```

**Modify:**

```text
services/worker/app/providers/completion_registry.py   # if exists from aigc branch
packages/prompts/agents/packaging_designer.md
```

**Out of scope:** Full timeline render changes, web UI, external AIGC tools.

---

## HyperFramesMaterialTool API

```python
class HyperFramesMaterialTool:
    def render_material(
        self,
        spec: dict,
        *,
        output_dir: Path,
        output_clip: Path,
        log_path: Path,
    ) -> dict:
        """
        1. scaffold.build_composition(spec, output_dir)
        2. hyperframes_tool.render(output_dir, output_clip, log_path)
        3. return { ok, artifact path, durationSec }
        """
```

Emit TaskEvent stage `rendering_material`.

---

## Template: benefit-card

**Params:** title, bullets[], colors.primary, durationSec (default 3)

HTML: full-screen card, animated bullet stagger (CSS or minimal JS registered on `window.__hfAnime` per hyperframes skill patterns — keep deterministic seek).

**Ken-burns:** params `assetRefs[0]` image path relative to composition; slow zoom 1.0→1.15.

**title-lower-third:** title + subtitle, bottom third safe area.

**custom:** only allow substituting text/colors inside scaffold — reject raw `<script>` from Agent output.

---

## MaterialAuthor Agent

Task key: `material_author`  
Schema: `material-spec`

Inputs:

```json
{
  "slot": { "role": "benefit_card", "scriptIntent": "...", "visualIntent": "..." },
  "variantOverrides": {},
  "brandColors": {}
}
```

Prompt selects template id; fills params.

---

## Provider: hyperframes_material_provider

```python
def execute(action, ctx):
    spec = ctx.runner.run("material_author", ...)  # or use pre-filled spec on action
    tool.render_material(spec, ...)
    return MaterialResult(artifact_ref=..., clip_duration=spec["durationSec"])
```

If GapPlanner already attached partial spec on action, skip Agent call.

---

## Security

`sanitize_params()` strip `<`, `>`, `javascript:` from string params.

Composition directory must stay under project sandbox.

---

## Task Checklist

- [ ] **Task 1:** scaffold.py builds composition from benefit_card fixture spec.
- [ ] **Task 2:** HyperFramesMaterialTool test with mocked CLI (reuse CommandRunner pattern from test_hyperframes_tool.py).
- [ ] **Task 3:** MaterialAuthor fixture + agent module.
- [ ] **Task 4:** hyperframes_material_provider unit test.
- [ ] **Task 5:** Register in completion_registry (merge conflict resolution with aigc branch documented in commit).

---

## Verification

```powershell
cd services/worker
python -m pytest tests/test_hyperframes_material_tool.py -v
python -m compileall app
```

Optional manual: `npx hyperframes render` on generated composition if CLI available.

---

## Acceptance Criteria

1. benefit-card spec renders composition directory with index.html + hyperframes.json.
2. Provider returns mp4 path (mocked CLI success).
3. MaterialSpec schema validated before render.
4. Agent cannot inject unbounded HTML (sanitizer test).

---

## Commit Message

```text
feat(worker): HyperFrames material tool and templates for clip generation
```
