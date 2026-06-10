---
name: videomaker-visual-craft
description: 槽位画面审美、反 AI 视觉指纹与内容驱动动效。触发：任何 template=composition 或 HF 包装 slot。
---

# VideoMaker Visual Craft

## When to use

- 任何 `template=composition` 的 MaterialSpec 创作
- `finishBrief` 润色（`source_then_polish` / `hf_native`）
- 需要自定义 HTML + GSAP，而非 ken-burns 兜底时

**与 `videomaker-composition` 并列必读**：前者管交卷与 lint；本 skill 管**画面好不好看、像不像 AI 模板**。

## Priority stack

1. **`visualStyleBible.avoid`** — 全片硬禁止项（即使 palette 未写明也不能违反）
2. **`visualStyleBible`** — palette / lighting / mood / cameraGrammar 锁定全片气质
3. **`brandColors`** — 品牌色与 bible 调和，不单独发明第二套 accent
4. 本 skill 默认审美 — 填补 bible 未写的构图与动效纪律

HyperFrames 通用 house-style 见 `skills/public/hyperframes/house-style.md`；卡壳时可 `skill_view` 补充阅读。

## Required reads (before `submit_material_spec`)

按顺序 `skill_view` 本目录 references（有 `visualStyleBible` 时 **PALETTE 必读**）：

| 顺序 | 文件 | 何时 |
|------|------|------|
| 1 | `references/PALETTE-FROM-BIBLE.md` | payload 含 `visualStyleBible` |
| 2 | `references/SLOT-VISUAL-CRAFT.md` | 总是 |
| 3 | `references/MOTION-BY-CONTENT.md` | 有 `timelineScript` 时 |
| 4 | `references/ANTI-AI-FINGERPRINTS.md` | 总是（交卷前再过一遍） |

路径前缀：`skills/private/videomaker-visual-craft/`

## CSS variable contract

在 `composition.styles` **顶部**声明（见 PALETTE-FROM-BIBLE）：

```css
:root {
  --vm-bg: ...;
  --vm-fg: ...;
  --vm-accent: ...;
  --vm-muted: ...;
}
```

槽位内颜色优先用 `var(--vm-*)`，**禁止**随手写 `#7c3aed` / `#a855f7` 等默认紫。

## Pre-submit checklist (8 items)

交卷前逐项自查；任一项 fail 则改 HTML/CSS/GSAP 后再 `composition_lint_draft`：

- [ ] 背景为 solid / 轻纹理 / 单点低 opacity glow — **非**紫粉或蓝紫对角渐变
- [ ] 主构图不是「圆角卡片 + 彩色左边框」信息块
- [ ] 至少 **1 处**内容语义动效（数字/对比/揭示），非全场相同 fade/blur
- [ ] 主标题字号达到 `renderTarget` 对应档位下限
- [ ] 安全区内构图，未把文字压到边缘
- [ ] 无 emoji 图标、假 logo、假「10万+用户」类数据
- [ ] `--vm-*` 与 `visualStyleBible` 气质一致
- [ ] `durationSec` 内动画完成并 hold 末帧（见 videomaker-composition `slotTiming`）
