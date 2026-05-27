# VideoMaker 爆款结构迁移引擎设计文档

日期：2026-05-27

## 1. 项目定位

VideoMaker 是一个面向短视频创作的 AI 结构迁移平台。系统从优质样例视频中抽取脚本结构、镜头节奏、包装样式等可复用创作方法，再将这些结构迁移到新的主题、商品信息或用户素材上，生成可解释、可调整、可验证的短视频方案与 demo。

项目的 P0 目标不是实现一个完整剪辑软件，也不是直接复刻样例视频，而是打通以下核心闭环：

```text
样例视频输入
→ 视频理解与结构拆解
→ 结构槽位标准化
→ 新内容与用户素材分析
→ 槽位匹配与素材缺口识别
→ 补全策略生成
→ 分镜 / 时间线 / 包装方案 / 视频 demo 输出
→ 迁移过程可视化
```

系统核心卖点是“可解释的结构迁移”：评审和用户能够清楚看到样例中抽取了什么结构、这些结构如何映射到新内容、哪些槽位发生素材缺口、系统如何补全，以及最终结果如何生成。

## 2. 设计目标

### 2.1 P0 目标

P0 阶段必须完成比赛评分中最关键的闭环能力：

1. 支持上传 1 条或多条样例视频。
2. 展示样例视频基础信息，包括时长、分辨率、镜头数、字幕 / 语音概览、关键帧、封面。
3. 至少拆解脚本结构、节奏结构、包装结构中的 2 类，推荐 P0 直接完成 3 类的基础版本。
4. 支持输入新主题、商品卖点、文案、图片、视频中的至少一种。
5. 基于结构槽位进行素材匹配，识别缺口并解释影响。
6. 至少支持 2 种补全策略：文案 / 字幕补全、包装补全、现有素材重组。AIGC 补全作为可插拔能力。
7. 输出脚本、分镜、时间线草案、包装建议、视频 demo 中的至少 2 项，推荐 P0 输出分镜 + 时间线 + HyperFrames demo。
8. 前端可视化展示“样例结构 → 新素材映射 → 缺口补全 → 生成结果”。

### 2.2 P1 目标

P1 阶段在 P0 数据结构和模块边界上扩展：

1. 多版本生成：高点击版、高转化版、高节奏版、高质感版。
2. 更完整的包装能力：字幕样式、标题条、卖点卡片、转场建议、封面方案、贴纸推荐。
3. 真实素材适配：镜头分类、高光片段筛选、商品 / 人物 / 场景识别、素材推荐。
4. 人工可调：hook 方式、卖点顺序、包装风格、视频节奏、结尾表达。
5. 自然语言改片：将一句话指令解析为结构、节奏、包装、素材映射或时间线变更。

### 2.3 暂缓目标

以下能力不进入 P0 主线，但设计上保留扩展点：

1. 完整时间轴剪辑器。
2. 多用户协作。
3. 复杂知识库自动合并与长期学习。
4. 音乐生成。
5. 大规模素材资产管理。
6. 完整 AIGC 生视频生产链路。

## 3. 总体架构

系统采用前后端分离架构：

```text
apps/web                Next.js 前端
services/api            Python API 服务
services/worker         Python 异步任务 Worker
packages/contracts      TypeScript / JSON Schema 契约
packages/prompts        Prompt 模板与 Agent 角色定义
storage                 本地任务产物与知识库文件
```

推荐 P0 使用 SQLite + 文件系统：

1. SQLite 存任务状态、视频记录、结构 JSON、素材索引、版本信息。
2. 文件系统存原始视频、关键帧、音频、字幕、渲染产物、Markdown 知识沉淀。
3. 后续如需要云端部署或多人协作，可以平滑迁移到 PostgreSQL + 对象存储。

## 4. 推荐项目结构

