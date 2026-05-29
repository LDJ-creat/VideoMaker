# P1 Model Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a thin `ModelGateway` with OpenAI-compatible adapters (text, vision, TTS, image) and one pluggable video adapter (submit + poll). Wire `LLMTool` to gateway in live mode; keep fixture mode for tests. **No LiteLLM.**

**Architecture:** `services/worker/app/gateway/` owns HTTP transport (httpx), retries, timeouts, and provider config from env. Tools (`LLMTool`, future ImageGen/VideoGen/TTSTool) call gateway — Agents never call httpx directly.

**Tech Stack:** Python 3.11+, httpx, pytest, respx or unittest.mock for HTTP.

---

## Session Context

**Depends on:** `feature/p1-contracts-extension` merged to `main` (or rebase onto it).

**Master plan:** `docs/superpowers/plans/2026-05-29-videomaker-p1-implementation-plan.md` §6.

**P0 baseline:** `services/worker/app/tools/llm_tool.py` has `fixture_mode=True` default, schema validation via `validate_contract`.

**Branch:** `feature/p1-model-gateway`

**Can parallel with:** `feature/p1-hyperframes-material` (after contracts merge) — no file overlap.

---

## Files Allowed To Change

**Create:**

```text
services/worker/app/gateway/__init__.py
services/worker/app/gateway/model_gateway.py
services/worker/app/gateway/config.py
services/worker/app/gateway/providers/base.py
services/worker/app/gateway/providers/openai_compatible_chat.py
services/worker/app/gateway/providers/openai_compatible_tts.py
services/worker/app/gateway/providers/openai_compatible_image.py
services/worker/app/gateway/providers/pluggable_video.py
services/worker/tests/test_model_gateway.py
services/worker/tests/test_openai_compatible_providers.py
```

**Modify:**

- `services/worker/app/tools/llm_tool.py`
- `services/worker/pyproject.toml` or requirements — add `httpx` if missing

**Out of scope:** Agent runners, pipelines, API routes, `apps/web/**`, deleting `structure_pipeline.py`.

---

## Configuration

Load from environment (implement in `config.py`):

| Env | Purpose |
| --- | --- |
| `TEXT_API_BASE`, `TEXT_API_KEY`, `TEXT_MODEL` | Chat completions |
| `VISION_API_BASE`, `VISION_API_KEY`, `VISION_MODEL` | Multimodal chat |
| `TTS_API_BASE`, `TTS_API_KEY`, `TTS_MODEL` | Speech synthesis |
| `IMAGE_API_BASE`, `IMAGE_API_KEY`, `IMAGE_MODEL` | Image generation |
| `VIDEO_DRIVER`, `VIDEO_API_BASE`, `VIDEO_API_KEY`, `VIDEO_MODEL` | Video job API |
| `VIDEOMAKER_FIXTURE_MODE` | `true` in tests |

Defaults: if `VISION_*` unset, fall back to `TEXT_*`.

---

## Task 1: Provider base and errors

- [ ] **Step 1: Write failing test** for `GatewayError` with `retryable` flag.

```python
# tests/test_model_gateway.py
from app.gateway.providers.base import GatewayError

def test_gateway_error_retryable():
    err = GatewayError(code="rate_limit", message="429", retryable=True)
    assert err.retryable is True
```

- [ ] **Step 2:** Implement `base.py` with `GatewayError`, `ProviderConfig` dataclass.

---

## Task 2: OpenAI-compatible chat provider

**Endpoint:** `POST {base_url}/chat/completions`

- [ ] **Step 1:** Test mock returns JSON content; gateway parses assistant message.
- [ ] **Step 2:** Implement `complete(messages, *, model, response_format=json_object optional)`.
- [ ] **Step 3:** Retry up to 2 times on HTTP 429/502/503 with exponential backoff (0.5s, 1s).

**JSON mode:** When `schema_name` passed to `ModelGateway.complete_json`, append system instruction: "Respond with valid JSON only."

---

## Task 3: ModelGateway facade

```python
@dataclass
class ModelGateway:
    config: GatewayConfig

    def complete_json(self, task: str, inputs: dict, schema_name: str, *, profile: str = "text") -> dict: ...
    def complete_text(self, task: str, inputs: dict, *, profile: str = "text") -> str: ...
    def generate_image(self, prompt: str, *, options: dict | None = None) -> bytes: ...
    def submit_video_job(self, prompt: str, *, options: dict | None = None) -> str: ...
    def poll_video_job(self, job_id: str) -> VideoJobResult: ...
    def synthesize_speech(self, text: str, *, options: dict | None = None) -> bytes: ...
```

- [ ] **Step 1:** Unit test `complete_json` with mocked httpx.
- [ ] **Step 2:** Implement routing: `profile=text|vision` selects chat provider config.
- [ ] **Step 3:** Record `latencyMs` on return (for AgentRunLog later).

---

## Task 4: TTS and Image providers

**TTS:** `POST {base_url}/audio/speech` (OpenAI shape) — body `{ model, input, voice }`.

**Image:** `POST {base_url}/images/generations` — return first `b64_json` or `url` (download if url).

- [ ] Tests with mocked responses returning minimal PNG bytes / WAV header.
- [ ] Timeout: TTS 60s, image 120s.

---

## Task 5: Pluggable video adapter

Design for unknown vendor via config `VIDEO_DRIVER`:

**Interface:**

```python
class VideoProvider(Protocol):
    def submit(self, prompt: str, options: dict) -> str: ...  # job_id
    def poll(self, job_id: str) -> VideoJobResult: ...  # status pending|succeeded|failed, video_bytes optional
```

**P1 implementation:** One concrete driver `generic_job` documented with env:

- `POST /videos` → `{ jobId }`
- `GET /videos/{jobId}` → `{ status, downloadUrl? }`

If real vendor differs, implement adapter in this file only — document extension point in module docstring.

- [ ] Poll interval 3s, max `max_poll_sec=300` from config.
- [ ] On timeout → `GatewayError(retryable=True)`.

---

## Task 6: Wire LLMTool

Modify `llm_tool.py`:

```python
def generate_json(self, task: str, inputs: dict, schema_name: str) -> dict:
    if self.fixture_mode:
        ...  # unchanged
    payload = self.gateway.complete_json(task, inputs, schema_name)
    return self._validate_payload(payload=payload, schema_name=schema_name)
```

- [ ] Add optional `gateway: ModelGateway | None` to dataclass.
- [ ] Existing tests in `test_llm_tool.py` must still pass.
- [ ] Add test: live mode without gateway raises `LLMToolConfigError`.

---

## Task 7: Integration test marker

```python
@pytest.mark.integration
def test_live_text_completion_skipped_by_default():
    ...
```

Skip unless `RUN_INTEGRATION=1` and API keys set.

---

## Verification

```powershell
cd services/worker
python -m pytest tests/test_model_gateway.py tests/test_openai_compatible_providers.py tests/test_llm_tool.py -v
python -m compileall app
```

---

## Acceptance Criteria

1. All unit tests pass without network.
2. `LLMTool(fixture_mode=True)` unchanged for CI.
3. Gateway supports text + vision + tts + image + video job lifecycle.
4. No LiteLLM dependency in pyproject/requirements.

---

## Commit Message

```text
feat(worker): add ModelGateway with OpenAI-compatible providers
```
