# VideoMaker UI/UX Design System

> 本规范指导 VideoMaker 的前端交互与视觉设计，确保「可解释的结构迁移」流程直观、可信，并在全站保持一致的 **暖调创意工作室（Warm Creative Studio）** 品牌气质。
>
> **状态：** 2026-06 首页与全局 tokens 已落地；工作台面板布局仍沿用 Bento 信息架构，视觉已随全局 semantic tokens 换为暖色体系。
>
> **实现源文件：** [`apps/web/app/globals.css`](../../../apps/web/app/globals.css)、[`apps/web/tailwind.config.ts`](../../../apps/web/tailwind.config.ts)、[`apps/web/app/layout.tsx`](../../../apps/web/app/layout.tsx)

---

## 1. 品牌与视觉方向

### 1.1 设计定位

VideoMaker 不是通用「AI 紫渐变 SaaS」，而是 **创意工作者的结构迁移工作台**：

| 维度 | 应传达 | 应避免 |
|------|--------|--------|
| 色彩 | 温暖、可接近、有创作欲（奶白、麦黄、柔和橙） | 冷紫/靛蓝大渐变、纯黑压抑底 |
| 形态 | 编辑感、结构感、步骤清晰 | 装饰大于内容的 Hero 块 |
| 密度 | 专业但不冰冷，留白充足 | 模板化居中 Banner + 空洞网格 |

**气质关键词：** 编辑杂志感 · 创意工作室 · 可解释 · 结构迁移

### 1.2 Logo

- 组件：[`apps/web/components/brand/video-maker-logo.tsx`](../../../apps/web/components/brand/video-maker-logo.tsx)
- 图形语义：胶片帧 + 结构节点连线（3 点）
- 着色：`currentColor`，继承 `text-primary`，深浅色自动适配
- 禁止：字母缩写方块（如 indigo `VM`）、与品牌无关的渐变底

---

## 2. 核心交互原则 (UX Principles)

以下原则在工作台与首页均适用，**不因视觉改版而改变**。

### 2.1 AI 过程「白盒化」(Explainable AI Process)

任务进度不能只有一个 Loading 圈。使用「控制台日志 + 步进器」混合 UI，将分析步骤（下载、解析音频、识别场景、提取结构槽等）清晰呈现。

### 2.2 Gap 分析的引导式映射 (Actionable Gap Visualization)

| 语义 | 颜色 | 用途 |
|------|------|------|
| Match / Success | `emerald-500` | 素材完美匹配结构槽 |
| Warning / Weak | `amber-500` | 弱匹配，允许通过但需关注 |
| Danger / Missing | `destructive` / `red-500` | 缺失关键素材；Gap Card 内须提供 Upload / Generate CTA |

### 2.3 非侵入式多轨呈现 (Compact Timeline Previews)

紧凑轨道块（A 轨视频/图片，B 轨文字/转场，C 轨音频）。支持悬停微缩预览，不做重型 NLE 臃肿 UI。

### 2.4 首页与项目生命周期（2026-06）

| 行为 | 规范 |
|------|------|
| 创建项目 | 输入名称 → **直接进入** `/projects/{id}` 工作台，不在首页停留刷新列表 |
| 工作台标题 | 展示 **项目名称**（`font-serif`），副信息为项目 ID / 当前样例 |
| 删除项目 | 卡片 hover 显示删除；**自定义 ConfirmDialog** 二次确认；后端级联删除 SQLite + `storage/projects/{id}/` |
| destructive 操作 | 使用 `ConfirmDialog` + `variant="destructive"` 按钮，文案说明不可撤销 |

---

## 3. 全局样式与双主题系统

基于 **Tailwind CSS** + **shadcn/ui**，通过 `class` 切换明暗。默认 **浅色暖调工作室**；深色为 **warm stone 暗房**（非纯黑）。

### 3.1 开发约束

- **必须**使用 semantic tokens：`bg-background`、`text-foreground`、`bg-primary`、`border-border`、`text-ai` 等
- **禁止**在业务组件中 hardcode `violet-*` / `indigo-*` 作为品牌色
- **禁止**依赖外部 CDN 纹理（如 grainy-gradients）；使用本地 `.bg-studio-texture`
- Hero / 营销区可用 `studio.cream` / `studio.wheat` / `studio.amber`（见 `tailwind.config.ts`），但 CTA 优先 `bg-primary`

### 3.2 语义色 Token 表

定义于 [`globals.css`](../../../apps/web/app/globals.css)（HSL，Tailwind 通过 `hsl(var(--token))` 引用）。

#### 浅色模式 — 晨光工作室

