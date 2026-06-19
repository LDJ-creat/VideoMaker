# Langfuse 与模型调用观测 E2E 检查清单

## 前置条件

1. Worker 安装 Langfuse 可选依赖：

```powershell
cd D:\VideoMaker\services\worker
pip install -e ".[langfuse]"
```

2. 启动 API 前设置环境变量（需被子进程继承）：

```powershell
$env:LANGFUSE_ENABLED = "true"
$env:LANGFUSE_PUBLIC_KEY = "pk-lf-..."
$env:LANGFUSE_SECRET_KEY = "sk-lf-..."
# 自托管：$env:LANGFUSE_HOST = "https://your-langfuse.example.com"
$env:VIDEOMAKER_OBSERVABILITY_CAPTURE = "full"   # 默认 full；可改为 summary
```

3. Live 模式（非 `VIDEOMAKER_FIXTURE_MODE=true`），Model Gateway 已配置 text/vision/image/video/tts。

## 1. 本地 model-calls 落盘

- [ ] 跑一次 **样本分析**（map_reduce）：`storage/projects/{projectId}/logs/model-calls/` 出现 `chat_json` 记录（含 keyframe batch、segment analyst）。
- [ ] 跑一次 **生成**：同目录出现 `image` / `video_submit` / `video_poll` / `tts`（视 gap 配置）。
- [ ] composition ReAct 素材：`chat_tools` 记录带 `agentName=material_author` 与递增 `turn`。

## 2. Agent-runs 双写

- [ ] `logs/agent-runs/` 仍有记录；segment/keyframe live 路径不再缺失。
- [ ] `GET /api/generations/{generationId}/agent-runs` 可查询。
- [ ] `GET /api/generations/{generationId}/model-calls?kind=chat` 返回摘要列表（无 base64）。
- [ ] 样本分析任务：`GET /api/tasks/{taskId}/model-calls` 可按 task 过滤。

## 3. Langfuse UI

- [ ] worker 结束后 30s 内可见 trace（`session_id` = taskId）。
- [ ] 同 task 下 agent span + model generation/span 层级正确。
- [ ] 用 `generationId` metadata 可过滤某次 variant 生成。

## 4. 降级与韧性

- [ ] `LANGFUSE_ENABLED=false`：pipeline 成功，仅本地 logs。
- [ ] `VIDEOMAKER_OBSERVABILITY_CAPTURE=summary`：input/output 截断，无 base64。
- [ ] Langfuse 不可达：生成/分析仍成功（MultiSink 吞异常）。

## 5. Token 与模型名

- [ ] OpenAI 兼容 chat：`tokenUsage` 出现在 model-call 与 agent-run。
- [ ] agent-run / model-call 的 `model` 为真实 gateway 模型名（非 `live`）。
