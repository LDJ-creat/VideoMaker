# ACP 素材作者与素材审核韧性计划

**Status:** implemented on `main` (2026-06-29 session)  
**Relates to:** slot-5 scoped regen 长跑、ACP 30min timeout、benefit-card fallback

## 目标

- `source_then_polish` 底片稀疏关键帧在 Worker 侧 normalize，避免 HF preview seek 黑帧误杀 review
- scoped regen 默认关闭 ACP in-session LLM review，post-session gate 保留
- ACP 分层超时（session / per-prompt）与 lint-passed partial harvest
- MCP write gate 与 Worker in-session review 策略对齐（`VM_ACP_IN_SESSION_REVIEW`）
- hf_native 禁止 external base-video MP4；source_then_polish overlay lint

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `VIDEOMAKER_COMPOSITION_BASE_VIDEO_MAX_KEYFRAME_SEC` | `2.0` | 超阈值则 normalize |
| `VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE` | `false` | gate/scoped regen 关闭 in-session |
| `VIDEOMAKER_COMPOSITION_ACP_PROMPT_TIMEOUT_SEC` | `600` | 单次 conn.prompt 上限 |
| `VIDEOMAKER_COMPOSITION_ACP_MAX_TOOL_CALLS_PER_PROMPT` | `80` | observability 软告警 |
| `VM_ACP_IN_SESSION_REVIEW` | worker 注入 MCP | MCP review/write gate |

## 关键文件

- `services/worker/app/composition/acp/base_video_normalize.py`
- `services/worker/app/composition/acp/scratch_assets.py`
- `services/worker/app/composition/acp/author.py`
- `services/composition/composition/mcp/handlers.py`
- `services/composition/composition/author/overlay_canvas_guard.py`
- `services/worker/app/pipelines/material_review.py`
- `services/worker/app/providers/hyperframes_material_provider.py`

## 验证

```powershell
cd services/worker
python -m pytest tests/test_base_video_normalize.py tests/test_acp_author.py tests/test_acp_scratch_asset_staging.py tests/test_material_review_infrastructure.py -q

cd services/composition
python -m pytest tests/test_overlay_canvas_guard.py tests/test_review_via_worker_observability.py -q
```

## 手动 E2E（slot-5）

1. 对 slot-5 发起 scoped material regen（`hf_only` + `hf_native`）
2. ACP session < 10min 产出 composition `material-spec.json`
3. `generated/action-slot-5.mp4` 非 benefit-card
4. post-session `material-reviews/slot-5/report.json` 中文 + `reviewInputs.mode=video`
5. 日志含 `inSessionReviewEnabled=false`（scoped regen 默认）