```text
VideoMaker/
  apps/
    web/
      app/
      components/
      features/
        sample-analysis/
        structure-mapping/
        gap-report/
        timeline-preview/
        generation-result/
      lib/
      styles/

  services/
    api/
      app/
        main.py
        routers/
          projects.py
          samples.py
          assets.py
          structures.py
          generations.py
          render.py
        schemas/
        services/
        db/
        settings.py

    worker/
      app/
        tasks/
          analyze_sample.py
          extract_structure.py
          analyze_assets.py
          map_slots.py
          generate_plan.py
          render_demo.py
        tools/
          ffmpeg_tool.py
          whisper_tool.py
          opencv_tool.py
          ocr_tool.py
          llm_tool.py
          hyperframes_tool.py
        pipelines/
          sample_pipeline.py
          generation_pipeline.py
        runtime/
          task_context.py
          artifact_store.py

  packages/
    contracts/
      video-structure.schema.json
      asset-inventory.schema.json
      gap-report.schema.json
      generation-plan.schema.json
      render-timeline.schema.json
      api-types.ts

    prompts/
      agents/
        structure_analyst.md
        content_strategist.md
        slot_mapper.md
        gap_planner.md
        storyboard_writer.md
        packaging_designer.md
        critique_reviser.md
      templates/

  storage/
    projects/
      {projectId}/
        samples/
        assets/
        artifacts/
        renders/
        logs/
        knowledge/

  docs/
    architecture/
    demos/
    superpowers/
      specs/
```

## 5. 核心领域模型

### 5.1 Project

Project 是一次创作任务的容器。

```ts
type Project = {
  id: string;
  name: string;
  status: "draft" | "analyzing" | "planning" | "rendering" | "completed" | "failed";
  createdAt: string;
  updatedAt: string;
  sampleVideoIds: string[];
  assetIds: string[];
  selectedStructureId?: string;
  currentGenerationId?: string;
};
```

### 5.2 SampleVideo

```ts
type SampleVideo = {
  id: string;
  projectId: string;
  sourceType: "upload" | "url";
  sourceUri: string;
  localPath: string;
  metadata: VideoMetadata;
  analysisStatus: TaskStatus;
  structureId?: string;
};
```

### 5.3 VideoStructure

VideoStructure 是系统最重要的契约。它是结构迁移、可视化、素材匹配和后续知识沉淀的权威数据源。

```ts
type VideoStructure = {
  id: string;
  projectId: string;
  sourceVideoId: string;
  version: string;
  metadata: VideoMetadata;
  narrative: NarrativeStructure;
  rhythm: RhythmProfile;
  packaging: PackagingProfile;
  slots: StructureSlot[];
  evidence: StructureEvidence[];
  confidence: number;
};
```

### 5.4 NarrativeStructure

```ts
type NarrativeStructure = {
  summary: string;
  segments: NarrativeSegment[];
};

type NarrativeSegment = {
  id: string;
  role: "hook" | "problem" | "solution" | "proof" | "benefit" | "comparison" | "cta" | "transition";
  startSec: number;
  endSec: number;
  scriptSummary: string;
  visualSummary: string;
  intent: string;
};
```

### 5.5 RhythmProfile

```ts
type RhythmProfile = {
  totalDurationSec: number;
  shotCount: number;
  avgShotDurationSec: number;
  tempo: "slow" | "medium" | "fast" | "mixed";
  climaxSec?: number;
  beatPoints: number[];
  shotBoundaries: ShotBoundary[];
};

type ShotBoundary = {
  startSec: number;
  endSec: number;
  confidence: number;
  changeReason: "visual_cut" | "scene_change" | "caption_change" | "beat" | "unknown";
};
```

### 5.6 PackagingProfile

```ts
type PackagingProfile = {
  subtitleStyle?: SubtitleStyle;
  titleCards: TitleCardPattern[];
  stickers: StickerPattern[];
  transitions: TransitionPattern[];
  coverStyle?: CoverStyle;
  visualDensity: "low" | "medium" | "high";
};
```

### 5.7 StructureSlot

StructureSlot 是样例结构迁移的最小单元。

```ts
type StructureSlot = {
  id: string;
  segmentId: string;
  role:
    | "hook_visual"
    | "hook_text"
    | "product_closeup"
    | "usage_scene"
    | "benefit_card"
    | "comparison"
    | "proof"
    | "transition"
    | "cta";
  startSec: number;
  endSec: number;
  requiredAssetType: Array<"video" | "image" | "text" | "voiceover" | "generated_visual" | "packaging">;
  visualIntent: string;
  scriptIntent: string;
  packagingHint?: string;
  importance: "must_have" | "recommended" | "optional";
  constraints: SlotConstraint[];
};
```

### 5.8 AssetInventory

