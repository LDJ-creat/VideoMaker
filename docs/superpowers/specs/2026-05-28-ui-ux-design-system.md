# VideoMaker UI/UX Design System

> 本规范指导 VideoMaker 的前端交互与视觉设计，确保 "Explainable Structure Migration"（可解释的结构迁移）流程的直观性。

## 1. 核心交互原则 (UX Principles)

- **AI 过程“白盒化” (Explainable AI Process)**：针对任务进度不能只用一个 Loading 圈。使用类似“控制台日志 + 步进器”的混合 UI，将分析步骤（如下载、解析音频、识别场景、提取结构槽）清晰呈现给用户。
- **Gap 分析的引导式映射 (Actionable Gap Visualization)**：
  - **绿色 (Match/Success)**：用户的 Asset 完美匹配结构槽。
  - **琥珀色 (Warning/Weak)**：弱匹配（如方向相关但画质差/时长不够），允许通过但建议关注。
  - **红色 (Danger/Missing)**：缺失关键素材。必须在 Gap Card 内直接提供 "Upload Asset" 或 "Generate" 的行动按钮（Call-to-Action）。
- **非侵入式的多轨呈现 (Compact Timeline Previews)**：采用紧凑的轨道块设计（A轨视频/图片，B轨文字/过度，C轨音频）。支持悬停级微缩预览（Scrubbing），不做重型专业非编（NLE）软件的臃肿 UI。

## 2. 全局样式与双主题系统 (Dual-Theme System)

项目基于 **Tailwind CSS** 与 **shadcn/ui** 实现主题无缝切换。默认主推明亮、通透的 **便当盒 SaaS 风 (Bento Grid)**，同时支持一键切换为 **深色专业工作台风 (Pro-dark Marginalist)**。

### 2.1 布局范式：便当盒网格 (Bento Grid)
- **卡片化**：所有功能区（输入面板、Gap 报告、Timeline）均设计为独立的 Bento Box 实心卡片。
- **呼吸感**：去除沉重的阴影设置。模块隔离通过微妙的浅色边框包裹和一致的间距（如 `gap-4` 或 `gap-6`）来实现透气感。

### 2.2 字体排版 (Typography)
- **界面字体 (UI)**：`Inter` 或 `Geist Sans`（或系统无衬线体）。追求现代、极简与高可读性。
- **代码与数据 (Data & Logs)**：`JetBrains Mono` 或 `Geist Mono`。用于展示 JSON 槽位提取结果、任务时间戳和进度详情。

### 2.3 语义与颜色变量 (Semantic Color Tokens)

依靠 `shadcn/ui` 的 `globals.css` 变量（如 `bg-background`、`text-primary`）开发，禁止在组件中 Hardcode 具体的 Tailwind 灰度色阶。

#### 基础层级 (Background & Surface)
- **Light Mode (Bento 首选)**: 
  - 全局背景 (`background`): `zinc-50` (`#fafafa`)
  - 卡片底色 (`card`): `white` (`#ffffff`)
  - 边框分割 (`border`): `zinc-200` (`#e4e4e7`)
- **Dark Mode (Pro 工作台)**:
  - 全局背景 (`background`): `zinc-950` (`#09090b`)
  - 卡片底色 (`card`): `zinc-900` (`#18181b`)
  - 边框分割 (`border`): `zinc-800` (`#27272a`)

#### 核心色彩状态语义 (Accents & Status)
- **行动点 (Primary Action)**：直接使用对比最强烈的 `primary` 变量。
- **AI 魔法态 (AI Active)**：使用 `violet-500` (`#8b5cf6`) 辅以柔和阴影模拟霓虹发光。
- **红色 / 缺失 (Gap Missing)**：`red-500` (`#ef4444`，对应 shadcn 的 `destructive`)。
- **琥珀色 / 隐患 (Gap Weak)**：`amber-500` (`#f59e0b`)。
- **绿色 / 匹配 (Gap Matched) 或 音频轨**：`emerald-500` (`#10b981`)。
- **蓝色 / 视频时间轨基色**：`blue-500` (`#0ea5e9`)。

## 3. 推荐使用的 Shadcn/ui 组件

为保持开发的统一极简审美，P0 阶段优先拼装和扩展以下基础组件：
- **Card**: 作为一切 Bento Grid 模块的基底包裹。
- **ScrollArea**: 用于美化长文本的 AI 进度日志。
- **Badge**: 快速构建 "Matched", "Missing" 的视觉标签。
- **Progress / Skeleton**: 呈现各类异步加载、生成进度的状态展现。
- **Tabs**: 优雅地容纳 "Local Upload" 与 "URL Fetch" 的结构录入区。