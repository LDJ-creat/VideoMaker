# P1 Agent Orchestration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce `AgentRunner`, wire all Agent prompt files, replace P0 deterministic semantic pipelines with LLM Agent calls, persist `agent_runs`, and **delete** `structure_pipeline.py`. On LLM failure — fail task; **no rule fallback**.

**Architecture:** Agents live in `services/worker/app/agents/`. Each agent: load prompt markdown → build inputs → `LLMTool.generate_json` → validate schema → write artifact. `AgentRunner` handles logging, prompt version hash, and error propagation.

**Tech Stack:** Python, pytest, `packages/prompts/agents/*.md`, ModelGateway via LLMTool.

---

## Session Context

**Depends on:**

1. `feature/p1-contracts-extension` merged.
2. `feature/p1-model-gateway` merged (LLMTool accepts gateway).

**Master plan:** §7, §15 Task 3.

**Branch:** `feature/p1-agent-orchestration`

**P0 code to remove:** `services/worker/app/pipelines/structure_pipeline.py` and imports.

**P0 code to refactor:** `p0_demo_pipeline.py`, `generation_pipeline.py` — replace `extract_video_structure` and deterministic planners with Agent stubs that call runner (full Agent logic may be refined in downstream plans but orchestration skeleton must work end-to-end with fixtures).

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/agents/__init__.py
services/worker/app/agents/runner.py
services/worker/app/agents/prompt_loader.py
services/worker/app/agents/structure_analyst.py
services/worker/app/agents/content_strategist.py
services/worker/app/agents/slot_mapper.py
services/worker/app/agents/gap_planner.py
services/worker/app/agents/storyboard_writer.py
services/worker/app/agents/packaging_designer.py
services/worker/app/runtime/agent_run_store.py
services/worker/tests/fixtures/agents/structure_analyst.json
services/worker/tests/fixtures/agents/slot_mapper.json
services/worker/tests/fixtures/agents/gap_planner.json
services/worker/tests/fixtures/agents/storyboard_writer.json
services/worker/tests/test_agent_runner.py
```

**Modify:**

```text
services/worker/app/tools/llm_tool.py          # fixture paths
services/worker/app/pipelines/p0_demo_pipeline.py
services/worker/app/pipelines/generation_pipeline.py
packages/prompts/agents/*.md                   # strip P0-only constraints where needed
```

**Delete:**

```text
services/worker/app/pipelines/structure_pipeline.py
services/worker/tests/test_structure_pipeline.py
```

**Out of scope:** Multimodal keyframe encoding (llm-structure plan), AIGC tools, API revise route, web UI.

---

## AgentRunner Design

```python
@dataclass
class AgentRunner:
    llm: LLMTool
    prompt_loader: PromptLoader
    run_store: AgentRunStore

    def run(
        self,
        agent_name: str,
        *,
        task: str,
        schema_name: str,
        inputs: dict,
        context: TaskContext,
    ) -> dict:
        prompt_version = self.prompt_loader.version(agent_name)
        system = self.prompt_loader.load(agent_name)
        merged_inputs = {"systemPrompt": system, "inputs": inputs}
        started = time.perf_counter()
        try:
            output = self.llm.generate_json(task, merged_inputs, schema_name)
            valid = True
            errors: list[str] = []
        except LLMToolValidationError as exc:
            valid = False
            errors = [e.message for e in exc.validation_errors]
            raise
        finally:
            self.run_store.record(AgentRunLog(...))
        return output
```

Emit `TaskEvent` stage `running_agent` with message `Running {agent_name}`.

---

## Task 1: PromptLoader

- [ ] Load `packages/prompts/agents/{name}.md` relative to repo root (detect via env `VIDEOMAKER_REPO_ROOT` or walk up from worker).
- [ ] `version()` = first 8 chars of sha256(file contents).
- [ ] Test: loading `structure_analyst.md` returns non-empty string.

---

## Task 2: AgentRunStore

- [ ] Write JSON logs to `storage/projects/{projectId}/logs/agent-runs/{runId}.json` OR append to generation log dir.
- [ ] Fields match `agent-run-log` schema.
- [ ] Test: record creates file with required keys.

---

## Task 3: StructureAnalyst agent (fixture path)

Replace `extract_video_structure(...)` in `p0_demo_pipeline.py`:

```python
from app.agents.structure_analyst import run_structure_analyst

structure = run_structure_analyst(runner, analysis=analysis, context=ctx)
```

Agent task key: `structure_analyst` → schema `video-structure`.

Fixture: `tests/fixtures/agents/structure_analyst.json` — valid minimal VideoStructure.

- [ ] Delete `structure_pipeline.py`.
- [ ] Update `test_p0_demo_pipeline.py` to use fixture LLMTool.
- [ ] Pipeline still produces schema-valid structure.

---

## Task 4: Generation agents (fixture path)

Wire in `generation_pipeline.py` order:

1. `content_strategist` → enrich inventory (schema: still `asset-inventory` partial update OR internal dict — document choice: merge into existing inventory in pipeline code)
2. `slot_mapper` → produces matches embedded in gap flow (schema: custom `slot-mapper-output` NOT allowed — must output fields mergeable to `gap-report`; implement mapper output as `{ slotMatches: [...] }` validated then merged)
3. `gap_planner` → `gap-report`
4. `storyboard_writer` → storyboard array merged into `generation-plan`
5. `packaging_designer` → packaging section

**Important:** If no intermediate schema exists, validate sub-outputs with JSON Schema fragments in tests or use partial validation against gap-report / generation-plan subschemas.

For P1 orchestration, acceptable pattern:

```python
gap_report = runner.run("gap_planner", task="gap_planner", schema_name="gap-report", inputs={...})
plan = build_generation_plan(gap_report, storyboard=runner.run(...), ...)
validate_contract("generation-plan", plan)
```

- [ ] Add fixtures for each agent task key.
- [ ] Remove deterministic Jaccard / keyword functions from generation_pipeline.

---

## Task 5: Error handling — no fallback

- [ ] On `LLMToolValidationError` or `LLMToolConfigError`: mark task failed, stage unchanged, error in TaskEvent.
- [ ] Do NOT catch and call rule pipeline.
- [ ] Test: invalid fixture raises and task status becomes failed.

---

## Task 6: Update prompts

Edit `packages/prompts/agents/gap_planner.md`:

- Remove "P0 strategies only" restriction.
- Add P1 providers list: `hyperframes_material`, `image_generation`, `video_generation`, `tts`, `asset_reuse`.

Other prompts: add "output JSON only", "do not copy sample verbatim".

---

## Task 7: Migrate tests

Replace imports from `structure_pipeline` in:

- `test_slot_mapping.py`
- `test_generation_plan.py`

Use fixture VideoStructure JSON files under `tests/fixtures/structures/`.

---

## Verification

```powershell
cd services/worker
python -m pytest -v
python -m compileall app

cd ../../services/api
python -m pytest -v
```

Ensure P0 flow tests still pass with worker in fixture mode.

---

## Acceptance Criteria

1. `structure_pipeline.py` deleted; no remaining imports.
2. Sample analysis + generation pipelines invoke AgentRunner.
3. CI passes with `fixture_mode=True` only.
4. Agent run logs written per call.
5. LLM failure fails task without silent fallback.

---

## Commit Message

```text
feat(worker): add AgentRunner and replace rule-based semantic pipelines
```
