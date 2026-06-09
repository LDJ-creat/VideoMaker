# Knowledge Category Template — UI 规范

> **状态：** 2026-06-09 定稿，供 [Knowledge Category Template Bootstrap Plan](../plans/2026-06-09-knowledge-category-template-bootstrap-plan.md) 前端实现使用。  
> **设计系统基线：** [2026-05-28-ui-ux-design-system.md](./2026-05-28-ui-ux-design-system.md)（Warm Creative Studio）

---

## 1. 设计定位

| 区域 | 用户心智 | 视觉气质 |
|------|----------|----------|
| Hero + WorkflowStrip | 我能做什么 | 营销编辑感、流程可解释 |
| **结构模板库** | 从爆款结构出发 | **Editorial Template Shelf** — 杂志架 / 选片墙 |
| 我的创意库 | 我的进行中项目 | 个人胶片库、hash 渐变占位 |

**记忆点：** 首页首次展示 **真实样例 keyframe 封面**（非项目 hash 渐变）。

**气质关键词：** 编辑杂志感 · 真实参考片 · 结构标签 · 与创意库视觉区分

**禁止：** 紫/靛蓝渐变、与 ProjectCard 完全同构、详情页展示 full skill Markdown、卡片 hover `translate-y`。

---

## 2. 信息架构

```text
/projects 首页
  HeroSection
  WorkflowStrip
  TemplateCategorySection     ← 新增
  ProjectGrid

/templates/{categorySlug}     ← 新增详情
  → POST from-knowledge-template
  → /projects/{id} 工作台
```

- 选用规则：**1 主 entry + 最多 2 参考 entry**（与 `project_knowledge_selection` 一致）
- 详情页 **不上传**；上传留在工作台 Input Wizard
- 创建成功后 **必须** 跳转工作台（§2.4 首页生命周期）

---

## 3. 首页 — TemplateCategorySection

**实现路径：** [`apps/web/components/home/template-category-section.tsx`](../../../apps/web/components/home/template-category-section.tsx)

**挂载：** [`apps/web/app/projects/page.tsx`](../../../apps/web/app/projects/page.tsx) — 插入于 `WorkflowStrip` 与 `ProjectGrid` 之间。

### 3.1 区块 Header

| 元素 | 规范 |
|------|------|
| 标题 | `font-serif text-2xl font-semibold tracking-tight` — 「结构模板库」 |
| 副标题 | `text-sm text-muted-foreground leading-relaxed` |
| 计数 | `rounded-full bg-secondary px-2 py-0.5 text-sm text-muted-foreground`（category 总数） |

### 3.2 TemplateCategoryCard

**路径：** [`apps/web/components/home/template-category-card.tsx`](../../../apps/web/components/home/template-category-card.tsx)

| 断点 | 布局 |
|------|------|
| `< sm` | 横向 scroll + snap，`min-w-[280px]` |
| `sm+` | `grid-cols-2` |
| `lg+` | `grid-cols-3`，首页最多 6 张 |

**Anatomy：**

```text
┌─────────────────────────────┐
│ 封面 aspect-video + 胶片孔   │  有图：`poster.jpg`；无图 **Template Shelf Frame**（纸纹 + 分类 monogram + slot ghost + 内框）
│  [Badge ai] 结构模板         │
├─────────────────────────────┤
│ category (font-serif)        │
│ N 个参考样例 · 更新时间       │
│ slotPattern (font-mono xs)   │
│ summary (line-clamp-2)       │
└─────────────────────────────┘
```

**样式：** `rounded-2xl border border-border bg-card shadow-sm`；hover `border-primary/30 shadow-md`（无位移）。整卡 `Link` → `/templates/{categorySlug}`。

**Fallback 封面（TemplateCoverPlaceholder）：**

| 元素 | 规范 |
|------|------|
| 背景 | 浅色 `from-studio-cream via-background to-studio-wheat` + `bg-studio-texture`；暗色 `dark:from-stone-900/95 dark:via-card dark:to-amber-950/25`（禁止浅黄块） |
| 内框 | `inset-3 rounded-lg border border-primary/10` |
| 中心 | 分类名（最多 5 字，`placeholderDisplayName`）+ 右下角小 `Film` |
| Ghost | 顶部 `slotPatterns[0]`（`font-mono text-[10px] opacity 25%`） |
| 文案 | 「待收录样例封面」 |
| 组件 | [`template-cover-placeholder.tsx`](../../../apps/web/components/home/template-cover-placeholder.tsx) |

**禁止：** 与 ProjectCard 同构的单图标占位、`projectCardTheme` hash 渐变。

### 3.2b ProjectCard 占位（我的创意库）

**Fallback 封面（ProjectCoverPlaceholder）：**

| 元素 | 规范 |
|------|------|
| 背景 | `getProjectCardTheme(name).gradient` + `bg-film-grain` +  subtle 斜向反光 |
| 中心 | 项目名（最多 5 字）+ `Clapperboard` 图标 |
| 文案 | 「等待样例或成片」 |
| Hover | monogram `group-hover:scale-105` |
| 组件 | [`project-cover-placeholder.tsx`](../../../apps/web/components/home/project-cover-placeholder.tsx) |

**禁止：** `Film` / `VideoIcon`、studio 纸纹、cream 暖色块（与模板库区隔）。

### 3.3 状态

| 状态 | UI |
|------|-----|
| Loading | `TemplateCategoryCardSkeleton` ×3 |
| Empty | 不渲染或单行 muted + 知识沉淀说明 |
| Error | `border-destructive/30 bg-destructive/10` + 重试 |

**testid：** `template-category-section`、`template-category-card`

---

## 4. 详情页 — `/templates/[categorySlug]`