```ts
type AssetInventory = {
  id: string;
  projectId: string;
  userBrief: UserBrief;
  assets: UserAsset[];
  extractedFacts: ContentFact[];
  candidateMoments: CandidateMoment[];
};

type UserBrief = {
  topic?: string;
  productName?: string;
  sellingPoints: string[];
  targetAudience?: string;
  tone?: string;
  mustMention: string[];
  avoidMention: string[];
};
```

### 5.9 GapReport

```ts
type GapReport = {
  id: string;
  projectId: string;
  structureId: string;
  inventoryId: string;
  slotMatches: SlotMatch[];
  missingSlots: MissingSlot[];
  weakSlots: WeakSlot[];
  summary: string;
};

type SlotMatch = {
  slotId: string;
  assetId?: string;
  momentId?: string;
  matchScore: number;
  matchReason: string;
};

type MissingSlot = {
  slotId: string;
  reason: string;
  impact: "low" | "medium" | "high";
  suggestedFixes: CompletionStrategy[];
};
```

### 5.10 GenerationPlan

```ts
type GenerationPlan = {
  id: string;
  projectId: string;
  structureId: string;
  inventoryId: string;
  gapReportId: string;
  variant: GenerationVariant;
  storyboard: StoryboardScene[];
  timeline: RenderTimeline;
  packagingPlan: PackagingPlan;
  completionActions: CompletionAction[];
};

type GenerationVariant =
  | "default"
  | "high_click"
  | "high_conversion"
  | "fast_paced"
  | "premium";
```

### 5.11 RenderTimeline

RenderTimeline 是前端时间线展示和 HyperFrames 渲染的共同契约。

```ts
type RenderTimeline = {
  durationSec: number;
  tracks: TimelineTrack[];
};

type TimelineTrack = {
  id: string;
  type: "video" | "image" | "text" | "voiceover" | "bgm" | "effect" | "transition";
  clips: TimelineClip[];
};

type TimelineClip = {
  id: string;
  startSec: number;
  endSec: number;
  sourceRef?: string;
  content?: string;
  styleRef?: string;
  transform?: ClipTransform;
  generatedBy?: string;
};
```

## 6. 核心模块设计

### 6.1 样例解析模块

职责：

1. 接收上传视频或外部链接。
2. 使用 FFmpeg 提取元信息、音频、关键帧。
3. 使用 OpenCV 做镜头切分和关键帧筛选。
4. 使用 fast-whisper 做 ASR。
5. 可选使用 OCR 抽取硬字幕。
6. 输出 SampleAnalysisResult。

P0 要求：

1. 可稳定处理本地视频。
2. 外部链接下载使用 yt-dlp 作为可选能力。
3. 所有中间产物落盘，支持重试复用。

### 6.2 结构拆解模块

职责：

1. 根据 ASR、OCR、关键帧、镜头边界和音频节奏生成 VideoStructure。
2. 将视频拆成 NarrativeSegment 和 StructureSlot。
3. 为每个结构判断证据来源和置信度。

实现建议：

1. 规则算法负责基础事实：时长、镜头边界、字幕密度、音频节奏点。
2. LLM 负责语义解释：hook 类型、卖点推进、CTA 意图、包装风格描述。
3. 结构输出必须通过 JSON Schema 校验。

### 6.3 知识沉淀模块

职责：

1. 将 VideoStructure 转换成可读 Markdown 结构经验。
2. 按视频类别、行业、风格进行归档。
3. 后续可作为 LLM 参考上下文。

设计规定：

1. P0 中 VideoStructure JSON 是权威数据源。
2. Markdown skill 是可读沉淀，不作为唯一系统数据源。
3. 知识合并、相似风格判断、自动进化进入 P1 或暂缓阶段。

### 6.4 用户素材分析模块

职责：

1. 分析用户输入的主题、商品卖点、文案。
2. 分析用户上传的图片和视频素材。
3. 生成 AssetInventory。

P0 可实现：

1. 文本信息结构化。
2. 图片 / 视频基础元信息。
3. 视频关键帧和片段候选。
4. 简单的商品、人物、场景描述。

P1 扩展：

1. 高光片段筛选。
2. 开头 / 中段 / 结尾素材推荐。
3. 更细粒度的视觉语义标签。

### 6.5 槽位匹配模块

职责：

1. 将 StructureSlot 与 AssetInventory 进行匹配。
2. 输出 SlotMatch、MissingSlot、WeakSlot。
3. 给出缺口原因和影响。