| Token | HSL | 约 Hex | 用途 |
|-------|-----|--------|------|
| `--background` | `40 33% 98%` | `#FFFBF5` | 页面奶白底 |
| `--foreground` | `24 10% 26%` | `#44403C` | 主文字 |
| `--card` | `0 0% 100%` | `#FFFFFF` | 卡片、输入区实心底 |
| `--primary` | `24 74% 55%` | `#E07A3A` | CTA、链接、焦点环 |
| `--primary-foreground` | `0 0% 100%` | `#FFFFFF` | 主按钮文字 |
| `--secondary` | `38 80% 92%` | `#FEF3C7` | Badge 底、标签区 |
| `--muted` | `30 20% 94%` | — | 次要背景、skeleton |
| `--muted-foreground` | `25 5% 45%` | — | 次要文字 |
| `--border` | `30 10% 88%` | — | 卡片边框 |
| `--ring` | `24 74% 55%` | — | focus ring |
| `--ai` | `32 95% 44%` | `#D97706` | AI / 结构证据 / `Badge variant="ai"` |
| `--destructive` | shadcn 默认红 | — | 删除、错误 |

#### 深色模式 — 暗房工作室

| Token | 说明 |
|-------|------|
| `--background` | `24 10% 10%` warm stone，避免 `#000` |
| `--card` | `24 6% 16%` |
| `--primary` / `--ring` / `--ai` | 琥珀系 `38 92% 50%`，暗底上更醒目 |
| `--border` | `24 6% 22%` |

#### 功能态 accent（Gap / Timeline / Badge，与工作台一致）

- **Primary Action：** `primary`
- **AI Active / 证据高亮：** `ai`（**已弃用** `violet-500` 魔法态）
- **Gap Missing：** `destructive`
- **Gap Weak：** `amber-500` / `Badge variant="warning"`
- **Gap Matched：** `emerald-500` / `Badge variant="success"`
- **视频轨基色：** `blue-500`（时间线预览，待后续统一为 token）

---

## 4. 字体排版 (Typography)

加载于 [`layout.tsx`](../../../apps/web/app/layout.tsx)（`next/font/google`）。

| 层级 | 字体 | Tailwind | 用途 |
|------|------|----------|------|
| 正文 UI | **Noto Sans SC** | `font-sans` | 按钮、表单、说明、流程标签 |
| 标题 / 编辑感 | **Noto Serif SC** | `font-serif` / `.font-display` | 首页 Hero、区块标题、项目名称、工作台主标题 |
| 数据 / 日志 | **Geist Mono** | `font-mono` | 项目 ID、时间戳、任务详情 |

**排版规则：**

- 首页与营销标题：`font-serif font-semibold tracking-tight`，层级 `text-4xl` → `text-6xl`
- 正文：`text-muted-foreground` + `leading-relaxed`；正文色对比度 ≥ 4.5:1（浅色下不用 `gray-400` 作正文）
- **已弃用** 以 `Inter` / `Geist Sans` 作为 UI 主字体

---

## 5. 布局与页面模式

### 5.1 全局壳层

| 区域 | 规范 | 实现 |
|------|------|------|
| 顶栏 | 浮动卡片：`fixed top-4`、圆角 `rounded-2xl`、`bg-background/85 backdrop-blur` | [`app-header.tsx`](../../../apps/web/components/app-header.tsx) |
| 主内容 | `main` 预留顶距 `pt-20 md:pt-24`，避免被顶栏遮挡 | `layout.tsx` |
| 最大宽度 | 首页 `max-w-6xl`；顶栏/主壳 `max-w-7xl` | `projects/page.tsx` |

### 5.2 首页 (`/projects`)

组件目录：[`apps/web/components/home/`](../../../apps/web/components/home/)

```
[ AppHeader 浮动 ]
[ HeroSection — 左文案 + 右 StructureMigrationVisual ]
[ WorkflowStrip — 四步：样例视频 → 结构提取 → 素材匹配 → 生成预览 ]
[ ProjectGrid — 创意库卡片 + 新建占位 ]
```

**Hero：**

- 背景：`from-studio-cream via-background to-studio-wheat` + `.bg-studio-texture`
- 输入区：**实心** `bg-card border shadow-sm rounded-2xl`（非紫渐变玻璃态）
- CTA：`Button` default → `primary` 暖橙

**创意库卡片：**

- 缩略图：按项目名 hash 的暖色渐变 + 胶片孔装饰（[`projectCardTheme.ts`](../../../apps/web/lib/projectCardTheme.ts)）
- 标题：`font-serif`
- Hover：`border-primary/30` + shadow；**禁止** `-translate-y` 引起 layout shift
- 删除：右上角 `Trash2`，hover/focus 显示；确认 [`confirm-dialog.tsx`](../../../apps/web/components/ui/confirm-dialog.tsx)