**页面：** [`apps/web/app/templates/[categorySlug]/page.tsx`](../../../apps/web/app/templates/[categorySlug]/page.tsx)  
**Feature 模块：** [`apps/web/features/knowledge-template/`](../../../apps/web/features/knowledge-template/)

**壳层：** `max-w-6xl mx-auto`；面包屑 `首页 / 结构模板 / {category 显示名}`（**不用 slug 作标题**）。

### 4.1 Desktop 布局 (lg+)

```text
Breadcrumb
CategoryTemplateHero（全宽）
┌─────────────────┬──────────────────────────┐
│ TemplateSelectionDock │ TemplateEntryGrid    │
│ sticky w-[300px]      │ 2 列 entry cards     │
└─────────────────┴──────────────────────────┘
```

Grid: `lg:grid lg:grid-cols-[300px_1fr] lg:gap-8`

### 4.2 CategoryTemplateHero

**路径：** [`CategoryTemplateHero.tsx`](../../../apps/web/features/knowledge-template/CategoryTemplateHero.tsx)

- `rounded-2xl border bg-card p-6 sm:p-8 shadow-sm`
- Badge：`结构模板 · {entryCount} 个样例参考`
- 标题 `font-serif text-3xl`；summary `line-clamp-3`
- 元数据 Badge 行：`slotPattern`、`tempo`、`durationBucket`（结构相关用 `variant="ai"`）
- lg+ 右侧 optional mosaic（最多 3 poster，轻微旋转；`prefers-reduced-motion` 关闭）

### 4.3 TemplateSelectionDock

**路径：** [`TemplateSelectionDock.tsx`](../../../apps/web/features/knowledge-template/TemplateSelectionDock.tsx)

复用 [`SelectionCurrentZone`](../../../apps/web/features/project-input/SelectionPanelZones.tsx) 语义：

1. **当前选用** — 主样例 1 槽 + 参考 2 槽（`SampleThumbnail sm` + title + 移除）
2. 规则说明 `text-xs text-muted-foreground`
3. 项目名 `Input`（默认 `{category} · {MM-DD}`）
4. CTA 全宽 `用所选模板创建项目` — **testid:** `template-create-project-button`
5. 说明：创建后可在工作台上传素材、填 Brief

`lg:sticky lg:top-28`

### 4.4 TemplateEntryCard

**路径：** [`TemplateEntryCard.tsx`](../../../apps/web/features/knowledge-template/TemplateEntryCard.tsx)

| 选中态 | 边框 |
|--------|------|
| 默认 | `border-border` |
| 主样例 | `border-primary border-l-4 bg-primary/5 ring-1 ring-primary/30` |
| 参考 | `border-ai/40 bg-ai/[0.06]` + Badge「参考」 |
| 不可 import | `opacity-55` + 遮罩「暂不可用」 |

操作：设为主样例 / 加为参考 / 预览（[`SamplePreviewDialog`](../../../apps/web/components/sample-preview-dialog.tsx)）。参考满 2 禁用并 tooltip。

**testid：** `template-entry-card`

### 4.5 Mobile (< lg)

- Hero 全宽；无 mosaic 或单行缩略图
- Entry 单列
- **TemplateSelectionSheet** — 底部固定栏 + sheet（选用清单 + 项目名 + CTA）

**路径：** [`TemplateSelectionSheet.tsx`](../../../apps/web/features/knowledge-template/TemplateSelectionSheet.tsx)

---

## 5. 组件索引

| 组件 | 路径 |
|------|------|
| TemplateCategorySection | `apps/web/components/home/template-category-section.tsx` |
| TemplateCategoryCard | `apps/web/components/home/template-category-card.tsx` |
| CategoryTemplateHero | `apps/web/features/knowledge-template/CategoryTemplateHero.tsx` |
| TemplateSelectionDock | `apps/web/features/knowledge-template/TemplateSelectionDock.tsx` |
| TemplateEntryCard | `apps/web/features/knowledge-template/TemplateEntryCard.tsx` |
| TemplateSelectionSheet | `apps/web/features/knowledge-template/TemplateSelectionSheet.tsx` |
| 详情页 | `apps/web/app/templates/[categorySlug]/page.tsx` |

**复用：** `SampleThumbnail`、`SelectionCurrentZone`、`SamplePreviewDialog`、`Badge`、`Card`、`Button`、`Input`。

**不展示：** 完整 `structure-skill.md`、项目内 `KnowledgeLibraryView` 双栏布局。

---

## 6. Tokens 与排版

- 标题 / category：`font-serif`
- slotPattern：`font-mono text-xs`
- CTA：`bg-primary`
- 结构标签：`Badge variant="ai"`
- 参考选中：`border-ai/40`（与 primary 主样例区分）
- 动效：区块 stagger `motion-safe-animate-in`；hover 仅 color/shadow

---

## 7. 交互与反馈

| 场景 | 行为 |
|------|------|
| 创建成功 | `router.push(/projects/{id})`；可选 toast |
| 参考已满 | toast 或 disabled + tooltip |
| 主样例未选 | CTA disabled |

---

## 8. 无障碍

- 卡片 `aria-label` 含 category 与 entry 数
- 选中 `aria-pressed` 或 live region
- 横向 scroll：`scroll-snap-type: x mandatory`

---

## 9. API 字段对照

| UI | API |
|----|-----|
| 封面 | `coverUrl` / `posterUrl` |
| 显示名 | `category` |
| 不可选 | `importable === false` |

---

## 变更记录

| 日期 | 说明 |
|------|------|
| 2026-06-09 | 初版：Editorial Template Shelf；首页 + 详情；1+2 选用；mobile bottom sheet |