匹配策略：

1. 类型匹配：槽位需要视频、图片、文本还是包装。
2. 语义匹配：槽位意图与素材标签 / 文案事实是否一致。
3. 时长匹配：素材可用片段是否能覆盖槽位时长。
4. 重要度匹配：must_have 槽位优先满足。

### 6.6 缺口补全模块

职责：

1. 根据 GapReport 选择补全策略。
2. 输出 CompletionAction。
3. 解释每个补全动作为什么合理。

P0 支持策略：

1. 文案 / 字幕补全：用卖点卡片、字幕、旁白补足画面不足。
2. 包装补全：用标题条、强调贴纸、转场、背景板增强表达。
3. 现有素材重组：裁切、放大、重复、慢放、重排已有素材。

P1 支持策略：

1. AIGC 生图补全。
2. AIGC 生视频补全。
3. TTS 旁白补全。
4. 封面生成。

### 6.7 脚本与分镜生成模块

职责：

1. 根据 VideoStructure、AssetInventory、GapReport 生成脚本。
2. 将脚本拆成 StoryboardScene。
3. 为每个分镜绑定素材、文案、包装和时间范围。

设计规定：

1. 分镜必须可以追溯到原始结构槽位。
2. 每个分镜必须标记素材来源：用户素材、包装补全、AIGC 补全、文本补全。
3. 输出必须能转成 RenderTimeline。

### 6.8 视频组装与渲染模块

职责：

1. 将 RenderTimeline 转换为 HyperFrames composition。
2. 合成字幕、图片、视频、旁白、BGM、转场和包装元素。
3. 输出可播放 demo。

P0 策略：

1. 优先使用 HyperFrames 生成稳定、可控、可解释的 demo。
2. 不依赖高成本生视频模型作为主链路。
3. 每次渲染保留 composition、配置、日志和最终视频。

### 6.9 人机协同模块

P0 先支持参数化调整：

1. hook 风格：痛点型、冲突型、结果型、悬念型。
2. 节奏：快节奏、标准、质感慢节奏。
3. 卖点顺序：价格优先、功能优先、场景优先。
4. 包装强度：轻、中、重。

P1 支持自然语言编辑：

```text
用户指令
→ EditIntent
→ 修改 VideoStructure / GenerationPlan / RenderTimeline
→ 重新生成受影响部分
```

自然语言编辑不能直接改最终视频文件，必须先落到结构化 EditIntent，便于解释和回滚。

## 7. Agent 设计

系统采用“受约束的多 Agent 流水线”，而不是让一个 Agent 自由调用所有工具。

### 7.1 Agent 列表

| Agent | 职责 | 输入 | 输出 |
| --- | --- | --- | --- |
| StructureAnalyst | 样例结构拆解 | SampleAnalysisResult | VideoStructure |
| ContentStrategist | 新内容策略整理 | UserBrief, AssetInventory | ContentPlan |
| SlotMapper | 槽位匹配 | VideoStructure, AssetInventory | SlotMatch[] |
| GapPlanner | 缺口补全规划 | GapReport | CompletionAction[] |
| StoryboardWriter | 脚本与分镜生成 | VideoStructure, AssetInventory, CompletionAction[] | StoryboardScene[] |
| PackagingDesigner | 包装方案生成 | VideoStructure, StoryboardScene[] | PackagingPlan |
| CritiqueReviser | 评估与修改 | GenerationPlan, UserFeedback | RevisedGenerationPlan |

### 7.2 Agent 约束

1. Agent 输入输出必须使用契约 JSON。
2. Agent 不直接读写任意文件，只通过 TaskContext 获取允许的 artifact。
3. Agent 不直接调用外部模型 API，由 LLMTool 统一代理。
4. Agent 输出必须通过 schema 校验，失败则进入修复或重试。
5. 每次 Agent 调用记录 prompt、输入摘要、输出、耗时、模型名和成本。

## 8. 工具协议

所有工具通过统一 ToolResult 返回：

```ts
type ToolResult<T> = {
  ok: boolean;
  data?: T;
  error?: ToolError;
  artifacts: ArtifactRef[];
  metrics?: Record<string, number | string>;
};

type ToolError = {
  code: string;
  message: string;
  retryable: boolean;
  details?: unknown;
};

type ArtifactRef = {
  id: string;
  type: "video" | "audio" | "image" | "json" | "text" | "html" | "render";
  uri: string;
  createdAt: string;
};
```