### 5.3 工作台 (`/projects/{id}`)

- 信息架构仍为 **Bento 卡片网格**（录入、进度、结构、Gap、时间线等独立 Card）
- 顶区：项目名称（serif）+ 项目 ID（mono）+ 操作按钮组
- 视觉继承全局 tokens；后续可单独做工作台布局 polish，不在本规范重复定义

---

## 6. 组件与图标

### 6.1 shadcn/ui 基础组件

| 组件 | 用途 |
|------|------|
| **Card** | Bento 模块基底、项目卡片 |
| **Button** | CTA；destructive 用于确认删除 |
| **Badge** | 状态标签；`ai` / `warning` / `success` 见 [`badge.tsx`](../../../apps/web/components/ui/badge.tsx) |
| **Input** | Hero 创建、表单 |
| **ScrollArea** | AI 进度长日志 |
| **Progress / Skeleton** | 异步加载 |
| **Tabs** | 录入区分栏 |
| **ConfirmDialog** |  destructive 二次确认（自定义，无 Radix Dialog 依赖） |

### 6.2 图标

- **统一 Lucide React**，viewBox 24，`w-4 h-4` / `w-5 h-5` 与上下文一致
- **禁止** emoji 作 UI 图标
- 品牌/流程：`Sparkles`（创建）、`Film` / `Layers` / `Puzzle` / `Play`（流程条）、`Trash2`（删除）

### 6.3 交互微规范

| 规则 | Do | Don't |
|------|----|-------|
| 可点击 | `cursor-pointer` + hover 颜色/边框反馈 | 无 hover 的卡片链接 |
| 过渡 | `transition-colors duration-200`（150–300ms） | 过慢或 layout 位移 hover |
| 焦点 | `focus-visible:ring-2 ring-ring` | 仅依赖颜色 |
| 动效 | 入场可 stagger；`prefers-reduced-motion` 下降级 | 无限装饰动画 |
| 对比 | 浅色玻璃/半透明 ≥ `bg-white/80` 或实心 card | 浅色下 `white/10` 玻璃 |

---

## 7. 反模式清单 (Anti-patterns)

1. **AI 紫渐变 Hero**（`from-violet-600 via-indigo-600`）— 与品牌定位冲突  
2. **indigo/violet 作为 Logo、hover 阴影、Badge 默认色**  
3. **Geist/Inter 作为中文 UI 主字体** — 标题缺乏编辑气质  
4. **卡片 hover `translate-y`** — 导致列表抖动  
5. **删除无确认** — 必须使用 ConfirmDialog  
6. **创建后仅刷新列表** — 必须跳转工作台  
7. **组件内 hardcode zinc 色阶** — 应使用 semantic tokens  

---

## 8. 文件索引（设计与实现对照）

| 类别 | 路径 |
|------|------|
| Design tokens | `apps/web/app/globals.css` |
| Tailwind 扩展 | `apps/web/tailwind.config.ts` |
| 字体 | `apps/web/app/layout.tsx` |
| 顶栏 | `apps/web/components/app-header.tsx` |
| Logo | `apps/web/components/brand/video-maker-logo.tsx` |
| 首页 Hero | `apps/web/components/home/hero-section.tsx` |
| 结构示意 | `apps/web/components/home/structure-migration-visual.tsx` |
| 流程条 | `apps/web/components/home/workflow-strip.tsx` |
| 项目卡片 | `apps/web/components/home/project-card.tsx` |
| 创意库 | `apps/web/components/home/project-grid.tsx` |
| 确认弹窗 | `apps/web/components/ui/confirm-dialog.tsx` |
| 工作台 | `apps/web/features/workbench/ProjectWorkbench.tsx` |
| 删除 API | `DELETE /api/projects/{id}` — `services/api/app/routers/projects.py` |

---

## 9. 后续演进（非阻塞）

- 工作台 Bento 区专项暖色 polish（时间线轨道色 token 化）
- `design-system/MASTER.md` 持久化（ui-ux-pro-max）供跨会话引用
- 项目卡片缩略图接入真实首帧预览（依赖 API 扩展）

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-05-28 | 初版：Bento + 双主题 + violet AI 魔法态 |
| 2026-06-05 | **暖调创意工作室改版**：Noto 字体、暖色 tokens、浮动 Header、首页分栏 Hero、流程条、项目卡片与删除交互、Logo SVG；弃用 violet/indigo 品牌色与 Geist UI 字体 |
