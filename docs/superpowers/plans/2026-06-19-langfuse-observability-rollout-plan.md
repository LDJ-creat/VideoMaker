# Langfuse Observability Rollout

归档自 Cursor 计划（2026-06-19）。实现以本仓库代码与 `docs/demos/langfuse-observability-e2e-checklist.md` 为准。

## 概要

- `ModelGateway` 统一 hook → `logs/model-calls/` + 可选 Langfuse
- `ObservabilitySink.record_model_call` / `flush()`
- Agent 覆盖：segment_analyst、keyframe_batch_analyst live 路径
- API：`GET .../model-calls`（generation + task）

## Env

| 变量 | 默认 |
|------|------|
| `VIDEOMAKER_OBSERVABILITY_CAPTURE` | `full` |
| `LANGFUSE_CAPTURE` | 继承 OBSERVABILITY_CAPTURE |
| `LANGFUSE_ENABLED` | `false` |