### 8.1 工具列表

| Tool | P0 必需 | 职责 |
| --- | --- | --- |
| FFmpegTool | 是 | 元信息、音频抽取、裁切、转码 |
| WhisperTool | 是 | ASR 转写 |
| OpenCVTool | 是 | 镜头切分、关键帧提取 |
| OCRTool | 可选 | 硬字幕提取 |
| LLMTool | 是 | 结构拆解、文案生成、补全规划 |
| HyperFramesTool | 是 | demo 渲染 |
| YtDlpTool | 可选 | 外部链接下载 |
| ImageGenerationTool | P1 | 生图补全 |
| VideoGenerationTool | P1 | 生视频补全 |
| TTSTool | P1 | 旁白合成 |

## 9. API 设计

### 9.1 Project API

```http
POST /api/projects
GET /api/projects/{projectId}
GET /api/projects/{projectId}/timeline
```

### 9.2 Sample API

```http
POST /api/projects/{projectId}/samples
POST /api/samples/{sampleId}/analyze
GET /api/samples/{sampleId}/analysis
GET /api/samples/{sampleId}/structure
```

### 9.3 Asset API

```http
POST /api/projects/{projectId}/assets
POST /api/projects/{projectId}/brief
POST /api/projects/{projectId}/assets/analyze
GET /api/projects/{projectId}/inventory
```

### 9.4 Generation API

```http
POST /api/projects/{projectId}/map-slots
GET /api/projects/{projectId}/gap-report
POST /api/projects/{projectId}/generation-plan
POST /api/generations/{generationId}/render
GET /api/generations/{generationId}
POST /api/generations/{generationId}/revise
```

### 9.5 Task API

```http
GET /api/tasks/{taskId}
POST /api/tasks/{taskId}/retry
POST /api/tasks/{taskId}/cancel
```

## 10. 前端产品设计

P0 前端建议采用一个项目工作台页面，核心展示四个区域：

1. 样例结构区：展示样例视频、关键帧、脚本段落、节奏曲线、包装标签。
2. 素材映射区：展示用户素材如何匹配到结构槽位。
3. 缺口补全区：展示缺失槽位、影响、补全策略和补全后结果。
4. 结果预览区：展示分镜、时间线和视频 demo。

推荐页面：

```text
/projects
/projects/{projectId}
/projects/{projectId}/sample-analysis
/projects/{projectId}/structure-mapping
/projects/{projectId}/generation
/projects/{projectId}/renders/{generationId}
```

可视化重点：

1. 槽位卡片：每个 StructureSlot 显示角色、时间范围、意图、重要度。
2. 映射连线：从样例槽位连接到用户素材或补全动作。
3. 缺口标签：缺失、弱匹配、已补全。
4. 时间线预览：按 track 展示视频、图片、字幕、旁白、包装和转场。
5. 对比视图：样例结构与生成结果并排展示。

## 11. 数据存储设计

### 11.1 SQLite 表

```text
projects
sample_videos
user_assets
video_structures
asset_inventories
gap_reports
generation_plans
render_outputs
tasks
artifacts
agent_runs
```

### 11.2 文件系统约定

```text
storage/projects/{projectId}/
  samples/{sampleId}/
    original.mp4
    audio.wav
    metadata.json
    transcript.json
    keyframes/
    shots.json

  assets/{assetId}/
    original
    metadata.json
    analysis.json

  artifacts/
    video-structure-{structureId}.json
    asset-inventory-{inventoryId}.json
    gap-report-{gapReportId}.json
    generation-plan-{generationId}.json

  renders/{generationId}/
    composition/
    preview.html
    output.mp4
    render-log.json

  knowledge/
    structure-skill.md
```

## 12. 任务与中断恢复

每个长任务必须具备：

1. taskId。
2. 当前阶段。
3. 输入 artifact 列表。
4. 输出 artifact 列表。
5. 可重试标记。
6. 错误码和错误详情。

任务状态：

```ts
type TaskStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "retrying";
```

中断恢复原则：

1. 每个阶段完成后落盘结构化 artifact。
2. 重试时优先复用已存在 artifact。
3. 不覆盖旧 generation，修改产生新版本。
4. 渲染失败不影响已生成的脚本、分镜和时间线。

