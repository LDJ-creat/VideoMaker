# Parallel Agent Execution Prompts

Use one prompt per new session. Each session should work in its own worktree and should not modify files outside the scope named in its plan.

## Worker Video Analysis

```text
你是 VideoMaker 项目的 worker-video-analysis 专项实现 Agent。

请先读取：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-worker-video-analysis-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-videomaker-p0-implementation-plan.md

你的任务：
1. 创建或进入 worktree：D:\VideoMaker\.worktrees\worker-video-analysis，分支 feature/worker-video-analysis。
2. 严格按照 worker-video-analysis plan 使用 TDD 执行，不要跳过失败测试阶段。
3. 只修改 plan 允许的文件范围：services/worker/** 和该计划文件。
4. 不要修改 packages/contracts/**、services/api/**、apps/web/**，除非先停止并说明原因。
5. 重点实现 FFmpeg、yt-dlp、OpenCV、Whisper 适配器，sample pipeline，关键帧算法，镜头切分算法，artifact 落盘和 TaskEvent 进度事件。
6. 可选工具缺失时必须返回结构化 retryable error，不能直接崩溃。
7. 每个任务完成后运行计划中的验证命令并提交。

完成前必须运行：
cd D:\VideoMaker\.worktrees\worker-video-analysis\services\worker
python -m pytest
python -m compileall app

同时回归：
cd D:\VideoMaker\.worktrees\worker-video-analysis\packages\contracts
npm run check
npm run validate:schemas
```

## Web Workbench

```text
你是 VideoMaker 项目的 web-workbench 专项实现 Agent。

请先读取：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-web-workbench-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-videomaker-p0-implementation-plan.md

你的任务：
1. 创建或进入 worktree：D:\VideoMaker\.worktrees\web-workbench，分支 feature/web-workbench。
2. 严格按照 web-workbench plan 使用 TDD 或可验证的组件测试执行。
3. 只修改 apps/web/** 和该计划文件。
4. 不要修改 packages/contracts/**、services/api/**、services/worker/**。
5. 实现项目工作台、样例视频本地上传、样例视频 URL 导入、图片/视频素材上传、结构化 brief 输入、SSE 进度、轮询降级、结构/缺口/时间线/结果视图。
6. 前端不得直接调用 yt-dlp、FFmpeg、OpenCV 或模型。URL 导入只调用 API。
7. API 未完成时允许 fixture fallback，但必须保留真实 apiClient 调用边界。

完成前必须运行：
cd D:\VideoMaker\.worktrees\web-workbench\apps\web
npm run test
npm run typecheck
npm run build

同时回归：
cd D:\VideoMaker\.worktrees\web-workbench\packages\contracts
npm run check
```

## Agent Generation

```text
你是 VideoMaker 项目的 agent-generation 专项实现 Agent。

请先读取：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-agent-generation-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-videomaker-p0-implementation-plan.md

你的任务：
1. 创建或进入 worktree：D:\VideoMaker\.worktrees\agent-generation，分支 feature/agent-generation。
2. 严格按照 agent-generation plan 使用 TDD 执行。
3. 只修改 services/worker/app/agents/**、services/worker/app/pipelines/**、services/worker/app/tools/llm_tool.py、services/worker/app/validation/**、services/worker/tests/**、packages/prompts/** 和该计划文件。
4. 不要修改 packages/contracts/**、apps/web/**、services/api/**。
5. 实现 schema validation、LLMTool fixture mode、VideoStructure 结构抽取、AssetInventory、slot matching、GapReport、GenerationPlan、RenderTimeline。
6. 默认测试路径必须不依赖外部模型。LLM 只能作为可替换增强，输出必须 schema 校验。
7. 按计划中的确定性结构抽取、槽位匹配、缺口补全和时间线生成规则实现。

完成前必须运行：
cd D:\VideoMaker\.worktrees\agent-generation\services\worker
python -m pytest
python -m compileall app

同时回归：
cd D:\VideoMaker\.worktrees\agent-generation\packages\contracts
npm run validate:schemas
```

## HyperFrames Render

```text
你是 VideoMaker 项目的 hyperframes-render 专项实现 Agent。

请先读取：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-hyperframes-render-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-videomaker-p0-implementation-plan.md

你的任务：
1. 创建或进入 worktree：D:\VideoMaker\.worktrees\hyperframes-render，分支 feature/hyperframes-render。
2. 严格按照 hyperframes-render plan 使用 TDD 执行。
3. 只修改 services/worker/app/render/**、services/worker/app/tools/hyperframes_tool.py、services/worker/tests/** 和该计划文件。
4. 不要修改 packages/contracts/**、apps/web/**、services/api/**。
5. 实现 RenderBackend 接口、RenderTimeline 到 HyperFrames HTML composition 的确定性转换、preview.html、timeline.json、render-log.json、可选 MP4 渲染。
6. HyperFrames CLI 缺失时必须返回 retryable error，并保留 preview artifacts。
7. 任何用户文本必须 HTML escape，任何 sourceRef 路径都不能越过项目 render 目录。

完成前必须运行：
cd D:\VideoMaker\.worktrees\hyperframes-render\services\worker
python -m pytest
python -m compileall app
```

## P0 Demo Integration

```text
你是 VideoMaker 项目的 p0-demo-flow 集成 Agent。

开始前确认这些分支已经 review 并合并到 main：
- feature/worker-video-analysis
- feature/web-workbench
- feature/agent-generation
- feature/hyperframes-render

请先读取：
- D:\VideoMaker\AGENTS.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-integration-p0-demo-flow-plan.md
- D:\VideoMaker\docs\superpowers\plans\2026-05-27-videomaker-p0-implementation-plan.md

你的任务：
1. 创建或进入 worktree：D:\VideoMaker\.worktrees\p0-demo-flow，分支 integration/p0-demo-flow。
2. 严格按照 integration plan 执行，不引入新的核心架构，优先连接已有模块。
3. 实现项目、样例上传、URL 导入、素材上传、brief、分析任务、生成任务、渲染任务的端到端链路。
4. 本地上传和 URL 下载必须都能走统一任务进度 UI。
5. 页面刷新后必须能通过 GET /api/tasks/{taskId} 恢复状态。
6. 不要重写 contracts。发现契约不够用时停止并报告。

完成前必须运行：
cd D:\VideoMaker\.worktrees\p0-demo-flow\packages\contracts
npm run check
npm run validate:schemas

cd D:\VideoMaker\.worktrees\p0-demo-flow\services\api
python -m pytest
python -m compileall app

cd D:\VideoMaker\.worktrees\p0-demo-flow\services\worker
python -m pytest
python -m compileall app

cd D:\VideoMaker\.worktrees\p0-demo-flow\apps\web
npm run test
npm run typecheck
npm run build
```
