# 单槽位画面构图（HyperFrames slot）

每个 MaterialSpec 对应 **一个固定时长镜头**，不是多 step 演示网页。原则：一槽一焦点、远观可读、留白充足。

## 一槽一焦点

每槽屏幕只放大 **1 个主信息 + 最多 2 个辅助**：

- hook / 金句：一句 hero 大字 + 可选副标
- 数据：一个 hero 数字 + 单位/语境
- 列表：≤3 条，用 stagger 依次出现（非一次全展示）
- finish 润色：底片为主，overlay 不遮主体

不要把口播全文打字到画面上 — 那是 PPT，不是视频镜头。

## 画幅与安全区

结合 payload `renderTarget`：

| aspectRatio | 画布 | 主标题下限 | 副标题 | 安全边距 |
|-------------|------|------------|--------|----------|
| 9:16 | 1080×1920 | 72–96px | 40–52px | 左右 8% / 上下 12% |
| 16:9 | 1920×1080 | 48–64px | 28–36px | 6% |
| 1:1 | 1080×1080 | 56–72px | 32–40px | 7% |

`#root` 内主内容保持在安全区内；字幕/角标贴边但不压主体。

## 背景层次（禁止空镜）

至少 2 层深度，但**克制**：

1. **基底**：`background: var(--vm-bg)` — solid 或极轻纸纹/颗粒（opacity ≤ 0.08）
2. **氛围**（可选 1 项）：单点 accent `radial-gradient` 偏移到角落，opacity ≤ 0.12
3. **内容层**：文字 / 图形 / video 底片

**禁止**全屏对角线性渐变作为主背景。

## 字体与层级

- 主标题：粗（700–900），一行优先，过长换行 ≤2 行
- 副标/说明：`--vm-muted`，字号 ≥ 主标题的 45%
- 禁止整屏密集小字（正文级 < 24px on 9:16）

## finish 模式（有 video 底片）

- 底片 `<video>` 占主视觉底层，全屏或 primary layer
- overlay：lower third、细字幕条、角标 — **细**、半透明或实色条，非大卡片
- 遵守 `do_not_replace_base_media`：不用全屏色块盖住底片

## variant 密度

| variantOverrides | 画面 |
|----------------|------|
| `polishStyle: minimal` / `overlayDensity: low` | 少装饰，多留底片/留白 |
| `polishStyle: rich` / `overlayDensity: high` | 可多 lower third、角标、对比行 — **仍遵守 ANTI-AI 禁止项** |