## 13. 长任务进度展示

视频解析、结构拆解、素材分析、补全规划和视频渲染都是长任务。前端需要展示阶段进度、当前产物、错误信息，并支持页面刷新后恢复状态。

### 13.1 通信策略

P0 推荐采用：

```text
SSE 作为主通道
轮询作为降级通道
tasks 表和 artifacts 表作为权威状态源
```

不优先使用 WebSocket。当前场景主要是服务端向前端单向推送任务状态，SSE 更轻、更容易调试，也足以覆盖阶段式进度展示。

接口约定：

```http
POST /api/tasks
GET /api/tasks/{taskId}
GET /api/tasks/{taskId}/events
POST /api/tasks/{taskId}/retry
POST /api/tasks/{taskId}/cancel
```

前端行为：

1. 发起长任务后拿到 taskId。
2. 优先连接 `GET /api/tasks/{taskId}/events` 接收 SSE。
3. SSE 断开后自动重连 2-3 次。
4. 多次失败后切换到 `GET /api/tasks/{taskId}`，每 2-5 秒轮询一次。
5. 页面刷新后根据 taskId 拉取当前任务状态并恢复 UI。
6. 每个阶段完成后展示已生成 artifact，例如字幕、关键帧、结构 JSON、时间线或视频 demo。

核心原则：SSE 是实时通知通道，不是权威状态源。数据库中的 task 状态和 artifact 记录才是恢复、重试和前端展示的权威数据。

### 13.2 TaskEvent 契约

```ts
type TaskEvent = {
  taskId: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled" | "retrying";
  stage:
    | "uploading"
    | "extracting_metadata"
    | "extracting_audio"
    | "transcribing"
    | "detecting_shots"
    | "extracting_keyframes"
    | "extracting_structure"
    | "analyzing_assets"
    | "mapping_slots"
    | "planning_completion"
    | "generating_storyboard"
    | "building_timeline"
    | "rendering"
    | "completed";
  progress: number;
  message: string;
  artifactRefs?: ArtifactRef[];
  error?: ToolError;
  updatedAt: string;
};
```

`progress` 范围为 0-100。P0 不追求 token 级或帧级精确进度，采用阶段加权即可。

### 13.3 阶段加权建议

样例分析任务：

```text
元信息提取 10%
音频抽取 15%
ASR 25%
镜头切分 20%
关键帧提取 10%
结构拆解 20%
```

生成任务：

```text
素材分析 15%
槽位匹配 15%
缺口规划 15%
分镜生成 20%
时间线生成 15%
渲染 20%
```

如果某阶段失败，任务进入 `failed`，保留已完成 artifact。用户点击重试时，从最近一个可复用 artifact 继续，而不是从头执行。

## 14. 安全边界

### 14.1 文件安全

1. 用户上传文件只能存储在当前 project 目录。
2. 禁止工具访问 project sandbox 之外的任意路径。
3. 外部链接下载必须限制文件大小、时长和格式。
4. 文件名统一生成，不信任用户原始文件名。

### 14.2 模型安全

1. LLM 输出必须经过 schema 校验。
2. 不执行模型生成的任意代码。
3. Prompt 中明确禁止复制样例内容，只迁移结构方法。
4. 对外部 API key 使用服务端环境变量，不暴露给前端。

### 14.3 内容安全

1. 记录用户输入和生成内容来源。
2. AIGC 补全内容标记为 generated。
3. 支持敏感词或违规内容拦截扩展点。
4. 对样例视频保留“结构迁移，不复刻内容”的版权边界说明。

## 15. 可观测性

P0 初期推荐使用日志 + 本地 artifact，Langfuse 作为可选增强。系统必须先保证任务恢复、artifact 追溯和本地调试能力，再接入外部观测平台。

必须记录：

1. 每个任务的状态变化。
2. 每个工具调用的输入摘要、输出 artifact、耗时、错误。
3. 每次 Agent 调用的模型名、prompt 版本、输出校验结果。
4. 每次生成的 GenerationPlan 和 RenderTimeline。

可观测性目标不是复杂监控，而是便于 demo 出错时定位问题，并便于在答辩中展示系统链路。

### 15.1 本地观测优先

P0 工程初始化和闭环早期先实现：

1. 每个 task 的输入、输出、状态变化和错误落库。
2. 每个工具调用的输入摘要、输出 artifact、耗时和错误落盘。
3. 每个 Agent 的 prompt 版本、输入摘要、输出 JSON、schema 校验结果落盘。
4. 每个 GenerationPlan 和 RenderTimeline 可追溯。

这些数据是任务恢复、前端展示和答辩复盘的基础，不应依赖 Langfuse 才能工作。

### 15.2 Langfuse 接入时机

建议在以下条件满足后接入 Langfuse：

1. 已经有 3 个以上稳定 Agent，例如结构拆解、槽位匹配、缺口规划、分镜生成。
2. Prompt 开始频繁迭代，需要比较不同 prompt 版本效果。
3. 需要观察模型成本、耗时、失败率和输出质量。
4. 需要回放一次完整生成链路，分析生成质量问题。
5. 准备演示或答辩，希望展示系统不是黑盒调用模型。

Langfuse 适合记录：

1. Prompt 版本。
2. 一次完整生成链路的 trace。
3. 每个 Agent 的输入摘要和输出。
4. 模型名、耗时、token、成本。
5. 人工反馈标记和质量评分。

Langfuse 不作为以下内容的权威存储：

1. 视频文件。
2. 大型二进制 artifact。
3. 任务恢复状态。
4. 前端展示所需的结构化业务数据。

### 15.3 ObservabilitySink 抽象

```ts
interface ObservabilitySink {
  recordTaskEvent(event: TaskEvent): Promise<void>;
  recordToolRun(run: ToolRunLog): Promise<void>;
  recordAgentRun(run: AgentRunLog): Promise<void>;
}
```

P0 默认启用：

```text
DatabaseSink
LocalFileSink
```

P1 或 P0 后期增加：

```text
LangfuseSink
```

这样 Langfuse 是增强能力，不会绑定主链路，也不会影响本地 demo 的稳定性。

## 16. 扩展性设计

### 16.1 模型可替换

所有模型调用走统一接口：

```ts
type ModelRequest = {
  task: string;
  inputs: unknown;
  schema?: unknown;
  options?: {
    model?: string;
    temperature?: number;
    maxTokens?: number;
  };
};
```

这样可以替换文本模型、多模态模型、生图模型、生视频模型和 TTS 服务。

### 16.2 补全策略可插拔

```ts
interface CompletionStrategyProvider {
  name: string;
  canHandle(slot: StructureSlot, context: GapContext): boolean;
  plan(slot: StructureSlot, context: GapContext): CompletionAction;
}
```

P0 注册：

1. TextCompletionProvider。
2. PackagingCompletionProvider。
3. AssetReuseProvider。

P1 注册：

1. ImageGenerationProvider。
2. VideoGenerationProvider。
3. TTSProvider。

### 16.3 渲染后端可替换

P0 使用 HyperFrames。后续可以增加 Remotion 或 FFmpeg 原生合成，但 RenderTimeline 不变。

```ts
interface RenderBackend {
  name: string;
  render(timeline: RenderTimeline, options: RenderOptions): Promise<RenderOutput>;
}
```

### 16.4 知识库可扩展

P0：

1. 每个样例生成 Markdown 结构总结。
2. 人工选择是否加入知识库。

P1：

1. 按行业、风格、时长、结构类型索引。
2. 支持相似结构推荐。
3. 支持知识条目合并和版本管理。

## 17. 开发分工建议

### 17.1 前端方向

1. 项目工作台。
2. 样例分析展示。
3. 结构槽位卡片。
4. 缺口报告展示。
5. 分镜和时间线可视化。
6. 渲染结果预览。

### 17.2 后端 API 方向

1. 项目、样例、素材、任务、生成 API。
2. SQLite schema。
3. artifact 管理。
4. task 状态管理和重试。

### 17.3 视频分析方向

1. FFmpeg 元信息和音频抽取。
2. Whisper ASR。
3. OpenCV 镜头切分。
4. 关键帧提取。
5. OCR 可选。

### 17.4 Agent 与生成方向

1. Prompt 和 Agent 输出 schema。
2. VideoStructure 生成。
3. 槽位匹配。
4. GapReport 和 GenerationPlan。
5. 脚本、分镜、包装生成。

### 17.5 渲染方向

1. RenderTimeline 到 HyperFrames 的转换。
2. 字幕、标题条、卖点卡片、转场组件。
3. preview.html 和 output.mp4 生成。

## 18. P0 实施里程碑

### Milestone 1：基础工程与契约

1. 初始化 monorepo。
2. 建立 contracts。
3. 建立 API 和 worker 骨架。
4. 建立 SQLite 和 artifact store。

### Milestone 2：样例分析

1. 上传样例视频。
2. 提取元信息、音频、关键帧、镜头边界。
3. ASR 转写。
4. 前端展示基础分析结果。

### Milestone 3：结构拆解

1. 生成 VideoStructure。
2. 前端展示 narrative、rhythm、packaging、slots。
3. 生成 Markdown 结构总结。

### Milestone 4：素材输入与槽位匹配

1. 输入新主题 / 商品信息 / 用户素材。
2. 生成 AssetInventory。
3. 执行 SlotMapper。
4. 输出 GapReport。

### Milestone 5：补全与生成计划

1. 支持文案补全。
2. 支持包装补全。
3. 支持素材重组。
4. 输出 Storyboard 和 RenderTimeline。

### Milestone 6：视频 demo 与展示

1. HyperFrames 渲染 demo。
2. 前端展示分镜、时间线、视频结果。
3. 支持基础参数调整并生成新版本。

## 19. 验收标准

P0 完成时应能演示：

1. 上传一个样例视频并看到基础解析结果。
2. 看到结构拆解结果，包括脚本段落、节奏信息、包装信息。
3. 输入新主题和少量素材。
4. 看到系统识别出哪些结构槽位已匹配、哪些缺失。
5. 看到每个缺口的补全策略。
6. 生成新的脚本、分镜和时间线。
7. 渲染出一个可播放视频 demo。
8. 修改一个参数后生成新版本，并且旧版本不被覆盖。

## 20. 主要风险与应对

### 20.1 范围过大

风险：同时做完整剪辑器、AIGC 生视频、知识库进化，会拖慢 P0。

应对：P0 只做结构迁移闭环，其他能力通过接口和数据结构保留扩展点。

### 20.2 模型输出不稳定

风险：LLM 结构拆解或生成结果不符合格式。

应对：所有输出走 JSON Schema 校验；失败时自动修复或重试；保留原始输出用于调试。

### 20.3 AIGC 成本和耗时不可控

风险：生图 / 生视频影响 demo 稳定性。

应对：P0 不依赖 AIGC 视频；优先用 HyperFrames、文案补全、包装补全和素材重组。

### 20.4 视频分析精度不足

风险：镜头切分、字幕识别、BGM 分析不够准确。

应对：P0 采用“算法事实 + LLM 解释”的混合方式，前端展示置信度，不追求全自动完美。

### 20.5 展示效果不足

风险：后台能力做了很多，但评审看不到迁移过程。

应对：将结构槽位、素材映射、缺口补全、时间线对比作为前端一等功能。

## 21. 技术选型结论

1. 前端：Next.js + TypeScript。
2. 后端：Python FastAPI。
3. 异步任务：P0 可先用轻量本地队列；后续接 Celery / RQ / Dramatiq。
4. 数据库：P0 SQLite；后续 PostgreSQL。
5. 文件存储：P0 本地 storage；后续对象存储。
6. 视频工具：FFmpeg、OpenCV。
7. ASR：fast-whisper。
8. 音频分析：librosa / pydub 作为可选增强。
9. 渲染：HyperFrames。
10. 模型：文本、多模态、生图、生视频、TTS 均通过统一 ModelGateway 接入。
11. 可观测性：本地日志 + artifact；Langfuse 可选接入。

## 22. 结论

本设计将 VideoMaker 收敛为一个“可解释的爆款视频结构迁移系统”。P0 阶段优先实现样例解析、结构抽取、槽位匹配、缺口补全、时间线生成和 HyperFrames demo，确保比赛要求中的基础闭环、素材缺口处理、展示可验证能力能够稳定完成。

系统通过 VideoStructure、AssetInventory、GapReport、GenerationPlan、RenderTimeline 五个核心契约保证模块边界清晰，便于前端、后端、视频分析、Agent 生成和渲染模块并行开发。P1 和暂缓能力均围绕这些契约扩展，避免后续推倒重来。
